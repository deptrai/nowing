---
baseline_commit: 500dccbdeb1be6e5085982a8c47e91d79bf19d3b
baseline_branch: develop
story_key: 9-5
status: backlog
---

# Story 9.5: Metered Deep-Research Endpoint cho Self-Host

**Status:** `backlog` / **deferred** *(chưa phê duyệt, Post-MVP / P1 business; Epic 9 đã DONE)*  
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng  
**Priority:** P1 (business) / Post-MVP  
**Requirements:** D5 · AD-15 · AD-8 · AD-16 · FR-37/FR-38  
**Baseline:** `500dccbdeb` on `develop`  
**Dependencies:** Story `9.1a` (self-host independence), `9.2` (cost metering real), `8.7` (auto-extract spend cap) đã done.

## Story

Với tư cách self-hoster,  
tôi muốn trả tiền theo call để dùng deep research trên bản self-host,  
để tôi không phải chuyển sang cloud chỉ vì một năng lực.

## Context & Current Reality

Tại baseline `500dccbdeb`:

| Mảnh | Trạng thái | Bằng chứng code |
|---|---|---|
| Deep research executor degrade khi `CHAINLENS_API_KEY` rỗng | ✅ BUILT | `app/capabilities/chainlens/research/executor.py:587-589` trả `_engine_unavailable("not_configured")` |
| Wallet / credit micros balance | ✅ BUILT | `app/services/wallet_credit.py:33-48` spendable, `50-70` check, `73-83` debit |
| Token usage ghi `cost_micros` + `usage_type` | ✅ BUILT | `app/services/token_tracking_service.py:35-119` accumulator; `record_token_usage` helper |
| Cost metering deep research theo cost thật (`costDollars` SSE) | ✅ BUILT (Story 9.2) | `app/capabilities/chainlens/research/executor.py` parse `costDollars`; `app/capabilities/core/billing.py:282-337` `_charge_chainlens` dùng cost thật |
| Flat `CHAINLENS_QUERY_MICROS_PER_CALL` fallback | ✅ BUILT | `app/config/__init__.py:915-917` default 5000; `billing.py:285-287` dùng fallback + warning |
| Self-host đi engine trực tiếp | ❌ KHÔNG ĐƯỢC PHÉP | ADR `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5: engine KHÔNG phải public multi-tenant SaaS |
| Endpoint self-host → Nowing Cloud → engine | ❌ GAP | chưa có design / code; chỉ có requirement trong `epics.md` và `prd.md:649-657` |
| Self-host API key / account mapping | ❌ GAP | chưa có model hoặc route để self-host instance đăng ký key theo account |
| Quota / chống abuse cho self-host calls | ❌ GAP | hiện metering nằm ở workspace-level Nowing Cloud; cần mở rộng cho self-host tenant |

## Deferred Sign-off Gates

Story này **KHÔNG THỂ chuyển `ready-for-dev`** cho đến khi cả hai điều sau đã xảy ra (theo `epics.md:633`):

1. Có số self-host thật (adoption) để biết có đáng build.
2. Story `9.2` đã cho số cost thật để định giá.

Ngoài ra cần một SCP phê duyệt:

- Cách self-host instance xác thực với Nowing Cloud (token? account? license key?).
- Mô hình pricing per call (margin, minimum, volume).
- Policy chống abuse / rate limit / quota per instance.
- Cách tiếp thị / vận hành (có thể dùng trial credit, top-up Stripe, hay invoice).

## Acceptance Criteria (draft — cần SCP phê duyệt trước khi dev)

### AC-1 — Self-host request phải đi qua Nowing Cloud, không đi engine trực tiếp
**Given** Phase 2 được phê duyệt  
**When** self-host gọi deep research  
**Then** request đi theo đường `self-host Nowing → Nowing Cloud API (metered, key theo account) → engine (vẫn 1 service key)`  
**And** **CẤM** `self-host → engine trực tiếp` — cách đó biến engine thành public multi-tenant SaaS có end-user auth, phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 và SCP v4 de-scope  
**And** metering/quota/chống abuse nằm ở Nowing Cloud (tái dụng account + credit wallet, `AD-8`), không nằm ở engine.

### AC-2 — Không có key Cloud thì vẫn degrade, không hard-fail
**Given** self-host không có key Nowing Cloud  
**When** gọi deep research  
**Then** hành vi giữ nguyên như Phase 1 — trả `engine_unavailable` kèm hướng dẫn cấu hình, không hard-fail (FR-38).

### AC-3 — Metering dùng cost thật hoặc fallback rõ ràng
**Given** self-host đã cấu hình key Nowing Cloud  
**When** gọi deep research  
**Then** cost thật (`costDollars` từ terminal `done.usage` SSE) được parse và trừ từ credit wallet của account Nowing Cloud  
**And** nếu engine bỏ qua `costDollars` (failed / cancelled / cost chưa tính được), dùng flat fallback `CHAINLENS_QUERY_MICROS_PER_CALL` và ghi warning  
**And** `costDollars = 0` chỉ xảy ra trong test key benchmark sponsored runway; production và benchmark mới 2026-08-02 emit cost thực tế. Nếu `costDollars = 0` từ engine thì không trừ credit.  
**And** mỗi call được ghi `TokenUsage` với `usage_type = "deep_research"`, `workspace_id`/`user_id` tương ứng.

### AC-4 — Quota / chống abuse cho self-host
**Given** một self-host instance  
**When** nó gọi nhiều lần trong khoảng thời gian ngắn  
**Then** Nowing Cloud áp rate limit / quota theo account  
**And** khi hết credit hoặc vượt quota, trả `InsufficientCreditsError` hoặc `rate_limit_exceeded` rõ ràng.

### AC-5 — Docs & README cập nhật
**Given** feature được bật  
**When** người dùng đọc `README.md` / `docs/self-host.md`  
**Then** thấy hướng dẫn kích hoạt deep research trên self-host, cách lấy key Nowing Cloud, và bảng so sánh self-host vs cloud  
**And** không gọi ChainLens là open-source, không gọi engine là sản phẩm riêng (AD-16).

## Resolved Decisions

### D1 — Self-host KHÔNG gọi engine trực tiếp
- `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4: engine scale theo tải của Nowing (một consumer đáng tin cậy), KHÔNG phải public multi-tenant SaaS.
- §5: Nowing giữ **một** service key; engine không có end-user auth.
- ⇒ Self-host instance muốn dùng engine phải đi qua Nowing Cloud API, nơi Nowing giữ key duy nhất và xử lý account/quota.

