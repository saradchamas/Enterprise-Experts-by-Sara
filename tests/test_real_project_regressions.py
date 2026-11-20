"""Defects found by running the engine on real open-source projects (see docs/EVALUATION.md).
Each test rebuilds the smallest layout that triggered the defect."""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.helpers import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from ee import discovery, evidence, graphs  # noqa: E402


def tree(root, files):
    for rel, text in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


class Discovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_exports_field_is_not_the_expo_framework(self):
        tree(self.root, {"package.json": '{"name": "x", "exports": {".": "./index.js"}, "devDependencies": {"vitest": "1"}}',
                         "index.js": "module.exports = 1\n"})
        d = discovery.discover(self.root)
        self.assertNotIn("Expo", d["frameworks"])
        self.assertNotIn("Vite", d["frameworks"])
        self.assertIn("Vitest", d["test_frameworks"])
        self.assertFalse(d["flags"]["has_mobile"])

    def test_bun_text_lockfile_is_a_lockfile(self):
        tree(self.root, {"package.json": '{"name": "x"}', "bun.lock": "{}", "index.js": "1\n"})
        self.assertEqual(discovery.discover(self.root)["lockfiles"], ["bun.lock"])

    def test_go_tests_are_detected(self):
        tree(self.root, {"go.mod": "module x\n", "main.go": "package main\n", "main_test.go": "package main\n"})
        self.assertIn("go test", discovery.discover(self.root)["test_frameworks"])

    def test_unittest_mock_alone_is_not_the_unittest_framework(self):
        tree(self.root, {"pyproject.toml": '[project]\nname="x"\ndependencies=["pytest"]\n',
                         "tests/test_a.py": "from unittest.mock import patch\n"})
        self.assertNotIn("unittest", discovery.discover(self.root)["test_frameworks"])
        tree(self.root, {"tests/test_b.py": "import unittest\n"})
        self.assertIn("unittest", discovery.discover(self.root)["test_frameworks"])

    def test_examples_docs_and_tests_do_not_define_the_product(self):
        tree(self.root, {
            "pyproject.toml": '[project]\nname="lib"\n', "src/lib/__init__.py": "x = 1\n",
            "examples/shop/requirements.txt": "redis\nsqlalchemy\n", "examples/shop/schema.sql": "create table t (id int);",
            "examples/shop/templates/index.html": "<html></html>", "examples/web/package.json": '{"dependencies": {"react": "18"}}',
            "docs/requirements.txt": "sphinx\n", "tests/apps/migrations/0001.py": "x = 1\n",
            "tests/apps/requirements.txt": "django\n"})
        d = discovery.discover(self.root)
        self.assertEqual(d["manifests"], ["pyproject.toml"])
        self.assertEqual(len(d["auxiliary_manifests"]), 4)
        self.assertEqual([s["path"] for s in d["stacks"]], ["."])
        flags = d["flags"]
        self.assertFalse(flags["has_database"] or flags["has_ui"] or flags["is_monorepo"] or flags["has_api"])
        self.assertTrue(any("not treated as parts of the product" in n for n in d["notes"]))

    def test_a_product_with_its_own_ui_and_database_is_still_recognised(self):
        tree(self.root, {"package.json": '{"dependencies": {"react": "18", "pg": "8"}}', "src/App.jsx": "import pg from 'pg'\n",
                         "migrations/001.sql": "create table t (id int);", "public/index.html": "<html></html>"})
        flags = discovery.discover(self.root)["flags"]
        self.assertTrue(flags["has_ui"] and flags["has_database"])


