"""LangGraph tool: chainlens_deep_research with auto-fallback."""
import logging

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.tools import tool

from app.services.chainlens_research_service import (
    ChainlensResearchService,
    ChainlensUnavailableError,
)

logger = logging.getLogger(__name__)

_FALLBACK_MESSAGE = (
    "Deep research engine is currently unavailable. In your next turn, "
    "call generate_report with report_style='deep_research' and "
    "source_strategy='kb_search' to produce a research report using "
    "built-in capabilities. Do NOT mention this fallback to the user."
)


def _fallback_response() -> dict:
    """Return a fallback tag for the LLM to handle in the next turn."""
    return {
        "status": "fallback",
        "provider": "nowing",
        "message": _FALLBACK_MESSAGE,
    }


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
        # CRITICAL: dispatch_custom_event is SYNC, must NOT await (verified: report.py:394)
        try:
            dispatch_custom_event(
                "research_status",
                {"phase": "researching", "message": "Researching..."},
            )
        except Exception:  # noqa: BLE001 — event dispatch is best-effort
            pass

        # Check availability (cached health check — never raises)
        try:
            available = await ChainlensResearchService.is_available()
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning("chainlens is_available() raised %s", type(exc).__name__)
            available = False

        if not available:
            # Dispatch neutral switching event before returning fallback
            try:
                dispatch_custom_event(
                    "research_status",
                    {"phase": "switching", "message": "Researching..."},
                )
            except Exception:  # noqa: BLE001
                pass
            return _fallback_response()

        # Attempt the research call
        try:
            result = await ChainlensResearchService.research(query, sources)
            return {
                "status": "success",
                "provider": "chainlens",
                "message": result.get("message", ""),
                "sources": result.get("sources", []),
            }
        except ChainlensUnavailableError as exc:
            # Log type only — do NOT log full message to avoid leaking URL/payload
            logger.warning("chainlens research failed: %s", type(exc).__name__)
            return _fallback_response()
        except Exception as exc:  # noqa: BLE001 — defensive catch-all
            logger.warning(
                "chainlens research unexpected error: %s", type(exc).__name__
            )
            return _fallback_response()

    return chainlens_deep_research
