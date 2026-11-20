# Evaluation log

What has actually been measured about the skill, as opposed to its engine's unit tests. Each entry says what was run and what it does and does not show.

## 2026-11-20 — quick review of `tests/fixtures/flawed-node`, with and without the skill

**Setup.** The same model reviewed the same small, deliberately flawed sample project (an Express API of about 20 lines with a SQL injection, no authentication, committed secrets, money stored as float, a test that tests nothing, no lockfile, no CI). One run used the skill at v0.3.0 with pre-supplied intake answers; one run got the same context as a plain request and no skill. Both were told to assess only. One run each, so there is no measure of variance.

| | With the skill | Without the skill |
|---|---|---|
| Verdict | NO-GO, 19/100 (engine) | "Not ready, do not launch" (prose) |
| SQL injection | found (Critical) | found (Critical) |
| No authentication / any order readable | found (Critical) | found (Critical) |
| Committed secrets | found (High) | found (Critical) |
| Payment journey not implemented | found | found |
| One failed query stops the server | found (inferred) | found |
| Money as float | found | found, and demonstrated by running the function |
| Negative quantities accepted | not reported separately | found, demonstrated |
| Test tests nothing | found | found |
| No lockfile, no CI | found | found |
| No backups / recovery plan | found as its own area, with RTO/RPO gap | mentioned in one line |
| No logging, metrics, alerting | found as its own area | mentioned in one line |
| Findings | 25, each with an ID, severity, location and evidence reference | 14 |
| Output | 8 expert reports, scorecard (md/json/html), 44 evidence records with captured output, remediation plan, delivery folder | one report |
| Project files modified | none | none |
| Cost | about 220,000 tokens, 11 minutes | about 110,000 tokens, 1 minute |

**What this shows.**
- On a tiny project with obvious defects, the skill did not find more of the serious problems than the model alone. Both found every seeded defect that matters; the unaided run demonstrated two of them by executing code, which the skill run did not.
- The skill's contribution here was structure and traceability: a repeatable decision from a fixed rule set, findings tied to recorded evidence, recovery and observability treated as areas of their own, and a package someone else can audit. It cost about twice the tokens and ten times the time.
- It says nothing about larger, real projects, where coverage and consistency matter more and an unaided review is more likely to miss whole areas. That is still unmeasured.

**Defects in the skill that this run exposed, all fixed in v0.4.0** (tests in `tests/test_universal.py`, class `FixesFromTheFirstEvaluation`):
1. An area was labelled "Verified" when its only evidence was a search that found nothing. Captured searches and listings now count as Observed; re-scoring the same review moves five of eight areas from "Verified" to "Observed only".
2. Discovery offered `npm audit` although it cannot run without a lockfile.
3. Discovery did not recognise Node's built-in test runner.
4. The delivery package listed out-of-scope reports as missing and left out `findings.json`.
5. The same search had to be repeated once per area; a record can now be shared across areas.
6. `state` described an area being worked on as "interrupted".
7. `graph` did not say when it had nothing to draw.
8. A search pattern containing words such as "delete from" could be refused as a destructive command.
9. Templates and instructions did not cover quick mode well (scorecard timing, out-of-scope targets, sensitive projects in quick mode, how much sourced research a quick review needs).

## 2026-11-20 — five runs of v0.4.0: full self-review, healthy project, fix loop, AI and deployment, screenshots

**Setup.** Five separate runs of the skill, each by a fresh agent with pre-supplied intake answers, one run each. Their review folders were re-scored afterwards with the fixed engine; all five decisions were unchanged, which means none of them had leaned on the loopholes found.

