"""Jev pre-router middleware — classify user intent before the LLM sees it.

Uses TypeSafe's Jev (System One model) to pre-classify the user's latest
message into a subagent routing decision. The result is injected into the
system prompt as a ``<jev_routing_hint>`` block that biases the main agent's
``task(subagent_type=...)`` choice — saving the LLM's routing reasoning
tokens and latency on every dispatch.

Design:
- Runs once per turn (first ``before_model`` call with a new HumanMessage).
- Jev ``Choice`` over the live subagent roster + ``none_needed``.
- Confidence-gated: hint is only injected when ``confidence >= threshold``
  (default 0.6). Below that, the LLM routes unaided.
- Non-blocking: Jev failure → skip hint, never block the turn.
- Zero-cost when disabled: middleware returns ``None`` early.

Feature flag: ``flags.enable_jev_router`` (default False).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.middleware.flags import enabled
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()

# ---------------------------------------------------------------------------
# Subagent roster — mirrors the eval's SUBAGENT_OPTIONS but kept generic.
# The middleware reads the live roster from the checkpointed subagent
# middleware's descriptor list at runtime.
# ---------------------------------------------------------------------------

_DEFAULT_JEV_INSTRUCTIONS = (
    "Which specialist should handle this user request? Pick the most "
    "specific match. If no specialist applies (casual chat, creative "
    "writing, general knowledge, coding help), pick 'none_needed'."
)

_CONFIDENCE_THRESHOLD = float(os.environ.get("JEV_ROUTER_CONFIDENCE", "0.6"))
_JEV_MODEL = os.environ.get("JEV_MODEL", "jev-latest")


class JevRouterMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Pre-route user messages via Jev before the LLM decides.

    Injects a ``<jev_routing_hint>`` system message when Jev's confidence
    exceeds the threshold. The LLM can still override — the hint is advisory,
    not binding.
    """

    def __init__(
        self,
        *,
        subagent_descriptors: list[dict[str, str]],
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        super().__init__()
        self._threshold = confidence_threshold
        # Build the Choice criteria from live subagent roster
        self._criteria: dict[str, str] = {}
        for desc in subagent_descriptors:
            name = desc.get("name", "")
            description = desc.get("description", "")
            if name:
                self._criteria[name] = description
        # Always include the "no agent needed" escape hatch
        self._criteria["none_needed"] = "Simple chat reply, no specialist needed"
        self._jev_client: Any = None
        self._jev_available: bool | None = None  # lazily probed

    async def _get_client(self) -> Any | None:
        """Lazily create the Jev client. Returns None if unavailable."""
        if self._jev_available is False:
            return None
        if self._jev_client is not None:
            return self._jev_client
        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            logger.debug("TYPESAFE_API_KEY not set — Jev router disabled")
            self._jev_available = False
            return None
        try:
            from typesafe_sdk import AsyncTypeSafeClient
            self._jev_client = AsyncTypeSafeClient()
            self._jev_available = True
            logger.info("Jev router client initialized (model=%s)", _JEV_MODEL)
            return self._jev_client
        except ImportError:
            logger.warning("typesafe-sdk not installed — Jev router disabled")
            self._jev_available = False
            return None
        except Exception:
            logger.warning("Jev client init failed — router disabled", exc_info=True)
            self._jev_available = False
            return None

    async def _classify(self, user_text: str) -> tuple[str | None, float | None]:
        """Run Jev classification. Returns (subagent_name, confidence) or (None, None)."""
        client = await self._get_client()
        if client is None:
            return None, None

        try:
            from typesafe_sdk import Choice
        except ImportError:
            return None, None

        start = time.perf_counter()
        try:
            response = await client.system_one(
                state={"user_message": user_text},
                questions={
                    "subagent": Choice(
                        instructions=_DEFAULT_JEV_INSTRUCTIONS,
                        criteria=self._criteria,
                    ),
                },
                model=_JEV_MODEL,
            )
            elapsed = (time.perf_counter() - start) * 1000

            answers = response.answers if hasattr(response, "answers") else {}
            ans = answers.get("subagent") if isinstance(answers, dict) else None
            if ans is None:
                _perf_log.info("[jev_router] no 'subagent' in answers (%.0fms)", elapsed)
                return None, None

            choice = getattr(ans, "choice", None) or (ans.get("choice") if isinstance(ans, dict) else None)
            confidence = getattr(ans, "confidence", None) or (ans.get("confidence") if isinstance(ans, dict) else None)

            _perf_log.info(
                "[jev_router] classified → %s (confidence=%.2f, %.0fms)",
                choice, confidence or 0, elapsed,
            )
            return choice, confidence

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("Jev classification failed (%.0fms): %s", elapsed, exc)
            return None, None

    async def abefore_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        """Inject Jev routing hint before the LLM call."""
        messages = state.get("messages") or []

        # Find the last HumanMessage — only classify fresh user input
        user_text = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and msg.content:
                if isinstance(msg.content, str):
                    user_text = msg.content
                elif isinstance(msg.content, list):
                    # Extract text blocks from multimodal content
                    texts = [
                        b.get("text", "") for b in msg.content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    user_text = " ".join(texts) if texts else None
                break

        if not user_text or len(user_text.strip()) < 3:
            return None

        # Skip if hint already injected for this message (avoid double-fire
        # on tool-call loops — only inject once per turn)
        hint_marker = "<jev_routing_hint>"
        for msg in messages:
            if isinstance(msg, SystemMessage) and hint_marker in str(msg.content):
                return None  # already injected

        choice, confidence = await self._classify(user_text)

        if choice is None or confidence is None:
            return None

        if confidence < self._threshold:
            logger.debug(
                "Jev router below threshold: %s (%.2f < %.2f) — skipping hint",
                choice, confidence, self._threshold,
            )
            return None

        if choice == "none_needed":
            hint = (
                f"{hint_marker}\n"
                f"Jev pre-classification: this message likely needs no specialist "
                f"(confidence={confidence:.0%}). Consider answering directly "
                f"without a `task()` call.\n"
                f"</jev_routing_hint>"
            )
        else:
            hint = (
                f"{hint_marker}\n"
                f"Jev pre-classification suggests routing to `{choice}` "
                f"(confidence={confidence:.0%}). Use `task(subagent_type=\"{choice}\", ...)` "
                f"if this matches the user's intent. You may override if the "
                f"suggestion is wrong.\n"
                f"</jev_routing_hint>"
            )

        logger.info(
            "Jev routing hint: %s (confidence=%.2f)",
            choice, confidence,
        )
        return {"messages": [SystemMessage(content=hint)]}


def build_jev_router_mw(
    flags: AgentFeatureFlags,
    subagent_descriptors: list[dict[str, str]] | None = None,
) -> JevRouterMiddleware | None:
    """Builder for the Jev pre-router middleware."""
    if not enabled(flags, "enable_jev_router"):
        return None
    if not os.environ.get("TYPESAFE_API_KEY"):
        logger.debug("TYPESAFE_API_KEY not set — Jev router middleware disabled")
        return None
    return JevRouterMiddleware(
        subagent_descriptors=subagent_descriptors or [],
    )


__all__ = ["JevRouterMiddleware", "build_jev_router_mw"]
