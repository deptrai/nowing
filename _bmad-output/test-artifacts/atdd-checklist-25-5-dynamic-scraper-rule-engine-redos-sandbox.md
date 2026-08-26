---
story_key: 25-5-dynamic-scraper-rule-engine-redos-sandbox
skill: bmad-nowing-test-first-atdd
phase: 4.4
---

# ATDD Checklist — 25-5: Dynamic Scraper Rule Engine & ReDoS Sandbox

> Titles only — **NO assertions / bodies**. Consumers: `bmad-testarch-atdd` (red-phase unit test bodies) and `bmad-nowing-integration-test` (Pattern 6, real Postgres).

---

## AC-1 — Admin Rule CRUD API

### Pattern 1 — Mirror
- [ ] should return exactly fields `{version, is_active, updated_at, updated_by}` in list response
- [ ] should return full `rule_schema` in `GET /{platform}` active rule response
- [ ] should NOT return `created_by_user_id` / `updated_by_user_id` in public list fields
- [ ] should resolve `{version}` path param to the integer `version` column, not `id`

### Pattern 2 — Over-Mocking
- [ ] should handle Redis publish failure without crashing the DB transaction
- [ ] should handle `ScraperRuleService.get_active_rule` returning `None` (no active rule)
- [ ] should handle DB `IntegrityError` on duplicate `(platform, version)`

### Pattern 3 — Edge cases
- [ ] should handle empty list (`GET /` with no rules)
- [ ] should handle pagination at `limit=0` and `limit=100`
- [ ] should handle version `0` and negative version as invalid
- [ ] should handle deleting the only active version (rejected)
- [ ] should handle concurrent create on same platform (version race)

### Pattern 4 — Arithmetic
- [ ] should compute next `version` as `max(existing versions) + 1` for a platform

### Pattern 5 — Error message
- [ ] should return `HTTP 422` with message containing `Invalid CSS selector` on bad CSS
- [ ] should return `HTTP 422` with `code=REDOS_TIMEOUT` on ReDoS timeout
- [ ] should return `HTTP 404` when activating/deleting a non-existent version

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should execute query and return rows with columns `{id, platform, version, rule_schema, is_active, created_by_user_id, updated_by_user_id, created_at, updated_at}`
- [ ] should respect UNIQUE constraint `(platform, version)` — duplicate raises `IntegrityError`
- [ ] should respect partial unique index `uq_scraper_rules_active_per_platform` — two `is_active=true` for same platform raises `IntegrityError`
- [ ] should respect FK constraint on `created_by_user_id` / `updated_by_user_id`

---

## AC-2 — Validation trước khi lưu

### Pattern 1 — Mirror
- [ ] should call `scraper_rule_validator.validate_css_selectors` before create
- [ ] should call `scraper_rule_validator.validate_regexes` before create
- [ ] should reject `RuleSchema` with `extra` fields when `ConfigDict(extra="forbid")`
- [ ] should not persist an invalid rule to DB

### Pattern 2 — Over-Mocking
- [ ] should handle `cssselect.parse` raising `SelectorSyntaxError`
- [ ] should handle `google-re2` not installed (fallback to `re` with timeout)
- [ ] should handle `ProcessPoolExecutor` timeout on catastrophic regex

### Pattern 3 — Edge cases
- [ ] should handle `selectors` being an empty dict
- [ ] should handle `regexes` being an empty dict
- [ ] should handle boundary `request_ms=0` and `request_ms=60000`
- [ ] should handle boundary `error_threshold_pct=0` and `error_threshold_pct=100`
- [ ] should handle `max_attempts=0` and `max_attempts=10`
- [ ] should handle `trip_duration_seconds=0` and `trip_duration_seconds=3600`
- [ ] should reject `request_ms=60001` (above max)
- [ ] should reject negative numbers in any numeric field

### Pattern 4 — Arithmetic
- [ ] should treat `request_ms` as milliseconds (not seconds) until wire step converts it
- [ ] should compute `trip_duration_seconds` as integer seconds (no float)

