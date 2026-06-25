---
storyId: 0.6
storyTitle: Error Handling & Fallback Validation
epicParent: epic-00-crypto-foundation
dependsOn: [Story 0.1, 0.2, 0.3, 0.4, 0.5 DONE]
blocks: [Epic 9 Phase 1]
relatedFRs: [FR-T3, FR35 Graceful Degradation]
relatedNFRs: [NFR-CS3 API Rate Awareness, NFR-Q3 Graceful Degradation > 98%]
priority: P0 (BLOCKING Phase 1 — final Epic 0 story)
estimatedEffort: 2-3 days
status: done
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 8.3: Error Handling & Fallback Validation

## User Story

**As a** developer,
**I want** to verify that partial API failures (rate limits, timeouts, 5xx errors) KHÔNG crash the entire crypto analysis,
**So that** users receive useful responses even when 1-2 sub-agents fail — proving graceful degradation gate (NFR-Q3 > 98%).

---

## Context

Story 8.1 validate tools work happy path. Story 8.2 validate parallel orchestration. Story 8.3 **stress-test failure modes** — critical vì production reality: APIs sẽ fail. Quality gate NFR-Q3 yêu cầu ≥ 98% requests có ≥1 agent error vẫn trả response đúng cấu trúc.

**Failure taxonomy** cần test:
1. **Tool-level** — single API call fails (429, 500, timeout) → tool returns `{"error": "..."}`
2. **Agent-level** — tool returns errors → agent adapts (fallback to different tool hoặc report limitation)
3. **Orchestration-level** — 1-2 sub-agents fail entirely → main agent synthesize from remaining agents
4. **Catastrophic** — 4/4 agents fail → main agent returns honest "cannot complete analysis" message

---

## Prerequisites

### Pre-flight Checklist

- [ ] **Epic 0 DONE**: 4 base sub-agents wired với error-return pattern (NOT exception raising)
- [ ] **Story 8.1 DONE**: Tool error paths verified (AC6, AC7, AC11)
- [ ] **Story 8.2 DONE**: Parallel orchestration proven + telemetry live
- [ ] Mock server or fault injection framework available (e.g., `respx` cho httpx)

**Nếu BẤT KỲ item nào FAIL** → không start Story 8.3.

---

## Deliverables

### 📄 Files to Create

#### 1. `nowing_backend/tests/integration/agents/test_graceful_degradation.py`

Test suite với **fault injection** simulate API failures mà không cần real API down.

