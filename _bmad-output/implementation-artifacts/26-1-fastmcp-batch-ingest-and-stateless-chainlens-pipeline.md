# Story 26.1: Batch Lead Ingestion, Stateless ChainLens Ingestion Pipeline & PII Vault

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a backend platform engineer,
I want Nowing FastAPI to expose a high-throughput authenticated REST batch lead ingestion endpoint (`POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`) and an idempotent ingestion endpoint for stateless ChainLens web crawls (`POST /v1/chainlens/ingest`),
So that autonomous sidecar agents (`dsh-worker`) and ChainLens crawlers can ingest hundreds of leads and research chunks directly into PostgreSQL 16 pgvector without distributed deadlocks, with PII encrypted at rest, and instant Zero-Cache UI synchronization.

---

## Acceptance Criteria

### AC-1: Batch Lead Ingestion Endpoint (`POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`)
- **Given** an authenticated request from `dsh-worker` with a batch of 1..100 leads,
- **When** `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` is called with payload schema `BatchLeadIngestPayload`,
- **Then** the endpoint:
  1. Validates the URL `workspace_id`, `task_id`, and `leads` array (`min_length=1`, `max_length=100`) using Pydantic schema validation; rejects any lead with all of `phone`, `email`, and `domain` empty as degenerate.
  2. Generates a single blind HMAC-SHA256 hash `value_hmac` per lead using the canonical normalized contact string form `phone=<normalized_phone>|email=<normalized_email>|domain=<domain>` and the configured `HMAC_SECRET`.
  3. Checks `global_dnc_records` and `workspace_dnc_records` for matching `value_hmac`. If matched, the lead is stored with `status = 'blacklisted'` and contact details are suppressed; a record is not created in `verified_contacts`.
  4. Persists PII in `verified_contacts` using the existing `VerifiedContactEncryption` service (Fernet/TokenEncryption).
  5. Enforces a per-workspace rate limit (e.g., 30 batches/minute) and returns `HTTP 200 OK` with JSON `BatchLeadIngestResponse`:
     ```json
     {
       "ingested_count": 0,
       "skipped_blacklisted_count": 0,
       "failed_count": 0,
       "execution_time_ms": 0.0,
       "lead_ids": []
     }
     ```
     in < 200ms total for 100 items.

### AC-2: Deterministic Sorting & Concurrency Deadlock Prevention (AD-109)
- **Given** concurrent worker threads or sidecar processes ingesting intersecting sets of leads into the same workspace,
- **When** executing bulk upsert operations on `leads` and `verified_contacts` tables,
- **Then** the repository MUST:
  1. Ensure `leads.value_hmac` and `verified_contacts.value_hmac` are `NOT NULL` and guarded by a `UNIQUE(workspace_id, value_hmac)` constraint.
  2. Deterministically sort all batch items in memory by `value_hmac ASC` before acquiring row-level locks and executing:
     ```sql
     INSERT INTO leads (
         id, workspace_id, client_id, source, source_url, company_name, domain,
         industry, company_size, location, fit_score, intent_score, composite_score,
         status, enriched, value_hmac, created_at, updated_at
     )
     VALUES (...)
     ON CONFLICT (workspace_id, value_hmac)
     DO UPDATE SET
         fit_score = GREATEST(leads.fit_score, EXCLUDED.fit_score),
         composite_score = GREATEST(COALESCE(leads.composite_score, 0), COALESCE(EXCLUDED.composite_score, 0)),
         updated_at = NOW()
     RETURNING id, value_hmac, workspace_id;
     ```
- **And** verified under a concurrency stress test with 20 parallel async threads inserting overlapping batches with 0 `DeadlockDetected` (`40P01`) exceptions and 0 duplicate `value_hmac` NULL rows.

