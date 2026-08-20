---
story_key: "26-9b"
epic: "epic-26"
story: "26.9b"
title: "Pro Excel Formatter in Daytona Sandbox"
status: "done"
baseline_commit: "6924b87dae9a1893a1d7639ce41faf4e4b7a4f34"
---

# Story 26.9b: Pro Excel Formatter in Daytona Sandbox

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Input is the wide-research matrix from `checkpoint.wide_research_matrix`.**
   - Story 26.9a writes a JSON matrix to the mission checkpoint.
   - Story 26.9b reads that matrix at the end of `ingestion` (or in a new `deliver` node) and generates an `.xlsx` file.

2. **Daytona sandbox is the execution environment.**
   - Reuse `middleware/filesystem/sandbox.py:get_or_create_sandbox()` and `sandbox_routes.py`.
   - Sandbox has `pandas`, `numpy`, `openpyxl` pre-installed.
   - Formatter is a Python script template, not a new dependency on the backend.

3. **Excel output features.**
   - Multiple tabs: Summary, Sources, Topics, Topic × Source Matrix.
   - Conditional formatting, auto-filter, formulas (e.g., count of sources per topic).
   - No PII in plain text; phones / tax IDs are masked or omitted.

---

## Story

As a sales ops user,
I want a wide-research DSH mission to produce a formatted Excel workbook in a Daytona sandbox,
so that I can share structured research output without building reports manually.

---

## Acceptance Criteria

### AC-1: Deliverable trigger

- **Given** a mission with `checkpoint.wide_research_matrix`,
- **When** the `ingestion` / `deliver` node runs Story 26.9b,
- **Then** it creates a sandbox, executes the formatter script, and stores the `.xlsx` file reference in `checkpoint.deliverables`.

### AC-2: Download route

- **Given** the `.xlsx` file exists in the sandbox,
- **When** the user requests download,
- **Then** `sandbox_routes.py` returns the file with MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

### AC-3: Formatter quality

- **Given** the formatter script runs,
- **When** it finishes,
- **Then** the workbook has at least the Summary, Sources, Topics, and Matrix tabs; `ruff check` on the script template is clean; and the file size is under 10 MB for 1,000 sources.

### AC-4: No PII leak

- **Given** the input matrix contains phone / email / tax IDs,
- **When** the formatter writes the workbook,
- **Then** those values are masked or omitted unless the caller explicitly opts in with `include_pii=true` and has the `LEADS_READ` permission.

---

## Tasks / Subtasks

- [x] Step 1: Add `openpyxl` to Daytona snapshot and update sandbox description.
- [x] Step 2: Create `scripts/sandbox_pro_excel_template.py` formatter script (Summary, Sources, Topics, Matrix tabs; PII redaction; file-size guard).
- [x] Step 3: Add `deliver` node to `LangGraphMissionExecutor` and `dsh_worker_deliver_subgraph.py`.
- [x] Step 4: Add DSH deliverable download route to `sandbox_routes.py` with `LEADS_READ` and `include_pii` checks.
- [x] Step 5: Add unit/integration tests for formatter template and download route.
- [x] Step 6: Run tests, ruff, and integration checks.

## Implementation Notes

### New files

| File | Purpose |
|---|---|
| `nowing_backend/app/tasks/dsh_worker_deliver_subgraph.py` (optional) | New `deliver` subgraph or extend `ingestion` node. |
| `nowing_backend/scripts/sandbox_pro_excel_template.py` | Python template loaded into sandbox. |
| `nowing_backend/tests/integration/dsh/test_pro_excel_formatter.py` | Integration test for sandbox execution + download. |

### Changed files

| File | Change |
|---|---|
| `nowing_backend/app/tasks/dsh_worker_langgraph.py` | Add `deliver` node and edge `ingestion -> deliver -> END` in `_build_graph`. Resumption follows same pattern as other nodes (`_subtask_success` check). |
| `nowing_backend/app/routes/sandbox_routes.py` | Add new DSH deliverable download route (current route is chat-only). Ensure `.xlsx` MIME, permission `LEADS_READ` (+ opt-in PII flag). |
| `nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/filesystem/sandbox.py` | Use `mission_id` as sandbox key; confirm `openpyxl` is in snapshot or install at runtime. |
| `nowing_backend/scripts/create_sandbox_snapshot.py` | Add `openpyxl` to `PACKAGES` so the Daytona snapshot has xlsx write support. |

