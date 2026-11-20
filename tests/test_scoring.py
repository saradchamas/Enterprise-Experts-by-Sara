"""Regression tests for the decision engine. The main thing they protect:
an incomplete, malformed or unproven review must never come out as GO."""
import json
import unittest

from tests.helpers import OK_CMD, ReviewCase, area, read, write

from ee import evidence, scoring


def finding(fid, severity, evidence_ids, status="open", **extra):
    return dict({"id": fid, "severity": severity, "title": f"{severity} issue", "evidence": evidence_ids,
                 "status": status, "recommendation": "fix it"}, **extra)


class Base(ReviewCase, unittest.TestCase):
    def run_with(self, mutate, key="full", **kw):
        review = self.copy(key, **kw)
        data = read(review)
        mutate(data, review)
        write(review, data)
        return scoring.evaluate(review)

    def assertInvalid(self, res, fragment):
        self.assertFalse(res["valid"], "review should be INVALID")
        self.assertEqual(res["decision"], "NO-GO")
        self.assertEqual(res["exit_code"], 2)
        self.assertTrue(any(fragment in e for e in res["errors"]), f"{fragment!r} not in {res['errors']}")


class CompleteReview(Base):
    def test_complete_verified_review_is_go(self):
        res = scoring.evaluate(self.copy())
        self.assertTrue(res["valid"], res["errors"])
        self.assertEqual((res["decision"], res["overall"], res["exit_code"]), ("GO", 90, 0))
        self.assertEqual(len(res["rows"]), 23)

    def test_quick_review_with_its_eight_areas_is_go(self):
        res = scoring.evaluate(self.copy("quick", mode="quick"))
        self.assertEqual(res["decision"], "GO", res)


class FalseGoRegressions(Base):
    def test_architecture_only_cannot_be_go(self):
        """The v0.1 bug: one perfect area returned GO for the whole project."""
        res = self.run_with(lambda d, r: d.update(areas=[dict(area(d, 1), score=100)]))
        self.assertInvalid(res, "required areas missing")

    def test_one_missing_area_invalidates_full_review(self):
        res = self.run_with(lambda d, r: d["areas"].remove(area(d, 7)))
        self.assertInvalid(res, "7 Disaster Recovery")

    def test_quick_review_missing_an_area_is_invalid(self):
        res = self.run_with(lambda d, r: d["areas"].remove(area(d, 9)), "quick", mode="quick")
        self.assertInvalid(res, "9 Quality Assurance")

    def test_focused_review_needs_scope(self):
        res = self.run_with(lambda d, r: d.pop("scope"), "focused", mode="focused", scope=[2, 6])
        self.assertInvalid(res, "focused mode needs 'scope'")

    def test_focused_review_is_never_a_release_go(self):
        res = scoring.evaluate(self.copy("focused", mode="focused", scope=[2, 6]))
        self.assertTrue(res["valid"], res["errors"])
        self.assertEqual(res["decision"], "CONDITIONAL GO")
        self.assertTrue(any("outside this focused review" in c for c in res["conditions"]))

    def test_declared_evidence_levels_are_ignored(self):
        def m(d, r):
            a = area(d, 2)
            a["evidence_levels"] = ["verified"]
            a["checks"] = [a["checks"][1]]  # only the observation remains
            a["score"] = 100
        res = self.run_with(m)
        row = next(x for x in res["rows"] if x["id"] == 2)
        self.assertEqual((row["final"], row["basis"]), (75, "Observed only"))
        self.assertEqual(res["decision"], "CONDITIONAL GO")

    def test_invalid_input_files(self):
        review = self.copy()
        (review / "findings.json").write_text("{not json")
        self.assertInvalid(scoring.evaluate(review), "not valid JSON")
        (review / "findings.json").write_text("[]")
        self.assertInvalid(scoring.evaluate(review), "must be a JSON object")
        (review / "findings.json").unlink()
        self.assertInvalid(scoring.evaluate(review), "not found")
        self.assertInvalid(self.run_with(lambda d, r: d.update(areas="all good")), "'areas' must be a list")
        self.assertInvalid(self.run_with(lambda d, r: d.update(schema_version=1)), "schema_version")
        self.assertInvalid(self.run_with(lambda d, r: d.update(mode="mega")), "mode must be")

    def test_scores_out_of_range_or_wrong_type(self):
        for bad in (150, -1, "90", True, None, float("nan")):
            with self.subTest(score=bad):
                res = self.run_with(lambda d, r, bad=bad: area(d, 3).update(score=bad))
                self.assertInvalid(res, "score must be a number from 0 to 100")

    def test_duplicates_are_rejected(self):
        self.assertInvalid(self.run_with(lambda d, r: d["areas"].append(dict(area(d, 3)))), "listed more than once")

        def dup_finding(d, r):
            for aid in (3, 4):
                a = area(d, aid)
                a["findings"] = [finding("DUP-1", "low", a["checks"][0]["evidence"])]
        self.assertInvalid(self.run_with(dup_finding), "duplicate id DUP-1")

        def dup_evidence(d, r):
            log = read(r, "evidence-log.json")
            log["records"].append(dict(log["records"][0]))
            (r / "evidence-log.json").write_text(json.dumps(log))
        self.assertInvalid(self.run_with(dup_evidence), "duplicate evidence id")

    def test_area_id_and_name_must_be_real(self):
        self.assertInvalid(self.run_with(lambda d, r: area(d, 5).update(id=99)), "id must be an expert area")
        self.assertInvalid(self.run_with(lambda d, r: area(d, 5).update(name="Security")), "does not match")

    def test_assessed_area_without_checks(self):
        self.assertInvalid(self.run_with(lambda d, r: area(d, 5).update(checks=[])), "must list the checks")

        def all_skipped(d, r):
            area(d, 5)["checks"] = [{"id": "X", "title": "t", "result": "not_assessed", "reason": "no access"}]
        self.assertInvalid(self.run_with(all_skipped), "no check was actually performed")


