# Recommendations and the Verified Improvement Loop

A review is useful when it answers four questions with evidence: what is wrong, what is the best solution *for this project*, did the improvement actually work, and is the project ready to release. This file covers the middle two.

## What a recommendation must contain

Every High or Critical finding, and every change you propose to make, is written up with:

| Field | Content |
|---|---|
| Problem | What is wrong and what it costs, with the evidence ID. |
| Affected files | Paths and lines. |
| Source | An authoritative reference for the fix: the framework's or vendor's own documentation, or a recognised standard (OWASP ASVS, NIST SSDF, WCAG, the language's style guide). Give the URL and, where available, the version or publication date it applies to. Look it up; do not cite from memory, and never invent a URL. If you could not find a source, say "no authoritative source found" and mark the recommendation as your own judgment. |
| Applicability | Why it fits this project: the versions actually in use (from the manifest or lockfile), the stack, the scale and risk profile from the intake. |
| Options | The recommended change and at least one alternative, including "do nothing" when that is defensible. |
| Trade-offs | Effect on security, performance, maintainability and cost. |
| Approval needed | What the user must approve (files, commands, external systems). |
| Verification | The exact check that will show it worked, and the acceptance criterion agreed beforehand. |

Do not apply a best practice because it is a best practice. Recommend what a demonstrated problem or a stated risk calls for. A weekend prototype does not need a service mesh; say so rather than padding the report.

Check compatibility before recommending: a fix written for a newer major version of a framework than the project uses is not a fix.

## The loop

1. **Baseline.** Establish a reproducible measurement before touching anything: the failing test, the vulnerable request, the benchmark (`EE bench run --label baseline`).
2. **Identify** the cause and record the evidence.
3. **Research** compatible solutions (see Source above).
4. **Propose** the smallest change that solves it. Small changes can be reviewed, measured and reverted.
5. **Approval.** The user decides. Record it with `EE approve`.
6. **Implement** on a branch or worktree.
7. **Re-run the same check**, the same way, on the same machine: `EE bench run --label candidate`, the same test command, the same request.
8. **Compare** (`EE bench compare`). The engine calls a change an improvement only when the difference is larger than the run-to-run noise and meets the agreed threshold. If runs failed, or the command, metric or environment differed, the comparison is refused.
9. **Check for regressions**: the full test suite, and a second look at security and cost.
10. **Keep or revert.** Keep the change only if the acceptance criterion passed. Otherwise revert it, or leave the finding open and report the change as unproven. Never describe an unmeasured change as an improvement.

### Benchmarks that mean something

- Same command, same data, same machine, nothing else heavy running. Use `--warmup` so caches and JITs settle.
- At least 5 measured runs when a run is short. Report the spread, not just one number.
- For a service, measure what users feel: use `--metric-regex` to capture p95 latency or throughput from a load tool's output rather than timing the tool itself.
- Load tests run against local or staging targets the user allowed. Never production.
- A laptop benchmark shows direction, not production numbers. Say so in the report.

## Independent review

The author of a change is the worst person to judge it. Each approved change is reviewed by someone who did not write it: the `independent-reviewer` subagent when available, otherwise you, re-reading the diff cold. The reviewer checks:

- Does the diff do what the approved recommendation said, and only that? Any file outside the approved paths?
- Does the re-check actually exercise the fix, or would it pass without it?
- New risks: security (input handling, auth, secrets), data (migrations, loss), behaviour changes callers depend on, cost.
- Are tests added or updated for the changed behaviour? Was any test weakened or deleted to make it pass?
- Is the rollback path real?

The reviewer's verdict (`approve`, `changes needed`, with reasons) goes into `change-log.md`. A change the reviewer rejects is not marked `fixed`.

## change-log.md

One entry per change: finding IDs, owner expert, approval (who, when), branch, files, what changed, baseline and candidate evidence IDs, benchmark verdict if any, reviewer verdict, rollback instruction.
