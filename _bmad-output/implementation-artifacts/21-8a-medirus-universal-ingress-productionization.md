# Story 21.8a: Medirus Universal Ingress Productionization

Status: done

<!-- Note: Consolidated from 21.8a–f. Governed by architecture-medirus-social-integration-2026-08-15 (AD-SOC-1 to AD-SOC-11) + TRINITY-4 + INTEGRATION-PLAN-2026-09-09.md (Option A: MCP streamable-http approved) -->

## Story

As a Nowing B2B sales development representative and real estate investor,
I want Medirus social ingress to run over MCP streamable-http, support every configured platform, process the Redis stream end-to-end, and expose health/governance telemetry,
so that I can ingest leads from any vertical (social, e-commerce, real estate, recruitment, B2B registry) reliably, without spawning Node subprocesses, without duplicate posts, and without losing data when Medirus throttles or proxies fail.

## Context

Story 21.8 (Foundation) delivered the schema, `SocialEntityExtractor`, Redis producer, and unit/integration tests. This story productionizes the remaining work (formerly 21.8a–f).

Current gaps to fix:
- `MedirusSocialAdapter` (`adapter.py`) still spawns `node src/mcp/server.js` over stdio per call.
- `MedirusMcpClient` exists (`mcp_client.py`) but its session lifecycle is partially broken.
- `run_social_stream_consumer` exists but has no production Celery caller.
- Only `facebook_group` and `twitter_keyword` are accepted; `facebook_page`/`twitter_user` return empty; no VN domain platforms supported.
- `social_routes.py` only exposes `POST`.
- `SocialMonitoredTarget` has no `account_id` column; no `medirus_proxy_bindings` table.
- No governance/health telemetry from Medirus (`x_governor_status`, `x_admin_stream_metrics`, `x_admin_stream_alerts`).

## Acceptance Criteria

