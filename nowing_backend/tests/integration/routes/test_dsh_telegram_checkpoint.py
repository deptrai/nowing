"""Red-phase ATDD integration tests for DSH Telegram Checkpoint flow (Story 26.6).

Tests the end-to-end notify endpoint and Telegram callback query execution against real Postgres:
- Worker calls POST /v1/dsh/missions/{mission_id}/notify-high-fit with worker secret and PAT.
- High-fit lead checkpoint card generation and TelegramCheckpointMessage DB persistence.
- Inline callback query handling (unlock, dossier, skip) with live Postgres transactions,
  wallet debits, PII decryption, audit logs, and Telegram message edits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config import config
from app.db import (
    BillingEvent,
    DshMission,
    ExternalChatAccount,
    ExternalChatBinding,
    Lead,
    TelegramCheckpointMessage,
    User,
    VerifiedContact,
    WorkspaceMembership,
)
from app.gateway.base.adapter import ParsedInboundEvent, PlatformSendResult
from app.gateway.telegram.callbacks import handle_callback_query
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_phone_e164,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


@pytest.fixture(autouse=True)
def _patch_telegram_account_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid Fernet decrypt of dummy credentials in integration tests."""
    for target in (
        "app.gateway.accounts.account_token",
        "app.services.dsh_telegram_checkpoint_service.account_token",
    ):
        monkeypatch.setattr(
            target,
            lambda _account: "test-telegram-token",
        )


def _encrypt(value: str) -> str:
    return VerifiedContactEncryption().encrypt(value)


def _phone_hash(phone: str) -> str:
    e164 = normalize_phone_e164(phone)
    assert e164
    return hash_phone_hmac(e164)


async def _setup_telegram_binding(
    db_session, db_workspace, db_user: User, external_peer_id: str = "12345678"
) -> tuple[ExternalChatAccount, ExternalChatBinding]:
    account = ExternalChatAccount(
        owner_workspace_id=db_workspace.id,
        owner_user_id=db_user.id,
        platform="telegram",
        mode="cloud_shared",
        bot_username="bot_nowing",
        encrypted_credentials="enc_credentials",
        health_status="ok",
    )
    db_session.add(account)
    await db_session.flush()

    binding = ExternalChatBinding(
        workspace_id=db_workspace.id,
        account_id=account.id,
        user_id=db_user.id,
        external_peer_id=external_peer_id,
        external_peer_kind="direct",
        state="bound",
    )
    db_session.add(binding)
    await db_session.flush()
    return account, binding


async def _create_mission_and_lead(
    db_session,
    db_workspace,
    db_user: User,
    *,
    fit_score: int = 88,
    phone: str = "+84908123456",
) -> tuple[DshMission, Lead, VerifiedContact]:
    mission = DshMission(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        status="running",
        phase="ingestion",
        progress_percent=90,
        payload={"query": "Real estate leads"},
        checkpoint={"phase": "ingestion", "version": 1},
    )
    db_session.add(mission)
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Công ty BĐS Hoàng Gia",
        domain="hoanggia.vn",
        fit_score=fit_score,
        intent_score=92,
        value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
        source="batdongsan",
        source_url="https://batdongsan.vn/item-888",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Nguyễn Hoàng"),
        title=_encrypt("Giám đốc kinh doanh"),
        phone=_encrypt(phone),
        email=_encrypt("hoang@hoanggia.vn"),
        phone_hmac=_phone_hash(phone),
        value_hmac=f"contact-hmac-{uuid4().hex[:8]}",
        is_unlocked=False,
        is_valid=True,
        consent_status="opted_in",
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()
    return mission, lead, contact


def _make_mock_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.send_message = AsyncMock(return_value=PlatformSendResult(external_message_id="999"))
    adapter.edit_message = AsyncMock()
    adapter.answer_callback_query = AsyncMock()
    return adapter


# ============================================================================
# 1. Internal Worker Notify Endpoint Tests (POST /v1/dsh/missions/.../notify-high-fit)
# ============================================================================


