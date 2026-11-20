"""Turn the output of trusted scanners into structured evidence.

Supported formats: SARIF 2.1 (semgrep, CodeQL, trivy and others), `npm audit --json`,
osv-scanner JSON, pip-audit JSON, trivy JSON and gitleaks JSON. The result is a list
of candidate findings for the expert to triage; nothing is added to findings.json
automatically, because a scanner hit is not yet a confirmed finding.
"""
import json
from pathlib import Path

from .evidence import load_log, record_level
from .secrets import mask

SEV = {"critical": "critical", "high": "high", "error": "high", "moderate": "medium", "medium": "medium",
       "warning": "medium", "low": "low", "note": "low", "info": "info", "none": "info", "negligible": "low"}


def _sev(value):
    return SEV.get(str(value or "").lower(), "unrated")


def _from_score(score):
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None
    return "critical" if score >= 9 else "high" if score >= 7 else "medium" if score >= 4 else "low"


def _item(tool, rule, title, severity, location=None, package=None, fixed_in=None, url=None):
    return {"tool": tool, "rule": rule, "title": (title or rule or "")[:300], "severity": severity,
            "location": location, "package": package, "fixed_in": fixed_in, "url": url}


def parse_sarif(doc):
    out = []
    for run in doc.get("runs", []):
        tool = run.get("tool", {}).get("driver", {})
        rules = {r.get("id"): r for r in tool.get("rules", [])}
        for res in run.get("results", []):
            rule = rules.get(res.get("ruleId"), {})
            sev = _from_score(res.get("properties", {}).get("security-severity")
                              or rule.get("properties", {}).get("security-severity")) \
                or _sev(res.get("level") or rule.get("defaultConfiguration", {}).get("level") or "warning")
            loc = None
            for l_ in res.get("locations", [])[:1]:
                phys = l_.get("physicalLocation", {})
                uri = phys.get("artifactLocation", {}).get("uri")
                line = phys.get("region", {}).get("startLine")
                loc = f"{uri}:{line}" if uri and line else uri
            out.append(_item(tool.get("name", "sarif"), res.get("ruleId"),
                             res.get("message", {}).get("text") or rule.get("shortDescription", {}).get("text"),
                             sev, loc, url=rule.get("helpUri")))
    return out


def parse_npm_audit(doc):
    out = []
    for name, v in doc.get("vulnerabilities", {}).items():
        advisories = [x for x in v.get("via", []) if isinstance(x, dict)]
        fix = v.get("fixAvailable")
        fixed = (f"{fix.get('name')}@{fix.get('version')}" if isinstance(fix, dict) else ("yes" if fix else None))
        if not advisories:
            out.append(_item("npm audit", None, f"{name}: vulnerable through " + ", ".join(map(str, v.get("via", []))),
                             _sev(v.get("severity")), package=f"{name} {v.get('range', '')}".strip(), fixed_in=fixed))
        for adv in advisories:
            out.append(_item("npm audit", str(adv.get("source") or ""), adv.get("title"), _sev(adv.get("severity")),
                             package=f"{name} {adv.get('range', '')}".strip(), fixed_in=fixed, url=adv.get("url")))
    return out


def parse_osv(doc):
    out = []
    for res in doc.get("results", []):
        src = res.get("source", {}).get("path")
        for pkg in res.get("packages", []):
            p = pkg.get("package", {})
            groups = {i: g for g in pkg.get("groups", []) for i in g.get("ids", [])}
            for v in pkg.get("vulnerabilities", []):
                sev = _from_score(groups.get(v.get("id"), {}).get("max_severity")) \
                    or _sev(v.get("database_specific", {}).get("severity"))
                fixed = next((e.get("fixed") for a in v.get("affected", []) for r in a.get("ranges", [])
                              for e in r.get("events", []) if e.get("fixed")), None)
                out.append(_item("osv-scanner", v.get("id"), v.get("summary") or v.get("id"), sev, src,
                                 f"{p.get('name')} {p.get('version')}", fixed,
                                 f"https://osv.dev/vulnerability/{v.get('id')}"))
    return out


def parse_pip_audit(doc):
    deps = doc.get("dependencies", doc) if isinstance(doc, dict) else doc
    out = []
    for d in deps:
        for v in d.get("vulns", []):
            out.append(_item("pip-audit", v.get("id"), v.get("description") or v.get("id"), "unrated",
                             package=f"{d.get('name')} {d.get('version')}",
                             fixed_in=", ".join(v.get("fix_versions", [])) or None,
                             url=f"https://osv.dev/vulnerability/{v.get('id')}"))
    return out