1. **MCP StreamableHTTP Transport** — **Given** `MEDIRUS_MCP_URL`, `MEDIRUS_MCP_API_KEY`, `MEDIRUS_CONSUMER_ID` are configured, **When** the adapter runs, **Then** it uses `mcp.client.streamable_http.streamablehttp_client` with Bearer auth and `X-Consumer-Id` headers, reuses a session across calls, and no `stdio_client`/`StdioServerParameters` path is used by default.
2. **3-Layer Envelope Parsing** — **Given** a tool call, **When** Medirus returns JSON, **Then** the client parses `success`, `data`, `meta` (incl. `datasetArtifactPath`, `durationMs`, `totalRecords`), and `summary`; empty/non-JSON responses degrade safely; `datasetArtifactPath` is fetched and merged when present.
3. **Structured Error Handling** — **Given** errors `XACT_4291`, `PROXY_EXHAUSTED`/`XACT_5030`, `ACCOUNT_HIBERNATION`, `XACT_4010`, `XACT_5000`, **When** they occur, **Then** `MedirusMcpError` carries `code`, `retry_after`/`retryAfterMs`, and `suggested_action`; the Celery ingest layer retries `XACT_4291` after `retry_after`, pauses target for `ACCOUNT_HIBERNATION`/proxy exhaustion, and stops on `XACT_4010`.
4. **Redis Stream Consumer Celery Wiring** — **Given** messages in `stream:social:raw_posts`, **When** Celery beat enqueues `process_social_stream` every 30 seconds, **Then** it reads via consumer group `social_processors`, persists/upserts into `SocialPost` (workspace-scoped unique on `(workspace_id, platform, external_post_id)`), creates `Lead` for high-intent posts, evaluates active `AlertRule` via `execute_alert_rule(session=..., alert_rule=..., fired_at=...)`, ACKs on success, and moves failures to `stream:social:failed` DLQ.
5. **Multi-Domain Target Expansion** — **Given** a `POST /workspaces/{id}/social-monitored-targets`, **When** payload uses any supported platform, **Then** it is accepted and persisted. Supported platforms: `facebook_group`, `facebook_page`, `twitter_keyword`, `twitter_user`, `tiktok_hashtag`, `chotot_category`, `shopee_keyword`, `topcv_search`, `vietnamworks_search`, `linkedin_company`, `batdongsan_category`, `masothue_lookup`, `b2b_registry_search`.
6. **Target CRUD** — **Given** an existing target, **When** a user calls `GET`/`PATCH`/`DELETE /workspaces/{id}/social-monitored-targets/{target_id}`, **Then** the endpoint returns the target, updates it, or deletes it (cascade deletes posts) while respecting workspace tenancy and `LEADS_WRITE` permission.
7. **Universal Scrape Target Mapper** — **Given** a `SocialMonitoredTarget` with `platform` and `target_id`, **When** `UniversalScrapeTargetMapper.map(target)` runs, **Then** it returns `(tool_name, arguments)` for the correct Medirus tool: `x_facebook_group_posts`, `x_facebook_posts`, `x_search_tweets`, `x_get_tweets`, or `x_scrape(platform, action, args)` for VN domains, with an `x_crawl_post` fallback when only post detail is available.
8. **Per-Account Proxy and Cookie Binding** — **Given** a target with `account_id` and `proxy_url`, **When** the scheduler calls Medirus, **Then** the request includes those values; if no target-level account exists, **Then** it falls back to `MEDIRUS_FACEBOOK_ACCOUNT_ID` or `x_facebook_list_accounts` (only when `MEDIRUS_MODE=local`; remote mode requires explicit `account_id`); bindings are stored in a new `medirus_proxy_bindings` table with `UNIQUE (workspace_id, account_id, platform)`.
9. **Medirus Governance and Health Integration** — **Given** admin telemetry is requested, **When** the system calls `x_governor_status`, **Then** it returns healthy proxy count, consumer quota, and backpressure; **When** `x_admin_stream_metrics` is called, **Then** it returns stream length, consumer lag, and throughput; **When** `x_admin_stream_alerts` reports a breach, **Then** Nowing sends an admin alert via Telegram/Email.
10. **Tests** — **Given** the completed implementation, **Then** unit tests cover envelope/auth/lifecycle, error matrix, `UniversalScrapeTargetMapper` for all 13 platforms, and integration tests cover Redis Stream end-to-end and a smoke MCP call to a live daemon (opt-in marker).

## Tasks / Subtasks

- [x] Task 1: `MedirusMcpClient` productionize (AC: 1, 2, 3)
  - [x] 1.1 Fix `mcp_client.py` session lifecycle: `connect()` must store the `streamablehttp_client` context manager and exit it cleanly; no `self.client._session.__aexit__` hack in `adapter_v2.py`.
  - [x] 1.2 Add `list_tools()` and a `health_check()` helper that calls `x_actions_list` or `x_governor_status`.
  - [x] 1.3 Improve `call_tool` non-JSON / empty handling; if `datasetArtifactPath` present, fetch artifact via HTTP GET or shared volume and merge with preview data.
  - [x] 1.4 Add test: `test_medirus_mcp_client_lifecycle.py` (session reuse, transport close).
- [x] Task 2: Replace stdio adapter with streamable-http (AC: 1, 7)
  - [x] 2.1 Update `adapter.py` (`MedirusSocialAdapter`) to use `MedirusMcpClient` via `async with`; remove or gate `stdio_client` behind `MEDIRUS_TRANSPORT=stdio`.
  - [x] 2.2 Finalize `adapter_v2.py` (`MedirusSocialAdapterV2`) and `UniversalScrapeTargetMapper`; fix session lifecycle per 1.1.
  - [x] 2.3 Export `STREAM_SOCIAL_RAW_POSTS` from `adapter_v2.py` or move to `medirus/constants.py`; do not import stream constant from `adapter.py` (v1) to avoid coupling.
  - [x] 2.4 Move `SocialPostData` / `SocialMonitoredTargetData` dataclasses to `medirus/models.py` or keep in `adapter.py` and re-export from `adapter_v2.py`; ensure `ingest_social_target_task` handles a single type.
  - [x] 2.5 Wire `adapter_v2` into `social_medirus_ingest.py` `ingest_social_target_task` so it actually gets used instead of the empty `facebook_page`/`twitter_user` branches.
