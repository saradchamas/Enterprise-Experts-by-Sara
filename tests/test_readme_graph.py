"""The engine module graph in the README must match the real imports."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EE = ROOT / "skills" / "enterprise-experts" / "scripts" / "ee"
LEFT_OUT = {"cli", "__main__", "__init__"}


def real_edges():
    modules = {p.stem for p in EE.glob("*.py")}
    edges = set()
    for path in EE.glob("*.py"):
        if path.stem in LEFT_OUT:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or node.level < 1:
                continue
            names = [node.module.split(".")[0]] if node.module else [a.name for a in node.names]
            edges.update((path.stem, name) for name in names if name in modules)
    return edges


def readme_edges():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("<!-- module-graph:start -->")[1].split("<!-- module-graph:end -->")[0]
    return set(re.findall(r"^\s*(\w+) --> (\w+)\s*$", block, re.M))


class ReadmeGraphTest(unittest.TestCase):
    def test_graph_matches_imports(self):
        self.assertEqual(readme_edges(), real_edges())


if __name__ == "__main__":
    unittest.main()
