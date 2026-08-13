---
title: Story 12.9 — Job Market Alerts
epic: 12
story: 9
status: review
priority: P1
baseline_commit: d9a21a5f5cc49c5138c949b1c76acfb1d744fdf5
---

# Story 12.9 — Job Market Alerts

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** job market researcher  
**I want:** to receive alerts when new job postings match my saved search criteria  
**So that:** I don't have to manually re-run searches every day.

---

## Acceptance Criteria

### AC-1 — Saved-search alert rule
**Given** a workspace user has a saved job search (`AlertRule` with `capability_id="vn_jobs.aggregate"`), **when** the rule is enabled and scheduled, **then** the Generic Alert Engine runs it and produces `alert_snapshots`.

### AC-2 — New posting notification
**Given** a job alert run, **when** the `new_items` diff strategy detects new postings, **then** subscribed users receive an in-app notification.

### AC-3 — Click to results
**Given** an in-app alert notification, **when** the user clicks it, **then** they are taken to the saved search results showing the new matching postings.

### AC-4 — Grouped alert view ✅
**Given** multiple job alerts, **when** viewed in the notifications/alerts panel, **then** they are grouped by search query with a match count.

### AC-5 — Degraded source / missing rule handling
**Given** a saved job search is deleted or the source scraper returns `degraded=true` with no new postings, **when** the alert job runs, **then** it skips the alert, logs `search_missing`/`degraded_source`, and the scheduler continues.

### AC-6 — Tests
**Given** the job alert flow, **when** it runs, **then** unit and integration tests cover matching, notification delivery, and degraded-source handling.

## ATDD Test List

### Unit (`tests/unit/alerts/test_job_alert.py`)

| Test | AC | Status |
|------|----|--------|
| `test_job_alert_rule_uses_vn_jobs_aggregate_capability` | AC-1 | Green |
| `test_job_alert_rule_query_schema_accepts_keyword_location_salary` | AC-1 | Green |
| `test_job_alert_diff_new_items_triggers_notification` | AC-2 | Green |
| `test_job_alert_no_notification_when_no_new_items` | AC-2 | Green |
| `test_job_alert_notification_has_deep_link_to_saved_search` | AC-3 | Green |
| `test_job_alert_notification_message_mentions_match_count` | AC-3 | Green |
| `test_job_alert_skips_when_degraded_and_zero_new_items` | AC-5 | Green |
| `test_job_alert_logs_degraded_source` | AC-5 | Green |
| `test_job_alert_logs_missing_rule` | AC-5 | Green |
| `test_job_alert_notifications_grouped_by_alert_rule` | AC-4 | Green |
| `test_job_alert_group_includes_rule_name_and_match_count` | AC-4 | Green |

### Integration (`tests/integration/alerts/test_job_alert_notification.py`)

| Test | AC | Status | Pattern |
|------|----|--------|---------|
| `test_job_alert_lifecycle_creates_in_app_notification` | AC-2 | Green | 6 (Postgres) |
| `test_job_alert_click_navigates_to_saved_search_results` | AC-3 | Green | 6 (Postgres) |
| `test_job_alert_degraded_source_skips_notification` | AC-5 | Green | 6 (Postgres) |
| `test_job_alert_scheduler_continues_after_degraded_run` | AC-5 | Green | 6 (Postgres) |

---

## Tasks / Subtasks

- [x] Add job-alert default template/UX wiring (AC-1)
  - [x] Register `vn_jobs.aggregate` as the canonical capability for job market alerts
  - [x] Seed default `AlertRule` query schema for title, location, salary range
- [x] Wire in-app notification deep-link (AC-2, AC-3)
  - [x] Add notification metadata `alert_rule_id`, `snapshot_id`, `new_items_count`
  - [x] Frontend route `/dashboard/{workspace_id}/research/saved-searches/{alert_rule_id}?snapshot={snapshot_id}`
