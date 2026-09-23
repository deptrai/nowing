"""Tests for Story 37.1 — Proactive Intent Signal Radar (AD-115).

Covers:
- AC-2: Aho-Corasick O(n) pre-filter + contact extraction + lead creation
  + round-robin assignment for ``stream:telegram:raw_events``.
- AC-3: contactless intent messages -> ``pending_enrichment`` leads, no billing.
- AC-1/AC-4: periodic scanner threshold logic + per-workspace budget and
  50-credit pause guardrails.

All DB/Redis/HTTP interaction is faked; no real services required.
"""

from __future__ import annotations

import types
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Scripted stand-in for ``AsyncSession``.

    ``execute_queue`` is a list of ``_FakeResult`` values consumed in order.
    ``scalar_values`` is consumed by ``session.scalar`` in order.
    """

    def __init__(
        self,
        *,
        execute_queue: list[_FakeResult] | None = None,
        scalar_values: list[Any] | None = None,
        get_map: dict[Any, Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self.rolled_back = False
        self._execute_queue = list(execute_queue or [])
        self._scalar_values = list(scalar_values or [])
        self._get_map = get_map or {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any, _params: Any | None = None) -> _FakeResult:
        if self._execute_queue:
            return self._execute_queue.pop(0)
        return _FakeResult()

    async def scalar(self, _stmt: Any) -> Any:
        if self._scalar_values:
            return self._scalar_values.pop(0)
        return None

    async def get(self, model: Any, pk: Any) -> Any:
        return self._get_map.get((model, pk)) or self._get_map.get(model)

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        # Simulate DB-side primary-key defaults so objects added before flush
        # get a real id (matches what PostgreSQL does on INSERT).
        for obj in self.added:
            if getattr(obj, "id", True) is None:
                obj.id = uuid4()


class _FakeRedis:
    def __init__(self, *, scans_used: int = 0) -> None:
        self._scans_used = scans_used
        self.incr_calls = 0
        self.acked: list[str] = []
        self.dlq: list[dict[str, Any]] = []

    async def get(self, _key: str) -> bytes:
        return str(self._scans_used).encode()

    async def set(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def incr(self, _key: str) -> int:
        self.incr_calls += 1
        self._scans_used += 1
        return self._scans_used

    async def expire(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def xack(self, *_args: Any) -> None:
        self.acked.append(str(_args[-1]))

    async def xadd(self, _stream: str, fields: dict[str, Any], **_: Any) -> None:
        self.dlq.append(fields)


# ---------------------------------------------------------------------------
# AC-2: Aho-Corasick matcher
# ---------------------------------------------------------------------------


class TestIntentKeywordMatcher:
    def test_matches_all_required_patterns(self):
        from app.lead_intelligence.signals.radar import IntentKeywordMatcher

        matcher = IntentKeywordMatcher(
            ("cần tìm nhà cung cấp", "báo giá", "tìm agency", "thuê ngoài")
        )
        for phrase in (
            "Cần tìm nhà cung cấp gấp",
            "Shop cần báo giá 100 áo",
            "Mình đang tìm agency chạy ads",
            "Công ty muốn thuê ngoài phần mềm",
        ):
            assert matcher.find_matches(phrase), phrase

    def test_accent_insensitive(self):
        from app.lead_intelligence.signals.radar import IntentKeywordMatcher

        matcher = IntentKeywordMatcher(("báo giá",))
        assert matcher.find_matches("can bao gia ngay") == ["báo giá"]
        assert matcher.has_match("XIN BAO GIA")

    def test_no_match_returns_empty(self):
        from app.lead_intelligence.signals.radar import IntentKeywordMatcher

        matcher = IntentKeywordMatcher(("báo giá", "thuê ngoài"))
        assert matcher.find_matches("chào mọi người") == []
        assert not matcher.has_match("")
        assert matcher.find_matches(None or "") == []

    def test_overlapping_and_multiple_matches(self):
        from app.lead_intelligence.signals.radar import IntentKeywordMatcher

        matcher = IntentKeywordMatcher(("cần tìm nhà cung cấp", "tìm nhà cung cấp"))
        hits = matcher.find_matches("cần tìm nhà cung cấp vải")
        # both the long pattern and its suffix pattern are reported
        assert set(hits) == {"cần tìm nhà cung cấp", "tìm nhà cung cấp"}

    def test_module_matcher_is_precompiled(self):
        from app.lead_intelligence.signals import radar

        assert radar.TELEGRAM_INTENT_MATCHER.has_match(
            "Ai có báo giá cho 500 hộp quà tết"
        )


# ---------------------------------------------------------------------------
# AC-2 / AC-3: telegram intent event -> Lead
# ---------------------------------------------------------------------------


def _intent_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "message_id": "42",
        "channel_username": "sourcing_vn",
        "message_text": "Mình cần báo giá 200 áo thun, sdt 0912345678",
        "workspace_id": "7",
    }
    payload.update(overrides)
    return payload


def _workspace_obj(**overrides: Any) -> Any:
    from app.db import Workspace

    ws = Workspace()  # declarative constructor sets up instrumented state
    ws.id = 7
    ws.icp_criteria = None
    for key, value in overrides.items():
        setattr(ws, key, value)
    return ws


class TestProcessTelegramIntentEvent:
    async def test_no_keyword_returns_none_without_session(self):
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        result = await process_telegram_intent_event(
            {"message_text": "bán nhà quận 7", "workspace_id": "7"},
            session=None,
        )
        assert result is None

    async def test_no_workspace_resolved_returns_none(self):
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        session = _FakeSession(execute_queue=[_FakeResult(None)])
        result = await process_telegram_intent_event(
            {"message_text": "cần báo giá", "channel_username": "ghost"},
            session=session,
        )
        assert result is None
        assert session.added == []

    async def test_contact_lead_created_and_committed(self):
        from app.db import Lead, Workspace
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        session = _FakeSession(
            scalar_values=[None],  # no existing lead
            get_map={Workspace: _workspace_obj()},
        )
        lead = await process_telegram_intent_event(
            _intent_payload(),
            session=session,
            redis_client=None,
        )
        assert isinstance(lead, Lead)
        assert lead.workspace_id == 7
        assert lead.status == "new"
        # Extracted contacts live only in the activity log — no VerifiedContact
        # exists, so the lead is never pre-marked as enriched.
        assert lead.needs_enrichment is True
        assert lead.enriched is False
        assert lead.intent_score >= 0.75
        assert lead.source == "telegram_intent"
        assert lead.source_url == "https://t.me/sourcing_vn/42"
        assert session.committed == 1
        activities = [o for o in session.added if type(o).__name__ == "LeadActivityLog"]
        assert activities and "0912345678" in str(activities[0].details["phones"])

    async def test_explicit_workspace_id_must_exist(self):
        """An unknown explicit workspace_id is not trusted blindly."""
        from app.db import Workspace
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        session = _FakeSession(get_map={Workspace: None})
        result = await process_telegram_intent_event(
            _intent_payload(workspace_id="999"),
            session=session,
        )
        assert result is None
        assert session.added == []

    async def test_workspace_resolved_via_monitored_target(self):
        """channel_username -> SocialMonitoredTarget.workspace_id -> lead."""
        from app.db import Lead, Workspace
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        session = _FakeSession(
            execute_queue=[_FakeResult(9)],  # SocialMonitoredTarget.workspace_id
            scalar_values=[None],
            get_map={Workspace: _workspace_obj(id=9)},
        )
        lead = await process_telegram_intent_event(
            _intent_payload(workspace_id=None),
            session=session,
        )
        assert isinstance(lead, Lead)
        assert lead.workspace_id == 9

    async def test_workspace_consent_settings_applied(self):
        from app.db import Workspace
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        session = _FakeSession(
            scalar_values=[None],
            get_map={
                Workspace: _workspace_obj(
                    icp_criteria={
                        "social_lead_consent_status": "consented",
                        "social_lead_legal_basis": "contract",
                    }
                )
            },
        )
        lead = await process_telegram_intent_event(_intent_payload(), session=session)
        assert lead is not None
        assert lead.consent_status == "consented"
        assert lead.legal_basis == "contract"

    async def test_distinct_senders_without_names_get_distinct_hmacs(self):
        """Channel fallback name must not collapse all senders into one lead."""
        from app.db import Workspace
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        # Two messages from different senders, same channel, no sender_name.
        session = _FakeSession(
            scalar_values=[None, None],
            get_map={Workspace: _workspace_obj()},
        )
        lead_a = await process_telegram_intent_event(
            _intent_payload(sender_id="111", message_id="1"), session=session
        )
        lead_b = await process_telegram_intent_event(
            _intent_payload(sender_id="222", message_id="2"), session=session
        )
        assert lead_a is not None and lead_b is not None
        assert lead_a.value_hmac != lead_b.value_hmac
        assert lead_a.company_name == lead_b.company_name  # shared fallback

    async def test_contactless_lead_is_pending_enrichment_no_billing(self, monkeypatch):
        """AC-3: no phone/email -> pending_enrichment, zero credit deduction."""
        from app.db import Lead, Workspace
        from app.lead_intelligence.signals import radar

        billing_spy = AsyncMock()
        monkeypatch.setattr(
            "app.services.billing_event_service.record_signal_scan", billing_spy
        )

        session = _FakeSession(
            scalar_values=[None],
            get_map={Workspace: _workspace_obj()},
        )
        lead = await radar.process_telegram_intent_event(
            _intent_payload(message_text="Cần tìm nhà cung cấp bao bì giá tốt"),
            session=session,
        )
        assert isinstance(lead, Lead)
        assert lead.status == "pending_enrichment"
        assert lead.needs_enrichment is True
        assert lead.enriched is False
        billing_spy.assert_not_called()

    async def test_duplicate_lead_skipped(self):
        from app.db import Workspace
        from app.lead_intelligence.signals.radar import process_telegram_intent_event

        session = _FakeSession(
            scalar_values=[uuid4()],  # existing lead id -> dedupe hit
            get_map={Workspace: _workspace_obj()},
        )
        result = await process_telegram_intent_event(_intent_payload(), session=session)
        assert result is None
        assert session.committed == 0

    async def test_contact_lead_assigned_round_robin(self, monkeypatch):
        """AC-2: contact-bearing leads go through LeadAssignmentService."""
        from app.db import Workspace
        from app.lead_intelligence.signals import radar

        assigned: list[list[Any]] = []

        class _FakeAssigner:
            def __init__(self, session: Any, redis_client: Any) -> None:
                pass

            async def assign_leads_batch(
                self, *, workspace_id: int, lead_ids: list[Any]
            ) -> Any:
                assigned.append(list(lead_ids))
                return None

        monkeypatch.setattr(
            "app.services.lead_assignment_service.LeadAssignmentService",
            _FakeAssigner,
        )
        session = _FakeSession(
            scalar_values=[None],
            get_map={Workspace: _workspace_obj()},
        )
        lead = await radar.process_telegram_intent_event(
            _intent_payload(),
            session=session,
            redis_client=object(),
        )
        assert lead is not None
        assert lead.id is not None  # flush() assigned the pk
        assert assigned == [[lead.id]]


# ---------------------------------------------------------------------------
# AC-2: stream consumer loop
# ---------------------------------------------------------------------------


class _StreamFakeRedis(_FakeRedis):
    def __init__(self, messages: list[tuple[str, dict[str, Any]]]) -> None:
        super().__init__()
        self._messages = messages
        self.group_created = False
        self.read_calls = 0

    async def xgroup_create(self, **_kwargs: Any) -> None:
        self.group_created = True

    async def xautoclaim(self, **_kwargs: Any) -> Any:
        return [None, [], None]

    async def xreadgroup(self, **_kwargs: Any) -> Any:
        self.read_calls += 1
        if self.read_calls > 1:
            return []
        from app.proprietary.platforms.telegram.stream_daemon import (
            STREAM_TELEGRAM_RAW_EVENTS,
        )

        return [(STREAM_TELEGRAM_RAW_EVENTS, self._messages)]


class _FakeSessionMaker:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionMaker:
        return self

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *_: Any) -> None:
        return None


class TestTelegramIntentConsumer:
    async def test_consumer_processes_and_acks_intent_events(self):
        from app.db import Lead, Workspace
        from app.lead_intelligence.signals.radar import run_telegram_intent_consumer

        redis = _StreamFakeRedis(
            [
                ("1-0", _intent_payload()),
                ("2-0", {"message_text": "random chatter", "workspace_id": "7"}),
            ]
        )
        # Msg 1: workspace get + lead dedupe; msg 2 exits before hitting the DB
        # since the trie rejects it.
        session = _FakeSession(
            scalar_values=[None],
            get_map={Workspace: _workspace_obj()},
        )
        created = await run_telegram_intent_consumer(
            redis_client=redis,
            consumer_name="test-consumer",
            max_loops=1,
            session_maker=_FakeSessionMaker(session),
        )
        assert created == 1
        assert redis.group_created is True
        assert "1-0" in redis.acked
        assert "2-0" in redis.acked
        assert any(
            type(o).__name__ == "Lead" and isinstance(o, Lead) for o in session.added
        )

    async def test_consumer_routes_failures_to_dlq_and_acks(self, monkeypatch):
        """A processing exception must land on the DLQ AND ack the original."""
        from app.lead_intelligence.signals import radar

        async def _explode(*_a: Any, **_k: Any) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(radar, "process_telegram_intent_event", _explode)

        redis = _StreamFakeRedis([("9-0", _intent_payload())])
        created = await radar.run_telegram_intent_consumer(
            redis_client=redis,
            consumer_name="test-consumer",
            max_loops=1,
            session_maker=_FakeSessionMaker(_FakeSession()),
        )
        assert created == 0
        assert len(redis.dlq) == 1
        assert redis.dlq[0]["original_id"] == "9-0"
        assert "boom" in redis.dlq[0]["error"]
        assert "9-0" in redis.acked  # original acked after DLQ write


# ---------------------------------------------------------------------------
# AC-1 / AC-4: periodic workspace scan
# ---------------------------------------------------------------------------


def _workspace(balance_micros: int) -> Any:
    return types.SimpleNamespace(id=7, credit_micros_balance=balance_micros)


class _ScanSession(_FakeSession):
    def __init__(self, workspace: Any, execute_queue: list[_FakeResult]) -> None:
        super().__init__(execute_queue=execute_queue)
        self._workspace = workspace

    async def get(self, model: Any, pk: Any) -> Any:
        return self._workspace


class TestScanWorkspaceHighIntent:
    async def test_pauses_below_50_credits(self):
        """AC-4: workspace pauses automatically under 50 credits."""
        from app.lead_intelligence.signals.radar import (
            MIN_WORKSPACE_CREDIT_MICROS,
            scan_workspace_high_intent,
        )

        session = _ScanSession(
            workspace=_workspace(MIN_WORKSPACE_CREDIT_MICROS - 1),
            execute_queue=[],
        )
        result = await scan_workspace_high_intent(session, _FakeRedis(), workspace_id=7)
        assert result["status"] == "paused_low_credit"
        assert session.committed == 0

    async def test_budget_exhausted_at_100_scans(self):
        """AC-4: no more than 100 scans per workspace per day."""
        from app.lead_intelligence.signals.radar import (
            MAX_SCANS_PER_WORKSPACE_PER_DAY,
            scan_workspace_high_intent,
        )

        session = _ScanSession(
            workspace=_workspace(10_000_000_000),
            execute_queue=[],
        )
        redis = _FakeRedis(scans_used=MAX_SCANS_PER_WORKSPACE_PER_DAY)
        result = await scan_workspace_high_intent(session, redis, workspace_id=7)
        assert result["status"] == "budget_exhausted"
        assert redis.incr_calls == 0

    async def test_hiring_surge_persists_signal_above_threshold(self, monkeypatch):
        """AC-1: >=3 new postings in 7 days -> SignalEvent at >=0.75 intent."""
        from app.config import config
        from app.db import SignalEvent
        from app.lead_intelligence.signals import radar

        monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 0)

        session = _ScanSession(
            workspace=_workspace(10_000_000_000),
            execute_queue=[
                _FakeResult(rows=["Acme Corp"]),  # hiring watchlist
                _FakeResult(None),  # dedupe check: no recent signal
                _FakeResult(None),  # _persist_signal idempotency check
            ],
        )
        now = datetime.now(UTC)
        listings = [
            {
                "posted_at": (now - timedelta(days=2)).date(),
                "source_url": "https://topcv.vn/j/1",
            },
            {
                "posted_at": (now - timedelta(days=3)).date(),
                "source_url": "https://vietnamworks.com/j/2",
            },
            {"posted_at": now.date(), "source_url": "https://topcv.vn/j/3"},
            {
                "posted_at": (now - timedelta(days=30)).date(),
                "source_url": "https://topcv.vn/old",
            },
        ]
        aggregate_fn = AsyncMock(return_value=types.SimpleNamespace(items=listings))
        result = await radar.scan_workspace_high_intent(
            session,
            _FakeRedis(),
            workspace_id=7,
            aggregate_fn=aggregate_fn,
            now=now,
        )
        assert result["status"] == "ok"
        assert result["signals_created"] == 1
        signals = [o for o in session.added if isinstance(o, SignalEvent)]
        assert len(signals) == 1
        assert signals[0].signal_type == "hiring"
        assert signals[0].confidence >= 75.0  # intent_score >= 0.75 (0-100 scale)
        assert session.committed == 1

    async def test_below_threshold_no_signal(self):
        from app.db import SignalEvent
        from app.lead_intelligence.signals import radar

        session = _ScanSession(
            workspace=_workspace(10_000_000_000),
            execute_queue=[_FakeResult(rows=["Acme Corp"])],
        )
        now = datetime.now(UTC)
        aggregate_fn = AsyncMock(
            return_value=types.SimpleNamespace(
                items=[
                    {"posted_at": now.date(), "source_url": "x"},
                    {"posted_at": now.date(), "source_url": "y"},
                ]
            )
        )
        result = await radar.scan_workspace_high_intent(
            session,
            _FakeRedis(),
            workspace_id=7,
            aggregate_fn=aggregate_fn,
            now=now,
        )
        assert result["signals_created"] == 0
        assert not [o for o in session.added if isinstance(o, SignalEvent)]

    async def test_new_incorporations_persist_signals(self, monkeypatch):
        from app.config import config
        from app.db import SignalEvent
        from app.lead_intelligence.signals import radar

        monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 0)

        session = _ScanSession(
            workspace=_workspace(10_000_000_000),
            execute_queue=[
                _FakeResult(None),  # incorporation dedupe check
                _FakeResult(None),  # persist idempotency check
                _FakeResult(rows=[]),  # empty hiring watchlist (runs second)
            ],
        )
        result = await radar.scan_workspace_high_intent(
            session,
            _FakeRedis(),
            workspace_id=7,
            aggregate_fn=AsyncMock(),
            new_incorporations=[
                {
                    "company_name": "CÔNG TY TNHH MỚI",
                    "tax_code": "0312345678",
                    "source_url": "https://masothue.com/0312345678",
                    "source": "masothue",
                }
            ],
        )
        assert result["signals_created"] == 1
        signals = [o for o in session.added if isinstance(o, SignalEvent)]
        assert signals[0].signal_type == "incorporation"
        assert signals[0].confidence >= 75.0

    async def test_pauses_when_billing_wallet_low(self, monkeypatch):
        """Credit guard covers the pool actually debited — the billing
        user's wallet, not just the workspace balance."""
        from app.config import config
        from app.lead_intelligence.signals import radar
        from app.services import wallet_credit

        monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 100)
        monkeypatch.setattr(
            wallet_credit, "spendable_micros", AsyncMock(return_value=0)
        )
        session = _ScanSession(
            workspace=_workspace(10_000_000_000),  # workspace pool healthy
            execute_queue=[_FakeResult(uuid4())],  # subscription creator
        )
        result = await radar.scan_workspace_high_intent(
            session, _FakeRedis(), workspace_id=7
        )
        assert result["status"] == "paused_low_credit"

    async def test_wallet_read_failure_keeps_scanning(self, monkeypatch):
        """Wallet balance read failure is fail-open — scans proceed."""
        from app.config import config
        from app.lead_intelligence.signals import radar
        from app.services import wallet_credit

        monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 100)
        monkeypatch.setattr(
            wallet_credit,
            "spendable_micros",
            AsyncMock(side_effect=RuntimeError("db down")),
        )
        session = _ScanSession(
            workspace=_workspace(10_000_000_000),
            execute_queue=[
                _FakeResult(uuid4()),  # billing user
                _FakeResult(rows=[]),  # empty hiring watchlist
            ],
        )
        result = await radar.scan_workspace_high_intent(
            session,
            _FakeRedis(),
            workspace_id=7,
            aggregate_fn=AsyncMock(),
        )
        assert result["status"] == "ok"

    async def test_incorporation_broadcast_capped_per_scan(self, monkeypatch):
        """The global listing is broadcast to every workspace — cap keeps a
        long listing from flooding one workspace's feed in a single run."""
        from app.config import config
        from app.db import SignalEvent
        from app.lead_intelligence.signals import radar

        monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 0)
        monkeypatch.setattr(radar, "MAX_INCORPORATION_SIGNALS_PER_SCAN", 2)

        session = _ScanSession(
            workspace=_workspace(10_000_000_000),
            execute_queue=[
                _FakeResult(None),  # dedupe item 1
                _FakeResult(None),  # persist idempotency item 1
                _FakeResult(None),  # dedupe item 2
                _FakeResult(None),  # persist idempotency item 2
                _FakeResult(rows=[]),  # empty hiring watchlist
            ],
        )
        incorporations = [
            {"company_name": f"CÔNG TY TNHH MỚI {i}", "tax_code": f"031234567{i}"}
            for i in range(5)
        ]
        await radar.scan_workspace_high_intent(
            session,
            _FakeRedis(),
            workspace_id=7,
            aggregate_fn=AsyncMock(),
            new_incorporations=incorporations,
        )
        signals = [o for o in session.added if isinstance(o, SignalEvent)]
        assert len(signals) == 2  # capped, not 5


