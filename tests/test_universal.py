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
        self.assertTrue(needs["long_running_server"] and needs["database"] and needs["ai_inference"])
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
        self.assertEqual(discover(FIXTURES / "healthy-node")["stacks"][0]["commands"]["audit"], ["npm", "audit", "--omit=dev"])

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
