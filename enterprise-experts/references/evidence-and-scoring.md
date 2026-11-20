# Evidence, Severity, Scoring and Go/No-Go

Read this once per review, before writing any finding. These rules are what make the report trustworthy: they turn "Claude thinks it's fine" into "here is what was checked and what happened".

## Evidence levels

| Level | Meaning | Example |
|---|---|---|
| **Verified** | You ran something and captured the result in `evidence/`. | `npm test` → 142 passed, 3 failed (E-004). `k6` run at 200 VUs → p95 840 ms (E-019). Restored backup into a scratch DB and row counts matched (E-031). |
| **Observed** | You read it directly in code/config/logs and cite the location. | `server/auth.ts:57` compares passwords with `==`. No `.github/workflows` directory exists. |
| **Inferred** | Reasoned from indirect signals; not directly seen or run. | "Likely no backups: no backup config in repo and no mention in docs." |
| **Not assessed** | Couldn't check (no access, out of scope). Say what would unlock it. | "Billing data not available — need read access to the AWS Cost Explorer." |

Rules:
- A check can only be marked **pass** on Verified or Observed evidence. Inferred evidence can support a *finding* (a risk), never a pass.
- Every evidence item gets an ID (`E-001`, `E-002`…) and a line in `evidence-log.md`: `E-007 | Security | npm audit --production | 2 high, 0 critical | evidence/E-007-npm-audit.txt`. Store raw output in `evidence/` (truncate huge outputs, keep the summary and the relevant part; mask secrets).
- Absence counts as evidence when you looked properly: "searched the repo for `helmet|csp|Content-Security-Policy` — no matches (E-012)" is Observed.

## Severity

| Severity | Use when | Effect |
|---|---|---|
| **Critical** | Can cause data breach, data loss, money loss, legal exposure, or full outage now, with a realistic path. E.g. exposed secret, auth bypass, SQL injection, no backups for production data, migrations that drop data. | Blocks GO. Fix before launch. |
| **High** | Serious risk or failure likely under normal growth or common conditions. E.g. no rate limiting on login, no tests on payment flow, no rollback path, N+1 queries on the main page. | Must be fixed or have an approved mitigation for CONDITIONAL GO. |
| **Medium** | Real weakness with limited blast radius or a workaround. | Schedule it. |
| **Low** | Hygiene, consistency, minor improvements. | Backlog. |
| **Info** | Good practice observed, or context. | No action. |

Calibrate to the project's real exposure recorded in Phase 0: the same missing control can be Medium for an internal demo and Critical for a system holding patient or payment data. State the reason when you raise or lower a severity on that basis.

## Area status values

- `assessed` — the expert completed its checks (with whatever evidence was possible).
- `partial` — some checks impossible due to access; the rest done.
- `not_assessed` — nothing meaningful could be checked. No score.
- `not_applicable` — the project has nothing in this area (e.g. no UI). No score, not counted as a gap.

## Scoring (0–100 per area)

The expert proposes a score with this rubric, then `scripts/scorecard.py` applies the caps:

| Score | Meaning |
|---|---|
| 90–100 | Enterprise-grade: controls in place, verified by tests/runs, documented, monitored. |
| 75–89 | Solid: main controls present and mostly verified; some gaps. |
| 60–74 | Workable: basics exist but notable gaps or little verification. |
| 40–59 | Weak: important controls missing. |
| 0–39 | Absent or dangerous. |

Caps (applied automatically by the script — listed here so you score consistently):
- Any **open Critical** in the area → max **40**.
- Any **open High** → max **70**.
- No **Verified** evidence in the area at all (only Observed/Inferred) → max **75**, and the area is labeled *Unverified*.
- Only **Inferred** evidence → max **50**.

Overall score = weighted average of scored areas. Core areas weigh 2: Security (2), Reliability (5), Database (6), Disaster Recovery (7), QA (9), DevOps (10). All others weigh 1.

## Go / No-Go (decided by `scripts/scorecard.py`)

- **NO-GO** if any of: an open Critical anywhere; a core area `not_assessed`; a core area scored below 60.
- **CONDITIONAL GO** if not NO-GO and any of: an open High without an accepted mitigation; a core area below 80; a core area Unverified.
- **GO** only when: no open Critical/High (or Highs with `accepted` mitigation signed off by the user), every core area ≥ 80 with Verified evidence.

`not_applicable` core areas (e.g. no database) are skipped, not penalised. The user can override the decision, but the report must keep the script's decision and record the override and who made it.

## findings.json schema

```json
{
  "project": "Way-Far driver app",
  "review_date": "2026-11-20",
  "mode": "full",
  "areas": [
    {
      "id": 2,
      "name": "Security",
      "status": "assessed",
      "score": 55,
      "summary": "JWT auth present; secrets committed; no rate limiting.",
      "findings": [
        {
          "id": "SEC-001",
          "severity": "critical",
          "title": "Stripe secret key committed in .env.production",
          "location": ".env.production:3",
          "evidence": ["E-011"],
          "evidence_level": "verified",
          "recommendation": "Rotate key, remove file from git history, load from secret manager.",
          "status": "open",
          "mitigation": null
        }
      ],
      "evidence_levels": ["verified", "observed"]
    }
  ]
}
```

- `status` of a finding: `open`, `fixed` (only after a re-check passed and was logged), `accepted` (user accepted the risk or a mitigation — put the text in `mitigation`), `false_positive`.
- `evidence_levels` on the area lists every level used by its checks (including passed checks, not only findings). The script uses it for the Unverified cap.
- Severities in lowercase: `critical`, `high`, `medium`, `low`, `info`.