- [x] Task 3: Scheduler error handling (AC: 3)
  - [x] 3.1 In `social_medirus_ingest.py`, catch `MedirusMcpError`; retry `XACT_4291` with `countdown=exc.retry_after`; pause target for `ACCOUNT_HIBERNATION`, `PROXY_EXHAUSTED`, `XACT_5030`; halt on `XACT_4010`.
  - [x] 3.2 Track target `status` transitions (`active` → `paused` → `error`) and `last_scraped_at`.
- [x] Task 4: Redis stream consumer Celery wiring (AC: 4)
  - [x] 4.1 Verify `celery_tasks/social_stream_worker.py` calls `run_social_stream_consumer` correctly (consumer group `social_processors`, block, batch size).
  - [x] 4.2 Verify `celery_app.py` beat schedule `process-social-stream` exists, expires=25, and is routed to `CELERY_TASK_DEFAULT_QUEUE` or a new `nowing.social` queue (not `CONNECTORS_QUEUE` which is for indexing).
  - [x] 4.3 Add DLQ behavior and ACK guarantees in `social_stream_worker.py` if missing.
  - [x] 4.4 Ensure `xadd` to `stream:social:raw_posts` uses `maxlen=20000, approximate=True` per AD-SOC-4.
  - [x] 4.5 Integration test: `test_social_redis_stream_end_to_end.py`.
- [x] Task 5: Multi-domain platform expansion (AC: 5, 6, 7)
  - [x] 5.1 Update `SocialTargetCreate.platform` regex in `social_routes.py` and `SUPPORTED_PLATFORMS` in `social_medirus_ingest.py` to 13 platforms.
  - [x] 5.2 Add `GET`, `PATCH`, `DELETE` endpoints to `social_routes.py`.
  - [x] 5.3 Implement `UniversalScrapeTargetMapper` arg builders for all 13 platforms (see Dev Notes for action args).
- [x] Task 6: Per-account proxy/cookie binding (AC: 8)
  - [x] 6.1 Add `account_id` column to `SocialMonitoredTarget` (Alembic migration 212 or later).
  - [x] 6.2 Add `medirus_proxy_bindings` table via new `MedirusProxyBinding` model in `app/models/leads/medirus.py` and register in `app/db/__init__.py`.
  - [x] 6.3 Update `SocialTargetCreate`/`SocialTargetRead` schemas to include `account_id`.
  - [x] 6.4 In `ingest_social_target_task`, inject `accountId`/`proxyUrl` from target; fallback to `MEDIRUS_FACEBOOK_ACCOUNT_ID` or `x_facebook_list_accounts` (only if `MEDIRUS_MODE=local`; remote mode requires explicit `account_id`).
- [x] Task 7: Governance and health integration (AC: 9)
  - [x] 7.1 Add Celery beat `health_probe_medirus` every 5 minutes calling `x_governor_status` and `x_admin_stream_metrics` (reuse `health_probe_task.py` pattern or create `medirus_health_task.py`).
  - [x] 7.2 Expose internal admin endpoint (or `HealthProbe`) returning `x_governor_status` + `x_admin_stream_metrics`.
  - [x] 7.3 On `x_admin_stream_alerts` breach, call `execute_alert_rule(session=session, alert_rule=rule, fired_at=datetime.now(UTC))` for each matching rule; send Telegram/Email via existing alert channels.
