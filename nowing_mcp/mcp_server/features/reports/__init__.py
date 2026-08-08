"""Report tools: list reports and export their content."""

from __future__ import annotations

import base64

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import READ

ExportFormat = Literal["pdf", "docx", "html", "latex", "epub", "odt", "plain"]

_TEXT_FORMATS = {"html", "latex", "plain"}
_BINARY_EXTENSIONS = {
    "pdf": "pdf",
    "docx": "docx",
    "html": "html",
    "latex": "tex",
    "epub": "epub",
    "odt": "odt",
    "plain": "txt",
}


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register report tools on the MCP server."""

    @mcp.tool(
        name="nowing_report_list",
        title="List reports in a workspace",
        annotations=READ,
        structured_output=False,
    )
    async def report_list(
        limit: Annotated[
            int, Field(ge=1, le=100, description="Maximum reports to return.")
        ] = 20,
        offset: Annotated[
            int, Field(ge=0, description="Number of reports to skip.")
        ] = 0,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """List reports the user has access to, newest first.

        Use this to find report ids and titles before exporting a report.
        Returns each report's id, title, style, and creation date.
        Example: limit=10.
        """
        resolved = await context.resolve(workspace)
        reports = await client.request(
            "GET",
            "/reports",
            params={"workspace_id": resolved.id, "limit": limit, "skip": offset},
        )
        reports = reports or []
        if response_format == "json":
            return to_json(reports)
        return _render_report_list(reports)

    @mcp.tool(
        name="nowing_report_export",
        title="Export a report in a chosen format",
        annotations=READ,
        structured_output=False,
    )
    async def report_export(
        report_id: Annotated[
            int, Field(description="Report id from nowing_report_list.")
        ],
        format: Annotated[
            ExportFormat,
            Field(
                description="Export format: pdf, docx, html, latex, epub, odt, or plain."
            ),
        ] = "pdf",
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Export a report (default PDF) and return its content.

        Text formats (plain, latex, html) come back readable as text. Binary
        formats (pdf, docx, epub, odt) are returned base64-encoded so they can
        be reconstructed byte-for-byte; the payload is shown here in a code
        block, and a long export is excerpted.
        Example: report_id=5, format='pdf'.
        """
        data, content_type = await client.request_bytes(
            "GET",
            f"/reports/{report_id}/export",
            params={"format": format},
        )
        if format in _TEXT_FORMATS:
            text = data.decode("utf-8", errors="replace")
            if response_format == "json":
                return to_json(
                    {"report_id": report_id, "format": format, "content": text}
                )
            return _render_text_export(report_id, format, content_type, text)
        encoded = base64.b64encode(data).decode("ascii")
        if response_format == "json":
            return to_json(
                {
                    "report_id": report_id,
                    "format": format,
                    "content_type": content_type,
                    "size_bytes": len(data),
                    "base64": encoded,
                }
            )
        return _render_binary_export(
            report_id, format, content_type, encoded, len(data)
        )


def _render_report_list(reports: list[dict]) -> str:
    if not reports:
        return "No reports found in this workspace."
    lines = [f"# {len(reports)} report(s) (newest first)", ""]
    for report in reports:
        style = report.get("report_style")
        style_text = f" [{style}]" if style else ""
        lines.append(
            f"- **{report.get('id')}**: {clip(report.get('title') or '(untitled)', 160)}"
            f"{style_text} — {report.get('created_at')}"
        )
    return "\n".join(lines).strip()


def _render_text_export(
    report_id: int, format: str, content_type: str | None, text: str
) -> str:
    header = f"# Exported report {report_id} ({format}, {content_type or 'text'})"
    return f"{header}\n\n```\n{clip(text, 20000)}\n```"


def _render_binary_export(
    report_id: int,
    format: str,
    content_type: str | None,
    encoded: str,
    size_bytes: int,
) -> str:
    extension = _BINARY_EXTENSIONS.get(format, format)
    header = (
        f"# Exported report {report_id} ({format}, {content_type or 'binary'}, "
        f"{size_bytes} bytes)"
    )
    if len(encoded) > 50000:
        # Base64 is decodable only when the length is a multiple of 4; clip
        # to the largest safe multiple and put the truncation marker outside
        # the code block so the payload stays valid.
        safe = (50000 // 4) * 4
        return (
            f"{header}\n\nDecode this base64 payload to reproduce the file "
            f"(e.g. `echo <payload> | base64 -d > report.{extension}`). "
            f"Payload is truncated from {size_bytes} bytes:\n\n"
            f"```text\n{encoded[:safe]}\n```\n\n"
            f"… [{len(encoded) - safe} more base64 characters truncated; "
            f"use `response_format='json'` for the full base64 payload.]"
        )
    return (
        f"{header}\n\nDecode this base64 payload to reproduce the file "
        f"(e.g. `echo <payload> | base64 -d > report.{extension}`):\n\n"
        f"```text\n{encoded}\n```"
    )