### AC-3: Stateless ChainLens Chunk Ingestion Pipeline (`POST /v1/chainlens/ingest`) (AD-101)
- **Given** completed web crawl chunks received from the stateless ChainLens Research Engine,
- **When** ChainLens calls `POST /v1/chainlens/ingest` with `ChainLensIngestPayload`,
- **Then** the endpoint:
  1. Validates the incoming token via a service-to-service API key or `ChainLensServiceAuth` (see OQ-7 / Story 39-1).
  2. Computes deterministic `UUIDv5` chunk IDs using namespace `uuid.NAMESPACE_URL`: `UUIDv5(NAMESPACE_URL, f"{source_url}:{chunk_index}:{sha256(content).hexdigest()}")`.
  3. Generates vector embeddings with a single canonical dimension (1536) in batch via `EmbeddingService`. Local BGE models are not used until an AD amendment explicitly introduces a dual-embedding strategy.
  4. Inserts chunks into the PostgreSQL 16 `chunks` table with `ON CONFLICT (id) DO NOTHING`. `chunks.id` is a UUID column.
  5. Records/updates the ingest job lifecycle in `chainlens_ingest_jobs` with `status` (`ok`, `partial`, `noop`), `chunks_received_count`, `chunks_ingested_count`, and `noop_source_ids`.

### AC-4: Zero-Cache CDC Isolation & Reactivity (AD-104)
- **Given** newly inserted or updated leads in the `leads` table,
- **When** PostgreSQL Logical WAL Replication triggers `zero_publication`,
- **Then** `zero-cache` broadcasts mutation events to connected web clients in < 10ms.
- **And** the `zero_publication` column list for `leads` includes only: `id`, `workspace_id`, `title`, `company_name`, `domain`, `source_url`, `fit_score`, `status`, `enriched`, `created_at`, `updated_at`. It does NOT include `value_hmac`, `is_blacklisted`, or any PII-derived columns.
- **And** the `chunks` table remains strictly excluded from `zero_publication` to prevent high-volume vector data from choking WAL replication bandwidth.

### AC-5: Hermetic Quality Testing & $0 API Cost Gate (AD-107)
- **Given** test execution in local development and CI/CD pipelines,
- **When** running pytest unit and integration test suites,
- **Then**:
  1. All external embedding and LLM calls use hermetic in-memory fakes/mocks or Golden Replay Cassettes (`.sse.jsonl`), passing with $0 external token cost.
  2. Tests cover PII encryption, HMAC computation, deterministic sorting, concurrency (20 overlapping async threads, 0 deadlocks), ChainLens callback with fake transport, and `zero_publication` column assertions.
  3. `ruff check` and `ruff format` pass with no errors.