### D2 — Reuse credit wallet + cost-thật của AD-8 / FR-37
- `User.credit_micros_balance` là ví duy nhất (`app/services/wallet_credit.py`).
- `TokenUsage` đã ghi `cost_micros` (`app/db.py:1125`).
- `_charge_chainlens` đã parse `costDollars` từ SSE và debit (`app/capabilities/core/billing.py:282-337`).
- Story 9.5 chỉ cần mở rộng **caller context**: từ workspace-user trên cloud sang account của một self-host instance.

### D3 — License / OSS messaging
- Deep-research engine là closed-source, hosted; core Nowing là Apache-2.0; crawler là BSL 1.1 (`AD-16`).
- Tài liệu self-host phải ghi: deep research là năng lực cloud; self-host cần key Nowing Cloud để dùng.

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
  - Có thể chạy live: `export CHAINLENS_API_URL + CHAINLENS_API_KEY`, `python3 ... --live "query"`.

#### Full-pipeline cost aggregation
- `costDollars` vẫn là **writer usage only**. Full-pipeline aggregation (classifier/planner/researcher/writer/reflection) là task 6 "LATER" trong `stories/42-1-costdollars-in-sse.md`.
- **Plan/timeline:** ChainLens sẽ tạo story + PRD follow-up (42-1b hoặc 42-3) trong tuần này, trình sprint planning tuần tới. Dự kiến land: **~2–4 sprint (2–4 tuần)** sau khi benchmark và SearXNG/Brave/proxy pipeline ổn định, vì cần wire `UsageLedgerService` với `PhaseTracker`.
- ChainLens ước tính: full-pipeline cost thực **cao hơn 1.5–2.5×** so với writer cost tùy mode.
- **Tác động pricing:** writer cost từ benchmark 2026-08-02 (`report-per-mode.md`) là baseline tạm thời: research speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519**. Giá self-host/cloud phải để lại margin 1.5–2.5× cho khi full-pipeline cost land. Không chốt giá cố định dựa trên writer cost.

#### Benchmark sạch hơn
- Plan: ổn định SearXNG (tắt mojeek/yep, fallback Brave/Jina), proxy/residential rotation hoặc Brave-first routing.
- Dự kiến rerun trong **24–48h** trên staging.
- ChainLens đồng ý: **State A mặc định**, **9.5 backlog** cho đến khi SCP phê duyệt.
- **2026-08-02:** ChainLens đã chạy focused rerun **6 query × 3 mode = 18 runs** sau khi ổn định SearXNG/Brave:

  | Mode | p95 | NFR-9 target | Kết luận |
  |---|---|---|---|
  | speed | 27.5 s | ≤ 30 s | ✅ PASS |
  | balanced | 44.3 s | ≤ 30 s | ❌ FAIL |
  | deep | 43.7 s | ≤ 60 s | ✅ PASS |

  - `ask` tier ở `quality` vẫn vượt target 30 s của NFR-6.
  - `costDollars` **không còn $0**; benchmark `report-per-mode.md` (2026-08-02, 31 queries) ghi cost thực tế (Nowing `tier=research`): speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519 / call**. `CHAINLENS_QUERY_MICROS_PER_CALL` fallback đã nâng → **60,000 micros (~$0.06)**.
  - Full benchmark **69 query** đang lên lịch để củng cố p95.

