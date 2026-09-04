"""Vertical Alert Rule Templates package (Story 6.11)."""

from app.alerts.templates.compiler import (
    TemplateCompilationError,
    compile_template,
)
from app.alerts.templates.models import (
    AlertTemplate,
    AlertTemplateParameter,
    AlertTemplateRead,
)
from app.alerts.templates.registry import (
    VerticalAlertTemplateRegistry,
)

__all__ = [
    "AlertTemplate",
    "AlertTemplateParameter",
    "AlertTemplateRead",
    "TemplateCompilationError",
    "VerticalAlertTemplateRegistry",
    "compile_template",
]
