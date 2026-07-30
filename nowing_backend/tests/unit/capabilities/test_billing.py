"""Billing charges the workspace owner once per billable success at the executor (03c).

Boundaries mocked: the DB session and the audit helper. NOT mocked: the real
WebCrawlCreditService debit math and the owner-billed decision.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

import app.capabilities.core.billing as billing
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.capabilities.web.crawl.schemas import CrawlInput, CrawlItem, CrawlOutput
from app.config import config
from app.services.web_crawl_credit_service import InsufficientCreditsError

pytestmark = pytest.mark.unit

_WORKSPACE_ID = 1
_OWNER = UUID("00000000-0000-0000-0000-0000000000bb")


class _FakeUser:
    def __init__(self, balance_micros: int, reserved_micros: int = 0):
        self.credit_micros_balance = balance_micros
        self.credit_micros_reserved = reserved_micros


def _make_session(owner_id, balance_micros):
    """Mock session serving owner-resolution and the charge_credits debit."""
    fake_user = _FakeUser(balance_micros)
    session = AsyncMock()
    session.add = MagicMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = owner_id  # owner resolution
        result.unique.return_value.scalar_one_or_none.return_value = fake_user  # debit
        result.first.return_value = (balance_micros, 0)  # spendable_micros
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user


def _output(*statuses: str) -> CrawlOutput:
    return CrawlOutput(
        items=[
            CrawlItem(url=f"https://{i}.com", status=status)
            for i, status in enumerate(statuses)
        ]
    )


def _ctx(session) -> CapabilityContext:
    return CapabilityContext(session=session, workspace_id=_WORKSPACE_ID)


@pytest.fixture(autouse=True)
def _stub_auto_reload(monkeypatch):
    import app.services.auto_reload_service as ar

    monkeypatch.setattr(ar, "maybe_trigger_auto_reload", AsyncMock())


@pytest.fixture
def record_usage(monkeypatch):
    rec = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(billing, "record_token_usage", rec)
    return rec


async def test_charges_workspace_owner_per_successful_crawl(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output("success", "empty", "success"), BillingUnit.WEB_CRAWL, _ctx(session)
    )

    # Owner debited 2 * 1000; one web_crawl audit row billed to the OWNER.
    assert user.credit_micros_balance == 100_000 - 2000
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "web_crawl"
    assert kwargs["user_id"] == _OWNER
    assert kwargs["workspace_id"] == _WORKSPACE_ID
    assert kwargs["cost_micros"] == 2000


def _output_with_captcha(*statuses: str, attempts: int, solved: int) -> CrawlOutput:
    out = _output(*statuses)
    out.captcha_attempts = attempts
    out.captcha_solved = solved
    return out


async def test_charges_workspace_owner_per_captcha_attempt_even_when_crawl_failed(
    monkeypatch, record_usage
):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 3000)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    # Crawl failed (no billable success) but the solver ran twice — attempts bill.
    await charge_capability(
        _output_with_captcha("failed", attempts=2, solved=1),
        BillingUnit.WEB_CRAWL,
        _ctx(session),
    )

    assert user.credit_micros_balance == 100_000 - 2 * 3000
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "web_crawl_captcha"
    assert kwargs["user_id"] == _OWNER
    assert kwargs["cost_micros"] == 6000


async def test_captcha_billing_disabled_does_not_charge_attempts(
    monkeypatch, record_usage
):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", False)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output_with_captcha("failed", attempts=2, solved=1),
        BillingUnit.WEB_CRAWL,
        _ctx(session),
    )

    record_usage.assert_not_awaited()
    assert user.credit_micros_balance == 100_000


async def test_no_successful_rows_is_free(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output("empty", "failed"), BillingUnit.WEB_CRAWL, _ctx(session)
    )

    record_usage.assert_not_awaited()
    assert user.credit_micros_balance == 100_000


async def test_disabled_is_noop(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output("success", "success"), BillingUnit.WEB_CRAWL, _ctx(session)
    )

    record_usage.assert_not_awaited()
    session.execute.assert_not_called()
    assert user.credit_micros_balance == 100_000


async def test_free_verb_without_a_unit_is_noop(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(_output("success", "success"), None, _ctx(session))

    record_usage.assert_not_awaited()
    session.execute.assert_not_called()
    assert user.credit_micros_balance == 100_000


def _gate_session(owner_id, balance_micros):
    """Mock session serving owner-resolution and the spendable-balance read."""
    session = AsyncMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = owner_id  # owner resolution
        result.first.return_value = (balance_micros, 0)  # balance, reserved
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session


async def test_gate_blocks_when_worst_case_exceeds_balance(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
    session = _gate_session(_OWNER, balance_micros=1500)  # affords 1 crawl, not 2

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            CrawlInput(startUrls=["https://a.com", "https://b.com"]),
            BillingUnit.WEB_CRAWL,
            _ctx(session),
        )


async def test_gate_passes_when_balance_covers_worst_case(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
    session = _gate_session(_OWNER, balance_micros=100_000)

    await gate_capability(
        CrawlInput(startUrls=["https://a.com", "https://b.com"]),
        BillingUnit.WEB_CRAWL,
        _ctx(session),
    )


async def test_gate_is_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    session = _gate_session(_OWNER, balance_micros=0)

    await gate_capability(
        CrawlInput(startUrls=["https://a.com"]), BillingUnit.WEB_CRAWL, _ctx(session)
    )


async def test_gate_reserves_worst_case_captcha_when_solving_enabled(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 3000)
    monkeypatch.setattr(config, "CAPTCHA_MAX_ATTEMPTS_PER_URL", 3)
    monkeypatch.setattr(billing, "captcha_enabled", lambda: True)
    session = _gate_session(_OWNER, balance_micros=5000)  # < 1 url * 3 * 3000

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            CrawlInput(startUrls=["https://a.com"]),
            BillingUnit.WEB_CRAWL,
            _ctx(session),
        )


async def test_gate_does_not_reserve_captcha_when_solving_disabled(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(billing, "captcha_enabled", lambda: False)
    session = _gate_session(_OWNER, balance_micros=0)

    # Solving off → attempts can never happen → nothing to reserve → passes.
    await gate_capability(
        CrawlInput(startUrls=["https://a.com"]), BillingUnit.WEB_CRAWL, _ctx(session)
    )


async def test_gate_is_noop_for_free_verb(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    session = _gate_session(_OWNER, balance_micros=0)

    await gate_capability(CrawlInput(startUrls=["https://a.com"]), None, _ctx(session))

    session.execute.assert_not_called()


# ===================================================================
# Platform scraper per-item billing (Reddit / Search / Maps / YouTube)
# ===================================================================


class _FakePlatformOutput:
    """Stand-in for a verb output: only the billing-read properties matter."""

    def __init__(self, items: int, attached_review_count: int = 0):
        self._items = items
        self._reviews = attached_review_count

    @property
    def billable_units(self) -> int:
        return self._items

    @property
    def attached_review_count(self) -> int:
        return self._reviews


class _FakePlatformInput:
    """Stand-in for a verb input reporting its worst-case unit counts."""

    def __init__(self, estimated_units: int, estimated_review_units: int = 0):
        self._units = estimated_units
        self._review_units = estimated_review_units

    @property
    def estimated_units(self) -> int:
        return self._units

    @property
    def estimated_review_units(self) -> int:
        return self._review_units


@pytest.fixture
def _enable_platform_billing(monkeypatch):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)


async def test_platform_charges_owner_per_item(
    monkeypatch, record_usage, _enable_platform_billing
):
    monkeypatch.setattr(config, "REDDIT_SCRAPE_MICROS_PER_ITEM", 3500)
    session, user = _make_session(_OWNER, balance_micros=1_000_000)

    charged = await charge_capability(
        _FakePlatformOutput(3), BillingUnit.REDDIT_ITEM, _ctx(session)
    )

    assert charged == 3 * 3500
    assert user.credit_micros_balance == 1_000_000 - 3 * 3500
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "reddit_item"
    assert kwargs["user_id"] == _OWNER
    assert kwargs["workspace_id"] == _WORKSPACE_ID
    assert kwargs["cost_micros"] == 3 * 3500


async def test_platform_maps_scrape_dual_meters_places_and_reviews(
    monkeypatch, record_usage, _enable_platform_billing
):
    monkeypatch.setattr(config, "GOOGLE_MAPS_MICROS_PER_PLACE", 5000)
    monkeypatch.setattr(config, "GOOGLE_MAPS_MICROS_PER_REVIEW", 2000)
    session, user = _make_session(_OWNER, balance_micros=1_000_000)

    # 2 places + 10 attached reviews -> 2*5000 + 10*2000 = 30000.
    charged = await charge_capability(
        _FakePlatformOutput(2, attached_review_count=10),
        BillingUnit.GOOGLE_MAPS_PLACE,
        _ctx(session),
    )

    assert charged == 2 * 5000 + 10 * 2000
    assert user.credit_micros_balance == 1_000_000 - 30_000
    assert record_usage.await_count == 2
    usage_types = {c.kwargs["usage_type"] for c in record_usage.await_args_list}
    assert usage_types == {"google_maps_place", "google_maps_review"}


async def test_platform_charge_disabled_is_noop(monkeypatch, record_usage):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", False)
    monkeypatch.setattr(config, "REDDIT_SCRAPE_MICROS_PER_ITEM", 3500)
    session, user = _make_session(_OWNER, balance_micros=1_000_000)

    charged = await charge_capability(
        _FakePlatformOutput(3), BillingUnit.REDDIT_ITEM, _ctx(session)
    )

    assert charged == 0
    record_usage.assert_not_awaited()
    session.execute.assert_not_called()
    assert user.credit_micros_balance == 1_000_000


async def test_platform_no_items_is_free(
    monkeypatch, record_usage, _enable_platform_billing
):
    monkeypatch.setattr(config, "YOUTUBE_MICROS_PER_COMMENT", 3500)
    session, user = _make_session(_OWNER, balance_micros=1_000_000)

    charged = await charge_capability(
        _FakePlatformOutput(0), BillingUnit.YOUTUBE_COMMENT, _ctx(session)
    )

    assert charged == 0
    record_usage.assert_not_awaited()
    assert user.credit_micros_balance == 1_000_000


async def test_platform_gate_blocks_when_worst_case_exceeds_balance(
    monkeypatch, _enable_platform_billing
):
    monkeypatch.setattr(config, "GOOGLE_SEARCH_MICROS_PER_SERP", 5500)
    session = _gate_session(_OWNER, balance_micros=6000)  # affords 1 SERP, not 2

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            _FakePlatformInput(estimated_units=2),
            BillingUnit.GOOGLE_SEARCH_SERP,
            _ctx(session),
        )


async def test_platform_gate_maps_reserves_places_plus_reviews(
    monkeypatch, _enable_platform_billing
):
    monkeypatch.setattr(config, "GOOGLE_MAPS_MICROS_PER_PLACE", 5000)
    monkeypatch.setattr(config, "GOOGLE_MAPS_MICROS_PER_REVIEW", 2000)
    # 1 place (5000) + 10 worst-case reviews (20000) = 25000 required.
    session = _gate_session(_OWNER, balance_micros=20_000)

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            _FakePlatformInput(estimated_units=1, estimated_review_units=10),
            BillingUnit.GOOGLE_MAPS_PLACE,
            _ctx(session),
        )


async def test_platform_gate_passes_when_affordable(
    monkeypatch, _enable_platform_billing
):
    monkeypatch.setattr(config, "GOOGLE_SEARCH_MICROS_PER_SERP", 5500)
    session = _gate_session(_OWNER, balance_micros=1_000_000)

    await gate_capability(
        _FakePlatformInput(estimated_units=2),
        BillingUnit.GOOGLE_SEARCH_SERP,
        _ctx(session),
    )


async def test_platform_gate_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", False)
    session = _gate_session(_OWNER, balance_micros=0)

    await gate_capability(
        _FakePlatformInput(estimated_units=1000),
        BillingUnit.REDDIT_ITEM,
        _ctx(session),
    )

    session.execute.assert_not_called()


# ===================================================================
# Instagram per-item / per-comment billing
# ===================================================================


async def test_instagram_item_charges_owner_per_item(
    monkeypatch, record_usage, _enable_platform_billing
):
    monkeypatch.setattr(config, "INSTAGRAM_SCRAPE_MICROS_PER_ITEM", 3500)
    session, user = _make_session(_OWNER, balance_micros=1_000_000)

    charged = await charge_capability(
        _FakePlatformOutput(4), BillingUnit.INSTAGRAM_ITEM, _ctx(session)
    )

    assert charged == 4 * 3500
    assert user.credit_micros_balance == 1_000_000 - 4 * 3500
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "instagram_item"


async def test_instagram_comment_charges_owner_per_comment(
    monkeypatch, record_usage, _enable_platform_billing
):
    monkeypatch.setattr(config, "INSTAGRAM_SCRAPE_MICROS_PER_COMMENT", 1500)
    session, user = _make_session(_OWNER, balance_micros=1_000_000)

    charged = await charge_capability(
        _FakePlatformOutput(6), BillingUnit.INSTAGRAM_COMMENT, _ctx(session)
    )

    assert charged == 6 * 1500
    assert user.credit_micros_balance == 1_000_000 - 6 * 1500
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "instagram_comment"


async def test_instagram_gate_blocks_when_worst_case_exceeds_balance(
    monkeypatch, _enable_platform_billing
):
    monkeypatch.setattr(config, "INSTAGRAM_SCRAPE_MICROS_PER_ITEM", 3500)
    session = _gate_session(_OWNER, balance_micros=5000)  # affords 1 item, not 2

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            _FakePlatformInput(estimated_units=2),
            BillingUnit.INSTAGRAM_ITEM,
            _ctx(session),
        )


# Red-phase scaffolds for 9.1a


async def test_chainlens_charge_records_degradation_in_call_details(
    monkeypatch, record_usage
):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "CHAINLENS_QUERY_MICROS_PER_CALL", 5000)
    session, _user = _make_session(_OWNER, balance_micros=100_000)

    output = SimpleNamespace(
        billable_units=1,
        status="partial",
        degraded=True,
        degradation_reason="fallback_kb_hits",
    )

    await charge_capability(output, BillingUnit.CHAINLENS_QUERY, _ctx(session))

    assert record_usage.awaited
    details = record_usage.await_args.kwargs["call_details"]
    assert details["degradation_reason"] == "fallback_kb_hits"
    assert details["final_status"] == "partial"


async def test_engine_unavailable_no_content_does_not_record_token_usage(
    monkeypatch, record_usage
):
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    output = ResearchOutput()
    output.status = "engine_unavailable"

    charged = await charge_capability(
        output, BillingUnit.CHAINLENS_QUERY, _ctx(session)
    )

    assert charged == 0
    assert getattr(output, "degraded", False) is True
    assert getattr(output, "degradation_reason", None) == "unknown"
    record_usage.assert_not_awaited()
    assert user.credit_micros_balance == 100_000


async def test_chainlens_charge_does_not_leak_secrets_in_call_details(
    monkeypatch, record_usage
):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    session, _user = _make_session(_OWNER, balance_micros=100_000)

    output = SimpleNamespace(
        billable_units=1,
        status="partial",
        degraded=True,
        degradation_reason="rate_limited",
    )

    await charge_capability(output, BillingUnit.CHAINLENS_QUERY, _ctx(session))

    details = record_usage.await_args.kwargs["call_details"]
    assert details["degradation_reason"] == "rate_limited"
    assert details["final_status"] == "partial"
    details_str = str(details)
    assert "query text" not in details_str.lower()
    assert "secret-key" not in details_str.lower()
    assert "https://example.com" not in details_str


# Red-phase scaffolds for 9.2 — deep-research cost metering


async def test_chainlens_charge_uses_actual_cost_micros_and_deep_research_usage(
    monkeypatch, record_usage
):
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    output = ResearchOutput(
        answer="Answer",
        status="complete",
        cost_micros=12300,
        cost_basis="actual",
        resolved_mode="quality",
        tokens_total=1280,
    )

    charged = await charge_capability(
        output, BillingUnit.CHAINLENS_QUERY, _ctx(session)
    )

    assert charged == 12300
    assert user.credit_micros_balance == 100_000 - 12300
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "deep_research"
    assert kwargs["cost_micros"] == 12300
    assert kwargs["user_id"] == _OWNER
    assert kwargs["workspace_id"] == _WORKSPACE_ID
    details = kwargs["call_details"]
    assert details["cost_basis"] == "actual"
    assert details["resolved_mode"] == "quality"
    assert details["tokens_total"] == 1280


async def test_chainlens_charge_fallback_to_flat_rate_logs_warning(
    monkeypatch, record_usage, caplog
):
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "CHAINLENS_QUERY_MICROS_PER_CALL", 5000)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    output = ResearchOutput(answer="Answer", status="complete")

    charged = await charge_capability(
        output, BillingUnit.CHAINLENS_QUERY, _ctx(session)
    )

    assert charged == 5000
    assert user.credit_micros_balance == 100_000 - 5000
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "deep_research"
    assert kwargs["cost_micros"] == 5000
    assert kwargs["call_details"]["cost_basis"] == "fallback"
    assert any("fallback" in rec.message for rec in caplog.records)


async def test_chainlens_billing_disabled_records_usage_without_debit(
    monkeypatch, record_usage
):
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", False)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    output = ResearchOutput(
        answer="Answer",
        status="complete",
        cost_micros=12300,
        cost_basis="actual",
        resolved_mode="quality",
    )

    charged = await charge_capability(
        output, BillingUnit.CHAINLENS_QUERY, _ctx(session)
    )

    assert charged == 0
    assert user.credit_micros_balance == 100_000
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "deep_research"
    assert kwargs["cost_micros"] == 12300


async def test_chainlens_charge_raises_when_actual_cost_exceeds_balance(
    monkeypatch, record_usage
):
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=10_000)

    output = ResearchOutput(
        answer="Answer",
        status="complete",
        cost_micros=12_300,
        cost_basis="actual",
        resolved_mode="quality",
    )

    with pytest.raises(InsufficientCreditsError):
        await charge_capability(
            output, BillingUnit.CHAINLENS_QUERY, _ctx(session)
        )

    assert user.credit_micros_balance == 10_000


async def test_chainlens_engine_unavailable_with_no_content_is_free(
    monkeypatch, record_usage
):
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    output = ResearchOutput(status="engine_unavailable")

    charged = await charge_capability(
        output, BillingUnit.CHAINLENS_QUERY, _ctx(session)
    )

    assert charged == 0
    assert user.credit_micros_balance == 100_000
    record_usage.assert_not_awaited()
