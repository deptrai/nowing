"""Synthetic DNS Probe Service for custom domain monitoring and alerting.

Periodically verifies that active custom domains have their required
_nowing-verify.<domain> TXT record and CNAME ingress target intact.
Dispatches in-app, Telegram, and AdminHealthAlerts with Redis cooldown
deduplication when records are missing or misconfigured.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import dns.exception
import dns.resolver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    CNAME_INGRESS_HOST,
    WEB_BUILDER_TXT_VERIFY_LABEL,
    WEB_BUILDER_TXT_VERIFY_PREFIX,
)
from app.models.admin_health import AdminHealthAlert
from app.models.workspaces import WorkspaceApp
from app.notifications.constants import TITLE_MAX_LENGTH
from app.notifications.service.facade import NotificationService

logger = logging.getLogger(__name__)

DEFAULT_CNAME_TARGET = CNAME_INGRESS_HOST or "cname-ingress.apps.nowing.net"
DEFAULT_TXT_LABEL = WEB_BUILDER_TXT_VERIFY_LABEL or "_nowing-verify"
DEFAULT_TXT_PREFIX = WEB_BUILDER_TXT_VERIFY_PREFIX or "nowing-verify="
DEFAULT_COOLDOWN_SECONDS = 43200  # 12 hours


@dataclass
class ProbeResult:
    """Outcome of a single DNS record verification check."""

    record_type: str
    target_host: str
    expected: str | None
    actual: list[str]
    success: bool
    status: str  # ok, missing, mismatch, invalid, error
    error_message: str | None = None


@dataclass
class DomainProbeReport:
    """Consolidated verification report for a domain."""

    domain: str
    txt_result: ProbeResult
    cname_result: ProbeResult
    is_healthy: bool
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary representation."""
        return asdict(self)


def _get_resolver(nameserver: str | None = None, timeout: float = 5.0) -> dns.resolver.Resolver:
    """Create a configured dns.resolver.Resolver instance."""
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout
    if nameserver:
        resolver.nameservers = [nameserver]
    return resolver


def verify_txt_record(
    domain: str,
    expected_token: str | None = None,
    nameserver: str | None = None,
    timeout: float = 5.0,
) -> ProbeResult:
    """Verify cryptographic proof-of-ownership TXT record for domain."""
    clean_domain = domain.lower().rstrip(".")
    txt_host = f"{DEFAULT_TXT_LABEL}.{clean_domain}"

    if len(txt_host) > 253:
        return ProbeResult(
            record_type="TXT",
            target_host=txt_host,
            expected=f"{DEFAULT_TXT_PREFIX}{expected_token}" if expected_token else f"{DEFAULT_TXT_PREFIX}*",
            actual=[],
            success=False,
            status="invalid",
            error_message=f"Hostname '{txt_host}' exceeds maximum 253 characters (RFC 1035).",
        )

    expected_val = f"{DEFAULT_TXT_PREFIX}{expected_token}" if expected_token else None
    actual_values: list[str] = []

    try:
        resolver = _get_resolver(nameserver=nameserver, timeout=timeout)
        answers = resolver.resolve(txt_host, "TXT")

        for rdata in answers:
            if hasattr(rdata, "strings") and isinstance(rdata.strings, (list, tuple)):
                raw_str = b"".join(rdata.strings).decode("utf-8", errors="replace")
                actual_values.append(raw_str)
            else:
                raw_str = str(rdata).strip('"')
                actual_values.append(raw_str)

        if not actual_values:
            return ProbeResult(
                record_type="TXT",
                target_host=txt_host,
                expected=expected_val or f"{DEFAULT_TXT_PREFIX}*",
                actual=[],
                success=False,
                status="missing",
                error_message=f"No TXT records found at '{txt_host}'.",
            )

        if expected_val is not None:
            for val in actual_values:
                if hmac.compare_digest(val, expected_val):
                    return ProbeResult(
                        record_type="TXT",
                        target_host=txt_host,
                        expected=expected_val,
                        actual=actual_values,
                        success=True,
                        status="ok",
                    )
            return ProbeResult(
                record_type="TXT",
                target_host=txt_host,
                expected=expected_val,
                actual=actual_values,
                success=False,
                status="mismatch",
                error_message=f"Found TXT values do not match expected '{expected_val}'.",
            )
        else:
            nowing_records = [v for v in actual_values if v.startswith(DEFAULT_TXT_PREFIX)]
            if nowing_records:
                return ProbeResult(
                    record_type="TXT",
                    target_host=txt_host,
                    expected=f"{DEFAULT_TXT_PREFIX}*",
                    actual=actual_values,
                    success=True,
                    status="ok",
                )
            return ProbeResult(
                record_type="TXT",
                target_host=txt_host,
                expected=f"{DEFAULT_TXT_PREFIX}*",
                actual=actual_values,
                success=False,
                status="missing",
                error_message=f"No TXT records starting with '{DEFAULT_TXT_PREFIX}' found at '{txt_host}'.",
            )

    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return ProbeResult(
            record_type="TXT",
            target_host=txt_host,
            expected=expected_val or f"{DEFAULT_TXT_PREFIX}*",
            actual=[],
            success=False,
            status="missing",
            error_message=f"TXT host '{txt_host}' does not exist or has no TXT answer.",
        )
    except dns.exception.Timeout:
        return ProbeResult(
            record_type="TXT",
            target_host=txt_host,
            expected=expected_val or f"{DEFAULT_TXT_PREFIX}*",
            actual=[],
            success=False,
            status="error",
            error_message=f"DNS query timed out after {timeout}s.",
        )
    except Exception as exc:
        return ProbeResult(
            record_type="TXT",
            target_host=txt_host,
            expected=expected_val or f"{DEFAULT_TXT_PREFIX}*",
            actual=[],
            success=False,
            status="error",
            error_message=str(exc),
        )


