# Epic 20 Context: Nowing Ecosystem Integration

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Tích hợp Nowing với hệ sinh thái `chainlens-research` (research engine bên ngoài) thành một hệ sinh thái liền mạch: dữ liệu scraper của Nowing được đưa vào index tập trung của ChainLens qua `POST /v1/ingest/scraper` (Nowing không giữ corpus public/vertical riêng), agent có thể yêu cầu gap-fill dữ liệu thiếu on-demand, dữ liệu private của user được tìm kiếm tại chỗ mà không rời Nowing, và toàn bộ usage được meter/bill về ledger Nowing. Phần mở rộng 2026-09-20 bổ sung trọn bộ capability suite của ChainLens (contents, code_search, wide_research, OpenAI gateway, webhook monitors, async jobs, Pulse feed + angle research) để Nowing dùng được ~100% năng lực của engine thay vì chỉ search cơ bản.

## Stories

- Story 20.1: Nowing Scraper `to_chunks()` + `NowingIngestService` (`POST /v1/ingest/scraper`)
- Story 20.2: Gap-Fill Caller + Cost Allocation
- Story 20.3: `NowingPrivateProvider` for `POST /v1/private-data/search`
- Story 20.4: Service-to-Service Auth (`ChainLensServiceAuth`) + Cost Ledger Sync
- Story 20.5: `chainlens.contents` URL Extraction Capability
- Story 20.6: `chainlens.code_search` Code Search Capability
- Story 20.7: ChainLens OpenAI Gateway Model Connections
- Story 20.8: ChainLens Webhook Monitors Automations
- Story 20.9: Async Research Jobs Resumption
- Story 20.10: `chainlens.pulse_feed` Curated Intelligence Feed
- Story 20.11: `chainlens.pulse_research` Angle Deep-Research

## Requirements & Constraints

- **FR-58 (scraper feed), FR-59 (gap-fill), FR-60 (private provider), FR-61 (service auth), FR-62 (chunk schema):** các contract cốt lõi giữa Nowing và `chainlens-research`.
- **Không xây owned corpus (AD-35):** dữ liệu public/vertical chỉ sống ở `chainlens-research`; Nowing giữ pointer (`chunk_id`/`source_url`), không nhân bản document.
- **PII redaction (AD-25/AD-49):** mọi outbound payload (query, urls) phải qua `redact_pii()` trước khi rời Nowing — đặc biệt với contents/code_search.
- **Cost thật (AD-8):** mọi call ChainLens phải ghi `TokenUsage` với `usage_type` riêng (vd `chainlens_contents`, `chainlens_code_search`, `chainlens_pulse_feed`, `chainlens_pulse_research`), quy đổi `costDollars → micros` cùng rate với external providers.
- **Degradation:** lỗi 5xx/timeout từ ChainLens phải degrade typed (banner + retry, `engine_unavailable`/`insufficient_credits`), không bao giờ lộ raw error; ingest retry exponential backoff max 3 lần rồi dead-letter queue.
- **Async door (AD-17):** research/gap-fill >60s phải chạy qua async mode (`?mode=async` hoặc `/async-jobs`), trả `run_id` cho user.
- **Success criteria mở rộng:** contents thay thế headless browser trong đa số tác vụ đọc URL; code_search giảm token waste; automations trigger được từ web monitors; Pulse cho phép 1 click từ headline sang cited report.

## Technical Decisions

