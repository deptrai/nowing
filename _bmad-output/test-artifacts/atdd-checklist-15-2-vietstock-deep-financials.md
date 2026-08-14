# ATDD Checklist — 15-2-vietstock-deep-financials

## AC-1: Given the Vietstock scraper is authenticated, when a company is queried, then 20+ years of historical financial statements are fetched.

### Pattern 1 (Mirror)
- [ ] should return `VietstockQuote` with fields `symbol, current_price, open, high, low, close, volume, change, change_percent, key_ratios`
- [ ] should return `VietstockFinancials` with `balance_sheet, income_statement, cash_flow` each containing 20+ periods
- [ ] should NOT return raw HTML or unredacted session cookies in the output

### Pattern 2 (Over-Mocking)
- [ ] should handle `httpx` throwing `ConnectError`
- [ ] should handle `httpx` throwing `TimeoutException`
- [ ] should handle response body returning invalid JSON / HTML challenge page
- [ ] should handle `ScraperPlatformAccountService.get_default_credentials` returning `None`

### Pattern 3 (Edge cases)
- [ ] Boundary: `symbol` exactly at `min_length=1` and `max_length=20`
- [ ] Boundary: `include_financials=True` with 130K statements paginated correctly
- [ ] Null/empty: `symbol` empty string → degrade without network call
- [ ] Null/empty: `symbol` with whitespace only → normalize or degrade
- [ ] Null/empty: response with zero statements → return empty `financials` without crashing
- [ ] Concurrent: two simultaneous scrapes for same symbol must respect process-local throttle

### Pattern 4 (Arithmetic)
- [ ] should compute `total_items` as sum of quote + statement periods fetched
- [ ] should paginate so that each page does not exceed `VIETSTOCK_MAX_STATEMENTS_PER_REQUEST` (default 100)

### Pattern 5 (Error message)
- [ ] should raise `VietstockInputError` with message containing `invalid symbol` for empty/invalid symbol
- [ ] should set `degraded=true` with `degradation_reason=api_error` when response body is HTML

### Pattern 6 (SQL — integration, real DB)
- [ ] should execute query and return `ScraperPlatformAccount` rows with columns `id, platform, encrypted_credentials, is_enabled, is_default` for platform `vietstock`
- [ ] should respect FK/UNIQUE constraints when persisting account usage state

---

## AC-2: Given financial ratios are extracted, when normalized to `Chunk[]`, then P/E, P/B, ROE, ROA are stored as comparable numeric values in `content` and `metadata.ratios`.

### Pattern 1 (Mirror)
- [ ] should return `metadata.ratios` with keys `pe, pb, roe, roa` (not `PE`, `P/B`, `ROE%`)
- [ ] should store each ratio as `float | None` (never as string)
- [ ] should include the same numeric ratios in `content` as human-readable text

### Pattern 2 (Over-Mocking)
- [ ] should handle parser returning ratio values as `None`
- [ ] should handle parser returning ratio values as malformed strings (`"N/A"`, `"—"`, `""`)
- [ ] should handle `to_chunks` raising `ChunkValidationError`

### Pattern 3 (Edge cases)
- [ ] Boundary: ratio exactly `0.0`
- [ ] Boundary: negative P/E (loss-making company)
- [ ] Boundary: very large P/E (`1_000_000.0`)
- [ ] Null/empty: all four ratios `None` → still create chunk with `ratios: null` for all
- [ ] Null/empty: ratio string `"12,5"` → `12.5`
- [ ] Null/empty: ratio string `"12.5x"` → `12.5`
- [ ] Null/empty: ratio string `"18.5%"` → `18.5`
- [ ] Null/empty: ratio string `"NaN"` or `"Inf"` → `None`

### Pattern 4 (Arithmetic)
- [ ] should compute `pe` as exactly `15.2` when raw input is `"15.2"`
- [ ] should compute `pb` as exactly `2.1` when raw input is `"2,1"`
- [ ] should compute `roe` as exactly `18.5` when raw input is `"18.5%"`
- [ ] should compute `roa` as exactly `10.2` when raw input is `"10.2x"`
- [ ] should compute all four as `None` when raw input is `"N/A"`

### Pattern 5 (Error message)
- [ ] should raise `VietstockParseError` with message containing `unsupported ratio format` only if parser cannot coerce
- [ ] should NOT raise when ratio is `None` (degrade silently)

### Pattern 6 (SQL — integration, real DB)
- [ ] should persist chunks via `NowingIngestService` and query `chainlens` index for `pe` filter returning numeric values

---

## AC-3: Given Vietstock data conflicts with CafeF for the same symbol and period, when both source `Chunk[]` are produced, then each chunk is sent with the same canonical `sourceId` and `metadata.conflict_flags` and `metadata.source_count` so `chainlens-research` canonical index handles cross-source merge; Nowing does not merge them locally.

### Pattern 1 (Mirror)
- [ ] should return chunks from Vietstock with `sourceId` matching canonical `symbol + statement_type + period` hash
- [ ] should set `metadata.conflict_flags` to `True` when another source exists
- [ ] should set `metadata.source_count` to `2` when both CafeF and Vietstock produce same entity
- [ ] should NOT produce a merged `content` combining CafeF and Vietstock data in Nowing

### Pattern 2 (Over-Mocking)
- [ ] should handle `NowingIngestService.ingest` returning `noopSourceIds` for duplicate `sourceId`
- [ ] should handle `to_chunks` producing multiple chunks per record (split by token limit)

