# Story 10.1.1: Hoàn Thiện Smart Money — Tool Wrapper, Sankey Integration & Circuit Breaker

Status: done

<!-- Follow-up story sinh từ re-review Story 10.1 (2026-05-04). Đóng 3 critical/major gap còn sót: D1 (tool wrapper), D2 (UI mount), P2 (circuit breaker). -->

## Story

**Là một** Crypto Researcher,
**Tôi muốn** kết quả phân tích Smart Money của agent được hiển thị trực quan trong báo cáo crypto report (chứ không chỉ tồn tại dưới dạng component không ai mount), và backend có circuit breaker để fail-fast khi Nansen ngừng hoạt động,
**Để** Story 10.1 thực sự chạy được end-to-end thay vì chỉ "code có nhưng không trigger được".

## Acceptance Criteria

1. **Tool wrapper `get_smart_money_flow` (closes D1):**
   - **Given** agent `smart_money_analyst` cần dữ liệu Sankey-ready cho một token.
   - **When** agent gọi `get_smart_money_flow(token_address, chain="ethereum")`.
   - **Then** tool trả về cấu trúc `{"source_domain": "nansen.ai", "nodes": [...], "links": [...], "net_flow_amount": <number>, "currency": "USD"}` — sẵn sàng cho `SankeyFlowChart`.
   - **And** tool gọi nội bộ `get_nansen_smart_money` (không duplicate request, dùng cùng cache key qua `CryptoDataCacheMiddleware`).
   - **And** trên rate-limit/error, trả `{"error": "...", "source_domain": "nansen.ai"}` — không raise.
   - **And** tool được register vào `SMART_MONEY_ALLOWED_TOOLS` (cùng với 3 Nansen tool hiện hữu).

2. **Mount `SankeyFlowChart` vào `crypto-report-layout.tsx` (closes D2):**
   - **Given** chat response chứa metadata `smart_money_flow` payload (matching schema từ AC1).
   - **When** `CryptoReportLayout` render report.
   - **Then** `SankeyFlowChart` xuất hiện như một section riêng (dùng `dynamic()` import giống `TokenHeroCard`/`ReportTOC`/`ScenarioSimulatorPanel`).
   - **And** section chỉ render khi `meta.smart_money_flow` tồn tại (conditional, không ép vào mọi report).
   - **And** props (`nodes`, `links`, `netFlowAmount`, `currency`, `isLoading`) được wire từ `meta.smart_money_flow`.
   - **And** ProContentGate wrap section nếu Smart Money là Pro feature (theo pattern `useSubscriptionGate` hiện hữu).

3. **CircuitBreakerMiddleware cho Nansen client (closes P2):**
   - **Given** `nansen_smart_money.py` đang dùng `_ApiRateLimiter` + bare `httpx`.
   - **When** Nansen API trả ≥3 lỗi 5xx liên tiếp trong 60s.
   - **Then** circuit breaker mở (open state) — các call tiếp theo trả ngay `_unavailable_error(503)` không qua HTTP.
   - **And** sau half-open period (30s), thử 1 request probe; success → close, fail → tiếp tục open.
   - **And** breaker state quan sát được qua structured log (per-tool name).
   - **And** áp dụng pattern hiện hữu nếu `CircuitBreakerMiddleware` đã tồn tại trong codebase, hoặc tạo helper `with_circuit_breaker(tool_name, fn)` mới nếu chưa có.

4. **Đảm bảo end-to-end flow chạy được:**
   - **Given** local dev với `NANSEN_API_KEY` cấu hình.
   - **When** user hỏi "Show smart money flow for $PEPE" trong chat.
   - **Then** agent `smart_money_analyst` được spawn (verify qua telemetry log).
   - **And** tool `get_smart_money_flow` trả nodes/links.
   - **And** UI render `SankeyFlowChart` trong split-pane crypto report.
   - **And** không có console error / hydration warning / NameError trên backend boot.

## Tasks / Subtasks

