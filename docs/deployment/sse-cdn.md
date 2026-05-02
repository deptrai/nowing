# SSE & CDN Compatibility (Cloudflare)

> **Story 11.6 / FR41.1** — production go-live blocker. Verify before production cutover.

## TL;DR

- Cloudflare may **buffer** or **recompress** SSE responses despite `Cache-Control: no-cache, no-transform`, depending on zone-level config (Auto Minify, Rocket Loader, etc.). Symptom: heartbeat events arrive in 30–60 s bursts instead of every 15 s, breaking the orchestra status strip. The smoke test below is the authoritative check — do not rely on tier-based heuristics.
- **Required config**: a Cloudflare Page Rule that disables Auto Minify, Rocket Loader, and caching on the SSE endpoint.
- **Verification**: run `nowing_backend/scripts/sse_cdn_smoke_test.py` against the production-mirror environment before launch.

## Affected endpoint

`/api/v1/threads/{thread_id}/runs/{run_id}/stream`

This endpoint serves `text/event-stream` with `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`. The backend (story 11.1) injects `: heartbeat\n\n` SSE comments every 15 s when no data event is in flight.

## Why no-transform isn't enough

`Cache-Control: no-transform` is a hint that some Cloudflare features (Auto Minify, Rocket Loader, image polish) are documented to honour, but it does not guarantee non-buffering at the edge. Zone-level transformations applied before/after the response often ignore the header for content types they don't recognise as "transformable plain text". For SSE this manifests as:

- Comments and events queue at the edge until an internal threshold flushes (size or time-based, varies by config).
- TLS keep-alive timing skews — clients see "stalled" connections then a burst.
- Auto-reconnect logic (story 11.1 FE) trips because the heartbeat appears to vanish for >15 s.

The empirical fix is to bypass edge transformation entirely for the SSE route — see the options below.

## Required Cloudflare configuration

### Option A — Page Rule (recommended for simplicity)

Create a rule with **higher priority** than any caching rule:

| Setting | Value |
|---|---|
| URL match | `*your-domain.com/api/v1/threads/*/runs/*/stream` |
| Cache Level | **Bypass** |
| Auto Minify | **OFF** (HTML / JS / CSS) |
| Rocket Loader | **OFF** |
| Browser Integrity Check | **OFF** (optional — only if it's interfering) |

### Option B — Cloudflare Worker (preferred for fine-grained control)

A Worker can guarantee streaming pass-through. Use the modern Module Worker API (`export default { fetch }`), explicitly pipe the origin response body without transformation, and set `Cache-Control: no-store` on the egress response to prevent any downstream cache:

```js
// sse-bypass-worker.js (Cloudflare Module Worker syntax)
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const isSSE = /^\/api\/v1\/threads\/[^\/]+\/runs\/[^\/]+\/stream$/.test(url.pathname);

    // Forward all non-SSE requests untouched.
    if (!isSSE) return fetch(request);

    // SSE: bypass cache and stream the body verbatim.
    const upstream = await fetch(request, { cf: { cacheTtl: 0, cacheEverything: false } });

    // Re-construct the response so we own the headers — overrides any
    // edge-applied transforms / caching directives.
    const headers = new Headers(upstream.headers);
    headers.set("Cache-Control", "no-cache, no-store, no-transform");
    headers.set("X-Accel-Buffering", "no");
    headers.delete("Content-Encoding"); // ensure no recompression on egress

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  },
};
```

> **Why not the legacy `addEventListener('fetch', ...)` form**: it does not let you reconstruct response headers as cleanly, and it's deprecated for new Workers. The Module form above is the supported pattern.

> **Note on `cf: { cacheTtl: 0, cacheEverything: false }`**: these are cache directives, not buffering directives. They prevent the edge from caching the response, but Cloudflare still buffers internally during transformation — the explicit header rewrite + `no-store` is what actually keeps the stream flowing.

### Option C — Disable orange-cloud for the API subdomain

If your API runs on a separate subdomain (e.g. `api.your-domain.com`), the cleanest approach is to set its DNS record to **DNS only** (grey cloud) so Cloudflare doesn't proxy it at all. Trade-off: no DDoS protection at edge — only viable if origin has its own DDoS mitigation.

## Smoke test

```bash
# Run from your CI or production-mirror env
python3 nowing_backend/scripts/sse_cdn_smoke_test.py \
    --base-url https://your-domain.com \
    --bearer-token "$TOKEN" \
    --thread-id 1 \
    --run-id <run-uuid>
```

Pass criteria:
- First heartbeat arrives within **16 s** of connection open.
- Subsequent heartbeats arrive at **15 s ± 2 s** intervals.
- Total connection survives ≥ 60 s without disconnect.

If the test fails, recheck the page rule / worker config and run again.

## Operational notes

- After Cloudflare config changes, allow ~5 minutes for global propagation before testing.
- Production deployments should add the smoke test as a post-deploy gate (CI step or runbook checklist item).
- Other CDNs (Fastly, AWS CloudFront, Akamai) have their own quirks — this doc is Cloudflare-specific. For another CDN, file an ADR amendment.

## References

- Story 11.6 ([`stories/11-6-production-go-live-hardening.md`](../../_bmad-output/planning-artifacts/stories/11-6-production-go-live-hardening.md))
- FR41.1 in PRD
- Backend SSE service: `nowing_backend/app/services/new_streaming_service.py`
- Heartbeat injection: `nowing_backend/app/tasks/chat/stream_new_chat.py:_with_heartbeat`
