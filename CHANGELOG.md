# Changelog

Versions follow [Semantic Versioning](https://semver.org). Until 1.0.0, minor versions may change the review file formats; each such change is listed under "Breaking".

## [0.4.0] - 2026-11-20

### Added
- **Capability matrix.** `capabilities` (also written by `discover --out`) classifies each of the 23 areas as applicable, not applicable or not assessed for this project, with the reason, and each run-based check as available, missing a tool, without a command, or unsupported. The skill applies only what the project needs.
- **Scanner results as evidence.** `scan import` normalises SARIF, npm audit, osv-scanner, pip-audit, trivy and gitleaks output into candidate findings for triage.
- **Visual regression.** `visual compare` / `visual approve` compare real PNG screenshots with user-approved baselines, using a dependency-free PNG decoder.
- **AI engineering workflow**, used only when the project uses AI: prompt injection, tool permissions, data sent to providers, evaluation, cost, and model, provider and dataset selection behind a privacy gate.
- **Deployment advisor**: project-specific comparison of hosting approaches; discovery now derives a deployment profile.
- Guidance for diagrams with evidence labels, real screenshots, and vetting skills, plugins and MCP servers before recommending them.
- Intake questions for AI data sharing, AI quality bar, deployment goals and how to run the interface.
- Rules for researching current documentation before recommending, and for updating the target project's own documentation after approved changes.
- `docs/EVALUATION.md`: the first with-versus-without comparison of the skill, and what it does not show.

### Changed
- Captured searches and listings (`grep`, `cat`, `ls`, `git log` and similar) now count as Observed, not Verified. An area whose only evidence is searches is capped as "nothing was run". Existing reviews may score lower.
- `evidence run --also` lets several areas cite one record.
- `state` reports areas being worked on as `in_progress` (was `interrupted`).

### Fixed
- Discovery offered `npm audit` without a lockfile and did not recognise Node's built-in test runner.
- The delivery package listed out-of-scope reports as missing and omitted `findings.json`.
- A search pattern containing words like "delete from" could be refused as destructive.
- `graph` now says when there is nothing to draw.

## [0.3.0] - 2026-11-20

### Added
- **Edit and command guard.** As a plugin, a PreToolUse hook now enforces the review's rules on Claude's own tool calls: project files are read-only during assessment; during remediation an edit needs a recorded approval covering that file and a non-default branch; destructive, publishing and deploying commands are blocked unless that exact command was approved. Closes the gap where "read-only" was only an instruction.
- `approve`, `state phase`, `state close`: recorded approvals and an explicit remediation phase.
- **Verified improvement loop.** `bench run` / `bench compare` measure a command before and after a change and report improved, regressed, no significant change or not comparable, judging the difference against run-to-run noise.
- **Diagrams from code.** `graph` writes a module dependency graph (with circular dependencies) and a database ERD from SQL and Prisma files, as Mermaid, labelled with their evidence level.
- **Final Engineering Delivery package.** `package` organises what a review produced and lists what is missing instead of filling gaps.
- Discovery lists optional analysis tools (semgrep, osv-scanner, trivy, gitleaks, k6, lighthouse and others) with whether they are installed, and flags text in the repository that tries to instruct an AI reviewer.
- Recommendation contract (authoritative source, applicability, options, trade-offs, verification) and an `independent-reviewer` subagent.

### Fixed
- `score` crashed on Windows consoles that cannot encode the scorecard's characters, and reported the crash as an invalid review.

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