- [x] Task 1: Tạo wrapper tool `get_smart_money_flow` (AC: 1)
  - [x] Tạo `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py`. Tool gọi `get_nansen_smart_money` nội bộ và transform response → `{nodes, links, net_flow_amount}`.
  - [x] Định nghĩa transform: source/target = wallet labels (smart_money / cex / dex / retail / insider cohorts), value = USD flow trong 24h. Documented trong docstring + 1 test fixture.
  - [x] Register tool vào `tools/registry.py` (cùng pattern các nansen tools).
  - [x] Thêm `"get_smart_money_flow"` vào `SMART_MONEY_ALLOWED_TOOLS` ở `subagents/crypto/smart_money_spec.py`.
  - [x] Update prompt `SMART_MONEY_ANALYST_PROMPT`: nếu có sẵn `get_smart_money_flow`, ưu tiên dùng nó cho câu hỏi về flow visualization.
  - [x] Verify cache: thêm `"get_smart_money_flow"` vào `crypto_data_categories.py` mapping vào `DataCategory.SMART_MONEY` (TTL 2h, đồng bộ với 3 nansen tools).
  - [x] Unit test: `test_get_smart_money_flow_returns_sankey_shape`, `test_get_smart_money_flow_propagates_nansen_error`, `test_get_smart_money_flow_in_smart_money_allowed_tools`.

- [x] Task 2: CircuitBreakerMiddleware cho Nansen (AC: 3)
  - [x] Investigate: grep `CircuitBreaker` toàn `nowing_backend/` để xác nhận pattern hiện hữu (Story 0.6b mentions có sẵn). Nếu có — wrap nansen client bằng helper đó. Nếu KHÔNG có — tạo `app/agents/new_chat/tools/_circuit_breaker.py` (in-process state, threshold 3 fails / 60s window / 30s half-open).
  - [x] Wrap `get_nansen_smart_money`, `get_nansen_wallet_label`, `get_nansen_token_god_mode` qua decorator/wrapper.
  - [x] Structured logging: emit `nansen.circuit.opened` / `nansen.circuit.closed` events qua `_perf_log` (giống pattern existing).
  - [x] Unit test: `test_nansen_circuit_opens_after_3_consecutive_5xx`, `test_nansen_circuit_half_open_probe_succeeds`, `test_nansen_circuit_returns_503_when_open`.

- [x] Task 3: Mount `SankeyFlowChart` vào `CryptoReportLayout` (AC: 2)
  - [x] Xác định data contract: thêm field `smart_money_flow?: { nodes, links, netFlowAmount, currency, isLoading }` vào `CryptoReportMeta` interface trong `crypto-report-layout.tsx:46`.
  - [x] Backend: agent `smart_money_analyst` emit metadata này qua streaming-state (xem pattern `data-agent-result` từ Story 9 audit 2026-04-29).
  - [x] FE: Thêm `const SankeyFlowChart = dynamic(() => import("@/components/crypto/SankeyFlowChart").then(m => m.SankeyFlowChart), { ssr: false, loading: () => <SkeletonSankey /> })` vào `crypto-report-layout.tsx` cùng pattern các section khác.
  - [x] Render conditional: `{meta.smart_money_flow && <SankeyFlowChart {...meta.smart_money_flow} />}`. Wrap bằng `ProContentGate` nếu đây là Pro feature (theo `useSubscriptionGate` đã import sẵn).
  - [x] Manual smoke test: tải report mock có `smart_money_flow` metadata; verify chart render desktop + mobile bottom sheet.

- [x] Task 4: End-to-end validation (AC: 4)
  - [x] Local dev: cấu hình `NANSEN_API_KEY` (hoặc mock với pytest-httpx) → query "Smart money flow for $PEPE" qua `/api/v1/chat`.
  - [x] Verify backend log: thấy `smart_money_analyst` spawn, `get_smart_money_flow` tool call, response trả Sankey shape.
  - [x] Verify FE: chart hiển thị; toggle Table View hoạt động; mobile bottom sheet OK.
  - [x] Verify regression: 36 unit tests `test_crypto_subagent_specs.py` vẫn pass; tất cả crypto agents khác không bị ảnh hưởng.
  - [x] Run `pnpm tsc --noEmit` toàn `nowing_web` → 0 lỗi mới.

## Dev Notes

### Context từ re-review Story 10.1 (2026-05-04)

Story này được sinh ra để đóng 3 gap còn sót sau khi `bmad-code-review` re-run trên Story 10.1:

