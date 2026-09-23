"""Core metrics helpers shared by all domain metric modules.

This module keeps instrument creation, attribute scrubbing, and low-cardinality
helpers in one place. Domain modules import from here; they never import each
other or the package :mod:`__init__` to avoid circular dependencies.
"""

from __future__ import annotations

import contextlib
import gc
import logging
from functools import lru_cache
from importlib import metadata
from typing import Any

from app.observability import otel

logger = logging.getLogger(__name__)

_INSTRUMENTATION_NAME = "nowing.platform"
_ERROR_CATEGORY_UNKNOWN = "unknown"

_ERROR_CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rate_limited", ("ratelimit", "rate_limit", "toomanyrequests", "429")),
    ("auth_failed", ("authentication", "auth", "unauthorized", "forbidden")),
    ("quota_exhausted", ("quota", "insufficient", "credit", "billing")),
    ("timeout", ("timeout", "timedout", "deadline")),
    ("network_failed", ("connection", "connect", "network", "dns", "socket")),
    ("server_error", ("internalserver", "serviceunavailable", "badgateway", "gateway")),
    ("lock_contention", ("lock", "busy", "contention", "alreadyrunning")),
    ("unsupported_format", ("unsupported", "format", "filetype")),
    ("provider_error", ("provider", "apierror", "apistatus", "badrequest")),
)


def _package_version() -> str:
    """Best-effort telemetry tag only."""
    with contextlib.suppress(Exception):
        return metadata.version("surf-new-backend")
    return "unknown"


def _is_enabled() -> bool:
    return otel.is_enabled()


def _clean_attrs(attrs: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Drop empty values and coerce low-cardinality attrs to OTel-safe scalars."""
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float):
            cleaned[key] = value
            continue
        text = str(value)
        if text:
            cleaned[key] = text
    return cleaned


def _attrs_with_optional_error_category(
    attrs: dict[str, Any], error_category: str | None
) -> dict[str, Any]:
    if error_category:
        return {**attrs, "error.category": error_category}
    return attrs


def categorize_exception(exc: BaseException | None) -> str:
    """Return a low-cardinality category for an exception."""
    if exc is None:
        return _ERROR_CATEGORY_UNKNOWN
    haystack = " ".join(
        cls.__name__.replace("-", "").replace("_", "").lower()
        for cls in type(exc).__mro__
    )
    for category, hints in _ERROR_CATEGORY_HINTS:
        if any(hint in haystack for hint in hints):
            return category
    return _ERROR_CATEGORY_UNKNOWN


def parse_celery_task_label(task_name: str | None) -> str:
    """Return the operation token from a Celery task name."""
    if not task_name:
        return "unknown"
    operation = str(task_name).split("_", 1)[0].strip()
    return operation or "unknown"


def _record(callable_obj: Any, value: int | float, attrs: dict[str, Any]) -> None:
    if not _is_enabled():
        return
    with contextlib.suppress(Exception):
        callable_obj.record(value, _clean_attrs(attrs))


def _add(callable_obj: Any, value: int, attrs: dict[str, Any]) -> None:
    if not _is_enabled():
        return
    with contextlib.suppress(Exception):
        callable_obj.add(value, _clean_attrs(attrs))


@lru_cache(maxsize=1)
def _get_meter() -> Any:
    from opentelemetry import metrics

    return metrics.get_meter(_INSTRUMENTATION_NAME, _package_version())


def _runtime_snapshot_value(key: str, transform: Any = None) -> list[Any]:
    from opentelemetry.metrics import Observation

    from app.utils.perf import system_snapshot

    snap = system_snapshot()
    value = snap.get(key)
    if not isinstance(value, int | float) or value < 0:
        return []
    if transform is not None:
        value = transform(value)
    return [Observation(value)]


def _observe_gc_collections(_options: Any) -> list[Any]:
    from opentelemetry.metrics import Observation

    return [
        Observation(count, {"generation": str(generation)})
        for generation, count in enumerate(gc.get_count())
    ]