### Pattern 3 (Edge cases)
- [ ] Boundary: same symbol, same statement type, same period from CafeF and Vietstock → identical canonical `sourceId` prefix (domain differs, hash identical)
- [ ] Boundary: different statement type (`balance_sheet` vs `income_statement`) → different `sourceId`
- [ ] Boundary: different period (`Q4-2025` vs `2025`) → different `sourceId`
- [ ] Null/empty: only one source available → `conflict_flags=False`, `source_count=1`
- [ ] Null/empty: period cannot be parsed → `sourceId` still stable (fallback to raw period string)

### Pattern 4 (Arithmetic)
- [ ] should compute identical SHA-256 digest for `(symbol="VNM", statement_type="balance_sheet", period="Q4-2025")` regardless of source
- [ ] should prefix with domain so `cafef:sha256:<digest>` and `vietstock:sha256:<digest>` are distinct but share the same digest

### Pattern 5 (Error message)
- [ ] should raise `ValueError` with message containing `ambiguous scope` if both `workspace_id` and `user_id` are `None` during chunk context resolution
- [ ] should NOT raise if only one scope is set

### Pattern 6 (SQL — integration, real DB)
- [ ] should query `ChainLensIngestJob` and verify `ingested_source_ids` contains the canonical `sourceId` with both domain prefixes

---

## AC-4: Given a batch of Vietstock `Chunk[]`, when `NowingIngestService.ingest()` is called, then it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.

### Pattern 1 (Mirror)
- [ ] should return `ingestJobId` (UUID string) on successful ingest
- [ ] should return `ingest_status` as one of `ok|partial|noop|failed`
- [ ] should NOT return raw chainlens response body to caller

### Pattern 2 (Over-Mocking)
- [ ] should handle chainlens-research returning `409 Conflict` (duplicate) → `noop`
- [ ] should handle chainlens-research returning `429 Too Many Requests` → retry then dead-letter
- [ ] should handle chainlens-research returning `5xx` → retry then dead-letter
- [ ] should handle `httpx` raising `TimeoutException` → retry then dead-letter

### Pattern 3 (Edge cases)
- [ ] Boundary: batch size exactly `CHAINLENS_INGEST_MAX_BATCH_SIZE=1000`
- [ ] Boundary: batch size `1001` → parent job + child job IDs
- [ ] Boundary: chunks count `0` → `ingest_status=noop` without HTTP call
- [ ] Null/empty: `chunks` empty list → no HTTP call
- [ ] Concurrent: two overlapping `sourceId` sets from parallel scrapes → 409 handled gracefully

### Pattern 4 (Arithmetic)
- [ ] should compute `cost_micros` as exactly `5000` when `billable_units=1` and `VIETSTOCK_DATA_MICROS_PER_ITEM=5000`
- [ ] should compute `cost_micros` as exactly `0` when `degraded=True` regardless of `billable_units`
- [ ] should compute `cost_micros` as exactly `0` when `quote is None`

### Pattern 5 (Error message)
- [ ] should return `ingest_status=failed` with `degradation_reason=chainlens_unavailable` after max retries
- [ ] should raise `NowingError` with `code=CHAINLENS_INGEST_FAILED` if ingest fails and caller requires strict handling

### Pattern 6 (SQL — integration, real DB)
- [ ] should persist `ChainLensIngestJob` row with `scraper_id="vietstock.scrape"`, `workspace_id`, `status`, `ingest_job_id`
- [ ] should persist `ChainLensIngestJob` parent + child rows when batch > 1000

---

## AC-5: Given the cookie-based session expires, when the scraper detects `401/403`, then it refreshes the cookie and retries once; if refresh fails, it marks `degraded=true` with `degradation_reason: AUTH_REFRESH_FAILED`.

### Pattern 1 (Mirror)
- [ ] should set `degraded=True` on 401/403 after refresh failure
- [ ] should set `degradation_reason="AUTH_REFRESH_FAILED"`
- [ ] should return `quote=None` and `cost_micros=0` when degraded
- [ ] should NOT log raw cookie values

### Pattern 2 (Over-Mocking)
- [ ] should handle refresh endpoint throwing `TimeoutException`
- [ ] should handle refresh endpoint returning `500 Internal Server Error`
- [ ] should handle `ScraperPlatformAccountRotator.get_credentials` returning `(None, None)`
- [ ] should handle `ScraperPlatformAccountService` query raising `OperationalError` (DB down)

### Pattern 3 (Edge cases)
- [ ] Boundary: 401 on first request → refresh → 200 on retry → success
- [ ] Boundary: 403 on first request → refresh → 403 on retry → degrade
- [ ] Boundary: 401 on first request → refresh → 429 on retry → degrade after 429 retries
- [ ] Null/empty: no credentials configured → degrade immediately with `degradation_reason=AUTH_REFRESH_FAILED`
- [ ] Null/empty: empty cookie string → degrade without network
- [ ] Concurrent: two scrapes trigger refresh at same time → only one network refresh (Rotator lock)

### Pattern 4 (Arithmetic)
- [ ] should retry exactly once after successful refresh, then stop
- [ ] should count `billable_units=0` when degraded due to auth refresh failure

### Pattern 5 (Error message)
- [ ] should raise `VietstockAuthRefreshError` with message containing `AUTH_REFRESH_FAILED` when refresh fails
- [ ] should log structured message `vietstock auth refresh failed` without raw cookie

### Pattern 6 (SQL — integration, real DB)
- [ ] should execute `UPDATE scraper_platform_accounts SET usage_state=...` via `record_use` after failed refresh
- [ ] should query `scraper_platform_accounts` and select `is_enabled=True, platform="vietstock"` during credential rotation
