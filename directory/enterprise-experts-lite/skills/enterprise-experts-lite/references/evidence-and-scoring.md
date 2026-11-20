# Evidence, Severity, Scoring and Go/No-Go (Lite edition)

Read this once per review, before writing any finding, and again before scoring. These rules turn "Claude thinks it's fine" into "here is what was run, what was read, and what happened".

In this edition nothing checks the rules for you. You keep the log, you apply the caps, you work out the decision. Treat a rule you cannot satisfy as a reason to lower the result, never as a detail to explain away: when in doubt, the review is **INVALID**, and an invalid review is NO-GO.

## The evidence log

Keep `evidence-log.md` in the review folder. Add a record **at the moment** you run or read something, never later from memory. Records are numbered `E-001`, `E-002`, … and never renumbered, edited or deleted. A correction is a new record that refers to the old one.

| Kind | What you record | Level it earns |
|---|---|---|
| command | The exact command, the folder it ran in, the time, the exit code, the commit, the areas it serves, and the path of the saved output: write the full output to `evidence/E-0xx-<short-name>.txt`. Mask anything that looks like a secret before saving. | **Verified**, if the output file exists and the command exercised something |
| command that only reads files | The same, for a search or listing (`grep`, `rg`, `cat`, `ls`, `find`, `wc`, `git ls-files`, `git log` and similar) | **Observed**: it shows what the files contain, not that anything works |
| observation | What you read and where: `path:line`, or a URL with the date you read it | **Observed** |
| inference | What you concluded and from what | **Inferred** |

One line per record is enough:

```
E-014 | command | area 9 (also 2, 5) | 2026-11-20 10:42 | commit 77e550a | cwd backend | exit 0 | `pytest -q` | evidence/E-014-backend-tests.txt | 142 passed
E-015 | observation | area 2 | backend/app/api/routes/login.py:23 | no attempt limit on the login route
E-016 | inference | area 4 | from E-014 and the single-process start command: one worker handles all requests
```

What each level can show:

- **Verified** shows that this command ran and produced this output. It is the only level that can show something *works*: tests pass, a backup restores, a build succeeds, p95 is 840 ms.
- **Observed** shows what the code or configuration *says*. Reading a backup job shows a backup is configured, not that it restores.
- **Inferred** is reasoning from indirect signals. It can support a finding (a risk), never a pass.
- A web page is an observation with its URL and the date. It shows what the page said that day.
- Looking properly and finding nothing is evidence: record the search and its result. A search that found nothing (exit code 1 from `grep` and its relatives) can back a pass; one that failed for another reason cannot.
- A command that failed, timed out or could not start shows a failure. It can back a `fail` or a finding, never a `pass`.
- A script you wrote yourself proves what it tests and nothing more. Say in the deliverable what was and was not exercised.

Honest limit: the log shows what you say you ran. A reader can open every output file, and should. Choosing checks that actually test the claim is your job.

## Severity

| Severity | Use when | Effect |
|---|---|---|
| **critical** | Can cause data breach, data loss, money loss, legal exposure or full outage now, by a realistic path (exposed secret, auth bypass, SQL injection, no backups of production data, a migration that drops data). | Blocks GO until fixed and re-verified. Accepting the risk does not lift it. |
| **high** | Serious risk, or failure likely under normal growth (no rate limit on login, no tests on the payment flow, no rollback path, N+1 queries on the main page). | CONDITIONAL GO at best while open. |
| **medium** | Real weakness with limited blast radius or a workaround. | Schedule it. |
| **low** | Hygiene, consistency. | Backlog. |
| **info** | Good practice observed, or context. | None. |

Calibrate to the intake answers: the same missing control can be medium for an internal demo and critical for a system holding patient or payment data. Say why when you raise or lower a severity on that basis.

## findings.json

```json
{
  "schema_version": 2,
  "project": "Way-Far driver app",
  "review_date": "2026-11-20",
  "mode": "full",
  "risk_profile": "sensitive",
  "areas": [
    {
      "id": 2,
      "name": "Security",
      "status": "assessed",
      "score": 55,
      "summary": "JWT auth present; secret committed; no rate limiting.",
      "checks": [
        {"id": "SEC-C1", "title": "Dependency vulnerabilities", "result": "pass", "evidence": ["E-007"]},
        {"id": "SEC-C2", "title": "Committed secrets", "result": "fail", "evidence": ["E-011"]},
        {"id": "SEC-C3", "title": "Penetration test of staging", "result": "not_assessed", "reason": "no staging URL"}
      ],
      "findings": [
        {
          "id": "SEC-001", "severity": "critical", "status": "open",
          "title": "Payment provider secret key committed in .env.production",
          "location": ".env.production:3", "evidence": ["E-011"],
          "recommendation": "Rotate the key, remove the file from git history, load it from a secret manager."
        }
      ]
    },
    {"id": 13, "name": "UI/UX", "status": "not_applicable", "reason": "API-only service, no user interface"}
  ]
}
```

Rules to keep. Each one is also a line of the self-check at the end:

