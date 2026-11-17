---
title: 'Epic 44.3 — Campaign meta-scheduler + rate-limit guard'
type: 'feature'
created: '2026-11-18'
status: 'done'
baseline_revision: 'ee6ac8467842bceb4635f24b1e31043b3b9f0ead'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-44-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-44-1-schema-opt-in-campaign-binding.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** `ScheduleConfig` + `launch_config` là inert metadata (zero consumers — schemas.py:24-36); `lead_campaigns.next_run_at`/`schedule_frequency`/`schedule_cron`/`max_runs` đã có cột (44.1) nhưng không ai tick. Và campaign run creation không có quota → 1 campaign có thể spam run/lead vô hạn.

**Approach:** Meta-scheduler pattern (precedent `check_periodic_schedules`/`check_social_monitored_targets` — celery_app.py:348-360): 1 beat entry quét `WHERE next_run_at <= now()` → `open_campaign_run` → `launch_campaign_run.apply_async`. Quota check TRONG `open_campaign_run` (seam duy nhất → route/launch/scheduler đều qua cùng door). `launch_config`: **DROP** — ScheduleConfig trên spec vẫn parse nhưng chỉ `schedule_*` scalar trên `lead_campaigns` là source of truth (ghi rõ trong docstring; không wire launch_config).

## Boundaries & Constraints

**Always:**
- **Quota trong `open_campaign_run`** (campaign_service.py — sửa hàm hiện có, giữ advisory lock): sau lock, TRƯỚC insert run — (a) runs/day cho campaign: `count(campaign_runs where campaign_id=:cid AND created_at >= date_trunc('day', now()))` >= **10** → raise `CampaignQuotaExceededError` (mới, kế `ConcurrentCampaignRunError` style); (b) leads/day workspace-wide: `count(campaign_leads join campaign_runs where workspace_id=:ws AND created_at >= today)` >= **500** → raise. Quota constants `CAMPAIGN_MAX_RUNS_PER_DAY = 10`, `WORKSPACE_MAX_CAMPAIGN_LEADS_PER_DAY = 500` — module-level, 1 chỗ chỉnh.
- Scheduler task `check_campaign_schedules` (trong `app/tasks/campaign_tasks.py` của 44.2 — nếu file chưa tồn tại vì chạy trước/song song thì tạo mới theo đúng file đó): `run_async_celery_task` + own `async_session_maker` + `set_request_tenant_context` per-campaign (RLS!). Body: `SELECT lead_campaigns WHERE status='scheduled' AND next_run_at IS NOT NULL AND next_run_at <= now() AND max_runs chưa đạt` → với mỗi campaign: `open_campaign_run(trigger='scheduled')` + `apply_async`; `CampaignQuotaExceededError`/`ConcurrentCampaignRunError` → **skip + `skipped_by_quota += 1`** (campaign counter, KHÔNG tạo run row hư); recompute `next_run_at` sau mỗi skip/launch theo `schedule_frequency`/`schedule_cron`.
- `next_run_at` compute: `schedule_frequency` ∈ `('hourly','daily','weekly','monthly')` → `now() + interval`; `schedule_cron` (nếu có) → croniter `next()`; helper `compute_next_run_at(campaign) -> datetime|None` trong campaign_service — return None khi `max_runs` đạt hoặc không có schedule → tick tự skip.
- Beat entry trong `celery_app.conf.beat_schedule` (celery_app.py:348+): `"check-campaign-schedules": {"task": "check_campaign_schedules", "schedule": crontab(minute="*"), "options": {"expires": 50}}` — y hệt `check-social-monitored-targets` pattern (:356-363).
- **Stale-run reaper** cùng task `check_campaign_schedules` (1 query thêm): run `'running'` với `started_at < now() - 2h` → `finalize_campaign_run(status='failed', error='stale_run_timeout')` + campaign status update. Const `CAMPAIGN_RUN_STALE_SECONDS = 7200`.
- Route-side: `CampaignQuotaExceededError` → **429** + detail tiếng Việt (mapping trong campaign_routes ở cả `/execute` và `/launch` — 44.2 chịu trách map route riêng nếu chưa có, spec này pin mapping cho `/execute`; nếu 44.2 chưa merge thì chỉ map ở /execute + TODO comment cho launch).
- PATCH campaign set `status='scheduled'` → recompute `next_run_at` (nếu 44.2 chưa merge, ghi TODO comment + unit test helper riêng).
- Timezone: `next_run_at` timestamptz, so sánh `now()` server-side — không naive datetime.

