# Reality-Check Review — Epic 21 Lead Intelligence

**Review date:** 2026-08-11  
**Scope:** Nowing architecture spine, Epic 21 engineering hand-off, UX contract, `epics.md`, and the four backend files cited after the latest AD-43/AD-46/AD-47/AD-49 fixes.  
**Method:** Read `ARCHITECTURE-SPINE.md`, `epic21-engineering-handoff-2026-08-11.md`, `ux-contract-lead-intelligence-panel.md`, `epics.md`, `nowing_backend/app/db.py`, `nowing_backend/app/capabilities/core/types.py`, `nowing_backend/app/capabilities/core/store.py`, `nowing_backend/app/services/pii/redact.py`, plus all package manifests, `docker-compose.*.yml` and lock files.

---

## Verdict

**CONDITIONAL PASS**

**Rationale:** The 2026-08-11 fixes have landed the `Capability.metadata` / `CapabilityRegistry.query_metadata` machinery, the `Memory.source_uuid`/`source_entity_type` columns, the `MemorySourceType` extension for Epic 21 entities, and the `redact_pii(..., context="lead_enrichment")` contract. AD-43, AD-46, AD-47 and AD-49 are now mutually consistent, unambiguous, and literally contractable: there is a single `client_id` natural-key identity, a single capability-metadata store, a single authoritative Memory provenance pointer, and a clean split between the `VerifiedContact` vault and the redaction surfaces.

However the fixes are **model-level, not schema-level** in places, and the existing `client_id` columns are still `Text`. Epic 21 is implementable once the residual open conditions below are closed, but is not ready to be sliced into working migrations/routes today.

---

## 1. Stack pins vs package files and docker-compose

| Spine Stack row | Declared pin | Source file | Actual resolved / image | Match |
|---|---|---|---|---|
| Python | 3.12 | `nowing_backend/pyproject.toml:5` `requires-python = ">=3.12"` | `target-version = "py312"` in `ruff` config; uv env resolves 3.12 | ✅ |
| FastAPI | `>=0.115.8` | `nowing_backend/pyproject.toml:16` | `uv.lock` `0.135.2` (`nowing_backend/uv.lock:4306`) | ✅ |
| SQLAlchemy | 2.x async (requires `psycopg[binary,pool]>=3.3.2`) | `nowing_backend/pyproject.toml` | SQLAlchemy is **not directly pinned** in `pyproject.toml` (transitive through `alembic`, `fastapi-users`, `langchain`); `uv.lock` `2.0.48` (`nowing_backend/uv.lock:10742`) | ⚠️ policy pin missing; lock satisfies 2.x |
| Alembic | `>=1.13.0` | `nowing_backend/pyproject.toml:7` | `uv.lock` `1.18.4` (`nowing_backend/uv.lock:2211`) | ✅ |
| PostgreSQL | 17+ with pgvector | `docker/docker-compose.deps-only.yml:40` `pgvector/pgvector:pg17` | `pgvector/pgvector:pg17` in all compose files (`docker-compose.yml:14`, `docker-compose.dev.yml:20`, `docker-compose.e2e.yml:64`, `docker-compose.watch-e2e.yml:20`, `docker-compose.deps-only.yml:40`) | ✅ |
| Redis | 8+ (cache + broker) | `docker/docker-compose.deps-only.yml:70` `redis:8-alpine` | `redis:8-alpine` in all compose files (`docker-compose.yml:50`, `docker-compose.dev.yml:67`, `docker-compose.e2e.yml:85`, `docker-compose.watch-e2e.yml:36`, `docker-compose.deps-only.yml:70`) | ✅ |
| Celery | `>=5.5.3` | `nowing_backend/pyproject.toml:41` `celery[redis]>=5.5.3` | `uv.lock` `5.6.3` (`nowing_backend/uv.lock:2797`) | ✅ |
| LiteLLM | `>=1.83.7` | `nowing_backend/pyproject.toml:72` | `uv.lock` `1.88.1` (`nowing_backend/uv.lock:5957`) | ✅ |
| LangChain / LangGraph | `langchain>=1.2.13`, `langgraph>=1.1.3` | `nowing_backend/pyproject.toml:67-68` | `uv.lock` `1.2.13` / `1.1.3` (`nowing_backend/uv.lock:5677`, `5843`) | ✅ |
| OpenTelemetry | API/SDK/Exporter `>=1.40.0`, semantic-conventions `>=0.61b0` | `nowing_backend/pyproject.toml:75-84` | `uv.lock` `1.40.0` / `0.61b0` (`nowing_backend/uv.lock:7887`, `7900`, `8139`, `8152`) | ✅ |
| Node.js | 20+ (web/desktop); `>=18.0.0 <23.0.0` (browser ext) | `nowing_web/package.json`, `nowing_browser_extension/package.json` | `nowing_web/package.json` has no `engines.node`; `nowing_desktop/package.json` has no `engines` block at all; `nowing_browser_extension/package.json:8` is `>=18.0.0 <23.0.0` | ⚠️ web/desktop engine claim not in source; extension OK |
| Next.js | `^16.1.0` | `nowing_web/package.json:126` | `pnpm-lock.yaml` `16.1.6` (`nowing_web/pnpm-lock.yaml:284-286`) | ✅ |
| React | `^19.2.3` (web), `18.2.0` (browser ext) | `nowing_web/package.json:137`, `nowing_browser_extension/package.json:39` | `pnpm-lock.yaml` `19.2.4` (`nowing_web/pnpm-lock.yaml:317-319`); browser ext lock `18.2.0` (`nowing_browser_extension/pnpm-lock.yaml:4118`) | ✅ |
| Tailwind CSS | `^4.1.11` | `nowing_web/package.json:184` | `pnpm-lock.yaml` `4.2.1` (`nowing_web/pnpm-lock.yaml:453-455`) | ✅ |
| Jotai | `^2.15.1` | `nowing_web/package.json:116` | `pnpm-lock.yaml` `2.18.0` (`nowing_web/pnpm-lock.yaml:254-256`) | ✅ |
| Zustand | `^5.0.9` | `nowing_web/package.json:163` | `pnpm-lock.yaml` `5.0.11` (`nowing_web/pnpm-lock.yaml:395-397`) | ✅ |
| Tanstack Query | `^5.90.7` | `nowing_web/package.json:94` | `pnpm-lock.yaml` `5.90.21` (`nowing_web/pnpm-lock.yaml:188-190`) | ✅ |
| Plate.js | `^52.0.17` | `nowing_web/package.json:131` | `pnpm-lock.yaml` `52.0.17` (e.g. `nowing_web/pnpm-lock.yaml:43`, `73`) | ✅ |
| Electron | `^42.4.0` | `nowing_desktop/package.json:31` | `pnpm-lock.yaml` `42.4.0` (`nowing_desktop/pnpm-lock.yaml:715`) | ✅ |
| Plasmo | `0.90.5` | `nowing_browser_extension/package.json:36` | `pnpm-lock.yaml` `0.90.5` (`nowing_browser_extension/pnpm-lock.yaml:3919`) | ✅ |
| Obsidian API | `latest` (intentional) | `nowing_obsidian/package.json:32` `obsidian: "latest"` | `nowing_obsidian/package.json:32` | ✅ |
| MCP SDK Python | `>=1.25.0,<2` (backend), `>=1.26.0,<2` (mcp) | `nowing_backend/pyproject.toml:51`, `nowing_mcp/pyproject.toml:9` | `uv.lock` `1.26.0` (`nowing_backend/uv.lock:6417`); `nowing_mcp/uv.lock:291` `1.28.1` | ✅ |

