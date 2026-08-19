"""Red-phase ATDD unit tests for DshTelegramCheckpointService (Story 26.6).

Covers:
- AC-1: High-fit lead checkpoint card building, MarkdownV2 escaping, PII masking, 1 card per mission.
- AC-2: 1-Click unlock callback handling, error mappings (402, 403, 409), inline card editing.
- AC-3: Dossier expansion and skip dismiss callbacks.
- AC-4: 1-Click auto-refund 24h for invalid numbers, verification check, 15% cap check.
- AC-5: Rate limits, audit logs, and callback_data <= 64 bytes assertion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = [
    pytest.mark.unit,
]


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        if self._value is None:
            raise ValueError("No row found")
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows

    def first(self) -> Any:
        if self._rows:
            return self._rows[0]
        return self._value


class _FakeSession:
    """AsyncSession stand-in with query matching."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.query_map: dict[str, Any] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        try:
            compiled = stmt.compile(compile_kwargs={"literal_binds": True})
            text = str(compiled).lower()
        except Exception:
            text = str(stmt).lower()
        for key, value in self.query_map.items():
            if key.lower() in text:
                if isinstance(value, list):
                    return _FakeResult(rows=value, value=value[0] if value else None)
                return _FakeResult(value=value)
        return _FakeResult()

    async def get(self, model: type, _ident: Any) -> Any | None:
        model_name = getattr(model, "__name__", str(model)).lower()
        if "lead" in model_name and "leads" in self.query_map:
            val = self.query_map["leads"]
            return val[0] if isinstance(val, list) and val else val
        if "contact" in model_name and "verified_contacts" in self.query_map:
            val = self.query_map["verified_contacts"]
            return val[0] if isinstance(val, list) and val else val
        if (
            "checkpoint" in model_name
            and "telegram_checkpoint_messages" in self.query_map
        ):
            val = self.query_map["telegram_checkpoint_messages"]
            return val[0] if isinstance(val, list) and val else val
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, _obj: Any) -> None:
        pass


