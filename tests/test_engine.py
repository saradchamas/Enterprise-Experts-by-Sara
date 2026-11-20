"""Unit tests: evidence capture, command policy, secret masking, intake, state, discovery adapters."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FIXTURES, OK_CMD

from ee import evidence, intake, state
from ee.discovery import discover, to_markdown
from ee.policy import check_command
from ee.secrets import mask_text


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ee-unit-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class EvidenceCapture(Tmp):
    def test_command_record_has_traceable_fields(self):
        rec = evidence.run_command(self.tmp, 9, "Unit tests", OK_CMD)
        for key in ("id", "command", "exit_code", "started_at", "duration_s", "artifact", "sha256", "runner"):
            self.assertIn(key, rec)
        self.assertEqual((rec["id"], rec["exit_code"]), ("E-001", 0))
        self.assertIn("check passed", (self.tmp / rec["artifact"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence.record_level(rec, self.tmp), ("verified", None))
        self.assertEqual(evidence.run_command(self.tmp, 9, "again", OK_CMD)["id"], "E-002")

    def test_failing_command_is_recorded_not_hidden(self):
        rec = evidence.run_command(self.tmp, 9, "fails", [sys.executable, "-c", "import sys; sys.exit(3)"])
        self.assertEqual(rec["exit_code"], 3)

    def test_timeout_is_recorded(self):
        rec = evidence.run_command(self.tmp, 3, "slow", [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
        self.assertTrue(rec["timed_out"])
        self.assertIsNone(rec["exit_code"])

    def test_secrets_never_reach_evidence_files(self):
        key = "sk-" + "a1B2" * 8            # built at runtime so no secret-shaped string is committed
        aws = "AKIA" + "ABCDEFGHIJKLMNOP"
        code = f"print('key={key}'); print('aws {aws}'); print('DB_PASSWORD=hunter2hunter2')"
        rec = evidence.run_command(self.tmp, 2, "leaky", [sys.executable, "-c", code])
        text = (self.tmp / rec["artifact"]).read_text(encoding="utf-8") + json.dumps(rec)
        for secret in (key, aws, "hunter2hunter2"):
            self.assertNotIn(secret, text)

    def test_mask_text_patterns(self):
        url = "postgres://user:" + "Sup3rS3cret" + "@db:5432/x"
        self.assertNotIn("Sup3rS3cret", mask_text(url))
        self.assertEqual(mask_text("nothing secret here"), "nothing secret here")

    def test_notes(self):
        with self.assertRaises(ValueError):
            evidence.add_note(self.tmp, 2, "t", "observation", "no location")
        with self.assertRaises(ValueError):
            evidence.add_note(self.tmp, 2, "t", "observation", "d", "missing.py:1", str(FIXTURES / "healthy-node"))
        with self.assertRaises(ValueError):
            evidence.add_note(self.tmp, 99, "t", "inference", "d")
        obs = evidence.add_note(self.tmp, 2, "t", "observation", "d", "src/index.js:1", str(FIXTURES / "healthy-node"))
        self.assertEqual(evidence.record_level(obs, self.tmp)[0], "observed")
        inf = evidence.add_note(self.tmp, 2, "t", "inference", "guess")
        self.assertEqual(evidence.record_level(inf, self.tmp)[0], "inferred")

    def test_git_commit_is_read_without_git_binary(self):
        (self.tmp / ".git" / "refs" / "heads").mkdir(parents=True)
        (self.tmp / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (self.tmp / ".git" / "refs" / "heads" / "main").write_text("a" * 40 + "\n")
        self.assertEqual(evidence.git_commit(self.tmp), "a" * 40)
        self.assertIsNone(evidence.git_commit(self.tmp / "nowhere"))


class CommandPolicy(Tmp):
    RISKY = ["rm -rf build", "git push origin main", "git reset --hard HEAD~1", "terraform apply -auto-approve",
             "kubectl delete pod x", "docker push repo/img", "npm publish", "vercel deploy --prod",
             "psql -c DROP TABLE users", "npx prisma migrate deploy", "php artisan migrate",
             "curl -X POST https://api.example.com/x", "aws s3 rm s3://bucket --recursive", "helm upgrade app ."]
    SAFE = ["npm test", "npm audit --omit=dev", "python -m pytest -q", "go test ./...", "git log --oneline",
            "git status", "terraform validate", "terraform fmt -check", "docker build -t x .", "ruff check ."]

    def test_risky_commands_need_approval(self):
        for cmd in self.RISKY:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(check_command(cmd.split()))

    def test_ordinary_checks_are_allowed(self):
        for cmd in self.SAFE:
            with self.subTest(cmd=cmd):
                self.assertIsNone(check_command(cmd.split()))

    def test_refusal_runs_nothing_and_approval_is_recorded(self):
        marker = self.tmp / "marker"
        argv = [sys.executable, "-c", f"open(r'{marker}','w'); print('git push')", "git", "push"]
        with self.assertRaises(PermissionError):
            evidence.run_command(self.tmp, 10, "push", argv)
        self.assertFalse(marker.exists())
        self.assertEqual(evidence.load_log(self.tmp)["records"], [])
        rec = evidence.run_command(self.tmp, 10, "push", argv, approved=True)
        self.assertTrue(rec["approved_risky_command"])


class Intake(unittest.TestCase):
    BASE = {"purpose": "x", "stage": "prototype", "exposure": "internal", "industry": "internal_tool",
            "data_types": ["none"], "handles_money": "no", "review_mode": "full",
            "change_permission": "assess_only", "environments_allowed": ["local"]}

    def test_risk_profile_derivation(self):
        d = intake.derive_risk_profile
        self.assertEqual(d(self.BASE), "standard")
        self.assertEqual(d(dict(self.BASE, data_types=["personal"])), "sensitive")
        self.assertEqual(d(dict(self.BASE, handles_money="yes")), "sensitive")
        self.assertEqual(d(dict(self.BASE, exposure="public", stage="production")), "sensitive")
        self.assertEqual(d(dict(self.BASE, data_types=["health"])), "regulated")
        self.assertEqual(d(dict(self.BASE, data_types=["payment_card"])), "regulated")
        self.assertEqual(d(dict(self.BASE, industry="healthcare")), "regulated")
        self.assertEqual(d(dict(self.BASE, data_types="unknown")), "sensitive")  # not knowing is a risk
        self.assertEqual(d({}), "sensitive")

    def test_profile_can_be_raised_not_lowered(self):
        self.assertEqual(intake.effective_risk_profile({"answers": self.BASE, "risk_profile": "regulated"}), "regulated")
        health = dict(self.BASE, data_types=["health"])
        self.assertEqual(intake.effective_risk_profile({"answers": health, "risk_profile": "standard"}), "regulated")

    def test_validation(self):
        self.assertEqual(intake.validate_intake({"answers": self.BASE}), [])
        self.assertTrue(intake.validate_intake({"answers": dict(self.BASE, stage="soon")}))
        self.assertTrue(intake.validate_intake({"answers": dict(self.BASE, data_types="personal")}))
        self.assertTrue(intake.validate_intake({"answers": dict(self.BASE, review_mode="focused")}))
        self.assertTrue(intake.validate_intake({}))
        self.assertEqual(intake.validate_intake({"answers": dict(self.BASE, stage="unknown")}), [])

    def test_questions_follow_discovery(self):
        keys = lambda **f: {q["key"] for q in intake.questions_for(f)}  # noqa: E731
        self.assertNotIn("backups", keys())
        self.assertIn("backups", keys(has_database=True))
        self.assertIn("ai_usage", keys(has_ai=True))
        self.assertNotIn("ui_audience", keys(has_database=True))
        self.assertIn("focus_areas", {q["key"] for q in intake.questions_for({}, "focused")})
        for key in intake.REQUIRED_KEYS:
            self.assertIn(key, keys())
        self.assertEqual(len(intake.QUESTION_KEYS), len(intake.QUESTIONS))


class State(Tmp):
    def test_waves_and_resume(self):
        state.init(self.tmp, "quick")
        plan = state.plan(state.load(self.tmp))
        self.assertEqual((plan["wave"], plan["ready"]), ("Foundation", [1, 6]))
        self.assertIn(2, plan["blocked"])
        state.set_status(self.tmp, 1, "done")
        state.set_status(self.tmp, 6, "in_progress")   # ... and the session dies here
        plan = state.plan(state.load(self.tmp))        # a new session picks it up
        self.assertEqual((plan["interrupted"], plan["done"], plan["wave"]), ([6], [1], "Foundation"))
        state.set_status(self.tmp, 6, "done")
        self.assertEqual(state.plan(state.load(self.tmp))["ready"], [2])
        for a in (2, 5, 8, 7, 9, 10):
            state.set_status(self.tmp, a, "done")
        self.assertTrue(state.plan(state.load(self.tmp))["complete"])

    def test_guards(self):
        with self.assertRaises(ValueError):
            state.init(self.tmp, "focused")
        state.init(self.tmp, "focused", [2, 6])
        with self.assertRaises(FileExistsError):
            state.init(self.tmp, "full")
        with self.assertRaises(ValueError):
            state.set_status(self.tmp, 9, "done")
        with self.assertRaises(ValueError):
            state.set_status(self.tmp, 2, "finished")
        self.assertFalse(list(self.tmp.glob("*.tmp")))

    def test_failed_area_keeps_later_waves_blocked(self):
        state.init(self.tmp, "focused", [1, 2])
        state.set_status(self.tmp, 1, "failed", "crashed")
        plan = state.plan(state.load(self.tmp))
        self.assertEqual((plan["failed"], plan["blocked"], plan["complete"]), ([1], [2], False))


class DiscoveryAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = {p.name: discover(p) for p in FIXTURES.iterdir() if p.is_dir()}

    def stack(self, fixture, path="."):
        return next(s for s in self.d[fixture]["stacks"] if s["path"] == path)

    def test_healthy_node(self):
        d, s = self.d["healthy-node"], self.stack("healthy-node")
        self.assertEqual(s["commands"]["test"], ["npm", "test"])
        self.assertEqual(s["commands"]["install"], ["npm", "ci"])
        self.assertTrue(d["flags"]["has_ci"] and d["flags"]["has_containers"])
        self.assertEqual((d["secrets"], d["notes"]), ([], ["No error-tracking, metrics or logging library detected in manifests."]))

    def test_flawed_node_finds_and_masks_secrets(self):
        d = self.d["flawed-node"]
        self.assertEqual({s["file"] for s in d["secrets"]}, {".env"})
        self.assertEqual(len(d["secrets"]), 2)
        dump = json.dumps(d) + to_markdown(d)
        for raw in ("FixturePassw0rd", "fixture-not-a-real-secret-0001"):
            self.assertNotIn(raw, dump)
        self.assertTrue(d["flags"]["has_database"] and d["flags"]["has_api"] and d["flags"]["has_paid_services"])
        self.assertIsNone(self.stack("flawed-node")["commands"]["install"])
        self.assertIn("lockfile", self.stack("flawed-node")["unavailable"]["install"])
        self.assertIn("No CI/CD configuration found.", d["notes"])

    def test_monorepo(self):
        d = self.d["monorepo"]
        self.assertTrue(d["flags"]["is_monorepo"] and d["flags"]["has_ui"])
        self.assertEqual({(s["path"], s["adapter"]) for s in d["stacks"]},
                         {(".", "node"), ("apps/web", "node"), ("apps/api", "node"), ("services/worker", "python")})
        self.assertEqual(self.stack("monorepo", "apps/web")["commands"]["typecheck"][-1], "--noEmit")
        self.assertIsNone(self.stack("monorepo", "apps/web")["commands"]["test"])
        self.assertEqual(self.stack("monorepo", "services/worker")["commands"]["lint"], ["ruff", "check", "."])

    def test_python_ai_app(self):
        d = self.d["python-fastapi"]
        self.assertTrue(d["flags"]["has_ai"] and d["flags"]["has_api"] and d["flags"]["has_database"])
        self.assertEqual(self.stack("python-fastapi")["commands"]["typecheck"], ["mypy", "."])
        self.assertIn("OpenAI", d["ai_libraries"])

    def test_go_service(self):
        self.assertEqual(self.stack("go-service")["commands"]["test"], ["go", "test", "./..."])

    def test_unsupported_stack_is_reported_not_guessed(self):
        d = self.d["unsupported-elixir"]
        self.assertEqual(d["stacks"], [])
        self.assertTrue(d["flags"]["unsupported_stack"])
        self.assertEqual(d["unsupported"][0]["language"], "Elixir")
        self.assertIn("Not assessed", " ".join(d["notes"]))

    def test_infrastructure_only(self):
        d = self.d["infra-only"]
        self.assertTrue(d["flags"]["infrastructure_only"] and d["flags"]["has_iac"])
        self.assertEqual([s["adapter"] for s in d["stacks"]], ["terraform"])
        self.assertFalse(d["flags"]["unsupported_stack"])

    def test_every_stack_declares_all_checks_and_reasons(self):
        for name, d in self.d.items():
            for s in d["stacks"]:
                for check, cmd in s["commands"].items():
                    with self.subTest(fixture=name, check=check):
                        self.assertTrue(cmd or s["unavailable"].get(check), "missing command needs a reason")
                self.assertIsInstance(s["prerequisites"], dict)

    def test_empty_directory(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        d = discover(tmp)
        self.assertEqual((d["stacks"], d["source_files"], d["flags"]["unsupported_stack"]), ([], 0, False))
        self.assertTrue(to_markdown(d))


if __name__ == "__main__":
    unittest.main()
