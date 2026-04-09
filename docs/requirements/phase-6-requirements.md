# Phase 6 Requirements — Enterprise Identity & Pilot Governance

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **6 April 2026** |
| **Approved by** | Product Owner |
| **Parent document** | [`product-requirements.md`](product-requirements.md) Section 3 — **Phase 6** summary is included; **authoritative** stories and decisions remain in this document. |
| **Phase 6 lock** | **LOCKED** — Requirements and **Approved product decisions** below are frozen for Phase 6 execution as of the approval date. Scope, acceptance criteria, or material changes require a **written change request** and **Product Owner re-approval** (updated status block and revision note). |
| **Depends on** | Phase 5 complete and QA sign-off per [`docs/qa/phase-5-report.md`](../qa/phase-5-report.md) |

---

## Phase goal (one sentence)

**First enterprise pilots can authenticate through their corporate identity provider, meet IT and Finance expectations for auditability and evidence export, and operate the platform with clear security and operational visibility—without adding new core revenue analytics or ingestion capabilities beyond what Phases 1–5 already deliver.**

---

## What Phase 5 delivered that Phase 6 builds on

Phase 5 completed **enterprise intelligence expansion**: **hybrid forecasting** (imported + statistical baselines with separation from actuals and UI disclaimer), **profitability modeling** (cost facts, allocation rules, margin with traceability), **customer segmentation** (stored rules, materialized/replayable membership, semantic alignment including `forecast_total`), and **multi-currency** (single reporting currency per tenant, FX rate table with effective dates, consolidated views with native + reporting amounts and no silent FX). Backend and semantic layers are covered by automated tests; Phase 5 UI sits behind `VITE_ENABLE_PHASE5`.

Phase 6 **does not replace** that functionality. It **wraps** it in **enterprise-grade access and governance**: users sign in via **SSO** where required, **audit and retention** practices align with pilot and legal commitments, and **IT Admins** have **observable** integration and job health suitable for production runbooks. Parent PRD **Section 5 — approved decision 4** (application auth first, **SSO planned after core value**) and **Section 6 — pending stakeholder sign-off** (retention, pilot SSO/currency/tenancy expectations, Finance release windows) are **primary inputs** for this phase.

---

## User stories — Phase 6 only

Stories are numbered **6.1–6.4** for traceability. Format: **Given / When / Then**.

### Story 6.1 — Enterprise SSO (SAML 2.0 / OIDC)

**Given** my organization uses a corporate IdP and our pilot contract expects enterprise login, **when** IT Admin configures SSO and users authenticate, **then** they access the application through **SAML 2.0 or OIDC** (per agreed v1 scope) with **secure token handling** and **no hardcoded IdP secrets** in code.

**Acceptance criteria**

- **IdP configuration** is stored via settings or admin-managed records (metadata URL or XML for SAML; issuer/client IDs for OIDC) — **secrets** only through environment or secure configuration, consistent with parent PRD Section 4 NFRs.
- **User identity mapping** follows **Approved product decisions** (JIT with domain allowlist; optional invite-only mode per tenant).
- **Session security:** timeouts and logout behavior are documented; **break-glass** local login is **limited** to **Super Admin** / **service** paths per **Approved product decisions**; standard users use **SSO only** when SSO is enabled for the tenant.
- **Role and org claims:** **application roles remain authoritative**; optional **IdP group → role mapping** only via **explicit** admin-configured mappings (see **Approved product decisions**).
- **Failure modes:** IdP unreachable, invalid metadata, or token validation failure surfaces **clear, non-leaky** errors for users and **actionable** signals for IT (no raw stack traces to end users for expected failures).

---

### Story 6.2 — Audit export and retention alignment

**Given** Finance and IT must demonstrate control over imports, NL queries, HubSpot sync, and security-relevant events, **when** an authorized reviewer requests audit evidence, **then** they can **export** or **retrieve** audit records within the **operational retention** window and **documented** limits, with a path to **long-term** policy once legal signs off (parent PRD Section 6).

**Acceptance criteria**

- **Export scope** includes, at minimum, the event families already implied by Phases 1–5: **imports/batches**, **NL query audit** (who/when/interpretation summary per Phase 3), **HubSpot sync** events, and **SSO** login/security events introduced in Phase 6 — **exact field manifest** fixed in design.
- **Operational default** remains **365 days** in primary store (parent PRD Section 5 — approved decision 9) unless/until **legal** extends — Phase 6 **surfaces** retention policy in admin or docs so pilots are not surprised.
- **Export formats** are suitable for **Finance/IT** review (e.g., CSV or JSON Lines — **fixed in design**); exports are **authorized** per **`audit_export`** (see **Approved product decisions**) and **logged** as high-risk actions where appropriate.
- **Tamper-evidence:** exports reflect **append-only** semantics consistent with existing audit design (no silent edits to historical audit rows).
- **Jurisdiction-specific retention** beyond defaults remains **subject to legal** (parent PRD Section 6) — Phase 6 delivers **configurable export** and **documentation hooks**, not legal advice or automatic multi-jurisdiction compliance certification.