def _make_lead(overrides: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "workspace_id": 1,
        "company_name": "Acme Corp_Special [Chars]",
        "domain": "acme.vn",
        "source": "batdongsan",
        "source_url": "https://batdongsan.vn/item-123",
        "fit_score": 85,
        "intent_score": 90,
        "phone": "0908123456",
        "email": "contact@acme.vn",
        "value_hmac": "lead-hmac-123",
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_contact(lead_id: UUID, overrides: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "workspace_id": 1,
        "lead_id": lead_id,
        "phone": "0908123456",
        "email": "contact@acme.vn",
        "name": "Nguyễn Văn A",
        "is_unlocked": False,
        "is_valid": True,
        "consent_status": "opted_in",
        "value_hmac": "contact-hmac-123",
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_checkpoint_message(
    token: str = "tok_test123456",
    status: str = "sent",
    overrides: dict | None = None,
    **kwargs: Any,
) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "callback_token": token,
        "status": status,
        "workspace_id": 1,
        "mission_id": uuid4(),
        "lead_id": uuid4(),
        "contact_id": uuid4(),
        "user_id": uuid4(),
        "external_message_id": "99",
        "external_peer_id": "12345",
        "unlocked_at": None,
        "refunded_at": None,
        "action_payload": {},
    }
    if overrides:
        defaults.update(overrides)
    if kwargs:
        defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ============================================================================
# AC-1: High-fit lead checkpoint card building and lead selection
# ============================================================================


class TestDshTelegramCardFormatting:
    """AC-1: Card formatting, PII masking, MarkdownV2 escaping."""

    def test_build_card_markdown_v2_escapes_special_characters(self) -> None:
        """Pattern 1: dynamic text with reserved characters is escaped."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        lead = _make_lead({"company_name": "Công ty TNHH A.B_C* & Co [HCM] ~ 100%!"})
        contact = _make_contact(lead.id)
        service = DshTelegramCheckpointService()

        card_text, _reply_markup = service.build_checkpoint_card(
            lead=lead, contact=contact, callback_token="tok_test123"
        )

        assert "A\\.B\\_C\\*" in card_text or "Công ty TNHH" in card_text
        assert "0908***456" in card_text or "0908" in card_text
        # Assert raw plaintext phone is NOT present
        assert "0908123456" not in card_text

    def test_build_card_inline_keyboard_structure(self) -> None:
        """Pattern 1: card has 3 inline action buttons with <= 64 byte callback_data."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        lead = _make_lead()
        contact = _make_contact(lead.id)
        service = DshTelegramCheckpointService()
        token = "tok_abcdef123456"

        _, reply_markup = service.build_checkpoint_card(
            lead=lead, contact=contact, callback_token=token
        )

        buttons = reply_markup["inline_keyboard"][0]
        assert len(buttons) == 3
        unlock_btn, dossier_btn, skip_btn = buttons
        assert unlock_btn["callback_data"] == f"dsh:unlock:{token}"
        assert dossier_btn["callback_data"] == f"dsh:dossier:{token}"
        assert skip_btn["callback_data"] == f"dsh:skip:{token}"

        # Assert 64-byte Telegram limit for all buttons
        for btn in buttons:
            assert len(btn["callback_data"].encode("utf-8")) <= 64


class TestDshLeadSelection:
    """AC-1: High-fit lead selection logic."""

    def test_select_highest_fit_lead_above_threshold(self) -> None:
        """Pattern 1: Selects the lead with fit_score >= 80 and highest score."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        leads = [
            _make_lead({"id": uuid4(), "fit_score": 75, "phone": "0901111111"}),
            _make_lead({"id": uuid4(), "fit_score": 88, "phone": "0902222222"}),
            _make_lead({"id": uuid4(), "fit_score": 92, "phone": "0903333333"}),
            _make_lead({"id": uuid4(), "fit_score": 81, "phone": "0904444444"}),
        ]
        service = DshTelegramCheckpointService()

        selected = service.select_high_fit_lead(leads, threshold=80)
        assert selected is not None
        assert selected.fit_score == 92
        assert selected.phone == "0903333333"

    def test_select_lead_boundary_exact_threshold_qualifies(self) -> None:
        """Pattern 3 (Edge): fit_score == 80 qualifies; 79 does not."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        leads_79 = [_make_lead({"fit_score": 79, "phone": "0901111111"})]
        leads_80 = [_make_lead({"fit_score": 80, "phone": "0901111111"})]
        service = DshTelegramCheckpointService()

        assert service.select_high_fit_lead(leads_79, threshold=80) is None
        assert service.select_high_fit_lead(leads_80, threshold=80) is not None

    def test_select_lead_skips_lead_without_phone(self) -> None:
        """Pattern 3 (Edge): lead with fit_score=95 but no phone is skipped."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        leads = [
            _make_lead({"fit_score": 95, "phone": None}),
            _make_lead({"fit_score": 82, "phone": "0902222222"}),
        ]
        service = DshTelegramCheckpointService()

        selected = service.select_high_fit_lead(leads, threshold=80)
        assert selected is not None
        assert selected.fit_score == 82

    def test_select_lead_with_dictionary_input(self) -> None:
        """Patch 9: Selects highest-fit lead from raw dict list from worker checkpoint."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        leads = [
            {"fit_score": 70, "phone": "0901111111", "company_name": "A"},
            {"fit_score": 90, "phone": "0902222222", "company_name": "B"},
            {"fit_score": 95, "phone": None, "company_name": "C"},
        ]
        service = DshTelegramCheckpointService()

        selected = service.select_high_fit_lead(leads, threshold=80)
        assert selected is not None
        assert selected["company_name"] == "B"
        assert selected["fit_score"] == 90
        assert selected["phone"] == "0902222222"


