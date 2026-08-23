import json
import logging
import uuid
from collections.abc import Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

from app.redis_client import get_redis_client
from app.schemas.dsh import BrowserOperatorCdpPayload
from app.services.pii.redact import redact_pii

MissionState = dict[str, Any]

logger = logging.getLogger(__name__)

# Hard ceiling for an extension to respond to a single CDP command (AC-2 / AD-108).
_CDP_RESULT_TIMEOUT_SECONDS = 60
# Max number of stale results to keep per mission. Avoids Redis list bloat.
_CDP_RESULT_QUEUE_MAXLEN = 5


class HumanInterventionRequired(Exception):  # noqa: N818
    """Raised when the agent encounters a CAPTCHA or requires human takeover."""


class CdpExecutionError(RuntimeError):
    """Raised when CDP execution fails but a graceful degradation is possible."""


class BrowserOperatorCdpSubgraph:
    """Subgraph for executing native browser CDP commands via extension."""

    def __init__(self, rest_client: Any) -> None:
        self.rest_client = rest_client

    @classmethod
    def build(cls, rest_client: Any) -> StateGraph:
        subgraph = StateGraph(MissionState)
        instance = cls(rest_client)

        subgraph.add_node("cdp_crawl", instance._cdp_crawl_node)
        subgraph.add_edge(START, "cdp_crawl")
        subgraph.add_edge("cdp_crawl", END)

        return subgraph.compile()

    @staticmethod
    def _redact_cdp_value(value: Any) -> Any:
        """Redact PII in string/CDP values before logging/checkpointing.

        Fail-soft: if redaction raises, log the incident and return a marker
        instead of aborting the mission.
        """
        if isinstance(value, str):
            try:
                return redact_pii(value, context="lead_enrichment").text
            except Exception as exc:
                logger.warning("PII redaction failed for CDP value: %s", exc)
                return "<redaction_failed>"
        return value

    @classmethod
    def _redact_cdp_data(cls, data: Any) -> Any:
        """Recursively redact strings inside a CDP result / dict."""
        if isinstance(data, Mapping):
            return {k: cls._redact_cdp_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [cls._redact_cdp_data(v) for v in data]
        return cls._redact_cdp_value(data)

    async def _cdp_crawl_node(self, state: MissionState, config: RunnableConfig) -> MissionState:
        logger.info("Executing CDP crawl step.")
        _ = config

        payload = state.get("payload") or {}
        mission_id = state.get("mission_id")
        resolved_user_id = state.get("user_id")

        if not mission_id:
            raise ValueError("mission_id is required in state to run CDP Subgraph.")
        if not resolved_user_id:
            raise ValueError("user_id is required in state to route CDP commands.")

        try:
            payload_model = BrowserOperatorCdpPayload.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"Invalid CDP mission payload: {exc}") from exc

        target_url = str(payload_model.target_url)

        redis = await get_redis_client()
        channel = f"cdp_stream:{resolved_user_id}"
        result_key = f"cdp_result:{resolved_user_id}:{mission_id}"

        # Ensure the result queue is capped to avoid bloat across retries/resumes.
        await redis.delete(result_key)

        # Check that at least one SSE client is listening before we publish.
        try:
            subs = await redis.pubsub_numsub(channel)
            if subs and subs[0][1] == 0:
                raise HumanInterventionRequired("No extension listening for CDP takeover")
        except HumanInterventionRequired:
            raise
        except Exception as exc:
            # If we cannot check subscription state due to a Redis error, surface it
            # as a degradation error so the retry/ DLQ path can distinguish it from
            # a genuine "no extension" condition.
            raise CdpExecutionError(f"Cannot verify extension CDP subscription: {exc}") from exc

        command_id = uuid.uuid4().hex
        cmd = {
            "action": "navigate",
            "url": target_url,
            "mission_id": str(mission_id),
            "command_id": command_id,
            "user_id": str(resolved_user_id),
        }

        # Publish command as an SSE event through the Redis pub/sub channel.
        await redis.publish(channel, json.dumps(cmd))

        # Wait for the extension to post the result.
        result_tuple = await redis.blpop(result_key, timeout=_CDP_RESULT_TIMEOUT_SECONDS)

        if not result_tuple:
            raise HumanInterventionRequired(
                "CDP takeover timed out: extension did not respond within 60s"
            )

        _, result_data = result_tuple
        try:
            parsed_result = json.loads(result_data)
        except json.JSONDecodeError as exc:
            raise CdpExecutionError(f"Malformed CDP result received from extension: {exc}") from exc

        if not isinstance(parsed_result, dict):
            raise CdpExecutionError("CDP result must be a JSON object")

        if parsed_result.get("requires_human"):
            challenge = parsed_result.get("challenge", "challenge")
            exc = HumanInterventionRequired(f"CDP requires human intervention: {challenge}")
            exc.challenge = challenge
            exc.target_url = target_url
            raise exc

        if parsed_result.get("error"):
            error_msg = parsed_result["error"]
            # Degrade on extension-reported CDP errors instead of crashing the mission.
            logger.warning("CDP execution failed for mission %s: %s", mission_id, error_msg)
            raise CdpExecutionError(f"Extension CDP execution failed: {error_msg}")

        # Verify the result belongs to the command we just sent. A mismatch means
        # we received a stale result, possibly from a previous command or a race.
        if parsed_result.get("command_id") != command_id:
            raise CdpExecutionError(
                f"CDP result command_id mismatch for mission {mission_id}: "
                f"expected {command_id}, got {parsed_result.get('command_id')}"
            )

        cdp_res = parsed_result.get("result") or {}

        # Build a source shape compatible with the downstream extraction node.
        # Prefer the URL the extension actually navigated to.
        navigated_url = cdp_res.get("navigatedUrl") or cdp_res.get("url") or target_url
        cdp_source = {
            "url": navigated_url,
            "domain": _extract_domain(navigated_url),
            "title": cdp_res.get("title", ""),
            "tab_id": cdp_res.get("tabId"),
        }

        sources = parsed_result.get("sources")
        if not isinstance(sources, list):
            sources = [cdp_source] if cdp_res else []

        # Sanitize sources: ensure shape and redact any raw text/html.
        sanitized_sources = []
        for source in sources:
            if isinstance(source, Mapping):
                url = source.get("navigatedUrl") or source.get("url") or navigated_url
                normalized = {
                    "url": url,
                    "domain": _extract_domain(url),
                    "title": source.get("title", ""),
                    "tab_id": source.get("tabId"),
                    "html": source.get("html", ""),
                    "text": source.get("text", ""),
                }
                normalized = self._redact_cdp_data(normalized)
                sanitized_sources.append(normalized)

        redacted_res = self._redact_cdp_data(cdp_res)
        redacted_parsed = self._redact_cdp_data(parsed_result)

        logger.info(
            "Received CDP result for mission %s: command_id=%s sources=%s",
            mission_id,
            command_id,
            len(sanitized_sources),
        )

        subtasks = list(state.get("subtasks") or [])
        subtasks.append(
            {
                "id": "cdp_crawl",
                "status": "success",
                "sources_count": len(sanitized_sources),
            }
        )

        state["sources"] = sanitized_sources
        state["subtasks"] = subtasks

        state_checkpoint = dict(state.get("checkpoint") or {})
        state_checkpoint["cdp_last_result"] = redacted_res
        state_checkpoint["sources"] = sanitized_sources
        state_checkpoint["subtasks"] = subtasks
        # Keep a PII-redacted trace of the raw command/result for debugging.
        try:
            redacted_url = redact_pii(target_url, context="lead_enrichment").text
        except Exception as exc:
            logger.warning("PII redaction failed for CDP target URL: %s", exc)
            redacted_url = "<redaction_failed>"
        state_checkpoint["cdp_last_command"] = {
            "action": "navigate",
            "url": redacted_url,
            "command_id": command_id,
        }
        state_checkpoint["cdp_last_response"] = redacted_parsed
        state["checkpoint"] = state_checkpoint

        # Trim the result queue so future runs/resumes keep only the most recent results.
        await redis.ltrim(result_key, -_CDP_RESULT_QUEUE_MAXLEN, -1)

        return state


def _extract_domain(url: str | None) -> str | None:
    from urllib.parse import urlparse

    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed.netloc if parsed.netloc else None
    except Exception:
        return None
