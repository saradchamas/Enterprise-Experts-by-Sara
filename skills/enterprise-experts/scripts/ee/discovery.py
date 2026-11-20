"""Read-only project inventory: stack, adapters, tests, CI/CD, containers, IaC,
database artifacts, observability, docs, largest files and likely committed
secrets (values masked). Standard library only."""
import json
import os
import re
from collections import Counter
from pathlib import Path

from .adapters import WORKSPACE_MARKERS, detect_stacks, unsupported_languages
from .evidence import git_commit
from .secrets import ENV_SECRET, PLACEHOLDER, SECRET_PATTERNS, mask

SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "env", "__pycache__", "dist", "build",
             ".next", ".nuxt", "out", "target", "bin", "obj", ".idea", ".vscode", "coverage", ".turbo",
             ".cache", "Pods", ".gradle", ".dart_tool", "enterprise-review", ".terraform", "bower_components"}
LANG = {".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
        ".py": "Python", ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
        ".cs": "C#", ".rs": "Rust", ".swift": "Swift", ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte",
        ".sql": "SQL", ".scala": "Scala", ".c": "C", ".cpp": "C++", ".h": "C/C++ header", ".sh": "Shell",
        ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".ex": "Elixir", ".exs": "Elixir",
        ".cbl": "COBOL", ".cob": "COBOL", ".pl": "Perl", ".lua": "Lua", ".r": "R", ".m": "Objective-C",
        ".hs": "Haskell", ".clj": "Clojure", ".erl": "Erlang", ".zig": "Zig"}
MANIFESTS = {"package.json", "requirements.txt", "pyproject.toml", "Pipfile", "go.mod", "pom.xml", "build.gradle",
             "build.gradle.kts", "Gemfile", "composer.json", "Cargo.toml", "pubspec.yaml", "Package.swift"}
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "Pipfile.lock",
             "uv.lock", "go.sum", "Gemfile.lock", "composer.lock", "Cargo.lock", "pubspec.lock"}
CI_FILES = {".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml", "bitbucket-pipelines.yml", ".travis.yml",
            "cloudbuild.yaml", "buildspec.yml", "vercel.json", "netlify.toml", "firebase.json", "fly.toml",
            "render.yaml", "Procfile", "app.yaml", "wrangler.toml"}
IAC_NAMES = {"serverless.yml", "serverless.yaml", "Chart.yaml", "cdk.json", "Pulumi.yaml", "kustomization.yaml",
             "template.yaml", "skaffold.yaml"}
FRAMEWORK_HINTS = {
    "next": "Next.js", "react": "React", "vue": "Vue", "nuxt": "Nuxt", "@angular/core": "Angular",
    "svelte": "Svelte", "express": "Express", "fastify": "Fastify", "@nestjs/core": "NestJS", "koa": "Koa",
    "hono": "Hono", "django": "Django", "flask": "Flask", "fastapi": "FastAPI", "laravel/framework": "Laravel",
    "rails": "Rails", "spring-boot": "Spring Boot", "gin-gonic/gin": "Gin", "react-native": "React Native",
    "expo": "Expo", "flutter": "Flutter", "electron": "Electron", "vite": "Vite", "tailwindcss": "Tailwind CSS",
}
TEST_HINTS = {"jest": "Jest", "vitest": "Vitest", "mocha": "Mocha", "@playwright/test": "Playwright",
              "playwright": "Playwright", "cypress": "Cypress", "pytest": "pytest", "unittest": "unittest",
              "phpunit": "PHPUnit", "rspec": "RSpec", "junit": "JUnit", "@testing-library/react": "Testing Library"}
DB_HINTS = {"prisma": "Prisma", "typeorm": "TypeORM", "sequelize": "Sequelize", "mongoose": "Mongoose (MongoDB)",
            "drizzle-orm": "Drizzle", "knex": "Knex", "pg": "PostgreSQL driver", "mysql2": "MySQL driver",
            "sqlalchemy": "SQLAlchemy", "alembic": "Alembic", "psycopg": "PostgreSQL driver", "redis": "Redis",
            "ioredis": "Redis", "firebase-admin": "Firebase", "firebase": "Firebase", "@supabase/supabase-js": "Supabase",
            "pymongo": "MongoDB", "gorm": "GORM"}
