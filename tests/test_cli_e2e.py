"""End-to-end: drives the real CLI as a subprocess through a whole review."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import BASE_ANSWERS, FIXTURES, REPO, SCRIPTS

from ee import __version__
from ee.areas import AREAS, QUICK_AREAS

CLI = [sys.executable, str(SCRIPTS / "enterprise_experts.py")]


def cli(*args, cwd=None):
    return subprocess.run(CLI + [str(a) for a in args], capture_output=True, text=True, cwd=cwd,
                          encoding="utf-8", errors="replace")


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.review = Path(tempfile.mkdtemp(prefix="ee-e2e-")) / "review"
        self.addCleanup(shutil.rmtree, self.review.parent, ignore_errors=True)

    def evidence(self, area, title, *command, project):
        out = cli("evidence", "run", "--review", self.review, "--area", area, "--title", title,
                  "--cwd", project, "--", *command)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def note(self, area, title, location, project):
        out = cli("evidence", "note", "--review", self.review, "--area", area, "--title", title,
                  "--kind", "observation", "--location", location, "--project", project, "--detail", "read")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def quick_review(self, fixture, sec_finding):
        project = FIXTURES / fixture
        self.assertEqual(cli("discover", project, "--out", self.review).returncode, 0)
        questions = json.loads(cli("questions", "--review", self.review, "--mode", "quick").stdout)
        self.assertTrue(questions["discovery_used"])
        (self.review / "intake.json").write_text(json.dumps(
            {"answers": dict(BASE_ANSWERS, review_mode="quick")}))
        self.assertEqual(cli("intake", "--review", self.review).returncode, 0)
        self.assertEqual(cli("state", "init", "--review", self.review, "--mode", "quick").returncode, 0)
        areas = []
        for aid in sorted(QUICK_AREAS):
            ran = self.evidence(aid, f"area {aid} check", sys.executable, "-c", "print('ok')", project=project)
            areas.append({"id": aid, "name": AREAS[aid], "status": "assessed", "score": 88, "findings": [],
                          "checks": [{"id": f"K{aid}", "title": "check", "result": "pass", "evidence": [ran["id"]]}]})
            cli("state", "set", "--review", self.review, "--area", aid, "--status", "done")
        if sec_finding:
            obs = self.note(2, "SQL built by string concatenation", "src/server.js:7", project)
            areas[1]["findings"] = [{"id": "SEC-001", "severity": "critical", "status": "open",
                                     "title": "SQL injection in GET /orders/:id", "evidence": [obs["id"]]}]
        (self.review / "findings.json").write_text(json.dumps(
            {"schema_version": 2, "project": fixture, "review_date": "2026-11-20", "mode": "quick",
             "risk_profile": "standard", "areas": areas}))
        return questions

    def test_flawed_project_ends_in_no_go(self):
        questions = self.quick_review("flawed-node", sec_finding=True)
        self.assertIn("backups", [q["key"] for q in questions["questions"]])   # it has a database
        out = cli("score", "--review", self.review)
        self.assertEqual(out.returncode, 20, out.stdout)
        self.assertIn("Decision: NO-GO", out.stdout)
        self.assertIn("SEC-001", out.stdout)
        for name in ("scorecard.md", "scorecard.json", "scorecard.html", "discovery.md", "evidence-log.json"):
            self.assertTrue((self.review / name).exists(), name)
        self.assertIn("NO-GO", (self.review / "scorecard.html").read_text(encoding="utf-8"))
        everything = "".join(p.read_text(encoding="utf-8") for p in self.review.rglob("*") if p.is_file())
        self.assertNotIn("FixturePassw0rd", everything)

    def test_healthy_project_can_reach_go(self):
        questions = self.quick_review("healthy-node", sec_finding=False)
        self.assertNotIn("backups", [q["key"] for q in questions["questions"]])  # no database here
        out = cli("score", "--review", self.review, "--json")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(json.loads(out.stdout)["decision"], "GO")
        self.assertTrue(json.loads(cli("state", "show", "--review", self.review).stdout)["plan"]["complete"])

    def test_real_project_tests_become_verified_evidence(self):
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        self.review.mkdir(parents=True)
        rec = self.evidence(9, "unit tests", "node", "--test", project=FIXTURES / "healthy-node")
        self.assertEqual(rec["exit_code"], 0)
        self.assertIn("pass 1", (self.review / rec["artifact"]).read_text(encoding="utf-8"))

    def test_incomplete_review_is_invalid_not_go(self):
        self.quick_review("healthy-node", sec_finding=False)
        data = json.loads((self.review / "findings.json").read_text(encoding="utf-8"))
        data["areas"] = data["areas"][:1]
        (self.review / "findings.json").write_text(json.dumps(data))
        self.assertEqual(cli("validate", "--review", self.review).returncode, 2)
        out = cli("score", "--review", self.review)
        self.assertEqual(out.returncode, 2)
        self.assertIn("INVALID REVIEW — NO-GO", out.stdout)

    def test_interrupted_review_fails_safe(self):
        """Evidence gathered, then the session died before findings.json was written."""
        self.review.mkdir(parents=True)
        cli("state", "init", "--review", self.review, "--mode", "full")
        cli("state", "set", "--review", self.review, "--area", 1, "--status", "in_progress")
        self.assertEqual(cli("score", "--review", self.review).returncode, 2)
        plan = json.loads(cli("state", "show", "--review", self.review).stdout)["plan"]
        self.assertEqual(plan["in_progress"], [1])
        self.assertEqual(cli("state", "init", "--review", self.review, "--mode", "full").returncode, 2)

    def test_risky_command_is_refused(self):
        self.review.mkdir(parents=True)
        out = cli("evidence", "run", "--review", self.review, "--area", 10, "--title", "deploy",
                  "--", "git", "push", "origin", "main")
        self.assertEqual(out.returncode, 3)
        self.assertIn("approval", out.stderr)

    def test_scorecard_prints_on_a_legacy_console(self):
        """Windows consoles default to a code page that cannot encode the star in the scorecard."""
        self.quick_review("healthy-node", sec_finding=False)
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        out = subprocess.run(CLI + ["score", "--review", str(self.review)], capture_output=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Decision: GO", out.stdout.decode("utf-8"))

    def test_misc_commands(self):
        self.assertEqual(cli("--version").stdout.strip(), __version__)
        self.assertEqual(cli("discover", "/definitely/not/here").returncode, 2)
        self.assertEqual(cli("intake", "--review", self.review).returncode, 2)
        old = subprocess.run([sys.executable, str(SCRIPTS / "discover_project.py"), str(FIXTURES / "go-service")],
                             capture_output=True, text=True)
        self.assertIn("go test ./...", old.stdout)
        old = subprocess.run([sys.executable, str(SCRIPTS / "scorecard.py"), str(self.review / "findings.json")],
                             capture_output=True, text=True)
        self.assertEqual(old.returncode, 2)   # the old entry point is fail-closed too


class SkillPackage(unittest.TestCase):
    SKILL = REPO / "skills" / "enterprise-experts"

    def test_frontmatter(self):
        text = (self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"---\nname: (.+)\ndescription: \"(.+)\"\n---\n", text)
        self.assertTrue(m, "SKILL.md frontmatter must hold name and a quoted description")
        self.assertEqual(m.group(1), "enterprise-experts")
        self.assertLessEqual(len(m.group(2)), 1024)
        self.assertLess(len(text.splitlines()), 500)

    def test_every_file_the_skill_points_to_exists(self):
        text = (self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        refs = set(re.findall(r"`((?:references|assets|scripts)/[\w./-]+\.\w+)`", text))
        self.assertGreater(len(refs), 8)
        for ref in refs:
            self.assertTrue((self.SKILL / ref).exists(), ref)

    def test_all_23_experts_are_specified(self):
        found = {}
        for path in (self.SKILL / "references").glob("experts-*.md"):
            body = path.read_text(encoding="utf-8")
            for m in re.finditer(r"(?m)^## (\d+)\. (.+?) — ", body):
                section = body[m.start():].split("\n---", 1)[0]
                found[int(m.group(1))] = section
        self.assertEqual(sorted(found), list(range(1, 24)))
        for aid, section in found.items():
            for part in ("**Mission:**", "**Deliverable `", "**Checks"):
                self.assertIn(part, section, f"expert {aid} lacks {part}")
        skill = (self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        for aid in AREAS:
            self.assertRegex(skill, rf"(?m)^\| {aid} \| .+`{aid:02d}-[\w-]+\.md`")

    def test_versions_agree(self):
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], __version__)
        self.assertIn(f"## [{__version__}]", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertIn(f"image: enterprise-experts:{__version__}", (REPO / "compose.yaml").read_text(encoding="utf-8"))

    def test_engine_uses_only_the_standard_library(self):
        allowed = set(sys.stdlib_module_names) | {"ee"}
        for path in (self.SKILL / "scripts").rglob("*.py"):
            for m in re.finditer(r"(?m)^(?:from|import) ([a-zA-Z_]\w*)", path.read_text(encoding="utf-8")):
                self.assertIn(m.group(1), allowed, f"{path.name} imports {m.group(1)}")


if __name__ == "__main__":
    unittest.main()