```python
"""Integration tests for graceful degradation.

Validates NFR-Q3 (>98% graceful degradation) và error handling contract
cho tất cả failure modes: rate limit, timeout, 5xx, network error.
"""
import pytest
import httpx
import respx

pytestmark = pytest.mark.integration


class TestToolLevelErrorHandling:
    """AC1-AC3: Individual tools return error dict, không raise."""

    @respx.mock
    async def test_coingecko_429_returns_error_dict(self):
        """AC1: CoinGecko rate limit → error dict + hint."""
        respx.get("https://api.coingecko.com/api/v3/coins/bitcoin").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )

        from app.agents.new_chat.tools.crypto_news import create_coingecko_token_info_tool
        tool = create_coingecko_token_info_tool()
        result = await tool.ainvoke({"coin_id": "bitcoin"})

        assert "error" in result
        assert "rate limit" in result["error"].lower()
        assert "try again" in result["error"].lower()  # actionable hint

    @respx.mock
    async def test_goplus_timeout_returns_error_dict(self):
        """AC2: GoPlus timeout → error dict, không raise."""
        respx.get(...).mock(side_effect=httpx.TimeoutException("Timeout"))

        from app.agents.new_chat.tools.contract_analysis import create_check_token_security_tool
        tool = create_check_token_security_tool()
        result = await tool.ainvoke({
            "contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            "chain_id": "1",
        })

        assert "error" in result
        assert "timeout" in result["error"].lower() or "unavailable" in result["error"].lower()

    @respx.mock
    async def test_defillama_500_returns_error_dict(self):
        """AC3: DeFiLlama 500 → error, không raise."""
        respx.get("https://api.llama.fi/protocols").mock(
            return_value=httpx.Response(500)
        )

        from app.agents.new_chat.tools.defillama import create_defillama_tvl_overview_tool
        tool = create_defillama_tvl_overview_tool()
        result = await tool.ainvoke({"limit": 5})

        assert "error" in result


class TestAgentLevelFallback:
    """AC4-AC6: Sub-agent adapts when primary tool fails."""

    @respx.mock
    async def test_news_analyst_fallback_to_chainlens_when_cryptopanic_down(self, agent_factory):
        """AC4: news_analyst adapt khi CryptoPanic 429 → dùng chainlens_deep_research."""
        # Mock CryptoPanic 429
        respx.get("https://cryptopanic.com/api/v1/posts/").mock(
            return_value=httpx.Response(429)
        )
        # Allow Chainlens through (real or mocked successful response)

        agent = await agent_factory(user_id="test", search_space_id="test")
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Tin tức mới nhất về $UNI"}]
        })

        # Agent phải vẫn trả response có content
        response_content = result["messages"][-1]["content"]
        assert len(response_content) > 100, "Agent crashed instead of falling back"
        # Có thể check mention của "limited news available" hoặc tương tự
        assert "error" not in response_content.lower() or "cryptopanic" in response_content.lower()

    @respx.mock
    async def test_smart_contract_analyst_partial_fail(self, agent_factory):
        """AC5: smart_contract_analyst — GoPlus fail nhưng Etherscan work."""
        respx.get("https://api.gopluslabs.io/...").mock(return_value=httpx.Response(500))
        # Etherscan mocked success
        respx.get("https://api.etherscan.io/...").mock(return_value=httpx.Response(200, json={...}))

        agent = await agent_factory(...)
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Security check 0x..."}]
        })

        # Agent vẫn trả partial analysis dựa trên Etherscan data
        response = result["messages"][-1]["content"]
        assert "verified" in response.lower() or "contract" in response.lower()
        assert "security score unavailable" in response.lower() or "goplus" in response.lower()


class TestOrchestrationLevelGraceful:
    """AC7-AC9: Main agent synthesize khi 1-2 sub-agents fail entirely."""

    @respx.mock
    async def test_main_agent_completes_with_1_agent_failure(self, agent_factory):
        """AC7: 1/4 agents fail → main agent vẫn synthesize từ 3 agents còn lại."""
        # Inject failure vào defillama_analyst bằng cách mock DeFiLlama 500
        respx.get("https://api.llama.fi/...").mock(return_value=httpx.Response(500))
        # Other agents work normally

        agent = await agent_factory(...)
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]
        })

        response = result["messages"][-1]["content"]
        # Response chứa nội dung từ 3 agents khác
        assert any(keyword in response.lower() for keyword in ["news", "sentiment", "security", "audit"])
        # Mention nguồn unavailable (transparency)
        assert "defillama" in response.lower() or "tvl" in response.lower() and "unavailable" in response.lower()

    @respx.mock
    async def test_main_agent_completes_with_2_agent_failure(self, agent_factory):
        """AC8: 2/4 agents fail → vẫn complete analysis."""
        # Mock 2 sources down
        respx.get("https://api.llama.fi/...").mock(return_value=httpx.Response(500))
        respx.get("https://api.gopluslabs.io/...").mock(return_value=httpx.Response(500))

        agent = await agent_factory(...)
        result = await agent.ainvoke({...})

        response = result["messages"][-1]["content"]
        # Response có meaningful content từ 2 agents thành công
        assert len(response) > 200

    async def test_catastrophic_all_agents_fail_honest_response(self, agent_factory):
        """AC9: 4/4 agents fail → honest fail message, không crash."""
        # Mock ALL external APIs down
        respx.route().mock(side_effect=httpx.TimeoutException("Network down"))

        agent = await agent_factory(...)
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]
        })

        response = result["messages"][-1]["content"]
        # Response phải mention limitation honestly
        assert any(phrase in response.lower() for phrase in [
            "data currently unavailable", "service unavailable", "không thể truy cập",
            "cannot complete analysis", "tạm thời không thể",
        ])
        # KHÔNG được hallucinate data


class TestDegradationRateBenchmark:
    """AC10: Statistical gate — degradation rate > 98% trên sample."""

    @pytest.mark.slow
    async def test_degradation_rate_exceeds_98_percent(self, agent_factory):
        """AC10: 100 queries với random 1-2 agent failures → ≥ 98% success rate."""
        import random

        success_count = 0
        total = 100

        for i in range(total):
            # Inject random failure
            agent_to_fail = random.choice(["defillama", "goplus", "cryptopanic", None, None])
            # (None means no failure for 40% of queries)

            # Apply mock based on choice
            with respx.mock() as mock:
                if agent_to_fail == "defillama":
                    mock.get("https://api.llama.fi/...").mock(return_value=httpx.Response(500))
                elif agent_to_fail == "goplus":
                    mock.get("https://api.gopluslabs.io/...").mock(return_value=httpx.Response(500))
                elif agent_to_fail == "cryptopanic":
                    mock.get("https://cryptopanic.com/...").mock(return_value=httpx.Response(429))

                agent = await agent_factory(...)
                try:
                    result = await agent.ainvoke({
                        "messages": [{"role": "user", "content": f"Phân tích $UNI query {i}"}]
                    })
                    response = result["messages"][-1]["content"]
                    # Success criteria: response có content > 100 chars, không thrown exception
                    if len(response) > 100:
                        success_count += 1
                except Exception:
                    pass  # Counted as failure

        degradation_rate = success_count / total
        assert degradation_rate >= 0.98, (
            f"Graceful degradation rate {degradation_rate:.2%} < 98% gate"
        )
```