## Open Questions / Risks

- **Account model cho self-host:** mỗi instance là một `User` + `Workspace`, hay một license entity mới? Ảnh hưởng đến schema.
- **Authentication:** self-host instance gửi gì đến Nowing Cloud? JWT, static API key, mTLS? *(Có thể tái dụng Nowing PAT/API key model, hoặc tạo key trong bảng `api_keys` của Nowing rồi map đến ChainLens service key.)*
- **Cost-thật writer-only:** `costDollars` mới chỉ tính writer usage. Benchmark 2026-08-02 (`report-per-mode.md`) đã ghi cost thực tế: research speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519**. Full-pipeline aggregation là task 6 "LATER"; ChainLens dự kiến land sau **2–4 sprint** (~2–4 tuần), có thể cao hơn 1.5–2.5×, cần để lại margin.
- **Sponsored runway cost = $0:** chỉ còn trong các benchmark test key cũ. Benchmark `report-per-mode.md` 2026-08-02 đã có cost thực tế.
- **Latency baseline p95:** rerun 2026-08-02 (focused 6×3 runs) cho p95 27.5s/44.3s/43.7s speed/balanced/deep — speed/deep đạt target, balanced vẫn vượt 30 s. State A vẫn là mặc định; full 69-query benchmark đang lên lịch để củng cố p95.
- **Cancel không stop engine:** self-host user cancel trên client vẫn có thể bị charge toàn bộ call. AbortSignal từ disconnect xuống pipeline là follow-up, chưa block 42-1.
- **Snippet đã nhận và lưu:** `nowing_backend/scripts/nowing-sse-contract-snippet.py` chạy mẫu OK.
- **No quota-remaining API:** Nowing Cloud phải tự track hoặc catch 429 từ ChainLens và map sang error tường minh.
- **State sync:** self-host có cần đồng bộ credit balance real-time không, hay định kỳ?
- **Offline mode:** nếu self-host mất kết nối Nowing Cloud, deep research degrade về `engine_unavailable`.
- **Conflict với AD-1:** Nowing là monolith; Nowing Cloud API này nằm trong cùng backend hay cần tách edge? Kiến trúc hiện tại gợi ý mở rộng route trong cùng backend.

## Tasks / Subtasks (draft)

- [x] Cập nhật SSE parser để nhận `costDollars` từ terminal `done.usage` (done — `executor.py` + `test_cost_metering.py`).
- [x] Nhận và lưu snippet `nowing-sse-contract-snippet.py` (done, `nowing_backend/scripts/`).
- [ ] Theo dõi ChainLens full-pipeline cost aggregation (task 6 LATER, dự kiến 2–4 sprint, 1.5–2.5× writer cost).
- [ ] Chạy benchmark e2e từ phía Nowing sau khi ChainLens rerun 24–48h.
- [ ] SCP phê duyệt account/key model, pricing, quota.
- [ ] Thiết kế API `/self-host/research` hoặc `/v1/chainlens/research` cho self-host calls.
- [ ] Schema self-host registration / key (nếu cần migration).
- [ ] Middleware xác thực self-host key và map đến `User` / `Workspace`.
- [ ] Tái sử dụng `_charge_chainlens` trong context self-host (metering, wallet debit, token usage).
- [ ] Rate limit / quota per self-host account.
- [ ] Degradation path khi key thiếu hoặc engine unavailable.
- [ ] Cập nhật `README.md`, `.env.example`, `docs/self-host.md`.
- [ ] Tests integration cho happy path, out-of-credit, rate limit, no key.

## Consistency & Conventions

- Theo `AD-8`: dùng `User.credit_micros_balance` + `TokenUsage.cost_micros`.
- Theo `AD-15`: engine gọi qua HTTP với 1 service key; không end-user auth.
- Theo `AD-16`: docs phân biệt rõ license ba tầng, không gọi engine là OSS.
- Theo `FR-38`: self-host không có engine/key phải degrade, không hard-fail.
- Theo `FR-37`: cost thật từ `costDollars` SSE; fallback flat chỉ khi thiếu.

## References

- `epics.md:628-647` — Story 9.5 gốc và AC nháp.
- `prd.md:642-657` — hai phase deep research (Phase 1/Phase 2) và ràng buộc kiến trúc.
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-8, AD-15, AD-16.
- `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` (companion) — engine boundary.
- `nowing_backend/app/capabilities/chainlens/research/executor.py` — degradation + SSE cost parse.
- `nowing_backend/app/capabilities/core/billing.py` — `_charge_chainlens` wallet logic.
- `nowing_backend/app/services/wallet_credit.py` — wallet primitives.
- `nowing_backend/app/services/token_tracking_service.py` — token usage recording.
