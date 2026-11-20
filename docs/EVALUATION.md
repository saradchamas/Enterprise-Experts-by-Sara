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

## Not yet evaluated

- Any real project, of any size.
- More than one run per configuration (variance).
- A healthy project (false positives; does it reach GO when it should?).
- Each of the 23 experts' output quality; only eight areas ran, once.
- The AI engineering, deployment advisor and screenshot workflows end to end.
- The edit guard inside a live Claude Code session (the plugin registers the hook and its logic is tested with simulated tool calls; a live session could not be authenticated in the build environment).
- Remediation: an approved fix, measured before and after, reviewed independently.