- [x] Build grouped alert view (AC-4)
  - [x] Backend: group notifications by `alert_rule_id` with counts
  - [x] Web: alerts panel renders grouped by saved-search name
- [x] Degraded / missing handling (AC-5)
  - [x] Skip alert when `AlertRule` deleted (cascade already deletes subscriptions)
  - [x] Detect `degraded=true` + zero new items in `execute.py`; log `degraded_source`
  - [x] Detect missing saved search in `alert_engine_tick`; log `search_missing`
- [x] Tests (AC-6)
  - [x] Unit test `tests/unit/alerts/test_job_alert.py`
  - [x] Integration test `tests/integration/alerts/test_job_alert_notification.py`

---

## Current State

- Story 12.6 (Saved Searches) shipped the `AlertRule`, `AlertSnapshot`, `AlertSubscription` tables and REST routes.
- Story 6.8 (Generic Alert Engine) shipped `new_items`, `price_change`, `threshold_cross`, `trend_detect` diff strategies, capability validation, cron/tick, and notification dispatch.
- `vn_jobs.aggregate` capability exists in `app/capabilities/vn_jobs/aggregate/`.
- Alert routes are at `/workspaces/{workspace_id}/alert-rules`.
- In-app notifications already created via `NotificationService.create_notification` in `app/alerts/engine/notify.py`.

## Verification

### AC Coverage

| AC | Evidence | Status |
|----|----------|--------|
| AC-1 | `AlertRule` + `vn_jobs.aggregate` capability + `default_job_alert_query` helper in `crud.py` + `JOB_ALERT_CAPABILITY_ID` | ✅ |
| AC-2 | `execute.py` `_should_skip_notification`; `notify.py` creates `alert_run_complete` notification with `rule_name` | ✅ |
| AC-3 | Notification message carries deep-link `/dashboard/{ws}/research/saved-searches/{rule_id}?snapshot={snap.id}`; web route + detail page renders snapshot; click handler in `NotificationsDropdown.tsx` | ✅ |
| AC-4 | `group_alert_notifications` in `app/alerts/services/grouping.py`; `NotificationsDropdown.tsx` groups `alert_run_complete` items by `alert_rule_id` with match count | ✅ |
| AC-5 | `execute.py` skips notify when `degraded` + zero items, logs `degraded_source`; `tick.py` `_execute_claimed_rule` re-checks rule, logs `search_missing`; scheduler advances `next_fire_at` | ✅ |
| AC-6 | 11 unit tests + 4 integration tests all green | ✅ |

## Implementation Notes

- This is a vertical consumer of the Generic Alert Engine (AD-33). Do NOT build a new scheduler or notification path.
- A "job market alert" is an `AlertRule` with `capability_id="vn_jobs.aggregate"`, `diff_strategy="new_items"`, and `notification_channels=["in_app"]`.
- The saved-search alert can be created by reusing the existing `POST /workspaces/{workspace_id}/alert-rules` route with a `query` like `{"keyword": "Senior Python", "location": "Ho Chi Minh", "salary_min": 2000}`.
- `vn_jobs.aggregate` returns `VnJobAggregateOutput(items=[...], degraded=True/False, degradation_reasons=[...])`. `execute.py` already sets `run_status = "degraded"` and stores `degradation_reasons`. When `degraded=true` and no new items, the alert should not notify.
- The `degraded_source` log should be a structured `logger.info` with `alert_rule_id`, `workspace_id`, `degradation_reasons`.
- The `search_missing` log should fire in `alert_engine_tick` if a claimed rule no longer exists (race with delete).
- Notification deep-link: use existing saved-search web route and append `?snapshot={snapshot_id}` to show the exact run results.

## Technical Requirements

- Reuse `app/alerts/engine/execute.py` and `notify.py`.
- Reuse `app/alerts/services/crud.py`.
- Reuse `app/routes/alert_rules_routes.py`.
- Web changes go in `nowing_web/`. Use existing notification and saved-search pages.
- No new backend tables unless absolutely necessary.

