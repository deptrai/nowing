"""Unit tests for CampaignSpec direction fields + AD-5 joint validation (Story 43.1).

Governed by spec: spec-43-1-campaignspec-direction-fields-ad5-validation.md
- Truth-table I/O matrix: mọi ô = 1 case parametrize, không ô nào silently pass.
- Regression: demand-shaped spec cũ parse y hệt trước khi thêm field mới.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.lead_intelligence.campaign.schemas import CampaignSpec, ICPCriteria

pytestmark = pytest.mark.unit


def _base_payload(**overrides: Any) -> dict[str, Any]:
    """Payload demand-shaped tối thiểu (giống spec cũ)."""
    payload: dict[str, Any] = {
        "name": "Test Campaign",
        "workspace_id": 1,
    }
    payload.update(overrides)
    return payload


def _supply_criteria(**overrides: Any) -> dict[str, Any]:
    criteria: dict[str, Any] = {
        "categories": ["trầm hương"],
        "locations": ["Khánh Hòa"],
    }
    criteria.update(overrides)
    return criteria


# ---------------------------------------------------------------------------
# 1. Truth-table I/O matrix (AD-5)
# ---------------------------------------------------------------------------
class TestDirectionTruthTable:
    """Mỗi ô trong I/O matrix của spec = 1 case."""

    def test_demand_default(self) -> None:
        """DEMAND_DEFAULT: payload thiếu 5 field mới → parse OK, direction='demand'."""
        spec = CampaignSpec.model_validate(_base_payload())
        assert spec.direction == "demand"
        assert spec.match_mode == "mine"
        assert spec.supply_criteria is None
        assert spec.corpus_scope == "workspace"
        assert spec.visibility == "private"

    def test_supply_ok(self) -> None:
        """SUPPLY_OK: direction='supply' + supply_criteria hợp lệ → parse OK."""
        spec = CampaignSpec.model_validate(
            _base_payload(
                direction="supply",
                supply_criteria=_supply_criteria(),
            )
        )
        assert spec.direction == "supply"
        assert spec.supply_criteria is not None
        assert spec.supply_criteria.categories == ["trầm hương"]
        assert spec.supply_criteria.locations == ["Khánh Hòa"]

    def test_supply_no_criteria(self) -> None:
        """SUPPLY_NO_CRITERIA: supply mà không có supply_criteria → 422."""
        with pytest.raises(ValidationError, match="requires supply_criteria"):
            CampaignSpec.model_validate(_base_payload(direction="supply"))

    def test_demand_with_criteria(self) -> None:
        """DEMAND_WITH_CRITERIA: demand + supply_criteria → 422."""
        with pytest.raises(ValidationError, match="only allowed when direction='supply'"):
            CampaignSpec.model_validate(
                _base_payload(supply_criteria=_supply_criteria())
            )

    @pytest.mark.parametrize("mode", ["pool", "hybrid"])
    def test_pool_gated(self, mode: str) -> None:
        """POOL_GATED: match_mode pool/hybrid (mọi direction) → 422 (platform phase)."""
        with pytest.raises(ValidationError, match="platform phase"):
            CampaignSpec.model_validate(_base_payload(match_mode=mode))
        with pytest.raises(ValidationError, match="platform phase"):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(),
                    match_mode=mode,
                )
            )

    @pytest.mark.parametrize("direction", ["demand", "supply"])
    def test_corpus_gated(self, direction: str) -> None:
        """CORPUS_GATED: corpus_scope='platform_b2b' → 422 (cả 2 direction)."""
        extra: dict[str, Any] = {}
        if direction == "supply":
            extra["supply_criteria"] = _supply_criteria()
        with pytest.raises(ValidationError, match="platform phase"):
            CampaignSpec.model_validate(
                _base_payload(direction=direction, corpus_scope="platform_b2b", **extra)
            )

    def test_supply_empty_categories(self) -> None:
        """SUPPLY_EMPTY: categories rỗng → 422 (min_length)."""
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(categories=[]),
                )
            )

    def test_supply_empty_locations(self) -> None:
        """SUPPLY_EMPTY: locations rỗng → 422 (min_length)."""
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(locations=[]),
                )
            )

    def test_supply_empty_string_items(self) -> None:
        """SUPPLY_EMPTY_ITEM: item chuỗi rỗng/whitespace → 422 (item-level)."""
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(categories=[""]),
                )
            )
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(locations=["   "]),
                )
            )

    def test_supply_visibility_poolable(self) -> None:
        """SUPPLY_VISIBILITY: supply + visibility='poolable' → OK (nhãn inert)."""
        spec = CampaignSpec.model_validate(
            _base_payload(
                direction="supply",
                supply_criteria=_supply_criteria(),
                visibility="poolable",
            )
        )
        assert spec.visibility == "poolable"

    def test_invalid_direction_literal(self) -> None:
        """INVALID_DIRECTION: direction ngoài enum → ValidationError."""
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(_base_payload(direction="sideways"))

    def test_supply_icp_mix(self) -> None:
        """SUPPLY_ICP_MIX: supply + icp_criteria non-default → 422."""
        with pytest.raises(ValidationError, match="must not set non-default icp_criteria"):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(),
                    icp_criteria={"target_industries": ["retail"]},
                )
            )

    def test_supply_icp_equivalent_default(self) -> None:
        """SUPPLY_ICP_EQUIV: supply + icp == ICPCriteria() (executor cũ build rỗng) → OK."""
        spec = CampaignSpec.model_validate(
            _base_payload(
                direction="supply",
                supply_criteria=_supply_criteria(),
                icp_criteria={"target_categories": [], "min_fit_score": 0.0},
            )
        )
        assert spec.icp_criteria == ICPCriteria()

    def test_supply_triggers(self) -> None:
        """SUPPLY_TRIGGERS: supply + signal_triggers/intent_tags non-empty → 422."""
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(),
                    signal_triggers=["funding"],
                )
            )
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(),
                    intent_tags=["hiring"],
                )
            )

    def test_supply_target_sources_escape_hatch(self) -> None:
        """SUPPLY_TARGET_SRC: supply + target_sources → OK (escape hatch, documented)."""
        spec = CampaignSpec.model_validate(
            _base_payload(
                direction="supply",
                supply_criteria=_supply_criteria(),
                target_sources=["enterprise"],
            )
        )
        assert spec.target_sources == ["enterprise"]

    def test_demand_visibility_poolable(self) -> None:
        """DEMAND_VISIBILITY: demand + visibility='poolable' → OK (nhãn inert)."""
        spec = CampaignSpec.model_validate(_base_payload(visibility="poolable"))
        assert spec.visibility == "poolable"

    @pytest.mark.parametrize("rating", [-1.0, 5.1])
    def test_min_rating_bounds(self, rating: float) -> None:
        """BOUNDS: min_rating ngoài [0, 5] → 422."""
        with pytest.raises(ValidationError):
            CampaignSpec.model_validate(
                _base_payload(
                    direction="supply",
                    supply_criteria=_supply_criteria(min_rating=rating),
                )
            )


# ---------------------------------------------------------------------------
# 2. Regression: demand-shaped spec cũ parse y hệt
# ---------------------------------------------------------------------------
class TestOldPayloadRegression:
    """Regression: payload cũ (không có field mới) parse không đổi qua mọi entry-point."""

    def test_model_validate_old_payload(self) -> None:
        spec = CampaignSpec.model_validate(
            _base_payload(query="tìm buyer", max_total_leads=50)
        )
        assert spec.query == "tìm buyer"
        assert spec.max_total_leads == 50

    def test_from_payload_old_payload(self) -> None:
        spec = CampaignSpec.from_payload(_base_payload(query="abc"))
        assert spec.direction == "demand"
        assert spec.query == "abc"

    def test_from_campaign_create_input_old_payload(self) -> None:
        """FE_OLD: CampaignCreateInput payload cũ (không key mới) → parse OK."""
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

    def test_from_campaign_create_input_accepts_supply_direction_keys(self) -> None:
        """FE payload mang direction='supply' + supply_criteria → parse đúng spec (43.5).

        Story 43.5 gỡ guard tạm: converter giờ wire direction qua FE contract
        thay vì raise. icp_config phải vắng mặt (supply cấm ICP demand).
        """
        payload = {
            "name": "FE Campaign",
            "workspace_id": 7,
            "direction": "supply",
            "supply_criteria": _supply_criteria(),
            "source_budget_config": {"sources": ["google_maps"]},
        }
        spec = CampaignSpec.from_campaign_create_input(payload)
        assert spec.direction == "supply"
        assert spec.supply_criteria is not None
        assert spec.supply_criteria.categories == ["trầm hương"]
        assert spec.supply_criteria.locations == ["Khánh Hòa"]
        assert spec.supply_criteria.require_tax_id is True
        assert spec.icp_criteria == ICPCriteria()

    @pytest.mark.parametrize(
        "key,val",
        [
            ("match_mode", "pool"),
            ("corpus_scope", "platform_b2b"),
            ("visibility", "poolable"),
        ],
    )
    def test_from_campaign_create_input_rejects_nondefault_direction_fields(
        self, key: str, val: str
    ) -> None:
        """Field direction-scoped non-default lẻ lẻ qua FE shape cũng 422."""
        payload = {
            "name": "FE Campaign",
            "workspace_id": 7,
            key: val,
            "icp_config": {"locations": ["Hà Nội"]},
        }
        with pytest.raises(ValueError, match="not supported via CampaignCreateInput"):
            CampaignSpec.from_campaign_create_input(payload)


# ---------------------------------------------------------------------------
# 4. Route guard tạm: direction='supply' → 422 cho tới khi 43.6 wire xong
# ---------------------------------------------------------------------------
class TestSupplyExecutionGuard:
    """Silent demand-execution của supply intent = tốn credits quét rác → guard 422."""

    def _supply_payload(self) -> dict[str, Any]:
        return _base_payload(
            direction="supply",
            supply_criteria=_supply_criteria(),
        )

    def test_execute_campaign_rejects_supply(self) -> None:
        """POST /campaigns/execute với direction='supply' → 422 trước khi vào engine."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        from fastapi import HTTPException

        from app.auth.context import AuthContext
        from app.routes.campaign_routes import execute_campaign

        auth = AuthContext.session(SimpleNamespace(id="u1"))
        with patch(
            "app.routes.campaign_routes.check_permission", new=AsyncMock()
        ), pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                execute_campaign(
                    1, self._supply_payload(), True, AsyncMock(), auth
                )
            )
        assert exc_info.value.status_code == 422
        assert "supply" in exc_info.value.detail

    def test_plan_campaign_rejects_supply(self) -> None:
        """POST /campaigns/plan với direction='supply' → 422 (plan cũng không đúng)."""
        import asyncio
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.auth.context import AuthContext
        from app.routes.campaign_routes import plan_campaign

        auth = AuthContext.session(SimpleNamespace(id="u1"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                plan_campaign(
                    1, self._supply_payload(), AsyncMock(), auth, SimpleNamespace()
                )
            )
        assert exc_info.value.status_code == 422
        assert "supply" in exc_info.value.detail
