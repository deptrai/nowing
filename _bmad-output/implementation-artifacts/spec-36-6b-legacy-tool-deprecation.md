---
title: 'Story 36.6b: Legacy Tool Deprecation — Route FB/Twitter via Unified `x_scrape` Dispatch'
type: 'feature'
created: '2026-09-15'
status: 'done'
baseline_commit: 'f13016bbbc93ed60f7e2f1e2ba0bfff5ee4cf8f5'
review_loop_iteration: 0
context:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-1'
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-2'
  - '../planning-artifacts/XACTIONS-REQUIREMENTS-2026-09-13.md#req-x1'
  - 'epic-36-context.md'
  - 'spec-36-6a-canonical-action-matrix.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 36.6a shipped the canonical action matrix but deliberately left `facebook_group`, `facebook_page`, `twitter_keyword`, `twitter_user` on dedicated legacy tools (`x_facebook_group_posts`, `x_facebook_posts`, `x_search_tweets`, `x_get_tweets`) to avoid regressing working monitoring. Now REQ-X1 (`x_scrape`) is confirmed live on XActions for those platforms, so the legacy tool branches inside `UniversalScrapeTargetMapper` are a parallel dispatch path that drifts from canonical action names.

**Approach:** Route the four legacy `platform` values through the same `CanonicalActionMatrix` + `x_scrape` envelope as every other platform — behind a *second* env flag `XACTIONS_LEGACY_TOOL_DEPRECATION` (default `false`) that only takes effect when `XACTIONS_USE_UNIFIED_DISPATCH=true`. Flag OFF preserves today's byte-identical legacy tool calls so a flag flip is an instant rollback.

## Boundaries & Constraints

**Always:**
- Gate on `XACTIONS_USE_UNIFIED_DISPATCH AND XACTIONS_LEGACY_TOOL_DEPRECATION`. Deprecation flag alone is a no-op — never bypass unified dispatch.
- Reuse `UniversalScrapeTargetMapper._unified_envelope` / `map_async` from 36.6a — do not fork the dispatch path.
- `STATIC_FALLBACK_MATRIX` already contains `facebook` (`group_posts`/`page_posts`) and `twitter` (`search_tweets`/`user_tweets`) entries from 36.6a — the dispatch side just stops special-casing them; no schema change needed.
- Preserve current arg semantics: `facebook_group`/`facebook_page` bind `target_id` → `url` via `_facebook_group_url` / `_facebook_page_url` (URL-ify non-HTTP ids). `twitter_keyword` binds `target_id` → `query`. `twitter_user` binds `target_id.strip('@')` → `username`. These arg-shape rules live inside the matrix-driven envelope.
- `x_crawl_post` fallback on `XACT_404`/`tool_not_found` stays in place — the unified envelope may still miss if XActions is older than the matrix.

**Ask First:**
- Removing the legacy tool call sites once both flags have been ON in production ≥ 1 sprint — NOT this story.
- Touching `app/agents/chat/multi_agent_chat/shared/tools/mcp/xactions_gateway.py` (chat-agent tool, separate from `SocialMonitoredTarget` dispatch) — NOT this story.
- Touching `app/proprietary/platforms/xactions/adapter.py` (legacy v1 adapter, no live callers) — NOT this story.

