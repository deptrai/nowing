---
baseline_commit: 2ae20a9028e81c1b77f804a9388fc3e786be3871
baseline_branch: develop
story_key: 9-5
status: ready-for-dev
---

# Story 9.5: Metered Deep-Research Endpoint cho Self-Host

**Status:** `ready-for-dev` *(đã chốt design, chờ dev implement; Post-MVP / P1 business; Epic 9 đã DONE)*
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng
**Priority:** P1 (business) / Post-MVP
**Requirements:** D5 · AD-15 · AD-8 · AD-16 · FR-37/FR-38
**Baseline:** `2ae20a902` on `develop`
**Dependencies:** Story `9.1a` (self-host independence), `9.2` (cost metering real), `8.7` (auto-extract spend cap) đã done.

## Story

Với tư cách self-hoster,
tôi muốn trả tiền theo call để dùng deep research trên bản self-host,
để tôi không phải chuyển sang cloud chỉ vì một năng lực.

## Context & Current Reality

Tại baseline `2ae20a902`:

| Mảnh | Trạng thái | Bằng chứng code |
|---|---|---|
| Deep research executor degrade khi service token chưa cấu hình | ✅ BUILT | `app/capabilities/chainlens/research/executor.py:799-802` (`ChainLensServiceAuth.configured` false → `_engine_unavailable("not_configured")` tại 788-790) |
| Wallet / credit micros balance | ✅ BUILT | `app/services/wallet_credit.py:33-47` `spendable_micros`, `50-71` `check_balance`, `73-103` `apply_debit` |
| Token usage ghi `cost_micros` + `usage_type` | ✅ BUILT | `app/services/token_tracking_service.py:54-70` `UsageType` (`DEEP_RESEARCH` = 62); `565-647` `record_token_usage`; `app/db.py:1182-1274` `TokenUsage` (`cost_micros` 1228, `usage_type` 1236) |
| Cost metering deep research theo cost thật (`costDollars` SSE) | ✅ BUILT (Story 9.2) | `app/capabilities/chainlens/research/executor.py:501-574` `_extract_cost` parse `costDollars`; `app/capabilities/core/billing.py:378-502` `_charge_chainlens` dùng cost thật |
| Flat `CHAINLENS_QUERY_MICROS_PER_CALL` fallback | ✅ BUILT | `app/config/__init__.py:1096-1102` default **60.000 micros (~$0.06)**; `billing.py:409-418` dùng fallback + warning |
| Self-host đi engine trực tiếp | ❌ KHÔNG ĐƯỢC PHÉP | ADR `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5: engine KHÔNG phải public multi-tenant SaaS |
| Endpoint self-host → Nowing Cloud → engine | 🆕 GAP cần build | xem Design Decisions D8 và AC-1/AC-4 |
| Self-host API key / account mapping | 🆕 GAP cần build | xem Design Decisions D4/D5; cần route + resolver cho self-host key |
| Quota / chống abuse cho self-host calls | 🆕 GAP cần build | xem Design Decisions D7; tái dụng token quota / Redis rate-limit theo `api_key` |

## Design Decisions

Các quyết định sau đã được chốt để story đủ rõ cho dev; không còn phụ thuộc SCP mới trước khi implement.

### D1 — Self-host KHÔNG gọi engine trực tiếp
- `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4: engine scale theo tải của Nowing (một consumer đáng tin cậy), KHÔNG phải public multi-tenant SaaS.
- §5: Nowing giữ **một** service key; engine không có end-user auth.
- ⇒ Self-host instance muốn dùng engine phải đi qua Nowing Cloud API, nơi Nowing giữ key duy nhất và xử lý account/quota.

