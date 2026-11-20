"""Research and proposals: what was looked up, where, when, and what is proposed because of it.

A source is a page that was actually read, with its URL and the date it was read. A proposal
(adopt a technology, change a model, add an MCP server, upgrade a library) must point at a
problem it solves and at the sources that support it. Nothing here is taken on memory: model
line-ups, prices, versions and tool listings change within months, so sources go stale.
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from . import evidence, state
from .areas import AREAS

FILE_NAME = "research.json"
LOG_NAME = "research-log.md"
CATEGORIES = ("technology", "model", "mcp", "tool", "dataset", "practice")
# Things that are installed, called or paid for: the vendor's or maintainer's own page must be among the sources.
NEEDS_OFFICIAL = frozenset({"model", "mcp", "tool", "dataset"})
# Facts that move quickly. A practice ("validate input at the boundary") does not go stale in 90 days.
FAST_MOVING = frozenset({"technology", "model", "mcp", "tool", "dataset"})
ACTIONS = ("adopt", "replace", "upgrade", "remove", "configure")
EFFORTS = ("S", "M", "L")
STATUSES = ("proposed", "approved", "rejected", "implemented", "verified")
DEFAULT_MAX_AGE_DAYS = 90
URL_RX = re.compile(r"^https?://[^\s/]+\.[^\s/]+", re.I)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path(review_dir):
    return Path(review_dir) / FILE_NAME


def load(review_dir):
    path = _path(review_dir)
    if not path.exists():
        return {"schema": 1, "sources": [], "proposals": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list) or not isinstance(data.get("proposals"), list):
        raise ValueError(f"{FILE_NAME} is malformed: it needs 'sources' and 'proposals' lists")
    return data


def _save(review_dir, data):
    Path(review_dir).mkdir(parents=True, exist_ok=True)
    tmp = _path(review_dir).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_path(review_dir))
    return data


def _next(items, prefix):
    numbers = [int(i["id"].split("-")[1]) for i in items if re.match(rf"^{prefix}-\d+$", str(i.get("id", "")))]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _day(text, what):
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        raise ValueError(f"{what} must be a date like 2026-11-20, got {text!r}") from None


def add_source(review_dir, area, category, subject, claim, url, official=False, retrieved=None, published=None,
               today=None):
    """Record one page that was read. Also written to the evidence log as an observation."""
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
    if not URL_RX.match(url or ""):
        raise ValueError("a source needs the http(s) URL of the page that was read; memory is not a source")
    if not (subject or "").strip() or not (claim or "").strip():
        raise ValueError("a source needs --subject (what it is about) and --claim (what the page said)")
    today = today or date.today()
    retrieved_day = _day(retrieved, "--retrieved") if retrieved else today
    if retrieved_day > today:
        raise ValueError("--retrieved is in the future")
    if published and _day(published, "--published") > today:
        raise ValueError("--published is in the future")
    note = evidence.add_note(review_dir, area, f"Source: {subject.strip()}", "observation",
                             f"{claim.strip()} (read {retrieved_day.isoformat()})", location=url)
    data = load(review_dir)
    source = {"id": _next(data["sources"], "R"), "category": category, "subject": subject.strip(),
              "claim": claim.strip(), "url": url, "official": bool(official),
              "retrieved": retrieved_day.isoformat(), "published": published, "area": area,
              "evidence": note["id"], "recorded_at": _now()}
    data["sources"].append(source)
    _save(review_dir, data)
    return source


def _known_findings(review_dir):
    try:
        data = json.loads((Path(review_dir) / "findings.json").read_text(encoding="utf-8"))
        return {f.get("id") for a in data.get("areas", []) for f in a.get("findings", []) or []}
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def propose(review_dir, area, category, action, title, sources, findings=(), goal=None, alternatives=(),
            effort="M", risk=None, rollback=None):
    """Record a proposal. It must solve something and rest on recorded sources."""
    if area not in AREAS:
        raise ValueError(f"--area must be an expert number from 1 to {len(AREAS)}")
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
    if action not in ACTIONS:
        raise ValueError(f"action must be one of: {', '.join(ACTIONS)}")
    if effort not in EFFORTS:
        raise ValueError("effort must be S, M or L")
    if not (title or "").strip():
        raise ValueError("a proposal needs --title")
    if not findings and not (goal or "").strip():
        raise ValueError("a proposal must solve something: give --findings <ids> or --goal <a goal the user stated>")
    if not sources:
        raise ValueError("a proposal needs --sources <R-ids>: record what you read with `research add` first")
    if not [a for a in alternatives if a.strip()]:
        raise ValueError("a proposal needs --alternatives: at least one other option that was considered "
                         "(keeping things as they are counts)")
    data = load(review_dir)
    known_sources = {s["id"] for s in data["sources"]}
    missing = [s for s in sources if s not in known_sources]
    if missing:
        raise ValueError(f"no such source in {FILE_NAME}: {', '.join(missing)}")
    known = _known_findings(review_dir)
    unknown = [f for f in findings if known is not None and f not in known]
    if unknown:
        raise ValueError(f"no such finding in findings.json: {', '.join(unknown)}")
    proposal = {"id": _next(data["proposals"], "P"), "area": area, "category": category, "action": action,
                "title": title.strip(), "findings": list(findings), "goal": (goal or "").strip() or None,
                "sources": list(sources), "alternatives": [a.strip() for a in alternatives if a.strip()],
                "effort": effort, "risk": risk, "rollback": rollback, "status": "proposed",
                "history": [{"status": "proposed", "at": _now()}]}
    data["proposals"].append(proposal)
    _save(review_dir, data)
    return proposal


def _find(data, proposal_id):
    for p in data["proposals"]:
        if p["id"] == proposal_id:
            return p
    raise ValueError(f"no such proposal: {proposal_id}")


def _verifying_record(review_dir, evidence_id, after):
    """A check that ran and passed after the proposal was approved; returns a problem text or None."""
    record = next((r for r in evidence.load_log(review_dir).get("records", []) if r.get("id") == evidence_id), None)
    if record is None:
        return f"no such evidence record: {evidence_id}"
    level, problem = evidence.record_level(record, review_dir)
    if problem:
        return f"{evidence_id}: {problem}"
    if level != "verified" or record.get("exit_code") != 0:
        return f"{evidence_id} is not a check that ran and passed (it must be a command with exit code 0)"
    if after and str(record.get("started_at", "")) <= after:
        return f"{evidence_id} ran before the proposal was approved, so it cannot show the change works"
    return None


def decide(review_dir, proposal_id, status, by=None, reason=None, paths=(), evidence_id=None, max_age_days=DEFAULT_MAX_AGE_DAYS,
           today=None):
    """Move a proposal forward. Approval is the user's; 'verified' needs a check that passed afterwards."""
    if status not in STATUSES[1:]:
        raise ValueError(f"status must be one of: {', '.join(STATUSES[1:])}")
    data = load(review_dir)
    p = _find(data, proposal_id)
    entry = {"status": status, "at": _now()}
    if status == "approved":
        if p["status"] != "proposed":
            raise ValueError(f"{proposal_id} is {p['status']}; only a proposed item can be approved")
        if not (by or "").strip():
            raise ValueError("an approval needs --by <who approved it>")
        blocking = [m for m in _proposal_problems(p, data, review_dir, max_age_days, today or date.today())]
        if blocking:
            raise ValueError(f"{proposal_id} cannot be approved yet: " + "; ".join(blocking))
        if paths:  # lets the guard allow edits to these files during remediation
            state.approve(review_dir, by, [], list(paths), None, f"proposal {proposal_id}: {p['title']}")
        entry.update(by=by.strip(), paths=list(paths))
    elif status == "rejected":
        if not (reason or "").strip():
            raise ValueError("a rejection needs --reason")
        entry.update(by=(by or "").strip() or None, reason=reason.strip())
    elif status == "implemented":
        if p["status"] != "approved":
            raise ValueError(f"{proposal_id} is {p['status']}; only an approved proposal can be implemented")
    elif status == "verified":
        if p["status"] != "implemented":
            raise ValueError(f"{proposal_id} is {p['status']}; mark it implemented before verified")
        if not evidence_id:
            raise ValueError("'verified' needs --evidence <E-id> of a check that ran and passed after the change")
        approved_at = next((h["at"] for h in p["history"] if h["status"] == "approved"), None)
        problem = _verifying_record(review_dir, evidence_id, approved_at)
        if problem:
            raise ValueError(problem)
        entry.update(evidence=evidence_id)
    p["status"] = status
    p["history"].append(entry)
    _save(review_dir, data)
    return p