**Never:**
- Do not delete `PLATFORM_TOOL_MAP`, `_facebook_group_url`, `_facebook_page_url`, or the legacy-tool branches — flag OFF must remain byte-identical to today.
- Do not change `SocialMonitoredTarget` schema, `SUPPORTED_PLATFORMS`, or route validation — `facebook_group`/`twitter_user` etc. remain valid `platform_kind` values.
- Do not change `derive_platform_action` semantics — `facebook_group` still derives `(platform="facebook", action="group_posts")` via `match.target_kind == "group"`.
- Do not introduce a new flag name or per-platform flag — one boolean is enough; finer-grained rollout is handled by XActions-side rollout.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Unified OFF (both flags irrelevant) | `XACTIONS_USE_UNIFIED_DISPATCH=false`, `target.platform="facebook_group"` | `map()` returns `("x_facebook_group_posts", {url: "https://www.facebook.com/groups/{id}", limit: 20})` — identical to today | N/A |
| Unified ON, deprecation OFF | `XACTIONS_USE_UNIFIED_DISPATCH=true`, `XACTIONS_LEGACY_TOOL_DEPRECATION=false`, `platform="twitter_user"` | `map()` still returns `("x_get_tweets", {username: "...", limit: 20})` — legacy branch preserved | N/A |
| Unified ON, deprecation ON, facebook_group | `target_id="group123"` | `("x_scrape", {platform:"facebook", action:"group_posts", args:{url:"https://www.facebook.com/groups/group123"}, context:{targetId,workspaceId}})` — `url` is URL-ified | N/A |
| Unified ON, deprecation ON, facebook_group with full URL | `target_id="https://www.facebook.com/groups/abc"` | Same as above, `args.url` passes through verbatim | N/A |
| Unified ON, deprecation ON, twitter_user | `target_id="@elon"` | `("x_scrape", {platform:"twitter", action:"user_tweets", args:{username:"elon"}, ...})` — `@` stripped | N/A |
| Unified ON, deprecation ON, twitter_keyword | `target_id="AI agents"` | `("x_scrape", {platform:"twitter", action:"search_tweets", args:{query:"AI agents"}, ...})` | N/A |
| Unified ON, deprecation ON, matrix lacks facebook/twitter | `x_actions_list` partial + static fallback updated | Static matrix covers all four kinds — dispatch still succeeds | Log warning "using static fallback" |
| Unified ON, deprecation ON, facebook_group without target_id | `target_id=""` or None | `ValueError("target_id required for action group_posts")` → caller maps to 422 at API layer | 422 |
| Deprecation ON without unified | `XACTIONS_USE_UNIFIED_DISPATCH=false`, `XACTIONS_LEGACY_TOOL_DEPRECATION=true` | Same as unified-OFF row — deprecation flag is a no-op | N/A |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:37-90` — `PLATFORM_TOOL_MAP`. The four legacy rows (`facebook_group`, `facebook_page`, `twitter_keyword`, `twitter_user`) keep their `args_builder` lambdas — they are the source of truth for flag-OFF arg semantics.
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:95-101` — `_facebook_group_url` / `_facebook_page_url`. Reused under deprecation flag to produce `args.url` for the unified envelope.
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:148-200` — `UniversalScrapeTargetMapper._unified_envelope`. Extend (or wrap) to handle multi-`target_kind` platforms and legacy-tool arg shapes when deprecation flag ON.
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:202-235` — `map()` sync path. Add deprecation-flag gate before the "mapping['tool'] != 'x_scrape' → return as-is" shortcut.
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:236-262` — `map_async()`. Mirror the same gate.
- `nowing_backend/app/proprietary/platforms/xactions/action_matrix.py:48-141` — `STATIC_FALLBACK_MATRIX`. Already contains `facebook.group_posts`, `facebook.page_posts`, `twitter.search_tweets`, `twitter.user_tweets` with `match.target_kind` — verify requiredArgs match what `_unified_envelope` produces, adjust if needed.
- `nowing_backend/app/proprietary/platforms/xactions/action_matrix.py:319-360` — `derive_platform_action`. Already resolves `facebook_group` → `("facebook","group_posts")` and `twitter_user` → `("twitter","user_tweets")` via `match.target_kind`. No signature change.
- `nowing_backend/app/config/entities.py:99-104` — add `XACTIONS_LEGACY_TOOL_DEPRECATION` env flag next to `XACTIONS_USE_UNIFIED_DISPATCH`; export in `__all__`.
- `nowing_backend/tests/unit/platforms/test_xactions_mapper.py:100-205` — existing flag-ON/OFF cases; extend with deprecation-flag matrix.
- `nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py` — add tests covering facebook/twitter entries in `STATIC_FALLBACK_MATRIX` and `derive_platform_action` for the four `platform_kind` values.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/config/entities.py` — add `XACTIONS_LEGACY_TOOL_DEPRECATION` env flag (default `false`, accepted truthy values matching `XACTIONS_USE_UNIFIED_DISPATCH`); add to `__all__`.
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` — introduce `_is_legacy_tool_deprecated()` helper (or inline `and` check). In `map()` and `map_async()`, replace the `if mapping["tool"] != "x_scrape": return legacy` shortcut with `if mapping["tool"] != "x_scrape" and not _is_legacy_tool_deprecated(): return legacy`. When the gate allows unified dispatch, route through `_unified_envelope` like the x_scrape rows.
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` — extend `_unified_envelope` (or add a sibling `_legacy_unified_envelope`) so the four legacy kinds produce canonical args: `facebook_group`/`facebook_page` set `args.url = _facebook_*_url(target_id)`; `twitter_keyword` sets `args.query = target_id`; `twitter_user` sets `args.username = target_id.lstrip('@')`. Honour the descriptor's `requiredArgs` name (`url`/`query`/`username`) rather than hard-coding.
- [x] `nowing_backend/app/proprietary/platforms/xactions/action_matrix.py` — audit `STATIC_FALLBACK_MATRIX.facebook` / `.twitter` entries; confirm `requiredArgs` line up with the arg names `_unified_envelope` will populate (`url`, `query`, `username`). Adjust `match.target_kind` or arg names if drift is found.
- [x] `nowing_backend/tests/unit/platforms/test_xactions_mapper.py` — add `TestLegacyToolDeprecation` class covering all I/O-matrix rows (flag matrix × 4 platform_kinds × URL/edge cases).
- [x] `nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py` — assert `derive_platform_action` maps `facebook_group`→`("facebook","group_posts")`, `facebook_page`→`("facebook","page_posts")`, `twitter_keyword`→`("twitter","search_tweets")`, `twitter_user`→`("twitter","user_tweets")` against `STATIC_FALLBACK_MATRIX` alone.

