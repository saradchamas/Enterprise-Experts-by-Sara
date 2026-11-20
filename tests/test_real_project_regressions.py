"""Defects found by running the engine on real open-source projects (see docs/EVALUATION.md).
Each test rebuilds the smallest layout that triggered the defect."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.helpers import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from ee import discovery, graphs  # noqa: E402


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
