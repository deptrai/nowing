"""Unit tests for CompliancePurgeService (Story 33.2)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.leads.enrichment import VerifiedContact
from app.models.leads.main import Lead
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
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        lead = MagicMock(spec=Lead)
        lead.workspace_id = 1
        session.get.return_value = lead

        with patch("app.services.compliance_purge_service.DncComplianceService") as mock_dnc:
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
        assert 1 in res["workspaces_affected"]
        session.delete.assert_any_call(contact)
        session.delete.assert_any_call(lead)
