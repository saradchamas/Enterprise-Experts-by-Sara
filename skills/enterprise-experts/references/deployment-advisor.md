# Deployment Advisor

Use when the capability matrix says `deployment advisor: yes` and either the project has no settled hosting, the intake shows a hosting problem (cost, reliability, operations burden), or the user asks. It feeds Infrastructure (11), DevOps (10) and Cost (12). It produces a recommendation, never an action: nothing is provisioned, deployed or changed without explicit permission.

If the project is already hosted and that hosting meets its needs, the right recommendation is to keep it. Do not move a working system for fashion.

A common middle case: the user already pays for something (a VPS, a plan) but the project is not on it yet, or nobody knows whether it is adequate. Then make the recommendation conditional: name the existing option first, list the facts that must be confirmed for it to hold (free memory, a supported system, someone patching it, a tested off-server backup), and name the fallback if any of them fails. When two of the user's goals pull apart (for example "lowest maintenance" and "use the server we already rent"), say so and let them choose; do not hide the tension.

Be proportionate. For a prototype or a small internal tool, compare two or three options on the criteria that actually decide it, and say which criteria you left out. The full comparison is for systems that will carry real users or data.

## 1. Requirements (from discovery, then confirmed with the user)

`discovery.json` has a `deployment_profile`. Confirm and complete it (`calls_an_ai_api` means the project calls a hosted model; it does not mean it needs GPU hosting):

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
| Managed database | Usually preferable to self-run for production data that matters | Region, backups, connection limits; the price can exceed a small project's whole budget, in which case a self-run database with tested backups is a legitimate choice |

Durable workflow engines and job services (Temporal, Inngest and similar) are application components, not hosting: recommend one only if the project has long-running workflows that need it.

## 3. Look up current facts

Plans, prices, limits and features change often. For each candidate, check the provider's own documentation and pricing page, record it as evidence (`EE evidence note --kind observation --location <url> ...` stores the URL and date), and confirm compatibility with the project's actual stack and versions. Do not quote prices or limits from memory. For usage-priced platforms, show how you converted rates into a monthly figure. If a page is blocked or only partly readable, mark the affected cells "not confirmed"; if you cannot browse at all, say so and give the comparison without numbers.

## 4. Compare

One table, same criteria for every candidate: where the data will live and which additional companies will hold it; region and distance to the users; whether the required exposure (for example internal-only) can be kept; compatibility with this stack; expected monthly cost at current and 10× load (show the assumptions); scalability; security (isolation, secrets, network exposure, TLS); reliability (redundancy, restarts, health checks); operational effort; monitoring and logs; backup and recovery; deploy and rollback process; lock-in and exit cost.

## 5. Recommend

The simplest architecture that meets the requirements. State what it does not cover, what must be set up around it (backups, monitoring, alerts), the migration steps and their risk, and the rollback plan. If analysing untrusted repositories or running tests is part of the workload, keep that away from live services.

Deliver it as a section of `11-infrastructure.md`, with a Proposed-labelled deployment diagram, and reference it from `10-devops.md` and `12-cost.md` when those areas are in scope.
