---
storyId: 0.2
storyTitle: Base Sub-Agents Implementation & Wiring
epicParent: epic-00-crypto-foundation
dependsOn: [Story 0.1]
blocks: [Story 0.3, Story 0.4, Epic 9 Phase 1]
relatedFRs: [crypto-subagents-epics FR6-FR9]
relatedNFRs: [NFR-CS1, NFR-CS2, NFR-CS4]
priority: P0 (BLOCKING)
estimatedEffort: 1 week
status: ready-for-dev (blocked on 0.1)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 0.2: Base Sub-Agents Implementation & Wiring

## User Story

**As a** main agent,
**I want** 4 base crypto sub-agents registered (`defillama_analyst`, `sentiment_analyst`, `news_analyst`, `smart_contract_analyst`),
**So that** I can spawn specialists in parallel qua `task()` tool when user requests crypto analysis.

---

## Context

Story 0.1 implements 11 crypto tools. Story 0.2 wraps tools thành **4 specialist sub-agents** với scoped tool access và optimized system prompts (< 500 tokens each).

Reference blueprint: `nowing_backend/docs/crypto-subagents-guide.md` (section "Bước 3: Tạo SubAgent specs").

---

## Deliverables

### 📄 Files to Create (5 files)

#### 1. `nowing_backend/app/agents/new_chat/subagents/crypto/__init__.py`

Empty file để mark directory là Python package.

#### 2-5. Spec files cho 4 base agents

Mỗi file export 3 constants theo pattern Story 9.1:

| File | Agent Name | Scoped Tools |
|------|-----------|--------------|
| `defillama_spec.py` | `defillama_analyst` | 5 DeFiLlama tools + `get_live_token_data` (DexScreener) + `chainlens_deep_research` |
| `sentiment_spec.py` | `sentiment_analyst` | `get_cmc_sentiment`, `get_reddit_crypto_sentiment`, `chainlens_deep_research` |
| `news_spec.py` | `news_analyst` | `get_crypto_news`, `get_coingecko_token_info`, `chainlens_deep_research` |
| `smart_contract_spec.py` | `smart_contract_analyst` | `get_contract_info`, `check_token_security`, `chainlens_deep_research` |

**Each file structure** (template):

```python
"""<Agent Name> sub-agent spec."""

DEFILLAMA_ANALYST_NAME = "defillama_analyst"

DEFILLAMA_ANALYST_DESCRIPTION = (
    "Specialist for DeFi market analysis: TVL, yields, protocol breakdown, "
    "stablecoins, bridges. Use when user asks about DeFi, TVL, yield farms, "
    "or specific DeFi protocols."
)

# NFR-CS1: prompt < 500 tokens (verify với tiktoken)
DEFILLAMA_ANALYST_PROMPT = """You are defillama_analyst — a DeFi market specialist.

For DeFi queries:
1. Use get_defillama_protocol for single-protocol deep dive
2. Use get_defillama_tvl_overview for market landscape
3. Use get_defillama_yields for yield opportunities
4. Use chainlens_deep_research for context that DeFiLlama doesn't have

Rules:
- ALWAYS cite TVL/APY numbers from tool output. NEVER fabricate.
- Convert TVL to human-readable: $1.5B not 1500000000.
- Flag risks: low TVL (<$1M), unaudited, recent exploits.

Output format:
📊 Key Metrics | 🔗 Chain Distribution | 📈 Trend (1d/7d) | 💡 Insights | ⚠️ Risk
"""
```

(Tương tự cho `sentiment_spec.py`, `news_spec.py`, `smart_contract_spec.py` — mỗi cái có structure phù hợp domain.)

---

### 📝 Files to Modify

#### 1. `nowing_backend/app/agents/new_chat/chat_deepagent.py` (~line 437-477)

**Imports** (top of file):
```python
from app.agents.new_chat.subagents.crypto.defillama_spec import (
    DEFILLAMA_ANALYST_NAME, DEFILLAMA_ANALYST_DESCRIPTION, DEFILLAMA_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.sentiment_spec import (
    SENTIMENT_ANALYST_NAME, SENTIMENT_ANALYST_DESCRIPTION, SENTIMENT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.news_spec import (
    NEWS_ANALYST_NAME, NEWS_ANALYST_DESCRIPTION, NEWS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_contract_spec import (
    SMART_CONTRACT_ANALYST_NAME, SMART_CONTRACT_ANALYST_DESCRIPTION, SMART_CONTRACT_ANALYST_PROMPT,
)
```