### Stack finding summary
- **Image pins (Postgres, Redis, Zero) are consistent across every docker-compose file.**
- **Python/Node resolved versions satisfy all declared ranges.**
- **Minor drifts:**
  - `SQLAlchemy` is cited as pinned from `pyproject.toml` but is not explicitly declared there; it is only present transitively and in `uv.lock`.
  - `Node.js 20+` for web/desktop is not backed by an `engines.node` field in `nowing_web/package.json` or `nowing_desktop/package.json` (only the browser extension has one). This does not break builds but makes the Stack source citation inaccurate.

---

## 2. AD-43 / AD-46 / AD-47 / AD-49 — contractability

These four ADs are now **literally contractable** and do not contradict one another.

### 2.1 AD-43 — `AlertRule` first-class table
(`ARCHITECTURE-SPINE.md:1228-1252`)

- `AlertRule` is its own table: `id`, `capability_id`, `query` (JSONB), `schedule`, `diff_strategy`, `threshold`, `notification_channels` (genuine channels only), `target_sequence_id` (FK to `Sequence.id`), `target_step_id`, `enabled`.
- `sequence_enrollment` is an `EnrollmentRequested` action, **not** a notification channel.
- The signal-to-sequence path creates a `SequenceRun`, not an `AutomationRun`.
- **No JSONB template inside `Automation.definition`, no dual ownership.**

### 2.2 AD-46 — `AlertRule` target and `Sequence` client scope
(`ARCHITECTURE-SPINE.md:1288-1302`)