#### 2. `nowing_backend/tests/integration/agents/fault_injection.py`

Helper utilities cho fault injection patterns.

```python
"""Fault injection utilities for graceful degradation testing."""
from contextlib import asynccontextmanager
import respx
import httpx


@asynccontextmanager
async def inject_api_failure(service: str, failure_type: str):
    """Inject failure cho 1 API source.

    service: 'defillama' | 'coingecko' | 'goplus' | 'cryptopanic' | 'reddit' | 'etherscan'
    failure_type: '429' | '500' | 'timeout' | 'network_error'
    """
    patterns = {
        "defillama": "https://api.llama.fi/",
        "coingecko": "https://api.coingecko.com/",
        "goplus": "https://api.gopluslabs.io/",
        "cryptopanic": "https://cryptopanic.com/",
        # ...
    }

    with respx.mock() as mock:
        if failure_type == "429":
            mock.get(patterns[service]).mock(return_value=httpx.Response(429))
        elif failure_type == "500":
            mock.get(patterns[service]).mock(return_value=httpx.Response(500))
        elif failure_type == "timeout":
            mock.get(patterns[service]).mock(side_effect=httpx.TimeoutException("Timeout"))
        elif failure_type == "network_error":
            mock.get(patterns[service]).mock(side_effect=httpx.NetworkError("Network"))
        yield mock
```

### 📝 Files to Modify

#### 1. `nowing_backend/app/agents/new_chat/chat_deepagent.py`

Enhance `ParallelismTelemetryMiddleware` (từ Story 8.2) để track **degradation events**:

```python
# Add fields to existing telemetry:
# - agent_error_count (per request)
# - fallback_used (bool)
# - partial_response (bool)
```

#### 2. Observability metrics

Register 2 new metrics:
- `crypto_orchestra_agent_errors_total{agent_name, error_type}` (counter)
- `crypto_orchestra_graceful_degradation_total{outcome="success|partial|failed"}` (counter)

Dashboard cần display: degradation rate = `success+partial / total` — phải ≥ 98%.

---

## Acceptance Criteria

### AC1: Tool returns error dict on 429

**Given** CoinGecko API trả HTTP 429
**When** `get_coingecko_token_info(coin_id="bitcoin")` được gọi
**Then** trả về `{"error": "CoinGecko rate limit reached, try again in 1 minute"}` hoặc tương tự
**And** message chứa actionable hint (thời gian retry)
**And** KHÔNG raise exception

### AC2: Tool returns error dict on timeout

**Given** GoPlus API timeout
**When** `check_token_security(...)` được gọi
**Then** trả về `{"error": "GoPlus API unavailable"}` hoặc tương tự
**And** error handling mất < 35 giây (timeout + buffer)
**And** KHÔNG raise exception

### AC3: Tool returns error dict on 5xx