### Pattern 5 — Error message
- [ ] should return `HTTP 422` with `detail[0].msg` containing `Invalid CSS selector`
- [ ] should return `HTTP 422` with body `{"code": "REDOS_TIMEOUT", "detail": ...}`
- [ ] should return `HTTP 422` with `detail[0].type="value_error.missing"` when a required key is absent

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should NOT insert a row into `scraper_rules` when validation fails
- [ ] should NOT write `AuditEvent` when validation fails

---

## AC-3 — ReDoS Sandbox Benchmark

### Pattern 1 — Mirror
- [ ] should return 422 for regex `(a+)+$` with input `'a' * 30 + '!'`
- [ ] should accept safe regex (e.g., `^\d+$`) on normal inputs
- [ ] should run outside the event loop (no `asyncio` blocking)

### Pattern 2 — Over-Mocking
- [ ] should handle `google-re2.compile` raising an exception
- [ ] should handle `re.search` hanging beyond 50ms
- [ ] should handle `ProcessPoolExecutor` worker termination

### Pattern 3 — Edge cases
- [ ] should handle benchmark on inputs of 1 KB, 10 KB, 100 KB
- [ ] should handle regex with no groups (simple patterns)
- [ ] should handle regex with valid but nested groups
- [ ] should handle empty regex string
- [ ] should handle `google-re2` with unsupported lookahead/lookbehind

### Pattern 4 — Arithmetic
- [ ] should compute max execution time < 50 ms for safe patterns
- [ ] should compute timeout at exactly 50 ms threshold (boundary)

### Pattern 5 — Error message
- [ ] should raise `ReDoSTimeoutError` with `code=REDOS_TIMEOUT`
- [ ] should return `HTTP 422` with message `Regex exceeds 50ms ReDoS limit`

### Pattern 6 — SQL Mock Not Executed
- [ ] (no DB required) should not access the database during ReDoS benchmark

---

## AC-4 — Versioned JSONB Storage + Audit

### Pattern 1 — Mirror
- [ ] should write `AuditEvent.action` exactly equal to `scraper_rule.create` / `scraper_rule.update` / `scraper_rule.activate` / `scraper_rule.trip` / `scraper_rule.reset`
- [ ] should write `AuditEvent.actor_id` equal to the superadmin UUID
- [ ] should write `AuditEvent.diff_payload` containing `platform`, `version`, and `rule_schema`
- [ ] should store `rule_schema` as JSONB, not as a string

### Pattern 2 — Over-Mocking
- [ ] should handle `AuditEvent` insert failure (log and continue, or rollback)
- [ ] should handle DB serialization failure on concurrent activate
- [ ] should handle partial unique index violation on concurrent activate

### Pattern 3 — Edge cases
- [ ] should handle first version created as active automatically
- [ ] should handle deactivating old version and activating new version atomically
- [ ] should handle activating a version that is already active (idempotent)
- [ ] should handle deleting the only inactive version of a platform
- [ ] should handle creating a rule for an unknown platform slug (allowed in DB, optional validation)

### Pattern 4 — Arithmetic
- [ ] should increment `version` by exactly 1 per new rule for a platform
- [ ] should set `created_at` and `updated_at` correctly on create
- [ ] should update `updated_at` and `updated_by_user_id` on activate/toggle/delete

### Pattern 5 — Error message
- [ ] should raise `HTTP 422` / `HTTP 409` with `Cannot delete active rule` on active delete
- [ ] should raise `HTTP 409` with `Another version is already active` on partial unique index violation

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should execute query and return `ScraperRule` rows with JSONB `rule_schema`
- [ ] should enforce partial unique index `is_active=true` per platform in real Postgres
- [ ] should enforce unique constraint `(platform, version)`
- [ ] should enforce FK on `created_by_user_id`
- [ ] should write an `AuditEvent` row for every create/activate/toggle/delete
- [ ] should rollback transaction when `AuditEvent` insert fails (if designed)

---

## AC-5 — Redis Pub/Sub Live Invalidation + Auto-Rollback

