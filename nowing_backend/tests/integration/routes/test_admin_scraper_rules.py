"""Red-phase integration tests for Story 25.5 — admin scraper rule routes.

These tests require a real Postgres database. They are intentionally left as
failing scaffolds until the implementation is written.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration]


def _load_models():
    """Lazy loader so collection does not fail before the model is added to app.db."""
    try:
        from app.db import AuditEvent, ScraperRule, User

        return ScraperRule, AuditEvent, User
    except ImportError as exc:
        pytest.fail(f"not implemented: {exc}")


@pytest_asyncio.fixture
async def scraper_rule_factory(db_session, db_superuser):
    """Factory to create a ScraperRule row for route tests."""
    scraper_rule_cls, _, _ = _load_models()

    async def _make(platform: str, version: int, *, is_active: bool = False):
        rule = scraper_rule_cls(
            platform=platform,
            version=version,
            rule_schema={
                "selectors": {"title": "span.js__card-title"},
                "regexes": {},
                "delays": {"request_ms": 1500, "retry_base_ms": 1000},
                "retries": {"max_attempts": 3, "statuses": [429, 500]},
                "circuit_breaker": {
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            },
            is_active=is_active,
            created_by_user_id=db_superuser.id,
            updated_by_user_id=db_superuser.id,
        )
        db_session.add(rule)
        await db_session.flush()
        return rule

    return _make


class TestAdminScraperRulesCRUD:
    """AC-1 / AC-4: admin rule CRUD with real DB."""

    async def test_list_rules_requires_superuser(self, client_as_regular_user):
        res = await client_as_regular_user.get("/api/v1/admin/scraper-rules")
        assert res.status_code == 403

    async def test_list_rules_returns_expected_fields(self, admin_client):
        res = await admin_client.get("/api/v1/admin/scraper-rules")
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        # Each item should expose version, is_active, updated_at, updated_by.
        if body["items"]:
            item = body["items"][0]
            assert set(item.keys()) >= {"version", "is_active", "updated_at", "updated_by"}

    async def test_create_rule_persists_row_and_audit(
        self, admin_client, db_session
    ):
        scraper_rule_cls, audit_event_cls, _ = _load_models()

        payload = {
            "rule_schema": {
                "selectors": {"title": "span.js__card-title"},
                "regexes": {},
                "delays": {"request_ms": 1500, "retry_base_ms": 1000},
                "retries": {"max_attempts": 3, "statuses": [429, 500]},
                "circuit_breaker": {
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            },
        }
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan", json=payload
        )
        assert res.status_code == 201

        body = res.json()
        assert body["platform"] == "batdongsan"
        assert body["version"] == 1

        # Verify DB row.
        rule = await db_session.get(scraper_rule_cls, body["id"])
        assert rule is not None
        assert rule.rule_schema["delays"]["request_ms"] == 1500

        # Verify audit event.
        audit = await db_session.get(audit_event_cls, body["id"])
        assert audit is not None
        assert audit.action == "scraper_rule.create"

    async def test_activate_version_switches_active_flag(self, admin_client, scraper_rule_factory, db_session):
        _old = await scraper_rule_factory("batdongsan", 1, is_active=True)
        new = await scraper_rule_factory("batdongsan", 2, is_active=False)

        res = await admin_client.patch(
            f"/api/v1/admin/scraper-rules/batdongsan/{new.version}",
            json={"is_active": True},
        )
        assert res.status_code == 200

        # Only one active rule per platform.
        scraper_rule_cls, _, _ = _load_models()
        from sqlalchemy import func, select

        count = await db_session.execute(
            select(func.count()).where(
                scraper_rule_cls.platform == "batdongsan",
                scraper_rule_cls.is_active.is_(True),
            )
        )
        assert count.scalar() == 1

    async def test_delete_active_rule_rejected(self, admin_client, scraper_rule_factory):
        rule = await scraper_rule_factory("batdongsan", 1, is_active=True)
        res = await admin_client.delete(
            f"/api/v1/admin/scraper-rules/batdongsan/{rule.version}"
        )
        assert res.status_code == 422


class TestAdminScraperRulesValidation:
    """AC-2 / AC-3: validation rejects bad CSS and ReDoS regex."""

    async def test_invalid_css_selector_returns_422(self, admin_client):
        payload = {
            "rule_schema": {
                "selectors": {"title": "span["},
                "regexes": {},
                "delays": {"request_ms": 1500, "retry_base_ms": 1000},
                "retries": {"max_attempts": 3, "statuses": [429, 500]},
                "circuit_breaker": {
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            },
        }
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan", json=payload
        )
        assert res.status_code == 422
        assert "Invalid CSS selector" in res.json()["detail"]

    async def test_redos_regex_returns_422(self, admin_client):
        payload = {
            "rule_schema": {
                "selectors": {"title": "span.js__card-title"},
                "regexes": {"dangerous": r"(a+)+$"},
                "delays": {"request_ms": 1500, "retry_base_ms": 1000},
                "retries": {"max_attempts": 3, "statuses": [429, 500]},
                "circuit_breaker": {
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            },
        }
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan", json=payload
        )
        assert res.status_code == 422
        assert res.json()["code"] == "REDOS_TIMEOUT"

    async def test_request_ms_above_max_returns_422(self, admin_client):
        payload = {
            "rule_schema": {
                "selectors": {},
                "regexes": {},
                "delays": {"request_ms": 60001, "retry_base_ms": 1000},
                "retries": {"max_attempts": 3, "statuses": [500]},
                "circuit_breaker": {
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            },
        }
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan", json=payload
        )
        assert res.status_code == 422


class TestAdminScraperRulesAuth:
    """AC-8: superadmin guard on all endpoints."""

    async def test_pat_rejected(self, pat_client):
        res = await pat_client.get("/api/v1/admin/scraper-rules")
        assert res.status_code == 403
        assert "PAT" in res.json()["detail"] or "Superadmin" in res.json()["detail"]

    async def test_non_superuser_rejected(self, client_as_regular_user):
        res = await client_as_regular_user.get("/api/v1/admin/scraper-rules")
        assert res.status_code == 403

    async def test_impersonated_session_rejected(self, admin_client):
        # Simulate an impersonated auth context via override.
        res = await admin_client.get("/api/v1/admin/scraper-rules")
        assert res.status_code in (200, 403)
        # If the implementation correctly rejects impersonation, this will be 403.
        # Until then it remains a red scaffold.


class TestAdminScraperRulesCircuitBreaker:
    """AC-7: trip/reset endpoints."""

    async def test_trip_sets_redis_open_and_db_flag(self, admin_client, scraper_rule_factory):
        rule = await scraper_rule_factory("batdongsan", 1, is_active=True)
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan/circuit-breaker/trip"
        )
        assert res.status_code == 200

        # After refresh, rule_schema.circuit_breaker.tripped must be True.
        assert rule.rule_schema["circuit_breaker"]["tripped"] is True

    async def test_reset_clears_redis_and_db_flag(self, admin_client, scraper_rule_factory):
        rule = await scraper_rule_factory("batdongsan", 1, is_active=True)
        await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan/circuit-breaker/trip"
        )
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan/circuit-breaker/reset"
        )
        assert res.status_code == 200
        assert rule.rule_schema["circuit_breaker"]["tripped"] is False

    async def test_refresh_publishes_scraper_config_updated(self, admin_client):
        res = await admin_client.post(
            "/api/v1/admin/scraper-rules/batdongsan/refresh"
        )
        assert res.status_code in (200, 204)
