# Final Project Health Report — {Project}

**Prepared by:** AI Engineering Orchestrator / Production Readiness Lead (Enterprise Experts by Sara)
**Date:** {YYYY-MM-DD}  |  **Mode:** Full / Focused / Quick Health Check  |  **Commit reviewed:** {hash/branch}

## 1. Decision

> **{GO / CONDITIONAL GO / NO-GO}** — Overall score **{NN}/100**

{2–4 sentences: why this decision, in plain language. If CONDITIONAL, list the exact conditions. If NO-GO, list the blockers.}

{If the user wrote in Arabic: add "## الملخص التنفيذي" here with the same decision, top issues and next steps in Arabic.}

## 2. Readiness targets

| Target | Status | Evidence |
|---|---|---|
| Architecture — Reviewed | ✅ Proven / ⚠️ Partly / ❌ Not yet / ➖ Not assessed | E-… |
| Security — Assessed | | |
| Testing — Evidence-based | | |
| Performance — Measured | | |
| Monitoring — Configured | | |
| Deployment — Repeatable | | |

A target is "Proven" only with Verified evidence. Reading the code and finding it plausible is "Partly".

## 3. Scorecard

{Paste the table from scorecard.md (output of scripts/scorecard.py): area, status, raw score, final score, cap reason, open Critical/High counts, evidence basis.}

## 4. Critical and High issues

| ID | Area | Severity | Issue | Evidence | Fix | Status |
|---|---|---|---|---|---|---|

## 5. What was done in this review

- **Checked:** {count of checks, commands run, areas covered}
- **Fixed and verified:** {list with finding IDs and evidence of the passing re-check}
- **Passed:** {notable strengths, with evidence}
- **Failed / still open:** {list}
- **Not assessed:** {areas/checks, and the access that would unlock each}

## 6. Needs human action

| # | Action | Who | Why it can't be automated |
|---|---|---|---|
| 1 | {Rotate the leaked API key} | {Owner} | {Requires provider account access} |

## 7. Deliverables index

| # | Area | Deliverable | File | Score |
|---|---|---|---|---|
| 1 | Architecture | System Architecture + Diagrams | `01-architecture.md` | |
| … | | | | |

## 8. Plan to reach GO

{The launch-blocker milestone from expert 23: ordered list of items, owner, effort, and the verification that will close each.}

## 9. Recommended tooling

{Companion skills/plugins or access that would raise the evidence level next time.}

## 10. Method and limits

Evidence levels: Verified (ran it), Observed (read it), Inferred (reasoned), Not assessed. Scores are capped when evidence is weak or issues are open (see evidence-and-scoring rules). This report reflects the project at the reviewed commit and the access available on the review date; it is an engineering assessment, not a guarantee, and the compliance section is not legal advice.
