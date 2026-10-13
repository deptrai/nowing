"""Unit tests for CompliancePurgeService (Story 33.2)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.leads.enrichment import VerifiedContact
from app.models.leads.main import Lead
from app.models.leads.social import SocialPost
from app.services.compliance_purge_service import (
    CompliancePurgeService,
    _normalize_value,
)

pytestmark = [pytest.mark.unit]


class TestNormalizeValue:
    """Test normalization and hashing."""

    def test_normalize_phone_valid(self):
        """Valid phone should return E.164 and HMAC."""
        norm, hmac_hash = _normalize_value("phone", "0908123456")
        assert norm == "+84908123456"
        assert len(hmac_hash) == 64

    def test_normalize_email_valid(self):
        """Valid email should return lowercase and HMAC."""
        norm, hmac_hash = _normalize_value("email", "USER@Example.COM")
        assert norm == "user@example.com"
        assert len(hmac_hash) == 64

    def test_normalize_invalid_type(self):
        """Invalid type should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported record type"):
            _normalize_value("invalid", "value")


class TestCompliancePurgeService:
    """Test cross-workspace purge functionality."""

    @pytest.mark.asyncio
    async def test_purge_phone_deletes_contacts_and_appends_dnc(self):
        """Purge should delete matching contacts, lead, and insert DNC record."""
        session = AsyncMock()

        lead_id = uuid.uuid4()
        contact = MagicMock(spec=VerifiedContact)
        contact.workspace_id = 1
        contact.lead_id = lead_id

        # Mock query results
        scalars_mock = MagicMock()
        scalars_mock.all.side_effect = [
            [contact],  # first query for VerifiedContact
            [],  # second query for remaining contacts
            [],  # third query for SocialPost
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        lead = MagicMock(spec=Lead)
        lead.workspace_id = 1
        session.get.return_value = lead

        with patch(
            "app.services.compliance_purge_service.DncComplianceService"
        ) as mock_dnc:
            dnc_instance = MagicMock()
            dnc_instance.invalidate_workspace_cache = AsyncMock()
            mock_dnc.return_value = dnc_instance

            res = await CompliancePurgeService.purge_individual(
                session,
                record_type="phone",
                value="0908123456",
            )

        assert res["status"] == "purged"
        assert res["purged_counts"]["verified_contacts"] == 1
        assert res["purged_counts"]["leads"] == 1
        assert res["purged_counts"]["social_posts"] == 0
        assert 1 in res["workspaces_affected"]
        session.get.assert_called_once_with(Lead, (lead_id, 1))
        session.delete.assert_any_call(contact)
        session.delete.assert_any_call(lead)

    @pytest.mark.asyncio
    async def test_purge_social_post_by_pii(self):
        """Purge should find and delete matching SocialPost containing PII."""
        session = AsyncMock()

        post = MagicMock(spec=SocialPost)
        post.workspace_id = 42
        post.raw_entities = {"phones": ["0908123456"]}

        scalars_mock = MagicMock()
        scalars_mock.all.side_effect = [
            [],  # VerifiedContact query
            [post],  # SocialPost query
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        with patch(
            "app.services.compliance_purge_service.DncComplianceService"
        ) as mock_dnc:
            dnc_instance = MagicMock()
            dnc_instance.invalidate_workspace_cache = AsyncMock()
            mock_dnc.return_value = dnc_instance

            res = await CompliancePurgeService.purge_individual(
                session,
                record_type="phone",
                value="0908123456",
            )

        assert res["status"] == "purged"
        assert res["purged_counts"]["verified_contacts"] == 0
        assert res["purged_counts"]["leads"] == 0
        assert res["purged_counts"]["social_posts"] == 1
        assert 42 in res["workspaces_affected"]
        session.delete.assert_called_once_with(post)

        # Assert executed statement filters by raw_entities, content, and author
        post_stmt = session.execute.call_args_list[1][0][0]
        stmt_sql = str(post_stmt)
        assert "social_posts.raw_entities" in stmt_sql
        assert "social_posts.content" in stmt_sql
        assert "social_posts.author_id" in stmt_sql
        assert "social_posts.author_name" in stmt_sql
        params = post_stmt.compile().params
        # Check that candidate value is JSON-quoted in raw_entities like filter
        assert any('"+84908123456"' in str(val) for val in params.values())

    @pytest.mark.asyncio
    async def test_purge_social_post_escapes_like_wildcards(self):
        """Purge should escape % and _ in LIKE patterns."""
        session = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.side_effect = [[], []]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        with patch(
            "app.services.compliance_purge_service.DncComplianceService"
        ) as mock_dnc:
            dnc_instance = MagicMock()
            dnc_instance.invalidate_workspace_cache = AsyncMock()
            mock_dnc.return_value = dnc_instance

            await CompliancePurgeService.purge_individual(
                session,
                record_type="email",
                value="test_%user@example.com",
            )

        post_stmt = session.execute.call_args_list[1][0][0]
        params = post_stmt.compile().params
        assert any(r"test\_\%user@example.com" in str(val) for val in params.values())

    @pytest.mark.asyncio
    async def test_purge_contact_with_none_workspace_id_does_not_fail_sorting(self):
        """Matched VerifiedContact with workspace_id=None should not pollute affected_workspaces."""
        session = AsyncMock()

        contact_null_ws = MagicMock(spec=VerifiedContact)
        contact_null_ws.workspace_id = None
        contact_null_ws.lead_id = None

        contact_valid_ws = MagicMock(spec=VerifiedContact)
        contact_valid_ws.workspace_id = 7
        contact_valid_ws.lead_id = None

        scalars_mock = MagicMock()
        scalars_mock.all.side_effect = [
            [contact_null_ws, contact_valid_ws],  # VerifiedContact query
            [],  # SocialPost query
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        with patch(
            "app.services.compliance_purge_service.DncComplianceService"
        ) as mock_dnc:
            dnc_instance = MagicMock()
            dnc_instance.invalidate_workspace_cache = AsyncMock()
            mock_dnc.return_value = dnc_instance

            res = await CompliancePurgeService.purge_individual(
                session,
                record_type="phone",
                value="0908123456",
            )

        assert res["status"] == "purged"
        assert res["purged_counts"]["verified_contacts"] == 2
        assert res["workspaces_affected"] == [7]
        assert len(res["refund_candidates"]) == 1
        assert res["refund_candidates"][0]["verified_contact_id"] == contact_valid_ws.id
        assert res["refund_candidates"][0]["workspace_id"] == 7
        dnc_instance.invalidate_workspace_cache.assert_awaited_once_with(7)


class TestProcessPostPurgeRefunds:
    """Unit tests for Phase 2 post-purge credit refunds and notifications (Story 33.4)."""

    @pytest.mark.asyncio
    async def test_successful_refund_within_30_day_window(self):
        """Contact unlocked within 30 days receives refund and owner notification."""
        session = AsyncMock()
        contact_id = uuid.uuid4()
        workspace_id = 1
        owner_id = uuid.uuid4()

        unlock_event = MagicMock()
        unlock_event.cost_micros = 3000
        unlock_event.user_id = owner_id

        refund_event = MagicMock()
        refund_event.cost_micros = -3000

        # Workspace owner lookup for notification (session.get(Workspace, ws_id))
        session.get.return_value = MagicMock(user_id=owner_id)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            # _list_billing_events returns [] for existing refund, [unlock_event] for original unlock
            mock_list_events.side_effect = [
                [],  # contact_unlock_refund
                [unlock_event],  # contact_unlock
            ]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                return_value=refund_event
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {
                        "verified_contact_id": contact_id,
                        "workspace_id": workspace_id,
                    }
                ],
                actor_user_id=owner_id,
            )

            assert summary["refunded_contacts"] == 1
            assert summary["refunded_micros"] == 3000
            assert summary["skipped"] == []

            billing_svc.record_contact_unlock_refund_24h.assert_awaited_once_with(
                session,
                verified_contact_id=contact_id,
                workspace_id=workspace_id,
                user_id=owner_id,
                cost_micros=3000,
                refund_window_hours=720,
            )

            mock_create_notif.assert_awaited_once()
            notif_kwargs = mock_create_notif.await_args.kwargs
            assert notif_kwargs["user_id"] == owner_id
            assert notif_kwargs["workspace_id"] == workspace_id
            assert notif_kwargs["notification_type"] == "compliance_purge_refund"
            assert notif_kwargs["notification_metadata"]["purged_contacts"] == 1
            assert notif_kwargs["notification_metadata"]["refunded_micros"] == 3000
            assert notif_kwargs["notification_metadata"]["has_expired_refunds"] is False
            assert "090" not in notif_kwargs["message"]

    @pytest.mark.asyncio
    async def test_refund_window_expired_skips_and_notifies(self):
        """Contact unlocked > 30 days ago is skipped with window_expired and owner notified."""
        from app.services.billing_event_service import RefundWindowExpiredError

        session = AsyncMock()
        contact_id = uuid.uuid4()
        workspace_id = 1
        owner_id = uuid.uuid4()

        unlock_event = MagicMock()
        unlock_event.cost_micros = 1500
        unlock_event.user_id = owner_id

        session.get.return_value = MagicMock(user_id=owner_id)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [
                [],  # contact_unlock_refund
                [unlock_event],  # contact_unlock
            ]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                side_effect=RefundWindowExpiredError("window expired")
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {
                        "verified_contact_id": contact_id,
                        "workspace_id": workspace_id,
                    }
                ],
            )

            assert summary["refunded_contacts"] == 0
            assert summary["refunded_micros"] == 0
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "window_expired"
            assert summary["skipped"][0]["verified_contact_id"] == str(contact_id)

            session.rollback.assert_awaited()  # releases pg_advisory_xact_lock on domain skip
            mock_create_notif.assert_awaited_once()
            notif_kwargs = mock_create_notif.await_args.kwargs
            assert notif_kwargs["notification_metadata"]["has_expired_refunds"] is True
            assert notif_kwargs["notification_metadata"]["refunded_credits"] == 0

    @pytest.mark.asyncio
    async def test_no_unlock_charge_skips_without_notification(self):
        """Contact never unlocked is skipped with no_unlock_charge and no notification."""
        session = AsyncMock()
        contact_id = uuid.uuid4()
        workspace_id = 1

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [
                [],  # contact_unlock_refund
                [],  # contact_unlock (no unlock event)
            ]

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {
                        "verified_contact_id": contact_id,
                        "workspace_id": workspace_id,
                    }
                ],
            )

            assert summary["refunded_contacts"] == 0
            assert summary["refunded_micros"] == 0
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "no_unlock_charge"
            mock_create_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_refunded_skips(self):
        """Already refunded contact is skipped with already_refunded."""
        session = AsyncMock()
        contact_id = uuid.uuid4()
        workspace_id = 1

        existing_refund = MagicMock()

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [
                [existing_refund],  # contact_unlock_refund already exists
            ]

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {
                        "verified_contact_id": contact_id,
                        "workspace_id": workspace_id,
                    }
                ],
            )

            assert summary["refunded_contacts"] == 0
            assert summary["refunded_micros"] == 0
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "already_refunded"
            mock_billing_cls.return_value.record_contact_unlock_refund_24h.assert_not_called()
            mock_create_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_exhausted_skips_with_structured_log(self, caplog):
        """Workspace exceeding refund budget cap logs warning and skips."""
        from app.services.billing_event_service import RefundBudgetExhaustedError

        session = AsyncMock()
        contact_id = uuid.uuid4()
        workspace_id = 1
        owner_id = uuid.uuid4()

        unlock_event = MagicMock()
        unlock_event.cost_micros = 1500
        unlock_event.user_id = owner_id

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [
                [],  # contact_unlock_refund
                [unlock_event],  # contact_unlock
            ]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                side_effect=RefundBudgetExhaustedError("cap exhausted")
            )
            mock_billing_cls.return_value = billing_svc

            import logging

            with caplog.at_level(logging.WARNING):
                summary = await CompliancePurgeService.process_post_purge_refunds(
                    session,
                    refund_candidates=[
                        {
                            "verified_contact_id": contact_id,
                            "workspace_id": workspace_id,
                        }
                    ],
                )

            assert summary["refunded_contacts"] == 0
            assert summary["refunded_micros"] == 0
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "budget_exhausted"
            assert any(
                "Refund budget exhausted" in record.message for record in caplog.records
            )
            mock_create_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_workspaces_send_isolated_notifications(self):
        """Multi-workspace purge sends separate notifications with per-workspace totals."""
        session = AsyncMock()
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        owner1, owner2 = uuid.uuid4(), uuid.uuid4()

        u1 = MagicMock(cost_micros=1500, user_id=owner1)
        u2 = MagicMock(cost_micros=3000, user_id=owner2)

        r1 = MagicMock(cost_micros=-1500)
        r2 = MagicMock(cost_micros=-3000)

        # Workspace owner lookups for ws 10 and ws 20 via session.get(Workspace)
        session.get.side_effect = [
            MagicMock(user_id=owner1),
            MagicMock(user_id=owner2),
        ]

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [
                [],  # c1 refund
                [u1],  # c1 unlock
                [],  # c2 refund
                [u2],  # c2 unlock
            ]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                side_effect=[r1, r2]
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {"verified_contact_id": c1, "workspace_id": 10},
                    {"verified_contact_id": c2, "workspace_id": 20},
                ],
            )

            assert summary["refunded_contacts"] == 2
            assert summary["refunded_micros"] == 4500
            assert mock_create_notif.await_count == 2

    @pytest.mark.asyncio
    async def test_uses_newest_unlock_event_for_refund_cost(self):
        """Multiple unlock events: refund uses the newest unlock's cost_micros."""
        session = AsyncMock()
        contact_id = uuid.uuid4()
        workspace_id = 1
        owner_id = uuid.uuid4()

        newest_unlock = MagicMock(cost_micros=3000, user_id=owner_id)
        older_unlock = MagicMock(cost_micros=1500, user_id=owner_id)
        refund_event = MagicMock(cost_micros=-3000)
        session.get.return_value = MagicMock(user_id=owner_id)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_list_events.side_effect = [[], [newest_unlock, older_unlock]]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                return_value=refund_event
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {
                        "verified_contact_id": contact_id,
                        "workspace_id": workspace_id,
                    }
                ],
            )

            assert summary["refunded_contacts"] == 1
            billing_svc.record_contact_unlock_refund_24h.assert_awaited_once_with(
                session,
                verified_contact_id=contact_id,
                workspace_id=workspace_id,
                user_id=owner_id,
                cost_micros=3000,
                refund_window_hours=720,
            )

    @pytest.mark.asyncio
    async def test_exception_isolation_rolls_back_and_continues(self):
        """Unexpected error on one contact rolls back and does not abort the rest."""
        session = AsyncMock()
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        owner_id = uuid.uuid4()

        u1 = MagicMock(cost_micros=1500, user_id=owner_id)
        u2 = MagicMock(cost_micros=3000, user_id=owner_id)
        r2 = MagicMock(cost_micros=-3000)
        session.get.return_value = MagicMock(user_id=owner_id)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_list_events.side_effect = [[], [u1], [], [u2]]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                side_effect=[RuntimeError("db down"), r2]
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {"verified_contact_id": c1, "workspace_id": 1},
                    {"verified_contact_id": c2, "workspace_id": 1},
                ],
            )

            assert summary["refunded_contacts"] == 1
            assert summary["refunded_micros"] == 3000
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "internal_error"
            assert summary["skipped"][0]["verified_contact_id"] == str(c1)
            session.rollback.assert_awaited()
            statuses = {d["status"] for d in summary["details"]}
            assert statuses == {"refunded", "skipped"}

    @pytest.mark.asyncio
    async def test_workspace_owner_fallback_when_unlock_user_missing(self):
        """Null BillingEvent.user_id falls back to workspace owner, not the actor."""
        session = AsyncMock()
        contact_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        actor_id = uuid.uuid4()

        unlock_event = MagicMock(cost_micros=1500, user_id=None)
        refund_event = MagicMock(cost_micros=-1500)
        session.get.return_value = MagicMock(user_id=owner_id)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [[], [unlock_event]]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                return_value=refund_event
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {"verified_contact_id": contact_id, "workspace_id": 1}
                ],
                actor_user_id=actor_id,
            )

            assert summary["refunded_contacts"] == 1
            billing_svc.record_contact_unlock_refund_24h.assert_awaited_once_with(
                session,
                verified_contact_id=contact_id,
                workspace_id=1,
                user_id=owner_id,
                cost_micros=1500,
                refund_window_hours=720,
            )
            notif_kwargs = mock_create_notif.await_args.kwargs
            assert notif_kwargs["user_id"] == owner_id

    @pytest.mark.asyncio
    async def test_missing_recipient_skips_with_missing_user_id(self):
        """No unlock user and no workspace owner -> skip missing_user_id, never actor."""
        session = AsyncMock()
        contact_id = uuid.uuid4()

        unlock_event = MagicMock(cost_micros=1500, user_id=None)
        session.get.return_value = MagicMock(user_id=None)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [[], [unlock_event]]

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {"verified_contact_id": contact_id, "workspace_id": 1}
                ],
                actor_user_id=uuid.uuid4(),  # superadmin actor must NOT be credited
            )

            assert summary["refunded_contacts"] == 0
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "missing_user_id"
            mock_billing_cls.return_value.record_contact_unlock_refund_24h.assert_not_called()
            mock_create_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_never_unlocked_candidate_skips_early(self):
        """Candidate with was_unlocked=False skips billing queries entirely."""
        session = AsyncMock()
        contact_id = uuid.uuid4()

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {
                        "verified_contact_id": contact_id,
                        "workspace_id": 1,
                        "was_unlocked": False,
                    }
                ],
            )

            assert summary["refunded_contacts"] == 0
            assert summary["skipped"] == []
            assert summary["details"] == []
            mock_list_events.assert_not_called()
            mock_create_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_billing_query_failure_isolated_per_candidate(self):
        """DB error on a candidate's billing query skips that candidate only."""
        session = AsyncMock()
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        owner_id = uuid.uuid4()

        u2 = MagicMock(cost_micros=2000, user_id=owner_id)
        r2 = MagicMock(cost_micros=-2000)
        session.get.return_value = MagicMock(user_id=owner_id)

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [
                RuntimeError("conn reset"),  # c1 refund-check query fails
                [],  # c2 refund-check
                [u2],  # c2 unlock
            ]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(return_value=r2)
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {"verified_contact_id": c1, "workspace_id": 1},
                    {"verified_contact_id": c2, "workspace_id": 1},
                ],
            )

            # c1 isolated as internal_error; c2 refunded normally
            assert summary["refunded_contacts"] == 1
            assert summary["refunded_micros"] == 2000
            assert len(summary["skipped"]) == 1
            assert summary["skipped"][0]["reason"] == "internal_error"
            assert summary["skipped"][0]["verified_contact_id"] == str(c1)
            session.rollback.assert_awaited()
            mock_create_notif.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notification_owner_lookup_failure_preserves_summary(self):
        """Owner lookup crash in notification loop must not wipe refund summary."""
        session = AsyncMock()
        contact_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        unlock_event = MagicMock(cost_micros=1500, user_id=owner_id)
        refund_event = MagicMock(cost_micros=-1500)
        # session.get(Workspace) crashes during notification owner resolution
        session.get.side_effect = RuntimeError("db gone")

        with (
            patch(
                "app.services.compliance_purge_service._list_billing_events"
            ) as mock_list_events,
            patch(
                "app.services.compliance_purge_service.BillingEventService"
            ) as mock_billing_cls,
            patch(
                "app.services.compliance_purge_service.NotificationService.create_notification",
                new_callable=AsyncMock,
            ) as mock_create_notif,
        ):
            mock_list_events.side_effect = [[], [unlock_event]]

            billing_svc = MagicMock()
            billing_svc.record_contact_unlock_refund_24h = AsyncMock(
                return_value=refund_event
            )
            mock_billing_cls.return_value = billing_svc

            summary = await CompliancePurgeService.process_post_purge_refunds(
                session,
                refund_candidates=[
                    {"verified_contact_id": contact_id, "workspace_id": 1}
                ],
            )

            # Refund result survives notification failure — no exception escapes
            assert summary["refunded_contacts"] == 1
            assert summary["refunded_micros"] == 1500
            assert summary["skipped"] == []
            mock_create_notif.assert_not_called()
            session.rollback.assert_awaited()
