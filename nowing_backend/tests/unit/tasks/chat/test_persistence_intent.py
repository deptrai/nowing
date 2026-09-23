"""persist_user_turn advisory intent-classification wiring (Story 39.5).

The classify call is advisory: a passing label lands on the USER row's
``platform_metadata["intent"]``; flag-off / below-gate / raised errors
leave persistence untouched. The caller's ``platform_metadata`` dict is
shared with ``persist_assistant_shell``, so it must never be mutated —
the intent merge happens on a copy.
"""

from __future__ import annotations

import pytest
from sqlalchemy.sql.dml import Insert

import app.tasks.chat.persistence as persistence

pytestmark = pytest.mark.unit

_INTENT_PAYLOAD = {
    "label": "search",
    "confidence": 0.9,
    "model": "jev-1.13.0",
    "backend": "jev",
}


class _FakeResult:
    def __init__(self, scalar):
        self._scalar = scalar

    def scalar(self):
        return self._scalar

    def scalars(self):
        return self

    def first(self):
        return self._scalar


def _insert_values(stmt) -> dict:
    """Extract an ORM ``pg_insert(...).values(...)`` payload.

    ``Insert._values`` maps ``Column`` objects to ``BindParameter``
    objects (``.value`` holds the Python value) for ORM inserts.
    """
    return {
        getattr(key, "name", key): getattr(raw, "value", raw)
        for key, raw in stmt._values.items()
    }


class _FakeSession:
    """Captures executed statements; ``insert_id`` controls the INSERT
    result (``None`` simulates the ON CONFLICT no-op race path)."""

    def __init__(self, captured: list, insert_id=42, lookup_id=99):
        self._captured = captured
        self._insert_id = insert_id
        self._lookup_id = lookup_id

    async def get(self, *_args, **_kwargs):
        return None

    async def execute(self, stmt):
        self._captured.append(stmt)
        if isinstance(stmt, Insert):
            return _FakeResult(self._insert_id)
        return _FakeResult(self._lookup_id)  # conflict lookup SELECT

    async def commit(self):
        return None


class _FakeSessionCM:
    def __init__(self, captured, insert_id=42):
        self._captured = captured
        self._insert_id = insert_id

    async def __aenter__(self):
        return _FakeSession(self._captured, insert_id=self._insert_id)

    async def __aexit__(self, *_exc):
        return False


@pytest.fixture
def _fake_db(monkeypatch):
    captured: list = []
    monkeypatch.setattr(
        persistence,
        "shielded_async_session",
        lambda: _FakeSessionCM(captured),
    )
    return captured


@pytest.fixture
def _quiet_guardrail(monkeypatch):
    """Stub the 39.4 advisory check — this file tests intent wiring."""

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(persistence, "check_passage", _noop)


def _inserts(captured: list) -> list[dict]:
    return [_insert_values(s) for s in captured if isinstance(s, Insert)]


async def test_intent_written_on_gate_pass(_fake_db, _quiet_guardrail, monkeypatch):
    seen: list[str] = []

    async def _classify(*_a, **_k):
        seen.append(_a[0])
        return dict(_INTENT_PAYLOAD)

    monkeypatch.setattr(persistence, "classify_intent", _classify)

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-1",
        user_query="Giá Bitcoin hôm nay bao nhiêu?",
        platform_metadata=None,
    )
    assert message_id == 42
    assert seen == ["Giá Bitcoin hôm nay bao nhiêu?"]

    inserts = _inserts(_fake_db)
    assert len(inserts) == 1
    assert inserts[0]["platform_metadata"] == {"intent": _INTENT_PAYLOAD}


async def test_intent_merges_into_copied_metadata(
    _fake_db, _quiet_guardrail, monkeypatch
):
    async def _classify(*_a, **_k):
        return dict(_INTENT_PAYLOAD)

    monkeypatch.setattr(persistence, "classify_intent", _classify)
    caller_meta = {"mode_x": True}

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-2",
        user_query="Tìm quán phở",
        platform_metadata=caller_meta,
    )
    assert message_id == 42
    inserts = _inserts(_fake_db)
    assert inserts[0]["platform_metadata"] == {
        "mode_x": True,
        "intent": _INTENT_PAYLOAD,
    }
    # The shared dict object must be untouched — persist_assistant_shell
    # receives the same object and must not inherit the user's intent.
    assert caller_meta == {"mode_x": True}
    assert inserts[0]["platform_metadata"] is not caller_meta


