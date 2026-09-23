"""Unit tests for Story 37.7 — AD-121 invalid-contact auto-refund + AD-110 cap.

Covers:
- extract_invalid_contact_error_code whitelist (ZALO_USER_NOT_FOUND /
  TELCO_NUMBER_UNALLOCATED only; manual claims rejected)
- auto_refund_invalid_contact: immediate wallet re-credit to the original
  payer, ``credit_refund_invalid_contact`` ledger entry, idempotency,
  VerifiedContact invalidation
- 15% monthly circuit breaker routing to the Admin Desk (refund_review)
- resolve_admin_desk_refund approve/reject
- VietQR top-up intents + Napas webhook fulfilment
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.db import (
    BillingEvent,
    CreditPurchase,
    CreditPurchaseStatus,
    Lead,
    PhoneWaterfallLog,
    User,
    VerifiedContact,
)
from app.services import vietqr_topup_service
from app.services.billing_service import (
    REFUND_ADMIN_DESK_EVENT,
    REFUND_INVALID_CONTACT_EVENT,
    REFUND_REJECTED_STATUS,
    REFUND_REVIEW_STATUS,
    BillingService,
    extract_invalid_contact_error_code,
)

# Real (non-placeholder) secret for webhook tests — the service refuses the
# public dev placeholder and any unset/empty secret.
_TEST_WEBHOOK_SECRET = "unit_test_webhook_secret_9f8e7d6c"

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _RefundSession:
    """Fake session dispatching selects by entity.

    Whole-row ``select(BillingEvent)`` calls (the monthly unlock/refund
    counters) pop from ``event_row_sets`` in call order; column selects
    (``BillingEvent.user_id`` payer lookup) return ``payer_id``.
    """

    def __init__(
        self,
        *,
        lead: Any = None,
        log: Any = None,
        payer_id: UUID | None = None,
        contacts: list[Any] | None = None,
        event_row_sets: list[list[Any]] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self._lead = lead
        self._log = log
        self._payer_id = payer_id
        self._contacts = contacts or []
        self._event_row_sets = list(event_row_sets or [])

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def get(self, model: type, _ident: Any) -> Any | None:
        return self._lead if model is Lead else None

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        try:
            cd = stmt.column_descriptions[0]
        except (AttributeError, TypeError, IndexError):
            return _FakeResult()  # text()/DDL e.g. pg_advisory_xact_lock
        entity, expr = cd.get("entity"), cd.get("expr")
        if entity is PhoneWaterfallLog:
            return _FakeResult(self._log)
        if entity is VerifiedContact:
            return _FakeResult(rows=self._contacts)
        if entity is BillingEvent:
            if expr is BillingEvent:  # whole-row select → event counter
                rows = self._event_row_sets.pop(0) if self._event_row_sets else []
                return _FakeResult(rows=rows)
            return _FakeResult(self._payer_id)
        return _FakeResult()

    async def commit(self) -> None:
        self.committed += 1


def _lead(workspace_id: int = 1) -> Lead:
    return Lead(
        id=uuid4(),
        workspace_id=workspace_id,
        client_id="bds",
        source="batdongsan",
        company_name="Test Co",
        source_url="https://batdongsan.com.vn/x-pr1",
    )


def _log(lead_id: UUID, workspace_id: int = 1, **kwargs: Any) -> PhoneWaterfallLog:
    log = PhoneWaterfallLog(
        id=uuid4(),
        workspace_id=workspace_id,
        lead_id=lead_id,
        status="success",
        cost_micros=1_500_000,
        tier_reached=1,
        provider_used="batdongsan",
        phone_hash="abc123",
        phone_masked="0908***456",
    )
    log.created_at = datetime.now(UTC)
    for key, value in kwargs.items():
        setattr(log, key, value)
    return log


# ─────────────────────────────────────────────────────────────
# Error-code extraction
# ─────────────────────────────────────────────────────────────


class TestExtractInvalidContactErrorCode:
    def test_direct_and_nested_codes(self) -> None:
        assert (
            extract_invalid_contact_error_code(
                {"hlr_status": "TELCO_NUMBER_UNALLOCATED"}
            )
            == "TELCO_NUMBER_UNALLOCATED"
        )
        assert (
            extract_invalid_contact_error_code(
                {"error": {"code": "zalo_user_not_found"}}
            )
            == "ZALO_USER_NOT_FOUND"
        )
        assert (
            extract_invalid_contact_error_code("TELCO_NUMBER_UNALLOCATED")
            == "TELCO_NUMBER_UNALLOCATED"
        )

    def test_non_matching_payloads(self) -> None:
        assert extract_invalid_contact_error_code(None) is None
        assert extract_invalid_contact_error_code({}) is None
        assert (
            extract_invalid_contact_error_code({"error": "USER_REPORTED_INVALID"})
            is None
        )
        assert extract_invalid_contact_error_code("manual claim") is None


# ─────────────────────────────────────────────────────────────
# auto_refund_invalid_contact (AD-121)
# ─────────────────────────────────────────────────────────────


class TestAutoRefundInvalidContact:
    @pytest.mark.asyncio
    async def test_rejects_manual_claim_codes(self) -> None:
        session = _RefundSession()
        with pytest.raises(HTTPException) as exc_info:
            await BillingService(session).auto_refund_invalid_contact(
                workspace_id=1,
                lead_id=uuid4(),
                user_id=uuid4(),
                error_code="reported_invalid_phone",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_refunds_original_payer_with_ledger_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lead = _lead()
        log = _log(lead.id)
        payer_id = uuid4()
        contact = SimpleNamespace(
            is_valid=True,
            verification_status="verified",
            refunded_at=None,
            invalid_reason=None,
        )
        # unlock events this month: 10 → cap = ceil(10 * .15) = 2; refunds: 0
        session = _RefundSession(
            lead=lead,
            log=log,
            payer_id=payer_id,
            contacts=[contact],
            event_row_sets=[
                [object()] * 10,  # unlock count rows
                [],  # refund count rows
            ],
        )

        wallet_calls: list[tuple[Any, int]] = []

        async def _apply_credit(_session: Any, user_id: Any, amount: int) -> int:
            wallet_calls.append((user_id, amount))
            await _session.commit()  # real apply_credit commits the txn
            return amount

        monkeypatch.setattr("app.services.wallet_credit.apply_credit", _apply_credit)
        monkeypatch.setattr("app.services.billing_service.get_redis", lambda: None)

        result = await BillingService(session).auto_refund_invalid_contact(
            workspace_id=1,
            lead_id=lead.id,
            user_id=uuid4(),
            error_code="ZALO_USER_NOT_FOUND",
        )

        assert result["refunded"] is True
        assert result["refund_micros"] == 1_500_000
        assert result["status"] == "refunded"
        # Wallet credited to the ORIGINAL payer, not the caller
        assert wallet_calls == [(payer_id, 1_500_000)]
        # Log marked refunded with the technical error code
        assert log.status == "refunded"
        assert log.refund_reason == "ZALO_USER_NOT_FOUND"
        # Audited ledger entry with the exact required event type
        refund_events = [
            o
            for o in session.added
            if isinstance(o, BillingEvent)
            and o.event_type == REFUND_INVALID_CONTACT_EVENT
        ]
        assert len(refund_events) == 1
        assert refund_events[0].cost_micros == -1_500_000
        assert refund_events[0].user_id == payer_id
        # Contact invalidated
        assert contact.is_valid is False
        assert contact.verification_status == "invalid"
        assert session.committed >= 1

    @pytest.mark.asyncio
    async def test_idempotent_when_already_refunded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lead = _lead()
        log = _log(
            lead.id,
            status="refunded",
            refunded_at=datetime.now(UTC),
            refund_reason="TELCO_NUMBER_UNALLOCATED",
        )
        session = _RefundSession(lead=lead, log=log)

        async def _apply_credit(*_a: Any, **_kw: Any) -> None:
            raise AssertionError("wallet must not be credited twice")

        monkeypatch.setattr("app.services.wallet_credit.apply_credit", _apply_credit)

        result = await BillingService(session).auto_refund_invalid_contact(
            workspace_id=1,
            lead_id=lead.id,
            user_id=uuid4(),
            error_code="TELCO_NUMBER_UNALLOCATED",
        )
        assert result["refunded"] is True
        assert result["already_refunded"] is True
        assert not session.added

    @pytest.mark.asyncio
    async def test_cap_routes_to_admin_desk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lead = _lead()
        log = _log(lead.id)
        # 10 unlocks, 2 refunds already → cap = ceil(10*.15) = 2 reached
        session = _RefundSession(
            lead=lead,
            log=log,
            event_row_sets=[[object()] * 10, [object(), object()]],
        )

        async def _apply_credit(*_a: Any, **_kw: Any) -> None:
            raise AssertionError("cap reached — no auto credit")

        monkeypatch.setattr("app.services.wallet_credit.apply_credit", _apply_credit)

        result = await BillingService(session).auto_refund_invalid_contact(
            workspace_id=1,
            lead_id=lead.id,
            user_id=uuid4(),
            error_code="TELCO_NUMBER_UNALLOCATED",
        )

        assert result["refunded"] is False
        assert result["routed_to_admin_desk"] is True
        assert result["status"] == REFUND_REVIEW_STATUS
        assert log.status == REFUND_REVIEW_STATUS
        desk_markers = [
            o
            for o in session.added
            if isinstance(o, BillingEvent) and o.event_type == REFUND_ADMIN_DESK_EVENT
        ]
        assert len(desk_markers) == 1

    @pytest.mark.asyncio
    async def test_zero_unlocks_routes_everything_to_desk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lead = _lead()
        log = _log(lead.id)
        session = _RefundSession(lead=lead, log=log, event_row_sets=[[], []])

        async def _apply_credit(*_a: Any, **_kw: Any) -> None:
            raise AssertionError("no unlocks — no auto credit")

        monkeypatch.setattr("app.services.wallet_credit.apply_credit", _apply_credit)

        result = await BillingService(session).auto_refund_invalid_contact(
            workspace_id=1,
            lead_id=lead.id,
            user_id=uuid4(),
            error_code="ZALO_USER_NOT_FOUND",
        )
        assert result["routed_to_admin_desk"] is True

    @pytest.mark.asyncio
    async def test_wrong_workspace_lead_rejected(self) -> None:
        lead = _lead(workspace_id=2)  # belongs to another workspace
        session = _RefundSession(lead=lead)
        with pytest.raises(HTTPException) as exc_info:
            await BillingService(session).auto_refund_invalid_contact(
                workspace_id=1,
                lead_id=lead.id,
                user_id=uuid4(),
                error_code="ZALO_USER_NOT_FOUND",
            )
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────
# Admin Desk resolution (AD-110)
# ─────────────────────────────────────────────────────────────


class _DeskSession:
    """Minimal session for resolve_admin_desk_refund."""

    def __init__(self, log: Any) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self._log = log

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        try:
            entity = stmt.column_descriptions[0].get("entity")
        except (AttributeError, TypeError, IndexError):
            return _FakeResult()
        if entity is PhoneWaterfallLog:
            return _FakeResult(self._log)
        return _FakeResult(rows=[])

    async def get(self, model: type, _ident: Any) -> Any | None:
        return None

    async def commit(self) -> None:
        self.committed += 1


class TestAdminDeskResolution:
    @pytest.mark.asyncio
    async def test_reject_marks_refund_rejected(self) -> None:
        log = _log(uuid4(), status=REFUND_REVIEW_STATUS)
        session = _DeskSession(log)

        result = await BillingService(session).resolve_admin_desk_refund(
            log_id=log.id, approve=False, admin_user_id=uuid4(), note="dup"
        )

        assert result["refunded"] is False
        assert result["status"] == REFUND_REJECTED_STATUS
        assert log.status == REFUND_REJECTED_STATUS
        assert "rejected:dup" in (log.refund_reason or "")

    @pytest.mark.asyncio
    async def test_resolve_requires_review_status(self) -> None:
        log = _log(uuid4(), status="success")
        session = _DeskSession(log)
        with pytest.raises(HTTPException) as exc_info:
            await BillingService(session).resolve_admin_desk_refund(
                log_id=log.id, approve=True
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_refunds_exact_log_and_original_payer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Desk approval refunds the queued log — not a newer log on the same
        lead — and credits the original payer's wallet, never the admin's."""
        lead = _lead()
        review_log = _log(
            lead.id,
            status=REFUND_REVIEW_STATUS,
            refund_reason="TELCO_NUMBER_UNALLOCATED",
        )
        newer_log = _log(lead.id)  # must NOT be refunded by this approval
        payer_id, admin_id = uuid4(), uuid4()
        session = _RefundSession(lead=lead, log=review_log, payer_id=payer_id)

        wallet_calls: list[tuple[Any, int]] = []

        async def _apply_credit(_s: Any, user_id: Any, amount: int) -> int:
            wallet_calls.append((user_id, amount))
            await _s.commit()
            return amount

        monkeypatch.setattr("app.services.wallet_credit.apply_credit", _apply_credit)
        monkeypatch.setattr("app.services.billing_service.get_redis", lambda: None)

        result = await BillingService(session).resolve_admin_desk_refund(
            log_id=review_log.id, approve=True, admin_user_id=admin_id, note="ok"
        )

        assert result["refunded"] is True
        assert review_log.status == "refunded"
        # Approval metadata persisted (audit-only — not a wallet destination)
        assert f"approved_by:{admin_id}" in (review_log.refund_reason or "")
        # Original payer credited; admin wallet untouched
        assert wallet_calls == [(payer_id, 1_500_000)]
        # Newer log for the same lead is untouched
        assert newer_log.status == "success"
        refund_events = [
            o
            for o in session.added
            if isinstance(o, BillingEvent)
            and o.event_type == REFUND_INVALID_CONTACT_EVENT
        ]
        assert len(refund_events) == 1
        assert refund_events[0].event_id == review_log.id
        assert refund_events[0].user_id == payer_id


