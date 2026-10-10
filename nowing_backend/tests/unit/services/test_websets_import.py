"""Unit tests for WebsetsImportService and map_webset_entity (Story 41.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.webset_campaign import WebsetCampaign
from app.services.chainlens.websets import WebsetsService
from app.services.websets_import import WebsetsImportService, map_webset_entity

pytestmark = pytest.mark.unit


class TestMapWebsetEntity:
    def test_map_webset_entity_full_data(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "it_123",
            "url": "https://example.com/company",
            "status": "ready",
            "data": {
                "name": "Công ty TNHH Phần mềm",
                "phone": "+84 987 654 321",
                "email": "contact@example.com",
            },
        }

        payload = map_webset_entity(raw_item, webset_id="wbs_999")
        assert payload is not None
        assert payload["company_name"] == "Công ty TNHH Phần mềm"
        assert payload["source"] == "websets"
        assert payload["source_url"] == "https://example.com/company"
        assert payload["phone"] == "+84 987 654 321"
        assert payload["email"] == "contact@example.com"
        assert payload["raw"]["entity_id"] == "it_123"
        assert payload["raw"]["webset_id"] == "wbs_999"

    def test_map_webset_entity_empty_data_skipped(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "it_empty",
            "status": "ready",
            "data": {},
        }
        payload = map_webset_entity(raw_item)
        assert payload is None

    def test_map_webset_entity_not_ready_skipped(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "it_pending",
            "status": "running",
            "data": {"name": "Running Corp", "phone": "0912345678"},
        }
        payload = map_webset_entity(raw_item)
        assert payload is None

    def test_map_webset_entity_fallback_name(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "it_fallback",
            "status": "verified",
            "url": "https://company.vn",
            "data": {"phone": "0912345678"},
        }
        payload = map_webset_entity(raw_item)
        assert payload is not None
        assert payload["company_name"] == "Webset Lead it_fallback"
        assert payload["phone"] == "0912345678"


class TestWebsetsImportService:
    @pytest.mark.asyncio
    async def test_import_webset_success(self) -> None:
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            yield {
                "id": "it_1",
                "status": "ready",
                "data": {"name": "Acme Corp", "phone": "0987111222"},
            }
            yield {
                "id": "it_2",
                "status": "verified",
                "data": {"name": "Beta LLC", "email": "info@beta.vn"},
            }

        mock_websets_svc.iter_ready_items = _mock_iter

        mock_campaign = WebsetCampaign(
            webset_id="wbs_123",
            campaign_id="camp_abc",
            workspace_id=42,
            status="pending",
            imported_count=0,
            stats={},
        )

        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_campaign
        mock_session.execute.return_value = mock_res

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        mock_batch_svc.ingest_batch.return_value = {"ingested_count": 2, "errors": []}

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        result = await import_service.import_webset(
            "wbs_123",
            session_factory=lambda: mock_session_cm,
        )

        assert result["status"] == "completed"
        assert result["imported_count"] == 2
        assert mock_campaign.status == "completed"
        assert mock_campaign.imported_count == 2
        mock_batch_svc.ingest_batch.assert_called_once()
        _, kwargs = mock_batch_svc.ingest_batch.call_args
        assert kwargs["workspace_id"] == 42
        assert len(kwargs["leads"]) == 2
        assert kwargs["leads"][0]["client_id"] == "camp_abc"

    @pytest.mark.asyncio
    async def test_import_webset_empty(self) -> None:
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            if False:
                yield {}

        mock_websets_svc.iter_ready_items = _mock_iter

        mock_campaign = WebsetCampaign(
            webset_id="wbs_empty",
            campaign_id="camp_abc",
            workspace_id=42,
            status="pending",
            imported_count=0,
            stats={},
        )

        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_campaign
        mock_session.execute.return_value = mock_res

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        result = await import_service.import_webset(
            "wbs_empty",
            session_factory=lambda: mock_session_cm,
        )

        assert result["status"] == "completed"
        assert result["imported_count"] == 0
        assert mock_campaign.status == "completed"
        assert mock_campaign.imported_count == 0
        mock_batch_svc.ingest_batch.assert_not_called()


class TestWebsetsImportTask:
    def test_import_webset_leads_celery_task(self) -> None:
        from app.tasks.webset_import import import_webset_leads

        with patch("app.tasks.webset_import.WebsetsImportService") as mock_svc_cls:
            mock_instance = AsyncMock()
            mock_instance.import_webset.return_value = {
                "status": "completed",
                "webset_id": "wbs_123",
                "imported_count": 5,
            }
            mock_svc_cls.return_value = mock_instance

            # Call the underlying task function (.apply or directly)
            res = import_webset_leads("wbs_123")
            assert res == {
                "status": "completed",
                "webset_id": "wbs_123",
                "imported_count": 5,
            }
            mock_instance.import_webset.assert_awaited_once_with("wbs_123")