## File Touch Plan

| Action | File |
|--------|------|
| Update | `nowing_backend/app/alerts/engine/tick.py` (missing-rule logging) |
| Update | `nowing_backend/app/alerts/engine/execute.py` (degraded + no new items skip) |
| Update | `nowing_backend/app/alerts/engine/notify.py` (deep-link in message) |
| Update | `nowing_backend/app/alerts/services/crud.py` (optional default query helper) |
| Add | `nowing_backend/tests/unit/alerts/test_job_alert.py` |
| Add | `nowing_backend/tests/integration/alerts/test_job_alert_notification.py` |
| Update | `nowing_web/...` (alerts panel grouping + deep-link) — TBD after backend |

## Test Commands

```bash
# Backend unit + integration
cd nowing_backend
uv run pytest tests/unit/alerts tests/integration/alerts -q

# Lint
ruff check app/alerts tests/unit/alerts tests/integration/alerts
```

## Architecture Compliance

- **AD-33**: Job market alert is an `AlertRule` template, not a new service.
- **AD-43**: `sequence_enrollment` is an action, not a notification channel — not used here.
- **AD-25**: PII redaction already runs in `vn_jobs.aggregate` before storing.
- **AD-34/AD-35**: `vn_jobs.aggregate` feeds `chainlens-research`; Nowing does not keep a job search index.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Patch-target gotcha: `execute.py` does `from .notify import notify_alert_run` — tests must patch `app.alerts.engine.execute.notify_alert_run`, not `app.alerts.engine.notify.notify_alert_run`.
- SQLAlchemy gotcha: `Notification.metadata` resolves to the declarative base `MetaData`; the JSONB column is `notification_metadata`.

### Completion Notes List

- Story 12.9 implemented as a vertical consumer of the Generic Alert Engine (AD-33). No new scheduler or notification path.
- `execute.py`: `_should_skip_notification` returns True when run failed? No — notifies on `failed`; skips only when `new_items_count == 0 and changed_items_count == 0`. Structured `degraded_source` log fires only when the skip is due to a degraded run.
- `notify.py`: message embeds deep-link `?snapshot={snapshot.id}`; metadata gains `rule_name`; per-subscriber/per-channel try/except so one bad subscriber never aborts others (Q4 guard).
- `tick.py`: `_execute_claimed_rule` re-reads the rule via `session.get(AlertRule, rule.id)`; if gone (race with delete) logs `search_missing` and returns; scheduler continues (`next_fire_at` advanced by `_claim_due_rules`).
- `grouping.py` (new): `group_alert_notifications` groups by `metadata.alert_rule_id`, sums `new_items_count`, keeps first-seen order, falls back to "Saved search" name.
- `crud.py`: `JOB_ALERT_CAPABILITY_ID = "vn_jobs.aggregate"` + `default_job_alert_query(keyword, location, salary_min, salary_max)`.
- `app/notifications/types.py`: `"alert_run_complete"` added to the `NotificationType` Literal so the inbox API filter accepts it.
- Frontend: `inbox.types.ts` gains `alert_run_complete` + `AlertRunCompleteMetadata` (guard + parser); `NotificationsDropdown.tsx` click handler routes to the saved-search detail page; new page `app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/` with snapshot summary + run history + `?snapshot=` highlight; `alert-rules.types.ts` + `alert-rules-api.service.ts` added.
- Pre-existing failures NOT caused by this story: `tests/unit/capabilities/test_run_truncation.py` (5 failed — `_FakeSession.execute()` arity; untouched by this story, fails on baseline code too).

### File List

