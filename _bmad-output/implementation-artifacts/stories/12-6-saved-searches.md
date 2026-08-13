---
title: Story 12.6 — Saved Searches
epic: 12
story: 6
status: done
priority: P0
---

# Story 12.6 — Saved Searches

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** researcher  
**I want:** to save complex search queries and auto-run them on schedule  
**So that:** I always have fresh results without manual work.

---

## Acceptance Criteria

### AC-1 — Save search query with schedule
**Given** a search query with filters, **When** saved, **Then** it persists with `schedule: 'daily' | 'weekly' | 'none'`, `timezone`, and `enabled` flag; it appears in my saved searches list.

### AC-2 — Scheduled run executes
**Given** a saved search with `schedule='daily'`, **When** the alert scheduler triggers at the configured time (default 00:00 UTC), **Then** it runs `vn_jobs.aggregate` and produces a run record.

### AC-3 — Delta detection
**Given** run N and run N+1 complete, **When** delta is computed, **Then** `new_items = source_ids in run N+1 not present in run N` (by `sourceId`); `removed_items` and `changed_items` are also tagged.

### AC-4 — New-item notification
**Given** `new_items > 0`, **When** the run completes, **Then** a notification is delivered via the configured channel (in-app, Telegram) with a link to the saved search and a summary count.

### AC-5 — Failure/degraded notification
**Given** the saved search run fails or returns `degraded=true`, **When** it completes, **Then** the notification states the failure/degraded state and `degradation_reasons`, and the next scheduled run still fires unless `enabled=false`.

---

## Architecture Decisions

- **AD-33 / AD-43:** Saved searches are implemented using the Generic Alert Engine, not a standalone scheduler.
- `AlertRule` is a **first-class table** (not JSON inside `Automation.definition`).
- The alert engine reuses Epic 6's **scheduler + Celery pattern** and **notification dispatch**.
- For 12.6, `capability_id='vn_jobs.aggregate'` and `diff_strategy='new_items'`.
- Notification channels are `in_app` and `telegram`; email is deferred until legal/PO approval.

## Data Model

### `alert_rules`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | Integer | FK workspaces |
| client_id | CITEXT \| null | AD-31 multi-tenancy |
| capability_id | str | e.g. `vn_jobs.aggregate` |
| name | str | user-facing saved search name |
| query | JSONB | structured query for capability |
| schedule | str | `'none'` \| `'daily'` \| `'weekly'`; maps to cron |
| timezone | str | e.g. `'UTC'` |
| cron | str | computed from `schedule` + `timezone` |
| next_fire_at | timestamp tz | precomputed next fire |
| last_fired_at | timestamp tz | |
| diff_strategy | str | `'new_items'` for 12.6 |
| threshold | JSONB \| null | null for `new_items` |
| notification_channels | list[str] | `['in_app']` default, may include `'telegram'` |
| enabled | bool | default true |

### `alert_snapshots`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| alert_rule_id | UUID | FK alert_rules |
| snapshot_json | JSONB | `{source_ids: list[str], items: list[dict]}` |
| run_status | str | `succeeded` \| `failed` \| `degraded` |
| degradation_reasons | list[str] \| null | |
| created_at | timestamp | |

### `alert_subscriptions`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK user |
| alert_rule_id | UUID | FK alert_rules |
| channels | list[str] | subset of rule channels |
| enabled | bool | default true |

## Code Review Findings

Review date: 2026-08-13. 3 parallel adversarial reviews (structure, security/edge cases, architecture/AC). P0 findings were fixed in the same pass.

| # | Layer | Finding | Status |
|---|-------|---------|--------|
| 1 | Correctness | Update `schedule`/`timezone` in `crud.py` reused old `rule.*` instead of `data.*` | ✅ fixed |
| 2 | Concurrency | `_claim_due_rules` only set `last_fired_at`; `next_fire_at` advanced later in a separate TX (race) | ✅ fixed — now advanced atomically in claim TX; `execute_alert_rule` no longer re-advances |
| 3 | Security | `notify_alert_run` sent notifications to `AlertSubscription.user_id` without verifying `WorkspaceMembership` | ✅ fixed — JOIN `WorkspaceMembership` on `workspace_id` |
| 4 | Security | No RLS policies on `alert_rules`, `alert_snapshots`, `alert_subscriptions` | ✅ fixed — added workspace/client RLS in migration; denormalized `workspace_id` onto `alert_subscriptions` |
| 5 | Architecture | `AlertRule` missing AD-43 `target_sequence_id` / `target_step_id` columns | ✅ fixed — columns added, FKs deferred until Sequence tables land |
| 6 | Architecture/AD-33 | `capability_id` not validated against `CapabilityRegistry` at create/update | ✅ fixed — `CapabilityRegistry.get()` at CRUD and execution |
| 7 | Validation | `notification_channels` accepted arbitrary strings (`sequence_enrollment` not rejected per AD-43) | ✅ fixed — Pydantic validator whitelist `in_app`, `telegram` |
| 8 | Security | `create_subscription_route` did not verify `data.user_id` is a workspace member | ✅ fixed — added membership check |
| 9 | Migration | `ix_alert_rules_due` missing `postgresql_where=enabled` partial index (model defined it) | ✅ fixed |
| 10 | Data Integrity | Snapshot JSON not validated before diff/notify | ✅ fixed — `_validate_items` fails fast on non-dict or missing id/source_id/canonical_id |
| 11 | Tests | Missing coverage for tick, notify, subscription, e2e execute | ✅ fixed — added `test_tick.py`, `test_notify.py`, `test_create_alert_subscription`, `test_alert_rule_execute_and_diff` |

