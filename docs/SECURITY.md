# Security and Permissions

## Principles

- **Read-only by default.** Discovery reads files and never writes into the project. Assessment does not edit project files.
- **Approval before change.** Code changes need an approved remediation plan and happen on a branch. Production systems, real databases, infrastructure, credentials, billing, pushes and deletions always need explicit approval, each time.
- **Fail-closed decisions.** A review that is incomplete or cannot be validated is NO-GO.
- **No secrets in output.** Secret-shaped values are masked in discovery output and in captured evidence.

## What enforces what

| Control | Enforced by | Strength |
|---|---|---|
| Decision rules, required areas, evidence integrity | the engine (`ee/scoring.py`), covered by regression tests | Deterministic |
| Secret masking in evidence and discovery | the engine (`ee/secrets.py`) | Pattern-based: catches common key formats, connection strings and `NAME_SECRET=value` lines. An unusual secret format can slip through; review evidence before sharing a report. |
| Refusing destructive or publishing commands | the engine (`ee/policy.py`) inside `evidence run` | A guardrail, not a sandbox. It only sees commands run through `evidence run`, and a determined command line can evade pattern matching. |
| Not editing project files during assessment | the skill's instructions to Claude, plus your Claude Code permission settings | Instruction-level. For a hard guarantee, run Claude Code with edit permissions denied during assessment, or review a read-only copy. |
| Isolation of the deterministic runner | Docker (`compose.yaml`) | Enforced by the container runtime; checked by `tools/docker_smoke.sh`. |

## Evidence integrity: what it does and does not prove

Each command record stores the command, exit code, start time, duration, tool version, commit and the SHA-256 of the captured output. The engine rejects a record whose output file is missing or changed.

This detects accidental edits and unsupported claims. It is not tamper-proof: someone with write access to the review folder can rewrite the output and the hash together. The hashes are not signed. Treat a review folder as trustworthy to the degree you trust whoever produced it, and keep it in version control if you need an audit trail.

## Recommendations for sensitive projects

- Review a clone, not your working copy with uncommitted secrets.
- Do not give Claude production credentials. Read-only access to metrics and logs is enough for assessment.
- Keep `change_permission` at `assess_only` for the first review.
- Read `evidence/` before sharing a report outside your team.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository (Security → Advisories → Report a vulnerability). Please do not open a public issue for a vulnerability.
