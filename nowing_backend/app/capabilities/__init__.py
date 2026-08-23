"""Scraper capability registry — typed, stateless verbs. See plans/backend/04-capabilities.md."""

from __future__ import annotations

from app.capabilities import (
    amazon as _amazon,  # noqa: F401
    b2b as _b2b,  # noqa: F401
    browser_operator as _browser_operator,  # noqa: F401
    cafef as _cafef,  # noqa: F401
    chainlens as _chainlens,  # noqa: F401
    ecommerce as _ecommerce,  # noqa: F401
    indeed as _indeed,  # noqa: F401
    itviec as _itviec,  # noqa: F401
    leads as _leads,  # noqa: F401
    masothue as _masothue,  # noqa: F401
    news as _news,  # noqa: F401
    procurement as _procurement,  # noqa: F401
    realestate as _realestate,  # noqa: F401
    recruitment as _recruitment,  # noqa: F401
    social as _social,  # noqa: F401
    telegram as _telegram,  # noqa: F401
    topcv as _topcv,  # noqa: F401
    vietnamworks as _vietnamworks,  # noqa: F401
    vietstock as _vietstock,  # noqa: F401
    vn_jobs as _vn_jobs,  # noqa: F401
    walmart as _walmart,  # noqa: F401
    web_builder as _web_builder,  # noqa: F401
)

__all__: list[str] = []
