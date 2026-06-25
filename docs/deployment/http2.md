# HTTP/2 Multiplexing (Traefik)

> **Story 11.6 / FR41.2** — production go-live blocker. Verify before production cutover.

## TL;DR

- Browsers limit concurrent **HTTP/1.1** connections per host to **6**. With 3+ tabs open, each consuming a long-lived SSE stream, additional tabs block waiting for connection slots.
- **HTTP/2** multiplexes unlimited concurrent streams over a single TCP connection — eliminates the bottleneck.
- **Required**: Traefik must terminate TLS with HTTP/2 enabled. This is the default for HTTPS entrypoints in Traefik v2.x+, but verify before launch.

## Why this matters for Nowing

Each open chat tab holds an SSE stream to `/api/v1/threads/*/runs/*/stream`. A user with the dashboard open in 3 browser tabs (e.g. comparing crypto reports across tokens) opens 3 long-lived streams. Add a few short-lived API calls and the browser hits the per-host HTTP/1.1 limit; the 4th tab's stream **waits** indefinitely.

HTTP/2 solves this by multiplexing all requests for a host over **one** TCP+TLS connection.

## Required Traefik config

### v2.x / v3.x static config (`traefik.yml` or CLI flags)

HTTP/2 is enabled **by default** on HTTPS entrypoints. The minimum config is:

```yaml
entryPoints:
  websecure:
    address: ":443"
    http:
      tls: {}  # HTTPS triggers ALPN h2 by default
    # Optional: HTTP/2 tuning lives nested under each entrypoint.
    # NOT a top-level `http2:` block — that key path does not exist in
    # Traefik and would be silently ignored on startup.
    http2:
      maxConcurrentStreams: 250  # Traefik default is 250; raise only if needed
```

Reference: https://doc.traefik.io/traefik/routing/entrypoints/#http2

### Verify with curl

```bash
curl -I --http2 -k https://your-domain.com/health
# Look for: HTTP/2 200
```

If you see `HTTP/1.1 200`, HTTP/2 is not active. Check:
- TLS is terminated by Traefik (not a sidecar that downgrades to HTTP/1.1)
- ALPN is enabled in your TLS config (it is by default)
- No reverse proxy in front of Traefik strips ALPN (e.g. AWS NLB in TCP mode passes through; AWS ALB terminates and may not negotiate h2 to backend)

### Plain HTTP entrypoint (for local dev only)

HTTP/2 over plain HTTP (h2c) is supported but **not enabled by default**. For local dev, either:
- Skip h2 — mainstream browsers (Chrome, Firefox, Safari) require h2 over TLS and won't multiplex over h2c regardless. Note: some HTTP clients (curl with `--http2-prior-knowledge`, Go, Python httpx) DO support h2c, so load tests can still see h2 against a local h2c entrypoint.
- Use a self-signed cert + add to system trust store

```yaml
# Only if you really need h2c locally (rare)
entryPoints:
  web:
    address: ":80"
    http2:
      maxConcurrentStreams: 250
```

## Multi-tab verification (manual)

1. Deploy the Traefik config to staging.
2. Open the Nowing dashboard in **3 browser tabs**, all with crypto reports streaming.
3. Open DevTools → Network tab on each.
4. Check the **Protocol** column — should show **`h2`** for the SSE connections.
5. Reload the 4th tab — it should connect immediately (not stall waiting for a connection slot).

## Common gotchas

| Symptom | Likely cause |
|---|---|
| 4th tab hangs while others stream | HTTP/1.1 (check Protocol column = `http/1.1`) |
| All tabs stall after 6 streams | Same as above |
| Some tabs show `h2`, others `http/1.1` | Mixed origin / Cloudflare downgrade — see [`sse-cdn.md`](./sse-cdn.md) |
| Streams disconnect after ~30 s | Reverse-proxy idle timeout — separate issue from HTTP/2; tune `transport.respondingTimeouts.idleTimeout` |

## CDN interaction

If Cloudflare is in front of Traefik:
- Cloudflare → browser: HTTP/2 (and HTTP/3 if enabled — even better).
- Cloudflare → origin: HTTP/1.1 by default. Edge multiplexing means the browser sees h2 even if origin is h1.

This is acceptable as long as Cloudflare → browser is h2 and the SSE bypass rule is configured (see [`sse-cdn.md`](./sse-cdn.md)).

## References

- Story 11.6 ([`stories/11-6-production-go-live-hardening.md`](../../_bmad-output/planning-artifacts/stories/11-6-production-go-live-hardening.md))
- FR41.2 in PRD
- Traefik HTTP/2 docs: https://doc.traefik.io/traefik/routing/entrypoints/#http2
- Browser per-host connection limits: https://stackoverflow.com/questions/985431/max-parallel-http-connections-in-a-browser
