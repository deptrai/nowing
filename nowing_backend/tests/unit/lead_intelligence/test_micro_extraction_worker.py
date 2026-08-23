"""Unit tests for the micro-LLM fallback worker (Story 21.21)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.confidence.prompts import build_batch_prompt
from app.lead_intelligence.services.micro_extraction_worker import MicroExtractionWorker

pytestmark = pytest.mark.unit


def _lead(
    description: str = "",
    address: str | None = "Phường 1, Quận 7, TP.HCM",
    phone: str | None = None,
    price: float | None = None,
    area: float | None = None,
    title: str | None = None,
) -> NormalizedLead:
    return NormalizedLead(
        source_name="test",
        source_id=str(uuid4()),
        primary_phone=phone,
        price=price,
        address=address,
        area=area,
        title=title,
        raw_data={"description": description},
    )


class TestMicroExtractionPrompt:
    def test_build_prompt_caps_snippet_and_masks_phone(self) -> None:
        long_text = (
            "Bán nhà Quận 7 giá 5 tỷ liên hệ 0912 345 678 "
            "để xem nhà ngay hôm nay kẻo lỡ cơ hội tốt"
        )
        lead = _lead(description=long_text)
        prompt, _ = build_batch_prompt([lead])
        assert "[PHONE]" in prompt
        assert "0912" not in prompt
        assert len(prompt) <= 350  # prompt includes system prefix; snippet cap is 250

    def test_build_prompt_returns_empty_without_anchor(self) -> None:
        lead = _lead(description="Thông tin bất động sản tổng quát")
        prompt, indices = build_batch_prompt([lead])
        assert prompt == ""
        assert indices == []


class TestMicroExtractionParseAndValidate:
    def test_validate_phone_rejects_1800_1900(self) -> None:
        assert MicroExtractionWorker._validate_phone("1900123456") is None
        assert MicroExtractionWorker._validate_phone("1800123456") is None

    def test_validate_phone_accepts_word_number(self) -> None:
        # Word-number phone: "không chín một ..." should be parsed to digits.
        phone = MicroExtractionWorker._validate_phone(
            "không chín một hai ba bốn năm sáu bảy tám"
        )
        assert phone
        assert phone.startswith("0")
        assert len(phone) == 10

    def test_validate_price_converts_ti(self) -> None:
        assert MicroExtractionWorker._validate_price("5 tỷ") == 5_000_000_000
        assert MicroExtractionWorker._validate_price("3,5 triệu") == 3_500_000

    def test_validate_area_converts_m2_string(self) -> None:
        assert MicroExtractionWorker._validate_area("75 m²") == 75.0

    def test_validate_district_strips_prefix(self) -> None:
        assert MicroExtractionWorker._validate_district("Quận 7") == "7"
        assert MicroExtractionWorker._validate_district("Quận 7, TP.HCM") == "7"

    def test_parse_and_validate_only_fills_missing(self) -> None:
        raw = {
            "phone": "0912345678",
            "price": 5_000_000_000,
            "district": "Quận 7",
            "area": 75,
        }
        merged = MicroExtractionWorker.parse_and_validate(raw, {"phone", "price"})
        assert "phone" in merged
        assert "price" in merged
        assert "district" not in merged
        assert "area" not in merged


class TestMicroExtractionWorker:
    @pytest.mark.asyncio
    async def test_micro_batch_enriches_missing_fields(self) -> None:
        lead = _lead(
            description="Bán nhà Quận 7 giá 5 tỷ lh 0912345678, diện tích 75m2",
            address="TP.HCM",
            phone=None,
            price=None,
            area=None,
        )

        mock_response = MagicMock(
            content={
                "0": {
                    "phone": "0912345678",
                    "price": 5_000_000_000,
                    "district": "Quận 7",
                    "area": 75,
                    "title": "Bán nhà Quận 7",
                }
            }
        )
        mock_router = MagicMock(ainvoke=AsyncMock(return_value=mock_response))

        worker = MicroExtractionWorker(router=mock_router, batch_size=2)
        result = await worker.micro_batch([lead], workspace_id=1)

        assert len(result) == 1
        assert result[0].primary_phone == "0912345678"
        assert result[0].price == 5_000_000_000
        assert result[0].area == 75.0
        assert result[0].schema_completeness_score == 1.0
        assert result[0].needs_enrichment is False

    @pytest.mark.asyncio
    async def test_micro_batch_degrades_on_timeout(self) -> None:
        lead = _lead(
            description="Bán nhà Quận 7 giá 5 tỷ lh 0912345678",
            phone=None,
            price=None,
        )

        async def _raise_timeout(*args: Any, **kwargs: Any) -> Any:
            raise TimeoutError("simulated timeout")

        mock_router = MagicMock(ainvoke=AsyncMock(side_effect=_raise_timeout))
        worker = MicroExtractionWorker(router=mock_router, batch_size=2)

        result = await worker.micro_batch([lead], workspace_id=1)

        assert result[0].needs_enrichment is True
        assert result[0].primary_phone is None

    @pytest.mark.asyncio
    async def test_micro_batch_respects_no_snippet(self) -> None:
        lead = _lead(description="Thông tin chung", phone=None)
        mock_router = MagicMock(ainvoke=AsyncMock())
        worker = MicroExtractionWorker(router=mock_router, batch_size=2)

        result = await worker.micro_batch([lead], workspace_id=1)

        # No anchor found, so no LLM call should be made.
        assert not mock_router.ainvoke.called
        assert result[0].needs_enrichment is True
