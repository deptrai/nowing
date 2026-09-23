"""Narrative Report Engine package (Story 6.12)."""

from app.reports.narrative.engine import (
    NarrativeSynthesisEngine,
)
from app.reports.narrative.models import (
    NarrativeReportCreateRequest,
    NarrativeReportMetadata,
    NarrativeTemplate,
    NarrativeTemplateParameter,
    SourceCitation,
)
from app.reports.narrative.registry import (
    NarrativeTemplateRegistry,
)

__all__ = [
    "NarrativeReportCreateRequest",
    "NarrativeReportMetadata",
    "NarrativeSynthesisEngine",
    "NarrativeTemplate",
    "NarrativeTemplateParameter",
    "NarrativeTemplateRegistry",
    "SourceCitation",
]
