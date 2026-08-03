# Blind Hunter Review — Story 8.7 diff

## Summary

Reviewed the patch at `8-7-review-diff.patch` with no other project context. The Story 8.7 cost-control gate itself is well-structured in isolation — the ordering is right, the service-side path is fail-closed, the enqueue-side path is principal-free, and the tests are admirably hermetic. However, the diff also touches the global model catalog and introduces several concurrency, observability, and documentation contradictions. From a blind perspective, the most dangerous items are the non-atomic budget/rate checks, the stale global-catalog update, and the false `memory_extract_skip` logs on the enqueue fast-path.

---

## Findings

### 1. Fast-path gate failures emit `memory_extract_skip` while still enqueuing

- **File/function/line:** `nowing_backend/app/services/memory/extract_budget.py`, `_check_budget()` (patch lines 561–588) and `_check_rate()` (patch lines 603–628); called from `check_workspace_gates()` (patch lines 727–756); invoked in `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`, `finalize_assistant_message()` (patch lines 1144–1152).
- **Why it is a problem:** On the enqueue-side fast path `check_workspace_gates` calls `_check_budget` and `_check_rate` with `fail_closed=False`. If either seam raises, the code logs `memory_extract_skip reason=budget_exceeded` (or `rate_limited`) but then returns `None`. `check_workspace_gates` therefore returns `allowed=True` and `assistant_finalize` enqueues the extraction anyway. The log stream says the turn was skipped; the system enqueues it. This contradicts the AC-8 “single structured skip line” contract and the module’s own claim that “any uncertainty resolves to ‘enqueue and let `check_extract_allowed` decide’.”
- **Evidence from the diff:** In `_check_budget` the `except Exception` branch (lines 577–588) is `logger.warning("memory_extract_skip reason=%s ...", REASON_BUDGET_EXCEEDED, ...)` followed by `if fail_closed: ... return None` when `fail_closed` is `False`. `check_workspace_gates` passes `stage="enqueue", fail_closed=False` at lines 744–749. `test_workspace_gates_never_fail_closed` and `test_finalize_enqueues_when_the_precheck_itself_errors` assert “allow/enqueue” but do not assert that no `memory_extract_skip` line was emitted.

---

### 2. Budget and rate caps are not atomic — concurrent turns can overspend / overshoot

- **File/function/line:** `nowing_backend/app/services/memory/extract_budget.py`, `_period_spend_micros()` (patch lines 478–490), `_check_budget()` (561–600), `_check_rate()` (603–640), `_record_extraction_sync()` (525–540); and `nowing_backend/app/services/memory/extraction.py`, `extract_from_turn()` (patch lines 974–1052).
- **Why it is a problem:** The gate reads the current spend or count before the LLM call, then writes the new cost/count only after the call succeeds. There is no `SELECT FOR UPDATE`, serializable transaction, or atomic `INCR`/check to make the read-check-write atomic. Multiple concurrent Celery workers (or even concurrent turns inside the same worker) can pass the gate with the same spend/count and then all record, pushing the workspace past `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` or `MEMORY_AUTO_EXTRACT_RATE_MAX`. That is a cost-bleed and a rate-limit bypass under load.
- **Evidence from the diff:** `extract_from_turn` calls `await check_extract_allowed(...)` (line 974), then `await invoke_extraction_llm(...)` (line 1055), then `await record_extraction(...)` (line 1052), then persists memories and `record_token_usage` (line 1080). `_check_rate` reads with `client.get(key)` (line 497) while `_record_extraction_sync` increments with `client.incr(key)` (line 530) and `client.expire(...)` (line 534) as separate commands. The `.env.example` comment (line 39) says the budget cap is one of “the only bounds that actually apply to extraction spend,” but the diff provides no synchronization to make that bound hard.

---

### 3. Global model catalog refresh may no longer update the in-memory `config`

