# Story 35.3 Spec: Per-Platform Scraper Failure Metrics & SSE Streaming Idle Heartbeat Guards

## Intent

As a System Reliability Engineer, I want per-scraper ingest failure counters and SSE stream idle heartbeat guards, so that scraper failures are surfaced immediately on Prometheus and idle client connections do not hang.

## Acceptance Criteria

- **Given** an ingest failure from any platform scraper, **When** error occurs, **Then** `record_scraper_ingest_failure(platform, reason)` increments.
- **And** long-running SSE connections emit keep-alive comments every 15 seconds.

## Technical Design

### 1. Prometheus Metric Instrument

In `app/observability/metrics/platform.py`:
```python
@lru_cache(maxsize=1)
def _scraper_ingest_failures():
    return _get_meter().create_counter(
        "nowing.scraper.ingest.failures",
        description="Count of scraper ingest failures per platform.",
    )

def record_scraper_ingest_failure(platform: str, reason: str) -> None:
    _add(_scraper_ingest_failures(), 1, {"platform": platform, "reason": reason})
```

### 2. SSE Keep-Alive Heartbeat (15s)

In `app/routes/dsh_routes.py` (`/dsh/cdp/stream`):
- When no command is received within a 15-second window, yield an SSE keep-alive comment `": ping\n\n"` (or `{"comment": "keep-alive"}`).
- This keeps TCP connections alive through corporate proxies, firewalls, and ingress routers.