@pytest.mark.asyncio
async def test_notify_high_fit_persists_checkpoint_message_and_sends_telegram_card(
    pat_client, db_user, db_workspace, db_session, monkeypatch
):
    """P0: Worker calls notify-high-fit -> creates TelegramCheckpointMessage in DB & sends card."""
    monkeypatch.setattr(
        config, "DSH_WORKER_SECRET", "test-dsh-worker-secret", raising=False
    )
    await _setup_telegram_binding(db_session, db_workspace, db_user)
    mission, lead, contact = await _create_mission_and_lead(
        db_session, db_workspace, db_user, fit_score=90
    )

    # Mock Telegram adapter send_message
    mock_send = AsyncMock(return_value=PlatformSendResult(external_message_id="777"))
    monkeypatch.setattr(
        "app.gateway.telegram.adapter.TelegramAdapter.send_message", mock_send
    )

    headers = {
        "X-Dsh-Worker-Secret": "test-dsh-worker-secret",
    }
    payload = {
        "lead_id": str(lead.id),
    }

    resp = await pat_client.post(
        f"/v1/dsh/missions/{mission.id}/notify-high-fit",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert data["callback_token"]
    assert data["contact_id"] == str(contact.id)

    # Assert row in real Postgres
    checkpoint_msg = (
        await db_session.execute(
            select(TelegramCheckpointMessage).where(
                TelegramCheckpointMessage.mission_id == mission.id,
                TelegramCheckpointMessage.lead_id == lead.id,
            )
        )
    ).scalar_one_or_none()
    assert checkpoint_msg is not None
    assert checkpoint_msg.status == "sent"
    assert checkpoint_msg.workspace_id == db_workspace.id
    assert checkpoint_msg.user_id == db_user.id
    assert checkpoint_msg.callback_token == data["callback_token"]
    assert checkpoint_msg.external_peer_id == "12345678"

    # Assert card content and inline keyboard
    mock_send.assert_awaited_once()
    send_kwargs = mock_send.call_args.kwargs
    card_text = send_kwargs["text"]
    assert "Công ty BĐS Hoàng Gia" in card_text
    assert "0908***456" in card_text or "0908" in card_text
    assert "+84908123456" not in card_text  # Plaintext masked
    reply_markup = send_kwargs.get("reply_markup", {})
    assert "inline_keyboard" in reply_markup
    buttons = reply_markup["inline_keyboard"][0]
    assert any("dsh:unlock:" in b["callback_data"] for b in buttons)


@pytest.mark.asyncio
async def test_notify_high_fit_requires_worker_secret(
    pat_client, db_user, db_workspace, db_session, monkeypatch
):
    """P0: Missing or invalid X-Dsh-Worker-Secret returns 403."""
    monkeypatch.setattr(config, "DSH_WORKER_SECRET", "correct-secret", raising=False)
    mission, lead, _ = await _create_mission_and_lead(db_session, db_workspace, db_user)

    resp = await pat_client.post(
        f"/v1/dsh/missions/{mission.id}/notify-high-fit",
        json={"lead_id": str(lead.id)},
        headers={"X-Dsh-Worker-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notify_high_fit_skips_when_user_disabled_preference(
    pat_client, db_user, db_workspace, db_session, monkeypatch
):
    """P1: When user explicitly sets dsh_high_fit_lead.telegram=False, skips silently."""
    monkeypatch.setattr(
        config, "DSH_WORKER_SECRET", "test-dsh-worker-secret", raising=False
    )
    await _setup_telegram_binding(db_session, db_workspace, db_user)
    mission, lead, _ = await _create_mission_and_lead(db_session, db_workspace, db_user)

    # Disable notification preference
    db_user.notification_preferences = {"dsh_high_fit_lead": {"telegram": False}}
    await db_session.flush()

    mock_send = AsyncMock()
    monkeypatch.setattr(
        "app.gateway.telegram.adapter.TelegramAdapter.send_message", mock_send
    )

    resp = await pat_client.post(
        f"/v1/dsh/missions/{mission.id}/notify-high-fit",
        json={"lead_id": str(lead.id)},
        headers={"X-Dsh-Worker-Secret": "test-dsh-worker-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("skipped", "disabled")
    mock_send.assert_not_awaited()


# ============================================================================
# 2. Telegram Callback Query Execution Tests with Real DB
# ============================================================================


@pytest.mark.asyncio
async def test_telegram_callback_unlock_flow_real_postgres(
    db_session, db_user, db_workspace
):
    """P0: dsh:unlock:{token} callback debits wallet, decrypts PII, writes BillingEvent and audit."""
    _, binding = await _setup_telegram_binding(db_session, db_workspace, db_user)
    mission, lead, contact = await _create_mission_and_lead(
        db_session, db_workspace, db_user
    )

    # Setup initial wallet balance
    db_user.credit_micros_balance = 50_000
    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    initial_spent = membership.monthly_spent_micros

    # Create checkpoint message
    token = f"tok_unlock_{uuid4().hex[:8]}"
    checkpoint = TelegramCheckpointMessage(
        workspace_id=db_workspace.id,
        mission_id=mission.id,
        lead_id=lead.id,
        contact_id=contact.id,
        user_id=db_user.id,
        callback_token=token,
        status="sent",
        external_peer_id=binding.external_peer_id,
        external_message_id="888",
    )
    db_session.add(checkpoint)
    await db_session.flush()

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="888",
        external_user_id=binding.external_peer_id,
        text=f"dsh:unlock:{token}",
        metadata={"callback_query_id": "cqid_123"},
        raw_payload={},
    )

    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    # Assert contact is unlocked in Postgres
    refreshed_contact = await db_session.get(VerifiedContact, contact.id)
    assert refreshed_contact.is_unlocked is True
    assert any(
        log.get("access_type") == "unlock"
        for log in refreshed_contact.pii_access_audit_logs
    )

    # Assert wallet debited by 1500 micros
    refreshed_user = await db_session.get(User, db_user.id)
    assert refreshed_user.credit_micros_balance == 50_000 - 1500

    # Assert workspace spend updated
    refreshed_membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    assert refreshed_membership.monthly_spent_micros == initial_spent + 1500

    # Assert BillingEvent row in Postgres
    billing_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_id == contact.id,
                BillingEvent.event_type == "contact_unlock",
            )
        )
    ).scalar_one()
    assert billing_event.cost_micros == 1500

    # Assert Telegram checkpoint status updated
    refreshed_msg = await db_session.get(TelegramCheckpointMessage, checkpoint.id)
    assert refreshed_msg.status == "unlocked"
    assert refreshed_msg.unlocked_at is not None

    # Assert Telegram adapter edit_message was called with unmasked phone
    adapter.edit_message.assert_awaited_once()
    edit_text = adapter.edit_message.call_args.kwargs["text"]
    assert "+84908123456" in edit_text or "0908123456" in edit_text


