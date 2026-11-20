"""Diagrams generated from the code itself, as Mermaid. Every diagram states how it
was derived: these are Observed (static analysis of files), never drawn from memory."""
import re
from collections import defaultdict
from pathlib import Path

from .discovery import SKIP_DIRS

PY_IMPORT = re.compile(r"(?m)^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))")
JS_IMPORT = re.compile(r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|require\(\s*|import\(\s*)['"](\.{1,2}/[^'"]+)['"]""")
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
CREATE_TABLE = re.compile(r"(?is)create\s+table\s+(?:if\s+not\s+exists\s+)?[`\"\[]?([\w.]+)[`\"\]]?\s*\((.*?)\)\s*;")
REFERENCES = re.compile(r"(?i)references\s+[`\"\[]?([\w.]+)[`\"\]]?")
PRISMA_MODEL = re.compile(r"(?s)\bmodel\s+(\w+)\s*\{(.*?)\}")


def _files(root):
    for path in Path(root).rglob("*"):
        if path.is_file() and not (set(path.relative_to(root).parts[:-1]) & SKIP_DIRS):
            yield path


def _module(rel, depth):
    parts = rel.parts[:-1][:depth]
    return "/".join(parts) if parts else "(root)"


def dependency_graph(root, depth=2):
    """Edges between directories (to `depth` levels), from import statements."""
    root = Path(root).resolve()
    files = [p for p in _files(root) if p.suffix in JS_EXT | {".py"}]
    top = {p.relative_to(root).parts[0].removesuffix(".py") for p in files}
    edges, scanned = defaultdict(int), 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        rel = path.relative_to(root)
        src = _module(rel, depth)
        targets = set()
        if path.suffix == ".py":
            for m in PY_IMPORT.finditer(text):
                name = (m.group(1) or m.group(2)).split(".")
                if name[0] in top:
                    cand = root.joinpath(*name)
                    while cand != root and not (cand.is_dir() or cand.with_suffix(".py").is_file()):
                        cand = cand.parent
                    if cand != root:
                        target_file = cand / "__init__.py" if cand.is_dir() else cand.with_suffix(".py")
                        targets.add(_module(target_file.relative_to(root), depth))
        else:
            for m in JS_IMPORT.finditer(text):
                target = (path.parent / m.group(1)).resolve()
                if root in target.parents:
                    as_file = target if target.suffix else target / "index"
                    if target.is_dir():
                        as_file = target / "index"
                    targets.add(_module(as_file.relative_to(root), depth))
        for dst in targets - {src}:
            edges[(src, dst)] += 1
    return {"files_scanned": scanned, "edges": [{"from": a, "to": b, "imports": n} for (a, b), n in sorted(edges.items())],
            "cycles": _cycles(edges)}


def _cycles(edges):
    graph = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
    found, seen = [], set()

    def visit(node, stack):
        for nxt in sorted(graph[node]):
            if nxt in stack:
                cycle = stack[stack.index(nxt):] + [nxt]
                key = frozenset(cycle)
                if key not in seen:
                    seen.add(key)
                    found.append(cycle)
            elif len(stack) < 30:
                visit(nxt, stack + [nxt])
    for start in sorted(graph):
        visit(start, [start])
    return found


def database_model(root):
    """Tables and foreign keys from SQL files and Prisma schemas."""
    tables, relations, sources = {}, set(), []
    for path in _files(root):
        if path.suffix.lower() == ".sql":
            text = path.read_text(encoding="utf-8", errors="ignore")
            hit = False
            for m in CREATE_TABLE.finditer(text + ";"):
                name, body = m.group(1).split(".")[-1], m.group(2)
                cols = []
                for line in re.split(r",\s*(?![^()]*\))", body):
                    line = line.strip()
                    word = line.split()[0].strip('`"[]') if line.split() else ""
                    if word and word.lower() not in ("primary", "foreign", "constraint", "unique", "check", "key", "index"):
                        cols.append((word, (line.split()[1] if len(line.split()) > 1 else "").split("(")[0]))
                    for ref in REFERENCES.findall(line):
                        relations.add((name, ref.split(".")[-1]))
                tables[name], hit = cols, True
            if hit:
                sources.append(path.relative_to(root).as_posix())
        elif path.name == "schema.prisma":
            text = path.read_text(encoding="utf-8", errors="ignore")
            models = dict(PRISMA_MODEL.findall(text))
            for name, body in models.items():
                cols = []
                for line in body.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and not parts[0].startswith(("@@", "//")):
                        base = parts[1].rstrip("?[]")
                        if base in models:
                            if "[]" not in parts[1]:
                                relations.add((name, base))
                        else:
                            cols.append((parts[0], base))
                tables[name] = cols
            sources.append(path.relative_to(root).as_posix())
    return {"tables": {t: [list(c) for c in cols] for t, cols in tables.items()},
            "relations": sorted([list(r) for r in relations if r[1] in tables]), "sources": sources}


def _id(name):
    return re.sub(r"\W", "_", name) or "root"


def write(root, out_dir, depth=2):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    dep = dependency_graph(root, depth)
    if dep["edges"]:
        lines = ["# Module dependency graph", "",
                 f"**Evidence level: Observed** — derived from import statements in {dep['files_scanned']} "
                 "Python/JavaScript/TypeScript files. Dynamic imports and other languages are not included.", "",
                 "```mermaid", "graph LR"]
        lines += [f'  {_id(e["from"])}["{e["from"]}"] -->|{e["imports"]}| {_id(e["to"])}["{e["to"]}"]' for e in dep["edges"]]
        lines += ["```", ""]
        lines += (["## Circular dependencies", ""] + [f"- {' → '.join(c)}" for c in dep["cycles"]] + [""]
                  if dep["cycles"] else ["No circular dependencies between these modules.", ""])
        (out / "dependency-graph.md").write_text("\n".join(lines), encoding="utf-8")
        written.append("dependency-graph.md")
    db = database_model(root)
    if db["tables"]:
        lines = ["# Database entity-relationship diagram", "",
                 f"**Evidence level: Observed** — parsed from {', '.join(db['sources'])}. It shows the schema as "
                 "written in these files, which may differ from the live database.", "", "```mermaid", "erDiagram"]
        for table, cols in db["tables"].items():
            lines.append(f"  {_id(table)} {{")
            lines += [f"    {_id(ctype) or 'unknown'} {_id(col)}" for col, ctype in cols]
            lines.append("  }")
        lines += [f"  {_id(parent)} ||--o{{ {_id(child)} : has" for child, parent in db["relations"]]
        lines += ["```", ""]
        (out / "database-erd.md").write_text("\n".join(lines), encoding="utf-8")
        written.append("database-erd.md")
    return {"written": written, "dependency": dep, "database": db}
