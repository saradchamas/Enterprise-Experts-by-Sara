# User Guide

## A review, step by step

1. Open the project in Claude and ask for a review ("Run Enterprise Experts on this project").
2. Claude inventories the project, then **asks you questions**. Answer what you know; "I don't know" is a valid answer and is recorded as such. Required questions cover what the project does, its stage, who can reach it, industry, the kinds of data it holds, whether it moves money, the review mode, whether Claude may change code, and where it may run things. Further questions appear only when they apply (backups if there is a database, AI usage if there is an LLM, and so on).
3. Claude tells you the risk profile your answers imply and what it means for the release gates.
4. The experts work in five waves. You are asked for approval before anything risky.
5. You receive a remediation plan. Nothing in your code changes unless you approve it; approved fixes are made on a branch.
6. You receive the Final Project Health Report with the decision.

If a session is interrupted, start a new one in the same project and ask to continue the review: the state file tells Claude where it stopped.

## Review modes

| Mode | Areas | The decision means |
|---|---|---|
| full | all 23 | release readiness |
| quick | 1 Architecture, 2 Security, 5 Reliability, 6 Database, 7 Disaster Recovery, 8 Observability, 9 QA, 10 DevOps | readiness of the core; on sensitive or regulated projects it is at best CONDITIONAL GO because more areas are core |
| focused | the areas you name | the state of those areas only; never a release GO unless the scope includes every core area |

## Files in the review folder

| File | Written by | Purpose |
|---|---|---|
| `discovery.json`, `discovery.md` | engine | what the project is made of, and which checks can run |
| `intake.json` | Claude, from your answers | scope, permissions, risk profile |
| `review-state.json` | engine | progress, for resuming |
| `evidence-log.json`, `evidence/` | engine | every evidence record and the captured output |
| `01-…` to `23-….md` | Claude | each expert's deliverable |
| `findings.json` | Claude | checks, findings and scores |
| `scorecard.md`, `.json`, `.html` | engine | the validated decision |
| `FINAL-PROJECT-HEALTH-REPORT.md` | Claude | the report for people |

## CLI reference

`EE` stands for `python skills/enterprise-experts/scripts/enterprise_experts.py`.

| Command | Purpose |
|---|---|
| `EE discover <project> [--out <review>]` | Inventory. Read-only. |
| `EE capabilities --review <review> [--json]` | Which areas, workflows and run-based checks apply to this project. |
| `EE questions --review <review> [--mode full\|quick\|focused]` | Intake questions for this project, as JSON. |
| `EE intake --review <review>` | Validate `intake.json`; print the risk profile. |
| `EE state init --review <review> --mode <mode> [--scope N ...]` | Start tracking a review. |
| `EE state set --review <review> --area N --status pending\|in_progress\|done\|failed\|skipped` | Update one area. |
| `EE state show --review <review>` | What is ready, in progress, blocked, done. |
| `EE evidence run --review <review> --area N --title "..." [--cwd DIR] [--timeout S] [--approved] -- <command>` | Run a check and capture it. |
| `EE evidence note --review <review> --area N --kind observation\|inference --title "..." [--location path:line] [--project DIR] [--detail "..."]` | Record something read or reasoned. |
| `EE evidence list --review <review>` | List records with their derived level; broken records are flagged. |
| `EE approve --review <review> --by NAME [--findings ID ...] --paths GLOB ...` | Record that the user approved a fix touching these files. |
| `EE approve --review <review> --by NAME --exact-command "..."` | Record that the user approved one risky command. |
| `EE state phase --review <review> --phase remediation\|assessment` | Open or leave the remediation phase (needs an approval). |
| `EE state close --review <review>` | Mark the review finished; the edit guard stops applying. |
| `EE bench run --review <review> --name N --label baseline\|candidate [--runs 5] [--warmup 1] [--metric-regex RX] -- <command>` | Measure a command several times. |
| `EE bench compare --review <review> --name N [--min-improvement 10] [--max-regression 5] [--higher-is-better]` | Judge before against after. |
| `EE scan import --review <review> --evidence E-0xx` (or `--file <path in review folder>`) | Normalise scanner output into candidate findings. |
| `EE visual compare --review <review> --name N --image <png> [--threshold 0.1]` | Compare a real screenshot with its approved baseline. |
| `EE visual approve --review <review> --name N --by NAME` | Make the current capture the approved baseline. |
| `EE graph <project> --out <dir> [--depth 2]` | Dependency graph and database ERD (Mermaid). |
| `EE package --review <review>` | Build `FINAL-ENGINEERING-DELIVERY/`. |
| `EE validate --review <review>` | Validate only. |
| `EE score --review <review> [--json] [--no-write]` | Validate, decide, write the scorecards. |

