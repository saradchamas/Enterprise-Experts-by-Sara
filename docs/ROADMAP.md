# Roadmap to v1.0

Status as of v0.6.0. Enterprise Experts is one reusable skill with a local engine; it is not a hosted product, and no dashboard, server or database is planned. "Tested" means an automated test or a recorded run exists; anything else is stated as not done.

## What v0.5.0 covers

| Area of the plan | Status | Evidence / what is missing |
|---|---|---|
| Strict scoring, fail-closed decision, risk gates | **Done, tested**; hardened in 0.5.0 after a self-review found a false-pass route | `tests/test_scoring.py`, `tests/test_universal.py` |
| Evidence engine (IDs, commands, timestamps, versions, commit, branch, hashes, produced files, parallel-safe) | **Done, tested** | Hashes are not signed: integrity detects edits but is not tamper-proof. A reviewer-written probe counts as a run whatever it tests |
| Policy engine: no unauthorised modification | **Done for tool calls, tested with simulated calls**; chained commands and redirection are checked | Not yet run in a live Claude Code session (`python tools/live_guard_test.py`); pattern matching is not a sandbox; absent in a standalone-skill install |
| Approval records and remediation phase | **Done, tested** | An approval record is an audit entry, not proof of who typed it |
| Project intake and questions | **Done, tested** | — |
| Capability matrix (applicable / not applicable / not assessed; checks available / tool missing / unsupported) | **Done, tested** on all 7 fixtures | Decided from the repository; items marked *confirm* depend on the user's answer |
| Stack adapters | **Done, tested** on 8 sample projects (Node/TS, Python, Go, monorepo, AI app, static site, Terraform-only, unsupported) and on this repository. Adapters also exist for Java, PHP, Rust, Dart/Flutter, .NET, Ruby | No samples yet for those six; no microservice sample |
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
| Final delivery package and exports | **Done, tested**: delivery folder, `report.xlsx`, `report.pdf`, HTML scorecard | The PDF is a plain-text summary in a Latin font; it cannot show Arabic or diagrams |
| Docker runner | **Done, tested** on Linux and in CI | Deterministic engine only. No separate sandbox for running untrusted project code. macOS/Windows not tested |
| CI | **Passing** on Linux, macOS, Windows × Python 3.10/3.13, lint, Docker smoke test | No dependency/image vulnerability scan, no SBOM |
| Continuous engineering | **Partly**: `trend` between reviews and a model-free `gate` with a CI template, both tested; this repository runs the gate on itself in CI | No scheduled expert review (it needs Claude and a person); the template has not been run in another project |
| Supply chain | **Partly**: reproducible skill archive, SBOM and checksums built and verified in CI; release workflow with provenance attestation written; actions pinned by commit; Dependabot | The release workflow has never run (no tag yet). No registry of trusted skills. No vulnerability scan of the Docker image |
| Releases, updates, rollback | **Upgrade and rollback tested** locally for 0.3.0 → 0.4.0 → 0.3.0 | No tagged release yet |
| Research and proposals | **Done, tested** (0.6.0): dated sources, proposals that must solve something, cite sources and weigh an alternative, official-source and 90-day staleness rules, approval, verification by a later passing check, `research-log.md` in the delivery package | The engine does not browse; the quality of the research depends on the session's web access and on the model. Not yet evaluated in a model-driven run |
| Skill evaluation | **Six runs recorded** in `docs/EVALUATION.md`: a with/without comparison, a full 23-expert review of this repository, a healthy project, a fix loop, AI and deployment, screenshots | One run each, by agents of the same model, with supplied answers; one real project (this one); no human judgment of report quality |

## v1.0 release checklist

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Incomplete evidence never returns an unjustified GO | Met | `tests/test_scoring.py` |
| 2 | All 23 roles validated | Partly | All 23 ran once on one real project; 8 sections were judged sufficient, 12 thin, 3 not useful for that kind of project. The guidance written in response is unevaluated |
| 3 | At least five project types tested | Met | Discovery on 8 sample types; full or focused reviews on 5 projects (one real) |
| 4 | Docker: fresh build and isolated audit pass | Met on Linux | `tools/docker_smoke.sh`, CI |
| 5 | Required PR checks pass | Met | CI green on all eight jobs for the Windows fix |
| 6 | No exposed secrets or unapproved mutations | Mostly | Masking, command policy and edit guard tested, and hardened after the self-review; guard not yet run live |
| 7 | Reports: evidence links validated | Met for scorecard and package | Engine validates every reference |
| 8 | Every documented command verified | Met for Linux | Exceptions are marked in the docs |
| 9 | Upgrade and rollback tested | Met locally | `tools/upgrade_rollback_test.sh`, 0.3.0 → 0.4.0 → 0.3.0 |
| 10 | Fresh installation on supported systems | Partly | Plugin install tested from a local clone on Linux |
| 11 | Interrupted runs resume or fail safely | Met | State and end-to-end tests |
| 12 | Versioned artifact and release notes | Ready, not done | Artifact, SBOM and checksums build in CI; pushing the first tag is the owner's decision |

Eight met (one of them locally only), three partly, one waiting for a tag.

## Known limitations

- **Evaluation is thin.** Six model-driven runs, one each, by agents rather than people, on small samples and on this repository. The engine alone has been run on five real open-source projects; the full expert review has not been run on an independent real project. No repeat runs, no human judgment of whether the reports are good.
- **Research and proposals are new.** The engine rules are tested and the workflow was exercised once, by hand, on one real project with two official sources. No model-driven run of the research workflow has been evaluated, and no proposal has yet been approved, built and verified on a real project.
- **On small projects the skill finds what the model finds anyway.** Its measured contribution so far is structure, an evidence trail and a rule-based decision, at 200,000 to 300,000 tokens per run.
- **A clean small project did not reach GO.** Without a Critical or High finding the decision rests on the reviewer's own area scores against a fixed gate. The scorecard now says so; whether the gates are right for small or early projects is an open question for the owner.
- **The engine validates form, not truth.** It proves a command ran and what it printed. It cannot tell whether that command was a meaningful test, whether a score is fair, or whether a cited source says what the report claims.
- **The guard is not a sandbox**, has not run in a live session, and exists only in the plugin install.
- **Expert guidance for non-web projects is new and unevaluated** (`references/project-types.md`).
- **Compatibility is demonstrated only for what was tested.** "Any project" is the design goal, not a tested claim.
- **Secret and injection detection are pattern-based**: they miss unusual cases and raise false positives.
## Suggested order

1. Owner actions: run `python tools/live_guard_test.py` on a machine where Claude Code is logged in; push the first tag when ready.
2. Run the skill on a real project of your own and have a person read the report. Fix what that shows.
3. Decide whether the release gates should vary with project stage or size.
4. Repeat the evaluation runs on the current version, including one with parallel subagents and one with the research workflow switched on.
5. Check the SARIF, osv-scanner, trivy and gitleaks importers against real tool output; samples for the six untested stacks.
