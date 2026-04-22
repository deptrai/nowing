---
storyId: 9.1
storyTitle: Tokenomics Analyst Sub-Agent
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
phase: Phase 1 — Quality Foundation
sprintPlan: _bmad-output/planning-artifacts/sprints/sprint-plan-phase1-crypto-orchestra.md
relatedFRs: [FR27, FR33, FR34, FR35]
relatedNFRs: [NFR-CS1, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
priority: P0 (Phase 1)
estimatedEffort: 3 days (Tue-Thu Week 1)
status: ready-for-dev
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 9.1: Tokenomics Analyst Sub-Agent

## User Story

**As a** crypto investor,
**I want** a specialist agent that analyzes token economics deeply,
**So that** I can evaluate long-term value accrual and inflation risks.

---

## 🚨 CRITICAL PREREQUISITE — Code Reality Check (verified 2026-04-23)

> **Code audit phát hiện Epic 0 (Crypto Foundation) CHƯA implement:**
>
> - ❌ `nowing_backend/app/agents/new_chat/subagents/crypto/` — **directory rỗng**
> - ❌ `chat_deepagent.py:472` — chỉ có `general_purpose_spec` được wired
> - ❌ Crypto tools chưa tồn tại: `defillama.py`, `crypto_sentiment.py`, `crypto_news.py`, `contract_analysis.py`
> - ✅ Chỉ có: `chainlens_research.py`, `crypto_realtime.py` (DexScreener)
>
> **Epic 0 đã được thêm vào `epics.md` làm prerequisite formal**. Story 9.1 KHÔNG thể start cho đến khi:
> 1. ✅ Epic 0 Story 0.1 DONE (4 tool files + registry)
> 2. ✅ Epic 0 Story 0.2 DONE (4 base sub-agent specs + SubAgentMiddleware wiring)
> 3. ✅ Epic 0 Story 0.3 DONE (main agent orchestration prompt)
> 4. ✅ Epic 0 testing (0.4-0.6) DONE (validate foundation works)
>
> **Timeline estimate**: Epic 0 (~2-3 weeks) → Epic 0 testing 0.4-0.6 (~1 week) → Story 9.1 start

### Pre-flight Checklist

Trước khi bắt đầu Story 9.1, Dev phải verify:

- [ ] Epic 0.1 DONE — `defillama.py`, `crypto_sentiment.py`, `crypto_news.py`, `contract_analysis.py` tồn tại, 11 tools registered
- [ ] Epic 0.2 DONE — 4 base specs (`defillama_spec`, `sentiment_spec`, `news_spec`, `smart_contract_spec`) trong `subagents/crypto/`
- [ ] Epic 0.2 DONE — `chat_deepagent.py` wire 5 sub-agents (general + 4 crypto) trong `SubAgentMiddleware`
- [ ] Epic 0.3 DONE — main agent system prompt có crypto orchestration section
- [ ] Epic 0 testing (Stories 0.4-0.6) DONE — API integration, parallel execution, error handling

**Nếu BẤT KỲ item nào FAIL** → STOP, không start Story 9.1. Escalate lên Dev Lead để finalize prerequisite chain.

---

## Context for Dev Agent

### Architectural Background

Nowing sử dụng [deepagents](https://github.com/langchain-ai/deepagents) (LangGraph-based) với `SubAgentMiddleware` pattern. Main agent điều phối multiple sub-agents chạy song song qua `task()` tool trong cùng 1 LangGraph ToolNode.

**Key files để hiểu trước khi code:**
- `nowing_backend/app/agents/new_chat/chat_deepagent.py:437-477` — nơi wire sub-agents
- `nowing_backend/docs/crypto-subagents-guide.md` — full implementation guide đã document từ trước
- `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` — reference cho Chainlens tool usage

### SubAgent TypedDict Structure

```python
from deepagents import SubAgent

my_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "tokenomics_analyst",
    "description": "...",  # optional, hiển thị trong task() tool docs
    "prompt": TOKENOMICS_SYSTEM_PROMPT,  # < 500 tokens (NFR-CS1)
    "model": llm,  # inject từ chat_deepagent.py runtime
    "tools": [...],  # scoped tool list
    "middleware": gp_middleware,  # shared stack
}
```

### gp_middleware (đã có, tận dụng)

Từ `chat_deepagent.py:438-448`, middleware stack gồm:
- `TodoListMiddleware()`
- `_memory_middleware`
- `NowingFilesystemMiddleware(...)`
- `create_summarization_middleware(llm, StateBackend)`
- `PatchToolCallsMiddleware()`
- `AnthropicPromptCachingMiddleware(...)`

**Story 9.1 reuse nguyên stack này** — không custom gì.

---

## Deliverables

### 📄 Files to Create

#### 1. `nowing_backend/app/agents/new_chat/subagents/crypto/tokenomics_spec.py` (~50 LOC)

**Purpose**: Define `tokenomics_analyst` sub-agent spec (name + system prompt only — model/tools/middleware inject at runtime).

**Structure reference** (follow pattern từ `crypto-subagents-guide.md`):

```python
"""Tokenomics Analyst sub-agent spec."""

TOKENOMICS_ANALYST_NAME = "tokenomics_analyst"

TOKENOMICS_ANALYST_DESCRIPTION = (
    "Specialist agent for deep token economics analysis: supply, vesting, "
    "distribution, inflation/deflation mechanics. Use when user asks about "
    "tokenomics, long-term value, vesting schedule, or token distribution."
)

# NOTE: System prompt MUST be < 500 tokens (NFR-CS1). Verify với tiktoken:
# import tiktoken
# enc = tiktoken.encoding_for_model("gpt-4")
# assert len(enc.encode(TOKENOMICS_ANALYST_PROMPT)) < 500
TOKENOMICS_ANALYST_PROMPT = """You are tokenomics_analyst — a specialist in crypto token economics.

For any token query, analyze:
1. **Supply**: circulating vs total vs max supply (from get_coingecko_token_info)
2. **Vesting**: schedule, cliff dates, linear vs stepped unlocks (from chainlens_deep_research)
3. **Distribution**: % breakdown (team/investors/community/treasury/public sale)
4. **Economics**: inflation/deflation mechanics, burn mechanisms, staking rewards
5. **Pressure**: buy pressure (utility, demand) vs sell pressure (unlocks, emissions)

**Rules (strict):**
- ALWAYS cite source from tool output. NEVER fabricate numbers.
- If a data point is not in tool output, say "not available" — do NOT guess.
- Prefer exact figures over rounded estimates.
- If chainlens_deep_research returns {"status": "fallback"}, use CoinGecko data only and note limitation.

**Output format:**
📊 Supply Overview | 📅 Vesting Schedule | 🥧 Distribution | 🔄 Economics | ⚖️ Buy/Sell Pressure | 💡 Key Insights

Keep response concise (< 500 words). Structured bullets preferred over prose.
"""
```

---

### 📝 Files to Modify

#### 2. `nowing_backend/app/agents/new_chat/chat_deepagent.py`

**Change location**: Around line 450-472 (sub-agent specs + SubAgentMiddleware registration)

**Required changes:**

a) **Import** (top of file):
```python
from app.agents.new_chat.subagents.crypto.tokenomics_spec import (
    TOKENOMICS_ANALYST_NAME,
    TOKENOMICS_ANALYST_DESCRIPTION,
    TOKENOMICS_ANALYST_PROMPT,
)
```

b) **Scope tools** (after existing tool list assembly):
```python
# Tokenomics analyst scoped tools — deterministic CoinGecko + Chainlens research supplementary
tokenomics_tools = [
    tool for tool in tools
    if tool.name in ("get_coingecko_token_info", "chainlens_deep_research")
]
```