def verify_cname_record(
    domain: str,
    expected_target: str = DEFAULT_CNAME_TARGET,
    nameserver: str | None = None,
    timeout: float = 5.0,
) -> ProbeResult:
    """Verify proof-of-control CNAME (or apex A/AAAA fallback) for domain."""
    clean_domain = domain.lower().rstrip(".")
    target_clean = expected_target.lower().rstrip(".")
    resolver = _get_resolver(nameserver=nameserver, timeout=timeout)
    actual_targets: list[str] = []

    try:
        current = clean_domain
        chain_hops = 0
        max_hops = 5

        while chain_hops < max_hops:
            chain_hops += 1
            try:
                answers = resolver.resolve(current, "CNAME")
                target = str(answers[0].target).lower().rstrip(".")
                actual_targets.append(target)
                if target == target_clean:
                    return ProbeResult(
                        record_type="CNAME",
                        target_host=clean_domain,
                        expected=target_clean,
                        actual=actual_targets,
                        success=True,
                        status="ok",
                    )
                current = target
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                break

        if actual_targets:
            return ProbeResult(
                record_type="CNAME",
                target_host=clean_domain,
                expected=target_clean,
                actual=actual_targets,
                success=False,
                status="mismatch",
                error_message=f"CNAME chain points to '{actual_targets[-1]}', expected '{target_clean}'.",
            )

        # Fallback for apex/root domains using A/AAAA ALIAS pointing to same IPs
        domain_ips: set[str] = set()
        target_ips: set[str] = set()

        for qtype in ("A", "AAAA"):
            try:
                for rdata in resolver.resolve(clean_domain, qtype):
                    domain_ips.add(str(rdata))
            except Exception as exc:
                logger.debug("Apex resolution failed for %s (%s): %s", clean_domain, qtype, exc)
            try:
                for rdata in resolver.resolve(target_clean, qtype):
                    target_ips.add(str(rdata))
            except Exception as exc:
                logger.debug("Apex resolution failed for %s (%s): %s", target_clean, qtype, exc)

        if domain_ips and target_ips and domain_ips.intersection(target_ips):
            return ProbeResult(
                record_type="CNAME",
                target_host=clean_domain,
                expected=target_clean,
                actual=sorted(domain_ips),
                success=True,
                status="ok",
            )

        return ProbeResult(
            record_type="CNAME",
            target_host=clean_domain,
            expected=target_clean,
            actual=sorted(domain_ips),
            success=False,
            status="missing",
            error_message=f"Domain '{clean_domain}' has no CNAME pointing to '{target_clean}' and no matching apex IPs.",
        )

    except dns.exception.Timeout:
        return ProbeResult(
            record_type="CNAME",
            target_host=clean_domain,
            expected=target_clean,
            actual=[],
            success=False,
            status="error",
            error_message=f"DNS query timed out after {timeout}s.",
        )
    except Exception as exc:
        return ProbeResult(
            record_type="CNAME",
            target_host=clean_domain,
            expected=target_clean,
            actual=[],
            success=False,
            status="error",
            error_message=str(exc),
        )