class EvidenceIntegrity(Base):
    def test_unknown_evidence_id(self):
        res = self.run_with(lambda d, r: area(d, 2)["checks"][0].update(evidence=["E-999"]))
        self.assertInvalid(res, "no such record")

    def test_pass_without_evidence(self):
        res = self.run_with(lambda d, r: area(d, 2)["checks"][0].update(evidence=[]))
        self.assertInvalid(res, "needs a non-empty list of evidence ids")

    def test_tampered_artifact(self):
        def m(d, r):
            rec = read(r, "evidence-log.json")["records"][0]
            (r / rec["artifact"]).write_text("all 500 tests passed, trust me")
        self.assertInvalid(self.run_with(m), "modified after capture")

    def test_deleted_artifact(self):
        def m(d, r):
            (r / read(r, "evidence-log.json")["records"][0]["artifact"]).unlink()
        self.assertInvalid(self.run_with(m), "artifact file is missing")

    def test_artifact_path_cannot_escape_review_folder(self):
        def m(d, r):
            log = read(r, "evidence-log.json")
            log["records"][0]["artifact"] = "../../../../etc/hostname"
            (r / "evidence-log.json").write_text(json.dumps(log))
        self.assertInvalid(self.run_with(m), "escapes the review folder")

    def test_hand_written_command_record_is_not_verified(self):
        def m(d, r):
            log = read(r, "evidence-log.json")
            log["records"].append({"id": "E-900", "kind": "command", "area": 2, "title": "pentest",
                                   "command": "pentest --all", "started_at": "2026-11-20T00:00:00Z",
                                   "exit_code": 0, "artifact": "evidence/none.txt", "sha256": "0" * 64})
            (r / "evidence-log.json").write_text(json.dumps(log))
            area(d, 2)["checks"][0]["evidence"] = ["E-900"]
        self.assertInvalid(self.run_with(m), "artifact file is missing")

    def test_pass_needs_more_than_an_inference(self):
        def m(d, r):
            rec = evidence.add_note(r, 7, "probably backed up", "inference", "hosting usually does backups")
            area(d, 7)["checks"] = [{"id": "DR-1", "title": "backups exist", "result": "pass", "evidence": [rec["id"]]}]
        self.assertInvalid(self.run_with(m), "marked pass but no evidence supports it")

    def test_command_that_never_ran_cannot_support_a_pass(self):
        def m(d, r):
            rec = evidence.run_command(r, 9, "tests", ["definitely-not-a-real-tool-xyz", "test"])
            self.assertEqual(rec["exit_code"], 127)
            area(d, 9)["checks"] = [{"id": "QA-1", "title": "tests pass", "result": "pass", "evidence": [rec["id"]]}]
        self.assertInvalid(self.run_with(m), "marked pass but no evidence supports it")

    def test_evidence_from_another_area(self):
        def m(d, r):
            area(d, 2)["checks"][0]["evidence"] = area(d, 9)["checks"][0]["evidence"]
        self.assertInvalid(self.run_with(m), "was recorded for area 9, not area 2")

    def test_synthesis_areas_may_reuse_evidence(self):
        def m(d, r):
            area(d, 22)["checks"].append({"id": "TL-9", "title": "cross-check", "result": "pass",
                                          "evidence": area(d, 9)["checks"][0]["evidence"]})
        self.assertEqual(self.run_with(m)["decision"], "GO")


