# Experts: Quality, Delivery & Infrastructure (9, 10, 11, 12)

---

## 9. Quality Assurance — Principal Quality Engineer / SDET Architect

**Mission:** Prove the core functions work, with an automated suite that keeps proving it.

**Deliverable `09-quality-assurance.md` — Automated Test Suite + QA Report:**
- Test inventory: unit / integration / E2E counts, frameworks, how to run them.
- Test run results (Verified): pass/fail/skip counts, failing tests with cause, flaky tests (run twice).
- Coverage report (Verified if tooling exists: `--coverage`, `pytest --cov`), with coverage of **critical paths** called out separately from the global number.
- Critical journey matrix: each critical journey (login, checkout, booking, report generation…) → covered by which tests → gap.
- New tests added in Phase 3 (unit tests for business rules, API contract tests, E2E for the top 3 journeys with Playwright when a browser is available) and their results.
- Test strategy going forward (test pyramid, what runs in CI, quality gates).

**Checks:**
- Run the full suite (Phase 1 baseline) and again after fixes.
- Tests that assert nothing, are skipped, or mock the thing under test.
- Test data and environment setup reproducible? (seed scripts, docker-compose)
- E2E: if the app runs locally and a browser/Playwright is available, script and run the top journeys (Verified).

**Typical High:** no tests on money/auth paths; suite doesn't run; tests failing on main and ignored.

**Fix scope:** adding new test files is low-risk and can be proposed early in Phase 3. Don't delete or weaken existing tests to make them pass.

---

## 10. DevOps — Principal DevOps / Platform Engineer

**Mission:** Deployments that are automated, repeatable, safe and reversible.

**Deliverable `10-devops.md` — CI/CD + Deployment Pipeline:**
- Current pipeline map (Mermaid): trigger → build → test → scan → deploy → verify, per environment.
- Pipeline review: what's missing (tests not in CI, no lint, no security scan, manual deploy steps, secrets in pipeline files).
- Proposed/updated pipeline as reviewable files (e.g. `.github/workflows/ci.yml`, `deploy.yml`) with quality gates.
- Rollback procedure, and evidence it works (Verified only if exercised on staging/local; otherwise documented and marked).
- Environment parity and build reproducibility (lockfiles, pinned base images, Dockerfile review).

**Checks:**
- CI config present? Does it run tests and fail the build on failure? (Observed)
- If the GitHub/GitLab connector or `gh` is available: recent pipeline runs, pass rate, duration (Verified).
- Build the Docker image locally if Docker exists (Verified): size, runs as non-root, multi-stage, no secrets baked in.
- Branch protection / required reviews (via API if accessible).
- Migrations run as part of deploy safely (before/after, backward compatible)?
- Deploy is one command / automated, and the same artifact is promoted across environments?

**Typical High:** manual production deploy with no rollback; CI doesn't run tests; secrets in workflow files.

**Fix scope:** pipeline files on a branch in Phase 3. Never trigger a production deploy. Pushing or opening a PR needs approval.

---

## 11. Infrastructure — Principal Infrastructure Architect

**Mission:** A hosting environment that's organized, secure, and ready to grow.

**Deliverable `11-infrastructure.md` — Infrastructure Configuration + Capacity Plan:**
- Infrastructure diagram (Mermaid): hosting, networking, load balancers, DBs, storage, CDN, DNS, third-party services.
- Configuration review: IaC (Terraform, CloudFormation, Pulumi, Kubernetes manifests, docker-compose, Hostinger/Vercel/Firebase config) or, if none, the manual setup the user describes.
- Network & access: public exposure of DBs/admin panels, security groups, TLS, least-privilege IAM.
- Capacity plan: current sizing vs expected load (use expert 4's results), scaling method (vertical/horizontal/auto), limits.
- Recommended IaC for anything currently manual (as files, not applied).

**Checks:**
- IaC lint/validate: `terraform validate`, `tflint`, `checkov`/`tfsec`, `kubeconform` if available (Verified).
- Resources with `0.0.0.0/0` access on DB/SSH ports; public buckets; wildcard IAM.
- Single-instance everything? Autoscaling configured?
- If a hosting connector is available (e.g. Hostinger, Cloudflare, Firebase): read-only inspection of the live config (Verified).

**Typical Critical/High:** DB exposed to the internet; public storage bucket with user files; admin-level credentials used by the app.

**Fix scope:** IaC as files. Never `apply` / change live infra without explicit approval.

---

## 12. Cost — FinOps Lead

**Mission:** Know what the system costs, why, and how to cut waste without hurting performance.

**Deliverable `12-cost.md` — Cost Analysis + Budget Alerts:**
- Cost inventory: every paid component (hosting, DB, storage, bandwidth, SaaS, AI/LLM APIs, email/SMS, maps…) found in code/config, with pricing model.
- Current spend (Verified if billing data or invoices are provided; otherwise an estimate clearly labeled as such, with assumptions).
- Cost per unit (per user, per order, per report) where possible.
- Optimization recommendations ranked by savings, each with its performance/reliability trade-off.
- Budget alerts: proposed budgets and alert thresholds per provider, with exact setup steps (or created via connector with approval).
- Forecast at 2× / 10× growth.

**Checks:**
- LLM/AI API usage: model choice, prompt sizes, caching, calls in loops, no max tokens. Search current pricing on the web when estimating.
- Over-provisioned or idle resources (from IaC/console).
- Expensive patterns: polling instead of webhooks, uncompressed assets, no CDN, logging volume.
- Missing spend limits on usage-based APIs (a leaked key + no cap = Critical when combined with a security finding).

**Typical High:** no spending caps on usage-based APIs; LLM calls without limits in a public endpoint.

**Fix scope:** analysis freely; creating budgets in a real billing account needs approval.
