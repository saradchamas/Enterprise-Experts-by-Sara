"""Technology adapters: for each detected stack, which checks can run and how.

An adapter never invents a result. It lists the commands that exist for this
project, the tools they need (and whether those tools are installed here), and
its limitations. Anything else is reported as not available, with a reason, so
the orchestrator records the check as Not assessed instead of guessing.
"""
import json
import re
import shutil
from pathlib import Path

CHECKS = ("install", "build", "test", "lint", "typecheck", "audit")


def _read(path, limit=300_000):
    try:
        return path.read_text(encoding="utf-8", errors="ignore") if path.stat().st_size <= limit else ""
    except OSError:
        return ""


def _node(d, root):
    try:
        pkg = json.loads(_read(d / "package.json") or "{}")
    except ValueError:
        pkg = {}
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    pm = "npm"
    for base in (d, root):
        for lock, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"),
                           ("package-lock.json", "npm")):
            if (base / lock).exists():
                pm = name
                break
        else:
            continue
        break
    has_lock = any((b / f).exists() for b in (d, root)
                   for f in ("pnpm-lock.yaml", "yarn.lock", "bun.lockb", "package-lock.json"))
    cmds, missing = {}, {}
    real_test = scripts.get("test") and "no test specified" not in scripts["test"]
    cmds["install"] = {"npm": ["npm", "ci"], "pnpm": ["pnpm", "install", "--frozen-lockfile"],
                       "yarn": ["yarn", "install", "--frozen-lockfile"], "bun": ["bun", "install", "--frozen-lockfile"]}[pm] \
        if has_lock else None
    if not has_lock:
        missing["install"] = "no lockfile, so a reproducible install is not possible"
    cmds["test"] = [pm, "test"] if real_test else None
    if not real_test:
        missing["test"] = "package.json has no real test script"
    for name in ("build", "lint"):
        cmds[name] = [pm, "run", name] if scripts.get(name) else None
        if not scripts.get(name):
            missing[name] = f"package.json has no {name} script"
    if scripts.get("typecheck"):
        cmds["typecheck"] = [pm, "run", "typecheck"]
    elif (d / "tsconfig.json").exists():
        cmds["typecheck"] = ["npx", "--no-install", "tsc", "--noEmit"]
    else:
        cmds["typecheck"], missing["typecheck"] = None, "not a TypeScript project"
    if has_lock:
        cmds["audit"] = {"npm": ["npm", "audit", "--omit=dev"], "pnpm": ["pnpm", "audit", "--prod"],
                         "yarn": ["yarn", "audit"], "bun": ["npm", "audit", "--omit=dev"]}[pm]
    else:
        cmds["audit"], missing["audit"] = None, "the dependency audit needs a lockfile, and there is none"
    return {"adapter": "node", "label": f"JavaScript/TypeScript ({pm})", "tools": ["node", pm], "commands": cmds,
            "unavailable": missing,
            "limitations": ["Tests and audit need dependencies installed and (for audit) network access."],
            "workspaces": bool(pkg.get("workspaces"))}


def _python(d, root):
    text = "\n".join(_read(d / f) for f in ("pyproject.toml", "requirements.txt", "requirements-dev.txt",
                                            "Pipfile", "setup.cfg", "tox.ini")).lower()
    has_tests = (d / "tests").is_dir() or (d / "test").is_dir() or "pytest" in text
    cmds, missing = {"install": None, "build": None, "typecheck": None}, {
        "install": "installing Python dependencies changes the environment; do it in a virtualenv with approval",
        "build": "no build step for this stack"}
    cmds["test"] = ["python", "-m", "pytest", "-q"] if has_tests else None
    if not has_tests:
        missing["test"] = "no tests directory and pytest is not a dependency"
    cmds["lint"] = ["ruff", "check", "."] if "ruff" in text else (["flake8"] if "flake8" in text else None)
    if not cmds["lint"]:
        missing["lint"] = "no linter configured"
    if "mypy" in text:
        cmds["typecheck"] = ["mypy", "."]
    else:
        missing["typecheck"] = "no type checker configured"
    cmds["audit"] = ["pip-audit"]
    return {"adapter": "python", "label": "Python", "tools": ["python", "pip-audit"], "commands": cmds,
            "unavailable": missing, "limitations": ["Tests need the project's dependencies installed."]}


def _simple(adapter, label, tools, cmds, limitations=(), unavailable=None):
    full = {k: cmds.get(k) for k in CHECKS}
    un = {k: "this adapter has no command for it" for k, v in full.items() if v is None}
    un.update(unavailable or {})
    return {"adapter": adapter, "label": label, "tools": list(tools), "commands": full, "unavailable": un,
            "limitations": list(limitations)}


def _java(d, root):
    if (d / "pom.xml").exists():
        mvn = "./mvnw" if (d / "mvnw").exists() else "mvn"
        return _simple("java", "Java/Kotlin (Maven)", ["java", "mvn"],
                       {"build": [mvn, "-q", "-DskipTests", "package"], "test": [mvn, "-q", "test"]},
                       ["Dependency audit needs the OWASP dependency-check plugin; not run automatically."])
    gr = "./gradlew" if (d / "gradlew").exists() else "gradle"
    return _simple("java", "Java/Kotlin (Gradle)", ["java", "gradle"],
                   {"build": [gr, "assemble"], "test": [gr, "test"], "lint": [gr, "check", "-x", "test"]},
                   ["Dependency audit needs a plugin; not run automatically."])


