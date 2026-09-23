---
story_key: 30-2-redis-event-bus-subscribe-failure-state-leak
status: done
epic: 30
---

# Story 30.2: Redis Event Bus Subscribe Failure State Leak

**Status:** `done`  
**Epic:** Epic 30 — Technical Debt

## Story

As a system operator,  
I want Redis event bus subscribe failures to clean up state and retry with backoff,  
so that cross-replica delivery does not fail silently when a subscriber times out.

## Acceptance Criteria

- **Given** a Redis subscribe timeout, **When** the failure handler runs, **Then** it removes the channel from the `subscribers` dict and schedules retry with exponential backoff.
- **Given** a recovered Redis connection, **When** retry fires, **Then** the channel is re-subscribed and events resume delivery.
- **Given** repeated subscribe failures, **When** max retries are exhausted, **Then** the incident is logged to `events_redis` metrics/alerting and the worker continues without a stuck subscription.

## Dev Notes

- Module: `app/capabilities/core/events_redis.py`
- Retry: exponential backoff, capped at ~30s
- Observability: counter `redis_event_bus_subscribe_failures_total`

## Verification

- Module: `app/capabilities/core/events_redis.py`
- Tests: timeout cleanup, retry re-subscription, max-retry logging
