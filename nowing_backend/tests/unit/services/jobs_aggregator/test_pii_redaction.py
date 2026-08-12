"""ATDD tests for jobs_aggregator PII redaction (Story 12-4c)."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.services.jobs_aggregator.orchestrator import _redact_listing
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing
from app.services.pii.redact import RedactedText

pytestmark = pytest.mark.unit


@pytest.fixture
def sample_listing() -> VnJobAggregatedListing:
    """Return a sample job listing with PII in description/requirement."""
    return VnJobAggregatedListing(
        id="vw:123",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Liên hệ 0901234567 hoặc hr@example.com để apply.",
        job_requirement="Gặp Nguyễn Văn A tại văn phòng.",
        confidence_score=0.7,
    )


def test_redact_listing_calls_record_vn_jobs_pii_detected_for_each_pii_type(
    sample_listing,
):
    """_redact_listing calls record_vn_jobs_pii_detected for each PII type."""
    with patch(
        "app.services.jobs_aggregator.orchestrator.record_vn_jobs_pii_detected"
    ) as mock_record:
        _redact_listing(sample_listing)

    # Should be called for phone, email, and name
    assert mock_record.call_count >= 3

    # Verify calls include pii_type parameter
    call_args_list = [call.kwargs for call in mock_record.call_args_list]
    pii_types = [args.get("pii_type") for args in call_args_list]
    assert "phone" in pii_types
    assert "email" in pii_types
    assert "name" in pii_types


def test_redact_listing_logs_pii_counts_as_structured_log_not_values(
    sample_listing, caplog
):
    """PII counts are logged as structured log (not values)."""
    with patch("app.services.jobs_aggregator.orchestrator.record_vn_jobs_pii_detected"), caplog.at_level(logging.INFO):
        _redact_listing(sample_listing)

    # Check that logs contain count information but not actual PII values
    log_messages = [record.message for record in caplog.records]
    assert any("pii" in msg.lower() for msg in log_messages)

    # Ensure actual phone/email/name values are NOT in logs
    for msg in log_messages:
        assert "0901234567" not in msg
        assert "hr@example.com" not in msg
        assert "Nguyễn Văn A" not in msg


def test_redact_job_pii_returns_counts_for_phones_emails_names():
    """redact_job_pii returns counts for phones, emails, names."""
    from app.services.pii.redact import redact_job_pii

    text = "Call 0901234567 or email hr@example.com. Contact Nguyễn Văn A."
    result = redact_job_pii(text)

    assert isinstance(result, RedactedText)
    assert result.phones_detected == 1
    assert result.emails_detected == 1
    assert result.names_detected == 1
    assert result.text == "Call <PHONE> or email <EMAIL> Contact <NAME>."


def test_redact_job_pii_returns_zero_counts_when_no_pii():
    """redact_job_pii returns zero counts when no PII is present."""
    from app.services.pii.redact import redact_job_pii

    text = "Apply at our office in Hà Nội."
    result = redact_job_pii(text)

    assert result.phones_detected == 0
    assert result.emails_detected == 0
    assert result.names_detected == 0
    assert result.text == text


def test_redact_listing_sets_pii_redacted_flag_when_pii_detected(sample_listing):
    """_redact_listing sets pii_redacted=True when PII is detected."""
    with patch("app.observability.metrics.record_vn_jobs_pii_detected"):
        result = _redact_listing(sample_listing)

    assert result.pii_redacted is True


def test_redact_listing_does_not_set_pii_redacted_flag_when_no_pii():
    """_redact_listing does not set pii_redacted when no PII is detected."""
    listing = VnJobAggregatedListing(
        id="vw:123",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="We are looking for a data engineer.",
        job_requirement="Python and SQL required.",
        confidence_score=0.7,
    )

    with patch("app.services.jobs_aggregator.orchestrator.record_vn_jobs_pii_detected"):
        result = _redact_listing(listing)

    assert result.pii_redacted is False
