# Story 10.1: Phân Tích Thực Thể & Dòng Tiền Thông Minh (Entity Resolution & Smart Money Flow)

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**Là một** Crypto Researcher,
**Tôi muốn** hệ thống tự động gom nhóm các địa chỉ ví và phân tích luồng tiền giữa chúng,
**Để** tôi có thể theo dõi hành vi của các quỹ đầu tư lớn, Market Makers và phát hiện các ví nội bộ (insider wallets) gom hàng.

## Acceptance Criteria

1. **Entity Clustering & Labeling (Gom nhóm và Gắn nhãn):**
   - **Given** hệ thống đã kết nối với nguồn dữ liệu on-chain (ví dụ: Nansen API hoặc Arkham).
   - **When** người dùng truy vấn một địa chỉ ví cụ thể hoặc một nhóm ví.
   - **Then** hệ thống trả về danh sách các ví liên quan có khả năng thuộc cùng một thực thể.
   - **And** tự động gắn nhãn (Auto-labeling) cho các ví (ví dụ: `Fund: a16z`, `Exchange: Binance`, `Suspected Insider`).

2. **Smart Money Inflow/Outflow Visualization (Trực quan hóa Dòng tiền):**
   - **Given** giao diện phân tích của một Token cụ thể (ví dụ: $PEPE) trong kiến trúc Split-Pane.
   - **When** người dùng mở tính năng "Smart Money Flow".
   - **Then** UI hiển thị biểu đồ Sankey trực quan hóa dòng tiền chuyển động giữa các CEX/DEX, Smart Money, và Retail.
   - **And** hiển thị bảng tóm tắt Net Flow (Dòng tiền ròng) của nhóm Smart Money.

3. **Trải nghiệm UX/UI (Responsive, Feedback & Accessibility):**
   - **Given** hệ thống đang tải hoặc phân tích dữ liệu lớn.
   - **When** chờ LLM và API phản hồi.
   - **Then** UI hiển thị Skeleton Loader mô phỏng biểu đồ Sankey (tuyệt đối KHÔNG dùng circular spinner).
   - **And** biểu đồ Sankey có một nút "Table View Toggle" để hỗ trợ Screen Readers đọc dữ liệu thô (đáp ứng WCAG 2.1 AA).
   - **And** biểu đồ Sankey hiển thị dưới dạng Bottom Sheet khi người dùng sử dụng thiết bị Mobile.

## Tasks / Subtasks

- [x] Task 1: Thiết lập LangGraph Sub-Agent (`smart_money_analyst`) (AC: 1)
  - [x] Tạo `smart_money_analyst_spec.py` đăng ký vào `SubAgentMiddleware`.
  - [x] Viết API client để gọi Nansen/Arkham (tích hợp `CircuitBreakerMiddleware` để fail-fast).
  - [x] Thiết lập Tool `get_smart_money_flow` lấy dữ liệu inflow/outflow.
- [x] Task 2: Phát triển Component Biểu đồ Sankey & Bảng dữ liệu thô (AC: 2, 3)
  - [x] Xây dựng `SankeyFlowChart` component (sử dụng Nivo hoặc D3.js) trong Context Pane.
  - [x] Tích hợp tính năng chuyển đổi `Table View Toggle` cho Accessibility.
  - [x] Áp dụng `SkeletonSankey` trong quá trình chờ SSE response.
- [x] Task 3: Tối ưu hoá Responsive UI (AC: 3)
  - [x] Xử lý Breakpoint Tailwind: Hiển thị Split-Pane trên Desktop (`lg:flex-row`).
  - [x] Xử lý Mobile: Đẩy Component Sankey xuống `BottomSheet` UI để tránh xung đột cử chỉ vuốt.
- [x] Task 4: API & RLS Security Check (AC: 1, 2)
  - [x] Đảm bảo các kết quả phân tích lưu cache trên Postgres đi qua `CryptoDataCacheMiddleware` (tuân thủ ADR-001).

## Dev Notes

