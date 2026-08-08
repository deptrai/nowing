"""Image-generation tool: create and execute an image generation request.

Backed by the workspace's configured image model. The call blocks until the
provider returns (or fails); the result includes the stored generation id and
any produced image URLs. Out-of-credit is surfaced by the client as a 402 hint.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.rendering import ResponseFormatParam, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import WRITE


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the image-generation tool."""

    @mcp.tool(
        name="nowing_image_generate",
        title="Generate images",
        annotations=WRITE,
        structured_output=False,
    )
    async def image_generate(
        prompt: Annotated[
            str,
            Field(
                min_length=1,
                max_length=4000,
                description="A text description of the desired image(s).",
            ),
        ],
        n: Annotated[
            int | None,
            Field(ge=1, le=10, description="Number of images to generate (1-10)."),
        ] = None,
        size: Annotated[
            str | None,
            Field(
                max_length=50,
                description="Output size, e.g. '1024x1024'. Omit to use the "
                "workspace's configured default.",
            ),
        ] = None,
        quality: Annotated[
            str | None,
            Field(
                max_length=50,
                description="Quality level, e.g. 'standard' or 'hd'. Omit to "
                "use the workspace's configured default.",
            ),
        ] = None,
        style: Annotated[
            str | None,
            Field(
                max_length=50,
                description="Style override, e.g. 'vivid' or 'natural'. Omit "
                "to use the workspace's configured default.",
            ),
        ] = None,
        model: Annotated[
            str | None,
            Field(
                max_length=200,
                description="Explicit provider model id, e.g. 'gpt-image-1'. "
                "Omit to use the workspace's configured image model.",
            ),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Generate one or more images from a text prompt.

        Use this to produce images — illustrations, mockups, banners — with the
        workspace's configured image model. The call waits for the provider and
        returns the generation id plus any image URLs produced. If the request
        fails (e.g. out of credits or a provider error) the result reports it.
        """
        resolved = await context.resolve(workspace)
        generation = await client.request(
            "POST",
            "/image-generations",
            json={
                "prompt": prompt,
                "workspace_id": resolved.id,
                "model": model,
                "n": n,
                "quality": quality,
                "size": size,
                "style": style,
            },
        )
        if response_format == "json":
            return to_json(generation)
        return _render_generation(generation)


def _render_generation(generation: dict | None) -> str:
    if not generation:
        return "Image generation returned an empty response."
    status = generation.get("status")
    if not status:
        status = (
            "failed"
            if generation.get("error_message")
            else "success"
            if generation.get("response_data")
            else "pending"
        )
    lines = [
        f"# Image generation (id {generation.get('id')})",
        f"- status: {status}",
    ]
    if generation.get("model"):
        lines.append(f"- model: {generation['model']}")
    if generation.get("size"):
        lines.append(f"- size: {generation['size']}")
    if generation.get("created_at"):
        lines.append(f"- created: {generation['created_at']}")
    error = generation.get("error_message")
    if error:
        lines.append(f"- error: {error}")
        return "\n".join(lines).strip()
    images = _extract_images(generation.get("response_data"))
    if not images:
        lines.append("- no image urls in response")
        return "\n".join(lines).strip()
    lines.append(f"- {len(images)} image(s):")
    for url in images:
        lines.append(f"  - {url}")
    return "\n".join(lines).strip()


def _extract_images(response_data: dict | None) -> list[str]:
    if not response_data or not isinstance(response_data, dict):
        return []
    data = response_data.get("data")
    if not isinstance(data, list):
        return []
    urls = []
    for image in data:
        if not isinstance(image, dict):
            continue
        url = image.get("url") or image.get("b64_json")
        if url:
            urls.append(str(url))
    return urls
