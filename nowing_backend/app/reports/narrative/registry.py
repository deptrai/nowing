"""Registry for canonical Narrative Report Templates (Story 6.12)."""

from __future__ import annotations

from typing import ClassVar

from app.reports.narrative.models import (
    NarrativeTemplate,
    NarrativeTemplateParameter,
)


class NarrativeTemplateRegistry:
    """Registry maintaining pre-configured narrative templates for indexed data."""

    _templates: ClassVar[dict[str, NarrativeTemplate]] = {}

    @classmethod
    def register(cls, template: NarrativeTemplate) -> None:
        cls._templates[template.template_id] = template

    @classmethod
    def get(cls, template_id: str) -> NarrativeTemplate | None:
        cls._ensure_initialized()
        return cls._templates.get(template_id)

    @classmethod
    def list_all(cls) -> list[NarrativeTemplate]:
        cls._ensure_initialized()
        return list(cls._templates.values())

    @classmethod
    def _ensure_initialized(cls) -> None:
        if cls._templates:
            return

        # 1. News Digest & Synthesis
        cls.register(
            NarrativeTemplate(
                template_id="news_digest",
                name="News Digest & Synthesis",
                description="Synthesize indexed press articles and news topics into structured executive digests with citations.",
                narrative_style="digest",
                required_capability="news.entity_search",
                parameters=[
                    NarrativeTemplateParameter(
                        name="topic",
                        label="Topic or Entity Name",
                        description="Tracked industry, keyword, or company (e.g. AI Vietnam, VinFast)",
                        type="string",
                        required=True,
                    ),
                    NarrativeTemplateParameter(
                        name="timeframe_days",
                        label="Timeframe (Days)",
                        description="Window of indexed news to summarize",
                        type="integer",
                        required=False,
                        default=7,
                    ),
                    NarrativeTemplateParameter(
                        name="max_sources",
                        label="Max Articles to Analyze",
                        type="integer",
                        required=False,
                        default=15,
                    ),
                ],
            )
        )

        # 2. Financial Trend Detection
        cls.register(
            NarrativeTemplate(
                template_id="financial_trend",
                name="Financial Trend & Margin Trajectory",
                description="Detect quarterly trajectory in revenue, gross margins, and debt ratios for Vietnamese public companies.",
                narrative_style="trend",
                required_capability="cafef.scrape",
                parameters=[
                    NarrativeTemplateParameter(
                        name="symbol",
                        label="Stock Ticker Symbol",
                        description="3-letter ticker (e.g. VNM, FPT, HPG)",
                        type="string",
                        required=True,
                    ),
                    NarrativeTemplateParameter(
                        name="metrics",
                        label="Financial Metrics to Highlight",
                        description="Comma-separated metrics: revenue, margin, debt",
                        type="string",
                        required=False,
                        default="revenue, margin, debt",
                    ),
                    NarrativeTemplateParameter(
                        name="periods",
                        label="Historical Quarters",
                        type="integer",
                        required=False,
                        default=4,
                    ),
                ],
            )
        )

        # 3. Corporate Registry Event Timeline
        cls.register(
            NarrativeTemplate(
                template_id="company_timeline",
                name="Corporate Event & Registry Timeline",
                description="Chronological event evolution covering legal representatives, tax status, and capital adjustments.",
                narrative_style="timeline",
                required_capability="masothue.scrape",
                parameters=[
                    NarrativeTemplateParameter(
                        name="company_name_or_tax_code",
                        label="Company Name or Tax Code (MST)",
                        description="10-digit/13-digit MST or exact corporate entity name",
                        type="string",
                        required=True,
                    ),
                    NarrativeTemplateParameter(
                        name="event_categories",
                        label="Event Categories",
                        description="Filter categories (e.g. all, legal, business, leadership)",
                        type="string",
                        required=False,
                        default="all",
                    ),
                ],
            )
        )