### D2 — Reuse credit wallet + cost-thật của AD-8 / FR-37
- `User.credit_micros_balance` là ví duy nhất (`app/services/wallet_credit.py:33-103`).
- `TokenUsage` đã ghi `cost_micros` / `usage_type` (`app/db.py:1182-1274`, `cost_micros` tại 1228, `usage_type` tại 1236).
- `_charge_chainlens` đã parse `costDollars` từ SSE và debit (`app/capabilities/core/billing.py:378-502`); `UsageType.DEEP_RESEARCH` tại `app/services/token_tracking_service.py:62`.
- Story 9.5 chỉ cần mở rộng **caller context**: từ workspace-user trên cloud sang account của một self-host instance.

### D3 — License / OSS messaging
- Deep-research engine là closed-source, hosted; core Nowing là Apache-2.0; crawler là BSL 1.1 (`AD-16`).
- Tài liệu self-host phải ghi: deep research là năng lực cloud; self-host cần key Nowing Cloud để dùng.

### D4 — Self-host entity: reuse `User` + API key table
- Mỗi instance self-host đăng ký bằng một API key gắn với một `User` (owner).
- Repo hiện **không có bảng `api_keys`**. Bảng khóa lập trình hiện có là `personal_access_tokens` (`app/db.py:3397-3455`).
- **Quyết định Phase 2 MVP:** tái dụng `personal_access_tokens`, thêm giá trị `token_kind='self_host'` (hoặc thêm cột `key_type` nếu muốn tách semantic) và gán `workspace_id` = workspace chủ sở hữu (hoặc một workspace đặc biệt cho self-host instance).
- Nếu cần theo dõi nhiều instance/key với metadata (hostname, version, v.v.), tạo migration mới `self_host_instance` và `self_host_api_key` (`self_host_api_key` 1-to-1 hoặc many-to-one với `User`). Tạo Alembic migration tương ứng.

### D5 — Auth model
- Self-host gọi Nowing Cloud bằng `Authorization: Bearer <self_host_api_key>`.
- Nowing Cloud validate key qua `resolve_pat` (`app/utils/pat.py:36-52`) hoặc một resolver tương tự; yêu cầu `token_kind='self_host'` (nếu dùng PAT) hoặc prefix `nw_sh_` (nếu tách bảng).
- Từ key xác định `User` (owner) và `Workspace` (lấy từ `workspace_id` của key hoặc workspace mặc định của owner). Debit `User.credit_micros_balance` (`app/services/wallet_credit.py:73-103`).
- Nếu key thiếu / không hợp lệ: trả `401` kèm hướng dẫn tạo key.
- Nếu `ChainLensServiceAuth` chưa configured (`app/services/chainlens/auth.py:96-98` hoặc `app/capabilities/chainlens/research/executor.py:799-802`): trả `ResearchOutput(status="engine_unavailable", degradation_reason="not_configured")` với hướng dẫn cấu hình `CHAINLENS_SERVICE_TOKEN` / `CHAINLENS_API_KEY`.

### D6 — Pricing per call
- Dùng `costDollars` thật từ SSE (`app/capabilities/chainlens/research/executor.py:501-574`), chuyển sang micros qua `ChainLensServiceAuth.cost_dollars_to_micros` (`app/services/chainlens/auth.py:269-289`).
- Nếu missing/invalid cost: fallback `CHAINLENS_QUERY_MICROS_PER_CALL = 60000` micros (`app/config/__init__.py:1096-1102`); `_charge_chainlens` tại `billing.py:409-418` log warning và dùng fallback.
- `costDollars = 0` (sponsored runway/benchmark test key) thì không trừ credit (`wallet_credit.apply_debit` no-op với `cost_micros <= 0` và `_charge_chainlens` bỏ qua `cost_micros < 0`).
- Margin ban đầu **1.5×** để dự phòng full-pipeline cost. Có thể cấu hình qua `SELF_HOST_RESEARCH_COST_MULTIPLIER` (default `1.5`) hoặc cặp numerator/denominator để tránh float. Billed micros = `floor(cost_micros * 1.5)` khi `cost_micros > 0`; ghi cả `cost_micros` gốc và `billed_micros` vào `call_details`.

