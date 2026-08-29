"""Main-agent lead generation tool factory."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from langchain_core.tools import tool

from app.db import async_session_maker

logger = logging.getLogger(__name__)


def create_multi_source_lead_gen_tool(
    workspace_id: int,
    db_session: Any | None = None,
):
    """Factory for the ``multi_source_lead_gen`` chat tool.

    Uses a fresh short-lived session per call so compiled-agent caches never
    retain a stale request-scoped session.
    """
    del db_session

    @tool
    async def multi_source_lead_gen(
        query: str,
        table_id: str | None = None,
        locations: list[str] | None = None,
        campaign_id: str | None = None,
        smoke_test: bool = False,
        target_sources: list[str] | None = None,
        target_keywords: list[str] | None = None,
        negative_keywords: list[str] | None = None,
        min_fit_score: float = 0.0,
        enrichment_depth: str = "standard",
        intent: str = "buy",
        product_type: str | None = None,
        price_segment: str | None = None,
        preferred_channels: list[str] | None = None,
        limit: int = 50,
    ) -> str:
        """Tìm kiếm khách hàng tiềm năng đa nguồn và lưu vào bảng dữ liệu.

        Đây là công cụ chính của Sales Copilot để tìm lead đa nguồn
        (Batdongsan, Chợ Tốt, Mua Bán, TopCV, ITviec, VietnamWorks, Masothue,
        Mua Sắm Công, Mạng xã hội, Web crawl, ChainLens Research) theo mô tả
        tự nhiên tiếng Việt hoặc tiếng Anh. Hỗ trợ smoke test trước khi chạy đầy đủ.

        Args:
            query: Mô tả đối tượng khách hàng hoặc doanh nghiệp cần tìm.
            table_id: ID tab bảng dữ liệu để hiển thị kết quả.
            locations: Danh sách tỉnh/thành phố giới hạn phạm vi.
            campaign_id: ID chiến dịch để theo dõi / tiếp tục.
            smoke_test: True để chạy thử nghiệm nhỏ (5-10 leads) trước khi tốn credits.
            target_sources: Danh sách nguồn cụ thể, ví dụ ["batdongsan", "topcv", "masothue"].
            target_keywords: Từ khóa cộng hưởng điểm fit.
            negative_keywords: Từ khóa loại trừ.
            min_fit_score: Điểm ICP tối thiểu (0-100).
            enrichment_depth: "light", "standard", hoặc "deep".
            intent: "buy" | "sell" | "hire" | "partner" | "invest" | "rent" | "research".
            product_type: Loại sản phẩm/dịch vụ, ví dụ "SaaS HR", "BĐS".
            price_segment: Phân khúc giá, ví dụ "premium", "mid-market", "SMB".
            preferred_channels: Kênh outreach mong muốn, ví dụ ["zalo", "email"].
            limit: Số leads tối đa (1-200, mặc định 50).
        """
        from app.capabilities.leads.orchestrator_tool import MultiSourceLeadGenTool

        session = None
        try:
            async with async_session_maker() as session_:
                session = session_
                lead_tool = MultiSourceLeadGenTool(db_session=session)
                result = await lead_tool.execute(
                    workspace_id=workspace_id,
                    query=query,
                    table_id=table_id,
                    locations=locations or [],
                    campaign_id=campaign_id,
                    smoke_test=smoke_test,
                    target_sources=target_sources or [],
                    target_keywords=target_keywords or [],
                    negative_keywords=negative_keywords or [],
                    min_fit_score=min_fit_score,
                    enrichment_depth=enrichment_depth,
                    intent=intent,
                    product_type=product_type,
                    price_segment=price_segment,
                    preferred_channels=preferred_channels or [],
                    limit=limit,
                )
                await session.commit()
                return result
        except Exception as exc:
            if session is not None:
                with contextlib.suppress(Exception):
                    await session.rollback()
            logger.exception("multi_source_lead_gen failed: %s", exc)
            return f"Lỗi khi tìm kiếm leads: {exc}"

    return multi_source_lead_gen