c) **Create spec** (after `general_purpose_spec`):
```python
tokenomics_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": TOKENOMICS_ANALYST_NAME,
    "description": TOKENOMICS_ANALYST_DESCRIPTION,
    "prompt": TOKENOMICS_ANALYST_PROMPT,
    "model": llm,
    "tools": tokenomics_tools,
    "middleware": gp_middleware,
}
```

d) **Register in SubAgentMiddleware** (replace line 472):
```python
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        # ... 4 Epic 0.2 specs (defillama, sentiment, news, smart_contract) phải có sẵn ...
        tokenomics_analyst_spec,  # Story 9.1
    ],
),
```

#### 3. Main agent orchestration prompt

**Location**: `nowing_backend/app/agents/new_chat/system_prompt.py` (47KB — find crypto-related lookup table section)

**Add entry** vào lookup table (format follow existing entries):
```
| tokenomics_analyst | Token supply, vesting, distribution, inflation analysis | "tokenomics of X", "vesting schedule", "long-term value", "token distribution" |
```

---

## Acceptance Criteria

### AC1: Sub-agent spec created + wired

**Given** Story 9.1 implementation done
**When** inspect `nowing_backend/app/agents/new_chat/subagents/crypto/`
**Then** file `tokenomics_spec.py` exists với 3 constants: `TOKENOMICS_ANALYST_NAME`, `TOKENOMICS_ANALYST_DESCRIPTION`, `TOKENOMICS_ANALYST_PROMPT`