### D7 — Quota / chống abuse
- Tái dụng token quota service (`app/services/token_quota_service.py`) hoặc Redis rate-limit theo `api_key` / `user_id`.
- Default: **120 req / 60s / key** (như ChainLens B2B); vượt → `429` + `Retry-After`.
- Daily quota: giới hạn bởi `User.credit_micros_balance` (pre-check qua `wallet_credit.check_balance`) hoặc cấu hình `SELF_HOST_RESEARCH_DAILY_QUOTA`.
- Có thể tái dụng pattern `enforce_capability_rate_limit` (`app/capabilities/core/access/rate_limit.py:68-76`) với key là `self_host:<key_hash>` thay vì `workspace_id`.

### D8 — Route
- `POST /v1/self-host/research` (hoặc `/v1/chainlens/research`) trên Nowing Cloud.
- Body: tương tự `ResearchInput` (`app/capabilities/chainlens/research/schemas.py:69-124`).
- Auth: `Authorization: Bearer <self_host_api_key>`; dependency mới `get_self_host_auth` (hoặc mở rộng `get_auth_context` tại `app/users.py:330-377`).
- Thực thi: gọi `build_research_executor()` (`app/capabilities/chainlens/research/definition.py:9-22` / `executor.py:793-866`) với `CapabilityContext(workspace_id=<owner_workspace>, run_id=<correlation_id>)`.
- Response: SSE `ResearchOutput` frames (`schemas.py:127-342`), hoặc `engine_unavailable` JSON nếu degraded.
- Pattern tham khảo: `app/capabilities/core/access/rest.py:197-362` (`_register_verb`: authn → workspace authz → gate → execute → charge → typed output) và `app/routes/chainlens_internal.py:77-191` (route `/v1/...` + service auth).

### D9 — Degradation
- Không có key / key lỗi: trả `401` hoặc `engine_unavailable` kèm hướng dẫn.
- `ChainLensServiceAuth` chưa configured: trả `engine_unavailable` `not_configured`.
- Engine trả 429/5xx/timeout: trả `engine_unavailable` với `degradation_reason` tương ứng (`rate_limited`, `upstream_error`).
- Giữ nguyên yêu cầu FR-38: không hard-fail, luôn có `next_action` rõ ràng.

## Acceptance Criteria

### AC-1 — Self-host request phải đi qua Nowing Cloud, không đi engine trực tiếp
**Given** self-host đã cấu hình key Nowing Cloud
**When** self-host gọi deep research
**Then** request đi theo đường `self-host Nowing → Nowing Cloud API (metered, key theo account) → engine (vẫn 1 service key)`
**And** **CẤM** `self-host → engine trực tiếp` — cách đó biến engine thành public multi-tenant SaaS có end-user auth, phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 và SCP v4 de-scope
**And** metering/quota/chống abuse nằm ở Nowing Cloud (tái dụng account + credit wallet, `AD-8`), không nằm ở engine.

### AC-2 — Không có key Cloud thì vẫn degrade, không hard-fail
**Given** self-host không có key Nowing Cloud
**When** gọi deep research
**Then** hành vi giữ nguyên như Phase 1 — trả `ResearchOutput(status="engine_unavailable", degradation_reason="not_configured")` kèm hướng dẫn cấu hình, không hard-fail (FR-38).