### Pattern 1 — Mirror
- [ ] should publish to channel `scraper_config_updated` on every create/activate/toggle/reset
- [ ] should publish payload with exactly `platform`, `version`, `is_active`, `updated_at`
- [ ] should invalidate in-memory cache key for that platform

### Pattern 2 — Over-Mocking
- [ ] should handle Redis Pub/Sub subscriber connection drop
- [ ] should handle Redis publish raising `ConnectionError`
- [ ] should handle worker missing the Pub/Sub message (TTL fallback)

### Pattern 3 — Edge cases
- [ ] should handle no active rule (no invalidation needed)
- [ ] should handle multiple rapid activations (only latest wins)
- [ ] should handle error rate exactly at 20% threshold (no rollback)
- [ ] should handle error rate above 20% but below `min_calls` (no rollback)

### Pattern 4 — Arithmetic
- [ ] should compute error rate as `failures / total_calls` in a rolling 5-minute window
- [ ] should trigger auto-fallback only when error rate > 20% and `total_calls >= min_calls`
- [ ] should compute TTL cache expiry at exactly 5 seconds

### Pattern 5 — Error message
- [ ] should log `scraper_config_updated` publish failure with warning
- [ ] should return `HTTP 503` or `unavailable` if Redis is down on `refresh` endpoint

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should read the newly activated rule from DB after TTL expires (real Postgres)
- [ ] should NOT use a stale cached rule after activation

---

## AC-6 — Wire rule vào scraper worker

### Pattern 1 — Mirror
- [ ] should use `rule_schema.delays.request_ms` when `USE_DYNAMIC_SCRAPER_RULES=true`
- [ ] should use `rule_schema.retries.max_attempts` when `USE_DYNAMIC_SCRAPER_RULES=true`
- [ ] should fallback to `BATDONGSAN_PAGE_DELAY_S` when flag is false
- [ ] should not apply `selectors` CSS in main mobile-API path

### Pattern 2 — Over-Mocking
- [ ] should handle `ScraperRulesService.get_active_rule` returning `None`
- [ ] should handle DB connection error when reading active rule
- [ ] should handle `PlatformCircuitBreaker.is_available` returning `False`

### Pattern 3 — Edge cases
- [ ] should handle `USE_DYNAMIC_SCRAPER_RULES=false` (ignore DB rule)
- [ ] should handle missing `delays.request_ms` in rule_schema (fallback default)
- [ ] should handle `selectors` missing (use hardcoded parser)
- [ ] should handle web fallback path when mobile API returns empty

### Pattern 4 — Arithmetic
- [ ] should convert `request_ms` to seconds by dividing by 1000 exactly
- [ ] should use `retry_base_ms` / 1000 for backoff base
- [ ] should cap `max_attempts` at the rule value, not a hardcoded value

### Pattern 5 — Error message
- [ ] should return `degraded` with `reason: circuit_breaker_tripped` when tripped
- [ ] should log warning when `USE_DYNAMIC_SCRAPER_RULES=true` but no active rule exists

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should read active `ScraperRule` from real Postgres in worker
- [ ] should fallback to hardcoded config when DB has no active rule

---

## AC-7 — Emergency Circuit Breaker

### Pattern 1 — Mirror
- [ ] should set `rule_schema.circuit_breaker.tripped=true` in DB on trip
- [ ] should set Redis key `circuit_breaker:scraper:{platform}=OPEN` on trip
- [ ] should delete both `state_key` and `failure_counter_key` on reset
- [ ] should set `tripped=false` in DB on reset

### Pattern 2 — Over-Mocking
- [ ] should handle Redis `set` failure on trip
- [ ] should handle Redis `delete` failure on reset
- [ ] should handle `PlatformCircuitBreaker` not having `trip()` / `reset()` methods (write key manually)

### Pattern 3 — Edge cases
- [ ] should handle trip when already tripped (idempotent)
- [ ] should handle reset when not tripped (no-op)
- [ ] should handle trip TTL exactly equal to `trip_duration_seconds`
- [ ] should handle trip TTL default 600s when not specified
- [ ] should handle worker still using cached `tripped=false` for up to TTL

