"""Compare two reviews of the same project (trend and drift), and a deterministic
gate for unattended runs (CI, schedules).

Neither needs an AI model. A scheduled job can run `gate` on every pull request and
`trend` whenever a new review is committed; the full expert review itself still
needs Claude and a person to answer its questions.
"""
import json
from pathlib import Path

from . import scoring
from .discovery import discover

RANK = {"GO": 0, "CONDITIONAL GO": 1, "NO-GO": 2}
SEVERE = ("critical", "high")


def _findings(review):
    try:
        data = json.loads((Path(review) / "findings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for a in data.get("areas", []) if isinstance(data, dict) else []:
        for f in (a.get("findings") or []) if isinstance(a, dict) else []:
            if isinstance(f, dict) and f.get("id"):
                out[f["id"]] = dict(f, area=a.get("id"))
    return out


def trend(previous_dir, current_dir):
    old, new = scoring.evaluate(previous_dir), scoring.evaluate(current_dir)
    of, nf = _findings(previous_dir), _findings(current_dir)

    def is_open(f):
        return f.get("status") in ("open", "accepted", "pending_decision")
    by_title_old = {(f.get("area"), f.get("title")): i for i, f in of.items()}
    matched = {}
    for i, f in nf.items():                      # same ID, or same area and title if IDs were renumbered
        matched[i] = i if i in of else by_title_old.get((f.get("area"), f.get("title")))
    carried = {v for v in matched.values() if v}
    new_open = [f for i, f in nf.items() if is_open(f) and not matched[i]]
    resolved = [dict(of[matched[i]], now=f.get("status")) for i, f in nf.items()
                if matched[i] and is_open(of[matched[i]]) and not is_open(f)]
    gone = [f for i, f in of.items() if is_open(f) and i not in carried]
    still = [f for i, f in nf.items() if matched[i] and is_open(f) and is_open(of[matched[i]])]
    old_rows, new_rows = ({r["id"]: r for r in x["rows"]} for x in (old, new))
    areas = []
    for aid in sorted(set(old_rows) | set(new_rows)):
        o, n = old_rows.get(aid), new_rows.get(aid)
        before, after = (o or {}).get("final"), (n or {}).get("final")
        areas.append({"id": aid, "name": (n or o)["name"], "before": before, "after": after,
                      "change": after - before if None not in (before, after) else None,
                      "basis_before": (o or {}).get("basis"), "basis_after": (n or {}).get("basis")})
    regressions = []
    if old["valid"] and new["valid"] and RANK[new["decision"]] > RANK[old["decision"]]:
        regressions.append(f"decision worsened from {old['decision']} to {new['decision']}")
    if not new["valid"]:
        regressions.append("the current review is invalid")
    regressions += [f"new {f['severity']} finding {f['id']}: {f.get('title')}" for f in new_open if f.get("severity") in SEVERE]
    regressions += [f"{a['name']} dropped {-a['change']} points" for a in areas if a["change"] is not None and a["change"] <= -10]
    out = {"previous": {"dir": str(previous_dir), "date": old.get("review_date"), "decision": old["decision"],
                        "valid": old["valid"], "overall": old["overall"]},
           "current": {"dir": str(current_dir), "date": new.get("review_date"), "decision": new["decision"],
                       "valid": new["valid"], "overall": new["overall"]},
           "areas": areas, "new_findings": new_open, "resolved_findings": resolved, "still_open": still,
           "no_longer_reported": gone, "regressions": regressions}
    cur = Path(current_dir)
    (cur / "trend.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    (cur / "trend.md").write_text(trend_markdown(out), encoding="utf-8")
    return out


def trend_markdown(t):
    def fmt(v):
        return "—" if v is None else v
    p, c = t["previous"], t["current"]
    o = ["# Review trend", "",
         f"| | Previous ({p['date']}) | Current ({c['date']}) |", "|---|---|---|",
         f"| Decision | {p['decision'] if p['valid'] else 'INVALID'} | {c['decision'] if c['valid'] else 'INVALID'} |",
         f"| Overall score | {fmt(p['overall'])} | {fmt(c['overall'])} |", "",
         "| # | Area | Before | After | Change | Evidence basis |", "|---|---|---|---|---|---|"]
    o += [f"| {a['id']} | {a['name']} | {fmt(a['before'])} | {fmt(a['after'])} | "
          f"{'—' if a['change'] is None else format(a['change'], '+d')} | {fmt(a['basis_before'])} → {fmt(a['basis_after'])} |"
          for a in t["areas"]]
    for title, items in (("Regressions", t["regressions"]),):
        o += ["", f"## {title}", ""] + ([f"- {x}" for x in items] or ["- none"])
    for title, key in (("New findings", "new_findings"), ("Resolved", "resolved_findings"), ("Still open", "still_open"),
                       ("Open before, not reported now (check they were really fixed)", "no_longer_reported")):
        o += ["", f"## {title} ({len(t[key])})", ""] + [f"- [{f.get('severity')}] {f.get('id')}: {f.get('title')}" for f in t[key]]
    return "\n".join(o) + "\n"


def gate(project_dir, baseline=None, exclude=()):
    """Deterministic pre-checks that need no model: committed secrets, text aimed at AI
    reviewers, and (against a baseline discovery.json) things that got worse."""
    d = discover(project_dir, exclude)

    def keep(path):
        return not any(path == e or path.startswith(e.rstrip("/") + "/") for e in exclude)
    secrets = [s for s in d["secrets"] if not s.get("in_example_file") and keep(s["file"])]
    injections = [s for s in d["prompt_injection_suspects"] if keep(s["file"])]
    failures = [f"possible committed secret: {s['file']}:{s['line']} ({s['type']})" for s in secrets]
    failures += [f"text addressed to an AI reviewer: {s['file']}:{s['line']}" for s in injections]
    warnings = []
    if baseline:
        base = json.loads(Path(baseline).read_text(encoding="utf-8"))
        if base.get("test_files", 0) and d["test_files"] < base["test_files"]:
            failures.append(f"test files dropped from {base['test_files']} to {d['test_files']}")
        if base.get("ci") and not d["ci"]:
            failures.append("CI configuration was removed")
        if base.get("lockfiles") and not d["lockfiles"]:
            failures.append("lockfiles were removed")
        for key in ("frameworks", "paid_services", "ai_libraries"):
            added = sorted(set(d.get(key, [])) - set(base.get(key, [])))
            if added:
                warnings.append(f"new {key.replace('_', ' ')}: {', '.join(added)} (re-run the affected experts)")
        new_stacks = sorted({s["path"] for s in d["stacks"]} - {s["path"] for s in base.get("stacks", [])})
        if new_stacks:
            warnings.append("new stacks: " + ", ".join(new_stacks))
    return {"passed": not failures, "failures": failures, "warnings": warnings,
            "checked": {"secrets": len(secrets), "prompt_injection": len(injections), "baseline": bool(baseline)}}
