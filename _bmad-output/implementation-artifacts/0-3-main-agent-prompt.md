# Story 0.3: Main Agent Orchestration Prompt Update

Status: done

## Story

As a main agent (Nowing),
I want clear instructions in my system prompt on when and how to spawn crypto sub-agents in parallel,
so that I can coordinate multiple specialists efficiently without unnecessary overhead for simple queries.

## Acceptance Criteria

1. **[AC-1: Parallel Orchestration — Full Analysis]**
   Given user yêu cầu "Phân tích toàn diện token $X" (hoặc tương tự),
   When main agent xử lý request,
   Then system prompt có instruction gọi đồng thời 3-4 agents phù hợp (ví dụ: `defillama_analyst` + `sentiment_analyst` + `news_analyst` + `smart_contract_analyst`),
   And response tổng hợp kết quả từ tất cả agents trước khi trả về user.

2. **[AC-2: Lookup Table]**
   System prompt có lookup table format:
   `agent_name | chuyên môn | trigger keywords`
   covering all 4 base agents: `defillama_analyst`, `sentiment_analyst`, `news_analyst`, `smart_contract_analyst`.

3. **[AC-3: Concrete parallel task() Examples]**
   System prompt có ví dụ `task()` calls — ít nhất 1 ví dụ multi-agent và 1 ví dụ single-agent.
   Note: `task()` notation là **pseudocode cho LLM reasoning** (không phải executable Python) — agent name không có quotes là intentional.

4. **[AC-4: Simple Query — No Multi-Agent Overhead]**
   Given user hỏi câu đơn giản "Giá $BTC hôm nay?" (hoặc tương tự),
   When main agent xử lý,
   Then main agent KHÔNG spawn multi-agent — chỉ gọi `get_live_token_data` trực tiếp,
   And response nhanh, không overhead từ parallel spawn.

5. **[AC-5: Section isolation]**
   Crypto orchestration instructions được đặt trong section riêng (`<crypto_orchestration>` tag) trong `NOWING_SYSTEM_INSTRUCTIONS`,
   không override hoặc conflict với các sections hiện tại (`knowledge_base_only_policy`, `memory_protocol`).

6. **[AC-6: Token budget]**
   Crypto section mới không tăng tổng token count của `NOWING_SYSTEM_INSTRUCTIONS` quá 300 tokens (giữ prompt cost tối thiểu).

## Tasks / Subtasks

- [x] **Task 1: Phân tích current state & xác định insertion point** (AC: 5)
  - [x] 1.1 Đọc toàn bộ `NOWING_SYSTEM_INSTRUCTIONS` trong `system_prompt.py` để hiểu cấu trúc hiện tại
  - [x] 1.2 Xác định vị trí tối ưu để chèn `<crypto_orchestration>` section (sau `memory_protocol` block)
  - [x] 1.3 Confirm không có crypto mentions nào đã tồn tại trong file (tránh duplicate)

- [x] **Task 2: Viết nội dung `<crypto_orchestration>` section** (AC: 1, 2, 3, 4, 6)
  - [x] 2.1 Viết lookup table với 4 agents (name | expertise | trigger keywords)
  - [x] 2.2 Viết decision logic: khi nào spawn multi-agent vs. gọi tool trực tiếp
  - [x] 2.3 Viết parallel `task()` example cho full analysis (3-4 agents)
  - [x] 2.4 Viết single-agent example cho simple price query
  - [x] 2.5 Verify token count ≤ 300 tokens (dùng tiktoken hoặc estimate thủ công)

- [x] **Task 3: Apply changes vào `system_prompt.py`** (AC: 5)
  - [x] 3.1 Chèn `<crypto_orchestration>` block vào cuối `NOWING_SYSTEM_INSTRUCTIONS`, trước closing `</system_instruction>` tag
  - [x] 3.2 Giữ nguyên tất cả nội dung hiện tại (không modify `knowledge_base_only_policy`, `memory_protocol`)

- [x] **Task 4: Smoke test manual** (AC: 1, 4)
  - [x] 4.1 Grep verify crypto section đã có trong file
  - [x] 4.2 `python -c "from app.agents.new_chat.system_prompt import NOWING_SYSTEM_INSTRUCTIONS; print('OK')"` — không có import errors
  - [x] 4.3 Kiểm tra visually rằng lookup table format đúng và `task()` examples có pseudocode format đúng (agent name không có quotes là intentional — đây là LLM reasoning instructions, không phải executable Python)