@pytest.mark.asyncio
async def test_telegram_callback_unlock_insufficient_credits_402_real_postgres(
    db_session, db_user, db_workspace
):
    """P0: Low wallet balance rejects unlock, does not debit, leaves contact locked."""
    _, binding = await _setup_telegram_binding(db_session, db_workspace, db_user)
    mission, lead, contact = await _create_mission_and_lead(
        db_session, db_workspace, db_user
    )

    db_user.credit_micros_balance = 500  # Less than 1500
    await db_session.flush()

    token = f"tok_low_bal_{uuid4().hex[:8]}"
    checkpoint = TelegramCheckpointMessage(
        workspace_id=db_workspace.id,
        mission_id=mission.id,
        lead_id=lead.id,
        contact_id=contact.id,
        user_id=db_user.id,
        callback_token=token,
        status="sent",
        external_peer_id=binding.external_peer_id,
        external_message_id="888",
    )
    db_session.add(checkpoint)
    await db_session.flush()

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="888",
        external_user_id=binding.external_peer_id,
        text=f"dsh:unlock:{token}",
        metadata={"callback_query_id": "cqid_402"},
        raw_payload={},
    )

    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    refreshed_contact = await db_session.get(VerifiedContact, contact.id)
    assert refreshed_contact.is_unlocked is False

    refreshed_user = await db_session.get(User, db_user.id)
    assert refreshed_user.credit_micros_balance == 500  # Not debited

    # Message edited with top-up notice and NO decrypted PII
    adapter.edit_message.assert_awaited_once()
    edit_text = adapter.edit_message.call_args.kwargs["text"]
    assert "Không đủ credits" in edit_text
    assert "+84908123456" not in edit_text


@pytest.mark.asyncio
async def test_telegram_callback_dossier_and_skip_real_postgres(
    db_session, db_user, db_workspace
):
    """P1: Dossier expands info; Skip updates status to dismissed."""
    _, binding = await _setup_telegram_binding(db_session, db_workspace, db_user)
    mission, lead, contact = await _create_mission_and_lead(
        db_session, db_workspace, db_user
    )

    token = f"tok_doss_{uuid4().hex[:8]}"
    checkpoint = TelegramCheckpointMessage(
        workspace_id=db_workspace.id,
        mission_id=mission.id,
        lead_id=lead.id,
        contact_id=contact.id,
        user_id=db_user.id,
        callback_token=token,
        status="sent",
        external_peer_id=binding.external_peer_id,
        external_message_id="888",
    )
    db_session.add(checkpoint)
    await db_session.flush()

    adapter = _make_mock_adapter()

    # 1. Dossier callback
    dossier_event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="888",
        external_user_id=binding.external_peer_id,
        text=f"dsh:dossier:{token}",
        metadata={"callback_query_id": "cqid_doss"},
        raw_payload={},
    )
    await handle_callback_query(
        session=db_session, adapter=adapter, event=dossier_event, binding=binding
    )
    adapter.edit_message.assert_awaited_once()
    assert "Công ty BĐS Hoàng Gia" in adapter.edit_message.call_args.kwargs["text"]

    # 2. Skip callback
    skip_event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="888",
        external_user_id=binding.external_peer_id,
        text=f"dsh:skip:{token}",
        metadata={"callback_query_id": "cqid_skip"},
        raw_payload={},
    )
    await handle_callback_query(
        session=db_session, adapter=adapter, event=skip_event, binding=binding
    )

    refreshed_msg = await db_session.get(TelegramCheckpointMessage, checkpoint.id)
    assert refreshed_msg.status == "dismissed"
