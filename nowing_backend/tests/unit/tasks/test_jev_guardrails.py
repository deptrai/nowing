"""Unit tests for Jev Guardrails (Story 40.4)."""

import pytest
from app.tasks.jev_guardrails import sanitize_pii_content, evaluate_entity_dedup


def test_sanitize_pii_content_redacts_cccd():
    text = "Khách hàng Nguyễn Văn A, CCCD: 012345678901, SĐT: 0912345678"
    sanitized = sanitize_pii_content(text)
    assert "[REDACTED_ID]" in sanitized
    assert "012345678901" not in sanitized
    assert "0912345678" in sanitized  # Phone numbers are kept intact for lead gen


def test_sanitize_pii_content_redacts_cmnd():
    text = "Số CMND: 123456789 đăng ký hôm nay"
    sanitized = sanitize_pii_content(text)
    assert "[REDACTED_ID]" in sanitized
    assert "123456789" not in sanitized


@pytest.mark.asyncio
async def test_evaluate_entity_dedup_exact_match():
    candidate = {"company_name": "Công ty TNHH ABC"}
    existing = [{"id": 1, "company_name": "Công ty TNHH ABC"}]
    res = await evaluate_entity_dedup(candidate, existing)
    assert res["action"] == "merge"
    assert res["score"] >= 1.5


@pytest.mark.asyncio
async def test_evaluate_entity_dedup_fuzzy_curate():
    candidate = {"company_name": "TNHH ABC"}
    existing = [{"id": 1, "company_name": "Công ty TNHH ABC"}]
    res = await evaluate_entity_dedup(candidate, existing)
    assert res["action"] == "curate"
    assert 0.5 <= res["score"] < 1.5


@pytest.mark.asyncio
async def test_evaluate_entity_dedup_new_entity():
    candidate = {"company_name": "Công ty XYZ"}
    existing = [{"id": 1, "company_name": "Công ty TNHH ABC"}]
    res = await evaluate_entity_dedup(candidate, existing)
    assert res["action"] == "create"
    assert res["score"] < 0.5
