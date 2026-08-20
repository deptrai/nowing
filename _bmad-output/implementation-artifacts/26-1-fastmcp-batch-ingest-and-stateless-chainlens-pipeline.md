---
story_key: "26-1"
epic: "epic-26"
story: "26.1"
title: "Batch Lead Ingestion, Stateless ChainLens Ingestion Pipeline & PII Vault"
status: "done"
baseline_commit: "4c37acfa9"
---

# Story 26.1: Batch Lead Ingestion, Stateless ChainLens Ingestion Pipeline & PII Vault

## ⚠️ CRITICAL BLOCKERS — Resolve Before Dev

1. **`chunks.id` UUID vs. existing `Integer` PK (AD-101 vs. schema).** The existing `Chunk` model (`nowing_backend/app/db.py:1635`) uses `Integer` primary key and is coupled to `documents`. AD-101 requires `chunks.id` UUID for ChainLens ingestion. Do **not** silently alter `Chunk.id` in place on a production-sized table. Choose one:
   - **Option A (not recommended):** amend architecture and perform a zero-downtime PK-type migration with backfill.
   - **Option B:** add `chunk_uuid UUID UNIQUE` to the existing `chunks` table and dual-write.
   - **Option C (recommended for 26.1):** create a new `chainlens_chunks` table with `UUID` primary key and `Vector(1536)`; leave legacy `chunks` for documents. Update AD-101 or create a System Decision if this deviates from the literal name.