def _proposal_problems(p, data, review_dir, max_age_days, today):
    by_id = {s["id"]: s for s in data["sources"]}
    sources = [by_id[s] for s in p.get("sources", []) if s in by_id]
    problems = []
    if len(sources) != len(p.get("sources", [])) or not sources:
        problems.append("it cites sources that are not recorded")
        return problems
    if not p.get("findings") and not p.get("goal"):
        problems.append("it does not say which finding or stated goal it serves")
    if not p.get("alternatives"):
        problems.append("no alternative was considered")
    if p.get("category") in NEEDS_OFFICIAL and not any(s.get("official") for s in sources):
        problems.append(f"a {p['category']} proposal needs at least one official source "
                        "(the vendor's or maintainer's own documentation, registry page or repository)")
    if p.get("category") in FAST_MOVING and p.get("status") in ("proposed", "approved"):
        newest = max(_day(s["retrieved"], "retrieved") for s in sources)
        age = (today - newest).days
        if age > max_age_days:
            problems.append(f"its newest source was read {age} days ago (limit {max_age_days}); read it again before acting")
    known = _known_findings(review_dir)
    gone = [f for f in p.get("findings", []) if known is not None and f not in known]
    if gone:
        problems.append(f"it refers to findings that are not in findings.json: {', '.join(gone)}")
    return problems


