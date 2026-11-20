"""Evidence engine: records what was actually run or read, so that evidence levels
are derived from records instead of being declared by whoever writes the report.

Record kinds and the level they earn:
  command      -> Verified  (only if the captured output file exists and its hash matches)
  observation  -> Observed  (only if it cites a location)
  inference    -> Inferred
"""
import contextlib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .areas import AREAS
from .policy import check_command
from .secrets import mask_text

# Commands that only read files. Capturing their output shows what the files contain
# (Observed); it does not show that anything works, so it never counts as Verified.
INSPECTION = re.compile(r"^\s*(?:grep|egrep|fgrep|rg|ag|cat|head|tail|wc|ls|tree|find|stat|file|jq|awk|sed\s+-n|"
                        r"git\s+(?:ls-files|log|show|status|diff|grep|blame|rev-parse|branch))\b")
LOG_NAME = "evidence-log.json"
KINDS = ("command", "observation", "inference")
ID_RX = re.compile(r"^E-\d{3,}$")
MAX_OUTPUT = 200_000


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit(project_dir):
    """Read the checked-out commit without needing the git binary."""
    try:
        git = Path(project_dir) / ".git"
        if git.is_file():  # worktree / submodule pointer
            git = (Path(project_dir) / git.read_text().split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text().strip()
        if not head.startswith("ref:"):
            return head[:40]
        ref = head.split(" ", 1)[1].strip()
        ref_file = git / ref
        if ref_file.exists():
            return ref_file.read_text().strip()[:40]
        packed = git / "packed-refs"
        if packed.exists():
            for line in packed.read_text().splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0][:40]
    except (OSError, IndexError):
        pass
    return None


def worktree_state(project_dir):
    """Branch and whether there are uncommitted changes, so a record made on edited-but-uncommitted
    code is not mistaken for evidence about the commit. None when git is not available."""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--branch"], cwd=project_dir, capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    lines = out.stdout.splitlines()
    branch = lines[0][3:].split("...")[0] if lines and lines[0].startswith("## ") else None
    dirty = [ln for ln in lines[1:] if "enterprise-review" not in ln]
    return {"branch": branch, "uncommitted_changes": bool(dirty)}


@contextlib.contextmanager
def _locked(review_dir):
    """One writer at a time for the evidence log, so parallel experts cannot overwrite each
    other's records. A lock directory is atomic to create on every platform."""
    lock = Path(review_dir) / "evidence-log.lock"
    Path(review_dir).mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 60
    while True:
        try:
            lock.mkdir()
            break
        except (FileExistsError, PermissionError):
            # PermissionError: on Windows a folder that another process is just removing
            # cannot be created for a moment. Either way: someone holds the lock, wait.
            try:
                if time.time() - lock.stat().st_mtime > 120:     # left behind by a crashed run
                    lock.rmdir()
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("the evidence log is locked by another run") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        for _ in range(40):
            try:
                lock.rmdir()
                break
            except FileNotFoundError:
                break
            except OSError:
                time.sleep(0.05)


def _append(review_dir, build):
    """Allocate the next id and store the record built for it, atomically."""
    with _locked(review_dir):
        log = load_log(review_dir)
        record = build(_next_id(log))
        log["records"].append(record)
        _save_log(review_dir, log)
    return record


def _replace(review_dir, record):
    with _locked(review_dir):
        log = load_log(review_dir)
        log["records"] = [record if r.get("id") == record["id"] else r for r in log["records"]]
        _save_log(review_dir, log)
    return record


def load_log(review_dir):
    path = Path(review_dir) / LOG_NAME
    if not path.exists():
        return {"schema_version": 2, "records": []}
    log = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(log, dict) or not isinstance(log.get("records"), list):
        raise ValueError("evidence-log.json is malformed: expected an object with a 'records' list")
    return log


def _save_log(review_dir, log):
    path = Path(review_dir) / LOG_NAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    for attempt in range(40):
        try:
            tmp.replace(path)
            return
        except PermissionError:      # Windows: the file is briefly open elsewhere (a reader, a virus scanner)
            if attempt == 39:
                raise
            time.sleep(0.05)


