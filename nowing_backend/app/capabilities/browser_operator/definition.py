from __future__ import annotations

from app.capabilities.browser_operator.executor import build_browser_operator_executor
from app.capabilities.browser_operator.schemas import (
    BrowserOperatorInput,
    BrowserOperatorOutput,
)
from app.capabilities.core import Capability, register_capability

BROWSER_OPERATOR_EXECUTE = Capability(
    name="browser_operator.execute",
    description=(
        "Directly control the user's browser via the connected Nowing Chrome Extension using CDP. "
        "Use this tool when the user asks to navigate to a website, scroll up/down, "
        "click an element, fill/enter text, extract content, take a screenshot, or detect CAPTCHA/2FA. "
        "The action field is one of: navigate, click, fill, scroll, extract, take_screenshot, detect_challenge."
    ),
    input_schema=BrowserOperatorInput,
    output_schema=BrowserOperatorOutput,
    executor=build_browser_operator_executor(),
    billing_unit=None,
    docs_url="/docs/capabilities/browser-operator",
)

register_capability(BROWSER_OPERATOR_EXECUTE)