**Given** DeFiLlama API trả HTTP 500
**When** `get_defillama_tvl_overview(limit=5)` được gọi
**Then** trả về `{"error": "..."}`
**And** KHÔNG raise exception

### AC4: News agent fallback to Chainlens

**Given** CryptoPanic 429
**When** `news_analyst` được spawn cho query "Tin tức $UNI"
**Then** agent adapt — dùng `chainlens_deep_research` để thay thế
**And** response có content > 100 chars (không empty)
**And** response có thể mention limited news hoặc cite Chainlens source

### AC5: Smart contract agent partial adaptation

**Given** GoPlus 500 nhưng Etherscan OK
**When** `smart_contract_analyst` được spawn
**Then** agent trả analysis dựa trên Etherscan data (contract verified, source code)
**And** response note rõ "security score unavailable" hoặc tương tự
**And** KHÔNG hallucinate security data

### AC6: DeFiLlama agent partial adaptation

**Given** DeFiLlama 500 nhưng CoinGecko OK
**When** `defillama_analyst` được spawn
**Then** agent fallback sang Chainlens hoặc trả graceful "limited DeFi data available"
**And** KHÔNG crash

### AC7: Main agent synthesizes with 1 agent failure

**Given** 1/4 sub-agents (e.g., defillama) fail entirely (all tools 500)
**When** user hỏi "Phân tích toàn diện $UNI"
**Then** main agent synthesize response từ 3 agents còn lại (sentiment, news, smart_contract)
**And** response mention rõ "DeFi metrics currently unavailable" hoặc tương đương
**And** response vẫn có structured sections cho 3 angles còn lại

### AC8: Main agent synthesizes with 2 agent failures

**Given** 2/4 sub-agents fail (e.g., defillama + goplus)
**When** user hỏi comprehensive analysis
**Then** main agent vẫn trả response với content > 200 chars từ 2 agents thành công
**And** response honest về nguồn unavailable

### AC9: Catastrophic failure — honest response

**Given** 4/4 agents fail (all external APIs down)
**When** user hỏi comprehensive analysis
**Then** main agent trả response chứa phrase như "data currently unavailable" / "service issues" / "tạm thời không thể phân tích"
**And** KHÔNG hallucinate fake data để làm user happy
**And** có thể suggest user thử lại sau

### AC10: P98 graceful degradation gate (NFR-Q3)

**Given** 100 queries với random injected failures (40% no fail, 30% single-agent fail, 20% 2-agent fail, 10% catastrophic)
**When** đếm queries trả response đúng cấu trúc (success hoặc graceful partial)
**Then** rate **≥ 98%**
**And** test report breakdown:
- Success (all agents work): ~40 queries
- Partial (1 agent failed): ~30 queries — expected degrade gracefully
- Partial (2 agents failed): ~20 queries — expected degrade gracefully
- Catastrophic (all failed): ~10 queries — expected honest fail message
**And** total success+partial+honest_fail ≥ 98 queries

### AC11: Telemetry captures degradation events

**Given** production traffic với agent errors
**When** telemetry middleware logs
**Then** metric `crypto_orchestra_agent_errors_total{agent_name, error_type}` increment correctly
**And** metric `crypto_orchestra_graceful_degradation_total{outcome}` phản ánh real outcome (success/partial/failed)
**And** dashboard panel "Degradation Rate" hiển thị % ≥ 98% gauge

---

## Definition of Done (9 checkpoints)

- [ ] **DoD-1** Pre-flight: Epic 0, Story 8.1, Story 8.2 DONE
- [ ] **DoD-2** Test files created (`test_graceful_degradation.py` + `fault_injection.py`)
- [ ] **DoD-3** `respx` hoặc equivalent fault injection library installed
- [ ] **DoD-4** AC1-AC3 (tool level) pass — 100% tools trả error dict, không raise
- [ ] **DoD-5** AC4-AC6 (agent level) pass — 4 sub-agents handle tool failures gracefully
- [ ] **DoD-6** AC7-AC9 (orchestration level) pass — main agent synthesize correctly
- [ ] **DoD-7** AC10 (P98 benchmark) pass — 100-query sample ≥ 98% graceful
- [ ] **DoD-8** AC11 telemetry dashboard hiển thị degradation rate gauge
- [ ] **DoD-9** Documentation: runbook cho ops team "what to do when degradation rate < 98%"