### AC-3 — Metering dùng cost thật hoặc fallback rõ ràng
**Given** self-host đã cấu hình key Nowing Cloud
**When** gọi deep research
**Then** cost thật (`costDollars` từ terminal `done.usage` SSE, parse tại `executor.py:501-574`) được chuyển sang `cost_micros` (`ChainLensServiceAuth.cost_dollars_to_micros` tại `auth.py:269-289`) và trừ từ `User.credit_micros_balance`
**And** nếu engine bỏ qua `costDollars` (failed / cancelled / cost chưa tính được), dùng flat fallback `CHAINLENS_QUERY_MICROS_PER_CALL = 60000` micros tại `config/__init__.py:1096-1102` và ghi warning
**And** `costDollars = 0` chỉ xảy ra trong test key benchmark sponsored runway; production và benchmark mới 2026-08-02 emit cost thực tế. Nếu `costDollars = 0` từ engine thì không trừ credit.
**And** mỗi call được ghi `TokenUsage` với `usage_type = UsageType.DEEP_RESEARCH` (`token_tracking_service.py:62`), `cost_micros`, `workspace_id`/`user_id` tương ứng.

### AC-4 — Quota / chống abuse cho self-host
**Given** một self-host instance đã đăng ký API key (`token_kind='self_host'` trong `personal_access_tokens` hoặc bảng `self_host_api_keys`)
**When** nó gọi `/v1/self-host/research` nhiều lần
**Then** Nowing Cloud áp rate limit **120 req / 60s / key** (tái dụng `enforce_capability_rate_limit` pattern tại `rate_limit.py:68-76` hoặc `TokenQuotaService`)
**And** giới hạn daily/quota phụ thuộc `User.credit_micros_balance` hoặc cấu hình `SELF_HOST_RESEARCH_DAILY_QUOTA`
**And** khi hết credit, trả `402 Payment Required` / `InsufficientCreditsError` rõ ràng
**And** khi vượt rate limit, trả `429 Too Many Requests` với `Retry-After`.

### AC-5 — Docs & README cập nhật
**Given** feature được bật
**When** người dùng đọc `README.md` / `docs/self-host.md`
**Then** thấy hướng dẫn kích hoạt deep research trên self-host, cách lấy key Nowing Cloud, và bảng so sánh self-host vs cloud
**And** không gọi ChainLens là open-source, không gọi engine là sản phẩm riêng (AD-16).

## ChainLens Technical Response — Final (2026-08-01)

Phản hồi từ team dev ChainLens sau follow-up. Hai blocker chính đã xong; các ràng buộc cần phản ánh vào SCP và design 9.5:

### F1 — Story 42-1 DONE: `costDollars` trong terminal `done.usage`
- Contract lock: **Option B** — `costDollars` được chèn **additively** trong terminal `done` frame:
  ```
  data: {"type":"done","usage":{...,"costDollars":<number>},"requestedMode":...,"resolvedMode":...}
  ```
- `costDollars` được tính bởi `ModelCostAnalyzer` từ cùng price catalog mà ledger sẽ dùng (AC2 single-source).
- **Writer usage only** — full-pipeline aggregation (classifier/researcher/writer/reflection) là follow-up đã ghi trong story task 6. Cho đến khi full-pipeline xong, cost trả về là **chi phí writer**, chưa phải tổng chi phí call.
- Code review xong, branch `story/42-1-costdollars` sẵn sàng merge.

| Trường hợp | Hành vi |
|---|---|
| failed / cancelled / timeout / 5xx / cost không tính được | Field `costDollars` bị **omit**. Consumer coi missing field = no bill. |
| Cost tính được = 0 (sponsored runway) | `costDollars: 0` chỉ xảy ra trong các benchmark test key; production và benchmark mới 2026-08-02 đã emit cost thực tế. |
| Engine chưa tính được cost | Không có fallback; field bị omit. |
| Client cancel | Engine hiện tại **không dừng ngay** khi HTTP disconnect. Nếu `done` đã emit trước cancel, `costDollars` vẫn xuất hiện. Nếu cancel trước `done`, stream đóng và không có `cost`. |

Live verify (agy/gemini-3.6-flash):
```json
{"type":"done","usage":{"promptTokens":4273,"completionTokens":3677,"totalTokens":7950,"model":"gemini-3.6-flash","costDollars":0.0482,...},"resolvedMode":"balanced"}
```

