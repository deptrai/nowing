"""Shared HTTP(S) URL field type for scraper input schemas.

Ports the SurfSense #1623 pattern: every scraper schema declares URL lists as
``list[HttpUrlStr]`` instead of ``list[str]`` so malformed or non-http(s)
values are rejected by Pydantic before the scraper runs.

Contract (Story 2.9 AC-1/AC-6):
- Whitespace is trimmed before validation (``validators.url`` does not trim).
- Only ``http``/``https`` schemes are accepted (``validators.url`` accepts
  ``ftp``, so the scheme is checked explicitly).
- ``validators.url`` raises on malformed input instead of returning ``False``,
  so the call is wrapped in try/except.
- No normalization: trailing slashes, query strings, and fragments are kept —
  downstream scrapers expect the exact URL they were given.
- A generous 2048-char cap bounds pathological inputs.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

import validators
from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

MAX_URL_LENGTH = 2048

_ERROR = PydanticCustomError("http_url", "must be a valid http(s) URL")


def _validate_http_url(value: str) -> str:
    url = value.strip()
    if len(url) > MAX_URL_LENGTH:
        raise _ERROR
    try:
        is_valid = validators.url(url)
    except Exception:
        is_valid = False
    if not is_valid:
        raise _ERROR
    try:
        scheme = urlsplit(url).scheme.lower()
    except ValueError:
        raise _ERROR from None
    if scheme not in {"http", "https"}:
        raise _ERROR
    return url


HttpUrlStr = Annotated[str, AfterValidator(_validate_http_url)]