- [x] Task 8: Config, env, and migrations (AC: 1, 8)
  - [x] 8.1 Ensure `app/config/entities.py` exports all `MEDIRUS_MCP_*` variables and they are in `app/config/__init__.py`; add `MEDIRUS_TRANSPORT` (default `streamable-http`) and `MEDIRUS_MODE` (default `local`).
  - [x] 8.2 Add `MEDIRUS_MCP_URL`, `MEDIRUS_MCP_API_KEY`, `MEDIRUS_FACEBOOK_ACCOUNT_ID`, `MEDIRUS_TRANSPORT`, `MEDIRUS_MODE` to `.env.local` and env templates.
  - [x] 8.3 Create Alembic migration(s): `account_id` on `social_monitored_targets`; `medirus_proxy_bindings`; new `category/storage_ref/scraper_id/benchmark_health/benchmark_alert` columns on `social_posts` if not already present (check `app/models/leads/social.py` and existing migrations).
- [x] Task 9: Tests and shadow-run (AC: 10)
  - [x] 9.1 Unit tests: `mcp_client`, `adapter_v2`, `UniversalScrapeTargetMapper`.
  - [x] 9.2 Integration: Redis stream consumer end-to-end.
  - [ ] 9.3 Optional smoke: live Medirus MCP `list_tools()`.
  - [ ] 9.4 Shadow-run: run new and old adapter side-by-side for 7 days only if legacy code not yet removed; success criteria: post count parity ≥ 99%, extracted phone overlap ≥ 95%, no missing platforms.

## Dev Notes

- **Architecture Invariants:** AD-SOC-1..11. Non-negotiable: no scraper reinvention in Nowing (AD-SOC-1); HTTP MCP (AD-SOC-4); intent extraction (AD-SOC-5); idempotent storage (AD-SOC-6); alert/lead hooks (AD-SOC-7); gap-fill caching (AD-SOC-8); legacy decommission (AD-SOC-9); 30-day Medirus raw TTL (AD-SOC-10); adaptive rate limiting (AD-SOC-11).
- **Existing MCP client pattern:** `app/agents/chat/multi_agent_chat/shared/tools/mcp/client.py` uses `streamablehttp_client`. Do not create another abstraction — `MedirusMcpClient` is the Medirus-specific thin wrapper.
- **Adapter lifecycle bug (P0):** `adapter_v2._get_client()` calls `self.client.connect().__aenter__()` without retaining the `connect()` context manager. Since `connect()` wraps `streamablehttp_client`, not exiting it leaks the transport/SSE reader. Fix by either (a) storing `self._cm = client.connect(); await self._cm.__aenter__()` and `await self._cm.__aexit__()` in `close()`, or (b) refactoring `MedirusMcpClient` itself to be an async context manager that owns `streamablehttp_client` + `ClientSession` in one object. Add a test asserting both `__aexit__`s are called.
- **Stdio fallback (optional):** If you must keep stdio (e.g. local dev without Medirus daemon running on port 3001), gate it behind `MEDIRUS_TRANSPORT=stdio`; default is `streamable-http`. Remove from the hot path.
- **VN-domain action args** (for `UniversalScrapeTargetMapper` `x_scrape` dispatch):
  - `tiktok_hashtag` → `{platform:"tiktok", action:"posts", hashtag:t.target_id}`
  - `chotot_category` → `{platform:"chotot", action:"posts", category:t.target_id}`
  - `shopee_keyword` → `{platform:"shopee", action:"search", keyword:t.target_id}`
  - `topcv_search` / `vietnamworks_search` → `{platform, action:"search", query:t.target_id}`
  - `linkedin_company` → `{platform:"linkedin", action:"company", company:t.target_id}`
  - `batdongsan_category` → `{platform:"batdongsan", action:"posts", category:t.target_id}`
  - `masothue_lookup` → `{platform:"masothue", action:"lookup", taxCode:t.target_id}`
  - `b2b_registry_search` → `{platform:"b2b_registry", action:"search", query:t.target_id}`