- [x] **Task 5: Unit test** (AC: 2, 3, 5)
  - [x] 5.1 Thêm test case vào test file của `system_prompt.py` (hoặc tạo mới nếu chưa có)
  - [x] 5.2 Test: `"crypto_orchestration"` in `NOWING_SYSTEM_INSTRUCTIONS`
  - [x] 5.3 Test: tất cả 4 agent names xuất hiện trong section
  - [x] 5.4 Test: `"task("` pattern xuất hiện trong section (parallel call example present)

## Dev Notes

### Scope & Approach

Story này **chỉ modify 1 file**: `nowing_backend/app/agents/new_chat/system_prompt.py`.

Mục tiêu: thêm 1 section `<crypto_orchestration>` vào cuối `NOWING_SYSTEM_INSTRUCTIONS` constant. Không refactor, không rename, không thay đổi function signatures.

### Current System Prompt Structure

`NOWING_SYSTEM_INSTRUCTIONS` hiện có (theo thứ tự):
1. Identity: "You are Nowing, a reasoning and acting AI agent..."
2. `<knowledge_base_only_policy>` — CRITICAL RULE về KB-first
3. `<memory_protocol>` — update_memory instruction

→ Thêm `<crypto_orchestration>` section **sau** `</memory_protocol>` và **trước** `</system_instruction>`.

### 4 Registered Agents (confirmed từ Story 0.2)

| Agent Name | File | Expertise |
|------------|------|-----------|
| `defillama_analyst` | `subagents/crypto/defillama_spec.py` | DeFi TVL, yields, protocols, stablecoins, bridges |
| `sentiment_analyst` | `subagents/crypto/sentiment_spec.py` | Fear & Greed Index, Reddit community sentiment |
| `news_analyst` | `subagents/crypto/news_spec.py` | Crypto news, CoinGecko token info |
| `smart_contract_analyst` | `subagents/crypto/smart_contract_spec.py` | Token security, contract info |

### Suggested `<crypto_orchestration>` Content

```xml
<crypto_orchestration>
CRYPTO ANALYSIS — AGENT ORCHESTRATION GUIDE:

When user requests crypto analysis, use the specialist agents below via task() calls.

AGENT LOOKUP TABLE:
| Agent                  | Expertise                                      | Trigger Keywords                              |
|------------------------|------------------------------------------------|-----------------------------------------------|
| defillama_analyst      | DeFi TVL, yields, protocols, stablecoins       | DeFi, TVL, yield farm, protocol, bridge       |
| sentiment_analyst      | Fear & Greed Index, Reddit sentiment           | sentiment, market mood, fear, greed, community|
| news_analyst           | Crypto news, token fundamentals (CoinGecko)    | news, event, launch, token info, fundamentals |
| smart_contract_analyst | Token security, contract audit, rug-pull check | security, contract, audit, rug, scam, token   |

DECISION RULE:
- Simple price/data query ("Giá $BTC?") → call get_live_token_data directly, NO sub-agents.
- Comprehensive/multi-dimensional query → spawn relevant agents in PARALLEL (same response).

PARALLEL TASK EXAMPLE (full analysis of token $X):
task(defillama_analyst, "Analyze DeFi metrics for token $X")
task(sentiment_analyst, "Get sentiment signals for $X")
task(news_analyst, "Latest news and fundamentals for $X")
task(smart_contract_analyst, "Security audit for contract address 0x...")

SINGLE-AGENT EXAMPLE (simple query):
# User: "Giá $ETH hiện tại?" → get_live_token_data(symbol="ETH") directly.

IMPORTANT: Always spawn multiple task() calls in the SAME response to maximize parallelism.
</crypto_orchestration>
```

### Token Budget Check

Estimated token count của section trên: ~230-260 tokens (well within ≤ 300 limit).

### Files to NOT Modify

- **`_SYSTEM_INSTRUCTIONS_SHARED`** (lines 54–89 trong `system_prompt.py`) — constant này nằm cùng file, có cấu trúc XML giống hệt `NOWING_SYSTEM_INSTRUCTIONS` nhưng dùng cho team thread prompt. **KHÔNG được touch.** Chỉ modify `NOWING_SYSTEM_INSTRUCTIONS` (lines 18–51).
- `NOWING_TOOLS_INSTRUCTIONS` / `NOWING_CITATION_INSTRUCTIONS` — unrelated
- `chat_deepagent.py` — đã được modify ở Story 0.2 (sub-agent wiring)
- Bất kỳ spec files nào trong `subagents/crypto/` — đã implement ở Story 0.2