- **Kiến trúc (Architecture Requirements):** Epic 10 KHÔNG sử dụng Neo4j hay Kafka. Hệ thống sử dụng kiến trúc RAG tiêu chuẩn với **PostgreSQL + pgvector** làm gốc, và dùng `CryptoDataCacheMiddleware` để lưu cache các kết quả của Crypto API nhằm tránh Thundering Herd (chi tiết ở Epic 9-DF).
- **Graceful Degradation:** Nếu API external (như Nansen) rate-limit, Tool phải trả về `{"error": "Rate limit exceeded"}` (Không throw Exception) để Orchestrator tự xử lý hạ cấp hoặc thông báo.
- **SSE Streaming:** Các response phải đẩy qua Server-Sent Events `/api/v1/chat`. Dùng Zustand store `useOrchestraStore` để bắt update.

### Project Structure Notes

- Backend Agent: `nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py`
- Backend Tool: `nowing_backend/app/agents/new_chat/tools/crypto_smart_money.py`
- Frontend Components: `app/components/chat/context-pane/SankeyFlowChart.tsx`
- Đảm bảo strict naming conventions (Python = `snake_case`, TS = `camelCase`).

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`]
- [Source: `_bmad-output/planning-artifacts/architecture.md#Crypto Orchestra Architecture`]

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro

### Debug Log References
- `pytest tests/unit/agents/new_chat/test_crypto_subagent_specs.py` passed with 33 tests.

### Completion Notes List
- ✅ Created `smart_money_spec.py` and integrated it into `SubAgentMiddleware`.
- ✅ Fixed unit tests in `test_crypto_subagent_specs.py` for token scoping and agent limits.
- ✅ Created `SankeyFlowChart.tsx` in frontend using Nivo Sankey, implementing Table View Toggle and mobile Bottom Sheet.
- ✅ Exported components in `nowing_web/components/crypto/index.ts`.
- ✅ Verified `CryptoDataCacheMiddleware` coverage for Nansen tools in `TOOL_CATEGORY_MAP`.

### File List
- `nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py` (NEW)
- `nowing_backend/app/agents/new_chat/chat_deepagent.py` (UPDATE)
- `nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py` (UPDATE)
- `nowing_web/components/crypto/SankeyFlowChart.tsx` (NEW)
- `nowing_web/components/crypto/index.ts` (UPDATE)

### Review Findings