- `AlertRule.client_id` must equal `Sequence.client_id` (or both `NULL`) before `SequencerService` is called.
- `Sequence` is client-scoped by default; workspace-global only when `shared = true` and `client_id IS NULL`.
- `SequenceRun`/`SequenceEnrollment` inherit `client_id` from the matched `Lead` for shared sequences.
- **No cross-client targeting ambiguity, no accidental workspace-global ownership.**

### 2.3 AD-47 — `Capability` metadata and `Memory` UUID provenance
(`ARCHITECTURE-SPINE.md:1305-1323`)

- `Capability.name` is the canonical identifier; `Capability.metadata` is a single optional `dict[str, Any]`.
- `CapabilityRegistry.query_metadata(key)` and `query_metadata_for(name, key)` are the **only** canonical metadata readers.
- `LeadSource` remains a workspace-scoped derived cache, separate from the in-process registry.
- `Memory.source_id` stays `Integer` for `document`/`chat_message`; `source_run_id` is only for `Run`; `source_uuid` + `source_entity_type` are the authoritative pointer for Epic 21 UUID entities.
- `MemorySourceType` is extended with `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`.
- **No two metadata stores, no UUID coerced into `source_id`, no ambiguous provenance.**

### 2.4 AD-49 — `VerifiedContact` redaction boundary
(`ARCHITECTURE-SPINE.md:1342-1355`)

- `VerifiedContact` stores raw email/phone encrypted at rest and is the authoritative outreach source; it is **never** passed through `redact_pii`.
- `redact_pii(..., context="lead_enrichment")` is applied to `Memory.content`, `Chunk[]`, audit logs, and non-privileged UI surfaces.
- `VerifiedContact.consent_status`/`legal_basis` gate first outreach; `Lead.consent_status`/`legal_basis` are UI summaries.
- **No split redaction/consent authority, no raw PII leaking into Memory or logs.**

---

## 3. Code changes consistent with the ADs

### 3.1 `Capability.metadata` and `CapabilityRegistry`

- `Capability` gains `metadata: dict[str, Any] | None = None` at `nowing_backend/app/capabilities/core/types.py:90`.
- `CapabilityRegistry.query_metadata(key)` and `query_metadata_for(name, key)` are implemented in `nowing_backend/app/capabilities/core/store.py:29-43`.
- The registry uses a single `_REGISTRY: dict[str, Capability]`; there is **no** parallel `_METADATA` dict.
- Unit tests in `nowing_backend/tests/unit/capabilities/test_registry.py:30-44` verify the new API.

This matches AD-47 and AD-44.

### 3.2 `Memory.source_uuid`, `source_entity_type`, `MemorySourceType`

- `Memory` has `source_uuid` and `source_entity_type` columns at `nowing_backend/app/db.py:2336-2337`, with index on `source_uuid`.
- The column-level comments explicitly state these are the authoritative provenance for Epic 21 UUID entities and that `source_id` remains `Integer`.
- `MemorySourceType` is extended with `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT` at `nowing_backend/app/db.py:588-593`.

This matches the model intent of AD-47/AD-44.

### 3.3 `redact_pii` contexts

- `redact_pii(text, context="default")` in `nowing_backend/app/services/pii/redact.py:70-88` supports `job_data`, `lead_enrichment`, and `default`.
- The docstring explicitly says `VerifiedContact` raw values are never passed through this function (`redact.py:74-76`).
- Tests in `nowing_backend/tests/unit/services/pii/test_redact.py:43-58` exercise `context="lead_enrichment"`.

This matches AD-49 and the tightened AD-25.

### 3.4 `client_id` CITEXT natural-key identity

- `VerticalClient.client_id` is `CITEXT`, `unique=True` (`nowing_backend/app/db.py:2185`).
- `AgentConfig.client_id` is `CITEXT` with a `ForeignKey` to `vertical_clients.client_id` (`nowing_backend/app/db.py:2208-2211`).

This establishes the single natural-key identity required by AD-45/AD-31.

---

## 4. Residual open conditions

The conditions below are **why the verdict is conditional, not a full PASS**.

### 4.1 DB schema drift on `Memory` provenance (AD-47)

- `Memory.source_uuid` and `Memory.source_entity_type` exist in `app/db.py:2336-2337` but **no Alembic migration adds them**.
- `MemorySourceType` is extended in `app/db.py:580-593`, but the Postgres enum was created with only `('document', 'chat_message', 'scraper_run', 'manual', 'unknown')` in `alembic/versions/177_add_research_memory_tables.py:41-42` and has not been altered since.
- `alembic/versions/186_add_memory_provenance_recipe.py` added `source_capability` and `source_input` but not `source_uuid`/`source_entity_type`.
- **Impact:** `alembic upgrade head` will not create these columns or enum values; a fresh DB will diverge from the model.

### 4.2 `MemoryRepository` does not yet wire `source_uuid` / `source_entity_type`