Exit codes of `score`: `0` GO, `10` CONDITIONAL GO, `20` NO-GO, `2` invalid review. `evidence run` exits `3` when it refuses a risky command. `bench compare` exits `0` improved, `10` no significant change, `20` regressed, `2` not comparable. These make the engine usable as a CI gate.

## Approvals and the edit guard (plugin install)

While a review is open in a project, the plugin checks each of Claude's edits and shell commands:

| Phase | Editing project files | Risky commands (delete, push, deploy, migrate...) |
|---|---|---|
| assessment | blocked; only the review folder is writable | blocked unless that exact command was approved |
| remediation | allowed only for files covered by a recorded approval, and never on `main`/`master` | blocked, except committing on the fix branch |
| closed | not checked | not checked |

When you say yes to a fix, Claude records it (`approve`), which is what unlocks those files. If a review was abandoned and the guard is in your way, run `EE state close --review <review>`.

The standalone skill (without the plugin) has no hook; there the same rules are instructions only.

## Measuring an improvement

```bash
EE bench run --review review --name orders-list --label baseline -- python scripts/bench_orders.py
# ... make the approved change on a branch ...
EE bench run --review review --name orders-list --label candidate -- python scripts/bench_orders.py
EE bench compare --review review --name orders-list
```

The verdict is `improved` only when the median changed by at least the threshold and by more than twice the run-to-run standard deviation. Different commands, metrics, machines or failed runs are refused as not comparable.

The older entry points `discover_project.py` and `scorecard.py` still work and call the same engine.

## What the skill applies to your project

After discovery the engine writes `capability-matrix.md`. Each of the 23 areas is marked applicable, not applicable or not assessed, with the reason; three extra workflows switch on only when the project calls for them:

| Workflow | Switches on when | What you get |
|---|---|---|
| AI engineering | the project uses an LLM or other AI library | prompt-injection, tool-permission and data-exposure review; evaluation and cost; model or provider comparison if a finding calls for it |
| Deployment advisor | the project is deployable and hosting is unsettled, a problem, or you ask | a comparison of fitting options for this project and the simplest one that meets your needs |
| Visual documentation | the project has an interface that can be run | real screenshots and visual regression against baselines you approve |

Nothing is sent to an outside AI provider, installed, provisioned or deployed without your explicit approval.

## Scanner results

When a supported scanner is installed, its machine-readable output is captured as evidence and normalised:

```bash
EE evidence run --review review --area 2 --title "npm audit" --cwd . -- npm audit --json
EE scan import --review review --evidence E-007
```

Supported: SARIF (semgrep, CodeQL, trivy and others), `npm audit --json`, osv-scanner JSON, pip-audit JSON, trivy JSON, gitleaks JSON. The output is a list of candidates; each is confirmed against the project before it becomes a finding.

## Screenshots

```bash
npx playwright screenshot --viewport-size=1440,900 http://localhost:3000 shot.png
EE visual compare --review review --name home-desktop --image shot.png     # exit 10: no baseline yet
EE visual approve --review review --name home-desktop --by Sara
EE visual compare --review review --name home-desktop --image shot.png     # exit 0 match, 20 changed
```

Baselines live in `enterprise-review/visual-baselines/` so later reviews compare against them.

## Reading the scorecard

- **Expert score** is what the expert proposed; **Final score** is after caps.
- **Evidence basis** says whether anything was actually run for that area. "Observed only" means the area was judged by reading; it is capped at 75.
- **Blockers** are the reasons for NO-GO. **Conditions** are what stands between CONDITIONAL GO and GO.
- "INVALID REVIEW" lists what is missing or inconsistent. It is not a judgment of your project; it means the review itself cannot support a decision yet.

The full rules are in the [scoring specification](../skills/enterprise-experts/references/evidence-and-scoring.md).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `INVALID REVIEW`: required areas missing | The review mode needs areas that are not in `findings.json`. Finish them, or mark them `not_assessed` with a reason. |
| `intake.json is missing` | The questions were not answered. Ask Claude to run the intake. |
| `risk_profile ... is lower than the intake answers require` | The profile was set lower than the answers imply. Use the profile `EE intake` prints. |
| `artifact was modified after capture` | An evidence file was edited. Re-run that check. |
| `evidence ... was recorded for area X, not area Y` | Evidence was cited by the wrong expert. Record it for the right area. |
| `Refused: this command ...` | The command could change something. Approve it explicitly, or choose a read-only check. |
| A check shows `[command not found]` | The tool is not installed here. Install it, or record the check as `not_assessed`. |
| Docker: `Permission denied` writing reports | The reports folder is not writable by the container user. See [DOCKER.md](DOCKER.md). |
