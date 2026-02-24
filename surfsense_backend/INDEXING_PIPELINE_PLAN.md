# Indexing Pipeline Refactor — Plan

## Context

The current system has 20+ connector indexers each implementing the same pipeline
independently. This causes:

- `safe_set_chunks`, `get_current_timestamp`, `check_document_by_unique_identifier`
  defined twice across `connector_indexers/base.py` and `document_processors/base.py`
- `config.embedding_model_instance.embed()` called in 20+ places directly
- `document.content` stores different things per connector (summary vs raw text)
- `source_markdown` column always NULL — never written by any connector
- GitHub uses custom character chunking, bypassing the shared chunker
- Obsidian calls LLM then discards the result, embeds raw text instead
- `LinearKBSyncService` and `NotionKBSyncService` both say they
  "mirror Phase 2 logic exactly" — a third copy of the same pipeline
- No tests anywhere

---

## What We Are Building

### 1. `ConnectorDocument`

The canonical data model. Every adapter produces one. The pipeline consumes one.
Nothing else crosses this boundary.

**File:** `app/pipeline/connector_document.py`

```
title: str
source_markdown: str          # raw content, always set, validated not empty
unique_id: str                # source-native key: page_id, issue_id, ts...
document_type: DocumentType
should_summarize: bool = True # drives SUMMARIZE step
content_type: "text" | "code" # drives CHUNK step (chunker vs code_chunker)
metadata: dict = {}
connector_id: int | None = None
search_space_id: int = 0
created_by_id: str = ""
```

### 2. `IndexingPipelineService`

The single pipeline. All connectors use it. Nothing changes inside it
when a new connector is added.

**File:** `app/services/indexing_pipeline_service.py`

**Public interface:**
```
prepare_for_indexing(connector_documents) → list[(Document, ConnectorDocument)]
index(document, connector_doc, llm)       → None
```

**Public interface:**
```
prepare_for_indexing(connector_documents) → list[(Document, ConnectorDocument)]
index(document, connector_doc, llm)       → None
```

**Private steps (one responsibility each):**
```
_compute_unique_identifier_hash(connector_doc)  → str
_compute_content_hash(connector_doc)            → str
_find_existing_by_identifier(hash)              → Document | None   # always selectinload chunks
_find_existing_by_content(hash)                 → Document | None
_create(connector_doc, hash)                    → Document          # creates new DB row
_mark_processing(document)                      → None              # status transition
_mark_ready(document, connector_doc, ...)       → None              # status transition + full data
_mark_failed(document, error)                   → None              # status transition + error
_summarize(connector_doc, llm)                  → str
_chunk(connector_doc)                           → list[str]
_embed_document(summary_content)                → list[float]
_embed_chunks(segments)                         → list[list[float]]
```

**What `prepare_for_indexing` orchestrates:**
```
for each ConnectorDocument:
    _compute_unique_identifier_hash
    _compute_content_hash
    _find_existing_by_identifier
        → not found: check content duplicate
            → duplicate: skip
            → new: _create
        → found, content_hash same, title same: skip (unchanged)
        → found, content_hash same, title different: update title inline
        → found, content_hash different: queue for full reprocess
session.commit() once
```

**What `index` orchestrates:**
```
try:
    _mark_processing(document), commit
    _summarize
    _chunk
    _embed_document
    _embed_chunks
    _mark_ready(document, connector_doc, ...)
except Exception as e:
    rollback()
    session.refresh(document)   ← required: rollback expires all attributes
    _mark_failed(document, e)
    commit()
```

### 3. Adapters

One per connector. Pure static converter. No IO, no DB, no hashing.

**File:** `app/pipeline/adapters/{connector_name}_adapter.py`

```python
class ClickUpAdapter:
    @staticmethod
    def to_connector_document(task: dict, connector_id, search_space_id, user_id) -> ConnectorDocument:
        ...
```

---

## What Moves Into The Service