### AC-6: Contact Unlock Billing (AD-105 / AD-110)
- **Given** a lead with `verified_contacts` containing encrypted phone/email,
- **When** an authenticated workspace member calls `POST /api/v1/workspaces/:workspace_id/leads/:lead_id/contacts/:contact_id/unlock`,
- **Then** the endpoint:
  1. Verifies `verified_contacts.is_unlocked = FALSE` and the attributed workspace owner has `User.credit_micros_balance >= 1_500`.
  2. In a single transaction: decrypts PII, sets `is_unlocked = TRUE`, calls `wallet_credit.apply_debit(user_id, 1_500, event_type='contact_unlock')`, and writes a `BillingEvent` with `event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `cost_micros=1_500`, `reason='contact_unlock'`.
  3. Returns the decrypted phone/email only after a successful debit; if decryption or debit fails, returns a 4xx error without leaking PII.

---

## Tasks / Subtasks

- [ ] **Task 1: Database Schema & Migration (AC: 1, 2, 4)**
  - [ ] Create the next Alembic revision for schema changes: `cd nowing_backend && uv run alembic revision --autogenerate -m "add lead batch and chainlens ingest"` and review the generated `nowing_backend/alembic/versions/<revision_id>_add_lead_batch_and_chainlens_ingest.py`.
  - [ ] Ensure `leads.value_hmac` and `verified_contacts.value_hmac` are `NOT NULL` and part of a `UNIQUE(workspace_id, value_hmac)` constraint.
  - [ ] Add `is_blacklisted`/`status` support to `leads` (e.g., `is_blacklisted BOOLEAN DEFAULT FALSE` or `blacklisted` value in the `status` enum).
  - [ ] Add `is_unlocked BOOLEAN DEFAULT FALSE` and `pii_access_audit_logs JSONB` to `verified_contacts`.
  - [ ] Migrate `chunks.id` to `UUID` type (or add `chunk_uuid UUID UNIQUE` and update primary key in a follow-up migration).
  - [ ] Verify `workspace_dnc_records` and `global_dnc_records` are used for blacklist checks; do not create `pii_blacklists` unless an explicit merge migration is written.

- [ ] **Task 2: PII Vault, HMAC & Blind Hash Utility (AC: 1, 2)**
  - [ ] Implement/extend `app/services/pii/verified_contact_encryption.py` (Fernet/TokenEncryption) to encrypt `phone`/`email` at rest.
  - [ ] Implement `app/services/lead_batch_service.py` helper `compute_contact_hmac(phone, email, domain, workspace_id) -> str` using `HMAC_SHA256("phone=<...>|email=<...>|domain=<...>", HMAC_SECRET)`.
  - [ ] Normalize phone (E.164), email (lowercase), and domain before HMAC.

- [ ] **Task 3: Batch Lead Ingestion Service & Schemas (AC: 1, 2, 4)**
  - [ ] Create Pydantic schemas in `nowing_backend/app/schemas/lead_batch_ingest.py`:
    - [ ] `LeadItemPayload`: `source_url (str)`, `company_name (str)`, `title (str | None)`, `domain (str | None)`, `contact_name (str | None)`, `phone (str | None)`, `email (str | None)`, `fit_score (float | None)`, `intent_signals (list[str])`, `extracted_metadata (dict[str, Any])`.
    - [ ] `BatchLeadIngestPayload`: `task_id (str)`, `leads (list[LeadItemPayload] = Field(min_length=1, max_length=100))`.
    - [ ] `BatchLeadIngestResponse`: `ingested_count (int)`, `skipped_blacklisted_count (int)`, `failed_count (int)`, `execution_time_ms (float)`, `lead_ids (list[UUID])`.
  - [ ] Implement `nowing_backend/app/services/lead_batch_service.py`:
    - [ ] Reject degenerate leads (no phone/email/domain).
    - [ ] Deterministic in-memory sort by `value_hmac ASC`.
    - [ ] Check batch against `workspace_dnc_records` and `global_dnc_records` in a single query.
    - [ ] Execute bulk upsert in PostgreSQL with `ON CONFLICT (workspace_id, value_hmac) DO UPDATE`.
    - [ ] Insert encrypted contacts into `verified_contacts` only for non-blacklisted leads.

- [ ] **Task 4: Batch Ingestion REST Route (AC: 1)**
  - [ ] Create `nowing_backend/app/routes/lead_batch_routes.py`:
    - [ ] `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`: Authenticated endpoint receiving `BatchLeadIngestPayload`.
    - [ ] Enforce per-workspace rate limit (e.g., 30 batches/minute).
  - [ ] Register the router in `nowing_backend/app/app.py`.
  - [ ] No MCP tool is required in this story; DSH sidecar calls the REST endpoint directly.

- [ ] **Task 5: Stateless ChainLens Chunk Ingestion Endpoint (AC: 3)**
  - [ ] Implement `POST /v1/chainlens/ingest` in `nowing_backend/app/routes/chainlens_internal.py`:
    - [ ] Schema `ChainLensIngestPayload`: `workspace_id (int)`, `scraper_id (str)`, `run_id (str)`, `chunks (list[ChainLensChunkItem])`.
    - [ ] Validate service-to-service API key or `ChainLensServiceAuth`.
    - [ ] Deterministic `UUIDv5` chunk ID generation: `uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.source_url}:{idx}:{hashlib.sha256(chunk.content.encode()).hexdigest()}")`.
    - [ ] Batch embedding generation with dimension 1536.
    - [ ] Insert into `chunks` table with `ON CONFLICT (id) DO NOTHING`.
    - [ ] Update `chainlens_ingest_jobs` with `status`, `chunks_received_count`, `chunks_ingested_count`, and `noop_source_ids`.

- [ ] **Task 6: Contact Unlock Billing (AD-105 / AD-110)**
  - [ ] Implement `POST /api/v1/workspaces/:workspace_id/leads/:lead_id/contacts/:contact_id/unlock`.
  - [ ] Before unlock, check `verified_contacts.is_unlocked = FALSE` and owner `User.credit_micros_balance >= 1_500`.
  - [ ] In one transaction: decrypt PII, set `is_unlocked = TRUE`, call `wallet_credit.apply_debit(user_id, 1_500, event_type='contact_unlock')`, and write `BillingEvent(event_type='contact_unlock', event_entity_type='verified_contact', cost_micros=1_500, reason='contact_unlock')`.
  - [ ] Unit/integration tests for insufficient balance, already unlocked, successful unlock, and failed decryption.

