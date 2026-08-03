# Story 8.7 — Edge Case Hunter Review

**Scope:** `app/services/memory/extract_budget.py`, `app/services/memory/extraction.py`, `app/tasks/chat/streaming/flows/shared/assistant_finalize.py`, `app/config/__init__.py`, `app/db.py`, `app/capabilities/core/access/rate_limit.py`, `.env.example`, and the two test files.

**Summary:** The new cost-control gate is defensively written and the unit/integration tests cover many obvious boundaries (negative caps, detached ORM, Redis fallback, `>=` thresholds, fail-closed errors). However, several unhandled edges remain around **rate-window semantics**, **budget/rate races under concurrency**, **Redis/in-memory timeout and isolation**, **schema/index support for the budget aggregate**, and **attribution/wallet attribution**. These are documented below with file/function/line references, scenarios, and suggested fixes or tests.

---

## Findings

### 1. Redis rate-limit TTL is refreshed on every increment, producing a sliding window instead of the documented fixed window

- **File / function / line:**
  - `nowing_backend/app/services/memory/extract_budget.py`, `_record_extraction_sync`, lines 229–244 (specifically `client.expire(key, window)` at line 238).
  - `nowing_backend/.env.example`, line 697 ("Redis fixed-window counter").
- **Edge case scenario:**
  - `MEMORY_AUTO_EXTRACT_RATE_MAX=3`, `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS=3600`.
  - Workspace extracts at `t=0`, then again at `t=3599`.
  - The second `INCR` calls `EXPIRE 3600` again, resetting the key's TTL so it now expires at `t=7199` instead of `t=3600`.
  - A third extraction at `t=3601` still sees a count of `2` (or is still blocked at `3` if `max=2`), whereas a true fixed window would have reset at `t=3600`.
- **Why current code does not handle it:**
  - `client.expire(key, window)` is unconditional. `EXPIRE` always restarts the TTL from the last increment, so the window is sliding, not fixed.
  - `.env.example` and the module docstring call it a "fixed-window counter".
  - The existing test `test_record_extraction_increments_and_refreshes_ttl` (8.7-UNIT-013) actually encodes the sliding behavior as correct, so the mismatch is embedded in tests too.
- **Suggested fix or test:**
  - Use a Lua script or `INCR` followed by conditional `EXPIRE` only when the new count is `1` (or when `TTL == -1` to recover a lost `EXPIRE`), so the first increment sets the fixed window boundary.
  - Add a test that asserts fixed-window semantics: `record_extraction` twice with the second call at `window - 1s`, then `await asyncio.sleep(2)` and assert the counter has reset (or its TTL is `<= window - elapsed`).
  - Alternatively, update `.env.example` and module docstring to say "sliding window" if that is the intended design.

---

### 2. Budget cap is a soft, read-only limit that a single extraction (or concurrent extractions) can exceed

- **File / function / line:**
  - `nowing_backend/app/services/memory/extract_budget.py`, `_period_spend_micros` lines 182–194; `_check_budget` lines 265–304.
  - `nowing_backend/app/services/memory/extraction.py`, `extract_from_turn` lines 219, 254–264, 271.
- **Edge case scenario:**
  - `MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000`, current window spend is `9_999`.
  - One extraction that costs `200` micros is allowed because `9_999 < 10_000`, but the resulting total is `10_199`, exceeding the cap.
  - Two Celery workers for the same workspace may both read `9_999`, both call the LLM, and both record token usage, pushing the workspace well past the cap.
- **Why current code does not handle it:**
  - `_check_budget` performs a `SELECT SUM(cost_micros)` of already-committed rows and compares it to the cap.
  - The current extraction's cost is not known until after the LLM, and `record_token_usage` is added to the same session and committed only at line 271.
  - There is no reservation, compare-and-set, or row-level lock on a per-workspace budget counter, so the pre-check sum is stale the moment it returns.
- **Suggested fix or test:**
  - **Option A (document):** state clearly in `.env.example` and module docstring that `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` is a "stop when observed spend reaches the cap" soft limit, not a hard ceiling.
  - **Option B (harder):** implement an atomic budget reservation (e.g., a `memory_extract_budget_spent` counter per workspace or a Redis `DECR`-style ledger). Reserve an upper-bound cost before the LLM, then credit back the unspent portion after `record_token_usage`.
  - Add tests: `test_extract_budget_overshoot_by_current_extraction` and a concurrency test with two `extract_from_turn` calls running in parallel against the same workspace and cap.

---

### 3. Rate-limit `GET`-then-`INCR` is not atomic; concurrent extractions can overshoot the limit

