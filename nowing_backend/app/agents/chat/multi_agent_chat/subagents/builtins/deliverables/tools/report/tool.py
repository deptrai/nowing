"""Factory for inline Markdown reports: optional KB sourcing, section-aware revision, short-lived DB sessions."""

import asyncio
import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    resolve_root_thread_id,
)
from app.db import Report, shielded_async_session
from app.services.connector_service import ConnectorService
from app.services.llm_service import get_agent_llm

from ._parsing import (
    _extract_metadata,
    _render_kb_hits_for_report,
    _report_search_types,
    _strip_wrapping_code_fences,
)
from ._prompts import (
    _FORMATTING_RULES,
    _REPORT_FOOTER,
    _REPORT_PROMPT,
    _REVISION_PROMPT,
)
from ._revise import _revise_with_sections

# Keep the old ``tools.report`` logger name after the package split.
logger = logging.getLogger(__package__)


# ─── Tool Factory ───────────────────────────────────────────────────────────


def create_generate_report_tool(
    workspace_id: int,
    thread_id: int | None = None,
    connector_service: ConnectorService | None = None,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
):
    """Create the generate_report tool with injected dependencies.

    Uses short-lived DB sessions per operation so no connection is held during
    the long LLM call. Generation: new reports are single-shot; revisions try
    section-level first (unchanged sections preserved) and fall back to full-doc.
    Source strategies: provided/conversation (use source_content), kb_search
    (internal KB queries), auto (KB search only when source_content is thin).
    """

    @tool
    async def generate_report(
        topic: str,
        runtime: ToolRuntime,
        source_content: str = "",
        source_strategy: str = "provided",
        search_queries: list[str] | None = None,
        report_style: str = "detailed",
        user_instructions: str | None = None,
        parent_report_id: int | None = None,
    ) -> Command:
        """
        Generate a structured Markdown report artifact from provided content.

        Use this tool when the user asks to create, generate, write, produce,
        draft, or summarize into a report-style deliverable.

        Trigger classes include:
        - Direct trigger words WITH creation/modification verb: report,
          document, memo, letter, template, article, guide, blog post,
          one-pager, briefing, comprehensive guide.
        - Creation-intent phrases: "write a report", "generate a document",
          "draft a summary", "create an executive summary".
        - Modification-intent phrases: "revise the report", "update the
          report", "make it shorter", "add a section about X", "expand the
          budget section", "rewrite in formal tone".

        IMPORTANT — what does NOT count as "asking for a report":
        - Questions or discussion about a report or its topic are NOT report
          requests. Respond to these conversationally in chat.
          Examples: "What other examples to put there?", "What else could be
          added?", "Can you explain section 2?", "Is the data accurate?",
          "What's missing?", "How could this be improved?", "What other
          topics are related?"
        - Quick summary requests, explanations, or follow-up questions.
        - The test: Does the message contain a creation/modification VERB
          (write, create, generate, draft, add, revise, update, expand,
          rewrite, make) directed at producing a deliverable? If no verb
          → answer in chat.

        FORMAT/EXPORT RULE:
        - Always generate the report content in Markdown.
        - If the user requests DOCX/Word/PDF or another file format, export
          from the generated Markdown report.

        SOURCE STRATEGY (how to collect source material):
        - source_strategy="conversation" — The conversation already has
          enough context (prior Q&A, filesystem exploration, pasted text,
          uploaded files, scraped webpages). Pass a thorough summary as
          source_content.
        - source_strategy="kb_search" — Search the knowledge base
          internally. Provide 1-5 targeted search_queries. The tool
          handles searching internally — do NOT manually read and dump
          /documents/ files into source_content.
        - source_strategy="provided" — Use only what is in source_content
          (default, backward-compatible).
        - source_strategy="auto" — Use source_content if it has enough
          material; otherwise fall back to internal KB search using
          search_queries.

        CONVERSATION REUSE (HIGH PRIORITY):
        - If the user has been asking questions in this chat and the
          conversation contains substantive answers/discussion on the
          topic, prefer source_strategy="conversation" with a thorough
          summary of the full chat history as source_content.
        - The user's prior questions and your answers ARE the source
          material. Do NOT redundantly search the knowledge base for
          information that is already in the chat.

        VERSIONING — parent_report_id:
        - Set parent_report_id when the user wants to MODIFY, REVISE,
          IMPROVE, UPDATE, EXPAND, or ADD CONTENT TO an existing report
          that was already generated in this conversation.
        - This includes both explicit AND implicit modification requests.
          If the user references the existing report using words like "it",
          "this", "here", "the report", or clearly refers to a previously
          generated report, treat it as a revision request.
        - The value must be the report_id from a previous generate_report
          result in this same conversation.
        - Do NOT set parent_report_id when:
          * The user asks for a report on a completely NEW/DIFFERENT topic
          * The user says "generate another report" (new report, not revision)
          * There is no prior report to reference

        Examples of when to SET parent_report_id:
          User: "Make that report shorter" → parent_report_id = <previous report_id>
          User: "Add a cost analysis section to the report" → parent_report_id = <previous report_id>
          User: "Rewrite the report in a more formal tone" → parent_report_id = <previous report_id>
          User: "I want more details about pricing in here" → parent_report_id = <previous report_id>
          User: "Include more examples" → parent_report_id = <previous report_id>
          User: "Can you also cover nutrition in this?" → parent_report_id = <previous report_id>
          User: "Make it more detailed" → parent_report_id = <previous report_id>
          User: "Not bad, but expand on the budget section" → parent_report_id = <previous report_id>
          User: "Also mention the competitor landscape" → parent_report_id = <previous report_id>

        Examples of when to LEAVE parent_report_id as None:
          User: "Generate a report on climate change" → None (new topic)
          User: "Write me a report about the budget" → None (new topic)
          User: "Create another report, this time about marketing" → None
          User: "Now write one about travel trends in Europe" → None (new topic)

        Args:
            topic: Short title for the report (max ~8 words).
            source_content: Text to base the report on. Can be empty when
                using source_strategy="kb_search".
            source_strategy: How to collect source material. One of
                "provided", "conversation", "kb_search", or "auto".
            search_queries: When source_strategy is "kb_search" or "auto",
                provide 1-5 targeted search queries for the knowledge base.
                These should be specific, not just the topic repeated.
            report_style: "detailed", "deep_research", or "brief".
            user_instructions: Optional focus or modification instructions.
                When revising (parent_report_id set), describe WHAT TO CHANGE.
            parent_report_id: ID of a previous report to revise (creates new
                version in the same version group).

        Returns:
            Dict with status, report_id, title, word_count, and message.
        """
        # Shared with the _save_failed_report closure.
        parent_report_content: str | None = None
        report_group_id: int | None = None

        def _failed(payload: dict[str, Any], *, error: str) -> Command:
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="report",
                    operation="generate",
                    status="failed",
                    external_id=str(payload.get("report_id"))
                    if payload.get("report_id") is not None
                    else None,
                    preview=topic,
                    error=error,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        async def _save_failed_report(error_msg: str) -> int | None:
            """Persist a failed report row using a short-lived session."""
            try:
                async with shielded_async_session() as session:
                    failed_report = Report(
                        title=topic,
                        content=None,
                        report_metadata={
                            "status": "failed",
                            "error_message": error_msg,
                        },
                        report_style=report_style,
                        workspace_id=workspace_id,
                        thread_id=resolve_root_thread_id(runtime, thread_id),
                        report_group_id=report_group_id,
                    )
                    session.add(failed_report)
                    await session.commit()
                    await session.refresh(failed_report)
                    # New group (v1 failed): point the group at itself.
                    if not failed_report.report_group_id:
                        failed_report.report_group_id = failed_report.id
                        await session.commit()
                    logger.info(
                        f"[generate_report] Saved failed report {failed_report.id}: {error_msg}"
                    )
                    return failed_report.id
            except Exception:  # best-effort failed report persistence; return None
                logger.exception(
                    "[generate_report] Could not persist failed report row"
                )
                return None

        try:
            # ── Phase 1: READ (short-lived session) ──────────────────────
            # Fetch parent report + LLM config, then release the connection
            # before the long LLM call.
            async with shielded_async_session() as read_session:
                if parent_report_id:
                    parent_report = await read_session.get(Report, parent_report_id)
                    if parent_report:
                        report_group_id = parent_report.report_group_id
                        parent_report_content = parent_report.content
                        logger.info(
                            f"[generate_report] Creating new version from parent {parent_report_id} "
                            f"(group {report_group_id})"
                        )
                    else:
                        logger.warning(
                            f"[generate_report] parent_report_id={parent_report_id} not found, "
                            "creating standalone report"
                        )

                llm = await get_agent_llm(read_session, workspace_id)

            if not llm:
                error_msg = (
                    "No LLM configured. Please configure a chat model in Settings."
                )
                report_id = await _save_failed_report(error_msg)
                return _failed(
                    {
                        "status": "failed",
                        "error": error_msg,
                        "report_id": report_id,
                        "title": topic,
                    },
                    error=error_msg,
                )

            user_instructions_section = ""
            if user_instructions:
                user_instructions_section = (
                    f"**Additional Instructions:** {user_instructions}"
                )

            # ── Phase 1b: SOURCE COLLECTION (smart KB search) ────────────
            # Decide whether to augment source_content with KB search results.
            effective_source = source_content or ""

            strategy = (source_strategy or "provided").lower().strip()

            needs_kb_search = False
            if strategy == "kb_search":
                needs_kb_search = True
            elif strategy == "auto":
                # Heuristic: if source_content has fewer than 200 words,
                # it's likely insufficient — augment with KB search.
                word_count_estimate = len(effective_source.split())
                if word_count_estimate < 200:
                    needs_kb_search = True
                    logger.info(
                        f"[generate_report] auto strategy: source has ~{word_count_estimate} words, "
                        "triggering KB search"
                    )
            # "provided" and "conversation" → use source_content as-is

            if needs_kb_search and connector_service and search_queries:
                query_count = min(len(search_queries), 5)
                dispatch_custom_event(
                    "report_progress",
                    {
                        "phase": "kb_search",
                        "message": f"Searching knowledge base ({query_count} queries)...",
                    },
                )
                logger.info(
                    f"[generate_report] Running internal KB search with "
                    f"{query_count} queries: {search_queries[:5]}"
                )
                try:
                    from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
                        search_chunks,
                    )
                    from app.agents.chat.multi_agent_chat.shared.retrieval.models import (
                        DocumentHit,
                        SearchScope,
                    )

                    scope = SearchScope(
                        document_types=_report_search_types(
                            available_connectors, available_document_types
                        )
                    )

                    # Each query gets its own short-lived session.
                    async def _run_single_query(q: str) -> list[DocumentHit]:
                        async with shielded_async_session() as kb_session:
                            return await search_chunks(
                                kb_session,
                                workspace_id=workspace_id,
                                query=q,
                                scope=scope,
                                top_k=10,
                            )

                    hits_per_query = await asyncio.gather(
                        *[_run_single_query(q) for q in search_queries[:5]]
                    )

                    seen_doc_ids: set[int] = set()
                    merged_hits: list[DocumentHit] = []
                    for hits in hits_per_query:
                        for hit in hits:
                            if hit.document_id in seen_doc_ids:
                                continue
                            seen_doc_ids.add(hit.document_id)
                            merged_hits.append(hit)

                    kb_combined = _render_kb_hits_for_report(merged_hits)
                    if kb_combined.strip():
                        if effective_source.strip():
                            effective_source = (
                                effective_source
                                + "\n\n--- Knowledge Base Search Results ---\n\n"
                                + kb_combined
                            )
                        else:
                            effective_source = kb_combined

                        doc_count = len(merged_hits)
                        dispatch_custom_event(
                            "report_progress",
                            {
                                "phase": "kb_search_done",
                                "message": f"Found {doc_count} relevant documents",
                            },
                        )
                        logger.info(
                            f"[generate_report] KB search added ~{len(kb_combined)} chars "
                            f"from {doc_count} documents"
                        )
                    else:
                        dispatch_custom_event(
                            "report_progress",
                            {
                                "phase": "kb_search_done",
                                "message": "No results found in knowledge base",
                            },
                        )
                        logger.info("[generate_report] KB search returned no results")

                except Exception as e:  # KB search query failure; proceed with existing source content
                    logger.warning(
                        f"[generate_report] Internal KB search failed: {e}. "
                        "Proceeding with existing source_content."
                    )
            elif needs_kb_search and not connector_service:
                logger.warning(
                    "[generate_report] KB search requested but connector_service "
                    "not available. Using source_content as-is."
                )
            elif needs_kb_search and not search_queries:
                logger.warning(
                    "[generate_report] KB search requested but no search_queries "
                    "provided. Using source_content as-is."
                )

            capped_source = effective_source[:100000]

            # Length constraint only when the user explicitly asked for brevity.
            length_instruction = ""
            if report_style == "brief":
                length_instruction = (
                    "**LENGTH CONSTRAINT (MANDATORY):** The user wants a SHORT report. "
                    "Keep it concise — aim for ~400 words (~1 page) unless a different "
                    "length is specified in the Additional Instructions above. "
                    "Prioritize brevity over thoroughness. Do NOT write a long report."
                )

            # ── Phase 2: LLM GENERATION (no DB connection held) ──────────

            report_content: str | None = None

            if parent_report_content:
                # Revision mode: section-level first (preserves untouched
                # sections), falling back to full-doc revision.
                dispatch_custom_event(
                    "report_progress",
                    {
                        "phase": "revision_start",
                        "message": "Analyzing sections to modify...",
                    },
                )
                logger.info(
                    "[generate_report] Revision mode — attempting section-level revision"
                )
                report_content = await _revise_with_sections(
                    llm=llm,
                    parent_content=parent_report_content,
                    user_instructions=user_instructions
                    or "Improve and refine the report.",
                    source_content=capped_source,
                    topic=topic,
                    report_style=report_style,
                )

                if report_content is None:
                    dispatch_custom_event(
                        "report_progress",
                        {"phase": "writing", "message": "Rewriting your full report"},
                    )
                    logger.info(
                        "[generate_report] Section-level revision deferred, "
                        "using full-document revision"
                    )
                    prompt = _REVISION_PROMPT.format(
                        topic=topic,
                        report_style=report_style,
                        user_instructions_section=user_instructions_section
                        or "Improve and refine the report.",
                        source_content=capped_source,
                        previous_report_content=parent_report_content,
                        length_instruction=length_instruction,
                        formatting_rules=_FORMATTING_RULES,
                    )
                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    report_content = response.content

            else:
                # New report: single-shot generation (one LLM call).
                dispatch_custom_event(
                    "report_progress",
                    {"phase": "writing", "message": "Writing your report"},
                )
                logger.info(
                    "[generate_report] New report — using single-shot generation"
                )
                prompt = _REPORT_PROMPT.format(
                    topic=topic,
                    report_style=report_style,
                    user_instructions_section=user_instructions_section,
                    previous_version_section="",
                    source_content=capped_source,
                    length_instruction=length_instruction,
                    formatting_rules=_FORMATTING_RULES,
                )
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                report_content = response.content

            if not report_content or not isinstance(report_content, str):
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return _failed(
                    {
                        "status": "failed",
                        "error": error_msg,
                        "report_id": report_id,
                        "title": topic,
                    },
                    error=error_msg,
                )

            # LLMs often wrap output in ```markdown ... ``` fences — strip them
            report_content = _strip_wrapping_code_fences(report_content)

            if not report_content:
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return _failed(
                    {
                        "status": "failed",
                        "error": error_msg,
                        "report_id": report_id,
                        "title": topic,
                    },
                    error=error_msg,
                )

            # Strip any existing footer(s) carried over from parent version(s)
            while report_content.rstrip().endswith(_REPORT_FOOTER):
                idx = report_content.rstrip().rfind(_REPORT_FOOTER)
                report_content = report_content[:idx].rstrip()
                if report_content.rstrip().endswith("---"):
                    report_content = report_content.rstrip()[:-3].rstrip()

            # Append exactly one standard footer.
            report_content += "\n\n---\n\n" + _REPORT_FOOTER

            metadata = _extract_metadata(report_content)

            # ── Phase 3: WRITE (short-lived session) ─────────────────────
            async with shielded_async_session() as write_session:
                report = Report(
                    title=topic,
                    content=report_content,
                    report_metadata=metadata,
                    report_style=report_style,
                    workspace_id=workspace_id,
                    thread_id=resolve_root_thread_id(runtime, thread_id),
                    report_group_id=report_group_id,
                )
                write_session.add(report)
                await write_session.commit()
                await write_session.refresh(report)

                # Brand-new report (v1): point the group at itself.
                if not report.report_group_id:
                    report.report_group_id = report.id
                    await write_session.commit()

                saved_report_id = report.id
                saved_group_id = report.report_group_id

            logger.info(
                f"[generate_report] Created report {saved_report_id} "
                f"(group={saved_group_id}): "
                f"{metadata.get('word_count', 0)} words, "
                f"{metadata.get('section_count', 0)} sections"
            )

            payload: dict[str, Any] = {
                "status": "ready",
                "report_id": saved_report_id,
                "title": topic,
                "word_count": metadata.get("word_count", 0),
                "is_revision": bool(parent_report_content),
                "report_markdown": report_content,
                "message": f"Report generated successfully: {topic}",
            }
            receipt = make_receipt(
                route="deliverables",
                type="report",
                operation="generate",
                status="success",
                external_id=str(saved_report_id),
                preview=topic,
            )
            return with_receipt(
                payload=payload,
                receipt=receipt,
                tool_call_id=runtime.tool_call_id,
            )

        except Exception as e:  # tool execution failure → persist failure and return degraded result
            error_message = str(e)
            logger.exception(f"[generate_report] Error: {error_message}")
            report_id = await _save_failed_report(error_message)
            return _failed(
                {
                    "status": "failed",
                    "error": error_message,
                    "report_id": report_id,
                    "title": topic,
                },
                error=error_message,
            )

    return generate_report
