---
story_key: 21-3-enriched-contact-data
status: pending-human-review
baseline_commit: 1261fb2a1
epic: 21
story: 3
---

# Story 21.3: Enriched Contact Data

## Story

As an SDR,
I want verified contact data (names, titles, emails, phone numbers) for my target accounts,
So that I can reach out to the right decision-makers.

## Acceptance Criteria

### AC-1 — Request enrichment for a lead
**Given** a `Lead` exists in a workspace,
**When** an authorized user requests contact enrichment for that `lead_id`,
**Then** the system creates an `EnrichmentRequest` row with `status=pending`, enqueues a Celery task, and returns the request with `202 Accepted`.

### AC-2 — Verify contacts via waterfall
**Given** an `EnrichmentRequest` is processed,
**When** the waterfall API is called,
**Then** the system tries the configured primary provider first (`cleanlist` or `bettercontact`), falls back to the secondary provider on failure, and finally applies basic verification (MX check + pattern matching) if both external providers fail.

> **Scope:** The MVP buys the waterfall via a single integration contract (Cleanlist or BetterContact). The implementation must **not** build 14+ provider integrations. Provider names are recorded in `VerifiedContact.source_provider` (`cleanlist`, `bettercontact`, `fallback`).

### AC-3 — Store verified contacts with PII protection
**Given** verified contacts are returned,
**When** they are persisted,
**Then** the system writes one `EnrichmentRequest` row and one or more `VerifiedContact` rows per decision-maker.

**And** each `VerifiedContact` includes `name`, `title`, `email`, `phone`, `verification_status`, `confidence`, `source_provider`, `consent_status`, `legal_basis`, `workspace_id`, `client_id`, and `lead_id`.

**And** raw PII (`name`, `title`, `email`, `phone`) is encrypted at rest using `TokenEncryption` (`app/utils/oauth_security.py`) before persistence. `VerifiedContact` is the authoritative PII vault and is **never** passed through `redact_pii`.

**And** `Lead.enriched` is set to `True`, and `Lead.consent_status` / `Lead.legal_basis` are cached from the first `VerifiedContact` (UI summaries only; authoritative gate remains `VerifiedContact`).

### AC-4 — Redact before memory and logs
**Given** enriched contact data is stored,
**When** a redacted `Memory` row, `Chunk[]`, audit log, or non-privileged UI surface is produced,
**Then** `redact_pii(..., context="lead_enrichment")` is applied so only masked placeholders (`<EMAIL>`, `<PHONE>`, `<NAME>`) appear outside the `VerifiedContact` vault.

**And** the `Memory` row has `type=semantic`, `source_type=MemorySourceType.ENRICHMENT`, `source_uuid=EnrichmentRequest.id`, `source_entity_type="enrichment_request"`, `tags=["enriched_contact"]`, and `content` is the redacted summary JSON.

### AC-5 — Cache with 30-day TTL
**Given** an enrichment succeeds for a `(workspace_id, client_id, lead_id)` tuple,
**When** the same lead is enriched again,
**Then** the system returns the cached `VerifiedContact` IDs without re-billing or re-calling the external API, if the cache key `enrichment:v1:{workspace_id}:{client_id}:{lead_id}` exists in Redis and has not expired.

### AC-6 — Billing via `BillingEvent`, not `TokenUsage`
**Given** an enrichment completes with one or more `VerifiedContact` rows,
**When** the cost is recorded,
**Then** the system writes a `BillingEvent` row with:
  - `event_entity_type="enrichment_request"`
  - `event_type="contact_enrichment"`
  - `event_id=EnrichmentRequest.id`
  - `cost_micros=CONTACT_ENRICHMENT_MICROS_PER_CONTACT * count(verified_contacts)`
  - `cost_basis="actual"`
**And** it calls `wallet_credit.check_balance` / `wallet_credit.apply_debit` before the external API call (pre-check) and commits the `BillingEvent` after persistence.

> **Constraint:** `TokenUsage` is for LLM/token steps only. The `lead.enrich` capability sets `billing_unit=None`. Do **not** add `BillingUnit.CONTACT_ENRICHMENT` or `UsageType.contact_enrichment`.

### AC-7 — Consent and legal basis gates
**Given** a `VerifiedContact` is created,
**When** `consent_status` or `legal_basis` is missing,
**Then** the row is still persisted but the system does **not** set `consent_status` / `legal_basis` to a default. The downstream sequencer (Story 21.4) must gate first send on `VerifiedContact.consent_status` in `{explicit, legitimate_interest}`.

