---
title: 'Story 36.6a: Canonical Action Matrix — Dynamic Dispatch via `x_actions_list`'
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_commit: 'e442062f12a1036e0a06e96e2c8a75f8497529e5'
review_loop_iteration: 0
context:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-1'
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-2'
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-6'
  - '../planning-artifacts/XACTIONS-REQUIREMENTS-2026-09-13.md#req-x3'
  - '../planning-artifacts/XACTIONS-REQUIREMENTS-2026-09-13.md#req-x4'
  - 'epic-36-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `UniversalScrapeTargetMapper.map()` dùng `PLATFORM_TOOL_MAP` hardcoded — khi XActions đổi action name hoặc requiredArgs, Nowing phải sửa code. Ngoài ra, nhiều entry hiện đang sai action (vd `tiktok_hashtag → action="posts"` trong khi canonical XActions là `posts_by_hashtag`; `masothue_lookup → action="lookup"` thay vì `company_by_taxcode`).

**Approach:** Thêm `CanonicalActionMatrix` — async TTL-cached registry được fetch từ `x_actions_list` MCP tool, có static fallback matrix khi XActions down. `UniversalScrapeTargetMapper` dispatch qua `x_scrape` với nested `{platform, action, args, context:{targetId, workspaceId}}` shape (theo AD-1/AD-2). Validate `SocialMonitoredTarget.platform` khi create/update (422 on unsupported). Toàn bộ sau feature flag `XACTIONS_USE_UNIFIED_DISPATCH` — flag OFF giữ behavior cũ.

## Boundaries & Constraints

**Always:**
- **Nested envelope:** Dispatch `x_scrape` với `{platform, action, args: {...}, context: {targetId, workspaceId}, accountId?, proxyUrl?}` — KHÔNG flat top-level fields. `args` chứa action-specific args theo `requiredArgs`/`optionalArgs` từ descriptor.
- **Cache TTL + fallback:** `CanonicalActionMatrix.get()` trả cached nếu `now - last_fetch < TTL_SECONDS` (mặc định 300s). Khi refresh fail hoặc trả empty/partial → serve stale cache, hoặc `STATIC_FALLBACK_MATRIX` (embed in code, conservative — chỉ platforms đã biết work: facebook/twitter/tiktok/chotot/shopee/topcv/vietnamworks/linkedin/batdongsan/masothue/b2b_registry).
- **Validation on create/update:** `POST/PATCH /workspaces/{id}/social-monitored-targets` — nếu `platform` không có trong matrix (kể cả fallback) → `HTTPException(422, detail=...)`. Chi tiết error gồm `supported_platforms` list.
- **Feature flag gate:** Tất cả dispatch mới chỉ active khi `XACTIONS_USE_UNIFIED_DISPATCH=true`. Flag OFF → dùng `PLATFORM_TOOL_MAP` cũ (giữ nguyên fallback path).
- **Derive platform+action:** Từ `SocialMonitoredTarget.platform` (vd `tiktok_hashtag`) → split thành `(platform="tiktok", action_hint="hashtag")` → lookup matrix `matrix["tiktok"]["posts_by_hashtag"]` (hoặc action có `match: {target_kind: "hashtag"}`). Nếu ambiguous → 422.

**Ask First:**
- Migration path cho existing `SocialMonitoredTarget` rows có `platform="tiktok_hashtag"` (legacy compound form) → cần data migration không? Default: NO — giữ nguyên compound form làm `platform_kind`, derive `platform`/`action` at dispatch time.
- Invalidate cache thủ công (admin endpoint `/admin/xactions/cache/refresh`)? Default: NO — TTL-based đủ.