**Tác động 9.5 / 9.2:**
- Parser Nowing đã cập nhật (`executor.py:_extract_cost`) để đọc `costDollars` từ `done.usage`, vẫn defensive với top-level `costDollars` và standalone `usage` event.
- Benchmark 2026-08-02 (`report-per-mode.md`, 31 queries) ghi cost thực tế: research speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519**. `costDollars` **không còn $0**.
- `CHAINLENS_QUERY_MICROS_PER_CALL` fallback nâng từ 5,000 ($0.005) → **60,000 micros (~$0.06)** để sát với cost thực tế khi engine không emit `costDollars`.
- Vì cost hiện là writer-only, full-pipeline aggregation có thể cao hơn 1.5–2.5×. Cần theo dõi follow-up 42-1b/42-3 trước khi chốt pricing.

### F2 — Benchmark mới với `agy/gemini-3.6-flash-*` (non-search, n=57)
ChainLens đã chạy `node --experimental-strip-types benchmark/run.ts --chainlens-only --all-modes`:

| Mode | Queries | p50 | p95 | Avg words | Avg cites | Quality pass |
|---|---|---|---|---|---|---|
| speed | 19 | 24,189 ms | 34,964 ms | 273 | 6.9 | 95% |
| balanced | 19 | 30,681 ms | 69,888 ms | 676 | 6.9 | 95% |
| deep | 19 | 42,922 ms | 114,513 ms | 2,067 | 8.1 | 89% |

- HTTP success = 100%.
- Fail/degraded do SearXNG CAPTCHA/rate-limit → `provider_failover_failed`.
- `costDollars` **không còn $0**. Benchmark `report-per-mode.md` (2026-08-02, 31 queries) ghi cost thực tế: research speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình toàn bộ **$0.0519 / call**. Cost tham chiếu Nowing (`tier=research`): **speed $0.0353 / balanced $0.0482 / quality $0.0671**.
- p95 vượt target NFR-9 (30s) ở mọi mode. ChainLens khuyến nghị chạy lại sau khi ổn định SearXNG/Brave/proxy.

**Tác động NFR-9 / 9.3:**
- State A vẫn là mặc định; **KHÔNG mở khóa sync chat-mode**.
- Cần benchmark từ phía Nowing (e2e, bao gồm network + parsing + charge) trước khi chốt p50/p95 chính thức.

### F3 — Auth & key model
- ChainLens B2B surface: **một Bearer API key duy nhất** (`Authorization: Bearer <64-hex>`), validate qua `ApiKeyGuard`.
- Không có end-user JWT.
- Nhiều API key per user, mỗi key có `quotaLimit`, `quotaResetAt`, `name`.
- **Khuyến nghị Phase 2:** Nowing Cloud dùng **một service key với `quotaLimit = -1` (unlimited)** rồi tự meter + quota per self-host tenant.

### F4 — Rate limit / quota
- 120 requests / 60s / key. Vượt → 429 + `Retry-After`.
- Daily quota theo key, Redis hash `quota:b2b:{keyId}` field `YYYY-MM-DD` UTC. `quotaLimit = -1` = unlimited. Vượt → 429.
- Redis outage → 503 `{"status":"error","reason":"b2b-admission-unavailable"}`.
- **Không có API / header** query quota còn lại; Nowing Cloud phải tự track hoặc catch 429.

### F5 — SSE contract & regression guard (Story 42-2 DONE)
- Data-only SSE frames `data: <json>`, không `event:` line.
- `id: N` line trên mỗi frame.
- Terminal `data: {"type":"done"}` (không `[DONE]`).
- JSON error `{"type":"error","data":"..."}`.
- Test matrix: `search-contract.spec.ts` (110 tests), `api.spec.ts` (31), `api.mutation.spec.ts` (620), Stryker 93.75% trên `search.controller.ts`.
- Nowing có thể tự chạy contract test bằng SSE consumer script; ChainLens cung cấp snippet Python trong 24h nếu cần.