**And** `chat_deepagent.py` imports và register `tokenomics_analyst_spec` trong `SubAgentMiddleware`
**And** server khởi động không error

### AC2: System prompt token budget (NFR-CS1)

**Given** `TOKENOMICS_ANALYST_PROMPT` constant
**When** đếm tokens bằng `tiktoken` (encoding `cl100k_base` hoặc `gpt-4`)
**Then** token count **< 500**
**And** có test assertion (unit test) verify điều này:
```python
def test_tokenomics_prompt_under_budget():
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4")
    assert len(enc.encode(TOKENOMICS_ANALYST_PROMPT)) < 500
```

### AC3: Tool scoping (security + context isolation)

**Given** `tokenomics_analyst_spec["tools"]`
**When** inspect tool names
**Then** agent CHỈ có access 2 tools: `get_coingecko_token_info` và `chainlens_deep_research`
**And** agent **KHÔNG có access** tới: `knowledge_base_search`, `generate_report`, các crypto tools khác (defillama, goplus, cryptopanic)
**And** có test verify:
```python
def test_tokenomics_tool_scoping():
    # Build tokenomics_tools list as in chat_deepagent.py
    assert [t.name for t in tokenomics_tools] == [
        "get_coingecko_token_info",
        "chainlens_deep_research",
    ]
```

### AC4: Stateless tools (NFR-CS4)

**Given** tool registry entries cho `get_coingecko_token_info` và `chainlens_deep_research`
**When** inspect registry
**Then** cả 2 tools có `requires=[]` trong `ToolDefinition`
**And** agent có thể spawn fresh mỗi request không cần session/DB context

### AC5: Functional — Agent spawn successfully

**Given** main agent nhận câu hỏi "Phân tích tokenomics của $UNI"
**When** main agent gọi `task(agent="tokenomics_analyst", task="...")`
**Then** sub-agent được spawn và trả về response có cấu trúc:
- 📊 Supply section với circulating/total/max
- 📅 Vesting section (hoặc "not available" nếu data không có)
- 🥧 Distribution %
- 🔄 Economics (inflation/deflation)
- ⚖️ Pressure analysis
- 💡 Insights

**And** response luôn cite source từ tool output
**And** không chứa số liệu fabricated

### AC6: Parallel execution (NFR-Q2)

**Given** 5 agents được spawn đồng thời (4 Epic 0.2 base agents + tokenomics_analyst)
**When** main agent gọi parallel `task()` tools trong 1 LangGraph ToolNode step
**Then** all 5 agents start trong cùng 1 graph step (verify qua trace logs)
**And** `total_time / max(individual_time)` < 1.3x

### AC7: Accuracy baseline (NFR-Q1) + Hallucination (NFR-Q2)

**Given** QA sample 50 tokenomics queries trên tokens phổ biến (BTC, ETH, UNI, AAVE, SOL, ARB, OP, MATIC, LINK, AVAX)
**When** QA team cross-check factual claims vs raw CoinGecko API response
**Then** factual error rate **< 3%**
**And** hallucination rate (số liệu không có trong tool output) **< 1%**

### AC8: Graceful degradation (NFR-Q3)

**Given** Chainlens service unavailable (trả `{"status": "fallback"}`)
**When** tokenomics_analyst được query
**Then** agent vẫn trả response dựa trên CoinGecko data only
**And** response note rõ: "Vesting details not available" hoặc tương tự
**And** không crash, không hallucinate vesting info