- **Medirus request for new features:** This story requires Medirus to expose generic `x_scrape` and thin-event stream for all crawlers (A1/A2 from `INTEGRATION-PLAN-2026-09-09.md`). If Medirus has not delivered, the implementation MUST fall back to `x_crawl_post` with `url` args per platform and accept reduced functionality; do **not** implement scraping in Nowing.
- **Do not break:** `SocialEntityExtractor`, Redis producer payload shape, existing alert rules, existing `facebook_group`/`twitter_keyword` behavior.
- **Out of scope:** Removing all legacy scraper directories (AD-SOC-9 decommission) — belongs to a follow-up once parity ≥ 99%.
- **PII:** Extracted phone/price/location still goes into `raw_entities` and lead CRM; do not store PII in logs.
- **Alert rule call signature:** Use `execute_alert_rule(session=session, alert_rule=rule, fired_at=datetime.now(UTC))` from `app/alerts/engine/execute.py`; do NOT invent `AlertEngine.evaluate_new_social_post()`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 21.8 + 21.8a–f, consolidated]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-medirus-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-medirus-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-medirus-21-8-correction.md]
- [Source: nowing_backend/app/proprietary/platforms/medirus/mcp_client.py]
- [Source: nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py]
- [Source: nowing_backend/app/proprietary/platforms/medirus/adapter.py:445-456 — stdio path to replace]
- [Source: nowing_backend/app/tasks/celery_tasks/social_medirus_ingest.py]
- [Source: nowing_backend/app/tasks/celery_tasks/social_stream_worker.py]
- [Source: nowing_backend/app/routes/social_routes.py]
- [Source: nowing_backend/app/models/leads/social.py]
- [Source: nowing_backend/alembic/versions/211_social_unique_workspace_scoped.py]
- [Source: Medirus/src/mcp/server.js — /mcp endpoint and quota gate]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

### Completion Notes List

- 2026-09-09: `mcp_client.py`, `adapter_v2.py`, `social_stream_worker.py`, `config/entities.py`, and `celery_app.py` were partially scaffolded before this consolidated story was created. Dev agent must verify all existing code against ACs, fix the lifecycle bug in 1.1, and complete all Tasks 2–9.
- 2026-09-09: Applied validation fixes: alert call signature, stream constant export, `MEDIRUS_TRANSPORT`/`MEDIRUS_MODE`, `medirus_proxy_bindings` model file, `maxlen` for Redis stream, `health_probe_medirus` naming, `datasetArtifactPath` fetch, `account_id` remote-mode caveat, upsert columns.

### File List

- `nowing_backend/app/proprietary/platforms/medirus/mcp_client.py` (exists, update lifecycle)
- `nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py` (exists, fix lifecycle, wire to ingest)
- `nowing_backend/app/proprietary/platforms/medirus/adapter.py` (replace stdio)
- `nowing_backend/app/proprietary/platforms/medirus/constants.py` (new, for `STREAM_SOCIAL_RAW_POSTS` if not kept in adapter_v2)
- `nowing_backend/app/proprietary/platforms/medirus/models.py` (new, for `SocialPostData`/`SocialMonitoredTargetData` if moved)
- `nowing_backend/app/tasks/celery_tasks/social_medirus_ingest.py` (error handling + use adapter_v2 + expand platforms)
- `nowing_backend/app/tasks/celery_tasks/social_stream_worker.py` (DLQ/ACK verification + maxlen)
- `nowing_backend/app/celery_app.py` (beat schedule already present)
- `nowing_backend/app/routes/social_routes.py` (CRUD + platform enum)
- `nowing_backend/app/models/leads/social.py` (add `account_id`)
- `nowing_backend/app/models/leads/medirus.py` (new, `MedirusProxyBinding`)
- `nowing_backend/alembic/versions/212_medirus_universal_ingress.py` (new migration, or follow next sequence)
- `nowing_backend/app/config/entities.py` (already added, verify exports)
- `nowing_backend/.env.local` (add MCP URL + API key + transport/mode, no secrets committed)
- `nowing_backend/tests/unit/platforms/test_medirus_mcp_client.py` (new)
- `nowing_backend/tests/unit/platforms/test_medirus_mapper.py` (new)
- `nowing_backend/tests/integration/platforms/test_social_redis_stream.py` (update/extend)

