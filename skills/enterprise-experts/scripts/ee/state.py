"""Review state: which expert areas are pending, running, done or failed, so an
interrupted review can resume instead of starting over."""
import json
from datetime import datetime, timezone
from pathlib import Path

from .areas import AREAS, MODES, WAVES, required_areas

STATE_NAME = "review-state.json"
STATUSES = ("pending", "in_progress", "done", "failed", "skipped")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path(review_dir):
    return Path(review_dir) / STATE_NAME


def load(review_dir):
    return json.loads(_path(review_dir).read_text(encoding="utf-8"))


def _save(review_dir, state):
    state["updated_at"] = _now()
    path = _path(review_dir)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)  # atomic: an interrupted write never leaves a half-written state file
    return state


def init(review_dir, mode, scope=None):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}")
    areas = required_areas(mode, scope)
    if not areas or not areas <= set(AREAS):
        raise ValueError("focused mode needs --scope with area ids 1-23")
    if _path(review_dir).exists():
        raise FileExistsError("a review is already in progress here; use 'state show' to resume it")
    Path(review_dir).mkdir(parents=True, exist_ok=True)
    return _save(review_dir, {"mode": mode, "scope": sorted(areas), "created_at": _now(), "phase": "assessment", "approvals": [],
                              "approved_commands": [],
                              "areas": {str(a): {"status": "pending"} for a in sorted(areas)}})


def set_status(review_dir, area, status, note=None):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {list(STATUSES)}")
    state = load(review_dir)
    if str(area) not in state["areas"]:
        raise ValueError(f"area {area} is not in this review's scope")
    entry = state["areas"][str(area)]
    entry.update({"status": status, "at": _now()})
    if note:
        entry["note"] = note
    return _save(review_dir, state)


def plan(state):
    """Dependency-aware view: the areas that can run now are the unfinished ones in
    the earliest wave that still has work. Areas left 'in_progress' were interrupted."""
    scope = {int(a) for a in state["areas"]}
    st = {int(a): v["status"] for a, v in state["areas"].items()}
    out = {"ready": [], "interrupted": [], "blocked": [], "done": [], "failed": [], "wave": None}
    earlier_open = False
    for wave, ids in WAVES:
        mine = [a for a in ids if a in scope]
        open_here = [a for a in mine if st[a] in ("pending", "in_progress", "failed")]
        for a in mine:
            if st[a] in ("done", "skipped"):
                out["done"].append(a)
            elif earlier_open:
                out["blocked"].append(a)
            elif st[a] == "in_progress":
                out["interrupted"].append(a)
            elif st[a] == "failed":
                out["failed"].append(a)
            else:
                out["ready"].append(a)
        if open_here and not earlier_open:
            out["wave"], earlier_open = wave, True
    out["complete"] = not earlier_open
    return out


def approve(review_dir, approved_by, findings=(), paths=(), command=None, note=None):
    """Record a decision the user made. Without a name there is nothing to audit."""
    if not approved_by or not str(approved_by).strip():
        raise ValueError("an approval needs --by <who approved it>")
    if not command and not paths:
        raise ValueError("an approval needs --paths (files a fix may touch) or --command (one exact command)")
    state = load(review_dir)
    entry = {"approved_by": approved_by.strip(), "at": _now(), "note": note}
    if command:
        state.setdefault("approved_commands", []).append(dict(entry, command=command))
    else:
        state.setdefault("approvals", []).append(dict(entry, findings=list(findings), paths=list(paths)))
    return _save(review_dir, state)


def set_phase(review_dir, phase):
    if phase not in ("assessment", "remediation"):
        raise ValueError("phase must be assessment or remediation")
    state = load(review_dir)
    if phase == "remediation" and not state.get("approvals"):
        raise ValueError("cannot enter remediation: no approval has been recorded")
    state["phase"] = phase
    return _save(review_dir, state)


def close(review_dir):
    state = load(review_dir)
    state["closed"] = True
    return _save(review_dir, state)
