"""Deterministic fake scraper adapters for lead-generation E2E smoke tests.

Patches the BĐS and non-BĐS adapter ``search_leads`` methods so local E2E does
not require real scraper platform accounts.  Returns synthetic listings that
exercise intent routing, price/location post-filter, and contact extraction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.lead_intelligence.adapters.base import RawLeadRecord

BROKER_PROMPT_NEEDLES = (
    "môi giới bất động sản",
    "bán nhà",
    "nhà bán",
    "bất động sản",
    "nhà phố",
    "cần bán",
    "ký gửi",
    "tìm khách mua",
    "có đất bán",
    "có nhà bán",
)


def _is_broker_prompt(query: str) -> bool:
    return any(needle in query.lower() for needle in BROKER_PROMPT_NEEDLES)


SELLER_PROMPT_NEEDLES = (
    "tôi cần bán",
    "toi can ban",
    "ký gửi",
    "ky gui",
    "tìm khách mua",
    "tim khach mua",
    "cần bán gấp",
    "can ban gap",
)


def _is_seller_prompt(query: str) -> bool:
    return any(needle in query.lower() for needle in SELLER_PROMPT_NEEDLES)


def _make_bds_records(source_name: str) -> list[RawLeadRecord]:
    """Return 5 synthetic BĐS listings for Quận 7 / TP.HCM.

    One record is above the 8 tỷ max and one is in Hà Nội so the post-filter
    can be exercised.  Four OK records use source-specific distinct phones so
    they survive phone-based deduplication and produce >= 10 visible leads.
    """
    base_phones = {
        "batdongsan": ["0901111001", "0901111004", "0901111005", "0901111006"],
        "chotot": ["0901111002", "0901111007", "0901111008", "0901111009"],
        "muaban_bds": ["0901111003", "0901111010", "0901111011", "0901111012"],
    }
    ok_phones = base_phones.get(source_name, ["0901111009"] * 4)
    records: list[RawLeadRecord] = []
    for idx, phone in enumerate(ok_phones, start=1):
        data = {
            "title": f"Bán nhà phố Quận 7 - {source_name} #{idx}",
            "description": (
                f"Liên hệ chính chủ {phone} hoặc email owner@example.com. "
                f"Zalo: {phone}, facebook.com/seller.page"
            ),
            "city": "Hồ Chí Minh",
            "address": "Quận 7, TP.HCM",
            "phone": phone,
            "price_value": 7_000_000_000,
        }
        records.append(
            RawLeadRecord(
                source_name=source_name,
                source_id=f"{source_name}_q7_ok_{idx}",
                data={**data, "listing_id": f"{source_name}_q7_ok_{idx}"},
                fetched_at=datetime.now(UTC),
            )
        )
    above = {
        "title": "Bán biệt thự Quận 7",
        "description": "Liên hệ 0909876543",
        "phone": "0909876543",
        "city": "Hồ Chí Minh",
        "address": "Quận 7, TP.HCM",
        "price_value": 9_500_000_000,
    }
    other_city = {
        "title": "Bán nhà phố Cầu Giấy",
        "description": "Liên hệ 0903334444",
        "phone": "0903334444",
        "city": "Hà Nội",
        "address": "Cầu Giấy, Hà Nội",
        "price_value": 6_000_000_000,
    }
    records.extend(
        [
            RawLeadRecord(
                source_name=source_name,
                source_id=f"{source_name}_q7_expensive",
                data={**above, "listing_id": f"{source_name}_q7_expensive"},
                fetched_at=datetime.now(UTC),
            ),
            RawLeadRecord(
                source_name=source_name,
                source_id=f"{source_name}_hn",
                data={**other_city, "listing_id": f"{source_name}_hn"},
                fetched_at=datetime.now(UTC),
            ),
        ]
    )
    return records


def _make_social_buyer_demand_records(source_name: str) -> list[RawLeadRecord]:
    """Return synthetic buyer-demand posts for seller-intent E2E tests."""
    records: list[RawLeadRecord] = []
    for idx in range(1, 6):
        phone = f"0905555{idx:03d}"
        post_text = (
            f"Tìm mua nhà Quận 7, TP.HCM dưới 8 tỷ. Liên hệ {phone}. (buyer {idx})"
        )
        title = f"Cần mua nhà phố Quận 7 - buyer {idx}"
        records.append(
            RawLeadRecord(
                source_name=source_name,
                source_id=f"{source_name}_buyer_{idx}",
                data={
                    "title": title,
                    "description": post_text,
                    "post_text": post_text,
                    "text": post_text,
                    "content": post_text,
                    "phone": phone,
                    "city": "Hồ Chí Minh",
                    "address": "Quận 7, TP.HCM",
                    "price_value": 7_500_000_000,
                },
                fetched_at=datetime.now(UTC),
            )
        )
    return records


def _make_telegram_buyer_demand_records(source_name: str) -> list[RawLeadRecord]:
    """Return synthetic Telegram buyer-demand posts for seller-intent E2E."""
    records: list[RawLeadRecord] = []
    for idx in range(1, 6):
        phone = f"0907777{idx:03d}"
        # Keep the message short so the phone survives downstream 100-char title truncation.
        message_text = f"{phone} mua nhà Quận 7 dưới 8 tỷ (buyer {idx})"
        records.append(
            RawLeadRecord(
                source_name=source_name,
                source_id=f"{source_name}_buyer_{idx}",
                data={
                    "message_text": message_text,
                    "message_id": f"{source_name}_buyer_{idx}",
                    "channel_username": "q7_buyers",
                    "city": "Hồ Chí Minh",
                    "address": "Quận 7, TP.HCM",
                    "posted_at": datetime.now(UTC).isoformat(),
                },
                fetched_at=datetime.now(UTC),
            )
        )
    return records


def _make_non_bds_records(source_name: str) -> list[RawLeadRecord]:
    """Return fake job/enterprise listings to prove they are not selected."""
    return [
        RawLeadRecord(
            source_name=source_name,
            source_id=f"{source_name}_fake",
            data={
                "title": "Tuyển dụng Python Developer",
                "company_name": "Fake Corp",
                "phone": "0900000001",
                "city": "Hà Nội",
            },
            fetched_at=datetime.now(UTC),
        )
    ]


async def _patched_search_leads(
    self: Any,
    workspace_id: int,
    query: str,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
) -> list[RawLeadRecord]:
    """Drop-in replacement for all concrete adapter search_leads methods."""
    if self.source_name in {"social", "telegram"} and _is_seller_prompt(query):
        if self.source_name == "telegram":
            return _make_telegram_buyer_demand_records(self.source_name)
        return _make_social_buyer_demand_records(self.source_name)
    if _is_broker_prompt(query):
        return _make_bds_records(self.source_name)
    return _make_non_bds_records(self.source_name)


def install_lead_scraper_fakes() -> None:
    """Patch adapter instances registered in LeadSourceAdapterRegistry."""
    from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
    from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
    from app.lead_intelligence.adapters.enterprise import (
        EnterpriseProcurementLeadAdapter,
    )
    from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
    from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
    from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
    from app.lead_intelligence.adapters.social import SocialLeadAdapter
    from app.lead_intelligence.adapters.telegram import TelegramLeadAdapter

    # Patch class methods so every adapter instance uses the fake.
    BatdongsanLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]
    ChototLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]
    MuabanBdsLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]
    JobMarketLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]
    EnterpriseProcurementLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]
    SocialLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]
    TelegramLeadAdapter.search_leads = _patched_search_leads  # type: ignore[assignment]

    # Ensure the default registry is populated with patched classes.
    LeadSourceAdapterRegistry.get_default()
