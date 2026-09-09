---
story_key: 21-8f-xactions-governance-health-integration
status: done
epic: 21
story: 8f
---

# Story 21.8f: XActions Governance and Health Integration

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-11, AD-SOC-7  
**Split from:** Story 21.8 — Social Ingress via XActions Integration (baseline)

---

## Story

As a Nowing platform admin,  
I want to see XActions governor status, stream metrics, and alerts in the Nowing admin dashboard,  
so that I can detect scraping issues early.

---

## Acceptance Criteria

1. **Governor Status** — **Given** admin telemetry, **When** `x_governor_status` is called, **Then** it displays healthy proxy count, consumer quota, and backpressure status.
2. **Stream Metrics** — **Given** admin telemetry, **When** `x_admin_stream_metrics` is called, **Then** it displays stream length, consumer lag, and throughput.
3. **Alert Hooks** — **Given** `x_admin_stream_alerts` breach, **When** it occurs, **Then** Nowing sends an alert via Telegram/Email.
4. **Health Probe** — **Given** the Nowing health probe system, **When** it checks XActions, **Then** it reports MCP connectivity and governor health.

---

## Tasks / Subtasks

- [x] Task 1: Health probe
  - [x] 1.1 Update `app/services/health/probes/xactions_probe.py` to check MCP/governor status.
  - [x] 1.2 Update `tests/unit/services/health/test_xactions_probe.py`.
- [x] Task 2: Governor and stream metrics callers
  - [x] 2.1 Add Celery beat `health_probe_xactions` every 5 minutes calling `x_governor_status` and `x_admin_stream_metrics`.
  - [x] 2.2 Expose internal admin endpoint or `HealthProbe` returning aggregated metrics.
- [x] Task 3: Alert dispatch
  - [x] 3.1 On `x_admin_stream_alerts` breach, call `execute_alert_rule` for matching rules.
  - [x] 3.2 Send Telegram/Email via existing alert channels.
- [x] Task 4: Admin dashboard
  - [x] 4.1 Add admin UI widget for XActions governor and stream metrics.

---

## Dev Notes

- Health probe should reuse existing `health/probes` pattern and not crash if XActions is unreachable; degrade gracefully.
- Governor metrics include consumer quota (RPM/burst) and backpressure multiplier.
- Alert rule call signature: `execute_alert_rule(session=session, alert_rule=rule, fired_at=datetime.now(UTC))`.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-xactions-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/services/health/probes/xactions_probe.py]
- [Code: nowing_backend/app/services/health/registry.py]
