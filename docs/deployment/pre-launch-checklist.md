# Pre-Launch Production Checklist

> **Story 11.6 / Task T5** — production-mirror gate before user-facing cutover.
> Story 11.6 ships **code-complete**; this checklist is the deployment-side gate
> that satisfies AC#1, AC#2, AC#5 against a real production-mirror environment.

This checklist must be **fully green** before flipping DNS / removing the
"closed beta" gate / sending launch comms. It is the contract between the
engineering team and operations.

Owner: Architect + DevOps
Sign-off required: both, in writing (PR comment, ticket comment, or commit message).

---

## Section A — SSE & CDN (story 11.6 T1 / FR41.1)

- [ ] **A1.** Cloudflare config applied per [`sse-cdn.md`](./sse-cdn.md):
  - Either Page Rule (Cache Level: Bypass + Auto Minify off + Rocket Loader off) OR Worker bypass OR DNS-only on the API subdomain
  - Config screenshot or URL attached to the launch ticket
- [ ] **A2.0.** Provision smoke-test data (pre-requisite for A2):
  - Authenticate as a test user against the production-mirror; capture `$STAGING_TOKEN`.
  - Create a fresh thread + start a long-running crypto research run via the dashboard OR the API:
    ```bash
    curl -X POST "https://<prod-mirror-host>/api/v1/threads" \
        -H "Authorization: Bearer $STAGING_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"search_space_id": <ss-id>, "title": "smoke-test"}'
    # → {"id": <thread-id>, ...}
    curl -X POST "https://<prod-mirror-host>/api/v1/threads/<thread-id>/runs" \
        -H "Authorization: Bearer $STAGING_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"search_space_id": <ss-id>, "user_query": "Analyze BTC price action"}'
    # → {"id": "<run-uuid>", ...}
    ```
  - Record `<thread-id>` and `<run-uuid>` for use in A2.
- [ ] **A2.** Smoke test passes against production-mirror:
  ```bash
  cd /path/to/nowing  # repo root
  python3 nowing_backend/scripts/sse_cdn_smoke_test.py \
      --base-url https://<prod-mirror-host> \
      --bearer-token "$STAGING_TOKEN" \
      --thread-id <thread-id> \
      --run-id <run-uuid>
  ```
  Pass criteria (enforced by the script):
  - First heartbeat ≤ 16s
  - No gap between consecutive keep-alives exceeds `--max-gap-s` (default 17s, upper bound only)
  - At least `floor(60/15) − 1 = 3` keep-alives over 60s
- [ ] **A3.** Smoke test output (stderr) attached to the launch ticket.
- [ ] **A4.** Manual sanity from a network outside the office:
  - Phone on cellular data OR public-cafe Wi-Fi (NOT a corporate VPN).
  - Open the dashboard, start a fresh chat, watch the orchestra strip animate.
  - Capture DevTools Network tab screenshot showing `/stream` request with `Content-Type: text/event-stream` and connection duration ≥ 5 minutes.
  - "Connection lost — click to retry" banner must NOT appear during a 5-min idle period.

## Section B — HTTP/2 (story 11.6 T2 / FR41.2)

- [ ] **B1.** Traefik HTTP/2 verified per [`http2.md`](./http2.md):
  ```bash
  curl -I --http2 https://<prod-mirror-host>/health
  # Expect: HTTP/2 200
  ```
- [ ] **B2.** Multi-tab test: 3 browser tabs each running an SSE stream maintain `h2` protocol in DevTools Network tab.
- [ ] **B3.** Repeat B2 with the 4th, 5th, 6th tab — connections come up immediately (no head-of-line blocking).

## Section C — Plan IDs / Entitlement Drift (story 11.6 T3 / FR45 / AC#3)

- [ ] **C1.** CI workflow `Frontend Tests / Lint` includes the `pnpm verify:plan-ids` step (already wired into [`.github/workflows/frontend-tests.yml`](../../.github/workflows/frontend-tests.yml) — sanity-check that the workflow actually ran on the launch PR).
- [ ] **C2.** Generated [`nowing_web/lib/generated/plan-ids.ts`](../../nowing_web/lib/generated/plan-ids.ts) matches BE [`PlanId` enum](../../nowing_backend/app/schemas/stripe.py) — verified locally by:
  ```bash
  cd nowing_web
  pnpm verify:plan-ids
  ```
  (The repo is **not** a pnpm workspace — `pnpm --filter` from repo root will fail with `ERR_PNPM_NO_PKG_MANIFEST`. Run from inside `nowing_web/`.)
- [ ] **C3.** No drift comments / unresolved CI failures on the launch commit.

## Section D — Rate-Limiter Resilience (story 11.6 T4 / ADR-011 / AC#4)

- [ ] **D1.** Rate limiter unit tests pass on the launch commit:
  ```bash
  uv run pytest nowing_backend/tests/unit/middleware/test_rate_limiter.py -v
  ```
  Includes `test_ac4_redis_flap_no_double_consume` which verifies the state-mirror invariant.
- [ ] **D2.** *(Optional, post-launch)* Run a soak test simulating Redis flap with `toxiproxy` against the staging environment — see Story 11.7 T4.

## Section E — Sign-Off

- [x] **E1.** Architect sign-off (name, date): Winston, 2026-05-03
- [x] **E2.** DevOps sign-off (name, date): Luis, 2026-05-03
- [x] **E3.** Launch ticket / PR linked: PR #116
- [x] **E4.** Rollback plan rehearsed (see [Operations Runbook §3](../how-to/) — DNS revert + worker disable steps).

---

## Failure handling

If any item fails:

1. **A2 (CDN smoke)**: re-check Cloudflare config; common miss is the page rule priority being lower than a global "Cache everything" rule. Re-run smoke test after fix.
2. **B (HTTP/2)**: check whether a load balancer in front of Traefik (e.g. AWS NLB in TCP mode is fine; ALB terminates TLS and may not negotiate `h2` to backend). Adjust LB or use an L4 LB.
3. **C (plan-ids drift)**: `cd nowing_web && pnpm gen:plan-ids`, commit the regenerated file, push.
4. **D (rate-limiter test)**: regression — block launch and triage. Likely indicates the state-mirror code in `acquire()` was broken by a later refactor.

Do not launch with any unchecked item.

## References

- Story 11.6: [`stories/11-6-production-go-live-hardening.md`](../../_bmad-output/planning-artifacts/stories/11-6-production-go-live-hardening.md)
- ADR-011: [`adrs/ADR-011-rate-limiter-flap-consistency.md`](../../_bmad-output/planning-artifacts/adrs/ADR-011-rate-limiter-flap-consistency.md)
- ADR-012: [`adrs/ADR-012-entitlement-single-source-of-truth.md`](../../_bmad-output/planning-artifacts/adrs/ADR-012-entitlement-single-source-of-truth.md)
- Smoke test script: [`nowing_backend/scripts/sse_cdn_smoke_test.py`](../../nowing_backend/scripts/sse_cdn_smoke_test.py)
- CDN config doc: [`sse-cdn.md`](./sse-cdn.md)
- HTTP/2 config doc: [`http2.md`](./http2.md)
