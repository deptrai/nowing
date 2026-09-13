---
story_key: 23-1-asynchronous-scraper-worker-pool
status: done
epic: 23
---

# Story 23.1: Asynchronous Scraper Worker Pool

**Status:** `done`  
**Epic:** Epic 23 — Lead Capture & Outreach Infrastructure

## Story

As a sales operator,  
I want lead scraping across 15+ Vietnamese platforms to run asynchronously in parallel Celery workers without blocking chat SSE responses,  
so that prospects appear in the live matrix as they are discovered.

## Acceptance Criteria

- **Given** a lead generation prompt requiring multi-source scraping, **When** `LeadGenOrchestrator` dispatches scraping tasks, **Then** Celery returns a `job_id` within 100ms and executes workers concurrently across independent worker pools.
- **Given** active scraping workers discovering leads in real time, **When** any individual worker extracts 5+ leads OR when 3 seconds elapse with buffered leads, **Then** it pushes records directly to Redis Stream `workspace:{id}:leads_stream`, triggering live table updates without waiting for full job completion.
- **Given** a scraper encountering Cloudflare anti-bot challenge or HTTP 429, **When** consecutive failures reach 3, **Then** the circuit breaker trips for that adapter for 10 minutes while remaining adapters continue.
- **Given** a worker process crash (`SIGKILL`/OOM), **When** Celery retries the task (`acks_late=True`), **Then** `ON CONFLICT (workspace_id, value_hmac) DO UPDATE` ensures zero duplicate rows.

## Dev Notes

- Celery queue: `nowing.lead_scrapers`
- Redis Stream: `workspace:{id}:leads_stream`
- Worker file: `app/tasks/lead_scrapers.py`
- Follows INV-23.1 – INV-23.11

## Verification

- Worker: `app/tasks/lead_scrapers.py`
- Orchestrator: `app/lead_intelligence/orchestrator.py`
- Tests: worker pool concurrency, circuit breaker, duplicate suppression
