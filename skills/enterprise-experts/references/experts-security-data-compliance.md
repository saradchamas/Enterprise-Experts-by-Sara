# Experts: Security, Data & Compliance (2, 14, 19)

---

## 2. Security — Principal Security Architect

**Mission:** Find real, exploitable weaknesses and get them fixed and re-verified.

**Deliverable `02-security.md` — Security Audit + Remediation Report:**
- Security architecture summary: authentication, authorization model (RBAC/ABAC), session/token handling, secrets management, encryption in transit/at rest.
- Threat model (STRIDE) for the main assets and trust boundaries, as a table: asset, threat, existing control, gap, severity.
- Findings with evidence, exploit scenario in one sentence, and fix.
- Remediation report: for each fixed item, what changed and the re-test that proves it.
- Residual risk list.

**Checks (with evidence method):**
- Committed secrets: the discovery secret scan (Observed; confirm each hit by reading the file); also check git history if allowed (`git log -p -S 'sk_live' --all | head`). Mask values.
- Dependency vulnerabilities: `npm audit --omit=dev`, `pip-audit`, `osv-scanner`, `govulncheck` (Verified). Report only reachable/production deps as High+.
- Static analysis: `semgrep --config auto` if installable (Verified), then triage — don't dump raw output.
- Injection: SQL built by string concatenation, `eval`, shell exec with user input, unsafe deserialization, SSRF (user-controlled URLs fetched server-side), path traversal in file access.
- AuthN: password hashing (bcrypt/argon2, not md5/sha1), JWT secret strength and algorithm pinning, token expiry, refresh rotation, brute-force protection, MFA for admin.
- AuthZ: object-level checks (IDOR), admin-route protection, multi-tenant isolation (tenant ID from token, not from request body).
- Web: CORS (`*` with credentials), CSRF on cookie auth, security headers (CSP, HSTS), XSS sinks (`dangerouslySetInnerHTML`, `v-html`, `innerHTML`), cookie flags.
- Transport & storage: HTTPS enforced, sensitive fields encrypted, PII in logs.
- Uploads: type/size validation, storage outside web root, scanning.
- If the app runs locally: try the top exploit paths against it (Verified), e.g. call another user's resource ID.
- If the `claude-security` skill/plugin is installed in this session, use it for a deeper scan and include its verified results.

**Typical Critical:** live secret in repo; auth bypass; SQLi; IDOR on personal/financial data; unauthenticated admin.

**Fix scope:** Phase 3 with approval. Secret rotation must be done by the user (you can't rotate keys in their provider) — give exact steps and mark the finding `open` until they confirm.

---

## 14. Data Governance — CDO / Data Governance Lead

**Mission:** Know what data exists, who owns it, how good it is, and how it's protected through its lifecycle.

**Deliverable `14-data-governance.md` — Data Quality + Governance Report:**
- Data catalog: datasets/tables, description, owner (or "unassigned"), classification (Public / Internal / Confidential / Restricted-PII/financial/health).
- Ownership matrix (data domain → owner → steward).
- Data quality assessment: completeness, uniqueness, validity, consistency, freshness — with measured results if a dataset/DB copy was available.
- Access & permissions review: who/what can read/write sensitive data.
- Retention & deletion policy proposal; lineage for key reports (source → transform → output).

**Checks:**
- Classify fields from schema: names, emails, phones, addresses, national IDs, payment, health → mark sensitive.
- Validation at input vs in DB constraints.
- If sample data or a local DB is available: run quality queries (null rates, duplicates on natural keys, out-of-range values, orphan rows) (Verified). Never pull production data into the review folder; record aggregate numbers only.
- Soft-delete vs hard-delete; ability to fulfil "delete my data" requests.
- Backups and exports containing PII — where they go.
- Analytics/BI pipelines copying PII.

**Typical High:** no owner for customer data; PII copied to analytics/third parties without need; no way to delete a user's data.

**Fix scope:** catalog and policies freely (documents). Changes to data or permissions need approval.

---

## 19. Compliance — Chief Compliance Officer

**Mission:** Identify which regulations and standards likely apply and where the project falls short — for a qualified human to confirm.

**Deliverable `19-compliance.md` — Compliance Gap Assessment:**
- Applicability screen: based on users' countries, data types, industry and sales model, which frameworks are likely relevant (e.g. GDPR, Lebanon's Law 81/2018 on electronic transactions and personal data, HIPAA, PCI DSS, SOC 2, ISO 27001, local medical/financial rules). Search the web for current requirements when relevant and cite sources.
- Control-by-control gap table: requirement → evidence found in project → status (met / partial / gap / unknown) → owner → action.
- Audit evidence index: which deliverables/evidence items from the other experts support each control.
- Risk register for compliance risks.
- Clear note: this is a gap assessment, not legal advice; list the items that need a lawyer or compliance officer.

**Checks:**
- Privacy policy / terms / consent capture present? Cookie consent for EU users?
- Data subject rights (access, export, deletion) implementable?
- Card data: does the app touch PANs or delegate to a PCI-compliant processor (Stripe Elements etc.)?
- Audit logging of admin and sensitive actions.
- Data residency / cross-border transfers to third-party processors (list them from the code: SDKs, APIs).
- Reuse findings from Security (2), Data Governance (14), DR (7), Incidents (18) as control evidence rather than re-checking.

**Typical High:** handling health or card data without the corresponding controls; no consent or deletion mechanism for EU personal data.

**Fix scope:** documents only. Never claim the project "is compliant" — only "no gaps found in the checked controls".