def _php(d, root):
    text = _read(d / "composer.json").lower()
    test = ["php", "artisan", "test"] if (d / "artisan").exists() else (
        ["vendor/bin/phpunit"] if "phpunit" in text else None)
    return _simple("php", "PHP (Laravel)" if (d / "artisan").exists() else "PHP (Composer)", ["php", "composer"],
                   {"install": ["composer", "install", "--no-interaction"] if (d / "composer.lock").exists() else None,
                    "test": test, "audit": ["composer", "audit"]},
                   unavailable={} if test else {"test": "phpunit is not a dependency"})


def _dart(d, root):
    flutter = re.search(r"(?m)^\s*flutter\s*:", _read(d / "pubspec.yaml")) is not None
    tool = "flutter" if flutter else "dart"
    return _simple("dart", "Flutter" if flutter else "Dart", [tool],
                   {"install": [tool, "pub", "get"], "test": [tool, "test"], "lint": [tool, "analyze"]},
                   ["Mobile builds, signing and store configuration are reviewed by reading config, not by building."])


def _ruby(d, root):
    text = (_read(d / "Gemfile") + _read(d / "Gemfile.lock")).lower()
    test = ["bundle", "exec", "rspec"] if "rspec" in text else (
        ["bundle", "exec", "rails", "test"] if "rails" in text else None)
    return _simple("ruby", "Ruby", ["ruby", "bundle"], {"test": test, "audit": ["bundle", "audit"],
                                                         "lint": ["bundle", "exec", "rubocop"] if "rubocop" in text else None})


FIXED = {
    "go.mod": lambda d, r: _simple("go", "Go", ["go", "govulncheck"],
                                   {"build": ["go", "build", "./..."], "test": ["go", "test", "./..."],
                                    "lint": ["go", "vet", "./..."], "audit": ["govulncheck", "./..."]}),
    "Cargo.toml": lambda d, r: _simple("rust", "Rust", ["cargo"],
                                       {"build": ["cargo", "build"], "test": ["cargo", "test"],
                                        "lint": ["cargo", "clippy"], "audit": ["cargo", "audit"]}),
}
MANIFEST_ADAPTERS = [("package.json", _node), ("pyproject.toml", _python), ("requirements.txt", _python),
                     ("Pipfile", _python), ("pom.xml", _java), ("build.gradle", _java), ("build.gradle.kts", _java),
                     ("go.mod", FIXED["go.mod"]), ("composer.json", _php), ("Cargo.toml", FIXED["Cargo.toml"]),
                     ("pubspec.yaml", _dart), ("Gemfile", _ruby)]
LANG_ADAPTER = {"TypeScript": "node", "JavaScript": "node", "Vue": "node", "Svelte": "node", "Python": "python",
                "Go": "go", "Java": "java", "Kotlin": "java", "PHP": "php", "Rust": "rust", "Dart": "dart",
                "C#": "dotnet", "Ruby": "ruby"}
NOT_CODE = {"SQL", "HTML", "CSS", "SCSS", "Shell", "Terraform"}
WORKSPACE_MARKERS = ("pnpm-workspace.yaml", "turbo.json", "nx.json", "lerna.json", "go.work", "rush.json")


def detect_stacks(root, manifest_paths, tf_dirs=(), dotnet_dirs=()):
    """One stack entry per directory that holds a manifest."""
    root = Path(root)
    stacks, seen = [], set()
    for rel in sorted(manifest_paths):
        d = (root / rel).parent
        for name, build in MANIFEST_ADAPTERS:
            if Path(rel).name == name:
                key = (d, build)
                if key in seen:
                    break
                seen.add(key)
                stacks.append(dict(build(d, root), path=d.relative_to(root).as_posix() or "."))
                break
    for d in sorted(set(dotnet_dirs)):
        stacks.append(dict(_simple("dotnet", ".NET", ["dotnet"],
                                   {"build": ["dotnet", "build"], "test": ["dotnet", "test"],
                                    "audit": ["dotnet", "list", "package", "--vulnerable"]}), path=d))
    for d in sorted(set(tf_dirs)):
        stacks.append(dict(_simple("terraform", "Terraform", ["terraform", "tflint"],
                                   {"lint": ["terraform", "fmt", "-check", "-recursive"],
                                    "build": ["terraform", "validate"]},
                                   ["terraform validate needs `terraform init` (network). plan/apply are never run."]),
                           path=d))
    for s in stacks:
        s["prerequisites"] = {t: shutil.which(t) is not None for t in s.pop("tools")}
    return stacks


def unsupported_languages(languages, stacks):
    have = {s["adapter"] for s in stacks}
    out = []
    for lang in languages:
        if lang in NOT_CODE:
            continue
        need = LANG_ADAPTER.get(lang)
        if need is None:
            out.append({"language": lang, "reason": "no adapter for this language yet: checks that need running "
                        "its toolchain are Not assessed; code can still be read and reviewed"})
        elif need not in have:
            out.append({"language": lang, "reason": f"{lang} files found but no manifest for the {need} adapter"})
    return out
