# Changelog

Versions follow [Semantic Versioning](https://semver.org). Until 1.0.0, minor versions may change the review file formats; each such change is listed under "Breaking".

## [0.6.0] - 2026-11-20

### Added
- **Research and proposals.** `research add|propose|decide|check|log`: sources are pages that were read, with URL and date, and are also written to the evidence log. A proposal (adopt, replace, upgrade, remove or configure a technology, model, MCP server, tool, dataset or practice) is refused unless it names a finding or a stated goal, cites recorded sources and weighs an alternative. Models, MCP servers, tools and datasets need an official source. Sources for fast-moving facts count for 90 days. Approval is recorded with a name and the files the change may touch; `verified` needs a check that passed after the approval. `research-log.md` goes into the delivery package.
- Intake question `innovation_scan`: whether to look for newer technologies at all, and whether project details may appear in web searches.
- `references/research-and-innovation.md`.
- `docs/EVALUATION.md` round 4: the engine on five real open-source projects.
- `research.json` is protected by the edit guard.

### Fixed (found on real projects)
- `graph` did not finish on a large project (Django, 7,104 files): the cycle search was exponential. It is now linear and reports one shortest example per group of modules.
- A dependency graph too large to draw is drawn at a coarser level, with the full edge list in `dependency-edges.csv`.
- The graph ignored relative imports and `src/` layouts, so a typical Python library had no edges.
- Manifests, schemas, migrations and HTML under examples, docs and tests folders made libraries look like monorepos with a UI and a database.
- The `exports` field of `package.json` was read as the Expo framework (and so as a mobile app); `vite` matched `vitest`.
- `bun.lock` was not recognised as a lockfile.
- Go tests, `unittest` and the Django test runner were not detected; `unittest.mock` alone no longer counts as unittest.
- Example and test schemas appeared in the ERD; test-data folders were scanned by `graph`.

### Changed
- `graph` output: `cycles` holds one example per group, with the group sizes in `cycle_group_sizes`.

## [0.5.1] - 2026-11-20

### Added
- MIT licence (`LICENSE`, also inside the skill folder so a standalone install carries it).

### Fixed
- The live guard test reported PASS when Claude had not run at all (for example when not logged in), because an untouched file looked like a blocked edit. It is now `tools/live_guard_test.py`, runs on Windows as well, and first does a control run without a review: if Claude cannot edit there, the result is INCONCLUSIVE.

## [0.5.0] - 2026-11-20

Driven by five evaluation runs of v0.4.0, including a full 23-expert review of this repository (`docs/EVALUATION.md`).

### Fixed (decision integrity)
- A check marked `pass` was accepted when its only evidence was a command that had failed. A pass now needs a command that exited 0, or an observation.
- `fixed` could be verified by the same run that demonstrated the defect. The re-check must now be a new, successful run recorded after the evidence that found the problem.
- Parallel `evidence run` calls silently lost records. The evidence log is now locked while written; tested with threads and separate processes.
- Malformed review files crashed with a traceback. They now make the review INVALID (exit 2).
- A file a command was meant to produce (a screenshot) was not part of the evidence. `evidence run --output` binds it to the record; a missing or altered file makes the record unusable.
- Re-running a benchmark overwrote evidence already cited. Each run now keeps its own file.
- An area with no passing check could score 100. Caps: no check passed 40, more failed than passed 70. A "not applicable" reason must say why, and overriding the capability matrix is shown on the scorecard.

### Fixed (guard and policy)
- The guard treated a shell line as read-only when its first word was `ls`, `cat` or `grep`, so `ls && rm -rf src` was allowed. Each chained command is now checked, and writing files by redirection is caught.
- The policy missed `git -C . push`, `find -delete`, plain `rm`, `gh release create`, `curl --request POST`, `xargs rm`, `sed -i`, `mv` and overwriting `cp`.
- The engine's own files (`review-state.json`, `evidence-log.json`, scorecards, captured output) can no longer be edited by hand through the hook.
- Approvals: paths that leave the project and unknown finding IDs are refused.

### Fixed (fit to the project)
- Discovery treated sample projects under `tests/fixtures` as the project. Such folders are left out, and `discover --exclude` leaves out more.
- A dependency declared in a manifest but never imported no longer makes the project an API, database or AI project.
- A Dockerfile alone no longer makes a library a service.
- `pip-audit` was suggested in a form that audits the reviewer's machine; it is now offered only with a requirements file. Audit commands produce JSON so `scan import` can read them. Python projects without pytest get `unittest`.
- Checks no longer leave caches (`__pycache__`) in the project.
- Secret masking in captured output covers more shapes (bearer tokens, URL parameters, JSON and YAML values, command-line flags, private key bodies).

### Added
- `export`: `report.xlsx` and `report.pdf`, written with the standard library.
- `trend`: compare two reviews of the same project. `gate`: model-free checks for CI and schedules, with a workflow template.
- Release workflow (on a version tag): tests, reproducible skill archive, SBOM, checksums, build provenance attestation, GitHub release. `tools/build_release.py` builds and verifies the artifacts; CI runs it.
- `tools/upgrade_rollback_test.sh`: installs an older version of the plugin, upgrades, rolls back. Passed for 0.3.0 → 0.4.0 → 0.3.0.
- `references/project-types.md`: how each expert adapts to a tool or library, a mobile app, infrastructure-only, a data pipeline, a prototype; rules for reviewer-written check scripts.
- Finding status `pending_decision`; benchmark thresholds agreed with the baseline and not changeable afterwards; `--min-abs-change`; `--workload` hashing; `bench --also`; `evidence share`; `evidence list --json`; web sources recorded as observations with URL and date.
- Visual comparisons are evidence records and produce a difference image.
- The scorecard explains results whose label could mislead; questions are scoped to the review mode; a snapshot of the scorecard is kept when remediation opens.

### Changed
- Evidence records include the branch and whether there were uncommitted changes.
- The delivery package keeps screenshots beside the expert reports, includes probes and research notes, and exits 2 for an invalid review.

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