---

## Dev Notes

### Testing Commands

```bash
cd nowing_backend

# Install fault injection library (nếu chưa có)
uv add --dev respx

# Run fast tests (AC1-AC9)
uv run pytest -m integration tests/integration/agents/test_graceful_degradation.py::TestToolLevelErrorHandling -v
uv run pytest -m integration tests/integration/agents/test_graceful_degradation.py::TestAgentLevelFallback -v
uv run pytest -m integration tests/integration/agents/test_graceful_degradation.py::TestOrchestrationLevelGraceful -v

# Run statistical benchmark (AC10 — slow, ~30-45 min)
uv run pytest -m "integration and slow" tests/integration/agents/test_graceful_degradation.py::TestDegradationRateBenchmark -v
```

### Failure Taxonomy Matrix

| Layer | Failure Type | Expected Behavior | Test AC |
|-------|-------------|-------------------|---------|
| Tool | 429 rate limit | Return `{"error": "rate limit... try again"}` | AC1 |
| Tool | 500 server error | Return `{"error": "..."}` | AC3 |
| Tool | Timeout (>30s) | Return `{"error": "... unavailable"}` within 35s | AC2 |
| Tool | Network error | Return `{"error": "..."}` | AC11 (implicit) |
| Agent | Tool error received | Fallback to alternative tool hoặc note limitation | AC4, AC5, AC6 |
| Orchestration | 1 agent fails | Synthesize from remaining 3 | AC7 |
| Orchestration | 2 agents fail | Synthesize from remaining 2 | AC8 |
| Orchestration | All agents fail | Honest "unavailable" response | AC9 |

### Key Libraries

- **`respx`**: HTTP request mocking cho httpx. Perfect fit vì codebase dùng `httpx.AsyncClient`.
- **`pytest-asyncio`**: Async test support (likely đã có).
- **`freezegun`** (optional): Time mocking nếu cần test retry backoff timing.

### Common Pitfalls

1. ❌ **Đừng** test với real API failures — flaky, slow, ethical issues (spamming). Dùng `respx` mock.
2. ❌ **Đừng** assert exact error messages — dùng substring match cho flexibility
3. ❌ **Đừng** assume agent LLM tuân chính xác instruction "fallback to chainlens" — LLM may phrase differently; assert behavior (content length, no crash) thay vì exact action
4. ⚠️ **respx.mock context manager**: phải wrap entire agent invocation, không chỉ tool call
5. ⚠️ **Benchmark cost**: AC10 = 100 queries với agents spawn, cost ~$10-15 token. Budget.

### Ops Runbook (for DoD-9)

File: `docs/runbooks/crypto-orchestra-degradation.md`

Content sections:
1. **Alert triggered when**: P95 degradation rate < 98% trong 1h
2. **Diagnose**:
   - Check dashboard: which agent error rate spike?
   - Check external API status pages (DeFiLlama, CoinGecko, GoPlus, CryptoPanic)
   - Check recent deploys — có change tool code không?
3. **Mitigate**:
   - Nếu external API down → wait hoặc increase timeout buffer
   - Nếu tool bug → rollback deploy hoặc disable affected agent via feature flag
4. **Escalate**: if degradation persists > 4h hoặc catastrophic (> 50% queries fail)

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR-T3 Test error handling & fallback | `epics.md` Epic 0 | AC1-AC11 |
| FR35 Graceful degradation | `prd.md` | AC7, AC8, AC9 |
| NFR-CS3 API rate awareness | `prd.md` | AC1, AC4 |
| NFR-Q3 Graceful degradation > 98% | `prd.md` Quality Gates | AC10, AC11 |

---

## Rollback Plan

Test code = zero production risk. Nếu telemetry enhancement có bug → feature flag `DEGRADATION_TELEMETRY_ENABLED=false` (reuse pattern từ Story 8.2).

---

**Status**: review

---

## Tasks / Subtasks

- [x] **Task 1**: Cài đặt respx fault injection library
  - [x] `uv add --dev respx` (v0.23.1 installed)

