"""PII redaction for Vietnamese job text."""

from __future__ import annotations

import pytest

from app.services.pii.redact import redact_job_pii, redact_pii

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


def test_lead_enrichment_context_redacts_pii():
    text = "Reach Nguyễn Văn A at hr@example.com or 0987654321."
    result = redact_pii(text, context="lead_enrichment")

    assert "hr@example.com" not in result.text
    assert "0987654321" not in result.text
    assert "Nguyễn Văn A" not in result.text
    assert "<EMAIL>" in result.text
    assert "<PHONE>" in result.text
    assert "<NAME>" in result.text
    assert result.has_pii


def test_unknown_context_raises():
    with pytest.raises(ValueError):
        redact_pii("text", context="unknown")


def test_redacts_vietnamworks_sample():
    """A representative VietnamWorks JD has phone, email and name masked."""
    text = (
        "Liên hệ chị Nguyễn Thị Hạnh qua số 0901234567 hoặc email hr@example.com "
        "để gửi CV trước 31/08."
    )
    result = redact_job_pii(text)

    assert "0901234567" not in result.text
    assert "hr@example.com" not in result.text
    assert "Nguyễn Thị Hạnh" not in result.text
    assert "<PHONE>" in result.text
    assert "<EMAIL>" in result.text
    assert "<NAME>" in result.text
    assert result.phones_detected == 1
    assert result.emails_detected == 1
    assert result.names_detected == 1


def test_redacts_topcv_sample():
    """A representative TopCV JD keeps role details but masks contact PII."""
    text = (
        "Công ty TNHH ABC tuyển Python Developer tại Hà Nội. "
        "Gửi CV đến anh Trần Văn Minh qua zalo 0912345678 hoặc hr@abc-corp.vn."
    )
    result = redact_job_pii(text)

    assert "0912345678" not in result.text
    assert "hr@abc-corp.vn" not in result.text
    assert "Trần Văn Minh" not in result.text
    assert "<PHONE>" in result.text
    assert "<EMAIL>" in result.text
    assert "<NAME>" in result.text
    assert "Python Developer" in result.text
    assert "Hà Nội" in result.text


def test_redacts_itviec_sample():
    """A representative ITviec JD masks phone and email in a free-text JD body."""
    text = (
        "We are hiring a Senior Backend Engineer. "
        "Contact Ms. Lê Thị Hương at +84 901 234 567 or hr@itviec-demo.com."
    )
    result = redact_job_pii(text)

    assert "+84 901 234 567" not in result.text
    assert "hr@itviec-demo.com" not in result.text
    assert "Lê Thị Hương" not in result.text
    assert "<PHONE>" in result.text
    assert "<EMAIL>" in result.text
    assert "<NAME>" in result.text
    assert "Senior Backend Engineer" in result.text