- [ ] **Task 7: Verification & Automated Test Suites (AC: 1, 2, 3, 5)**
  - [ ] Unit tests for HMAC, PII encryption, and sorting in `tests/unit/services/test_lead_batch_service.py`.
  - [ ] Unit tests for batch ingestion in `tests/unit/routes/test_lead_batch_ingest.py`.
  - [ ] Concurrency deadlock stress test (20 parallel async workers) in `tests/integration/services/test_lead_batch_concurrency.py`.
  - [ ] Integration tests for ChainLens ingestion in `tests/integration/routes/test_chainlens_ingest_pipeline.py` using fake ChainLens callback.
  - [ ] Verify `zero_publication` column list for `leads` (must exclude `value_hmac`/`is_blacklisted`/`pii_access_audit_logs`) and ensure `chunks` is excluded.
  - [ ] `ruff check` and `ruff format` pass.

---

## Dev Notes

### 1. Architecture Compliance & Invariants
- **AD-101 (Stateless ChainLens Ingestion):** ChainLens is a stateless crawler. Chunks are streamed to Nowing via `POST /v1/chainlens/ingest`; Nowing stores chunks with deterministic `UUIDv5` `id`. The legacy `NowingIngestService` (`POST /v1/ingest/scraper`) must be retired.
- **AD-104 (Zero-Cache CDC Isolation):** `leads` table is published to `zero_publication` with an explicit, PII-safe column list. `chunks` table is explicitly excluded to preserve WAL streaming performance.
- **AD-105 & AD-110 (PII Vault & Decree 13 Compliance):** Raw phone and email are encrypted at rest in `verified_contacts` using the existing `VerifiedContactEncryption` (Fernet/TokenEncryption). AES-256-GCM is not used; Fernet/TokenEncryption is the canonical service. Deduplication uses blind HMAC-SHA256 (`value_hmac`). Blacklist checks use existing DNC tables. Contact unlock debits 1.5 credits via `BillingEvent`. Opt-out workflow handles retroactive suppression, credit refund, and deletion/anonymization.
- **AD-107 (Hermetic $0 Testing):** Tests must mock embedding generation and use SQLite / test PostgreSQL without calling live OpenAI or external APIs.
- **AD-109 (Deterministic Sorting & Deadlock Prevention):** When multiple concurrent transactions execute bulk `INSERT ... ON CONFLICT`, PostgreSQL can deadlock if rows are inserted in different order. Sorting by `value_hmac ASC` enforces a universal lock acquisition sequence, eliminating deadlocks.

### 2. Encryption Implementation Pattern
Use the existing `VerifiedContactEncryption` service (`app/services/pii/verified_contact_encryption.py`) which wraps `cryptography.fernet.Fernet` or `TokenEncryption`.

```python
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

service = VerifiedContactEncryption()
encrypted_phone = service.encrypt(phone)   # returns URL-safe base64 ciphertext
plaintext = service.decrypt(encrypted_phone)
```

Do not introduce a second AES-256-GCM PII cipher. If the security team later requires AES-GCM, it must be adopted as a separate architecture amendment with a decrypt/re-encrypt migration plan.

### 3. Blind HMAC-SHA256 Deduplication Pattern
```python
import hashlib
import hmac
import re

def normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", phone)
    if cleaned.startswith("0") and len(cleaned) == 10:
        cleaned = "+84" + cleaned[1:]
    return cleaned

def compute_contact_hmac(workspace_id: int, phone: str | None, email: str | None, domain: str | None, secret_key: str) -> str:
    norm_phone = normalize_phone(phone)
    norm_email = (email or "").strip().lower()
    raw = f"phone={norm_phone}|email={norm_email}|domain={domain or ''}"
    return hmac.new(secret_key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
```

