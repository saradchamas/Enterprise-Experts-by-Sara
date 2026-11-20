# Intake Questions

The review starts by asking. A production-readiness verdict depends on facts that are not in the code: what data the system holds, who uses it, what "down" costs, what you are allowed to run. Guessing them produces a confident report about the wrong project.

## How to ask

1. **Discover first.** Run `EE discover`, read the README and entry points, then run `EE questions --review <review>`. It returns only the questions that fit this project: a project with no database is not asked about database backups; an AI app is asked what the model can reach.
2. **Don't ask what the project already answers.** If the README states the purpose or the deploy process is in a workflow file, propose the answer and ask the user to confirm it ("I read this as an internal logistics dashboard — correct?"). Confirmation is still required for the required questions; an inferred answer is a guess until the user agrees.
3. **Ask in small batches**, most important first. Use the multiple-choice question tool when the session has one (up to four questions per call, options taken from the question's `options`); otherwise ask in plain text. Use the user's language.
   - Batch 1 — risk and scope (always): `purpose`, `stage`, `exposure`, `industry`, `data_types`, `handles_money`, `review_mode`, `change_permission`, `environments_allowed`.
   - Batch 2 — what matters: `critical_journeys`, `users_scale`, `users_regions`, `known_problems`, `deadline`, `out_of_scope`.
   - Batch 3 — access and operations, only those returned for this project: hosting, deploy, backups, monitoring, billing, CI, AI usage, UI audience, API consumers, compliance targets, tickets, limits.
4. **Explain why when it isn't obvious.** Each question carries a `why`. One short clause is enough.
5. **"I don't know" is an answer.** Record it as `"unknown"`. Unknown data types or money handling raise the risk profile, and the checks that depended on the answer become `not_assessed` with "owner did not know" as the reason. Often that is itself a finding (nobody knows whether backups were ever restored).
6. **Keep asking during the review.** Experts will hit questions the bank doesn't cover (a business rule, an odd config). Ask then, in the same way, and add the answer to `intake.json` under a new key. Collect non-urgent ones and ask them together rather than interrupting repeatedly. Questions only the business can answer also go in the relevant deliverable under "Needs a human".
7. **If the user is not available** (scheduled or unattended run): do not invent answers. Answer what the repository proves, mark the rest `"unknown"`, state at the top of the report that the intake was unanswered, and expect a stricter risk profile and a decision no better than CONDITIONAL GO.

## intake.json

```json
{
  "schema_version": 1,
  "answered_by": "Sara",
  "date": "2026-11-20",
  "answers": {
    "purpose": "Marketplace connecting shippers with delivery drivers in Lebanon",
    "stage": "pre_launch",
    "exposure": "public",
    "industry": "logistics",
    "data_types": ["personal", "credentials"],
    "handles_money": "yes",
    "review_mode": "full",
    "change_permission": "fix_on_branch_after_approval",
    "environments_allowed": ["local", "staging"],
    "critical_journeys": ["driver signup", "create shipment", "payout"],
    "restore_tested": "unknown"
  },
  "inferred_confirmed": ["purpose"],
  "risk_profile": null
}
```

`EE intake --review <review>` validates the file and prints the risk profile. Set `"risk_profile"` only to make it stricter than the derived one.

## What the answers change

| Answer | Effect |
|---|---|
| `data_types` includes health, payment card, government ID or children's data; or `industry` is healthcare, finance or government | Risk profile **regulated**: Observability, Data Governance, Incidents and Compliance become core areas; core areas need 90 for GO. |
| Personal data, credentials, financial records, confidential business data; money handled; or public and in production; or any of these unknown | Risk profile **sensitive**: Observability, Data Governance and Incidents become core; core areas need 85. |
| None of the above | **standard**: core areas are Security, Reliability, Database, DR, QA, DevOps; they need 80. |
| `review_mode` | Which areas `findings.json` must contain. A missing area makes the review invalid. |
| `change_permission: assess_only` | Phase 3 produces a plan only. No project file is edited. |
| `environments_allowed` | Where load, resilience and E2E tests may run. `none_read_code_only` means nothing is executed against a running system and those checks are `not_assessed`. |
| `critical_journeys` | What QA must show tests for, what SLOs are written for, what UX walks through. |
| `users_regions`, `compliance_targets` | Which regulations the Compliance expert screens. |
| `out_of_scope` | Respected by every expert; listed in the report so readers know what wasn't looked at. |
| `budget_limits` | Depth and parallelism of the review; what was skipped is reported. |