**Never:**
- Không đổi signature `UniversalScrapeTargetMapper.map()` return type — vẫn trả `tuple[str, dict]` (tool_name, args). Caller (`fetch_posts_for_target`) không cần đổi.
- Không migrate sang `x_scrape` cho Facebook/Twitter legacy tools (`x_facebook_group_posts`, `x_search_tweets`...) — giữ nguyên. Unified dispatch chỉ apply cho platforms đang dùng `x_scrape` trong `PLATFORM_TOOL_MAP`.
- Không thêm cột `action` vào `social_monitored_targets` — derive từ `platform` field.
- Không để `x_actions_list` network call block request path — validation dùng cached matrix (không fetch synchronous).
- Không drop `PLATFORM_TOOL_MAP` khỏi code — nó là fallback khi flag OFF.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path — cache hit, valid platform | `platform="tiktok_hashtag"`, `XACTIONS_USE_UNIFIED_DISPATCH=true`, cache has `tiktok` descriptor with `posts_by_hashtag` action | `map()` returns `("x_scrape", {platform:"tiktok", action:"posts_by_hashtag", args:{hashtag:...}, context:{targetId, workspaceId}})` | N/A |
| Cache miss → fetch `x_actions_list` | Cold start, flag ON | `await client.call_tool("x_actions_list", {})`, parse `ActionDescriptor[]`, populate cache, then map | Fetch fail → fallback to static matrix, log warning |
| XActions down + static fallback | Flag ON, `x_actions_list` raises, static matrix has `tiktok` | Map succeeds via static fallback | Log warning "using static fallback matrix" |
| Unsupported platform | `platform="xyz_unknown"`, flag ON | `map()` raises `ValueError("Unsupported platform: xyz_unknown")` | API layer → 422 |
| Ambiguous action | `platform="tiktok"` without kind suffix, descriptor has multiple actions | `map()` raises `ValueError("Ambiguous action for platform tiktok — expected tiktok_<kind>")` | API layer → 422 |
| Flag OFF | `XACTIONS_USE_UNIFIED_DISPATCH=false` | `map()` uses `PLATFORM_TOOL_MAP` exactly as before | N/A |
| `SocialMonitoredTarget` create with unsupported platform | POST `{platform: "xyz"}`, flag ON | `HTTPException(422, detail={supported_platforms: [...]})` | 422 response |
| Partial catalog from XActions | `x_actions_list` returns only 3 of 12 platforms | Serve merged: live catalog ∪ static fallback for missing | Log info "partial catalog merged with static" |
| `target_id` empty after derive | `platform="tiktok_hashtag"`, `target_id=""` | `map()` raises `ValueError("target_id required for action posts_by_hashtag")` | 422 |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:34-87` — `PLATFORM_TOOL_MAP` (static dict, flag OFF path). `map()` at 145-151.
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:136-172` — `UniversalScrapeTargetMapper` — extend with `CanonicalActionMatrix`-backed `map()` under flag.
- `nowing_backend/app/proprietary/platforms/xactions/mcp_client.py:201-228` — `list_tools()` and `call_tool()` — `x_actions_list` is invoked via `call_tool("x_actions_list", {})`.
- `nowing_backend/app/proprietary/platforms/xactions/action_matrix.py` — **NEW FILE** — `CanonicalActionMatrix` class + `STATIC_FALLBACK_MATRIX` + `parse_action_descriptors()`.
- `nowing_backend/app/config/entities.py:90-92` — add `XACTIONS_USE_UNIFIED_DISPATCH` env flag next to `XACTIONS_STREAM_SINGLE_WRITER_ENABLED`.
- `nowing_backend/app/routes/social_routes.py:30-101` — `SUPPORTED_PLATFORMS`, `SocialTargetCreate/Update` Pydantic schemas — validate `platform` against matrix when flag ON.
- `nowing_backend/app/routes/social_routes.py:140-186, 251-280` — `create_social_target`, `update_social_target` — inject validation.
- `nowing_backend/app/services/model_list_service.py:171-187` — TTL cache pattern (reference impl).
- `nowing_backend/app/models/leads/social.py:33-83` — `SocialMonitoredTarget` model (no `action` column; derive from `platform`).
- `nowing_backend/tests/unit/platforms/test_xactions_mapper.py` — extend for matrix-driven tests.
- `nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py` — **NEW FILE** — unit tests for cache/fallback/parse.
- `nowing_backend/tests/unit/routes/test_social_routes.py` — add 422 validation tests.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/config/entities.py` — add `XACTIONS_USE_UNIFIED_DISPATCH` flag (default `false`).
- [x] `nowing_backend/app/proprietary/platforms/xactions/action_matrix.py` — NEW: `ActionDescriptor` Pydantic schema, `CanonicalActionMatrix` class with `async def get(client) -> dict`, `STATIC_FALLBACK_MATRIX` dict, TTL cache (300s), merge-with-static logic on partial catalog, `derive_platform_action(platform_kind) -> tuple[str, str]`.
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` — extend `UniversalScrapeTargetMapper.map()` to check flag: if ON, resolve via `CanonicalActionMatrix.get_sync()` (sync `map()` preserved); new `map_async()` awaits `CanonicalActionMatrix.get(client)`; if OFF, existing `PLATFORM_TOOL_MAP` path unchanged.
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` — `XActionsSocialAdapterV2.fetch_posts_for_target`: `await UniversalScrapeTargetMapper.map_async(target, client)` when flag ON.
- [x] `nowing_backend/app/routes/social_routes.py` — inject matrix-based platform validation into `create_social_target` behind flag (update route has no `platform` field on `SocialTargetUpdate`), raise `HTTPException(422, detail={supported_platforms})` on unsupported.
- [x] `nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py` — NEW: tests for cache hit/miss, fallback on fetch fail, partial catalog merge, derive_platform_action, descriptor parse.
- [x] `nowing_backend/tests/unit/platforms/test_xactions_mapper.py` — extend tests for flag-ON dispatch shape (nested `args`, `context` envelope).
- [x] `nowing_backend/tests/unit/routes/test_social_routes.py` — 422 tests for unsupported platform.

**Acceptance Criteria:**
- Given `XACTIONS_USE_UNIFIED_DISPATCH=true` and `x_actions_list` returns canonical descriptors, when `UniversalScrapeTargetMapper.map()` is called for `tiktok_hashtag` target, then it returns `("x_scrape", {platform:"tiktok", action:"posts_by_hashtag", args:{hashtag:...}, context:{targetId, workspaceId}})` — not `action="posts"`.
- Given flag ON and `x_actions_list` fetch fails, when `map()` called, then it serves `STATIC_FALLBACK_MATRIX` without raising.
- Given flag ON and POST `/social-monitored-targets` with `platform="xyz_unknown"`, when validation runs, then API returns `422` with `detail.supported_platforms` list.
- Given flag OFF, when `map()` called for any target, then behavior is byte-identical to current `PLATFORM_TOOL_MAP` path.
- Given `x_actions_list` returns only 3 platforms (partial), when `map()` called for `tiktok_hashtag` (in static fallback), then mapping succeeds via merged catalog.

## Spec Change Log

## Design Notes

**Tại sao `map()` phải async khi flag ON:** `x_actions_list` là MCP call — bắt buộc await. Sync `map()` giữ cho flag OFF để không phá signature; flag ON dùng `map_async()`. Caller `fetch_posts_for_target` đã là async nên không phá API.

**Tại sao không migrate Facebook/Twitter legacy tools:** `x_facebook_group_posts`, `x_search_tweets` vẫn đang hoạt động — unified dispatch chỉ thay các entry đã dùng `x_scrape` (VN platforms + LinkedIn). Legacy tools chuyển ở Story 36.6b sau khi XActions REQ-X1 confirmed live trên mọi platform.

**Derive `platform` + `action` từ `platform_kind`:** `platform` field hiện lưu compound `tiktok_hashtag`, `chotot_category`... Split tại `_` cuối cùng được `kind` → tra descriptor có `match.target_kind == kind` → dùng descriptor.action. Nếu descriptor không có `match` → dùng descriptor đầu tiên của platform. Nếu nhiều descriptors mà không có kind → 422 ambiguous.

**STATIC_FALLBACK_MATRIX shape:** embed in `action_matrix.py`. Per platform, dict of `{action_name: {requiredArgs: [...], match: {target_kind: "<suffix>"}}}`. Cover all 11 platforms currently in `PLATFORM_TOOL_MAP` — conservative (only actions already working).

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/platforms/test_canonical_action_matrix.py -q` — expected: all pass
- `cd nowing_backend && uv run pytest tests/unit/platforms/test_xactions_mapper.py -q` — expected: all pass (flag OFF + flag ON shapes)
- `cd nowing_backend && uv run pytest tests/unit/routes/test_social_routes.py -q` — expected: all pass (422 cases covered)
- `cd nowing_backend && uv run pytest tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py -q` — expected: all pass (no regression)