### 4. Deterministic Bulk Upsert SQL
```python
# Sort batch items by value_hmac ASC
sorted_leads = sorted(leads_batch, key=lambda x: x["value_hmac"])

stmt = insert(Lead).values(sorted_leads)
upsert_stmt = stmt.on_conflict_do_update(
    index_elements=["workspace_id", "value_hmac"],
    set_={
        "fit_score": func.greatest(Lead.fit_score, stmt.excluded.fit_score),
        "composite_score": func.greatest(
            func.coalesce(Lead.composite_score, 0),
            func.coalesce(stmt.excluded.composite_score, 0),
        ),
        "updated_at": func.now(),
    },
).returning(Lead.id, Lead.value_hmac)
```

---

### Project Structure Notes

- **Existing Files Modified:**
  - `nowing_backend/app/db.py`: Add `is_unlocked`/`pii_access_audit_logs` to `verified_contacts`, make `value_hmac` NOT NULL, add `UNIQUE(workspace_id, value_hmac)`, migrate `chunks.id` to UUID, add `is_blacklisted`/`status` to `leads`.
  - `nowing_backend/app/app.py`: Mount `lead_batch_routes` router.
  - `nowing_backend/app/services/pii/verified_contact_encryption.py`: Verify/extend PII encryption for phone/email.
  - `nowing_backend/app/services/lead_batch_service.py`: New service for HMAC, blacklist check, sorted bulk upsert.
  - `nowing_backend/app/routes/chainlens_internal.py`: Add/update `POST /v1/chainlens/ingest` handler.
  - `nowing_backend/app/routes/lead_pipeline_routes.py` (or new `lead_routes.py`): Add `POST .../contacts/:contact_id/unlock` handler.
  - `nowing_backend/app/zero_publication.py`: Explicit `leads` column list and continue to exclude `chunks`.

- **New Files Created:**
  - `nowing_backend/alembic/versions/<revision_id>_add_lead_batch_and_chainlens_ingest.py`: Database migration generated by `uv run alembic revision --autogenerate -m "add lead batch and chainlens ingest"` (actual revision ID assigned by Alembic).
  - `nowing_backend/app/schemas/lead_batch_ingest.py`: Request/Response schemas for batch lead ingestion.
  - `nowing_backend/app/services/lead_batch_service.py`: HMAC, blacklist check, deadlock-free batch ingestion logic.
  - `nowing_backend/app/routes/lead_batch_routes.py`: FastAPI route handler for `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`.
  - `nowing_backend/tests/unit/services/test_lead_batch_service.py`: Unit tests for HMAC, sorting, and PII encryption.
  - `nowing_backend/tests/unit/routes/test_lead_batch_ingest.py`: Unit tests for REST endpoint.
  - `nowing_backend/tests/integration/services/test_lead_batch_concurrency.py`: 20-thread concurrency test.
  - `nowing_backend/tests/integration/routes/test_chainlens_ingest_pipeline.py`: Integration tests for `/v1/chainlens/ingest`.

---

### References

- Architecture Contract: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (Sections 2, 3, 4, 5)
- Implementation Readiness Report: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md`
- Epics & Stories Specification: `_bmad-output/planning-artifacts/epics.md` (Story 26.1, Lines 3308–3320)
- Existing Partitioned Leads Table: `nowing_backend/alembic/versions/217_partition_leads_table_zero_downtime.py`
- Existing ChainLens Internal Routes: `nowing_backend/app/routes/chainlens_internal.py`
- Zero-Cache Publication Configuration: `nowing_backend/app/zero_publication.py`
- Unit Economics Hypothesis: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/UNIT-ECONOMICS-HYPOTHESIS.md`
- Final v5 Review: `_bmad-output/review-artifacts/epic-26-architecture-review-2026-08-17-v5.md`

---

## Validation & Developer Context (2026-08-17)

This section captures code-level guardrails discovered during the `bmad-create-story` validation run. It is meant to prevent the dev agent from reinventing wheels, picking wrong files, or introducing regressions.

### 1. Existing Patterns to Reuse