class TestStreamHealthMetrics:
    async def test_logs_pending_and_dlq_at_warning(self, caplog):
        import logging

        from app.lead_intelligence.signals.radar import _log_stream_health

        class _Redis(_FakeRedis):
            async def xlen(self, _key: str) -> int:
                return 40 if "raw" in _key else 3

            async def xpending(self, *_a: Any) -> dict:
                return {"pending": 7}

        with caplog.at_level(logging.WARNING):
            await _log_stream_health(_Redis())
        assert "stream_len=40 pending=7 dlq_len=3" in caplog.text

    async def test_tuple_xpending_and_quiet_info_log(self, caplog):
        import logging

        from app.lead_intelligence.signals.radar import _log_stream_health

        class _Redis(_FakeRedis):
            async def xlen(self, _key: str) -> int:
                return 5

            async def xpending(self, *_a: Any) -> tuple:
                return (0, None, None, None)

        with caplog.at_level(logging.INFO):
            await _log_stream_health(_Redis())
        assert "pending=0 dlq_len=5" in caplog.text

    async def test_metric_failure_never_raises(self):
        from app.lead_intelligence.signals.radar import _log_stream_health

        class _Redis(_FakeRedis):
            async def xlen(self, _key: str) -> int:
                raise RuntimeError("redis down")

        await _log_stream_health(_Redis())  # must not raise


