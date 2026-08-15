# Project: Epic 21 — Lead Gen Intelligence

## Architecture & Tenancy Foundation
- **Tenancy (AD-31)**:
  - `workspace_id: Integer` (FK workspaces.id) as primary tenant partition.
  - `client_id: CITEXT` (natural key of vertical_clients.client_id, nullable) as sub-tenant partition.
  - Transaction-local GUC via `set_request_tenant_context(workspace_id, client_id)`.
  - PostgreSQL Row-Level Security (RLS) policies on all tables.
  - Composite indexes on `(workspace_id, client_id, ...)` across all query lookup paths.
- **Provenance Tracking (AD-44 / AD-47)**:
  - `Memory.source_uuid: UUID` + `Memory.source_entity_type: String` for Lead Intelligence entities (`signal_event`, `lead_score`, `verified_contact`, `sequence_run`, `outcome_event`).
  - `Memory.source_id: Integer` preserved for legacy chat/document tracking without type coercion.
- **PII Governance (AD-25 / AD-49)**:
  - `VerifiedContact` acts as authoritative PII vault, encrypting raw contact details at rest using Fernet cipher (`TokenEncryption`).
  - All derived memory embeddings, search chunks, audit logs, and non-privileged UI surfaces run through `redact_pii(text, context="lead_enrichment")`.
- **Automation & Alerts (AD-43)**:
  - Standalone `alert_rules` table with 1-minute Celery Beat polling (`alert_engine_tick`), snapshot diffing, and domain action generation (`EnrollmentRequested` -> `SequenceRun`).
- **Ledgering & Metering (AD-42)**:
  - Separation of LLM cost tracking (`TokenUsage`) and non-LLM business event ledger (`BillingEvent` with idempotent partial unique indexes).

---

## Feature Inventory & Story Status Matrix

| # | Story | Description | Milestone | Current Status | Worktree / Branch / Source |
|---|-------|-------------|-----------|----------------|----------------------------|
| 1 | Story 21.1 | Intent Signal Detection & Subscriptions | Milestone R1 | **DONE / PASS** | Main repo (`app/lead_intelligence/signals/`, 40 tests pass) |
| 2 | Story 21.2 | Lead Scoring Engine & ICP Configuration | Milestone R1 | **DONE / PASS** | Main repo (`app/lead_intelligence/scoring/`, integration tests pass) |
| 3 | Story 21.3 | Contact Enrichment & PII Governance | Milestone R2 | **IN_DEV / INTEGRATING** | `/Users/luisphan/Documents/GitHub/wt-21-3-enriched-contact-data` (`feat/story-21-3-enriched-contact-data`) |
| 4 | Story 21.4 | Outbound Prospecting Sequencer | Milestone R3 | **READY-FOR-DEV** | Next in execution pipeline |
| 5 | Story 21.5 | CRM Integration & Write-Back | Milestone R4 | **IMPLEMENTED (In Worktree)** | `/Users/luisphan/Documents/GitHub/nowing-worktree-21.5` (`story-21.5-crm`) |
| 6 | Story 21.6 | Multi-Channel Prospecting Delivery | Milestone R3 | **READY-FOR-DEV** | Follows Story 21.4 |
| 7 | Story 21.7 | Outcome-Based Pricing & ROI Tracking | Milestone R5 | **READY-FOR-DEV** | Follows Story 21.6 |

---

## Milestone Decomposition & Sequential Execution Roadmap

Strict BMad Pipeline Sequence:
1. `bmad-create-story`: Validate / prepare story spec.
2. `bmad-testarch-atdd`: Write red-phase acceptance tests.
3. `bmad-dev-story`: Implement code to make tests green.
4. `bmad-code-review`: Adversarial review + mutation testing check + Forensic Integrity Audit.
5. `bmad-sprint-status`: Record milestone completion.

### Milestones Table

| # | Milestone | Scope / Stories | Dependencies | Status |
|---|-----------|-----------------|--------------|--------|
| M1 | Intent & Scoring (R1) | Story 21.1, Story 21.2 | None | **DONE** |
| M2 | Contact Enrichment & PII (R2) | Story 21.3 | M1 | **IN_PROGRESS** (Integrating & Review) |
| M3 | Outbound Sequencer & Multi-Channel (R3) | Story 21.4, Story 21.6 | M2 | **READY-FOR-DEV** |
| M4 | CRM Integration (R4) | Story 21.5 | M3 | **READY-FOR-INTEGRATION** (Worktree 21.5) |
| M5 | Pricing & ROI Tracking (R5) | Story 21.7 | M4 | **PLANNED** |
| M6 | Final Verification & Quality Gates | All Stories 21.1-21.7 full suite | M5 | **PLANNED** |
