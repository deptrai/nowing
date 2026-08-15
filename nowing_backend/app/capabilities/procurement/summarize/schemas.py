"""Schemas for procurement.summarize capability (Story 16.5 / AC-5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.proprietary.platforms.muasamcong.schemas import (
    CountdownInfo,
    QualificationCriteria,
)


class ProcurementSummarizeInput(BaseModel):
    """Input for summarizing tender dossiers and criteria."""

    bid_no: str = Field(min_length=1, max_length=100, description="Số TBMT (e.g. IB2400123456)")
    bid_turn_no: str = Field(default="00", max_length=10, description="Số lần chỉnh sửa / đăng tải")


class ProcurementSummarizeOutput(BaseModel):
    """Structured AI Executive Summary of HSMT."""

    bid_no: str = Field(description="Số TBMT")
    bid_turn_no: str = Field(default="00", description="Số lần chỉnh sửa")
    project_name: str | None = Field(default=None, description="Tên gói thầu")
    procuring_entity: str | None = Field(default=None, description="Bên mời thầu")
    investor: str | None = Field(default=None, description="Chủ đầu tư")
    bid_price: float | None = Field(default=None, description="Giá gói thầu (VND)")
    qualification: QualificationCriteria = Field(default_factory=QualificationCriteria, description="4 tiêu chí năng lực cốt lõi")
    countdown: CountdownInfo = Field(default_factory=CountdownInfo, description="Thời gian đếm ngược đóng thầu")
    summary_notes: str | None = Field(default=None, description="Ghi chú tổng hợp của AI")
    degraded: bool = Field(default=False, description="Cờ cảnh báo nếu API gặp sự cố hoặc không tìm thấy dữ liệu")
    degradation_reason: str | None = Field(default=None, description="Nguyên nhân fallback nếu có")
