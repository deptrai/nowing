---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 3-16-okf-knowledge-export
status: done
---

# Story 3.16: Open Knowledge Format (OKF) Knowledge Export

**Status:** done
**Epic:** 3 — Knowledge Base + Long-Term Memory
**Priority:** MEDIUM
**Requirements:** FR-32, RS-8
**Architecture:** AD-11.1
**Dependencies:** Story 3.8 (memory), 3.7 (retention/export policy), 3.13 (memory provenance), 3.15 (run citations).

## Story

As a data owner or integrator,
I want to export my workspace knowledge base in Open Knowledge Format (OKF),
So that I can move, archive, or integrate Nowing knowledge with other tools.

## Context

### Upstream reference

SurfSense PR #1617 (`MODSetter/SurfSense#1617`, merged commit `08d431454fe2bd118dc311bfdd59d01848c6fa90`) already implemented the OKF pattern we need to port:

- Added `surfsense_backend/app/services/okf/` as a pure serialization package:
  - `serializer.py` builds YAML frontmatter and turns a `Document` row into an OKF concept (`document_to_concept`), builds `index.md` listings (`folder_to_index`), and builds `log.md` change logs (`folder_to_log`).
  - `type_mapping.py` maps `DocumentType` → OKF `type` strings (e.g. `NOTE` → `"Note"`, `CRAWLED_URL` → `"Web Page"`) and extracts a canonical `resource` URL from `document_metadata` keys such as `url`, `permalink`, `html_url`, `webViewLink`.
  - `validator.py` provides `parse_frontmatter`, `validate_concept`, `validate_bundle`, and `is_conformant_concept`; only `type` is required, reserved `index.md`/`log.md` are exempt.
- Updated `surfsense_backend/app/services/export_service.py` (`build_export_zip`) to:
  - Resolve document markdown from `source_markdown` → `blocknote_document` → chunk concatenation (`resolve_document_markdown`).
  - Emit each document as an OKF concept `.md` inside the folder tree.
  - Accumulate `ConceptRef` and `LogEntry` entries per directory and write OKF `index.md` and `log.md` files, including a root `index.md` with `okf_version: "0.1"` frontmatter.
  - Avoid filename collisions with reserved stems (`index`, `log`) and deduplicate same-title concepts with a numeric suffix.
  - Keep batched `LIMIT/OFFSET` document reads and append each batch to the ZIP via `asyncio.to_thread`.
- Added content negotiation to `GET /documents/{id}` in `surfsense_backend/app/routes/documents_routes.py`: when `Accept` contains `text/markdown`, it returns a `PlainTextResponse` with the OKF concept; otherwise it returns the JSON `DocumentRead` record.
- Wired `surfsense_mcp/mcp_server/core/client.py` to accept per-request `headers` and made `get_document` request `Accept: text/markdown` when `response_format == "markdown"`.
- Added unit tests (`tests/unit/services/okf/*`) and integration tests (`tests/integration/test_okf_export_bundle.py`, `test_okf_read.py`, `test_okf_path_identity.py`).

Upstream deliberately keeps **storage unchanged** — frontmatter is derived at read time, never stored, and chunks/embeddings remain a derived search projection.

### Nowing current state

- `nowing_backend/app/services/export_service.py` (line 82 `build_export_zip`, line 46 `_get_document_markdown`) and `nowing_backend/app/routes/export_routes.py` (line 21 `export_knowledge_base`) already export a ZIP of plain markdown documents per workspace/folder. They do **not** emit OKF frontmatter, `index.md`, `log.md`, or memory/relations.
- `nowing_backend/app/db.py` has the models we need to export:
  - `Document` (line 1418), `Chunk` (line 1541), `Memory` (line 2025), `MemoryRelation` (line 2166), `Folder` (line 1380).
  - `DocumentType` enum (line 44) and `Permission` enum with `DOCUMENTS_READ` / `MEMORY_READ` (line 299).
