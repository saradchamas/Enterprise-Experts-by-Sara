# Developer Guide

## Layout

```
.claude-plugin/            plugin.json, marketplace.json
agents/                    expert-reviewer, independent-reviewer (both read-only)
hooks/                     hooks.json + guard.py (PreToolUse edit/command guard)
skills/enterprise-experts/
  SKILL.md                 the orchestrator's workflow
  references/              23 expert specifications, intake, scoring, companion skills
  assets/                  deliverable and final-report templates
  scripts/
    enterprise_experts.py  CLI entry point
    discover_project.py, scorecard.py   v0.1-compatible entry points
    ee/                    the engine
tests/                     unit, regression and end-to-end tests; fixtures/
docker/Dockerfile, compose.yaml, tools/docker_smoke.sh
```

### Why the engine lives inside the skill

A skill must work when only its own folder is installed. So the engine sits in `skills/enterprise-experts/scripts/ee/` and uses only the standard library, instead of being a separate top-level package that a standalone install would not have.

### Engine modules

| Module | Responsibility |
|---|---|
| `areas.py` | The 23 areas, waves, modes, risk profiles and gates. The single place to change a gate. |
| `discovery.py` | Read-only inventory and secret scan. |
| `adapters.py` | Per-stack check commands, prerequisites and limitations. |
| `intake.py` | Question bank, intake validation, risk-profile derivation. |
| `evidence.py` | Recording commands and notes; deriving evidence levels. |
| `policy.py` | Which commands need approval. |
| `secrets.py` | Secret patterns and masking. |
| `scoring.py` | Validation and the decision. |
| `state.py` | Resumable review state and wave planning. |
| `report.py` | Markdown, JSON and HTML scorecards. |
| `guard.py` | Decides whether an edit or command is allowed while a review is open; called by the plugin hook. |
| `bench.py` | Repeated measurement and before/after verdicts. |
| `graphs.py` | Dependency graph and ERD from code, as Mermaid. |
| `package.py` | The Final Engineering Delivery folder. |
| `tools.py` | Optional analysis tools and their availability. |
| `capabilities.py` | Capability matrix: applicable areas, workflows and run-based checks. |
| `scanners.py` | Scanner output (SARIF and tool JSON) to candidate findings. |
| `visual.py` | PNG decoding and screenshot comparison against approved baselines. |
| `cli.py` | Argument parsing only. |

Data flow: `discover` → `questions`/`intake.json` → `evidence-log.json` + `findings.json` → `validate` → `score` → scorecards.

## Running the checks

```bash
python -m unittest discover -s tests -t .     # all tests; no dependencies
ruff check .                                  # lint (pip install ruff)
tools/docker_smoke.sh                         # needs Docker
claude plugin validate .                      # needs the Claude Code CLI
```

`pytest` also runs the suite if you prefer it.

## Tests

| File | Covers |
|---|---|
| `tests/test_scoring.py` | Decision regressions: every way an incomplete, malformed or unproven review could wrongly become GO. |
| `tests/test_engine.py` | Evidence capture, masking, command policy, intake, state, adapters on the fixtures. |
| `tests/test_improvement.py` | Guard decisions and the hook script, approvals, benchmark verdicts, diagrams, packaging, prompt-injection scan. |
| `tests/test_universal.py` | Capability matrix on every fixture, scanner importers (real npm audit and pip-audit output), PNG decoder and visual regression (real browser screenshots), deployment profile, AI and deployment questions. |
| `tests/test_cli_e2e.py` | Whole reviews through the real CLI; interrupted runs; skill package consistency (all 23 experts specified, referenced files exist, versions agree, standard library only). |

Fixtures in `tests/fixtures/`: `healthy-node`, `flawed-node`, `monorepo`, `python-fastapi` (AI app), `go-service`, `infra-only`, `unsupported-elixir`.

Any change to a decision rule needs a test in `test_scoring.py` that fails without the change.

## Adding a stack adapter

1. In `adapters.py`, write a function returning `_simple(adapter_id, label, tools, commands, limitations)` and register its manifest in `MANIFEST_ADAPTERS`. Commands are argument lists, never shell strings.
2. Map its languages in `LANG_ADAPTER`.
3. A check without a command must have a reason in `unavailable`; the test `test_every_stack_declares_all_checks_and_reasons` enforces this.
4. Add a fixture and assertions in `DiscoveryAdapters`.

## Adding an intake question

Add a `q(...)` entry to `QUESTIONS` in `intake.py`. Use `when="<flag>"` to ask it only when discovery sets that flag. If the answer should change the risk profile, change `derive_risk_profile` and add a test. Document the effect in `references/intake-questions.md`.

## Changing an expert

Edit its section in the matching `references/experts-*.md`. Each section must keep **Mission**, **Deliverable** and **Checks** (a test checks this for all 23).

## Releasing

1. Update `__version__` in `ee/__init__.py`, `version` in `.claude-plugin/plugin.json`, the image tag in `compose.yaml`, and add a `CHANGELOG.md` entry. A test fails if the first three disagree with the changelog.
2. All CI jobs green on the pull request.
3. Merge, tag `vX.Y.Z`, create the GitHub release with the changelog entry and the packaged `.skill` file.

## Commit conventions

Commits are authored by the repository owner. Do not add tool, model or session attribution lines.