class FindingsPolicy(Base):
    def ev(self, d, aid):
        return area(d, aid)["checks"][0]["evidence"]

    def test_open_critical_blocks(self):
        res = self.run_with(lambda d, r: area(d, 13).update(findings=[finding("UX-1", "critical", self.ev(d, 13))]))
        self.assertEqual((res["decision"], res["exit_code"]), ("NO-GO", 20))
        self.assertEqual(next(x for x in res["rows"] if x["id"] == 13)["final"], 40)

    def test_accepting_a_critical_does_not_lift_it(self):
        mit = {"approved_by": "Sara", "reason": "launch pressure", "date": "2026-11-20", "controls": ["WAF rule"]}
        res = self.run_with(lambda d, r: area(d, 2).update(
            findings=[finding("SEC-1", "critical", self.ev(d, 2), "accepted", mitigation=mit)]))
        self.assertEqual(res["decision"], "NO-GO")
        self.assertTrue(any("does not lift a Critical" in b for b in res["blockers"]))

    def test_open_high_is_conditional(self):
        res = self.run_with(lambda d, r: area(d, 3).update(findings=[finding("PERF-1", "high", self.ev(d, 3))]))
        self.assertEqual((res["decision"], res["exit_code"]), ("CONDITIONAL GO", 10))

    def test_accepted_high_needs_documented_mitigation(self):
        res = self.run_with(lambda d, r: area(d, 3).update(
            findings=[finding("PERF-1", "high", self.ev(d, 3), "accepted", mitigation={"approved_by": "Sara"})]))
        self.assertInvalid(res, "accepted risk needs mitigation fields ['reason', 'date', 'controls']")
        res = self.run_with(lambda d, r: area(d, 3).update(
            findings=[finding("PERF-1", "high", self.ev(d, 3), "accepted")]))
        self.assertInvalid(res, "accepted risk needs mitigation fields")

    def test_accepted_high_with_mitigation(self):
        mit = {"approved_by": "Sara", "reason": "low traffic", "date": "2026-11-20", "controls": ["rate limit"]}

        def m(d, r):
            area(d, 3)["findings"] = [finding("PERF-1", "high", self.ev(d, 3), "accepted", mitigation=mit)]
        self.assertEqual(self.run_with(m)["decision"], "GO")

        def sensitive(d, r):
            m(d, r)
            d["risk_profile"] = "sensitive"
        res = self.run_with(sensitive)
        self.assertEqual(res["decision"], "CONDITIONAL GO")

    def test_fixed_needs_a_recheck_that_ran(self):
        res = self.run_with(lambda d, r: area(d, 2).update(
            findings=[finding("SEC-1", "critical", self.ev(d, 2), "fixed")]))
        self.assertInvalid(res, "verification: needs a non-empty list")

        def observed_only(d, r):
            area(d, 2)["findings"] = [finding("SEC-1", "critical", self.ev(d, 2), "fixed",
                                              verification=area(d, 2)["checks"][1]["evidence"])]
        self.assertInvalid(self.run_with(observed_only), "'fixed' needs a re-check that ran and succeeded")

        def verified(d, r):
            rec = evidence.run_command(r, 2, "re-test injection", OK_CMD)
            area(d, 2)["findings"] = [finding("SEC-1", "critical", self.ev(d, 2), "fixed", verification=[rec["id"]])]
        self.assertEqual(self.run_with(verified)["decision"], "GO")

    def test_false_positive_needs_reason_and_bad_enums_rejected(self):
        self.assertInvalid(self.run_with(lambda d, r: area(d, 2).update(
            findings=[finding("SEC-1", "high", self.ev(d, 2), "false_positive")])), "false_positive needs a 'reason'")
        self.assertInvalid(self.run_with(lambda d, r: area(d, 2).update(
            findings=[finding("SEC-1", "urgent", self.ev(d, 2))])), "severity must be")
        self.assertInvalid(self.run_with(lambda d, r: area(d, 2).update(
            findings=[finding("SEC-1", "high", self.ev(d, 2), "wontfix")])), "status must be")