# ---------------------------------------------------------------------------
# AC-1: incorporation source fetch + parse
# ---------------------------------------------------------------------------


class TestNewIncorporations:
    def test_dkkd_parser_extracts_names_and_tax_codes(self):
        from app.lead_intelligence.signals.radar import _parse_dkkd_new_companies

        html = """
        <div>
          Tên doanh nghiệp: CÔNG TY TNHH ABC XYZ
          Mã số doanh nghiệp/MST: 0109876543
        </div>
        """
        items = _parse_dkkd_new_companies(html)
        assert items and items[0]["company_name"].startswith("CÔNG TY TNHH ABC")
        assert items[0]["tax_code"] == "0109876543"
        assert items[0]["source"] == "dangkykinhdoanh"

    async def test_fetch_degrades_gracefully_per_source(self):
        from app.lead_intelligence.signals.radar import fetch_new_incorporations

        async def _fail(_url: str) -> str:
            raise RuntimeError("network down")

        items, reasons = await fetch_new_incorporations(fetch_page_fn=_fail)
        assert items == []
        assert len(reasons) == 2  # masothue + dangkykinhdoanh both degraded

    async def test_fetch_collects_dkkd_items(self):
        from app.lead_intelligence.signals import radar

        async def _fetch(url: str) -> str:
            if "dangkykinhdoanh" in url:
                return "Tên doanh nghiệp: CÔNG TY CP DEMO\nMST: 0301234567"
            return "<html>no companies</html>"

        items, reasons = await radar.fetch_new_incorporations(fetch_page_fn=_fetch)
        # masothue parsed zero items -> surfaced as a degradation, not "no data"
        assert "masothue_new_listing.empty_parse" in reasons
        assert any(i["source"] == "dangkykinhdoanh" for i in items)


