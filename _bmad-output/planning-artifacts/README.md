# Nowing — Planning Artifacts

**Last updated:** 2026-08-11

Thư mục này chứa toàn bộ artifact lập kế hoạch sản phẩm của Nowing: PRD, epics, architecture spine, UX contracts, sprint-change proposals, và implementation readiness reports.

## Sơ đồ artifact

```
planning-artifacts/
├── prds/prd-Nowing-2026-07-22/prd.md          # Product Requirements Document (canonical)
├── epics.md                                     # Epic & story catalog (canonical)
├── sprint-change-proposal-*                     # Strategic change proposals (ADOPTED)
├── architecture/
│   ├── architecture-Nowing-2026-07-22/
│   │   ├── ARCHITECTURE-SPINE.md               # Architecture decisions (canonical, 45 ADs)
│   │   ├── architecture-validation-report-*.md # Lint + review reports
│   │   └── reviews/                             # Reality-check / adversarial reviews
│   └── epic21-architecture-update.md           # Pre-merge source (superseded)
├── ux-design/                                   # Epic-level UX docs
├── ux-designs/ux-Nowing-2026-07-22/            # Canonical UX contracts
└── implementation-readiness-report-*.md        # Cross-artifact readiness assessments
```

## Trạng thái nhanh (2026-08-11)

| Layer | Artifact | Status |
|---|---|---|
| Product | `prd.md` | Active — last updated 2026-08-11 |
| Epics | `epics.md` | Active — Epic 21 stories reflect resolved ADs |
| Architecture | `ARCHITECTURE-SPINE.md` | **FIT for implementation** (`bmad-architecture` PASS) |
| UX | `ux-designs/ux-Nowing-2026-07-22/*.md` | Contracted — all 8 Epic 21 patterns |
| Readiness | `implementation-readiness-report-2026-08-11.md` | Step 9 completed — architecture validated |
| Sprint | `../implementation-artifacts/sprint-status.yaml` | Epic 21 in `backlog`, awaiting governance gates |

## Các AD mới / sửa đổi quan trọng

- **AD-8 / AD-10 / AD-42** — `BillingEvent` là ledger cho business events không phải LLM; `TokenUsage` chỉ cho token consumption.
- **AD-31** — `client_id` tenancy trên tất cả bảng Epic 21 (và `Memory`, `Run`, `TokenUsage`, `ResearchThread`, `BillingEvent`).
- **AD-33** — `AlertRule.capability_id`, `notification_channels` gồm `in_app`, `telegram`, `email`; signal-driven enrollment dùng `target_sequence_id` / `target_step_id` (FK thật).
- **AD-44 / AD-45 / AD-47** — `Capability.name` là canonical id + `CapabilityRegistry.query_metadata`; `client_id` là CITEXT natural key; `Memory.source_uuid` + `source_entity_type` là authoritative provenance.
- **AD-36–AD-42** — Lead intelligence architecture (enrichment, signals, scoring, sequencer, CRM, Zalo/LinkedIn deferred, outcome pricing).
- **AD-39** — `Sequence` là bounded context mới, không phải `Automation` subtype.
- **AD-22 / AD-23** — VietnamWorks / TopCV / ITviec scrapers: `ADOPTED` sau khi 300 unit tests pass.

## Cổng còn mở trước khi Epic 21 vào dev

1. Email outreach legal/ToS.
2. Contact-enrichment vendor POC (Cleanlist / BetterContact).
3. PII/consent pipeline tách HR redaction vs lead enrichment.
4. CRM sync scope (read-first → write-back).
5. Outcome-pricing display / per-lead projected cost estimator.
6. TopCV anti-bot POC (Epic 12 hard gate).

## Cách sử dụng

- **PO / BA:** bắt đầu từ `prd.md` → `epics.md`.
- **Engineering:** `ARCHITECTURE-SPINE.md` là source of truth; `ux-designs/ux-Nowing-2026-07-22/` chứa UI contracts.
- ** sprint planning:** dùng `../implementation-artifacts/sprint-status.yaml`.
- **Validation / readiness:** dùng `implementation-readiness-report-2026-08-11.md` và `architecture-validation-report-2026-08-11.md`.

## Liên kết ngoài

- [Sprint status](../implementation-artifacts/sprint-status.yaml)
- [Sprint status summary](../implementation-artifacts/sprint-status-summary-2026-08-11.md)
- [Implementation artifacts](../implementation-artifacts/)
