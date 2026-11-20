"""Report exports: an Excel workbook and a PDF summary, written with the standard
library only (no office or PDF packages).

Limits, stated plainly: the PDF is a plain text summary in a built-in Latin font.
Characters outside Latin-1 (Arabic, for example) cannot be drawn and are replaced
by '?'; use the HTML or Markdown report for those. The workbook holds values only
(no formulas, charts or styling beyond a bold header row).
"""
import json
import textwrap
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from . import __version__, report, scoring
from .evidence import load_log, record_level

# ---------------------------------------------------------------- data ----


def collect(review_dir):
    review = Path(review_dir)
    res = scoring.evaluate(review)
    try:
        data = json.loads((review / "findings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    areas = data.get("areas", []) if isinstance(data, dict) and isinstance(data.get("areas"), list) else []
    findings, checks = [], []
    for a in areas:
        if not isinstance(a, dict):
            continue
        for f in a.get("findings", []) or []:
            if isinstance(f, dict):
                findings.append([f.get("id"), a.get("id"), a.get("name"), f.get("severity"), f.get("status"),
                                 f.get("title"), f.get("location"), ", ".join(map(str, f.get("evidence", []) or [])),
                                 f.get("recommendation")])
        for c in a.get("checks", []) or []:
            if isinstance(c, dict):
                checks.append([c.get("id"), a.get("id"), a.get("name"), c.get("title"), c.get("result"),
                               ", ".join(map(str, c.get("evidence", []) or [])), c.get("reason")])
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda r: (order.get(r[3], 9), str(r[0])))
    evidence = []
    try:
        for r in load_log(review).get("records", []):
            level, problem = record_level(r, review)
            evidence.append([r.get("id"), r.get("area"), r.get("kind"), level or f"BROKEN: {problem}", r.get("title"),
                             r.get("command") or r.get("location"), r.get("exit_code"),
                             r.get("started_at") or r.get("recorded_at"), r.get("commit"), r.get("artifact")])
    except (OSError, ValueError):
        pass
    return res, findings, checks, evidence

# ---------------------------------------------------------------- xlsx ----


def _col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _clean(text):
    return "".join(ch for ch in str(text) if ch in "\t\n" or ord(ch) >= 32)


def _sheet(rows):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r, row in enumerate(rows, 1):
        out.append(f'<row r="{r}">')
        for c, value in enumerate(row, 1):
            ref, style = f"{_col(c)}{r}", ' s="1"' if r == 1 else ""
            if value is None or value == "":
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
            else:
                out.append(f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(_clean(value))}</t></is></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path, sheets):
    """sheets: list of (name, rows). The first row of each sheet is the header."""
    names = [n for n, _ in sheets]
    ns = "http://schemas.openxmlformats.org"
    files = {
        "[Content_Types].xml": (
            f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="{ns}/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                      for i in range(1, len(names) + 1)) + "</Types>"),
        "_rels/.rels": (
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{ns}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{ns}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"),
        "xl/workbook.xml": (
            f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{ns}/spreadsheetml/2006/main" '
            f'xmlns:r="{ns}/officeDocument/2006/relationships"><sheets>'
            + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1))
            + "</sheets></workbook>"),
        "xl/_rels/workbook.xml.rels": (
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{ns}/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i}" Type="{ns}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                      for i in range(1, len(names) + 1))
            + f'<Relationship Id="rId{len(names) + 1}" Type="{ns}/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"),
        "xl/styles.xml": (
            f'<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="{ns}/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'),
    }
    for i, (_name, rows) in enumerate(sheets, 1):
        files[f"xl/worksheets/sheet{i}.xml"] = _sheet(rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            z.writestr(name, body)

# ----------------------------------------------------------------- pdf ----


def _latin(text):
    return str(text).replace("—", "-").replace("–", "-").replace("★", "*").replace("…", "...").replace("→", "->") \
        .encode("latin-1", "replace").decode("latin-1")


def write_pdf(path, lines, title="Report"):
    """A minimal multi-page PDF. `lines` is a list of (style, text); style is h1, h2 or p."""
    width, height, margin = 595, 842, 50
    sizes = {"h1": (16, 22, "F2"), "h2": (12, 18, "F2"), "p": (9, 12, "F1"), "mono": (8, 10, "F3")}
    pages, ops, y = [], [], height - margin
    for style, text in lines:
        size, lead, font = sizes[style]
        wrap = {"h1": 60, "h2": 80, "p": 105, "mono": 100}[style]
        chunks = textwrap.wrap(_latin(text), wrap) or [""]
        for chunk in chunks:
            if y - lead < margin:
                pages.append(ops)
                ops, y = [], height - margin
            y -= lead
            safe = chunk.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"BT /{font} {size} Tf {margin} {y} Td ({safe}) Tj ET")
    pages.append(ops)
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
               "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"]
    kids = []
    for ops in pages:
        stream = "\n".join(ops).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        content_id = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Contents {content_id} 0 R "
                       "/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> >>")
        kids.append(len(objects))
    objects[1] = f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(f'{k} 0 R' for k in kids)}] >>"
    objects.append(f"<< /Title ({_latin(title).replace('(', '').replace(')', '')}) /Producer (Enterprise Experts {__version__}) >>")
    out, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        body = obj if isinstance(obj, bytes) else obj.encode("latin-1")
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, len(objects), xref)
    Path(path).write_bytes(bytes(out))
    return len(pages)

