---
story_key: 21-8b-redis-stream-consumer-celery-wiring
status: done
epic: 21
story: 8b
---

# Story 21.8b: Redis Stream Consumer Celery Wiring

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-4, AD-SOC-6, AD-SOC-7  
**Split from:** Story 21.8 — Social Ingress via XActions Integration (baseline)

---

## Story

As a Nowing backend engineer,  
I want `run_social_stream_consumer` to run as a Celery beat task,  
so that ingested social posts are processed into `SocialPost` and `Lead` records continuously.

---

## Acceptance Criteria

1. **Celery Task Registration** — **Given** messages in `stream:social:raw_posts`, **When** `process_social_stream` Celery task runs, **Then** it reads via consumer group `social_processors`, persists posts, creates leads for high-intent posts, evaluates `AlertRule`, and ACKs messages.
2. **Failed Message Handling** — **Given** a failed message, **When** processing throws, **Then** it moves to `stream:social:failed` DLQ and ACKs the original.
3. **Beat Schedule** — **Given** Celery beat, **When** every 30 seconds, **Then** `process_social_stream` is enqueued with `expires=25`.

---

## Tasks / Subtasks

- [x] Task 1: Celery task wrapper
  - [x] 1.1 Create `app/tasks/celery_tasks/social_stream_worker.py` wrapping `run_social_stream_consumer`.
  - [x] 1.2 Ensure consumer group `social_processors`, batch size, and block settings are correct.
- [x] Task 2: DLQ and ACK guarantees
  - [x] 2.1 Move failed messages to `stream:social:failed` before ACK.
  - [x] 2.2 ACK successful messages only after DB persistence and lead creation.
- [x] Task 3: Beat schedule
  - [x] 3.1 Add `process-social-stream` to `celery_app.py` beat schedule (`crontab(second="*/30")`, `expires=25`).
  - [x] 3.2 Add `app.tasks.celery_tasks.social_stream_worker` to `include`.
- [x] Task 4: Integration test
  - [x] 4.1 `tests/integration/platforms/test_social_redis_stream.py` end-to-end.

---

## Dev Notes

- Do not route to `CONNECTORS_QUEUE` (reserved for indexing); use the default queue or a dedicated `nowing.social` queue.
- `xadd` to `stream:social:raw_posts` must use `maxlen=20000, approximate=True` per AD-SOC-4.
- Alert rule call signature: `execute_alert_rule(session=session, alert_rule=rule, fired_at=datetime.now(UTC))`.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-xactions-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/tasks/celery_tasks/social_stream_worker.py]
- [Code: nowing_backend/app/celery_app.py]