### Review Findings (2026-09-09)

- [x] [Review][Patch] Celery beat `health_probe_medirus` chưa register task — patched 2026-09-09 — `nowing_backend/app/celery_app.py:525`
- [x] [Review][Patch] `MedirusSocialAdapter._call_mcp_tool` bridge qua v2 bị truyền dict thay vì object — patched 2026-09-09 — `adapter.py:419`
- [x] [Review][Patch] `published_at` string chưa parse datetime gây `AttributeError` khi `to_dict()` — patched 2026-09-09 — `adapter_v2.py:183` / `models.py`
- [x] [Review][Patch] `MedirusSocialAdapterV2` không được `close()` / `async with` trong Celery task, leak kết nối — patched 2026-09-09 — `social_medirus_ingest.py:1449`
- [x] [Review][Patch] `test_social_medirus_ingest.py` cũ bị broken (import `MedirusSocialAdapter` + thiếu `task` param) — patched 2026-09-09 — `tests/unit/tasks/celery_tasks/test_social_medirus_ingest.py`
- [x] [Review][Patch] `MedirusProxyBinding` chưa được đọc/tra cứu trong ingestion — patched 2026-09-09 — `adapter_v2.py:587` / `social_medirus_ingest.py`
- [x] [Review][Patch] `MedirusHealthProbe` dùng sai key `healthyProxies` thay vì `healthyProxyCount` — patched 2026-09-09 — `medirus_probe.py:34`
- [x] [Review][Patch] `MedirusProxyBinding` thiếu relationship `workspace`/`back_populates` — patched 2026-09-09 — `models/workspaces.py`
- [x] [Review][Patch] `_normalize_platform_for_post` cắt ngắn `b2b_registry_search` thành `b2b` — patched 2026-09-09 — `adapter_v2.py:545`
- [x] [Review][Patch] Thiếu `x_crawl_post` fallback trong `UniversalScrapeTargetMapper` — patched 2026-09-09 — `adapter_v2.py`
- [x] [Review][Patch] `paused` target không tự động resume do scheduler chỉ lọc `status == active` — patched 2026-09-09 — `social_medirus_ingest.py:223`
- [x] [Review][Patch] `retry_after` từ `retryAfterMs` không chia 1000 gây countdown sai đơn vị — patched 2026-09-09 — `mcp_client.py:147` / `social_medirus_ingest.py:156`
- [x] [Review][Patch] Consumer name dùng `nowing-{request.id}` mới mỗi lần chạy, gây PEL leak — patched 2026-09-09 — `social_stream_worker.py:32`
- [x] [Review][Patch] `SocialPostData` thiếu thin-event fields `category/storage_ref/scraper_id/benchmark_health/benchmark_alert` — patched 2026-09-09 — `models.py`
- [x] [Review][Patch] `_fetch_artifact` đọc file sync block event loop, thiếu path traversal guard — patched 2026-09-09 — `mcp_client.py:163`
- [x] [Review][Patch] `list_social_targets` thiếu pagination, ordering, filter — patched 2026-09-09 — `social_routes.py:168`
- [x] [Review][Patch] Thiếu tích hợp `x_admin_stream_alerts` với `execute_alert_rule` — patched 2026-09-09 — `medirus_probe.py`
- [x] [Review][Patch] `MEDIRUS_CONSUMER_ID` bị bỏ khỏi `__all__` trong `config/entities.py` — patched 2026-09-09
- [x] [Review][Patch] `.env.local` ghi đè `NEXT_FRONTEND_URL=3002` thay vì 3000 — patched 2026-09-09
- [x] [Review][Patch] `category` model/migration default mismatch (`server_default='general'` vs `nullable=True`) — patched 2026-09-09 — `social.py:143` / migration
- [x] [Review][Defer] Một số file unit test mới chưa bao phủ lifecycle, health probe, route CRUD — resolved (added test_medirus_probe.py & test_social_routes.py)