### Format-String Safety

`NOWING_SYSTEM_INSTRUCTIONS` được interpolate bằng `.format(resolved_today=resolved_today)` (xem `build_nowing_system_prompt()` trong cùng file). **KHÔNG dùng ký tự `{` hoặc `}` trong nội dung `<crypto_orchestration>`** — Python sẽ raise `KeyError` lúc runtime nếu có bất kỳ `{...}` nào không phải `{resolved_today}`.

### Testing Approach

Unit test nhẹ (string assertions) đủ để verify story này. Story 0.4 (API Integration Tests) và Story 0.5 (Parallel Execution Validation) sẽ test behavior thực tế.

Nếu chưa có test file cho `system_prompt.py`, tạo `tests/agents/new_chat/test_system_prompt.py`.

### Project Structure Notes

- **File cần modify**: `nowing_backend/app/agents/new_chat/system_prompt.py`
- **Naming**: Section tag `<crypto_orchestration>` consistent với existing XML-style tags trong file (`<knowledge_base_only_policy>`, `<memory_protocol>`)
- **No new files**: Story này không tạo file mới nào

### References

- Story 0.2 (Base Sub-Agents): `_bmad-output/planning-artifacts/stories/0-2-base-sub-agents.md` — danh sách 4 agents và specs đã implemented
- Epic 0 spec (Story 2.6/0.3): `_bmad-output/planning-artifacts/crypto-subagents-epics.md#Story-0.3`
- Epics.md Story 0.3: `_bmad-output/planning-artifacts/epics.md` (line 764-786)
- Current system prompt: `nowing_backend/app/agents/new_chat/system_prompt.py` (lines 17-50)
- DeFiLlama agent spec: `nowing_backend/app/agents/new_chat/subagents/crypto/defillama_spec.py`
- FR9 (orchestration requirement): `_bmad-output/planning-artifacts/crypto-subagents-epics.md#FR9`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

N/A — implementation straightforward, no blockers.

### Completion Notes List

- Task 2 content taken directly from Dev Notes suggested content (already well-designed)
- Format-string safety: `<crypto_orchestration>` content uses no `{...}` placeholders — safe with `.format(resolved_today=...)` interpolation
- `_SYSTEM_INSTRUCTIONS_SHARED` confirmed untouched (verified via automated test)
- Token count estimated ~230-260 tokens (well within ≤300 budget)
- Import test used `importlib.util.spec_from_file_location` to bypass `__init__.py` chain (which depends on `deepagents` package not installed in test env)

### File List

- `nowing_backend/app/agents/new_chat/system_prompt.py` (modified)
- `nowing_backend/tests/unit/agents/new_chat/test_system_prompt.py` (created + updated in review)

### Review Findings

_Code review: 2026-04-24 (3 adversarial reviewers + acceptance auditor, review_mode=full)_

- [x] [Review][Patch] Test file dùng relative cwd path → CI break [tests/unit/agents/new_chat/test_system_prompt.py] — Fixed: anchored path via `Path(__file__).resolve().parents[4]`, removed private-attr import; 7/7 tests pass from both backend cwd and repo root.
- [x] [Review][Patch] Test coupling đến `_SYSTEM_INSTRUCTIONS_SHARED` (private attribute) [tests/unit/agents/new_chat/test_system_prompt.py] — Fixed: replaced module import with file-text regex scan; scoped agent-name assertions to `<crypto_orchestration>` body; parametrized 4 agents; task() pattern now matches `task(<identifier>` not just `task(`.
- [x] [Review][Defer] Weak assertion scoping (original tests) — fixed inline as part of Patch #2.
- [x] [Review][Defer] `get_live_token_data` chưa register trong `_TOOL_INSTRUCTIONS` [app/agents/new_chat/system_prompt.py] — deferred, pre-existing drift from Story 0.1; covered by Story 0.4.
- [x] [Review][Defer] Shared team-thread prompt thiếu crypto orchestration [`_SYSTEM_INSTRUCTIONS_SHARED`] — deferred, requires product decision.
- [x] [Review][Defer] Working-tree leak Story 0.2 files — deferred, housekeeping.

**Acceptance Auditor verdict**: ACCEPT — all 6 ACs pass; token budget ~250-290 (within ≤300).