- **Một chiều Nowing → ChainLens (AD-15):** ChainLens là external service, không phải scraper capability; không gọi ngược inline. Contract ổn định, cost đo thật, failure phải degrade.
- **Chunk schema (AD-34):** `Chunk.metadata` bắt buộc gồm `source: 'nowing_scraper'`, `sourceId` (stable fingerprint), `domain`, `fetchedAt`, `contentType`, `canonicalEntityId` (nếu có); chunk >8,000 tokens phải split với `chunkIndex`/`chunkTotal`; batch >1,000 chunks paginate với parent/child `ingestJobId`; duplicate `sourceId` (409) map sang `noop`.
- **Service auth:** Bearer service token + `X-Correlation-Id` + `X-Workspace-Id` trên mọi outbound call; token tự rotate trước khi hết hạn (30 ngày); rotate fail → fail-open với `service_auth_unavailable`, không gửi user data với token invalid.
- **Private data:** OAuth tokens không bao giờ rời Nowing Postgres; private search trả `chunks: []` + `costDollars: 0` khi không có data (không 404); RLS theo `workspaceId` bắt buộc.
- **Capability pattern:** copy cấu trúc `app/capabilities/news/entity_search/` (`definition.py` + `executor.py` + `schemas.py`), `billing_unit=BillingUnit.CHAINLENS_QUERY`, `context_aware=True`; tạo dedicated Input/Output schemas — KHÔNG widen `ResearchInput.output` Literal.
- **Agent tool wiring (3 bước bắt buộc per tool):** (a) register `Capability`, (b) append verb vào `_CI_VERBS` trong `tools/index.py`, (c) update `system_prompt.md` `<available_tools>`+`<playbook>` + `description.md` triggers — deploy prompt SAU khi tools đã registered.
- **Subagent strategy:** giữ MỘT chainlens subagent, mở rộng từ "deep research" sang "ChainLens intelligence" (không tách nhiều subagent).
- **Monitors:** `TriggerType.CHAINLENS_MONITOR` cần Alembic migration `ALTER TYPE automation_trigger_type ADD VALUE` (Postgres enum, không chạy trong transaction block); store `{query, cron, dedupKeyPolicy, monitorId}` trong `AutomationTrigger.params` JSONB sẵn có; inbound webhook phải verify HMAC-SHA256 (`hmac.compare_digest`) với `CHAINLENS_AUTH_CONTEXT_SECRET`.
- **Async jobs:** phân biệt 2 hệ run — `AsyncJobsClient` (external HTTP `/async-jobs`) map external `runId` → Nowing `run_id` qua `start_async_run`.
- **Pulse research:** reuse `research/sse_parser.py` + `ResearchOutput` (same SSE contract `init`→`text_delta`→`done{usage,chatId}`); feed/angles là public GET throttled — plain `httpx.get`, không SSE parser; persist `chatId` cho SEP-2567 resume.
- **OpenAI gateway:** zero backend schema change — chỉ thêm preset template (base URL `https://research-api.chainlens.net/v1`) + frontend badge.

## UX & Interaction Patterns

- **Tool routing cheat-sheet (binding):** mỗi ChainLens tool có description + when-to-use rule LLM nhìn thấy — copy verbatim từ UX spec Part A vào system prompt (vd: `contents` chỉ khi có URL cụ thể, `pulse_feed` cho "what's new", `entity_search` cho "news about <entity>", `wide_research` cho so sánh N entities, `code_search` chỉ cho câu hỏi lập trình).
- **Cost transparency:** hiển thị estimated cost TRƯỚC khi chạy wide_research/pulse_research/research depth; pulse angle dùng `estimatedCredits` từ feed trực tiếp.
- **Latency honesty:** mọi action >5s phải có progressive feedback (streaming, phase labels "Đang đọc trang web…", "Đang tổng hợp…"); wide_research (≤120s) phải stream progress "Đã phân tích N/M thực thể…" và checkpoint từng entity (resume không mất kết quả đã xong).
- **Model picker:** ChainLens models trong group riêng "ChainLens (Web-Grounded)" với globe icon + tooltip latency ~3–6s first token.
- **Pulse two-step flow:** browse feed (topic chips, infinite scroll theo `nextCursor` keyset — không offset) → angle picker với cost badge → `pulse_research` SSE vào cùng renderer deep-research.
- **Monitors trong Automation builder:** preset picker (daily/weekly/hourly/custom cron) — KHÔNG expose raw cron; zero-delta run hiển thị empty state thân thiện, không error.
- **Degradation + i18n:** mọi surface degrade theo pattern `degradation-ux` chuẩn; toàn bộ copy mới ship cả `vi.json` lẫn `en.json` (namespace `chainlens.*`), Vietnamese-first.

## Cross-Story Dependencies

- **20.1 phụ thuộc 20.4** (service auth) — `NowingIngestService` auth qua `ChainLensServiceAuth`.
- **20.2 phụ thuộc 20.1** — gap-fill chạy scraper Nowing rồi push kết quả về ChainLens qua ingest contract.
- **20.10 → 20.11:** pulse_research cần `{itemId, angleId}` từ pulse_feed; angle picker chỉ hiện khi `anglesCount > 0`.
- **Epic 13 (DROPPED 2026-08-08):** canonical entity storage đã chuyển sang `chainlens-research`; ingest contract của 20.1 là điểm kết nối duy nhất.
- **Epic 20 là prerequisite cho nhiều story khác:** 12.4 (job aggregator), 14.1 (RSS), 15.1/15.2 (financial), 16.1/16.2 (company), 17.1/17.2 (e-commerce), 24.2, 26.1 đều phụ thuộc `NowingIngestService` — không schedule trước khi 20.1 complete.
- **Story 26.9c (Epic 26):** upgrade DSH crawl subgraph sang native `output=wide_research`, checkpoint per `AD-108`.
- **Epic 32 (Browser Operator):** contents capability là Fast-Reader cho public web; auth-walled URLs route sang Browser Operator qua typed `unsupported_auth_wall` hint.