- `nowing_backend/app/routes/documents_routes.py::read_document` (line 1294) returns JSON only; it does not content-negotiate `text/markdown`.
- `nowing_mcp/mcp_server/core/client.py::request` (line 55) has no `headers` override; `nowing_mcp/mcp_server/features/knowledge_base/search_tools.py::get_document` (line 112) always requests JSON and renders it by hand.
- `nowing_backend/app/schemas/memory.py::MemoryRead` (line 43) and `MemorySearchHit` (line 146) expose `source_run_id`, `source_capability`, `source_input`, and a computed `citation` (`run_<uuid>`), giving us the provenance fields to serialize.
- No `nowing_backend/app/services/okf/` package exists.
- No secret redaction helper exists for export content; `document_metadata` and `Memory.source_input` may contain connector-specific JSON that can carry `api_key`, `token`, `secret`, and other credentials.

## Acceptance Criteria

1. **OKF bundle structure**
   - **Given** a workspace with documents, chunks, memories, relations, and source provenance, **When** I request an OKF export, **Then** it produces a valid OKF v0.2 bundle where every concept file has parseable YAML frontmatter with a non-empty `type`, and the whole bundle passes `validate_bundle`.
   - **And** the bundle preserves the workspace folder hierarchy for documents and contains per-directory `index.md` listings and `log.md` change logs, plus a root `index.md` declaring `okf_version`.
   - **And** each `Document` becomes an OKF concept with `type`, `title`, `description`, `resource`, `tags`, and `timestamp` derived from its columns and `document_metadata`.
   - **And** each `Chunk`, `Memory`, `MemoryRelation`, and citation is represented as an additional OKF concept under a reserved subdirectory (e.g. `.okf/chunks/`, `.okf/memories/`, `.okf/relations/`, `.okf/citations/`) with its own `index.md` and `log.md`.

2. **DocumentType & resource mapping**
   - **Given** a document of any `DocumentType`, **When** it is serialized, **Then** the OKF `type` string is a human-readable Title Case value (e.g. `Note`, `Web Page`, `Slack Message`, `GitHub Document`) and the `resource` frontmatter is extracted from known metadata URL keys without leaking internal integer ids.

3. **Content-negotiated single-document read**
   - **Given** `GET /documents/{document_id}` with `Accept: text/markdown`, **When** the caller has `documents:read`, **Then** it returns a `200` `text/markdown` OKF concept.
   - **And** the default `Accept: application/json` still returns the existing `DocumentRead` JSON.

4. **Tenant isolation & redaction**
   - **Given** an export is generated, **When** inspected, **Then** it does not include data from other workspaces and redacts API keys, tokens, secrets, and passwords found in `document_metadata`, `Memory.source_input`, or any other JSON provenance.
   - **And** raw cross-tenant `source_id` values are not exposed; provenance is serialized as stable bundle-relative paths or public citations (`run_<uuid>` / `chat_<id>`) where appropriate.

5. **Large workspace handling**
   - **Given** a large knowledge base, **When** I request an export, **Then** the job streams/paginates documents, chunks, memories, and relations in batches (default 100 rows) and writes them to a temp ZIP incrementally so it does not OOM.
   - **And** documents in `pending` or `processing` state are skipped and reported in the `X-Skipped-Documents` header.

6. **Permission & access**
   - **Given** a workspace member without `documents:read` (and `memory:read` when the bundle includes memory facts), **When** they request an export, **Then** they receive `403`.

7. **MCP round-trip**
   - **Given** `nowing_get_document(document_id, response_format="markdown")`, **When** called, **Then** the MCP client sends `Accept: text/markdown` and returns the OKF concept text unchanged.

## Tasks / Subtasks

### Backend — OKF serialization package

- [x] Create `nowing_backend/app/services/okf/__init__.py`
  - Export `INDEX_FILENAME`, `LOG_FILENAME`, `ConceptRef`, `LogEntry`, `SubdirRef`, `build_frontmatter`, `document_to_concept`, `memory_to_concept`, `chunk_to_concept`, `relation_to_concept`, `citation_to_concept`, `folder_to_index`, `folder_to_log`, `render_frontmatter`, `okf_resource`, `okf_type`, `redact_secrets`, `is_conformant_concept`, `parse_frontmatter`, `validate_bundle`, `validate_concept`.
