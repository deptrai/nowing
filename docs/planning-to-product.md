# Nowing — Từ kế hoạch đến sản phẩm cuối cùng

**Ngày cập nhật:** 2026-08-11  
**Nguồn:** `epics.md`, `ARCHITECTURE-SPINE.md`, `sprint-status.yaml`, các `implementation-readiness-report` mới nhất.

Tài liệu này tổng hợp trạng thái lập kế hoạch, triển khai và các cổng còn mở để đưa Nowing từ trạng thái hiện tại đến sản phẩm cuối cùng.

## Tầm nhìn sản phẩm

Nowing là **open-core research memory** cho agents và teams. Khác với các công cụ ghi chú hay chatbot thông thường, Nowing **nhớ những gì nó đi tìm trên web thực** (live web), không chỉ những gì người dùng nhập. Sản phẩm cuối cùng cần đạt được:

- **Self-host miễn phí** với toàn bộ lõi Apache-2.0.
- **Cloud pay-as-you-go** cho deep-research engine và hosted connectors.
- **Multi-surface** (web, desktop, extension, Obsidian, MCP, evals).
- **Agentic workflow hoàn chỉnh**: research → memory → chat → deliverables → automations → write-back.
- **Vertical market fit**: bắt đầu từ HR/Recruitment Việt Nam, mở rộng sang Lead Intelligence.

## Roadmap epic hiện tại

```
E1–E9: Nền tảng cốt lõi      ───────────────────────────── DONE
E10:  Mở rộng scraper BĐS  ───────────────────────────── DONE
E11:  Telegram automation  ───────────────────────────── DONE
E18:  Public/Vertical chat ───────────────────────────── DONE
E12:  HR/Recruitment VN    ─────────────── in-progress (pilot)
E14–E16: VN data verticals ─────────────── in-progress
E17:  E-commerce VN        ─────────────── backlog (P2, Phase 2)
E20:  ChainLens ecosystem  ─────────────── in-progress
E21:  Lead Intelligence    ─────────────── backlog (gated, architecture FIT)
```

## Trạng thái sprint (theo `sprint-status.yaml`)

| Nhóm epic | Trạng thái | Ghi chú |
|---|---|---|
| E1–E9 (core) | ✅ done | Brownfield + các story P0 đã hoàn thành |
| E10, E11 | ✅ done | BĐS aggregator, Telegram bot |
| E12 | 🔄 in-progress | VietnamWorks, TopCV, ITviec, aggregate, PII |
| E14–E16 | 🔄 in-progress | News, finance, company directory VN |
| E18 | 🔄 in-progress | Public agent-chat, AgentConfig, client tenancy |
| E20 | 🔄 in-progress | Ingest, gap-fill, private provider, cost sync |
| E21 | ⏸️ backlog | `bmad-architecture` PASS with implementation conditions; governance/legal gates chưa đóng |
| Tech Debt | 🔄 in-progress | 7 deferred issues cần story |

### Các story đang in-progress (2026-08-11)

- **E3.17** — (memory recall bounded retrieval, continuation)
- **E9.6c** — (provenance re-validation extension)
- **E12.3, E12.4, E12.5** — (TopCV/ITviec aggregate, PII redaction)
- **E12.9** — Saved Searches (ready-for-dev, P0)
- **E20.1, E20.2, E20.3, E20.4** — ChainLens integration

## Architecture Decisions (AD) đang chi phối tiến độ

### AD đã chốt và đang thực thi

| AD | Nội dung | Tác động |
|---|---|---|
| AD-15 | ChainLens là external deep-research dependency | Tách FR-24 khỏi Epic 2, cost thật qua `done.usage.costDollars` |
| AD-17 | Deep research dùng async door sẵn có | Giảm phạm vi 9.3; vẫn cần Redis bus + async agent door |
| AD-18 | Memory injection có bounded retrieval | Block mọi lượt chat full-scan memory; dùng HNSW/GIN |
| AD-19 / AD-20 | Anti-bot/CAPTTCHA thuộc Nowing; screenshot-as-evidence | Giữ nguyên stack Python, không dựng visual-RAG |
| AD-27 / AD-28 (re-scoped) | Scraper output feeds `chainlens-research` | Nowing không giữ canonical index |
| AD-29 / AD-30 / AD-31 | Public agent-chat, AgentConfig, `client_id` tenancy | Epic 18 foundation |
| AD-32 | Connector management page là canonical | Deprecate modal theo 3 phase |
| AD-33 | Generic Alert Engine dùng Automation runtime | 8 domain-alert stories dùng chung một scheduler/diff/notif |

### AD mới cho Epic 21 (chưa dev)