def check(review_dir, max_age_days=DEFAULT_MAX_AGE_DAYS, today=None):
    """Which proposals are supported right now. A proposal with problems must not be acted on."""
    today = today or date.today()
    data = load(review_dir)
    problems, supported = {}, []
    for s in data["sources"]:
        if not URL_RX.match(str(s.get("url", ""))) or not s.get("claim") or not s.get("retrieved"):
            problems.setdefault(s.get("id", "?"), []).append("source lacks a URL, a claim or the date it was read")
    log_ids = {r.get("id") for r in evidence.load_log(review_dir).get("records", [])}
    for s in data["sources"]:
        if s.get("evidence") not in log_ids:
            problems.setdefault(s.get("id", "?"), []).append("its evidence record is missing from the evidence log")
    for p in data["proposals"]:
        found = _proposal_problems(p, data, review_dir, max_age_days, today)
        history = [h.get("status") for h in p.get("history", [])]
        if p.get("status") in ("implemented", "verified") and "approved" not in history:
            found.append("it was implemented without a recorded approval")
        if p.get("status") == "verified":
            approved_at = next((h["at"] for h in p["history"] if h["status"] == "approved"), None)
            eid = next((h.get("evidence") for h in reversed(p["history"]) if h["status"] == "verified"), None)
            problem = _verifying_record(review_dir, eid, approved_at) if eid else "no verifying evidence is recorded"
            if problem:
                found.append(problem)
        if found:
            problems[p["id"]] = found
        else:
            supported.append(p["id"])
    return {"valid": not problems, "sources": len(data["sources"]), "proposals": len(data["proposals"]),
            "supported": supported, "problems": problems, "max_age_days": max_age_days, "checked_on": today.isoformat()}


def write_log(review_dir, max_age_days=DEFAULT_MAX_AGE_DAYS, today=None):
    """research-log.md: the proposals that hold up, the ones that do not, and every source with its date."""
    data = load(review_dir)
    result = check(review_dir, max_age_days, today)
    by_id = {s["id"]: s for s in data["sources"]}
    lines = ["# Research and proposals", "",
             f"Checked on {result['checked_on']}. Sources for fast-moving facts (models, tools, MCP servers, "
             f"technology versions, datasets) count for {max_age_days} days after they were read.", "",
             "Every statement below comes from a page that was read on the date shown. "
             "Nothing here is quoted from memory.", ""]

    def block(p):
        serves = ", ".join(p.get("findings") or []) or f"goal: {p.get('goal')}"
        out = [f"### {p['id']} — {p['title']}", "",
               f"- Area: {p['area']} {AREAS[p['area']]} | {p['action']} ({p['category']}) | effort {p['effort']} | status **{p['status']}**",
               f"- Serves: {serves}",
               f"- Alternatives considered: {'; '.join(p.get('alternatives') or []) or 'none'}"]
        if p.get("risk"):
            out.append(f"- Risk: {p['risk']}")
        if p.get("rollback"):
            out.append(f"- Rollback: {p['rollback']}")
        for sid in p.get("sources", []):
            s = by_id.get(sid)
            if s:
                out.append(f"- {sid} ({'official' if s.get('official') else 'third party'}, read {s['retrieved']}): "
                           f"{s['claim']} — {s['url']}")
        for problem in result["problems"].get(p["id"], []):
            out.append(f"- **Problem:** {problem}")
        return out + [""]

    good = [p for p in data["proposals"] if p["id"] in result["supported"] and p["status"] != "rejected"]
    bad = [p for p in data["proposals"] if p["id"] not in result["supported"]]
    rejected = [p for p in data["proposals"] if p["id"] in result["supported"] and p["status"] == "rejected"]
    lines += ["## Proposals that are supported", ""]
    lines += [line for p in good for line in block(p)] or ["None.", ""]
    lines += ["## Proposals that must not be acted on yet", ""]
    lines += [line for p in bad for line in block(p)] or ["None.", ""]
    if rejected:
        lines += ["## Rejected", ""] + [line for p in rejected for line in block(p)]
    lines += ["## All sources", "", "| ID | Category | Subject | Official | Read on | URL |", "|---|---|---|---|---|---|"]
    lines += [f"| {s['id']} | {s['category']} | {s['subject']} | {'yes' if s.get('official') else 'no'} | "
              f"{s['retrieved']} | {s['url']} |" for s in data["sources"]] or ["| — | | | | | |"]
    path = Path(review_dir) / LOG_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dict(result, written=LOG_NAME)
