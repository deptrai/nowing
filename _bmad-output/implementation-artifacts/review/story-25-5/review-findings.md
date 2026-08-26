# Story 25.5 — Code Review Findings (bmad-code-review)

Review run: 2026-08-26
Scope: backend code chunk (`nowing_backend/app/**`, `alembic`, `pyproject.toml`, `uv.lock`) vs story spec.
Layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

## Status

**CHANGES REQUESTED.** Multiple high-severity findings break AC-1, AC-2, AC-3, AC-5, AC-6, AC-7.

---

## decision-needed

1. **Spec contradiction: AC-1 example regex uses lookbehind/lookahead, but `google-re2` rejects lookaround.**
   - The AC-1 payload example `(?:(?<=\D)|^)...(?=\D)|$)` contains `(?<=...)` and `(?=...)`. `re2.compile` does not support these, so the example itself fails validation.
   - Decide: (a) update the AC-1 example to a re2-compatible pattern, or (b) add an explicit fallback path for lookaround patterns (e.g., pre-validate with `re` syntax only).

2. **`RuleSchema` uses `ConfigDict(extra="forbid")` while the spec also says "Để lại room cho extension (`headers`, `user_agent`, `cookies`)."**
   - Decide: (a) keep `extra="forbid"` and require a new story to add fields, or (b) relax to `extra="ignore"` and document the extension plan.

---

## patch (high)

3. **Mutating service functions do not commit the transaction.**
   - `scraper_rules_service.create_rule`, `activate_rule`, `delete_rule`, `trip_circuit_breaker`, `reset_circuit_breaker` call `await session.flush()` but never `await session.commit()`. `get_async_session()` does not auto-commit on close, so writes are rolled back after the route returns.
   - Fix: add `await session.commit()` at the end of each write path.

4. **In-place `rule_schema` JSONB mutation is not persisted by SQLAlchemy.**
   - `ScraperRule.rule_schema` uses plain `JSONB` (no `MutableDict.as_mutable`). `trip`/`reset` do `rule.rule_schema["circuit_breaker"]["tripped"] = ...` without `flag_modified(rule, "rule_schema")`.
   - Fix: reassign a copy (`rule.rule_schema = {**rule.rule_schema}`) or call `flag_modified(rule, "rule_schema")` before `commit()`.

5. **Dynamic rule is never loaded into the worker: cache is never populated and there is no DB fallback.**
   - `scraper_rule_cache.set()` has no production caller. `get_batdongsan_rule()` only calls `scraper_rule_cache.get()` and falls back to `_DEFAULT_RULE`.
   - `scraper_rules_service.get_active_rule()` is not used by the scraper.
   - Fix: warm the cache in `create_rule`/`activate_rule`; make `get_batdongsan_rule()` load from DB on cache miss.

6. **Redis Pub/Sub subscriber is never started in app lifespan or Celery worker.**
   - `start_rule_subscriber` / `start_background_subscriber` are defined but never called. Workers never invalidate their in-memory cache.
   - Fix: call `start_background_subscriber` in `app.app:lifespan` and in Celery `@worker_process_init`, or document a simpler per-process reload strategy.

7. **ReDoS validation runs synchronously on the async event loop.**
   - `scraper_rules_service.create_rule` calls `validate_regexes()` directly. `validate_regexes_async()` exists but is not used.
   - Fix: call `validate_regexes_async()` in `create_rule` (and `validate_css_selectors_async` if the loop may block).

8. **ReDoS fallback uses an unsafe `ThreadPoolExecutor` that cannot kill a hung regex thread.**
   - `_benchmark_with_re()` uses `ThreadPoolExecutor(max_workers=1)` with `future.result(timeout=0.05)`, then `shutdown(wait=False)`. The timed-out worker continues.
   - Fix: use `ProcessPoolExecutor` with a `terminate()` on timeout, or reject the fallback entirely unless `re2` is installed.

9. **ReDoS benchmark does not use the required 1 KB / 10 KB / 100 KB inputs or fixed dangerous-pattern test set.**
   - `_build_test_inputs()` generates lengths `256, 2560, 25600`. The fixed patterns `(a+)+$`, `(a|aa)+$`, `(a+)+b` with `'a' * 30 + '!'`, etc., are not run.
   - Fix: match the AC-3 input sizes and add the fixed pattern test suite.

10. **`batdongsan/scraper.py` main scrape loop still uses hardcoded delays/retries, not the dynamic rule.**
    - `scraper.py` still references `_MAX_RETRIES`, `_page_delay()`, `config.BATDONGSAN_PAGE_DELAY_S`. The dynamic rule is only wired into `fetch_listings` / `fetch_web_listings`.
    - Fix: integrate `get_batdongsan_rule()` into the main retry/delay logic in `scraper.py`.

