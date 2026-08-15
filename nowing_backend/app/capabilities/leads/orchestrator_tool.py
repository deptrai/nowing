"""Chat Agent Tool Bridge for Multi-Source Lead Generation Orchestrator (Story 21.15)."""

from __future__ import annotations

import logging
from typing import Any

from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
)

logger = logging.getLogger(__name__)


class MultiSourceLeadGenTool:
    """Structured Chat Agent Tool allowing AI to trigger multi-scraper lead discovery."""

    name = "multi_source_lead_gen"
    description = (
        "Tìm kiếm và quét khách hàng tiềm năng đa nguồn (Batdongsan, Chợ Tốt, TopCV, ITviec, "
        "Masothue, Mua Sắm Công, Mạng xã hội), tự động khử trùng lặp và làm giàu số điện thoại."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Mô tả đối tượng khách hàng hoặc doanh nghiệp cần tìm bằng tiếng Việt tự nhiên",
            },
            "table_id": {
                "type": "string",
                "description": "ID của Tab Bảng (Table Tab ID) để hiển thị danh sách leads",
            },
            "locations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Danh sách tỉnh/thành phố cần giới hạn phạm vi",
            },
        },
        "required": ["query"],
    }

    def __init__(self, orchestrator: LeadGenOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or LeadGenOrchestrator()

    async def execute(
        self,
        workspace_id: int,
        query: str,
        table_id: str | None = None,
        locations: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute orchestrator and return formatted Markdown summary for chat turn."""
        filters = {}
        if locations:
            filters["locations"] = locations

        result = await self.orchestrator.execute_multi_source_lead_gen(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            table_id=table_id,
        )

        total = result.total_deduplicated
        sources_used = sorted({s for lead in result.leads for s in lead.sources})
        source_str = ", ".join(sources_used) if sources_used else "đa nguồn"

        lines = [
            "### 🎯 Kết Quả Tìm Kiếm Khách Hàng Tiềm Năng (Lead Generation)",
            "",
            f"- **Trạng thái:** `{result.status.upper()}`",
            f"- **Đã tìm thấy:** `{total} leads` (Khử trùng từ {result.total_discovered} bản ghi thô từ nguồn {source_str})",
        ]

        if table_id:
            lines.append(
                f"- **Tab Bảng Dữ Liệu:** [Xem Bảng Dữ Liệu Live](#table_id={table_id})"
            )

        if result.degraded_sources:
            lines.append(
                f"- ⚠️ **Nguồn bị gián đoạn/bỏ qua:** {', '.join(result.degraded_sources)}"
            )

        lines.append("")
        lines.append(
            "| Tên / Tiêu đề | Doanh nghiệp / Người liên hệ | Số điện thoại | Độ tin cậy | Nguồn |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        for lead in result.leads[:10]:
            phone_disp = lead.primary_phone or "Chưa có SĐT"
            contact_disp = lead.company_name or lead.contact_name or "N/A"
            conf = f"{lead.confidence_score:.0f}%"
            src = "/".join(lead.sources)
            lines.append(
                f"| {lead.title or 'N/A'} | {contact_disp} | `{phone_disp}` | {conf} | {src} |"
            )

        if len(result.leads) > 10:
            lines.append(
                f"*(...và còn {len(result.leads) - 10} leads khác đã lưu vào bảng dữ liệu)*"
            )

        return "\n".join(lines)
