---
title: "Epic 21 Proposal — Lead Gen Intelligence"
status: PROPOSED
date: 2026-08-11
---

## Epic 21: Lead Gen Intelligence `[PROPOSED]` (mới 2026-08-10)

### Story 21.1: Intent Signal Detection `[PROPOSED]`

As a salesperson,
I want to detect buying signals from companies (funding, hiring, tech stack, executive moves),
So that I can reach out at the right moment.

**Acceptance Criteria:**
**Given** a company in workspace, **When** signals are monitored, **Then** funding events, job postings, tech stack changes, and executive moves are detected and surfaced with signal type, confidence, source URL, and timestamp.
**Given** multiple signals for the same company, **When** aggregated, **Then** a composite lead score is calculated.
**Given** a signal is detected, **When** it is stored, **Then** it writes a `SignalEvent` row (with `client_id`, `workspace_id`) and a redacted `Memory` row of type `semantic` with tag `lead_signal`. The `Memory` row stores a summary with `source_input` pointing to the original `chunk_id`/`capability`/`input`; it does not duplicate the full public document (AD-27/AD-35).
**Given** a signal trigger is configured, **When** it fires, **Then** it uses an AD-33 `AlertRule` template with `capability_id` set to a registered signal capability (e.g. `funding.signal`, `hiring.signal`) and `notification_channels` from the allowed set (`in_app`, `telegram`, `email`). Signal-driven enrollment uses `target_sequence_id` and optional `target_step_id`; `sequence_enrollment` is not a notification channel.
**Given** a signal source is a scraper/connector, **When** it runs, **Then** it is registered as a `CapabilityRegistry` capability with `emits_signals=true` and `signal_types=[...]`. Metering: any LLM/token cost goes to `TokenUsage`; the signal-scan business event goes to `BillingEvent` with `usage_type = "signal_scan"`.
_Sources: Crunchbase, LinkedIn, company websites, job boards, news. FR-63. Governed by AD-31 (`client_id`), AD-33 (AlertRule engine), AD-37 (signal detection framework), AD-39 (signal-to-sequence triggers)._

### Story 21.2: Lead Scoring & Prioritization `[PROPOSED]`

As a sales manager,
I want leads scored and ranked by conversion likelihood,
So that my team focuses on the highest-value prospects.

**Acceptance Criteria:**
**Given** a set of leads, **When** scored, **Then** each lead receives a composite score based on fit (firmographics, technographics) and intent (signal strength, recency).
**Given** a lead score, **When** displayed, **Then** it shows score breakdown (fit vs intent), trend, and comparison to similar converted leads.
**Given** a lead score is computed, **When** it is stored, **Then** it writes a `LeadScore` row (with `client_id`, `workspace_id`, `id: UUID`) and a redacted `Memory` row of type `semantic` with tag `lead_score` (reuse `Memory` infrastructure; no separate lead-score vector store).
**Given** a lead score uses intent signals, **When** it reads signal data, **Then** it queries `SignalEvent` and `Memory` from Story 21.1 (AD-37), not a separate signal store.
**Given** a lead score is computed, **When** it incurs cost (e.g. LLM reasoning), **Then** the business event is recorded in `BillingEvent` with `usage_type = "lead_scoring"`; LLM token cost, if any, goes to `TokenUsage`.
_FR-64. Governed by AD-31 (`client_id`), AD-38 (lead scoring), AD-11 (Memory as first-class persistence), AD-37 (signal data)._

### Story 21.3: Enriched Contact Data `[PROPOSED]`

As an SDR,
I want verified contact data (email, phone) for my target accounts,
So that I can reach out to the right decision-makers.

**Acceptance Criteria:**
**Given** a company, **When** contact enrichment is requested, **Then** decision-maker names, titles, emails, and phone numbers are returned with verification status.
**Given** contact data, **When** verified, **Then** email is validated via waterfall (5+ providers) and phone via real-time validation (9+ providers).
**Given** verified contact data, **When** it is embedded or stored, **Then** it is passed through `app/services/pii/redact.py` with `context="lead_enrichment"` (per AD-25) and consent/legal basis fields are captured before persistence.
**Given** enrichment is successful, **When** a cost event is recorded, **Then** it writes a `BillingEvent` row with `usage_type = "contact_enrichment"` and debits `User.credit_micros_balance` via the existing wallet service (AD-8, AD-10, AD-42). `TokenUsage` is only used if an LLM/token step is involved.
**Given** enriched data is stored, **When** it is persisted, **Then** it writes `EnrichmentRequest` and `VerifiedContact` rows with `client_id`, `workspace_id`, and `id: UUID` (AD-31, AD-36).
_FR-65. Governed by AD-25, AD-31 (`client_id`), AD-36, AD-42 (`BillingEvent`)._

