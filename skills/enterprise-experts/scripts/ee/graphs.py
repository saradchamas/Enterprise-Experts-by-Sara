"""Diagrams generated from the code itself, as Mermaid. Every diagram states how it
was derived: these are Observed (static analysis of files), never drawn from memory."""
import re
from collections import defaultdict
from pathlib import Path

from .discovery import AUX_DIRS, FIXTURE_DIRS, SKIP_DIRS

PY_IMPORT = re.compile(r"(?m)^\s*(?:from\s+(\.*[\w.]*)\s+import\s+(\(?[\w ,]*)|import\s+([\w.]+))")
PY_ROOTS = ("", "src", "lib")   # where top-level Python packages usually live
JS_IMPORT = re.compile(r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|require\(\s*|import\(\s*)['"](\.{1,2}/[^'"]+)['"]""")
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
CREATE_TABLE = re.compile(r"(?is)create\s+table\s+(?:if\s+not\s+exists\s+)?[`\"\[]?([\w.]+)[`\"\]]?\s*\((.*?)\)\s*;")
REFERENCES = re.compile(r"(?i)references\s+[`\"\[]?([\w.]+)[`\"\]]?")
MAX_DRAWN_EDGES = 120
# SQLModel (`class Item(Base, table=True):`) and SQLAlchemy declarative classes (`__tablename__ = "item"`).
ORM_CLASS = re.compile(r"(?m)^class\s+(\w+)\(([^)]*)\):\n((?:[ \t]+.*\n|\n)+)")
ORM_FIELD = re.compile(r"^[ \t]+(\w+)\s*(?::\s*([\w.\[\] |]+?)\s*(?:=|$)|=\s*(?:Column|mapped_column)\()")
PRISMA_MODEL = re.compile(r"(?s)\bmodel\s+(\w+)\s*\{(.*?)\}")


def _files(root, also_skip=frozenset()):
    skip = SKIP_DIRS | FIXTURE_DIRS | also_skip
    for path in Path(root).rglob("*"):
        if path.is_file() and not (set(path.relative_to(root).parts[:-1]) & skip):
            yield path


def _py_target(base, names):
    """The file or package a dotted name points at, walking back to the longest part that exists."""
    cand = base.joinpath(*names)
    while cand != base and not (cand.is_dir() or cand.with_suffix(".py").is_file()):
        cand = cand.parent
    if cand == base:
        return None
    return cand / "__init__.py" if cand.is_dir() else cand.with_suffix(".py")


def _module(rel, depth):
    parts = rel.parts[:-1][:depth]
    return "/".join(parts) if parts else "(root)"


def dependency_graph(root, depth=2):
    """Edges between directories (to `depth` levels), from import statements."""
    root = Path(root).resolve()
    files = [p for p in _files(root) if p.suffix in JS_EXT | {".py"}]
    # Top-level packages live at the root, under src/ or lib/, or one level down in a service folder
    # (backend/app, services/api/src/...). Each is a place an absolute import can start from.
    bases = [root / r for r in PY_ROOTS if (root / r).is_dir()]
    for sub in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in SKIP_DIRS | FIXTURE_DIRS
                      and not p.name.startswith(".")):
        if any((sub / m).exists() for m in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile")):
            bases += [b for b in (sub, sub / "src") if b.is_dir()]
    tops = {b: {c.name.removesuffix(".py") for c in b.iterdir() if c.is_dir() or c.suffix == ".py"} for b in bases}
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
                dotted = m.group(1) if m.group(1) is not None else m.group(3)
                target_file = None
                if dotted.startswith("."):                       # relative: from . import x / from ..pkg import y
                    level = len(dotted) - len(dotted.lstrip("."))
                    base = path.parent
                    for _ in range(level - 1):
                        base = base.parent
                    if root != base and root not in base.parents:
                        continue
                    rest = [x for x in dotted.lstrip(".").split(".") if x]
                    firsts = [x.strip() for x in (m.group(2) or "").strip("( ").split(",") if x.strip()]
                    for names in ([rest + [f.split()[0]] for f in firsts] if not rest else [rest]):
                        target_file = _py_target(base, names)
                        if target_file is not None and root in target_file.parents:
                            targets.add(_module(target_file.relative_to(root), depth))
                    continue
                name = dotted.split(".")
                for base in bases:
                    if name[0] in tops[base]:
                        target_file = _py_target(base, name)
                        if target_file is not None:
                            targets.add(_module(target_file.relative_to(root), depth))
                            break
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
    cycles, sizes = _cycles(edges)
    return {"files_scanned": scanned, "edges": [{"from": a, "to": b, "imports": n} for (a, b), n in sorted(edges.items())],
            "cycles": cycles, "cycle_group_sizes": sizes}


def _cycles(edges):
    """One example cycle per group of modules that depend on each other in a circle.

    Groups are strongly connected components (Tarjan, iterative), so the cost grows with the
    number of edges. Listing every distinct cycle grows exponentially and never finished on a
    large project; one shortest example per group is what a reader can act on."""
    graph = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        graph.setdefault(b, set())
    index, low, on_stack, stack, groups, counter = {}, {}, set(), [], [], 0
    for root in sorted(graph):
        if root in index:
            continue
        work = [(root, iter(sorted(graph[root])))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            pushed = False
            for nxt in children:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(graph[nxt]))))
                    pushed = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if pushed:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                group = []
                while True:
                    top = stack.pop()
                    on_stack.discard(top)
                    group.append(top)
                    if top == node:
                        break
                if len(group) > 1:
                    groups.append(sorted(group))
    found = []
    for group in sorted(groups):
        members, start = set(group), group[0]
        parent, queue, end = {start: None}, [start], None
        while queue and end is None:          # shortest way from `start` back to itself, inside the group
            node = queue.pop(0)
            for nxt in sorted(graph[node] & members):
                if nxt == start:
                    end = node
                    break
                if nxt not in parent:
                    parent[nxt] = node
                    queue.append(nxt)
        path = []
        while end is not None:
            path.append(end)
            end = parent[end]
        found.append(path[::-1] + [start])
    return found, [len(g) for g in sorted(groups)]


def database_model(root):
    """Tables and foreign keys from SQL files and Prisma schemas."""
    tables, relations, sources = {}, set(), []
    for path in _files(root, AUX_DIRS):       # schemas in examples, docs and tests are not the product's
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
        elif path.suffix == ".py":
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "table=True" not in text and "__tablename__" not in text:
                continue
            hit = False
            for m in ORM_CLASS.finditer(text):
                name, bases_text, body = m.group(1), m.group(2), m.group(3)
                explicit = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", body)
                if not explicit and not re.search(r"table\s*=\s*True", bases_text):
                    continue
                table = explicit.group(1) if explicit else name.lower()      # SQLModel's default table name
                cols = []
                for line in body.splitlines():
                    col = ORM_FIELD.match(line)
                    if not col or col.group(1).startswith("_"):
                        continue
                    if re.search(r"\b(?:R|r)elationship\(", line):
                        continue
                    cols.append((col.group(1), re.sub(r"\W.*", "", col.group(2) or "") or "column"))
                for ref in re.findall(r"(?:foreign_key\s*=\s*|ForeignKey\(\s*)['\"]([\w.]+)['\"]", body):
                    relations.add((table, ref.split(".")[0]))      # a Field(...) call may span several lines
                tables[table], hit = cols, True
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
        # A diagram with hundreds of arrows cannot be read and most viewers refuse to draw it.
        drawn, note = dep, ""
        if len(dep["edges"]) > MAX_DRAWN_EDGES and depth > 1:
            drawn = dependency_graph(root, 1)
            note = (f" The project has {len(dep['edges'])} dependencies between modules at depth {depth}; the diagram "
                    f"is drawn at depth 1 and the full list is in `dependency-edges.csv`.")
        shown = sorted(drawn["edges"], key=lambda e: -e["imports"])[:MAX_DRAWN_EDGES]
        if len(shown) < len(drawn["edges"]):
            note += (f" Only the {MAX_DRAWN_EDGES} most-used of {len(drawn['edges'])} dependencies are drawn.")
        if note:
            rows = ["from,to,imports"] + [f'"{e["from"]}","{e["to"]}",{e["imports"]}' for e in dep["edges"]]
            (out / "dependency-edges.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
            written.append("dependency-edges.csv")
        lines = ["# Module dependency graph", "",
                 f"**Evidence level: Observed** — derived from import statements in {dep['files_scanned']} "
                 "Python/JavaScript/TypeScript files. Dynamic imports and other languages are not included." + note, "",
                 "```mermaid", "graph LR"]
        lines += [f'  {_id(e["from"])}["{e["from"]}"] -->|{e["imports"]}| {_id(e["to"])}["{e["to"]}"]'
                  for e in sorted(shown, key=lambda e: (e["from"], e["to"]))]
        lines += ["```", ""]
        lines += (["## Circular dependencies", "",
                   "One shortest example per group of modules that depend on each other in a circle; "
                   "the number is how many modules are in that group.", ""]
                  + [f"- ({n} modules) {' → '.join(c)}" for c, n in zip(dep["cycles"], dep["cycle_group_sizes"], strict=True)] + [""]
                  if dep["cycles"] else ["No circular dependencies between these modules.", ""])
        (out / "dependency-graph.md").write_text("\n".join(lines), encoding="utf-8")
        written.append("dependency-graph.md")
    db = database_model(root)
    if db["tables"]:
        lines = ["# Database entity-relationship diagram", "",
                 f"**Evidence level: Observed** — parsed from {', '.join(db['sources'])}. It shows the schema as "
                 "written in these files, which may differ from the live database. For Python models, columns a class "
                 "inherits from a base class are not shown.", "", "```mermaid", "erDiagram"]
        for table, cols in db["tables"].items():
            lines.append(f"  {_id(table)} {{")
            lines += [f"    {_id(ctype) or 'unknown'} {_id(col)}" for col, ctype in cols]
            lines.append("  }")
        lines += [f"  {_id(parent)} ||--o{{ {_id(child)} : has" for child, parent in db["relations"]]
        lines += ["```", ""]
        (out / "database-erd.md").write_text("\n".join(lines), encoding="utf-8")
        written.append("database-erd.md")
    skipped = []
    if not dep["edges"]:
        skipped.append("dependency graph: no imports between directories were found "
                       f"({dep['files_scanned']} Python/JS/TS files scanned), so there is nothing to draw")
    if not db["tables"]:
        skipped.append("database ERD: no CREATE TABLE statements or Prisma models found")
    return {"written": written, "skipped": skipped, "dependency": dep, "database": db}