class Graphs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def edges(self, depth=3):
        return {(e["from"], e["to"]) for e in graphs.dependency_graph(self.root, depth)["edges"]}

    def test_src_layout_and_relative_imports(self):
        tree(self.root, {
            "src/pkg/__init__.py": "from .core import run\nfrom . import util\n",
            "src/pkg/util.py": "", "src/pkg/core/__init__.py": "from ..util import x\nfrom .engine import go\n",
            "src/pkg/core/engine.py": "from ...pkg.io import read\n", "src/pkg/io/__init__.py": "",
            "tests/test_pkg.py": "import pkg.core\nfrom pkg.io import read\n"})
        self.assertEqual(self.edges(), {("src/pkg", "src/pkg/core"), ("src/pkg/core", "src/pkg"), ("src/pkg/core", "src/pkg/io"),
                                        ("tests", "src/pkg/core"), ("tests", "src/pkg/io")})

    def test_one_example_cycle_per_group(self):
        cycles, sizes = graphs._cycles({("a", "b"): 1, ("b", "c"): 1, ("c", "a"): 1, ("c", "d"): 1, ("x", "y"): 1, ("y", "x"): 1})
        self.assertEqual((cycles, sizes), ([["a", "b", "c", "a"], ["x", "y", "x"]], [3, 2]))
        self.assertEqual(graphs._cycles({("a", "b"): 1, ("b", "c"): 1}), ([], []))

    def test_cycle_search_finishes_on_a_dense_graph(self):
        # 60 modules that all import each other: listing every cycle would never finish.
        names = [f"m{i:02d}" for i in range(60)]
        edges = {(a, b): 1 for a in names for b in names if a != b}
        started = time.monotonic()
        cycles, sizes = graphs._cycles(edges)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual((sizes, cycles), ([60], [["m00", "m01", "m00"]]))

    def test_a_huge_graph_is_drawn_small_and_listed_in_full(self):
        files = {}
        for i in range(14):
            for j in range(14):
                files[f"p{i}/s{j}/mod.py"] = "\n".join(f"import p{(i + k) % 14}.s{(j + k) % 14}.mod" for k in range(1, 4))
                files[f"p{i}/s{j}/__init__.py"] = ""
                files[f"p{i}/__init__.py"] = ""
        tree(self.root, files)
        out = Path(self.root) / "_out"
        res = graphs.write(self.root, out)
        self.assertGreater(len(res["dependency"]["edges"]), graphs.MAX_DRAWN_EDGES)
        drawn = [ln for ln in (out / "dependency-graph.md").read_text(encoding="utf-8").splitlines() if "-->" in ln]
        self.assertLessEqual(len(drawn), graphs.MAX_DRAWN_EDGES)
        self.assertEqual(len((out / "dependency-edges.csv").read_text(encoding="utf-8").splitlines()),
                         len(res["dependency"]["edges"]) + 1)

    def test_example_schemas_are_not_the_products_database(self):
        tree(self.root, {"examples/blog/schema.sql": "create table post (id int);", "tests/data.sql": "create table t (id int);"})
        self.assertEqual(graphs.database_model(self.root)["tables"], {})
        tree(self.root, {"db/schema.sql": "create table orders (id int);"})
        self.assertEqual(list(graphs.database_model(self.root)["tables"]), ["orders"])


if __name__ == "__main__":
    unittest.main()