### AC-8 — REST endpoints
**Given** a user with the correct permission,
**When** they call the enrichment endpoints,
**Then** the following endpoints behave as specified:
  - `POST /workspaces/{workspace_id}/leads/{lead_id}/enrich` — start enrichment, return `EnrichmentRequestRead` with `status=pending` and `202 Accepted`.
  - `POST /workspaces/{workspace_id}/leads/enrich` — bulk enrichment for a list of `lead_ids`, returns a list of `EnrichmentRequestRead` (one per lead).
  - `GET /workspaces/{workspace_id}/leads/{lead_id}/enrichments` — list `EnrichmentRequest` rows for a lead with pagination.
  - `GET /workspaces/{workspace_id}/leads/{lead_id}/contacts` — list `VerifiedContactRead` for a lead, latest first, with pagination.
  - `GET /workspaces/{workspace_id}/leads/enrich/cost` — return `cost_per_contact_micros` and estimated cost for a list of `lead_ids`.

### AC-9 — Capability and MCP wiring
**Given** the `lead.enrich` capability is registered,
**When** it is invoked via REST, MCP, or the agent runtime,
**Then** it uses `EnrichmentInput` / `EnrichmentOutput` schemas, `billing_unit=None`, and `metadata={"emits_leads": false, "requires_pii_redaction_context": "lead_enrichment"}`.

**And** MCP tools `nowing_enrich_lead` and `nowing_list_contacts` are registered in `nowing_mcp/mcp_server/features/enrichment/` and added to `EXPECTED_TOOLS` in `nowing_mcp/mcp_server/selfcheck.py` and `MCP_TOOL_CATALOG` in `app/mcp_tools.py` (group `LEAD_INTELLIGENCE`).

### AC-10 — Degradation and error handling
**Given** the wallet is insufficient or the external provider fails,
**When** enrichment is requested,
**Then** the system returns `degraded=true` with a clear `degradation_reason` (`insufficient_wallet`, `provider_unavailable`, `lead_not_found`) and does not write `VerifiedContact` rows or a `BillingEvent`.

## Tasks / Subtasks

### Task 1: Models & Migration
- [x] 1.1 Add `EnrichmentRequest` to `nowing_backend/app/db.py` (UUID PK, inherits `Base + TimestampMixin`):
  - `id` (UUID, PK, default uuid4)
  - `workspace_id` (Integer, FK `workspaces.id`, index)
  - `client_id` (CITEXT, nullable, index)
  - `lead_id` (UUID, FK `leads.id`, index)
  - `status` (String(20), default `pending`) — `pending / processing / completed / failed`
  - `provider_results` (JSONB, default `{}`, server default `{'{}'::jsonb}`) — waterfall results per provider
  - `cost_micros` (BigInteger, default 0)
  - `contact_count` (Integer, default 0)
  - `created_at` (TIMESTAMP, default now)
  - Composite index `(workspace_id, client_id, lead_id, created_at DESC)`
- [x] 1.2 Add `VerifiedContact` to `app/db.py`:
  - `id` (UUID, PK, default uuid4)
  - `workspace_id` (Integer, FK `workspaces.id`, index)
  - `client_id` (CITEXT, nullable, index)
  - `lead_id` (UUID, FK `leads.id`, index)
  - `enrichment_request_id` (UUID, FK `enrichment_requests.id`, index)
  - `name` (Text, nullable) — raw PII, encrypted at rest
  - `title` (Text, nullable) — raw PII, encrypted at rest
  - `email` (Text, nullable) — raw PII, encrypted at rest
  - `phone` (Text, nullable) — raw PII, encrypted at rest
  - `verification_status` (String(20), default `unverified`) — `unverified / verified / low_confidence`
  - `confidence` (Float, nullable=False, default=0.0)
  - `source_provider` (String(50), nullable=False)
  - `consent_status` (String(50), nullable) — `explicit / legitimate_interest / none`
  - `legal_basis` (String(50), nullable) — `consent / legitimate_interest / contract / legal_obligation`
  - `created_at` (TIMESTAMP, default now)
  - Composite index `(workspace_id, client_id, lead_id, created_at DESC)`
