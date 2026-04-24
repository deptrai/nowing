"""
Nowing deep agent implementation.

This module provides the factory function for creating Nowing deep agents
with configurable tools via the tools registry and configurable prompts
via NewLLMConfig.

We use ``create_agent`` (from langchain) rather than ``create_deep_agent``
(from deepagents) so that the middleware stack is fully under our control.
This lets us swap in ``NowingFilesystemMiddleware`` — a customisable
subclass of the default ``FilesystemMiddleware`` — while preserving every
other behaviour that ``create_deep_agent`` provides (todo-list, subagents,
summarisation, prompt-caching, etc.).
"""

import asyncio
import contextvars
import logging
import time
from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent, SubAgentMiddleware, __version__ as deepagents_version
from deepagents.backends import StateBackend
from deepagents.graph import BASE_AGENT_PROMPT
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from deepagents.middleware.summarization import create_summarization_middleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.context import NowingContextSchema
from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.middleware import (
    DedupHITLToolCallsMiddleware,
    KnowledgeBaseSearchMiddleware,
    MemoryInjectionMiddleware,
    NowingFilesystemMiddleware,
)
from app.agents.new_chat.system_prompt import (
    build_configurable_system_prompt,
    build_nowing_system_prompt,
)
from app.observability.metrics import FULL_SUITE_DURATION_HISTOGRAM
from app.agents.new_chat.subagents.crypto.defillama_spec import (
    DEFILLAMA_ALLOWED_TOOLS,
    DEFILLAMA_ANALYST_DESCRIPTION,
    DEFILLAMA_ANALYST_NAME,
    DEFILLAMA_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.news_spec import (
    NEWS_ALLOWED_TOOLS,
    NEWS_ANALYST_DESCRIPTION,
    NEWS_ANALYST_NAME,
    NEWS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.sentiment_spec import (
    SENTIMENT_ALLOWED_TOOLS,
    SENTIMENT_ANALYST_DESCRIPTION,
    SENTIMENT_ANALYST_NAME,
    SENTIMENT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_contract_spec import (
    SMART_CONTRACT_ALLOWED_TOOLS,
    SMART_CONTRACT_ANALYST_DESCRIPTION,
    SMART_CONTRACT_ANALYST_NAME,
    SMART_CONTRACT_ANALYST_PROMPT,
)
from app.agents.new_chat.tools.registry import build_tools_async
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

# =============================================================================
# Connector Type Mapping
# =============================================================================

# Maps SearchSourceConnectorType enum values to the searchable document/connector types
# used by pre-search middleware and web_search.
# Live search connectors (TAVILY_API, LINKUP_API, BAIDU_SEARCH_API) are routed to
# the web_search tool; all others are considered local/indexed data.
_CONNECTOR_TYPE_TO_SEARCHABLE: dict[str, str] = {
    # Live search connectors (handled by web_search tool)
    "TAVILY_API": "TAVILY_API",
    "LINKUP_API": "LINKUP_API",
    "BAIDU_SEARCH_API": "BAIDU_SEARCH_API",
    # Local/indexed connectors (handled by KB pre-search middleware)
    "SLACK_CONNECTOR": "SLACK_CONNECTOR",
    "TEAMS_CONNECTOR": "TEAMS_CONNECTOR",
    "NOTION_CONNECTOR": "NOTION_CONNECTOR",
    "GITHUB_CONNECTOR": "GITHUB_CONNECTOR",
    "LINEAR_CONNECTOR": "LINEAR_CONNECTOR",
    "DISCORD_CONNECTOR": "DISCORD_CONNECTOR",
    "JIRA_CONNECTOR": "JIRA_CONNECTOR",
    "CONFLUENCE_CONNECTOR": "CONFLUENCE_CONNECTOR",
    "CLICKUP_CONNECTOR": "CLICKUP_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",  # Connector type differs from document type
    "AIRTABLE_CONNECTOR": "AIRTABLE_CONNECTOR",
    "LUMA_CONNECTOR": "LUMA_CONNECTOR",
    "ELASTICSEARCH_CONNECTOR": "ELASTICSEARCH_CONNECTOR",
    "WEBCRAWLER_CONNECTOR": "CRAWLED_URL",  # Maps to document type
    "BOOKSTACK_CONNECTOR": "BOOKSTACK_CONNECTOR",
    "CIRCLEBACK_CONNECTOR": "CIRCLEBACK",  # Connector type differs from document type
    "OBSIDIAN_CONNECTOR": "OBSIDIAN_CONNECTOR",
    "DROPBOX_CONNECTOR": "DROPBOX_FILE",  # Connector type differs from document type
    "ONEDRIVE_CONNECTOR": "ONEDRIVE_FILE",  # Connector type differs from document type
    # Composio connectors (unified to native document types).
    # Reverse of NATIVE_TO_LEGACY_DOCTYPE in app.db.
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "COMPOSIO_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    # Cryptocurrency data
    "DEXSCREENER_CONNECTOR": "DEXSCREENER_CONNECTOR",
}

# Document types that don't come from SearchSourceConnector but should always be searchable
_ALWAYS_AVAILABLE_DOC_TYPES: list[str] = [
    "EXTENSION",  # Browser extension data
    "FILE",  # Uploaded files
    "NOTE",  # User notes
    "YOUTUBE_VIDEO",  # YouTube videos
]


def _map_connectors_to_searchable_types(
    connector_types: list[Any],
) -> list[str]:
    """
    Map SearchSourceConnectorType enums to searchable document/connector types.

    This function:
    1. Converts connector type enums to their searchable counterparts
    2. Includes always-available document types (EXTENSION, FILE, NOTE, YOUTUBE_VIDEO)
    3. Deduplicates while preserving order

    Args:
        connector_types: List of SearchSourceConnectorType enum values

    Returns:
        List of searchable connector/document type strings
    """
    result_set: set[str] = set()
    result_list: list[str] = []

    # Add always-available document types first
    for doc_type in _ALWAYS_AVAILABLE_DOC_TYPES:
        if doc_type not in result_set:
            result_set.add(doc_type)
            result_list.append(doc_type)

    # Map each connector type to its searchable equivalent
    for ct in connector_types:
        # Handle both enum and string types
        ct_str = ct.value if hasattr(ct, "value") else str(ct)
        searchable = _CONNECTOR_TYPE_TO_SEARCHABLE.get(ct_str)
        if searchable and searchable not in result_set:
            result_set.add(searchable)
            result_list.append(searchable)

    return result_list


# =============================================================================
# Parallelism Telemetry Middleware
# =============================================================================

_agent_log = logging.getLogger("app.agents")

# ContextVar to pass model-call start time from abefore_model to aafter_model.
# Each async task/step gets its own copy, so concurrent agent calls don't interfere.
_prl_step_start: contextvars.ContextVar[float] = contextvars.ContextVar(
    "_prl_step_start", default=0.0
)


class ParallelSpawnDirectiveMiddleware(AgentMiddleware):
    """Injects a parallel-spawn mandate into both system message and last human message.

    Placed immediately after SubAgentMiddleware. Modifies both:
    1. System message — persistent instruction
    2. Last HumanMessage — inline mandate for comprehensive-analysis queries
    """

    _DIRECTIVE = """\
## Task Tool: Mandatory Parallel Execution

IMMEDIATELY call task() for ALL 4 sub-agents in a SINGLE response — do NOT write any text first:
1. defillama_analyst — on-chain TVL / DeFi metrics
2. sentiment_analyst — market sentiment and fear/greed data
3. news_analyst — latest news and market developments
4. smart_contract_analyst — contract security analysis

CRITICAL RULES:
- Your ENTIRE response MUST consist of tool calls only — zero text before the first tool call.
- ALL 4 task() calls MUST appear in the SAME response to enable parallel execution.
- Do NOT describe your plan. Do NOT acknowledge the request. Call task() immediately."""

    _INLINE_MANDATE = (
        "\n\n[SYSTEM OVERRIDE — PARALLEL EXECUTION REQUIRED]\n"
        "You MUST respond with EXACTLY 4 simultaneous task() tool calls and NOTHING ELSE:\n"
        "  task(subagent_type='defillama_analyst', description='...')\n"
        "  task(subagent_type='sentiment_analyst', description='...')\n"
        "  task(subagent_type='news_analyst', description='...')\n"
        "  task(subagent_type='smart_contract_analyst', description='...')\n"
        "ALL 4 calls in ONE response. Zero text. Zero preamble. Start with the first task() call NOW."
    )

    _KEYWORDS = (
        "phân tích toàn diện", "full analysis", "comprehensive", "đánh giá toàn diện",
        "investment analysis", "phân tích tổng thể", "full crypto analysis", "full review",
        "đánh giá chi tiết", "đánh giá investment", "phân tích chi tiết", "đánh giá đầy đủ",
        "phân tích tổng thể", "investment-grade analysis", "comprehensive review",
    )

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        import uuid
        from langchain_core.messages import AIMessage, HumanMessage

        try:
            from langchain.agents.middleware.types import ModelResponse
        except ImportError:
            ModelResponse = None

        # Detect comprehensive query in the last HumanMessage
        messages = list(request.messages)
        query_content = ""
        is_comprehensive = False
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if not isinstance(msg, HumanMessage):
                continue
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if any(kw in content.lower() for kw in self._KEYWORDS):
                is_comprehensive = True
                query_content = content
                break

        if is_comprehensive and ModelResponse is not None:
            # Synthetic bypass: return 4 parallel task() calls WITHOUT invoking the LLM.
            # This guarantees all spawns happen in a single LangGraph step (AC1/AC2).
            short_q = query_content[:300]
            synthetic_ai = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "subagent_type": "defillama_analyst",
                            "description": f"Analyze on-chain TVL and DeFi metrics for: {short_q}",
                        },
                        "id": uuid.uuid4().hex[:8],
                        "type": "tool_call",
                    },
                    {
                        "name": "task",
                        "args": {
                            "subagent_type": "sentiment_analyst",
                            "description": f"Analyze market sentiment and fear/greed data for: {short_q}",
                        },
                        "id": uuid.uuid4().hex[:8],
                        "type": "tool_call",
                    },
                    {
                        "name": "task",
                        "args": {
                            "subagent_type": "news_analyst",
                            "description": f"Find latest news and market developments for: {short_q}",
                        },
                        "id": uuid.uuid4().hex[:8],
                        "type": "tool_call",
                    },
                    {
                        "name": "task",
                        "args": {
                            "subagent_type": "smart_contract_analyst",
                            "description": f"Analyze smart contract security for: {short_q}",
                        },
                        "id": uuid.uuid4().hex[:8],
                        "type": "tool_call",
                    },
                ],
            )
            return ModelResponse(result=[synthetic_ai])

        # Non-comprehensive query: inject directive into system message and delegate to LLM
        from deepagents.middleware._utils import append_to_system_message

        new_sys = append_to_system_message(request.system_message, self._DIRECTIVE)
        return await handler(request.override(system_message=new_sys, messages=messages))

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return handler(request)