- **Required areas.** `full` needs all 23 areas; `quick` needs 1, 2, 5, 6, 7, 8, 9, 10; `focused` needs a `"scope"` list and every area in it. A missing area makes the review invalid.
- **Area status**: `assessed`, `partial` (some checks were impossible), `not_assessed`, `not_applicable`. The last two need a `reason` of at least a sentence, and carry no score. Areas 1, 2, 9, 17 and 22 cannot be `not_applicable`.
- **Score**: a number from 0 to 100.
- **Checks**: every assessed or partial area lists the checks performed. `pass` and `fail` need evidence IDs. A `pass` needs a command that exited 0 or an observation. `not_assessed` and `not_applicable` checks need a `reason`.
- **Evidence references** must exist in the log and belong to the same area (or list it under "also"). Only the areas that synthesise others' work (17, 19, 21, 22, 23) may cite another area's evidence.
- **IDs** of areas, checks, findings and evidence are unique.
- **Finding status**:
  - `open` needs evidence.
  - `fixed` needs `"verification": ["E-0xx"]`: a command that exited 0, recorded after the evidence that found the problem.
  - `pending_decision`: a verified fix exists but the user must still decide. Needs a `note`. Counts as unresolved.
  - `accepted` needs `"mitigation": {"approved_by": "...", "reason": "...", "date": "YYYY-MM-DD", "controls": ["..."]}`. Only the user can accept a risk.
  - `false_positive` needs a `reason`.
- **Intake**: `intake.json` must exist; the mode must match it; the risk profile may not be lower than the answers imply.

## Scoring, step by step

**Step 1. Propose a score for each area.**

| Score | Meaning |
|---|---|
| 90–100 | Enterprise-grade: controls in place, verified by runs, documented, monitored. |
| 75–89 | Solid: main controls present and mostly verified; some gaps. |
| 60–74 | Workable: basics exist, notable gaps or little verification. |
| 40–59 | Weak: important controls missing. |
| 0–39 | Absent or dangerous. |

**Step 2. Apply the caps.** The final score is the proposed score, lowered to the lowest cap that applies:

| Condition in the area | Cap |
|---|---|
| An unresolved Critical (open, pending or accepted) | 40 |
| No check passed | 40 |
| Inferred evidence only | 50 |
| An open High | 70 |
| More checks failed than passed | 70 |
| No Verified evidence (nothing was run) | 75 |

**Step 3. Work out the overall score**: the average of the final scores of all scored areas, with core areas counted twice. Show the arithmetic in the scorecard.

**Step 4. Find the risk profile's gates.**

| Profile | Core areas | Core score for GO | Core score that blocks |
|---|---|---|---|
| standard | 2 Security, 5 Reliability, 6 Database, 7 DR, 9 QA, 10 DevOps | 80 | below 60 |
| sensitive | the above + 8 Observability, 14 Data Governance, 18 Incidents | 85 | below 65 |
| regulated | the above + 19 Compliance | 90 | below 70 |

**Step 5. Decide.**

- **NO-GO**: any unresolved Critical; a core area not assessed; a core area below the blocking score; or the review is invalid.
- **CONDITIONAL GO**: otherwise, if any of: an open High; a core area below the GO score, without Verified evidence, or only partially assessed; a non-core area not assessed; an accepted High on a sensitive or regulated project; a core area outside the review's scope (always true for a narrow focused review).
- **GO**: none of the above.

A core area that is truly `not_applicable` (no database) is skipped. The user can decide to launch against the decision; the report then shows both, with who decided and why.

## scorecard.md

Start with this line, then the decision:

> Lite edition: these scores and this decision were applied by the reviewer from written rules. No independent program validated the evidence or the arithmetic.

Then: decision, overall score, date, mode, risk profile, the commit or commits the evidence was recorded at, and one row per area:

| # | Area | Status | Proposed score | Final score | Cap applied | Unresolved Critical | Open High | Evidence basis |
|---|---|---|---|---|---|---|---|---|

"Evidence basis" is `Verified (n of m checks were run)`, `Observed only` or `Inferred only`, where n counts the checks that cite a Verified record. Sharing one run into an area does not make the area verified: count honestly.

Below the table: every blocker (reason for NO-GO), every condition, and a "How to read this result" section when the label alone could mislead: a prototype; a NO-GO with no Critical or High finding (things are missing, nothing dangerous is live); a non-core area scoring very low under a CONDITIONAL GO.

## Self-check before the report

Go through this list against the files, not from memory. Any "no" means fix it or declare the review INVALID.

1. Does `findings.json` contain every area the mode requires?
2. Does every `pass` and `fail` check cite an evidence ID that exists in `evidence-log.md`?
3. Does every `pass` rest on a command that exited 0 or on an observation, and never on an inference or a failed command?
4. Does every command record have its output file in `evidence/`, and does the file still say what the record says?
5. Does every `fixed` finding cite a passing re-check recorded after the evidence that found it?
6. Was every cap in Step 2 applied? Re-do the arithmetic of the overall score.
7. Does the decision follow Step 5 exactly, with every blocker and condition listed?
8. Does the scorecard say how many checks per area were actually run, and at which commit?
9. Is every change in `change-log.md` covered by an entry in `approvals.md` made before the change?
10. Is the Lite-edition line at the top of the scorecard and the final report?
