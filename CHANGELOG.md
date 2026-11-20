# Changelog

Versions follow [Semantic Versioning](https://semver.org). Until 1.0.0, minor versions may change the review file formats; each such change is listed under "Breaking".

## [0.2.0] - 2026-11-20

### Fixed
- **False GO.** `scorecard.py` scored only the areas present in `findings.json`, so a file holding one perfect area returned GO for the whole project. The decision engine now requires every area of the review mode and is fail-closed: an incomplete or malformed review is INVALID and always NO-GO.
- Evidence levels were whatever the findings file declared. They are now derived from evidence records; a "Verified" claim needs the captured output of a command that ran, with a matching hash.

### Added
- Project intake: questions tailored to what discovery found, `intake.json`, and a risk profile (standard / sensitive / regulated) that sets the release gates and cannot be lowered below what the answers imply.
- Evidence engine: `evidence run` captures command output with timestamp, exit code, tool version, commit and SHA-256, and masks secrets; `evidence note` records observations and inferences.
- Command policy: commands that delete, publish, deploy, migrate or change remotes are refused unless the user approved them.
- Stack adapters (Node/TypeScript, Python, Java/Kotlin, Go, PHP, Rust, Dart/Flutter, .NET, Ruby, Terraform), monorepo, AI-app, mobile, microservice and infrastructure-only detection, and explicit reporting of unsupported stacks.
- Resumable review state with wave ordering.
- Scorecard exports: Markdown, JSON, HTML.
- Strict rules for findings: `fixed` needs a re-check that ran, `accepted` needs a documented approval, an accepted Critical still blocks GO, duplicate IDs and out-of-range scores are rejected.
- 76 automated tests, seven fixture projects, GitHub Actions CI on Linux, macOS and Windows, a Docker runner, a Claude Code plugin manifest and a read-only `expert-reviewer` subagent.

### Breaking
- The skill moved from `enterprise-experts/` to `skills/enterprise-experts/`.
- `findings.json` is now schema version 2 (see `skills/enterprise-experts/references/evidence-and-scoring.md`). Version 1 files are rejected.
- `scorecard.py <findings.json>` still runs but scores the whole review folder and needs `intake.json` and `evidence-log.json`.

## [0.1.0] - 2026-11-20

- First draft: orchestrator workflow, 23 expert references, templates, `discover_project.py`, `scorecard.py`.
