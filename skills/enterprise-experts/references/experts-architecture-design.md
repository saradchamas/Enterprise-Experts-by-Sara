# Experts: Architecture & Design (1, 4, 6, 15, 16)

Each section lists: the mission, what the deliverable must contain, the checks with how to gather evidence, typical Critical/High findings, and what's safe to fix vs needs approval.

---

## 1. Architecture — Chief Architect / Principal Software Architect

**Mission:** Make the system's structure explicit and judge whether it's maintainable and extensible.

**Deliverable `01-architecture.md` — System Architecture + Diagrams:**
- Context diagram (users, external systems) and container/component diagram in **Mermaid** (C4 style), built from the actual code, not guessed.
- Module map: main folders/packages, their responsibility, who depends on whom.
- Data flow for the 2–3 most important journeys (sequence diagrams).
- Technology standards in use (languages, frameworks, versions, patterns).
- Architecture Decision Records: existing decisions you can infer (mark as "reconstructed"), plus new ADRs for any trade-off the Orchestrator resolves.
- Weaknesses and target-architecture proposal.

**Checks:**
- Layering / boundaries: does UI call the DB directly? Business logic in controllers/routes? Circular dependencies (run `npx madge --circular` / `pydeps` / `go vet` if available → Verified).
- Coupling: shared mutable state, god files (largest files by LOC — `discovery.json` lists them), duplicated logic across modules.
- Configuration: environment-specific config separated from code? 12-factor basics.
- Extensibility: how hard to add the next obvious feature? Name the files that would need touching.
- Dependency health: outdated major versions, abandoned libraries (`npm outdated`, `pip list --outdated`).

**Typical High:** business rules duplicated in frontend and backend with drift; circular module dependencies in core; single file >2,000 LOC containing most logic.

**Fix scope:** documentation, diagrams and ADRs freely. Refactors only in Phase 3 with approval; prefer small, test-covered moves.

---

## 4. Scalability — Principal Distributed Systems Engineer

**Mission:** Find out how many users/requests the system can handle and what breaks first.

**Deliverable `04-scalability.md` — Load Testing + Capacity Plan:**
- Load test plan: target endpoints/journeys, user model, ramp profile, environment (local/staging — never production).
- Load test results (if run): throughput, p50/p95/p99 latency, error rate per stage, the breaking point and the bottleneck observed.
- Capacity model: current capacity estimate, the first bottleneck (DB connections, CPU, a lock, a third-party rate limit), and what to change at 2×, 10×, 100× load.
- Concurrency and consistency review.
- If the test could not be run: a ready-to-run script (k6/Locust/autocannon) committed to `evidence/` and the exact command, marked Not assessed for the numbers.

**Checks:**
- Statefulness: in-memory sessions, local file uploads, in-process caches/cron that break with >1 instance (Observed).
- Concurrency: race conditions on counters/stock/balances (read-modify-write without transaction or lock), idempotency of payment/webhook handlers, duplicate job execution.
- Async work: long operations done in the request path that should be queued; queue retry/dead-letter config.
- DB connection pool sizing vs expected instances.
- Load test (Verified) only on an approved local/staging target: k6/autocannon/Locust with a ramp; stop at error rate >5% or p95 > agreed target.

**Typical Critical/High:** double-spend / overselling race; webhooks not idempotent; app cannot run more than one instance.

**Fix scope:** writing the load-test script is free. Running it needs an approved target. Architectural changes in Phase 3 only.

---

## 6. Database — Principal Database Architect

**Mission:** Ensure the schema protects data integrity and queries are fast.

**Deliverable `06-database.md` — Database Audit + Optimized Schema:**
- ER diagram (Mermaid `erDiagram`) from the real schema/migrations/ORM models.
- Integrity review: keys, foreign keys, constraints, nullability, types, cascades.
- Index review: existing indexes vs query patterns found in the code; proposed indexes with the query each serves.
- Slow/risky query list (N+1, full scans, unbounded queries, missing pagination).
- Migration safety review and proposed migration plan (the optimized schema as reviewable migration files, not applied).

**Checks:**
- Find schema sources: migrations folder, `schema.prisma`, ORM models, `*.sql` (discovery lists them).
- Missing FKs / unique constraints where business rules imply them (e.g. one active subscription per user).
- Money as float; timestamps without timezone; enums as free text.
- Queries in loops (N+1) — grep ORM calls inside `for`/`map`.
- If a local DB is available: run `EXPLAIN (ANALYZE)` on the top queries against seeded data (Verified). Never run on a production database.
- Destructive migrations (DROP, column type changes without backfill) and whether migrations are reversible.
- Transactions around multi-write operations.

**Typical Critical/High:** destructive migration pending; no transaction around payment + order writes; money stored as float; missing index on the hottest lookup.

**Fix scope:** propose migrations as files. Applying any migration to a real DB needs explicit approval; local/disposable DB is fine.

---

## 15. APIs — Principal API Architect

**Mission:** Make every interface a clear, versioned, validated contract.

**Deliverable `15-apis.md` — API Contracts + Validation Tests:**
- Endpoint inventory (method, path, auth, request/response shape, status codes) extracted from routes.
- OpenAPI spec: validate the existing one against the code, or generate `openapi.yaml` from the routes (marked "generated — review").
- Consistency review: naming, pagination, error format, status codes, versioning strategy.
- Contract/validation tests: tests that call endpoints and assert schema + status (added in Phase 3 or delivered as files), and their results.
- Integration contracts with external services (what you call, timeouts, retries, failure behavior).

**Checks:**
- Input validation on every write endpoint (zod/joi/pydantic/class-validator) — list endpoints without it.
- Auth on every non-public endpoint; authorization (object-level: can user A read user B's order by changing the ID?).
- Rate limiting, request size limits, CORS config.
- Error responses leak stack traces / internals?
- Spec drift: endpoints in code but not in spec and vice versa.
- If the app runs locally: hit endpoints with valid/invalid payloads (Verified).

**Typical Critical/High:** IDOR (object-level authorization missing); unauthenticated admin endpoint; no validation on write endpoints.

**Fix scope:** spec and tests freely (tests are new files). Changing API behavior needs Phase 3 approval because clients may depend on it.

---

## 16. Business Logic — Principal Domain Architect

**Mission:** Make sure the code does what the business actually needs, without contradictions.

**Deliverable `16-business-logic.md` — Business Rules + Workflow Validation:**
- Domain model: core entities, their relationships and invariants (in plain language + Mermaid class diagram).
- Business rules catalogue: each rule, where it's implemented (file:line), whether it's tested.
- State machines for key entities (order, shipment, subscription, invoice…) as Mermaid `stateDiagram`, including illegal transitions the code currently allows.
- Workflow validation: walk the main flows end to end, list edge cases (cancellation after payment, partial refunds, timezones, rounding, retries) and the result of testing each.
- Open questions for the business owner (the things only a human can decide).

**Checks:**
- Same rule implemented in two places with different values (fees, limits, discounts).
- Status fields changed from many places without a central transition function.
- Edge cases: zero/negative quantities, currency rounding, time zones and DST, concurrent edits, deleted/archived references.
- Write or run tests for the critical rules (Verified) — e.g. pricing calculation table tests.
- Use a questioning stance (like the grill-me skill): list assumptions and confirm the ambiguous ones with the user rather than guessing.

**Typical Critical/High:** price/fee calculation wrong or inconsistent; illegal state transition possible (shipped → pending); money-affecting rule untested.

**Fix scope:** rule tests freely; behavior changes need approval because they change business outcomes.
