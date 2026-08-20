---
story_key: "26-9b"
epic: "epic-26"
story: "26.9b"
title: "Pro Excel Formatter in Daytona Sandbox"
status: "backlog"
baseline_commit: "TBD"
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
| `nowing_backend/app/tasks/dsh_worker_langgraph.py` | Add `deliver` edge from `ingestion` or extend `ingestion` node. |
| `nowing_backend/app/routes/sandbox_routes.py` | Ensure `.xlsx` MIME is served from sandbox file store. |