async def test_no_intent_key_when_classifier_returns_none(
    _fake_db, _quiet_guardrail, monkeypatch
):
    """Below-gate / flag-off inside classify_intent -> None -> no key."""

    async def _classify(*_a, **_k):
        return None

    monkeypatch.setattr(persistence, "classify_intent", _classify)

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-3",
        user_query="Tìm quán phở",
        platform_metadata={"mode_x": True},
    )
    assert message_id == 42
    inserts = _inserts(_fake_db)
    assert inserts[0]["platform_metadata"] == {"mode_x": True}
    assert "intent" not in inserts[0]["platform_metadata"]


async def test_flag_off_persists_without_intent(
    _fake_db, _quiet_guardrail, monkeypatch
):
    """Real classify_intent with DECISION_ENABLED=false -> no key, insert OK."""
    monkeypatch.setenv("DECISION_ENABLED", "false")
    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-4",
        user_query="Tìm quán phở",
        platform_metadata=None,
    )
    assert message_id == 42
    inserts = _inserts(_fake_db)
    assert inserts[0]["platform_metadata"] is None


async def test_guardrail_raise_does_not_block_intent(_fake_db, monkeypatch):
    """The other gather leg failing must not lose the intent payload."""

    async def _boom(*_a, **_k):
        raise RuntimeError("guardrail exploded")

    async def _classify(*_a, **_k):
        return dict(_INTENT_PAYLOAD)

    monkeypatch.setattr(persistence, "check_passage", _boom)
    monkeypatch.setattr(persistence, "classify_intent", _classify)

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-x",
        user_query="Tìm quán phở",
        platform_metadata=None,
    )
    assert message_id == 42
    inserts = _inserts(_fake_db)
    assert inserts[0]["platform_metadata"] == {"intent": _INTENT_PAYLOAD}


async def test_caller_supplied_intent_key_is_stripped(
    _fake_db, _quiet_guardrail, monkeypatch
):
    """platform_metadata is client-controlled — a spoofed "intent" key
    must not reach the row when the classifier produced no payload."""

    async def _classify(*_a, **_k):
        return None

    monkeypatch.setattr(persistence, "classify_intent", _classify)
    caller_meta = {"intent": {"label": "complaint"}, "mode_x": True}

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-s",
        user_query="Tìm quán phở",
        platform_metadata=caller_meta,
    )
    assert message_id == 42
    inserts = _inserts(_fake_db)
    assert inserts[0]["platform_metadata"] == {"mode_x": True}
    # ...and the caller's dict still holds its original (unstripped) data.
    assert caller_meta == {"intent": {"label": "complaint"}, "mode_x": True}


async def test_insert_succeeds_when_classify_raises(
    _fake_db, _quiet_guardrail, monkeypatch
):
    async def _boom(*_a, **_k):
        raise RuntimeError("classify exploded")

    monkeypatch.setattr(persistence, "classify_intent", _boom)

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-5",
        user_query="Tìm quán phở",
        platform_metadata=None,
    )
    assert message_id == 42
    inserts = _inserts(_fake_db)
    assert inserts[0]["platform_metadata"] is None


async def test_race_path_does_not_rewrite_metadata(_quiet_guardrail, monkeypatch):
    """Conflict -> race_recovered: existing row returned, no second write."""
    captured: list = []
    monkeypatch.setattr(
        persistence,
        "shielded_async_session",
        lambda: _FakeSessionCM(captured, insert_id=None),  # conflict
    )

    async def _classify(*_a, **_k):
        return dict(_INTENT_PAYLOAD)

    monkeypatch.setattr(persistence, "classify_intent", _classify)

    message_id = await persistence.persist_user_turn(
        chat_id=1,
        user_id=None,
        turn_id="t-6",
        user_query="Tìm quán phở",
        platform_metadata=None,
    )
    assert message_id == 99  # existing row's id via the lookup SELECT
    # Exactly two statements: the (no-op'd) INSERT and the lookup SELECT —
    # no UPDATE rewriting the existing row's metadata.
    assert len(captured) == 2
    assert isinstance(captured[0], Insert)
    assert not isinstance(captured[1], Insert)