| Run | Project | Mode | Engine decision | Cost |
|---|---|---|---|---|
| A | This repository (a real project: Python engine, tests, Docker, CI) | full, all 23 areas | CONDITIONAL GO, 73/100; 5 High, no Critical | about 294,000 tokens, 15 min |
| B | `healthy-node` sample (a small clean library) | quick | CONDITIONAL GO, 78/100; no Critical or High | about 207,000 tokens, 6 min |
| C | `flawed-node` sample | focused 2/6/9, then two approved fixes | NO-GO 22 → NO-GO 35 after fixes | about 245,000 tokens, 14 min |
| D | `python-fastapi` sample | focused 2/11/12 with AI and deployment workflows | NO-GO, 40/100; no Critical or High | about 206,000 tokens, 10 min |
| E | `static-site` sample | focused 13 with real screenshots | CONDITIONAL GO, 30/100; 3 High | about 213,000 tokens, 7 min |

**What they show.**

- *All 23 experts have now run once, on one real project (A).* Asked whether each reference section gave enough for a real assessment, the reviewer answered: yes for 8 (Architecture, QA, DevOps, Business Logic, Documentation, Strategy, Technical Leadership, Delivery), thin for 12, not useful for 3 (Disaster Recovery, Observability, Analytics). The cause was the same throughout: the sections assume a hosted web application with a database, and this project is a tool. `references/project-types.md` was written in response and has not itself been evaluated.
- *The full review found real, serious defects in the skill's own engine* (A), all confirmed and fixed in v0.5.0: a check marked "pass" was accepted on the evidence of a command that had failed, so a review built entirely on failed commands scored GO 100/100; the command guard let `ls && rm -rf src` through; parallel evidence runs silently lost records; malformed review files caused crashes instead of INVALID; and there is no licence.
- *A healthy project did not reach GO* (B). The four findings were real but minor (one Medium, three Low). The result was CONDITIONAL GO only because the reviewer's own scores for two core areas (78 and 65) sat under the fixed 80 gate. With no Critical or High, the decision depends on a subjective score, and a prototype is held to the same gate as a production system. The scorecard now explains this; the gates themselves are unchanged. The capability matrix had also treated the library as a service because it had a Dockerfile (fixed).
- *The fix loop works end to end* (C): approval recorded, fix branch, 1 test → 14 tests, the injection probe fails before and passes after, mutation checks confirm the tests catch the old code, rollback rehearsed. It also exposed that "fixed" could be verified by the very run that had demonstrated the defect (fixed), that re-running a benchmark corrupted earlier evidence (fixed), and that the loop had no outcome for "correct but slower": the money fix was measurably slower and was honestly left undecided (a `pending_decision` status now exists).
- *The privacy gate shaped the AI review* (D): only the provider the user allowed was considered, and nothing was sent to any model. The deployment recommendation was "keep the server you already rent", conditional on three facts nobody had confirmed. The run also found that the sample "AI service" declared its libraries but never used them, which the skill had treated as an AI application (fixed: declared and used are now distinguished), and that the suggested `pip-audit` command audited the reviewer's machine instead of the project (fixed).
- *Screenshots and visual regression work with a real browser* (E): 13 real captures, and no-baseline, match and changed verdicts all behaved. Six of nine UX findings came from a scripted walk of the page, not from the still images. It exposed that a capture which failed and produced no image still counted as Verified evidence, and that the image file was not part of the evidence record (both fixed: `--output` binds the file to the record).

**Cost.** Between about 200,000 and 300,000 tokens and 6 to 15 minutes per run, for projects from 20 lines to about 6,000.

**Honest limits of this round.** One run per case. The reviewers were agents of the same model that wrote the skill, given the answers a user would give; no person judged whether the deliverables were good. Only one of the five projects is real, and it is the skill's own repository. Fixes made in v0.5.0 are covered by tests but have not been through another round of runs.

## Round 4 — the engine on real open-source projects (v0.6.0)

The deterministic engine (`discover`, capability matrix, `graph`, `gate`) was run on shallow clones of five public projects. Nothing in them was executed or changed; no model took part, so this round says nothing about the quality of an expert review.

