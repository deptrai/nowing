# Story 26.1: Batch Lead Ingestion, Stateless ChainLens Ingestion Pipeline & PII Vault

Status: in-review

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
  4. Persists PII in `verified_contacts` using the existing `VerifiedContactEncryption` service (Fernet/TokenEncryption). [DEFERRED] A future AD amendment may migrate to AES-256-GCM.
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
- **When** executing bulk upsert operations on partitioned `leads` and `verified_contacts` tables,
- **Then** the database repository MUST deterministically sort all batch items in memory by `value_hmac ASC` before acquiring row-level locks and executing:
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
- **And** verified under a concurrency stress test with 20 parallel async threads inserting overlapping batches with 0 `DeadlockDetected` (`40P01`) exceptions.

### AC-3: Stateless ChainLens Chunk Ingestion Pipeline (`POST /v1/chainlens/ingest`) (AD-101)
- **Given** completed web crawl chunks received from the stateless ChainLens Research Engine,
- **When** ChainLens calls `POST /v1/chainlens/ingest` with `ChainLensIngestPayload`,
- **Then** the endpoint:
  1. Validates the incoming token via `ChainLensServiceAuth`.
  2. Computes deterministic `UUIDv5` chunk IDs using namespace `uuid.NAMESPACE_URL`: `UUIDv5(NAMESPACE_URL, f"{source_url}:{chunk_index}:{sha256(content)}")`.
  3. Generates vector embeddings (`dimension=1536` for OpenAI / `1024` for local BGE) in batch via `EmbeddingService`.
  4. Inserts chunks into the PostgreSQL 16 `chunks` table with `ON CONFLICT (id) DO NOTHING`.
  5. Records/updates the ingest job lifecycle in `chainlens_ingest_jobs` (`status="ok"`, `ingested_source_ids`, `noop_source_ids`).

### AC-4: Zero-Cache CDC Isolation & Reactivity (AD-104)
- **Given** newly inserted or updated leads in the `leads` table,
- **When** PostgreSQL Logical WAL Replication triggers `zero_publication`,
- **Then** `zero-cache` broadcasts mutation events to connected web clients in < 10ms.
- **And** the `chunks` table remains strictly excluded from `zero_publication` to prevent high-volume vector data from choking WAL replication bandwidth.

### AC-5: Hermetic Quality Testing & $0 API Cost Gate (AD-107)
- **Given** test execution in local development and CI/CD pipelines,
- **When** running pytest unit and integration test suites,
- **Then** all external embedding and LLM calls use hermetic in-memory fakes/mocks, passing 100% with $0 external token cost and clean `ruff` linting.

---

## Tasks / Subtasks

- [ ] **Task 1: Database Schema & Migration 224 (AC: 1, 2, 4)**
  - [ ] Create Alembic migration `nowing_backend/alembic/versions/224_add_pii_blacklists_and_batch_leads.py`.
  - [ ] Add `pii_blacklists` table with columns: `id (UUID PK)`, `value_hmac (VARCHAR(64) UNIQUE NOT NULL)`, `record_type (VARCHAR(20))`, `reason (VARCHAR(255))`, `source (VARCHAR(50))`, `is_active (BOOLEAN DEFAULT TRUE)`, `created_at`, `updated_at`.
  - [ ] Ensure unique index on `(workspace_id, value_hmac)` across partitioned `leads` table for atomic `ON CONFLICT` resolution.
  - [ ] Add `is_blacklisted (BOOLEAN DEFAULT FALSE)` column to `leads` if not already present.
  - [ ] Update `app/db.py` with SQLAlchemy ORM model `PIIBlacklist`.

- [ ] **Task 2: PII Vault Encryption & Blind HMAC Utility (AC: 1, 2)**
  - [ ] Implement `app/services/pii_vault_service.py`:
    - [ ] `compute_blind_hmac(raw_value: str, secret_key: str | None = None) -> str`: Normalizes string (strip, lowercase, E.164 phone normalize) and returns SHA-256 HMAC digest.
    - [ ] `encrypt_pii_field(plaintext: str, key_bytes: bytes | None = None) -> str`: Uses `cryptography.hazmat.primitives.ciphers.aead.AESGCM` with 12-byte random nonce and returns `base64(nonce + ciphertext + tag)`.
    - [ ] `decrypt_pii_field(ciphertext_b64: str, key_bytes: bytes | None = None) -> str`: Recovers plaintext securely.

