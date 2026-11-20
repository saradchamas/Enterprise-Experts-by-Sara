# Evidence, Severity, Scoring and Go/No-Go

Read this once per review, before writing any finding. These rules turn "Claude thinks it's fine" into "here is what was run, what was read, and what happened". They are enforced by `EE validate` / `EE score`, which is fail-closed: anything missing, malformed or unsupported makes the review **INVALID**, and an invalid review is always NO-GO.

## Evidence levels are earned, not declared

You never write an evidence level. You create evidence records, and the engine derives the level from the record:

| Record | How it is created | Level |
|---|---|---|
| command | `EE evidence run … -- <command>` ran it and stored the output with timestamp, exit code, tool version, commit and a hash | **Verified** — as long as the stored output still exists and is unmodified |
| command that only reads files | the same, where the command is a search or listing (`grep`, `rg`, `cat`, `ls`, `find`, `wc`, `git ls-files`, `git log` and similar) | **Observed** — it shows what the files contain, not that anything works |
| observation | `EE evidence note --kind observation --location path:line` | **Observed** |
| inference | `EE evidence note --kind inference` | **Inferred** |

What each level can prove:
- **Verified** proves that this command ran and produced this output. It is the only level that can show something *works*: tests pass, a backup restores, a build succeeds, p95 is 840 ms.
- **Observed** proves what the code or config *says*. Reading a backup cron job shows a backup is configured, not that it restores. Reading a deploy workflow does not show a deployment succeeded.
- **Inferred** is reasoning from indirect signals. It can support a *finding* (a risk), never a pass.
- A web page you consulted is recorded as an observation with its URL as the location (`EE evidence note --kind observation --location https://...`); the date is stored. It shows what the page said on that day.
- When a command is meant to produce a file (a screenshot, a report), name it with `--output`: the file's hash joins the record, and the record is unusable if the file was not produced or is changed later.
- Evidence commands can run in parallel; the log is locked while it is written. `EE evidence share --id E-0xx --also N` lets another area cite an existing record.
- Looking properly and finding nothing is evidence: run the search through `EE evidence run -- grep -rn "helmet\|Content-Security-Policy" src` and cite it. A captured search is Observed, and a search that found nothing (exit code 1 from `grep`, `rg` and their relatives) can back a `pass`; one that failed for another reason (a missing file, a bad option) cannot. An area whose only evidence is searches has not had anything run, and is capped accordingly. The scorecard shows, for each area, how many of its checks rest on something that was run: sharing one run into an area does not make the whole area verified, so do not describe it that way.
- One run can serve several areas: `EE evidence run --area 9 --also 2 5 ...` lets those areas cite the same record instead of repeating the command.

Honest limit: the engine can prove a command ran and what it printed. It cannot judge whether that command was the right test of the claim. Choosing meaningful checks is your job, and the reviewer reading the report can open every evidence file.

## Severity

| Severity | Use when | Effect |
|---|---|---|
| **critical** | Can cause data breach, data loss, money loss, legal exposure or full outage now, by a realistic path (exposed secret, auth bypass, SQL injection, no backups of production data, a migration that drops data). | Blocks GO until fixed and re-verified. Accepting the risk does not lift it. |
| **high** | Serious risk, or failure likely under normal growth (no rate limit on login, no tests on the payment flow, no rollback path, N+1 queries on the main page). | CONDITIONAL GO at best while open. |
| **medium** | Real weakness with limited blast radius or a workaround. | Schedule it. |
| **low** | Hygiene, consistency. | Backlog. |
| **info** | Good practice observed, or context. | None. |

Calibrate to the intake answers: the same missing control can be medium for an internal demo and critical for a system holding patient or payment data. Say why when you raise or lower a severity on that basis.

## findings.json (schema version 2)

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

Rules the engine enforces:
- **Required areas.** `full` needs all 23 areas; `quick` needs 1, 2, 5, 6, 7, 8, 9, 10; `focused` needs a `"scope"` list and every area in it. A missing area is an error, not a gap to explain later.
- **Area status**: `assessed`, `partial` (some checks impossible), `not_assessed`, `not_applicable`. The last two need a `reason` that says why in a sentence, and carry no score. Areas 1, 2, 9, 17 and 22 cannot be `not_applicable`. Marking an area not applicable when the capability matrix found it applicable is allowed (the matrix can be wrong) and is shown on the scorecard.
- **Score**: a number from 0 to 100.
- **Checks**: every assessed or partial area lists the checks performed. `pass` and `fail` need evidence. A `pass` needs a command that ran and exited 0, or an observation; a command that failed, timed out or could not start can only back a `fail` or a finding. `not_assessed` / `not_applicable` checks need a `reason`.
- **Evidence references** must exist in `evidence-log.json`, be intact, and belong to the same area. Only the areas that synthesise others' work (17, 19, 21, 22, 23) may cite another area's evidence.
- **IDs** of areas, checks, findings and evidence are unique.
- **Finding status**:
  - `open` — needs evidence.
  - `fixed` — needs `"verification": ["E-0xx"]`: a command that exited 0, recorded after the evidence that found the problem. The run that demonstrated the defect cannot verify its own fix.
  - `pending_decision` — a verified fix exists but the user must still decide (for example correct but slower). Needs a `note`. Counts as unresolved.
  - `accepted` — needs `"mitigation": {"approved_by": "...", "reason": "...", "date": "YYYY-MM-DD", "controls": ["..."]}`. Only the user can accept a risk.
  - `false_positive` — needs a `reason`.
- **Intake**: `intake.json` must exist and be valid; `mode` must match it; `risk_profile` may not be lower than the answers imply.

## Scoring

The expert proposes a score; the engine applies caps.

| Score | Meaning |
|---|---|
| 90–100 | Enterprise-grade: controls in place, verified by runs, documented, monitored. |
| 75–89 | Solid: main controls present and mostly verified; some gaps. |
| 60–74 | Workable: basics exist, notable gaps or little verification. |
| 40–59 | Weak: important controls missing. |
| 0–39 | Absent or dangerous. |

Caps: an unresolved Critical (open or accepted) caps the area at **40**; an open High at **70**; no Verified evidence at **75**; inferred evidence only at **50**; no check passed at **40**; more checks failed than passed at **70**. The overall score is the weighted average of scored areas, core areas counting double.

## Risk profiles and release gates

| Profile | Core areas | Core score for GO | Core score that blocks |
|---|---|---|---|
| standard | 2 Security, 5 Reliability, 6 Database, 7 DR, 9 QA, 10 DevOps | 80 | below 60 |
| sensitive | the above + 8 Observability, 14 Data Governance, 18 Incidents | 85 | below 65 |
| regulated | the above + 19 Compliance | 90 | below 70 |

Decision:
- **NO-GO** — any unresolved Critical; a core area not assessed; a core area below the blocking score; or the review is invalid.
- **CONDITIONAL GO** — otherwise, if any of: an open High; a core area below the GO score, without Verified evidence, or only partially assessed; a non-core area not assessed; an accepted High on a sensitive or regulated project; a core area outside the review's scope (always true for a narrow focused review).
- **GO** — none of the above.

The scorecard adds a "How to read this result" section when the label alone could mislead: a prototype, a NO-GO with no Critical or High finding (things are missing, nothing dangerous is live), a non-core area scoring very low under a CONDITIONAL GO, or an override of the capability matrix. Carry those sentences into the report.

A core area that is genuinely `not_applicable` (no database) is skipped. The user can decide to launch against the engine's decision; the report then shows both, with who decided and why. Process exit codes: GO 0, CONDITIONAL GO 10, NO-GO 20, invalid 2.