| AD | Nội dung | Trạng thái |
|---|---|---|
| AD-36 | Waterfall enrichment qua API (Cleanlist/BetterContact) | Adopted, chờ vendor validation |
| AD-37 | Signal detection framework (hybrid build + buy) | Adopted |
| AD-38 | Lead scoring composite fit + intent | Adopted |
| AD-39 | Sequencer email-first, multi-source lead ingestion | Revised 2026-08-11 |
| AD-40 | CRM integration bidirectional, read-first | Adopted |
| AD-41 | Zalo/LinkedIn channels deferred khỏi MVP | Deferred |
| AD-42 | Outcome-based pricing support (`BillingEvent` ledger) | Adopted |

## Cổng mở (gating path to product)

### Cổng kỹ thuật

1. **Memory production deploy (E3.10 / E3.14)**
   - Prod đang ở alembic 174; migrations 175–179 chưa deploy.
   - Thứ tự: `mig177 → backfill → mig178`.
   - Block: xác nhận data-loss recovery (E3.10) và performance gate (E3.14).

2. **Deep-research async scale-out (E9.3)**
   - `run_event_bus` single-process; cần Redis pub/sub cho multi-replica.
   - Agent door đang sync; cần submit-and-return.
   - Kết quả research cần thành deliverable + notification.

3. **ChainLens integration (E20)**
   - 4 story in-progress: `NowingIngestService`, gap-fill caller, `NowingPrivateProvider`, cost ledger sync.
   - Cần ChainLens service auth/cost contract.

4. **NFR-1 Performance**
   - Được đánh `PARTIAL`, chưa gán epic.
   - Cần benchmark chính thức và owner.

### Cổng pháp lý / chiến lược

1. **Public repo attribution (AD-16.1)**
   - Codebase kế thừa từ SurfSense với 81% byte-identical files.
   - Cần luật sư xác nhận Apache-2.0 §4 attribution và quyền đặt Nowing làm BSL Licensor.

2. **Epic 12 legal/ToS**
   - Legal counsel approved all 3 sources (VietnamWorks, TopCV, ITviec) 2026-08-08.
   - VietnamWorks code verified and AD-22 ADOPTED; TopCV code verified and AD-23 ADOPTED; TopCV anti-bot POC remains a hard gate before merge.
   - PII redaction pipeline (AD-25) phải chạy trước khi job data vào memory.

3. **Epic 21 governance gates**
   - Email outreach legal/ToS.
   - Vendor contract POC (Cleanlist/BetterContact).
   - Zalo OA business verification (deferred).
   - PII/consent pipeline tách HR redaction vs lead enrichment.
   - CRM sync scope (read-first → write-back).

4. **Story 9.5 (metered self-host endpoint)**
   - Đang deferred chờ SCP approval.

## Đường đến sản phẩm cuối cùng

### Phase 1 — Production-ready core (ngắn hạn)

1. Deploy memory migrations 175–179 lên production theo đúng thứ tự.
2. Hoàn thành E3.14 (bounded memory injection) và E8.7/8.8 (auto-extract spend cap + kill-switch).
3. Đóng E9.3: Redis bus, async agent door, notification/deliverable persistence.
4. Hoàn thành E18 (public/vertical chat) — PAT scope + composite RLS test plan đã pass.

### Phase 2 — Vertical pilot (trung hạn)

1. Hoàn thành E12.3/12.4/12.5/12.9 cho HR Việt Nam pilot.
2. Hoàn thành E20 integration với `chainlens-research` (ingest, gap-fill, private provider, cost sync).
3. Chạy pilot 20–50 workspace Việt Nam, thu metrics.

### Phase 3 — Scale & monetization (dài hạn)

1. Đóng governance gates của Epic 21 (Lead Intelligence).
2. Xây AD-31/AD-33/AD-36 → AD-42: vertical `client_id`, generic alert engine, waterfall enrichment, signal detection, lead scoring, sequencer, CRM sync, outcome pricing.
3. Mở rộng E14–E16 (news, finance, company VN) và chuẩn bị E17 (e-commerce VN) cho Phase 2.
4. Resolve tech debt td-1→td-7 và NFR-1.
5. Public repo sau khi luật sư xử lý attribution.

## Tài liệu liên quan

- [`epics.md`](../_bmad-output/planning-artifacts/epics.md) — toàn bộ epic/story.
- [`ARCHITECTURE-SPINE.md`](../_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md) — 45 ADs.
- [`sprint-status.yaml`](../_bmad-output/implementation-artifacts/sprint-status.yaml) — nguồn chân lý tiến độ.
- [`implementation-readiness-report-2026-08-11.md`](../_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-11.md) — readiness mới nhất.
