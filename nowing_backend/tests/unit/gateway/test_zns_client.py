"""Unit tests for ZNS Client, sending time-window validation, and DNC compliance (INV-23.9)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


@pytest.mark.unit
@pytest.mark.parametrize(
    ("hour", "minute", "expected_allowed"),
    [
        (7, 59, False),   # Before 08:00 VN Time -> Rejected
        (8, 0, True),     # 08:00 VN Time -> Allowed
        (12, 30, True),   # Mid-day -> Allowed
        (21, 30, True),   # 21:30 VN Time -> Allowed
        (21, 31, False),  # After 21:30 VN Time -> Rejected
        (23, 0, False),   # Night -> Rejected
    ],
)
def test_zns_sending_window_time_gate(hour: int, minute: int, expected_allowed: bool):
    """Verify Nghị định 91/2020/NĐ-CP sending window compliance (08:00 to 21:30 VN time)."""
    from app.gateway.zalo.zns_client import (
        is_zns_sending_window_open,  # Red-phase import
    )

    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    test_dt = datetime(2026, 8, 16, hour, minute, tzinfo=vn_tz)

    assert is_zns_sending_window_open(now=test_dt) is expected_allowed


@pytest.mark.unit
def test_zns_dynamic_variable_validation():
    """Verify dynamic template parameter validation against required keys."""
    from app.gateway.zalo.zns_client import validate_template_params  # Red-phase import

    template_schema = ["customer_name", "property_name", "price", "consultant_phone"]
    valid_payload = {
        "customer_name": "Nguyen Van A",
        "property_name": "Vinhomes Grand Park",
        "price": "3.2 Tỷ",
        "consultant_phone": "0912345678",
    }

    validated = validate_template_params(template_schema, valid_payload)
    assert validated == valid_payload

    # Missing required parameter raises ValueError or validation exception
    with pytest.raises(ValueError, match="Missing required template parameter"):
        validate_template_params(template_schema, {"customer_name": "Nguyen Van A"})