---

### Story 6.3 — Enterprise admin — security posture and pilot commitments

**Given** a dedicated deployment per enterprise customer (parent PRD Section 5 — approved decision 10), **when** IT Admin manages tenant-level security and pilot obligations, **then** they can **see and adjust** (within product limits) **SSO status**, **session-related settings** where exposed, and **pilot-relevant** items such as **reporting currency** visibility and **integration authority** (e.g., who may connect HubSpot, upload FX rates) **without** developer-only configuration files for routine changes.

**Acceptance criteria**

- **Admin-only** surfaces are **authenticated**, **role-gated**, and **audited** when they change security-sensitive settings.
- **Reporting currency** and other **pilot-contract** items called out in parent PRD Section 6 are **visible** and **change-controlled** per design (who may change, with audit trail).
- **No new anonymous** access paths; aligns with parent PRD Section 4 **Access control**.
- **Documentation** links or in-product copy reference **Finance freeze windows** (parent PRD Section 5 — decision 11 and Section 6) — **calendar enforcement** in-product is **optional** for Phase 6; **explicitly out of scope** if not listed below (see Out of scope).

---

### Story 6.4 — Operational visibility for integrations and background work

**Given** Excel ingest (Phase 1 batch jobs—not the optional Phase 7 matrix/workbook interop, which is gated by **`ENABLE_PHASE7`** per [`phase-7-requirements.md`](phase-7-requirements.md)), HubSpot sync, Celery jobs, and Phase 5 long-running work exist, **when** IT Admin monitors production health, **then** they have a **consolidated** view of **connection health**, **recent job outcomes**, and **actionable errors** (aligned with existing HubSpot connection status and batch semantics) suitable for **pilot runbooks**.

**Acceptance criteria**

- **HubSpot:** connection status and **recent sync** outcomes remain **visible**; Phase 6 **aggregates** or **improves navigation** rather than duplicating logic inconsistently.
- **Background jobs:** failed or stuck jobs (within existing Celery semantics) are **surfaced** with enough context to open **retry** or **support** workflows per existing product behavior.
- **No false “green”** when partial failures occurred — behavior matches **documented** Phase 4/5 failure semantics.
- **Performance:** admin views stay within reasonable latency; heavy listings may be **paginated** or **time-bounded**.

---

## Explicitly out of scope for Phase 6

- **Multi-tenant SaaS** productization (parent PRD Section 5 — approved decision 10: **dedicated deployment** remains the first enterprise model; multi-tenant is a **later** option).
- **New revenue analytics**, **new NL capabilities**, **new CRM connectors**, **new Phase 5 metric types** (forecasting, profitability, segments, FX) — Phase 6 is **governance and operations**, not new business analytics.
- **General ledger**, **tax**, **statutory filings** as system of record (unchanged from prior phases).
- **Full SCIM / lifecycle management** — **unless** explicitly pulled in by change request (**JIT with domain allowlist** per **Approved product decisions** is in scope; **full SCIM** is not).
- **Automatic FX rate market feeds** (Phase 5: optional API remains deferred unless change request).
- **In-product legal certification** (GDPR, SOC 2) — Phase 6 supports **operational** evidence export; **formal** attestation is **out of band**.
- **Replacing** dedicated deployment with **shared infrastructure** for the first pilot **unless** contract mandates — treat as **separate** initiative.

---

## Approved product decisions (Product Owner)

The following answers were **approved** on **6 April 2026** and supersede the prior “open questions” list in this document. They align with [`product-requirements.md`](product-requirements.md) Section 4–6 and **must** drive UX copy, QA acceptance, and pilot playbooks.

