# Roadmap to v1.0

Status as of v0.2.0. "Tested" means an automated test or a recorded manual run exists; anything else is stated as not done.

## Gap analysis against the v1.0 plan

| Priority | Component | Status in v0.2.0 | Still missing |
|---|---|---|---|
| P0 | Assessment engine (strict validation, deterministic decision) | **Done, tested** (38 regression tests) | JSON Schema files for external tools |
| P0 | Evidence engine (IDs, commands, timestamps, tool versions, commit, artifacts) | **Done, tested** | Signed hashes; today integrity detects edits but is not tamper-proof |
| P0 | Security boundaries (read-only default, approvals, masking) | **Partly.** Command policy and masking are tested. "Do not edit the project during assessment" is an instruction to Claude, not an enforced control | Plugin hooks that block edits outside the remediation phase |
| P0 | Automated tests | **Done:** 76 tests (unit, regression, end-to-end, interrupted runs, adversarial inputs) | Tests of the AI workflow itself (see below) |
| P0 | Project adapters | **Done, tested** on 7 fixtures: Node/TS, Python, Go, monorepo, AI app, Terraform-only, unsupported stack. Java, PHP, Rust, Dart/Flutter, .NET, Ruby adapters exist | Fixtures for Java, PHP, Rust, Flutter, .NET, Ruby; microservice fixture |
| P0 | Docker runtime | **Done, tested on Linux** for the deterministic engine | macOS and Windows/WSL2 runs; image scanning; digest pinning. It does not run the AI workflow or project toolchains |
| P0 | CI quality gates | **Configured:** tests on Linux/macOS/Windows × Python 3.10/3.13, lint, Docker smoke test; actions pinned by commit; read-only token | First green run on GitHub; dependency and image vulnerability scan; SBOM |
| P1 | 23 expert specifications | **Specified;** a test checks each has mission, deliverable and checks | Evaluation of the depth and quality of each expert's output on real projects |
| P1 | Workflow orchestrator | **Partly:** wave ordering, state, resume are implemented and tested; a read-only `expert-reviewer` subagent exists | Token budgets and retry policy enforced in code; contradiction detection is by instruction only |
| P1 | Remediation engine | **Instruction-level only** (plan, approval, branch, re-check). The engine enforces that `fixed` needs a re-check | Tooling for worktrees, diff review and rollback |
| P1 | Skill/plugin manager | Not built. Companion skills are used if present and never installed automatically | Detection and version checks of companions |
| P1 | Documentation generator | Instruction-level (expert 17) | — |
| P1 | Release management | Changelog, version consistency test | First tagged release; release workflow |
| P1 | Update manager | Manual, documented | Tested upgrade and rollback between two published versions |
| P1 | Cross-platform support | Linux tested; macOS/Windows in CI matrix | Confirmed CI results |
| P1 | Cost and resource controls | Command timeouts; intake asks for limits | Enforced token budgets |
| P2 | Dashboard, scheduled reviews, integrations | Not built | — |
| P2 | Exports | Markdown, JSON, HTML for the scorecard | PDF, Excel; HTML for the full report |

## v1.0 release checklist

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Scorecard integrity: incomplete evidence never returns an unjustified GO | Met | `tests/test_scoring.py` |
| 2 | All 23 roles validated | Partly | Specifications are checked for structure; output quality is not evaluated |
| 3 | Cross-project support: at least five distinct project types tested | Met for discovery | 7 fixtures in `tests/test_engine.py`; full reviews on real projects not yet done |
| 4 | Docker: fresh build and isolated audit command pass | Met on Linux | `tools/docker_smoke.sh` |
| 5 | CI: required PR checks pass | Not yet shown | Workflow exists; needs its first run |
| 6 | Security: no exposed secrets or unapproved mutations | Partly | Masking and command policy tested; edit prevention not enforced |
| 7 | Reports: evidence links and artifacts validated | Met for the scorecard | Engine validates every reference |
| 8 | Documentation: every documented command verified | Met for Linux | Commands in `docs/` were run; exceptions are marked in place |
| 9 | Updates: upgrade and rollback tested | Not met | No second published version yet |
| 10 | Installation: fresh install on supported systems | Partly | Plugin install/uninstall tested from a local clone on Linux |
| 11 | Recovery: interrupted runs resume or fail safely | Met | `test_interrupted_review_fails_safe`, state tests |
| 12 | Release: versioned artifact and release notes | Not met | No tag yet |

Five of twelve are met, four partly, three not. This is not a v1.0.

## Known limitations

- **The AI workflow is unevaluated.** The engine is tested; how well Claude plays the 23 experts on a real project has not been measured. The next step is with-skill versus without-skill runs on the fixtures and on one real project, reviewed by a person.
- **The engine validates form, not truth.** It proves a command ran and what it printed. It cannot tell whether that command was a meaningful test of the claim, or whether a score of 85 is fair. A reviewer still has to read the evidence.
- **Evidence is not tamper-proof** (see `docs/SECURITY.md`).
- **Secret detection is pattern-based** and will miss unusual formats; it also produces false positives that need triage.
- **Unsupported stacks** (for example Elixir, Swift, C/C++) are reviewed by reading only; their run-based checks are Not assessed.
- **No licence** has been chosen.

## Suggested order

1. Merge this pull request once CI is green; tag v0.2.0.
2. Evaluate the skill on the fixtures and one real project; fix what the evaluation shows.
3. Plugin hooks that block edits during assessment; remediation tooling.
4. Remaining fixtures; image and dependency scanning; SBOM.
5. A second release, to test upgrade and rollback.
6. P2 items only after the CLI workflow is stable.
