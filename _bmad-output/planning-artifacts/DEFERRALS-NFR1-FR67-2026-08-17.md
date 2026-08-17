# Deferral Decision — NFR-1 / FR-67 (2026-08-17)

## Context

NFR-1 Performance và FR-67 CRM Integration & Write-Back được flagged trong `implementation-readiness-report-2026-08-17.md` là rủi ro product-level, nhưng **không chặn Epic 26**.

## Decision

| Item | Decision | Reasoning |
| --- | --- | --- |
| **NFR-1 Performance** | **DEFERRED** | Bounds mơ hồ. Phần NFR-1b/1c/1d đã có E3.14. Performance cơ sở (CRUD/scraper) là nền tảng, không cần story riêng. Cần số đo thật trước khi cắt bound. |
| **FR-67 CRM Integration & Write-Back** | **DEFERRED** | Thuộc Epic 21 (Lead Gen Intelligence), phụ thuộc Phase 1/2/3 theo AD-40. Không liên quan Epic 26. Cần HubSpot/Salesforce/Pipedrive/Lark Base/Google Sheets connectors. |

## Conditions to re-open

- **NFR-1:** Khi có load test / latency benchmark thực tế cho batch ingestion 100 leads (< 200ms) và ChainLens chunk ingestion p95.
- **FR-67:** Khi Epic 21 lead scoring + outreach automation ship và có requirement CRM write-back rõ ràng.

## References

- `implementation-readiness-report-2026-08-17.md` §Step 3 / §Final Assessment
- `epics.md` FR-67 mapping
- `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` NFR-9 (Deep-Research Latency) — NFR-1 liên quan nhưng scoped riêng.
