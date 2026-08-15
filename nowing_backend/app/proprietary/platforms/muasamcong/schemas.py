"""Pydantic schemas for Muasamcong scraper, dossiers, and AI summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProcurementTenderItem(BaseModel):
    """Normalized tender item returned from e-GP v2.0."""

    model_config = ConfigDict(from_attributes=True)

    bid_no: str = Field(description="Số TBMT (e.g. IB2400123456)")
    bid_turn_no: str = Field(default="00", description="Số lần chỉnh sửa / đăng tải")
    project_name: str = Field(description="Tên gói thầu / Tên dự án")
    procuring_entity: str | None = Field(default=None, description="Bên mời thầu")
    investor: str | None = Field(default=None, description="Chủ đầu tư")
    field: str | None = Field(default=None, description="Lĩnh vực (Xây lắp, Hàng hóa, Tư vấn)")
    bid_type: str | None = Field(default=None, description="Hình thức lựa chọn (Đấu thầu rộng rãi)")
    funding_source: str | None = Field(default=None, description="Nguồn vốn")
    bid_price: float | None = Field(default=None, description="Giá gói thầu (VND)")
    bid_open_date: datetime | None = Field(default=None, description="Thời điểm mở thầu")
    bid_closing_at: datetime | None = Field(default=None, description="Thời điểm đóng thầu")
    location: str | None = Field(default=None, description="Địa điểm thực hiện gói thầu")
    dossier_url: str | None = Field(default=None, description="Đường link tải E-HSMT")
    raw_specs: dict[str, Any] = Field(default_factory=dict, description="Thông số kỹ thuật thô từ API")
    status: str = Field(default="active", description="Trạng thái (active, closed, cancelled)")


class ScrapeResult(BaseModel):
    """Result wrapper for tender scraping operations."""

    items: list[ProcurementTenderItem] = Field(default_factory=list)
    total_elements: int = 0
    total_pages: int = 0
    page_number: int = 0
    page_size: int = 10
    degraded: bool = False
    degradation_reason: str | None = None


class TextChunk(BaseModel):
    """A vectorized chunk of dossier text."""

    chunk_index: int
    content: str
    section_title: str | None = None
    embedding: list[float] | None = None


class QualificationCriteria(BaseModel):
    """4 Core qualification criteria extracted from E-HSMT (Story 16.5 / AC-4)."""

    annual_turnover: str = Field(default="Không yêu cầu cụ thể", description="Yêu cầu doanh thu bình quân hàng năm")
    similar_contracts: str = Field(default="Không yêu cầu cụ thể", description="Kinh nghiệm thực hiện hợp đồng tương tự")
    key_personnel: str = Field(default="Không yêu cầu cụ thể", description="Yêu cầu về nhân sự chủ chốt")
    bid_security: str = Field(default="Không yêu cầu cụ thể", description="Giá trị và thời hạn bảo đảm dự thầu")


class CountdownInfo(BaseModel):
    """Bid deadline countdown intelligence (Story 16.5 / AC-4 / AD-PROC-8)."""

    is_closed: bool = False
    is_urgent: bool = False  # True if < 48 hours remaining
    hours_remaining: float = 0.0
    countdown_text: str = "Đã đóng thầu"


class ExecutiveSummary(BaseModel):
    """Executive AI summary for tender cards."""

    bid_no: str
    bid_turn_no: str = "00"
    qualification: QualificationCriteria = Field(default_factory=QualificationCriteria)
    countdown: CountdownInfo = Field(default_factory=CountdownInfo)
    procuring_entity: str | None = None
    summary_notes: str | None = None