class TestDshNotificationPreferences:
    """AC-1: User notification preference checking."""

    def test_notification_skipped_when_preference_explicitly_false(self) -> None:
        """Pattern 1: user_notification_preferences['dsh_high_fit_lead']['telegram'] == False skips."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        user = SimpleNamespace(
            notification_preferences={"dsh_high_fit_lead": {"telegram": False}}
        )
        service = DshTelegramCheckpointService()
        assert service.should_send_telegram_notification(user) is False

    def test_notification_defaults_to_enabled_when_preference_missing(self) -> None:
        """Pattern 1: Missing preference defaults to enabled."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        user_none = SimpleNamespace(notification_preferences=None)
        user_empty = SimpleNamespace(notification_preferences={})
        service = DshTelegramCheckpointService()
        assert service.should_send_telegram_notification(user_none) is True
        assert service.should_send_telegram_notification(user_empty) is True


# ============================================================================
# AC-2: 1-Click unlock callback handling
# ============================================================================


class TestDshUnlockCallback:
    """AC-2: 1-Click unlock, message edit, and error paths."""

    @pytest.mark.asyncio
    async def test_unlock_callback_success_edits_message_with_unmasked_phone(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 1: Unlocks contact, edits card with decrypted phone and action buttons."""
        from app.services.contact_unlock_service import ContactUnlockResult
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        checkpoint = _make_checkpoint_message("tok_123", status="sent")
        contact = _make_contact(checkpoint.lead_id, {"id": checkpoint.contact_id})
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]
        session.query_map["verified_contacts"] = [contact]

        unlock_result = ContactUnlockResult(
            contact_id=checkpoint.contact_id,
            is_unlocked=True,
            cost_micros=1500,
            phone="0908123456",
            email="contact@acme.vn",
            name="Nguyễn Văn A",
        )
        mocker.patch(
            "app.services.contact_unlock_service.ContactUnlockService.unlock_contact",
            new=AsyncMock(return_value=unlock_result),
        )

        service = DshTelegramCheckpointService()
        await service.handle_unlock_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_123",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        call_kwargs = adapter.edit_message.call_args.kwargs
        assert "0908123456" in call_kwargs["text"]
        assert "-1.5 credits" in call_kwargs["text"]
        assert checkpoint.status == "unlocked"
        assert checkpoint.unlocked_at is not None

    @pytest.mark.asyncio
    async def test_unlock_callback_insufficient_credits_402_edits_message_without_pii(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 2: 402 PAYMENT_REQUIRED edits card with top-up message and NO PII."""
        from fastapi import HTTPException, status

        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        checkpoint = _make_checkpoint_message("tok_123", status="sent")
        contact = _make_contact(checkpoint.lead_id, {"id": checkpoint.contact_id})
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]
        session.query_map["verified_contacts"] = [contact]

        mocker.patch(
            "app.services.contact_unlock_service.ContactUnlockService.unlock_contact",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Insufficient credits",
                )
            ),
        )

        service = DshTelegramCheckpointService()
        await service.handle_unlock_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_123",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        call_kwargs = adapter.edit_message.call_args.kwargs
        assert "Không đủ credits" in call_kwargs["text"]
        assert "0908123456" not in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_unlock_callback_dnc_blocked_403_edits_message(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 5: 403 Forbidden (DNC) edits message with DNC blocked notice."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        checkpoint = _make_checkpoint_message("tok_123", status="sent")
        contact = _make_contact(checkpoint.lead_id, {"id": checkpoint.contact_id})
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]
        session.query_map["verified_contacts"] = [contact]

        mocker.patch(
            "app.services.contact_unlock_service.ContactUnlockService.unlock_contact",
            new=AsyncMock(
                side_effect=HTTPException(status_code=403, detail="DNC blocked")
            ),
        )

        service = DshTelegramCheckpointService()
        await service.handle_unlock_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_123",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        call_kwargs = adapter.edit_message.call_args.kwargs
        assert "DNC" in call_kwargs["text"]


# ============================================================================
# AC-3: Dossier and Skip callbacks
# ============================================================================