- [ ] **Task 3: FastMCP Batch Lead Ingestion Service & Schemas (AC: 1, 2, 4)**
  - [ ] Create Pydantic schemas in `nowing_backend/app/schemas/fastmcp_ingest.py`:
    - [ ] `LeadItemPayload`: `source_url (str)`, `company_name (str)`, `title (str | None)`, `domain (str | None)`, `contact_name (str | None)`, `phone (str | None)`, `email (str | None)`, `fit_score (float | None)`, `intent_score (float | None)`, `composite_score (float | None)`, `industry (str | None)`, `location (str | None)`, `tech_stack (list[str])`, `metadata (dict[str, Any])`.
    - [ ] `BatchLeadIngestPayload`: `workspace_id (int)`, `task_id (str)`, `leads (list[LeadItemPayload] = Field(min_length=1, max_length=100))`.
    - [ ] `BatchLeadIngestResponse`: `ingested_count (int)`, `skipped_blacklisted_count (int)`, `execution_time_ms (float)`, `lead_ids (list[str])`.
  - [ ] Implement `nowing_backend/app/services/lead_batch_service.py`:
    - [ ] Deterministic in-memory sort by `value_hmac ASC`.
    - [ ] Check batch against `pii_blacklists`, `global_dnc_records`, and `workspace_dnc_records` in a single query.
    - [ ] Execute bulk upsert in PostgreSQL with `ON CONFLICT (workspace_id, value_hmac) DO UPDATE`.
    - [ ] Insert encrypted contacts into `verified_contacts`.

- [ ] **Task 4: FastMCP Tool API Route & Gateway Mounting (AC: 1)**
  - [ ] Create `nowing_backend/app/routes/fastmcp_routes.py`:
    - [ ] `POST /mcp/v1/tools/batch_ingest_leads`: Authenticated endpoint receiving `BatchLeadIngestPayload`.
    - [ ] `POST /mcp/v1/tools/ingest_lead`: Single item helper endpoint.
  - [ ] Register `fastmcp_router` in `nowing_backend/app/app.py` with prefix `/mcp/v1`.
  - [ ] Register `nowing_batch_ingest_leads` in `app/mcp_tools.py` catalog under group `McpToolGroup.LEAD_INTELLIGENCE`.

- [ ] **Task 5: Stateless ChainLens Chunk Ingestion Endpoint (AC: 3)**
  - [ ] Implement `POST /v1/chainlens/ingest` in `nowing_backend/app/routes/chainlens_internal.py`:
    - [ ] Schema `ChainLensIngestPayload`: `workspace_id (int)`, `scraper_id (str)`, `run_id (str)`, `chunks (list[ChainLensChunkItem])`.
    - [ ] Deterministic `UUIDv5` chunk ID generation: `uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.source_url}:{idx}:{hashlib.sha256(chunk.content.encode()).hexdigest()}")`.
    - [ ] Batch embedding generation with fallback/caching.
    - [ ] Insert into `chunks` table with `ON CONFLICT (id) DO NOTHING`.
    - [ ] Update `chainlens_ingest_jobs` record status and return `_ScraperRunResponse`.

- [ ] **Task 6: Verification & Automated Test Suites (AC: 1, 2, 3, 5)**
  - [ ] Unit tests for PII encryption, HMAC, and sorting in `tests/unit/mcp/test_pii_vault_service.py`.
  - [ ] Unit tests for FastMCP batch ingestion in `tests/unit/mcp/test_fastmcp_batch_ingest.py`.
  - [ ] Concurrency deadlock stress test (20 parallel async workers) in `tests/integration/mcp/test_concurrency_deadlock.py`.
  - [ ] Integration tests for ChainLens ingestion in `tests/integration/routes/test_chainlens_ingest_pipeline.py`.
  - [ ] Verify `zero_publication` tables via SQL assertion (ensure `leads` is present, `chunks` is absent).
  - [ ] Enforce 0 lint errors via `ruff check` and formatting via `ruff format`.

---

## Dev Notes