- [x] Create `nowing_backend/app/services/okf/serializer.py`
  - [ ] `build_frontmatter(model)` returns ordered `{type, resource?, title?, description?, tags?, timestamp?, ...}` from `Document` / `Memory` / `Chunk` / `MemoryRelation` and redacted metadata.
  - [ ] `render_frontmatter(frontmatter)` uses `yaml.safe_dump` with `sort_keys=False` and delimiters `---`.
  - [ ] `concept_to_markdown(frontmatter, body)` and type-specific helpers `document_to_concept`, `memory_to_concept`, `chunk_to_concept`, `relation_to_concept`, `citation_to_concept`.
  - [ ] `ConceptRef`, `LogEntry`, `SubdirRef` dataclasses.
  - [ ] `folder_to_index(concepts, subdirectories)` and `folder_to_log(entries)` mirroring upstream grouping/newest-first behavior.
- [x] Create `nowing_backend/app/services/okf/type_mapping.py`
  - [ ] `OKF_TYPE_BY_DOCUMENT_TYPE` mapping for every `DocumentType` in `app/db.py` line 44.
  - [ ] `okf_type(document_type)` with fallback to Title-Cased enum value.
  - [ ] `okf_resource(document_type, metadata)` scanning known URL keys (`url`, `permalink`, `html_url`, `webViewLink`, `source_url`, `sourceUrl`, etc.) and returning only `http(s)` URIs.
  - [ ] `okf_memory_type`, `okf_relation_type`, `okf_chunk_type`, `okf_citation_type` helpers.
- [x] Create `nowing_backend/app/services/okf/validator.py`
  - [ ] `parse_frontmatter(text)` returns `(dict, error)`.
  - [ ] `validate_concept(text)` checks frontmatter `type` is a non-empty string.
  - [ ] `validate_bundle(files: dict[str, str])` returns path→errors; exempts `index.md` and `log.md`.
  - [ ] `is_conformant_concept(text)` convenience.
- [x] Create `nowing_backend/app/services/okf/redaction.py`
  - [ ] `redact_secrets(value: Any) -> Any` recursively redacts dict/list/str.
  - [ ] Redact values for keys matching `api_key`, `token`, `secret`, `password`, `access_token`, `refresh_token`, `bearer`, `authorization`, `credentials`, `private_key`, `client_secret` (case-insensitive, substring match).
  - [ ] Redact string values matching common token patterns (`sk-...`, `pat_...`, `Bearer ...`, `nw_pat_...`, hex-like secrets ≥ 20 chars).
  - [ ] Replace with `"[REDACTED]"`.

### Backend — export service

- [x] Update `nowing_backend/app/services/export_service.py`
  - [ ] Rename `_get_document_markdown` to `resolve_document_markdown` (public) and keep the 3-tier fallback: `source_markdown` → `blocknote_document` markdown conversion → chunk concatenation.
  - [ ] Import OKF helpers; build concepts instead of plain markdown files.
  - [ ] Accumulate `dir_concepts` and `dir_logs` for both the document tree and the `.okf/{chunks,memories,relations,citations}/` trees.
  - [ ] Write reserved `index.md` and `log.md` files for every directory that has content, with root `index.md` frontmatter declaring `okf_version: "0.2"`.
  - [ ] Avoid reserved stems (`index`, `log`) and deduplicate titles with `_<n>` suffix.
  - [ ] Add workspace-scoped, batched reads for `Chunk`, `Memory`, and `MemoryRelation` alongside the existing `Document` batch loop.
  - [ ] Redact `document_metadata`, `Memory.source_input`, and any other JSON provenance before serialization.
  - [ ] Skip `Document` rows whose `status["state"]` is `pending` or `processing`; report them in `ExportResult.skipped_docs`.
  - [ ] Continue to write the ZIP in `w`/`a` batches via `asyncio.to_thread` and return `ExportResult(zip_path, export_name, zip_size, skipped_docs)`.
- [x] Update `nowing_backend/app/routes/export_routes.py`
  - [ ] Permission check: require `Permission.DOCUMENTS_READ.value`; if the request includes memory facts, also require `Permission.MEMORY_READ.value`.
  - [ ] Call `build_export_zip` and stream the temp file with `Content-Disposition`, `Content-Length`, and `X-Skipped-Documents` headers; unlink the temp file after streaming.

### Backend — single-document OKF read