OBS_HINTS = {"@sentry/": "Sentry", "sentry-sdk": "Sentry", "sentry_sdk": "Sentry", "@opentelemetry/": "OpenTelemetry",
             "opentelemetry": "OpenTelemetry", "dd-trace": "Datadog", "datadog": "Datadog", "prom-client": "Prometheus",
             "prometheus": "Prometheus", "winston": "winston (logging)", "pino": "pino (logging)",
             "structlog": "structlog (logging)", "loguru": "loguru (logging)", "newrelic": "New Relic",
             "posthog": "PostHog (analytics)", "mixpanel": "Mixpanel (analytics)", "@segment/": "Segment (analytics)",
             "honeycomb": "Honeycomb"}
PAID_HINTS = {"stripe": "Stripe", "openai": "OpenAI API", "@anthropic-ai/sdk": "Anthropic API", "anthropic": "Anthropic API",
              "twilio": "Twilio", "@sendgrid/": "SendGrid", "aws-sdk": "AWS SDK", "@aws-sdk/": "AWS SDK",
              "@google-cloud/": "Google Cloud", "boto3": "AWS SDK", "resend": "Resend", "algoliasearch": "Algolia",
              "@googlemaps/": "Google Maps", "cloudinary": "Cloudinary"}
AI_HINTS = {"openai": "OpenAI", "@anthropic-ai/sdk": "Anthropic", "anthropic": "Anthropic", "langchain": "LangChain",
            "llama-index": "LlamaIndex", "llama_index": "LlamaIndex", "@google/generative-ai": "Google Gemini",
            "google-generativeai": "Google Gemini", "ollama": "Ollama", "transformers": "Transformers",
            "@ai-sdk/": "Vercel AI SDK", "litellm": "LiteLLM", "cohere": "Cohere", "mistralai": "Mistral"}
UI_FRAMEWORKS = {"Next.js", "React", "Vue", "Nuxt", "Angular", "Svelte", "React Native", "Expo", "Flutter", "Electron"}
API_FRAMEWORKS = {"Express", "Fastify", "NestJS", "Koa", "Hono", "Django", "Flask", "FastAPI", "Laravel", "Rails",
                  "Spring Boot", "Gin"}
MOBILE_FRAMEWORKS = {"React Native", "Expo", "Flutter"}
TEXT_EXT = set(LANG) | {".json", ".yml", ".yaml", ".toml", ".env", ".ini", ".cfg", ".conf", ".properties", ".tf",
                         ".md", ".txt", ".xml", ".gradle", ".pem", ".key", ""}


def read_text(p, limit=400_000):
    try:
        if p.stat().st_size > limit:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_test_file(rel):
    name = rel.name.lower()
    parts = {x.lower() for x in rel.parts[:-1]}
    return (bool(parts & {"test", "tests", "__tests__", "spec", "specs", "e2e", "cypress"})
            or re.search(r"(\.|_)(test|spec)\.[a-z]+$", name) is not None
            or name.startswith("test_") or name.endswith("_test.go") or name.endswith("test.java"))