| Concern | Existing Code | What to Reuse |
|---|---|---|
| PII encryption at rest | `app/services/pii/verified_contact_encryption.py` | `VerifiedContactEncryption.encrypt(value)` / `decrypt(value)` and `encrypt_contact(contact)` for `name`/`title`/`email`/`phone`. Do NOT write a new AES-GCM cipher. |
| HMAC hashing | `app/lead_intelligence/dnc/normalizer.py` | `normalize_phone_e164`, `normalize_email`, `normalize_domain`, `hash_phone_hmac(value, config.SECRET_KEY)`. Use `config.SECRET_KEY` as HMAC key unless a dedicated `HMAC_SECRET` is added. |
| DNC blacklist lookup | `app/lead_intelligence/dnc/service.py` | `DncComplianceService` and `WorkspaceDncRecord`/`GlobalDncRecord` tables. Do NOT create a new `pii_blacklists` table (AD-110 Rule 1). |
| Wallet + BillingEvent + spend cap | `app/services/billing_event_service.py` | `_record_business_event` / `BillingEventService.record_contact_enrichment` pattern. It calls `WorkspaceCreditService.record_spend` (per-seat cap) → `wallet_credit.check_balance` → `wallet_credit.apply_debit` and writes `BillingEvent` with idempotency. Use this for contact unlock rather than calling `wallet_credit.apply_debit` directly. |
| Rate limiting | `app/rate_limiter.py` | Shared `Limiter` from `slowapi`. For per-workspace rate limit use a custom key like `f"lead_batch:{workspace_id}"` and call `limiter.limiter.hit(RateLimitItemPerMinute(30), key)`. |
| Embedding | `app/utils/document_converters.py` | `embed_text(text)` / `embed_texts(texts)` use `config.embedding_model_instance`. For 1536-dim canonical output, ensure `EMBEDDING_MODEL` env points to a 1536-dim model (e.g., OpenAI text-embedding-3-small) or add a dedicated `CHAINLENS_EMBEDDING_MODEL` config. See risk below. |
| Router mounting | `app/app.py` | `app.include_router(lead_batch_router, prefix="/api/v1")`. `chainlens_internal` already mounted at `/v1`; add `POST /chainlens/ingest` there. |

### 2. Database Migration Gaps

| Table / Column | Current State | Required for Story 26.1 |
|---|---|---|
| `leads.value_hmac` | `String(64)`, nullable | `NOT NULL` and `UNIQUE(workspace_id, value_hmac)`. **Caution:** existing rows with NULL `value_hmac` will block a plain `ALTER COLUMN NOT NULL`; backfill with `generate_lead_hmac` or default to a deterministic value first. |
| `leads.status` | `String(50)`, default `new` | Add `'blacklisted'` enum value. Consider using `status` instead of a separate `is_blacklisted` boolean to avoid adding a new column. |
| `verified_contacts.is_unlocked` | **Missing** | Add `Boolean DEFAULT FALSE`. |
| `verified_contacts.pii_access_audit_logs` | **Missing** | Add `JSONB DEFAULT '[]'`. |
| `verified_contacts.value_hmac` | **Missing** | Add `String(64)` and `UNIQUE(workspace_id, value_hmac)` for contact-level dedup/atomic upsert. |
| `chunks.id` | `Integer` (via `BaseModel`) | **Architecture requires UUID.** This is a heavy migration. Option A: alter `chunks.id` to `UUID` (risky for existing rows). Option B: add `chunk_uuid UUID UNIQUE` and a migration/copy plan. Option C: create a new `chainlens_chunks` table with UUID PK. **Recommend raising a decision record before dev starts.** |
| `chunks.embedding` | `Vector(config.embedding_model_instance.dimension)` | Column dimension depends on env. If env uses 1024-dim BGE, 1536-dim vectors cannot be stored. Address via config or separate `embedding_1536` column. |

### 3. Critical Risks & Open Questions

