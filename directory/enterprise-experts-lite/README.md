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

## Data handling

This plugin has no service behind it and no connectors. Nothing is sent to the author, and nothing is retained outside your machine.

**What it reads.** The files of the project you ask it to review. If those files contain personal data (seed data, fixtures, configuration), Claude reads it as part of the review.

**What it stores, and where.** Only files in `enterprise-review/<date>/` inside your project: the intake answers (including the name of whoever answered and approved), the evidence log, saved command output, the findings and the reports. Values that look like secrets are masked before output is saved. Delete the folder to remove everything.

**What can leave your machine, and only when you say yes at the start:**

| What | Goes to | When |
|---|---|---|
| Search terms and page requests | The web search and fetch tools of your Claude session, and the sites they open | Only if you ask for research. You choose whether terms stay generic or may include project details. Secrets and personal data are never put into a search. |
| Names and versions of your dependencies | The package registry or advisory service of your stack (for example the npm registry for `npm audit`, PyPI's advisory service for `pip-audit`) | Only if you allow tools that contact the network |

The plugin itself runs no code. Any command is run by Claude in your session, under the permissions you have set there.

It is intended for software teams, not for users under 18.

## Limits

- A full review reads a lot of the project and can use several hundred thousand tokens.
- Results depend on what Claude is allowed to run. Checks that could not run are reported as not assessed, not guessed.
- The compliance deliverable is a gap assessment for a qualified person to review, not legal advice.

## Licence

MIT © 2026 Sara Darwich Chamas.
