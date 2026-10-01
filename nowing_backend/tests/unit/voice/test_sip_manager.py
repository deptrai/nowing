"""Unit tests for SipTrunkManager (Story 38.6 / Multi-tenant BYO-SIP)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.voice_sip import SipTrunkCreateRequest, SipTrunkUpdateRequest
from app.services.voice.sip_manager import (
    SipCredentialDecryptionError,
    SipTrunkManager,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def manager():
    return SipTrunkManager(secret_key="unit_test_secret_key_38_6_32bytes!!")


class TestCryptoAndMasking:
    """AES-256-GCM encryption/decryption of SIP passwords."""

    def test_encrypt_decrypt_roundtrip(self, manager: SipTrunkManager):
        plaintext = "P@ssw0rd_Viettel_2026!#"
        ciphertext = manager.encrypt_password(plaintext)
        assert ciphertext != plaintext
        assert manager.decrypt_password(ciphertext) == plaintext

    def test_decrypt_corrupted_ciphertext_raises_error(self, manager: SipTrunkManager):
        with pytest.raises(SipCredentialDecryptionError):
            manager.decrypt_password("not_valid_ciphertext_or_wrong_key")

    def test_different_keys_fail_to_decrypt(self):
        m1 = SipTrunkManager(secret_key="key_one_32_bytes_long_secret_1!")
        m2 = SipTrunkManager(secret_key="key_two_32_bytes_long_secret_2!")
        cipher = m1.encrypt_password("secret")
        with pytest.raises(SipCredentialDecryptionError):
            m2.decrypt_password(cipher)


class TestSipTrunkCRUD:
    """CRUD operations with workspace tenant isolation."""

    async def test_create_trunk_encrypts_password(self, manager: SipTrunkManager):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()

        req = SipTrunkCreateRequest(
            name="Viettel Outbound Trunk",
            brandname="NOWING",
            outbound_did="+842871099999",
            sip_server="sip.viettel.vn:5060",
            sip_username="nowing_corp",
            sip_password="plaintext_password_never_stored",
            is_default=True,
        )

        trunk = await manager.create_trunk(session, workspace_id=15, req=req)

        assert trunk.workspace_id == 15
        assert trunk.name == "Viettel Outbound Trunk"
        assert trunk.outbound_did == "+842871099999"
        assert trunk.sip_password_encrypted != "plaintext_password_never_stored"
        # Decrypts back to original
        assert (
            manager.decrypt_password(trunk.sip_password_encrypted)
            == "plaintext_password_never_stored"
        )
        assert trunk.is_default is True
        session.add.assert_called_once_with(trunk)
        session.flush.assert_called_once()

    async def test_update_trunk_re_encrypts_new_password(self, manager: SipTrunkManager):
        session = AsyncMock()
        existing_trunk = MagicMock()
        existing_trunk.sip_password_encrypted = manager.encrypt_password("old_pass")

        # Mock get_trunk
        res = MagicMock()
        res.scalar_one_or_none.return_value = existing_trunk
        session.execute.return_value = res

        trunk_id = uuid4()
        req = SipTrunkUpdateRequest(sip_password="brand_new_secure_password")
        await manager.update_trunk(session, 15, trunk_id, req)

        assert (
            manager.decrypt_password(existing_trunk.sip_password_encrypted)
            == "brand_new_secure_password"
        )

    async def test_delete_trunk_removes_from_session(self, manager: SipTrunkManager):
        session = AsyncMock()
        existing_trunk = MagicMock()
        res = MagicMock()
        res.scalar_one_or_none.return_value = existing_trunk
        session.execute.return_value = res
        session.delete = AsyncMock()

        trunk_id = uuid4()
        deleted = await manager.delete_trunk(session, 15, trunk_id)
        assert deleted is True
        session.delete.assert_called_once_with(existing_trunk)


class TestResolutionCascade:
    """Dynamic resolution cascades: default trunk -> first trunk -> system fallback."""

    async def test_resolves_workspace_default_trunk(self, manager: SipTrunkManager):
        session = AsyncMock()
        mock_trunk = MagicMock()
        mock_trunk.livekit_trunk_id = "lk_trunk_viettel_1"
        mock_trunk.name = "Primary Trunk"
        mock_trunk.brandname = "NOWING"
        mock_trunk.outbound_did = "+842871099999"
        mock_trunk.sip_server = "sip.viettel.vn:5060"
        mock_trunk.sip_username = "user1"
        mock_trunk.sip_password_encrypted = manager.encrypt_password("real_pass")
        mock_trunk.is_default = True
        mock_trunk.is_verified = True

        res = MagicMock()
        res.scalars.return_value.first.return_value = mock_trunk
        session.execute.return_value = res

        resolved = await manager.resolve_workspace_trunk(session, workspace_id=15)

        assert resolved.trunk_id == "lk_trunk_viettel_1"
        assert resolved.brandname == "NOWING"
        assert resolved.sip_password == "real_pass"
        assert resolved.is_verified is True

    async def test_fallback_to_system_default_when_no_trunks(self, manager: SipTrunkManager):
        session = AsyncMock()
        res = MagicMock()
        res.scalars.return_value.first.return_value = None
        session.execute.return_value = res

        resolved = await manager.resolve_workspace_trunk(session, workspace_id=99)

        assert resolved.name == "System Default Trunk"
        assert resolved.workspace_id == 99
        assert resolved.is_verified is False
