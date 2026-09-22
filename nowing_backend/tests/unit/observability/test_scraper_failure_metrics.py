"""Unit tests for scraper ingest failure metrics (Story 35.3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.observability.metrics.platform import record_scraper_ingest_failure

pytestmark = [pytest.mark.unit]


def test_record_scraper_ingest_failure():
    """record_scraper_ingest_failure should add count with platform and reason labels."""
    with patch("app.observability.metrics.platform._add") as mock_add:
        record_scraper_ingest_failure("batdongsan", "captcha_detected")

    mock_add.assert_called_once()
    args, kwargs = mock_add.call_args
    assert args[1] == 1  # count increment
    assert args[2] == {"platform": "batdongsan", "reason": "captcha_detected"}