### Validation Findings (must resolve before/during dev)

| Severity | Finding | Mitigation in story |
|---|---|---|
| High | `openpyxl` is **not** in the current Daytona snapshot (`scripts/create_sandbox_snapshot.py` only installs `pandas`, `numpy`, `matplotlib`, `scipy`, `scikit-learn`). `pandas.to_excel` for `.xlsx` will fail without it. | Add `openpyxl` to `PACKAGES` in `create_sandbox_snapshot.py` and update `execute_code/description.py` if needed. Fallback: install via `pip install openpyxl` in the formatter script if allowed by network. |
| High | `sandbox_routes.py` route `/threads/{thread_id}/sandbox/download` is hard-coded to chat threads (`NewChatThread`) and checks `Permission.CHATS_READ`. DSH deliverable download needs a mission-scoped route. | Add `GET /workspaces/{workspace_id}/dsh/missions/{mission_id}/deliverables/{filename}` or equivalent; check `LEADS_READ` and `include_pii` flag. |
| High | PII masking (AC-4) is not implemented anywhere in the Excel path. `wide_research_matrix.sources` may contain raw `content`/emails/phones. | Pass an `include_pii: bool` option; default to redact `content` and any non-whitelisted fields. Reuse `_normalize_source` pattern from 26.9a. |
| Medium | Sandbox lifecycle is thread-oriented. Reusing `get_or_create_sandbox(mission_id)` works (the label is just `nowing_thread`), but file persistence and deletion logic assume thread context. | Document that `mission_id` is used as the sandbox key; ensure `persist_and_delete_sandbox` is called after the formatter writes `/home/daytona/documents/...`. |
| Medium | File-size guard (AC-3 "under 10 MB") is not specified in design. | Add `xl` writer guard or post-execution size check; fail gracefully if > 10 MB. |
| Medium | `deliver` node placement is ambiguous. Running deliver for every mission may add latency/cost; it should be gated on `research_mode=wide` or on `checkpoint.wide_research_matrix`. | AC-1 should read: "Given `research_mode=wide` (or `checkpoint.wide_research_matrix` exists)". |
| Low | `ruff check` on a script template inside a sandbox is unusual; the dev agent should lint the template file in the repo (`scripts/sandbox_pro_excel_template.py`) with `ruff`. | Update AC-3 to clarify `ruff` runs on the repo template, not inside the sandbox. |
| Low | `deliverables` schema is not defined; UI/frontend may not know how to display it. | Define `checkpoint.deliverables` as a list of `{type, filename, sandbox_path, size, created_at}` objects. |

### Decisions needed

1. **New download route or reuse thread route?** Decision: add a dedicated DSH deliverable route (recommended) to avoid coupling DSH to chat thread model.
2. **Include PII default?** Decision: default `include_pii=false`; only workspace members with `LEADS_READ` can request `include_pii=true`.
3. **Keep sandbox alive or persist-and-delete?** Decision: use `persist_and_delete_sandbox` pattern; file is served from local `SANDBOX_FILES_DIR` via the new route.

---

## File List

### New files

- `nowing_backend/app/tasks/dsh_worker_deliver_subgraph.py`
- `nowing_backend/scripts/sandbox_pro_excel_template.py`
- `nowing_backend/tests/unit/tasks/test_dsh_worker_deliver_subgraph.py`
- `nowing_backend/tests/integration/dsh/test_pro_excel_formatter.py`

### Modified files

- `nowing_backend/app/tasks/dsh_worker_langgraph.py`
- `nowing_backend/app/routes/sandbox_routes.py`
- `nowing_backend/scripts/create_sandbox_snapshot.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/filesystem/tools/execute_code/description.py`

---

## Change Log