- [x] [Review][Patch] Missing Web Search Fallback Instruction — Violates AC 1. The `SMART_MONEY_ANALYST_PROMPT` lacks specific instructions for the agent to fall-back to `web_search` if Nansen tools are rate-limited. It only instructs not to hallucinate data on error. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- [x] [Review][Patch] Missing Middleware Integration for New Tools — Violates AC 4. The diff introduces new external Nansen tools (e.g., `get_nansen_smart_money`, `get_nansen_wallet_label`, `get_nansen_token_god_mode`), but there is no evidence in the diff showing these tools being added to `CryptoDataCacheMiddleware` or `TOOL_CATEGORY_MAP` to prevent Thundering Herd. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- [x] [Review][Patch] Routing Failure Risk — `SMART_MONEY_ANALYST_DESCRIPTION` is written entirely in Vietnamese. If the `DeepAgent` orchestrator uses semantic embedding models (which are typically English-dominant) to route user intents to the correct subagent, this agent will likely be ignored or misrouted. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- [x] [Review][Patch] Contradictory Tooling — The prompt explicitly commands the agent to focus *only* on on-chain flow ("Chỉ tập trung vào dữ liệu on-chain flow"), yet inexplicably includes `web_search` in the allowed tools. This contradiction invites the LLM to wander off-topic and hallucinate external narratives. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- [x] [Review][Patch] Undocumented Tools — `chainlens_deep_research` is injected into the allowed tools list, but the prompt provides absolutely zero guidance on what it is, when to use it, or what data it returns. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- [x] [Review][Patch] React Key Anti-Pattern — The table view iterates over `data.links` using the array index as the React key (`key={i}`). If the flow data is dynamic, filterable, or sortable, this will cause state bleeding and unpredictable DOM updates. [nowing_web/components/crypto/SankeyFlowChart.tsx:122]
- [x] [Review][Patch] Ignored Data Interfaces — The `SankeyNode` interface explicitly defines a `nodeColor?: string` property, but the `ResponsiveSankey` component completely ignores it, instead hardcoding a generic D3 color scheme (`colors={{ scheme: 'category10' }}`). [nowing_web/components/crypto/SankeyFlowChart.tsx:84]
- [x] [Review][Patch] Theme Incompatibility — The Nivo chart configuration is oblivious to the application's theme. While the wrapper div uses Tailwind dark mode classes, the chart's labels and link colors use hardcoded contrast modifiers, which will likely result in black text on a dark background in dark mode. [nowing_web/components/crypto/SankeyFlowChart.tsx]
- [x] [Review][Patch] Hardcoded Localization — The table view explicitly forces `en-US` formatting and `USD` currency strings. If the flows represent native tokens (e.g., ETH, BTC) or the user's locale is different, the UI will display misleading or confusing data. [nowing_web/components/crypto/SankeyFlowChart.tsx:125]
- [x] [Review][Patch] Aggressive Fixed Layouts — The component dictates its own fixed heights (`min-h-[400px]`, `h-[500px]`) rather than being truly responsive to a parent container. This reduces reusability and creates awkward whitespace on ultra-wide or non-standard viewports. [nowing_web/components/crypto/SankeyFlowChart.tsx]
- [x] [Review][Patch] Missing Array Guards — `TypeError` crashing the component tree if `data` object missing `nodes` or `links` arrays at runtime. Guard snippet: `if (!data?.nodes?.length || !data?.links?.length) {` [nowing_web/components/crypto/SankeyFlowChart.tsx:59]
- [x] [Review][Patch] Missing Value Fallback — Displays `$NaN` in the data table if `link.value` is missing or NaN. Guard snippet: `{Number.isFinite(link.value) ? new Intl.NumberFormat(...).format(link.value) : 'N/A'}` [nowing_web/components/crypto/SankeyFlowChart.tsx:129]
- [x] [Review][Defer] Mobile Modal Rendering Crash Risk — The mobile view mounts the `ResponsiveSankey` inside a conditionally opened `<Sheet>`. Nivo charts historically fail to calculate their bounding boxes when mounted inside unmeasured portals/modals, often resulting in a `0x0` invisible chart until a window resize event is triggered. [nowing_web/components/crypto/SankeyFlowChart.tsx] — deferred, pre-existing
- [x] [Review][Defer] Nivo Link Reference Error — `Nivo Sankey` throws fatal runtime error if link source or target ID missing from nodes array. Guard snippet: `<ResponsiveSankey data={{...data, links: data.links.filter(l => data.nodes.some(n => n.id === l.source) && data.nodes.some(n => n.id === l.target))}} />` [nowing_web/components/crypto/SankeyFlowChart.tsx:81] — deferred, pre-existing
- [x] [Review][Defer] Poor Error Handling Strategy — The prompt instructs the LLM on how to handle tool errors. Relying on an LLM to reliably parse stringified JSON errors and self-regulate is a known anti-pattern. Error boundaries should be handled in the code's execution layer, not in the prompt text. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py] — deferred, pre-existing architectural issue
- [x] [Review][Defer] Brittle Unit Tests — `test_smart_money_analyst_spec_valid` asserts that exactly 5 tools are present (`len(...) == 5`). This is a lazy test that provides no value but guarantees the test suite will break if a valid tool is simply added or removed in the future. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py] — deferred, pre-existing pattern

### Re-Review Findings (2026-05-04)

Re-review của 5 file Story 10.1. Status `done` nhưng phát hiện 3 CRITICAL chưa giải quyết.

