"""Assemble the Final Engineering Delivery Package from a review folder.

It only organises what the review actually produced. Anything the review did not
produce is listed in MANIFEST.md as not available; nothing is generated to fill a gap.
"""
import json
import re
import shutil
from pathlib import Path

from . import __version__, export, report, research, scoring  # noqa: F401
from .areas import AREAS, required_areas

OUT = "FINAL-ENGINEERING-DELIVERY"
# section -> (description, [(glob in review folder, destination subfolder)])
EXPERT = ["0[1-9]-*.md", "1[0-9]-*.md", "2[0-3]-*.md"]
LAYOUT = [
    ("00-executive-summary", "Decision, scores and the health report", [
        ("FINAL-PROJECT-HEALTH-REPORT.md", ""), ("scorecard.md", ""), ("scorecard.html", ""), ("scorecard.json", ""),
        ("report.xlsx", ""), ("report.pdf", ""), ("trend.md", ""), ("00-scope-and-access.md", ""),
        ("scorecard-before-remediation.md", ""),
        ("capability-matrix.md", "")]),
    ("01-architecture", "Architecture deliverable and generated diagrams", [
        ("01-architecture.md", ""), ("graphs/*.md", "graphs")]),
    # Screenshots sit beside the expert reports so that the image links inside them keep working.
    ("02-expert-assessments", "One report per expert area in scope, with the screenshots they reference",
     [(p, "") for p in EXPERT] + [("screenshots/**/*", "screenshots")]),
    ("03-security", "Security audit, data governance and compliance gaps", [
        ("02-security.md", ""), ("14-data-governance.md", ""), ("19-compliance.md", ""), ("scans/*", "scans")]),
    ("04-code-quality", "Technical leadership review and debt register", [("22-technical-leadership.md", "")]),
    ("05-performance", "Benchmarks, scalability and cost", [
        ("03-performance.md", ""), ("04-scalability.md", ""), ("12-cost.md", ""), ("benchmarks/*", "benchmarks")]),
    ("06-testing", "QA report", [("09-quality-assurance.md", "")]),
    ("07-infrastructure", "DevOps, infrastructure, monitoring, recovery", [
        ("10-devops.md", ""), ("11-infrastructure.md", ""), ("08-observability.md", ""),
        ("07-disaster-recovery.md", ""), ("18-incident-management.md", "")]),
    ("08-improvements", "Approved changes and their verification", [("change-log.md", ""), ("remediation-plan.md", "")]),
    ("09-documentation", "Documentation deliverable", [("17-documentation.md", "")]),
    ("10-evidence", "Evidence index, captured output and working files", [
        ("evidence-log.json", ""), ("findings.json", ""), ("evidence/*", "execution-logs"), ("intake.json", ""),
        ("discovery.json", ""), ("discovery.md", ""), ("capability-matrix.json", ""), ("review-state.json", ""),
        ("research-log.md", ""), ("research.json", ""), ("checks/**/*", "checks"), ("probes/**/*", "probes")]),
]
OPTIONAL = {"scorecard-before-remediation.md", "report.xlsx", "report.pdf", "trend.md", "remediation-plan.md", "change-log.md", "research-log.md", "research.json",
            "capability-matrix.md", "capability-matrix.json", "00-scope-and-access.md"}
NOT_IMPLEMENTED = ["PDF of the full report with diagrams (report.pdf is a plain-text summary)", "SBOM of the reviewed project"]


def build(review_dir):
    review = Path(review_dir)
    export.export(review)                     # report.xlsx, report.pdf; also refreshes the scorecards
    res = scoring.evaluate(review)
    research_result = research.write_log(review) if (review / research.FILE_NAME).exists() else None
    out = review / OUT
    if out.exists():
        shutil.rmtree(out)
    manifest = [f"# Final Engineering Delivery — {res.get('project') or 'project'}", "",
                f"Decision: **{'INVALID REVIEW — NO-GO' if not res['valid'] else res['decision']}**  |  "
                f"Overall: {res['overall'] if res['overall'] is not None else 'n/a'}/100  |  "
                f"Review date: {res.get('review_date')}  |  Engine {__version__}", "",
                "Only artifacts this review actually produced are included. Missing items are listed, not invented.", ""]
    summary = {"sections": {}, "missing": [], "out_of_scope": []}
    try:
        data = json.loads((review / "findings.json").read_text(encoding="utf-8"))
        scope = required_areas(data.get("mode"), data.get("scope")) or set(AREAS)
    except (OSError, ValueError, AttributeError, TypeError):
        scope = set(AREAS)

    def in_scope(pattern):
        m = re.match(r"(\d\d)-", pattern)
        return not m or int(m.group(1)) in scope
    for section, desc, sources in LAYOUT:
        copied, missing = [], []
        for pattern, sub in sources:
            matches = sorted(p for p in review.glob(pattern) if p.is_file() and OUT not in p.parts)
            if not matches and not in_scope(pattern):
                summary["out_of_scope"].append(f"{section}/{pattern}")
                continue
            if not matches and "*" not in pattern and pattern not in OPTIONAL:
                missing.append(pattern)
            for src in matches:
                base = pattern.split("**")[0].split("*")[0].rstrip("/") if "**" in pattern else None
                inner = src.relative_to(review / base) if base else Path(src.name)
                dst = out / section / sub / inner
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(dst.relative_to(out).as_posix())
        manifest += [f"## {section} — {desc}", ""]
        manifest += [f"- `{c}`" for c in copied] or ["- nothing produced for this section"]
        manifest += [f"- not available: `{m}` (not produced in this review)" for m in missing] + [""]
        summary["sections"][section] = copied
        summary["missing"] += [f"{section}/{m}" for m in missing]
    if summary["out_of_scope"]:
        manifest += ["## Outside this review's scope", ""] + [f"- `{x}`" for x in summary["out_of_scope"]] + [""]
    if research_result:
        bad = research_result["problems"]
        manifest += ["## Research and proposals", "",
                     f"- {research_result['sources']} dated sources, {research_result['proposals']} proposals, "
                     f"{len(research_result['supported'])} supported (see `research-log.md`)"]
        manifest += [f"- must not be acted on yet: {k} — {'; '.join(v)}" for k, v in bad.items()] + [""]
        summary["research"] = {"supported": research_result["supported"], "problems": bad}
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