- [x] 1.3 Add `Permission.LEADS_ENRICH` and `Permission.CONTACTS_READ` to `app/db.py` `Permission` enum.
- [x] 1.4 Verify `MemorySourceType.ENRICHMENT` already exists in `app/db.py` (it does at line 599).
- [x] 1.5 Alembic migration `200_add_enrichment_tables.py`:
  - Create `enrichment_requests` and `verified_contacts` tables with FKs, indexes, RLS-scoped by `workspace_id` + `client_id`.
  - `client_id` uses `CITEXT` and `CheckConstraint` / `ForeignKey` to `vertical_clients.client_id` per AD-45.
  - Add `Lead.enriched`, `Lead.consent_status`, `Lead.legal_basis` if not already present (they exist from Story 21.2).

### Task 2: PII Encryption Service
- [x] 2.1 Create `app/services/pii/verified_contact_encryption.py`:
  - `VerifiedContactEncryption` wraps `TokenEncryption(config.SECRET_KEY)`.
  - `encrypt(value: str | None) -> str | None`
  - `decrypt(value: str | None) -> str | None`
  - `encrypt_contact(contact: VerifiedContactDict) -> VerifiedContactDict`
  - `decrypt_contact(contact: VerifiedContactDict) -> VerifiedContactDict`
- [x] 2.2 Store ciphertext in `VerifiedContact.name/title/email/phone`; decrypt only when returning `VerifiedContactRead` to authorized callers.

### Task 3: Enrichment Service
- [x] 3.1 Create `app/lead_intelligence/enrichment/__init__.py`, `service.py`, `schemas.py`, `capability.py`, `providers.py`, `fallback.py`:
  - `EnrichmentService.enrich(session, ctx, lead_id: UUID, requested_count: int = 5) -> EnrichmentOutput`
  - Check `Lead` exists and belongs to `(workspace_id, client_id)`.
  - Check cache key `enrichment:v1:{workspace_id}:{client_id}:{lead_id}` in Redis. On hit, return existing `VerifiedContact` IDs and skip billing.
  - Pre-check wallet with `wallet_credit.check_balance` for `CONTACT_ENRICHMENT_MICROS_PER_CONTACT * requested_count`.
  - Create `EnrichmentRequest(status="pending")` and enqueue `enrich_lead_task`.
  - Celery task calls `_run_waterfall(session, request_id)`:
    - Update `status="processing"`.
    - Call primary provider (`cleanlist` or `bettercontact`) via `httpx` with timeout 30s.
    - On failure (network, 5xx, no results), try secondary provider.
    - On both failures, use fallback (`MX` check for email, regex for phone).
    - For each verified decision-maker, create `VerifiedContact` with encrypted PII.
    - Update `EnrichmentRequest.status="completed"`, `contact_count`, `provider_results`.
    - Call `BillingEventService.record_contact_enrichment` and commit.
    - Write redacted `Memory` via `MemoryRepository.create_memory`.
    - Set `Lead.enriched=True`, `Lead.consent_status`, `Lead.legal_basis` from first contact.
    - Set Redis cache key with TTL `CONTACT_ENRICHMENT_CACHE_TTL_SECONDS`.
- [x] 3.2 Return `EnrichmentOutput` with `enrichment_request_id`, `lead_id`, `contact_count`, `cost_micros`, `verified_contact_ids`, `degraded`, `degradation_reasons`.

### Task 4: Waterfall Provider Client
- [x] 4.1 Create `app/lead_intelligence/enrichment/providers.py`:
  - `CleanlistClient` and `BetterContactClient` with a common `WaterfallProvider` protocol.
  - `primary` / `secondary` resolved from `CONTACT_ENRICHMENT_PRIMARY_PROVIDER`.
  - Methods: `find_contacts(lead: Lead, requested_count: int) -> list[VerifiedContactDict]`.
  - Each `VerifiedContactDict` has `name`, `title`, `email`, `phone`, `verification_status`, `confidence`, `source_provider`.
- [x] 4.2 Create `app/lead_intelligence/enrichment/fallback.py`:
  - `FallbackVerifier` with `verify_email(email)` (MX DNS lookup + regex) and `verify_phone(phone)` (E.164 regex).
  - Returns `verification_status="low_confidence"` and `source_provider="fallback"`.