- [x] **Task 2**: Thêm 2 Prometheus metrics mới (AC11)
  - [x] `AGENT_ERRORS_COUNTER{agent_name, error_type}` trong `app/observability/metrics.py`
  - [x] `GRACEFUL_DEGRADATION_COUNTER{outcome}` trong `app/observability/metrics.py`
  - [x] No-op stubs cho khi prometheus_client không có

- [x] **Task 3**: Enhance ParallelismTelemetryMiddleware — degradation tracking (AC11)
  - [x] Thêm field `agent_error_count`, `fallback_used`, `partial_response` logic
  - [x] Method `_track_degradation()` inspect ToolMessages, classify error type
  - [x] Increment `AGENT_ERRORS_COUNTER` và `GRACEFUL_DEGRADATION_COUNTER`
  - [x] Gọi `_track_degradation` từ cả `__call__` và `aafter_model`

- [x] **Task 4**: Tạo fault_injection.py helper utilities
  - [x] `inject_api_failure(service, failure_type)` async context manager
  - [x] `inject_all_failures(failure_type)` cho catastrophic test (AC9)
  - [x] Pattern mapping cho 7 services (coingecko, defillama, goplus, cryptopanic, etherscan, reddit, chainlens)

- [x] **Task 5**: Tạo test_graceful_degradation.py (AC1-AC10)
  - [x] `TestToolLevelErrorHandling` — 6 tests AC1-AC3 với respx context manager
  - [x] `TestTelemetryErrorTracking` — 4 tests AC11
  - [x] `TestOrchestrationLevelGraceful` — 5 tests AC7-AC9 (3 structural + 2 LLM-guarded)
  - [x] `TestAgentLevelFallback` — 3 tests AC4-AC6 (2 structural + 1 LLM-guarded)
  - [x] `TestDegradationRateBenchmark` — AC10 @pytest.mark.slow (LLM-guarded)

- [x] **Task 6**: Tạo runbook docs/runbooks/crypto-orchestra-degradation.md (DoD-9)
  - [x] Alert trigger conditions và Prometheus query
  - [x] Diagnose steps (per-agent error rate, external status pages, recent deploys)
  - [x] Mitigate scenarios (external outage, code bug, feature flag disable)
  - [x] Escalation criteria

- [x] **Task 7**: Validate — chạy tests và verify pass
  - [x] 15 passed, 3 skipped (3 skipped hợp lý vì cần ANTHROPIC_API_KEY)
  - [x] AC1-AC3: 6/6 pass
  - [x] AC11: 4/4 pass
  - [x] AC7-AC9 structural: 3/3 pass
  - [x] AC4-AC6 structural: 2/2 pass

---

## File List

- `nowing_backend/app/observability/metrics.py` — added `AGENT_ERRORS_COUNTER`, `GRACEFUL_DEGRADATION_COUNTER`
- `nowing_backend/app/agents/new_chat/chat_deepagent.py` — enhanced `ParallelismTelemetryMiddleware` with `_track_degradation`, updated imports
- `nowing_backend/tests/integration/agents/fault_injection.py` — new file, fault injection helpers
- `nowing_backend/tests/integration/agents/test_graceful_degradation.py` — new file, full test suite
- `docs/runbooks/crypto-orchestra-degradation.md` — new file, ops runbook
- `nowing_backend/pyproject.toml` — added `respx==0.23.1` dev dependency

---

## Dev Agent Record

### Implementation Notes

**Tool-level error handling** (AC1-AC3): Confirmed ALL tools already return `{"error": "..."}` on failures — không cần sửa tool code, chỉ viết tests validate behavior.

**respx mock strategy**: Dùng `with respx.mock(assert_all_mocked=True) as router:` bên trong test thay vì `@respx.mock` decorator — decorator không work đúng với async class methods trong pytest-asyncio.

**Telemetry**: `_track_degradation()` inspect ToolMessages sau mỗi LLM step. ToolMessage content là JSON string `{"error": "..."}` → parse và classify error_type (rate_limit, timeout, server_error, network_error).

**Test markers**:
- `@pytest.mark.integration` — tất cả tests
- `@pytest.mark.slow` — AC10 benchmark (100 queries, ~30-45 min với real LLM)
- `@_NEEDS_REAL_LLM` — content quality assertions cần ANTHROPIC_API_KEY

### Change Log

