# Deployment Advisor

Use when the capability matrix says `deployment advisor: yes` and either the project has no settled hosting, the intake shows a hosting problem (cost, reliability, operations burden), or the user asks. It feeds Infrastructure (11), DevOps (10) and Cost (12). It produces a recommendation, never an action: nothing is provisioned, deployed or changed without explicit permission.

If the project is already hosted and that hosting meets its needs, the right recommendation is to keep it. Do not move a working system for fashion.

## 1. Requirements (from discovery, then confirmed with the user)

`discovery.json` has a `deployment_profile`. Confirm and complete it:

- Runtime: long-running server, static frontend, background workers, scheduled jobs, websockets, AI inference or GPU, mobile store release.
- State: database engine and size, file storage, cache or queue.
- Load: users and requests now and expected (intake `users_scale`), regions.
- Limits: monthly budget, who operates it and how much time they have, data residency, compliance (intake `deployment_goals`, `users_regions`, risk profile).
- What exists: current host, anything already paid for (for example a VPS), existing Docker setup.

## 2. Candidate approaches

Pick two to four that fit. Typical families:

| Approach | Fits when | Watch for |
|---|---|---|
| Keep the current hosting | It meets the requirements | — |
| Self-hosted platform on a VPS (for example Coolify, Dokku, plain Docker Compose) | A VPS already exists; cost matters; someone can operate a server | You own patching, backups, monitoring and recovery |
| Managed application platform (for example Render, Railway, Fly.io) | Small team, little operations time; APIs, workers, cron | Cost grows with usage; platform limits |
| Frontend/edge platform (for example Vercel, Netlify, Cloudflare) | Next.js or static frontends; edge functions | Long-running or stateful backends need another home |
| Cloud provider services (AWS, GCP, Azure) | Compliance, scale or specific managed services are required | Complexity and cost control |
| GPU or serverless inference host | The project runs its own models | Cold starts, per-second pricing |
| Managed database | Almost always preferable to self-run for production data | Region, backups, connection limits |

Durable workflow engines and job services (Temporal, Inngest and similar) are application components, not hosting: recommend one only if the project has long-running workflows that need it.

## 3. Look up current facts

Plans, prices, limits and features change often. For each candidate, check the provider's own documentation and pricing page, record the URL and the date, and confirm compatibility with the project's actual stack and versions. Do not quote prices or limits from memory. If you cannot browse, say so and give the comparison without numbers.

## 4. Compare

One table, same criteria for every candidate: compatibility with this stack; expected monthly cost at current and 10× load (show the assumptions); scalability; security (isolation, secrets, network exposure, TLS); reliability (redundancy, restarts, health checks); operational effort; monitoring and logs; backup and recovery; deploy and rollback process; lock-in and exit cost.

## 5. Recommend

The simplest architecture that meets the requirements. State what it does not cover, what must be set up around it (backups, monitoring, alerts), the migration steps and their risk, and the rollback plan. If analysing untrusted repositories or running tests is part of the workload, keep that away from live services.

Deliver it as a section of `11-infrastructure.md`, with a Proposed-labelled deployment diagram, and reference it from `10-devops.md` and `12-cost.md`.