- `create_memory` (`nowing_backend/app/services/memory/repository.py:244-265`) and `update_memory` (`nowing_backend/app/services/memory/repository.py:410-431`) accept `source_id`, `source_run_id`, `source_capability`, and `source_input`, but have **no parameters or assignment for `source_uuid` / `source_entity_type`**.
- Callers such as `MemoryExtractionService` (`extraction.py:230-245`) and `RunMemoryExtractionService` (`run_extraction.py:392-407`) also do not set them.
- **Impact:** even if the columns existed in the DB, the repository would leave them `NULL`.

### 4.3 Existing `client_id` columns are still `Text` (AD-45)

The hand-off and AD-45 require existing `client_id: Text` columns to be migrated to `CITEXT` with a `CheckConstraint` or `ForeignKey` to `vertical_clients.client_id` before Epic 21 tables are enabled. They are not:

- `Memory.client_id` — `nowing_backend/app/db.py:2298`
- `Run.client_id` — `nowing_backend/app/db.py:3518`
- `TokenUsage.client_id` — `nowing_backend/app/db.py:1262`
- `ResearchThread.client_id` — `nowing_backend/app/db.py:2143`
- `PersonalAccessToken.client_id` — `nowing_backend/app/db.py:3433`
- `NewChatThread.client_id` — `nowing_backend/app/db.py:728`

No such migration exists in `nowing_backend/alembic/versions`.

### 4.4 Epic 21 tables and lead pipeline are not yet in the code

`nowing_backend/app/db.py` and the broader backend contain **no** `Lead`, `LeadSource`, `VerifiedContact`, `SignalEvent`, `SignalSubscription`, `LeadScore`, `Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun`, `CrmConnection`, `CrmSyncLog`, `BillingEvent`, `OutcomeEvent`, `AlertRule`, or `EnrichmentRequest` tables.

There is no `lead_extractor` capability, no `VerifiedContact` encryption-at-rest implementation, and no `BillingEvent`/`OutcomeEvent` ledger. These are the implementation work products of Epic 21, not architecture defects, but they must be built.

### 4.5 `redact_pii` is not wired into the ingestion/extraction paths

- `app/services/memory/extraction.py` and `app/services/memory/run_extraction.py` contain **no** `redact_pii` calls.
- The job-aggregator / scraper pipelines (`app/proprietary/platforms/`, `app/services/jobs_aggregator/`) also do not call `redact_pii` or `redact_job_pii` before persisting `Memory.content`.
- This is a pre-existing AD-25 wiring gap; the new `lead_enrichment` context is ready but not yet invoked.

### 4.6 Stack citation and SQLAlchemy pin

As noted in §1:
- `SQLAlchemy` is not explicitly pinned in `nowing_backend/pyproject.toml`.
- `Node.js 20+` for `nowing_web` and `nowing_desktop` is not declared in those `package.json` files.

### 4.7 Business / legal gates (from hand-off §5)

- Email outreach legal/ToS sign-off.
- Contact-enrichment vendor contract / POC.
- PII/consent pipeline sign-off.
- CRM sync scope confirmed.
- Outcome-pricing display tested with real `BillingEvent` data.
- TopCV anti-bot POC pass (Epic 12 dependency).

---

## 5. Epic 21 implementability

**The spine + hand-off are now coherent enough to implement**, provided the residual conditions above are closed in the right order:

1. **Pre-schema:** migrate existing `client_id: Text` columns to `CITEXT` + FK/CheckConstraint (AD-45). Without this, Epic 21 tables cannot safely share the client-tenancy column.
2. **Memory provenance:** add Alembic migrations for `Memory.source_uuid`, `Memory.source_entity_type`, and the new `MemorySourceType` enum values; wire them through `MemoryRepository.create_memory/update_memory` (AD-47).
3. **Build Epic 21 bounded contexts:** lead extractor, `Lead`/`LeadSource`, signal/scoring, `VerifiedContact` (with encryption at rest), `Sequence`/`AlertRule`/`BillingEvent`/`OutcomeEvent`, and the `EnrollmentRequested` action path.
4. **Wire PII redaction:** call `redact_pii(..., context="lead_enrichment")` at the `Memory`/`Chunk[]`/log/UI boundaries, never on `VerifiedContact`.
5. **Close business/legal gates** before public beta.

Because the latest fixes removed the key architecture ambiguities (`Capability.metadata`, `Memory.source_uuid`, `redact_pii` boundary), the remaining work is implementation and schema migration rather than redesign. The architecture is therefore **CONDITIONAL PASS**.

---

## 6. Review artifact actions

- **No code was changed** in this review.
- **One file was overwritten:** `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/reviews/review-reality-check.md` (this file).