# ---------------------------------------------------------------------------
# AC-1: incorporation detection via SignalDetectionService.detect
# ---------------------------------------------------------------------------


class TestDetectIncorporation:
    async def test_detect_incorporation_gates_on_active_date(self, monkeypatch):
        """Recent active_date -> confidence 80; old incorporation -> 40."""
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        recent = (datetime.now(UTC) - timedelta(days=5)).strftime("%d/%m/%Y")
        old = (datetime.now(UTC) - timedelta(days=400)).strftime("%d/%m/%Y")
        companies = [
            types.SimpleNamespace(
                name="CÔNG TY MỚI A",
                tax_code="0301111111",
                detail_url="https://masothue.com/0301111111",
                active_date=recent,
                founding_date=None,
            ),
            types.SimpleNamespace(
                name="CÔNG TY CŨ B",
                tax_code="0302222222",
                detail_url="https://masothue.com/0302222222",
                active_date=old,
                founding_date=None,
            ),
        ]

        async def _fake_scrape(_input: Any, **_kwargs: Any) -> Any:
            return types.SimpleNamespace(
                items=companies, degraded=False, degradation_reason=None
            )

        monkeypatch.setattr(
            "app.proprietary.platforms.masothue.scraper.scrape_masothue",
            _fake_scrape,
        )

        session = _FakeSession()  # execute -> None (idempotency miss) each time
        ctx = types.SimpleNamespace(
            session=session,
            workspace_id=7,
            client_id=None,
            user_id=None,  # skip wallet billing path
        )
        output = await SignalDetectionService().detect(
            session,
            ctx,
            SignalInput(company_name="ACME", confidence_threshold=75.0),
            "incorporation",
        )
        assert len(output.items) == 1
        assert output.items[0].confidence >= 75.0
        assert output.items[0].company_name == "CÔNG TY MỚI A"


