"""Wire contract tests: FE CampaignCreateInput supply shape → CampaignSpec (Story 43.5).

Governed by spec: spec-43-5-fe-intake-tim-nha-cung-cap.md
- Wire keys top-level: direction="supply" + supply_criteria (D1).
- require_tax_id default ON (D2), location_profile derive từ locations[0] (D3).
- Route guard 422 vẫn còn (43.6 mới gỡ) — supply submit dừng ở plan/execute.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.lead_intelligence.campaign.schemas import CampaignSpec, ICPCriteria

pytestmark = pytest.mark.unit


def _supply_payload(**overrides: Any) -> dict[str, Any]:
    """Supply-shaped CampaignCreateInput đầy đủ keys."""
    payload: dict[str, Any] = {
        "name": "Tìm NCC vải",
        "workspace_id": 3,
        "direction": "supply",
        "supply_criteria": {
            "categories": ["vải", "dệt may"],
            "locations": ["Khánh Hòa", "TP. Hồ Chí Minh"],
            "min_rating": 4.0,
            "require_tax_id": True,
            "require_verified": True,
        },
        "query": "vải nhuộm tự nhiên",
        "source_budget_config": {
            "sources": ["chotot", "facebook"],
            "expected_leads_target": 30,
            "auto_unlock_verified_phones": True,
        },
        "launch_config": {"auto_start": True},
    }
    payload.update(overrides)
    return payload


class TestSupplyWireContract:
    """Matrix wire contract FE → CampaignSpec."""

    def test_supply_wire_ok(self) -> None:
        """SUPPLY_WIRE_OK: full keys top-level → spec đúng mọi fields."""
        spec = CampaignSpec.from_campaign_create_input(_supply_payload())
        assert spec.direction == "supply"
        assert spec.supply_criteria is not None
        assert spec.supply_criteria.categories == ["vải", "dệt may"]
        assert spec.supply_criteria.locations == ["Khánh Hòa", "TP. Hồ Chí Minh"]
        assert spec.supply_criteria.min_rating == 4.0
        assert spec.supply_criteria.require_tax_id is True
        assert spec.supply_criteria.require_verified is True
        assert spec.query == "vải nhuộm tự nhiên"
        assert spec.max_total_leads == 30
        assert spec.target_sources == ["chotot", "facebook"]
        assert spec.metadata["launch_config"] == {"auto_start": True}
        # Supply cấm ICP demand — converter không map icp_config
        assert spec.icp_criteria == ICPCriteria()

    def test_supply_derived_location_profile(self) -> None:
        """SUPPLY_DERIVED_LOCATION_PROFILE: locations[0] → province_code chuẩn (D3)."""
        spec = CampaignSpec.from_campaign_create_input(_supply_payload())
        assert spec.location_profile is not None
        # "Khánh Hòa" resolve qua location_normalize → code "KH"
        assert spec.location_profile.province_code == "KH"
        assert spec.location_profile.province_name == "Khánh Hòa"

    def test_supply_derived_location_profile_unknown_location(self) -> None:
        """Free-text không resolve được → giữ nguyên text (graceful degrade)."""
        spec = CampaignSpec.from_campaign_create_input(
            _supply_payload(
                supply_criteria={
                    "categories": ["vải"],
                    "locations": ["Quận 10 browser quelque"],
                }
            )
        )
        assert spec.location_profile is not None
        assert spec.location_profile.province_code == "Quận 10 browser quelque"

    def test_supply_require_tax_default(self) -> None:
        """SUPPLY_REQUIRE_TAX_DEFAULT: bỏ keys optional → default đúng (D2)."""
        spec = CampaignSpec.from_campaign_create_input(
            _supply_payload(
                supply_criteria={"categories": ["vải"], "locations": ["Hà Nội"]}
            )
        )
        assert spec.supply_criteria is not None
        assert spec.supply_criteria.require_tax_id is True
        assert spec.supply_criteria.require_verified is False
        assert spec.supply_criteria.min_rating == 0.0

    def test_supply_missing_criteria_rejected(self) -> None:
        """Supply mà thiếu supply_criteria → ValidationError (categories bắt buộc)."""
        payload = _supply_payload()
        del payload["supply_criteria"]
        with pytest.raises(ValidationError):
            CampaignSpec.from_campaign_create_input(payload)

    def test_supply_icp_config_rejected(self) -> None:
        """Supply + icp_config non-default → 422 (model_validator AD-5)."""
        payload = _supply_payload(icp_config={"locations": ["Hà Nội"]})
        with pytest.raises(ValueError, match="must not set non-default icp_criteria"):
            CampaignSpec.from_campaign_create_input(payload)

    def test_supply_from_payload_dispatch(self) -> None:
        """Pure supply payload (không icp_config/source_budget) → from_payload vẫn dispatch."""
        spec = CampaignSpec.from_payload(
            {
                "name": "Pure supply",
                "workspace_id": 1,
                "direction": "supply",
                "supply_criteria": {
                    "categories": ["cà phê"],
                    "locations": ["Đắk Lắk"],
                },
            }
        )
        assert spec.direction == "supply"
        assert spec.supply_criteria is not None
        assert spec.supply_criteria.categories == ["cà phê"]


class TestDemandUnchanged:
    """DEMAND_UNCHANGED: payload demand cũ parse bit-for-bit như trước 43.5."""

    def test_demand_payload_parse(self) -> None:
        payload = {
            "name": "FE Campaign",
            "workspace_id": 7,
            "icp_config": {
                "target_industries": ["f&B"],
                "locations": ["Hà Nội"],
                "keywords": "cà phê, trà",
            },
            "source_budget_config": {
                "sources": ["google_maps", "facebook"],
                "expected_leads_target": 100,
            },
            "launch_config": {"run_immediately": True},
        }
        spec = CampaignSpec.from_campaign_create_input(payload)
        assert spec.direction == "demand"
        assert spec.supply_criteria is None
        assert spec.name == "FE Campaign"
        assert spec.workspace_id == 7
        assert spec.icp_criteria.target_locations == ["Hà Nội"]
        assert spec.icp_criteria.target_industries == ["f&B"]
        assert spec.max_total_leads == 100
        assert spec.target_sources == ["google_maps", "facebook"]
        assert spec.metadata["launch_config"] == {"run_immediately": True}

    def test_demand_explicit_direction_key(self) -> None:
        """Demand payload gửi tường minh direction='demand' → parse như cũ."""
        payload = {
            "name": "Explicit demand",
            "workspace_id": 1,
            "direction": "demand",
            "icp_config": {"locations": ["Hà Nội"]},
            "source_budget_config": {"sources": ["chotot"]},
        }
        spec = CampaignSpec.from_campaign_create_input(payload)
        assert spec.direction == "demand"
        assert spec.supply_criteria is None

    def test_demand_with_supply_criteria_rejected(self) -> None:
        """Demand + supply_criteria → 422 (conflict, AD-5)."""
        payload = {
            "name": "Conflict",
            "workspace_id": 1,
            "direction": "demand",
            "supply_criteria": {"categories": ["vải"], "locations": ["KH"]},
            "icp_config": {},
        }
        with pytest.raises(ValueError, match="only allowed when direction='supply'"):
            CampaignSpec.from_campaign_create_input(payload)


class TestInvalidDirection:
    """Non-literal direction vẫn reject."""

    @pytest.mark.parametrize("bad", ["sideways", "SUPPLY", "buyer"])
    def test_invalid_direction_literal(self, bad: str) -> None:
        payload = _supply_payload(direction=bad)
        with pytest.raises(ValueError, match="direction must be"):
            CampaignSpec.from_campaign_create_input(payload)

    @pytest.mark.parametrize(
        "key,val",
        [("match_mode", "pool"), ("corpus_scope", "platform_b2b")],
    )
    def test_nondefault_platform_fields_still_rejected(self, key: str, val: str) -> None:
        """match_mode/corpus_scope non-default → vẫn 422 (platform phase)."""
        payload = _supply_payload(**{key: val})
        with pytest.raises(ValueError, match="not supported via CampaignCreateInput"):
            CampaignSpec.from_campaign_create_input(payload)