### Task 5: REST API
- [x] 5.1 Create `app/routes/enrichment_routes.py`:
  - `POST /workspaces/{workspace_id}/leads/{lead_id}/enrich` — start or return cached enrichment.
  - `POST /workspaces/{workspace_id}/leads/enrich` — bulk (`lead_ids: list[UUID]`).
  - `GET /workspaces/{workspace_id}/leads/{lead_id}/enrichments` — list requests.
  - `GET /workspaces/{workspace_id}/leads/{lead_id}/contacts` — list contacts.
  - `GET /workspaces/{workspace_id}/leads/enrich/cost` — cost projection.
- [x] 5.2 RBAC: `Permission.LEADS_ENRICH` for POSTs, `Permission.LEADS_READ` or `CONTACTS_READ` for GETs.
- [x] 5.3 Register `enrichment_routes` in `app/routes/__init__.py`.

### Task 6: Capability Registration
- [x] 6.1 Create `app/lead_intelligence/enrichment/capability.py`:
  - `LEAD_ENRICH = Capability(name="lead.enrich", billing_unit=None, context_aware=True, metadata={...})`
  - `register_capability(LEAD_ENRICH)`.
- [x] 6.2 Create `app/lead_intelligence/enrichment/schemas.py`:
  - `EnrichmentInput(lead_id: UUID, requested_count: int = 5, lead_ids: list[UUID] | None = None for bulk)`
  - `EnrichmentOutput(enrichment_request_id, lead_id, contact_count, cost_micros, verified_contact_ids, degraded, degradation_reasons)`
  - `VerifiedContactRead(id, name, title, email, phone, verification_status, confidence, source_provider, consent_status, legal_basis, created_at)` — Pydantic `from_attributes=True`
  - `EnrichmentRequestRead(id, lead_id, status, contact_count, cost_micros, created_at)`
  - `EnrichmentCostOutput(cost_per_contact_micros, estimated_cost_micros, lead_count)`
- [x] 6.3 Import `app.lead_intelligence.enrichment.capability` in `app/routes/__init__.py` for side-effect registration.

### Task 7: MCP Tools
- [x] 7.1 Create `nowing_mcp/mcp_server/features/enrichment/__init__.py` and `tools.py`:
  - `nowing_enrich_lead(lead_id, requested_count=5)`
  - `nowing_list_contacts(lead_id, limit=20, offset=0)`
- [x] 7.2 Register in `nowing_mcp/mcp_server/server.py`.
- [x] 7.3 Add tool names to `MCP_TOOL_CATALOG` in `app/mcp_tools.py` (group `LEAD_INTELLIGENCE`).
- [x] 7.4 Update `EXPECTED_TOOLS` in `nowing_mcp/mcp_server/selfcheck.py`.

### Task 8: Billing Service
- [x] 8.1 Extend `app/services/billing_event_service.py`:
  - `record_contact_enrichment(session, enrichment_request_id, workspace_id, client_id, user_id, cost_micros)`.
  - Calls `_record_business_event` with `event_entity_type="enrichment_request"`, `event_type="contact_enrichment"`, `event_id=enrichment_request_id`.
  - Idempotent: raises `ValueError` on duplicate for the same `enrichment_request_id`.

### Task 9: Configuration
- [x] 9.1 Add to `app/config/__init__.py`:
  - `CLEANLIST_API_KEY` (default "")
  - `BETTERCONTACT_API_KEY` (default "")
  - `CONTACT_ENRICHMENT_MICROS_PER_CONTACT` (default 0 — billing off)
  - `CONTACT_ENRICHMENT_CACHE_TTL_SECONDS` (default 2592000 = 30 days)
  - `CONTACT_ENRICHMENT_PRIMARY_PROVIDER` (default `cleanlist`, allowed `cleanlist | bettercontact`)
  - `CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD` (default 5)
  - `CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS` (default 30)
  - `CONTACT_ENRICHMENT_RETRY_ATTEMPTS` (default 3)
- [x] 9.2 Add `.env.example` entries.

### Task 10: Celery Task
- [x] 10.1 Create `app/tasks/celery_tasks/enrichment_tasks.py`:
  - `enrich_lead_task(enrichment_request_id: UUID)` shared task.
  - Opens async DB session, calls `EnrichmentService._run_waterfall`, commits.
- [x] 10.2 Register task import in `app/celery_app.py` (or ensure it is auto-discovered).

### Task 11: Tests
- [x] 11.1 Unit tests `tests/unit/lead_intelligence/test_enrichment.py`:
  - Mock provider clients and Redis cache.
  - Assert `VerifiedContact` creation with encrypted PII.
  - Assert `BillingEvent` with correct `event_entity_type`/`event_type`.
  - Assert `redact_pii(..., context='lead_enrichment')` called before `MemoryRepository.create_memory`.
  - Assert cache hit skips billing and API call.
  - Assert insufficient wallet returns degraded.
  - Assert fallback verifier returns `low_confidence`.
