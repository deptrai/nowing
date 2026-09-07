# Epic 26 Context: Autonomous Lead Missions & Deep Sales Research

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Hệ thống Nowing tự động hóa toàn bộ vòng đời tìm kiếm, sàng lọc, chấm điểm và tiếp cận khách hàng tiềm năng tại thị trường Việt Nam. Epic 26 cung cấp nền tảng "Autonomous Lead Missions" giúp sales rep đặt mục tiêu ICP (ngành, địa bàn, ý định), hệ thống tự động lập kế hoạch, chọn nguồn dữ liệu tối ưu, chạy thử (smoke test), triển khai chạy đầy đủ, và theo dõi hiệu quả chi phí trong thời gian thực — tất cả trước khi tiêu tốn credit thật.

## Stories

- Story 26.1: FastMCP Ingest Gateway, Batch Ingestion & Stateless ChainLens Pipeline
- Story 26.2: dsh-worker Sidecar Container, Redis Streams & Task Resumption
- Story 26.3: Multi-Tier Hybrid LLM Router
- Story 26.4: PII Vault AES-256 Encryption, HMAC Deduplication & Decree 13/2020 Compliance
- Story 26.5: Split-Canvas, Glass-Box Mission Control & Two-Tier Phone Unlock
- Story 26.6: Telegram Interactive Checkpoint Bot & 1-Click Auto-Refund Dialogue
- Story 26.7: Hermetic Quality Gates, Benchmark Suite & Anti-Zombie Chaos Tests
- Story 26.10: Mission Control Glass-Box UX Refinement
- Story 26.11: Two-Tier Phone Unlock UX Refinement
- Story 26.25: Customer Location Profile Selector with Progressive Disclosure
- Story 26.26: Location-Aware Adapter Routing & Coverage Quality
- Story 26.27: Pre-Flight Lead Plan Summary & PlanSummaryCard
- Story 26.28: Source Coverage Badge in Right-Canvas
- Story 26.29: Smoke Test Feedback Loop for Location Refinement

## Requirements & Constraints

- **FR-69.2–69.6:** Location-aware lead targeting, pre-flight plan summary, source coverage badges, and smoke test feedback loop are first-class UX requirements.
- **FR-85:** Unified multi-source AI lead generation orchestrator must route across all registered adapters and respect location/profile constraints.
- **FR-86:** Origami Split-Canvas UX requires persistent Right-Canvas mirrors for key workflows (Mission Control, Source Status, Plan Summary).
- **NFR-1:** API response times for pre-flight read-only planning must remain under 200ms.
- **AD-31/AD-42:** Adapter metadata includes `supported_provinces` and `coverage_quality_by_location`; orchestrator ranks candidates with composite score.
- **AD-103:** Hybrid LLM Router with free-tier Gemini Flash / local vLLM priority and graceful cloud fallback.
- **AD-105:** PII (phones) encrypted at rest, deduplicated by HMAC, masked by default.
- **AD-107:** Hermetic testability with Golden Streaming Cassettes and in-memory fakes; unit tests must not depend on live external scrapers.
- **AD-110:** PII opt-out, anti-fraud refund cap 15%, Two-Tier phone unlock UX.

## Technical Decisions

- **Location modeling:** Vietnamese GSO/TCTK province/district/ward codes; progressive disclosure in UI; `LocationProfile` embedded in `CampaignSpec` and `ICPCriteria`.
- **Coverage scoring:** Composite formula `location_coverage_score * 0.4 + vertical_relevance * 0.4 + cost_efficiency * 0.2`; quality tiers mapped to `high/medium/low/none` badges.
- **Pre-flight plan:** `LeadGenPlanner.plan_from_campaign` remains a tuple-returning method for existing callers; enriched pre-flight plan uses a dedicated `create_preflight_plan` path returning `CampaignPlanResponse`.
- **State management:** Wizard state stored in `useCampaignBuilder`; Right-Canvas state synchronized through Jotai atoms (`threadCanvasModeMapAtom`, `activePlanSpecAtom`).
- **Cost model:** Base lead 1,500 VND, verified unlock 5,000 VND; displayed and billed in credit micros (1 VND = 40 micros).
- **Right-Canvas pattern:** A new `CanvasMode` (e.g. `"plan"`) can be added without breaking existing modes; it re-uses the existing `DynamicRightPanelCanvas` switch.

## UX & Interaction Patterns

- Origami Split-View: cột trái chat/prompt, cột phải là Right-Canvas context-aware (Lead Matrix, Research, Scraper Health, Plan Summary).
- Campaign Builder Wizard: 3 steps — ICP Builder (Step 1), Sources & Budget (Step 2), Launch & Schedule (Step 3), với `PlanSummaryCard` hiển thị tóm tắt trước khi launch.
- Quickstart Playbook Builder: 5-step mini-wizard (Preset → Intent → Location → Product → Channels → Plan Summary), sử dụng `LocationSelector` ở Step 2 và `PlanSummaryCard` ở Step 5.
- Coverage badge color code: High (emerald), Medium (sky), Low (amber), None (rose).
- Smoke test: 5 leads, no persistence, returns real preview; CTA chuyển sang "Chạy đầy đủ" / "Chỉnh sửa kế hoạch".

## Cross-Story Dependencies

- Story 26.27 depends on Story 26.25 (`LocationProfile`, `LocationSelector`) and Story 26.26 (`coverage_quality_by_location`, composite routing).
- Story 26.28 (Right-Canvas Source Coverage) shares the Right-Canvas mode infrastructure với Story 26.27.
- Story 26.29 (Smoke Test Feedback Loop) mở rộng hành vi Smoke Test trong `PlanSummaryCard`.
