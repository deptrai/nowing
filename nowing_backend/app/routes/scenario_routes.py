"""
Scenario re-synthesis routes for the crypto analysis feature.

POST /scenarios/resynthesize — stream a scenario-adjusted analysis based on
the original checkpoint state (ToolMessages from sub-agents) without re-running
any tools.
"""

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import AsyncGenerator, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.llm_config import (
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_llm_config_from_yaml,
)
from app.db import (
    ChatRun,
    ChatRunStatus,
    NewChatThread,
    ScenarioResult,
    get_async_session,
)
from app.services.new_streaming_service import VercelStreamingService
from app.users import current_active_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_SCENARIO_CACHE_TTL_MINUTES = 60
_TOOL_MESSAGE_CHAR_BUDGET = 24_000  # rough cap before context overflow on most models


ScenarioLiteral = Literal["base", "bull", "bear", "stress"]
ScopeLiteral = Literal["conclusion", "full"]


class ResynthesizeRequest(BaseModel):
    thread_id: int
    scenario: ScenarioLiteral
    assumptions: dict = {}
    scope: ScopeLiteral = "conclusion"
    llm_config_id: int = -1


def _assumptions_hash(assumptions: dict) -> str:
    # allow_nan=False rejects NaN/Infinity which would otherwise produce
    # non-JSON output and corrupt cache keys
    serialized = json.dumps(assumptions, sort_keys=True, allow_nan=False)
    return hashlib.sha256(serialized.encode()).hexdigest()  # full 64 chars to fill String(64) column


def _truncate_tool_messages(messages: list[ToolMessage]) -> list[ToolMessage]:
    """Cap total ToolMessage character count to avoid LLM context overflow.

    Walks newest-first (typical relevance order in LangGraph state) and keeps
    messages until the budget is exhausted; remaining ones are truncated to a
    short summary.
    """
    kept: list[ToolMessage] = []
    used = 0
    for msg in messages:
        content = str(msg.content or "")
        if used + len(content) <= _TOOL_MESSAGE_CHAR_BUDGET:
            kept.append(msg)
            used += len(content)
        else:
            remaining = max(0, _TOOL_MESSAGE_CHAR_BUDGET - used)
            if remaining > 200:
                truncated = content[:remaining] + "\n\n[... truncated due to context budget ...]"
                kept.append(ToolMessage(content=truncated, tool_call_id=msg.tool_call_id))
                used = _TOOL_MESSAGE_CHAR_BUDGET
            break
    return kept


def _build_scenario_prompt(scenario: str, assumptions: dict, scope: str) -> str:
    assumption_lines = []
    if assumptions.get("btc_shock") is not None:
        pct = assumptions["btc_shock"] * 100
        sign = "+" if pct >= 0 else ""
        assumption_lines.append(f"- BTC price: {sign}{pct:.0f}% shock")
    if assumptions.get("eth_shock") is not None:
        pct = assumptions["eth_shock"] * 100
        sign = "+" if pct >= 0 else ""
        assumption_lines.append(f"- ETH price: {sign}{pct:.0f}% shock")
    if assumptions.get("competitor_growth") is not None:
        pct = assumptions["competitor_growth"] * 100
        sign = "+" if pct >= 0 else ""
        assumption_lines.append(f"- Competitor growth: {sign}{pct:.0f}%")
    if assumptions.get("tvl_shock") is not None:
        pct = assumptions["tvl_shock"] * 100
        sign = "+" if pct >= 0 else ""
        assumption_lines.append(f"- TVL: {sign}{pct:.0f}% shock")
    if assumptions.get("fee_switch_passes"):
        assumption_lines.append("- Fee switch governance vote: PASSES")
    if assumptions.get("regulatory_adverse"):
        assumption_lines.append("- Regulatory environment: ADVERSE (hostile regulation)")

    assumptions_text = "\n".join(assumption_lines) if assumption_lines else "- Standard market conditions"

    scope_instruction = (
        "Focus specifically on updating the **Conclusion** section with revised price targets, "
        "risk ratings, and yield projections. Keep other sections intact."
        if scope == "conclusion"
        else "Re-synthesize the full analysis with updated metrics throughout."
    )

    scenario_label = {
        "base": "Base Case",
        "bull": "Bull Case",
        "bear": "Bear Case",
        "stress": "Stress Test",
    }.get(scenario, scenario.title())

    return f"""# {scenario_label} Re-synthesis

The user has selected the **{scenario_label}** scenario with the following assumptions:

{assumptions_text}

Using the sub-agent data already provided above (in the ToolMessages), re-synthesize the analysis under these scenario assumptions.

Instructions:
1. **DO NOT call any tools.** All data is already in the ToolMessages above.
2. Adjust price targets, yield expectations, risk assessment, and TVL projections to reflect the scenario.
3. Keep citation tags [[cite:...]] around numeric values where applicable.
4. {scope_instruction}
5. Clearly label this as the **{scenario_label}** at the start of your response.
6. Be explicit about what changes vs. the base case.

Write the updated analysis now:"""


