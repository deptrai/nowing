"""Scraper capability registry — typed, stateless verbs. See plans/backend/04-capabilities.md."""

from __future__ import annotations

from app.capabilities import (
    amazon as _amazon,  # noqa: F401
    indeed as _indeed,  # noqa: F401
    itviec as _itviec,  # noqa: F401
    topcv as _topcv,  # noqa: F401
    vietnamworks as _vietnamworks,  # noqa: F401
    vn_jobs as _vn_jobs,  # noqa: F401
    walmart as _walmart,  # noqa: F401
)

__all__: list[str] = []