- **File / function / line:**
  - `nowing_backend/app/services/memory/extract_budget.py`, `_rate_count_sync` lines 197–208; `_record_extraction_sync` lines 229–244; `record_extraction` lines 247–262.
  - `nowing_backend/app/services/memory/extraction.py`, `extract_from_turn` line 219.
- **Edge case scenario:**
  - `MEMORY_AUTO_EXTRACT_RATE_MAX=1`.
  - Two `extract_from_turn` tasks for the same workspace start simultaneously.
  - Both call `_rate_count` and read `0`; both proceed to the LLM; both then call `record_extraction`, leaving the counter at `2`.
- **Why current code does not handle it:**
  - The gate reads the current count with `GET` (or in-memory list), then increments with `INCR` only after the LLM succeeds.
  - The increment is not part of the decision; the read and increment are separate, non-atomic operations.
  - Counting after the LLM is intentional (to avoid burning slots on transient LLM errors), but it opens the window to this race.
- **Suggested fix or test:**
  - Implement the decision as an atomic `INCR`-and-check (Lua or Redis pipeline) that returns the new count and only allows the extraction if `count <= max`. If the extraction fails later, `DECR` the counter to release the slot.
  - Alternatively, accept the race and explicitly document the rate limit as a "best-effort abuse guard".
  - Add a concurrent test: launch two `extract_from_turn` coroutines in parallel with `rate_max=1` and assert only one LLM call occurs and only one `record_extraction` increment is recorded.

---

### 4. `record_extraction` is called before `session.commit()`; DB failures after counting consume rate slots

- **File / function / line:**
  - `nowing_backend/app/services/memory/extraction.py`, `extract_from_turn` line 219 (`await record_extraction(workspace.id)`) and line 271 (`await self.session.commit()`).
  - `nowing_backend/app/services/memory/extract_budget.py`, `_record_extraction_sync` lines 229–244.
- **Edge case scenario:**
  - The LLM succeeds and `record_extraction` increments Redis to `1`.
  - The `create_memory` loop or `session.commit()` then fails (e.g., DB constraint error, deadlock, network blip).
  - Celery retries the task. The gate now sees a rate count of `1` (or higher if previous retries also incremented), and the retry either is blocked or consumes another slot for a turn that was never durable.
- **Why current code does not handle it:**
  - Redis is not part of the SQLAlchemy transaction. Once `record_extraction` runs, the counter cannot be rolled back if the DB transaction fails.
  - `record_extraction` is placed after the LLM but before `session.commit`, so any post-LLM failure burns a rate slot.
- **Suggested fix or test:**
  - Move `await record_extraction(workspace.id)` to **after** `await self.session.commit()` so the rate counter only increments for a durable, committed extraction. If the commit fails, no slot is consumed.
  - Place it after the idempotency guard is established, so redelivery does not re-increment.
  - Add a test that simulates `session.commit()` raising after a successful `record_extraction` and asserts the rate counter is unchanged on retry.

---

### 5. Redis client has no socket connect/operation timeout

- **File / function / line:**
  - `nowing_backend/app/services/memory/extract_budget.py`, `_redis_client` lines 102–115 (`redis.from_url(config.REDIS_APP_URL, decode_responses=True)` at line 114).
  - Also `nowing_backend/app/capabilities/core/access/rate_limit.py`, `_redis_client` lines 27–33 (same pattern, not strictly 8.7 but relevant).
- **Edge case scenario:**
  - `REDIS_APP_URL` points to a blackholed host, or Redis is behind a firewall that drops packets.
  - `redis-py` attempts `GET`/`INCR` and waits for the OS TCP timeout (often ~75 seconds by default).
  - Although the call is offloaded to a thread via `asyncio.to_thread`, the Celery task or `assistant_finalize` finalization still waits for that timeout before the in-memory fallback can run.
- **Why current code does not handle it:**
  - `redis.from_url` is called with only `decode_responses=True`; no `socket_connect_timeout` or `socket_timeout` is set.
  - The code relies on the thread offload to avoid blocking the event loop, but the thread itself has no upper bound on how long it waits for a network timeout.
- **Suggested fix or test:**
  - Pass `socket_connect_timeout=2` and `socket_timeout=2` (or a configurable value) to `redis.from_url`. If both limits are exceeded, fall back to the in-memory counter quickly.
  - Add a test with a blackholed/unreachable `REDIS_APP_URL` (e.g., `redis://240.0.0.1:6379/0`) and assert the gate returns/falls back within a few seconds, not the OS TCP timeout.

---

### 6. In-memory rate fallback is per-process, not per-deployment