### F6 — Request schema
```json
{
  "query",
  "sources[]",
  "history[]",
  "optimizationMode?": "auto|speed|balanced|deep|deep-reasoning",
  "tier?": "search|ask|reason|research",
  "systemInstructions?",
  "chatId?",
  "stream?": true,
  "title?",
  "messageId?"
}
```
- `tier` default `ask`, `optimizationMode` default `auto`, `stream` default `true`.
- `sources ∈ {web, discussions, academic}`.
- `deep/deep-reasoning` map sang legacy `quality`.
- Không có versioning URL / formal changelog.

### F7 — Async / long-running
- Không có webhook/callback.
- Client cancel đóng SSE nhưng engine **KHÔNG dừng xử lý**. AbortSignal từ disconnect xuống pipeline là follow-up.

### F8 — Follow-up 2026-08-02

#### Python SSE contract test snippet
- ChainLens cung cấp `nowing-sse-contract-snippet.py` để chạy standalone, parse SSE wire format, extract answer/sources/terminal `done`/costDollars, ignore unknown/future event types.
- Hỗ trợ sample frames: `init`, `progress`, `evidence_ready`, `synthesizing`, `researchComplete`, `done`/done.usage, `error`.
- **Đã lưu và chạy thử:**
  - Path: `nowing_backend/scripts/nowing-sse-contract-snippet.py` (track trong git) + bản sao `_bmad-output/test-artifacts/nowing-sse-contract-snippet.py`.
  - `python3 nowing_backend/scripts/nowing-sse-contract-snippet.py` chạy mẫu, trả `costDollars: 0.00123` từ `done.usage`.
  - Có thể chạy live: `export CHAINLENS_API_URL + CHAINLENS_SERVICE_TOKEN` (hoặc `CHAINLENS_API_KEY` legacy), `python3 ... --live "query"`.

#### Full-pipeline cost aggregation
- `costDollars` vẫn là **writer usage only**. Full-pipeline aggregation (classifier/planner/researcher/writer/reflection) là task 6 "LATER" trong `stories/42-1-costdollars-in-sse.md`.
- **Plan/timeline:** ChainLens sẽ tạo story + PRD follow-up (42-1b hoặc 42-3) trong tuần này, trình sprint planning tuần tới. Dự kiến land: **~2–4 sprint (2–4 tuần)** sau khi benchmark và SearXNG/Brave/proxy pipeline ổn định, vì cần wire `UsageLedgerService` với `PhaseTracker`.
- ChainLens ước tính: full-pipeline cost thực **cao hơn 1.5–2.5×** so với writer cost tùy mode.
- **Tác động pricing:** writer cost từ benchmark 2026-08-02 (`report-per-mode.md`) là baseline tạm thời: research speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519**. Giá self-host/cloud phải để lại margin 1.5–2.5× cho khi full-pipeline cost land. Không chốt giá cố định dựa trên writer cost.

#### Benchmark sạch hơn
- Plan: ổn định SearXNG (tắt mojeek/yep, fallback Brave/Jina), proxy/residential rotation hoặc Brave-first routing.
- Dự kiến rerun trong **24–48h** trên staging.
- ChainLens đồng ý: **State A mặc định**; story 9.5 đã chốt design và chuyển `ready-for-dev`.
- **2026-08-02:** ChainLens đã chạy focused rerun **6 query × 3 mode = 18 runs** sau khi ổn định SearXNG/Brave:

  | Mode | p95 | NFR-9 target | Kết luận |
  |---|---|---|---|
  | speed | 27.5 s | ≤ 30 s | ✅ PASS |
  | balanced | 44.3 s | ≤ 30 s | ❌ FAIL |
  | deep | 43.7 s | ≤ 60 s | ✅ PASS |

  - `ask` tier ở `quality` vẫn vượt target 30 s của NFR-6.
  - `costDollars` **không còn $0**; benchmark `report-per-mode.md` (2026-08-02, 31 queries) ghi cost thực tế (Nowing `tier=research`): speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519 / call**. `CHAINLENS_QUERY_MICROS_PER_CALL` fallback đã nâng → **60,000 micros (~$0.06)**.
  - Full benchmark **69 query** đang lên lịch để củng cố p95.