def discover(root):
    root = Path(root).resolve()
    d = {"root": str(root), "languages": Counter(), "manifests": [], "lockfiles": [], "frameworks": set(),
         "test_frameworks": set(), "test_files": 0, "source_files": 0, "ci": [], "containers": [], "iac": [],
         "database": {"tools": set(), "migrations_dirs": [], "schema_files": [], "sql_files": 0},
         "observability": set(), "paid_services": set(), "env_files": [], "docs": [], "api_specs": [],
         "largest_source_files": [], "secrets": [], "scripts": {}, "has_git": (root / ".git").exists(),
         "gitignore_covers_env": None, "notes": [], "commit": git_commit(root),
         "ai_libraries": set(), "workspace_markers": [], "dockerfile_dirs": set(), "tf_dirs": set(),
         "dotnet_dirs": set(), "data_markers": []}
    dep_blob = []
    sizes = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
        dp = Path(dirpath)
        rel_dir = dp.relative_to(root)
        low = dp.name.lower()
        if low in ("migrations", "migrate", "alembic"):
            d["database"]["migrations_dirs"].append(rel_dir.as_posix())
        if rel_dir.as_posix().replace("\\", "/") == ".github/workflows":
            d["ci"] += [(rel_dir / f).as_posix() for f in filenames if f.endswith((".yml", ".yaml"))]
        if low == "docs" and len(rel_dir.parts) <= 2:
            d["docs"].append(rel_dir.as_posix() + "/")
        for f in filenames:
            p = dp / f
            rel = p.relative_to(root)
            ext = p.suffix.lower()
            fl = f.lower()
            if f in MANIFESTS or ext == ".csproj":
                d["manifests"].append(rel.as_posix())
                dep_blob.append(read_text(p).lower())
                if f == "package.json" and len(rel.parts) == 1:
                    try:
                        d["scripts"] = json.loads(read_text(p)).get("scripts", {})
                    except (ValueError, AttributeError):
                        pass
            if ext in (".csproj", ".sln"):
                d["dotnet_dirs"].add(rel_dir.as_posix() or ".")
            if ext == ".tf":
                d["tf_dirs"].add(rel_dir.as_posix() or ".")
            if f in WORKSPACE_MARKERS:
                d["workspace_markers"].append(rel.as_posix())
            if fl.startswith("dockerfile"):
                d["dockerfile_dirs"].add(rel_dir.as_posix() or ".")
            if fl in ("dbt_project.yml", "airflow.cfg", "dagster.yaml") or ext == ".ipynb":
                d["data_markers"].append(rel.as_posix())
            if f in LOCKFILES:
                d["lockfiles"].append(rel.as_posix())
            if f in CI_FILES:
                d["ci"].append(rel.as_posix())
            if fl.startswith("dockerfile") or fl.startswith("docker-compose") or fl in ("compose.yml", "compose.yaml"):
                d["containers"].append(rel.as_posix())
            if ext == ".tf" or f in IAC_NAMES:
                d["iac"].append(rel.as_posix())
            if fl in ("schema.prisma", "schema.sql", "schema.rb", "structure.sql") or fl.endswith(".dbml"):
                d["database"]["schema_files"].append(rel.as_posix())
            if ext == ".sql":
                d["database"]["sql_files"] += 1
            if fl.startswith(".env"):
                d["env_files"].append(rel.as_posix())
            if fl.startswith("readme") or fl in ("claude.md", "agents.md", "contributing.md", "changelog.md", "security.md"):
                d["docs"].append(rel.as_posix())
            if re.search(r"(openapi|swagger)[^/]*\.(ya?ml|json)$", fl):
                d["api_specs"].append(rel.as_posix())
            if ext in LANG:
                d["languages"][LANG[ext]] += 1
                if is_test_file(rel):
                    d["test_files"] += 1
                else:
                    d["source_files"] += 1
                    try:
                        sizes.append((p.stat().st_size, rel.as_posix()))
                    except OSError:
                        pass
            # secret scan
            if (ext in TEXT_EXT or fl.startswith(".env")) and f not in LOCKFILES and len(d["secrets"]) < 200:
                is_example = bool(re.search(r"(example|sample|template|\.dist)$", fl))
                text = read_text(p, 300_000)
                if not text:
                    continue
                for n, line in enumerate(text.splitlines(), 1):
                    if len(line) > 2000:
                        continue
                    for label, rx in SECRET_PATTERNS:
                        m = rx.search(line)
                        if not m:
                            continue
                        val = m.group(1) if m.groups() else m.group(0)
                        if label == "Hardcoded credential assignment" and (PLACEHOLDER.search(val) or is_test_file(rel)):
                            continue
                        if is_example and PLACEHOLDER.search(val):
                            continue
                        d["secrets"].append({"file": rel.as_posix(), "line": n, "type": label, "masked": mask(val),
                                             "in_example_file": is_example})
                        break
                if fl.startswith(".env") and not is_example:
                    for n, line in enumerate(text.splitlines(), 1):
                        m = ENV_SECRET.match(line.strip())
                        if m and not PLACEHOLDER.search(m.group(2)):
                            d["secrets"].append({"file": rel.as_posix(), "line": n, "type": f"Env secret {m.group(1)}",
                                                 "masked": mask(m.group(2)), "in_example_file": False})
    blob = "\n".join(dep_blob)
    for hints, target in ((FRAMEWORK_HINTS, d["frameworks"]), (TEST_HINTS, d["test_frameworks"]),
                          (DB_HINTS, d["database"]["tools"]), (OBS_HINTS, d["observability"]),
                          (PAID_HINTS, d["paid_services"]), (AI_HINTS, d["ai_libraries"])):
        for key, label in hints.items():
            if re.search(r"(?<![a-z0-9_\-])" + re.escape(key), blob):
                target.add(label)
    gi = root / ".gitignore"
    if gi.exists():
        d["gitignore_covers_env"] = bool(re.search(r"(?m)^\s*\.env", read_text(gi)))
    sizes.sort(reverse=True)
    d["largest_source_files"] = [{"file": f, "kb": round(s / 1024, 1)} for s, f in sizes[:10]]
    # de-duplicate secrets per file/line
    seen, uniq = set(), []
    for s in d["secrets"]:
        k = (s["file"], s["line"])
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    d["secrets"] = uniq
    # notes: quick gaps
    if not d["ci"]:
        d["notes"].append("No CI/CD configuration found.")
    if d["test_files"] == 0:
        d["notes"].append("No test files found.")
    if not d["containers"]:
        d["notes"].append("No Dockerfile / compose file found.")
    if not d["observability"]:
        d["notes"].append("No error-tracking, metrics or logging library detected in manifests.")
    if d["manifests"] and not d["lockfiles"]:
        d["notes"].append("Dependency manifest without a lockfile (builds not reproducible).")
    real_env = [e for e in d["env_files"] if not re.search(r"(example|sample|template|dist)$", e.lower())]
    if real_env:
        d["notes"].append("Real .env file(s) present in the tree: " + ", ".join(real_env) +
                          " — check `git ls-files` to see whether they are committed.")
    if d["gitignore_covers_env"] is False:
        d["notes"].append(".gitignore does not ignore .env files.")
    if not any(x.lower().startswith("readme") for x in d["docs"]):
        d["notes"].append("No README at any level.")
    # stacks, adapters and project-type flags
    d["stacks"] = detect_stacks(root, d["manifests"], d["tf_dirs"], d["dotnet_dirs"])
    d["unsupported"] = unsupported_languages(d["languages"], d["stacks"])
    code_stacks = [s for s in d["stacks"] if s["adapter"] != "terraform"]
    fw = d["frameworks"]
    d["flags"] = {
        "is_monorepo": bool(d["workspace_markers"]) or any(s.get("workspaces") for s in d["stacks"])
        or len({s["path"] for s in code_stacks}) >= 3,
        "is_microservices": len(d["dockerfile_dirs"]) >= 3,
        "has_ui": bool(fw & UI_FRAMEWORKS) or any(k in d["languages"] for k in ("HTML", "Vue", "Svelte")),
        "has_api": bool(fw & API_FRAMEWORKS) or bool(d["api_specs"]),
        "has_mobile": bool(fw & MOBILE_FRAMEWORKS),
        "has_database": bool(d["database"]["tools"] or d["database"]["migrations_dirs"]
                             or d["database"]["schema_files"] or d["database"]["sql_files"]),
        "has_ai": bool(d["ai_libraries"]),
        "has_paid_services": bool(d["paid_services"]),
        "has_ci": bool(d["ci"]),
        "has_containers": bool(d["containers"]),
        "has_iac": bool(d["iac"]),
        "has_data_pipeline": bool(d["data_markers"]),
        "infrastructure_only": bool(d["iac"]) and not code_stacks and d["source_files"] <= d["languages"].get("Shell", 0),
        "unsupported_stack": not d["stacks"] and d["source_files"] > 0,
    }
    if d["flags"]["unsupported_stack"]:
        d["notes"].append("No supported stack adapter matched: run-based checks are Not assessed for this project.")
    for k in ("dockerfile_dirs", "tf_dirs", "dotnet_dirs"):
        del d[k]
    # make JSON-serialisable
    for k in ("frameworks", "test_frameworks", "observability", "paid_services", "ai_libraries"):
        d[k] = sorted(d[k])
    d["database"]["tools"] = sorted(d["database"]["tools"])
    d["languages"] = dict(d["languages"].most_common())
    return d


