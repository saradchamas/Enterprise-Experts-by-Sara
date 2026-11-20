"""Assemble the Final Engineering Delivery Package from a review folder.

It only organises what the review actually produced. Anything the review did not
produce is listed in MANIFEST.md as not available; nothing is generated to fill a gap.
"""
import json
import shutil
from pathlib import Path

from . import __version__, report, scoring
from .areas import AREAS

OUT = "FINAL-ENGINEERING-DELIVERY"
# section -> (description, [(glob in review folder, destination subfolder)])
LAYOUT = [
    ("00-executive-summary", "Decision, scores and the health report", [
        ("FINAL-PROJECT-HEALTH-REPORT.md", ""), ("scorecard.md", ""), ("scorecard.html", ""), ("scorecard.json", "")]),
    ("01-architecture", "Architecture deliverable and generated diagrams", [
        ("01-architecture.md", ""), ("graphs/*.md", "graphs")]),
    ("02-expert-assessments", "One report per expert area in scope", [("[0-2][0-9]-*.md", "")]),
    ("03-security", "Security audit, data governance and compliance gaps", [
        ("02-security.md", ""), ("14-data-governance.md", ""), ("19-compliance.md", "")]),
    ("04-code-quality", "Technical leadership review and debt register", [("22-technical-leadership.md", "")]),
    ("05-performance", "Benchmarks: baseline, candidate, comparison", [
        ("03-performance.md", ""), ("04-scalability.md", ""), ("benchmarks/*", "benchmarks")]),
    ("06-testing", "QA report", [("09-quality-assurance.md", "")]),
    ("07-infrastructure", "DevOps, infrastructure, monitoring, recovery", [
        ("10-devops.md", ""), ("11-infrastructure.md", ""), ("08-observability.md", ""),
        ("07-disaster-recovery.md", ""), ("18-incident-management.md", "")]),
    ("08-improvements", "Approved changes and their verification", [("change-log.md", ""), ("remediation-plan.md", "")]),
    ("09-documentation", "Documentation deliverable", [("17-documentation.md", "")]),
    ("10-evidence", "Evidence index and captured output", [
        ("evidence-log.json", ""), ("evidence/*", "execution-logs"), ("intake.json", ""),
        ("discovery.json", ""), ("discovery.md", ""), ("review-state.json", "")]),
]
NOT_IMPLEMENTED = ["PDF export of the health report", "Excel export", "interactive dashboard", "SBOM of the reviewed project"]


def build(review_dir):
    review = Path(review_dir)
    res = scoring.evaluate(review)
    report.write_all(res, review)
    out = review / OUT
    if out.exists():
        shutil.rmtree(out)
    manifest = [f"# Final Engineering Delivery — {res.get('project') or 'project'}", "",
                f"Decision: **{'INVALID REVIEW — NO-GO' if not res['valid'] else res['decision']}**  |  "
                f"Overall: {res['overall'] if res['overall'] is not None else 'n/a'}/100  |  "
                f"Review date: {res.get('review_date')}  |  Engine {__version__}", "",
                "Only artifacts this review actually produced are included. Missing items are listed, not invented.", ""]
    summary = {"sections": {}, "missing": []}
    for section, desc, sources in LAYOUT:
        copied, missing = [], []
        for pattern, sub in sources:
            matches = sorted(p for p in review.glob(pattern) if p.is_file())
            if not matches:
                missing.append(pattern)
            for src in matches:
                dst = out / section / sub / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(dst.relative_to(out).as_posix())
        manifest += [f"## {section} — {desc}", ""]
        manifest += [f"- `{c}`" for c in copied] or ["- nothing produced for this section"]
        manifest += [f"- not available: `{m}` (not produced in this review)" for m in missing] + [""]
        summary["sections"][section] = copied
        summary["missing"] += [f"{section}/{m}" for m in missing]
    rows = {r["id"]: r for r in res["rows"]}
    manifest += ["## Areas", "", "| # | Area | Status | Final score |", "|---|---|---|---|"]
    manifest += [f"| {a} | {n} | {rows[a]['status'] if a in rows else 'not in this review'} | "
                 f"{rows[a]['final'] if a in rows and rows[a]['final'] is not None else '—'} |" for a, n in AREAS.items()]
    manifest += ["", "## Not implemented in this version of the toolkit", ""] + [f"- {x}" for x in NOT_IMPLEMENTED] + [""]
    decision = ["# Release decision", "", report.to_markdown(res).split("\n", 2)[2]]
    (out / "00-executive-summary").mkdir(parents=True, exist_ok=True)
    (out / "00-executive-summary" / "release-decision.md").write_text("\n".join(decision), encoding="utf-8")
    (out / "MANIFEST.md").write_text("\n".join(manifest), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(dict(summary, decision=res["decision"], valid=res["valid"]), indent=2),
                                       encoding="utf-8")
    return dict(summary, path=str(out), decision=res["decision"], valid=res["valid"])