def probe_domain(
    domain: str,
    expected_token: str | None = None,
    expected_cname_target: str = DEFAULT_CNAME_TARGET,
    nameserver: str | None = None,
    timeout: float = 5.0,
) -> DomainProbeReport:
    """Run both TXT and CNAME verification probes for a domain."""
    txt_res = verify_txt_record(
        domain=domain,
        expected_token=expected_token,
        nameserver=nameserver,
        timeout=timeout,
    )
    cname_res = verify_cname_record(
        domain=domain,
        expected_target=expected_cname_target,
        nameserver=nameserver,
        timeout=timeout,
    )
    is_healthy = txt_res.success and cname_res.success

    return DomainProbeReport(
        domain=domain,
        txt_result=txt_res,
        cname_result=cname_res,
        is_healthy=is_healthy,
        checked_at=datetime.now(UTC).isoformat(),
    )


class SyntheticDnsProbeService:
    """Service orchestrating periodic custom domain DNS synthetic probes and alerting."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Any | None = None,
        cname_target: str = DEFAULT_CNAME_TARGET,
        timeout: float = 5.0,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self.session = session
        self.redis = redis
        self.cname_target = cname_target
        self.timeout = timeout
        self.cooldown_seconds = cooldown_seconds

    async def _get_redis(self) -> Any:
        if self.redis is not None:
            return self.redis
        try:
            from app.redis_client import get_redis_client

            self.redis = await get_redis_client()
            return self.redis
        except Exception as exc:
            logger.debug("Redis unavailable for DNS probe cooldown: %s", exc)
            return None

    async def probe_all_active_custom_domains(self) -> dict[str, Any]:
        """Query all active custom domains from database, run probes, and dispatch alerts."""
        stmt = select(WorkspaceApp).where(
            WorkspaceApp.custom_domain.isnot(None),
            WorkspaceApp.custom_domain_status == "active",
        )
        res = await self.session.execute(stmt)
        apps = list(res.scalars().all())

        scanned = len(apps)
        healthy = 0
        unhealthy = 0
        alerts_dispatched = 0
        reports: list[dict[str, Any]] = []

        for app in apps:
            domain = str(app.custom_domain)
            token = str(app.custom_domain_verify_token) if app.custom_domain_verify_token else None

            # Run blocking DNS probes in thread pool to avoid blocking the event loop
            report = await asyncio.to_thread(
                probe_domain,
                domain=domain,
                expected_token=token,
                expected_cname_target=self.cname_target,
                timeout=self.timeout,
            )
            reports.append(report.to_dict())

            if report.is_healthy:
                healthy += 1
                await self._handle_healthy_recovery(app, report)
            else:
                unhealthy += 1
                dispatched = await self._handle_unhealthy_incident(app, report)
                if dispatched:
                    alerts_dispatched += 1

        return {
            "scanned": scanned,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "alerts_dispatched": alerts_dispatched,
            "reports": reports,
        }

    async def _handle_unhealthy_incident(
        self,
        app: WorkspaceApp,
        report: DomainProbeReport,
    ) -> bool:
        """Handle unhealthy domain probe: manage cooldown, record alert, and dispatch notifications."""
        redis = await self._get_redis()
        cooldown_key = f"dns_probe:alert_cooldown:{app.id}"
        failing_flag = f"dns_probe:is_failing:{app.id}"

        # Cooldown deduplication check
        if redis is not None:
            try:
                is_in_cooldown = await redis.get(cooldown_key)
                if is_in_cooldown:
                    logger.info("DNS probe alert for app %s (%s) is in cooldown; skipping alert dispatch", app.id, app.custom_domain)
                    return False
            except Exception as exc:
                logger.debug("Redis cooldown check failed: %s", exc)

        failures = []
        if not report.txt_result.success:
            failures.append(f"TXT record ({report.txt_result.status}): {report.txt_result.error_message}")
        if not report.cname_result.success:
            failures.append(f"CNAME record ({report.cname_result.status}): {report.cname_result.error_message}")
        failure_summary = "; ".join(failures)

        title = f"Custom Domain Alert: '{app.custom_domain}' verification failed"[:TITLE_MAX_LENGTH]
        message = (
            f"DNS synthetic probe detected an issue with domain '{app.custom_domain}' "
            f"for workspace app '{app.name}': {failure_summary}."
        )

        # 1. In-App Notification for app owner
        if app.user_id:
            try:
                await NotificationService.create_notification(
                    session=self.session,
                    user_id=app.user_id,
                    notification_type="custom_domain_dns_failed",
                    title=title,
                    message=message,
                    workspace_id=app.workspace_id,
                    notification_metadata={
                        "app_id": str(app.id),
                        "custom_domain": app.custom_domain,
                        "failure_summary": failure_summary,
                        "checked_at": report.checked_at,
                    },
                )
            except Exception as err:
                logger.warning("Failed to create in-app notification for user %s: %s", app.user_id, err)

        # 2. Telegram Notification if owner has bound Telegram account
        if app.user_id:
            await self._dispatch_telegram_alert(app, title, message)

        # 3. Create or update AdminHealthAlert for system monitoring
        service_id = f"custom_domain.{app.custom_domain}"
        existing_alert_stmt = select(AdminHealthAlert).where(
            AdminHealthAlert.service_id == service_id,
            AdminHealthAlert.status.in_(["open", "acknowledged"]),
        )
        existing_res = await self.session.execute(existing_alert_stmt)
        existing_alert = existing_res.scalar_one_or_none()

        now = datetime.now(UTC)
        if existing_alert:
            existing_alert.message = message
            existing_alert.updated_at = now
        else:
            admin_alert = AdminHealthAlert(
                service_id=service_id,
                status="open",
                severity="high",
                message=message,
                triggered_at=now,
            )
            self.session.add(admin_alert)

        await self.session.commit()

        # Mark cooldown and failing flag in Redis
        if redis is not None:
            try:
                await redis.set(cooldown_key, "1", ex=self.cooldown_seconds)
                await redis.set(failing_flag, "1")
            except Exception as exc:
                logger.debug("Redis set cooldown failed: %s", exc)

        return True

    async def _handle_healthy_recovery(
        self,
        app: WorkspaceApp,
        report: DomainProbeReport,
    ) -> None:
        """Handle domain recovery if it was previously in a failing state."""
        redis = await self._get_redis()
        cooldown_key = f"dns_probe:alert_cooldown:{app.id}"
        failing_flag = f"dns_probe:is_failing:{app.id}"

        was_failing = False
        if redis is not None:
            try:
                was_failing = bool(await redis.get(failing_flag))
                if was_failing:
                    await redis.delete(cooldown_key)
                    await redis.delete(failing_flag)
            except Exception as exc:
                logger.debug("Redis recovery check failed: %s", exc)

        # Auto-resolve any open AdminHealthAlert
        service_id = f"custom_domain.{app.custom_domain}"
        existing_alert_stmt = select(AdminHealthAlert).where(
            AdminHealthAlert.service_id == service_id,
            AdminHealthAlert.status.in_(["open", "acknowledged"]),
        )
        existing_res = await self.session.execute(existing_alert_stmt)
        open_alerts = list(existing_res.scalars().all())

        if open_alerts or was_failing:
            now = datetime.now(UTC)
            for alert in open_alerts:
                alert.status = "resolved"
                alert.resolved_at = now
                alert.updated_at = now

            if app.user_id and was_failing:
                recovery_title = f"Custom Domain Recovered: '{app.custom_domain}' is healthy"[:TITLE_MAX_LENGTH]
                recovery_msg = f"DNS synthetic probe confirmed that domain '{app.custom_domain}' is now properly verified."
                try:
                    await NotificationService.create_notification(
                        session=self.session,
                        user_id=app.user_id,
                        notification_type="custom_domain_dns_recovered",
                        title=recovery_title,
                        message=recovery_msg,
                        workspace_id=app.workspace_id,
                        notification_metadata={
                            "app_id": str(app.id),
                            "custom_domain": app.custom_domain,
                            "checked_at": report.checked_at,
                        },
                    )
                except Exception as err:
                    logger.warning("Failed to dispatch recovery in-app notification: %s", err)

            await self.session.commit()

    async def _dispatch_telegram_alert(
        self,
        app: WorkspaceApp,
        title: str,
        message: str,
    ) -> None:
        """Send best-effort Telegram notification if the user has an active Telegram binding."""
        from app.automations.services.telegram_notifications import (
            account_token,
            resolve_telegram_binding_for_run,
        )
        from app.gateway.telegram.adapter import TelegramAdapter
        from app.gateway.telegram.formatting import escape_markdown_v2

        try:
            binding = await resolve_telegram_binding_for_run(
                self.session,
                user_id=app.user_id,
                workspace_id=app.workspace_id,
            )
            if not binding or not binding.external_peer_id:
                return

            token = account_token(binding.account)
            if not token:
                return

            adapter = TelegramAdapter(token)
            raw_text = f"🚨 *{title}*\n\n{message}"
            escaped_text = escape_markdown_v2(raw_text)

            await adapter.send_message(
                external_peer_id=binding.external_peer_id,
                text=escaped_text,
                parse_mode="MarkdownV2",
            )
        except Exception as err:
            logger.warning("Failed to dispatch Telegram alert for domain %s: %s", app.custom_domain, err)