11. **Circuit breaker trip/reset does not integrate with `PlatformCircuitBreaker` or the worker.**
    - `scraper_rules_service` writes `scraper_rule:{platform}:circuit_breaker` JSON. `PlatformCircuitBreaker` uses `circuit_breaker:scraper:{platform} = "OPEN"` and `circuit_breaker:failures:{platform}`.
    - Neither `scraper.py` nor `fetch.py` checks the rule `circuit_breaker.tripped` flag.
    - Fix: align keys and values with `PlatformCircuitBreaker`, reset both `state_key` and `failure_counter_key`, and make `scraper.py` check `is_available()` / `tripped`.

12. **Validation error responses mix three shapes.**
    - `InvalidSelectorError` → string detail; `ReDoSTimeoutError/InvalidRegexError` → `{"code", "message"}`; Pydantic `ValidationError` → `exc.errors()`.
    - AC-2 asks for a single format (`{"code": ..., "detail": ...}` or FastAPI default list).
    - Fix: unify to `{"code": "INVALID_CSS_SELECTOR"|"REDOS_TIMEOUT"|"VALIDATION_ERROR", "detail": ...}`.

13. **`PATCH /{platform}/{version}` only supports activation, not deactivation.**
    - The route raises 422 when `payload.is_active is False`. The spec says PATCH should be able to adjust `is_active` (activate/deactivate).
    - Fix: add `deactivate_rule()` and allow `PATCH is_active=false`.

14. **First rule creation does not publish `scraper_config_updated`.**
    - `create_rule` calls `publish_rule_update(redis=None, ...)` for the first (auto-activated) version, which returns early and broadcasts nothing.
    - Fix: fetch a Redis client and publish, or at least warn and set the in-process cache.

15. **Pub/Sub payload shape deviates from the spec.**
    - `publish_rule_update` sends `{"platform", "version", "is_active", "circuit_breaker_tripped"}`. AC-5 expects `{"platform", "version", "is_active", "updated_at"}`.
    - Fix: include `updated_at` and remove `circuit_breaker_tripped` from the pubsub payload (or extend the spec).

---

## patch (medium)

16. **Audit event action names and `diff_payload` keys deviate from the spec.**
    - Actions use `scraper_rule.create` (with key `"schema"` instead of `rule_schema`), `scraper_rule.circuit_breaker.trip` / `scraper_rule.circuit_breaker.reset` (spec expects `scraper_rule.trip` / `scraper_rule.reset`).
    - Fix: align names/keys with AC-4.

17. **`lxml` is imported but not declared as a direct dependency.**
    - `scraper_rule_validator.py` uses `from lxml import etree`; `pyproject.toml` adds `cssselect` but not `lxml`.
    - Fix: add `lxml>=...` to `pyproject.toml`.

18. **Path parameters `platform` and `version` are not validated.**
    - `version` can be negative, raising `ValueError` that becomes 500. `platform` has no length/regex validation in the route.
    - Fix: add `Path(..., ge=1, max_length=64)` to route params.

19. **`trip_duration_seconds` can be `0`, causing Redis `SET ... EX 0` error.**
    - `RuleCircuitBreaker.trip_duration_seconds` uses `ge=0`. Redis `EX 0` is invalid.
    - Fix: clamp `ex=max(1, ...)` or change schema to `ge=1`.

20. **`tripped_at` stored in Redis uses `perf_counter()` instead of wall-clock time.**
    - `_now()` returns `time.perf_counter()`, which is process-relative and not comparable across workers.
    - Fix: use `time.time()`.

21. **Redis connection errors in `trip`/`reset` are not caught.**
    - `redis.set` / `redis.delete` can raise `ConnectionError` / `TimeoutError`, producing 500.
    - Fix: wrap in try/except and return a structured 503 or continue with DB-only state.

22. **`fetch_listings`/`fetch_web_listings` do not check `retries.statuses` and do not honor `circuit_breaker.tripped`.**
    - Only `BatdongsanRateLimitedError` triggers retry; `retries.statuses` list is ignored. Tripped breaker is not checked before outbound requests.
    - Fix: match the status list and stop requests when tripped.

23. **`fetch_listings` adds `delays.request_ms` before every attempt, not per request.**
    - `await asyncio.sleep(request_delay_s)` is inside the `for attempt` loop, multiplying pacing.
    - Fix: sleep once before the first attempt or between retries only.

24. **Version creation/activation lacks `SELECT ... FOR UPDATE` locking.**
    - Concurrent `POST` can compute the same `new_version` and collide; concurrent `PATCH` can transiently produce two active rows.
    - Fix: lock the platform rows during create/activate.

25. **`refresh` endpoint does not invalidate the local in-process cache.**
    - `POST /refresh` publishes but does not call `scraper_rule_cache.invalidate()`.
    - Fix: invalidate the local cache immediately after publish.

26. **No error-rate metric / auto-rollback endpoint for INV-25.6.**
    - AC-5 requires the metric to be calculated and displayed, even if auto-rollback is deferred.
    - Fix: record per-platform error/success rates and expose an admin endpoint or log/alert as a minimum.

---

## Dismissed / low

- `ScraperRuleListItem.updated_by` returns UUID rather than display name — API contract currently uses `UUID | None`; may be a UI/UX polish item, not an AC violation.
