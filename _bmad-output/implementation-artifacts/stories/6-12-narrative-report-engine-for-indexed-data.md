---
story_key: 6-12-narrative-report-engine-for-indexed-data
status: done
baseline_commit: fb2613d66
epic: 6
story: 12
---

# Story 6.12: Narrative Report Engine for Indexed Data

**Status:** `done`  
**Epic:** 6 — Automations  
**Governed by:** AD-33 (Generic Alert Engine Scheduler), AD-34 (Citation & Provenance Architecture), AD-35 (Graceful Degradation Contract), `epics.md` lines 4092–4105.  
**Consolidated from:** Story 14.4 (News Digest & Synthesis), Story 15.4 (Financial Trend Detection), Story 16.4 (Company Timeline).

---

## Story

As an **analyst or business researcher**,  
I want a unified narrative report engine that queries indexed and scraped data (news articles, corporate registries, and financial statements) and prompts an LLM to generate structured narratives (News Digest, Financial Trend Detection, and Company Event Timeline) with click-through citations and provenance badges,  
so that I can understand longitudinal market trends and company evolutions in seconds without reading through dozens of disparate sources or writing bespoke synthesis pipelines.

---

## Acceptance Criteria

### AC-1 — Narrative Report Templates & Configuration Catalog
**Given** the narrative report backend,  
**When** a client requests available narrative templates via `GET /workspaces/{workspace_id}/reports/narrative/templates`,  
**Then** it returns the registered narrative templates:
1. `news_digest`:
   - Narrative style: `digest`
   - Parameters: `topic` (string, required), `timeframe_days` (int, default 7), `max_sources` (int, default 15).
   - Expected output structure: Executive Summary, Key Developing Stories, Entity Mentions & Sentiment, Citations list.
2. `financial_trend`:
   - Narrative style: `trend`
   - Parameters: `symbol` (string, required, e.g. "VNM", "FPT"), `metrics` (list of strings: revenue, margin, debt), `periods` (int, default 4).
   - Expected output structure: Financial Overview, Growth & Margin Trajectory, Key Metric Changes with supporting numbers, Citations.
3. `company_timeline`:
   - Narrative style: `timeline`
   - Parameters: `company_name_or_tax_code` (string, required), `event_categories` (list of strings: all, legal, business, leadership).
   - Expected output structure: Chronological Event Feed, Event Badges (date, source, change type), Evolution Analysis, Citations.

### AC-2 — Data Ingress & Grounded LLM Synthesis with Source Citations
**Given** a valid narrative report request,  
**When** the synthesis engine executes:
1. It queries relevant indexed chunks or domain data sources (`chainlens.research`, `news.entity_search`, `cafef.scrape`, `masothue.scrape`).
2. It prompts the LLM with strict grounding instructions: every non-obvious claim or data point must cite an indexed source identifier (`[sourceId]`).
3. It parses the synthesized response into Markdown and metadata containing a typed list of `SourceCitation` (`source_id`, `title`, `url`, `pub_date`, `source_type`).
4. It persists a standard `Report` row in the database with `workspace_id`, `title`, `content`, `report_style`, and `report_metadata`.
5. Returns `201 Created` with the generated `ReportContentRead` including the citation metadata.

### AC-3 — Scheduled & Automated Generation via Generic Alert Scheduler
**Given** a recurring monitoring cadence configured for a narrative report,  
**When** Celery Beat or automation trigger runs:
1. The engine executes the synthesis pipeline in the background.
2. Upon completion, it updates or creates a new `Report` artifact linked to the workspace.
3. It creates an `in_app` notification with deep link: `/dashboard/{workspace_id}/reports/{report_id}`.

### AC-4 — Graceful Degradation on Missing Data or LLM Failure
**Given** a narrative report execution,  
**When** the underlying data source is empty, rate-limited (429), or LLM synthesis fails:
1. The engine does not crash or raise unhandled 500 errors.
2. It persists/returns a report with `degraded = True` and a list of `degradation_reasons` (e.g. `["empty_dataset"]`, `["upstream_timeout"]`, `["synthesis_failed"]`).
3. The generated content includes a helpful notice and actionable retry advice instead of blank or corrupted text.

