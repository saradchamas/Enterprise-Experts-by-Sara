"""Capability matrix, scanner importers, visual regression, deployment profile and the new intake questions."""
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from tests.helpers import FIXTURES, OK_CMD

from ee import capabilities, evidence, intake, scanners, visual
from ee.discovery import discover


def matrix(name):
    return capabilities.build(discover(FIXTURES / name))


def status(m, aid):
    return next(a for a in m["areas"] if a["id"] == aid)["status"]


class CapabilityMatrix(unittest.TestCase):
    def test_every_project_gets_all_23_areas_classified_with_a_reason(self):
        for name in ("healthy-node", "flawed-node", "monorepo", "python-fastapi", "go-service", "infra-only",
                     "unsupported-elixir"):
            m = matrix(name)
            self.assertEqual([a["id"] for a in m["areas"]], list(range(1, 24)), name)
            for a in m["areas"]:
                self.assertIn(a["status"], ("applicable", "not_applicable", "not_assessed"))
                self.assertTrue(a["reason"])
            for aid in (1, 2, 9, 17, 22):
                self.assertEqual(status(m, aid), "applicable")

    def test_api_with_database(self):
        m = matrix("flawed-node")
        self.assertEqual([status(m, a) for a in (6, 7, 15, 13, 12, 11)],
                         ["applicable", "applicable", "applicable", "not_applicable", "applicable", "not_assessed"])
        self.assertFalse(m["workflows"]["ai_engineering"]["active"])
        self.assertIn("do not introduce AI", m["workflows"]["ai_engineering"]["reason"])
        self.assertTrue(m["workflows"]["deployment_advisor"]["active"])

    def test_library_without_service_parts(self):
        m = matrix("go-service")
        self.assertEqual([status(m, a) for a in (6, 13, 15, 4, 8)], ["not_applicable"] * 5)
        self.assertTrue(next(a for a in m["areas"] if a["id"] == 6)["confirm_with_user"])

    def test_ai_ui_and_infrastructure_projects(self):
        self.assertTrue(matrix("python-fastapi")["workflows"]["ai_engineering"]["active"])
        mono = matrix("monorepo")
        self.assertTrue(mono["workflows"]["visual_documentation"]["active"])
        self.assertEqual(status(mono, 13), "applicable")
        infra = matrix("infra-only")
        self.assertEqual([status(infra, a) for a in (16, 11, 7, 13)],
                         ["not_applicable", "applicable", "applicable", "not_applicable"])

    def test_checks_are_classified_never_guessed(self):
        m = matrix("flawed-node")
        by = {c["check"]: c for c in m["checks"]}
        self.assertEqual(by["install"]["status"], "no_command")
        self.assertIn("lockfile", by["install"]["reason"])
        self.assertIn(by["test"]["status"], ("available", "tool_missing"))
        un = matrix("unsupported-elixir")
        self.assertEqual([c["status"] for c in un["checks"]], ["unsupported"])
        self.assertTrue(capabilities.to_markdown(un))
        for c in matrix("monorepo")["checks"]:
            self.assertTrue(c["status"] == "available" or c["reason"], c)

    def test_deployment_profile_and_questions(self):
        d = discover(FIXTURES / "python-fastapi")
        needs = d["deployment_profile"]["needs"]
        self.assertTrue(needs["long_running_server"] and needs["database"] and needs["calls_an_ai_api"])
        self.assertFalse(needs["static_frontend"] or needs["mobile_store_release"])
        keys = {q["key"] for q in intake.questions_for(d["flags"])}
        self.assertTrue({"external_ai_allowed", "ai_quality_bar", "deployment_goals"} <= keys)
        self.assertNotIn("ui_run", keys)
        lib = {q["key"] for q in intake.questions_for(discover(FIXTURES / "go-service")["flags"])}
        self.assertFalse({"external_ai_allowed", "deployment_goals", "ui_run"} & lib)
        self.assertIn("ui_run", {q["key"] for q in intake.questions_for(discover(FIXTURES / "monorepo")["flags"])})


SARIF = {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{
    "tool": {"driver": {"name": "Semgrep OSS", "rules": [
        {"id": "js.sqli", "shortDescription": {"text": "SQL built by concatenation"}, "helpUri": "https://example.test/sqli",
         "properties": {"security-severity": "9.1"}},
        {"id": "js.style", "defaultConfiguration": {"level": "note"}}]}},
    "results": [
        {"ruleId": "js.sqli", "level": "error", "message": {"text": "User input reaches a SQL query"},
         "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/server.js"}, "region": {"startLine": 7}}}]},
        {"ruleId": "js.style", "message": {"text": "Prefer const"}, "locations": []}]}]}
OSV = {"results": [{"source": {"path": "package-lock.json", "type": "lockfile"}, "packages": [{
    "package": {"name": "lodash", "version": "4.17.15", "ecosystem": "npm"},
    "vulnerabilities": [{"id": "GHSA-35jh-r3h4-6jhm", "summary": "Command Injection in lodash",
                         "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.21"}]}]}]}],
    "groups": [{"ids": ["GHSA-35jh-r3h4-6jhm"], "max_severity": "7.2"}]}]}]}