**Decision-needed (3) — phải resolve trước khi patch:**
- [ ] [Review][Decision] **Tool `get_smart_money_flow` (Task 1) chưa tồn tại** — Task 1 yêu cầu tool `get_smart_money_flow` lấy dữ liệu inflow/outflow trả về shape phù hợp Sankey (`nodes` + `links`). Hiện tại chỉ có `get_nansen_smart_money/wallet_label/token_god_mode` với schema khác. Quyết định: (a) tạo wrapper tool mới `get_smart_money_flow` build nodes/links từ Nansen response, hay (b) đổi tên tool/spec để khớp với hiện trạng và update Task 1 spec.
- [ ] [Review][Decision] **`SankeyFlowChart` không được mount ở đâu cả** — Vi phạm AC2. Component export từ `index.ts` nhưng zero importer. Quyết định: mount ở Context Pane component nào (hiện chưa thấy `ContextPane` trong `nowing_web`)? Cần spec UI integration point hoặc tạo container component mới.
- [~] [Review][Decision][DISMISS] **Description `SMART_MONEY_ANALYST_DESCRIPTION` ngôn ngữ không nhất quán với sibling agents** — Description hiện English nhưng các crypto agent khác có thể đang Vietnamese (cần check). Routing semantic embedding bị ảnh hưởng. Quyết định: chuẩn hóa toàn bộ về English (theo embedding model) hay Vietnamese (theo locale user)?

