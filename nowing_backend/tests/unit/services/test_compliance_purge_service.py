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