# ---------------------------------------------------------------------------
# Beat schedule registration (AC-1 wiring)
# ---------------------------------------------------------------------------


class TestCeleryWiring:
    def test_periodic_task_and_schedule_registered(self):
        import app.tasks.celery_tasks.signal_radar_tasks  # noqa: F401
        from app.celery_app import celery_app

        assert "scan_high_intent_companies_periodic" in celery_app.tasks
        assert "process_telegram_intent_stream" in celery_app.tasks

        entry = celery_app.conf.beat_schedule["scan-high-intent-companies"]
        assert entry["task"] == "scan_high_intent_companies_periodic"
        # crontab(hour="*/6") fires 4x per day
        assert entry["schedule"].hour == {0, 6, 12, 18}

        tg = celery_app.conf.beat_schedule["process-telegram-intent-stream"]
        assert tg["task"] == "process_telegram_intent_stream"


# ---------------------------------------------------------------------------
# lead_id soft-link on signal rows (review 37.4)
# ---------------------------------------------------------------------------


class TestPersistSignalLeadLink:
    """Signals carry lead_id so a company rename doesn't orphan history."""

    async def test_persist_signal_links_matching_lead(self):
        from app.db import SignalEvent
        from app.lead_intelligence.signals.service import SignalDetectionService

        lead_id = uuid4()
        session = _FakeSession(
            execute_queue=[
                _FakeResult(lead_id),  # lead lookup by company name
                _FakeResult(None),  # idempotency check
            ]
        )
        signal = await SignalDetectionService().persist_signal(
            session,
            workspace_id=7,
            client_id=None,
            company_name="Acme Corp",
            signal_type="hiring",
            raw={
                "confidence": 80.0,
                "detected_at": datetime.now(UTC),
                "job_count": 4,
            },
        )
        assert signal is not None
        assert isinstance(signal, SignalEvent)
        assert signal.lead_id == lead_id

    async def test_persist_signal_no_lead_leaves_null(self):
        from app.lead_intelligence.signals.service import SignalDetectionService

        session = _FakeSession(
            execute_queue=[
                _FakeResult(None),  # no matching lead
                _FakeResult(None),  # idempotency check
            ]
        )
        signal = await SignalDetectionService().persist_signal(
            session,
            workspace_id=7,
            client_id=None,
            company_name="Unknown Co",
            signal_type="news",
            raw={
                "confidence": 80.0,
                "detected_at": datetime.now(UTC),
                "summary": "Mentioned in press.",
            },
        )
        assert signal is not None
        assert signal.lead_id is None