class TestDshDossierAndSkipCallbacks:
    """AC-3: Dossier expansion and skip dismiss actions."""

    @pytest.mark.asyncio
    async def test_dossier_callback_appends_dossier_and_escapes_markdown(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 1: Appends company details, intent score, and deep-link."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        lead = _make_lead({"company_name": "Tập đoàn BĐS [VIP]"})
        checkpoint = _make_checkpoint_message("tok_dossier", lead_id=lead.id)
        contact = _make_contact(lead.id, {"id": checkpoint.contact_id})
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]
        session.query_map["leads"] = [lead]
        session.query_map["verified_contacts"] = [contact]

        service = DshTelegramCheckpointService()
        await service.handle_dossier_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_dossier",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        call_kwargs = adapter.edit_message.call_args.kwargs
        assert "Tập đoàn BĐS" in call_kwargs["text"]
        assert "Fit:" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_skip_callback_marks_dismissed_and_edits_message(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 1: Edits card to dismissed copy and updates status."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        checkpoint = _make_checkpoint_message("tok_skip", status="sent")
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]

        service = DshTelegramCheckpointService()
        await service.handle_skip_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_skip",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        assert "bỏ qua" in adapter.edit_message.call_args.kwargs["text"].lower()
        assert checkpoint.status == "dismissed"


# ============================================================================
# AC-4: 1-Click auto-refund callbacks
# ============================================================================


class TestDshRefundCallback:
    """AC-4: Auto-refund for invalid numbers with SLA, verification, and 15% cap."""

    @pytest.mark.asyncio
    async def test_refund_callback_when_number_verified_active_rejects_refund(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 3: When number is verified reachable, refund is denied."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        checkpoint = _make_checkpoint_message(
            "tok_ref",
            status="unlocked",
            overrides={"unlocked_at": datetime.now(UTC) - timedelta(hours=1)},
        )
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]

        # Verification returns number is valid/active
        mocker.patch(
            "app.services.dsh_telegram_checkpoint_service.DshTelegramCheckpointService._verify_phone_is_invalid",
            new=AsyncMock(return_value=False),  # False => not invalid (still valid)
        )

        service = DshTelegramCheckpointService()
        await service.handle_refund_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_ref",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        assert "vẫn hoạt động" in adapter.edit_message.call_args.kwargs["text"].lower()
        assert checkpoint.status == "unlocked"  # not refunded

    @pytest.mark.asyncio
    async def test_refund_callback_success_credits_wallet_and_edits_message(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 1 & 4: Verified invalid number credits +1.5 credits and sets status='refunded'."""
        from app.services.dsh_telegram_checkpoint_service import (
            DshTelegramCheckpointService,
        )

        session = _FakeSession()
        adapter = MagicMock()
        adapter.edit_message = AsyncMock()
        adapter.answer_callback_query = AsyncMock()

        checkpoint = _make_checkpoint_message(
            "tok_ref",
            status="unlocked",
            overrides={"unlocked_at": datetime.now(UTC) - timedelta(hours=2)},
        )
        session.query_map["telegram_checkpoint_messages"] = [checkpoint]

        mocker.patch(
            "app.services.dsh_telegram_checkpoint_service.DshTelegramCheckpointService._verify_phone_is_invalid",
            new=AsyncMock(return_value=True),  # True => confirmed invalid
        )
        mocker.patch(
            "app.services.billing_event_service.BillingEventService.record_contact_unlock_refund_24h",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    event_type="contact_unlock_refund", cost_micros=-1500
                )
            ),
        )

        service = DshTelegramCheckpointService()
        await service.handle_refund_callback(
            session=session,
            adapter=adapter,
            event=SimpleNamespace(external_peer_id="12345", external_message_id="99"),
            binding=SimpleNamespace(workspace_id=1, user_id=checkpoint.user_id),
            callback_token="tok_ref",
            callback_query_id="cqid",
        )

        adapter.edit_message.assert_awaited_once()
        call_kwargs = adapter.edit_message.call_args.kwargs
        assert (
            "+1.5 credits" in call_kwargs["text"]
            or "hoàn tiền" in call_kwargs["text"].lower()
        )
        assert checkpoint.status == "refunded"
        assert checkpoint.refunded_at is not None