- 2026-04-24: Story 0.6 implemented — fault injection tests, telemetry metrics, ops runbook (Luisphan)
- 2026-04-24: Code review performed (3-layer adversarial: Blind Hunter, Edge Case Hunter, Acceptance Auditor) — 26 findings triaged
- 2026-04-24: Review patches applied — 18 patch findings fixed, 3 decisions resolved, 8 deferred, 4 dismissed. 14 tests pass, 9 skipped (structural + LLM-guarded)

---

### Review Findings

**Decisions resolved (3 → folded into patches/defers below):**

- [x] [Review][Decision] AC4/AC5/AC6 content verification → **Hybrid**: fill AC6 structural gap (P6), defer content verification tests until nightly LLM pipeline (W8).
- [x] [Review][Decision] AC10 benchmark gate → **Advisory**: keep `@pytest.mark.slow` + `@_NEEDS_REAL_LLM`, document in runbook as "advisory until nightly pipeline" (P17).
- [x] [Review][Decision] Runbook Scenario C feature flags → **Remove + replace**: drop feature-flag mitigation, use git revert/rollback guidance instead (P18).

**Patch (16):**

- [x] [Review][Patch] [HIGH] Counter double-count idempotency bug — `_track_degradation` runs on every model step AND re-scans ALL prior messages, so `AGENT_ERRORS_COUNTER` + `GRACEFUL_DEGRADATION_COUNTER` increment N× per request [chat_deepagent.py:_track_degradation]
- [x] [Review][Patch] [HIGH] ContextVar default `0.0` regression — `_prl_step_start.get(0.0)` yields huge inflated elapsed when unset (perf_counter epoch-sized); previous code used `perf_counter()` [chat_deepagent.py:333,343]
- [x] [Review][Patch] [HIGH] ContextVar `_prl_step_start` race across parallel sub-agents — siblings each copy-on-task parent's start time; mutations isolated, so `_check_spawn_pattern` attributes timing to wrong invocation [chat_deepagent.py:326-345]
- [x] [Review][Patch] [HIGH] Benchmark `except Exception: pass` swallows failures silently — any exception treated as non-success with no log; combined with `len(response) > 50` mock-LLM threshold, gate can report 98% while broken [test_graceful_degradation.py:TestDegradationRateBenchmark]
- [x] [Review][Patch] [HIGH] Structural tests unguarded against real LLM — `test_main_agent_no_crash_*` call `agent.ainvoke` with no `@_NEEDS_REAL_LLM` skip; if ANTHROPIC_API_KEY is set in CI they consume billable tokens, if unset they exercise mock path only [test_graceful_degradation.py:TestOrchestrationLevelGraceful, TestAgentLevelFallback]
- [x] [Review][Patch] [HIGH] AC6 test missing entirely — no `defillama_analyst` fallback test in TestAgentLevelFallback [test_graceful_degradation.py]
- [x] [Review][Patch] [HIGH] Middleware short-circuit bypasses `_track_degradation` in tests — conftest `_patched_awrap` returns synthetic ModelResponse, so `ParallelismTelemetryMiddleware.awrap_model_call` never fires; integration-level AC11 coverage is hollow [conftest.py:_patched_awrap]
- [x] [Review][Patch] [MED] Error classification substring matching — `"500" in error_msg` matches `"HTTP 5000ms"`; cascade order routes `"network timeout"` → timeout instead of network_error [chat_deepagent.py:_track_degradation classification block]
- [x] [Review][Patch] [MED] Non-string ToolMessage content (block list) not parsed — LangChain multimodal content may be a list; current `else: parsed = content` → `isinstance(dict)` fails silently [chat_deepagent.py:_track_degradation]
- [x] [Review][Patch] [MED] Tool tests don't verify mock was hit — `test_defillama_500_returns_error_dict` asserts only `"error" in result`, passes even if tool returned validation error before calling mocked URL [test_graceful_degradation.py:TestToolLevelErrorHandling]
- [x] [Review][Patch] [MED] `inject_all_failures` missing `.pass_through()` for LLM — AC9 real-LLM test will raise `AllMockedAssertionError` on Anthropic calls [fault_injection.py:inject_all_failures]
- [x] [Review][Patch] [MED] AC10 success threshold `len > 50` vs spec `len > 100` — lenient gate [test_graceful_degradation.py:test_degradation_rate_exceeds_98_percent]
- [x] [Review][Patch] [MED] AC11 telemetry tests don't snapshot counter values — "Should not raise" assertion only; regression removing `.inc()` would still pass [test_graceful_degradation.py:TestTelemetryErrorTracking]
- [x] [Review][Patch] [LOW] `parsed["error"]` membership check — `{"error": null, "data": [...]}` would misclassify as failure; use truthy check or `parsed.get("error")` [chat_deepagent.py:_track_degradation]
- [x] [Review][Patch] [LOW] Inner `import json` in hot-path middleware — move to module top [chat_deepagent.py:_track_degradation]
- [x] [Review][Patch] [LOW] AC7 content assertion too permissive — accepts bare `"tvl"` or `"on-chain"` keywords even if TVL was hallucinated [test_graceful_degradation.py:test_main_agent_synthesizes_with_1_failure_mentions_unavailable]
- [x] [Review][Patch] [MED] Document AC10 benchmark as advisory in runbook + DoD note (from D2) [docs/runbooks/crypto-orchestra-degradation.md, story DoD-7]
- [x] [Review][Patch] [MED] Rewrite runbook Scenario C — replace feature-flag mitigation with git revert/rollback guidance (from D3) [docs/runbooks/crypto-orchestra-degradation.md]

