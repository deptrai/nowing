"""Chat Agent Tool Bridge for Multi-Source Lead Generation Orchestrator (Story 21.15)."""

from __future__ import annotations

import html
import logging
from typing import Any

from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
)

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
        "Sales Copilot: tìm kiếm và quét khách hàng tiềm năng đa nguồn (Batdongsan, Chợ Tốt, "
        "Mua Bán, TopCV, ITviec, VietnamWorks, Masothue, Mua Sắm Công, Mạng xã hội, Web crawl, "
        "ChainLens), tự động khử trùng lặp, làm giàu số điện thoại và hỗ trợ smoke test."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Mô tả đối tượng khách hàng hoặc doanh nghiệp cần tìm bằng tiếng Việt/Anh tự nhiên",
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
            "campaign_id": {
                "type": "string",
                "description": "ID chiến dịch để theo dõi / tiếp tục",
            },
            "smoke_test": {
                "type": "boolean",
                "default": False,
                "description": "Chạy thử nghiệm nhỏ trước khi tốn credits",
            },
            "target_sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Danh sách nguồn cụ thể, ví dụ [\"batdongsan\", \"topcv\", \"masothue\"]",
            },
            "target_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Từ khóa cộng hưởng điểm fit",
            },
            "negative_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Từ khóa loại trừ",
            },
            "min_fit_score": {
                "type": "number",
                "default": 0.0,
                "description": "Điểm ICP tối thiểu (0-100)",
            },
            "enrichment_depth": {
                "type": "string",
                "enum": ["light", "standard", "deep"],
                "default": "standard",
                "description": "Mức độ làm giàu dữ liệu",
            },
            "intent": {
                "type": "string",
                "enum": ["buy", "sell", "hire", "partner", "invest", "rent", "research"],
                "default": "buy",
                "description": "Hành vi mua/bán/tuyển dụng/...",
            },
            "product_type": {
                "type": "string",
                "description": "Loại sản phẩm/dịch vụ, ví dụ SaaS HR, BĐS",
            },
            "price_segment": {
                "type": "string",
                "description": "Phân khúc giá: premium, mid-market, SMB",
            },
            "preferred_channels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Kênh outreach: email, phone, zalo, linkedin, facebook",
            },
            "limit": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
                "description": "Số leads tối đa",
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
        **kwargs: Any,
    ) -> str:
        """Execute orchestrator and return formatted Markdown summary for chat turn."""
        from app.lead_intelligence.campaign.schemas import (
            CampaignSpec,
            ICPCriteria,
        )

        filters: dict[str, Any] = {}
        if locations:
            filters["locations"] = locations
        if target_sources:
            filters["target_sources"] = target_sources
        if target_keywords:
            filters["target_keywords"] = target_keywords
        if negative_keywords:
            filters["negative_keywords"] = negative_keywords
        if preferred_channels:
            filters["preferred_channels"] = preferred_channels

        campaign_spec = None
        if campaign_id or smoke_test or target_sources or intent:
            campaign_spec = CampaignSpec(
                name=campaign_id or f"sales-copilot-{workspace_id}",
                workspace_id=workspace_id,
                client_id=campaign_id,
                table_id=table_id,
                query=query,
                icp_criteria=ICPCriteria(
                    target_keywords=target_keywords or [],
                    negative_keywords=negative_keywords or [],
                    target_locations=locations or [],
                    target_industries=[product_type] if product_type else [],
                    min_fit_score=min_fit_score,
                ),
                intent_tags=[intent, product_type] if product_type else [intent],
                target_sources=target_sources or [],
                max_total_leads=min(limit, 10) if smoke_test else limit,
                metadata={
                    "smoke_test": smoke_test,
                    "enrichment_depth": enrichment_depth,
                    "product_type": product_type,
                    "price_segment": price_segment,
                    "preferred_channels": preferred_channels or [],
                },
            )

        if self.db_session is not None:
            result = await self.orchestrator.execute_and_persist(
                session=self.db_session,
                workspace_id=workspace_id,
                query=query,
                table_id=table_id,
                limit=min(limit, 10) if smoke_test else limit,
                filters=filters or None,
                campaign_spec=campaign_spec,
            )
        else:
            result = await self.orchestrator.execute_multi_source_lead_gen(
                workspace_id=workspace_id,
                query=query,
                filters=filters or None,
                table_id=table_id,
                limit=min(limit, 10) if smoke_test else limit,
                campaign_spec=campaign_spec,
            )

        total = result.total_deduplicated
        sources_used = sorted({s for lead in result.leads for s in lead.sources})
        source_str = ", ".join(sources_used) if sources_used else "đa nguồn"

        lines = [
            "### Kết Quả Tìm Kiếm Khách Hàng Tiềm Năng (Lead Generation)",
            "",
            f"- **Trạng thái:** `{result.status.upper()}`",
            f"- **Đã tìm thấy:** `{total} leads` (Khử trùng từ {result.total_discovered} bản ghi thô từ nguồn {source_str})",
        ]

        if table_id:
            safe_table_id = html.escape(str(table_id))
            lines.append(
                f"- **Tab Bảng Dữ Liệu:** [Xem Bảng Dữ Liệu Live](#table_id={safe_table_id})"
            )

        if result.degraded_sources:
            safe_degraded = [html.escape(s) for s in result.degraded_sources]
            lines.append(
                f"- ⚠️ **Nguồn bị gián đoạn/bỏ qua:** {', '.join(safe_degraded)}"
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
