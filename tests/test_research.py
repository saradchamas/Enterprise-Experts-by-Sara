"""Research and proposals: dated sources, supported proposals, approval and verification."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.helpers import SCRIPTS, build_review

sys.path.insert(0, str(SCRIPTS))
from ee import cli, evidence, guard, package, research, state  # noqa: E402

TODAY = date(2026, 11, 20)
OK = [sys.executable, "-c", "print('ok')"]
FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]


class ResearchCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.review = Path(self.tmp.name) / "review"
        build_review(self.review)
        state.init(self.review, "full")
        self.project = str(self.review / "_project")

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, **kw):
        args = dict(area=1, category="mcp", subject="Example MCP server", claim="Offers read-only access to issues",
                    url="https://example.org/docs/mcp", official=True, today=TODAY)
        args.update(kw)
        return research.add_source(self.review, **args)

    def proposal(self, sources, **kw):
        args = dict(area=1, category="mcp", action="adopt", title="Connect the issue tracker",
                    goal="see open bugs during reviews", alternatives=["keep exporting CSV by hand"])
        args.update(kw)
        return research.propose(self.review, sources=sources, **args)


class Sources(ResearchCase):
    def test_a_source_is_dated_and_lands_in_the_evidence_log(self):
        s = self.source()
        self.assertEqual((s["id"], s["retrieved"]), ("R-001", "2026-11-20"))
        record = next(r for r in evidence.load_log(self.review)["records"] if r["id"] == s["evidence"])
        self.assertEqual((record["kind"], record["location"]), ("observation", "https://example.org/docs/mcp"))

    def test_memory_is_not_a_source(self):
        for url in ("", "from memory", "example.org/page", "ftp://example.org/x"):
            with self.assertRaises(ValueError):
                self.source(url=url)

    def test_future_dates_and_empty_claims_are_refused(self):
        with self.assertRaises(ValueError):
            self.source(retrieved="2027-01-01")
        with self.assertRaises(ValueError):
            self.source(claim="  ")
        with self.assertRaises(ValueError):
            self.source(retrieved="last week")


class Proposals(ResearchCase):
    def test_a_proposal_must_solve_something_cite_sources_and_weigh_an_alternative(self):
        s = self.source()
        with self.assertRaises(ValueError):
            self.proposal([s["id"]], goal=None)
        with self.assertRaises(ValueError):
            self.proposal([])
        with self.assertRaises(ValueError):
            self.proposal(["R-999"])
        with self.assertRaises(ValueError):
            self.proposal([s["id"]], alternatives=[])
        with self.assertRaises(ValueError):
            self.proposal([s["id"]], findings=["NOPE-001"])
        self.assertEqual(self.proposal([s["id"]])["status"], "proposed")

    def test_tools_models_and_mcp_servers_need_an_official_source(self):
        s = self.source(official=False, url="https://blog.example.com/top-10-mcp")
        p = self.proposal([s["id"]])
        result = research.check(self.review, today=TODAY)
        self.assertFalse(result["valid"])
        self.assertIn("official source", result["problems"][p["id"]][0])
        with self.assertRaises(ValueError):
            research.decide(self.review, p["id"], "approved", by="Sara", today=TODAY)

    def test_a_practice_does_not_need_an_official_source(self):
        s = self.source(category="practice", official=False)
        self.proposal([s["id"]], category="practice")
        self.assertTrue(research.check(self.review, today=TODAY)["valid"])

    def test_sources_for_fast_moving_facts_go_stale(self):
        s = self.source(category="model", retrieved="2026-07-01")
        p = self.proposal([s["id"]], category="model")
        result = research.check(self.review, today=TODAY)
        self.assertIn("days ago", result["problems"][p["id"]][0])
        fresh = self.source(category="model", retrieved="2026-11-19")
        p2 = self.proposal([s["id"], fresh["id"]], category="model")
        self.assertIn(p2["id"], research.check(self.review, today=TODAY)["supported"])

    def test_an_old_source_is_fine_for_a_practice(self):
        s = self.source(category="practice", retrieved="2025-01-01")
        self.proposal([s["id"]], category="practice")
        self.assertTrue(research.check(self.review, today=TODAY)["valid"])


class Lifecycle(ResearchCase):
    def approved(self):
        s = self.source()
        p = self.proposal([s["id"]])
        research.decide(self.review, p["id"], "approved", by="Sara", paths=["app.py"], today=TODAY)
        return p["id"]

    def test_approval_needs_a_name_and_opens_only_the_named_files(self):
        s = self.source()
        p = self.proposal([s["id"]])
        with self.assertRaises(ValueError):
            research.decide(self.review, p["id"], "approved", today=TODAY)
        research.decide(self.review, p["id"], "approved", by="Sara", paths=["app.py"], today=TODAY)
        approvals = state.load(self.review)["approvals"]
        self.assertEqual((approvals[-1]["paths"], approvals[-1]["approved_by"]), (["app.py"], "Sara"))
        self.assertIn(p["id"], approvals[-1]["note"])

    def test_nothing_is_implemented_without_approval(self):
        s = self.source()
        p = self.proposal([s["id"]])
        with self.assertRaises(ValueError):
            research.decide(self.review, p["id"], "implemented")

    def test_verified_needs_a_check_that_passed_after_approval(self):
        before = evidence.run_command(self.review, 1, "ran before approval", OK, cwd=self.project)
        pid = self.approved()
        research.decide(self.review, pid, "implemented")
        with self.assertRaises(ValueError):
            research.decide(self.review, pid, "verified")
        with self.assertRaises(ValueError):
            research.decide(self.review, pid, "verified", evidence_id=before["id"])
        import time
        time.sleep(1.1)  # evidence timestamps have one-second resolution
        failed = evidence.run_command(self.review, 1, "check fails", FAIL, cwd=self.project)
        note = evidence.add_note(self.review, 1, "looked", "observation", "seems fine", "app.py:1", self.project)
        for bad in (failed["id"], note["id"], "E-999"):
            with self.assertRaises(ValueError):
                research.decide(self.review, pid, "verified", evidence_id=bad)
        passed = evidence.run_command(self.review, 1, "check passes", OK, cwd=self.project)
        self.assertEqual(research.decide(self.review, pid, "verified", evidence_id=passed["id"])["status"], "verified")
        self.assertTrue(research.check(self.review, today=TODAY)["valid"])

    def test_a_status_edited_by_hand_is_caught(self):
        s = self.source()
        p = self.proposal([s["id"]])
        data = research.load(self.review)
        data["proposals"][0]["status"] = "verified"
        (self.review / research.FILE_NAME).write_text(json.dumps(data), encoding="utf-8")
        problems = research.check(self.review, today=TODAY)["problems"][p["id"]]
        self.assertTrue(any("without a recorded approval" in x for x in problems))

    def test_not_now_is_recorded_as_deferred_and_can_still_be_approved(self):
        s = self.source()
        p = self.proposal([s["id"]])
        with self.assertRaises(ValueError):
            research.decide(self.review, p["id"], "deferred")
        research.decide(self.review, p["id"], "deferred", reason="waiting for the hosting decision")
        research.write_log(self.review, today=TODAY)
        text = (self.review / "research-log.md").read_text(encoding="utf-8")
        self.assertIn("status **deferred**", text)
        self.assertIn("waiting for the hosting decision", text)
        self.assertEqual(research.decide(self.review, p["id"], "approved", by="Sara", today=TODAY)["status"], "approved")

    def test_rejection_needs_a_reason(self):
        s = self.source()
        p = self.proposal([s["id"]])
        with self.assertRaises(ValueError):
            research.decide(self.review, p["id"], "rejected")
        self.assertEqual(research.decide(self.review, p["id"], "rejected", reason="not needed")["status"], "rejected")


class Outputs(ResearchCase):
    def test_log_separates_supported_from_unsupported(self):
        good = self.source()
        self.proposal([good["id"]], title="Supported idea")
        weak = self.source(official=False, url="https://blog.example.com/post")
        self.proposal([weak["id"]], title="Unsupported idea")
        result = research.write_log(self.review, today=TODAY)
        text = (self.review / "research-log.md").read_text(encoding="utf-8")
        ok, bad = text.split("## Proposals that must not be acted on yet")
        self.assertIn("Supported idea", ok)
        self.assertIn("Unsupported idea", bad)
        self.assertIn("read 2026-11-20", text)
        self.assertFalse(result["valid"])

    def test_package_includes_the_research_log(self):
        s = self.source()
        self.proposal([s["id"]])
        out = package.build(self.review)
        self.assertIn("P-001", out["research"]["supported"])
        self.assertTrue((Path(out["path"]) / "06-evidence" / "research-log.md").exists() or
                        list(Path(out["path"]).rglob("research-log.md")))

    def test_cli_round_trip_and_exit_codes(self):
        r = str(self.review)
        self.assertEqual(cli.main(["research", "add", "--review", r, "--area", "2", "--category", "tool", "--subject", "Scanner X",
                                   "--claim", "Version 3 supports SARIF", "--url", "https://example.org/x", "--official"]), 0)
        self.assertEqual(cli.main(["research", "propose", "--review", r, "--area", "2", "--category", "tool", "--title", "Add scanner X",
                                   "--sources", "R-001", "--goal", "catch leaks in CI", "--alternatives", "do nothing"]), 0)
        self.assertEqual(cli.main(["research", "check", "--review", r]), 0)
        self.assertEqual(cli.main(["research", "add", "--review", r, "--area", "2", "--subject", "x", "--claim", "y", "--url", "memory"]), 2)
        self.assertEqual(cli.main(["research", "decide", "--review", r, "--id", "P-001", "--status", "implemented"]), 2)
        self.assertEqual(cli.main(["research", "log", "--review", r]), 0)

    def test_guard_protects_the_research_file(self):
        self.assertIn("research.json", guard.ENGINE_OWNED)


if __name__ == "__main__":
    unittest.main()