| # | Topic | Approved answer |
|---|--------|-----------------|
| 1 | **Enterprise pilot and SSO** | **SSO is required** for any **production** enterprise pilot—password-only is not acceptable for that segment. **Timeline:** SSO is a **release gate** before **production go-live** of the enterprise pilot; the **exact calendar date** is **contract-specific** (parent PRD Section 6). |
| 2 | **OIDC vs SAML** | **Implementation order:** **OIDC first**, then **SAML 2.0**, in the **same Phase 6 release**. If the **first signed pilot** is **SAML-only**, engineering may **reorder** to SAML-first for that pilot only—**both protocols** remain **in scope for Phase 6 GA** so sales is not blocked by IdP type. |
| 3 | **Local / password login** | **Retain** email/password as **break-glass** for **Super Admin** (and **non-interactive** automation paths such as API keys where they already exist). For SSO-enabled **production** tenants, **standard end users** authenticate via **SSO only**. Non-production environments may keep broader password use per environment policy. |
| 4 | **User provisioning** | **Default: JIT provisioning** when the user’s email **domain** is on the tenant’s **admin-managed allowlist**, with a **clear audit trail** on first login. **Optional tenant setting:** **invite-only** (disable JIT) for customers who require pre-registration. |
| 5 | **IdP groups and roles** | **Application roles remain the source of truth.** **Optional:** map **IdP group identifiers** to **app roles** through an **explicit admin-configured mapping**—no implicit “sync all groups” behavior in Phase 6. |
| 6 | **Who may export audit data** | Permission: **`audit_export`** (name may vary in implementation). **Default:** granted to **IT Admin**; tenant may assign to **Finance** or **security/auditor** personas for pilot needs. **Content:** include **user id and email** in exports for accountability; **no default PII redaction** in v1—if **legal** requires redaction for a jurisdiction, treat as a **targeted follow-up**, not a Phase 6 blocker. |
| 7 | **Retention vs SIEM** | **365 days** operational retention in the primary store remains the default (parent PRD Section 5 — decision 9). **Automated SIEM streaming / outbound webhooks** are **out of scope for Phase 6**; **manual export** (download) satisfies Story 6.2. **Streaming** requires a **change request** if a future pilot mandates it. |
| 8 | **Reporting currency** | **Default USD** (parent PRD Section 5 — decision 7). **Non-USD** is set at **tenant provisioning** or via the **existing admin path** already implied by Phase 5—Phase 6 **surfaces visibility**, not a new currency engine. |
| 9 | **Admin UI depth (Story 6.3)** | **Self-service in product** for **routine** pilot operations: **SSO/IdP configuration**, **domain allowlist**, **audit export**, **operational/integration health**, and **visibility** of **reporting currency** and security-sensitive toggles. **Infrastructure** (VPC, cluster secrets, certificate **mounting** at the edge) stays **DevOps**—but **IdP metadata URLs**, **rotating OIDC client secrets** stored in app-managed secure config, and **SAML cert uploads** should **not** require a code deploy when the product can safely hold them. |
| 10 | **Naming and packaging** | **Internal:** “Phase 6” in engineering roadmaps. **Customer-facing:** describe capabilities as **“Enterprise SSO & governance”** (or equivalent plain language) **when GA**—**no** separate SKU or branded “pack” until **pricing and packaging** decisions exist. |

---

## Decisions that need architect input before we proceed

These should be resolved in design review (**`@technical-architect`** per parent PRD Section 5 — schema governance) before locking Phase 6 implementation:

1. **SSO protocol implementation** — **OIDC first, SAML second** per **Approved product decisions**; concrete libraries, callback URLs, and **SAML** metadata handling for the **first pilot’s** IdP profile.
2. **Identity linking** — How **JIT** creates rows; **stable key** (IdP `sub` + issuer vs. email); **email change** and **merge** behavior; interaction with **invite-only** mode.
3. **Token and session model** — How OIDC/SAML assertions map to existing **JWT** session shape; **refresh**, **logout** (front-channel / back-channel), and **single logout** expectations.
4. **Secrets and key rotation** — Where IdP client secrets and SAML certificates live; **rotation** without full redeploy.
5. **Audit schema** — Whether **SSO events** and **audit exports** require new tables or extend existing audit storage; **volume** and **indexing** for 365-day queries.
6. **RLS and SSO** — Defense-in-depth: ensuring **tenant** and **org/BU** scoping remains correct when **principal** comes from IdP claims vs. local user record.
7. **Deployment topology** — Dedicated per customer: **per-tenant SSO config** storage vs. environment-only; impact on **CI/CD** and **secrets management**.
8. **Rate limiting and abuse** — SSO callback endpoints and **export** endpoints need **throttling** and **size limits** to avoid DoS or accidental data exfiltration.

---

*Aligned to [`product-requirements.md`](product-requirements.md). UX alignment with `@ux-ui-designer`; quality gates with `@quality-analyst`; identity and schema changes with `@technical-architect`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 6 draft: enterprise identity, audit export/retention alignment, enterprise admin, operational visibility; depends on Phase 5 QA GO. |
| 6 April 2026 | **APPROVED** by Product Owner; **Approved product decisions** finalized; Phase 6 requirements **LOCKED**; open questions **resolved**. |
| 6 April 2026 | Parent [`product-requirements.md`](product-requirements.md) Section 3 updated with Phase 6 summary. |
