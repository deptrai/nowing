"""PII redaction for Vietnamese job text."""

from __future__ import annotations

import pytest

from app.services.pii.redact import redact_job_pii

pytestmark = pytest.mark.unit


def test_redacts_vietnamese_phone():
    text = "Liên hệ 0987654321 hoặc +84 912 345 678."
    result = redact_job_pii(text)

    assert "0987654321" not in result.text
    assert "+84 912 345 678" not in result.text
    assert "<PHONE>" in result.text
    assert result.phones_detected == 2
    assert result.has_pii


def test_redacts_email():
    text = "Gửi CV về hr@example.com trước 31/08."
    result = redact_job_pii(text)

    assert "hr@example.com" not in result.text
    assert "<EMAIL>" in result.text
    assert result.emails_detected == 1
    assert result.has_pii


def test_redacts_person_name():
    text = "Liên hệ chị Nguyễn Thị Hạnh để biết thêm."
    result = redact_job_pii(text)

    assert "Nguyễn Thị Hạnh" not in result.text
    assert "<NAME>" in result.text
    assert result.names_detected == 1
    assert result.has_pii