- [x] Update `nowing_backend/app/routes/documents_routes.py::read_document` (line 1294)
  - [ ] Add `request: Request` parameter and import `PlainTextResponse`.
  - [ ] After the permission check, if `"text/markdown"` is in `request.headers.get("accept", "")`, resolve markdown and return `PlainTextResponse(document_to_concept(document, body=markdown), media_type="text/markdown")`.
  - [ ] Keep the existing JSON branch unchanged.

### MCP client & tool

- [x] Update `nowing_mcp/mcp_server/core/client.py::request` (line 55)
  - [ ] Add optional `headers: dict[str, str] | None = None` parameter and merge with auth headers: `headers = {**self._auth_headers(), **(headers or {})}`.
- [x] Update `nowing_mcp/mcp_server/features/knowledge_base/search_tools.py::get_document` (line 112)
  - [ ] When `response_format == "json"`, call `client.request("GET", f"/documents/{document_id}")`.
  - [ ] When `response_format == "markdown"`, call `client.request("GET", f"/documents/{document_id}", headers={"Accept": "text/markdown"})` and return the concept text directly (clip if too long).

### Tests

- [x] `nowing_backend/tests/unit/services/okf/test_serializer.py` — concept building, index/log rendering, reserved filenames.
- [x] `nowing_backend/tests/unit/services/okf/test_type_mapping.py` — every `DocumentType` maps to a non-empty OKF type; URL extraction for each connector's metadata shape.
- [x] `nowing_backend/tests/unit/services/okf/test_validator.py` — frontmatter parsing, `validate_bundle` on sample exports, reserved-file exemption.
- [x] `nowing_backend/tests/unit/services/okf/test_redaction.py` — redaction of keys and regex-shaped tokens, nested dicts/lists.
- [x] `nowing_backend/tests/integration/test_okf_export_bundle.py` — create documents, chunks, memories, relations; call `build_export_zip`; assert `validate_bundle` is empty and reserved files present.
- [x] `nowing_backend/tests/integration/document_upload/test_okf_read.py` — content-negotiated `GET /documents/{id}` returns `text/markdown` OKF concept and default returns JSON.
- [x] `nowing_mcp/tests/test_get_document_okf.py` — mock client records `Accept: text/markdown` and passes concept text through.

## Dev Notes

- **Port, do not blindly copy.** SurfSense uses the same FastAPI + Pydantic v2 + SQLAlchemy stack, but Nowing has additional models (`Memory`, `MemoryRelation`, `Chunk`) and provenance fields (`source_run_id`, `source_input`, `source_capability`) that must be included in the OKF bundle.
- **Storage remains the source of truth.** OKF frontmatter is derived from `Document`, `Memory`, `Chunk`, and `MemoryRelation` columns on read; it is never stored. Chunks and embeddings remain a derived, rebuildable search projection.
- **Redaction is an export-time concern.** Run `redact_secrets` on `document_metadata`, `Memory.source_input`, and any other JSON payload before it becomes frontmatter or body. Do not mutate the database rows.
- **Workspace scoping is mandatory.** Every SELECT for the export must include `workspace_id == <id>`. `Memory.workspace_id` is nullable for user memory; only export non-null workspace memories. `MemoryRelation` has its own `workspace_id` column.
- **Do not expose raw internal `source_id` values in the bundle.** Map `Memory.source_type == "document"` to a bundle-relative document path, `source_type == "scraper_run"` to `run_<uuid>`, and `source_type == "chat_message"` to `chat_<id>`. This matches the existing `MemoryRead.citation` convention (`run_<uuid>`).
- **OKF version:** target `okf_version: "0.2"` (the current spec); upstream used `0.1`.
- **Filename safety:** `_sanitize_filename` keeps alphanumerics, spaces, hyphens, underscores, and dots, truncates to 80 chars, and collides are resolved with `_1`, `_2`, etc. Reserve `index` and `log` stems by appending `_`.
- **Batching/Streaming:** keep the existing `batch_size = 100` loop, apply it to `Chunk`, `Memory`, and `MemoryRelation` as well, and write each batch to the temp ZIP before loading the next. Use `asyncio.to_thread` for disk I/O.
- **ponytail:** keep the OKF package free of HTTP/MCP/framework dependencies; it should be pure functions operating on ORM rows and returning strings. The only I/O belongs in `export_service.py` and the route.
- The `nowing_mcp` server calls the same REST routes, so it automatically receives the OKF concept when it sets `Accept: text/markdown`; no separate MCP serialization code is needed.

