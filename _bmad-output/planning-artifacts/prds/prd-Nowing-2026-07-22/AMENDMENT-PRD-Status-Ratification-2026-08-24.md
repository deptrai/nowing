# PRD Status Ratification Amendment — 2026-08-24

**PRD:** `prd-Nowing-2026-07-22/prd.md`  
**Amendment date:** 2026-08-24  
**Author:** bmad-prd skill  
**Status:** Superseded (2026-08-25) — the 2026-08-25 pass updated FR-43–47 and FR-93/94; this amendment is retained as history for FR-49–52, FR-56–62, and FR-63–69.  

## 1. Change summary

This amendment ratifies the status of a set of Functional Requirements (FRs) in `prd-Nowing-2026-07-22/prd.md` so that they reflect the current reality of `epics.md`, `sprint-status.yaml`, and the `implementation-readiness-report-2026-08-24.md` (Sections 2–3). No FR numbering or structure was changed; only status tags and short explanatory notes were updated.

## 2. Status ratification log

| FR | Old status | New status | Rationale / source |
|---|---|---|---|
| FR-93 | `[BACKLOG]` | `[READY-FOR-DEV]` | In-PRD per `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`; covered by Epic 27 / Story 27.1 (review), 27.1a (done), 27.2a/27.2b (ready-for-dev). |
| FR-94 | `[BACKLOG]` | `[READY-FOR-DEV]` | In-PRD per Epic 27 Amendment; covered by Epic 27 / Stories 27.2a/27.2b (ready-for-dev); Story 27.1 (review). |
| FR-43 | `[PROPOSED]` | `[READY-FOR-DEV]` | Epic 12 / Story 12.1; ToS/legal review approved 2026-08-08; VietnamWorks public-API spike passed (no CAPTCHA). |
| FR-44 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 12 / Story 12.2; Cloudflare/anti-bot POC remains a hard gate before production merge. |
| FR-45 | `[PROPOSED]` | `[READY-FOR-DEV]` | Epic 12 / Story 12.3; HTML server-rendered parsing spike passed (no Cloudflare); rate-limit + user-agent rotation required. |
| FR-46 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 12 / Stories 12.4a–e; aggregator depends on FR-43–45, canonical `Chunk[]` schema (FR-62, AD-34), and `NowingIngestService` (Epic 20 done); PII redaction (FR-47) runs before ingest. |
| FR-47 | `[PROPOSED]` | `[READY-FOR-DEV]` | Epic 12 / Story 12.5; shared PII redaction pipeline for job descriptions/requirements; runs before any `Chunk[]` ingest or `Memory` storage. |
| FR-49 | `[PROPOSED] — re-scoped …` | `[RE-SCOPED]` | Feed/crawl infrastructure in Nowing is done (Epic 14: Stories 14.1, 14.2a done; 14.2b blocked by `chainlens-research` entity-search contract). Nowing does not keep a local news index. |
| FR-50 | `[PROPOSED] — re-scoped …` | `[RE-SCOPED]` | Feed/crawl infrastructure in Nowing is done (Epic 15: Stories 15.1, 15.1b, 15.2 done). No local financial index. |
| FR-51 | `[PROPOSED] — re-scoped …` | `[RE-SCOPED]` | Feed/crawl infrastructure partially done (Epic 16: Story 16.1 masothue and 16.5 public procurement done; 16.2 official business registry delegated to XActions). No local company index. |
| FR-52 | `[PROPOSED] — re-scoped …` | `[RE-SCOPED]` | Feed/crawl infrastructure partially done (Epic 17: Story 17.2 Shopee done; 17.1 Lazada and 17.5 TikTok Shop blocked-by-external XActions). No local product index. |
| FR-54 | `[DEFERRED]` | `[REMOVED]` | ChainLens-only; no Nowing epic (Epic 19 dropped). Google Search/Maps web search is handled by `chainlens-research` generic crawl and Exa MCP (FR-8.1). |
| FR-56 | `[PROPOSED]` | `[DONE]` | Epic 18 / Story 18.1; public agent-chat endpoints and PAT auth implemented. |
| FR-57 | `[PROPOSED]` | `[DONE]` | Epic 18 / Story 18.3; `agent_configs` table and `bdsai-listing-assistant` seed implemented. |
| FR-58 | `[PROPOSED]` | `[DONE]` | Epic 20 / Story 20.1; `NowingIngestService` and scraper `to_chunks()` feed `chainlens-research` via `POST /v1/ingest/scraper`. |
| FR-59 | `[PROPOSED]` | `[DONE]` | Epic 20 / Story 20.2; gap-fill caller and cost allocation wired on the Nowing side. |
| FR-60 | `[PROPOSED]` | `[DONE]` | Epic 20 / Story 20.3; `NowingPrivateProvider` and `POST /v1/private-data/search` implemented. |
| FR-61 | `[PROPOSED]` | `[DONE]` | Epic 20 / Story 20.4; service-to-service auth and cost ledger sync between Nowing and `chainlens-research` implemented. |
| FR-62 | `[PROPOSED]` | `[DONE]` | Epic 20 / Story 20.1; canonical `Chunk.metadata` schema and `source` enum shared with `chainlens-research` implemented. |
| FR-63 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.1 done; Epic 21 overall in-progress. |
| FR-64 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.2 done; Epic 21 overall in-progress. |
| FR-65 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.3 done; 3-tier phone waterfall and PII vault in place. Epic 21 overall in-progress. |
| FR-66 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.4 done; outbound sequence engine and split-view panel implemented. Epic 21 overall in-progress. |
| FR-67 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.5 done; Lark Base / Google Sheets / HubSpot/Salesforce/Pipedrive sync and read-first dedup implemented. Epic 21 overall in-progress. |
| FR-68 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.6 done; Zalo OA deep-link, ZNS templates, and Telegram alerts implemented. Epic 21 overall in-progress. |
| FR-69 | `[PROPOSED]` | `[IN-PROGRESS]` | Epic 21 / Story 21.7 done; $0 chat/sequencer + pay-as-you-go credit ledger for verified leads and booked meetings implemented. Depends on FR-66 (outbound automation). Epic 21 overall in-progress. |
| FR-5  | `(REMOVED)` in heading | `[REMOVED]` | AI File Sorting already removed in migration 172; heading normalized to `[REMOVED]`. Body kept as historical context. |
| FR-10 | heading had no status tag | (no change) | Body already ratifies only Owner/Editor/Viewer and notes Admin role was removed by migration 72. Status is effectively `[REMOVED]`. |
| FR-48 | `[REMOVED 2026-08-08 …]` | (no change) | Already correctly states canonical entity storage moved to `chainlens-research` and Epic 13 is dropped. |

## 3. Sources

- `implementation-readiness-report-2026-08-24.md` Sections 2–3
- `epics.md` (Epic 12, 14–21, 27)
- `sprint-status.yaml` (last updated 2026-08-24)
- `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`

## 4. Decision workspace

A `bmad-prd` working memlog is kept at:
`_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/.bmad-prd-update-2026-08-24/.memlog.md`.
