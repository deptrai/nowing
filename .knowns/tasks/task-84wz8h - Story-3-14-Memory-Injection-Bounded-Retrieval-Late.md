---
id: 84wz8h
title: 'Story 3.14: Memory Injection - Bounded Retrieval & Latency Budget'
status: review
priority: high
labels:
  - epic-3
  - 3-14-memory-injection-bounded-retrieval
createdAt: '2026-07-28T10:30:26.832Z'
updatedAt: '2026-07-28T16:30:27.699Z'
timeSpent: 0
parent: gz7a08
spec: stories/story-3-14-memory-injection-bounded-retrieval-latency-budget
order: 0
---
# Story 3.14: Memory Injection - Bounded Retrieval & Latency Budget

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
NFR-1b/1c/1d + AD-18 (mới). Story file: implementation-artifacts/3-14-memory-injection-bounded-retrieval.md. Chặn trên retrieval + 8.000-char read budget + latency/fail-soft counter + real RRF/cosine signals; nên chạy trước khi chốt SM-10 của 3-9. Bắt đầu dev 2026-07-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-07-28: Restarted benchmark after fixing _build_sentinel_manifest guard; seeded eval workspace 47; backend running on 0.0.0.0:8000; /health build_id verified.
2026-07-28: Benchmark AC-3 seeding in progress; memories count 50,206 / 200,406.
2026-07-28: Fixed _scope_sql_for_injection to bind UUID not string; re-running full benchmark after cleanup restored g0=6.
2026-07-28: AC-3 benchmark passed after migration 183 + script fixes; nowing-evals run completed; gate fails closed on baseline unratified (expected). D1 (AC-5 freshness skip) remains due to no LLM credentials/worker.
<!-- SECTION:NOTES:END -->