**Manual checks:**
- `XACTIONS_USE_UNIFIED_DISPATCH=false uv run python -c "from app.proprietary.platforms.xactions.adapter_v2 import UniversalScrapeTargetMapper; ..."` — flag OFF path unchanged.

## Suggested Review Order

**Entry point — unified dispatch shape**

- Nested envelope construction for x_scrape under flag ON; binds target_id → single requiredArg.
  [`adapter_v2.py:158`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L158)

- map() branches flag OFF (PLATFORM_TOOL_MAP) vs ON (get_sync + _unified_envelope).
  [`adapter_v2.py:205`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L205)

- map_async() awaits CanonicalActionMatrix.get(client) when flag ON; delegates to map() when OFF.
  [`adapter_v2.py:233`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L233)

**Canonical action matrix (fetch + fallback + derive)**

- Loop-scoped lock, TTL cache, merge-with-static on partial catalog.
  [`action_matrix.py:211`](../../nowing_backend/app/proprietary/platforms/xactions/action_matrix.py#L211)

- STATIC_FALLBACK_MATRIX — canonical action names for 11 known-working platforms.
  [`action_matrix.py:51`](../../nowing_backend/app/proprietary/platforms/xactions/action_matrix.py#L51)

- derive_platform_action — split platform_kind, match target_kind, ambiguous → 422.
  [`action_matrix.py:319`](../../nowing_backend/app/proprietary/platforms/xactions/action_matrix.py#L319)

**Route validation (422 + supported_platforms)**

- _matrix_supported_platform_kinds — derives supported_platforms list from matrix.
  [`social_routes.py:57`](../../nowing_backend/app/routes/social_routes.py#L57)

- _validate_platform_against_matrix — raises HTTPException(422) with supported_platforms.
  [`social_routes.py:78`](../../nowing_backend/app/routes/social_routes.py#L78)

- SocialTargetCreate.platform validator relaxes when flag ON so route can raise detailed 422.
  [`social_routes.py:120`](../../nowing_backend/app/routes/social_routes.py#L120)

- create_social_target injects matrix check before workspace lookup.
  [`social_routes.py:211`](../../nowing_backend/app/routes/social_routes.py#L211)

**Config flag**

- XACTIONS_USE_UNIFIED_DISPATCH env flag (default false) + __all__ entry.
  [`entities.py:99`](../../nowing_backend/app/config/entities.py#L99)

**Caller wiring**

- fetch_posts_for_target picks map_async under flag ON, keeps sync map otherwise.
  [`adapter_v2.py:300`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L300)

**Tests**

- test_canonical_action_matrix.py — cache/fallback/merge/derive coverage.
  [`test_canonical_action_matrix.py:1`](../../nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py#L1)

- test_xactions_mapper.py — flag-ON nested envelope + flag-OFF flat args + legacy tool preservation.
  [`test_xactions_mapper.py:100`](../../nowing_backend/tests/unit/platforms/test_xactions_mapper.py#L100)

- test_social_routes.py — 422 with supported_platforms payload.
  [`test_social_routes.py:328`](../../nowing_backend/tests/unit/routes/test_social_routes.py#L328)
