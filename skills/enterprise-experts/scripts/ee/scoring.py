"""Validation and the Go/No-Go decision.

Fail-closed: anything missing, malformed, duplicated or unsupported by a real
evidence record makes the review INVALID, and an invalid review is always NO-GO.
Evidence levels are derived from evidence-log.json, never read from findings.json.
"""
import json
import re
from pathlib import Path

from . import SCHEMA_VERSION
from .areas import (AREA_STATUSES, AREAS, CHECK_RESULTS, FINDING_STATUSES, GATES, MODES, RISK_PROFILES,
                    RISK_RANK, SEVERITIES, required_areas)
from .evidence import ID_RX, load_log, record_level
from .intake import effective_risk_profile, load_intake, validate_intake

FINDINGS_NAME = "findings.json"
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Areas every software project has; they cannot be waved away as "not applicable".
NEVER_NOT_APPLICABLE = {1, 2, 9, 17, 22}
# Areas that legitimately build on other experts' evidence.
MAY_REUSE_EVIDENCE = {17, 19, 21, 22, 23}
EXIT = {"GO": 0, "CONDITIONAL GO": 10, "NO-GO": 20, "INVALID": 2}


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _text(v):
    return isinstance(v, str) and v.strip() != ""


class _Evidence:
    """Resolved evidence records for a review folder."""

    def __init__(self, review_dir, errors):
        self.review_dir, self.by_id, self._cache = review_dir, {}, {}
        try:
            log = load_log(review_dir)
            records = log.get("records", [])
            if not isinstance(records, list):
                raise ValueError("records must be a list")
        except (ValueError, OSError, AttributeError) as exc:
            errors.append(f"evidence-log.json is unreadable: {exc}")
            records = []
        for rec in records:
            eid = rec.get("id") if isinstance(rec, dict) else None
            if not isinstance(eid, str) or not ID_RX.match(eid):
                errors.append(f"evidence record with invalid id: {eid!r}")
            elif eid in self.by_id:
                errors.append(f"duplicate evidence id: {eid}")
            else:
                self.by_id[eid] = rec

    def level(self, eid):
        """(level, problem). Level is None when the record is missing or broken."""
        if eid not in self._cache:
            rec = self.by_id.get(eid)
            self._cache[eid] = (None, "no such record in evidence-log.json") if rec is None \
                else record_level(rec, self.review_dir)
        return self._cache[eid]

    def supports_pass(self, eid):
        level, _ = self.level(eid)
        rec = self.by_id.get(eid, {})
        if level == "observed":
            return True
        return (level == "verified" and not rec.get("timed_out")
                and rec.get("exit_code") is not None and rec.get("exit_code") != 127)


def _refs(value, where, errors, ev, area_id, levels, require=True):
    """Validate a list of evidence references and collect their levels."""
    if not isinstance(value, list) or (require and not value):
        errors.append(f"{where}: needs a non-empty list of evidence ids")
        return []
    ok = []
    for eid in value:
        level, problem = ev.level(eid)
        if level is None:
            errors.append(f"{where}: evidence {eid!r} is not usable ({problem})")
            continue
        rec_area = ev.by_id[eid].get("area")
        if rec_area != area_id and area_id not in MAY_REUSE_EVIDENCE:
            errors.append(f"{where}: evidence {eid} was recorded for area {rec_area}, not area {area_id}")
            continue
        levels.add(level)
        ok.append(eid)
    return ok


