"""Chat Agent Tool Bridge for Multi-Source Lead Generation Orchestrator (Story 21.15)."""

from __future__ import annotations

import html
import logging
from typing import Any

from app.lead_intelligence.adapters.base import LeadIntent
from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator

logger = logging.getLogger(__name__)


def _sanitize_markdown_cell(text: str | None, max_length: int = 80) -> str:
    """Sanitize cell text against markdown table breaking, HTML injection, and line breaks."""
    if not text:
        return "N/A"
    # Escape HTML
    escaped = html.escape(str(text).strip())
    # Replace markdown table pipes and newlines
    safe = escaped.replace("|", "\\|").replace("\n", " ").replace("\r", "")
    return (safe[:max_length] + "...") if len(safe) > max_length else safe


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

    def __init__(
        self,
        orchestrator: LeadGenOrchestrator | None = None,
        db_session: Any | None = None,
    ) -> None:
        self.orchestrator = orchestrator or LeadGenOrchestrator()
        self.db_session = db_session

    async def execute(
        self,
        workspace_id: int,
        query: str,
        table_id: str | None = None,
        locations: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute orchestrator and return formatted Markdown summary for chat turn."""
        filters: dict[str, Any] = {}
        if locations:
            filters["locations"] = locations

        if self.db_session is not None:
            result = await self.orchestrator.execute_and_persist(
                session=self.db_session,
                workspace_id=workspace_id,
                query=query,
                table_id=table_id,
                filters=filters,
            )
        else:
            result = await self.orchestrator.execute_multi_source_lead_gen(
                workspace_id=workspace_id,
                query=query,
                filters=filters,
                table_id=table_id,
            )

        total = result.total_deduplicated
        sources_used = sorted({s for lead in result.leads for s in lead.sources})
        source_str = ", ".join(sources_used) if sources_used else "đa nguồn"
        is_real_estate = any(
            s in {"batdongsan", "chotot", "muaban_bds"} for s in sources_used
        )
        is_social = any(s == "social" for s in sources_used)
        is_sell = result.intent == LeadIntent.SELL

        if total == 0 and not result.leads:
            return "Không tìm thấy leads phù hợp. Bạn có thể thử mở rộng địa điểm, giá, hoặc thêm từ khóa BĐS/công ty cụ thể hơn."

        status_text = (
            "Một số nguồn bị gián đoạn"
            if result.degraded_sources
            else "Hoàn tất"
        )

        if is_sell and is_social:
            header = "### Nguồn Cầu / Người Mua Tiềm Năng"
            count_label = f"{total} nguồn cầu tiềm năng"
        elif is_sell and is_real_estate:
            header = "### Tin Đăng Bán Tương Tự / Đối Thủ Cạnh Tranh"
            count_label = f"{total} tin đăng bán tương tự"
        else:
            header = "### Kết Quả Tìm Kiếm Khách Hàng Tiềm Năng (Lead Generation)"
            count_label = f"{total} leads"

        lines = [
            header,
            "",
            f"- **Tìm thấy:** {count_label} (từ {result.total_discovered} bản ghi thô qua {source_str}) — *{status_text}*",
        ]

        if table_id:
            safe_table_id = html.escape(str(table_id))
            lines.append(
                f"- **Bảng dữ liệu:** [Xem chi tiết](#table_id={safe_table_id})"
            )

        # CTA to open the Right Dock / Leads panel.
        if is_sell and is_real_estate:
            lines.append(
                "- 👉 [Mở Right Dock để xem toàn bộ tin đăng, lấy SĐT chủ tin, và phân tích giá](#right-dock=leads)"
            )
        else:
            lines.append("- 👉 [Mở Right Dock để xem toàn bộ leads và mở khóa liên hệ](#right-dock=leads)")

        if is_sell and is_real_estate:
            lines.append("- **Gợi ý hành động tiếp theo:** Tìm người mua · Lấy SĐT chủ tin · Phân tích giá")

        if result.degraded_sources:
            safe_degraded = [html.escape(s) for s in result.degraded_sources]
            lines.append(
                f"- _Nguồn gián đoạn (vẫn có dữ liệu từ các nguồn khác):_ `{'`, `'.join(safe_degraded)}`"
            )

        lines.append("")
        lines.append(
            "| Tên / Tiêu đề | Doanh nghiệp / Người liên hệ | Số điện thoại | Độ tin cậy | Nguồn |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        for lead in result.leads[:10]:
            phone_disp = _sanitize_markdown_cell(lead.primary_phone, max_length=20)
            contact_disp = _sanitize_markdown_cell(
                lead.company_name or lead.contact_name, max_length=40
            )
            title_disp = _sanitize_markdown_cell(lead.title, max_length=60)
            conf = f"{lead.confidence_score:.0f}%"
            src = "/".join(lead.sources)
            lines.append(
                f"| {title_disp} | {contact_disp} | `{phone_disp}` | {conf} | {src} |"
            )

        if len(result.leads) > 10:
            lines.append(
                f"*(...và còn {len(result.leads) - 10} leads khác đã lưu vào bảng dữ liệu)*"
            )

        return "\n".join(lines)