TRIVY = {"SchemaVersion": 2, "Results": [{"Target": "Dockerfile", "Misconfigurations": [
    {"ID": "DS002", "Title": "Image user should not be root", "Severity": "HIGH", "PrimaryURL": "https://example.test/ds002"}],
    "Vulnerabilities": [{"VulnerabilityID": "CVE-2024-0001", "PkgName": "openssl", "InstalledVersion": "3.0.0",
                         "FixedVersion": "3.0.1", "Severity": "CRITICAL", "Title": "openssl issue"}]}]}
FAKE_SECRET = "tok_" + "9f8e7d6c5b4a" * 2
GITLEAKS = [{"Description": "Generic API Key", "File": "config/dev.js", "StartLine": 12, "RuleID": "generic-api-key",
             "Secret": FAKE_SECRET, "Match": "key = " + FAKE_SECRET}]


class ScannerImport(unittest.TestCase):
    def setUp(self):
        self.review = Path(tempfile.mkdtemp(prefix="ee-scan-")).resolve()
        self.addCleanup(shutil.rmtree, self.review, ignore_errors=True)

    def put(self, name, doc):
        (self.review / name).write_text(json.dumps(doc) if not isinstance(doc, str) else doc, encoding="utf-8")
        return scanners.import_scan(self.review, file=name)

    def test_real_npm_audit_output(self):
        shutil.copy(FIXTURES / "scans" / "npm-audit.json", self.review / "npm.json")
        res = scanners.import_scan(self.review, file="npm.json")
        self.assertEqual(res["format"], "npm-audit")
        self.assertEqual({c["package"].split()[0] for c in res["candidates"]}, {"lodash", "minimist"})
        self.assertTrue({"critical", "high"} <= set(res["by_severity"]))
        self.assertTrue(all(c["url"] and c["title"] for c in res["candidates"]))
        saved = json.loads((self.review / "scans" / "npm-normalized.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["count"], res["count"])
        self.assertIn("need triage", saved["note"])

    def test_real_pip_audit_output(self):
        shutil.copy(FIXTURES / "scans" / "pip-audit.json", self.review / "pip.json")
        res = scanners.import_scan(self.review, file="pip.json")
        self.assertEqual(res["format"], "pip-audit")
        self.assertGreaterEqual(res["count"], 1)
        first = res["candidates"][0]
        self.assertEqual((first["package"], first["severity"]), ("jinja2 2.10", "unrated"))   # the tool gives no severity
        self.assertTrue(first["fixed_in"])

    def test_sarif(self):
        res = self.put("semgrep.sarif", SARIF)
        self.assertEqual((res["format"], res["count"]), ("sarif", 2))
        hit, style = res["candidates"]
        self.assertEqual((hit["severity"], hit["location"], hit["tool"], hit["url"]),
                         ("critical", "src/server.js:7", "Semgrep OSS", "https://example.test/sqli"))
        self.assertEqual(style["severity"], "low")

    def test_osv_trivy_gitleaks(self):
        osv = self.put("osv.json", OSV)["candidates"][0]
        self.assertEqual((osv["severity"], osv["fixed_in"], osv["package"]), ("high", "4.17.21", "lodash 4.17.15"))
        trivy = self.put("trivy.json", TRIVY)
        self.assertEqual(trivy["by_severity"], {"critical": 1, "high": 1})
        leaks = self.put("leaks.json", GITLEAKS)
        self.assertEqual(leaks["format"], "gitleaks")
        self.assertNotIn(FAKE_SECRET, json.dumps(leaks))
        self.assertNotIn(FAKE_SECRET, (self.review / "scans" / "leaks-normalized.json").read_text(encoding="utf-8"))

    def test_import_from_recorded_evidence_with_noise_around_the_json(self):
        code = "print('npm warn something'); print(open(r'%s').read())" % (FIXTURES / "scans" / "npm-audit.json")
        rec = evidence.run_command(self.review, 2, "npm audit", [sys.executable, "-c", code])
        res = scanners.import_scan(self.review, evidence_id=rec["id"])
        self.assertEqual((res["format"], res["evidence"]), ("npm-audit", rec["id"]))
        self.assertTrue((self.review / "scans" / f"{rec['id']}-normalized.json").exists())

    def test_refusals(self):
        with self.assertRaises(ValueError):
            scanners.import_scan(self.review)                               # nothing given
        with self.assertRaises(ValueError):
            scanners.import_scan(self.review, evidence_id="E-404")
        with self.assertRaises(ValueError):
            scanners.import_scan(self.review, file="../outside.json")       # must live with the evidence
        with self.assertRaises(ValueError):
            self.put("notes.json", {"hello": "world"})                      # unknown format is not guessed
        with self.assertRaises(ValueError):
            self.put("log.txt", "no json here at all")
        rec = evidence.run_command(self.review, 2, "scan", OK_CMD)
        (self.review / rec["artifact"]).write_text("{}")                     # tampered evidence is refused
        with self.assertRaises(ValueError):
            scanners.import_scan(self.review, evidence_id=rec["id"])
        self.assertEqual(self.put("clean.json", {"auditReportVersion": 2, "vulnerabilities": {}})["count"], 0)


def png(width, height, pixel, ftype=0, channels=3, patch=None):
    """Encode a flat-colour PNG using one filter type, optionally with a rectangle of another colour."""
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row += bytes(patch[1] if patch and patch[0](x, y) else pixel)
        rows.append(row)
    raw, prev = bytearray(), bytearray(width * channels)
    for row in rows:
        out = bytearray(len(row))
        for i in range(len(row)):
            a = row[i - channels] if i >= channels else 0
            b, c = prev[i], (prev[i - channels] if i >= channels else 0)
            if ftype == 0:
                pred = 0
            elif ftype == 1:
                pred = a
            elif ftype == 2:
                pred = b
            elif ftype == 3:
                pred = (a + b) >> 1
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
            out[i] = (row[i] - pred) & 255
        raw += bytes([ftype]) + out
        prev = row

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    ctype = {1: 0, 3: 2, 4: 6}[channels]
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, ctype, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))