| Project (commit) | Tracked files | discover | graph | What went wrong before the fixes |
|---|---|---|---|---|
| pallets/flask (49943b5) | 236 | 0.2 s | 0.1 s | A library was classed as a monorepo with a UI, a database and Redis, all from `examples/`. The graph had no edges: `src/` layout and relative imports were not followed. The ERD showed a table from an example. |
| expressjs/express (43fca52) | 216 | 0.2 s | 0.1 s | Classed as having a UI because of HTML in `examples/`. |
| gin-gonic/gin (0f09c3a) | 130 | 0.2 s | 0.1 s | "Test frameworks: none" with 41 Go test files. (The graph does not read Go; it says so.) |
| fastapi/full-stack-fastapi-template (77e550a) | 252 | 0.2 s | 0.1 s | Reported the Expo framework and a mobile app: the `exports` field of `package.json` matched "expo". `bun.lock` was not recognised as a lockfile. `from unittest.mock import` was read as the unittest framework. |
| django/django (c67d872) | 7,104 | 4.8 s | 1.7 s | **`graph` did not finish**: stopped by hand after 9 minutes 53 seconds of CPU. The cycle search listed every distinct cycle, which grows exponentially. Stray `requirements.txt` files under `tests/` and `docs/` were treated as parts of the product. The 1,130-edge diagram was too large for any viewer to draw. |

Times are after the fixes, on the build machine.

**Fixed in v0.6.0, each with a regression test** (`tests/test_real_project_regressions.py`):

1. Cycle detection is now linear (strongly connected components, one shortest example per group). Django: under 2 seconds.
2. A graph with more than 120 edges is drawn at a coarser level, and the full list goes to `dependency-edges.csv`.
3. The graph follows relative imports and `src/` layouts.
4. Manifests, schemas, migrations and HTML under examples, docs and tests folders no longer define what the product is; they are listed in a note.
5. Framework and tool names match whole names only.
6. `bun.lock` is a lockfile.
7. Go tests, `unittest` and the Django test runner are detected; `unittest.mock` alone is not.
8. Example and test schemas are left out of the ERD.

`gate` failed on the FastAPI template (exit 20) because its committed `.env` holds default credentials. That is a correct detection of what is in the repository; whether it matters is for a reviewer to judge, since the values are placeholders meant to be changed.

**Research workflow, exercised once by hand.** On the same template: the image tags in `compose.yml` were captured as evidence, two official pages were read on 2026-11-20 (the PostgreSQL versioning policy and Docker's build best practices, both through a summarising fetch tool, which the recorded claims say), one proposal was recorded (pin the floating `adminer` image tag), one proposal with no problem behind it was refused by the engine, and for PostgreSQL 18 the result was "supported until November 2030, nothing to propose". This shows the commands work on a real project with real sources. It was not a review, nobody approved or built anything, and no model-driven run of the research workflow has been evaluated.

**Honest limits of this round.** Five projects, all well-maintained open-source libraries or templates, none of them a private business application, none larger than about 7,000 files. Only the engine ran. Projects' own tests were not run. A defect list from five projects is a sample, not a guarantee for the sixth.

## Not yet evaluated

- The full expert review (the model-driven part) on a real project that is not this one, and on anything large. Round 4 covers the engine only.
- The research workflow in a model-driven run, and a proposal taken from approval through build to verification on a real project.
- Repeat runs (variance), and a person judging the quality of the deliverables.
- Whether a genuinely production-ready project reaches GO.
- `references/project-types.md` and the other guidance added in v0.5.0.
- The edit guard inside a live Claude Code session. The plugin registers the hook and its logic is tested with simulated tool calls; a live session could not be authenticated in the build environment (the test there ends INCONCLUSIVE). `python tools/live_guard_test.py` runs the check on a machine where `claude` is logged in.
- Parallel subagents (every run so far used a single agent).
- The scanner importers for SARIF, osv-scanner, trivy and gitleaks against output captured from those tools.