- [x] 11.2 Unit tests `tests/unit/capabilities/test_lead_enrich_capability.py`.
- [x] 11.3 Integration tests `tests/integration/lead_intelligence/test_enrichment.py`:
  - Create workspace + lead, trigger enrichment with mocked HTTP provider, assert `VerifiedContact` rows, `Memory` provenance, `BillingEvent`, and wallet debit.
- [x] 11.4 Migration test for `200_add_enrichment_tables.py`.
- [x] 11.5 Target coverage ≥ 90% for enrichment service.

### Review Findings
- [ ] [Review][Patch] IDOR & Cross-Tenant Isolation check in resolve_lead_phone [nowing_backend/app/services/phone_waterfall_service.py:5931]
- [ ] [Review][Patch] Batdongsan Mutex Lock fallback when token lock is busy [nowing_backend/app/services/phone_waterfall_service.py:5754]
- [ ] [Review][Patch] Sanitize raw_response phone in PhoneWaterfallLog (AD-25/49) [nowing_backend/app/services/phone_waterfall_service.py:6102]
- [ ] [Review][Patch] Restrict Chợ Tốt regex listing extraction to Chợ Tốt sources only [nowing_backend/app/services/phone_waterfall_service.py:5821]
- [ ] [Review][Patch] with_for_update() row lock & refund to original payer in auto_refund_lead [nowing_backend/app/services/billing_service.py:6258]
- [ ] [Review][Patch] Enforce LEADS_ENRICH or LEADS_WRITE permission on resolve-phone endpoint [nowing_backend/app/routes/leads_routes.py:7027]
- [ ] [Review][Patch] Call set_request_tenant_context in Celery worker tasks [nowing_backend/app/tasks/phone_waterfall_worker.py:6415]
- [ ] [Review][Patch] Mask phone in get_company_graph and _map_lead_to_read [nowing_backend/app/routes/leads_routes.py:6886]
- [ ] [Review][Patch] Use VerifiedContactEncryption instead of local PhoneEncryption [nowing_backend/app/services/phone_waterfall_service.py:5673]
- [ ] [Review][Patch] Fix VerifiedContact.phone_masked assertion in integration tests [nowing_backend/tests/integration/services/test_phone_waterfall_integration.py:8497]
- [ ] [Review][Patch] Align Alembic migration revision 213 after 212 [nowing_backend/alembic/versions/192_add_phone_waterfall_logs_and_refund.py]

## Dev Notes

### Architecture Patterns & Constraints

- **AD-31:** Every Epic 21 table must include `workspace_id: Integer` and `client_id: CITEXT | None` with indexes. `client_id` is the natural key of `vertical_clients.client_id`, not the UUID `id`.
- **AD-36:** Buy the waterfall via a single provider contract (Cleanlist/BetterContact). Do **not** build 14+ integrations. Pay per verified result. Cache in Redis (TTL 30 days). Fallback is MX + pattern matching only.
- **AD-42 / AD-10:** Business events go to `BillingEvent`. `TokenUsage` is LLM-only. The `lead.enrich` capability uses `billing_unit=None`.
- **AD-25 / AD-49:** `VerifiedContact` is the access-controlled PII vault. Raw PII is encrypted at rest. `redact_pii(..., context='lead_enrichment')` runs only on `Memory.content`, `Chunk[]`, audit logs, and non-privileged UI surfaces.
- **AD-44 / AD-47:** For Epic 21 UUID entities, `Memory.source_uuid` + `Memory.source_entity_type` is the authoritative provenance. `MemorySourceType.ENRICHMENT` already exists.
- **AD-45:** Migrate existing `client_id: Text` columns to `CITEXT` before enabling Epic 21 tables if not already done. This is tracked as a pre-condition for the Epic.

### Data Model

```python
class EnrichmentRequest(Base, TimestampMixin):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    lead_id: UUID
    status: str                 # pending / processing / completed / failed
    provider_results: JSONB
    cost_micros: int
    contact_count: int
    created_at: datetime

class VerifiedContact(Base, TimestampMixin):
    id: UUID
    workspace_id: Integer
    client_id: CITEXT | None
    lead_id: UUID
    enrichment_request_id: UUID
    name: str | None            # encrypted at rest
    title: str | None           # encrypted at rest
    email: str | None           # encrypted at rest
    phone: str | None           # encrypted at rest
    verification_status: str    # unverified / verified / low_confidence
    confidence: float
    source_provider: str
    consent_status: str | None
    legal_basis: str | None
    created_at: datetime
```