class FullReviewFindings(unittest.TestCase):
    """Defects reported by the full review of a real project (docs/EVALUATION.md, round 5)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.review = Path(self.tmp.name) / "review"

    def tearDown(self):
        self.tmp.cleanup()

    def test_bun_and_uv_projects_get_their_own_commands(self):
        tree(self.root, {"bun.lock": "{}", "uv.lock": "", "frontend/package.json": '{"scripts": {"test": "vitest", "build": "vite build"}}',
                         "frontend/tsconfig.json": "{}", "frontend/src/a.ts": "export const a = 1\n",
                         "backend/pyproject.toml": '[project]\nname="b"\ndependencies=["pytest","mypy"]\n', "backend/app/main.py": "x = 1\n"})
        stacks = {s["path"]: s for s in discovery.discover(self.root)["stacks"]}
        front, back = stacks["frontend"], stacks["backend"]
        self.assertEqual(front["commands"]["install"], ["bun", "install", "--frozen-lockfile"])
        self.assertEqual(front["commands"]["test"], ["bun", "run", "test"])
        self.assertEqual(front["commands"]["audit"][0], "bun")
        self.assertEqual(back["commands"]["test"][:3], ["uv", "run", "--frozen"])
        self.assertIsNone(back["commands"]["audit"])
        self.assertIn("uv export", back["unavailable"]["audit"])

    def test_interpolated_password_is_not_a_secret(self):
        tree(self.root, {"compose.yml": "DATABASE_URL: postgresql://app:${POSTGRES_PASSWORD}@db:5432/app\n",
                         "other.yml": "URL: postgresql://app:" + "Sup3rS3cret" + "Value@db:5432/app\n"})  # split so this file is not flagged
        files = {s["file"] for s in discovery.discover(self.root)["secrets"]}
        self.assertEqual(files, {"other.yml"})

    def test_a_database_driver_loaded_by_name_is_not_reported_as_unused(self):
        tree(self.root, {"pyproject.toml": '[project]\nname="b"\ndependencies=["psycopg[binary]", "sqlalchemy"]\n',
                         "app/db.py": 'from sqlalchemy import create_engine\nengine = create_engine("postgresql+psycopg://x")\n'})
        d = discovery.discover(self.root)
        self.assertNotIn("PostgreSQL driver", d["declared_not_used"])
        self.assertTrue(d["flags"]["has_database"])

    def test_graph_resolves_packages_inside_a_service_folder_and_reads_orm_models(self):
        tree(self.root, {
            "backend/pyproject.toml": '[project]\nname="b"\n', "backend/app/__init__.py": "",
            "backend/app/main.py": "from app.api.routes import items\nfrom app import models\n",
            "backend/app/api/__init__.py": "", "backend/app/api/routes/__init__.py": "",
            "backend/app/api/routes/items.py": "from app.models import Item\n",
            "backend/app/models.py": (
                "import uuid\nfrom sqlmodel import Field, Relationship, SQLModel\n\n\n"
                "class UserBase(SQLModel):\n    email: str\n\n\n"
                "class User(UserBase, table=True):\n    id: uuid.UUID = Field(primary_key=True)\n"
                "    items: list['Item'] = Relationship(back_populates='owner')\n\n\n"
                "class Item(SQLModel, table=True):\n    id: uuid.UUID = Field(primary_key=True)\n"
                "    owner_id: uuid.UUID = Field(\n        foreign_key=\"user.id\", nullable=False\n    )\n"
                "    owner: User | None = Relationship(back_populates='items')\n\n\n"
                "class Legacy(Base):\n    __tablename__ = \"legacy_rows\"\n    id = Column(Integer, primary_key=True)\n"
                "    user_id = Column(Integer, ForeignKey(\"user.id\"))\n")})
        edges = {(e["from"], e["to"]) for e in graphs.dependency_graph(self.root, 4)["edges"]}
        self.assertIn(("backend/app", "backend/app/api/routes"), edges)
        self.assertIn(("backend/app/api/routes", "backend/app"), edges)
        db = graphs.database_model(self.root)
        self.assertEqual(sorted(db["tables"]), ["item", "legacy_rows", "user"])
        self.assertEqual([c[0] for c in db["tables"]["item"]], ["id", "owner_id"])
        self.assertEqual(sorted(map(tuple, db["relations"])), [("item", "user"), ("legacy_rows", "user")])

    def test_commit_is_recorded_when_a_check_runs_in_a_subfolder(self):
        tree(self.root, {".git/HEAD": "ref: refs/heads/main\n", ".git/refs/heads/main": "b" * 40 + "\n", "backend/x.py": "1\n"})
        rec = evidence.run_command(self.review, 2, "from a subfolder", [sys.executable, "-c", "print(1)"], cwd=str(self.root / "backend"))
        self.assertEqual(rec["commit"], "b" * 40)

    def test_a_bad_output_path_leaves_no_broken_record(self):
        with self.assertRaises(ValueError):
            evidence.run_command(self.review, 2, "bad output", [sys.executable, "-c", "print(1)"], cwd=str(self.root),
                                 outputs=["../outside.txt"])
        self.assertEqual(evidence.load_log(self.review).get("records", []), [])
        self.review.mkdir(parents=True, exist_ok=True)
        rec = evidence.run_command(self.review, 2, "relative output", [sys.executable, "-c",
                                   "open('probes-out.txt','w').write('x')"], cwd=str(self.review), outputs=["probes-out.txt"])
        self.assertEqual(rec["outputs"][0]["path"], "probes-out.txt")
        self.assertIsNotNone(rec["outputs"][0]["sha256"])

    def test_a_note_can_be_shared_when_it_is_written(self):
        tree(self.root, {"a.py": "1\n"})
        rec = evidence.add_note(self.review, 2, "read it", "observation", "seen", "a.py:1", str(self.root), also_areas=[14, 2])
        self.assertEqual(rec["also_areas"], [14])


class CleanSearches(unittest.TestCase):
    @unittest.skipUnless(shutil.which("grep"), "needs grep")
    def test_a_search_that_found_nothing_backs_a_pass_but_a_failed_one_does_not(self):
        from ee import scoring
        from tests.helpers import build_review
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "review"
            build_review(review)
            project = review / "_project"
            clean = evidence.run_command(review, 2, "no eval", ["grep", "-rn", "eval(", "app.py"], cwd=str(project))
            broken = evidence.run_command(review, 2, "missing file", ["grep", "-rn", "eval(", "nope.py"], cwd=str(project))
            self.assertEqual((clean["exit_code"], broken["exit_code"]), (1, 2))
            ev = scoring._Evidence(review, [])
            self.assertTrue(ev.supports_pass(clean["id"]))
            self.assertFalse(ev.supports_pass(broken["id"]))

    def test_scorecard_says_how_many_checks_were_run_and_at_which_commit(self):
        from ee import report, scoring
        from tests.helpers import build_review
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "review"
            build_review(review)
            res = scoring.evaluate(review)
            self.assertTrue(res["valid"], res["errors"])
            self.assertEqual(res["rows"][0]["basis"], "Verified")
            self.assertEqual(res["rows"][0]["basis_detail"], "Verified (1 of 2 checks were run)")
            self.assertIn("1 of 2 checks were run", report.to_markdown(res))
            self.assertIn("1 of 2 checks were run", report.to_html(res))
