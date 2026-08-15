"""Viral Mechanics Deconstruction & 4-Tier Hook Taxonomy (Story 21.12 / AC 3 / AD-25)."""

from __future__ import annotations

import logging
from typing import Literal

from app.schemas.voice_profile import DeconstructedElements
from app.services.pii.redact import redact_pii

logger = logging.getLogger(__name__)


class ViralMechanicsDeconstructor:
    """Deconstructs viral posts into structural elements, sanitizes PII, and classifies hook taxonomies."""

    async def sanitize_and_redact(self, raw_content: str) -> str:
        """Sanitize phone numbers, emails, and names from post content per AD-25."""
        if not raw_content:
            return ""
        result = redact_pii(raw_content, context="social_template")
        # Replace placeholders with friendly tokens
        sanitized = (
            result.text.replace("<PHONE>", "[REDACTED_PHONE]")
            .replace("<EMAIL>", "[REDACTED_EMAIL]")
            .replace("<NAME>", "[REDACTED_NAME]")
        )
        return sanitized

    async def deconstruct(self, content: str) -> DeconstructedElements:
        """Deconstruct viral post into hook, re_hook, body, cta, and 4-tier hook taxonomy."""
        sanitized = await self.sanitize_and_redact(content)
        lines = [line.strip() for line in sanitized.split("\n") if line.strip()]

        if not lines:
            return DeconstructedElements(
                hook="",
                re_hook="",
                body="",
                cta="",
                taxonomy="contrarian_hook",
                analysis="why_it_worked: Empty post content",
            )

        # 1. Structural extraction
        if len(lines) == 1:
            hook = lines[0]
            re_hook = ""
            body = lines[0]
            cta = ""
        elif len(lines) == 2:
            hook = lines[0]
            re_hook = ""
            body = lines[1]
            cta = ""
        elif len(lines) == 3:
            hook = lines[0]
            re_hook = lines[1]
            body = lines[1]
            cta = lines[2]
        else:
            hook = lines[0]
            re_hook = lines[1]
            cta = lines[-1]
            body = "\n".join(lines[2:-1])

        # 2. Hook taxonomy classification
        lower_hook = hook.lower()

        taxonomy: Literal["contrarian_hook", "story_shift", "value_list", "data_reveal"]
        if any(
            w in lower_hook
            for w in [
                "hầu hết",
                "sai lầm",
                "đừng",
                "dừng",
                "sai cách",
                "đốt tiền",
                "sự thật",
                "ngừng",
            ]
        ):
            taxonomy = "contrarian_hook"
            analysis = "why_it_worked: Disruptive contrarian hook immediately stops scrolling by challenging conventional industry practices."
        elif any(
            w in lower_hook
            for w in ["quy trình", "bước", "bí quyết", "checklist", "top ", "cách"]
        ):
            taxonomy = "value_list"
            analysis = "why_it_worked: High-density actionable framework promises instant practical ROI."
        elif (
            any(char.isdigit() for char in hook)
            or "%" in hook
            or any(w in lower_hook for w in ["tỷ", "triệu", "roi", "$"])
        ):
            taxonomy = "data_reveal"
            analysis = "why_it_worked: Concrete statistical metrics or financial numbers create immediate credibility."
        else:
            taxonomy = "story_shift"
            analysis = "why_it_worked: Personal vulnerability and before-and-after journey build authentic emotional connection."

        return DeconstructedElements(
            hook=hook,
            re_hook=re_hook,
            body=body,
            cta=cta,
            taxonomy=taxonomy,
            analysis=analysis,
        )