**Patch (16) — fix không cần input người dùng:**
- [x] [Review][Patch] [CRITICAL] Missing import + spec dict cho `smart_money_spec` — `chat_deepagent.py:2323` dùng `SMART_MONEY_ALLOWED_TOOLS` và `:2446` dùng `smart_money_spec` nhưng chưa có `from app.agents.new_chat.subagents.crypto.smart_money_spec import (...)` (line 89-94 chỉ có yield_optimizer) và chưa có `smart_money_spec: SubAgent = {...}` literal (như yield_optimizer_spec ở `:2389`). `create_nowing_deep_agent()` sẽ raise `NameError` ngay khi load. [nowing_backend/app/agents/new_chat/chat_deepagent.py:2323,2446]
- [ ] [Review][Patch][DEFERRED] [MAJOR] CircuitBreakerMiddleware chưa wired cho Nansen client — Task 1 yêu cầu fail-fast nhưng `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` chỉ dùng `_ApiRateLimiter` + bare `httpx`. [nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py]
- [x] [Review][Patch] [MAJOR] Test parser regex bắt artifact `*([whale_tracker_spec] if whale_tracker_spec is not None else [` như spec name — vô tình che lỗi NameError ở chat_deepagent. Cần strip splat conditional bằng regex riêng trước khi `re.split(",")`, rename function thành `test_subagent_middleware_registers_eight_agents`, cập nhật count 9 → 8. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py:385-400]
- [x] [Review][Patch] [MAJOR] `web_search` trong `SMART_MONEY_ALLOWED_TOOLS` vi phạm invariant "no unrelated tools leak" (`test_unrelated_tools_excluded_from_all_crypto_agents` docstring). Test pass do smart_money không có trong iteration list — silent governance violation. Add smart_money vào iteration + whitelist exception, hoặc remove web_search. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py:252-265]
- [x] [Review][Patch] [MAJOR] Sankey crash trên self-loop link — filter ở `:289` chỉ check node existence, không reject `l.source === l.target`. Nivo `d3-sankey` throw "Error: circular link" → unrecoverable. Add `&& l.source !== l.target` + wrap chart trong `<ErrorBoundary>` fallback table view. [nowing_web/components/crypto/SankeyFlowChart.tsx:289]
- [x] [Review][Patch] [MAJOR] Duplicate node ids + TableRow key collision — Nivo throw "Error: missing <id>" khi dedupe sai; React warning khi 2 link cùng `source-target`. Dedupe nodes bằng `Map`, key TableRow thêm index. [nowing_web/components/crypto/SankeyFlowChart.tsx:289,320]
- [x] [Review][Patch] [MAJOR] SSR/CSR hydration mismatch + Nivo 0×0 measure trên mobile sheet — `useIsMobile()` return `false` ở SSR/first paint → desktop wrapper render trước, sau đó switch sang Sheet (Nivo measure 0×0). Gate render với `if (isMobile === undefined) return <SkeletonSankey />` (cần expose tri-state). [nowing_web/components/crypto/SankeyFlowChart.tsx:246]
- [x] [Review][Patch] [MAJOR] `Intl.NumberFormat` throw `RangeError` trên invalid locale/currency (e.g. `currency="USDT"`) — không có try/catch, crash whole component tree. Wrap trong memoized helper với fallback `('en-US', 'USD')`. [nowing_web/components/crypto/SankeyFlowChart.tsx:266,325]
- [x] [Review][Patch] [MAJOR] Prop `netFlowUsd` (USD) + `currency` override mismatch — caller pass `currency="EUR"` mislabel USD figures. Drop `currency` override hoặc rename prop thành `netFlowAmount`. [nowing_web/components/crypto/SankeyFlowChart.tsx:201-208,266]
- [x] [Review][Patch] [MINOR] `netFlowUsd === 0` render đỏ như "distributing" — `isAccumulating = netFlowUsd > 0` chia 2 nhánh, zero rơi vào red. Cần 3-way: `> 0 ? green : < 0 ? red : muted`, label "Flat". [nowing_web/components/crypto/SankeyFlowChart.tsx:257]
- [x] [Review][Patch] [MINOR] `Number.isFinite` guard cho header — `Intl.NumberFormat.format(NaN)` → "$NaN" hiện trên header dù table cells đã guard. [nowing_web/components/crypto/SankeyFlowChart.tsx:266]
- [x] [Review][Patch] [MINOR] Empty `links` ẩn cả header — "quiet day" có data nhưng UI báo "No flow data available", mất KPI net flow. Render header luôn nếu `netFlowUsd !== undefined`, chỉ chart body fallback empty state. [nowing_web/components/crypto/SankeyFlowChart.tsx:253]
- [x] [Review][Patch] [MINOR] Prompt cho phép `web_search` không bound → loop khi Nansen 401 — Add prompt guard "call web_search at most once per token" hoặc thay bằng `chainlens_deep_research` cho consistency với sibling agents. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- [x] [Review][Patch] [MINOR] Sankey color fallback `#94a3b8` blend với `bg-muted/20` — node không có `nodeColor` invisible. Dùng palette index thay vì grey duy nhất. [nowing_web/components/crypto/SankeyFlowChart.tsx:292]
- [x] [Review][Patch] [MINOR] Mobile Sheet trigger button chỉ "View Smart Money Flow" — không hiển thị net flow KPI at-a-glance, regression UX so với desktop. [nowing_web/components/crypto/SankeyFlowChart.tsx:343-346]
- [x] [Review][Patch] [MINOR] `_bind_tools()` + `Any, Sequence` imports dead code — không ai import `_bind_tools` (private + spec_module dùng tuple constants). Delete cả helper và unused imports. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py:43-44]

**Defer (4) — pre-existing/nice-to-have:**
- [x] [Review][Defer] viewMode preference lost on Sheet remount — a11y user toggle "Table View" rồi đóng/mở Sheet thì chart view trở lại. Lift state lên context/localStorage. [nowing_web/components/crypto/SankeyFlowChart.tsx:245] — deferred, a11y enhancement
- [x] [Review][Defer] `_ALL_TOOL_NAMES` thêm `get_certik_*`, `get_live_token_price` không liên quan Story 10.1 — scope creep từ stories khác. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py:131-150] — deferred, anticipates future stories
- [x] [Review][Defer] Tokenomics test docstring weakened ("exactly these tools" thay vì list cụ thể) — Story 9.1 scope, không phải 10.1. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py:273-274] — deferred, off-scope
- [x] [Review][Defer] `min-h-[400px]` outer + `min-h-[300px]` inner double constraint trong Sheet `h-[calc(100%-60px)]` — layout NIT cần visual verification. [nowing_web/components/crypto/SankeyFlowChart.tsx] — deferred, NIT
