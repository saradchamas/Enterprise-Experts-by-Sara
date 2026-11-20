#!/usr/bin/env python3
"""Inventory a software project for the Enterprise Experts review.

Usage: python discover_project.py <project_dir> [--out <review_dir>]

Read-only. Detects stack, manifests, tests, CI/CD, containers, IaC, database
artifacts, observability, docs, largest source files, and likely committed
secrets (values are masked). Writes discovery.json and discovery.md.
Standard library only.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "env", "__pycache__", "dist", "build",
             ".next", ".nuxt", "out", "target", "bin", "obj", ".idea", ".vscode", "coverage", ".turbo",
             ".cache", "Pods", ".gradle", ".dart_tool", "enterprise-review", ".terraform", "bower_components"}
LANG = {".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
        ".py": "Python", ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
        ".cs": "C#", ".rs": "Rust", ".swift": "Swift", ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte",
        ".sql": "SQL", ".scala": "Scala", ".c": "C", ".cpp": "C++", ".h": "C/C++ header", ".sh": "Shell",
        ".html": "HTML", ".css": "CSS", ".scss": "SCSS"}
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
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{16,}\b")),
    ("Generic sk- API key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("Connection string with password", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:/@'\"]+:[^\s@'\"]{3,}@")),
    ("Hardcoded credential assignment", re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key)\b\s*[:=]\s*['\"]([^'\"\s$<{]{8,})['\"]")),
]
PLACEHOLDER = re.compile(r"(?i)(example|changeme|change_me|your[_-]|placeholder|xxxx|dummy|test|sample|<.*>|\*\*\*|todo|localhost|password123?$)")
TEXT_EXT = set(LANG) | {".json", ".yml", ".yaml", ".toml", ".env", ".ini", ".cfg", ".conf", ".properties", ".tf",
                         ".md", ".txt", ".xml", ".gradle", ".pem", ".key", ""}


def mask(s):
    s = s.strip()
    return (s[:4] + "…" + s[-2:]) if len(s) > 10 else "…masked…"


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
         "gitignore_covers_env": None, "notes": []}
    dep_blob = []
    sizes = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
        dp = Path(dirpath)
        rel_dir = dp.relative_to(root)
        low = dp.name.lower()
        if low in ("migrations", "migrate", "alembic"):
            d["database"]["migrations_dirs"].append(str(rel_dir))
        if str(rel_dir).replace("\\", "/") == ".github/workflows":
            d["ci"] += [str(rel_dir / f) for f in filenames if f.endswith((".yml", ".yaml"))]
        if low == "docs" and len(rel_dir.parts) <= 2:
            d["docs"].append(str(rel_dir) + "/")
        for f in filenames:
            p = dp / f
            rel = p.relative_to(root)
            ext = p.suffix.lower()
            fl = f.lower()
            if f in MANIFESTS or ext == ".csproj":
                d["manifests"].append(str(rel))
                dep_blob.append(read_text(p).lower())
                if f == "package.json" and len(rel.parts) == 1:
                    try:
                        d["scripts"] = json.loads(read_text(p)).get("scripts", {})
                    except (ValueError, AttributeError):
                        pass
            if f in LOCKFILES:
                d["lockfiles"].append(str(rel))
            if f in CI_FILES:
                d["ci"].append(str(rel))
            if fl.startswith("dockerfile") or fl.startswith("docker-compose") or fl in ("compose.yml", "compose.yaml"):
                d["containers"].append(str(rel))
            if ext == ".tf" or f in IAC_NAMES:
                d["iac"].append(str(rel))
            if fl in ("schema.prisma", "schema.sql", "schema.rb", "structure.sql") or fl.endswith(".dbml"):
                d["database"]["schema_files"].append(str(rel))
            if ext == ".sql":
                d["database"]["sql_files"] += 1
            if fl.startswith(".env"):
                d["env_files"].append(str(rel))
            if fl.startswith("readme") or fl in ("claude.md", "agents.md", "contributing.md", "changelog.md", "security.md"):
                d["docs"].append(str(rel))
            if re.search(r"(openapi|swagger)[^/]*\.(ya?ml|json)$", fl):
                d["api_specs"].append(str(rel))
            if ext in LANG:
                d["languages"][LANG[ext]] += 1
                if is_test_file(rel):
                    d["test_files"] += 1
                else:
                    d["source_files"] += 1
                    try:
                        sizes.append((p.stat().st_size, str(rel)))
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
                        d["secrets"].append({"file": str(rel), "line": n, "type": label, "masked": mask(val),
                                             "in_example_file": is_example})
                        break
                # plain KEY=value secrets inside real .env files
                if fl.startswith(".env") and not is_example:
                    for n, line in enumerate(text.splitlines(), 1):
                        m = re.match(r"\s*([A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*=\s*(\S{8,})", line)
                        if m and not PLACEHOLDER.search(m.group(2)):
                            d["secrets"].append({"file": str(rel), "line": n, "type": f"Env secret {m.group(1)}",
                                                 "masked": mask(m.group(2).strip('"\'')), "in_example_file": False})
    blob = "\n".join(dep_blob)
    for hints, target in ((FRAMEWORK_HINTS, d["frameworks"]), (TEST_HINTS, d["test_frameworks"]),
                          (DB_HINTS, d["database"]["tools"]), (OBS_HINTS, d["observability"]),
                          (PAID_HINTS, d["paid_services"])):
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
    # make JSON-serialisable
    for k in ("frameworks", "test_frameworks", "observability", "paid_services"):
        d[k] = sorted(d[k])
    d["database"]["tools"] = sorted(d["database"]["tools"])
    d["languages"] = dict(d["languages"].most_common())
    return d


def to_markdown(d):
    def lst(xs, n=15):
        xs = list(xs)
        return ", ".join(f"`{x}`" for x in xs[:n]) + (f" … (+{len(xs) - n} more)" if len(xs) > n else "") if xs else "none found"
    o = ["# Project Discovery", "", f"Root: `{d['root']}`  |  Git repo: {'yes' if d['has_git'] else 'no'}", "",
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    ap.add_argument("--out", help="directory to write discovery.json and discovery.md")
    a = ap.parse_args()
    if not Path(a.project_dir).is_dir():
        print(f"Not a directory: {a.project_dir}", file=sys.stderr)
        return 2
    d = discover(a.project_dir)
    md = to_markdown(d)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "discovery.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "discovery.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