### Story 21.4: Outbound Prospecting Automation `[PROPOSED]`

As a sales team,
I want to automate personalized email outreach from any scraper source,
So that I can scale outbound without sacrificing quality.

**Acceptance Criteria:**
**Given** a lead list, **When** outreach is triggered, **Then** personalized messages are generated using lead context + ICP + intent signals.
**Given** outreach sequences, **When** configured, **Then** email sequences are supported in MVP. **LinkedIn and Zalo are deferred** until legal/sender setup gates close.
**Given** a workspace with connected scrapers/ connectors, **When** the user creates a lead list, **Then** leads can be sourced from any available scraper/connector that registers with `emits_leads=true` (FR-6 sources + Exa/Indeed/Walmart/BĐS/HR verticals as applicable).
**Given** a sales sequence is created, **When** it is persisted, **Then** it uses first-class `Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, and `SequenceRun` tables with `client_id`, `workspace_id`, and UUID `id` (AD-31, AD-39). `Sequence` is **not** an `Automation` subtype; only the Epic 6 scheduler/Celery pattern and notification dispatcher are reused.
**Given** an email is sent, delivered, bounced, or replied, **When** a notification is needed, **Then** it is dispatched through the Story 11.1 notification service with `NotificationChannel` extended to include `email_reply`, `email_delivered`, `email_bounced`; an inbound email handler (SES webhook or IMAP idle) is implemented as a capability.
**Given** a sequence trigger is based on a signal (e.g. funding event), **When** it fires, **Then** it uses an AD-33 `AlertRule` template with `capability_id` = the signal capability and `notification_channels` from the allowed set (`in_app`, `telegram`, `email`). Signal-driven enrollment uses `target_sequence_id` and optional `target_step_id`; `sequence_enrollment` is not a notification channel.
**Given** lead sources are displayed, **When** the user creates a lead list, **Then** the source list comes from `CapabilityRegistry` metadata (`emits_leads=true`), not a hard-coded list.
**Given** a sequence step is executed, **When** it incurs cost (e.g. email send, LLM personalization), **Then** it writes a `BillingEvent` row with the appropriate `usage_type`; LLM token cost, if any, goes to `TokenUsage`.
_FR-66. Governed by AD-31 (`client_id`), AD-33 (AlertRule), AD-39 (sequencer), AD-42 (`BillingEvent`)._

### Story 21.5: CRM Integration & Write-Back `[PROPOSED]`

As a sales operations manager,
I want lead intelligence data synced with our CRM,
So that reps work from a single source of truth.

**Acceptance Criteria:**
**Given** a CRM connection (Salesforce, HubSpot, Pipedrive), **When** lead data changes, **Then** it syncs bidirectionally.
**Given** a CRM provider is configured, **When** the user authorizes it, **Then** it reuses the existing `Connection` / OAuth model from FR-7 (AD-3); no new auth table is created.
**Given** a CRM sync runs, **When** it reads or writes data, **Then** it uses the `CrmConnection`/`CrmSyncLog` models with `client_id`, `workspace_id`, and UUID `id`, and the conflict-resolution audit log from AD-40.
**Given** lead scores or signals are pushed to CRM, **When** data is written, **Then** it writes through the shared `Memory`/`LeadScore` layer, not a separate CRM-only cache.
_FR-67. Governed by AD-3, AD-31 (`client_id`), AD-40._

### Story 21.6: Zalo Integration (Vietnam Market) `[DEFERRED]`

As a Vietnamese salesperson,
I want to communicate with leads via Zalo,
Because 81% of Vietnamese professionals use Zalo as their primary messaging platform.

**Status:** Deferred out of MVP per **AD-41**. UX and contracts keep Zalo disabled until legal/ToS/business messaging gates close.

**Acceptance Criteria (future):**
**Given** a Zalo OA connection, **When** configured, **Then** outreach sequences can include Zalo messages.
**Given** a lead with Zalo contact, **When** outreach is triggered, **Then** personalized Zalo messages are sent.
**Given** a Zalo reply, **When** received, **Then** it's logged in the lead's activity timeline.
**Comply** with Zalo's business messaging policies and Decree 356.
_FR-68._

### Story 21.7: Outcome-Based Pricing `[PROPOSED]`

As a sales team,
I want to pay per qualified meeting booked (not just per seat),
So that cost is tied to actual pipeline value delivered.

**Acceptance Criteria:**
**Given** a pricing plan, **When** selected, **Then** outcome-based option is available: pay per qualified meeting booked OR pay per lead enriched.
**Given** usage, **When** tracked, **Then** the dashboard shows cost-per-meeting and cost-per-lead metrics.
**Given** a meeting is booked or a lead is enriched, **When** an outcome event is recorded, **Then** it writes an `OutcomeEvent` row (with `client_id`, `workspace_id`, `billing_event_id`) and a `BillingEvent` row with `usage_type` of `outcome_meeting_booked` or `outcome_lead_enriched`, debiting `User.credit_micros_balance` via the existing wallet service (AD-8, AD-10, AD-42). `TokenUsage` is not used for business outcomes.
**Given** a pricing plan is configured, **When** it is persisted, **Then** it uses `PricingPlan` with `client_id`, `workspace_id`, and UUID `id` (AD-31, AD-42).
**Given** outcome pricing is enabled, **When** the user views the dashboard, **Then** the dashboard reuses or extends the usage/credit dashboard from Story 8.3 (AD-10).
_FR-69. Governed by AD-8, AD-10, AD-31 (`client_id`), AD-42._

---

## Epic 21 UX Contract Traceability (2026-08-11 refresh)

Tám pattern mới từ audit Origami đã được đưa vào UX contracts. Mapping dưới đây liên kết các pattern này với FRs, stories, và canonical contracts.

| ID | UX Pattern | FR / Story | Canonical Contract | Priority | Status |
|---|---|---|---|---|---|---|
| N1 | Sidebar onboarding checklist | Story 21.4 (SDR activation) | `ux-contract-sidebar-onboarding.md` | P1 | Contracted |
| N2 | Workspace mode switch (Outbound / Research / Content) | FR-66 / Story 21.4 | `ux-contract-workspace-mode-switch.md` | P1 | Contracted |
| N3 | Tables directory / lead lists library | FR-63 / Story 21.1 | `ux-contract-tables-directory.md` | P2 | Contracted |
| N4 | Inbox empty state + Email only; lead source from all scrapers | FR-66 / Story 21.4 | `ux-contract-lead-intelligence-panel.md` §8 | P0 | Contracted |
| N5 | Positive-reply notifications (email/Telegram only; Zalo disabled) | FR-66 / Story 21.4 | `ux-contract-positive-reply-notifications.md` | P1 | Contracted |
| N6 | Per-lead projected cost inline | FR-69 / Story 21.7 | `ux-contract-lead-intelligence-panel.md` §7 | P1 | Contracted |
| N7 | Source-specific table tabs (dynamic, all scraper/connector sources) | FR-63 / Story 21.1 | `ux-contract-lead-intelligence-panel.md` §2.1 | P2 | Contracted |
| N8 | “Connect a campaign” status chip | FR-66 / Story 21.4 | `ux-contract-lead-intelligence-panel.md` §5 | P1 | Contracted |

**Evidence:** `ux-research-origami-final-2026-08-11.md` + `../evidence/origami-*-2026-08-11.*`.

**Hand-off:** `implementation-artifacts/epic21-ux-handoff-2026-08-11.md`.

**Wireframes:** `ux-design/epic21-ux-wireframes-2026-08-11.md`.

**Open governance:** Zalo OA setup UI và LinkedIn automation **deferred** out of MVP; email outreach legal/ToS, vendor enrichment POC, PII pipeline, CRM sync scope, và outcome-pricing display vẫn pending trước khi chuyển sang implementation.

---