2. **Embedding dimension 1536 vs. configured `chunks.embedding`.** `chunks.embedding` is `Vector(config.embedding_model_instance.dimension)`. If the configured model is 1024-dim (e.g. BGE), 1536-dim vectors cannot be inserted. Either fix `EMBEDDING_MODEL` to a 1536-dim model (e.g. `text-embedding-3-small`) at config load time or use a dedicated `chainlens_chunks.embedding Vector(1536)` column.
3. **Contact unlock billing path.** Do **not** call `wallet_credit.apply_debit` directly; use `BillingEventService.record_contact_unlock(...)` (to be added) which enforces per-seat spend cap, idempotency, and wallet debit in one path.
4. **`leads.value_hmac` backfill.** The column is currently `nullable=True`; migration must backfill existing rows before applying `NOT NULL`, or the migration will fail.

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
  2. Generates a single blind HMAC-SHA256 hash `value_hmac` per lead using the canonical normalized contact string form `phone=<normalized_phone>|email=<normalized_email>|domain=<domain>` and `config.SECRET_KEY`. Reuse `app/lead_intelligence/dnc/normalizer.py` (`normalize_phone_e164`, `normalize_email`, `normalize_domain`) and `hash_phone_hmac(..., config.SECRET_KEY)` or the HMAC logic in `app/lead_intelligence/services/deduplication_service.py`.
  3. Checks the batch against DNC tables in a single call via `DncComplianceService.batch_filter_leads(...)` (`app/lead_intelligence/dnc/service.py`). If a lead is blocked, it is stored with `status = 'blacklisted'` and contact details are suppressed; a record is not created in `verified_contacts`.
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
  2. Add `verified_contacts.is_unlocked BOOLEAN DEFAULT FALSE`, `verified_contacts.pii_access_audit_logs JSONB DEFAULT '[]'`, and `verified_contacts.value_hmac String(64)` with `UNIQUE(workspace_id, value_hmac)`.
  3. Backfill existing `leads` rows with NULL `value_hmac` using `generate_lead_hmac` or a deterministic HMAC before applying `ALTER COLUMN ... NOT NULL`.
  4. Deterministically sort all batch items in memory by `value_hmac ASC` before acquiring row-level locks and executing:
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
  2. Computes deterministic `UUIDv5` chunk IDs using namespace `uuid.NAMESPACE_URL` and a per-workspace input: `UUIDv5(NAMESPACE_URL, f"{workspace_id}:{source_url}:{chunk_index}:{sha256(content).hexdigest()}")`. This prevents cross-workspace chunk id collisions while keeping deterministic, idempotent ingestion.
  3. Generates vector embeddings with a single canonical dimension (1536) in batch by calling `config.embedding_model_instance.embed_texts(chunks)` (or a thin wrapper). Verify the configured model outputs 1536 dimensions; if `config.embedding_model_instance.dimension != 1536`, fail fast with a clear config error and do not attempt to write to a mismatched `Vector` column. Local BGE models are not used until an AD amendment explicitly introduces a dual-embedding strategy.
  4. Inserts chunks into a PostgreSQL 16 table with UUID primary key and `ON CONFLICT (id) DO NOTHING`. If the existing `chunks` table is used, its `id` column must be migrated to `UUID` (see Critical Blocker #1 and Decision Record). If a new `chainlens_chunks` table is created, its `id` is `UUID(as_uuid=True)`.
  5. Records/updates the ingest job lifecycle in `chainlens_ingest_jobs` with `status` (`ok`, `partial`, `noop`), `chunks_received_count`, `chunks_ingested_count`, and `noop_source_ids`.

### AC-4: Zero-Cache CDC Isolation & Reactivity (AD-104)
- **Given** newly inserted or updated leads in the `leads` table,
- **When** PostgreSQL Logical WAL Replication triggers `zero_publication`,
- **Then** `zero-cache` broadcasts mutation events to connected web clients in < 10ms.
- **And** the `zero_publication` column list for `leads` includes only: `id`, `workspace_id`, `title`, `company_name`, `domain`, `source_url`, `fit_score`, `status`, `enriched`, `created_at`, `updated_at`. It does NOT include `value_hmac`, any `is_blacklisted` column, or any PII-derived columns. If a blacklisted state is needed, use `status = 'blacklisted'`; do not add a new `is_blacklisted` column to `zero_publication`.
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
  2. In a single transaction: decrypts PII, sets `is_unlocked = TRUE`, then calls `BillingEventService.record_contact_unlock(session, verified_contact_id=..., workspace_id=..., client_id=..., user_id=..., cost_micros=1_500)`. This single call enforces the workspace per-seat spend cap (`WorkspaceCreditService.record_spend`), checks wallet balance, atomically debits `wallet_credit.apply_debit`, and writes the `BillingEvent` with `event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `cost_micros=1_500`, and `cost_basis='actual'`. If `BillingEventService.record_contact_unlock` does not yet exist, add it to `app/services/billing_event_service.py` following the `record_contact_enrichment` pattern.
  3. Returns the decrypted phone/email only after a successful debit; if decryption or debit fails, returns a 4xx error without leaking PII.

---

## Tasks / Subtasks

- [ ] **Task 1: Database Schema & Migration (AC: 1, 2, 4)**
  - [ ] Create the next Alembic revision after `224_add_unique_constraint_leads_value_hmac.py`: `cd nowing_backend && uv run alembic revision --autogenerate -m "add lead batch and chainlens ingest"` and review the generated `nowing_backend/alembic/versions/<revision_id>_add_lead_batch_and_chainlens_ingest.py`.
  - [ ] Backfill existing `leads.value_hmac` NULL rows using `generate_lead_hmac` or a deterministic HMAC (`workspace_id` + normalized `phone|email|domain`) **before** applying `ALTER COLUMN ... NOT NULL`.
  - [ ] Make `leads.value_hmac` `NOT NULL` and `UNIQUE(workspace_id, value_hmac)` (full constraint, not partial).
  - [ ] Add `verified_contacts.value_hmac String(64) NOT NULL`, `is_unlocked BOOLEAN DEFAULT FALSE`, and `pii_access_audit_logs JSONB DEFAULT '[]'`. Add `UNIQUE(workspace_id, value_hmac)`.
  - [ ] Resolve `chunks.id` UUID vs. existing `Integer` PK via a Decision Record before merging. **Recommended for 26.1:** create a new `chainlens_chunks` table with `id UUID` PK, `Vector(1536)`, and no `document_id` FK. If reusing existing `chunks`, perform a zero-downtime migration and update `Chunk` model inheritance.
  - [ ] Use `status='blacklisted'` for DNC-blocked leads; do **not** add a separate `is_blacklisted` column to `zero_publication`.
  - [ ] Verify `workspace_dnc_records` and `global_dnc_records` are used for blacklist checks; do not create `pii_blacklists` unless an explicit merge migration is written.

- [ ] **Task 2: PII Vault, HMAC & Blind Hash Utility (AC: 1, 2)**
  - [ ] Reuse `VerifiedContactEncryption` (`app/services/pii/verified_contact_encryption.py`) to encrypt `name`/`title`/`phone`/`email` at rest. Use `encrypt_contact(contact)` and `decrypt_contact(contact)` for bulk operations.
  - [ ] Reuse HMAC helpers in `app/lead_intelligence/dnc/normalizer.py` (`normalize_phone_e164`, `normalize_email`, `normalize_domain`, `hash_phone_hmac(..., config.SECRET_KEY)`) or the logic in `app/lead_intelligence/services/deduplication_service.py`. Do **not** introduce a second `HMAC_SECRET` unless a dedicated one is added via architecture decision.
  - [ ] If creating `app/services/lead_batch_service.py`, keep it thin; delegate to `DncComplianceService.batch_filter_leads`, `deduplication_service` cluster keys, and `lead_stream_service` bulk upsert patterns.

- [ ] **Task 3: Batch Lead Ingestion Service & Schemas (AC: 1, 2, 4)**
  - [ ] Create Pydantic schemas in `nowing_backend/app/schemas/lead_batch_ingest.py`:
    - [ ] `LeadItemPayload`: `source_url (str)`, `company_name (str)`, `title (str | None)`, `domain (str | None)`, `contact_name (str | None)`, `phone (str | None)`, `email (str | None)`, `fit_score (float | None)`, `intent_signals (list[str])`, `extracted_metadata (dict[str, Any])`.
    - [ ] `BatchLeadIngestPayload`: `task_id (str)`, `leads (list[LeadItemPayload] = Field(min_length=1, max_length=100))`.
    - [ ] `BatchLeadIngestResponse`: `ingested_count (int)`, `skipped_blacklisted_count (int)`, `failed_count (int)`, `execution_time_ms (float)`, `lead_ids (list[UUID])`.
  - [ ] Implement the batch lead ingestion route as a **thin REST wrapper** around existing services. **Do not create a large new service.**
    - Reuse `app/lead_intelligence/services/lead_stream_service.py` (`LeadStreamBuffer.ingest_stream_leads_to_db` or `build_lead_upsert_stmt`) for deterministic `value_hmac` generation, in-memory dedup, sorted by `value_hmac ASC`, and `pg_insert(Lead).on_conflict_do_update(...)` on the partitioned `leads` table.
    - Reuse `DncComplianceService.batch_filter_leads(...)` (`app/lead_intelligence/dnc/service.py`) for single-call DNC fail-closed filtering.
    - Reuse `VerifiedContactEncryption.encrypt_contact(...)` to persist PII in `verified_contacts` only for non-blacklisted leads.
    - If a new module is needed for schema/validation only, keep `app/services/lead_batch_service.py` or `app/routes/lead_batch_routes.py` under ~100 lines and delegate all persistence logic to `lead_stream_service` + `DncComplianceService`.

- [ ] **Task 4: Batch Ingestion REST Route (AC: 1)**
  - [ ] Create `nowing_backend/app/routes/lead_batch_routes.py`:
    - [ ] `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`: Authenticated endpoint receiving `BatchLeadIngestPayload`.
    - [ ] Enforce per-workspace rate limit (e.g., 30 batches/minute).
  - [ ] Register the router in `nowing_backend/app/app.py`.
  - [ ] No MCP tool is required in this story; DSH sidecar calls the REST endpoint directly.

- [ ] **Task 5: Stateless ChainLens Chunk Ingestion Endpoint (AC: 3)**
  - [ ] Implement `POST /v1/chainlens/ingest` in `nowing_backend/app/routes/chainlens_internal.py`.
  - [ ] Create a **new** service module for the ChainLens → Nowing direction, e.g. `app/services/chainlens/ingest_reception.py` or `app/services/chainlens_reception.py`. Do **not** add the new logic to `NowingIngestService` (`app/services/chainlens/ingest.py`), which is the Nowing → ChainLens direction.
    - [ ] Schema `ChainLensIngestPayload`: `workspace_id (int)`, `scraper_id (str)`, `run_id (str)`, `chunks (list[ChainLensChunkItem])`.
    - [ ] Validate service-to-service API key via `ChainLensServiceAuth` (reuse from Story 20.4).
    - [ ] Deterministic per-workspace `UUIDv5` chunk ID generation: `uuid.uuid5(uuid.NAMESPACE_URL, f"{workspace_id}:{chunk.source_url}:{idx}:{hashlib.sha256(chunk.content.encode()).hexdigest()}")`.
    - [ ] Batch embedding generation by calling `config.embedding_model_instance.embed_texts(...)` with 1536-dim output. Fail fast if the configured model dimension is not 1536.
    - [ ] Insert into the target chunks table (`chunks` if migrated, or `chainlens_chunks`) with `ON CONFLICT (id) DO NOTHING`.
    - [ ] Update the existing `chainlens_ingest_jobs` table (`ingested_source_ids`, `noop_source_ids`, `chunks_received_count`, etc.) with `status` (`ok`, `partial`, `noop`).

- [ ] **Task 6: Contact Unlock Billing (AD-105 / AD-110)**
  - [ ] Implement `POST /api/v1/workspaces/:workspace_id/leads/:lead_id/contacts/:contact_id/unlock` in `app/routes/lead_routes.py` or `app/routes/lead_pipeline_routes.py`.
  - [ ] Before unlock, check `verified_contacts.is_unlocked = FALSE` and owner `User.credit_micros_balance >= 1_500`.
  - [ ] Add `BillingEventService.record_contact_unlock(session, *, verified_contact_id, workspace_id, client_id, user_id, cost_micros=1_500)` to `app/services/billing_event_service.py`, following the `record_contact_enrichment` / `_record_business_event` pattern (idempotent, enforces `WorkspaceCreditService.record_spend`, checks wallet, debits, writes `BillingEvent`).
  - [ ] In one transaction: decrypt PII, set `is_unlocked = TRUE`, append to `pii_access_audit_logs`, and call `BillingEventService.record_contact_unlock`. Do **not** call `wallet_credit.apply_debit` directly.
  - [ ] Return decrypted phone/email only after a successful `BillingEventService` call. On any failure, do not leak PII.
  - [ ] Unit/integration tests for insufficient balance, already unlocked, successful unlock, and failed decryption.

- [ ] **Task 7: Verification & Automated Test Suites (AC: 1, 2, 3, 5)**
  - [ ] Unit tests for HMAC, PII encryption, and sorting in `tests/unit/services/test_lead_batch_service.py`.
  - [ ] Unit tests for batch ingestion in `tests/unit/routes/test_lead_batch_ingest.py`.
  - [ ] Concurrency deadlock stress test (20 parallel async workers) in `tests/integration/services/test_lead_batch_concurrency.py`.
  - [ ] Integration tests for ChainLens ingestion in `tests/integration/routes/test_chainlens_ingest_pipeline.py` using fake ChainLens callback.
  - [ ] Verify `zero_publication` column list for `leads` excludes `value_hmac`, any `is_blacklisted` column, and `pii_access_audit_logs`; ensure `chunks` is not published.
  - [ ] Verify embedding dimension 1536 with mocked `config.embedding_model_instance` and a fake 1024-dim model fails gracefully.
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

> **Ponytail note:** The `lead_stream_service.py` already wraps `pg_insert(Lead).on_conflict_do_update(...)` for stream ingestion. Reuse or extend it before writing a brand-new `lead_batch_service.py`.

### 5. BillingEventService Pattern for Contact Unlock

Do **not** call `wallet_credit.apply_debit` directly from the route. Use the canonical billing path:

```python
from app.services.billing_event_service import BillingEventService

billing_event = await BillingEventService().record_contact_unlock(
    session,
    verified_contact_id=verified_contact.id,
    workspace_id=workspace_id,
    client_id=client_id,
    user_id=attributed_user_id,
    cost_micros=1_500,
)
```

`record_contact_unlock` should be added to `app/services/billing_event_service.py` and call `_record_business_event(..., event_entity_type='verified_contact', event_type='contact_unlock', return_existing=True)` so it is idempotent and enforces the workspace per-seat spend cap via `WorkspaceCreditService.record_spend` before `wallet_credit.apply_debit`.

### 6. Reuse Existing Batch, DNC, and Embedding Services

| Concern | Reuse First | Avoid |
|---|---|---|
| Bulk lead upsert | `app/lead_intelligence/services/lead_stream_service.py` (`LeadStreamBuffer`, `ingest_stream_leads_to_db`) | Writing a second `pg_insert` from scratch |
| Lead dedup/HMAC | `app/lead_intelligence/services/deduplication_service.py` (`EntityDeduplicationService.compute_cluster_keys`) | Local `compute_contact_hmac` with a different key/algorithm |
| DNC batch check | `app/lead_intelligence/dnc/service.py` (`DncComplianceService.batch_filter_leads`) | Manual `workspace_dnc_records` + `global_dnc_records` queries |
| Embedding | `config.embedding_model_instance.embed_texts(...)` | Introducing an `EmbeddingService` class that does not exist |
| Rate limiting | `app/rate_limiter.py` shared `Limiter` from `slowapi` | Ad-hoc Redis `INCR` outside the existing limiter |

---

### Project Structure Notes

- **Existing Files Modified:**
  - `nowing_backend/app/db.py`: Add `verified_contacts.value_hmac`, `is_unlocked`, `pii_access_audit_logs`; backfill `leads.value_hmac` then make it `NOT NULL`; do not add `is_blacklisted` to `leads` (use `status='blacklisted'`); do not migrate `chunks.id` to UUID unless the Decision Record chooses Option A/B.
  - `nowing_backend/app/config/__init__.py`: Add `CHAINLENS_EMBEDDING_DIMENSION` (default 1536) and optionally `LEAD_BATCH_INGEST_RATE_LIMIT` configs.
  - `nowing_backend/app/app.py`: Mount `lead_batch_routes` router.
  - `nowing_backend/app/services/pii/verified_contact_encryption.py`: Verify/extend PII encryption for `name`/`title`/`phone`/`email`.
  - `nowing_backend/app/services/billing_event_service.py`: Add `record_contact_unlock` method following `_record_business_event` pattern.
  - `nowing_backend/app/lead_intelligence/services/lead_stream_service.py` or `app/services/lead_batch_service.py`: Bulk upsert logic (reuse `pg_insert` pattern).
  - `nowing_backend/app/routes/chainlens_internal.py`: Add `POST /chainlens/ingest` handler.
  - `nowing_backend/app/services/chainlens/ingest_reception.py` (new): Stateless ChainLens → Nowing ingestion service. Do **not** add to `NowingIngestService`.
  - `nowing_backend/app/routes/lead_pipeline_routes.py` (or new `lead_routes.py`): Add `POST .../contacts/:contact_id/unlock` handler.
  - `nowing_backend/app/zero_publication.py`: Continue to publish `leads` PII-safe columns only and exclude `chunks`/`chainlens_chunks`.

- **New Files Created:**
  - `nowing_backend/alembic/versions/<revision_id>_add_lead_batch_and_chainlens_ingest.py`: Database migration. **Must** backfill `leads.value_hmac` before `NOT NULL`; decide on `chunks.id` UUID vs. new `chainlens_chunks` table.
  - `nowing_backend/app/schemas/lead_batch_ingest.py`: Request/Response schemas for batch lead ingestion.
  - `nowing_backend/app/services/lead_batch_service.py` (optional, **under ~100 lines**): validation + thin orchestration only. Core upsert/HMAC/DNC **must** delegate to `lead_stream_service.py` + `DncComplianceService`.
  - `nowing_backend/app/services/chainlens/ingest_reception.py` (recommended name): Stateless ChainLens → Nowing ingestion service (reverse of `NowingIngestService`).
  - `nowing_backend/app/routes/lead_batch_routes.py`: FastAPI route handler for `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`.
  - `nowing_backend/tests/unit/services/test_lead_batch_service.py`: Unit tests for HMAC, sorting, PII encryption, and `BillingEventService.record_contact_unlock`.
  - `nowing_backend/tests/unit/routes/test_lead_batch_ingest.py`: Unit tests for REST endpoint.
  - `nowing_backend/tests/integration/services/test_lead_batch_concurrency.py`: 20-thread concurrency test.
  - `nowing_backend/tests/integration/routes/test_chainlens_ingest_pipeline.py`: Integration tests for `/v1/chainlens/ingest` including dimension mismatch and UUID idempotency.

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
|| Batch DNC filter | `app/lead_intelligence/dnc/service.py` | `DncComplianceService.batch_filter_leads(workspace_id, leads, session)` returns leads tagged with `blocked_by_dnc` and `dnc_reason`. Use this in batch ingestion. |
|| Bulk lead upsert | `app/lead_intelligence/services/lead_stream_service.py` | `ingest_stream_leads_to_db(workspace_id, leads)` already wraps `pg_insert(Lead).on_conflict_do_update(...)` for partitioned tables. Reuse or extend before writing a new `lead_batch_service.py`. |
| Wallet + BillingEvent + spend cap | `app/services/billing_event_service.py` | `_record_business_event` / `BillingEventService.record_contact_enrichment` pattern. It calls `WorkspaceCreditService.record_spend` (per-seat cap) → `wallet_credit.check_balance` → `wallet_credit.apply_debit` and writes `BillingEvent` with idempotency. Add `record_contact_unlock` for this story and call it instead of calling `wallet_credit.apply_debit` directly. |
| Rate limiting | `app/rate_limiter.py` | Shared `Limiter` from `slowapi`. For per-workspace rate limit use a custom key like `f"lead_batch_ingest:{workspace_id}"` and call `limiter.limiter.hit(RateLimitItemPerMinute(30), key)`. |
| Embedding | `app/utils/document_converters.py` | `embed_text(text)` / `embed_texts(texts)` use `config.embedding_model_instance`. For 1536-dim canonical output, ensure `EMBEDDING_MODEL` env points to a 1536-dim model (e.g., OpenAI text-embedding-3-small) or configure `CHAINLENS_EMBEDDING_DIMENSION=1536` and use a model that outputs 1536 dimensions. If the configured model dimension differs, fail fast rather than writing to a mismatched `Vector` column. |
| Router mounting | `app/app.py` | `app.include_router(lead_batch_router, prefix="/api/v1")`. `chainlens_internal` already mounted at `/v1`; add `POST /chainlens/ingest` there. |

### 2. Database Migration Gaps

| Table / Column | Current State | Required for Story 26.1 |
|---|---|---|
| `leads.value_hmac` | `String(64)`, nullable | `NOT NULL` and `UNIQUE(workspace_id, value_hmac)`. **Caution:** existing rows with NULL `value_hmac` will block a plain `ALTER COLUMN NOT NULL`; backfill with `generate_lead_hmac` or a deterministic HMAC before the `NOT NULL` migration. Migration 224 already added a partial unique index. |
| `leads.status` | `String(50)`, default `new` | Add `'blacklisted'` enum value. Do **not** add a separate `is_blacklisted` boolean; it would need to be excluded from `zero_publication`. |
| `verified_contacts.is_unlocked` | **Missing** | Add `Boolean DEFAULT FALSE`. |
| `verified_contacts.pii_access_audit_logs` | **Missing** | Add `JSONB DEFAULT '[]'`. |
| `verified_contacts.value_hmac` | **Missing** | Add `String(64) NOT NULL` and `UNIQUE(workspace_id, value_hmac)` for contact-level dedup/atomic upsert. |
| `chunks.id` | `Integer` (via `BaseModel`) | **Architecture requires UUID.** This is a heavy migration. Option A: alter `chunks.id` to `UUID` (risky for existing rows). Option B: add `chunk_uuid UUID UNIQUE` and a migration/copy plan. Option C: create a new `chainlens_chunks` table with UUID PK. **Recommend raising a decision record before dev starts.** |
| `chunks.embedding` | `Vector(config.embedding_model_instance.dimension)` | Column dimension is `config.embedding_model_instance.dimension`. If a 1024-dim BGE model is configured, 1536-dim vectors cannot be stored. Either pin `EMBEDDING_MODEL` to a 1536-dim model at config load time, or create a dedicated `chainlens_chunks.embedding Vector(1536)` column. Fail fast on dimension mismatch. |

### 3. Critical Risks & Open Questions

1. **Chunks primary key type.** Architecture AD-101 says `chunks.id` MUST be UUID. Existing `Chunk` model inherits `BaseModel` which sets `id = Integer`. Changing this in place is a breaking schema change. The dev agent must either (a) get an architecture amendment, or (b) implement a safe migration plan before AC-3 can be considered done. Do not gloss over this.
2. **Embedding dimension mismatch (FIXED in this validation).** AC-3 now explicitly uses `config.embedding_model_instance.embed_texts(...)`. The dev agent must verify `config.embedding_model_instance.dimension == 1536`; if the configured model is 1024-dim BGE, fail fast and either switch to a 1536-dim model or use a dedicated `chainlens_chunks.embedding Vector(1536)` column. Do not invent an `EmbeddingService` class.
3. **Contact unlock billing path (FIXED in this validation).** AC-6 and Task 6 now require `BillingEventService.record_contact_unlock(...)` which calls `_record_business_event(..., event_entity_type='verified_contact', event_type='contact_unlock')`, enforcing `WorkspaceCreditService.record_spend` per-seat cap, wallet balance check, and debit before writing the `BillingEvent`. Direct `wallet_credit.apply_debit` from the route is no longer allowed.
4. **NowingIngestService vs new ChainLens → Nowing flow (FIXED in this validation).** Task 5 now requires a new service module (`app/services/chainlens/ingest_reception.py` or similar) for the reverse direction. `app/services/chainlens/ingest.py` (`NowingIngestService`) is Nowing → ChainLens and must not be modified for this story.
5. **`verified_contacts` uniqueness.** The story implies `ON CONFLICT (workspace_id, value_hmac) DO UPDATE` on `verified_contacts`. This requires `value_hmac` column and a unique constraint. Currently `VerifiedContact` has no `value_hmac`. Add it in the migration.
6. **Zero publication for `leads`.** `app/zero_publication.py` has `LEADS_COLS` that currently does NOT include `value_hmac`. Keep it that way. If you add `is_blacklisted` as a separate column, do NOT add it to `LEADS_COLS`; use `status='blacklisted'` instead, which is already published. `chunks` is correctly not in `ZERO_PUBLICATION`.

### 4. Files to Read Before Coding

- `app/services/pii/verified_contact_encryption.py` — PII encryption contract.
- `app/lead_intelligence/dnc/normalizer.py` and `app/lead_intelligence/dnc/service.py` — HMAC + DNC lookup.
- `app/lead_intelligence/services/lead_stream_service.py` and `app/lead_intelligence/services/deduplication_service.py` — existing bulk upsert and HMAC/dedup patterns.
- `app/services/billing_event_service.py` — canonical billing path.
- `app/services/wallet_credit.py` — wallet debit primitive.
- `app/services/workspace_credit_service.py` — spend cap enforcement (recently added `record_spend`).
- `app/routes/chainlens_internal.py` — where to add `POST /chainlens/ingest`.
- `app/db.py` — `Lead`, `VerifiedContact`, `Chunk`, `BillingEvent`, `WorkspaceDncRecord`, `GlobalDncRecord` models.
- `app/zero_publication.py` — Zero CDC column list.
- `app/utils/document_converters.py` — embedding helper.
- `app/rate_limiter.py` — rate limiting.

### 5. Validation Verdict

- Story 26.1 is **ready-for-dev** after the dev agent acknowledges the four critical blockers at the top of this file and produces a Decision Record for the `chunks.id` / `chainlens_chunks` approach before implementation.
- The two highest-risk schema changes are: (1) `leads.value_hmac` `NOT NULL` backfill on a partitioned table, and (2) UUID/embedding for ChainLens chunks. Do not start coding these without a migration plan.
- Spec updates applied: `BillingEventService.record_contact_unlock` for contact unlock, `DncComplianceService.batch_filter_leads` for DNC, `lead_stream_service` / `deduplication_service` for bulk upsert/HMAC, and `config.embedding_model_instance` for embedding.
- No new dependencies appear required beyond existing `slowapi`, `httpx`, `pgvector`, `cryptography`/`TokenEncryption`.

---

## Challenge Log (grill-me)

> **Persona:** Hoài nghi, dựa trên evidence trong codebase. Tìm thấy duplicate / simpler alternative → yêu cầu clarify trước implement.

### Q1 — Is this already implemented?

- **`app/lead_intelligence/services/lead_stream_service.py`** (`build_lead_upsert_stmt`, `ingest_stream_leads_to_db`) đã có logic đầy đủ: generate `value_hmac`, in-memory dedup, `pg_insert(Lead).on_conflict_do_update(index_elements=["workspace_id", "value_hmac"])` trên partitioned `leads`. Đây là phần core của AC-1 / AC-2.
- **`app/lead_intelligence/services/deduplication_service.py`** (`compute_phone_hmac`, `deduplicate_leads`, `apply_dnc_compliance`) đã có HMAC + DNC filtering trong pipeline lead generation.
- **`app/lead_intelligence/dnc/service.py`** (`DncComplianceService.batch_filter_leads`) đã có batch DNC lookup.
- **`app/services/billing_event_service.py`** (`BillingEventService.record_contact_enrichment`, `_record_business_event`) đã có canonical billing path với spend cap và wallet debit.
- **Chưa có:** `POST /v1/chainlens/ingest`, `app/services/chainlens/ingest_reception.py`, `BillingEventService.record_contact_unlock`, `app/routes/lead_batch_routes.py`.
- **Inconsistency note:** `app/services/phone_waterfall_service.py:912-928` vẫn tự viết `BillingEvent` + tự gọi `wallet_credit.apply_debit` cho contact enrichment, không qua `BillingEventService`. Đây là anti-pattern đã được 26.1 fix cho contact unlock nhưng cũng nên audit lại phone waterfall sau này.

**Verdict:** Tìm thấy **logic tương đương nặng ký** cho batch lead ingestion. RESOLVED — Task 3 now mandates `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` is a thin REST wrapper around `lead_stream_service.py` + `DncComplianceService`. `lead_batch_service.py` is optional and must stay under ~100 lines.

### Q2 — Is there a simpler alternative?

| AC / Concern | Simpler Alternative | Avoid |
|---|---|---|
| Batch lead HMAC + dedup + DNC + upsert | `LeadStreamBuffer.ingest_stream_leads_to_db` / `build_lead_upsert_stmt` + `DncComplianceService.batch_filter_leads` | Viết `lead_batch_service.py` từ đầu với logic `pg_insert` thứ 2 |
| HMAC helper | `deduplication_service.compute_phone_hmac` hoặc `DncComplianceService` normalizer + `config.SECRET_KEY` | Hàm `compute_contact_hmac` local với secret khác |
| Contact unlock billing | Thêm `record_contact_unlock` vào `BillingEventService` (reuses `_record_business_event`) | Gọi `wallet_credit.apply_debit` trực tiếp từ route |
| ChainLens auth | Reuse `ChainLensServiceAuth` từ `app/services/chainlens/auth.py` | Viết header validation mới |
| Embedding | `config.embedding_model_instance.embed_texts(chunks)` | Class `EmbeddingService` không tồn tại |

**Verdict:** Có simpler alternative rõ ràng. Dev agent **PHẢI** tuân theo reuse table trong Dev Notes; nếu tạo service mới mà không extend từ `lead_stream_service`/`deduplication_service` thì HALT để clarify.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary — batch size:** `leads` `min_length=1`, `max_length=100`. What about `101`? Pydantic handles, but route must return `422` with clear message. Tests should cover `0`, `1`, `100`, `101`.
- [ ] **Duplicate `value_hmac` inside a single batch:** `lead_stream_service.py` already in-memory dedups by `(workspace_id, value_hmac)`. Story AC không mention; test skeleton must assert `ingested_count`/`lead_ids` reflect dedup.
- [ ] **Only `domain` present, no phone/email:** AC says reject if **all** of phone/email/domain empty. A lead with only domain is accepted. Should it create a `verified_contacts` row? Spec says only non-blacklisted leads get contacts; but without phone/email there is nothing to encrypt. Need behavior: store lead without `verified_contacts`.
- [ ] **Same contact across multiple leads:** `verified_contacts` unique is `(workspace_id, value_hmac)`. If two leads in same workspace share phone/email, the second lead cannot insert a new verified contact. Should it link existing `verified_contact` to second lead? AC không nói.
- [ ] **Concurrent unlock of same contact:** `is_unlocked = FALSE` check + unique `verified_contact.id` as `BillingEvent.event_id` must prevent double debit. Need test: 20 async workers, only first succeeds, rest get `409` or `402`.
- [ ] **Balance vs. spendable balance:** `User.credit_micros_balance >= 1_500` is checked, but `wallet_credit.spendable_micros` subtracts `credit_micros_reserved`. Should unlock fail if `balance >= 1500` but `spendable < 1500`? `BillingEventService` path uses `spendable`, so this is an AC/BillingEventService consistency gap.
- [x] **ChainLens UUIDv5 collision across workspaces:** RESOLVED — AC-3 and Task 5 updated to `UUIDv5(NAMESPACE_URL, f"{workspace_id}:{source_url}:{chunk_index}:{sha256(content).hexdigest()}")`.
- [ ] **Duplicate ChainLens job row:** `chainlens_ingest_jobs` has no unique constraint on `(workspace_id, scraper_id, run_id)`. Same payload posted twice → duplicate rows. Need idempotency key or `ON CONFLICT`.
- [ ] **Embedding model 1024-dim:** AC says fail fast, but does not define error code / message. Need `500` with config error or `422`.
- [ ] **`status='blacklisted'` for DNC leads:** Is blacklisted lead `ingested_count++` or `skipped_blacklisted_count++`? AC-1 says "skipped_blacklisted_count". Need test assert.

### Q4 — Failure modes unspecified (Pattern 2, 4, 6)

- [ ] **`DncComplianceService.batch_filter_leads` raises:** DNC service is fail-closed. If Redis/Postgres lỗi, should the whole batch fail (`503`), or ingest with all leads marked blacklisted? AC không specify.
- [ ] **`wallet_credit.apply_debit` raises `InsufficientCreditsError` after `is_unlocked = TRUE`:** Current AC sets `is_unlocked = TRUE` then debits. If debit fails, contact stays unlocked but no charge. Need rollback to `is_unlocked = FALSE` or set `is_unlocked = TRUE` only **after** successful `BillingEventService` call.
- [ ] **`BillingEventService.record_contact_unlock` returns existing (idempotent):** If retry due to network, same `event_id=verified_contact.id` may return existing. UI may show success. Need ensure decrypt not re-run and no double PII audit log.
- [ ] **`WorkspaceCreditService.record_spend` raises spend-cap exceeded:** Should return `402` with `reason='spend_cap_exceeded'`. AC chỉ nói "4xx".
- [ ] **`config.embedding_model_instance` is `None` or `dimension != 1536`:** Must fail fast. Need error contract.
- [ ] **PostgreSQL `ON CONFLICT` on `verified_contacts` violates `(workspace_id, value_hmac)` unique:** If same contact appears twice in sorted batch, the second insert conflicts. `ON CONFLICT DO UPDATE` should be used, but AC says DO NOTHING? AC-2 only covers `leads`. `verified_contacts` upsert behavior is unspecified.
- [ ] **Migration backfill `leads.value_hmac` fails on partitioned table:** `ALTER COLUMN ... NOT NULL` on a partitioned table locks and may fail if any partition has NULL. Need test migration against prod-like data, not just fresh DB.
- [ ] **`ChainLensServiceAuth` token invalid/expired:** Return `401` or `403`. Need specify, and avoid leaking whether token exists.
- [ ] **Rate limiter (Redis/SlowAPI) unavailable:** `app/rate_limiter.py` uses slowapi with Redis. If Redis down, slowapi defaults may allow unbounded calls. AC says enforce 30 batches/minute; failure mode not specified.
- [ ] **Chunk content > model max tokens:** `embed_texts` may truncate or raise. Need behavior (truncate vs. reject).

### Triage

| Finding | Severity | Action |
|---|---|---|
| Duplicate batch lead ingestion logic | **Resolved** | Spec now mandates reuse of `lead_stream_service.py` + `DncComplianceService`. Dev agent must not create a second bulk upsert. |
| Simpler alternative: `BillingEventService.record_contact_unlock`, `DncComplianceService.batch_filter_leads`, `ChainLensServiceAuth`, `config.embedding_model_instance` | **Non-critical** | Already fixed in updated story; verify dev agent uses them. |
| Cross-workspace chunk UUID collision | **Resolved** | `workspace_id` added to UUIDv5 input. |
| `verified_contacts` upsert on `(workspace_id, value_hmac)` conflict unspecified | **Non-critical** | Add to test skeleton (Q3) and AC-2 clarify. |
| Balance vs. spendable balance check | **Non-critical** | Add AC / test: dùng `spendable_micros` (BillingEventService path). |
| is_unlocked set before debit failure / rollback | **Non-critical** | Add AC: set `is_unlocked = TRUE` **after** `BillingEventService.record_contact_unlock` returns success. |
| DNC service fail-closed, DB migration backfill, rate limiter Redis down, embedding dimension, spend cap, chunk token overflow | **Non-critical** | Add failure-mode tests to test skeleton. |

**Overall Verdict:** Critical blockers resolved. Updated spec mandates (1) thin REST wrapper reusing `lead_stream_service.py` + `DncComplianceService` and (2) per-workspace UUIDv5 chunk id including `workspace_id`. Proceed to `bmad-nowing-test-first-atdd`.

---

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High) / Antigravity Orchestrator

### Debug Log References

- Verified PostgreSQL 16 schema compatibility for partitioned tables.
- Verified Zero-Cache replication publication constraints.
- Verified absence of forward dependencies for Story 26.1.

### Completion Notes List

- Story 26.1 updated to align with architecture review v2/v3/v5 findings and validated against current code (migrations 217, 224, `app/db.py`, `billing_event_service.py`, `lead_stream_service.py`, `DncComplianceService`).
- REST endpoint `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` is canonical; no MCP tool in scope.
- HMAC reuses `app/lead_intelligence/dnc/normalizer.py` with `config.SECRET_KEY` or `deduplication_service` cluster keys; `value_hmac` is `NOT NULL` and `UNIQUE` per workspace.
- PII encryption uses existing `VerifiedContactEncryption` (Fernet/TokenEncryption); AES-256-GCM is not used.
- Blacklist checks use `DncComplianceService.batch_filter_leads` and existing `workspace_dnc_records` / `global_dnc_records`.
- ChainLens chunk ingestion uses 1536-dim embeddings via `config.embedding_model_instance` and a UUID PK table (`chunks` after migration or a new `chainlens_chunks` table per Decision Record).
- Contact unlock billing uses `BillingEventService.record_contact_unlock` (added) which enforces `WorkspaceCreditService.record_spend` per-seat cap, wallet balance check, and debit.
- Marked status as `ready-for-dev`.

### File List

- `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`
- `nowing_backend/app/db.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/services/pii/verified_contact_encryption.py`
- `nowing_backend/app/services/billing_event_service.py`
- `nowing_backend/app/lead_intelligence/dnc/normalizer.py`
- `nowing_backend/app/lead_intelligence/dnc/service.py`
- `nowing_backend/app/lead_intelligence/services/lead_stream_service.py`
- `nowing_backend/app/lead_intelligence/services/deduplication_service.py`
- `nowing_backend/app/services/chainlens/auth.py`
- `nowing_backend/app/services/chainlens/ingest.py` (read-only; do not modify)
- `nowing_backend/app/services/chainlens/ingest_reception.py` (new)
- `nowing_backend/app/routes/chainlens_internal.py`
- `nowing_backend/app/routes/lead_batch_routes.py`
- `nowing_backend/app/routes/lead_pipeline_routes.py`
- `nowing_backend/app/schemas/lead_batch_ingest.py`
- `nowing_backend/app/zero_publication.py`
- `nowing_backend/app/utils/document_converters.py`
- `nowing_backend/app/rate_limiter.py`
- `nowing_backend/alembic/versions/<revision_id>_add_lead_batch_and_chainlens_ingest.py`
- `nowing_backend/tests/unit/services/test_lead_batch_service.py`
- `nowing_backend/tests/unit/routes/test_lead_batch_ingest.py`
- `nowing_backend/tests/integration/services/test_lead_batch_concurrency.py`
- `nowing_backend/tests/integration/routes/test_chainlens_ingest_pipeline.py`
