"""Schemas for procurement.search capability (Story 16.5 / AC-5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.proprietary.platforms.muasamcong.schemas import ProcurementTenderItem


class ProcurementSearchInput(BaseModel):
    """Input payload for searching public procurement tenders."""

    keyword: str | None = Field(default=None, description="Từ khóa tìm kiếm gói thầu")
    field: str | None = Field(default=None, description="Lĩnh vực (Xây lắp, Mua sắm hàng hóa, Tư vấn)")
    min_price: float | None = Field(default=None, description="Giá gói thầu tối thiểu (VND)")
    max_price: float | None = Field(default=None, description="Giá gói thầu tối đa (VND)")
    location: str | None = Field(default=None, description="Tỉnh/Thành phố hoặc địa bàn mời thầu")
    page: int = Field(default=0, ge=0, description="Trang kết quả")
    size: int = Field(default=10, ge=1, le=50, description="Số lượng gói thầu mỗi trang")


class ProcurementSearchOutput(BaseModel):
    """Output payload returned from public procurement tender search."""

    tenders: list[ProcurementTenderItem] = Field(default_factory=list, description="Danh sách gói thầu")
    total_count: int = Field(default=0, description="Tổng số gói thầu tìm thấy")
    page: int = Field(default=0, description="Trang hiện tại")
    size: int = Field(default=10, description="Kích thước trang")
    degraded: bool = Field(default=False, description="Cờ cảnh báo nếu API gặp sự cố/fallback")
    degradation_reason: str | None = Field(default=None, description="Nguyên nhân fallback nếu có")