| Currently in | Moves to |
|---|---|
| `connector_indexers/base.py` | `IndexingPipelineService` |
| `document_processors/base.py` | `IndexingPipelineService` (duplicates removed) |
| `document_converters.py` | `IndexingPipelineService` |
| `config.embedding_model_instance.embed()` (20 places) | `_embed_document`, `_embed_chunks` only |
| `config.chunker_instance.chunk()` (all connectors) | `_chunk` only |
| `config.code_chunker_instance.chunk()` (unused/GitHub) | `_chunk` only |

**Stays outside (adapter concern):**
- `build_document_metadata_string()`
- `build_document_metadata_markdown()`
- `convert_element_to_markdown()`
- `convert_document_to_markdown()`

---

## Implementation Order

### Step 1 — Create `ConnectorDocument`
New file. Nothing references it yet. Zero risk.

### Step 2 — Create `IndexingPipelineService`
New file. Nothing calls it yet. Zero risk.

### Step 3 — Write tests (see test plan below)
Tests call the new service directly. No connector changed yet.

### Step 4 — Migrate one connector (ClickUp — simplest)
- Write `ClickUpAdapter`
- Update `clickup_indexer.py` to use the service
- Keep old code until verified working in testing

### Step 5 — Migrate remaining connectors one by one
Each connector migrated = old Phase 2 code deleted from that indexer.

### Step 6 — Update `LinearKBSyncService` and `NotionKBSyncService`
Replace their Phase 2 reimplementation with a call to `service.index()`.

### Step 7 — Update `composio_indexer.py`
Standalone indexer for Composio connectors (`composio_google_drive_connector.py`,
`composio_google_calendar_connector.py`, `composio_gmail_connector.py`).
Same migration pattern as standard connectors.

### Step 8 — Delete duplicate base functions
Only after all connectors are migrated.
`connector_indexers/base.py` and `document_processors/base.py` — remove duplicates,
keep only connector helpers (`get_connector_by_id`, `calculate_date_range`, etc.)

---

## Session Management Rules

These rules apply to the pipeline implementation. They replace the inconsistent patterns
found across the 20+ existing connectors.

### No `session.no_autoflush`
All connectors used `with session.no_autoflush` before `_find_existing_by_content`.
This is cargo-cult. `session.add(document)` happens AFTER the content_hash check,
so no staged documents exist in the session at check time. Autoflush is harmless.
For same-content same-batch items, autoflush correctly finds the first staged document
and deduplicates. Without `no_autoflush`, same-batch dedup works better, not worse.

### Error handling in `index()`
After a rollback, SQLAlchemy expires all object attributes. Accessing any attribute
on `document` after rollback raises `MissingGreenlet` in async mode.
The correct pattern:
```python
except Exception as e:
    await self.session.rollback()
    await self.session.refresh(document)   # reload from DB before touching attributes
    await self._write_failed(document, str(e))
    await self.session.commit()
```

### `safe_set_chunks` requires `selectinload`
`safe_set_chunks` uses `set_committed_value` which marks old chunks as orphans for
cascade deletion. This only works if the old chunks were loaded into the session first.
`_find_existing_by_identifier` MUST always use `selectinload(Document.chunks)`.
Any call to `_write_ready` on a document not loaded with `selectinload` will silently
accumulate chunks instead of replacing them.

### Phase 1 batch size
Not implemented upfront. If a connector proves to need it during migration, add a
`batch_size` parameter to `prepare_for_indexing` at that point.

### `session.refresh()` is not needed after Phase 1 commit
After Phase 1's commit, `index()` only SETs attributes on the document — it never
READs them. SQLAlchemy write operations do not trigger lazy loading. No refresh needed.

---

## Connector Deviations — Handled at Migration Time

| Connector | Deviation | How handled |
|---|---|---|
| Webcrawler | Content unknown at Phase 1 — fetched during Phase 2 | Call `prepare_for_indexing` per URL after crawling, not in bulk |
| Slack, Discord | No LLM summarization | `should_summarize = False` in `ConnectorDocument` |
| GitHub | Custom 4000-char character chunking | `content_type = "code"` → `code_chunker_instance` |
| Obsidian | LLM called but result discarded, raw content embedded | `should_summarize = True` → pipeline fixes this correctly |

