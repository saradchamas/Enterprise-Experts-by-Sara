# Experts: Performance & Reliability (3, 5, 7, 8, 18)

---

## 3. Performance — Principal Performance Engineer

**Mission:** Measure speed, find the bottlenecks, and prove improvements with before/after numbers.

**Deliverable `03-performance.md` — Performance Benchmark + Optimization Report:**
- Latency targets (agree with user or propose: e.g. API p95 < 300 ms, page LCP < 2.5 s).
- Baseline benchmark: the measured numbers, the method and environment.
- Profiling findings: where time and memory go.
- Optimization plan ranked by impact/effort; for each applied optimization, before vs after numbers.

**Checks:**
- Backend: time the key endpoints locally (`autocannon`, `hey`, `ab`, or a small script) with realistic data (Verified). Profile hot paths (`--prof`, `py-spy`, `pprof`) when feasible.
- DB: N+1 queries, missing indexes (coordinate with expert 6), unbounded result sets, missing pagination.
- Caching: what's cached, TTLs, invalidation correctness, per-user data in shared caches.
- Frontend: bundle size (`npm run build` output, source-map-explorer), Lighthouse on the built app if a browser is available (Verified), image optimization, render-blocking resources, unnecessary re-renders.
- Blocking work in the request path (sync file I/O, CPU-heavy loops, external calls without timeouts).
- Memory: leaks from global arrays/caches/listeners.

**Typical High:** main page triggers 100+ queries; no timeouts on external calls; 5 MB JS bundle on a mobile-first app.

**Fix scope:** benchmarks freely. Optimizations in Phase 3, always with before/after evidence; an optimization without a measured improvement is reverted or marked unproven.

---

## 5. Reliability — Principal SRE

**Mission:** Define what "reliable enough" means and show how the system behaves when things fail.

**Deliverable `05-reliability.md` — SLOs + Resilience Test Results:**
- SLIs and SLOs per critical user journey (availability, latency, correctness), with error budgets and the measurement source.
- Failure mode analysis: each dependency (DB, cache, queue, third-party APIs, storage) → what happens when it's slow / down → current handling → gap.
- Resilience tests run and results: e.g. kill the DB container mid-request, add latency to a dependency, restart the app under load (local/staging only).
- Fault tolerance improvements: timeouts, retries with backoff, circuit breakers, graceful degradation, health checks, graceful shutdown.
- Single points of failure list.

**Checks:**
- Health/readiness endpoints exist and check real dependencies?
- Timeouts and retries on every outbound call; retries are idempotent-safe.
- Graceful shutdown (SIGTERM handling, draining).
- Unhandled promise rejections / uncaught exceptions crash the process?
- Background jobs: retry, dead-letter, alert on failure.
- With docker-compose locally: stop a dependency and observe behavior (Verified).
- If Sentry/monitoring is accessible: real error rates and top errors (Verified).

**Typical High:** no timeouts on third-party calls; process crashes on one bad request; no health check.

**Fix scope:** SLO docs freely. Resilience tests only on local/staging with approval. Code changes Phase 3.

---

## 7. Disaster Recovery — DR Architect

**Mission:** Make sure data and service can actually be restored, within agreed time and data-loss limits.

**Deliverable `07-disaster-recovery.md` — Backup + Tested Recovery Plan:**
- RTO/RPO targets per system (agree with user; propose defaults).
- Backup inventory: what's backed up (DB, file storage, secrets, config, IaC state), how, how often, where, retention, encryption, who can delete it.
- Recovery plan: step-by-step runbook for: DB loss, region/host loss, accidental deletion, ransomware/compromised account.
- **Restore test** result: the strongest evidence possible. Restore the latest backup (or a dump) into a scratch/local DB and verify row counts and app start (Verified). If not possible, mark Not assessed and give the exact test procedure.
- Gaps and actions.

**Checks:**
- Is there any backup config in IaC/hosting settings, or documented? (Observed / Inferred / ask the user.)
- Managed DB automated backups + point-in-time recovery enabled? (needs console access → otherwise ask.)
- User-uploaded files backed up (S3 versioning, etc.)?
- Backups stored in a separate account/region and protected from the same credentials as production?
- Has a restore ever been tested? An untested backup counts as "unknown", not as "exists".

**Typical Critical:** production data with no backups; backups never restored; backups deletable with the app's own credentials.

**Fix scope:** plan and runbooks freely. Never touch production backups or restore over real data; restores only into scratch environments with approval.

---

## 8. Observability — Principal Observability Engineer

**Mission:** Make problems visible quickly, with enough context to find the cause.

**Deliverable `08-observability.md` — Monitoring Dashboards + Alerts:**
- Current state: logging (structured? levels? correlation IDs?), metrics, tracing, error tracking, uptime checks.
- Dashboard design: for each critical journey, the panels (RED: rate, errors, duration; plus saturation) with the exact metric/query. If a tool is connected (Grafana, Datadog, Sentry, SigNoz, Honeycomb), create or export the dashboard as JSON/config; otherwise deliver the definitions as files.
- Alert rules: condition, threshold, window, severity, who gets paged, linked runbook (from expert 18). Tie alerts to SLOs from expert 5.
- Instrumentation gaps with exact code locations to add logs/metrics/spans.

**Checks:**
- Logging library and format; PII or secrets in logs (grep log calls with `password|token|email|card`).
- Request IDs propagated across services.
- Error tracking SDK initialized and capturing in production builds.
- Metrics endpoint / OpenTelemetry setup.
- Alerts exist and route to a human? (Observed in config or confirmed with user.)
- If a monitoring connector is available: verify dashboards/alerts actually exist and fire (Verified).

**Typical High:** errors only go to console; no alerting at all; secrets/PII in logs.

**Fix scope:** instrumentation code in Phase 3; creating dashboards/alerts in a real monitoring tool needs approval (it's an external system).

---

## 18. Incident Management — Head of SRE / Incident Lead

**Mission:** When something breaks, the team knows exactly what to do.

**Deliverable `18-incident-management.md` — Incident Runbooks + Response Plan:**
- Severity classification (SEV1–SEV4) with concrete examples from this project.
- Response plan: roles (incident commander, comms, fixer), escalation path and contacts (placeholders if unknown), communication templates (status page, customer message).
- Runbooks for the top likely incidents found by other experts (e.g. DB down, payment provider failing, deploy broke production, leaked key, queue backlog): detection signal → triage steps → mitigation → recovery → verification.
- Postmortem template (blameless) and corrective-action tracking.
- If past incidents/errors are available (Sentry, logs, tickets): a short analysis of the top recurring ones.

**Checks:**
- Can the team roll back a deploy quickly? (link to expert 10's rollback evidence)
- Are alerts (expert 8) linked to runbooks?
- On-call / who gets notified exists?
- Access to production for responders is controlled and logged.

**Typical High:** no rollback procedure; nobody gets notified on outage.

**Fix scope:** documents freely.