### 1. Architecture Compliance & Invariants
- **AD-101 (Stateless ChainLens Ingestion):** ChainLens is purely a stateless crawler. All chunk embeddings and persistent storage occur inside Nowing backend via `POST /v1/chainlens/ingest` with deterministic `UUIDv5` IDs.
- **AD-104 (Zero-Cache CDC Isolation):** `leads` table is published to `zero_publication` (`publish_via_partition_root = true`). `chunks` table is explicitly excluded to preserve WAL streaming performance.
- **AD-105 & AD-110 (PII Vault & Decree 13 Compliance):** Raw phone and email are never stored as plaintext in `verified_contacts`. AES-256-GCM ciphertext + IV is stored. Deduplication uses blind HMAC-SHA256 (`value_hmac`). Blacklisted hashes (`pii_blacklists`) suppress contact details and disable unlocking.
- **AD-107 (Hermetic $0 Testing):** Tests must mock embedding generation and use SQLite / test PostgreSQL without calling live OpenAI or external APIs.
- **AD-109 (Deterministic Sorting & Deadlock Prevention):** When multiple concurrent transactions execute bulk `INSERT ... ON CONFLICT`, PostgreSQL can deadlock if rows are inserted in different order. Sorting by `value_hmac ASC` enforces a universal lock acquisition sequence, eliminating deadlocks.

### 2. Encryption Implementation Pattern
```python
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_pii(plaintext: str, key_bytes: bytes) -> str:
    """Encrypts plaintext with AES-256-GCM.
    
    Output format: base64(12-byte nonce + ciphertext_with_tag)
    """
    if not plaintext:
        return ""
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")

def decrypt_pii(ciphertext_b64: str, key_bytes: bytes) -> str:
    """Decrypts base64 encoded AES-256-GCM ciphertext."""
    if not ciphertext_b64:
        return ""
    data = base64.b64decode(ciphertext_b64)
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key_bytes)
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
```

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

def compute_contact_hmac(workspace_id: int, phone: str | None, email: str | None, secret_key: str) -> str:
    norm_phone = normalize_phone(phone)
    norm_email = (email or "").strip().lower()
    raw = f"{workspace_id}:{norm_phone}:{norm_email}"
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
  - `nowing_backend/app/db.py`: Add `PIIBlacklist` model and relationship definitions.
  - `nowing_backend/app/app.py`: Mount `fastmcp_router` under `/mcp/v1`.
  - `nowing_backend/app/mcp_tools.py`: Register `nowing_batch_ingest_leads` tool definition.
  - `nowing_backend/app/routes/chainlens_internal.py`: Add `POST /v1/chainlens/ingest` handler.

- **New Files Created:**
  - `nowing_backend/alembic/versions/224_add_pii_blacklists_and_batch_leads.py`: Database migration.
  - `nowing_backend/app/schemas/fastmcp_ingest.py`: Request/Response schemas for FastMCP ingestion.
  - `nowing_backend/app/services/pii_vault_service.py`: Cryptographic helpers (AES-256-GCM, Blind HMAC).
  - `nowing_backend/app/services/lead_batch_service.py`: Deadlock-free batch ingestion logic.
  - `nowing_backend/app/routes/fastmcp_routes.py`: FastAPI route handler for `/mcp/v1/tools/*`.
  - `nowing_backend/tests/unit/mcp/test_pii_vault_service.py`: Unit tests for encryption & HMAC.
  - `nowing_backend/tests/unit/mcp/test_fastmcp_batch_ingest.py`: Unit tests for FastMCP endpoint.
  - `nowing_backend/tests/integration/mcp/test_concurrency_deadlock.py`: 20-thread concurrency test.
  - `nowing_backend/tests/integration/routes/test_chainlens_ingest_pipeline.py`: Integration tests for `/v1/chainlens/ingest`.

---

### References

- Architecture Contract: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (Sections 2, 3, 4)
- Implementation Readiness Report: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md`
- Epics & Stories Specification: `_bmad-output/planning-artifacts/epics.md` (Story 26.1, Lines 3308–3320)
- Existing Partitioned Leads Table: `nowing_backend/alembic/versions/217_partition_leads_table_zero_downtime.py`
- Existing ChainLens Internal Routes: `nowing_backend/app/routes/chainlens_internal.py`
- Zero-Cache Publication Configuration: `nowing_backend/app/zero_publication.py`

---

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High) / Antigravity Orchestrator

### Debug Log References

- Verified PostgreSQL 16 schema compatibility for partitioned tables.
- Verified Zero-Cache replication publication constraints.
- Verified absence of forward dependencies for Story 26.1.

### Completion Notes List

- Story 26.1 initialized and validated against all 10 architectural invariants (AD-101 to AD-110).
- Detailed deterministic sorting and concurrency deadlock prevention patterns embedded.
- AES-256-GCM authenticated cipher and blind HMAC algorithms fully specified.
- Marked status as `ready-for-dev`.

### File List

- `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`