class TestUnresolvedPayer:
    @pytest.mark.asyncio
    async def test_no_payer_routes_to_review_without_ledger(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No resolvable payer → route to review; no fake successful refund."""
        lead = _lead()
        log = _log(lead.id)
        session = _RefundSession(
            lead=lead,
            log=log,
            payer_id=None,
            event_row_sets=[[object()] * 10, []],  # under the 15% cap
        )

        async def _apply_credit(*_a: Any, **_kw: Any) -> None:
            raise AssertionError("no payer — wallet must not be credited")

        monkeypatch.setattr("app.services.wallet_credit.apply_credit", _apply_credit)

        result = await BillingService(session).auto_refund_invalid_contact(
            workspace_id=1,
            lead_id=lead.id,
            user_id=uuid4(),
            error_code="ZALO_USER_NOT_FOUND",
        )

        assert result["refunded"] is False
        assert result["routed_to_admin_desk"] is True
        assert result["status"] == REFUND_REVIEW_STATUS
        assert log.status == REFUND_REVIEW_STATUS
        assert "payer_unresolved" in (log.refund_reason or "")
        refund_events = [
            o
            for o in session.added
            if isinstance(o, BillingEvent)
            and o.event_type == REFUND_INVALID_CONTACT_EVENT
        ]
        assert not refund_events


# ─────────────────────────────────────────────────────────────
# VietQR top-up intents + webhook (AC-2)
# ─────────────────────────────────────────────────────────────


class _TopupSession:
    """Fake session for VietQR intent creation / webhook fulfilment."""

    def __init__(
        self,
        *,
        purchase: Any = None,
        user: Any = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self._purchase = purchase
        self._user = user

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        # emulate PK default for refresh-less dict building
        if isinstance(obj, CreditPurchase) and getattr(obj, "id", None) is None:
            obj.id = uuid4()

    async def get(self, model: type, _ident: Any) -> Any | None:
        if model is CreditPurchase:
            return self._purchase
        return None

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        try:
            entity = stmt.column_descriptions[0].get("entity")
        except (AttributeError, TypeError, IndexError):
            return _FakeResult()  # update()/text() stmts (lazy expiry etc.)
        if entity is CreditPurchase:
            return _FakeResult(self._purchase)
        if entity is User:
            return _FakeResult(self._user)
        return _FakeResult()

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        pass

    async def refresh(self, _obj: Any) -> None:
        pass


def _sign(body: bytes, secret: str = _TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _purchase(**kwargs: Any) -> CreditPurchase:
    pid = uuid4()
    purchase = CreditPurchase(
        id=pid,
        user_id=uuid4(),
        stripe_checkout_session_id=vietqr_topup_service.build_transfer_memo(pid),
        quantity=1_000,
        credit_micros_granted=10_000_000,  # 1.000 credits
        amount_total=990_000,
        currency="vnd",
        source="vietqr",
        status=CreditPurchaseStatus.PENDING,
    )
    purchase.created_at = datetime.now(UTC)
    for key, value in kwargs.items():
        setattr(purchase, key, value)
    return purchase


class TestVietqrTopupService:
    @pytest.fixture(autouse=True)
    def _vietqr_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Feature is opt-in (default off) and webhook fulfilment requires a
        # real configured secret — enable both for these unit tests.
        monkeypatch.setattr(vietqr_topup_service.config, "VIETQR_TOPUP_ENABLED", True)
        monkeypatch.setenv("VIETQR_WEBHOOK_SECRET", _TEST_WEBHOOK_SECRET)

    def test_pricing_tiers_match_spec(self) -> None:
        tiers = {t["id"]: t for t in vietqr_topup_service.pricing_tiers()}
        assert tiers["starter"]["price_vnd"] == 990_000
        assert tiers["starter"]["credits"] == 1_000
        assert tiers["professional"]["price_vnd"] == 2_490_000
        assert tiers["professional"]["credits"] == 3_500
        assert tiers["professional"]["seats"] == 3
        assert tiers["professional"]["highlighted"] is True
        assert tiers["business"]["price_vnd"] == 5_990_000
        assert tiers["business"]["credits"] == 10_000
        assert tiers["business"]["seats"] is None

    @pytest.mark.asyncio
    async def test_create_tier_intent(self) -> None:
        session = _TopupSession()
        intent = await vietqr_topup_service.create_topup_intent(
            session, user_id=uuid4(), tier_id="professional"
        )
        assert intent["amount_vnd"] == 2_490_000
        assert intent["credits"] == 3_500
        assert intent["status"] == "pending"
        assert intent["transfer_memo"].startswith("NOWING ")
        assert "addInfo=" in intent["qr_url"]
        purchase = session.added[0]
        assert purchase.source == "vietqr"
        assert purchase.status == CreditPurchaseStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_intent_rejects_unknown_tier_and_tiny_amount(
        self,
    ) -> None:
        session = _TopupSession()
        with pytest.raises(ValueError):
            await vietqr_topup_service.create_topup_intent(
                session, user_id=uuid4(), tier_id="platinum"
            )
        with pytest.raises(ValueError):
            await vietqr_topup_service.create_topup_intent(
                session, user_id=uuid4(), amount_vnd=1_000
            )

    @pytest.mark.asyncio
    async def test_intent_expires_after_window(self) -> None:
        purchase = _purchase()
        purchase.created_at = datetime.now(UTC) - timedelta(minutes=11)
        session = _TopupSession(purchase=purchase)
        intent = await vietqr_topup_service.get_topup_intent(
            session, intent_id=purchase.id, user_id=purchase.user_id
        )
        assert intent is not None
        assert intent["status"] == "expired"

    @pytest.mark.asyncio
    async def test_webhook_rejects_bad_signature(self) -> None:
        session = _TopupSession()
        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=b"{}", signature="deadbeef"
        )
        assert result["status"] == "invalid_signature"

    @pytest.mark.asyncio
    async def test_webhook_credits_wallet_on_matching_memo(self) -> None:
        purchase = _purchase()
        user = SimpleNamespace(id=purchase.user_id, credit_micros_balance=0)
        session = _TopupSession(purchase=purchase, user=user)

        body = json.dumps(
            {
                "amount": purchase.amount_total,
                "description": f"CK {purchase.stripe_checkout_session_id}",
                "transaction_id": "FT24001",
            }
        ).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )

        assert result["status"] == "credited"
        assert purchase.status == CreditPurchaseStatus.COMPLETED
        assert purchase.stripe_payment_intent_id == "FT24001"
        assert user.credit_micros_balance == purchase.credit_micros_granted

    @pytest.mark.asyncio
    async def test_webhook_idempotent_on_replay(self) -> None:
        purchase = _purchase(status=CreditPurchaseStatus.COMPLETED)
        session = _TopupSession(purchase=purchase, user=SimpleNamespace())
        body = json.dumps(
            {"amount": 990_000, "content": purchase.stripe_checkout_session_id}
        ).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )
        assert result["status"] == "already_completed"

    @pytest.mark.asyncio
    async def test_webhook_underpaid_not_credited(self) -> None:
        purchase = _purchase()
        user = SimpleNamespace(id=purchase.user_id, credit_micros_balance=0)
        session = _TopupSession(purchase=purchase, user=user)
        body = json.dumps(
            {"amount": 100_000, "content": purchase.stripe_checkout_session_id}
        ).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )
        assert result["status"] == "amount_mismatch"
        assert purchase.status == CreditPurchaseStatus.PENDING
        assert user.credit_micros_balance == 0

    @pytest.mark.asyncio
    async def test_webhook_no_memo_ignored(self) -> None:
        session = _TopupSession()
        body = json.dumps({"amount": 990_000, "content": "random memo"}).encode()
        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )
        assert result["status"] == "no_memo"

    @pytest.mark.asyncio
    async def test_webhook_credits_expired_intent(self) -> None:
        """Late transfer still credits — the money did arrive (AC-2)."""
        purchase = _purchase(status=CreditPurchaseStatus.EXPIRED)
        user = SimpleNamespace(id=purchase.user_id, credit_micros_balance=0)
        session = _TopupSession(purchase=purchase, user=user)
        body = json.dumps(
            {
                "amount": purchase.amount_total,
                "content": purchase.stripe_checkout_session_id,
            }
        ).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )

        assert result["status"] == "credited"
        assert purchase.status == CreditPurchaseStatus.COMPLETED
        assert user.credit_micros_balance == purchase.credit_micros_granted

    @pytest.mark.asyncio
    async def test_webhook_unknown_amount_not_credited(self) -> None:
        """No parseable amount → no credit; intent stays PENDING for retry."""
        purchase = _purchase()
        user = SimpleNamespace(id=purchase.user_id, credit_micros_balance=0)
        session = _TopupSession(purchase=purchase, user=user)
        body = json.dumps({"content": purchase.stripe_checkout_session_id}).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )

        assert result["status"] == "amount_unknown"
        assert purchase.status == CreditPurchaseStatus.PENDING
        assert user.credit_micros_balance == 0

    @pytest.mark.asyncio
    async def test_webhook_empty_amount_key_does_not_shadow(self) -> None:
        """An empty/zero earlier candidate key must not shadow a later valid one."""
        purchase = _purchase()
        user = SimpleNamespace(id=purchase.user_id, credit_micros_balance=0)
        session = _TopupSession(purchase=purchase, user=user)
        body = json.dumps(
            {
                "amount": 0,
                "transferAmount": purchase.amount_total,
                "content": purchase.stripe_checkout_session_id,
            }
        ).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )

        assert result["status"] == "credited"

    @pytest.mark.asyncio
    async def test_webhook_refuses_unsafe_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _TopupSession()
        body = json.dumps({"amount": 1, "content": "x"}).encode()

        monkeypatch.delenv("VIETQR_WEBHOOK_SECRET", raising=False)
        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )
        assert result["status"] == "webhook_unconfigured"

        # The public dev placeholder must never fulfil webhooks.
        monkeypatch.setenv("VIETQR_WEBHOOK_SECRET", "test_webhook_secret_key_123")
        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )
        assert result["status"] == "webhook_unconfigured"

    @pytest.mark.asyncio
    async def test_create_intent_rejects_tier_and_amount_together(self) -> None:
        session = _TopupSession()
        with pytest.raises(ValueError):
            await vietqr_topup_service.create_topup_intent(
                session, user_id=uuid4(), tier_id="starter", amount_vnd=990_000
            )

    @pytest.mark.asyncio
    async def test_create_intent_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(vietqr_topup_service.config, "VIETQR_TOPUP_ENABLED", False)
        session = _TopupSession()
        with pytest.raises(ValueError, match="disabled"):
            await vietqr_topup_service.create_topup_intent(
                session, user_id=uuid4(), tier_id="starter"
            )

    @pytest.mark.asyncio
    async def test_create_intent_rejects_nonpositive_rate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(vietqr_topup_service.config, "VIETQR_VND_PER_USD", 0)
        session = _TopupSession()
        with pytest.raises(ValueError):
            await vietqr_topup_service.create_topup_intent(
                session, user_id=uuid4(), amount_vnd=100_000
            )

    @pytest.mark.asyncio
    async def test_create_intent_retries_on_memo_collision(self) -> None:
        from sqlalchemy.exc import IntegrityError

        session = _TopupSession()
        real_commit = session.commit
        calls = {"n": 0}

        async def _flaky_commit() -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise IntegrityError("stmt", {}, Exception("dup memo"))
            await real_commit()

        session.commit = _flaky_commit  # type: ignore[method-assign]

        intent = await vietqr_topup_service.create_topup_intent(
            session, user_id=uuid4(), tier_id="starter"
        )
        assert intent["status"] == "pending"
        assert calls["n"] == 2  # one collision + one successful retry

    @pytest.mark.asyncio
    async def test_webhook_missing_user_fails_intent(self) -> None:
        """A purchase whose wallet owner is gone closes FAILED, not PENDING."""
        purchase = _purchase()
        session = _TopupSession(purchase=purchase, user=None)
        body = json.dumps(
            {
                "amount": purchase.amount_total,
                "content": purchase.stripe_checkout_session_id,
            }
        ).encode()

        result = await vietqr_topup_service.process_transfer_webhook(
            session, raw_body=body, signature=_sign(body)
        )

        assert result["status"] == "user_not_found"
        assert purchase.status == CreditPurchaseStatus.FAILED