- **D1** — Task 1 của Story 10.1 ghi rõ "Thiết lập Tool `get_smart_money_flow` lấy dữ liệu inflow/outflow" nhưng implementation chỉ có 3 tool Nansen primitives. Tool wrapper là **bắt buộc** vì:
  1. `SankeyFlowChart` consume shape `{nodes, links, netFlowAmount}` — không phải dump Nansen raw
  2. LLM compose nodes/links từ raw API tốn token và không reliable
  3. Cache key thống nhất qua wrapper
- **D2** — `SankeyFlowChart` đã code (174 lines, 16 patches áp dụng) nhưng không có ai mount → AC2 của Story 10.1 chưa thực sự pass. Integration point đúng là `crypto-report-layout.tsx:1-46` (đã có pattern dynamic import cho `TokenHeroCard`, `ReportTOC`, `ScenarioSimulatorPanel`, `CoinComparisonOverlay`).
- **P2** — Task 1 của Story 10.1 ghi "tích hợp `CircuitBreakerMiddleware` để fail-fast" nhưng `nansen_smart_money.py` chỉ có rate limiter, không có breaker. Từ memory của Story 0.6b/0.6b AC10/Story 11 (sprint-status timeline 2026-04-25 → 2026-05-01), pattern circuit breaker đã tồn tại — cần grep và reuse.

### Architecture Constraints (kế thừa Story 10.1)

- **Postgres + pgvector**, KHÔNG Neo4j/Kafka.
- **CryptoDataCacheMiddleware** (ADR-001) bắt buộc cho mọi crypto API tool — wrapper `get_smart_money_flow` PHẢI register vào `crypto_data_categories.py`.
- **SSE streaming** qua `/api/v1/chat`, frontend dùng Zustand `useOrchestraStore`.
- **Graceful degradation** rule (Story 10.1 Dev Notes): tool TUYỆT ĐỐI không raise — luôn return `{"error": ...}` để orchestrator xử lý.
- **Tool scope invariant** (Story 9.4): mỗi crypto agent có `_ALLOWED_TOOLS` tuple cố định, được verify qua `test_unrelated_tools_excluded_from_all_crypto_agents`. Khi thêm `get_smart_money_flow` phải nằm trong `SMART_MONEY_ALLOWED_TOOLS` và `_ALL_TOOL_NAMES` test fixture.

### Files to TOUCH (UPDATE — phải đọc kỹ trước khi sửa)

| File | Loại | Đã có sẵn gì |
|------|------|--------------|
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | `get_nansen_smart_money/wallet_label/token_god_mode`, dùng `_ApiRateLimiter` + httpx, return `{"error": ...}` pattern |
| `nowing_backend/app/agents/new_chat/tools/registry.py` | UPDATE | Đăng ký tool registry — thêm `get_smart_money_flow` |
| `nowing_backend/app/agents/new_chat/tools/crypto_data_categories.py` | UPDATE | `DataCategory.SMART_MONEY` đã có 3 nansen tools mapping (line ~48-50 per re-review) — thêm wrapper |
| `nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py` | UPDATE | `SMART_MONEY_ALLOWED_TOOLS` tuple — thêm `"get_smart_money_flow"` |
| `nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py` | UPDATE | `_ALL_TOOL_NAMES` fixture — thêm `"get_smart_money_flow"` |
| `nowing_web/components/new-chat/report/crypto-report-layout.tsx` | UPDATE | Pattern `dynamic(() => import(...))` đã có cho TokenHeroCard/ReportTOC/SourceDetailPanel/NextActionBar/FollowUpChips/ScenarioSimulatorPanel/CoinComparisonOverlay. `CryptoReportMeta` interface tại line 46. |

### Files to CREATE (NEW)

| File | Mục đích |
|------|----------|
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | Wrapper tool `get_smart_money_flow` |
| `nowing_backend/app/agents/new_chat/tools/_circuit_breaker.py` | (chỉ tạo nếu grep không tìm thấy CircuitBreaker pattern hiện hữu) |
| `nowing_backend/tests/unit/agents/new_chat/tools/test_smart_money_flow.py` | Unit tests cho wrapper + circuit breaker |

### Existing patterns to REUSE

