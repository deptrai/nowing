"""Main-agent lead generation tool factory."""

from __future__ import annotations

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
    ) -> str:
        """Tìm kiếm khách hàng tiềm năng đa nguồn và lưu vào bảng dữ liệu.

        Dùng khi user muốn tìm lead từ nhiều nguồn (Batdongsan, Chợ Tốt,
        TopCV, ITviec, Masothue) bằng mô tả tự nhiên tiếng Việt.

        Args:
            query: Mô tả đối tượng khách hàng hoặc doanh nghiệp cần tìm.
            table_id: ID tab bảng dữ liệu để hiển thị kết quả.
            locations: Danh sách tỉnh/thành phố giới hạn phạm vi.
        """
        from app.capabilities.leads.orchestrator_tool import MultiSourceLeadGenTool

        try:
            async with async_session_maker() as session:
                lead_tool = MultiSourceLeadGenTool(db_session=session)
                return await lead_tool.execute(
                    workspace_id=workspace_id,
                    query=query,
                    table_id=table_id,
                    locations=locations or [],
                )
        except Exception as exc:
            logger.exception("multi_source_lead_gen failed: %s", exc)
            return f"Lỗi khi tìm kiếm leads: {exc}"

    return multi_source_lead_gen