- **File / function / line:**
  - `nowing_backend/app/services/memory/extract_budget.py`, `_memory_hits` line 98, `_memory_lock` line 99, `_memory_count` lines 122–128, `_memory_incr` lines 131–138.
- **Edge case scenario:**
  - Redis becomes unavailable in a multi-process deployment (e.g., 4 uvicorn workers or 8 Celery workers).
  - Each process maintains its own `_memory_hits` dict.
  - A workspace can hit `rate_max` on each worker before the in-memory fallback blocks it, effectively multiplying the allowed throughput by the number of processes.
- **Why current code does not handle it:**
  - The fallback stores window timestamps in a module-level `defaultdict(list)` guarded by `threading.Lock`, which is local to a single OS process.
  - The `.env.example` comment correctly calls it a "per-worker in-memory fallback", but there is no cross-process fallback and no metric/observability that the global limit has been relaxed.
- **Suggested fix or test:**
  - Document explicitly that the rate limit is per-process when Redis is unavailable, and add a log/metric field (`fallback=per_process`).
  - If a stricter cross-process fallback is required, use a shared backend such as a lightweight SQLite/DuckDB file or a DB-backed counter table.
  - Add a multi-process test (or at least a test that forks two processes) verifying the per-process behavior and the documented limitation.

---

### 7. Budget aggregate query can scan a hot `token_usage` table because no covering/partial index exists

- **File / function / line:**
  - `nowing_backend/app/services/memory/extract_budget.py`, `_period_spend_micros` lines 186–193.
  - `nowing_backend/app/db.py`, `TokenUsage` model lines 1125–1190.
  - `nowing_backend/alembic/versions/125_add_token_usage_table.py` and `170_rename_searchspace_to_workspace.py` (single-column `workspace_id` and `usage_type` indexes; no `created_at` or composite index).
- **Edge case scenario:**
  - A workspace has a large `token_usage` history.
  - The budget gate executes `SELECT COALESCE(SUM(cost_micros), 0) FROM token_usage WHERE workspace_id = ? AND usage_type = 'memory_create' AND created_at >= ?`.
  - PostgreSQL must scan the `workspace_id` or `usage_type` index and then apply the `created_at` and `usage_type` filters, which can become slow enough to time out or stall the streaming `assistant_finalize` path.
- **Why current code does not handle it:**
  - The query filters on three columns but only single-column indexes exist for `workspace_id` and `usage_type`.
  - `created_at` is unindexed for this query, and there is no partial index for `usage_type = 'memory_create'`.
- **Suggested fix or test:**
  - Add a migration creating a partial composite index such as:
    ```sql
    CREATE INDEX ix_token_usage_memory_create_workspace_created
    ON token_usage (workspace_id, created_at)
    WHERE usage_type = 'memory_create';
    ```
  - Add an `EXPLAIN` test (or a load test) that asserts the budget query uses an index scan and not a sequential/heap scan with a large `token_usage` table.

---

### 8. Wallet pre-check uses the turn author, but `.env.example` describes it as the workspace owner's wallet

- **File / function / line:**
  - `nowing_backend/app/services/memory/extraction.py`, `extract_from_turn` lines 159–174 (`created_by_id = user_message.author_id`, `attributed_user_id=created_by_id`).
  - `nowing_backend/app/services/memory/extract_budget.py`, `_wallet_spendable_micros` lines 141–161; `check_extract_allowed` line 347.
  - `nowing_backend/.env.example`, lines 680–682 ("Minimum spendable balance ... the workspace owner must have").
- **Edge case scenario:**
  - A workspace has a funded owner and a member with a zero-balance wallet.
  - The member sends a message.
  - The extraction gate checks the **member's** wallet, sees `spendable < min_reserve`, and skips with `insufficient_wallet`, even though the `.env` docs describe the gate as protecting the **owner's** ability to pay.
- **Why current code does not handle it:**
  - `extraction.py` resolves `created_by_id` from `user_message.author_id` and passes it to `check_extract_allowed`.
  - The gate never consults `workspace.user_id` (the owner) for the wallet pre-check.
  - This creates an ambiguity between per-author attribution and the documented per-owner eligibility check.
- **Suggested fix or test:**
  - Decide the intended product semantics:
    - If extraction should be gated by the **workspace owner's** wallet, pass `workspace.user_id` to the wallet check while still recording `TokenUsage` with the turn author.
    - If extraction should be gated by the **turn author's** wallet, update `.env.example` and module docstring to say "turn author" instead of "owner".
  - Add an integration test for a shared workspace where the owner is funded but the member is not, and assert the resulting `reason` and whether extraction is allowed according to the chosen design.

---