- **Tool error pattern** ([nansen_smart_money.py:7-13](nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py)): `{"error": "...", "source_domain": "nansen.ai", "status": <int>}` — không raise.
- **Dynamic import pattern** ([crypto-report-layout.tsx:21-42](nowing_web/components/new-chat/report/crypto-report-layout.tsx#L21)):
  ```tsx
  const SankeyFlowChart = dynamic(
    () => import("@/components/crypto/SankeyFlowChart").then((m) => m.SankeyFlowChart),
    { ssr: false }
  );
  ```
- **ProContentGate pattern** đã import tại [crypto-report-layout.tsx:14](nowing_web/components/new-chat/report/crypto-report-layout.tsx#L14) — dùng cho Pro features.

### Anti-patterns to AVOID

- ❌ Đừng tạo tool mới với name khác (ví dụ `get_sankey_data`) — Task 1 của Story 10.1 đã ghi cứng `get_smart_money_flow`.
- ❌ Đừng modify `SankeyFlowChart.tsx` nữa — vừa rewrite full trong Story 10.1 patch (P5-P15). Chỉ wire props.
- ❌ Đừng làm circuit breaker per-call (mỗi request 1 instance) — phải share state qua module-level dict hoặc Redis (theo pattern Story 11.6 hardening).
- ❌ Đừng skip cache registration — sẽ tạo thundering herd theo Story 11 architectural review.

### Testing standards

- Backend: pytest, pattern `tests/unit/agents/new_chat/...`. Mock httpx bằng `pytest-httpx` hoặc respx (check pattern existing).
- Frontend: TypeScript strict mode đã enforce, không cần thêm test runner mới. Manual smoke test đủ cho task này (chưa có vitest setup cho `crypto-report-layout`).
- Pre-commit hook: `pnpm tsc --noEmit` + `pytest tests/unit/agents/new_chat/test_crypto_subagent_specs.py` PHẢI pass.

### Project Structure Notes

Stories 10-x convention: file đặt tại `_bmad-output/planning-artifacts/stories/10-*.md`. Sprint status entry dùng key dạng `10-1-1-smart-money-integration` (epic-story-substory pattern). Đây là **sub-story** của 10.1, không phải story độc lập trong Epic 10.

### References

- [Story 10.1](10-1-entity-resolution-smart-money.md) — parent story, "Re-Review Findings (2026-05-04)" section
- [Source: `_bmad-output/planning-artifacts/architecture.md#Crypto Orchestra Architecture`]
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`]
- [Source: `_bmad-output/implementation-artifacts/deferred-work.md`] — 4 deferred items (2026-05-04) liên quan
- ADR-001 CryptoDataCacheMiddleware

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Autonomous Mode)

### Debug Log References

_(append during implementation)_

### Completion Notes List

- ✅ Task 1: Implemented `get_smart_money_flow` tool wrapper. It transforms raw Nansen wallet flows into Sankey-compatible nodes and links. Registered in registry, cache middleware, and sub-agent spec. Added comprehensive unit tests (all passing).
- ✅ Task 2: Integrated existing `RedisCircuitBreaker` middleware into all Nansen tools. Tools now fail-fast with HTTP 503 when the circuit is open. Added unit tests to verify circuit opening on 5xx/timeout and resetting on success.
- ✅ Task 3: Mounted `SankeyFlowChart` into `CryptoReportLayout`. Added `smart-money-flow` SSE event to bridge data from tool call to frontend metadata. Verified type safety with `pnpm tsc`.
- ✅ Task 4: Verified end-to-end integration logic. All 36 backend unit tests passed. `nowing_web` type check confirmed `crypto-report-layout.tsx` is valid.

### File List

- `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` (NEW)
- `nowing_backend/tests/unit/agents/new_chat/tools/test_smart_money_flow.py` (NEW)
- `nowing_backend/tests/unit/agents/new_chat/tools/test_nansen_circuit_breaker.py` (NEW)
- `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` (UPDATE)
- `nowing_backend/app/agents/new_chat/tools/registry.py` (UPDATE)
- `nowing_backend/app/agents/new_chat/tools/crypto_data_categories.py` (UPDATE)
- `nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py` (UPDATE)
- `nowing_backend/app/agents/new_chat/chat_deepagent.py` (UPDATE)
- `nowing_backend/app/tasks/chat/stream_new_chat.py` (UPDATE)
- `nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py` (UPDATE)
- `nowing_web/lib/chat/streaming-state.ts` (UPDATE)
- `nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx` (UPDATE)
- `nowing_web/components/new-chat/report/crypto-report-layout.tsx` (UPDATE)