**Tool scoping logic** (after existing tool list assembly, before `general_purpose_spec`):
```python
defillama_tools = [t for t in tools if t.name in (
    "get_defillama_protocol", "get_defillama_tvl_overview", "get_defillama_yields",
    "get_defillama_stablecoins", "get_defillama_bridges",
    "get_live_token_data", "chainlens_deep_research",
)]

sentiment_tools = [t for t in tools if t.name in (
    "get_cmc_sentiment", "get_reddit_crypto_sentiment", "chainlens_deep_research",
)]

news_tools = [t for t in tools if t.name in (
    "get_crypto_news", "get_coingecko_token_info", "chainlens_deep_research",
)]

smart_contract_tools = [t for t in tools if t.name in (
    "get_contract_info", "check_token_security", "chainlens_deep_research",
)]
```

**Specs** (after `general_purpose_spec`):
```python
defillama_analyst_spec: SubAgent = {
    "name": DEFILLAMA_ANALYST_NAME,
    "description": DEFILLAMA_ANALYST_DESCRIPTION,
    "prompt": DEFILLAMA_ANALYST_PROMPT,
    "model": llm,
    "tools": defillama_tools,
    "middleware": gp_middleware,
}

sentiment_analyst_spec: SubAgent = {
    "name": SENTIMENT_ANALYST_NAME,
    "description": SENTIMENT_ANALYST_DESCRIPTION,
    "prompt": SENTIMENT_ANALYST_PROMPT,
    "model": llm,
    "tools": sentiment_tools,
    "middleware": gp_middleware,
}

news_analyst_spec: SubAgent = {
    "name": NEWS_ANALYST_NAME,
    "description": NEWS_ANALYST_DESCRIPTION,
    "prompt": NEWS_ANALYST_PROMPT,
    "model": llm,
    "tools": news_tools,
    "middleware": gp_middleware,
}

smart_contract_analyst_spec: SubAgent = {
    "name": SMART_CONTRACT_ANALYST_NAME,
    "description": SMART_CONTRACT_ANALYST_DESCRIPTION,
    "prompt": SMART_CONTRACT_ANALYST_PROMPT,
    "model": llm,
    "tools": smart_contract_tools,
    "middleware": gp_middleware,
}
```

**SubAgentMiddleware registration** (replace line 472):
```python
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        defillama_analyst_spec,
        sentiment_analyst_spec,
        news_analyst_spec,
        smart_contract_analyst_spec,
    ],
),
```

---

## Acceptance Criteria

### AC1: Spec files created và export đúng constants

**Given** 4 spec files được tạo
**When** import từng module
**Then** mỗi module export 3 constants: `{NAME}_NAME`, `{NAME}_DESCRIPTION`, `{NAME}_PROMPT`
**And** không SyntaxError/ImportError

### AC2: System prompt token budget (NFR-CS1)

**Given** 4 PROMPT constants
**When** đếm tokens bằng `tiktoken` cho mỗi prompt
**Then** mỗi prompt < 500 tokens
**And** unit test verify cả 4:
```python
@pytest.mark.parametrize("prompt", [
    DEFILLAMA_ANALYST_PROMPT, SENTIMENT_ANALYST_PROMPT,
    NEWS_ANALYST_PROMPT, SMART_CONTRACT_ANALYST_PROMPT,
])
def test_prompts_under_token_budget(prompt):
    enc = tiktoken.encoding_for_model("gpt-4")
    assert len(enc.encode(prompt)) < 500
```

### AC3: Tool scoping enforced

**Given** mỗi sub-agent spec
**When** inspect `spec["tools"]` (list of LangChain Tool objects)
**Then** chỉ chứa tools đúng theo bảng scope ở trên
**And** đặc biệt: `defillama_analyst` không có access tools của smart_contract/sentiment/news

### AC4: SubAgentMiddleware registration