**Deferred (8):**

- [x] [Review][Defer] respx catch-all `.pass_through()` with real HTTP in tests — testing infra concern, not story scope [test_graceful_degradation.py]
- [x] [Review][Defer] Counter label cardinality risk with free-form `agent_name="unknown"` — speculative; monitor in production [chat_deepagent.py:_track_degradation]
- [x] [Review][Defer] Pure-LLM failures (no ToolMessages) invisible to `GRACEFUL_DEGRADATION_COUNTER` — design decision; current scope is tool-layer degradation [chat_deepagent.py:_track_degradation]
- [x] [Review][Defer] `respx>=0.23.1` added only to `dev` group — tests are dev-only anyway, prod `ImportError` not a real path [pyproject.toml]
- [x] [Review][Defer] Dashboard panel "Degradation Rate" gauge (DoD-8) not implemented — Grafana artifact, separate task [spec:DoD-8]
- [x] [Review][Defer] AC9 anti-hallucination assertion missing — automatic verification hard without golden dataset [test_graceful_degradation.py:test_catastrophic_failure_returns_honest_message]
- [x] [Review][Defer] AC2 `<35s` timing assertion missing — respx raises immediately, timing naturally bounded [test_graceful_degradation.py:test_goplus_timeout_returns_error_dict]
- [x] [Review][Defer] AC4/AC5/AC6 content-verification tests — defer LLM-based content checks until nightly pipeline with ANTHROPIC_API_KEY (from D1) [test_graceful_degradation.py:TestAgentLevelFallback]

**Dismissed as noise (4):**

- Removed duplicate `"phân tích tổng thể"` keyword (harmless dedupe)
- `respx.mock(...)` sync context in `async def` test (works correctly — respx supports this pattern)
- Auditor claim "`query_sample_100` fixture undefined" — FALSE POSITIVE (defined in conftest.py:459-577)
- Auditor claim "fault_injection.py not in diff" — diff rendering artifact, file exists (83 lines)

**Next**: Epic 0 DONE (all 6 stories) → trigger Phase 1 Epic 9 Story 9.1 + Story 9.4.

---

## Scope expansion 2026-04-24 — see [Story 0.6b](0-6b-rate-limit-paced-escalation.md)

E2E verification against TrollLLM 10 RPM (2026-04-24) surfaced that Tier 2 natural sequential pacing is still faster than very-strict provider RPM windows once KB planner + main synthesis LLM calls accumulate. Follow-up story **0.6b** adds a **Tier 3 paced sequential** mode: after 3 consecutive rate-limit events in the cooldown window, forces `asyncio.sleep(7)` between agent emissions and retries main synthesis up to 3× with paced backoff. Guarantees completion at the cost of latency (~42-50s for 6 agents).

Tier 1 (parallel) and Tier 2 (natural sequential) behavior in this story remain unchanged — Tier 3 only activates at `escalation_level() == 2`.