def validate(review_dir):
    """Return (data, intake, context, errors). Any error means the review is INVALID."""
    review_dir = Path(review_dir)
    errors = []
    try:
        data = json.loads((review_dir / FINDINGS_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None, {}, [f"{FINDINGS_NAME} not found in {review_dir}"]
    except ValueError as exc:
        return None, None, {}, [f"{FINDINGS_NAME} is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, None, {}, [f"{FINDINGS_NAME} must be a JSON object"]

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not _text(data.get("project")):
        errors.append("project name is missing")
    if not (isinstance(data.get("review_date"), str) and DATE_RX.match(data["review_date"])):
        errors.append("review_date must be YYYY-MM-DD")
    mode = data.get("mode")
    if mode not in MODES:
        errors.append(f"mode must be one of {list(MODES)}")
    scope = data.get("scope")
    if mode == "focused":
        if (not isinstance(scope, list) or not scope
                or any(isinstance(s, bool) or s not in AREAS for s in scope) or len(set(scope)) != len(scope)):
            errors.append("focused mode needs 'scope': a non-empty list of distinct area ids (1-23)")
            scope = []

    # --- intake and risk profile -------------------------------------------
    intake = None
    try:
        intake = load_intake(review_dir)
    except ValueError as exc:
        errors.append(f"intake.json is not valid JSON: {exc}")
    risk = data.get("risk_profile")
    if risk not in RISK_PROFILES:
        errors.append(f"risk_profile must be one of {list(RISK_PROFILES)}")
        risk = "regulated"  # strictest gates while invalid
    if intake is None:
        errors.append("intake.json is missing: the project questions were not answered")
    else:
        intake_errors = validate_intake(intake)
        errors += intake_errors
        if not intake_errors:
            needed = effective_risk_profile(intake)
            if RISK_RANK[risk] < RISK_RANK[needed]:
                errors.append(f"risk_profile '{risk}' is lower than the intake answers require ('{needed}')")
            if intake["answers"].get("review_mode") != mode:
                errors.append("mode differs from the review_mode answered in intake.json")

    # --- areas --------------------------------------------------------------
    ev = _Evidence(review_dir, errors)
    areas = data.get("areas")
    if not isinstance(areas, list):
        errors.append("'areas' must be a list")
        areas = []
    seen_areas, seen_ids, area_levels = set(), set(), {}
    for idx, area in enumerate(areas):
        if not isinstance(area, dict):
            errors.append(f"areas[{idx}] is not an object")
            continue
        aid = area.get("id")
        if isinstance(aid, bool) or aid not in AREAS:
            errors.append(f"areas[{idx}]: id must be an expert area number 1-23, got {aid!r}")
            continue
        tag = f"area {aid} {AREAS[aid]}"
        if aid in seen_areas:
            errors.append(f"{tag}: listed more than once")
            continue
        seen_areas.add(aid)
        if "name" in area and area["name"] != AREAS[aid]:
            errors.append(f"{tag}: name {area['name']!r} does not match the area id")
        status = area.get("status")
        if status not in AREA_STATUSES:
            errors.append(f"{tag}: status must be one of {list(AREA_STATUSES)}")
            continue
        levels = area_levels.setdefault(aid, set())
        if status in ("not_assessed", "not_applicable"):
            if not _text(area.get("reason")):
                errors.append(f"{tag}: status {status} needs a 'reason'")
            if status == "not_applicable" and aid in NEVER_NOT_APPLICABLE:
                errors.append(f"{tag}: this area applies to every software project and cannot be not_applicable")
        else:
            score = area.get("score")
            if not _is_num(score) or not 0 <= score <= 100:
                errors.append(f"{tag}: score must be a number from 0 to 100, got {score!r}")
            checks = area.get("checks")
            if not isinstance(checks, list) or not checks:
                errors.append(f"{tag}: an assessed area must list the checks that were performed")
                checks = []
            for chk in checks:
                if not isinstance(chk, dict) or not _text(chk.get("id")) or not _text(chk.get("title")):
                    errors.append(f"{tag}: every check needs an id and a title")
                    continue
                cid = chk["id"]
                if cid in seen_ids:
                    errors.append(f"{tag}: duplicate id {cid}")
                seen_ids.add(cid)
                result = chk.get("result")
                if result not in CHECK_RESULTS:
                    errors.append(f"{tag}: check {cid} result must be one of {list(CHECK_RESULTS)}")
                elif result in ("not_assessed", "not_applicable"):
                    if not _text(chk.get("reason")):
                        errors.append(f"{tag}: check {cid} is {result} and needs a 'reason'")
                else:
                    ok = _refs(chk.get("evidence"), f"{tag}: check {cid}", errors, ev, aid, levels)
                    if result == "pass" and ok and not any(ev.supports_pass(e) for e in ok):
                        errors.append(f"{tag}: check {cid} is marked pass but no evidence supports it "
                                      "(a pass needs something that was run, or read at a cited location)")
            if status == "assessed" and checks and all(
                    isinstance(c, dict) and c.get("result") in ("not_assessed", "not_applicable") for c in checks):
                errors.append(f"{tag}: status is 'assessed' but no check was actually performed")
        findings = area.get("findings", [])
        if not isinstance(findings, list):
            errors.append(f"{tag}: 'findings' must be a list")
            continue
        for f in findings:
            if not isinstance(f, dict) or not _text(f.get("id")) or not _text(f.get("title")):
                errors.append(f"{tag}: every finding needs an id and a title")
                continue
            fid = f["id"]
            ftag = f"{tag}: finding {fid}"
            if fid in seen_ids:
                errors.append(f"{tag}: duplicate id {fid}")
            seen_ids.add(fid)
            if f.get("severity") not in SEVERITIES:
                errors.append(f"{ftag}: severity must be one of {list(SEVERITIES)}")
            fstatus = f.get("status")
            if fstatus not in FINDING_STATUSES:
                errors.append(f"{ftag}: status must be one of {list(FINDING_STATUSES)}")
                continue
            _refs(f.get("evidence"), ftag, errors, ev, aid, levels)
            if fstatus == "fixed":
                proof = _refs(f.get("verification"), f"{ftag} verification", errors, ev, aid, levels)
                if proof and not all(ev.level(e)[0] == "verified" and ev.supports_pass(e) for e in proof):
                    errors.append(f"{ftag}: 'fixed' needs a re-check that was actually run (command evidence)")
            elif fstatus == "accepted":
                m = f.get("mitigation")
                missing = [k for k in ("approved_by", "reason", "date", "controls")
                           if not (isinstance(m, dict) and (_text(m.get(k)) or (k == "controls" and m.get(k))))]
                if missing:
                    errors.append(f"{ftag}: accepted risk needs mitigation fields {missing}")
                elif not DATE_RX.match(str(m["date"])):
                    errors.append(f"{ftag}: mitigation date must be YYYY-MM-DD")
            elif fstatus == "false_positive" and not _text(f.get("reason")):
                errors.append(f"{ftag}: false_positive needs a 'reason'")

    required = required_areas(mode, scope) if mode in MODES else set()
    missing = sorted(required - seen_areas)
    if missing:
        errors.append("required areas missing for a %s review: %s" %
                      (mode, ", ".join(f"{a} {AREAS[a]}" for a in missing)))
    return data, intake, {"risk": risk, "area_levels": area_levels, "required": required}, errors


def evaluate(review_dir):
    data, _intake, ctx, errors = validate(review_dir)
    result = {"valid": not errors, "errors": errors, "decision": "NO-GO", "overall": None, "rows": [],
              "blockers": [], "conditions": [], "project": (data or {}).get("project"),
              "review_date": (data or {}).get("review_date"), "mode": (data or {}).get("mode"),
              "risk_profile": ctx.get("risk"), "exit_code": EXIT["INVALID"]}
    if errors:
        result["blockers"] = ["The review is INVALID and cannot support a release decision. Fix the errors and re-run."]
        return result

    gate = GATES[ctx["risk"]]
    core = gate["core"]
    blockers, conditions, rows = result["blockers"], result["conditions"], result["rows"]
    wsum = wtot = 0
    for area in sorted(data["areas"], key=lambda a: a["id"]):
        aid, name, status = area["id"], AREAS[area["id"]], area["status"]
        findings = area.get("findings", [])
        crit = [f for f in findings if f["severity"] == "critical" and f["status"] in ("open", "accepted")]
        high_open = [f for f in findings if f["severity"] == "high" and f["status"] == "open"]
        high_acc = [f for f in findings if f["severity"] == "high" and f["status"] == "accepted"]
        is_core = aid in core
        for f in crit:
            note = " (risk acceptance does not lift a Critical)" if f["status"] == "accepted" else ""
            blockers.append(f"{f['id']} ({name}): {f['title']}{note}")
        if status in ("not_assessed", "not_applicable"):
            rows.append({"id": aid, "name": name, "core": is_core, "status": status, "score": None, "final": None,
                         "caps": area.get("reason", ""), "critical": len(crit), "high": len(high_open), "basis": "—"})
            if status == "not_assessed":
                (blockers if is_core else conditions).append(
                    f"{'Core area' if is_core else 'Area'} {aid} {name} was not assessed: {area.get('reason')}")
            continue
        levels = ctx["area_levels"].get(aid, set())
        limits = []
        if crit:
            limits.append((40, f"{len(crit)} unresolved Critical"))
        if high_open:
            limits.append((70, f"{len(high_open)} open High"))
        if "verified" in levels:
            basis = "Verified"
        elif "observed" in levels:
            basis = "Observed only"
            limits.append((75, "nothing was run (no Verified evidence)"))
        else:
            basis = "Inferred only"
            limits.append((50, "inferred evidence only"))
        final, caps = float(area["score"]), []
        for limit, why in limits:
            if final > limit:
                final = limit
                caps.append(why)
        weight = 2 if is_core else 1
        wsum += final * weight
        wtot += weight
        rows.append({"id": aid, "name": name, "core": is_core, "status": status, "score": area["score"],
                     "final": round(final), "caps": "; ".join(caps), "critical": len(crit),
                     "high": len(high_open), "basis": basis})
        for f in high_open:
            conditions.append(f"Open High {f['id']} ({name}): {f['title']}")
        if ctx["risk"] != "standard":
            for f in high_acc:
                conditions.append(f"Accepted High {f['id']} ({name}) needs sign-off review for a {ctx['risk']} project")
        if is_core:
            if final < gate["block_score"]:
                blockers.append(f"Core area {aid} {name} scored {round(final)} (below {gate['block_score']})")
            elif final < gate["go_score"]:
                conditions.append(f"Core area {aid} {name} scored {round(final)} (below {gate['go_score']})")
            if basis != "Verified":
                conditions.append(f"Core area {aid} {name} has no Verified evidence: nothing was actually run")
            if status == "partial":
                conditions.append(f"Core area {aid} {name} was only partially assessed")
    present = {a["id"] for a in data["areas"]}
    for aid in sorted(core - present):
        conditions.append(f"Core area {aid} {AREAS[aid]} is outside this {data['mode']} review: "
                          "the decision covers the reviewed scope only, not a release")
    if not wtot:
        blockers.append("No area was scored")
    else:
        result["overall"] = round(wsum / wtot)
    result["decision"] = "NO-GO" if blockers else ("CONDITIONAL GO" if conditions else "GO")
    result["exit_code"] = EXIT[result["decision"]]
    return result
