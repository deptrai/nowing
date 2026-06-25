"""LangGraph tool: chainlens_deep_research with auto-fallback."""
import asyncio
import logging

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.tools import tool

from app.services.chainlens_research_service import (
    ChainlensResearchService,
    ChainlensUnavailableError,
)

logger = logging.getLogger(__name__)

# Outer timeout — service internal allows 2×125s with retry. Cap at 130s to bound agent turn.
_RESEARCH_OUTER_TIMEOUT_SECONDS = 130.0

# Neutral fallback instruction — does not reveal whether the engine is unavailable,
# disabled, or misconfigured. LLM switches to built-in report with `source_strategy="auto"`
# so it can use source_content, KB search, or general knowledge depending on what's available.
_FALLBACK_MESSAGE = (
    "Use the built-in research path for this turn. In your next turn, call "
    "generate_report with report_style='deep_research' and "
    "source_strategy='auto' to produce a research report using built-in "
    "capabilities. Do NOT mention this fallback to the user."
)


def _fallback_response() -> dict:
    """Return a fallback tag for the LLM to handle in the next turn."""
    return {
        "status": "fallback",
        "provider": "nowing",
        "message": _FALLBACK_MESSAGE,
    }


def _dispatch_event(phase: str) -> None:
    """Best-effort neutral status event — silent if not in LangGraph runtime context."""
    try:
        dispatch_custom_event(
            "research_status",
            {"phase": phase, "message": "Researching..."},
        )
    except Exception as exc:  # noqa: BLE001 — event dispatch is best-effort
        logger.debug("dispatch_custom_event skipped: %s", type(exc).__name__)


def create_chainlens_research_tool():
    """Factory function returning the chainlens_deep_research LangGraph tool."""

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
        and source_strategy="auto" to produce a fallback research report.
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
        # Neutral status event — dispatch_custom_event is SYNC, must NOT await
        _dispatch_event("researching")

        # Check availability (cached health check — never raises)
        try:
            available = await ChainlensResearchService.is_available()
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning("chainlens is_available() raised %s", type(exc).__name__)
            available = False

        if not available:
            _dispatch_event("switching")
            return _fallback_response()

        # Attempt the research call with an outer timeout
        try:
            result = await asyncio.wait_for(
                ChainlensResearchService.research(query, sources),
                timeout=_RESEARCH_OUTER_TIMEOUT_SECONDS,
            )
            message = (result.get("message") or "").strip()
            if not message:
                logger.warning("chainlens research returned empty message — falling back")
                _dispatch_event("switching")
                return _fallback_response()
            return {
                "status": "success",
                "provider": "chainlens",
                "message": message,
                "sources": result.get("sources") or [],
            }
        except ValueError as exc:
            # Input validation error from service (empty query / invalid sources).
            # Client-side bug, not an outage — still fall back so user gets an answer.
            logger.info("chainlens research rejected input: %s", exc)
            _dispatch_event("switching")
            return _fallback_response()
        except asyncio.TimeoutError:
            logger.warning(
                "chainlens research exceeded outer timeout (%.0fs)",
                _RESEARCH_OUTER_TIMEOUT_SECONDS,
            )
            _dispatch_event("switching")
            return _fallback_response()
        except ChainlensUnavailableError as exc:
            # Log type only — do NOT log full message to avoid leaking URL/payload
            logger.warning("chainlens research failed: %s", type(exc).__name__)
            _dispatch_event("switching")
            return _fallback_response()
        except Exception as exc:  # noqa: BLE001 — defensive catch-all
            logger.warning(
                "chainlens research unexpected error: %s", type(exc).__name__
            )
            _dispatch_event("switching")
            return _fallback_response()

    return chainlens_deep_research