1. **Chunks primary key type.** Architecture AD-101 says `chunks.id` MUST be UUID. Existing `Chunk` model inherits `BaseModel` which sets `id = Integer`. Changing this in place is a breaking schema change. The dev agent must either (a) get an architecture amendment, or (b) implement a safe migration plan before AC-3 can be considered done. Do not gloss over this.
2. **Embedding dimension mismatch.** The `EmbeddingService` mentioned in the story does not exist as a named class. The code uses `config.embedding_model_instance.embed*`. The `chunks.embedding` column is dimensioned by the configured model. The story says "1536-dim canonical". If `EMBEDDING_MODEL` is a 1024-dim BGE model, the column will be 1024 and 1536-dim vectors will fail. The dev agent must verify the configured model dimension and either adjust config or alter the column.
3. **Contact unlock billing path.** The story currently says "call `wallet_credit.apply_debit(user_id, 1_500)` and write `BillingEvent`". The correct path is to add `BillingEventService.record_contact_unlock(...)` (or use `_record_business_event`) because it already enforces the workspace per-seat spend cap via `WorkspaceCreditService.record_spend`, checks wallet balance, and writes the `BillingEvent` atomically. This avoids double-spend and missed spend-cap enforcement.
4. **NowingIngestService vs new ChainLens -> Nowing flow.** `app/services/chainlens/ingest.py` (`NowingIngestService`) sends chunks from Nowing to ChainLens (`POST /v1/ingest/scraper`). The new `POST /v1/chainlens/ingest` is the reverse direction and should be implemented in a new module (e.g., `app/services/chainlens/nowing_ingest.py` or `app/services/chainlens_reception.py`) and a new route. Do not add the new logic to `NowingIngestService`; the architecture says the two directions must not coexist.
5. **`verified_contacts` uniqueness.** The story implies `ON CONFLICT (workspace_id, value_hmac) DO UPDATE` on `verified_contacts`. This requires `value_hmac` column and a unique constraint. Currently `VerifiedContact` has no `value_hmac`. Add it in the migration.
6. **Zero publication for `leads`.** `app/zero_publication.py` has `LEADS_COLS` that currently does NOT include `value_hmac`. Keep it that way. If you add `is_blacklisted` as a separate column, do NOT add it to `LEADS_COLS`; use `status='blacklisted'` instead, which is already published. `chunks` is correctly not in `ZERO_PUBLICATION`.

### 4. Files to Read Before Coding

- `app/services/pii/verified_contact_encryption.py` — PII encryption contract.
- `app/lead_intelligence/dnc/normalizer.py` and `app/lead_intelligence/dnc/service.py` — HMAC + DNC lookup.
- `app/services/billing_event_service.py` — canonical billing path.
- `app/services/wallet_credit.py` — wallet debit primitive.
- `app/services/workspace_credit_service.py` — spend cap enforcement (recently added `record_spend`).
- `app/routes/chainlens_internal.py` — where to add `POST /chainlens/ingest`.
- `app/db.py` — `Lead`, `VerifiedContact`, `Chunk`, `BillingEvent`, `WorkspaceDncRecord`, `GlobalDncRecord` models.
- `app/zero_publication.py` — Zero CDC column list.
- `app/utils/document_converters.py` — embedding helper.
- `app/rate_limiter.py` — rate limiting.

### 5. Validation Verdict

- Story 26.1 is **ready-for-dev** after the dev agent acknowledges the two hard blockers above (`chunks.id` UUID migration and embedding dimension) and chooses an approach before implementation.
- Minor spec updates needed in Task 7 (use `BillingEventService` pattern) and Task 5 (retire `NowingIngestService` and create new service).
- No new dependencies appear required beyond existing `slowapi`, `httpx`, `pgvector`, `cryptography`/`TokenEncryption`.

---

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High) / Antigravity Orchestrator

### Debug Log References

- Verified PostgreSQL 16 schema compatibility for partitioned tables.
- Verified Zero-Cache replication publication constraints.
- Verified absence of forward dependencies for Story 26.1.

### Completion Notes List

- Story 26.1 updated to align with architecture review v2/v3/v5 findings.
- REST endpoint `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` is canonical; no MCP tool in scope.
- HMAC uses canonical normalized contact string; `value_hmac` is `NOT NULL` and `UNIQUE` per workspace.
- PII encryption uses existing `VerifiedContactEncryption` (Fernet/TokenEncryption); AES-256-GCM is not used.
- Blacklist checks use existing `workspace_dnc_records` / `global_dnc_records`.
- ChainLens chunk ingestion uses single 1536-dimension embeddings and `UUID` `chunks.id`.
- Contact unlock billing uses `wallet_credit.apply_debit` + `BillingEvent` with 1,500 `credit_micros`.
- Marked status as `ready-for-dev`.

### File List

- `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`