**Given** server khởi động
**When** inspect `SubAgentMiddleware.subagents`
**Then** đúng 5 sub-agents được register: `general_purpose`, `defillama_analyst`, `sentiment_analyst`, `news_analyst`, `smart_contract_analyst`
**And** main agent có thể discover qua `task` tool docs

### AC5: Functional spawn — defillama_analyst

**Given** main agent nhận câu "Phân tích DeFi TVL của Uniswap"
**When** main agent gọi `task(agent="defillama_analyst", task="Get TVL breakdown for Uniswap")`
**Then** sub-agent spawn successfully (không error)
**And** response chứa structured output: 📊 Key Metrics, 🔗 Chain Distribution, 📈 Trend, 💡 Insights, ⚠️ Risk
**And** TVL number cite từ tool output (verify qua trace)

### AC6: Functional spawn — sentiment_analyst

**Given** main agent nhận câu "Sentiment thị trường crypto hiện tại"
**When** main agent gọi `task(agent="sentiment_analyst", ...)`
**Then** sub-agent dùng `get_cmc_sentiment` để lấy Fear & Greed Index
**And** response cho biết F&G value + classification (Extreme Fear / Fear / Neutral / Greed / Extreme Greed)

### AC7: Functional spawn — news_analyst

**Given** main agent nhận "Có tin tức gì mới về $UNI?"
**When** main agent gọi `task(agent="news_analyst", task="Recent UNI news")`
**Then** sub-agent dùng `get_crypto_news(currencies="UNI")` + optional `get_coingecko_token_info`
**And** trả về top 5-10 articles với title, source, published_at, sentiment

### AC8: Functional spawn — smart_contract_analyst

**Given** main agent nhận "Kiểm tra security contract 0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
**When** main agent gọi `task(agent="smart_contract_analyst", ...)`
**Then** sub-agent gọi `check_token_security` + optional `get_contract_info`
**And** response có risk_level 🟢/🟡/🔴 + risks_detected list
**And** mention concrete checks: open source, no honeypot, buy/sell tax, holder distribution

### AC9: Parallel execution (NFR-CS2)

**Given** main agent nhận "Phân tích toàn diện $UNI"
**When** main agent gọi parallel `task()` cho 4 agents (defillama + sentiment + news + smart_contract)
**Then** trace logs show all 4 agents start trong cùng 1 LangGraph ToolNode step
**And** `total_time / max(individual_time)` < 1.3x
**And** kết quả tổng hợp được trước khi trả lời user

### AC10: Stateless invariant (NFR-CS4)

**Given** parallel spawn 4 agents
**When** đo behavior
**Then** không có shared state giữa agents
**And** mỗi agent có middleware stack riêng (instance riêng)
**And** không cross-contamination message history

---

## Definition of Done (8 checkpoints)

- [ ] **DoD-1** Story 0.1 verified DONE (precondition)
- [ ] **DoD-2** 5 files created (`__init__.py` + 4 specs)
- [ ] **DoD-3** `chat_deepagent.py` import + wire 4 new specs
- [ ] **DoD-4** Server khởi động không error, `SubAgentMiddleware` có 5 agents
- [ ] **DoD-5** Unit tests: token budget cho 4 prompts (NFR-CS1)
- [ ] **DoD-6** Unit tests: tool scoping cho 4 agents
- [ ] **DoD-7** Integration test: spawn 4 agents parallel, parallelism ratio < 1.3x
- [ ] **DoD-8** Manual smoke test: 1 query thực tế cho mỗi agent (4 queries total) trả về structured output đúng

---

## Dev Notes

### Token Counting Helper

```python
# Add to tests/utils/token_counter.py
import tiktoken

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken."""
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def assert_under_budget(text: str, budget: int = 500, label: str = "prompt"):
    count = count_tokens(text)
    assert count < budget, f"{label} exceeds budget: {count} > {budget}"
```

### Common Pitfalls

1. ❌ **Đừng** import LLM ở module-level — phải runtime inject từ `chat_deepagent.py`
2. ❌ **Đừng** quên `# type: ignore[typeddict-unknown-key]` cho SubAgent dict construction
3. ❌ **Đừng** wire agent với `tools=tools` (full list) — phải scoped lists
4. ⚠️ Chainlens fallback: agents handle `{"status": "fallback"}` gracefully — không treat as error

