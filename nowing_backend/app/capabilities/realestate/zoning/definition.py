"""Capability registration for realestate.zoning (Story 10.8 / AD-GIS-6)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.realestate.zoning.executor import build_zoning_executor
from app.capabilities.realestate.zoning.schemas import (
    ZoningCheckInput,
    ZoningCheckOutput,
)

REALESTATE_ZONING = Capability(
    name="realestate.zoning",
    description=(
        "Tra cứu bản đồ quy hoạch sử dụng đất không gian và kiểm tra cảnh báo rủi ro "
        "dính quy hoạch mở đường / hành lang giao thông (DGT) hoặc đất công viên cây xanh (CX) "
        "theo tọa độ GPS tại Việt Nam."
    ),
    input_schema=ZoningCheckInput,
    output_schema=ZoningCheckOutput,
    executor=build_zoning_executor(),
    billing_unit=None,
    docs_url="/docs/capabilities/realestate/zoning",
    context_aware=True,
)

register_capability(REALESTATE_ZONING)