- Added: `nowing_backend/app/alerts/services/grouping.py`
- Added: `nowing_backend/tests/unit/alerts/test_job_alert.py`
- Added: `nowing_backend/tests/integration/alerts/test_job_alert_notification.py`
- Added: `nowing_web/contracts/types/alert-rules.types.ts`
- Added: `nowing_web/lib/apis/alert-rules-api.service.ts`
- Added: `nowing_web/app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/page.tsx`
- Added: `nowing_web/app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/saved-search-detail-content.tsx`
- Updated: `nowing_backend/app/alerts/engine/execute.py`
- Updated: `nowing_backend/app/alerts/engine/notify.py`
- Updated: `nowing_backend/app/alerts/engine/tick.py`
- Updated: `nowing_backend/app/alerts/services/crud.py`
- Updated: `nowing_backend/app/notifications/types.py`
- Updated: `nowing_backend/tests/unit/alerts/test_notify.py`
- Updated: `nowing_web/contracts/types/inbox.types.ts`
- Updated: `nowing_web/components/layout/ui/sidebar/NotificationsDropdown.tsx`

### Change Log

- 2026-08-13: Created story file for 12.9 Job Market Alerts.
- 2026-08-13: Grill-me challenge phase completed (Challenge Log appended).
- 2026-08-13: ATDD red-phase: added `tests/unit/alerts/test_job_alert.py` (11 tests: 5 red, 4 green descriptive-only, 2 pending grouping) and `tests/integration/alerts/test_job_alert_notification.py` (4 red tests).
- 2026-08-13: testarch-atdd red-phase: unit test bodies with mock DB; 5 unit tests + 4 integration tests fail as expected; ruff clean.
- 2026-08-13: Implemented backend: `_should_skip_notification` (AC-2/AC-5) + `degraded_source` log in `execute.py`; deep-link + `rule_name` + per-subscriber guard in `notify.py`; `_execute_claimed_rule` + `search_missing` in `tick.py`; `group_alert_notifications` in new `grouping.py`; `default_job_alert_query` + `JOB_ALERT_CAPABILITY_ID` in `crud.py`; `alert_run_complete` added to `NotificationType`.
- 2026-08-13: Unit tests green — replaced 3 `pytest.fail` stubs, added 2 missing AC-2 tests, fixed patch target to `app.alerts.engine.execute.notify_alert_run`, fixed `test_notify.py` fake snapshot `id`; 37 unit tests pass.
- 2026-08-13: Integration tests green — implemented 4 tests in `test_job_alert_notification.py` (lifecycle notification, deep-link + snapshot queryable, degraded skip, scheduler continuation after degraded run).
- 2026-08-13: Frontend — `inbox.types.ts` `alert_run_complete` type + metadata schema/guard/parser; `NotificationsDropdown.tsx` click → saved-search detail; new `research/saved-searches/[alert_rule_id]` page + content; `alert-rules.types.ts` + `alert-rules-api.service.ts`. `pnpm tsc --noEmit` and biome clean.
- 2026-08-13: Full verification — `ruff check app/alerts app/notifications/types.py tests/unit/alerts tests/integration/alerts` clean; `pytest tests/unit/alerts tests/integration/alerts` 47 passed; full `tests/unit` run 2061 passed with 5 pre-existing failures in `test_run_truncation.py` (unrelated, fail on baseline). Status → `review`.

## Challenge Log (grill-me)

### Q1 — Already implemented?

- `app/alerts/` engine, models, CRUD, routes, and tests shipped in 12.6/6.8.
- `vn_jobs.aggregate` capability exists.
- `NotificationService.create_notification` exists.
- **Not found:** job-alert-specific template, `alert_run_complete` notification handling in `NotificationsDropdown.tsx` (only `new_mention`, `comment_reply`, `insufficient_credits`), notification grouping by `alert_rule_id`, deep-link to saved-search results, or `test_job_alert_matching.py`.
- **Verdict:** No duplicate logic. Proceed.

### Q2 — Simpler alternative?