### AC-5 — Frontend Citation Linkage & Narrative Viewer
**Given** the report view in `nowing_web`,  
**When** a user reads a narrative report (Digest, Trend, or Timeline):
1. Citation tags (e.g. `[1]`, `[source-1]`) are clickable, opening the source drawer or direct article link.
2. For Timeline reports, events are presented chronologically with clean date/category badges.
3. Degraded reports display a non-blocking warning banner with a "Retry Generation" action.

### AC-6 — Test Coverage
**Given** the narrative report engine and routes,  
**When** test suites execute,  
**Then**:
- Unit tests cover template catalog, parameter validation, prompt building, citation extraction, and degradation fallback logic.
- Integration tests cover `GET /reports/narrative/templates` and `POST /reports/narrative` lifecycle with mocked LLM and data providers.
- All tests pass with 100% ruff clean.

---

## Tasks / Subtasks

- [x] Backend Narrative Report Architecture (`app/reports/narrative/`)
  - [x] Define schemas and models: `NarrativeTemplate`, `NarrativeReportCreate`, `SourceCitation`, `NarrativeReportMetadata` in `app/reports/narrative/models.py`.
  - [x] Implement `NarrativeTemplateRegistry` with `news_digest`, `financial_trend`, `company_timeline` templates.
  - [x] Implement `NarrativeSynthesisEngine` (`app/reports/narrative/engine.py`): data fetching, prompt assembly, LiteLLM generation, citation extraction, degradation handling.
- [x] Backend API Routes & Integration (`app/routes/narrative_reports_routes.py`)
  - [x] Add `GET /workspaces/{workspace_id}/reports/narrative/templates` route.
  - [x] Add `POST /workspaces/{workspace_id}/reports/narrative` on-demand generation route.
  - [x] Mount route in `app/app/factory.py` with RBAC checks (`REPORTS_READ`, `REPORTS_CREATE`).
- [x] Frontend Contracts & UI Integration
  - [x] Add TypeScript types to `contracts/types/reports.types.ts`.
  - [x] Add service methods in `lib/apis/reports-api.service.ts`.
  - [x] Add Narrative Generator modal / drawer in `nowing_web`.
- [x] Verification & Tests
  - [x] Write unit tests in `nowing_backend/tests/unit/reports/test_narrative_engine.py`.
  - [x] Write integration test in `nowing_backend/tests/integration/reports/test_narrative_routes.py`.
  - [x] Run `ruff check` and pytest suite.

---

## Suggested Review Order

**Narrative Synthesis Engine & Data Models**

- Defines template definitions, parameters schema, citations, and metadata
  [`models.py:11`](../../../nowing_backend/app/reports/narrative/models.py#L11)

- Template registry with canonical news digest, financial trend, and corporate timeline templates
  [`registry.py:14`](../../../nowing_backend/app/reports/narrative/registry.py#L14)

- Synthesis engine with data ingress, prompt assembly, and graceful degradation contract
  [`engine.py:42`](../../../nowing_backend/app/reports/narrative/engine.py#L42)

**API Routes & RBAC**

- Template catalog and on-demand report generation REST endpoints
  [`narrative_reports_routes.py:27`](../../../nowing_backend/app/routes/narrative_reports_routes.py#L27)

**Frontend Modal & Contracts**

- TypeScript contracts for narrative templates and generation payloads
  [`reports.types.ts:32`](../../../nowing_web/contracts/types/reports.types.ts#L32)

- Interactive modal component for synthesizing grounded narrative reports
  [`NarrativeReportModal.tsx:42`](../../../nowing_web/components/reports/NarrativeReportModal.tsx#L42)

**Test Suites**

- Unit tests for template registry, markdown synthesis, citation extraction, and degradation
  [`test_narrative_engine.py:10`](../../../nowing_backend/tests/unit/reports/test_narrative_engine.py#L10)

- Integration tests for templates catalog and on-demand report lifecycle
  [`test_narrative_routes.py:84`](../../../nowing_backend/tests/integration/reports/test_narrative_routes.py#L84)

