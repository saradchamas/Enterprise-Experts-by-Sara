#!/usr/bin/env python3
"""Apply the Enterprise Experts scoring caps and Go/No-Go rules to findings.json.

Usage: python scorecard.py <findings.json> [--out scorecard.md]

Prints a markdown scorecard and the decision; also writes scorecard.json next to
the output file. Rules are documented in references/evidence-and-scoring.md.
"""
import argparse
import json
import sys
from pathlib import Path

CORE = {2, 5, 6, 7, 9, 10}
WEIGHT = {a: 2 for a in CORE}
OPEN = {"open"}


def evaluate(data):
    rows, blockers, conditions = [], [], []
    wsum = wtot = 0
    for area in sorted(data.get("areas", []), key=lambda a: a.get("id", 0)):
        aid, name = area.get("id"), area.get("name", "?")
        status = area.get("status", "assessed")
        findings = area.get("findings", [])
        open_f = [f for f in findings if f.get("status", "open") in OPEN]
        accepted = [f for f in findings if f.get("status") == "accepted"]
        crit = [f for f in open_f if f.get("severity") == "critical"]
        high = [f for f in open_f if f.get("severity") == "high"]
        levels = {str(lv).lower() for lv in area.get("evidence_levels", [])}
        levels |= {str(f.get("evidence_level", "")).lower() for f in findings}
        levels.discard("")
        is_core = aid in CORE

        if status in ("not_assessed", "not_applicable"):
            rows.append([aid, name, status, "—", "—", "", len(crit), len(high), "—"])
            if status == "not_assessed" and is_core:
                blockers.append(f"Core area {aid} {name} was not assessed")
            for f in crit:
                blockers.append(f"{f.get('id')} ({name}): {f.get('title')}")
            continue

        raw = area.get("score")
        if raw is None:
            rows.append([aid, name, status, "missing", "—", "no score given", len(crit), len(high), "—"])
            if is_core:
                blockers.append(f"Core area {aid} {name} has no score")
            continue

        final, reasons = float(raw), []

        def cap(limit, why):
            nonlocal final
            if final > limit:
                final = limit
                reasons.append(why)

        if crit:
            cap(40, f"{len(crit)} open Critical")
        if high:
            cap(70, f"{len(high)} open High")
        verified = "verified" in levels
        if levels and levels <= {"inferred", "not assessed", "not_assessed"}:
            cap(50, "inferred evidence only")
            basis = "Inferred"
        elif not verified:
            cap(75, "no Verified evidence")
            basis = "Unverified"
        else:
            basis = "Verified"

        w = WEIGHT.get(aid, 1)
        wsum += final * w
        wtot += w
        rows.append([aid, name, status, int(raw), int(round(final)), "; ".join(reasons), len(crit), len(high), basis])

        for f in crit:
            blockers.append(f"{f.get('id')} ({name}): {f.get('title')}")
        for f in high:
            conditions.append(f"Open High {f.get('id')} ({name}): {f.get('title')}")
        for f in accepted:
            if f.get("severity") in ("critical", "high") and not f.get("mitigation"):
                conditions.append(f"{f.get('id')} ({name}) accepted without a recorded mitigation")
        if is_core:
            if final < 60:
                blockers.append(f"Core area {aid} {name} scored {int(round(final))} (< 60)")
            elif final < 80:
                conditions.append(f"Core area {aid} {name} scored {int(round(final))} (< 80)")
            if basis != "Verified":
                conditions.append(f"Core area {aid} {name} has no Verified evidence")

    overall = round(wsum / wtot) if wtot else None
    decision = "NO-GO" if blockers else ("CONDITIONAL GO" if conditions else "GO")
    if overall is None:
        decision = "NO-GO"
        blockers.append("No area was scored")
    return {"decision": decision, "overall": overall, "rows": rows,
            "blockers": blockers, "conditions": conditions}


def to_markdown(data, res):
    out = [f"# Scorecard — {data.get('project', 'Project')}", "",
           f"**Decision: {res['decision']}**  |  **Overall score: {res['overall'] if res['overall'] is not None else 'n/a'}/100**"
           f"  |  Review date: {data.get('review_date', '?')}  |  Mode: {data.get('mode', '?')}", "",
           "| # | Area | Status | Expert score | Final score | Cap applied | Open Critical | Open High | Evidence basis |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        star = " ★" if r[0] in CORE else ""
        out.append(f"| {r[0]} | {r[1]}{star} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[8]} |")
    out += ["", "★ = core readiness area (weight 2; must be assessed, verified and ≥ 80 for GO).", ""]
    if res["blockers"]:
        out += ["## Blockers (reasons for NO-GO)", ""] + [f"- {b}" for b in res["blockers"]] + [""]
    if res["conditions"]:
        out += ["## Conditions (to move to GO)", ""] + [f"- {c}" for c in res["conditions"]] + [""]
    if not res["blockers"] and not res["conditions"]:
        out += ["All core areas are verified at 80+ with no open Critical or High findings.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings")
    ap.add_argument("--out")
    args = ap.parse_args()
    data = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    res = evaluate(data)
    md = to_markdown(data, res)
    if args.out:
        out = Path(args.out)
        out.write_text(md, encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