**Acceptance Criteria:**
- Given `XACTIONS_USE_UNIFIED_DISPATCH=false`, when `map()` is called for any of the four legacy `platform` values, then the return value is byte-identical to today's `PLATFORM_TOOL_MAP` output.
- Given `XACTIONS_USE_UNIFIED_DISPATCH=true` and `XACTIONS_LEGACY_TOOL_DEPRECATION=false`, when `map()` is called for `facebook_group`, then it still returns `("x_facebook_group_posts", ...)` — no behaviour change.
- Given both flags ON and a `facebook_group` target with `target_id="group123"`, when `map_async()` resolves, then it returns `("x_scrape", {platform:"facebook", action:"group_posts", args:{url:"https://www.facebook.com/groups/group123"}, context:{targetId,workspaceId}})`.
- Given both flags ON and a `twitter_user` target with `target_id="@elon"`, when `map_async()` resolves, then `args.username == "elon"` (`@` stripped).
- Given both flags ON and `x_actions_list` returns a partial catalog missing facebook/twitter, when `map_async()` resolves, then the static fallback supplies the descriptor and dispatch still succeeds.
- Given `XACTIONS_USE_UNIFIED_DISPATCH=false` but `XACTIONS_LEGACY_TOOL_DEPRECATION=true`, when `map()` is called for `facebook_group`, then the legacy tool is still used — deprecation flag alone never bypasses unified dispatch.

## Spec Change Log

## Design Notes

**Tại sao cần flag thứ hai thay vì chỉ dùng `XACTIONS_USE_UNIFIED_DISPATCH`:** 36.6a ship unified dispatch nhưng giữ legacy tools vì XActions REQ-X1 chưa confirm trên FB/Twitter. Bây giờ REQ-X1 confirmed nhưng việc flip toàn bộ 4 platform cùng lúc vẫn là 1 bước deploy-risk. Flag riêng cho phép ship code sớm, bật dần trên staging → prod, và rollback tức thì mà không cần redeploy (chỉ cần `XACTIONS_LEGACY_TOOL_DEPRECATION=false`).