### Reference Files

- **Blueprint**: `crypto-subagents-guide.md` Section "Bước 3: Tạo SubAgent specs"
- **Pattern**: `chat_deepagent.py:437-477` (existing general_purpose wiring)
- **Story 9.1 spec**: `_bmad-output/planning-artifacts/stories/story-9.1-tokenomics-analyst.md` (similar structure)

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| 4 base crypto sub-agents | `crypto-subagents-guide.md` Step 3 | AC1, AC4 |
| NFR-CS1 Token Budget | `prd.md` + `epics.md` | AC2 |
| NFR-CS2 Parallel Execution | `prd.md` + `epics.md` | AC9 |
| NFR-CS4 Stateless | `prd.md` + `epics.md` | AC3, AC10 |

---

**Status**: done (code review 2026-04-23 — P1 critical fix applied, P2/P3/D1/D2 all addressed; 32 unit tests pass)
**Next**: Story 0.3 (Main Agent Prompt) starts after this DONE.

---

## Review Findings (2026-04-23)

Review target: commit `1d050f72c` (+409/-1, 8 files). Reviewed by 3 adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor).

### decision-needed

- [x] [Review][Decision→Patch] Integration test gap — ĐÃ ADDRESS: thêm `tests/unit/agents/new_chat/test_crypto_subagent_wiring.py` với 15 tests mới cover AC3/AC4/AC10/P1/P3/prompt fidelity (structural). AC5–AC9 functional spawn + parallel ratio tracked in Story 0-4/0-5.
- [x] [Review][Decision→Patch] Shared `gp_middleware` — ĐÃ ADDRESS: thêm `test_each_crypto_spec_uses_fresh_middleware_factory` verify mỗi spec gọi `_build_gp_middleware()` fresh, không share mutable instance.

### patch

- [x] [Review][Patch] **CRITICAL** — `SubAgent` dict dùng key `"prompt"` thay vì `"system_prompt"` [nowing_backend/app/agents/new_chat/chat_deepagent.py:509,517,525,533]. ĐÃ FIX: đổi 4 key thành `"system_prompt"`. Deepagents `SubAgent` TypedDict yêu cầu `system_prompt`; `SubAgentMiddleware.wrap_agent` đọc `spec["system_prompt"]` — nếu không fix sẽ `KeyError` ngay lần gọi đầu.
- [x] [Review][Patch] ~~Tool scoping test là tautology~~ — ĐÃ verify: test hiện tại import `DEFILLAMA_ALLOWED_TOOLS` từ spec files (`test_crypto_subagent_specs.py:12,18,24,30`), không còn duplicate tuple. Constants là single source of truth shared giữa production và test. Đã address trước review.
- [x] [Review][Patch] `chainlens_deep_research` feature-flag guard — ĐÃ ADDRESS: thêm `_perf_log.error(...)` trong `create_nowing_deep_agent` khi `chainlens_deep_research` không có trong registry nhưng 4 crypto agents đang reference nó [chat_deepagent.py:501-512]. Test `test_chainlens_missing_guard_is_present` verify guard tồn tại.

### defer

- [x] [Review][Defer] `news_analyst` prompt reference `sentiment_signal`/`positive_ratio` field [news_spec.py:28] — deferred, cần confirm output shape của `get_crypto_news`.
- [x] [Review][Defer] tiktoken dùng `gpt-4` encoding cho budget test nhưng runtime model có thể là Claude/Gemini [test_crypto_subagent_specs.py:51] — deferred, conservative approximation không phải bug.
- [x] [Review][Defer] Agent name hyphen vs underscore (`general-purpose` vs `defillama_analyst`) — deferred, minor consistency, không block functionality.
- [x] [Review][Defer] `description` length/uniqueness không có test validate [test_crypto_subagent_specs.py:57] — deferred, nice-to-have.
- [x] [Review][Defer] Tool scope filter dùng `t.name` attribute access — deferred, sẽ fail rõ ở chỗ khác nếu registry trả dicts.