async def _stream_scenario_resynthesize(
    thread_id: int,
    scenario: str,
    assumptions: dict,
    scope: str,
    llm_config_id: int,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    streaming_service = VercelStreamingService()

    # Load LLM
    if llm_config_id >= 0:
        agent_config = await load_agent_config(
            session=session, config_id=llm_config_id, search_space_id=None
        )
        if not agent_config:
            yield streaming_service.format_error(f"LLM config {llm_config_id} not found")
            yield streaming_service.format_done()
            return
        llm = create_chat_litellm_from_agent_config(agent_config)
    else:
        llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
        if not llm_config:
            yield streaming_service.format_error("Default LLM config not available")
            yield streaming_service.format_done()
            return
        llm = create_chat_litellm_from_config(llm_config)

    if not llm:
        yield streaming_service.format_error("Failed to initialize LLM")
        yield streaming_service.format_done()
        return

    # Load checkpoint messages from LangGraph PostgresSaver.
    # Background runs store checkpoints under ChatRun.langgraph_thread_id ("run-<uuid>"),
    # while old inline runs use str(thread_id).  Look up the latest completed run first;
    # fall back to the str(thread_id) path for legacy inline threads.
    run_result = await session.execute(
        select(ChatRun)
        .where(
            ChatRun.thread_id == thread_id,
            ChatRun.status == ChatRunStatus.COMPLETED,
        )
        .order_by(ChatRun.started_at.desc())
        .limit(1)
    )
    latest_run = run_result.scalars().first()
    lg_thread_id = latest_run.langgraph_thread_id if latest_run else str(thread_id)

    checkpointer = await get_checkpointer()
    config = {"configurable": {"thread_id": lg_thread_id}}

    try:
        # aget() returns Checkpoint (dict) directly; aget_tuple() returns CheckpointTuple
        # which exposes .checkpoint, .config, .metadata etc.  We need the tuple.
        checkpoint_tuple = await checkpointer.aget_tuple(config)
    except Exception as e:
        logger.error("[scenario_resynthesize] Failed to load checkpoint: %s", e)
        yield streaming_service.format_error("Failed to load conversation checkpoint")
        yield streaming_service.format_done()
        return

    if not checkpoint_tuple:
        yield streaming_service.format_error("No checkpoint found for this thread")
        yield streaming_service.format_done()
        return

    messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
    if not messages:
        yield streaming_service.format_error("No messages found in checkpoint")
        yield streaming_service.format_done()
        return

    # Extract ToolMessages (sub-agent results) for context — cap total chars
    raw_tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    if not raw_tool_messages:
        yield streaming_service.format_error("No sub-agent data found in checkpoint")
        yield streaming_service.format_done()
        return
    tool_messages = _truncate_tool_messages(raw_tool_messages)

    # Build synthesis messages: system + tool results + scenario prompt
    synthesis_messages = [
        SystemMessage(
            content="You are a crypto analysis assistant. Re-synthesize the analysis based on the sub-agent data and scenario assumptions provided. DO NOT call any tools. Respond with analysis text only."
        ),
        *tool_messages,
        HumanMessage(content=_build_scenario_prompt(scenario, assumptions, scope)),
    ]

    # Stream LLM response — only persist on clean completion
    accumulated = ""
    stream_completed = False
    try:
        try:
            async for chunk in llm.astream(synthesis_messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    accumulated += token
                    yield streaming_service.format_data(
                        "scenario-text-delta", {"delta": token}
                    )
            stream_completed = True
        except asyncio.CancelledError:
            logger.info("[scenario_resynthesize] Stream cancelled by client")
            raise
        except Exception as e:
            logger.error("[scenario_resynthesize] LLM stream error: %s", e)
            yield streaming_service.format_error(f"Synthesis failed: {str(e)}")
            yield streaming_service.format_done()
            return
    finally:
        # Only persist on clean completion — never partial content
        if stream_completed and accumulated:
            try:
                ahash = _assumptions_hash(assumptions)
                result = ScenarioResult(
                    thread_id=thread_id,
                    scenario=scenario,
                    assumptions_hash=ahash,
                    assumptions=assumptions,
                    content=accumulated,
                )
                session.add(result)
                await session.commit()
            except Exception as e:
                logger.warning(
                    "[scenario_resynthesize] Failed to persist scenario result: %s", e
                )

    yield streaming_service.format_data(
        "scenario-complete",
        {"scenario": scenario, "assumptions": assumptions, "content_length": len(accumulated)},
    )
    yield streaming_service.format_done()


@router.post("/resynthesize")
async def resynthesize_scenario(
    req: ResynthesizeRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
) -> StreamingResponse:
    # Reject base early — clients should display the original assistant message
    # rather than re-running synthesis (no useful work, wastes LLM tokens)
    if req.scenario == "base":
        raise HTTPException(
            status_code=400,
            detail="Use the original report for base scenario; no re-synthesis needed.",
        )

    # Verify thread ownership
    thread_result = await session.execute(
        select(NewChatThread).where(NewChatThread.id == req.thread_id)
    )
    thread = thread_result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if str(thread.created_by_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate assumptions are JSON-serializable (rejects NaN/Infinity)
    try:
        ahash = _assumptions_hash(req.assumptions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid assumptions: {e}")

    # Check cache
    cache_cutoff = datetime.now(UTC) - timedelta(minutes=_SCENARIO_CACHE_TTL_MINUTES)
    cached = await session.execute(
        select(ScenarioResult).where(
            ScenarioResult.thread_id == req.thread_id,
            ScenarioResult.scenario == req.scenario,
            ScenarioResult.assumptions_hash == ahash,
            ScenarioResult.created_at >= cache_cutoff,
        )
    )
    cached_result = cached.scalars().first()
    if cached_result and (cached_result.content or "").strip():
        streaming_service = VercelStreamingService()

        async def _serve_cache() -> AsyncGenerator[str, None]:
            yield streaming_service.format_data(
                "scenario-text-delta", {"delta": cached_result.content}
            )
            yield streaming_service.format_data(
                "scenario-complete",
                {
                    "scenario": req.scenario,
                    "assumptions": req.assumptions,
                    "cached": True,
                    "content_length": len(cached_result.content),
                },
            )
            yield streaming_service.format_done()

        return StreamingResponse(
            _serve_cache(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    # Suppress unused-arg lint — current_user retained for FastAPI dep injection
    _ = current_user

    return StreamingResponse(
        _stream_scenario_resynthesize(
            thread_id=req.thread_id,
            scenario=req.scenario,
            assumptions=req.assumptions,
            scope=req.scope,
            llm_config_id=req.llm_config_id,
            session=session,
        ),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