class ParallelismTelemetryMiddleware(AgentMiddleware):
    """Detects sequential task() spawns and logs a warning.

    When the LLM issues task() calls across multiple LangGraph steps instead of
    batching them in a single step (anti-pattern), this middleware logs a warning
    so operators can investigate prompt or model issues.

    Supports two usage patterns:
    - AgentMiddleware hooks: abefore_model / aafter_model (used in production graph)
    - Callable middleware:   await mw(state, config, next_fn)  (used in tests)
    """

    async def __call__(self, state: Any, config: Any, next_middleware: Any) -> Any:
        """Callable middleware interface for testing and pipeline composition.

        Calls next_middleware, then inspects the result state for task() tool calls.
        """
        _prl_step_start.set(time.perf_counter())
        result_state = await next_middleware(state, config)
        _elapsed = time.perf_counter() - _prl_step_start.get(time.perf_counter())
        self._check_spawn_pattern(result_state, _elapsed)
        return result_state

    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        _prl_step_start.set(time.perf_counter())
        return None

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        _elapsed = time.perf_counter() - _prl_step_start.get(time.perf_counter())
        self._check_spawn_pattern(state, _elapsed)
        return None

    def _check_spawn_pattern(self, state: Any, elapsed: float) -> None:
        """Inspect state messages for task() tool_calls and log accordingly."""
        if isinstance(state, dict):
            messages = state.get("messages") or []
        else:
            messages = getattr(state, "messages", None) or []

        task_calls = []
        for msg in reversed(messages):
            if isinstance(msg, dict):
                role = msg.get("type") or msg.get("role") or ""
            else:
                role = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
            if role not in ("ai", "assistant"):
                continue
            if isinstance(msg, dict):
                tool_calls = msg.get("tool_calls") or []
            else:
                tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name")
                else:
                    name = getattr(tc, "name", None)
                if name == "task":
                    task_calls.append(tc)
            if task_calls:
                break

        agent_count = len(task_calls)
        if agent_count >= 4:
            _agent_log.info(
                "parallel_spawn: %d agents dispatched in single step, elapsed=%.3fs",
                agent_count,
                elapsed,
            )
            FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="4+").observe(elapsed)
        elif agent_count >= 2:
            _agent_log.info(
                "parallel_spawn: %d agents dispatched in single step, elapsed=%.3fs",
                agent_count,
                elapsed,
            )
            FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="2-3").observe(elapsed)
        elif agent_count == 1:
            # Single task() per step is the sequential anti-pattern — find query snippet
            _query_snippet = ""
            for _m in reversed(messages):
                if isinstance(_m, dict):
                    _role = _m.get("type") or _m.get("role") or ""
                else:
                    _role = getattr(_m, "type", None) or getattr(_m, "role", None) or ""
                if _role in ("ai", "assistant"):
                    continue  # skip the AI message we just inspected
                _c = (_m.get("content", "") if isinstance(_m, dict) else getattr(_m, "content", "")) or ""
                if _c:
                    _query_snippet = str(_c)[:120]
                    break
            _agent_log.warning(
                "potential_sequential_spawn detected: single task() call per step. "
                "LLM may be spawning sub-agents sequentially instead of in a parallel batch. "
                "query_snippet=%r",
                _query_snippet,
            )
            FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="1").observe(elapsed)


