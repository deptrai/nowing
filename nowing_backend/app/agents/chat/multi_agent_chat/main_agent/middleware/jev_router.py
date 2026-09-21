"""Jev pre-router middleware — classify user intent before the LLM sees it.

Routes the classification through ``DecisionService.decide()`` (the AD-J1
port) with the registry ``subagent_routing`` question set, so the call
gets strict answer validation, the pinned model, the fallback chain, and
``TokenUsage`` telemetry for free. The result is injected as a
``<jev_routing_hint>`` system message that biases the main agent's
``task(subagent_type=...)`` choice — saving the LLM's routing reasoning
tokens and latency on every dispatch.

Design:
- Runs once per user message: the dedup marker scan is scoped to
  messages *after* the last HumanMessage (a checkpointed hint from an
  older turn cannot block a new one) and ``_last_classified`` remembers
  the text already classified so failure/below-threshold paths do not
  re-fire — and re-pay — on every model call in the react loop.
- Confidence-gated via ``ConfidenceGate.for_task("routing")``
  (``DECISION_ROUTING_THRESHOLD``, default 0.6). Below that, the LLM
  routes unaided.
- Fail-open absolutely: any exception inside ``abefore_model`` —
  backend, validation, DB, UUID — yields ``None`` and the turn
  continues without a hint.
- Zero-cost when disabled: the builder returns ``None`` early.

Feature flag: ``flags.enable_jev_router`` (default False). The decision
layer is separately gated by ``DECISION_ENABLED`` /
``DECISION_ROUTING_ENABLED`` inside ``decide()``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

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
from app.config.decision import decision_enabled, decision_task_enabled
from app.services.decision import (
    ConfidenceGate,
    DecisionError,
    InvalidDecisionAnswer,
    get_decision_service,
    get_question_registry,
)

if TYPE_CHECKING:
    from app.services.decision import DecisionResult, Question

logger = logging.getLogger(__name__)

_QUESTION_SET_NAME = "subagent_routing"
_QUESTION_ID = "subagent"
_NONE_NEEDED = "none_needed"
_HINT_MARKER = "<jev_routing_hint>"
# Small fixed budget for the token_usage commit — it runs outside the
# decision timeout and a wedged DB must not stall the pre-LLM hook.
_COMMIT_TIMEOUT_SECONDS = 2.0


class JevRouterMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Pre-route user messages via DecisionService before the LLM decides.

    Injects a ``<jev_routing_hint>`` system message when the routing
    answer's confidence passes the gate. The LLM can still override —
    the hint is advisory, not binding.
    """

    def __init__(
        self,
        *,
        subagent_descriptors: list[dict[str, str]] | None = None,
        workspace_id: int | None = None,
        user_id: str | None = None,
        client_id: str | None = None,
        thread_id: int | None = None,
    ) -> None:
        super().__init__()
        self._workspace_id = workspace_id
        self._user_id = user_id
        self._client_id = client_id
        self._thread_id = thread_id
        self._last_classified: str | None = None
        self._questions: dict[str, Question] | None = None
        self._question_set_label = ""
        self._required_state_keys: tuple[str, ...] = ()

        # Construction must never kill the agent build — a failure here
        # disables the router (abefore_model returns None early).
        try:
            # Criteria = registry options ∩ live subagent roster + the
            # ``none_needed`` escape hatch. Values stay the eval-tuned
            # registry descriptions — descriptor text is NOT used. A
            # missing/empty roster keeps the full registry set.
            qs = get_question_registry().get_set(_QUESTION_SET_NAME)
            question = qs.questions[_QUESTION_ID]
            registry_criteria = getattr(question, "criteria", {})
            live_names = {
                name
                for desc in subagent_descriptors or []
                if (name := desc.get("name", ""))
            }
            if live_names:
                criteria = {
                    name: description
                    for name, description in registry_criteria.items()
                    if name in live_names or name == _NONE_NEEDED
                }
                # A roster fully disjoint from the registry would leave
                # only none_needed — a confident answer would then
                # actively suppress live subagents. Fall back to the
                # full registry set instead.
                if set(criteria) == {_NONE_NEEDED}:
                    criteria = dict(registry_criteria)
            else:
                criteria = dict(registry_criteria)
            self._questions = {
                _QUESTION_ID: dataclasses.replace(question, criteria=criteria)
            }
            self._question_set_label = f"{qs.name}@{qs.version}"
            self._required_state_keys = qs.required_state_keys
        except Exception:
            logger.warning(
                "Jev router: question build failed — router disabled",
                exc_info=True,
            )

    async def _decide(self, user_text: str) -> DecisionResult:
        """Run the routing decision, wiring telemetry context.

        A session is opened only when ids make ``_record_usage``
        meaningful (session + workspace_id + user_id all required); it
        is committed in ``finally`` so even a failed ``decide()`` leg —
        which still records usage internally — is persisted.
        """
        user_uuid = None
        if self._user_id is not None:
            try:
                user_uuid = UUID(self._user_id)
            except (TypeError, ValueError):
                # A raw/non-UUID user_id would fail the telemetry flush —
                # pass None so _record_usage skips cleanly instead.
                logger.debug(
                    "Jev router: user_id %r is not a valid UUID — "
                    "usage telemetry will be skipped",
                    self._user_id,
                )

        decide_kwargs: dict[str, Any] = {
            "task": "routing",
            # model=None → the service applies its pin (anything else
            # raises invalid_model); timeout=None → the configured
            # DECISION_TIMEOUT_SECONDS ceiling.
            "model": None,
            "timeout": None,
            "question_set": self._question_set_label,
            "required_state_keys": self._required_state_keys,
            "workspace_id": self._workspace_id,
            "user_id": user_uuid,
            "client_id": self._client_id,
            "thread_id": self._thread_id,
        }
        service = get_decision_service()
        state = {"user_message": user_text}

        telemetry_ok = (
            self._workspace_id is not None
            and user_uuid is not None
            # Don't check out a DB session when the decision layer is
            # off — decide() raises `disabled` before doing any work.
            and decision_enabled()
            and decision_task_enabled("routing")
        )
        if not telemetry_ok:
            return await service.decide(
                state, self._questions, session=None, **decide_kwargs
            )

        from app.db import async_session_maker

        async with async_session_maker() as session:
            try:
                return await service.decide(
                    state, self._questions, session=session, **decide_kwargs
                )
            finally:
                try:
                    await asyncio.wait_for(
                        session.commit(), timeout=_COMMIT_TIMEOUT_SECONDS
                    )
                except Exception:  # telemetry commit failure; the hint must still ship
                    logger.warning(
                        "Jev router: token_usage commit failed", exc_info=True
                    )

    async def abefore_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        """Inject the routing hint before the LLM call. Never raises."""
        try:
            if self._questions is None:
                return None  # question build failed at construction

            messages = state.get("messages") or []

            # Find the last HumanMessage — tool calls may trail it in a
            # react loop, so it is not necessarily the trailing message.
            # Break on the FIRST HumanMessage found regardless of content:
            # an empty newest message means "nothing to classify", not
            # "fall back to an older one".
            last_human_idx = -1
            last_human: HumanMessage | None = None
            user_text = None
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if isinstance(msg, HumanMessage):
                    last_human_idx = i
                    last_human = msg
                    if isinstance(msg.content, str):
                        user_text = msg.content
                    elif isinstance(msg.content, list):
                        # Extract text blocks from multimodal content
                        texts = [
                            b.get("text", "")
                            for b in msg.content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                        user_text = " ".join(texts) if texts else None
                    break

            if not user_text or len(user_text.strip()) < 3:
                return None
            user_text = user_text.strip()

            # Once per user message. Dedup prefers the message id — a
            # shared (agent-cache) instance can see identical text from
            # different threads — and falls back to the stripped text.
            dedup_key = getattr(last_human, "id", None) or user_text
            if dedup_key == self._last_classified:
                return None
            # The marker scan only looks at messages AFTER the last
            # HumanMessage so a hint checkpointed from an older turn
            # cannot block a new message; _last_classified covers the
            # other direction — failure and below-threshold outcomes
            # must not re-fire (and re-pay) on every model call.
            for msg in messages[last_human_idx + 1 :]:
                if isinstance(msg, SystemMessage) and _HINT_MARKER in str(
                    msg.content
                ):
                    # Record the key too — if context editing later
                    # evicts the marker, a rebuilt middleware still
                    # won't re-pay for this message.
                    self._last_classified = dedup_key
                    return None  # already injected this turn

            # Mark BEFORE the paid call so error paths dedup too.
            self._last_classified = dedup_key

            result = await self._decide(user_text)

            answer = result.answers[_QUESTION_ID]
            gate = ConfidenceGate.for_task("routing")
            if not gate.passes(answer):
                logger.debug(
                    "Jev router below threshold: %s (%.2f < %.2f) — "
                    "skipping hint",
                    answer.value,
                    answer.confidence,
                    gate.threshold,
                )
                return None

            choice = answer.value
            confidence = answer.confidence

            if choice == _NONE_NEEDED:
                hint = (
                    f"{_HINT_MARKER}\n"
                    f"Jev pre-classification: this message likely needs no specialist "
                    f"(confidence={confidence:.0%}). Consider answering directly "
                    f"without a `task()` call.\n"
                    f"</jev_routing_hint>"
                )
            else:
                hint = (
                    f"{_HINT_MARKER}\n"
                    f"Jev pre-classification suggests routing to `{choice}` "
                    f"(confidence={confidence:.0%}). Use `task(subagent_type=\"{choice}\", ...)` "
                    f"if this matches the user's intent. You may override if the "
                    f"suggestion is wrong.\n"
                    f"</jev_routing_hint>"
                )

            logger.info(
                "Jev routing hint: %s (confidence=%.2f)",
                choice,
                confidence,
            )
            return {"messages": [SystemMessage(content=hint)]}
        except InvalidDecisionAnswer as exc:
            logger.warning(
                "Jev router: invalid decision answer — skipping hint: %s", exc
            )
            return None
        except DecisionError as exc:
            logger.warning(
                "Jev router: decision failed (code=%s) — skipping hint: %s",
                exc.code,
                exc,
            )
            return None
        except Exception:  # fail-open absolutely — a hook bug must not kill the turn
            logger.exception("Jev router: unexpected error — skipping hint")
            return None


def build_jev_router_mw(
    flags: AgentFeatureFlags,
    subagent_descriptors: list[dict[str, str]] | None = None,
    *,
    workspace_id: int | None = None,
    user_id: str | None = None,
    client_id: str | None = None,
    thread_id: int | None = None,
) -> JevRouterMiddleware | None:
    """Builder for the Jev pre-router middleware."""
    if not enabled(flags, "enable_jev_router"):
        return None
    return JevRouterMiddleware(
        subagent_descriptors=subagent_descriptors,
        workspace_id=workspace_id,
        user_id=user_id,
        client_id=client_id,
        thread_id=thread_id,
    )


__all__ = ["JevRouterMiddleware", "build_jev_router_mw"]
