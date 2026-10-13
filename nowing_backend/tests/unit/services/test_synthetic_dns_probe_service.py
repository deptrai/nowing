"""Unit tests for SyntheticDnsProbeService and Celery DNS probe task."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dns.synthetic_probe_service import (
    DomainProbeReport,
    ProbeResult,
    SyntheticDnsProbeService,
    verify_cname_record,
    verify_txt_record,
)


@pytest.mark.unit
def test_verify_txt_record_success():
    """Verify TXT record passes when expected token matches."""
    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_rdata = MagicMock()
        mock_rdata.strings = [b"nowing-verify=secret-token-123"]
        mock_resolve.return_value = [mock_rdata]

        res = verify_txt_record("shop.example.com", expected_token="secret-token-123")
        assert res.success is True
        assert res.status == "ok"
        assert res.record_type == "TXT"


@pytest.mark.unit
def test_verify_txt_record_mismatch():
    """Verify TXT record fails when found token is different."""
    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_rdata = MagicMock()
        mock_rdata.strings = [b"nowing-verify=wrong-token"]
        mock_resolve.return_value = [mock_rdata]

        res = verify_txt_record("shop.example.com", expected_token="secret-token-123")
        assert res.success is False
        assert res.status == "mismatch"


@pytest.mark.unit
def test_verify_txt_record_hostname_too_long():
    """Verify hostname exceeding 253 characters fails fast with invalid status."""
    long_domain = "a" * 250 + ".com"
    res = verify_txt_record(long_domain, expected_token="token")
    assert res.success is False
    assert res.status == "invalid"
    assert "exceeds maximum 253 characters" in (res.error_message or "")


@pytest.mark.unit
def test_verify_cname_record_direct_match():
    """Verify CNAME record passes when pointing to expected target."""
    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_rdata = MagicMock()
        mock_rdata.target = "cname-ingress.apps.nowing.net."
        mock_resolve.return_value = [mock_rdata]

        res = verify_cname_record(
            "sub.mybrand.vn",
            expected_target="cname-ingress.apps.nowing.net",
        )
        assert res.success is True
        assert res.status == "ok"


@pytest.mark.unit
def test_verify_cname_record_mismatch():
    """Verify CNAME record fails when pointing to a foreign target."""
    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_rdata = MagicMock()
        mock_rdata.target = "other-service.cloudflare.com."
        mock_resolve.return_value = [mock_rdata]

        res = verify_cname_record(
            "sub.mybrand.vn",
            expected_target="cname-ingress.apps.nowing.net",
        )
        assert res.success is False
        assert res.status == "mismatch"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_probe_service_healthy_flow():
    """Probe service processes healthy domains without dispatching alerts."""
    mock_app = MagicMock()
    mock_app.id = "app-123"
    mock_app.name = "Storefront"
    mock_app.custom_domain = "store.customer.com"
    mock_app.custom_domain_verify_token = "tok-123"
    mock_app.workspace_id = 1
    mock_app.user_id = None

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_app]
    mock_session.execute.return_value = mock_result

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    service = SyntheticDnsProbeService(session=mock_session, redis=mock_redis)

    healthy_report = DomainProbeReport(
        domain="store.customer.com",
        txt_result=ProbeResult("TXT", "_nowing-verify.store.customer.com", "tok", ["tok"], True, "ok"),
        cname_result=ProbeResult("CNAME", "store.customer.com", "target", ["target"], True, "ok"),
        is_healthy=True,
        checked_at="2026-10-13T12:00:00Z",
    )

    with patch("app.services.dns.synthetic_probe_service.probe_domain", return_value=healthy_report):
        summary = await service.probe_all_active_custom_domains()

    assert summary["scanned"] == 1
    assert summary["healthy"] == 1
    assert summary["unhealthy"] == 0
    assert summary["alerts_dispatched"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_probe_service_unhealthy_flow_dispatches_alerts():
    """Probe service detects unhealthy domain and dispatches in-app and AdminHealthAlert."""
    mock_app = MagicMock()
    mock_app.id = "app-456"
    mock_app.name = "My Landing Page"
    mock_app.custom_domain = "landing.example.com"
    mock_app.custom_domain_verify_token = "tok-456"
    mock_app.workspace_id = 2
    mock_app.user_id = MagicMock()  # User exists

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    # First query for apps
    apps_res = MagicMock()
    apps_res.scalars.return_value.all.return_value = [mock_app]
    # Second query for existing AdminHealthAlert (None)
    alert_res = MagicMock()
    alert_res.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [apps_res, alert_res]

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Not in cooldown

    service = SyntheticDnsProbeService(session=mock_session, redis=mock_redis)

    unhealthy_report = DomainProbeReport(
        domain="landing.example.com",
        txt_result=ProbeResult("TXT", "_nowing-verify.landing.example.com", "tok", [], False, "missing", "Record missing"),
        cname_result=ProbeResult("CNAME", "landing.example.com", "target", ["target"], True, "ok"),
        is_healthy=False,
        checked_at="2026-10-13T12:00:00Z",
    )

    with (
        patch("app.services.dns.synthetic_probe_service.probe_domain", return_value=unhealthy_report),
        patch("app.notifications.service.facade.NotificationService.create_notification", new_callable=AsyncMock) as mock_notify,
        patch.object(service, "_dispatch_telegram_alert", new_callable=AsyncMock) as mock_tg,
    ):
        summary = await service.probe_all_active_custom_domains()

    assert summary["scanned"] == 1
    assert summary["healthy"] == 0
    assert summary["unhealthy"] == 1
    assert summary["alerts_dispatched"] == 1

    # Verify notification was sent
    mock_notify.assert_called_once()
    mock_tg.assert_called_once()
    # Verify AdminHealthAlert was added to session
    mock_session.add.assert_called_once()
    # Verify cooldown was written to Redis
    mock_redis.set.assert_any_call("dns_probe:alert_cooldown:app-456", "1", ex=service.cooldown_seconds)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_probe_service_unhealthy_cooldown_dedup():
    """Unhealthy domain in active cooldown skips duplicate alert dispatch."""
    mock_app = MagicMock()
    mock_app.id = "app-789"
    mock_app.name = "My Shop"
    mock_app.custom_domain = "shop.brand.com"
    mock_app.custom_domain_verify_token = "tok-789"
    mock_app.workspace_id = 3
    mock_app.user_id = MagicMock()

    mock_session = AsyncMock()
    apps_res = MagicMock()
    apps_res.scalars.return_value.all.return_value = [mock_app]
    mock_session.execute.return_value = apps_res

    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"1"  # Already in cooldown

    service = SyntheticDnsProbeService(session=mock_session, redis=mock_redis)

    unhealthy_report = DomainProbeReport(
        domain="shop.brand.com",
        txt_result=ProbeResult("TXT", "_nowing-verify.shop.brand.com", "tok", [], False, "missing", "Error"),
        cname_result=ProbeResult("CNAME", "shop.brand.com", "target", [], False, "missing", "Error"),
        is_healthy=False,
        checked_at="2026-10-13T12:00:00Z",
    )

    with (
        patch("app.services.dns.synthetic_probe_service.probe_domain", return_value=unhealthy_report),
        patch("app.notifications.service.facade.NotificationService.create_notification", new_callable=AsyncMock) as mock_notify,
    ):
        summary = await service.probe_all_active_custom_domains()

    assert summary["scanned"] == 1
    assert summary["unhealthy"] == 1
    assert summary["alerts_dispatched"] == 0
    mock_notify.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_probe_service_recovery_flow():
    """Recovered domain resolves open AdminHealthAlert and clears cooldown."""
    mock_app = MagicMock()
    mock_app.id = "app-recovered"
    mock_app.name = "Recovered App"
    mock_app.custom_domain = "recovered.com"
    mock_app.custom_domain_verify_token = "tok-rec"
    mock_app.workspace_id = 1
    mock_app.user_id = MagicMock()

    mock_alert = MagicMock()
    mock_alert.status = "open"

    mock_session = AsyncMock()
    apps_res = MagicMock()
    apps_res.scalars.return_value.all.return_value = [mock_app]
    open_alerts_res = MagicMock()
    open_alerts_res.scalars.return_value.all.return_value = [mock_alert]

    mock_session.execute.side_effect = [apps_res, open_alerts_res]

    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"1"  # Was previously failing

    service = SyntheticDnsProbeService(session=mock_session, redis=mock_redis)

    healthy_report = DomainProbeReport(
        domain="recovered.com",
        txt_result=ProbeResult("TXT", "_nowing-verify.recovered.com", "tok", ["tok"], True, "ok"),
        cname_result=ProbeResult("CNAME", "recovered.com", "target", ["target"], True, "ok"),
        is_healthy=True,
        checked_at="2026-10-13T12:00:00Z",
    )

    with (
        patch("app.services.dns.synthetic_probe_service.probe_domain", return_value=healthy_report),
        patch("app.notifications.service.facade.NotificationService.create_notification", new_callable=AsyncMock) as mock_notify,
    ):
        summary = await service.probe_all_active_custom_domains()

    assert summary["healthy"] == 1
    assert mock_alert.status == "resolved"
    mock_redis.delete.assert_any_call("dns_probe:alert_cooldown:app-recovered")
    mock_redis.delete.assert_any_call("dns_probe:is_failing:app-recovered")
    mock_notify.assert_called_once()


@pytest.mark.unit
def test_celery_task_execution():
    """Verify Celery task delegates to run_async_celery_task."""
    from app.tasks.celery_tasks.dns_probe_task import dns_synthetic_probe_periodic_task

    mock_summary = {"scanned": 5, "healthy": 5, "unhealthy": 0, "alerts_dispatched": 0}

    with patch("app.tasks.celery_tasks.dns_probe_task.run_async_celery_task", return_value=mock_summary) as mock_run:
        result = dns_synthetic_probe_periodic_task()
        assert result == mock_summary
        mock_run.assert_called_once()