**Never:**
- KHÔNG queue run khi vượt quota (v1 REJECT/skip — party pin); KHÔNG tạo run row cho scheduled-skip (chỉ `skipped_by_quota`++); KHÔNG per-user quota / burst window (v1 chỉ daily); KHÔNG parse `launch_config` — DROP rõ ràng; KHÔNG sửa `execute_and_persist` signature; KHÔNG per-campaign timezone (server time); KHÔNG thêm bảng mới; KHÔNG đụng `webset_campaigns`/automations scheduler.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| QUOTA_RUNS_HIT | campaign đã 10 runs hôm nay | `open_campaign_run` raise `CampaignQuotaExceededError`; route → 429 | raise → 429 / skip |
| QUOTA_LEADS_HIT | workspace 500 leads hôm nay qua campaigns | raise tương tự | raise → 429 / skip |
| TICK_DUE | campaign scheduled, next_run_at quá khứ | run tạo + apply_async + next_run_at recompute tương lai | No error expected |
| TICK_SKIP_QUOTA | due nhưng quota hit | `skipped_by_quota+1`, next_run_at recompute, 0 run row | silent skip + counter |
| TICK_NOT_DUE | next_run_at tương lai | không động gì | No error expected |
| MAX_RUNS | runs count >= max_runs | `compute_next_run_at` → None, status → 'completed' | documented |
| STALE_RUN | run 'running' started_at > 2h | finalize failed + error 'stale_run_timeout' | reaper |
| MANUAL_QUOTA | `/execute` persist lần 11 trong ngày | 429 + message rõ | HTTPException 429 |
| SCHEDULED_SET | PATCH status='scheduled' | next_run_at computed từ scalars | helper + test |

</intent-contract>

## Code Map

- `app/lead_intelligence/services/campaign_service.py` -- `open_campaign_run` += quota checks (sau lock); += `CampaignQuotaExceededError`, `compute_next_run_at`, consts
- `app/tasks/campaign_tasks.py` (từ 44.2, hoặc NEW nếu chưa có) -- `check_campaign_schedules` task: tick scan + stale reaper
- `app/celery_app.py` :348-363 -- += beat entry `"check-campaign-schedules"`
- `app/routes/campaign_routes.py` -- map `CampaignQuotaExceededError` → 429 tại `/execute` (+`/launch` nếu 44.2 đã merge)
- `nowing_backend/app/lead_intelligence/campaign/schemas.py` :24-36 -- docstring note: ScheduleConfig inert, `lead_campaigns.schedule_*` là truth (1 dòng comment)
- `tests/unit/services/test_campaign_quota.py` + `tests/unit/tasks/test_campaign_scheduler.py` -- NEW
- `app/tenant_context.py` :17 -- set_request_tenant_context (task RLS)

## Tasks & Acceptance

**Execution:**
- `campaign_service.py` -- quota + `compute_next_run_at` + exception -- giữ lock ordering: lock → concurrent-check → quota → insert
- `app/tasks/campaign_tasks.py` -- `check_campaign_schedules` -- auto_refund pattern, per-campaign tenant ctx
- `app/celery_app.py` -- beat entry -- 1 block y hệt social pattern
- `campaign_routes.py` -- 429 mapping -- nhỏ
- tests -- unit quota (runs/leads đếm qua mock/count), scheduler tick (due/not-due/skip/stale), next_run_at compute

**Acceptance Criteria:**
- Given 10 runs hôm nay, khi `open_campaign_run`/`/execute`, then raise/429 và không run thứ 11
- Given campaign `scheduled` + `next_run_at` quá khứ, khi beat tick chạy, then run mới trigger='scheduled' + `next_run_at` tương lai
- Given due nhưng quota đầy, then `skipped_by_quota` +1, 0 run row
- Given `max_runs` đạt, then `next_run_at=None` và campaign 'completed'
- Given run 'running' > 2h, then finalize failed 'stale_run_timeout'

## Spec Change Log

## Review Triage Log

## Design Notes

- Quota constants conservative (10/500) — party/architect pin; tune sau qua config nếu cần.
- `skipped_by_quota` counter thay vì run row — observability không phình bảng (party pin).
- Scheduler không lock campaign row khi tick — `open_campaign_run` advisory lock tự serialize 2 tick overlap.

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/services/test_campaign_quota.py tests/unit/tasks/test_campaign_scheduler.py -x -q` -- expected: pass
- `pytest tests/unit/lead_intelligence/ tests/unit/services/ -x -q` -- expected: không regression
- `python -c "from app.celery_app import celery_app; assert 'check-campaign-schedules' in celery_app.conf.beat_schedule"` -- expected: OK