---

## Testing Philosophy

Two rules drive every decision below:

**1. Test behavior through public interfaces, not implementation details.**
`IndexingPipelineService` exposes two public methods: `prepare_for_indexing` and
`index`. Private methods (`_create`, `_summarize`, `_mark_ready`, etc.) are
implementation details. Testing them directly couples tests to internal structure —
renaming a private method breaks tests even though behavior hasn't changed.

**2. Mock only true external boundaries.**
Mocking internal collaborators (session, chunker) tests your assumptions about
those collaborators, not the actual code. A mock never fails because of a bug in
the real system. The DB is not mocked — a real test DB is used. Only the LLM and
embedding model are mocked: they are genuine external services (cost, latency,
non-determinism, network flakiness).

**Consequence:** most tests are integration tests. Unit tests cover only pure
functions and value objects that have no dependencies.

---

## Test Plan

### Unit tests — pure functions and value objects, no mocks

#### `ConnectorDocument`

| Test | Checks |
|---|---|
| `source_markdown` empty → validation error | rejection of invalid input |
| `source_markdown` whitespace only → validation error | rejection of invalid input |
| Valid document created with defaults | all default values correct |
| `should_summarize=False` accepted | optional flag works |
| `content_type="code"` accepted | optional flag works |

#### `_compute_unique_identifier_hash` + `_compute_content_hash`

| Test | Checks |
|---|---|
| Same input → same hash (both functions) | determinism |
| Different `unique_id` → different hash | isolation by field |
| Different `search_space_id` → different hash | isolation by space |
| Different `document_type` → different hash | isolation by type |
| Same content, different space → different hash | space-scoped content dedup |
| Different content → different hash | content sensitivity |

#### Adapters

Each adapter is a pure static converter. Zero mocks needed.

| Test | Checks |
|---|---|
| `to_connector_document` returns valid `ConnectorDocument` | output type |
| `unique_id` maps to correct source field | field mapping |
| `document_type` is correct enum value | enum correctness |
| `source_markdown` contains expected content | content mapping |
| `should_summarize` set correctly for this connector | flag correctness |
| `content_type` set correctly (code vs text) | flag correctness |
| Empty/missing fields handled gracefully | robustness |

---

### Integration tests — real DB, LLM and embedding model mocked

#### `prepare_for_indexing`

| Test | Checks |
|---|---|
| New document → status=pending in DB, returned | `_create` + hash logic |
| Same `content_hash`, same title → skipped, not returned | unchanged dedup |
| Same `content_hash`, different title → title updated, not returned | title-only update |
| Changed `content_hash` → existing doc returned for reprocessing | update detection |
| Duplicate content hash within batch → skipped | same-batch dedup |
| Multiple documents → one commit for all | batch commit |

#### `index`

| Test | Mocks | Checks |
|---|---|---|
| `document.status = ready` after call | llm, embedding | happy path |
| `document.content = summary` when `should_summarize=True` | llm, embedding | summarization used |
| `document.content = source_markdown` when `should_summarize=False` | embedding | summarization skipped |
| `document.source_markdown` always set | llm, embedding | field always written |
| Chunks written to DB | llm, embedding | chunking + persistence |
| `document.status = processing` set before heavy work | llm (slow), embedding | status progression |
| LLM raises → `document.status = failed` | llm (raises) | error handling |
| After LLM error → not stuck in `processing` | llm (raises) | recovery correctness |
| After LLM error → chunks NOT written | llm (raises) | no partial data |

---

## What Does NOT Need Tests

| Component | Reason |
|---|---|
| Private methods of `IndexingPipelineService` | covered by integration tests on public interface |
| Celery task wiring | orchestration only, no logic |
| External API calls (Notion, Slack, etc.) | external dependency, not our logic |
| `get_user_long_context_llm` | existing service, not our code |
| `calculate_date_range` | already has a `# FIX:` comment — needs its own separate tests |
| Full end-to-end indexer run | too many moving parts, not unit or integration |