class GatesAndProfiles(Base):
    def test_core_scores(self):
        res = self.run_with(lambda d, r: area(d, 9).update(score=70))
        self.assertEqual(res["decision"], "CONDITIONAL GO")
        res = self.run_with(lambda d, r: area(d, 9).update(score=50))
        self.assertEqual(res["decision"], "NO-GO")

    def test_not_assessed_and_not_applicable(self):
        na = {"status": "not_assessed", "reason": "no access to backups"}
        self.assertEqual(self.run_with(lambda d, r: area(d, 7).update(na))["decision"], "NO-GO")
        self.assertEqual(self.run_with(lambda d, r: area(d, 20).update(na))["decision"], "CONDITIONAL GO")
        self.assertInvalid(self.run_with(lambda d, r: area(d, 20).update(status="not_assessed")), "needs a 'reason'")
        ok = self.run_with(lambda d, r: area(d, 13).update(status="not_applicable", reason="no user interface"))
        self.assertEqual(ok["decision"], "GO")
        bad = self.run_with(lambda d, r: area(d, 2).update(status="not_applicable", reason="it is fine"))
        self.assertInvalid(bad, "cannot be not_applicable")

    def test_partial_core_area_is_conditional(self):
        self.assertEqual(self.run_with(lambda d, r: area(d, 6).update(status="partial"))["decision"], "CONDITIONAL GO")

    def test_intake_is_required(self):
        review = self.copy()
        (review / "intake.json").unlink()
        self.assertInvalid(scoring.evaluate(review), "intake.json is missing")

    def test_intake_missing_required_answer(self):
        review = self.copy()
        intake = read(review, "intake.json")
        del intake["answers"]["data_types"]
        write(review, intake=intake)
        self.assertInvalid(scoring.evaluate(review), "required answer missing: data_types")

    def test_risk_profile_cannot_be_downgraded(self):
        review = self.copy()
        intake = read(review, "intake.json")
        intake["answers"]["data_types"] = ["health", "personal"]
        write(review, intake=intake)
        self.assertInvalid(scoring.evaluate(review), "lower than the intake answers require ('regulated')")

    def test_regulated_profile_tightens_gates(self):
        review = self.copy()
        intake = read(review, "intake.json")
        intake["answers"]["data_types"] = ["health"]
        data = read(review)
        data["risk_profile"] = "regulated"
        write(review, data, intake)
        self.assertEqual(scoring.evaluate(review)["decision"], "GO")  # every area is at 90
        area(data, 19).update(status="not_assessed", reason="no lawyer available")
        write(review, data)
        res = scoring.evaluate(review)
        self.assertEqual(res["decision"], "NO-GO")
        area(data, 19).update(status="assessed", score=85)
        write(review, data)
        self.assertEqual(scoring.evaluate(review)["decision"], "CONDITIONAL GO")

    def test_mode_must_match_intake(self):
        self.assertInvalid(self.run_with(lambda d, r: d.update(mode="quick")), "mode differs from the review_mode")


if __name__ == "__main__":
    unittest.main()