def to_markdown(d):
    def lst(xs, n=15):
        xs = list(xs)
        return ", ".join(f"`{x}`" for x in xs[:n]) + (f" … (+{len(xs) - n} more)" if len(xs) > n else "") if xs else "none found"
    o = ["# Project Discovery", "", f"Root: `{d['root']}`  |  Git repo: {'yes' if d['has_git'] else 'no'}  |  Commit: {d['commit'] or 'n/a'}", "",
         "| Aspect | Found |", "|---|---|",
         f"| Languages (files) | {', '.join(f'{k} {v}' for k, v in d['languages'].items()) or 'none'} |",
         f"| Frameworks | {', '.join(d['frameworks']) or 'none detected'} |",
         f"| Manifests | {lst(d['manifests'])} |",
         f"| Lockfiles | {lst(d['lockfiles'])} |",
         f"| Source files / test files | {d['source_files']} / {d['test_files']} |",
         f"| Test frameworks | {', '.join(d['test_frameworks']) or 'none detected'} |",
         f"| CI/CD & deploy config | {lst(d['ci'])} |",
         f"| Containers | {lst(d['containers'])} |",
         f"| Infrastructure as code | {lst(d['iac'])} |",
         f"| Database tools | {', '.join(d['database']['tools']) or 'none detected'} |",
         f"| Migrations dirs | {lst(d['database']['migrations_dirs'])} |",
         f"| Schema files / .sql files | {lst(d['database']['schema_files'])} / {d['database']['sql_files']} |",
         f"| Observability & analytics | {', '.join(d['observability']) or 'none detected'} |",
         f"| Paid / usage-based services | {', '.join(d['paid_services']) or 'none detected'} |",
         f"| API specs | {lst(d['api_specs'])} |",
         f"| Docs | {lst(d['docs'])} |",
         f"| Env files | {lst(d['env_files'])} |", ""]
    o += ["## Project type", "", ", ".join(k for k, v in d["flags"].items() if v) or "no special flags", "",
          "## Stacks and available checks", ""]
    if not d["stacks"]:
        o += ["No supported stack detected.", ""]
    for s in d["stacks"]:
        o += [f"### `{s['path']}` — {s['label']}", "",
              "Tools: " + ", ".join(f"{t} ({'installed' if ok else 'NOT installed here'})"
                                    for t, ok in s["prerequisites"].items()), ""]
        o += [f"- {name}: `{' '.join(cmd)}`" if cmd else f"- {name}: not available — {s['unavailable'].get(name, '')}"
              for name, cmd in s["commands"].items()]
        o += [f"- Limitation: {x}" for x in s["limitations"]] + [""]
    if d["unsupported"]:
        o += ["## Not supported by an adapter", ""] + [f"- {u['language']}: {u['reason']}" for u in d["unsupported"]] + [""]
    if d["scripts"]:
        o += ["## package.json scripts", ""] + [f"- `{k}`: `{v}`" for k, v in list(d["scripts"].items())[:25]] + [""]
    o += ["## Largest source files", ""] + [f"- `{x['file']}` — {x['kb']} KB" for x in d["largest_source_files"]] + [""]
    o += [f"## Possible committed secrets ({len(d['secrets'])})", "",
          "Values are masked. Triage each one: confirm it is real and whether it is tracked by git before reporting.", ""]
    if d["secrets"]:
        o += ["| File | Line | Type | Masked value |", "|---|---|---|---|"]
        o += [f"| `{s['file']}` | {s['line']} | {s['type']} | `{s['masked']}` |" for s in d["secrets"][:60]]
    else:
        o.append("None matched the built-in patterns (this does not prove there are none).")
    o += ["", "## Gaps noticed", ""] + ([f"- {n}" for n in d["notes"]] or ["- None from the automated pass."]) + [""]
    return "\n".join(o)