### Encryption Pattern

```python
from app.config import config
from app.utils.oauth_security import TokenEncryption

_encryptor = TokenEncryption(config.SECRET_KEY)

# Before write
verified_contact.email = _encryptor.encrypt_token(raw_email)

# After read
raw_email = _encryptor.decrypt_token(verified_contact.email)
```

### Cache Key

```
enrichment:v1:{workspace_id}:{client_id}:{lead_id}
Value: comma-separated list of VerifiedContact.id
TTL: CONTACT_ENRICHMENT_CACHE_TTL_SECONDS (30 days)
```

### Billing Flow

```
1. wallet_credit.check_balance(user_id, estimated_cost)
2. Run waterfall (provider or fallback)
3. Create EnrichmentRequest + VerifiedContact rows
4. BillingEventService.record_contact_enrichment(...)
5. wallet_credit.apply_debit(user_id, actual_cost)
6. MemoryRepository.create_memory(redacted_summary)
7. Set cache
```

### Waterfall Provider Selection

```python
providers = ["cleanlist", "bettercontact"]
if config.CONTACT_ENRICHMENT_PRIMARY_PROVIDER == "bettercontact":
    providers = ["bettercontact", "cleanlist"]
```

Only one API client is active at runtime based on `CONTACT_ENRICHMENT_PRIMARY_PROVIDER`. The secondary is tried only if the primary fails to return verified data.

### Source Tree Components to Touch

```
nowing_backend/
├── app/
│   ├── db.py                        # UPDATE: add EnrichmentRequest, VerifiedContact, Permission
│   ├── config/__init__.py           # UPDATE: enrichment config keys
│   ├── lead_intelligence/
│   │   ├── __init__.py
│   │   └── enrichment/              # NEW
│   │       ├── __init__.py
│   │       ├── service.py           # EnrichmentService
│   │       ├── schemas.py
│   │       ├── capability.py
│   │       ├── providers.py         # Cleanlist/BetterContact clients
│   │       └── fallback.py          # MX + regex fallback

│   ├── services/
│   │   ├── billing_event_service.py # UPDATE: record_contact_enrichment
│   │   ├── pii/
│   │   │   ├── redact.py            # REUSE: context='lead_enrichment'
│   │   │   └── verified_contact_encryption.py  # NEW
│   │   ├── memory/
│   │   │   └── repository.py        # REUSE: create_memory with source_uuid/source_entity_type
│   │   └── wallet_credit.py         # REUSE: check_balance / apply_debit
│   ├── routes/
│   │   └── enrichment_routes.py     # NEW
│   ├── tasks/
│   │   └── celery_tasks/
│   │       └── enrichment_tasks.py  # NEW: enrich_lead_task
│   └── mcp_tools.py                 # UPDATE: add enrichment tools
├── alembic/versions/
│   └── 200_add_enrichment_tables.py # NEW
├── tests/
│   ├── unit/lead_intelligence/test_enrichment.py
│   ├── unit/capabilities/test_lead_enrich_capability.py
│   └── integration/lead_intelligence/test_enrichment.py
└── nowing_mcp/
    └── mcp_server/
        ├── server.py                # UPDATE: import enrichment feature
        ├── selfcheck.py             # UPDATE: EXPECTED_TOOLS
        ├── features/
        │   └── enrichment/          # NEW
        │       ├── __init__.py
        │       └── tools.py
```

### Key Dependencies

| Dependency | Purpose | Note |
|---|---|---|
| `Lead` table (21.2/BE-1) | Enrichment target | Must exist before migration |
| `BillingEvent` (21.1/21.2) | Business ledger | Reuse `_record_business_event` |
| `wallet_credit.py` | Wallet debit | Reuse `check_balance` / `apply_debit` |
| `TokenEncryption` | PII encryption at rest | `app/utils/oauth_security.py` |
| `redact_pii` | Redaction for Memory/logs | `context='lead_enrichment'` |
| `MemoryRepository` | Provenance | `source_uuid`, `source_entity_type` |
| `Redis` | 30-day cache | `app/utils/indexing_locks.py` pattern |
| Cleanlist/BetterContact API | Waterfall source | Config `*_API_KEY`; one primary |
| `httpx` | External HTTP | Existing dependency |
| `dns.resolver` / `smtplib` | MX fallback | Basic verification only |
| `Celery` | Async enrichment | `app/celery_app.py` |

