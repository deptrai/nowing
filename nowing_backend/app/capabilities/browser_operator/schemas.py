from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BrowserOperatorInput(BaseModel):
    action: Literal[
        "navigate",
        "click",
        "fill",
        "scroll",
        "extract",
        "take_screenshot",
        "detect_challenge",
    ] = Field(
        ...,
        description="Action to perform in the user's browser.",
    )
    url: str | None = Field(
        default=None,
        description="Target URL for navigation or context matching. Required for 'navigate'; optional for other actions to pick the matching browser tab.",
    )
    selector: str | None = Field(
        default=None,
        description="CSS selector for 'click', 'fill', or 'extract'.",
    )
    text: str | None = Field(
        default=None,
        description="Text to type for the 'fill' action.",
    )
    direction: Literal["up", "down"] = Field(
        default="down",
        description="Direction to scroll for the 'scroll' action.",
    )
    px: int = Field(
        default=400,
        description="Pixel distance to scroll (e.g. 400).",
    )
    format: Literal["png", "jpeg"] = Field(
        default="png",
        description="Format for the 'take_screenshot' action.",
    )


class BrowserOperatorOutput(BaseModel):
    success: bool
    action: str
    message: str
    data: dict[str, Any] | list[Any] | str | None = None