- **File/function/line:** `nowing_backend/app/config/__init__.py`, `refresh_global_model_catalog()` (patch lines 140–183) and `initialize_openrouter_integration()` (patch lines 118–125).
- **Why it is a problem:** The old implementation did `config.GLOBAL_CONNECTIONS = connections; config.GLOBAL_MODELS = models` after computing the catalog. The new async version calls `connections, models = await _service_refresh(session)` and simply returns the tuple. The diff does not show any assignment back into `config`. `LLMRouterService.rebuild` (lines 172–178) then reads `config.GLOBAL_LLM_CONFIGS` and `config.ROUTER_SETTINGS`, which are also not refreshed in the visible diff. Unless the unshown `app.services.global_model_catalog` service mutates `config` as a side effect, the “rebuild the in-memory global catalog, including DB-managed rows” function may not actually update the in-memory catalog used by the rest of the app. Additionally, `initialize_openrouter_integration` replaces the startup refresh with `pass`, so no visible caller loads the catalog at startup.
- **Evidence from the diff:** Removed lines 133–136 show the previous `config.GLOBAL_CONNECTIONS` / `config.GLOBAL_MODELS` assignments. New code at line 157 only does `connections, models = await _service_refresh(session)` and `return connections, models`; no `config.*` assignment appears in the hunk. `initialize_openrouter_integration` at lines 122–125 replaces `refresh_global_model_catalog()` with `pass` and a comment about an async lifespan that is not present in the diff.

---

### 4. Startup pricing registration may run before the DB-managed catalog is loaded

- **File/function/line:** `nowing_backend/app/config/__init__.py`, `initialize_pricing_registration()` (patch lines 186–197), `initialize_openrouter_integration()` (patch lines 118–125), and `refresh_global_model_catalog()` (patch lines 140–183).
- **Why it is a problem:** `initialize_pricing_registration` now calls `register_pricing_for_managed_global_models()` at synchronous startup. But `initialize_openrouter_integration` no longer loads the global model catalog, and the new catalog refresh is async and deferred. So the managed-model pricing call may see an empty or stale in-memory catalog at startup and never be re-run unless an admin triggers a rebuild with `rebuild_routers=True`.
- **Evidence from the diff:** `initialize_openrouter_integration` removes `refresh_global_model_catalog()` (lines 122–125). `initialize_pricing_registration` adds `register_pricing_for_managed_global_models()` at line 196. `refresh_global_model_catalog(rebuild_routers=True)` does call both pricing registration functions and `LLMRouterService.rebuild`, but no call site with `rebuild_routers=True` is visible in the diff.

---

### 5. Rate-limit Redis client has no connection / socket timeout

- **File/function/line:** `nowing_backend/app/services/memory/extract_budget.py`, `_redis_client()` (patch lines 398–411), `_rate_count()` (patch lines 507–522), and `_record_extraction_sync()` (patch lines 525–540).
- **Why it is a problem:** `_redis_client()` uses `redis.from_url(config.REDIS_APP_URL, decode_responses=True)` with no `socket_timeout`, `socket_connect_timeout`, or retry settings. Because `_rate_count` and `record_extraction` run the synchronous client inside `asyncio.to_thread`, a hung TCP connect to Redis will tie up a worker thread for the OS default timeout (potentially minutes) and stall the event loop. This is a denial-of-service / availability risk on the chat/celery worker path.
- **Evidence from the diff:** `_redis_client` at lines 408–410. `_rate_count` offloads `client.get` to a thread at line 522. The integration test file comment at lines 1297–1299 explicitly warns: “redis-py is built with no `socket_connect_timeout` … hang on a blackholed host instead of failing fast.”

---

### 6. Wallet pre-check is documented for the workspace owner but implemented for the turn author

