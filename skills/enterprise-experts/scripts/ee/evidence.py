"""Evidence engine: records what was actually run or read, so that evidence levels
are derived from records instead of being declared by whoever writes the report.

Record kinds and the level they earn:
  command      -> Verified  (only if the captured output file exists and its hash matches)
  observation  -> Observed  (only if it cites a location)
  inference    -> Inferred
"""
import hashlib
import json
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


def load_log(review_dir):
    path = Path(review_dir) / LOG_NAME
    if not path.exists():
        return {"schema_version": 2, "records": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_log(review_dir, log):
    path = Path(review_dir) / LOG_NAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


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


def run_command(review_dir, area, title, argv, cwd=".", timeout=900, approved=False, also_areas=()):
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
    log = load_log(review)
    eid = _next_id(log)
    started, t0 = _now(), time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              errors="replace", stdin=subprocess.DEVNULL)
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
        "commit": git_commit(cwd), "artifact": f"evidence/{artifact.name}", "sha256": sha256_file(artifact),
        "approved_risky_command": bool(reason),
    }
    if also_areas:
        record["also_areas"] = sorted(set(also_areas) - {area})
    log["records"].append(record)
    _save_log(review, log)
    return record


def add_note(review_dir, area, title, kind, detail, location=None, project_dir=None):
    """Record something read in the code (observation) or reasoned (inference)."""
    _check_area(area)
    if kind not in ("observation", "inference"):
        raise ValueError("kind must be observation or inference")
    if kind == "observation" and not location:
        raise ValueError("an observation must cite a location (path or path:line)")
    review = Path(review_dir)
    review.mkdir(parents=True, exist_ok=True)
    log = load_log(review)
    record = {"id": _next_id(log), "kind": kind, "area": area, "title": title,
              "detail": mask_text(detail or ""), "location": location, "recorded_at": _now(),
              "commit": git_commit(project_dir) if project_dir else None}
    if kind == "observation" and project_dir:
        target = Path(project_dir) / re.sub(r":\d+(-\d+)?$", "", location)
        record["location_exists"] = target.exists()
        if not target.exists():
            raise ValueError(f"location does not exist in the project: {location}")
    log["records"].append(record)
    _save_log(review, log)
    return record


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
        if INSPECTION.match(record["command"]):
            return "observed", None      # a captured search or listing: what the files say, not proof it works
        return "verified", None
    if kind == "observation":
        if not record.get("location"):
            return None, "observation has no location"
        return "observed", None
    if kind == "inference":
        return "inferred", None
    return None, f"unknown evidence kind {kind!r}"


def add_artifact(review_dir, area, title, command, artifact_path, exit_code=0, commit=None):
    """Register a file produced by a run of ours (e.g. benchmark results) as command evidence."""
    _check_area(area)
    review = Path(review_dir)
    log = load_log(review)
    artifact = Path(artifact_path).resolve().relative_to(review.resolve()).as_posix()
    record = {"id": _next_id(log), "kind": "command", "area": area, "title": title, "command": command,
              "exit_code": exit_code, "timed_out": False, "started_at": _now(),
              "runner": f"python {platform.python_version()} on {sys.platform}", "commit": commit,
              "artifact": artifact, "sha256": sha256_file(review / artifact), "approved_risky_command": False}
    log["records"].append(record)
    _save_log(review, log)
    return record


def refresh_hash(review_dir, evidence_id):
    """Re-hash an artifact that the engine itself has just finished writing."""
    log = load_log(review_dir)
    for rec in log["records"]:
        if rec["id"] == evidence_id:
            rec["sha256"] = sha256_file(Path(review_dir) / rec["artifact"])
    _save_log(review_dir, log)