class VisualRegression(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="ee-visual-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.review = self.root / "enterprise-review" / "2026-11-20"

    def image(self, name, **kw):
        path = self.root / name
        path.write_bytes(png(**kw))
        return path

    def test_decoder_handles_every_filter_type_and_alpha(self):
        def in_patch(x, y):
            return 3 <= x < 9 and 2 <= y < 6
        for channels, colour, other in ((3, (10, 200, 30), (250, 0, 99)), (4, (10, 200, 30, 255), (250, 0, 99, 128)),
                                        (1, (77,), (200,))):
            expected = None
            for ftype in range(5):
                path = self.image(f"f{ftype}-{channels}.png", width=12, height=8, pixel=colour, ftype=ftype,
                                  channels=channels, patch=(in_patch, other))
                w, h, c, rows = visual.read_png(path)
                self.assertEqual((w, h, c), (12, 8, channels))
                expected = expected or rows
                self.assertEqual(rows, expected, f"filter {ftype}, {channels} channels")
            self.assertEqual(expected[3][3 * channels:4 * channels], bytes(other))
            self.assertEqual(expected[0][:channels], bytes(colour))

    def test_real_browser_screenshots(self):
        before, after = FIXTURES / "visual" / "home-before.png", FIXTURES / "visual" / "home-after.png"
        self.assertEqual(visual.read_png(before)[:2], (400, 300))
        self.assertEqual(visual.diff_ratio(before, before), (0.0, None))
        ratio, problem = visual.diff_ratio(before, after)
        self.assertIsNone(problem)
        self.assertTrue(0.005 < ratio < 0.2, ratio)      # the heading text changed, the rest did not

    def test_baseline_workflow(self):
        shot = self.image("a.png", width=20, height=10, pixel=(255, 255, 255))
        first = visual.compare(self.review, "home-desktop", shot)
        self.assertEqual(first["verdict"], "no_baseline")           # nothing is "passing" before a human approves it
        with self.assertRaises(ValueError):
            visual.approve(self.review, "home-desktop", " ")
        with self.assertRaises(ValueError):
            visual.approve(self.review, "never-captured", "Sara")
        meta = visual.approve(self.review, "home-desktop", "Sara")
        self.assertEqual(meta["approved_by"], "Sara")
        self.assertTrue((self.root / "enterprise-review" / "visual-baselines" / "home-desktop.png").exists())
        same = visual.compare(self.review, "home-desktop", shot)
        self.assertEqual((same["verdict"], same["changed_pct"], same["baseline"]["approved_by"]), ("match", 0.0, "Sara"))
        changed = self.image("b.png", width=20, height=10, pixel=(255, 255, 255),
                             patch=(lambda x, y: x < 4 and y < 5, (0, 0, 0)))
        res = visual.compare(self.review, "home-desktop", changed)
        self.assertEqual((res["verdict"], res["changed_pct"]), ("changed", 10.0))
        self.assertEqual(visual.compare(self.review, "home-desktop", changed, threshold=15)["verdict"], "match")
        saved = json.loads((self.review / "screenshots" / "home-desktop.compare.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["verdict"], "match")

    def test_antialiasing_noise_is_tolerated_but_size_change_is_not(self):
        a = self.image("a.png", width=10, height=10, pixel=(100, 100, 100))
        b = self.image("b.png", width=10, height=10, pixel=(108, 100, 96))
        self.assertEqual(visual.diff_ratio(a, b), (0.0, None))
        visual.compare(self.review, "s", a)
        visual.approve(self.review, "s", "Sara")
        bigger = self.image("c.png", width=12, height=10, pixel=(100, 100, 100))
        res = visual.compare(self.review, "s", bigger)
        self.assertEqual(res["verdict"], "changed")
        self.assertIn("size changed", res["reason"])

    def test_only_real_supported_pngs_are_accepted(self):
        fake = self.root / "mock.png"
        fake.write_text("<svg>a pretty mockup</svg>")
        with self.assertRaises(ValueError):
            visual.compare(self.review, "home", fake)
        with self.assertRaises(ValueError):
            visual.compare(self.review, "Bad Name", self.image("a.png", width=2, height=2, pixel=(0, 0, 0)))
        self.assertFalse((self.review / "screenshots" / "home.png").exists())


if __name__ == "__main__":
    unittest.main()


class FixesFromTheFirstEvaluation(unittest.TestCase):
    """Each of these was reported by a real run of the skill on the flawed sample project."""

    def setUp(self):
        self.review = Path(tempfile.mkdtemp(prefix="ee-fix-")).resolve()
        self.addCleanup(shutil.rmtree, self.review, ignore_errors=True)

    def test_a_captured_search_is_observed_not_verified(self):
        (self.review / "a.txt").write_text("backup: none\n")
        for argv in (["grep", "-rn", "backup", "."], ["cat", "a.txt"], ["ls"], ["git", "ls-files", ".env"], ["wc", "-l", "a.txt"]):
            rec = evidence.run_command(self.review, 7, "search", argv, cwd=str(self.review))
            self.assertEqual(evidence.record_level(rec, self.review)[0], "observed", argv)
        ran = evidence.run_command(self.review, 7, "restore test", OK_CMD)
        self.assertEqual(evidence.record_level(ran, self.review)[0], "verified")

    def test_search_patterns_are_not_mistaken_for_destructive_commands(self):
        from ee.policy import check_command
        self.assertIsNone(check_command(["grep", "-rn", "delete from", "src"]))
        self.assertIsNone(check_command(["rg", "rm -rf|git push"]))
        self.assertIsNotNone(check_command(["psql", "-c", "delete from users"]))
        self.assertIsNotNone(check_command(["find", ".", "-exec", "rm", "-rf", "{}", ";"]))

    def test_one_record_can_serve_several_areas(self):
        from tests.helpers import build_review, read, write
        from ee import scoring
        review = build_review(self.review / "r", mode="quick")
        shared = evidence.run_command(review, 2, "integration test run", OK_CMD, also_areas=[5])
        data = read(review)
        for aid, ok in ((5, True), (9, False)):
            copy = json.loads(json.dumps(data))
            next(a for a in copy["areas"] if a["id"] == aid)["checks"][0]["evidence"] = [shared["id"]]
            write(review, copy)
            self.assertEqual(scoring.evaluate(review)["valid"], ok, aid)

    def test_no_lockfile_means_no_audit_and_node_test_is_detected(self):
        d = discover(FIXTURES / "flawed-node")
        stack = d["stacks"][0]
        self.assertIsNone(stack["commands"]["audit"])
        self.assertIn("lockfile", stack["unavailable"]["audit"])
        self.assertIn("node:test", d["test_frameworks"])
        self.assertEqual(discover(FIXTURES / "healthy-node")["stacks"][0]["commands"]["audit"], ["npm", "audit", "--omit=dev", "--json"])

    def test_package_respects_review_scope_and_ships_findings(self):
        from tests.helpers import build_review
        from ee import package
        review = build_review(self.review / "r", mode="quick")
        res = package.build(review)
        self.assertTrue((review / package.OUT / "10-evidence" / "findings.json").is_file())
        self.assertIn("06-testing/09-quality-assurance.md", res["missing"])          # in quick scope, not written
        self.assertIn("03-security/19-compliance.md", res["out_of_scope"])           # not in quick scope
        self.assertFalse([m for m in res["missing"] if "19-compliance" in m or "benchmarks" in m])
        self.assertIn("Outside this review's scope", (review / package.OUT / "MANIFEST.md").read_text(encoding="utf-8"))

    def test_graph_says_what_it_did_not_draw(self):
        from ee import graphs
        res = graphs.write(FIXTURES / "flawed-node", self.review / "g")
        self.assertEqual(res["written"], ["database-erd.md"])
        self.assertIn("dependency graph", res["skipped"][0])


class FixesFromTheSecondEvaluation(unittest.TestCase):
    """Reported by five real runs of the skill (healthy project, fix loop, AI app, UI with screenshots, full review)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="ee-fix2-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def review(self, **kw):
        from tests.helpers import build_review
        return build_review(self.root / "r", **kw)

    def test_a_failed_command_cannot_back_a_pass(self):
        from tests.helpers import read, write
        from ee import scoring
        review = self.review(mode="quick")
        failed = evidence.run_command(review, 9, "capture", [sys.executable, "-c", "import sys; sys.exit(1)"])
        data = read(review)
        next(a for a in data["areas"] if a["id"] == 9)["checks"][0]["evidence"] = [failed["id"]]
        write(review, data)
        res = scoring.evaluate(review)
        self.assertFalse(res["valid"])
        self.assertTrue(any("marked pass but no evidence supports it" in e for e in res["errors"]))
        next(a for a in data["areas"] if a["id"] == 9)["checks"][0]["result"] = "fail"   # as a failure it is fine
        write(review, data)
        self.assertTrue(scoring.evaluate(review)["valid"])

    def test_output_files_are_part_of_the_evidence(self):
        review = self.root / "rev"
        shot = review / "screenshots" / "raw" / "home.png"
        make = [sys.executable, "-c", f"import pathlib; p=pathlib.Path(r'{shot}'); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'img')"]
        ok = evidence.run_command(review, 13, "capture home", make, outputs=[shot])
        self.assertEqual(evidence.record_level(ok, review), ("verified", None))
        self.assertEqual(ok["outputs"][0]["path"], "screenshots/raw/home.png")
        shot.write_bytes(b"retouched")
        self.assertIn("modified after capture", evidence.record_level(ok, review)[1])
        missing = evidence.run_command(review, 13, "capture that fails", [sys.executable, "-c", "pass"],
                                       outputs=[review / "screenshots" / "never.png"])
        level, problem = evidence.record_level(missing, review)
        self.assertIsNone(level)
        self.assertIn("did not produce its output file", problem)
        with self.assertRaises(ValueError):
            evidence.run_command(review, 13, "x", [sys.executable, "-c", "pass"], outputs=[self.root / "outside.png"])

    def test_web_sources_can_be_recorded(self):
        rec = evidence.add_note(self.root, 12, "provider pricing page", "observation", "price per million tokens",
                                "https://example.test/pricing", str(self.root))
        self.assertEqual(evidence.record_level(rec, self.root)[0], "observed")
        self.assertEqual(rec["source_url"], "https://example.test/pricing")
        self.assertRegex(rec["checked_at"], r"^\d{4}-\d\d-\d\d$")
        with self.assertRaises(ValueError):
            evidence.add_note(self.root, 12, "x", "inference", "d", "https://example.test/pricing")

    def test_checks_do_not_leave_caches_in_the_project(self):
        project = self.root / "p"
        project.mkdir()
        (project / "mod.py").write_text("X = 1\n")
        evidence.run_command(self.root / "rev", 9, "import", [sys.executable, "-c", "import mod"], cwd=str(project))
        self.assertEqual(sorted(p.name for p in project.iterdir()), ["mod.py"])

    def test_declared_but_unused_dependencies(self):
        project = self.root / "p"
        (project / "app").mkdir(parents=True)
        (project / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["fastapi", "openai", "sqlalchemy"]\n')
        (project / "app" / "main.py").write_text("def answer(q):\n    return q.strip()\n")
        d = discover(project)
        self.assertEqual(d["declared_not_used"], ["FastAPI", "OpenAI", "OpenAI API", "SQLAlchemy"])
        self.assertFalse(d["flags"]["has_ai"] or d["flags"]["has_api"] or d["flags"]["has_database"])
        m = capabilities.build(d)
        self.assertFalse(m["workflows"]["ai_engineering"]["active"])
        self.assertIn("declared", m["workflows"]["ai_engineering"]["reason"])
        self.assertIn("not imported anywhere", " ".join(d["notes"]))
        used = discover(FIXTURES / "python-fastapi")
        self.assertEqual(used["declared_not_used"], [])
        self.assertTrue(used["flags"]["has_ai"] and used["flags"]["has_api"] and used["flags"]["has_database"])
        self.assertEqual(discover(FIXTURES / "flawed-node")["declared_not_used"], ["Stripe"])

    def test_a_dockerfile_does_not_make_a_library_a_service(self):
        m = matrix("healthy-node")
        self.assertEqual([status(m, a) for a in (3, 4, 5, 7, 8, 18, 12)], ["not_applicable"] * 7)
        self.assertEqual(status(m, 11), "applicable")                       # it does have container and CI config
        self.assertFalse(m["workflows"]["deployment_advisor"]["active"])
        self.assertIn("only if hosting is unsettled", matrix("flawed-node")["workflows"]["deployment_advisor"]["reason"])

    def test_questions_follow_the_review_scope(self):
        quick = {q["key"] for q in intake.questions_for({"has_database": True}, "quick")}
        full = {q["key"] for q in intake.questions_for({"has_database": True}, "full")}
        self.assertFalse({"kpis", "compliance_targets", "data_owner", "issue_tracker"} & quick)
        self.assertTrue({"kpis", "compliance_targets", "data_owner", "issue_tracker"} <= full)
        self.assertTrue(set(intake.REQUIRED_KEYS) <= quick)
        self.assertTrue({"backups", "execution_allowed", "critical_journeys"} <= quick)
        ui = {q["key"] for q in intake.questions_for({"has_ui": True, "has_database": True}, "focused", [13])}
        self.assertIn("ui_audience", ui)
        self.assertNotIn("backups", ui)

    def test_scorecard_explains_misleading_labels(self):
        from tests.helpers import read, write
        from ee import report, scoring
        review = self.review(mode="quick", answers={"stage": "prototype"})
        data = read(review)
        next(a for a in data["areas"] if a["id"] == 2)["score"] = 40
        write(review, data)
        res = scoring.evaluate(review)
        self.assertEqual(res["decision"], "NO-GO")
        notes = " ".join(res["notes"])
        self.assertIn("Stage is prototype", notes)
        self.assertIn("no open Critical or High findings", notes)
        self.assertIn("How to read this result", report.to_markdown(res))
        next(a for a in data["areas"] if a["id"] == 2)["score"] = 90
        next(a for a in data["areas"] if a["id"] == 1)["score"] = 30
        write(review, data)
        res = scoring.evaluate(review)
        self.assertEqual(res["decision"], "GO")                              # area 1 is not core
        self.assertTrue(any("Architecture scored 30" in n for n in res["notes"]))

    def test_visual_compare_is_citable_and_draws_the_difference(self):
        review = self.root / "enterprise-review" / "d"
        before, after = FIXTURES / "visual" / "home-before.png", FIXTURES / "visual" / "home-after.png"
        first = visual.compare(review, "home", before)
        self.assertEqual(evidence.record_level(next(r for r in evidence.load_log(review)["records"]
                                                    if r["id"] == first["evidence"]), review)[0], "verified")
        approved = visual.approve(review, "home", "Sara")
        self.assertTrue(approved["evidence"])
        changed = visual.compare(review, "home", after)
        self.assertEqual(changed["verdict"], "changed")
        w, h, c, rows = visual.read_png(review / changed["diff_image"])
        self.assertEqual((w, h, c), (400, 300, 3))
        self.assertTrue(any(b"\xe0\x10\x10" in r for r in rows))            # changed pixels are marked
        self.assertEqual(len(list((review / "screenshots").glob("home.compare-*.json"))), 2)
        ids = [r["id"] for r in evidence.load_log(review)["records"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_package_keeps_screenshots_next_to_the_reports(self):
        from ee import package
        review = self.review(mode="focused", scope=[13])
        (review / "screenshots" / "raw").mkdir(parents=True)
        (review / "screenshots" / "raw" / "home.png").write_bytes((FIXTURES / "visual" / "home-before.png").read_bytes())
        (review / "13-ui-ux.md").write_text("![home](screenshots/raw/home.png)\n")
        (review / "00-scope-and-access.md").write_text("# scope\n")
        res = package.build(review)
        out = review / package.OUT
        self.assertTrue((out / "02-expert-assessments" / "screenshots" / "raw" / "home.png").is_file())
        self.assertTrue((out / "02-expert-assessments" / "13-ui-ux.md").is_file())
        self.assertFalse((out / "02-expert-assessments" / "00-scope-and-access.md").exists())
        self.assertTrue((out / "00-executive-summary" / "00-scope-and-access.md").is_file())
        self.assertFalse([m for m in res["missing"] if "change-log" in m or "remediation-plan" in m])


class FixesFromTheSelfReview(unittest.TestCase):
    """Found when the skill ran a full 23-expert review of its own repository."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="ee-fix3-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_chained_shell_commands_are_each_checked(self):
        from ee.policy import check_command, check_shell
        for cmd in ("ls && rm -rf src", "cat README.md; git push --force", "grep x . | xargs rm", "echo hi > src/app.py",
                    "git -C . push --force", "find . -delete", "rm x", "gh release create v1", "curl --request POST https://x.test",
                    "true || terraform apply", "echo $(git push)", "npm test >> package.json", "cat a | tee src/b.js"):
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(check_shell(cmd))
        for cmd in ("ls -la", "grep -rn 'delete from' src", "npm test 2>&1 | tail -5", "git status && git diff",
                    "python -m pytest -q > /dev/null", "node --test > /tmp/out.txt", "git log --oneline | head",
                    "npm audit --json > enterprise-review/2026-11-20/audit.json"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(check_shell(cmd))
        self.assertIsNone(check_command(["grep", "-rn", "rm -rf; git push", "src"]))   # no shell: the pattern is just text

    def test_guard_blocks_chained_commands_and_hand_edits_of_engine_files(self):
        from ee import guard, state
        (self.root / "src").mkdir()
        review = self.root / "enterprise-review" / "d"
        state.init(review, "quick")

        def bash(c):
            return guard.decide({"tool_name": "Bash", "tool_input": {"command": c}, "cwd": str(self.root)})[0]

        def write(p):
            return guard.decide({"tool_name": "Write", "tool_input": {"file_path": str(p)}, "cwd": str(self.root)})
        self.assertFalse(bash("ls && rm -rf src"))
        self.assertFalse(bash("cat README.md; git push --force"))
        self.assertFalse(bash("echo x > src/app.py"))
        self.assertTrue(bash("ls src && git status"))
        for name in ("review-state.json", "evidence-log.json", "scorecard.json", "evidence/E-001-x.txt"):
            allowed, msg = write(review / name)
            self.assertFalse(allowed, name)
            self.assertIn("written by the engine only", msg)
        self.assertTrue(write(review / "findings.json")[0])
        self.assertTrue(write(review / "02-security.md")[0])

    def test_parallel_evidence_runs_keep_every_record(self):
        import threading
        errors = []

        def work(i):
            try:
                evidence.run_command(self.root, 1 + i % 5, f"run {i}", [sys.executable, "-c", f"print({i})"])
                evidence.add_note(self.root, 2, f"note {i}", "inference", "x")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        threads = [threading.Thread(target=work, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        records = evidence.load_log(self.root)["records"]
        ids = [r["id"] for r in records]
        self.assertEqual((len(ids), len(set(ids))), (24, 24))
        self.assertFalse([r for r in records if r["kind"] == "pending"])
        self.assertEqual(len(list((self.root / "evidence").iterdir())), 12)
        self.assertFalse((self.root / "evidence-log.lock").exists())
        for r in records:
            if r["kind"] == "command":
                self.assertEqual(evidence.record_level(r, self.root)[0], "verified")

    def test_parallel_runs_from_separate_processes(self):
        import subprocess
        cli = [sys.executable, str(FIXTURES.parents[1] / "skills" / "enterprise-experts" / "scripts" / "enterprise_experts.py"),
               "evidence", "run", "--review", str(self.root), "--area", "9", "--title", "p", "--", sys.executable, "-c", "print(1)"]
        procs = [subprocess.Popen(cli, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for _ in range(6)]
        self.assertEqual([p.wait() for p in procs], [0] * 6)
        ids = [r["id"] for r in evidence.load_log(self.root)["records"]]
        self.assertEqual(sorted(ids), [f"E-{i:03d}" for i in range(1, 7)])

    def test_malformed_review_files_are_invalid_not_crashes(self):
        from tests.helpers import build_review, read, write
        from ee import scoring, state
        from ee.cli import main
        review = build_review(self.root / "r", mode="quick")
        good = read(review)
        for breaker in (lambda d: d["areas"][0].update(id=[1]), lambda d: d["areas"].append("x"),
                        lambda d: d["areas"][0].update(checks="none"), lambda d: d["areas"][0].update(findings=[5]),
                        lambda d: d.update(areas=[{"id": 2, "status": "assessed", "score": 90, "checks": [{"id": ["a"]}]}])):
            data = json.loads(json.dumps(good))
            breaker(data)
            write(review, data)
            res = scoring.evaluate(review)
            self.assertEqual((res["valid"], res["decision"], res["exit_code"]), (False, "NO-GO", 2))
        write(review, good)
        for bad in ("[]", '{"records": {}}', '{"records": ["x"]}'):
            (review / "evidence-log.json").write_text(bad)
            self.assertFalse(scoring.evaluate(review)["valid"], bad)
            self.assertEqual(main(["score", "--review", str(review), "--no-write"]), 2)
        (review / "review-state.json").write_text("{}")
        self.assertEqual(main(["state", "show", "--review", str(review)]), 2)
        (review / "evidence-log.json").write_text("[]")
        self.assertEqual(main(["evidence", "run", "--review", str(review), "--area", "1", "--title", "t", "--",
                               sys.executable, "-c", "pass"]), 2)
        self.assertEqual(main(["package", "--review", str(review)]), 2)
        del state

    def test_scores_cannot_ignore_failed_checks_or_lazy_not_applicable(self):
        from tests.helpers import build_review, read, write
        from ee import scoring
        review = build_review(self.root / "r", mode="quick")
        data = read(review)
        arch = next(a for a in data["areas"] if a["id"] == 1)
        arch["score"] = 100
        for c in arch["checks"]:
            c["result"] = "fail"
        write(review, data)
        row = next(r for r in scoring.evaluate(review)["rows"] if r["id"] == 1)
        self.assertEqual((row["final"], row["caps"]), (40, "no check passed"))
        dr = next(a for a in data["areas"] if a["id"] == 7)
        dr.update(status="not_applicable", reason="n/a")
        write(review, data)
        self.assertTrue(any("says why" in e for e in scoring.evaluate(review)["errors"]))
        dr["reason"] = "the project stores no data and defines no infrastructure"
        write(review, data)
        (review / "capability-matrix.json").write_text(json.dumps({"areas": [{"id": 7, "status": "applicable"}]}))
        res = scoring.evaluate(review)
        self.assertTrue(res["valid"])
        self.assertTrue(any("Disaster Recovery was marked not applicable although the capability matrix" in n for n in res["notes"]))

    def test_fixed_needs_a_new_successful_run(self):
        from tests.helpers import build_review, read, write
        from ee import scoring
        review = build_review(self.root / "r", mode="quick")
        probe = evidence.run_command(review, 2, "exploit probe", [sys.executable, "-c", "import sys; print('VULNERABLE'); sys.exit(1)"])
        data = read(review)
        sec = next(a for a in data["areas"] if a["id"] == 2)
        sec["findings"] = [{"id": "SEC-001", "severity": "critical", "status": "fixed", "title": "SQL injection",
                            "evidence": [probe["id"]], "verification": [probe["id"]]}]
        write(review, data)
        self.assertTrue(any("ran and succeeded" in e for e in scoring.evaluate(review)["errors"]))
        sec["findings"][0]["verification"] = sec["checks"][0]["evidence"]      # a passing run, but made BEFORE the finding
        write(review, data)
        self.assertTrue(any("new run made after" in e for e in scoring.evaluate(review)["errors"]))
        recheck = evidence.run_command(review, 2, "exploit probe after fix", [sys.executable, "-c", "print('SAFE')"])
        sec["findings"][0]["verification"] = [recheck["id"]]
        write(review, data)
        self.assertTrue(scoring.evaluate(review)["valid"])
        sec["findings"][0].update(status="pending_decision")
        write(review, data)
        self.assertTrue(any("pending_decision needs a 'note'" in e for e in scoring.evaluate(review)["errors"]))
        sec["findings"][0]["note"] = "correct but slower; Sara decides keep or revert"
        write(review, data)
        res = scoring.evaluate(review)
        self.assertEqual((res["valid"], res["decision"]), (True, "NO-GO"))      # undecided still counts as unresolved

    def test_discovery_ignores_sample_projects_kept_as_test_data(self):
        repo = FIXTURES.parents[1]
        d = discover(repo)
        self.assertIn("tests/fixtures", d["excluded"])
        self.assertEqual({s["adapter"] for s in d["stacks"]}, {"python"})
        self.assertFalse(d["flags"]["has_ai"] or d["flags"]["has_database"] or d["flags"]["has_ui"])
        self.assertEqual(d["secrets"], [])
        self.assertEqual(discover(repo, exclude=["tests", "tools"])["test_files"], 0)
        plain = self.root / "p"
        (plain / "tests").mkdir(parents=True)
        (plain / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (plain / "tests" / "test_x.py").write_text("import unittest\n")
        self.assertEqual(discover(plain)["stacks"][0]["commands"]["test"],
                         ["python", "-m", "unittest", "discover", "-s", "tests", "-t", "."])

    def test_masking_covers_more_secret_shapes(self):
        from ee.secrets import mask_text
        value = "Zq9" + "x7Lm2Pw8" * 3
        shapes = [f"Authorization: Bearer {value}", f"https://api.example.test/v1?api_key={value}&x=1",
                  f'{{"password": "{value}"}}', f"password: {value}", f"client_secret={value}", f"--token {value}",
                  f"mysql -u root --password={value}", f"export API_KEY={value}", f"glpat-{value}", f"whsec_{value}",
                  "-----BEGIN RSA " + f"PRIVATE KEY-----\n{value}\n{value}\n-----END RSA " + "PRIVATE KEY-----",
                  "postgres" + f"://user:{value}@db:5432/x"]
        for text in shapes:
            with self.subTest(text=text[:30]):
                self.assertNotIn(value, mask_text(text))
        self.assertEqual(mask_text("14 tests passed in 0.3s"), "14 tests passed in 0.3s")

    def test_benchmark_runs_keep_their_evidence_and_agreed_thresholds(self):
        from ee import bench
        cmd = [sys.executable, "-c", "print('ns=35.0')"]
        script = self.root / "bench.js"
        script.write_text("// workload v1\n")
        first = bench.run(self.root, "total", "baseline", cmd, runs=3, warmup=0, metric_regex=r"ns=([\d.]+)", area=9,
                          also_areas=[6], workload_files=[script],
                          acceptance={"max_regression_pct": 400, "min_abs_change": 100})
        bench.run(self.root, "total", "baseline", cmd, runs=3, warmup=0, metric_regex=r"ns=([\d.]+)", area=9,
                  workload_files=[script], acceptance={"max_regression_pct": 400, "min_abs_change": 100})
        rec = next(r for r in evidence.load_log(self.root)["records"] if r["id"] == first["evidence"])
        self.assertEqual(evidence.record_level(rec, self.root)[0], "verified")       # the first run's evidence survives
        self.assertEqual(rec["also_areas"], [6])
        slower = [sys.executable, "-c", "print('ns=90.0')"]
        with self.assertRaises(ValueError):
            bench.run(self.root, "total", "candidate", cmd, runs=3, warmup=0, acceptance={"max_regression_pct": 1})
        bench.run(self.root, "total", "candidate", cmd[:2] + ["print('ns=90.0')"], runs=3, warmup=0,
                  metric_regex=r"ns=([\d.]+)", area=9, workload_files=[script])
        del slower
        res = bench.compare(self.root, "total")
        self.assertEqual(res["verdict"], "not_comparable")                           # the command string differs
        with self.assertRaises(ValueError):
            bench.compare(self.root, "total", max_regression=5)                      # cannot move the goalposts afterwards
        self.assertTrue(res["thresholds"]["agreed_with_baseline"])

    def test_approvals_are_checked(self):
        from tests.helpers import build_review
        from ee import state
        review = build_review(self.root / "r", mode="quick")
        state.init(review, "quick")
        for bad in (["../../*"], ["/etc/passwd"], ["src/../../x"]):
            with self.assertRaises(ValueError):
                state.approve(review, "Sara", paths=bad)
        with self.assertRaises(ValueError):
            state.approve(review, "Sara", findings=["NOPE-999"], paths=["src/*"])
        state.approve(review, "Sara", paths=["src/*"])
