# Epic 21 Engineering Hand-off — Lead Intelligence (2026-08-11)

**Date:** 2026-08-11
**Author:** Architecture / PO
**Audience:** Backend, Frontend, QA, DevOps
**Status:** ✅ **Architecture FIT** — implementation can be sliced after governance gates close.

This hand-off complements the UX hand-off (`epic21-ux-handoff-2026-08-11.md`) with the canonical technical tasks, data model, API shape, and launch gates.

---

## 0. Must-read before starting

- `epic21-ux-handoff-2026-08-11.md`
- `../architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-31, AD-33, AD-36–AD-42)
- `../epics.md` (Story 21.1–21.7)
- `../ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`
- `../ux-designs/ux-Nowing-2026-07-22/ux-contract-positive-reply-notifications.md`

---

## 1. Data model

Every new table below uses UUID `id`, `workspace_id`, and nullable `client_id` (AD-31). Composite indexes on `(workspace_id, client_id)`.

### Core lead tables

```python
class Lead(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    source: str                 # capability_id from CapabilityRegistry
    source_url: str | None
    source_chunk_id: UUID | None
    company_name: str
    domain: str | None
    industry: str | None
    fit_score: float | None
    intent_score: float | None
    composite_score: float | None
    status: str                 # new / enriched / contacted / replied / meeting / disqualified
    enriched: bool
    consent_status: str | None  # explicit / legitimate_interest / none
    legal_basis: str | None
    created_at: datetime

class LeadSource(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    capability_id: str          # e.g. 'vn_jobs.aggregate'
    provider: str
    enabled_for_leads: bool
    last_ingest_at: datetime | None
    lead_count: int
```

### Enrichment (AD-36)

```python
class EnrichmentRequest(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    lead_id: UUID
    status: str                 # pending / processing / completed / failed
    provider_results: JSONB
    cost_micros: int
    created_at: datetime

class VerifiedContact(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    lead_id: UUID
    email: str | None           # redacted before display
    phone: str | None           # redacted before display
    verification_status: str    # unverified / verified / low_confidence
    confidence: float
    source_provider: str
```

### Signals (AD-37)

```python
class SignalEvent(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    company_name: str
    signal_type: str            # funding / hiring / tech_stack / executive_move / news
    source_url: str
    chunk_id: UUID | None       # pointer to chainlens-research Chunk
    confidence: float
    detected_at: datetime
    processed: bool

class SignalSubscription(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    signal_types: list[str]
    notification_channels: list[str]
```

### Lead scoring (AD-38)

```python
class LeadScore(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    lead_id: UUID
    company_name: str
    score: float
    fit_score: float
    intent_score: float
    factors_json: JSONB
    computed_at: datetime
```

### Sequencer (AD-39)

```python
class Sequence(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    name: str
    trigger_type: str           # manual / signal / schedule
    status: str                 # draft / active / paused / archived
    channel: str                # email (linkedin / zalo reserved, disabled)

class SequenceStep(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    sequence_id: UUID
    step_order: int
    channel: str
    template: str               # Jinja / MJML email template
    wait_duration: int          # seconds
    condition: JSONB | None     # e.g. { "type": "email_opened", "wait": 86400 }

class SequenceEnrollment(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    sequence_id: UUID
    lead_id: UUID
    status: str                 # enrolled / active / paused / completed / bounced
    current_step: int
    enrolled_at: datetime

class SequenceEvent(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    enrollment_id: UUID
    event_type: str             # sent / delivered / opened / replied / bounced / meeting_booked
    channel: str
    metadata: JSONB
    created_at: datetime

class SequenceRun(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    sequence_id: UUID
    status: str                 # running / completed / failed
    started_at: datetime
    finished_at: datetime | None
```

### CRM (AD-40)

```python
class CrmConnection(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    provider: str               # salesforce / hubspot / pipedrive
    credentials_encrypted: str
    sync_config: JSONB
    last_sync_at: datetime | None

class CrmSyncLog(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    connection_id: UUID
    direction: str              # nowing_to_crm / crm_to_nowing
    entity_type: str
    entity_id: UUID
    status: str                 # success / conflict / error
    error_message: str | None
    synced_at: datetime
```

### Billing (AD-8 / AD-10 / AD-42)

```python
class BillingEvent(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    user_id: UUID
    event_id: UUID               # points to SignalEvent / EnrichmentRequest / LeadScore / SequenceEvent / OutcomeEvent
    event_type: str               # contact_enrichment / lead_scoring / signal_scan / email_send / outcome_meeting_booked / outcome_lead_enriched
    cost_micros: int
    currency: str                 # USD
    cost_basis: str               # actual / estimated
    created_at: datetime

class OutcomeEvent(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    event_type: str               # outcome_meeting_booked / outcome_lead_enriched
    lead_id: UUID
    sequence_id: UUID | None
    billing_event_id: UUID
    attribution: str              # first-touch sequence_id
    cost_micros: int
    created_at: datetime

class PricingPlan(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    plan_type: str                # seat / outcome / hybrid
    seat_price: int | None        # micros
    outcome_rates_json: JSONB     # { "meeting_booked": 5000000, "lead_enriched": 50000 }
    billing_period: str | None
```

---

## 2. Capability registry extensions

Lead and signal capabilities must register metadata:

```python
# capability definition.py
{
  "id": "vn_jobs.aggregate",
  "emits_leads": True,
  "emits_signals": False,
  ...
}

{
  "id": "funding.signal",
  "emits_leads": False,
  "emits_signals": True,
  "signal_types": ["funding"],
  ...
}
```

`CapabilityRegistry` query for lead source picker:
```sql
SELECT id, display_name, metadata
FROM capability_registry
WHERE workspace_id = :ws
  AND (metadata->>'emits_leads')::bool = true;
```

---

## 3. AlertRule schema for signals → sequences (AD-33)

```python
class AlertRule(Base):
    id: UUID
    workspace_id: UUID
    client_id: UUID | None
    capability_id: str            # registered signal capability, e.g. 'funding.signal'
    query: JSONB                  # structured query for capability
    schedule: str                 # cron expression
    diff_strategy: str            # new_items / price_change / threshold_cross / trend_detect
    threshold: JSONB | None
    notification_channels: list[str]   # ["in_app", "telegram", "email", "sequence_enrollment"]
    target: JSONB | None          # { "sequence_id": "uuid", "step_id": "uuid" | null }
```

Execution: reuses Epic 6 Automation scheduler + Celery + notification dispatch.

---

## 4. Implementation stories (suggested slice)

### Backend

| # | Story | Depends on | AC summary |
|---|---|---|---|
| BE-1 | Lead + `LeadSource` tables + migrations | AD-31 | Schema + CRUD + `client_id` filter; unit tests. |
| BE-2 | `CapabilityRegistry.emits_leads` metadata | BE-1 | Lead source picker API; integration tests. |
| BE-3 | `EnrichmentRequest` + `VerifiedContact` + waterfall API | BE-1 | Call Cleanlist/BetterContact; PII redaction; `BillingEvent.contact_enrichment`.
| BE-4 | `SignalEvent` + `SignalSubscription` + signal capabilities | BE-2, AD-37 | AlertRule integration; redacted `Memory` row; `BillingEvent.signal_scan`. |
| BE-5 | `LeadScore` model + scoring engine | BE-1, BE-4 | Composite score; `BillingEvent.lead_scoring`; redacted `Memory` row. |
| BE-6 | `Sequence` bounded context + Celery executor | BE-1, BE-2 | New tables; reuse Epic 6 scheduler; `BillingEvent.email_send`. |
| BE-7 | Inbound email capability + `SequenceEvent` | BE-6, Story 11.1 | SES/IMAP webhook → `SequenceEvent` → notification dispatch. |
| BE-8 | `CrmConnection` + `CrmSyncLog` + OAuth reuse | BE-1 | Read-first dedup; phased write-back. |
| BE-9 | `BillingEvent` + `OutcomeEvent` + `PricingPlan` | BE-3, BE-6 | Wallet debit; outcome pricing; dashboard reuse. |

### Frontend

| # | Story | UX contract | AC summary |
|---|---|---|---|
| FE-1 | Workspace mode switch | N2 | Outbound/Research/Content nav filter. |
| FE-2 | Lead list / inbox empty state | N4 | Lead source picker from `CapabilityRegistry.emits_leads`; email sender connection. |
| FE-3 | Source-specific tabs | N7 | Dynamic tabs from actual lead sources. |
| FE-4 | Per-lead projected cost | N6 | Read `BillingEvent` + wallet; display cost. |
| FE-5 | Campaign status chip | N8 | Set `lead.sequence_id` on `Sequence`. |
| FE-6 | Positive-reply / delivery / bounce notifications | N5 | Notification settings; `email_reply`/`email_delivered`/`email_bounced` channels. |
| FE-7 | Onboarding checklist | N1 | Computed state from `Sequence`/`CapabilityRegistry`. |
| FE-8 | Tables directory | N3 | Lead list library; `client_id` filter. |

---

## 5. Launch gates

### Engineering pre-launch

- [ ] All new tables have `client_id` and RLS filter tests.
- [ ] `BillingEvent` writes for every non-LLM business event; `TokenUsage` stays LLM-only.
- [ ] `Sequence` does not reuse `Automation` schema.
- [ ] Signal capabilities register `emits_signals=true`; lead capabilities `emits_leads=true`.
- [ ] `AlertRule` uses `capability_id` + `sequence_enrollment` channel for signal-driven triggers.
- [ ] PII redaction runs before any lead/contact data is embedded or displayed.
- [ ] CRM sync starts read-only; write-back behind feature flag.
- [ ] Zalo/LinkedIn channels disabled in UI and backend (return 400 with "deferred" message).
- [ ] Unit + integration tests for all BE stories; Playwright E2E for P0 FE stories.

### Business / legal gates (must close before public beta)

- [ ] Email outreach legal/ToS sign-off.
- [ ] Contact-enrichment vendor contract / POC (Cleanlist / BetterContact).
- [ ] PII/consent pipeline for lead data approved.
- [ ] CRM sync scope confirmed.
- [ ] Outcome-pricing display and cost estimator tested with real `BillingEvent` data.
- [ ] TopCV anti-bot POC pass (Epic 12 dependency).

---

## 6. Migration / deployment notes

- Alembic migrations must add new tables in one batch per deployment slice.
- `client_id` column additions should be separate migration if applied to existing tables (`Memory`, `Run`, `TokenUsage`, `ResearchThread`) before Epic 21 tables.
- `CapabilityRegistry` metadata columns (`emits_leads`, `emits_signals`, `signal_types`) can be JSONB `metadata` additions.
- `BillingEvent` table must exist before any BE-3/4/5/6/9 code is enabled.

---

## 7. Testing strategy

- **Unit:** each capability executor, PII redaction, `BillingEvent` ledger, `Sequence` executor.
- **Integration:** end-to-end signal → `AlertRule` → `SequenceEnrollment` → email send → `SequenceEvent` → notification.
- **E2E (Playwright):** N4 empty state, N5 notifications, N6 cost display, N8 campaign chip.
- **Mutation gate:** run `scripts/mutation-gate.py` on `app/services/pii/`, `app/services/billing/`, `app/capabilities/lead/`, `app/automations/sequencer/` once they exist.

---

## 8. Files to implement against

- `../epics.md` — Story 21.1–21.7 ACs.
- `../architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-31, AD-33, AD-36–AD-42.
- `../ux-designs/ux-Nowing-2026-07-22/*.md` — UI contracts.
- `epic21-ux-handoff-2026-08-11.md` — UX hand-off and business questions.

---

**Next action:** Engineering lead creates sub-issues/stories in sprint tracker and schedules BE-1 → BE-9 / FE-1 → FE-8 once governance gates are closed.