def _next_id(log):
    nums = [int(r["id"][2:]) for r in log["records"] if ID_RX.match(str(r.get("id", "")))]
    return f"E-{(max(nums) + 1 if nums else 1):03d}"


def _tool_version(argv, cwd):
    try:
        out = subprocess.run([argv[0], "--version"], cwd=cwd, capture_output=True, text=True, timeout=10)
        lines = (out.stdout or out.stderr).strip().splitlines()
        return lines[0][:120] if lines else None
    except (OSError, subprocess.SubprocessError):
        return None


def _check_area(area):
    if area not in AREAS:
        raise ValueError(f"area must be 1-23, got {area!r}")


def run_command(review_dir, area, title, argv, cwd=".", timeout=900, approved=False, also_areas=(),
                outputs=(), project=None):
    """Run a command (no shell), store its masked output, and append a record."""
    _check_area(area)
    for extra in also_areas:
        _check_area(extra)
    if not argv:
        raise ValueError("no command given")
    reason = check_command(argv)
    if reason and not approved:
        raise PermissionError(
            f"Refused: this command {reason}. Get the user's explicit approval, then re-run with --approved.")
    review = Path(review_dir)
    (review / "evidence").mkdir(parents=True, exist_ok=True)
    # Reserve the id first, so runs started in parallel never share one.
    eid = _append(review, lambda i: {"id": i, "kind": "pending", "area": area, "title": title})["id"]
    started, t0 = _now(), time.monotonic()
    timed_out = False
    # Checks must not litter the project being assessed with caches.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              errors="replace", stdin=subprocess.DEVNULL, env=env)
        exit_code, output = proc.returncode, (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    except subprocess.TimeoutExpired as exc:
        timed_out, exit_code = True, None
        output = f"[timed out after {timeout}s]\n" + (exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
    except FileNotFoundError:
        exit_code, output = 127, f"[command not found: {argv[0]}]"
    duration = round(time.monotonic() - t0, 2)
    output = mask_text(output)
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT // 2] + "\n…[truncated]…\n" + output[-MAX_OUTPUT // 2:]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "command"
    artifact = review / "evidence" / f"{eid}-{slug}.txt"
    header = f"$ {mask_text(' '.join(argv))}\n# cwd: {cwd}\n# started: {started}  exit: {exit_code}  duration: {duration}s\n\n"
    artifact.write_text(header + output, encoding="utf-8")
    record = {
        "id": eid, "kind": "command", "area": area, "title": title,
        "command": mask_text(" ".join(argv)), "exit_code": exit_code, "timed_out": timed_out,
        "started_at": started, "duration_s": duration,
        "tool_version": _tool_version(argv, cwd), "runner": f"python {platform.python_version()} on {sys.platform}",
        "commit": git_commit(project or cwd), "artifact": f"evidence/{artifact.name}", "sha256": sha256_file(artifact),
        "approved_risky_command": bool(reason),
    }
    if outputs:
        # Files the command was meant to produce (a screenshot, a report). They become part of
        # the record: a missing or later-modified output makes the record unusable.
        record["outputs"] = []
        for out in outputs:
            path = Path(out).resolve()
            if review.resolve() not in path.parents:
                raise ValueError(f"--output must be inside the review folder: {out}")
            rel = path.relative_to(review.resolve()).as_posix()
            record["outputs"].append({"path": rel, "sha256": sha256_file(path) if path.is_file() else None})
    state = worktree_state(project or cwd)
    if state:
        record.update(state)
    if also_areas:
        record["also_areas"] = sorted(set(also_areas) - {area})
    return _replace(review, record)


def share(review_dir, evidence_id, areas):
    """Let more areas cite a record that already exists."""
    for a in areas:
        _check_area(a)
    with _locked(review_dir):
        log = load_log(review_dir)
        rec = next((r for r in log["records"] if r.get("id") == evidence_id), None)
        if rec is None:
            raise ValueError(f"no evidence record {evidence_id}")
        rec["also_areas"] = sorted((set(rec.get("also_areas", [])) | set(areas)) - {rec.get("area")})
        _save_log(review_dir, log)
    return rec


def add_note(review_dir, area, title, kind, detail, location=None, project_dir=None):
    """Record something read in the code (observation) or reasoned (inference)."""
    _check_area(area)
    if kind not in ("observation", "inference"):
        raise ValueError("kind must be observation or inference")
    if kind == "observation" and not location:
        raise ValueError("an observation must cite a location (path or path:line)")
    review = Path(review_dir)
    review.mkdir(parents=True, exist_ok=True)
    record = {"id": None, "kind": kind, "area": area, "title": title,
              "detail": mask_text(detail or ""), "location": location, "recorded_at": _now(),
              "commit": git_commit(project_dir) if project_dir else None}
    if location and re.match(r"https?://", location):
        if kind != "observation":
            raise ValueError("a web source is recorded as an observation")
        record.update(source_url=location, checked_at=_now()[:10],
                      note="external source as read on this date; it shows what the page said, not that it is right")
    elif kind == "observation" and project_dir:
        target = Path(project_dir) / re.sub(r":\d+(-\d+)?$", "", location)
        record["location_exists"] = target.exists()
        if not target.exists():
            raise ValueError(f"location does not exist in the project: {location}")
    return _append(review, lambda i: dict(record, id=i))


def record_level(record, review_dir):
    """The evidence level a record has earned, plus a problem description if it is broken."""
    kind = record.get("kind")
    if kind == "command":
        artifact = record.get("artifact")
        if not artifact:
            return None, "command record has no artifact"
        path = (Path(review_dir) / artifact).resolve()
        if Path(review_dir).resolve() not in path.parents:
            return None, "artifact path escapes the review folder"
        if not path.is_file():
            return None, f"artifact file is missing: {artifact}"
        if sha256_file(path) != record.get("sha256"):
            return None, f"artifact was modified after capture: {artifact}"
        if not record.get("command") or not record.get("started_at"):
            return None, "command record lacks command or timestamp"
        for out in record.get("outputs", []):
            target = Path(review_dir) / out["path"]
            if out.get("sha256") is None or not target.is_file():
                return None, f"the command did not produce its output file: {out['path']}"
            if sha256_file(target) != out["sha256"]:
                return None, f"output file was modified after capture: {out['path']}"
        if INSPECTION.match(record["command"]):
            return "observed", None      # a captured search or listing: what the files say, not proof it works
        return "verified", None
    if kind == "observation":
        if not record.get("location"):
            return None, "observation has no location"
        return "observed", None
    if kind == "inference":
        return "inferred", None
    if kind == "pending":
        return None, "the command was started but never finished recording (interrupted run)"
    return None, f"unknown evidence kind {kind!r}"


def add_artifact(review_dir, area, title, command, artifact_path, exit_code=0, commit=None, also_areas=()):
    """Register a file produced by a run of ours (e.g. benchmark results) as command evidence."""
    _check_area(area)
    review = Path(review_dir)
    artifact = Path(artifact_path).resolve().relative_to(review.resolve()).as_posix()
    record = {"id": None, "kind": "command", "area": area, "title": title, "command": command,
              "exit_code": exit_code, "timed_out": False, "started_at": _now(),
              "runner": f"python {platform.python_version()} on {sys.platform}", "commit": commit,
              "artifact": artifact, "sha256": sha256_file(review / artifact), "approved_risky_command": False}
    if also_areas:
        record["also_areas"] = sorted(set(also_areas) - {area})
    return _append(review, lambda i: dict(record, id=i))


def refresh_hash(review_dir, evidence_id):
    """Re-hash an artifact that the engine itself has just finished writing."""
    with _locked(review_dir):
        log = load_log(review_dir)
        for rec in log["records"]:
            if rec["id"] == evidence_id:
                rec["sha256"] = sha256_file(Path(review_dir) / rec["artifact"])
        _save_log(review_dir, log)
