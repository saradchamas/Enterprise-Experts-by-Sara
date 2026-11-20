# Enterprise Experts by Sara — Lite edition

A Claude skill that turns Claude into an AI engineering team: 23 specialist experts and a Production Readiness Lead who review any software project, record evidence for every conclusion, and hand back a Final Project Health Report with a score per area, the critical issues, and a GO / CONDITIONAL GO / NO-GO.

This is the **instructions-only edition**. It contains Markdown and JSON, nothing else: no scripts, no hooks, nothing that runs on your machine by itself.

## What you get

- **A review across 23 areas**: architecture, security, performance, scalability, reliability, database, disaster recovery, observability, QA, DevOps, infrastructure, cost, UI/UX, data governance, APIs, business logic, documentation, incidents, compliance, analytics, strategy, technical leadership, delivery.
- **Questions first.** Before reviewing, the skill asks what the project is for, what data it holds, and what it may run and change.
- **An evidence log.** Every command run and every file read is recorded; each finding and each "pass" points to a record.
- **Research, if you want it**: newer technologies, AI models, tools and MCP servers that would help this project, each proposal tied to a problem and to pages that were read, with URL and date.
- **Changes only after your approval**, on a branch, re-checked afterwards.

## Install

```
/plugin install enterprise-experts-lite --marketplace saradchamas/Enterprise-Experts-by-Sara
```

## Use

Open your project and say, for example:

- "Run Enterprise Experts on this project — full review."
- "Is this project production-ready? Quick health check."
- "Enterprise Experts: only Security, Database and DevOps."

Output is written to `enterprise-review/<date>/` inside the project.

## How this edition differs from the full one

| | Lite (this plugin) | Full (GitHub) |
|---|---|---|
| The 23 experts, intake questions, report | Yes | Yes |
| Evidence log | Kept by Claude, by hand | Written by a program that captures each command's output and hash |
| Scores and decision | Applied by Claude from written rules | Computed by a program that refuses incomplete or unsupported reviews |
| Unapproved edits | A rule Claude follows | Blocked by a hook |
| Diagrams from code, image comparison, benchmarks, Excel and PDF export | Done by hand or not available | Built in |

In short: this edition gives you the method and the report. It cannot give you an independent check that the method was followed. Read the scorecard with that in mind, and open the evidence files.

The full edition, its tests and its evaluation record are at <https://github.com/saradchamas/Enterprise-Experts-by-Sara>.

## Limits

- A full review reads a lot of the project and can use several hundred thousand tokens.
- Results depend on what Claude is allowed to run. Checks that could not run are reported as not assessed, not guessed.
- The compliance deliverable is a gap assessment for a qualified person to review, not legal advice.

## Licence

MIT © 2026 Sara Darwich Chamas.