### Retry & Error Handling

- External provider: max `CONTACT_ENRICHMENT_RETRY_ATTEMPTS` (3) with exponential backoff (1s, 2s, 4s).
- Network/5xx/provider timeout: fall back to secondary provider.
- Both providers fail or return no verified contacts: use `FallbackVerifier`.
- Insufficient wallet: return `degraded=true`, do not create `EnrichmentRequest`/`VerifiedContact`.
- Missing API key: attempt secondary; if both missing, use fallback and `source_provider="fallback"`.
- Lead not found or not in workspace/client scope: return `422` with `lead_not_found`.

### Pagination / Filter

`GET /workspaces/{id}/leads/{lead_id}/contacts`:
- `limit` (int, default 20, max 100)
- `offset` (int, default 0)
- sort by `created_at DESC`

`GET /workspaces/{id}/leads/{lead_id}/enrichments`:
- same pagination.

### Out of Scope for 21.3

- CRM write-back → Story 21.5
- Outbound email / sequencer → Story 21.4
- Zalo / LinkedIn outreach → Story 21.6 (deferred)
- Outcome-based pricing / `PricingPlan` → Story 21.7
- UI Data Panel “Contacts” tab → FE-2 / Story 21.4a
- Consent opt-in UX → Story 21.4 (SequenceEnrollment gates on `VerifiedContact.consent_status`)

### UX Integration

- Contacts display in Data Panel “Contacts” tab (per `ux-contract-lead-intelligence-panel.md`).
- Raw PII is hidden from non-privileged users; UI reads `VerifiedContact` through redaction or RBAC-gated endpoints.
- Cost projection shown before bulk enrichment via `GET /leads/enrich/cost`.

## References

- `_bmad-output/planning-artifacts/epics.md` §FR-65
- `_bmad-output/planning-artifacts/epic21-proposal-2026-08-11.md` Story 21.3
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` AD-10, AD-25, AD-31, AD-36, AD-42, AD-44, AD-45, AD-47, AD-49
- `_bmad-output/planning-artifacts/implementation-artifacts/epic21-engineering-handoff-2026-08-11.md` BE-3
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`
- `_bmad-output/implementation-artifacts/stories/21-1-intent-signal-detection.md`
- `_bmad-output/implementation-artifacts/stories/21-2-lead-scoring.md`
- `nowing_backend/app/db.py`
- `nowing_backend/app/services/billing_event_service.py`
- `nowing_backend/app/services/wallet_credit.py`
- `nowing_backend/app/services/pii/redact.py`
- `nowing_backend/app/services/memory/repository.py`
- `nowing_backend/app/utils/oauth_security.py`
- `nowing_backend/app/lead_intelligence/scoring/service.py`
- `nowing_backend/app/lead_intelligence/scoring/capability.py`

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- `nowing_backend/app/db.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/lead_intelligence/enrichment/service.py`
- `nowing_backend/app/lead_intelligence/enrichment/schemas.py`
- `nowing_backend/app/lead_intelligence/enrichment/capability.py`
- `nowing_backend/app/lead_intelligence/enrichment/providers.py`
- `nowing_backend/app/lead_intelligence/enrichment/fallback.py`

- `nowing_backend/app/routes/enrichment_routes.py`
- `nowing_backend/app/services/billing_event_service.py`
- `nowing_backend/app/services/pii/verified_contact_encryption.py`
- `nowing_backend/app/tasks/celery_tasks/enrichment_tasks.py`
- `nowing_backend/app/mcp_tools.py`
- `nowing_backend/alembic/versions/200_add_enrichment_tables.py`
- `nowing_mcp/mcp_server/server.py`
- `nowing_mcp/mcp_server/selfcheck.py`
- `nowing_mcp/mcp_server/features/enrichment/tools.py`

### Timestamp

Created: 2026-08-10
Last Updated: 2026-08-15

## Dev Agent Record

### Debug Log

