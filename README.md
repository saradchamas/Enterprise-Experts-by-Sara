# Enterprise-Experts-by-Sara

**Enterprise Experts by Sara** is a Claude skill that turns Claude from an assistant that writes code into an **AI engineering team**: 23 specialist experts plus an **AI Engineering Orchestrator / Production Readiness Lead** who coordinates them, prevents conflicting changes, and hands back a **Final Project Health Report** with a score per area, the critical issues, the evidence, and a **Go / No-Go** recommendation.

The idea: instead of asking "is my project good?", you run a process that makes Claude **prove every conclusion** — what it checked, what it fixed, what passed, what failed, and what still needs a human.

> Results are not automatic just because the skill is installed. Claude needs suitable access to the project, tools to run and test it, clear standards, and limited permissions for sensitive operations. The readiness states below are targets, and each one needs evidence or a test result.

## What you get

| # | Area | Final deliverable |
|---|---|---|
| 1 | Architecture | Complete System Architecture + Diagrams |
| 2 | Security | Security Audit + Remediation Report |
| 3 | Performance | Performance Benchmark + Optimization Report |
| 4 | Scalability | Load Testing + Capacity Plan |
| 5 | Reliability | SLOs + Resilience Test Results |
| 6 | Database | Database Audit + Optimized Schema |
| 7 | Disaster Recovery | Backup + Tested Recovery Plan |
| 8 | Observability | Monitoring Dashboards + Alerts |
| 9 | Quality Assurance | Automated Test Suite + QA Report |
| 10 | DevOps | CI/CD + Deployment Pipeline |
| 11 | Infrastructure | Infrastructure Configuration + Capacity Plan |
| 12 | Cost Optimization | Cost Analysis + Budget Alerts |
| 13 | UI/UX | UX Audit + Design Improvements |
| 14 | Data Governance | Data Quality + Governance Report |
| 15 | APIs | API Contracts + Validation Tests |
| 16 | Business Logic | Business Rules + Workflow Validation |
| 17 | Documentation | Complete Technical Documentation |
| 18 | Incident Management | Incident Runbooks + Response Plan |
| 19 | Compliance | Compliance Gap Assessment |
| 20 | Analytics | KPI Dashboards + Product Reports |
| 21 | Technology Strategy | Technology Roadmap |
| 22 | Technical Leadership | Architecture + Code Review Reports |
| 23 | Engineering Delivery | Engineering Plan + Progress Tracking |
| ★ | Orchestration | **Final Project Health Report** (scores, critical issues, evidence, Go/No-Go) |

Target states: **Architecture Reviewed · Security Assessed · Testing Evidence-based · Performance Measured · Monitoring Configured · Deployment Repeatable**.

## How it works

1. **Intake & guardrails** — records what access Claude really has and sets limits (read-only by default; approval required for production, databases, infrastructure, money, compliance, pushing or deleting).
2. **Discovery** — `scripts/discover_project.py` inventories the stack, tests, CI, containers, IaC, database, observability, docs, and scans for committed secrets (masked).
3. **Expert assessment in waves** — Foundation → Protection → Runtime → Delivery → Synthesis. Every finding carries an evidence level: *Verified* (ran it), *Observed* (read it), *Inferred*, or *Not assessed*.
4. **Remediation (with approval only)** — fixes on a branch, one owner per change, re-verified before anything is called "fixed".
5. **Final report** — `scripts/scorecard.py` applies score caps and the Go/No-Go rules deterministically, so the decision can't be talked up.

Three modes: **Full Review** (all 23), **Focused Review** (the areas you name), **Quick Health Check** (the 8 core areas).

## Repository layout

```
enterprise-experts/
├── SKILL.md                         # the Orchestrator's workflow
├── references/
│   ├── evidence-and-scoring.md      # evidence levels, severities, score caps, Go/No-Go
│   ├── experts-architecture-design.md        # experts 1, 4, 6, 15, 16
│   ├── experts-security-data-compliance.md   # experts 2, 14, 19
│   ├── experts-performance-reliability.md    # experts 3, 5, 7, 8, 18
│   ├── experts-quality-delivery-infra.md     # experts 9, 10, 11, 12
│   ├── experts-product-leadership.md         # experts 13, 17, 20, 21, 22, 23
│   └── companion-skills.md          # 47 optional skills/plugins mapped to the experts
├── assets/                          # deliverable + final report templates
└── scripts/
    ├── discover_project.py          # project inventory + secret scan
    └── scorecard.py                 # score caps + Go/No-Go decision
```

## Using it

Install the `enterprise-experts` folder as a skill, open your project, and say for example:

- "Run Enterprise Experts on this project — full review."
- "Is this project production-ready? Quick health check."
- "راجع المشروع من كل الجهات وعطيني Final Project Health Report."
- "Enterprise Experts: only Security, Database and DevOps."

Output is written to `enterprise-review/<date>/` inside the project.

## Notes

- The companion skills listed in `references/companion-skills.md` are optional boosters. Community skills vary in quality; inspect source code and permissions before installing any.
- The compliance deliverable is a gap assessment for a qualified person to review, not legal advice.