# =============================================================================
# Deep Agent Factory
# =============================================================================


async def create_nowing_deep_agent(
    llm: BaseChatModel,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    checkpointer: Checkpointer,
    user_id: str | None = None,
    thread_id: int | None = None,
    agent_config: AgentConfig | None = None,
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
    firecrawl_api_key: str | None = None,
    thread_visibility: ChatVisibility | None = None,
    mentioned_document_ids: list[int] | None = None,
):
    """
    Create a Nowing deep agent with configurable tools and prompts.

    The agent comes with built-in tools that can be configured:
    - generate_podcast: Generate audio podcasts from content
    - generate_image: Generate images from text descriptions using AI models
    - scrape_webpage: Extract content from webpages
    - update_memory: Update the user's personal or team memory document

    The agent also includes TodoListMiddleware by default (via create_deep_agent) which provides:
    - write_todos: Create and update planning/todo lists for complex tasks

    The system prompt can be configured via agent_config:
    - Custom system instructions (or use defaults)
    - Citation toggle (enable/disable citation requirements)

    Args:
        llm: ChatLiteLLM instance for the agent's language model
        search_space_id: The user's search space ID
        db_session: Database session for tools that need DB access
        connector_service: Initialized connector service for knowledge base search
        checkpointer: LangGraph checkpointer for conversation state persistence.
                      Use AsyncPostgresSaver for production or MemorySaver for testing.
        user_id: The current user's UUID string (required for memory tools)
        agent_config: Optional AgentConfig from NewLLMConfig for prompt configuration.
                     If None, uses default system prompt with citations enabled.
        enabled_tools: Explicit list of tool names to enable. If None, all default tools
                      are enabled. Use this to limit which tools are available.
        disabled_tools: List of tool names to disable. Applied after enabled_tools.
                       Use this to exclude specific tools from the defaults.
        additional_tools: Extra custom tools to add beyond the built-in ones.
                         These are always added regardless of enabled/disabled settings.
        firecrawl_api_key: Optional Firecrawl API key for premium web scraping.
                          Falls back to Chromium/Trafilatura if not provided.

    Returns:
        CompiledStateGraph: The configured deep agent

    Examples:
        # Create agent with all default tools and default prompt
        agent = create_nowing_deep_agent(llm, search_space_id, db_session, ...)

        # Create agent with custom prompt configuration
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            agent_config=AgentConfig(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="...",
                system_instructions="Custom instructions...",
                citations_enabled=False,
            )
        )

        # Create agent with only specific tools
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            enabled_tools=["scrape_webpage"]
        )

        # Create agent without podcast generation
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            disabled_tools=["generate_podcast"]
        )

        # Add custom tools
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            additional_tools=[my_custom_tool]
        )
    """
    _t_agent_total = time.perf_counter()

    # Discover available connectors and document types for this search space
    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        connector_types = await connector_service.get_available_connectors(
            search_space_id
        )
        if connector_types:
            available_connectors = _map_connectors_to_searchable_types(connector_types)

        available_document_types = await connector_service.get_available_document_types(
            search_space_id
        )

    except Exception as e:
        logging.warning(f"Failed to discover available connectors/document types: {e}")
    _perf_log.info(
        "[create_agent] Connector/doc-type discovery in %.3fs",
        time.perf_counter() - _t0,
    )

    # Build dependencies dict for the tools registry
    visibility = thread_visibility or ChatVisibility.PRIVATE

    # Extract the model's context window so tools can size their output.
    _model_profile = getattr(llm, "profile", None)
    _max_input_tokens: int | None = (
        _model_profile.get("max_input_tokens")
        if isinstance(_model_profile, dict)
        else None
    )

    dependencies = {
        "search_space_id": search_space_id,
        "db_session": db_session,
        "connector_service": connector_service,
        "firecrawl_api_key": firecrawl_api_key,
        "user_id": user_id,
        "thread_id": thread_id,
        "thread_visibility": visibility,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
        "max_input_tokens": _max_input_tokens,
        "llm": llm,
    }

    # Disable Notion action tools if no Notion connector is configured
    modified_disabled_tools = list(disabled_tools) if disabled_tools else []
    has_notion_connector = (
        available_connectors is not None and "NOTION_CONNECTOR" in available_connectors
    )
    if not has_notion_connector:
        notion_tools = [
            "create_notion_page",
            "update_notion_page",
            "delete_notion_page",
        ]
        modified_disabled_tools.extend(notion_tools)

    # Disable Linear action tools if no Linear connector is configured
    has_linear_connector = (
        available_connectors is not None and "LINEAR_CONNECTOR" in available_connectors
    )
    if not has_linear_connector:
        linear_tools = [
            "create_linear_issue",
            "update_linear_issue",
            "delete_linear_issue",
        ]
        modified_disabled_tools.extend(linear_tools)

    # Disable Google Drive action tools if no Google Drive connector is configured
    has_google_drive_connector = (
        available_connectors is not None and "GOOGLE_DRIVE_FILE" in available_connectors
    )
    if not has_google_drive_connector:
        google_drive_tools = [
            "create_google_drive_file",
            "delete_google_drive_file",
        ]
        modified_disabled_tools.extend(google_drive_tools)

    has_dropbox_connector = (
        available_connectors is not None and "DROPBOX_FILE" in available_connectors
    )
    if not has_dropbox_connector:
        modified_disabled_tools.extend(["create_dropbox_file", "delete_dropbox_file"])

    has_onedrive_connector = (
        available_connectors is not None and "ONEDRIVE_FILE" in available_connectors
    )
    if not has_onedrive_connector:
        modified_disabled_tools.extend(["create_onedrive_file", "delete_onedrive_file"])

    # Disable Google Calendar action tools if no Google Calendar connector is configured
    has_google_calendar_connector = (
        available_connectors is not None
        and "GOOGLE_CALENDAR_CONNECTOR" in available_connectors
    )
    if not has_google_calendar_connector:
        calendar_tools = [
            "create_calendar_event",
            "update_calendar_event",
            "delete_calendar_event",
        ]
        modified_disabled_tools.extend(calendar_tools)

    # Disable Gmail action tools if no Gmail connector is configured
    has_gmail_connector = (
        available_connectors is not None
        and "GOOGLE_GMAIL_CONNECTOR" in available_connectors
    )
    if not has_gmail_connector:
        gmail_tools = [
            "create_gmail_draft",
            "update_gmail_draft",
            "send_gmail_email",
            "trash_gmail_email",
        ]
        modified_disabled_tools.extend(gmail_tools)

    # Disable Jira action tools if no Jira connector is configured
    has_jira_connector = (
        available_connectors is not None and "JIRA_CONNECTOR" in available_connectors
    )
    if not has_jira_connector:
        jira_tools = [
            "create_jira_issue",
            "update_jira_issue",
            "delete_jira_issue",
        ]
        modified_disabled_tools.extend(jira_tools)

    # Disable Confluence action tools if no Confluence connector is configured
    has_confluence_connector = (
        available_connectors is not None
        and "CONFLUENCE_CONNECTOR" in available_connectors
    )
    if not has_confluence_connector:
        confluence_tools = [
            "create_confluence_page",
            "update_confluence_page",
            "delete_confluence_page",
        ]
        modified_disabled_tools.extend(confluence_tools)

    # Remove direct KB search tool; we now pre-seed a scoped filesystem via middleware.
    if "search_knowledge_base" not in modified_disabled_tools:
        modified_disabled_tools.append("search_knowledge_base")

    # Build tools using the async registry (includes MCP tools)
    _t0 = time.perf_counter()
    tools = await build_tools_async(
        dependencies=dependencies,
        enabled_tools=enabled_tools,
        disabled_tools=modified_disabled_tools,
        additional_tools=list(additional_tools) if additional_tools else None,
    )
    _perf_log.info(
        "[create_agent] build_tools_async in %.3fs (%d tools)",
        time.perf_counter() - _t0,
        len(tools),
    )

    # Build system prompt based on agent_config, scoped to the tools actually enabled
    _t0 = time.perf_counter()
    _enabled_tool_names = {t.name for t in tools}
    _user_disabled_tool_names = set(disabled_tools) if disabled_tools else set()
    if agent_config is not None:
        system_prompt = build_configurable_system_prompt(
            custom_system_instructions=agent_config.system_instructions,
            use_default_system_instructions=agent_config.use_default_system_instructions,
            citations_enabled=agent_config.citations_enabled,
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
        )
    else:
        system_prompt = build_nowing_system_prompt(
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    # -- Build the middleware stack (mirrors create_deep_agent internals) ------
    _memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    # NFR-CS4: each sub-agent gets a *fresh* middleware list with *fresh* instances
    # so that any per-invocation state (todos buffer, summarization cache,
    # filesystem handles) cannot cross-contaminate when sub-agents run in parallel.
    # _memory_middleware is the only intentionally shared instance — it is read-only
    # context injection, no per-call mutation.
    def _build_gp_middleware() -> list[Any]:
        return [
            TodoListMiddleware(),
            _memory_middleware,
            NowingFilesystemMiddleware(
                search_space_id=search_space_id,
                created_by_id=user_id,
            ),
            create_summarization_middleware(llm, StateBackend),
            PatchToolCallsMiddleware(),
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
        ]

    general_purpose_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": llm,
        "tools": tools,
        "middleware": _build_gp_middleware(),
    }

    # Crypto sub-agent tool scoping (allowed sets imported from spec files —
    # single source of truth shared with tests).
    def _scope_tools(allowed: tuple[str, ...], agent_label: str) -> list[BaseTool]:
        scoped = [t for t in tools if t.name in allowed]
        scoped_names = {t.name for t in scoped}
        missing = set(allowed) - scoped_names
        if missing:
            # NFR-CS4: surface silent registry drift (e.g. a tool gated off by env flag).
            _perf_log.warning(
                "[create_agent] sub-agent %s missing tools from registry: %s",
                agent_label,
                sorted(missing),
            )
        return scoped

    defillama_tools = _scope_tools(DEFILLAMA_ALLOWED_TOOLS, DEFILLAMA_ANALYST_NAME)
    sentiment_tools = _scope_tools(SENTIMENT_ALLOWED_TOOLS, SENTIMENT_ANALYST_NAME)
    news_tools = _scope_tools(NEWS_ALLOWED_TOOLS, NEWS_ANALYST_NAME)
    smart_contract_tools = _scope_tools(SMART_CONTRACT_ALLOWED_TOOLS, SMART_CONTRACT_ANALYST_NAME)

    # Guard: all 4 crypto prompts reference chainlens_deep_research unconditionally.
    # If the feature flag (CHAINLENS_RESEARCH_ENABLED) is off, the tool is silently
    # absent from the registry → LLM will hallucinate tool calls. Escalate to ERROR
    # so this is noticeable in logs instead of buried in per-agent warnings.
    _tool_names = {t.name for t in tools}
    if "chainlens_deep_research" not in _tool_names:
        _perf_log.error(
            "[create_agent] chainlens_deep_research is NOT in the tool registry but all "
            "4 crypto sub-agent prompts reference it. Either enable CHAINLENS_RESEARCH_ENABLED "
            "or update crypto sub-agent prompts to remove chainlens references."
        )

    defillama_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": DEFILLAMA_ANALYST_NAME,
        "description": DEFILLAMA_ANALYST_DESCRIPTION,
        "system_prompt": DEFILLAMA_ANALYST_PROMPT,
        "model": llm,
        "tools": defillama_tools,
        "middleware": _build_gp_middleware(),
    }
    sentiment_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": SENTIMENT_ANALYST_NAME,
        "description": SENTIMENT_ANALYST_DESCRIPTION,
        "system_prompt": SENTIMENT_ANALYST_PROMPT,
        "model": llm,
        "tools": sentiment_tools,
        "middleware": _build_gp_middleware(),
    }
    news_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": NEWS_ANALYST_NAME,
        "description": NEWS_ANALYST_DESCRIPTION,
        "system_prompt": NEWS_ANALYST_PROMPT,
        "model": llm,
        "tools": news_tools,
        "middleware": _build_gp_middleware(),
    }
    smart_contract_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": SMART_CONTRACT_ANALYST_NAME,
        "description": SMART_CONTRACT_ANALYST_DESCRIPTION,
        "system_prompt": SMART_CONTRACT_ANALYST_PROMPT,
        "model": llm,
        "tools": smart_contract_tools,
        "middleware": _build_gp_middleware(),
    }

    # Main agent middleware
    deepagent_middleware = [
        TodoListMiddleware(),
        _memory_middleware,
        KnowledgeBaseSearchMiddleware(
            llm=llm,
            search_space_id=search_space_id,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
        ),
        NowingFilesystemMiddleware(
            search_space_id=search_space_id,
            created_by_id=user_id,
        ),
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
        ParallelSpawnDirectiveMiddleware(),
        ParallelismTelemetryMiddleware(),
        create_summarization_middleware(llm, StateBackend),
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    # Combine system_prompt with BASE_AGENT_PROMPT (same as create_deep_agent)
    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    _t0 = time.perf_counter()
    agent = await asyncio.to_thread(
        create_agent,
        llm,
        system_prompt=final_system_prompt,
        tools=tools,
        middleware=deepagent_middleware,
        context_schema=NowingContextSchema,
        checkpointer=checkpointer,
    )
    agent = agent.with_config(
        {
            "recursion_limit": 10_000,
            "metadata": {
                "ls_integration": "deepagents",
                "versions": {"deepagents": deepagents_version},
            },
        }
    )
    _perf_log.info(
        "[create_agent] Graph compiled (create_agent) in %.3fs",
        time.perf_counter() - _t0,
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent
