# Story 7.2: LangGraph Tool — `chainlens_deep_research` + Fallback Logic

Status: done

## Story

As a Kỹ sư AI/Backend,
I want tạo LangGraph tool `chainlens_deep_research` và đăng ký vào `BUILTIN_TOOLS`, đồng thời thêm tool instructions/examples vào system prompt,
So that LangGraph Agent có thể thực thi deep research một cách minh bạch — gọi Chainlens khi available và tự động fallback (qua return tag, không phải gọi trực tiếp `generate_report`) khi không khả dụng.

## Acceptance Criteria

1. **Given** file `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` được tạo (~60 LOC)
   **When** tool `chainlens_deep_research` được Agent invoke với args `(query: str, sources: list[str] | None = None)`
   **Then** tool gọi `ChainlensResearchService.is_available()` trước
   **And** nếu `True`: gọi `ChainlensResearchService.research(query, sources)` và return `{"status": "success", "provider": "chainlens", "message": str, "sources": list}`
   **And** nếu `False`: return `{"status": "fallback", "provider": "nowing", "message": "Chainlens Research is currently unavailable. Please use generate_report with report_style='deep_research' and source_strategy='kb_search' to produce a research report using Nowing's built-in capabilities."}` — **không** gọi `generate_report` trực tiếp; LLM sẽ tự decide ở turn tiếp theo dựa vào message này

2. **Given** Chainlens API đang available nhưng raise `ChainlensUnavailableError` (HTTP 5xx, timeout, network error)
   **When** `ChainlensResearchService.research()` raise exception
   **Then** tool catch exception, log warning ở server-side với tên exception (không log full stack trace)
   **And** return cùng format fallback `{"status": "fallback", "provider": "nowing", "message": "..."}`
   **And** user nhận được kết quả từ fallback mà không thấy thông báo lỗi liên quan đến Chainlens (FR25 silent fallback)

3. **Given** tool đang chạy (có thể mất tới 120s)
   **When** tool bắt đầu thực thi
   **Then** dispatch `dispatch_custom_event("research_status", {"phase": "researching", "message": "Researching..."})` (sync function — **KHÔNG** `await`) để FE hiển thị loading indicator
   **And** message **NEUTRAL** — KHÔNG mention "Chainlens" hay "fallback" để giữ FR25 silent
   **And** khi fallback xảy ra, dispatch event tiếp `{"phase": "switching", "message": "Researching..."}` (cùng neutral message — không expose vendor name)

4. **Given** factory function `create_chainlens_research_tool()` được định nghĩa trong file
   **When** module được import
   **Then** factory trả về `BaseTool` được decorate bởi `@tool` từ `langchain_core.tools`
   **And** tool có docstring chi tiết (English) mô tả: when to use, args, return format, fallback behavior — vì docstring được LLM đọc để decide tool calling

5. **Given** `nowing_backend/app/agents/new_chat/tools/registry.py` được edit
   **When** module được load
   **Then** `BUILTIN_TOOLS` list có thêm entry:
   ```python
   ToolDefinition(
       name="chainlens_deep_research",
       description="Perform deep web research using Chainlens engine with auto-fallback to built-in research",
       factory=lambda deps: create_chainlens_research_tool(),
       requires=[],  # No deps — uses external API + Config
       enabled_by_default=True,
   )
   ```
   **And** import statement mới được thêm: `from .chainlens_research import create_chainlens_research_tool`
   **And** entry được đặt **ngay sau** `web_search` ToolDefinition (vì cùng nhóm "research/search" tools)

6. **Given** `nowing_backend/app/agents/new_chat/system_prompt.py` được edit
   **When** module được load
   **Then** `_TOOL_INSTRUCTIONS["chainlens_deep_research"]` được thêm với nội dung:
   - Mô tả: Deep web research engine, dùng khi user yêu cầu "deep research", "thorough investigation", "comprehensive research", "nghiên cứu chuyên sâu"
   - Args: `query`, `sources` (default `["web"]`, options `["web", "discussions", "academic"]`)
   - Return: `{status, provider, message, sources}` 
   - **CRITICAL fallback handling instruction:** "If `status == 'fallback'`, you MUST call `generate_report` in the next turn with: `topic=<query>`, `source_strategy='kb_search'`, `search_queries=[<query>]`, `report_style='deep_research'` — do NOT mention Chainlens to the user." 
   - **Verified `generate_report` signature** (xem `report.py:596-603`): `topic: str` (required), `source_content: str = ""`, `source_strategy: str = "provided"`, `search_queries: list[str] | None = None`, `report_style: str = "detailed"`, `user_instructions: str | None = None`, `parent_report_id: int | None = None` — fallback chỉ cần 4 params: topic, source_strategy, search_queries, report_style
   - Negative guidance: "Do NOT use this for simple factual questions — use `web_search` for those."
   
   **And** `_TOOL_EXAMPLES["chainlens_deep_research"]` được thêm với ít nhất 2 examples:
   - Example 1: Successful Chainlens call
   - Example 2: Fallback scenario — show LLM follow-up call to `generate_report`

7. **Given** `_ALL_TOOL_NAMES_ORDERED` list trong `system_prompt.py`
   **When** list được update
   **Then** `"chainlens_deep_research"` được insert **ngay sau** `"web_search"` (vị trí thứ 3 trong list — vì priority cao trong nhóm research)

8. **Given** cả `ChainlensResearchService.research()` raise exception **VÀ** Agent sau đó cũng fail khi gọi `generate_report` fallback
   **When** exception cascade xảy ra
   **Then** Agent (LangGraph layer, không phải tool) trả về error message thân thiện cho user qua SSE: "Không thể thực hiện nghiên cứu chuyên sâu lúc này. Vui lòng thử lại sau."
   **Note:** AC này được handle ở Agent error handler chung (Story 7.3 sẽ bổ sung), tool layer chỉ cần đảm bảo không raise exception ra Agent.

## Tasks / Subtasks

- [x] Task 1: Tạo file `chainlens_research.py` (AC: #1, #2, #3, #4)
  - [x] 1.1 Tạo `nowing_backend/app/agents/new_chat/tools/chainlens_research.py`
  - [x] 1.2 Import `from langchain_core.tools import tool`, `from langchain_core.callbacks import dispatch_custom_event`
  - [x] 1.3 Verify symbols từ Story 7.1 đã exist: `python -c "from app.services.chainlens_research_service import ChainlensResearchService, ChainlensUnavailableError"` (nếu fail → 7.1 chưa done, dừng)
  - [x] 1.4 Import `from app.services.chainlens_research_service import ChainlensResearchService, ChainlensUnavailableError`
  - [x] 1.5 Import `logging` và setup `logger = logging.getLogger(__name__)`
  - [x] 1.6 Implement `create_chainlens_research_tool()` factory trả về `@tool`-decorated async function
  - [x] 1.7 Trong tool body: dispatch event "researching" (**SYNC** call, KHÔNG await) → check `is_available()` → branch success/fallback
  - [x] 1.8 Wrap `research()` call trong try/except `ChainlensUnavailableError` → return fallback dict
  - [x] 1.9 Đảm bảo docstring tool mô tả đầy đủ (English) cho LLM tool description

- [x] Task 2: Đăng ký tool vào registry (AC: #5)
  - [x] 2.1 Mở `nowing_backend/app/agents/new_chat/tools/registry.py`
  - [x] 2.2 Thêm import: `from .chainlens_research import create_chainlens_research_tool` (theo alphabetical order trong import block)
  - [x] 2.3 Thêm `ToolDefinition` mới vào `BUILTIN_TOOLS` list **ngay sau** `web_search` entry (~dòng 200)
  - [x] 2.4 Verify tool được register: `python -c "from app.agents.new_chat.tools.registry import BUILTIN_TOOLS; print([t.name for t in BUILTIN_TOOLS if 'chainlens' in t.name])"`

- [x] Task 3: Update system prompt (AC: #6, #7)
  - [x] 3.1 Mở `nowing_backend/app/agents/new_chat/system_prompt.py`
  - [x] 3.2 Thêm `_TOOL_INSTRUCTIONS["chainlens_deep_research"]` (sau `_TOOL_INSTRUCTIONS["web_search"]`, ~dòng 264)
  - [x] 3.3 Thêm `_TOOL_EXAMPLES["chainlens_deep_research"]` (sau `_TOOL_EXAMPLES["web_search"]`, ~dòng 446)
  - [x] 3.4 Update `_ALL_TOOL_NAMES_ORDERED` (~dòng 447) — insert `"chainlens_deep_research"` sau `"web_search"`

- [x] Task 4: Unit tests (AC: #1, #2, #3, #4)
  - [x] 4.1 Tạo `nowing_backend/tests/unit/agents/new_chat/tools/test_chainlens_research_tool.py` (folder đã tồn tại — xem `test_update_memory_scope.py` làm pattern reference)
  - [x] 4.2 Test success path: mock `ChainlensResearchService.is_available()` → True, `research()` → return dict; verify tool return `{"status": "success", "provider": "chainlens", ...}`
  - [x] 4.3 Test feature flag off path: mock `is_available()` → False; verify tool return `{"status": "fallback", "provider": "nowing", ...}` (KHÔNG raise)
  - [x] 4.4 Test exception path: mock `research()` raise `ChainlensUnavailableError`; verify tool return `{"status": "fallback", ...}` + verify warning log
  - [x] 4.5 Test event dispatch: dùng `patch("app.agents.new_chat.tools.chainlens_research.dispatch_custom_event")` để mock function trực tiếp; verify nó được gọi với neutral message (không chứa "Chainlens"). KHÔNG cần thiết lập callback handler thật vì test chỉ verify call signature.
  - [x] 4.6 Test sources param: pass `sources=["web", "academic"]` → verify `research()` được gọi với đúng list

- [x] Task 5: Integration smoke test (AC: #5, #6, #7)
  - [x] 5.1 Verify `from app.agents.new_chat.tools.registry import BUILTIN_TOOLS` không raise import error
  - [x] 5.2 Verify `chainlens_deep_research` xuất hiện trong `_ALL_TOOL_NAMES_ORDERED`
  - [x] 5.3 Verify system prompt build không lỗi: gọi `_get_tools_instructions()` với `enabled_tool_names={"chainlens_deep_research"}` → string output có chứa tool name

## Dev Notes

### CRITICAL Design Decisions (PHẢI tuân theo)

**1. Tool layer KHÔNG gọi `generate_report` trực tiếp**

Architecture decision: Tool chỉ trả về tag `{"status": "fallback", "message": "use generate_report..."}`. LLM (Agent) đọc message này và tự decide gọi `generate_report` ở turn tiếp theo.

**Lý do:**
- Giữ tool layer thuần (single responsibility)
- LLM đã được instruct qua `_TOOL_INSTRUCTIONS` để xử lý `status == "fallback"`
- Tránh circular import (tool A gọi tool B)
- Tránh hardcode tham số `generate_report` trong tool layer

**2. FR25 Silent Fallback — Event message phải neutral**

```python
# ✅ CORRECT
dispatch_custom_event("research_status", {"phase": "researching", "message": "Researching..."})

# ❌ WRONG — leak vendor name
dispatch_custom_event("research_status", {"phase": "fallback", "message": "Chainlens unavailable, using Nowing..."})
```

User KHÔNG được thấy "Chainlens" hay "fallback" trong UI. FE chỉ hiển thị "Đang nghiên cứu...".

### Codebase Patterns — PHẢI tuân theo

**Tool factory pattern** (xem `web_search.py` dòng 141-200 làm reference):
- Factory function `create_X_tool(deps...)` trả về `@tool`-decorated async function
- Tool function nested trong factory để capture closure
- Use `from langchain_core.tools import tool`

**Custom event dispatch** (chỉ dùng khi cần — `web_search.py` không dùng, nhưng `report.py:394` có dùng):
```python
from langchain_core.callbacks import dispatch_custom_event
# CRITICAL: dispatch_custom_event là SYNC function, KHÔNG dùng `await` (xem report.py:394)
# Nếu await sẽ raise TypeError silent → bị swallow trong try/except → event KHÔNG fire
dispatch_custom_event("research_status", {"phase": "...", "message": "..."})
```

**Logging** — dùng `logger = logging.getLogger(__name__)`, level `warning` cho expected fallback (KHÔNG dùng `error` vì fallback là behavior bình thường).

### File Locations

```
nowing_backend/app/agents/new_chat/tools/
    chainlens_research.py                       # [NEW] ~60 LOC
nowing_backend/app/agents/new_chat/tools/
    registry.py                                 # [EDIT] +1 import, +1 ToolDefinition (~10 dòng)
nowing_backend/app/agents/new_chat/
    system_prompt.py                            # [EDIT] +_TOOL_INSTRUCTIONS, +_TOOL_EXAMPLES, +1 entry vào _ALL_TOOL_NAMES_ORDERED (~50 dòng)
nowing_backend/tests/unit/agents/new_chat/tools/
    test_chainlens_research_tool.py             # [NEW] unit tests (folder đã tồn tại)
```

### Implementation Reference

**File `chainlens_research.py`** (architecture.md đã cung cấp blueprint, phiên bản đã refine cho FR25 silent):

```python
"""LangGraph tool: chainlens_deep_research with auto-fallback."""
import logging

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.tools import tool

from app.services.chainlens_research_service import (
    ChainlensResearchService,
    ChainlensUnavailableError,
)

logger = logging.getLogger(__name__)


def create_chainlens_research_tool():
    @tool
    async def chainlens_deep_research(
        query: str,
        sources: list[str] | None = None,
    ) -> dict:
        """Perform deep web research on a topic using an external research engine.

        Use this when the user explicitly asks for "deep research", "thorough
        investigation", "comprehensive research", or "nghiên cứu chuyên sâu" on
        a topic. This tool provides significantly better research quality than
        built-in search by synthesizing multiple web sources into a structured
        research report.

        If the engine is unavailable, this tool returns
        {"status": "fallback", ...} — DO NOT treat this as an error. Instead,
        in the next turn, call generate_report with report_style="deep_research"
        and source_strategy="kb_search" to produce a fallback research report.
        Do NOT mention the underlying engine name to the user.

        Args:
            query: The research question or topic.
            sources: Research source types. Options: "web", "discussions",
                     "academic". Default: ["web"].

        Returns:
            On success: {"status": "success", "provider": "chainlens",
                         "message": str, "sources": list}
            On fallback: {"status": "fallback", "provider": "nowing",
                          "message": str (instructions for next turn)}
        """
        # Neutral status event — do NOT leak vendor name
        # CRITICAL: dispatch_custom_event là SYNC, KHÔNG await (verified: report.py:394)
        try:
            dispatch_custom_event(
                "research_status",
                {"phase": "researching", "message": "Researching..."},
            )
        except Exception:
            pass  # event dispatch best-effort, never block tool

        # Check availability (cached health check)
        try:
            available = await ChainlensResearchService.is_available()
        except Exception as exc:
            logger.warning("chainlens is_available() raised %s", type(exc).__name__)
            available = False

        if not available:
            return _fallback_response()

        # Try the call
        try:
            result = await ChainlensResearchService.research(query, sources)
            return {
                "status": "success",
                "provider": "chainlens",
                "message": result.get("message", ""),
                "sources": result.get("sources", []),
            }
        except ChainlensUnavailableError as exc:
            # Log type only — KHÔNG log full message để tránh leak URL/payload
            logger.warning("chainlens research failed: %s", type(exc).__name__)
            return _fallback_response()
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning(
                "chainlens research unexpected error: %s", type(exc).__name__
            )
            return _fallback_response()

    return chainlens_deep_research


def _fallback_response() -> dict:
    """Return a fallback tag for the LLM to handle in the next turn."""
    return {
        "status": "fallback",
        "provider": "nowing",
        "message": (
            "Deep research engine is currently unavailable. In your next turn, "
            "call generate_report with report_style='deep_research' and "
            "source_strategy='kb_search' to produce a research report using "
            "built-in capabilities. Do NOT mention this fallback to the user."
        ),
    }
```

**Registry entry** (vào `registry.py` ngay sau `web_search` ToolDefinition):

```python
# Chainlens deep research tool — auto-fallback to generate_report when unavailable
# Feature flag CHAINLENS_RESEARCH_ENABLED controlled inside service layer
ToolDefinition(
    name="chainlens_deep_research",
    description="Perform deep web research using Chainlens engine with auto-fallback to built-in research",
    factory=lambda deps: create_chainlens_research_tool(),
    requires=[],  # No DB/connector deps — uses external API + Config
    enabled_by_default=True,
),
```

**System prompt addition** (vào `system_prompt.py`):

```python
_TOOL_INSTRUCTIONS["chainlens_deep_research"] = """
- chainlens_deep_research: Perform deep web research on a topic using an external engine.
  - Use this when the user explicitly asks for "deep research", "thorough investigation",
    "comprehensive research", or "nghiên cứu chuyên sâu" on a topic.
  - This tool synthesizes multiple web sources into a structured research report —
    significantly better than `web_search` for in-depth topic investigation.
  - DO NOT use for simple factual questions or current events — use `web_search` instead.
  - Args:
    - query: The research question or topic.
    - sources: ["web", "discussions", "academic"] — defaults to ["web"]. Use "academic"
      for scientific topics, "discussions" for community sentiment.
  - Returns: { status, provider, message, sources }
  - CRITICAL FALLBACK HANDLING:
    * If `status == "fallback"`, you MUST call `generate_report` in your next turn with
      these exact arguments (signature verified — see report.py:596):
        topic=<original query>,
        source_strategy="kb_search",
        search_queries=[<original query>],
        report_style="deep_research"
    * Do NOT mention "Chainlens", "fallback", or "engine unavailable" to the user.
    * Present the resulting report naturally as if it were the primary result.
"""

_TOOL_EXAMPLES["chainlens_deep_research"] = """
- User: "Do a deep research on AI agents in 2026"
  - Call: `chainlens_deep_research(query="AI agents landscape and trends in 2026", sources=["web", "academic"])`
  - If returns status="success", present the message and sources to the user with citations.
- User: "Thoroughly investigate the impact of DeFi on traditional banking"
  - Call: `chainlens_deep_research(query="Impact of DeFi on traditional banking industry", sources=["web", "discussions"])`
- If a previous chainlens_deep_research call returned status="fallback":
  - Next turn call: `generate_report(topic="DeFi Impact on Banking", source_strategy="kb_search", search_queries=["DeFi banking impact", "decentralized finance disruption"], report_style="deep_research")`
  - Do NOT tell the user about the fallback — present the report directly.
"""

# Update _ALL_TOOL_NAMES_ORDERED — insert after "web_search":
_ALL_TOOL_NAMES_ORDERED = [
    "search_nowing_docs",
    "web_search",
    "chainlens_deep_research",   # ← NEW
    "generate_podcast",
    "generate_video_presentation",
    "generate_report",
    "generate_image",
    "scrape_webpage",
    "update_memory",
]
```

### Testing Patterns

```python
# tests/agents/new_chat/tools/test_chainlens_research_tool.py
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.new_chat.tools.chainlens_research import (
    create_chainlens_research_tool,
)
from app.services.chainlens_research_service import ChainlensUnavailableError


@pytest.mark.asyncio
async def test_success_returns_chainlens_result():
    tool = create_chainlens_research_tool()
    
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc:
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(return_value={
            "message": "Research result",
            "sources": [{"url": "https://example.com"}],
        })
        
        result = await tool.ainvoke({"query": "AI agents 2026"})
        
        assert result["status"] == "success"
        assert result["provider"] == "chainlens"
        assert result["message"] == "Research result"
        assert len(result["sources"]) == 1


@pytest.mark.asyncio
async def test_unavailable_returns_fallback_tag():
    tool = create_chainlens_research_tool()
    
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc:
        mock_svc.is_available = AsyncMock(return_value=False)
        
        result = await tool.ainvoke({"query": "test"})
        
        assert result["status"] == "fallback"
        assert result["provider"] == "nowing"
        assert "generate_report" in result["message"]
        # FR25: must NOT leak vendor name in user-visible content
        assert "chainlens" not in result["message"].lower()


@pytest.mark.asyncio
async def test_research_exception_returns_fallback_not_raise():
    tool = create_chainlens_research_tool()
    
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc:
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(
            side_effect=ChainlensUnavailableError("timeout")
        )
        
        # Must NOT raise — must return fallback dict
        result = await tool.ainvoke({"query": "test"})
        
        assert result["status"] == "fallback"
```

### Project Structure Notes

- File mới `chainlens_research.py` nằm trong `app/agents/new_chat/tools/` (cùng folder với `web_search.py`, `report.py` — đúng pattern)
- Story 7.1 đã tạo `ChainlensResearchService` ở `app/services/chainlens_research_service.py` — Story 7.2 chỉ import, không sửa
- Không cần thêm vào `app/agents/new_chat/tools/__init__.py` — registry.py import trực tiếp
- KHÔNG cần thêm vào DB migration, FE, env vars (đã có ở Story 7.1)

### Dependencies

- **Story 7.1 PHẢI done trước** — `ChainlensResearchService` và `ChainlensUnavailableError` được import từ Story 7.1
- Nếu Story 7.1 chưa done, Story 7.2 sẽ fail import

### Previous Story Intelligence

Story 7.1 (`7-1-chainlens-research-service-health-check.md`) đã chuẩn bị:
- `ChainlensResearchService.is_available()` → async, returns bool, no exception
- `ChainlensResearchService.research(query, sources)` → async, returns `dict {"message": str, "sources": list}`, raise `ChainlensUnavailableError` on any failure
- 4 env vars trong `Config` class
- In-process health cache với TTL

Story 7.2 chỉ consume API public của Story 7.1 — KHÔNG cần biết internal cache logic.

### NFR Compliance

- **NFR-P4 (Deep Research ≤ 120s):** Story 7.1 đã handle timeout (125s client). Story 7.2 chỉ cần ensure tool không block sau khi service raise.
- **FR25 (Silent fallback):** AC #2, #3 + neutral event message + tool docstring + system prompt instruction → 4 lớp bảo vệ.

### References

- Architecture blueprint: `_bmad-output/planning-artifacts/architecture.md` — section "Tool Layer — chainlens_deep_research" và "System Prompt Integration" và "Tool Binding Integration"
- Story 7.1 (dependency): `_bmad-output/implementation-artifacts/7-1-chainlens-research-service-health-check.md`
- Tool pattern reference: `nowing_backend/app/agents/new_chat/tools/web_search.py` (dòng 141+ — factory pattern)
- Registry pattern: `nowing_backend/app/agents/new_chat/tools/registry.py` (dòng 199-208 — `web_search` ToolDefinition)
- System prompt pattern: `nowing_backend/app/agents/new_chat/system_prompt.py` (dòng 244, 422, 447 — web_search instructions/examples/ordered list)
- LangChain custom event docs: https://python.langchain.com/docs/how_to/callbacks_custom_events/

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

- Pre-existing failures confirmed unrelated: `test_dexscreener_connector` (base_url mismatch), `test_document_hashing` (env issue)
- `dispatch_custom_event` is SYNC — must NOT await (verified from report.py:394)
- FR25 enforcement: 4 layers — tool docstring, tool return message, event messages, system prompt instructions

### Completion Notes List

- All 5 tasks completed
- 7 unit tests added, all passing (394 total unit tests, 0 new regressions)
- `create_chainlens_research_tool()` factory pattern follows web_search.py convention
- `_FALLBACK_MESSAGE` does NOT mention "Chainlens" — FR25 compliant
- Tool registered in BUILTIN_TOOLS at position 6 (after web_search at 5)
- system_prompt.py updated: _TOOL_INSTRUCTIONS, _TOOL_EXAMPLES, _ALL_TOOL_NAMES_ORDERED

### File List

- `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` (new, ~112 LOC)
- `nowing_backend/app/agents/new_chat/tools/registry.py` (edited — added import + ToolDefinition)
- `nowing_backend/app/agents/new_chat/system_prompt.py` (edited — instructions, examples, ordered list)
- `nowing_backend/tests/unit/agents/new_chat/tools/test_chainlens_research_tool.py` (new, 7 tests)

### Review Findings (2026-04-19)

- [x] [Review][Decision] Double-fallback khi KB trống — `_FALLBACK_MESSAGE` yêu cầu LLM gọi `generate_report(source_strategy="kb_search")`, nhưng KB có thể rỗng → cascade silent failure. Spec chưa quy định. Options: (a) chấp nhận known limitation, (b) đổi `source_strategy="auto"`, (c) để Story 7.3 xử tại agent level.
- [x] [Review][Patch] Thiếu outer timeout → tool block tối đa ~250s (service retry 2×125s) — add `asyncio.wait_for(..., timeout=130)` [chainlens_research.py:94]
- [x] [Review][Patch] Tool register & expose cho LLM kể cả khi `CHAINLENS_RESEARCH_ENABLED=FALSE` — lãng phí ~600 tokens prompt + is_available call mỗi turn [registry.py:208-216]
- [x] [Review][Patch] `ValueError` từ service (empty query / invalid sources) bị nuốt bởi `except Exception` → log "unexpected error" che lấp client bug [chainlens_research.py:105]
- [x] [Review][Patch] Fallback message `"engine is currently unavailable"` misleading khi flag OFF — dùng wording trung tính [chainlens_research.py:14-19]
- [x] [Review][Patch] `result.get("message", "")` trả `None` nếu value là `None` — dùng `result.get("message") or ""` [chainlens_research.py:98]
- [x] [Review][Patch] Chainlens 200 với `message` rỗng/whitespace → LLM render empty, không trigger fallback [chainlens_research.py:94-100]
- [x] [Review][Patch] System prompt literal `<original query>` placeholder — Haiku có thể pass string `"<original query>"` [system_prompt.py:281]
- [x] [Review][Patch] AC#3 PARTIAL — thiếu dispatch "switching" event ở 2 `except` blocks trước `_fallback_response()` [chainlens_research.py:101-109]
- [x] [Review][Patch] Test gaps — thêm 3 tests: (a) ValueError từ service → fallback, (b) "switching" event dispatched trên unavailability path, (c) empty-message success → fallback [test_chainlens_research_tool.py]
- [x] [Review][Patch] Dead code `hasattr(mock_svc, "research")` — dùng `mock_svc.research.assert_not_called()` [test_chainlens_research_tool.py:77]
- [x] [Review][Defer] Bare `except Exception` quanh `dispatch_custom_event` nuốt real bugs [chainlens_research.py:67-72, 83-89] — deferred, low risk
- [x] [Review][Defer] Provider name `"nowing"` hardcode — coupling với brand, dùng `"builtin"` để decouple [chainlens_research.py:26] — deferred, cosmetic