- **File/function/line:** `nowing_backend/.env.example` (patch lines 42–45); `nowing_backend/app/services/memory/extract_budget.py` module docstring (patch lines 308–310) and `_wallet_spendable_micros()` docstring (patch line 438); `nowing_backend/app/services/memory/extraction.py`, `extract_from_turn()` (patch lines 964–989 and 1076–1089).
- **Why it is a problem:** The `.env.example` and the `extract_budget` docstrings repeatedly describe the wallet pre-check as being for the “workspace owner.” The code, however, uses `created_by_id = user_message.author_id` and passes that to `check_extract_allowed`; it also removed the `created_by_id or workspace.user_id` fallback for `record_token_usage` (line 1076 comment). This is consistent with AC-4 (anonymous turns must be skipped rather than silently attributed to the owner), but the operator-facing documentation is stale. In a multi-user workspace, a member with a low wallet will block extraction even if the workspace owner is fully funded.
- **Evidence from the diff:** `.env.example` line 42: “Minimum spendable balance … the workspace owner must have.” `extract_budget.py` line 308: “do not perform optional background work for an owner who cannot pay for their foreground work.” `extraction.py` lines 964–974 pass `attributed_user_id=created_by_id` and lines 1076–1084 explicitly remove the `workspace.user_id` fallback, using `created_by_id` for `record_token_usage`.

---

### 7. In-memory rate-limit fallback is per-process and unbounded

- **File/function/line:** `nowing_backend/app/services/memory/extract_budget.py`, `_memory_hits` (patch line 394), `_memory_count()` (patch lines 418–424), `_memory_incr()` (patch lines 427–434).
- **Why it is a problem:** The Redis fallback stores hits in a module-level `defaultdict(list)`. Entries are only pruned for the key currently being read; workspace keys that are never accessed again are never evicted. Also, the fallback is per-worker process, so when Redis is unavailable each worker keeps its own counter. The effective rate limit across workers becomes `rate_max × worker_count`, and the module state grows without bound for long-lived processes.
- **Evidence from the diff:** `_memory_hits` declared at line 394. `_memory_count` (lines 420–424) and `_memory_incr` (lines 430–434) filter and reassign only the accessed key. `.env.example` line 58 states the limit is backed by “a Redis fixed-window counter … with a per-worker in-memory fallback when Redis is unreachable.”

---

### 8. “Fixed-window” rate-limit terminology contradicts the sliding-window implementation

- **File/function/line:** `nowing_backend/.env.example` (patch line 58); `nowing_backend/app/services/memory/extract_budget.py`, `_record_extraction_sync()` (patch lines 525–540); `nowing_backend/tests/unit/memory/test_auto_extract_gate.py`, `test_record_extraction_increments_and_refreshes_ttl()` (patch lines 2581–2612).
- **Why it is a problem:** The `.env.example` calls the Redis counter a “fixed-window counter,” but `_record_extraction_sync` runs `INCR` followed by `EXPIRE key window` on *every* increment, refreshing the TTL from the last hit. The unit test explicitly asserts this TTL-refresh behavior. That creates a rolling / sliding window, not a counter that resets at fixed interval boundaries. This is a contradiction between operator-facing documentation and the code.
- **Evidence from the diff:** `_record_extraction_sync` lines 530–534. The unit test at lines 2605–2612 calls `record_extraction` twice and asserts `client.ttls[key] == window` after each, with the comment “TTL must be refreshed on every increment.”

---

## What the diff does well (from a blind perspective)

- Gate ordering is correct: `anonymous_unbilled` → `insufficient_wallet` → `budget_exceeded` → `rate_limited`, all before the LLM call.
- The service-side `check_extract_allowed` is fail-closed and contained; the enqueue-side `check_workspace_gates` is principal-free and fail-open, matching the AC-7 rationale.
- Defaults are safe: `MEMORY_AUTO_EXTRACT_BUDGET_MICROS=0` and `MEMORY_AUTO_EXTRACT_RATE_MAX=0` mean the shipped configuration adds no gating.
- `record_extraction` is called *after* the LLM succeeds, so transient LLM failures do not inflate the rate counter.
- The test suite is hermetic: autouse fixtures pin config, stub Redis, and assert single-machine-parseable skip lines.