---

## Files To Create

```
app/indexing_pipeline/
    connector_document.py          ← ConnectorDocument model
    adapters/
        clickup_adapter.py         ← first adapter (pilot)
        notion_adapter.py
        slack_adapter.py
        ...
        google/                    ← created when 2nd Google connector is migrated
            shared.py              ← shared pure helpers (metadata, markdown conversion)
            google_drive_adapter.py
            google_docs_adapter.py

app/clients/                       ← created when 2nd connector of a family is migrated
    google_client.py               ← shared OAuth + API client for all Google connectors

app/indexing_pipeline/
    indexing_pipeline_service.py   ← IndexingPipelineService

tests/
    unit/
        indexing_pipeline/
            test_connector_document.py
            test_compute_hashes.py
        adapters/
            test_clickup_adapter.py
            test_notion_adapter.py
            test_slack_adapter.py
    integration/
        indexing_pipeline/
            test_prepare_for_indexing.py
            test_index.py
```

## TDD Build Order

One test → one implementation → repeat. Never write multiple tests before making
the previous one green.

---

### Phase 1 — `ConnectorDocument` (unit)

**File:** `tests/unit/indexing_pipeline/test_connector_document.py`
**Implements:** `app/indexing_pipeline/connector_document.py`

- `test_empty_source_markdown_raises`
- `test_whitespace_only_source_markdown_raises`
- `test_valid_document_created_with_defaults`
- `test_should_summarize_false_accepted`
- `test_content_type_code_accepted`

→ After this phase: add `make_connector_document` factory fixture to `tests/conftest.py`

---

### Phase 2 — Hash functions (unit)

**File:** `tests/unit/indexing_pipeline/test_compute_hashes.py`
**Implements:** `_compute_unique_identifier_hash`, `_compute_content_hash` on `IndexingPipelineService`

- `test_same_input_same_hash`
- `test_different_unique_id_different_hash`
- `test_different_search_space_id_different_hash`
- `test_different_document_type_different_hash`
- `test_same_content_same_space_same_hash`
- `test_same_content_different_space_different_hash`
- `test_different_content_different_hash`

---

### Phase 3 — `prepare_for_indexing` (integration)

**File:** `tests/integration/indexing_pipeline/test_prepare_for_indexing.py`
**Implements:** `prepare_for_indexing` + all private DB methods it uses

- `test_new_document_written_as_pending`
- `test_unchanged_document_skipped`
- `test_title_only_change_updates_title`
- `test_changed_content_queued_for_reprocessing`
- `test_duplicate_content_in_batch_skipped`
- `test_multiple_documents_one_commit`

---

### Phase 4 — `index` (integration)

**File:** `tests/integration/indexing_pipeline/test_index.py`
**Implements:** `index` + all private processing methods it uses

- `test_sets_status_ready`
- `test_content_is_summary_when_should_summarize_true`
- `test_content_is_source_markdown_when_should_summarize_false`
- `test_source_markdown_always_set`
- `test_chunks_written_to_db`
- `test_status_processing_set_before_heavy_work`
- `test_llm_error_sets_status_failed`
- `test_llm_error_document_not_stuck_in_processing`
- `test_llm_error_chunks_not_written`

---

### Phase 5 — Adapters (unit, one file per connector)

Start with ClickUp — simplest connector, no special deviations.

**File:** `tests/unit/adapters/test_clickup_adapter.py`
**Implements:** `app/pipeline/adapters/clickup_adapter.py`

Then repeat for each connector as it is migrated.

---

**Total: 12 unit tests + 15 integration tests = 27 tests.**

---

## Out of Scope (for now)

Document processors (`youtube_processor`, `file_processors`, `markdown_processor`,
`extension_processor`, `circleback_processor`) follow the same 2-phase pattern and
will eventually migrate to the pipeline. Excluded from this refactor — they handle
user uploads, not connector syncs, and their migration is a separate task.
