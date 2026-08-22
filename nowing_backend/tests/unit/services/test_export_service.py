"""Unit tests for Export Service & Cloud Connectors (Story 21.13)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.export_service import (
    ExportService,
    mask_email,
    mask_phone,
)

pytestmark = pytest.mark.unit


def _create_sample_leads():
    return [
        SimpleNamespace(
            id=uuid4(),
            company_name="Công Ty Cổ Phần Công Nghệ VNG",
            domain="vng.com.vn",
            source="facebook",
            industry="Software & Gaming",
            company_size="2000-5000",
            location="TP. Hồ Chí Minh",
            fit_score=95.0,
            intent_score=90.0,
            composite_score=95.0,
            status="qualified",
            created_at=datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC),
            verified_contacts=[
                SimpleNamespace(
                    name="Lê Hồng Minh",
                    title="Founder & CEO",
                    email="minh.le@vng.com.vn",
                    phone="0908123456",
                    confidence=0.95,
                )
            ],
        ),
        SimpleNamespace(
            id=uuid4(),
            company_name="Tập Đoàn FPT",
            domain="fpt.com.vn",
            source="topcv",
            industry="IT Services",
            company_size="10000+",
            location="Hà Nội",
            fit_score=88.0,
            intent_score=82.0,
            composite_score=88.0,
            status="new",
            created_at=datetime(2026, 8, 15, 12, 30, 0, tzinfo=UTC),
            verified_contacts=[
                SimpleNamespace(
                    name="Trương Gia Bình",
                    title="Chủ tịch HĐQT",
                    email="binhtg@fpt.com.vn",
                    phone="0912345678",
                    confidence=0.99,
                )
            ],
        ),
    ]


def test_mask_phone_utility():
    assert mask_phone("0908123456") == "0908***456"
    assert mask_phone("0912.345.678") == "0912***678"
    assert mask_phone("+84908123456") == "0908***456"
    assert mask_phone("") == ""
    assert mask_phone(None) == ""


def test_mask_email_utility():
    assert mask_email("minh.le@vng.com.vn") == "m***@vng.com.vn"
    assert mask_email("a@b.com") == "a***@b.com"
    assert mask_email("") == ""
    assert mask_email(None) == ""


def test_generate_csv_with_pii_masked():
    leads = _create_sample_leads()
    service = ExportService()
    csv_content = service.generate_csv(leads, mask_pii=True)

    assert (
        "Company Name,Domain,Source,Industry,Location,Fit Score,Status,Contact Name,Contact Title,Email,Phone"
        in csv_content
    )
    assert "Công Ty Cổ Phần Công Nghệ VNG" in csv_content
    # Phone should be masked
    assert "0908***456" in csv_content
    assert "0908123456" not in csv_content
    assert "m***@vng.com.vn" in csv_content


def test_generate_csv_unmasked():
    leads = _create_sample_leads()
    service = ExportService()
    csv_content = service.generate_csv(leads, mask_pii=False)

    assert "0908123456" in csv_content
    assert "minh.le@vng.com.vn" in csv_content


def test_prepare_lark_records():
    leads = _create_sample_leads()
    service = ExportService()
    records = service.prepare_lark_records(leads, mask_pii=False)

    assert len(records) == 2
    first_record = records[0]["fields"]
    assert first_record["Company Name"] == "Công Ty Cổ Phần Công Nghệ VNG"
    assert first_record["Fit Score"] == 95.0
    assert first_record["Contact Name"] == "Lê Hồng Minh"
    assert first_record["Phone"] == "0908123456"


def test_prepare_google_sheets_rows():
    leads = _create_sample_leads()
    service = ExportService()
    rows = service.prepare_google_sheets_rows(leads, mask_pii=False)

    assert len(rows) == 3  # Header + 2 data rows
    assert rows[0][0] == "Company Name"
    assert rows[1][0] == "Công Ty Cổ Phần Công Nghệ VNG"
    assert rows[1][5] == 95.0
    assert rows[2][0] == "Tập Đoàn FPT"