### Pattern 4 — Arithmetic
- [ ] should set Redis key TTL to `trip_duration_seconds` exactly
- [ ] should expire the OPEN state after TTL

### Pattern 5 — Error message
- [ ] should return `HTTP 403` for non-superadmin trip/reset
- [ ] should return `HTTP 422` for platform not found

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should update `ScraperRule.rule_schema` JSONB in real Postgres on trip/reset
- [ ] should write `AuditEvent` with `scraper_rule.trip` / `scraper_rule.reset`

---

## AC-8 — Superadmin Guard

### Pattern 1 — Mirror
- [ ] should call `require_superuser` on all 8 `/api/v1/admin/scraper-rules/*` endpoints
- [ ] should reject PAT token with `HTTP 403`
- [ ] should reject non-superuser session with `HTTP 403`
- [ ] should reject impersonated session with `HTTP 403`

### Pattern 2 — Over-Mocking
- [ ] should handle `require_superuser` raising an unexpected auth exception
- [ ] should handle auth service unavailable

### Pattern 3 — Edge cases
- [ ] should handle missing `Authorization` header
- [ ] should handle expired session
- [ ] should handle valid superuser session with no workspace context

### Pattern 4 — Arithmetic
- [ ] (none)

### Pattern 5 — Error message
- [ ] should return `HTTP 403` with message `Superadmin required`
- [ ] should return `HTTP 403` with message `PAT is not allowed` for PAT

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should NOT create `ScraperRule` row when request is rejected
- [ ] should NOT write `AuditEvent` when request is rejected

---

## AC-9 — Admin UI `/admin/scrapers/rules`

### Pattern 1 — Mirror
- [ ] should render platform list, version, `is_active`, circuit breaker status, `updated_at`
- [ ] should render JSON editor / form with `selectors`, `regexes`, `delays`, `retries`, `circuit_breaker`
- [ ] should not render sensitive raw `diff_payload` in UI

### Pattern 2 — Over-Mocking
- [ ] should handle API `500` on list load
- [ ] should handle API `422` on save
- [ ] should handle network error during 5-second polling

### Pattern 3 — Edge cases
- [ ] should handle empty platform list
- [ ] should handle invalid JSON in rule editor (client-side validate)
- [ ] should handle confirm modal for trip/reset
- [ ] should handle polling interval exactly 5 seconds

### Pattern 4 — Arithmetic
- [ ] should poll every 5000 ms
- [ ] should convert `request_ms` display to seconds in UI helper (optional)

### Pattern 5 — Error message
- [ ] should display inline error when CSS selector is invalid
- [ ] should display inline error when regex is rejected by ReDoS sandbox
- [ ] should display `403` redirect to `/admin` when not superadmin

### Pattern 6 — SQL Mock Not Executed
- [ ] (no DB required) should call `/api/v1/admin/scraper-rules` endpoints and handle responses

---

## Cross-AC / System-Wide Tests

### Pattern 1 — Mirror
- [ ] should reflect `rule_schema` changes end-to-end from UI → DB → worker within 2 TTL cycles

### Pattern 2 — Over-Mocking
- [ ] should handle `google-re2` missing in production (fallback to `re` with timeout)

### Pattern 3 — Edge cases
- [ ] should handle creating a rule for all supported platform slugs (`batdongsan`, `chotot`, `topcv`, `muaban_bds`, `masothue`, `itviec`)
- [ ] should handle `zero_publication` replication if `scraper_rules` is added to it

### Pattern 4 — Arithmetic
- [ ] should not regress existing scraper delay when `USE_DYNAMIC_SCRAPER_RULES=false`

### Pattern 5 — Error message
- [ ] should return a consistent 422/500/403 error envelope across all endpoints

### Pattern 6 — SQL Mock Not Executed (`@pytest.mark.integration`)
- [ ] should pass `alembic upgrade head` and `alembic history` with single head
- [ ] should pass `from app.app import app` import smoke with `ScraperRule` registered
