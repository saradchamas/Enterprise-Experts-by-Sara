"""Scorecard exports: Markdown, JSON and a self-contained HTML page."""
import html
import json
from pathlib import Path

from .areas import GATES


def _title(res):
    return "INVALID REVIEW — NO-GO" if not res["valid"] else res["decision"]


def to_markdown(res):
    o = [f"# Scorecard — {res.get('project') or 'Project'}", "",
         f"**Decision: {_title(res)}**  |  **Overall score: {res['overall'] if res['overall'] is not None else 'n/a'}/100**"
         f"  |  Review date: {res.get('review_date') or '?'}  |  Mode: {res.get('mode') or '?'}"
         f"  |  Risk profile: {res.get('risk_profile') or '?'}", ""]
    if not res["valid"]:
        o += ["## Validation errors", "",
              "The decision engine is fail-closed: until every error below is fixed, the only possible result is NO-GO.", ""]
        o += [f"- {e}" for e in res["errors"]] + [""]
        return "\n".join(o)
    gate = GATES[res["risk_profile"]]
    o += ["| # | Area | Status | Expert score | Final score | Cap / reason | Unresolved Critical | Open High | Evidence basis |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        o.append("| {id} | {name}{star} | {status} | {score} | {final} | {caps} | {critical} | {high} | {basis} |".format(
            star=" ★" if r["core"] else "", **{k: ("—" if v is None else v) for k, v in r.items()}))
    o += ["", f"★ = core area for a {res['risk_profile']} project (weight 2; for GO it must be assessed, backed by "
          f"Verified evidence and score at least {gate['go_score']}).", ""]
    if res["blockers"]:
        o += ["## Blockers (reasons for NO-GO)", ""] + [f"- {b}" for b in res["blockers"]] + [""]
    if res["conditions"]:
        o += ["## Conditions (to reach GO)", ""] + [f"- {c}" for c in res["conditions"]] + [""]
    if not res["blockers"] and not res["conditions"]:
        o += ["Every required area is assessed, every core area is verified and above the gate, "
              "and no Critical or High finding is unresolved.", ""]
    return "\n".join(o)


def to_html(res):
    e = html.escape
    color = {"GO": "#1a7f37", "CONDITIONAL GO": "#9a6700"}.get(res["decision"] if res["valid"] else "", "#cf222e")
    rows = "".join(
        "<tr><td>{}</td><td>{}{}</td><td>{}</td><td>{}</td><td><b>{}</b></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            r["id"], e(r["name"]), " ★" if r["core"] else "", e(r["status"]),
            "—" if r["score"] is None else r["score"], "—" if r["final"] is None else r["final"],
            e(str(r["caps"])), r["critical"], r["high"], e(r["basis"])) for r in res["rows"])

    def block(title, items):
        return f"<h2>{title}</h2><ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Scorecard — {e(str(res.get('project')))}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#1f2328}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d0d7de;padding:6px 8px;text-align:left}}
th{{background:#f6f8fa}}.d{{display:inline-block;padding:.4rem 1rem;border-radius:6px;color:#fff;background:{color};font-weight:700}}</style></head>
<body><h1>Scorecard — {e(str(res.get('project')))}</h1>
<p><span class="d">{e(_title(res))}</span> &nbsp; Overall: <b>{res['overall'] if res['overall'] is not None else 'n/a'}/100</b>
&nbsp;|&nbsp; {e(str(res.get('review_date')))} &nbsp;|&nbsp; mode: {e(str(res.get('mode')))} &nbsp;|&nbsp; risk profile: {e(str(res.get('risk_profile')))}</p>
{block('Validation errors', res['errors'])}
{'<table><tr><th>#</th><th>Area</th><th>Status</th><th>Expert score</th><th>Final</th><th>Cap / reason</th><th>Unresolved Critical</th><th>Open High</th><th>Evidence basis</th></tr>' + rows + '</table><p>★ core area for this risk profile</p>' if res['rows'] else ''}
{block('Blockers', res['blockers'])}{block('Conditions', res['conditions'])}</body></html>"""


def write_all(res, review_dir):
    review_dir = Path(review_dir)
    (review_dir / "scorecard.md").write_text(to_markdown(res), encoding="utf-8")
    (review_dir / "scorecard.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (review_dir / "scorecard.html").write_text(to_html(res), encoding="utf-8")
