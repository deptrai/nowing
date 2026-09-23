"""Unit tests for Story 37.2: Vietnam Cultural Honorific & Relationship Tone Engine.

Covers:
- AC-1: Deterministic honorific resolution (CCCD/MST birth year, graduation year,
  title seniority) per AD-116 — 0ms latency, $0 token cost.
- AC-2: ``{salutation}`` token injection into sequence-step template context.
- AC-3: Anti-translation quality gate + foreign/ambiguous fallbacks.
- AC-4: Decree 91/2020/NĐ-CP curfew — dispatch halted 21:00-08:00 ICT.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.unit

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None, rowcount: int = 1) -> None:
        self._value = value
        self._rows = rows or []
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if not getattr(obj, "id", None):
                obj.id = uuid4()

    async def execute(self, _stmt: Any, _params: Any | None = None) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def get(self, _model: Any, _ident: Any) -> Any:
        return self._scalar


# ============================================================================
# AC-1: Deterministic Honorific Resolution
# ============================================================================


class TestVietnamHonorificResolver:
    """AC-1: Age/title → (prospect, sender) pronoun pair resolution."""

    def _resolver(self):
        from app.services.sequencer.honorifics import VietnamHonorificResolver

        return VietnamHonorificResolver()

    def test_cccd_extracts_birth_year_and_gender_female(self) -> None:
        """CCCD digit 4 encodes century+gender; digits 5-6 encode birth year."""
        # digits[3]='1' → 1900s female; digits[4:6]='90' → 1990.
        res = self._resolver().resolve(
            profile={"name": "Nguyễn Lan", "cccd": "031190000123"},
            sender_birth_year=1995,
        )
        assert res.prospect_birth_year == 1990
        assert res.prospect_pronoun == "Chị"
        assert res.sender_pronoun == "Em"
        assert res.salutation == "Chị Lan"

    def test_cccd_extracts_birth_year_and_gender_male(self) -> None:
        # digits[3]='0' → 1900s male; '85' → 1985.
        res = self._resolver().resolve(
            profile={"name": "Trần Minh", "cccd": "079085001122"},
            sender_birth_year=1995,
        )
        assert res.prospect_birth_year == 1985
        assert res.prospect_pronoun == "Anh"
        assert res.sender_pronoun == "Em"
        assert res.salutation == "Anh Minh"

    def test_graduation_year_infers_birth_year(self) -> None:
        """Graduation year 2010 → estimated birth year ≈ 1988 (22 at graduation)."""
        res = self._resolver().resolve(
            profile={"name": "Lê Văn Hùng", "graduation_year": "2010"},
            sender_birth_year=1995,
        )
        assert res.prospect_birth_year == 1988
        assert res.prospect_pronoun == "Anh"
        assert res.sender_pronoun == "Em"

    def test_senior_title_maps_to_anh_em_pair(self) -> None:
        res = self._resolver().resolve(
            profile={"name": "Phạm Thị Hoa", "title": "Giám đốc kinh doanh"},
        )
        assert res.prospect_pronoun == "Chị"
        assert res.sender_pronoun == "Em"
        assert res.salutation == "Chị Hoa"
        assert res.reason == "senior_title"

    def test_clearly_younger_prospect_maps_to_em(self) -> None:
        """Prospect ≥5y younger than the sender is addressed as 'Em'."""
        res = self._resolver().resolve(
            profile={"name": "Vũ Đức Anh", "birth_year": "2002"},
            sender_birth_year=1990,
            sender_gender="male",
        )
        assert res.prospect_pronoun == "Em"
        assert res.sender_pronoun == "Anh"
        assert res.salutation == "Em Anh"

    def test_junior_title_maps_to_em(self) -> None:
        res = self._resolver().resolve(
            profile={
                "name": "Đỗ Văn Nam",
                "title": "Nhân viên kinh doanh",
                "birth_year": "2001",
            },
            sender_birth_year=1990,
        )
        assert res.prospect_pronoun == "Em"
        assert res.sender_pronoun == "Anh"


# ============================================================================
# AC-3: Foreign fallback, ambiguous fallback, anti-translation gate
# ============================================================================


class TestForeignAndAmbiguousFallback:
    def _resolver(self):
        from app.services.sequencer.honorifics import VietnamHonorificResolver

        return VietnamHonorificResolver()

    def test_foreign_contact_international_domain_male(self) -> None:
        res = self._resolver().resolve(
            profile={
                "name": "John Smith",
                "email": "john@acme.com",
                "gender": "male",
            }
        )
        assert res.tone == "en"
        assert res.salutation == "Dear Mr. Smith"
        assert res.sender_pronoun == "We"

    def test_foreign_contact_unknown_gender(self) -> None:
        res = self._resolver().resolve(
            profile={"name": "Alex Tan", "domain": "acme.sg"}
        )
        assert res.tone == "en"
        assert res.salutation == "Dear Mr./Ms. Tan"

    def test_vietnamese_domain_not_foreign(self) -> None:
        res = self._resolver().resolve(
            profile={
                "name": "John Nguyen",
                "email": "john@company.vn",
            }
        )
        # .vn domain keeps the VN pipeline (Nguyen is a VN surname anyway).
        assert res.tone == "vi"

    def test_ambiguous_gender_falls_back_to_quy_anh_chi(self) -> None:
        """VN name without gender markers → neutral 'Quý anh/chị'."""
        res = self._resolver().resolve(
            profile={"name": "Nguyễn Minh"},  # 'Minh' is unisex; no middle marker
        )
        assert res.prospect_pronoun == "Quý anh/chị"
        assert res.sender_pronoun == "Chúng tôi"
        assert "Quý anh/chị" in res.salutation

    def test_no_contact_name_falls_back_to_quy_doi_tac(self) -> None:
        lead = MagicMock(company_name="Công ty TNHH ABC", custom_fields={})
        # MagicMock auto-attrs are not str → resolver ignores them.
        res = self._resolver().resolve(lead=lead)
        assert res.prospect_pronoun == "Quý đối tác"
        assert res.sender_pronoun == "Chúng tôi"
        assert res.salutation == "Quý đối tác"


class TestHonorificQualityGate:
    """AC-3: Reject robotic direct translations (Bạn/Tôi)."""

    def test_ban_pronoun_rejected(self) -> None:
        from app.services.sequencer.honorifics import HonorificQualityGate

        assert HonorificQualityGate.is_robotic("Chào bạn, bạn có khỏe không?")
        assert HonorificQualityGate.is_robotic("Bạn có thể xem báo giá")

    def test_toi_self_reference_rejected(self) -> None:
        from app.services.sequencer.honorifics import HonorificQualityGate

        assert HonorificQualityGate.is_robotic("Tôi xin gửi bạn bảng giá")

    def test_accentless_robotic_pronouns_rejected(self) -> None:
        """NFD-normalized matching catches diacritic-less machine output."""
        from app.services.sequencer.honorifics import HonorificQualityGate

        assert HonorificQualityGate.is_robotic("Chao ban, ban co khoe khong?")
        assert HonorificQualityGate.is_robotic("Toi xin gui ban bao gia")

    def test_legitimate_toi_phrases_accepted(self) -> None:
        """'theo tôi', 'với tôi', 'cho tôi', 'chúng tôi' are allowed."""
        from app.services.sequencer.honorifics import HonorificQualityGate

        assert HonorificQualityGate.is_acceptable(
            "Theo tôi, giá này rất hợp lý cho anh."
        )
        assert HonorificQualityGate.is_acceptable(
            "Với tôi thì căn này phù hợp nhu cầu chị."
        )
        assert HonorificQualityGate.is_acceptable(
            "Anh cho tôi xin số điện thoại được không ạ?"
        )
        assert HonorificQualityGate.is_acceptable(
            "Của tôi là báo giá mới nhất từ chủ đầu tư."
        )

    def test_legitimate_ban_compounds_accepted(self) -> None:
        """'ban giám đốc' / 'ban tổ chức' are not the robotic pronoun."""
        from app.services.sequencer.honorifics import HonorificQualityGate

        assert HonorificQualityGate.is_acceptable(
            "Ban giám đốc đã phê duyệt chính sách mới."
        )
        assert HonorificQualityGate.is_acceptable(
            "Ban tổ chức sự kiện sẽ liên hệ anh sau."
        )

    def test_chung_toi_accepted(self) -> None:
        from app.services.sequencer.honorifics import HonorificQualityGate

        assert HonorificQualityGate.is_acceptable(
            "Dạ em chào anh, chúng tôi xin gửi báo giá chi tiết ạ."
        )
        assert HonorificQualityGate.is_acceptable("")


# ============================================================================
# AC-4: Decree 91 curfew (21:00 - 08:00 ICT)
# ============================================================================


class TestDecree91Curfew:
    def test_curfew_window(self) -> None:
        from app.services.sequencer.scheduling import is_dispatch_curfew

        assert is_dispatch_curfew(datetime(2026, 9, 17, 22, 0, tzinfo=VN_TZ))
        assert is_dispatch_curfew(datetime(2026, 9, 17, 21, 0, tzinfo=VN_TZ))
        assert is_dispatch_curfew(datetime(2026, 9, 17, 7, 59, tzinfo=VN_TZ))
        assert not is_dispatch_curfew(datetime(2026, 9, 17, 8, 0, tzinfo=VN_TZ))
        assert not is_dispatch_curfew(datetime(2026, 9, 17, 20, 59, tzinfo=VN_TZ))
        assert not is_dispatch_curfew(datetime(2026, 9, 17, 12, 0, tzinfo=VN_TZ))

    def test_eta_at_21_30_pushes_to_next_morning(self) -> None:
        """A target at/after 21:00 must roll to next-day 08:05 + jitter."""
        from app.services.sequencer_service import calculate_step_eta

        base = datetime(2026, 9, 17, 20, 0, tzinfo=VN_TZ)
        with patch("random.randint", return_value=300):
            result = calculate_step_eta(delay_seconds=5400, from_dt=base)  # 21:30

        assert result.date() == datetime(2026, 9, 18, tzinfo=VN_TZ).date()
        assert result.hour == 8 and result.minute == 10

    async def test_send_step_deferred_during_curfew(self) -> None:
        """Dispatch halts in curfew: skipped event + re-scheduled enrollment."""
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()

        lead = MagicMock(
            id=uuid4(), workspace_id=1, consent_status="opted_in",
            legal_basis="legitimate_interest", custom_fields={},
        )
        # NOTE: `name` is a reserved MagicMock kwarg — assign it after construction.
        contact = MagicMock(
            consent=True, is_valid=True, email="lan@company.vn",
            title="Giám đốc", phone=None, external_chat_ids={},
        )
        contact.name = "Nguyễn Thị Lan"
        sequence = MagicMock(id=uuid4(), created_by_user_id=uuid4(), workspace_id=1)
        step = MagicMock(
            id=uuid4(), channel="email", step_order=1,
            template={}, wait_duration_seconds=0,
        )
        enrollment = MagicMock(
            workspace_id=1, client_id="default", id=uuid4(),
            current_step=1, version=1, status="executing", scheduled_at=None,
        )

        with (
            patch.object(
                sequencer, "_resolve_verified_contact", return_value=contact
            ),
            patch.object(
                sequencer, "check_outbound_compliance",
                new_callable=AsyncMock, return_value=True,
            ),
            patch(
                "app.services.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.sequencer.dispatch.is_dispatch_curfew",
                return_value=True,
            ),
        ):
            event = await sequencer._handle_send_step(
                session=session, sequence=sequence, step=step,
                enrollment=enrollment, lead=lead,
            )

        assert event.event_type == "skipped"
        assert event.event_subtype == "curfew_decree91"
        assert enrollment.status == "scheduled"
        assert enrollment.scheduled_at is not None


# ============================================================================
# AC-2: {salutation} context injection
# ============================================================================


class TestSalutationInjection:
    async def test_context_vars_include_salutation(self) -> None:
        """Send step injects resolved honorific under the {salutation} token."""
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()

        lead = MagicMock(
            id=uuid4(), workspace_id=1, consent_status="opted_in",
            legal_basis="legitimate_interest", custom_fields={},
        )
        # NOTE: `name` is a reserved MagicMock kwarg — assign it after construction.
        contact = MagicMock(
            consent=True, is_valid=True, email="lan@company.vn",
            title="Giám đốc", phone=None, external_chat_ids={},
        )
        contact.name = "Nguyễn Thị Lan"
        sequence = MagicMock(id=uuid4(), created_by_user_id=uuid4(), workspace_id=1)
        step = MagicMock(
            id=uuid4(), channel="email", step_order=1,
            template={"subject": "Chào {salutation}", "body": "Kính gửi {salutation}"},
        )
        enrollment = MagicMock(
            workspace_id=1, client_id="default", id=uuid4(),
            current_step=1, version=1, status="executing", scheduled_at=None,
        )

        captured: dict[str, Any] = {}

        async def _fake_dispatch(**kwargs: Any):
            captured.update(kwargs)
            return "msg_test", "email"

        with (
            patch.object(
                sequencer, "_resolve_verified_contact", return_value=contact
            ),
            patch.object(
                sequencer, "check_outbound_compliance",
                new_callable=AsyncMock, return_value=True,
            ),
            patch(
                "app.services.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.sequencer.dispatch.is_dispatch_curfew",
                return_value=False,
            ),
            patch.object(
                sequencer, "_dispatch_single_channel", side_effect=_fake_dispatch
            ),
            patch.object(
                sequencer.billing_service, "record_sequence_send",
                new_callable=AsyncMock,
            ),
            patch.object(
                sequencer, "_advance_to_next_step", new_callable=AsyncMock
            ),
        ):
            event = await sequencer._handle_send_step(
                session=session, sequence=sequence, step=step,
                enrollment=enrollment, lead=lead,
            )

        assert event is not None and event.event_type == "sent"
        ctx = captured["context_vars"]
        # 'Nguyễn Thị Lan' + senior title 'Giám đốc' → Chị - Em pair.
        assert ctx["salutation"] == "Chị Lan"
        assert ctx["prospect_pronoun"] == "Chị"
        assert ctx["sender_pronoun"] == "Em"

    def test_salutation_token_interpolates_in_template(self) -> None:
        from app.services.sequencer_service import interpolate_template_variables

        out = interpolate_template_variables(
            "Kính gửi {salutation}, em là tư vấn viên Nowing.",
            {"salutation": "Anh Minh"},
        )
        assert out == "Kính gửi Anh Minh, em là tư vấn viên Nowing."

    async def test_resolve_honorific_context_on_inbound(self) -> None:
        """inbound.resolve_honorific_context exposes {salutation} for replies."""
        from app.services.sequencer_service import SequencerService

        sequencer = SequencerService()
        session = _FakeSession(scalar=None)
        # NOTE: `name` is a reserved MagicMock kwarg — assign it after construction.
        contact = MagicMock(
            lead_id=uuid4(), consent=True, is_valid=True,
            title="Trưởng phòng",
        )
        contact.name = "Trần Văn Bình"

        with patch.object(
            sequencer, "_resolve_inbound_contact",
            new_callable=AsyncMock, return_value=contact,
        ):
            ctx = await sequencer.resolve_honorific_context(
                session, workspace_id=1, email="binh@company.vn"
            )

        assert ctx["salutation"] == "Anh Bình"
        assert ctx["prospect_pronoun"] == "Anh"
        assert ctx["sender_pronoun"] == "Em"


# ============================================================================
# Review-fix regressions
# ============================================================================


class TestForeignDetectionFreemail:
    """Free-mail domains are NOT foreign evidence; nationality synonyms OK."""

    def _resolver(self):
        from app.services.sequencer.honorifics import VietnamHonorificResolver

        return VietnamHonorificResolver()

    def test_gmail_domain_not_foreign(self) -> None:
        res = self._resolver().resolve(
            profile={"name": "Linda Hoang", "email": "linda@gmail.com"}
        )
        # 'Hoang' is a VN surname → VN pipeline (gender ambiguous → Quý anh/chị).
        assert res.tone == "vi"

    def test_non_vn_name_gmail_stays_vn_pipeline(self) -> None:
        res = self._resolver().resolve(
            profile={"name": "Emily Watson", "email": "emily@gmail.com"}
        )
        # gmail.com is free-mail → no foreign signal → stays vi, neutral tone.
        assert res.tone == "vi"
        assert res.prospect_pronoun == "Quý anh/chị"

    def test_corporate_domain_is_foreign(self) -> None:
        res = self._resolver().resolve(
            profile={"name": "Emily Watson", "email": "emily@acme-global.com"}
        )
        assert res.tone == "en"
        assert res.salutation == "Dear Mr./Ms. Watson"

    @pytest.mark.parametrize("nat", ["vietnamese", "vi", "việt", "vietnam", "vn"])
    def test_vietnamese_nationality_synonyms(self, nat: str) -> None:
        res = self._resolver().resolve(
            profile={
                "name": "Emily Watson",
                "email": "emily@acme-global.com",
                "nationality": nat,
            }
        )
        assert res.tone == "vi"


class TestCollectPrecedenceAndGender:
    def _resolver(self):
        from app.services.sequencer.honorifics import VietnamHonorificResolver

        return VietnamHonorificResolver()

    def test_contact_overrides_lead_fields(self) -> None:
        """Contact name/title/email/phone beat the less reliable lead values."""
        lead = MagicMock(
            contact_name="Wrong Name", legal_representative=None,
            custom_fields={"title": "Nhân viên"}, domain=None, tax_id=None,
            extra_data={},
        )
        contact = MagicMock(
            email=None, phone=None, external_chat_ids={},
        )
        contact.name = "Nguyễn Thị Lan"
        contact.title = "Giám đốc"

        res = self._resolver().resolve(lead=lead, contact=contact)
        # Contact name wins → salutation uses 'Lan', not 'Name'.
        assert res.contact_name == "Nguyễn Thị Lan"
        assert res.salutation == "Chị Lan"
        assert res.reason == "senior_title"

    def test_mst_does_not_infer_birth_year(self) -> None:
        """MST is an org tax id — it must not produce a birth year."""
        res = self._resolver().resolve(
            profile={"name": "Nguyễn Văn An", "mst": "0312345678-1985"},
        )
        assert res.prospect_birth_year is None

    @pytest.mark.parametrize("sender_gender", ["f", "nu", "nữ", "female"])
    def test_sender_gender_synonyms_female(self, sender_gender: str) -> None:
        res = self._resolver().resolve(
            profile={"name": "Vũ Đức Anh", "birth_year": "2002"},
            sender_birth_year=1990,
            sender_gender=sender_gender,
        )
        assert res.sender_pronoun == "Chị"


class TestCurfewDeferralWindow:
    async def test_deferral_schedules_next_0805_window(self) -> None:
        """Curfew deferral lands in the next 08:05 + jitter ICT window."""
        from app.services.sequencer import scheduling as sched
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()
        sequence = MagicMock(id=uuid4())
        step = MagicMock(id=uuid4())
        enrollment = MagicMock(
            workspace_id=1, client_id="default", id=uuid4(),
            version=1, status="executing",
        )

        real_calc = sched.calculate_step_eta
        curfew_now = datetime(2026, 9, 17, 22, 30, tzinfo=VN_TZ)

        with (
            patch(
                "app.services.sequencer.dispatch.calculate_step_eta",
                side_effect=lambda delay, from_dt=None: real_calc(
                    delay, from_dt or curfew_now
                ),
            ),
            patch("random.randint", return_value=0),
        ):
            event = await sequencer._defer_step_for_curfew(
                session, sequence, step, enrollment, channel="email"
            )

        assert event.event_subtype == "curfew_decree91"
        vn_dt = enrollment.scheduled_at.astimezone(VN_TZ)
        assert vn_dt.date() == datetime(2026, 9, 18, tzinfo=VN_TZ).date()
        assert (vn_dt.hour, vn_dt.minute) == (8, 5)

    async def test_deferral_skipped_when_enrollment_moved_on(self) -> None:
        """rowcount=0 (opt-out/version bump) → enrollment state untouched."""
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()

        async def _no_rows(_stmt: Any, _params: Any | None = None) -> _FakeResult:
            return _FakeResult(rowcount=0)

        session.execute = _no_rows
        sequencer = SequencerService()
        enrollment = MagicMock(
            workspace_id=1, client_id="default", id=uuid4(),
            version=2, status="unsubscribed", scheduled_at=None,
        )

        with patch("random.randint", return_value=0):
            event = await sequencer._defer_step_for_curfew(
                session, MagicMock(id=uuid4()), MagicMock(id=uuid4()),
                enrollment, channel="zalo",
            )

        # Opt-out state must survive — no overwrite back to "scheduled".
        assert enrollment.status == "unsubscribed"
        assert event.event_metadata["rescheduled_at"] is None


class TestZnsTemplateInterpolation:
    async def test_zalo_dispatch_interpolates_nested_template_data(self) -> None:
        """Nested dicts/lists in ZNS template_data get {salutation} values."""
        from app.services.sequencer_service import SequencerService

        sequencer = SequencerService()
        session = _FakeSession()
        contact = MagicMock(
            phone="+84909123456", email=None, external_chat_ids={},
        )
        template_data = {
            "template_id": "T1",
            "template_data": {
                "customer_name": "{salutation}",
                "nested": {"x": "{salutation}", "n": 5},
                "list": ["{salutation}", 7],
            },
        }
        context_vars = {"salutation": "Chị Lan"}

        with (
            patch(
                "app.services.sequencer.dispatch.DncComplianceService.is_blocked",
                new_callable=AsyncMock,
                return_value=MagicMock(is_blocked=False),
            ),
            patch.object(
                sequencer, "_send_zns_dispatch",
                new_callable=AsyncMock, return_value="zns_1",
            ) as mock_send,
        ):
            msg_id, used = await sequencer._dispatch_single_channel(
                session=session,
                sequence=MagicMock(id=uuid4()),
                step=MagicMock(id=uuid4()),
                enrollment=MagicMock(id=uuid4(), workspace_id=1),
                lead=MagicMock(id=uuid4()),
                contact=contact,
                channel="zalo",
                template_data=template_data,
                context_vars=context_vars,
                attributed_user_id=None,
                cost_micros=0,
            )

        assert used == "zalo" and msg_id == "zns_1"
        sent = mock_send.await_args.kwargs["template_data"]
        assert sent == {
            "customer_name": "Chị Lan",
            "nested": {"x": "Chị Lan", "n": 5},
            "list": ["Chị Lan", 7],
        }

    async def test_zalo_dispatch_tolerates_list_template_data(self) -> None:
        """zalo_data may be a list — no .items() crash."""
        from app.services.sequencer_service import SequencerService

        sequencer = SequencerService()
        contact = MagicMock(
            phone="+84909123456", email=None, external_chat_ids={},
        )
        with (
            patch(
                "app.services.sequencer.dispatch.DncComplianceService.is_blocked",
                new_callable=AsyncMock,
                return_value=MagicMock(is_blocked=False),
            ),
            patch.object(
                sequencer, "_send_zns_dispatch",
                new_callable=AsyncMock, return_value="zns_1",
            ) as mock_send,
        ):
            await sequencer._dispatch_single_channel(
                session=_FakeSession(),
                sequence=MagicMock(id=uuid4()),
                step=MagicMock(id=uuid4()),
                enrollment=MagicMock(id=uuid4(), workspace_id=1),
                lead=MagicMock(id=uuid4()),
                contact=contact,
                channel="zalo",
                template_data={
                    "template_id": "T1",
                    "template_data": ["{salutation}"],
                },
                context_vars={"salutation": "Anh Minh"},
                attributed_user_id=None,
                cost_micros=0,
            )

        assert mock_send.await_args.kwargs["template_data"] == ["Anh Minh"]


class TestAutoReplyHonorific:
    async def test_llm_response_robotic_rejection_still_records_usage(self) -> None:
        """Robotic gate returns '' AFTER token usage is recorded (AC-3)."""
        from app.services.auto_reply_agent import AutoReplyAgent

        agent = AutoReplyAgent()

        response = MagicMock()
        response.choices = [
            MagicMock(message=MagicMock(content="Chào bạn, tôi xin gửi báo giá"))
        ]
        response.usage = MagicMock(
            prompt_tokens=10, completion_tokens=20, total_tokens=30
        )
        response.model = "test-model"
        router = MagicMock()
        router.acompletion = AsyncMock(return_value=response)

        session = _FakeSession()
        with (
            patch(
                "app.services.llm_router_service.LLMRouterService.get_router",
                return_value=router,
            ),
            patch(
                "app.services.auto_reply_agent.record_token_usage",
                new_callable=AsyncMock,
            ) as mock_record,
        ):
            out = await agent._generate_llm_response(
                "câu hỏi", "context",
                session=session, workspace_id=15, user_id=uuid4(),
            )

        assert out == ""
        mock_record.assert_awaited_once()

    async def test_generate_reply_passes_honorific_to_llm(self) -> None:
        """Resolved honorific pair reaches _generate_llm_response (AC-2)."""
        from app.services.auto_reply_agent import AutoReplyAgent
        from app.services.sequencer.honorifics import HonorificResolution

        agent = AutoReplyAgent()
        resolution = HonorificResolution(
            salutation="Chị Lan", prospect_pronoun="Chị",
            sender_pronoun="Em", reason="senior_title",
        )
        session = _FakeSession()

        with (
            patch.object(
                agent, "_retrieve_knowledge_chunks",
                new_callable=AsyncMock,
                return_value=[{"content": "Báo giá chi tiết", "similarity": 0.9}],
            ),
            patch.object(
                agent, "_resolve_honorific",
                new_callable=AsyncMock, return_value=resolution,
            ),
            patch.object(
                agent, "_generate_llm_response",
                new_callable=AsyncMock, return_value="Dạ chị Lan",
            ) as mock_gen,
        ):
            result = await agent.generate_reply(
                workspace_id=1, channel="zalo", sender_id="sid_1",
                text="cho chị xin báo giá", fallback_text="fallback",
                session=session,
            )

        assert result.reply_text == "Dạ chị Lan"
        assert mock_gen.await_args.kwargs["honorific"] is resolution


class TestWorkspaceSenderDemographics:
    """Per-workspace sender profile overrides SEQUENCER_SENDER_* envs."""

    async def test_workspace_settings_override_env(self, monkeypatch) -> None:
        import types

        from app.services.sequencer.honorifics import (
            workspace_sender_demographics,
        )

        monkeypatch.setenv("SEQUENCER_SENDER_BIRTH_YEAR", "1980")
        workspace = types.SimpleNamespace(
            icp_criteria={
                "sequencer_sender_birth_year": "1996",
                "sequencer_sender_gender": "female",
            }
        )
        session = _FakeSession(scalar=workspace)
        year, gender = await workspace_sender_demographics(session, 1)
        assert year == 1996
        assert gender == "female"

    async def test_missing_workspace_settings_returns_nones(self) -> None:
        import types

        from app.services.sequencer.honorifics import (
            workspace_sender_demographics,
        )

        session = _FakeSession(scalar=types.SimpleNamespace(icp_criteria=None))
        assert await workspace_sender_demographics(session, 1) == (None, None)

    async def test_lookup_failure_is_fail_open(self) -> None:
        from app.services.sequencer.honorifics import (
            workspace_sender_demographics,
        )

        class _BoomSession(_FakeSession):
            async def get(self, *_a: Any, **_k: Any) -> Any:
                raise RuntimeError("db down")

        assert await workspace_sender_demographics(_BoomSession(), 1) == (
            None,
            None,
        )

    async def test_resolver_falls_back_to_env_when_workspace_unset(
        self, monkeypatch
    ) -> None:
        """Workspace without sender keys → global env defaults still apply."""
        import types

        from app.config import config
        from app.services.sequencer.honorifics import (
            VietnamHonorificResolver,
            workspace_sender_demographics,
        )

        # Config attrs are read at import time — patch the attr, not env.
        monkeypatch.setattr(config, "SEQUENCER_SENDER_BIRTH_YEAR", 1980)
        session = _FakeSession(
            scalar=types.SimpleNamespace(icp_criteria={})
        )
        year, gender = await workspace_sender_demographics(session, 1)
        res = VietnamHonorificResolver().resolve(
            profile={
                "name": "Nguyễn Lan",
                "birth_year": 1970,
                "gender": "female",
            },
            sender_birth_year=year,
            sender_gender=gender,
        )
        # env sender 1980 is younger than the 1970 prospect → sender "Em".
        assert res.prospect_pronoun == "Chị"
        assert res.sender_pronoun == "Em"