## Remaining Risks

- **Cost-thật writer-only:** `costDollars` mới chỉ tính writer usage. Full-pipeline aggregation là follow-up 42-1b/42-3, dự kiến land sau **2–4 sprint** (~2–4 tuần), có thể cao hơn 1.5–2.5×. Đã chốt margin 1.5× trong D6 để dự phòng; cần theo dõi và điều chỉnh multiplier khi full-pipeline cost land.
- **Cancel không stop engine:** self-host user cancel trên client vẫn có thể bị charge toàn bộ call. AbortSignal từ disconnect xuống pipeline là follow-up ChainLens, chưa block 42-1.
- **No quota-remaining API:** Nowing Cloud phải tự track hoặc catch 429 từ ChainLens và map sang error tường minh.
- **Latency p95:** balanced (44.3 s) vẫn vượt NFR-9 30 s; State A mặc định, sync chat-mode vẫn bị khóa.

## Tasks / Subtasks

### Pre-built (do not re-implement)
- [x] Cập nhật SSE parser để nhận `costDollars` từ terminal `done.usage` (Story 9.2 — `executor.py:501-574` + `test_cost_metering.py`).
- [x] Nhận và lưu snippet `nowing-sse-contract-snippet.py` (Story 9.2 / 42-2 — `nowing_backend/scripts/`).
- [x] Thiết lập `ChainLensServiceAuth` với `CHAINLENS_SERVICE_TOKEN` + `CHAINLENS_API_KEY` fallback (Story 20.4 — `app/services/chainlens/auth.py:56-311`).

### Build for Story 9.5
- [ ] Migration schema (nếu cần): thêm `token_kind='self_host'` vào `personal_access_tokens` hoặc tạo bảng `self_host_instance` + `self_host_api_key`.
- [ ] Tạo dependency `get_self_host_auth` (hoặc mở rộng `get_auth_context` tại `app/users.py:330-377`) để validate `Authorization: Bearer <self_host_api_key>`, map đến `User` + `Workspace`.
- [ ] Thêm route `POST /v1/self-host/research` (hoặc `/v1/chainlens/research`) trong router mới `app/routes/self_host_research.py`, mount tại `app/app.py` với prefix `/v1`.
- [ ] Tái dụng `build_research_executor()` (`definition.py:9-22`) / `_call_chainlens` (`executor.py:793-866`) trong context self-host (`CapabilityContext` với `workspace_id` từ key).
- [ ] Áp margin 1.5× (config `SELF_HOST_RESEARCH_COST_MULTIPLIER`) trên `cost_micros` thực tế / fallback; ghi `cost_micros` gốc + `billed_micros` vào `call_details`.
- [ ] Gọi `wallet_credit.check_balance` / `apply_debit` (`wallet_credit.py:50-103`) và `record_token_usage` (`token_tracking_service.py:565-647`) với `usage_type=UsageType.DEEP_RESEARCH` cho self-host account.
- [ ] Thêm rate limit / quota theo self-host API key: tái dụng `enforce_capability_rate_limit` pattern (`rate_limit.py:68-76`) hoặc `TokenQuotaService`; default 120 req/60s/key; daily quota theo `User.credit_micros_balance` hoặc `SELF_HOST_RESEARCH_DAILY_QUOTA`.
- [ ] Degradation path: thiếu key → `401` / hướng dẫn; `ChainLensServiceAuth` chưa configured → `ResearchOutput(status="engine_unavailable", degradation_reason="not_configured")`; engine 429/5xx/timeout → `engine_unavailable` với reason tương ứng.
- [ ] Cập nhật `README.md`, `.env.example`, `docs/self-host.md` với hướng dẫn lấy key, cấu hình, và bảng so sánh self-host vs cloud.
- [ ] Tests: unit + integration cho happy path, out-of-credit, rate limit, no key, invalid key, engine unavailable, cost=0.

