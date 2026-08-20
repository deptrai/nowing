# PRD Amendment — Implementation Readiness Closeout

**PRD:** `prd-Nowing-2026-07-22/prd.md`  
**Amendment date:** 2026-08-20  
**Author:** Devin / BMAD `bmad-check-implementation-readiness`  
**Status:** Ratified

## 1. FR-48 — Removed from Nowing scope

`FR-48: Canonical Entity Storage & Multi-Domain Indexing (Epic 13)` đã được gỡ bỏ khỏi PRD canonical của Nowing. Lý do: Nowing không còn giữ canonical entity index; `chainlens-research` đảm nhận deduplication, embedding, full-text/vector search, merge history. Nowing scraper/aggregator chỉ output `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`.

**Decision:** DROPPED from Nowing PRD. Không cần coverage trong `epics.md`.

## 2. FR-50, FR-51, FR-52 — Re-scoped to feed chainlens-research

- `FR-50: Financial Data Integration (Epic 15)`
- `FR-51: Company Data Integration (Epic 16)`
- `FR-52: E-commerce Intelligence (Epic 17)`

Đều đã được re-scope từ "local Nowing index" sang "scraper data feed to `chainlens-research`". Các capability tương ứng vẫn có thể tồn tại trên Nowing (E15/E16/E17) nhưng chỉ để scrape, chuẩn hóa, redact PII và gửi `Chunk[]`; phần index/search thuộc `chainlens-research`.

**Decision:** RE-SCOPED. Coverage trong `epics.md` được thể hiện qua:
- `FR-58: Scraper Feed to chainlens-research`
- `FR-62: Canonical Chunk Metadata Schema`
- `Story 20.1: Nowing Scraper to_chunks() + NowingIngestService`
- Các story 15.1, 15.2, 16.1, 16.2, 17.1, 17.2 trong `epics.md` (đã nằm trong Epic 15–17 hoặc được gộp vào 6.11/6.12).

Không yêu cầu thêm story mới cho E15/E16/E17 trong `epics.md` vì scope đã thu hẹp về feed-only.

## 3. FR-70 – FR-92 — Out-of-PRD implementation backlog

Các FR từ `FR-70` đến `FR-92` không xuất hiện trong `prd-Nowing-2026-07-22/prd.md`. Chúng là implementation backlog / market-specific elaboration được giữ lại trong `epics.md` (Epic 21 mở rộng, Epic 22, Epic 23).

**Decision:** Giữ nguyên trạng thái `out-of-prd` trong `epics.md`. Không đưa vào PRD canonical trừ khi có PRD amendment riêng. Tiếp tục track bằng ghi chú `out-of-prd` ở dòng 83 của `epics.md`.

## 4. Forward dependencies — Resolution

### 4.1 Story 2.10 → Story 3.15

`Story 2.10: Exa MCP Search Connector` hoàn thành trước `Story 3.15: Run Citations as Verifiable Sources` và dùng `WEB_RESULT` citation contract dự kiến của 3.15.

**Decision:** SHARED CONTEXT / SOFT DEPENDENCY. `2.10` dùng provisional contract; khi `3.15` merge, team E2 regression-test `2.10` với final contract. Đã có dependency note trong `epics.md` (Story 2.10) và trong SCP 2026-08-08.

### 4.2 Story 9.5 → Story 9.6

`Story 9.5: Metered Deep-Research Endpoint cho Self-Host` tham chiếu `Memory Provenance` (Story 9.6). Tuy nhiên, `9.5` đang ở trạng thái `POST-MVP — deferred` và yêu cầu một SCP mới trước khi dev.

**Decision:** HARD DEPENDENCY nhưng DEFERRED. `9.5` không được phép chuyển `ready-for-dev` cho tới khi: (a) `9.6` hoàn thành provenance recipe, (b) có self-host demand evidence, (c) SCP về pricing model được phê duyệt. Đã thêm dependency note vào forward dependency table trong `epics.md`.

### 4.3 Story 20.1 → Story 20.4

`Story 20.1: Nowing Scraper to_chunks() + NowingIngestService` cần `ChainLensServiceAuth` + cost ledger sync từ `Story 20.4`.

**Decision:** PREREQUISITE — ALREADY SATISFIED. `20.4` đã `done` theo `sprint-status.yaml`. `20.1` ghi rõ "Auth qua `ChainLensServiceAuth` (`Story 20.4`)" và forward dependency table đã có mục này. Không còn blocker.

## 5. Overall readiness after closeout

Sau amendment này:
- PRD canonical (FR-1..FR-69) có coverage đầy đủ trong `epics.md`, trừ các FR đã bị loại bỏ/re-scope sang `chainlens-research`.
- FR-70–FR-92 được công nhận là out-of-PRD implementation backlog.
- Forward dependencies đã được phân loại (soft/hard/prerequisite) và ghi rõ.
- Không còn missing coverage nào cản trở Phase 4 implementation.

**Overall status:** `READY WITH CONDITIONS` — điều kiện còn lại là ratify amendment này và đảm bảo UX contract `epic21-lead-intelligence-ux.md` được review trước khi dev lead-gen UI.
