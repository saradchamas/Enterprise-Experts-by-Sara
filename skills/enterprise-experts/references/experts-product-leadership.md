# Experts: Product & Leadership (13, 17, 20, 21, 22, 23)

The synthesis experts (17, 21, 22, 23) run last and **reuse** the other experts' findings and evidence rather than redoing the work. Reference finding IDs (e.g. SEC-001) instead of restating them.

---

## 13. UI/UX — Principal Product Designer / UX Architect

**Mission:** A clearer, easier, accessible experience.

**Deliverable `13-ui-ux.md` — UX Audit + Design Improvements:**
- User journey maps for the top 3–5 journeys, with friction points.
- Heuristic evaluation (Nielsen's 10) with severity per issue and screenshot/file reference.
- Accessibility audit (WCAG 2.2 AA): automated scan results (axe/Lighthouse if a browser is available → Verified) plus manual checks (keyboard navigation, focus, contrast, labels, alt text).
- Responsive/mobile review.
- Design-system consistency: colors, typography, spacing, components duplicated with variations.
- Improvement proposals: concrete before/after descriptions; implemented changes in Phase 3 with screenshots.

**Checks:**
- Run the app and walk the journeys (Verified with screenshots) when possible; otherwise review components/templates (Observed).
- Empty, loading and error states exist for main screens.
- Forms: validation messages, labels, input types on mobile.
- RTL/Arabic support if the audience needs it.

**Typical High:** critical journey blocked on mobile; forms unusable by keyboard/screen reader; no error states on payment.

**Fix scope:** UI changes in Phase 3. If the project has no UI, mark `not_applicable`.

---

## 17. Documentation — Staff Technical Writer / Documentation Architect

**Mission:** Anyone joining can understand, run, change and operate the system.

**Deliverable `17-documentation.md` — Complete Technical Documentation:**
- Documentation audit: what exists (README, docs/, API docs, runbooks, ADRs, CLAUDE.md) vs what's needed; accuracy check of existing docs against code (e.g. does the README's setup actually work? → Verified by following it in Phase 1).
- The documentation set, written or updated (as files in the project's `docs/` on the review branch, or in the review folder):
  - README: purpose, quick start, configuration/env vars (names only), scripts.
  - Architecture overview (link expert 1), API reference (link expert 15's OpenAPI), deployment guide (expert 10), operations runbooks (experts 7, 18), data dictionary (experts 6, 14), ADR index.
  - `CLAUDE.md` for future AI-assisted development: commands, conventions, guardrails.
- Doc maintenance plan (where docs live, who updates, review in PRs).

**Checks:** follow setup instructions from scratch; list every env var used in code vs documented; dead links; outdated commands.

**Fix scope:** writing docs is safe and can be done as part of the deliverable (on the review branch).

---

## 20. Analytics — Head of Product Analytics

**Mission:** Measure whether the product works for the business and its users.

**Deliverable `20-analytics.md` — KPI Dashboards + Product Reports:**
- KPI tree: north-star metric → input metrics → the events/data that measure them (agree with user; propose from the product's purpose).
- Tracking audit: analytics tools in code (PostHog, GA4, Mixpanel, Segment…), events currently tracked, naming consistency, gaps for the KPI tree, PII sent to analytics (coordinate with expert 14).
- Tracking plan: event name, trigger, properties, owner.
- Dashboard definitions (funnel, retention, activation, feature usage) with the exact queries/metrics; built in the connected tool when available and approved, or delivered as specs/SQL.
- Product report: if data is available, the actual numbers and insights (Verified); otherwise the report template ready to fill.

**Checks:** grep for tracking calls; compare to the KPI tree; check consent before tracking for regulated users.

**Fix scope:** tracking code in Phase 3; dashboards in external tools need approval.

---

## 21. Technology Strategy — CTO

**Mission:** A clear technical direction aligned with the business.

**Deliverable `21-technology-strategy.md` — Technology Roadmap:**
- Current-state summary (from all experts): strengths, risks, debt hotspots.
- Strategic decisions needed (build vs buy, monolith vs services, platform/hosting choice, framework upgrades, AI usage), each with options, trade-offs, cost, risk, and a recommendation framed for the user's decision.
- Technology roadmap in horizons: **Now (0–1 month: launch blockers)**, **Next (1–3 months)**, **Later (3–12 months)**, each item linked to finding IDs and business value.
- Technology risk register (vendor lock-in, end-of-life versions, key-person dependency, licensing).
- Challenge assumptions (grill-me stance): list the 3–5 assumptions the roadmap depends on and ask the user to confirm them.

**Checks:**
- End-of-life or unsupported runtime/framework versions (compare versions in manifests with vendor support dates; search the web for current dates and cite them).
- Dependency freshness: run the stack's outdated command where one exists (`npm outdated`, `pip list --outdated`, `go list -u -m all`) through `EE evidence run`.
- Vendor lock-in: which providers the code is tied to (from discovery's paid services, IaC and SDK imports) and what leaving would cost.
- Licences of key dependencies that conflict with how the product is sold.
- Every roadmap item traces to a finding ID or an intake answer; an item with neither is an opinion and is labelled as one.
- Does the roadmap fit the team and deadline given in the intake?

---

## 22. Technical Leadership — Distinguished Engineer / Chief Architect

**Mission:** Cross-cutting quality review — consistency, debt and decision quality across the whole codebase.

**Deliverable `22-technical-leadership.md` — Architecture + Code Review Reports:**
- Code review report: sampled review of the most critical and most changed modules (`git log --format= --name-only | sort | uniq -c | sort -rn | head` → churn hotspots, Verified), covering correctness, error handling, readability, duplication, typing, consistency.
- Static quality metrics where tooling exists (lint errors, type-check errors via `tsc --noEmit`/`mypy`, complexity) (Verified).
- Technical debt register: item, location, interest (what it costs now), principal (effort to fix), priority.
- Cross-expert consistency check: conflicting recommendations between experts and how they were resolved (ADR references).
- Engineering standards proposal (coding conventions, review checklist, definition of done).
- Review of any Phase 3 changes made by other experts — a second pair of eyes before the final report.

**Checks:**
- Churn hotspots from git history (command above), then read the top files.
- Lint and type-check results using the stack's commands from discovery, through `EE evidence run`.
- Error handling in the critical journeys named in the intake: swallowed exceptions, missing timeouts, inconsistent error shapes.
- Duplication and dead code in the largest files listed by discovery.
- Consistency across modules: naming, folder structure, how config and logging are done.
- Every other expert's recommendations read side by side for contradictions.

---

## 23. Engineering Delivery — VP of Engineering

**Mission:** Turn all findings into an executable, trackable plan.

**Deliverable `23-engineering-delivery.md` — Engineering Plan + Progress Tracking:**
- Consolidated backlog of all open findings, de-duplicated, each with: ID, title, severity, owner role, effort (S/M/L), dependencies, acceptance criteria (= the verification that will prove it fixed).
- Milestone plan: **Launch-blockers** (all Critical + required Highs) → **Hardening** → **Scale**, with sequencing that respects dependencies.
- Progress tracking: table of status per item (open / in progress / fixed-verified / accepted), and the % of Critical/High closed. Update it whenever Phase 3 fixes land.
- Team/process recommendations: roles needed, review process, CI gates, definition of done.
- If the user wants tickets and an issue-tracker connector (Jira/Linear/GitHub) is available: create them after approval, link finding IDs. Don't change a ticket's status until the whole piece of work is finished.
- Delivery metrics to track going forward (deployment frequency, lead time, change-failure rate, MTTR).

**Checks:**
- Every open finding in `findings.json` appears exactly once in the backlog, with an owner role and acceptance criteria.
- No backlog item depends on an item scheduled after it.
- Commit and release cadence from git history (`git log --date=short --format=%ad | sort | uniq -c`) as a baseline for delivery metrics.
- Whether work is reviewed before merge (branch protection or PR history, if the repository host is accessible).
- The launch-blocker milestone contains every Critical and every High the scorecard lists as a blocker or condition.
- The plan is achievable with the team and deadline from the intake; say so plainly if it is not.