## Verification

| AC | Evidence | Status |
|----|----------|--------|
| AC-1 | `tests/integration/alerts/test_saved_search_lifecycle.py::test_create_alert_rule`; `AlertRuleCreate` schema; `derive_cron` sets `cron` and `next_fire_at` | ✅ |
| AC-2 | `app.alerts.engine.tick.alert_engine_tick` Celery task; `execute_alert_rule` calls `vn_jobs.aggregate` capability via `execute_with_context` | ✅ |
| AC-3 | `tests/unit/alerts/test_diff.py`; `diff_new_items` returns `new_items`, `removed_items`, `changed_items` by `sourceId` | ✅ |
| AC-4 | `app.alerts.engine.notify.notify_alert_run` creates in-app `Notification` and sends Telegram; includes saved search deep link | ✅ |
| AC-5 | `execute_alert_rule` catches capability failure, marks snapshot `failed`/`degraded`, records `degradation_reasons`, still advances `next_fire_at` if `enabled` | ✅ |

## Test Results

```bash
uv run pytest tests/unit/alerts tests/integration/alerts tests/unit/automations -q
# 304 passed
```

## Implementation Plan

### 1. Schema (Alembic migration)
- Create `alert_rules`, `alert_snapshots`, `alert_subscriptions` tables.
- Add indexes on `(workspace_id, enabled, next_fire_at)` for tick query.

### 2. SQLAlchemy models
- `nowing_backend/app/alerts/persistence/models/alert_rule.py`
- `nowing_backend/app/alerts/persistence/models/alert_snapshot.py`
- `nowing_backend/app/alerts/persistence/models/alert_subscription.py`

### 3. Alert engine core
- `nowing_backend/app/alerts/engine/tick.py` — Celery task `alert_engine_tick` run every minute.
- `nowing_backend/app/alerts/engine/execute.py` — gọi capability, ghi snapshot, compute diff.
- `nowing_backend/app/alerts/engine/notify.py` — gọi `NotificationService.create_notification` và Telegram.
- `nowing_backend/app/alerts/engine/diff.py` — `new_items` diff strategy.

### 4. REST routes
- `nowing_backend/app/routes/alert_rules_routes.py`:
  - `GET /workspaces/{workspace_id}/alert-rules`
  - `POST /workspaces/{workspace_id}/alert-rules`
  - `GET /workspaces/{workspace_id}/alert-rules/{id}`
  - `PUT /workspaces/{workspace_id}/alert-rules/{id}`
  - `DELETE /workspaces/{workspace_id}/alert-rules/{id}`
  - `POST /workspaces/{workspace_id}/alert-rules/{id}/run` (manual trigger)

### 5. Capability wiring
- Tickle `vn_jobs.aggregate` via `execute_with_context`.
- Build `CapabilityContext(session=session, workspace_id=workspace_id)`.
- Validate `capability_id` is registered in `CapabilityRegistry`.

### 6. Tests
- Unit: `tests/unit/alerts/test_diff.py`, `tests/unit/alerts/test_tick.py`.
- Integration: `tests/integration/alerts/test_saved_search_lifecycle.py`, `tests/integration/alerts/test_saved_search_notification.py`.

## Reuse Boundaries

- **Do reuse:**
  - `app/celery_app.py` for Celery task + beat schedule.
  - `app/automations/triggers/builtin/schedule/cron.py` for cron math.
  - `app/automations/services/telegram_notifications.py` for Telegram delivery.
  - `app/notifications/service/facade.py::NotificationService.create_notification` for in-app.
  - `app/capabilities/core/__init__.py::execute_with_context` for capability execution.
  - `app/services/jobs_aggregator.schemas.VnJobAggregateInput/Output` for query/result shape.
  - `app/capabilities/vn_jobs/aggregate/definition.py` for capability metadata.

- **Do NOT reuse:**
  - `Automation` / `AutomationRun` / `AutomationTrigger` tables for `AlertRule` data.
  - `Automation.definition` JSON for alert config.

## Test Commands

```bash
# Unit
uv run pytest tests/unit/alerts -q

# Integration (needs Postgres + Redis)
uv run pytest tests/integration/alerts -q

# Lint
ruff check app/alerts app/routes/alert_rules_routes.py tests/unit/alerts tests/integration/alerts
ruff format app/alerts app/routes/alert_rules_routes.py tests/unit/alerts tests/integration/alerts
```

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/automations/triggers/builtin/schedule/selector.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/automations/triggers/builtin/schedule/cron.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/automations/services/telegram_notifications.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/notifications/service/facade.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/__init__.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/vn_jobs/aggregate/definition.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/vn_jobs/aggregate/schemas.py" />
