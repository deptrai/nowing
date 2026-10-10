"""Unit tests for WebsetsImportService and map_webset_entity (Story 41.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from app.models.billing import BillingEvent
from app.models.webset_campaign import WebsetCampaign
from app.services.chainlens.websets import WebsetsService
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.websets_import import (
    WEBSET_LEAD_IMPORT_COST_MICROS,
    WebsetsImportService,
    map_webset_entity,
)

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

    def test_map_webset_entity_enrichments_full(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "ent_101",
            "status": "ready",
            "canonical_url": "https://techcorp.vn",
            "enrichments": {
                "company_name": {"value": "Tech Corp Vietnam", "status": "verified"},
                "phone": {"value": "+84 901 234 567", "status": "verified"},
                "email": {"value": "hr@techcorp.vn", "status": "verified"},
                "title": {"value": "Managing Director", "status": "verified"},
                "website": {"value": "techcorp.vn", "status": "verified"},
            },
        }

        payload = map_webset_entity(raw_item, webset_id="wbs_456")
        assert payload is not None
        assert payload["company_name"] == "Tech Corp Vietnam"
        assert payload["phone"] == "+84 901 234 567"
        assert payload["email"] == "hr@techcorp.vn"
        assert payload["title"] == "Managing Director"
        assert payload["domain"] == "techcorp.vn"
        assert payload["source"] == "websets"
        assert payload["source_url"] == "https://techcorp.vn"
        assert payload["_entity_id"] == "ent_101"
        assert payload["raw"]["entity_id"] == "ent_101"
        assert payload["raw"]["webset_id"] == "wbs_456"
        assert payload["extra_metadata"] == {"websets": {}}

    def test_map_webset_entity_unmapped_enrichments_stored_in_metadata(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "ent_102",
            "status": "verified",
            "url": "https://store.vn",
            "enrichments": {
                "company_name": {"value": "Retail Store", "status": "verified"},
                "opening_hours": {"value": "08:00 - 21:00", "status": "verified"},
                "annual_revenue": {"value": "$5M", "status": "verified"},
            },
        }

        payload = map_webset_entity(raw_item)
        assert payload is not None
        assert payload["company_name"] == "Retail Store"
        assert payload["extra_metadata"]["websets"]["opening_hours"] == {
            "value": "08:00 - 21:00",
            "status": "verified",
        }
        assert payload["extra_metadata"]["websets"]["annual_revenue"] == {
            "value": "$5M",
            "status": "verified",
        }

    def test_map_webset_entity_fallback_grounding_url_as_source_url(self) -> None:
        raw_item: dict[str, Any] = {
            "id": "ent_103",
            "status": "ready",
            "enrichments": {
                "company_name": {
                    "value": "Grounding Test",
                    "groundingUrl": "https://yellowpages.vn/listing/123",
                },
                "phone": {"value": "0987654321"},
            },
        }

        payload = map_webset_entity(raw_item)
        assert payload is not None
        assert payload["company_name"] == "Grounding Test"
        assert payload["source_url"] == "https://yellowpages.vn/listing/123"

    def test_map_webset_entity_truncates_to_varchar_bounds(self) -> None:
        """company_name > 200 / domain > 255 must be truncated.

        Regression cho AI-41.4: giá trị quá dài ném StringDataRightTruncationError
        và abort cả batch 100 leads.
        """
        raw_item: dict[str, Any] = {
            "id": "ent_long",
            "status": "ready",
            "enrichments": {
                "company_name": {"value": "X" * 500},
                "website": {"value": "d" * 300 + ".vn"},
            },
        }

        payload = map_webset_entity(raw_item)
        assert payload is not None
        assert payload["company_name"] == "X" * 200
        assert len(payload["company_name"]) == 200
        assert payload["domain"] == ("d" * 300 + ".vn")[:255]
        assert len(payload["domain"]) == 255


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

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(
                    return_value=UUID("22222222-2222-2222-2222-222222222222")
                ),
            ),
            patch("app.services.wallet_credit.reserve_credit", new=AsyncMock()),
            patch("app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()),
            patch("app.services.wallet_credit.release_credit", new=AsyncMock()),
        ):
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

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(
                    return_value=UUID("22222222-2222-2222-2222-222222222222")
                ),
            ),
            patch("app.services.wallet_credit.reserve_credit", new=AsyncMock()),
            patch("app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()),
            patch("app.services.wallet_credit.release_credit", new=AsyncMock()),
        ):
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

    @pytest.mark.asyncio
    async def test_import_webset_ingest_failure_marks_campaign_failed(self) -> None:
        """ingest_batch raise -> campaign.status='failed' và exception propagate."""
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            yield {
                "id": "it_1",
                "status": "ready",
                "data": {"name": "Acme", "phone": "0987111222"},
            }

        mock_websets_svc.iter_ready_items = _mock_iter

        mock_campaign = WebsetCampaign(
            webset_id="wbs_123",
            campaign_id="camp_abc",
            workspace_id=42,
            status="pending",
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
        mock_batch_svc.ingest_batch.side_effect = RuntimeError("db exploded")

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(
                    return_value=UUID("22222222-2222-2222-2222-222222222222")
                ),
            ),
            patch("app.services.wallet_credit.reserve_credit", new=AsyncMock()),
            patch("app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()),
            patch("app.services.wallet_credit.release_credit", new=AsyncMock()),
            pytest.raises(RuntimeError, match="db exploded"),
        ):
            await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert mock_campaign.status == "failed"

    @pytest.mark.asyncio
    async def test_import_webset_completed_campaign_skipped(self) -> None:
        """Campaign status='completed' -> skip sớm, không drain lại."""
        mock_websets_svc = MagicMock(spec=WebsetsService)

        called = False

        async def _mock_iter(webset_id: str, workspace_id: int):
            nonlocal called
            called = True
            yield {"id": "it_1", "status": "ready", "data": {"name": "X"}}

        mock_websets_svc.iter_ready_items = _mock_iter

        mock_campaign = WebsetCampaign(
            webset_id="wbs_123",
            campaign_id="camp_abc",
            workspace_id=42,
            status="completed",
            imported_count=7,
            stats={},
        )

        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_campaign
        mock_session.execute.return_value = mock_res
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=AsyncMock(),
        )

        result = await import_service.import_webset(
            "wbs_123",
            session_factory=lambda: mock_session_cm,
        )

        assert result["status"] == "skipped"
        assert result["imported_count"] == 7
        assert called is False


class TestWebsetsImportTaskRegistration:
    def test_celery_task_registered(self) -> None:
        from app.celery_app import celery_app

        assert "app.tasks.webset_import.import_webset_leads" in celery_app.tasks


class TestWebsetsImportBilling:
    @pytest.mark.asyncio
    async def test_billing_reserve_and_commit_success(self) -> None:
        owner_id = UUID("11111111-1111-1111-1111-111111111111")
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
        mock_session.add = MagicMock()
        mock_session.new = []

        def _mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)
            if "webset_campaigns" in stmt_str:
                res.scalar_one_or_none.return_value = mock_campaign
            elif "billing_events" in stmt_str:
                res.scalar_one_or_none.return_value = None
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_session.execute.side_effect = _mock_execute

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        mock_batch_svc.ingest_batch.return_value = {
            "ingested_count": 2,
            "accepted": [True, True],
        }

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=owner_id),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit", new=AsyncMock()
            ) as mock_reserve,
            patch(
                "app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()
            ) as mock_commit,
            patch(
                "app.services.wallet_credit.release_credit", new=AsyncMock()
            ) as mock_release,
        ):
            res = await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert res["status"] == "completed"
        assert res["imported_count"] == 2
        mock_reserve.assert_awaited_once_with(
            mock_session, owner_id, 2 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        mock_commit.assert_awaited_once_with(
            mock_session, owner_id, 2 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        mock_release.assert_not_called()

        added_billing_events = [
            call.args[0]
            for call in mock_session.add.call_args_list
            if isinstance(call.args[0], BillingEvent)
        ]
        assert len(added_billing_events) == 2
        assert added_billing_events[0].event_entity_type == "webset"
        assert added_billing_events[0].event_type == "lead_import"
        assert added_billing_events[0].event_id == uuid5(NAMESPACE_URL, "wbs_123:it_1")
        assert added_billing_events[1].event_id == uuid5(NAMESPACE_URL, "wbs_123:it_2")

    @pytest.mark.asyncio
    async def test_billing_quota_exceeded_stops_import(self) -> None:
        owner_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            yield {
                "id": "it_1",
                "status": "ready",
                "data": {"name": "Acme Corp", "phone": "0987111222"},
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

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=owner_id),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit",
                side_effect=InsufficientCreditsError(
                    required_micros=WEBSET_LEAD_IMPORT_COST_MICROS,
                    balance_micros=0,
                ),
            ),
        ):
            res = await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert res["status"] == "quota_exceeded"
        assert res["imported_count"] == 0
        assert mock_campaign.status == "quota_exceeded"
        mock_batch_svc.ingest_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_billing_dnc_blocked_releases_credit(self) -> None:
        owner_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            yield {
                "id": "it_1",
                "status": "ready",
                "data": {"name": "Acme Corp", "phone": "0987111222"},
            }
            yield {
                "id": "it_2",
                "status": "ready",
                "data": {"name": "Blocked Corp", "phone": "0987999888"},
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
        mock_session.add = MagicMock()
        mock_session.new = []

        def _mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)
            if "webset_campaigns" in stmt_str:
                res.scalar_one_or_none.return_value = mock_campaign
            elif "billing_events" in stmt_str:
                res.scalar_one_or_none.return_value = None
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_session.execute.side_effect = _mock_execute

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        # First lead accepted, second blocked by DNC
        mock_batch_svc.ingest_batch.return_value = {
            "ingested_count": 1,
            "accepted": [True, False],
        }

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=owner_id),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit", new=AsyncMock()
            ) as mock_reserve,
            patch(
                "app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()
            ) as mock_commit,
            patch(
                "app.services.wallet_credit.release_credit", new=AsyncMock()
            ) as mock_release,
        ):
            res = await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert res["status"] == "completed"
        assert res["imported_count"] == 1
        mock_reserve.assert_awaited_once_with(
            mock_session, owner_id, 2 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        mock_commit.assert_awaited_once_with(
            mock_session, owner_id, 1 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        mock_release.assert_awaited_once_with(
            mock_session, owner_id, 1 * WEBSET_LEAD_IMPORT_COST_MICROS
        )

    @pytest.mark.asyncio
    async def test_billing_idempotency_duplicate_event_releases_credit(self) -> None:
        owner_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            yield {
                "id": "it_1",
                "status": "ready",
                "data": {"name": "Acme Corp", "phone": "0987111222"},
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
        mock_session.add = MagicMock()
        mock_session.new = []

        existing_event = BillingEvent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            workspace_id=42,
            event_entity_type="webset",
            event_type="lead_import",
            event_id=uuid5(NAMESPACE_URL, "wbs_123:it_1"),
        )

        def _mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)
            if "webset_campaigns" in stmt_str:
                res.scalar_one_or_none.return_value = mock_campaign
            elif "billing_events" in stmt_str:
                res.scalars.return_value.all.return_value = [existing_event.event_id]
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_session.execute.side_effect = _mock_execute

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        mock_batch_svc.ingest_batch.return_value = {
            "ingested_count": 1,
            "accepted": [True],
        }

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=owner_id),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit", new=AsyncMock()
            ) as mock_reserve,
            patch(
                "app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()
            ) as mock_commit,
            patch(
                "app.services.wallet_credit.release_credit", new=AsyncMock()
            ) as mock_release,
        ):
            res = await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert res["status"] == "completed"
        mock_reserve.assert_awaited_once_with(
            mock_session, owner_id, 1 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        # Existing event -> released, not committed!
        mock_commit.assert_not_called()
        mock_release.assert_awaited_once_with(
            mock_session, owner_id, 1 * WEBSET_LEAD_IMPORT_COST_MICROS
        )

    @pytest.mark.asyncio
    async def test_billing_owner_none_fails_closed(self) -> None:
        """Workspace without resolvable owner -> fail closed, no billing calls.

        Regression cho AI-41.5: import không owner nghĩa là free leads — phải
        fail với status='failed' + stats.failure_reason='no_workspace_owner'
        thay vì silently skip billing rồi import tiếp.
        """
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            yield {
                "id": "it_1",
                "status": "ready",
                "data": {"name": "Acme Corp", "phone": "0987111222"},
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
        mock_session.add = MagicMock()
        mock_session.new = []

        def _mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)
            if "webset_campaigns" in stmt_str:
                res.scalar_one_or_none.return_value = mock_campaign
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_session.execute.side_effect = _mock_execute

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        mock_batch_svc.ingest_batch.return_value = {
            "ingested_count": 1,
            "accepted": [True],
        }

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit", new=AsyncMock()
            ) as mock_reserve,
            patch(
                "app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()
            ) as mock_commit,
            patch(
                "app.services.wallet_credit.release_credit", new=AsyncMock()
            ) as mock_release,
        ):
            res = await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert res["status"] == "failed"
        assert mock_campaign.status == "failed"
        assert mock_campaign.stats["failure_reason"] == "no_workspace_owner"
        mock_batch_svc.ingest_batch.assert_not_called()
        mock_reserve.assert_not_called()
        mock_commit.assert_not_called()
        mock_release.assert_not_called()

    @pytest.mark.asyncio
    async def test_billing_idless_identical_entities_dedup_via_content_key(
        self,
    ) -> None:
        """105 items không entity id -> content-key fallback dedup xuyên batch.

        Regression cho AI-41.3: fallback cũ `idx:{idx}` reset theo batch nên
        batch 2 item 0 trùng event_id với batch 1 item 0 (uuid5 collision →
        lần lượt bị coi là duplicate hoặc dedup sai). Content key giống nhau
        cho entity giống nhau → cùng event_id → chỉ debit đúng 1 lead.
        """
        owner_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_websets_svc = MagicMock(spec=WebsetsService)

        async def _mock_iter(webset_id: str, workspace_id: int):
            for _ in range(105):
                yield {
                    "status": "ready",
                    "data": {"name": "Acme Corp", "phone": "0987111222"},
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

        added_event_ids: list[Any] = []
        mock_session = AsyncMock()
        mock_session.new = []

        def _mock_add(obj):
            if isinstance(obj, BillingEvent):
                added_event_ids.append(obj.event_id)

        mock_session.add = MagicMock(side_effect=_mock_add)

        def _mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)
            if "webset_campaigns" in stmt_str:
                res.scalar_one_or_none.return_value = mock_campaign
            elif "billing_events" in stmt_str:
                # Mirror real dedup: batch 2's select sees batch 1's committed rows.
                res.scalars.return_value.all.return_value = list(added_event_ids)
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_session.execute.side_effect = _mock_execute

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        mock_batch_svc.ingest_batch.side_effect = [
            {"ingested_count": 100, "accepted": [True] * 100},
            {"ingested_count": 5, "accepted": [True] * 5},
        ]

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=owner_id),
            ),
            patch("app.services.wallet_credit.reserve_credit", new=AsyncMock()),
            patch(
                "app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()
            ) as mock_commit,
            patch(
                "app.services.wallet_credit.release_credit", new=AsyncMock()
            ) as mock_release,
        ):
            res = await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert res["status"] == "completed"
        expected_id = uuid5(
            NAMESPACE_URL, "wbs_123:lead:Acme Corp|None|0987111222|None"
        )
        assert added_event_ids == [expected_id]
        mock_commit.assert_awaited_once_with(
            mock_session, owner_id, WEBSET_LEAD_IMPORT_COST_MICROS
        )
        release_total = sum(call.args[2] for call in mock_release.await_args_list)
        assert release_total == 104 * WEBSET_LEAD_IMPORT_COST_MICROS

    @pytest.mark.asyncio
    async def test_billing_failure_rolls_back_then_releases(self) -> None:
        """ingest_batch raise sau khi reserve -> session.rollback() TRƯỚC release_credit.

        Regression cho AI-41.2: release trên aborted session (không rollback) ném
        InFailedSqlTransactionError -> nuốt trong inner except -> credit lock vĩnh viễn.
        """
        owner_id = UUID("11111111-1111-1111-1111-111111111111")
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

        call_order: list[str] = []
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.new = []
        mock_session.rollback.side_effect = lambda: call_order.append("rollback")

        def _mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)
            if "webset_campaigns" in stmt_str:
                res.scalar_one_or_none.return_value = mock_campaign
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_session.execute.side_effect = _mock_execute

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_batch_svc = AsyncMock()
        mock_batch_svc.ingest_batch.side_effect = RuntimeError("db exploded")

        import_service = WebsetsImportService(
            websets_service=mock_websets_svc,
            batch_service=mock_batch_svc,
        )

        with (
            patch(
                "app.services.websets_import._resolve_workspace_owner",
                new=AsyncMock(return_value=owner_id),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit", new=AsyncMock()
            ) as mock_reserve,
            patch(
                "app.services.wallet_credit.commit_reserved_credit", new=AsyncMock()
            ) as mock_commit,
            patch(
                "app.services.wallet_credit.release_credit",
                new=AsyncMock(side_effect=lambda *a, **k: call_order.append("release")),
            ) as mock_release,
            pytest.raises(RuntimeError, match="db exploded"),
        ):
            await import_service.import_webset(
                "wbs_123",
                session_factory=lambda: mock_session_cm,
            )

        assert mock_campaign.status == "failed"
        mock_reserve.assert_awaited_once_with(
            mock_session, owner_id, 2 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        mock_commit.assert_not_called()
        # Full reservation released, and rollback strictly precedes release.
        mock_release.assert_awaited_once_with(
            mock_session, owner_id, 2 * WEBSET_LEAD_IMPORT_COST_MICROS
        )
        assert call_order == ["rollback", "release"]
