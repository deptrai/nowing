"""Unit tests for Story 37.5: pitch-portal generation + opt-out (AD-119).

Covers AC-1 (deterministic, idempotent build behind the unified SSR route),
AC-3 (Stored-XSS sanitization of prospect fields), AC-4 (Decree 13 self-serve
opt-out purging contacts + DNC + enrollment cancel), and AC-5 (template token
detection + cached URL injection).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.pitch_portal import (
    PITCH_PORTAL_CACHE_TTL_SECONDS,
    build_pitch_portal_url,
    build_portal_content,
    ensure_pitch_portal,
    pitch_portal_cache_key,
    process_pitch_opt_out,
    sanitize_text,
    template_requests_pitch_portal,
)


def _lead(**overrides):
    defaults = {
        "id": uuid4(),
        "workspace_id": 7,
        "company_name": "Công ty LogiTech",
        "industry": "Logistics",
        "location": "TP.HCM",
        "domain": "logitech.vn",
        "consent_status": "legitimate_interest",
        "assigned_to_user_id": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _redis(cached: dict | None = None, raw: str | None = None):
    redis = MagicMock()
    if raw is not None:
        redis.get = AsyncMock(return_value=raw)
    else:
        redis.get = AsyncMock(
            return_value=(
                json.dumps(cached, ensure_ascii=False) if cached else None
            )
        )
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


def _session(scalars_list=None, workspace=None):
    """AsyncSession stand-in.

    ``execute()`` returns a result whose ``scalar_one_or_none`` is None and
    ``scalars().all()`` yields ``scalars_list`` (used for VerifiedContact and
    WorkspaceApp lookups). ``get()`` returns ``workspace``.
    """
    session = AsyncMock()
    session.add = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = scalars_list or []
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=workspace)
    return session


@pytest.mark.unit
class TestSanitizeText:
    """AC-3: Stored XSS sanitization of dynamic prospect fields."""

    def test_strips_script_tag(self):
        assert sanitize_text('<script>alert("x")</script>ABC') == 'alert("x")ABC'

    def test_strips_inline_html(self):
        assert sanitize_text("<b>Công ty</b> <img src=x onerror=1>") == (
            "Công ty"
        )

    def test_stray_brackets_removed(self):
        assert "<" not in sanitize_text("a<b>c")

    def test_caps_length_and_non_str(self):
        assert sanitize_text("x" * 500, max_len=10) == "x" * 10
        assert sanitize_text(None) == ""
        assert sanitize_text(123) == ""


@pytest.mark.unit
class TestTemplateToken:
    """AC-5: {pitch_portal_url} / {{pitch_portal_url}} detection."""

    @pytest.mark.parametrize(
        "template",
        [
            {"body": "Xem portal: {pitch_portal_url}"},
            {"body": "Xem portal: {{pitch_portal_url}}"},
            {"subject": "Hi", "body": "link {pitch_portal_url}"},
            {"template_data": {"url": "{{ pitch_portal_url }}"}},
            {"nested": [{"deep": "{pitch_portal_url}"}]},
        ],
    )
    def test_detects_token(self, template):
        assert template_requests_pitch_portal(template) is True

    @pytest.mark.parametrize(
        "template",
        [
            {"body": "Không có portal"},
            {"body": "{other_var}"},
            {},
            None,
            "plain string without token",
        ],
    )
    def test_ignores_absent_token(self, template):
        assert template_requests_pitch_portal(template) is False


@pytest.mark.unit
class TestPortalBuild:
    """AC-1/AC-5: deterministic URL + idempotent cached build."""

    def test_url_uses_default_base(self):
        lead_id = uuid4()
        url = build_pitch_portal_url("acme", lead_id)
        assert url == f"https://pitch.nowing.ai/acme/{lead_id}"

    def test_url_uses_config_base(self):
        with patch(
            "app.services.pitch_portal.config"
        ) as cfg:
            cfg.PITCH_PORTAL_BASE_URL = "https://pitch.example.com/"
            assert build_pitch_portal_url("1", "abc") == (
                "https://pitch.example.com/1/abc"
            )

    def test_content_sanitized_and_complete(self):
        lead = _lead(
            company_name='<script>alert(1)</script>Công ty ABC',
            industry="Logistics<img>",
        )
        content = build_portal_content(lead)
        assert "script" not in content["headline"].lower() or "<" not in content["headline"]
        assert "<" not in content["exec_summary"]
        assert len(content["exec_cards"]) == 3
        assert content["logo_url"] == (
            "https://www.google.com/s2/favicons?domain=logitech.vn&sz=128"
        )
        assert content["roi"]["default_sales_reps"] == 3

    def test_logo_none_for_bad_domain(self):
        content = build_portal_content(_lead(domain="not a domain!!"))
        assert content["logo_url"] is None

    async def test_ensure_builds_and_caches_on_miss(self):
        lead = _lead()
        redis = _redis()
        session = _session(workspace=SimpleNamespace(name="Nowing"))

        portal = await ensure_pitch_portal(session, redis, lead)

        assert portal["cache_hit"] is False
        assert portal["url"].endswith(f"/{lead.id}")
        assert portal["url"].startswith("https://pitch.nowing.ai/")
        redis.set.assert_awaited_once()
        args, kwargs = redis.set.await_args
        assert args[0] == pitch_portal_cache_key(lead.id)
        assert kwargs["ex"] == PITCH_PORTAL_CACHE_TTL_SECONDS

    async def test_ensure_cache_hit_skips_rebuild(self):
        lead = _lead()
        cached = {
            "version": 1,
            "headline": "cached",
            "roi": {},
            "workspace_ref": "acme",
        }
        redis = _redis(cached=cached)
        session = _session()

        portal = await ensure_pitch_portal(session, redis, lead)

        assert portal["cache_hit"] is True
        assert portal["content"]["headline"] == "cached"
        # The pinned workspace_ref keeps the URL stable — no re-resolution.
        assert portal["url"] == f"https://pitch.nowing.ai/acme/{lead.id}"
        redis.set.assert_not_awaited()
        # No workspace lookup needed when content is cached.
        session.get.assert_not_awaited()
        session.execute.assert_not_awaited()

    async def test_ensure_deterministic_url_across_calls(self):
        lead = _lead()
        first = await ensure_pitch_portal(
            _session(), _redis(), lead
        )
        second = await ensure_pitch_portal(
            _session(), _redis(cached={"version": 1}), lead
        )
        assert first["url"] == second["url"]

    async def test_workspace_ref_pinned_in_cached_blob(self):
        """Republishing a different app must not change an existing URL."""
        lead = _lead()
        session = _session()
        redis = _redis()

        first = await ensure_pitch_portal(session, redis, lead)

        # Simulate a poisoned cache read: blob pinned to a different slug
        # wins over whatever the workspace publishes next.
        blob = json.loads(redis.set.await_args.args[1])
        assert blob["workspace_ref"] == first["url"].split("/")[-2]
        blob["workspace_ref"] = "legacy-slug"
        redis2 = _redis(raw=json.dumps(blob))
        second = await ensure_pitch_portal(session, redis2, lead)
        assert second["url"] == (
            f"https://pitch.nowing.ai/legacy-slug/{lead.id}"
        )

    @pytest.mark.parametrize(
        "poisoned",
        [
            '"just a string"',
            '["not", "a", "dict"]',
            '{"version": 0, "headline": "stale"}',
            '{"headline": "no version"}',
            '{"version": 1, "exec_cards": "oops"}',
            '{"version": 1, "exec_cards": [{"tone": "red"}]}',
            '{"version": 1, "roi": {"default_sales_reps": 99, '
            '"min_sales_reps": 1, "max_sales_reps": 20}}',
        ],
    )
    async def test_poisoned_or_stale_cache_rebuilt(self, poisoned):
        """Malformed/stale cache entries are treated as a miss + overwritten."""
        lead = _lead()
        redis = _redis(raw=poisoned)
        session = _session()

        portal = await ensure_pitch_portal(session, redis, lead)

        assert portal["cache_hit"] is False
        assert portal["content"]["version"] == 1
        redis.set.assert_awaited_once()

    async def test_ensure_tolerates_redis_down(self):
        lead = _lead()
        redis = MagicMock()
        redis.get = AsyncMock(side_effect=ConnectionError("down"))
        redis.set = AsyncMock(side_effect=ConnectionError("down"))
        session = _session(workspace=SimpleNamespace(name="Nowing"))

        portal = await ensure_pitch_portal(session, redis, lead)
        assert portal["url"].endswith(f"/{lead.id}")


@pytest.mark.unit
class TestPitchOptOut:
    """AC-4: Decree 13 self-serve opt-out processing."""

    def _contact(self, **overrides):
        defaults = {
            "id": uuid4(),
            "lead_id": None,
            "workspace_id": 7,
            "phone": "0901234567",
            "email": "ceo@logitech.vn",
            "is_valid": True,
            "is_unlocked": True,
            "consent": True,
            "consent_status": "granted",
            "name": "Anh Nam",
            "title": "CEO",
            "phone_hmac": "h",
            "email_hmac": "h",
            "value_hmac": "h",
            "pii_access_audit_logs": [],
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    async def test_purges_contacts_and_marks_lead(self):
        lead = _lead()
        contact = self._contact(lead_id=lead.id)
        workspace = SimpleNamespace(user_id=uuid4())
        session = _session(scalars_list=[contact], workspace=workspace)
        redis = _redis()

        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            new=AsyncMock(),
        ):
            purged = await process_pitch_opt_out(session, redis, lead=lead)

        assert purged == 1
        # PII anonymized
        assert contact.phone is None
        assert contact.email is None
        assert contact.name is None
        assert contact.consent is False
        assert contact.consent_status == "withdrawn"
        assert contact.pii_access_audit_logs
        # Lead withdrawn + enrollment cancellation issued
        assert lead.consent_status == "withdrawn"
        # Cached portal artifact evicted so the page stops rendering.
        redis.delete.assert_awaited_once_with(pitch_portal_cache_key(lead.id))
        # DNC records + timeline log added to session
        assert session.add.call_count >= 3  # 2 DNC + 1 activity log

    async def test_dnc_records_use_normalized_hmac(self):
        """DNC rows must key on the same HMAC is_blocked() recomputes."""
        from app.db import WorkspaceDncRecord
        from app.lead_intelligence.dnc.normalizer import (
            hash_phone_hmac,
            normalize_email,
            normalize_phone_e164,
        )

        lead = _lead()
        contact = self._contact(lead_id=lead.id)
        workspace = SimpleNamespace(user_id=uuid4())
        session = _session(scalars_list=[contact], workspace=workspace)

        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            new=AsyncMock(),
        ):
            await process_pitch_opt_out(session, _redis(), lead=lead)

        records = [
            call.args[0]
            for call in session.add.call_args_list
            if isinstance(call.args[0], WorkspaceDncRecord)
        ]
        by_type = {r.record_type: r for r in records}
        assert set(by_type) == {"phone", "email"}
        assert by_type["phone"].value_hmac == hash_phone_hmac(
            normalize_phone_e164("0901234567")
        )
        assert by_type["email"].value_hmac == hash_phone_hmac(
            normalize_email("ceo@logitech.vn")
        )
        # Normalized values stored, not masked/raw PII.
        assert by_type["phone"].value == normalize_phone_e164("0901234567")
        assert by_type["email"].value == normalize_email("ceo@logitech.vn")

    async def test_undecryptable_contact_falls_back_to_stored_hmac(self):
        """Decrypt failure still writes a DNC row from the stored blind HMAC."""
        from app.db import WorkspaceDncRecord

        lead = _lead()
        contact = self._contact(
            lead_id=lead.id,
            phone="gAAAAABnot-really-encrypted",
            phone_hmac="stored-phone-hmac",
            email="ceo@logitech.vn",
        )
        workspace = SimpleNamespace(user_id=uuid4())
        session = _session(scalars_list=[contact], workspace=workspace)

        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            new=AsyncMock(),
        ):
            purged = await process_pitch_opt_out(session, _redis(), lead=lead)

        assert purged == 1
        assert contact.phone is None  # anonymized regardless
        phone_records = [
            call.args[0]
            for call in session.add.call_args_list
            if isinstance(call.args[0], WorkspaceDncRecord)
            and call.args[0].record_type == "phone"
        ]
        assert any(
            r.value_hmac == "stored-phone-hmac" for r in phone_records
        )

    async def test_idempotent_second_run(self):
        lead = _lead()
        session = _session(scalars_list=[], workspace=SimpleNamespace())

        purged = await process_pitch_opt_out(session, _redis(), lead=lead)

        assert purged == 0
        assert lead.consent_status == "withdrawn"


@pytest.mark.unit
class TestGenerateStepHandler:
    """AC-5: generate_pitch_portal step executes, logs, and advances."""

    async def test_step_generates_and_advances(self):
        from app.services.sequencer.enrollments import SequencerEnrollmentMixin

        svc = SequencerEnrollmentMixin()
        lead = _lead()
        enrollment = SimpleNamespace(
            id=uuid4(),
            workspace_id=7,
            client_id=None,
            current_step=1,
            status="executing",
            scheduled_at=None,
            version=1,
            last_event_at=None,
            updated_at=None,
        )
        sequence = SimpleNamespace(id=uuid4(), workspace_id=7)
        step = SimpleNamespace(
            id=uuid4(), step_order=1, channel="email", step_type="generate_pitch_portal"
        )

        session = _session()
        portal = {"url": "https://pitch.nowing.ai/7/x", "cache_hit": False}

        # enrollments.py imports both lazily inside the function, so patching
        # the definition site intercepts the call.
        with (
            patch(
                "app.redis_client.get_redis_client", new=AsyncMock(return_value=_redis())
            ),
            patch(
                "app.services.pitch_portal.ensure_pitch_portal",
                new=AsyncMock(return_value=portal),
            ),
            patch.object(
                svc, "_advance_to_next_step", new=AsyncMock()
            ) as mock_advance,
        ):
            event = await svc._handle_generate_pitch_portal_step(
                session, sequence, step, enrollment, lead
            )

        assert event.event_subtype == "pitch_portal_generated"
        assert event.event_metadata["pitch_portal_url"] == portal["url"]
        mock_advance.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_step_advances_on_failure(self):
        from app.services.sequencer.enrollments import SequencerEnrollmentMixin

        svc = SequencerEnrollmentMixin()
        lead = _lead()
        enrollment = SimpleNamespace(
            id=uuid4(), workspace_id=7, client_id=None, current_step=1,
            status="executing", scheduled_at=None, version=1,
            last_event_at=None, updated_at=None,
        )
        sequence = SimpleNamespace(id=uuid4(), workspace_id=7)
        step = SimpleNamespace(
            id=uuid4(), step_order=1, channel="email",
            step_type="generate_pitch_portal",
        )
        session = _session()

        with (
            patch(
                "app.services.pitch_portal.ensure_pitch_portal",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch.object(svc, "_advance_to_next_step", new=AsyncMock()) as mock_advance,
        ):
            event = await svc._handle_generate_pitch_portal_step(
                session, sequence, step, enrollment, lead
            )

        assert event.event_subtype == "pitch_portal_build_failed"
        mock_advance.assert_awaited_once()


@pytest.mark.unit
class TestDispatchInjection:
    """AC-5: {pitch_portal_url} is injected into send-step context vars."""

    async def test_token_absent_returns_none_without_build(self):
        from app.services.sequencer.dispatch import SequencerDispatchMixin

        svc = SequencerDispatchMixin()
        with patch(
            "app.services.pitch_portal.ensure_pitch_portal", new=AsyncMock()
        ) as mock_ensure:
            result = await svc._resolve_pitch_portal_url(
                _session(), _lead(), {"body": "no portal here"}
            )
        assert result is None
        mock_ensure.assert_not_awaited()

    async def test_token_present_builds_and_returns_url(self):
        from app.services.sequencer.dispatch import SequencerDispatchMixin

        svc = SequencerDispatchMixin()
        svc._get_redis_async = AsyncMock(return_value=_redis())
        portal = {"url": "https://pitch.nowing.ai/7/x", "cache_hit": True}
        with patch(
            "app.services.pitch_portal.ensure_pitch_portal",
            new=AsyncMock(return_value=portal),
        ) as mock_ensure:
            result = await svc._resolve_pitch_portal_url(
                _session(),
                _lead(),
                {"body": "Xem báo cáo: {{pitch_portal_url}}"},
            )
        assert result == portal["url"]
        mock_ensure.assert_awaited_once()

    async def test_send_step_dispatches_interpolated_portal_url(self):
        """AC-5: the provider-visible body contains the generated URL."""
        from app.services.sequencer_service import SequencerService

        sequencer = SequencerService()
        session = _session()
        portal_url = "https://pitch.nowing.ai/7/abc"
        lead = MagicMock(
            id=uuid4(),
            workspace_id=1,
            consent_status="opted_in",
            legal_basis="legitimate_interest",
            custom_fields={},
        )
        contact = MagicMock(
            consent=True,
            is_valid=True,
            email="test@example.com",
            external_chat_ids={},
            name=None,
            title=None,
            phone=None,
        )
        sequence = MagicMock(
            id=uuid4(), created_by_user_id=uuid4(), workspace_id=1
        )
        step = MagicMock(
            id=uuid4(),
            channel="email",
            step_order=1,
            template={
                "subject": "Hi",
                "body": "Xem {pitch_portal_url}",
            },
            fallback_channels=[],
        )
        enrollment = MagicMock(
            id=uuid4(),
            workspace_id=1,
            client_id="default",
            current_step=1,
            version=0,
        )

        with (
            patch.object(
                sequencer, "_resolve_verified_contact", return_value=contact
            ),
            patch.object(
                sequencer, "check_outbound_compliance", return_value=True
            ),
            patch.object(
                sequencer,
                "get_billing_event_for_step",
                return_value={"cost_micros": 0, "event_type": "email_send"},
            ),
            patch.object(
                sequencer, "_get_redis_async", new=AsyncMock(return_value=_redis())
            ),
            patch.object(
                sequencer, "_send_email_dispatch", new=AsyncMock(return_value="msg_1")
            ) as mock_send,
            patch.object(
                sequencer, "_advance_to_next_step", new=AsyncMock()
            ),
            patch.object(
                sequencer.billing_service,
                "record_sequence_send",
                new=AsyncMock(),
            ),
            patch(
                "app.services.sequencer.dispatch.is_dispatch_curfew",
                return_value=False,
            ),
            patch(
                "app.services.sequencer.dispatch.workspace_sender_demographics",
                new=AsyncMock(return_value=(None, None)),
            ),
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.is_blocked",
                new=AsyncMock(return_value=MagicMock(is_blocked=False)),
            ),
            patch(
                "app.services.pitch_portal.ensure_pitch_portal",
                new=AsyncMock(
                    return_value={"url": portal_url, "cache_hit": True}
                ),
            ),
        ):
            event = await sequencer._handle_send_step(
                session=session,
                sequence=sequence,
                step=step,
                enrollment=enrollment,
                lead=lead,
            )

        assert event.event_type == "sent"
        mock_send.assert_awaited_once()
        assert portal_url in mock_send.await_args.kwargs["body"]


@pytest.mark.unit
class TestDoubleBraceInterpolation:
    """AC-5 spec syntax: {{pitch_portal_url}} interpolates like {var}."""

    def test_double_brace_replaced(self):
        from app.services.sequencer.templates import (
            interpolate_template_variables,
        )

        out = interpolate_template_variables(
            "Portal: {{pitch_portal_url}}",
            {"pitch_portal_url": "https://pitch.nowing.ai/1/x"},
        )
        assert out == "Portal: https://pitch.nowing.ai/1/x"

    def test_single_brace_still_works(self):
        from app.services.sequencer.templates import (
            interpolate_template_variables,
        )

        out = interpolate_template_variables(
            "{company} — {pitch_portal_url}",
            {"company": "ABC", "pitch_portal_url": "u"},
        )
        assert out == "ABC — u"
