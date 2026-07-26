"""In-process double for the sync ``redis`` client used by rate-limit counters.

Shared so that "no test may open a real Redis connection" is a property a module
can *install* rather than a discipline every test author has to remember. The
first version of this lived privately inside
``tests/unit/memory/test_auto_extract_gate.py``; two integration tests then
raised ``MEMORY_AUTO_EXTRACT_RATE_MAX`` above zero without it and silently
started reading a live ``redis://localhost:6379/0``, which is exactly the class
of mistake a shared installer prevents.

Covers only the three commands the counters use (``get`` / ``incr`` /
``expire``). Deliberately not a full Redis emulation.
"""

from __future__ import annotations

from collections import defaultdict


class FakeRedis:
    """Minimal sync-Redis double.

    ``fail=True`` makes every command raise, which is how the
    Redis-unavailable fallback paths are exercised without touching a socket.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.store: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    def _guard(self) -> None:
        if self.fail:
            raise RuntimeError("redis unavailable")

    def get(self, key: str) -> str | None:
        self._guard()
        value = self.store.get(key)
        return None if value is None else str(value)

    def incr(self, key: str) -> int:
        self._guard()
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key: str, seconds: int) -> bool:
        self._guard()
        self.ttls[key] = seconds
        return True


def install_fake_redis(monkeypatch, module, *, fail: bool = False) -> FakeRedis:
    """Point ``module``'s cached Redis client at a :class:`FakeRedis`.

    Also rebinds ``module._memory_hits`` to a **fresh** ``defaultdict(list)``.
    That matters: the in-memory fallback container is mutated in place, so
    clearing the production one at setup would protect this test from earlier
    residue while leaking its own residue forward, and
    ``monkeypatch.setattr(module, "_memory_hits", module._memory_hits)`` would
    be a no-op (it records and restores the same object). Installing a new
    container makes monkeypatch's teardown genuinely restore the original.

    Returns the double so tests can seed ``.store`` or assert on ``.ttls``.
    """
    client = FakeRedis(fail=fail)
    monkeypatch.setattr(module, "_redis", client)
    monkeypatch.setattr(module, "_memory_hits", defaultdict(list))
    return client