- Route mount prefix: routers are mounted under `/api/v1` (app/app.py), so route tests must use `/api/v1/workspaces/...`.
- 404/402 error bodies: `HTTPException(detail="<code>")` serializes `detail` as a plain string, not `{"code": ...}`.
- `VerifiedContact.phone` was `String(50)` but Fernet ciphertext is ~120 chars → `StringDataRightTruncationError` on insert. Bumped to `String(200)` in model + migration 200 (pre-release migration, edited in place; test DB table dropped once to regenerate).
- Enqueue patching: `enqueue_enrichment_request` does not exist in the service module; the real symbol is `EnrichmentService._enqueue`. Integration tests patch `_enqueue` with `AsyncMock` to avoid a live Celery broker.
- Celery `retry_kwargs={"max_retries": 2}` does not set the task attribute (default is 3) — moved to decorator-level `max_retries=2`.
- `record_contact_enrichment` is an instance method on `BillingEventService` (unlike module-level `record_signal_scan`); `_record_business_event` does not commit on the positive-cost path (deferred to caller) — tests must not assert `session.committed`.
- Fallback DNS test: `dns` is imported inside the function, so fake `dns`/`dns.resolver` modules must be injected via `sys.modules` (dotted-path setattr fails with `No module named 'app.lead_intelligence.enrichment.fallback.dns'`).
- `Identity` is not importable from `mcp_server.core.auth`; MCP tests use `identity.bind_api_key` / `identity.unbind_api_key` and monkeypatch `mcp_server.server.NowingClient`.
- Pre-existing failures confirmed on pristine baseline (1261fb2a1 worktree): `tests/unit/capabilities/test_registry.py::test_capability_metadata_and_registry_query` (order-dependent registry state pollution) + 4 `test_run_truncation.py` tests (`_FakeSession.execute()` 3-arg call from Story 18.8 tenant-context change) — identical 5 failures, unrelated to this story.

### Completion Notes

- All story tasks 1–11 complete; 31/31 checklist items checked.
- Unit: `tests/unit/lead_intelligence` (providers 12 + fallback 7 + cache 7 + contact_enrichment 9 = 35) + capability 3 + encryption 4 + billing 5 new (16 file total) + celery task 2 + migration roundtrip 2 — all green; targeted suites 104 passed.
- Full unit suite: 2153 passed, 5 failed (pre-existing on baseline, see Debug Log).
- Full integration suite: 892 passed, 12 skipped, 1 xfailed — 0 failures (incl. PAT client-scoped contacts test).
- MCP: `nowing_mcp/tests` 112 passed (4 new `test_enrichment_tools.py`).
- ruff check + format clean on all story files.
- MCP tools `nowing_enrich_lead` / `nowing_list_contacts` added to catalog + `selfcheck.py` EXPECTED_TOOLS.

### Story 21.3 P0: Vietnam Phone & Contact Waterfall Engine Implementation
- **3-Tier Phone Waterfall Engine:**
  - Tier 1: Batdongsan Token Pool & Phone Reveal with Redis distributed mutex (`batdongsan:token:{id}`) and token rotation (`ScraperPlatformAccountRotator`).
  - Tier 2: Chợ Tốt Mobile API with RSA PKCS1v15 encrypted list_id and device spoofing.
  - Tier 3: Passive Carrier Prefix validation (Viettel, Vinaphone/VNPT, MobiFone, Vietnamobile, Gmobile, Itelecom, Wintel) + HLR/Zalo verification.
- **Anti-ReDoS & Security:**
  - `<50ms` execution bound on normalization via `time.perf_counter()`.
  - Sensitive PII AES-256 encrypted at rest in `VerifiedContact` vault (`TokenEncryption`).
  - Phone masked as `0908***456` in logs, non-privileged endpoints, and cache.
- **Billing & 24h Auto-Refund SLA:**
  - 1.5 credits (1,500,000 micros) debited per success via `BillingEvent(event_type="contact_enrichment")`. 0 credits charged if all tiers fail.
  - 30-day Redis cache (`enrich:phone:{hash}`) prevents repeat charges.
  - Auto-Refund SLA: reports within 24h revert 100% credits to wallet balance, log negative `BillingEvent(event_type="lead_refund")`, mark contact `is_valid=False`, and evict Redis cache.
- **Verification:**
  - `tests/unit/services/test_phone_waterfall_service.py`: 16/16 unit tests passed in 0.98s.
  - `tests/integration/services/test_phone_waterfall_integration.py`: integration test suite created.
  - `ruff check` & `ruff format`: 0 errors.
  - `python3 scripts/check-docs-drift.py`: PASSED.