---

## Definition of Done (8 checkpoints)

- [ ] **DoD-1** Pre-flight: Epic 0 artifacts verified exist trong repo
- [ ] **DoD-2** `tokenomics_spec.py` created, 3 constants exported
- [ ] **DoD-3** `chat_deepagent.py` imports + wires `tokenomics_analyst_spec`
- [ ] **DoD-4** System prompt < 500 tokens (unit test pass)
- [ ] **DoD-5** Tool scoping enforced (unit test pass — only 2 tools)
- [ ] **DoD-6** Integration test: 5-agent parallel spawn works, parallelism ratio logged
- [ ] **DoD-7** QA: 50-query sample passed accuracy <3% + hallucination <1%
- [ ] **DoD-8** Main agent system prompt updated với lookup table entry

---

## Dev Notes

### Testing Commands

```bash
# Run unit tests cho story này
cd nowing_backend
uv run pytest tests/unit/agents/new_chat/subagents/crypto/test_tokenomics_spec.py -v

# Run integration test với parallel spawn
uv run pytest tests/integration/agents/test_crypto_parallel_spawn.py -v

# Token count verification manually
uv run python -c "
import tiktoken
from app.agents.new_chat.subagents.crypto.tokenomics_spec import TOKENOMICS_ANALYST_PROMPT
enc = tiktoken.encoding_for_model('gpt-4')
count = len(enc.encode(TOKENOMICS_ANALYST_PROMPT))
print(f'Token count: {count} / 500')
assert count < 500, f'Prompt exceeds 500 tokens: {count}'
"
```

### Common Pitfalls

1. ❌ **KHÔNG** wire agent ở module-level globals — phải inject `llm` + `tools` runtime từ `create_deepagent()` factory
2. ❌ **KHÔNG** hardcode tool names — use registry lookup để survive tool renaming
3. ❌ **KHÔNG** bypass middleware stack — phải reuse `gp_middleware` để consistent behavior
4. ❌ **KHÔNG** quên `# type: ignore[typeddict-unknown-key]` comment — `SubAgent` TypedDict có fields optional
5. ⚠️ **Chainlens fallback**: agent phải handle `{"status": "fallback"}` gracefully, không crash

### Related Files (for reference)

- `nowing_backend/app/agents/new_chat/chat_deepagent.py` — wiring location
- `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` — tool usage pattern
- `nowing_backend/docs/crypto-subagents-guide.md` — Epic 0 implementation guide (spec blueprints)
- `nowing_backend/tests/unit/agents/new_chat/tools/test_chainlens_research_tool.py` — test pattern reference

---

## Rollback Plan

Nếu Story 9.1 cause production issues:

1. **Feature flag** (recommended): wrap `tokenomics_analyst_spec` registration trong env check `CRYPTO_ORCHESTRA_PHASE1_ENABLED`
2. **Git revert**: single commit touching 2-3 files → easy revert
3. **Monitoring**: watch `parallelism_ratio` + `agent_error_rate` trong canary — nếu spike, auto-disable feature flag

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR27 Tokenomics Analyst | `prd.md` Line ~293 | AC1, AC5 |
| FR33 Parallel Orchestration | `prd.md` | AC6 |
| FR35 Graceful Degradation | `prd.md` | AC8 |
| NFR-CS1 Token Budget | `prd.md` + `epics.md` | AC2 |
| NFR-CS4 Stateless Tools | `prd.md` + `epics.md` | AC4 |
| NFR-Q1 Accuracy <3% | `prd.md` Quality Gates | AC7 |
| NFR-Q2 Parallelism <1.3x | `prd.md` Quality Gates | AC6 |
| NFR-Q3 Graceful Degradation >98% | `prd.md` Quality Gates | AC8 |
| NFR-Q4 Hallucination <1% | `prd.md` Quality Gates | AC7 |

---

**Status**: ready-for-dev ✅ (blocked on Pre-flight Checklist)
**Next**: Dev verify Epic 0 state → if OK, start Week 1 Tuesday → if NOT OK, escalate to Dev Lead