**Tại sao không xoá `PLATFORM_TOOL_MAP` entries:** chúng vẫn là source of truth cho flag-OFF path — rollback phải byte-identical. Chỉ khi cả 2 flags ON ≥ 1 sprint mới có story dọn dẹp.

**Arg-name binding:** `_unified_envelope` hiện bind `target_id` vào `requiredArgs[0]` (single-arg). Với `facebook_*` cần URL-ify trước khi bind. Implement bằng cách nhét URL-ification vào `args_builder`-equivalent: một per-`platform_kind` hook `_build_unified_args(platform_kind, target_id, descriptor)` trả `dict`. Giữ `_unified_envelope` signature nhưng route qua hook đó.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/platforms/test_xactions_mapper.py -q` — expected: all pass (flag OFF, flag ON+deprecation OFF, flag ON+deprecation ON)
- `cd nowing_backend && uv run pytest tests/unit/platforms/test_canonical_action_matrix.py -q` — expected: all pass (incl. new facebook/twitter derive tests)
- `cd nowing_backend && uv run pytest tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py -q` — expected: all pass (no regression)
- `cd nowing_backend && uv run pytest tests/unit/routes/test_social_routes.py -q` — expected: all pass (platform validation unchanged)

**Manual checks:**
- `XACTIONS_USE_UNIFIED_DISPATCH=false XACTIONS_LEGACY_TOOL_DEPRECATION=true uv run python -c "from app.proprietary.platforms.xactions.adapter_v2 import UniversalScrapeTargetMapper as M; t=type('T',(),{'platform':'facebook_group','target_id':'abc','id':1,'workspace_id':2})(); print(M.map(t))"` — expected: `('x_facebook_group_posts', {'url': 'https://www.facebook.com/groups/abc', 'limit': 20})` (deprecation flag no-op).
- `XACTIONS_USE_UNIFIED_DISPATCH=true XACTIONS_LEGACY_TOOL_DEPRECATION=true uv run python -c "..."` — expected: `('x_scrape', {'platform':'facebook','action':'group_posts','args':{'url':'https://www.facebook.com/groups/abc'},'context':{...}})`.

## Suggested Review Order

**Deprecation gate & dispatch routing**

- Second flag — deprecation only fires when unified dispatch is also ON.
  [`entities.py:108`](../../nowing_backend/app/config/entities.py#L108)

- Sync path — legacy shortcut preserved when `_is_legacy_tool_deprecated()` is False.
  [`adapter_v2.py:297`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L297)

- Async path — same gate mirrored so `map_async()` never diverges from `map()`.
  [`adapter_v2.py:333`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L333)

- `_is_legacy_tool_deprecated` — the two-flag AND gate; deprecation alone is a no-op.
  [`adapter_v2.py:140`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L140)

**Arg-shape canonicalization**

- `_build_unified_args` — descriptor `requiredArgs[0]` wins; URL-ify only when arg is `url`; `twitter_user` strips `@`; `limit=20` preserved for the four legacy kinds.
  [`adapter_v2.py:153`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L153)

- `_unified_envelope` — whitespace/None `target_id` rejected before dispatch.
  [`adapter_v2.py:240`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L240)

**Static fallback (read-only audit)**

- Facebook + twitter descriptors already in `STATIC_FALLBACK_MATRIX` — confirm `requiredArgs` match.
  [`action_matrix.py:115`](../../nowing_backend/app/proprietary/platforms/xactions/action_matrix.py#L115)

**Tests**

- `TestLegacyToolDeprecation` — flag-matrix + arg-shape + edge cases.
  [`test_xactions_mapper.py:236`](../../nowing_backend/tests/unit/platforms/test_xactions_mapper.py#L236)

- Derive-from-static coverage for all four `platform_kind` values.
  [`test_canonical_action_matrix.py:129`](../../nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py#L129)
