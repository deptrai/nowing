"""Red-phase ATDD integration tests for Telegram 1-Click Auto-Refund Dialog (Story 26.6).

Tests the refund callback with real Postgres, live BillingEvent ledger,
24h SLA window, 15% budget cap, verification, and idempotency:
- Dispatch dsh:refund:{token} callback.
- Verified invalid number writes negative BillingEvent (-1500 micros), credits wallet,
  reverses member spend, and updates VerifiedContact.is_valid=False.
- Verification returning active number rejects refund.
- Expired 24h window or exhausted 15% cap rejects refund cleanly without exceptions.
- Idempotent second refund does not double-credit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import (
    BillingEvent,
    DshMission,
    ExternalChatAccount,
    ExternalChatBinding,
    Lead,
    PhoneWaterfallLog,
    TelegramCheckpointMessage,
    User,
    VerifiedContact,
    WorkspaceMembership,
)
from app.gateway.base.adapter import ParsedInboundEvent
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


async def _setup_unlocked_telegram_checkpoint(
    db_session,
    db_workspace,
    db_user: User,
    *,
    unlocked_at: datetime | None = None,
    waterfall_status: str = "failed",
) -> tuple[ExternalChatBinding, TelegramCheckpointMessage, VerifiedContact]:
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
        external_peer_id="12345678",
        external_peer_kind="direct",
        state="bound",
    )
    db_session.add(binding)
    await db_session.flush()

    mission = DshMission(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        status="success",
        phase="ingestion",
        progress_percent=100,
        payload={},
        checkpoint={},
    )
    db_session.add(mission)
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Công ty Đất Vàng",
        domain="datvang.vn",
        fit_score=85,
        value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
        source="batdongsan",
    )
    db_session.add(lead)
    await db_session.flush()

    phone = "+84908123456"
    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Trần Văn B"),
        phone=_encrypt(phone),
        email=_encrypt("b@datvang.vn"),
        phone_hmac=_phone_hash(phone),
        value_hmac=f"contact-hmac-{uuid4().hex[:8]}",
        is_unlocked=True,
        is_valid=True,
        consent_status="opted_in",
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    unlock_ts = unlocked_at or (datetime.now(UTC) - timedelta(hours=2))

    # Original unlock BillingEvent
    db_session.add(
        BillingEvent(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            event_entity_type="verified_contact",
            event_type="contact_unlock",
            event_id=contact.id,
            cost_micros=1500,
            currency="USD",
            cost_basis="actual",
            created_at=unlock_ts,
        )
    )

    # Waterfall log evidence
    db_session.add(
        PhoneWaterfallLog(
            workspace_id=db_workspace.id,
            contact_id=contact.id,
            lead_id=lead.id,
            phone_hash=_phone_hash(phone),
            tier_reached=3,
            provider_used="tier_3_carrier",
            status=waterfall_status,
            cost_micros=0,
            created_at=unlock_ts,
        )
    )

    token = f"tok_refund_{uuid4().hex[:8]}"
    checkpoint = TelegramCheckpointMessage(
        workspace_id=db_workspace.id,
        mission_id=mission.id,
        lead_id=lead.id,
        contact_id=contact.id,
        user_id=db_user.id,
        callback_token=token,
        status="unlocked",
        unlocked_at=unlock_ts,
        external_peer_id=binding.external_peer_id,
        external_message_id="999",
    )
    db_session.add(checkpoint)

    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    membership.monthly_spent_micros += 1500
    db_user.credit_micros_balance -= 1500
    await db_session.flush()

    return binding, checkpoint, contact


def _make_mock_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.send_message = AsyncMock()
    adapter.edit_message = AsyncMock()
    adapter.answer_callback_query = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_telegram_callback_refund_success_within_24h_window(
    db_session, db_user, db_workspace
):
    """P0: Invalid number within 24h triggers +1.5 credit refund, marks contact invalid, updates status."""
    binding, checkpoint, contact = await _setup_unlocked_telegram_checkpoint(
        db_session, db_workspace, db_user, waterfall_status="failed"
    )
    balance_before = db_user.credit_micros_balance
    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    spent_before = membership.monthly_spent_micros

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="999",
        external_user_id=binding.external_peer_id,
        text=f"dsh:refund:{checkpoint.callback_token}",
        metadata={"callback_query_id": "cqid_refund_ok"},
        raw_payload={},
    )

    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    # 1. Assert BillingEvent with cost_micros = -1500
    refund_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_id == contact.id,
                BillingEvent.event_type == "contact_unlock_refund",
            )
        )
    ).scalar_one()
    assert refund_event.cost_micros == -1500
    assert refund_event.user_id == db_user.id

    # 2. Assert wallet balance refunded
    refreshed_user = await db_session.get(User, db_user.id)
    assert refreshed_user.credit_micros_balance == balance_before + 1500

    # 3. Assert member spend reversed
    refreshed_membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    assert refreshed_membership.monthly_spent_micros == spent_before - 1500

    # 4. Assert contact is marked invalid in DB
    refreshed_contact = await db_session.get(VerifiedContact, contact.id)
    assert refreshed_contact.is_valid is False
    assert any(
        log.get("access_type") == "refund"
        for log in refreshed_contact.pii_access_audit_logs
    )

    # 5. Assert checkpoint message status updated
    refreshed_msg = await db_session.get(TelegramCheckpointMessage, checkpoint.id)
    assert refreshed_msg.status == "refunded"
    assert refreshed_msg.refunded_at is not None

    # 6. Assert Telegram message edit
    adapter.edit_message.assert_awaited_once()
    edit_text = adapter.edit_message.call_args.kwargs["text"]
    assert "+1.5 credits" in edit_text or "hoàn tiền" in edit_text.lower()


@pytest.mark.asyncio
async def test_telegram_callback_refund_rejected_when_number_is_active(
    db_session, db_user, db_workspace, monkeypatch
):
    """P0: When verification shows number is active, refund is denied with clear copy."""
    binding, checkpoint, contact = await _setup_unlocked_telegram_checkpoint(
        db_session, db_workspace, db_user, waterfall_status="success"
    )
    balance_before = db_user.credit_micros_balance

    # Verification returns False (not invalid => still active)
    monkeypatch.setattr(
        "app.services.dsh_telegram_checkpoint_service.DshTelegramCheckpointService._verify_phone_is_invalid",
        AsyncMock(return_value=False),
    )

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="999",
        external_user_id=binding.external_peer_id,
        text=f"dsh:refund:{checkpoint.callback_token}",
        metadata={"callback_query_id": "cqid_refund_active"},
        raw_payload={},
    )

    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    # No refund BillingEvent created
    refund_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_id == contact.id,
                BillingEvent.event_type == "contact_unlock_refund",
            )
        )
    ).scalar_one_or_none()
    assert refund_event is None

    # Wallet balance unchanged
    refreshed_user = await db_session.get(User, db_user.id)
    assert refreshed_user.credit_micros_balance == balance_before

    # Message edited with active notice
    adapter.edit_message.assert_awaited_once()
    edit_text = adapter.edit_message.call_args.kwargs["text"]
    assert "vẫn hoạt động" in edit_text.lower()


@pytest.mark.asyncio
async def test_telegram_callback_refund_rejected_when_24h_window_expired(
    db_session, db_user, db_workspace
):
    """P0: Refund after 24h SLA window is rejected."""
    expired_time = datetime.now(UTC) - timedelta(hours=25)
    binding, checkpoint, _ = await _setup_unlocked_telegram_checkpoint(
        db_session,
        db_workspace,
        db_user,
        unlocked_at=expired_time,
        waterfall_status="failed",
    )

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="999",
        external_user_id=binding.external_peer_id,
        text=f"dsh:refund:{checkpoint.callback_token}",
        metadata={"callback_query_id": "cqid_expired"},
        raw_payload={},
    )

    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    adapter.edit_message.assert_awaited_once()
    edit_text = adapter.edit_message.call_args.kwargs["text"]
    assert "24h" in edit_text or "hết hạn" in edit_text.lower()


@pytest.mark.asyncio
async def test_telegram_callback_refund_rejected_when_15_percent_cap_exhausted(
    db_session, db_user, db_workspace
):
    """P0: Refund exceeding 15% billing-cycle cap is rejected."""
    binding, checkpoint, _ = await _setup_unlocked_telegram_checkpoint(
        db_session, db_workspace, db_user, waterfall_status="failed"
    )

    # Seed 20 unlocks and 4 refunds (cap = ceil(21 * 0.15) = 4)
    for _ in range(20):
        db_session.add(
            BillingEvent(
                workspace_id=db_workspace.id,
                user_id=db_user.id,
                event_entity_type="verified_contact",
                event_type="contact_unlock",
                event_id=uuid4(),
                cost_micros=1500,
                currency="USD",
                cost_basis="actual",
            )
        )
    for _ in range(4):
        db_session.add(
            BillingEvent(
                workspace_id=db_workspace.id,
                user_id=db_user.id,
                event_entity_type="verified_contact",
                event_type="contact_unlock_refund",
                event_id=uuid4(),
                cost_micros=-1500,
                currency="USD",
                cost_basis="actual",
            )
        )
    await db_session.flush()

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="999",
        external_user_id=binding.external_peer_id,
        text=f"dsh:refund:{checkpoint.callback_token}",
        metadata={"callback_query_id": "cqid_cap_exceeded"},
        raw_payload={},
    )

    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    adapter.edit_message.assert_awaited_once()
    edit_text = adapter.edit_message.call_args.kwargs["text"]
    assert "hạn mức" in edit_text.lower() or "cap" in edit_text.lower()


@pytest.mark.asyncio
async def test_telegram_callback_refund_idempotent_real_postgres(
    db_session, db_user, db_workspace
):
    """P0: Two concurrent or successive refund clicks only credit the wallet once."""
    binding, checkpoint, contact = await _setup_unlocked_telegram_checkpoint(
        db_session, db_workspace, db_user, waterfall_status="failed"
    )
    balance_before = db_user.credit_micros_balance

    adapter = _make_mock_adapter()
    event = ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=binding.external_peer_id,
        external_peer_kind="direct",
        external_message_id="999",
        external_user_id=binding.external_peer_id,
        text=f"dsh:refund:{checkpoint.callback_token}",
        metadata={"callback_query_id": "cqid_idem"},
        raw_payload={},
    )

    # Dispatch twice
    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )
    await handle_callback_query(
        session=db_session, adapter=adapter, event=event, binding=binding
    )

    # Exactly 1 refund event
    refund_events = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact.id,
                    BillingEvent.event_type == "contact_unlock_refund",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(refund_events) == 1

    # Exactly +1500 credited
    refreshed_user = await db_session.get(User, db_user.id)
    assert refreshed_user.credit_micros_balance == balance_before + 1500