## Verification

- [x] Backend unit tests pass:
  ```bash
  cd nowing_backend
  pytest tests/unit/services/okf/ -q
  pytest tests/integration/test_okf_export_bundle.py -q
  pytest tests/integration/document_upload/test_okf_read.py -q
  ```
- [x] Backend lint / typecheck:
  ```bash
  cd nowing_backend
  ruff check app/services/okf/ app/services/export_service.py app/routes/export_routes.py app/routes/documents_routes.py
  ruff format app/services/okf/ app/services/export_service.py app/routes/export_routes.py app/routes/documents_routes.py
  ```
- [x] MCP tests pass:
  ```bash
  cd nowing_mcp
  pytest tests/test_get_document_okf.py -q
  ruff check mcp_server/core/client.py mcp_server/features/knowledge_base/search_tools.py
  ```
- [x] Manual smoke test:
  ```bash
  curl -H "Accept: text/markdown" "http://localhost:8000/api/v1/documents/{id}"
  curl -o /tmp/export.zip "http://localhost:8000/api/v1/workspaces/{id}/export"
  python - <<'PY'
  import zipfile, json
  from nowing_backend.app.services.okf import validate_bundle
  with zipfile.ZipFile('/tmp/export.zip') as zf:
      files = {n: zf.read(n).decode('utf-8') for n in zf.namelist()}
  print(validate_bundle(files))
  PY
  ```
- [x] Bundle sanity checks:
  - `index.md` starts with `---\nokf_version: "0.2"`.
  - Reserved `index.md` and `log.md` files do not have YAML frontmatter.
  - No file contains a string matching `nw_pat_` or an `api_key` value.
  - `validate_bundle(files) == {}`.

## Review Findings (tech debt review 2026-08-08)

Scope: commit `80a6c5fa6` — OKF export implementation.

**patch (LOW) — fixed 2026-08-08:**
- [x] [Review][Patch] Path traversal risk in `_sanitize_filename` — dots (`.`) allowed in filenames, could create `..` segments for ZIP slip. Fixed by removing `.` from allowed characters. File extensions (`.md`) are appended separately by `_unique_file_path`. [edge]

**dismissed:** 2 (BlockNote redaction — `blocknote_document` is user-authored content, not system metadata; `source_capability` not redacted — capability name string, not a secret)

**Mutation gate (redaction module):** 100% (10/10 killed) — PASS
**Unit tests:** 40 passed
**MCP tests:** 2 passed
**Ruff:** All checks passed

## References

- Upstream PR: `MODSetter/SurfSense#1617`
- Upstream merge commit: `08d431454fe2bd118dc311bfdd59d01848c6fa90`
- Upstream files:
  - `surfsense_backend/app/services/okf/__init__.py`
  - `surfsense_backend/app/services/okf/serializer.py`
  - `surfsense_backend/app/services/okf/type_mapping.py`
  - `surfsense_backend/app/services/okf/validator.py`
  - `surfsense_backend/app/services/export_service.py`
  - `surfsense_backend/app/routes/documents_routes.py`
  - `surfsense_backend/app/routes/export_routes.py`
  - `surfsense_mcp/mcp_server/core/client.py`
  - `surfsense_mcp/mcp_server/features/knowledge_base/search_tools.py`
- OKF spec: `https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md`
- Nowing files:
  - `nowing_backend/app/db.py` (`Document` line 1418, `Chunk` line 1541, `Memory` line 2025, `MemoryRelation` line 2166, `DocumentType` line 44, `Permission` line 299)
  - `nowing_backend/app/services/export_service.py` (`build_export_zip` line 82, `_get_document_markdown` line 46)
  - `nowing_backend/app/routes/export_routes.py` (`export_knowledge_base` line 21)
  - `nowing_backend/app/routes/documents_routes.py` (`read_document` line 1294)
  - `nowing_backend/app/schemas/memory.py` (`MemoryRead` line 43, `MemorySearchHit` line 146)
  - `nowing_mcp/mcp_server/core/client.py` (`request` line 55)
  - `nowing_mcp/mcp_server/features/knowledge_base/search_tools.py` (`get_document` line 112)