def parse_trivy(doc):
    out = []
    for res in doc.get("Results", []):
        for v in res.get("Vulnerabilities") or []:
            out.append(_item("trivy", v.get("VulnerabilityID"), v.get("Title") or v.get("VulnerabilityID"),
                             _sev(v.get("Severity")), res.get("Target"),
                             f"{v.get('PkgName')} {v.get('InstalledVersion')}", v.get("FixedVersion"), v.get("PrimaryURL")))
        for m in res.get("Misconfigurations") or []:
            out.append(_item("trivy", m.get("ID"), m.get("Title"), _sev(m.get("Severity")), res.get("Target"),
                             url=m.get("PrimaryURL")))
    return out


def parse_gitleaks(doc):
    return [_item("gitleaks", x.get("RuleID"), f"{x.get('Description')} ({mask(str(x.get('Secret', '')))})", "high",
                  f"{x.get('File')}:{x.get('StartLine')}") for x in doc]


def detect_and_parse(doc):
    """(format, candidates). Raises ValueError for a format we do not know."""
    if isinstance(doc, dict):
        if "runs" in doc and ("$schema" in doc or "version" in doc):
            return "sarif", parse_sarif(doc)
        if "auditReportVersion" in doc or isinstance(doc.get("vulnerabilities"), dict):
            return "npm-audit", parse_npm_audit(doc)
        if "Results" in doc or "SchemaVersion" in doc:
            return "trivy", parse_trivy(doc)
        if "results" in doc and isinstance(doc["results"], list):
            return "osv-scanner", parse_osv(doc)
        if "dependencies" in doc:
            return "pip-audit", parse_pip_audit(doc)
    if isinstance(doc, list):
        if doc and all(isinstance(x, dict) and "RuleID" in x for x in doc):
            return "gitleaks", parse_gitleaks(doc)
        if all(isinstance(x, dict) and "vulns" in x for x in doc):
            return "pip-audit", parse_pip_audit(doc)
        if not doc:
            return "empty-list", []
    raise ValueError("unrecognised scanner output: supported are SARIF, npm audit, osv-scanner, pip-audit, trivy, gitleaks")


def _extract_json(text):
    """Scanner JSON from captured output, which may have a header or log lines around it."""
    decoder = json.JSONDecoder()
    best = None
    for i, ch in enumerate(text):
        if ch in "{[" and (i == 0 or text[i - 1] == "\n"):
            try:
                doc, end = decoder.raw_decode(text[i:])
            except ValueError:
                continue
            if best is None or end > best[1]:
                best = (doc, end)
    if best is None:
        raise ValueError("no JSON document found in the scanner output")
    return best[0]


def import_scan(review_dir, evidence_id=None, file=None):
    """Parse a recorded scanner run (by evidence id) or a results file inside the review folder."""
    review = Path(review_dir).resolve()
    if bool(evidence_id) == bool(file):
        raise ValueError("give exactly one of --evidence or --file")
    if evidence_id:
        rec = next((r for r in load_log(review)["records"] if r.get("id") == evidence_id), None)
        if rec is None:
            raise ValueError(f"no evidence record {evidence_id}")
        level, problem = record_level(rec, review)
        if level != "verified":
            raise ValueError(f"{evidence_id} is not intact command evidence ({problem or level})")
        path, name = review / rec["artifact"], evidence_id
    else:
        path = (review / file).resolve()
        if review not in path.parents or not path.is_file():
            raise ValueError("the results file must exist inside the review folder (so it is kept with the evidence)")
        name = path.stem
    fmt, items = detect_and_parse(_extract_json(path.read_text(encoding="utf-8", errors="replace")))
    counts = {}
    for it in items:
        counts[it["severity"]] = counts.get(it["severity"], 0) + 1
    out = {"source": path.relative_to(review).as_posix(), "evidence": evidence_id, "format": fmt,
           "count": len(items), "by_severity": counts, "candidates": items,
           "note": "Candidates need triage: confirm each is real and reachable before adding it to findings.json. "
                   "'unrated' means the tool gave no severity."}
    (review / "scans").mkdir(exist_ok=True)
    (review / "scans" / f"{name}-normalized.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