# -------------------------------------------------------------- export ----


def export(review_dir, formats=("xlsx", "pdf")):
    review = Path(review_dir)
    res, findings, checks, evidence = collect(review)
    report.write_all(res, review)
    decision = "INVALID REVIEW - NO-GO" if not res["valid"] else res["decision"]
    written = []
    if "xlsx" in formats:
        summary = [["Field", "Value"], ["Project", res.get("project")], ["Decision", decision],
                   ["Overall score", res["overall"]], ["Review date", res.get("review_date")], ["Mode", res.get("mode")],
                   ["Risk profile", res.get("risk_profile")], ["Engine version", __version__]]
        summary += [["Blocker", b] for b in res["blockers"]] + [["Condition", c] for c in res["conditions"]]
        summary += [["Validation error", e] for e in res["errors"]]
        score_rows = [["#", "Area", "Core", "Status", "Expert score", "Final score", "Cap / reason",
                       "Unresolved Critical", "Open High", "Evidence basis"]]
        score_rows += [[r["id"], r["name"], "yes" if r["core"] else "no", r["status"], r["score"], r["final"], r["caps"],
                        r["critical"], r["high"], r["basis"]] for r in res["rows"]]
        write_xlsx(review / "report.xlsx", [
            ("Summary", summary), ("Scorecard", score_rows),
            ("Findings", [["ID", "Area #", "Area", "Severity", "Status", "Title", "Location", "Evidence", "Recommendation"]] + findings),
            ("Checks", [["ID", "Area #", "Area", "Check", "Result", "Evidence", "Reason"]] + checks),
            ("Evidence", [["ID", "Area #", "Kind", "Level", "Title", "Command / location", "Exit code", "When", "Commit",
                           "Artifact"]] + evidence)])
        written.append("report.xlsx")
    if "pdf" in formats:
        lines = [("h1", f"Project Health Summary - {res.get('project') or 'project'}"),
                 ("h2", f"Decision: {decision}    Overall: {res['overall'] if res['overall'] is not None else 'n/a'}/100"),
                 ("p", f"Review date {res.get('review_date')}  |  mode {res.get('mode')}  |  risk profile "
                       f"{res.get('risk_profile')}  |  engine {__version__}"), ("p", "")]
        if res["errors"]:
            lines += [("h2", "Validation errors")] + [("p", f"- {e}") for e in res["errors"]]
        if res["rows"]:
            lines += [("h2", "Scorecard"), ("mono", f"{'#':>2}  {'Area':<24}{'Status':<16}{'Score':>5} {'Final':>5}  Basis")]
            lines += [("mono", f"{r['id']:>2}{'*' if r['core'] else ' '} {r['name']:<24}{r['status']:<16}"
                               f"{'' if r['score'] is None else r['score']:>5} {'' if r['final'] is None else r['final']:>5}  {r['basis']}")
                      for r in res["rows"]]
            lines += [("p", "* core area for this risk profile"), ("p", "")]
        for heading, items in (("How to read this result", res.get("notes", [])), ("Blockers", res["blockers"]),
                               ("Conditions", res["conditions"])):
            if items:
                lines += [("h2", heading)] + [("p", f"- {i}") for i in items] + [("p", "")]
        if findings:
            lines += [("h2", f"Findings ({len(findings)})")]
            lines += [("p", f"[{f[3]}] {f[0]} ({f[2]}, {f[4]}): {f[5]}" + (f"  @ {f[6]}" if f[6] else "")) for f in findings]
        lines += [("p", ""), ("p", "Plain-text summary. Characters outside Latin-1 are shown as '?'. The full report, "
                               "evidence and expert deliverables are in the review folder.")]
        write_pdf(review / "report.pdf", lines, title=f"Project Health Summary - {res.get('project')}")
        written.append("report.pdf")
    return {"written": written, "decision": decision, "findings": len(findings), "evidence": len(evidence)}
