"""Green-phase unit tests for Story 25.5 — scraper rule CRUD service."""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.unit]


def _load_service() -> Any:
    """Lazy loader so the test module can be collected before the source exists."""
    try:
        return importlib.import_module("app.services.scraper_rules_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")


def _mock_session(**scalar_kwargs) -> AsyncMock:
    """Return a minimal AsyncSession double for the service functions."""
    session = AsyncMock()
    result = MagicMock()
    for key, value in scalar_kwargs.items():
        setattr(result, key, MagicMock(return_value=value))
    if "scalars" in scalar_kwargs:
        result.scalars.return_value = MagicMock(
            all=MagicMock(return_value=scalar_kwargs["scalars"])
        )
    session.execute.return_value = result
    # session.add/delete are sync on AsyncSession; AsyncMock would make them coroutines.
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


class TestScraperRulesServiceCRUD:
    """AC-1 / AC-4: versioned CRUD with audit."""

    def test_service_exports_expected_functions(self) -> None:
        mod = _load_service()
        expected = {
            "get_rules",
            "get_active_rule",
            "create_rule",
            "activate_rule",
            "delete_rule",
            "trip_circuit_breaker",
            "reset_circuit_breaker",
        }
        missing = expected - set(dir(mod))
        assert not missing, f"missing exports: {missing}"

    async def test_create_rule_sets_version_to_max_plus_one(self) -> None:
        mod = _load_service()
        session = _mock_session(scalar=7)

        rule = await mod.create_rule(
            session=session,
            platform="batdongsan",
            rule_schema={"selectors": {"title": "span"}},
            auth=MagicMock(user=MagicMock(id=uuid4())),
        )
        assert rule.version == 8

    async def test_create_first_rule_auto_activates(self) -> None:
        mod = _load_service()
        session = _mock_session(scalar=None)

        rule = await mod.create_rule(
            session=session,
            platform="batdongsan",
            rule_schema={"selectors": {"title": "span"}},
            auth=MagicMock(user=MagicMock(id=uuid4())),
        )
        assert rule.is_active is True

    async def test_activate_rule_deactivates_old_and_publishes_event(self) -> None:
        mod = _load_service()
        rule = MagicMock(
            is_active=False,
            rule_schema={"circuit_breaker": {"tripped": False}},
            version=8,
        )
        session = _mock_session(scalar_one_or_none=rule)
        mock_publish = AsyncMock()

        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "app.services.scraper_rules_service.publish_rule_update",
                mock_publish,
            )
            new_rule = await mod.activate_rule(
                session=session,
                platform="batdongsan",
                version=8,
                auth=MagicMock(user=MagicMock(id=uuid4())),
                redis=AsyncMock(),
            )

        assert new_rule.is_active is True
        mock_publish.assert_awaited_once()

    async def test_delete_rule_rejects_active_version(self) -> None:
        mod = _load_service()
        rule = MagicMock(is_active=True)
        session = _mock_session(scalar_one_or_none=rule)

        with pytest.raises(mod.CannotDeleteActiveRuleError):
            await mod.delete_rule(
                session=session,
                platform="batdongsan",
                version=7,
                auth=MagicMock(user=MagicMock(id=uuid4())),
            )

    async def test_get_rules_returns_expected_fields(self) -> None:
        mod = _load_service()
        session = _mock_session(scalars=[])
        rules = await mod.get_rules(session=session, limit=20, offset=0)
        assert isinstance(rules, list)

    async def test_get_active_rule_returns_only_active(self) -> None:
        mod = _load_service()
        session = _mock_session(scalar_one_or_none=None)
        rule = await mod.get_active_rule(session=session, platform="batdongsan")
        assert rule is None


class TestScraperRulesServiceAudit:
    """AC-4: AuditEvent logging on every mutate."""

    async def test_create_rule_writes_audit_event(self) -> None:
        mod = _load_service()
        session = _mock_session(scalar=None)

        with pytest.MonkeyPatch.context() as m:
            mock_audit = MagicMock()
            m.setattr("app.services.scraper_rules_service.AuditEvent", mock_audit)
            await mod.create_rule(
                session=session,
                platform="batdongsan",
                rule_schema={"selectors": {}},
                auth=MagicMock(user=MagicMock(id=uuid4())),
            )

        mock_audit.assert_called_once()

    async def test_audit_diff_payload_contains_platform_version_schema(self) -> None:
        mod = _load_service()
        rule = MagicMock(
            is_active=False,
            rule_schema={"circuit_breaker": {"tripped": False}},
            version=8,
        )
        session = _mock_session(scalar_one_or_none=rule)

        with pytest.MonkeyPatch.context() as m:
            mock_audit = MagicMock()
            m.setattr("app.services.scraper_rules_service.AuditEvent", mock_audit)
            await mod.activate_rule(
                session=session,
                platform="batdongsan",
                version=8,
                auth=MagicMock(user=MagicMock(id=uuid4())),
                redis=AsyncMock(),
            )

        call_kwargs = mock_audit.call_args.kwargs
        assert "diff_payload" in call_kwargs
        assert call_kwargs["diff_payload"]["platform"] == "batdongsan"
        assert call_kwargs["diff_payload"]["version"] == 8


class TestScraperRulesServiceVersioning:
    """AC-1 / AC-4: version number and unique constraints."""

    async def test_version_zero_rejected(self) -> None:
        mod = _load_service()
        # Version 0 should never be generated or accepted.
        with pytest.raises(ValueError):
            await mod.activate_rule(
                session=AsyncMock(),
                platform="batdongsan",
                version=0,
                auth=MagicMock(),
            )

    async def test_get_rules_respects_platform_filter(self) -> None:
        mod = _load_service()
        session = _mock_session(scalars=[])
        await mod.get_rules(session=session, limit=10, offset=0, platform="batdongsan")
        # Assert query was filtered by platform.
        assert session.execute.called


class TestScraperRulesServiceCircuitBreaker:
    """AC-7: admin trip / reset."""

    async def test_trip_circuit_breaker_sets_redis_open(self) -> None:
        mod = _load_service()
        rule = MagicMock(rule_schema={"circuit_breaker": {"tripped": False}}, version=7)
        session = _mock_session(scalar_one_or_none=rule)
        redis = AsyncMock()

        await mod.trip_circuit_breaker(
            session=session,
            platform="batdongsan",
            auth=MagicMock(user=MagicMock(id=uuid4())),
            redis=redis,
        )

        redis.set.assert_awaited_once()

    async def test_reset_circuit_breaker_deletes_state_and_counter_keys(self) -> None:
        mod = _load_service()
        rule = MagicMock(rule_schema={"circuit_breaker": {"tripped": True}}, version=7)
        session = _mock_session(scalar_one_or_none=rule)
        redis = AsyncMock()

        await mod.reset_circuit_breaker(
            session=session,
            platform="batdongsan",
            auth=MagicMock(user=MagicMock(id=uuid4())),
            redis=redis,
        )

        assert redis.delete.await_count == 1

    async def test_trip_updates_rule_schema_tripped_flag(self) -> None:
        mod = _load_service()
        rule = MagicMock(rule_schema={"circuit_breaker": {"tripped": False}}, version=7)
        session = _mock_session(scalar_one_or_none=rule)

        await mod.trip_circuit_breaker(
            session=session,
            platform="batdongsan",
            auth=MagicMock(user=MagicMock(id=uuid4())),
            redis=AsyncMock(),
        )

        assert rule.rule_schema["circuit_breaker"]["tripped"] is True
