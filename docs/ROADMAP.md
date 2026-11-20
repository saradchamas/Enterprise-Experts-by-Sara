# Roadmap to v1.0

Status as of v0.4.0. Enterprise Experts is one reusable skill with a local engine; it is not a hosted product, and no dashboard, server or database is planned. "Tested" means an automated test or a recorded run exists; anything else is stated as not done.

## What v0.4.0 covers

| Area of the plan | Status | Evidence / what is missing |
|---|---|---|
| Strict scoring, fail-closed decision, risk gates | **Done, tested** | `tests/test_scoring.py` (38 tests) |
| Evidence engine (IDs, commands, timestamps, versions, commit, hashes) | **Done, tested** | Hashes are not signed: integrity detects edits but is not tamper-proof |
| Policy engine: no unauthorised modification | **Done for tool calls, tested with simulated calls** | `tests/test_improvement.py`. Not yet run in a live Claude Code session; cannot see writes made inside a shell command; absent in a standalone-skill install |
| Approval records and remediation phase | **Done, tested** | An approval record is an audit entry, not proof of who typed it |
| Project intake and questions | **Done, tested** | — |
| Capability matrix (applicable / not applicable / not assessed; checks available / tool missing / unsupported) | **Done, tested** on all 7 fixtures | Decided from the repository; items marked *confirm* depend on the user's answer |
| Stack adapters | **Done, tested** on 7 fixtures (Node/TS, Python, Go, monorepo, AI app, Terraform-only, unsupported). Adapters also exist for Java, PHP, Rust, Dart/Flutter, .NET, Ruby | No fixtures yet for those six; no microservice fixture |
| Orchestration: waves, state, resume | **Done, tested** | Token and time budgets are not enforced in code |
| Agents | Orchestrator (the skill), `expert-reviewer`, `independent-reviewer` | Standards research, implementation and verification are steps the orchestrator performs, not separate agents. No typed-output validation of subagent results beyond `findings.json` validation |
| Recommendation contract and standards research | **Specified** in `references/improvement-loop.md` | Instruction-level: nothing verifies that a cited URL exists or says what is claimed |
| Verified improvement loop | **Benchmark measurement and verdicts done, tested** | The loop around them (branch, PR, review) is instruction-level |
| Diagrams from evidence | **Dependency graph and ERD done, tested** | C4, API/service calls, infrastructure topology, trust boundaries, trend charts: drawn by the experts, not generated |
| Tool integration | **Detection + import, tested**: 15 optional tools listed with availability; SARIF, npm audit, osv-scanner, pip-audit, trivy and gitleaks output normalised into candidate findings | npm audit and pip-audit parsers are tested on real output; the other four on hand-built samples of the documented formats |
| AI engineering workflow, model/provider/dataset selection | **Specified** in `references/ai-engineering.md`; activates only when AI is found; intake asks before any data goes to a provider | Instruction-level and unevaluated. The privacy gate is not enforced in code |
| Deployment advisor | **Specified** in `references/deployment-advisor.md`; discovery derives a deployment profile (tested) | Recommendation quality unevaluated; depends on browsing for current prices |
| Real screenshots and visual regression | **Comparison done, tested** on real browser screenshots; capture is by Playwright, run by the expert | Capture workflow not evaluated on a real app; 8-bit non-interlaced PNG only; no mobile capture |
| Integration discovery and vetting | **Specified** (trust checklist) | Instruction-level |
| Prompt-injection protection | **Pattern scan + rule in the skill, tested** | Pattern-based; not evaluated against adversarial repositories with a live model |
| Final delivery package | **Done, tested**; respects the review's scope | HTML scorecard only; no PDF or Excel |
| Docker runner | **Done, tested** on Linux and in CI | Deterministic engine only. No separate sandbox for running untrusted project code. macOS/Windows not tested |
| CI | **Passing** on Linux, macOS, Windows × Python 3.10/3.13, lint, Docker smoke test | No dependency/image vulnerability scan, no SBOM |
| Continuous engineering (PR gates, schedules, drift, trends) | **Not built** | `score` and `bench compare` exit codes make a CI gate possible; no workflow templates, history or trend tracking yet |
| Supply chain (SBOM, provenance, signed releases, skill registry) | **Not built** | Actions are pinned by commit; Dependabot is configured |
| Releases, updates, rollback | Changelog and version-consistency test | No tag yet; upgrade and rollback not tested between two published versions |
| Skill evaluation (with vs without the skill) | **Started**: one comparison on one small sample project; see `docs/EVALUATION.md` | No real project, no repeat runs, eight of 23 experts exercised once. Still the most important gap |

## v1.0 release checklist

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Incomplete evidence never returns an unjustified GO | Met | `tests/test_scoring.py` |
| 2 | All 23 roles validated | Partly | Structure is checked; eight areas ran once in an evaluation; the rest are unevaluated |
| 3 | At least five project types tested | Met for discovery | 7 fixtures; no full reviews of real projects yet |
| 4 | Docker: fresh build and isolated audit pass | Met on Linux | `tools/docker_smoke.sh`, CI |
| 5 | Required PR checks pass | Met | CI green on all eight jobs for the Windows fix |
| 6 | No exposed secrets or unapproved mutations | Mostly | Masking, command policy and edit guard tested; guard not yet run live |
| 7 | Reports: evidence links validated | Met for scorecard and package | Engine validates every reference |
| 8 | Every documented command verified | Met for Linux | Exceptions are marked in the docs |
| 9 | Upgrade and rollback tested | Not met | Needs two published versions |
| 10 | Fresh installation on supported systems | Partly | Plugin install tested from a local clone on Linux |
| 11 | Interrupted runs resume or fail safely | Met | State and end-to-end tests |
| 12 | Versioned artifact and release notes | Not met | No tag yet |

Six met, four partly, two not.

## Known limitations

- **The AI workflow is barely evaluated.** One run on a small sample project found the same serious defects with and without the skill; the skill added traceability at about twice the token cost (`docs/EVALUATION.md`). Its value on real, larger projects is unmeasured.
- **Compatibility is demonstrated only for what was tested**: discovery and the capability matrix on seven sample project types. "Any project" is the design goal, not a tested claim.
- **The engine validates form, not truth.** It proves a command ran and what it printed. It cannot tell whether that command was a meaningful test, whether a score of 85 is fair, or whether a cited source says what the report claims. A person still has to read the evidence.
- **The guard is not a sandbox.** It checks tool calls by pattern. Run untrusted projects' code in a container or VM of your own.
- **Benchmarks on a development machine show direction, not production numbers.**
- **Secret and injection detection are pattern-based**: they miss unusual cases and raise false positives.
- **Unsupported stacks** are reviewed by reading only.
- **No licence** has been chosen.

## Suggested order

1. Evaluate on a real project, and on the healthy sample (does it reach GO when it should?), with repeat runs. Fix what that shows.
2. Run the guard in a live session; add a sandboxed runner for project code.
3. Check the SARIF, osv-scanner, trivy and gitleaks importers against output captured from those tools.
4. Tag a release with checksums and an SBOM; then a second release to test upgrade and rollback.
5. CI templates for pull-request gates and scheduled re-checks, with history.
6. PDF and spreadsheet exports of the report.
