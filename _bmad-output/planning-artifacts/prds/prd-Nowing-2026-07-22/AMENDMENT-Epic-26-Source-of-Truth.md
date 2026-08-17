# PRD Amendment — Epic 26 Source of Truth (2026-08-17)

## Decision

Thay vì cập nhật toàn bộ `prd-Nowing-2026-07-22/prd.md` (đã lỗi thời so với epics mới), **PRD vẫn là source-of-truth cho product vision và các FR gốc**, còn **architecture spine `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` là source-of-truth cho Epic 26** cùng các FR-70–FR-92 và NFR-9/NFR-11 được sinh sau PRD.

## Scope

Amendment này áp dụng cho:
- Epic 26: Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure
- Các FR không có trong PRD gốc: FR-58–FR-92, FR-24 re-bind sang Epic 9, FR-37/FR-38/FR-39/NFR-9.

## Mapping mới

| Original PRD | New Source of Truth | Rationale |
| --- | --- | --- |
| FR-24 (ChainLens in Epic 2 Connectors) | `architecture-unified-...` AD-15 / Epic 9 | ChainLens = engine, không phải connector |
| FR-37 (Deep-research cost metering) | `architecture-unified-...` AD-8 / Story 9.2 | Parse `costDollars` thật, không flat rate |
| FR-38 (Research degradation) | `architecture-unified-...` AD-15 / Story 9.1a | Degrade sang Nowing hybrid search |
| FR-39 (Memory→scraper-run provenance) | `architecture-unified-...` AD-11.1 / Story 9.6 | `Memory` tự chứa recipe |
| NFR-9 (Deep-research latency budget) | `architecture-unified-...` NFR-9 / Story 9.3 | State A async, State B sync gated |
| FR-84–FR-92 (lead infrastructure / DNC / RLS / partitioning / async worker / Telegram / Zalo) | `architecture-unified-...` AD-101–AD-110 / Epic 26 | New FRs after PRD freeze |

## Acceptance

- Epic 26 implementation MUST follow `ARCHITECTURE-SPINE.md` (final) and Story `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md` (ready-for-dev).
- `ARCHITECTURE-SPINE.md` decisions override any conflicting statements in PRD §4.2 / §4.9 for the Epic 26 scope.
- This amendment does NOT invalidate other PRD sections; it only clarifies source-of-truth for the post-PRD scope.

## References

- `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`
- `epic-26-architecture-review-2026-08-17-v5.md`
- `implementation-readiness-report-2026-08-17.md`
