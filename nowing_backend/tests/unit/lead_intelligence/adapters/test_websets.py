"""Unit tests for WebsetsAdapter (Story 41.1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lead_intelligence.adapters.base import RawLeadRecord
from app.lead_intelligence.adapters.websets import WebsetsAdapter
from app.models.webset_campaign import WebsetCampaign
from app.services.chainlens.websets import WebsetsService

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_service() -> WebsetsService:
    service = AsyncMock(spec=WebsetsService)
    service.create_webset.return_value = {
        "id": "wbs_abc123",
        "status": "running",
    }
    return service


class TestWebsetsAdapter:
    @pytest.mark.asyncio
    async def test_search_leads_creates_campaign_and_returns_empty(
        self, mock_service: WebsetsService
    ) -> None:
        adapter = WebsetsAdapter(service=mock_service)
        workspace_id = 999

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        with patch(
            "app.lead_intelligence.adapters.websets.async_session_maker",
            return_value=mock_session_cm,
        ):
            leads = await adapter.search_leads(
                workspace_id=workspace_id,
                query="Công ty công nghệ tại Hà Nội",
                filters={
                    "campaign_id": "camp_test_1",
                    "base_webhook_url": "http://localhost:8000",
                },
            )

        assert leads == []
        assert adapter.last_execution_status == "pending"

        # Verify create_webset was called with expected metadata
        mock_service.create_webset.assert_called_once()
        _, kwargs = mock_service.create_webset.call_args
        assert kwargs["workspace_id"] == workspace_id
        assert kwargs["metadata"]["campaign_id"] == "camp_test_1"
        assert (
            "http://localhost:8000/api/v1/webhooks/chainlens/webset-idle?t="
            in kwargs["metadata"]["webhookUrl"]
        )
        # Verify columns contract uses 'key' instead of 'name' (Story 41.2)
        for col in kwargs["columns"]:
            assert "key" in col
            assert "name" not in col

        # Verify DB row WebsetCampaign was added and committed
        mock_session.add.assert_called_once()
        campaign = mock_session.add.call_args[0][0]
        assert isinstance(campaign, WebsetCampaign)
        assert campaign.workspace_id == workspace_id
        assert campaign.campaign_id == "camp_test_1"
        assert campaign.webset_id == "wbs_abc123"
        assert campaign.status == "pending"
        assert len(campaign.webhook_secret) > 10
        mock_session.commit.assert_awaited_once()

    def test_normalize_lead(self) -> None:
        adapter = WebsetsAdapter()
        raw = RawLeadRecord(
            source_name="websets",
            source_id="item_001",
            data={
                "company_name": "Công ty TNHH Phần mềm",
                "title": "Giám đốc kỹ thuật",
                "phone": "0987654321",
                "email": "dev@company.vn",
                "source_url": "https://company.vn",
            },
        )

        norm = adapter.normalize_lead(raw)
        assert norm.source_name == "websets"
        assert norm.source_id == "item_001"
        assert norm.company_name == "Công ty TNHH Phần mềm"
        assert norm.title == "Giám đốc kỹ thuật"
        assert norm.primary_phone == "0987654321"
        assert norm.primary_email == "dev@company.vn"
        assert norm.source_url == "https://company.vn"

    def test_extract_contact_candidates(self) -> None:
        adapter = WebsetsAdapter()
        raw = RawLeadRecord(
            source_name="websets",
            source_id="item_002",
            data={
                "phone": "+84 987 654 321",
                "email": "CONTACT@EXAMPLE.COM ",
            },
        )

        candidates = adapter.extract_contact_candidates(raw)
        assert len(candidates) == 2

        phone_cand = next(c for c in candidates if c.channel == "phone")
        assert phone_cand.value == "0987654321"

        email_cand = next(c for c in candidates if c.channel == "email")
        assert email_cand.value == "contact@example.com"

    @pytest.mark.asyncio
    async def test_search_leads_chainlens_unavailable_returns_degraded(
        self, mock_service: WebsetsService
    ) -> None:
        """ChainLens 5xx/timeout -> adapter degraded, không raise (spec CHAINLENS_DOWN)."""
        from app.services.chainlens.websets import WebsetsUnavailable

        adapter = WebsetsAdapter(service=mock_service)
        mock_service.create_webset.side_effect = WebsetsUnavailable("503 down")

        leads = await adapter.search_leads(
            workspace_id=1,
            query="test",
            filters={"base_webhook_url": "http://localhost:8000"},
        )

        assert leads == []
        assert adapter.last_execution_status == "degraded"

    @pytest.mark.asyncio
    async def test_search_leads_missing_webset_id_raises_and_marks_failed(
        self, mock_service: WebsetsService
    ) -> None:
        mock_service.create_webset.return_value = {"status": "running"}
        adapter = WebsetsAdapter(service=mock_service)

        with pytest.raises(ValueError, match="missing webset_id"):
            await adapter.search_leads(
                workspace_id=1,
                query="test",
                filters={"base_webhook_url": "http://localhost:8000"},
            )
        assert adapter.last_execution_status == "failed"

    @pytest.mark.asyncio
    async def test_search_leads_resets_status_from_previous_run(
        self, mock_service: WebsetsService
    ) -> None:
        """Singleton adapter không rò rỉ status 'pending'/'failed' run trước."""
        adapter = WebsetsAdapter(service=mock_service)
        adapter.last_execution_status = "pending"
        mock_service.create_webset.side_effect = RuntimeError("boom")

        await adapter.search_leads(
            workspace_id=1,
            query="test",
            filters={"base_webhook_url": "http://localhost:8000"},
        )
        # Failure mới ghi đè lên 'pending' cũ thay vì giữ nguyên
        assert adapter.last_execution_status == "degraded"
