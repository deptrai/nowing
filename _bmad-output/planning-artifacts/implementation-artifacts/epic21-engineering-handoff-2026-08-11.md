# Epic 21 Engineering Hand-off — Lead Intelligence (2026-08-11)

**Date:** 2026-08-11
**Author:** Architecture / PO
**Audience:** Backend, Frontend, QA, DevOps
**Status:** ✅ **Architecture FIT** — implementation can be sliced after governance gates close.

This hand-off complements the UX hand-off (`epic21-ux-handoff-2026-08-11.md`) with the canonical technical tasks, data model, API shape, and launch gates.

---

## 0. Must-read before starting

- `epic21-ux-handoff-2026-08-11.md`
- `../architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-31, AD-33, AD-36–AD-42, AD-45–AD-49)
- `../epics.md` (Story 21.1–21.7)
- `../ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`
- `../ux-designs/ux-Nowing-2026-07-22/ux-contract-positive-reply-notifications.md`

---

## 1. Data model

Every new table below uses UUID `id`, `workspace_id: Integer` (`ForeignKey workspaces.id`), and nullable `client_id: CITEXT` (AD-31/AD-45). `client_id` is the natural key of `vertical_clients.client_id`, not the UUID `vertical_clients.id`. Composite indexes on `(workspace_id, client_id)`. Existing `Memory`, `Run`, and `TokenUsage` already use `workspace_id: Integer` and `client_id: Text`; an Alembic migration must change them to `CITEXT` and add a `CheckConstraint` or `ForeignKey` to `vertical_clients.client_id` before Epic 21 tables are enabled.

### Core lead tables

```python
class Lead(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    source: str                 # Capability.name (canonical identifier); lead-source picker uses LeadSource cache
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
    workspace_id: Integer
    client_id: CITEXT | None
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
    workspace_id: Integer
    client_id: CITEXT | None
    lead_id: UUID
    status: str                 # pending / processing / completed / failed
    provider_results: JSONB
    cost_micros: int
    created_at: datetime

class VerifiedContact(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    lead_id: UUID
    email: str | None           # raw value stored encrypted at rest; authoritative for outreach (AD-49)
    phone: str | None           # raw value stored encrypted at rest; authoritative for outreach (AD-49)
    verification_status: str    # unverified / verified / low_confidence
    confidence: float
    source_provider: str
    consent_status: str | None  # explicit / legitimate_interest / none — authoritative gate for first outreach
    legal_basis: str | None     # consent / legitimate_interest / contract / legal_obligation — authoritative gate for first outreach
    # Access-controlled PII vault: raw email/phone are NOT redacted here. Redaction (context='lead_enrichment') is applied
    # to Memory.content, Chunk[], audit logs, and non-privileged UI surfaces only.
    # `Lead.consent_status`/`legal_basis` are cached UI summaries; `SequenceEnrollment` and the sequencer must gate on `VerifiedContact.consent_status` before the first send.
```

### Signals (AD-37)

```python
class SignalEvent(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    company_name: str
    signal_type: str            # funding / hiring / tech_stack / executive_move / news
    source_url: str
    chunk_id: UUID | None       # pointer to chainlens-research Chunk
    confidence: float
    detected_at: datetime
    processed: bool

class SignalSubscription(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    signal_types: list[str]
    notification_channels: list[str]
```

### Lead scoring (AD-38)

```python
class LeadScore(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
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
    workspace_id: Integer
    client_id: CITEXT | None   # NOT NULL for client-scoped; NULL only when shared = true
    name: str
    trigger_type: str           # manual / signal / schedule
    status: str                 # draft / active / paused / archived
    channel: str                # email (linkedin / zalo reserved, disabled)
    shared: bool                # default false; true AND client_id IS NULL = workspace-global

class SequenceStep(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    sequence_id: UUID
    step_order: int
    channel: str
    template: str               # Jinja / MJML email template
    wait_duration: int          # seconds
    condition: JSONB | None     # e.g. { "type": "email_opened", "wait": 86400 }

class SequenceEnrollment(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None    # sequence client_id for client-scoped; matched Lead.client_id for shared
    sequence_id: UUID
    lead_id: UUID
    triggering_lead_id: UUID    # the matched Lead whose signal triggered the enrollment
    triggering_alert_rule_id: UUID | None
    status: str                 # enrolled / active / paused / completed / bounced
    current_step: int
    enrolled_at: datetime

class SequenceEvent(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    enrollment_id: UUID
    event_type: str             # sent (billed as sequence_event/email_send)
                                # delivered / opened / replied / bounced (status + notifications only; no BillingEvent)
                                # meeting_booked (creates OutcomeEvent + BillingEvent outcome_meeting_booked)
    channel: str
    metadata: JSONB
    created_at: datetime

class SequenceRun(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None    # sequence client_id for client-scoped; matched Lead.client_id for shared
    sequence_id: UUID
    triggering_lead_id: UUID    # the matched Lead whose signal triggered the run
    triggering_alert_rule_id: UUID | None
    status: str                 # running / completed / failed
    started_at: datetime
    finished_at: datetime | None
```

### CRM (AD-40)

```python
class CrmConnection(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    provider: str               # salesforce / hubspot / pipedrive
    credentials_encrypted: str
    sync_config: JSONB
    last_sync_at: datetime | None

class CrmSyncLog(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
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
    workspace_id: Integer
    client_id: CITEXT | None
    user_id: UUID | None          # nullable; automated events default to workspace owner
    event_entity_type: str        # signal_event | enrichment_request | lead_score | sequence_event | outcome_event
    event_type: str               # allowed matrix (AD-42 / AD-48):
                                  #   signal_event → signal_scan
                                  #   enrichment_request → contact_enrichment
                                  #   lead_score → lead_scoring
                                  #   sequence_event → email_send (only for SequenceEvent.event_type == 'sent')
                                  #   outcome_event → outcome_meeting_booked (from meeting_booked only) | outcome_lead_enriched
    event_id: UUID               # points to SignalEvent / EnrichmentRequest / LeadScore / SequenceEvent / OutcomeEvent.id
    cost_micros: int
    currency: str                 # USD
    cost_basis: str               # actual | estimated | refunded
    created_at: datetime

class OutcomeEvent(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    event_type: str               # outcome_meeting_booked / outcome_lead_enriched
    lead_id: UUID
    sequence_id: UUID | None
    attribution: str              # first-touch sequence_id
    cost_micros: int
    created_at: datetime
    # billing_event_id removed; one OutcomeEvent maps to one BillingEvent via BillingEvent.event_id
    # partial unique index: (event_id) WHERE BillingEvent.event_entity_type = 'outcome_event'

class PricingPlan(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    plan_type: str                # seat / outcome / hybrid
    seat_price: int | None        # micros
    outcome_rates_json: JSONB     # { "meeting_booked": 5000000, "lead_enriched": 50000 }
    billing_period: str | None
```

---

### Memory provenance note (AD-44)

```python
class Memory(Base):
    # existing columns (already in app/db.py)
    workspace_id: Integer
    client_id: CITEXT | None
    source_id: Integer | None            # chat message / document IDs (Integer sources)
    source_run_id: UUID | None           # only when source is a Run (UUID)
    source_input: JSONB                  # immutable recipe
    # new for Epic 21:
    source_uuid: UUID | None             # SignalEvent / LeadScore / Lead / EnrichmentRequest / SequenceEvent / OutcomeEvent
    source_entity_type: str | None       # e.g. 'signal_event', 'lead_score', 'lead', 'enrichment_request', 'sequence_event', 'outcome_event'
```

- `source_uuid` + `source_entity_type` are the **authoritative** source pointer for Epic 21 UUID entities. Do not coerce UUIDs into `source_id` (Integer).
- `source_run_id` is set only when the source is a `Run` and may be set alongside `source_uuid` for audit context; `source_uuid`/`source_entity_type` remain authoritative for re-validation and provenance display.
- `source_id` stays `Integer` for `document` / `chat_message`.
- `MemorySourceType` is extended with `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`.
- `source_input` continues to store the immutable recipe/capability/input.

---

## 2. Capability metadata and lead-source cache (AD-44 / AD-47)

Lead and signal capabilities may advertise metadata at registration. The in-process `CapabilityRegistry` in `app/capabilities/core/store.py` is a **runtime registry of executable verbs**, not a workspace-scoped persisted table. The `Capability` dataclass gains an optional `metadata: dict` field; `Capability.name` is the canonical identifier. `CapabilityRegistry.query_metadata(key)` returns `{capability_name: metadata_value}` and `query_metadata_for(name, key)` returns a single value. Workspace-scoped lead-source metadata lives in the `LeadSource` table, which is a **derived cache** updated by the `lead_extractor` pipeline.

```python
@dataclass
class Capability:
    name: str                     # canonical identifier
    ...
    metadata: dict | None = None  # optional; holds Epic 21 advertising keys

# capability definition.py example
{
  "name": "vn_jobs.aggregate",
  "metadata": {
    "emits_leads": True,
    "emits_signals": False,
    "requires_pii_redaction_context": "job_data",
  },
  ...
}

{
  "name": "funding.signal",
  "metadata": {
    "emits_leads": False,
    "emits_signals": True,
    "signal_types": ["funding"],
  },
  ...
}

{
  "name": "lead_extractor",
  "metadata": {
    "lead_extractor": True,
  },
  ...
}
```

Canonical metadata keys for Epic 21:
- `emits_leads: bool`
- `emits_signals: bool`
- `signal_types: list[str]`
- `lead_extractor: bool`
- `requires_pii_redaction_context: str`

**Lead source picker query** (against the workspace-scoped `LeadSource` cache, not the in-process dict):
```sql
SELECT id, capability_id, provider, enabled_for_leads, lead_count
FROM lead_sources
WHERE workspace_id = :ws
  AND client_id IS NOT DISTINCT FROM :client_id
  AND enabled_for_leads = true;
```

- The `lead_extractor` capability is the **sole writer** of `Lead` and `LeadSource` rows; its `metadata` must carry `lead_extractor: true`.
- Use `CapabilityRegistry.query_metadata(key)` or `query_metadata_for(name, key)` to read capability metadata; do not read `_REGISTRY` directly outside the registry.
- If a persisted `capability_registry` table is added later, it must remain a platform/global catalog and must not be conflated with the in-process `_REGISTRY` dict or the workspace-scoped `LeadSource` cache.

---

## 3. AlertRule schema for signals → sequences (AD-33 / AD-43 / AD-46)

`AlertRule` is a **first-class table**, not a JSON template inside `Automation.definition`.

```python
class AlertRule(Base):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    capability_id: str            # registered signal capability, e.g. 'funding.signal'
    query: JSONB                  # structured query for capability
    schedule: str                 # cron expression
    diff_strategy: str            # new_items / price_change / threshold_cross / trend_detect
    threshold: JSONB | None
    notification_channels: list[str]   # ["in_app", "telegram", "email"] (genuine channels only)
    target_sequence_id: UUID | None   # foreign key to Sequence.id; null = notification-only
    target_step_id: UUID | None       # foreign key to SequenceStep.id; optional step inside the sequence; null = first step
    enabled: bool
```

- `AlertRule.target_sequence_id` is a foreign key to `Sequence.id`; `target_step_id` is a foreign key to `SequenceStep.id` (nullable).
- For client-scoped `Sequence`s, the `AlertRule.client_id` must match `Sequence.client_id` (or both `NULL`) before `SequencerService` is called. Shared `Sequence`s (`shared=true` and `client_id IS NULL`) may be targeted by any `AlertRule`.
- `Sequence` is client-scoped by default. A workspace-global `Sequence` must have `shared = true` **and** `client_id IS NULL`.
- The matched `Lead.client_id` must equal the rule's `client_id` (or the rule is workspace-global); the resulting `SequenceRun`/`SequenceEnrollment` `client_id` is always the matched `Lead.client_id`.

Execution:
- Reuses the Epic 6 **scheduler/Celery pattern** and **notification dispatch**.
- Does **not** reuse the `Automation` / `AutomationRun` data schema.
- `sequence_enrollment` is **not** a notification channel; it is an action that emits an `EnrollmentRequested` domain event / Celery task to the Sequence bounded context.
- The alert engine calls `SequencerService` to create a `SequenceRun` (UUID) and enroll matched lead(s); it never creates an `AutomationRun`.

---

## 4. Implementation stories (suggested slice)

### Backend

| # | Story | Depends on | AC summary |
|---|---|---|---|
| BE-1 | Lead + `LeadSource` tables + migrations | AD-31 | Schema + CRUD + `client_id` filter; unit tests. |
| BE-2 | Capability `emits_leads` metadata + `LeadSource` cache | BE-1 | Lead source picker queries `LeadSource`; capability metadata is advertising only (AD-44). |
| BE-3 | `EnrichmentRequest` + `VerifiedContact` + waterfall API | BE-1 | Call Cleanlist/BetterContact; PII redaction; `BillingEvent` (`enrichment_request` / `contact_enrichment`). |
| BE-4 | `SignalEvent` + `SignalSubscription` + signal capabilities | BE-2, AD-37 | AlertRule integration; redacted `Memory` row (`source_uuid` → `SignalEvent`); `BillingEvent` (`signal_event` / `signal_scan`). |
| BE-5 | `LeadScore` model + scoring engine | BE-1, BE-4 | Composite score; `BillingEvent` (`lead_score` / `lead_scoring`); redacted `Memory` row (`source_uuid` → `LeadScore`). |
| BE-6 | `Sequence` bounded context + Celery executor | BE-1, BE-2 | New tables; reuse Epic 6 scheduler; `BillingEvent` (`sequence_event` / `email_send`). |
| BE-7 | Inbound email capability + `SequenceEvent` | BE-6, Story 11.1 | SES/IMAP webhook → `SequenceEvent` → notification dispatch. |
| BE-8 | `CrmConnection` + `CrmSyncLog` + OAuth reuse | BE-1 | Read-first dedup; phased write-back. |
| BE-9 | `BillingEvent` + `OutcomeEvent` + `PricingPlan` | BE-3, BE-6 | Wallet debit; outcome pricing; dashboard reuse. |

### Frontend

| # | Story | UX contract | AC summary |
|---|---|---|---|
| FE-1 | Workspace mode switch | N2 | Outbound/Research/Content nav filter. |
| FE-2 | Lead list / inbox empty state | N4 | Lead source picker from `LeadSource` cache (populated by `lead_extractor`); email sender connection. |
| FE-3 | Source-specific tabs | N7 | Dynamic tabs from actual lead sources. |
| FE-4 | Per-lead projected cost | N6 | Read `BillingEvent` + wallet; display cost. |
| FE-5 | Campaign status chip | N8 | Set `lead.sequence_id` on `Sequence`. |
| FE-6 | Positive-reply / delivery / bounce notifications | N5 | Notification settings; `email_reply`/`email_delivered`/`email_bounced` channels. |
| FE-7 | Onboarding checklist | N1 | Computed state from `Sequence` / `LeadSource` cache. |
| FE-8 | Tables directory | N3 | Lead list library; `client_id` filter. |

---

## 5. Launch gates

### Engineering pre-launch

- [ ] All new tables have `workspace_id: Integer`, `client_id: CITEXT`, and RLS filter tests. Existing `Memory`/`Run`/`TokenUsage` `client_id: Text` columns are migrated to `CITEXT` with a `CheckConstraint` or `ForeignKey` to `vertical_clients.client_id` before Epic 21 tables are enabled.
- [ ] `BillingEvent` writes for every new non-LLM business event with `event_entity_type` + `event_type`; `TokenUsage` stays LLM-only; existing non-LLM `TokenUsage` rows are grandfathered. Only `SequenceEvent.event_type == 'sent'` bills as `sequence_event`/`email_send`; `meeting_booked` creates an `OutcomeEvent` + `BillingEvent` `outcome_event`/`outcome_meeting_booked`; delivery/open/reply/bounce do not create `BillingEvent`.
- [ ] `Sequence` does not reuse `Automation` schema.
- [ ] Signal capabilities advertise `emits_signals=true`; lead-source capabilities advertise `emits_leads=true`; `lead_extractor` is the sole writer of `Lead`/`LeadSource`.
- [ ] `AlertRule` is a first-class table; `AlertRule.client_id` matches the target `Sequence.client_id` (or both `NULL`) before enrollment; signal-driven enrollment uses the `EnrollmentRequested` action (not a notification channel) and creates a `SequenceRun` via `SequencerService`, never an `AutomationRun`.
- [ ] `VerifiedContact` stores raw email/phone encrypted at rest and is never redacted in place. PII redaction (`context='lead_enrichment'`) runs on `Memory.content`, `Chunk[]`, audit logs, and non-privileged UI surfaces; authorized send/personalization reads raw values from `VerifiedContact`.
- [ ] `Memory.source_uuid` and `Memory.source_entity_type` are added for Epic 21 UUID entities; `MemorySourceType` is extended with `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`; UUIDs are not coerced into `Memory.source_id`.
- [ ] `OutcomeEvent.billing_event_id` is removed; one `OutcomeEvent` maps to one `BillingEvent` via `BillingEvent.event_id`.
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
- All new Epic 21 tables use `workspace_id: Integer` (`ForeignKey workspaces.id`) and `client_id: CITEXT` (nullable) per AD-31/AD-45. `client_id` is the natural key of `vertical_clients.client_id`, not the UUID `vertical_clients.id`. Do **not** use `workspace_id: UUID`.
- Existing `client_id` columns that are currently `Text` (`Memory`, `Run`, `TokenUsage`, `ResearchThread`, `PersonalAccessToken`) must be migrated to `CITEXT` and gain a `CheckConstraint` or `ForeignKey` to `vertical_clients.client_id` before Epic 21 tables are enabled. The future `clients` table is the already-existing `vertical_clients` table; no UUID `client_id` surrogate is introduced.
- Add `Memory.source_uuid` (UUID, nullable, indexed) and `Memory.source_entity_type` (str, nullable) for Epic 21 UUID entity references; preserve `Memory.source_id` as Integer; extend `MemorySourceType` with `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`.
- Add `Sequence.shared` (bool, default `false`, not null) with a DB check that `(shared = true AND client_id IS NULL) OR (shared = false AND client_id IS NOT NULL)`.
- Capability metadata (`emits_leads`, `emits_signals`, `signal_types`, `lead_extractor`, `requires_pii_redaction_context`) lives in `Capability.metadata`; `Capability.name` is the canonical identifier; `CapabilityRegistry.query_metadata(key)` is the canonical read path; the workspace-scoped `LeadSource` table is the lead-source cache.
- `AlertRule` is a first-class table with its own migration; `AlertRule.target_sequence_id` (FK to `Sequence.id`) and `AlertRule.target_step_id` (FK to `SequenceStep.id`, nullable) are real foreign-key columns. For client-scoped `Sequence`s, the rule's `client_id` must match `Sequence.client_id` (or both `NULL`); shared `Sequence`s (`shared=true` and `client_id IS NULL`) may be targeted by any `AlertRule`, but the matched `Lead.client_id` must equal the rule's `client_id` (or the rule is workspace-global).
- `BillingEvent` table must exist before any BE-3/4/5/6/9 code is enabled. It requires `event_entity_type`, `event_type`, and a partial unique index on `event_id` where `event_entity_type = 'outcome_event'`. Only `SequenceEvent.event_type == 'sent'` bills as `sequence_event`/`email_send`; `meeting_booked` creates an `OutcomeEvent` + `BillingEvent` `outcome_event`/`outcome_meeting_booked`.

---

## 7. Testing strategy

- **Unit:** each capability executor, PII redaction, `BillingEvent` ledger, `Sequence` executor.
- **Integration:** end-to-end signal → `AlertRule` → `SequenceEnrollment` → email send → `SequenceEvent` → notification.
- **E2E (Playwright):** N4 empty state, N5 notifications, N6 cost display, N8 campaign chip.
- **Mutation gate:** run `scripts/mutation-gate.py` on `app/services/pii/`, `app/services/billing/`, `app/capabilities/lead/`, `app/automations/sequencer/` once they exist.

---

## 8. Files to implement against

- `../epics.md` — Story 21.1–21.7 ACs.
- `../architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-25, AD-31, AD-33, AD-36–AD-50 (especially AD-45–AD-49).
- `../ux-designs/ux-Nowing-2026-07-22/*.md` — UI contracts.
- `epic21-ux-handoff-2026-08-11.md` — UX hand-off and business questions.

---

**Next action:** Engineering lead creates sub-issues/stories in sprint tracker and schedules BE-1 → BE-9 / FE-1 → FE-8 once governance gates are closed.