- Reuse `AlertRule` + `vn_jobs.aggregate` instead of a new scheduler.
- Extend `NotificationsDropdown.tsx` with `alert_run_complete` type handling rather than a new notifications page.
- Deep-link to existing saved-search page (`/dashboard/{workspace_id}/research/saved-searches/{alert_rule_id}`) with `?snapshot={snapshot_id}` instead of building a new results view.
- **Verdict:** Reuse path is clear. Proceed with documented file touch plan.

### Q3 — Edge cases spec misses (Pattern 3)

- **Boundary:** `vn_jobs.aggregate` returns `items` but no `degraded` flag — current `execute.py` only checks `degradation_reasons` / `degraded` key; need explicit handling when `degraded=true` but `new_items_count > 0` (notify with degraded warning? or still notify? AC-5 says skip only when no new postings + degraded).
- **Null/empty:** `query` may be `{}` or missing `keyword` — `vn_jobs.aggregate` input schema may reject; need validation at alert creation.
- **Concurrent:** Rule deleted after `_claim_due_rules` but before `execute_alert_rule` — current `execute_alert_rule` receives the object in memory, no re-check; `_tick` catch/rollback will log exception but not `search_missing`.
- **Workspace membership change:** Subscription query already joins `WorkspaceMembership`, but a user's membership may be removed after notification is created — no impact on delivered notifications.
- **Snapshot deleted after notification clicked:** Web route must handle 404/redirect.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- **`vn_jobs.aggregate` executor throws:** `execute.py` catches, writes `run_status="failed"` snapshot, and still calls `notify_alert_run` with a failed snapshot. Current `notify.py` will send a "Saved search failed" message to all subscribed users. OK but should be covered in tests.
- **`NotificationService.create_notification` throws inside `notify_alert_run`:** Not caught; one failing subscriber could abort the entire notification loop. `notify.py` should catch per-subscriber errors.
- **`TelegramAdapter.send_message` throws:** Caught and logged; `record_gateway_outbound` marks failed. OK.
- **Celery/Redis unavailable:** `alert_engine_tick` does not run. Monitoring/alerting is outside scope.
- **Database connection lost during `_tick`:** `run_async_celery_task` likely retries via Celery; need test.
- **Frontend `?snapshot={snapshot_id}` points to non-existent snapshot:** Saved-search page should fall back to latest snapshot or show empty state.

### Triage

- **Q4 `NotificationService.create_notification` throw is a real failure mode** — non-critical for P1 but should add a guard in `notify.py` so one bad subscriber does not abort others.
- **Q3 concurrent rule-delete race** — non-critical; current rollback + exception log is acceptable, but add `search_missing` log as specified in AC-5.
- No critical findings. **Proceed to test-first ATDD / dev-story.**

## Review Findings

### decision-needed

- [x] [Review][Decision] AC-4 frontend grouping incomplete — implemented `NotificationsDropdown.tsx` grouping by `alert_rule_id` with match count; `use-inbox.ts` includes `alert_run_complete` in `status` category.

### patch

- [x] [Review][Patch] `group_alert_notifications` can crash on malformed `new_items_count` [`nowing_backend/app/alerts/services/grouping.py:63`] — wrapped `int()` in `try/except (TypeError, ValueError)`. Added corresponding frontend `groupInboxNotifications` helper that parses numeric strings and falls back to 0.

### defer

- [x] [Review][Defer] `NotificationsDropdown` silently ignores navigation if `workspace_id` or `alert_rule_id` is missing — defensive UX gap, schema enforces both as required.
- [x] [Review][Defer] `SavedSearchDetailContent` only validates `alertRuleId` by length — invalid IDs fall through to API 404, acceptable fallback.
- [x] [Review][Defer] `SavedSearchDetailContent` falls back to "No runs yet" when linked snapshot is missing — graceful degradation, UX polish only.
- [x] [Review][Defer] `default_job_alert_query` does not validate `salary_min <= salary_max` — helper not wired to a route yet; validate when consumed.

## Status

done
