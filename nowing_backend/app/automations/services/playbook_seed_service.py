"""System seed service for high-value vertical Playbook templates (Story 24.5)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.playbook_scope import PlaybookScope
from app.automations.persistence.models.playbook import Playbook

logger = logging.getLogger(__name__)


def _bds_inputs_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["province", "max_price_ty_vnd"],
        "properties": {
            "province": {
                "type": "string",
                "title": "Tỉnh / Thành phố",
                "enum": [
                    "Hà Nội",
                    "TP. Hồ Chí Minh",
                    "Đà Nẵng",
                    "Bình Dương",
                    "Đồng Nai",
                    "Khánh Hòa",
                ],
                "default": "Hà Nội",
            },
            "property_type": {
                "type": "string",
                "title": "Loại hình BĐS",
                "enum": ["Nhà riêng", "Đất nền", "Biệt thự / Liền kề", "Căn hộ chung cư"],
                "default": "Nhà riêng",
            },
            "max_price_ty_vnd": {
                "type": "number",
                "title": "Mức giá trần (Tỷ VNĐ)",
                "default": 10.0,
                "minimum": 0.5,
                "maximum": 500.0,
            },
            "max_leads": {
                "type": "integer",
                "title": "Giới hạn số lượng Lead (Tối đa 200)",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
            },
            "zalo_message_template": {
                "type": "string",
                "title": "Mẫu tin nhắn mở đầu Zalo",
                "default": "Dạ chào anh/chị, em thấy tin đăng BĐS tại {{province}} của mình. Em có khách đang tìm mua đúng phân khúc này, em xin phép liên hệ hỗ trợ ạ!",
            },
        },
    }


def _recruitment_inputs_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tech_stack", "location"],
        "properties": {
            "tech_stack": {
                "type": "array",
                "title": "Kỹ năng / Tech Stack",
                "items": {"type": "string"},
                "default": ["React", "NodeJS", "TypeScript"],
            },
            "min_experience_years": {
                "type": "number",
                "title": "Số năm kinh nghiệm tối thiểu",
                "default": 3,
                "minimum": 1,
                "maximum": 20,
            },
            "location": {
                "type": "string",
                "title": "Địa điểm làm việc",
                "enum": ["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Remote / Toàn quốc"],
                "default": "Hà Nội",
            },
            "max_leads": {
                "type": "integer",
                "title": "Số lượng hồ sơ quét (Tối đa 200)",
                "default": 30,
                "minimum": 1,
                "maximum": 200,
            },
        },
    }


def _b2b_inputs_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["province", "industry"],
        "properties": {
            "province": {
                "type": "string",
                "title": "Tỉnh / Thành phố",
                "enum": [
                    "Hà Nội",
                    "TP. Hồ Chí Minh",
                    "Đà Nẵng",
                    "Hải Phòng",
                    "Bình Dương",
                ],
                "default": "Hà Nội",
            },
            "industry": {
                "type": "string",
                "title": "Ngành nghề kinh doanh",
                "enum": [
                    "Công nghệ thông tin",
                    "Thương mại điện tử & Bán lẻ",
                    "Xây dựng & Nội thất",
                    "Dịch vụ & Du lịch",
                    "Tài chính & Bảo hiểm",
                ],
                "default": "Công nghệ thông tin",
            },
            "min_charter_capital_million_vnd": {
                "type": "number",
                "title": "Vốn điều lệ tối thiểu (Triệu VNĐ)",
                "default": 1000,
                "minimum": 100,
            },
            "max_leads": {
                "type": "integer",
                "title": "Số lượng doanh nghiệp quét (Tối đa 200)",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
            },
        },
    }


def _ecommerce_inputs_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["product_keywords", "platform"],
        "properties": {
            "product_keywords": {
                "type": "string",
                "title": "Từ khóa sản phẩm / Ngành hàng",
                "default": "iPhone 16 Pro Max 256GB",
            },
            "platform": {
                "type": "string",
                "title": "Sàn thương mại điện tử",
                "enum": ["Shopee", "Lazada", "TikTok Shop", "Tiki"],
                "default": "Shopee",
            },
            "discount_threshold_percent": {
                "type": "number",
                "title": "Ngưỡng giảm giá kích hoạt cảnh báo (%)",
                "default": 15,
                "minimum": 5,
                "maximum": 90,
            },
            "telegram_channel_or_group": {
                "type": "string",
                "title": "Kênh / Nhóm nhận cảnh báo Telegram",
                "default": "@nowing_price_alerts",
            },
            "max_skus": {
                "type": "integer",
                "title": "Số lượng SKU theo dõi (Tối đa 200)",
                "default": 20,
                "minimum": 1,
                "maximum": 200,
            },
        },
    }


def _definition(
    name: str,
    metadata: dict[str, Any],
    plan: list[dict[str, Any]],
    inputs_schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "schema_version": "1.1",
        "metadata": metadata,
        "plan": plan,
        "inputs": {"schema": inputs_schema},
    }


def _playbook(
    name: str,
    description: str,
    verticals: list[str],
    inputs_schema: dict[str, Any],
    plan: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "verticals": verticals,
        "tool_scope": ["agent_task"],
        "scope": PlaybookScope.SYSTEM,
        "is_approved": True,
        "version": 1,
        "inputs_schema": inputs_schema,
        "definition": _definition(name, metadata, plan, inputs_schema),
    }


_BDS_METADATA = {
    "author_badge": "official",
    "author_name": "Nowing RealEstate Lab",
    "estimated_credits_cost": 35,
    "run_count": 1420,
    "is_featured": True,
    "tags": ["bds", "batdongsan", "zalo", "chinh-chu"],
}

_BDS_PLAN = [
    {
        "step_id": "scrape_bds",
        "action": "agent_task",
        "params": {
            "query": "Tìm tin đăng bất động sản {{property_type}} tại {{province}} giá dưới {{max_price_ty_vnd}} tỷ, tối đa {{max_leads}} tin.",
        },
    },
    {
        "step_id": "extract_phone",
        "action": "agent_task",
        "params": {
            "query": "Trích xuất số điện thoại và thông tin liên hệ từ {{max_leads}} tin đăng BĐS vừa tìm được.",
        },
    },
    {
        "step_id": "draft_zalo",
        "action": "agent_task",
        "params": {
            "query": "Soạn tin nhắn Zalo mở đầu theo mẫu: {{zalo_message_template}} để gửi đến các chủ tin đăng.",
        },
    },
]


_RECRUITMENT_METADATA = {
    "author_badge": "official",
    "author_name": "Nowing HR Intelligence",
    "estimated_credits_cost": 25,
    "run_count": 980,
    "is_featured": True,
    "tags": ["recruitment", "headhunter", "it", "jd-match"],
}

_RECRUITMENT_PLAN = [
    {
        "step_id": "scrape_talent",
        "action": "agent_task",
        "params": {
            "query": "Tìm ứng viên IT có tech stack {{tech_stack}} tại {{location}}, tối đa {{max_leads}} hồ sơ.",
        },
    },
    {
        "step_id": "analyze_tech_stack",
        "action": "agent_task",
        "params": {
            "query": "Phân tích tech stack và kinh nghiệm {{min_experience_years}} năm của {{max_leads}} ứng viên.",
        },
    },
    {
        "step_id": "rank_fit_score",
        "action": "agent_task",
        "params": {
            "query": "Xếp hạng độ phù hợp JD của {{max_leads}} ứng viên IT.",
        },
    },
]


_B2B_METADATA = {
    "author_badge": "official",
    "author_name": "Nowing B2B Engine",
    "estimated_credits_cost": 40,
    "run_count": 2150,
    "is_featured": True,
    "tags": ["b2b", "masothue", "outreach", "mst-verify"],
}

_B2B_PLAN = [
    {
        "step_id": "scrape_new_biz",
        "action": "agent_task",
        "params": {
            "query": "Tìm doanh nghiệp mới tại {{province}}, ngành {{industry}}, vốn điều lệ từ {{min_charter_capital_million_vnd}} triệu, tối đa {{max_leads}} doanh nghiệp.",
        },
    },
    {
        "step_id": "enrich_mst_director",
        "action": "agent_task",
        "params": {
            "query": "Tra cứu MST và SĐT người đại diện cho {{max_leads}} doanh nghiệp mới.",
        },
    },
    {
        "step_id": "push_to_crm",
        "action": "agent_task",
        "params": {
            "query": "Đẩy {{max_leads}} doanh nghiệp đã xác thực vào CRM.",
        },
    },
]


_ECOMMERCE_METADATA = {
    "author_badge": "official",
    "author_name": "Nowing E-Commerce Radar",
    "estimated_credits_cost": 15,
    "run_count": 760,
    "is_featured": True,
    "tags": ["ecommerce", "shopee", "lazada", "telegram", "price-tracking"],
}

_ECOMMERCE_PLAN = [
    {
        "step_id": "crawl_skus",
        "action": "agent_task",
        "params": {
            "query": "Crawl SKU {{product_keywords}} trên {{platform}}, tối đa {{max_skus}} sản phẩm.",
        },
    },
    {
        "step_id": "calc_price_diff",
        "action": "agent_task",
        "params": {
            "query": "Tính toán biến động giá và % giảm so với ngưỡng {{discount_threshold_percent}}% cho {{max_skus}} SKU.",
        },
    },
    {
        "step_id": "send_telegram_alert",
        "action": "agent_task",
        "params": {
            "query": "Gửi cảnh báo giá tới kênh Telegram {{telegram_channel_or_group}} khi phát hiện SKU giảm giá.",
        },
    },
]


OFFICIAL_PLAYBOOKS: list[dict[str, Any]] = [
    _playbook(
        name="BĐS Ngộp & Môi Giới Pro",
        description="Săn BĐS chính chủ/ngộp giá ➔ Lọc SĐT & kiểm tra quy hoạch ➔ Soạn tin nhắn Zalo gửi báo giá.",
        verticals=["realestate"],
        inputs_schema=_bds_inputs_schema(),
        plan=_BDS_PLAN,
        metadata=_BDS_METADATA,
    ),
    _playbook(
        name="IT Headhunter Săn Senior",
        description="Quét TopCV/ITviec ➔ Bóc tách Tech Stack ➔ So khớp JD ứng viên chuyên sâu.",
        verticals=["recruitment"],
        inputs_schema=_recruitment_inputs_schema(),
        plan=_RECRUITMENT_PLAN,
        metadata=_RECRUITMENT_METADATA,
    ),
    _playbook(
        name="B2B Sales Doanh Nghiệp Mới",
        description="Quét doanh nghiệp mới thành lập ➔ Tra cứu MST & SĐT người đại diện ➔ Tự động gửi kịch bản giới thiệu.",
        verticals=["b2b"],
        inputs_schema=_b2b_inputs_schema(),
        plan=_B2B_PLAN,
        metadata=_B2B_METADATA,
    ),
    _playbook(
        name="E-Commerce Flash Price Tracking",
        description="Theo dõi biến động giá Shopee/Lazada ➔ Bắn cảnh báo tức thì qua Telegram.",
        verticals=["ecommerce"],
        inputs_schema=_ecommerce_inputs_schema(),
        plan=_ECOMMERCE_PLAN,
        metadata=_ECOMMERCE_METADATA,
    ),
]


async def seed_system_playbooks(session: AsyncSession) -> int:
    """Idempotently seed official vertical playbooks into the database.

    Existing official playbooks are upserted by (name, scope) where
    ``workspace_id IS NULL``. Playbooks removed from the official list
    are hidden from the marketplace by setting ``is_approved = False``.
    """
    seeded_count = 0
    for pb_data in OFFICIAL_PLAYBOOKS:
        stmt = (
            pg_insert(Playbook)
            .values(
                workspace_id=None,
                created_by_user_id=None,
                name=pb_data["name"],
                description=pb_data["description"],
                verticals=pb_data["verticals"],
                tool_scope=pb_data["tool_scope"],
                scope=pb_data["scope"],
                inputs_schema=pb_data["inputs_schema"],
                definition=pb_data["definition"],
                version=pb_data["version"],
                is_approved=pb_data["is_approved"],
            )
            .on_conflict_do_update(
                index_elements=["name", "scope"],
                index_where=text("workspace_id IS NULL"),
                set_={
                    "description": pb_data["description"],
                    "verticals": pb_data["verticals"],
                    "tool_scope": pb_data["tool_scope"],
                    "inputs_schema": pb_data["inputs_schema"],
                    "definition": pb_data["definition"],
                    "version": pb_data["version"],
                    "is_approved": pb_data["is_approved"],
                    "created_by_user_id": None,
                },
            )
        )
        await session.execute(stmt)
        seeded_count += 1

    # Hide stale official playbooks instead of deleting them.
    official_names = {pb["name"] for pb in OFFICIAL_PLAYBOOKS}
    hide_stmt = (
        update(Playbook)
        .where(
            Playbook.scope == PlaybookScope.SYSTEM,
            Playbook.workspace_id.is_(None),
            Playbook.name.notin_(official_names),
        )
        .values(is_approved=False)
    )
    await session.execute(hide_stmt)

    await session.commit()
    logger.info("Successfully seeded %d system playbooks", seeded_count)
    return seeded_count