### Follow-up (LATER, không block 9.5)
- [ ] Theo dõi ChainLens full-pipeline cost aggregation (42-1b/42-3, dự kiến 2–4 sprint); điều chỉnh `SELF_HOST_RESEARCH_COST_MULTIPLIER` khi full-pipeline cost land.
- [ ] Chạy benchmark e2e từ phía Nowing sau khi ChainLens rerun 24–48h.

## Consistency & Conventions

- Theo `AD-8`: dùng `User.credit_micros_balance` + `TokenUsage.cost_micros`.
- Theo `AD-15`: Nowing Cloud outbound dùng `ChainLensServiceAuth` (`CHAINLENS_SERVICE_TOKEN` preferred, `CHAINLENS_API_KEY` legacy fallback); engine vẫn 1 service key, không end-user auth.
- Theo `AD-16`: docs phân biệt rõ license ba tầng, không gọi engine là OSS.
- Theo `FR-38`: self-host không có key / `ChainLensServiceAuth` chưa configured phải degrade về `engine_unavailable`, không hard-fail.
- Theo `FR-37`: cost thật từ `costDollars` SSE; fallback flat `CHAINLENS_QUERY_MICROS_PER_CALL = 60000` micros chỉ khi thiếu.

## References

- `epics.md:1253-1274` — Story 9.5 gốc và AC nháp.
- `prd.md:1083-1120` — FR-38 + Phase 1/Phase 2 deep research cho self-host và ràng buộc kiến trúc.
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-8, AD-15, AD-16.
- `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` (companion) — engine boundary.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:501-574` — `_extract_cost` parse `costDollars`.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:788-790` — `_engine_unavailable`.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:793-866` — `_call_chainlens`.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:799-802` — `ChainLensServiceAuth.configured` check.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py:69-342` — `ResearchInput`, `ResearchOutput` (`cost_dollars`, `cost_micros`, `resolved_mode`, `tier`, `workspace_id`, `correlation_id`, ...).
- `nowing_backend/app/capabilities/core/billing.py:378-502` — `_charge_chainlens`, `BillingUnit.CHAINLENS_QUERY`.
- `nowing_backend/app/capabilities/core/types.py:15-49` — `BillingUnit` enum.
- `nowing_backend/app/capabilities/core/access/rest.py:197-362` — pattern route/capability (`_register_verb`).
- `nowing_backend/app/services/wallet_credit.py:33-103` — `spendable_micros`, `check_balance`, `apply_debit`.
- `nowing_backend/app/services/token_tracking_service.py:54-70,565-647` — `UsageType.DEEP_RESEARCH`, `record_token_usage`.
- `nowing_backend/app/config/__init__.py:1086-1102` — `CHAINLENS_SERVICE_TOKEN`, `CHAINLENS_API_KEY`, `CHAINLENS_QUERY_MICROS_PER_CALL` (default 60000).
- `nowing_backend/app/db.py:1182-1274,3397-3455` — `TokenUsage` (`cost_micros` 1228, `usage_type` 1236), `PersonalAccessToken` (API-key table để tái dụng).
- `nowing_backend/app/services/chainlens/auth.py:56-311` — `ChainLensServiceAuth`, `cost_dollars_to_micros`, `configured`.
- `nowing_backend/app/users.py:330-377` + `app/utils/pat.py:36-52` — `get_auth_context` / `resolve_pat` pattern.
- `nowing_backend/app/capabilities/core/access/rate_limit.py:68-76` — `enforce_capability_rate_limit` pattern.
- `nowing_backend/app/routes/chainlens_internal.py:77-191` — route `/v1/...` + service-to-service auth pattern.
