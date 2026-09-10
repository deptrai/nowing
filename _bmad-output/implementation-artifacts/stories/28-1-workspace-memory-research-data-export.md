---
story_key: 28-1-workspace-memory-research-data-export
status: done
epic: 28
---

# Story 28.1: Workspace Memory & Research Data Export

**Status:** `done`  
**Epic:** Epic 28 — Self-Host Trust, Data Portability & Legal Readiness

## Story

As a workspace owner,  
I want to export all workspace memory, research threads, and citations in JSON or CSV on top of OKF,  
so that I can back up, migrate, or leave the platform without lock-in.

## Acceptance Criteria

- **Given** a workspace with memories, research threads, and citations, **When** an owner requests a portable export, **Then** the backend produces a ZIP containing JSON/CSV files plus the canonical OKF bundle, scoped strictly to that workspace.
- **Given** a workspace with no memories or documents, **When** an export is requested, **Then** it returns an empty but valid bundle with `item_count=0` instead of a 500 error.
- **Given** the export contains memory with `source_run_id` or `source_uuid`, **When** the CSV is opened, **Then** provenance fields are preserved as stable identifiers so citations can be re-linked after import.
- **Given** a large workspace with >10,000 memories, **When** the export runs, **Then** it streams in batches, enforces a file size limit per part, and does not OOM the worker.
- **Given** a memory has a corrupted embedding or missing `content`, **When** the export reaches that row, **Then** it logs `export_row_skipped` and continues, producing a valid bundle.

## Dev Notes

- Export format: OKF bundle + derived JSON/CSV
- Redaction: API keys, OAuth tokens, embeddings for human-readable formats
- FR-95 · AR-11 · RS-8 · INV-28.4 · AD-28.2

## Verification

- Service: `app/services/export_service.py`
- Tests: empty workspace, batch streaming, provenance preservation, redaction