- Added `openpyxl` to Daytona snapshot PACKAGES and updated `execute_code` description.
- Created Pro Excel formatter template with 4 tabs, PII redaction, conditional formatting, auto-filter, and 10 MB size guard.
- Added `DshDeliverSubgraph` and `deliver` node to `LangGraphMissionExecutor` (graph: `ingestion -> deliver -> END`).
- Added DSH deliverable download route with `LEADS_READ` permission check.
- Added unit tests for formatter and deliver subgraph; integration tests for the download route.
- Applied code-review patches: removed live-sandbox fallback / dead `include_pii` query, added `include_pii` metadata, verified formatter output, used `sync_files_to_sandbox` for caching, fixed `_bool_from_raw` and PII regex.
- Verified: `ruff` clean, `tests/unit/tasks` 202 passed, `tests/integration/dsh/test_pro_excel_formatter.py` 3 passed.

---

## Dev Agent Record

### Debug Log

- `DshDeliverSubgraph` initially used `__file__` path off by one directory; corrected to repo root.
- `dsh_worker_langgraph.py` `_deliver_node` needed `_is_valid_matrix` gate to avoid running sandbox on degenerate test matrices.
- Formatter template required ruff fixes (UP015/UP017/RUF005/B905).

### Completion Notes

All ACs satisfied:
- AC-1: `deliver` node creates sandbox, runs formatter, stores `.xlsx` reference in `checkpoint.deliverables`.
- AC-2: New download route returns `.xlsx` with `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- AC-3: Workbook has Summary, Sources, Topics, Matrix tabs; template is `ruff` clean; file size guard < 10 MB.
- AC-4: PII fields are redacted by default; `include_pii=true` can be set via mission payload `extras`. Download requires `LEADS_READ`.

Story status: `done`

---

### Review Findings

- [x] [Review][Patch] Download route blocks local files when sandbox is disabled (`sandbox_routes.py:135-136`) — AC-2 is violated for persisted deliverables in `DAYTONA_SANDBOX_ENABLED=false` environments. Move `is_sandbox_enabled()` check to guard only the live-sandbox fallback.
- [x] [Review][Patch] Download route `include_pii` query parameter is dead state (`sandbox_routes.py:120,143`) — it is accepted but never used to select or regenerate a PII-included deliverable. Remove it or wire it to deliverable metadata.
- [x] [Review][Patch] PII opt-in is only checked at mission creation, not at generation/download (`dsh_worker_deliver_subgraph.py:91`, `dsh_worker_langgraph.py:419`) — a mission created with `extras.include_pii=true` persists PII, and any `LEADS_READ` holder can download. AC-4 intent should be enforced by recording `include_pii` in deliverable metadata and/or requiring `LEADS_READ` at the route.
- [x] [Review][Patch] Formatter output file is not verified to exist before the sandbox is deleted (`dsh_worker_deliver_subgraph.py:126-128`) — if the formatter writes to a different path or `persist_and_delete_sandbox` silently skips, `get_local_sandbox_file` returns `None` after deletion.
- [x] [Review][Patch] `download_dsh_deliverable` fallback tries to create a sandbox to download a file that was already deleted after persist (`sandbox_routes.py:177-184`) — this fallback is unlikely to succeed and may leak a sandbox; prefer 404 when local file is missing.
- [x] [Review][Patch] Formatter script `_bool_from_raw` coerces any non-empty, non-false string to `True` (`sandbox_pro_excel_template.py:568-575`) — strings like `"maybe"` or `"-"` become `True`, misrepresenting the matrix.
- [x] [Review][Patch] Formatter PII regex in topic text over-matches (`sandbox_pro_excel_template.py:553-554`) — `a.b@c.d` or `@home` in a topic will be masked as `[EMAIL]`.
- [x] [Review][Patch] Formatter script re-uploads on every mission run with no caching (`dsh_worker_deliver_subgraph.py:95-106`) — adds latency and network overhead inside the 300s timeout; consider pre-baking the formatter in the snapshot or checking existence before upload.
- [x] [Review][Defer] Hardcoded `filename == "wide_research_output.xlsx"` in `DshDeliverSubgraph` (`dsh_worker_deliver_subgraph.py:136`) — pre-existing pattern for single deliverable; revisit if multi-deliverable support is added.