### 9. Unregistered/unknown extraction model cost is recorded as `0`, causing the budget cap to under-count spend

- **File / function / line:**
  - `nowing_backend/app/services/token_tracking_service.py`, `_extract_cost_usd` lines 276–349; `async_log_success_event` line 434 (`cost_micros = round(cost_usd * 1_000_000) if cost_usd > 0 else 0`).
  - `nowing_backend/app/services/memory/extraction.py`, `record_token_usage` lines 254–264.
  - `nowing_backend/app/services/memory/extract_budget.py`, `_period_spend_micros` lines 186–193.
- **Edge case scenario:**
  - A workspace uses a model whose pricing is not registered in LiteLLM/Nowing.
  - `_extract_cost_usd` cannot resolve a cost and returns `0.0`, so `record_token_usage` writes `cost_micros=0`.
  - The budget `SUM` therefore does not include the actual extraction cost, and the workspace can exceed its configured cap without the gate noticing.
- **Why current code does not handle it:**
  - The budget cap relies on `TokenUsage.cost_micros` being accurate.
  - When pricing is missing, the token tracker fails open and records `0` with only a log warning.
  - The extraction gate has no notion of estimated or default cost.
- **Suggested fix or test:**
  - For `usage_type='memory_create'`, treat an unresolved cost as a warning/error condition. Either:
    - Fail the extraction closed when `cost_usd` cannot be resolved for a paid model, or
    - Record a conservative default/estimated cost (e.g., `QUOTA_MAX_RESERVE_MICROS` or a `MEMORY_AUTO_EXTRACT_DEFAULT_COST_MICROS` config) so the budget remains meaningful.
  - Add a test with a fake LLM whose pricing is unregistered and a budget cap, asserting either that the extraction is skipped or that the budget is charged a non-zero fallback cost.

---

## Edge cases that are already well handled

The following were explicitly checked and are covered by the implementation or tests, so they are **not** reported as findings:

- **Detached/expired ORM `Workspace`:** `check_extract_allowed` and `check_workspace_gates` wrap `workspace.id` in `try/except` and fail closed / fall open appropriately (lines 347–360 and 431–444). Tested in 8.7-UNIT-021/026.
- **Negative `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` / `MEMORY_AUTO_EXTRACT_RATE_MAX`:** Both short-circuit via `<= 0`, treating negative values as disabled. Tested in 8.7-UNIT-030.
- **`rate_max=1` and `rate > max` boundaries:** `>=` is used correctly and tested in 8.7-UNIT-031 and 8.7-UNIT-032.
- **Redis unavailable:** `_rate_count_sync` and `_record_extraction_sync` catch `Exception` and fall back to the in-memory window. Tested in 8.7-UNIT-015.
- **Anonymous/unbilled turn:** `attributed_user_id is None` is checked first and returns `anonymous_unbilled`. Tested in 8.7-UNIT-016 and 8.7-INT-009.
- **Missing user for wallet check:** `_wallet_spendable_micros` catches `ValueError` and returns `0`, failing closed. Tested in 8.7-UNIT-004.
- **Fail-closed on wallet/budget/rate seam errors:** `check_extract_allowed` returns `insufficient_wallet`, `budget_exceeded`, or `rate_limited` when a seam raises. Tested in 8.7-UNIT-018/019/033.
- **Enqueue-side `check_workspace_gates` never fails closed:** It falls through to `allowed=True` on any error. Tested in 8.7-UNIT-025.
- **`record_extraction` is a no-op when rate limit is disabled:** Guarded by `if config.MEMORY_AUTO_EXTRACT_RATE_MAX <= 0`. Tested in 8.7-UNIT-014.
- **`record_extraction` does not increment on LLM transient failures:** It is placed after `invoke_extraction_llm`. Tested in 8.7-INT-007.
- **Config parsing of `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW`:** `_env_choice` normalizes unknown values to `day` with a warning. Tested in 8.7-UNIT-008.
- **`MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` and `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS` clamped:** `max(1, ...)` prevents `0`/negative from disabling the wallet gate or breaking Redis `EXPIRE`.

---

## Recommendations

1. **Prioritize findings 1, 2, and 3** (rate-window semantics and races). They directly affect the correctness of the two cost-control mechanisms.
2. **Add a composite/partial index for `_period_spend_micros`** before the feature is enabled in production; otherwise the budget cap becomes an accidental DoS vector on the `token_usage` table.
3. **Resolve the attribution ambiguity** in finding 8 and document the decision consistently across code, `.env.example`, and tests.
4. **Add socket timeouts** to the Redis client before this code reaches a multi-tenant deployment.
