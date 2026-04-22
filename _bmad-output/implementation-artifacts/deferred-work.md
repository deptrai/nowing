# Deferred Work

## Deferred from: code review of story 3-5-model-selection-via-quota (2026-04-14)

- **stripe_subscription_id has no unique constraint** [nowing_backend/app/db.py] — Column added without UNIQUE constraint. Should be enforced once Stripe integration (Epic 5) is implemented to prevent duplicate subscription mappings.
- **load_llm_config_from_yaml reads API keys directly from YAML file, not env vars** [nowing_backend/app/config.py] — Pre-existing: YAML config stores API keys inline. Spec Task 1.2 says "đọc API keys từ env vars" but this is the existing pattern used throughout the project. To be refactored when security hardening is prioritized.

## Deferred from: code review of story 5-1 (2026-04-14)

- `ref` cast `as any` on Switch component in `pricing.tsx:99` — pre-existing issue, not introduced by this change. Should use proper `React.ComponentRef<typeof Switch>` type.

## Deferred from: code review of story 5-2 (2026-04-14)

- Webhook handler needs to distinguish `mode='subscription'` from `mode='payment'` in `checkout.session.completed` and update User's `subscription_status`, `plan_id`, `stripe_subscription_id` — scope of Story 5.3.
- Subscription lifecycle events (`invoice.paid`, `customer.subscription.updated/deleted`, `invoice.payment_failed`) not handled — scope of Story 5.3.
- `_get_or_create_stripe_customer` can create orphaned Stripe customers if `db_session.commit()` fails after `customers.create`. Consider idempotency key in future.

## Deferred from: Story 5.6 post-story bug fixes (2026-04-15)

- **`api_key` exposed in LLM preferences response** [`nowing_backend/app/routes/search_space_routes.py`] — `GET/PUT /search-spaces/{id}/llm-preferences` returns full config objects including `api_key` (nested `agent_llm`, `document_summary_llm`, etc. fields). Should return sanitized Public versions (no api_key). Low risk since endpoint requires authentication, but still a credentials leak.

## Deferred from: code review of story-5.3 (2026-04-15)

- Race condition: `checkout.session.completed` and `customer.subscription.deleted` can fire near-simultaneously; if deleted arrives between checkout handlers, subscription can be reactivated. Fix requires Stripe API call to verify subscription status before activation.
- `invoice.payment_succeeded` does not update `subscription_current_period_end` — currently relies on `customer.subscription.updated` firing in the same event sequence. If that event is lost, period_end is stale.

## Deferred from: code review of Epic 5 (2026-04-15) — RESOLVED 2026-04-15

- ~~**Migration 124 drops enum type unconditionally**~~ — **Fixed**: Added `CASCADE` to `DROP TYPE IF EXISTS subscriptionstatus CASCADE` in `124_add_subscription_token_quota_columns.py`.
- ~~**`checkout_url` rejects non-HTTPS URLs**~~ — **Closed as invalid**: Original `startsWith("https://")` check is intentionally correct — Stripe always returns HTTPS URLs even in test mode. Relaxing to `http` would weaken security. No change made.
- ~~**`verify-checkout-session` endpoint lacks rate limiting**~~ — **Fixed**: Added in-memory per-user rate limit (20 calls/60s) via `_check_verify_session_rate_limit()` in `stripe_routes.py`.
- ~~**Rejected user can re-submit approval request immediately**~~ — **Fixed**: Added 24h cooldown check using `created_at >= now() - 24h` on REJECTED requests before creating a new SubscriptionRequest.
- ~~**`token_reset_date` not set in `_handle_subscription_event`**~~ — **Fixed**: When `new_status == ACTIVE` and `token_reset_date is None`, now sets `user.token_reset_date = datetime.now(UTC).date()`.

## Deferred from: code review of story-6.6 (2026-04-17)

- Double-click protection ngoài trạng thái `disabled` của button — rủi ro race nhỏ nếu user spam click trước khi state update; pre-existing pattern phổ biến trong codebase.
- Admin approval flow thiếu persistent state indicator — toast biến mất, user không có history UI khi `admin_approval_mode=true`; UX enhancement, không block chức năng.

## Deferred from: code review of story-6.7 (2026-04-17)

- Token expiry giữa chừng redeem flow → `AuthenticationError` redirect về login mà không giữ context (code đã nhập) — liên quan auth infrastructure chung, pre-existing ngoài scope story.
- `currentUserAtom` query không check loading/error state ở redeem page — áp dụng pattern hiện có từ buy-tokens page; có thể xử lý thống nhất sau.

## Deferred from: code review of story 6-1-database-migration-gift-codes-gift-requests (2026-04-17)

- CHECK constraint `expires_at > created_at` trên `gift_codes` — defensive DB-level guard; pre-existing pattern (`SubscriptionRequest`, `PagePurchase` không có similar check).
- CHECK constraint `amount_paid >= 0` và `duration_months > 0` trên `gift_codes` — defensive; `PagePurchase.amount_total` cũng không có check.
- `gift_requests.updated_at` không có `onupdate` trigger / app-level auto-populate — app-level concern; fit project pattern (TimestampMixin chỉ track `created_at`).
- Thiếu `currency` column trên `gift_codes` (so với `PagePurchase`) — không thuộc AC Story 6.1; USD-only launch. Revisit khi mở rộng sang i18n/đa tiền tệ.
- Thiếu `relationship()` back-ref trên `GiftCode`/`GiftRequest` → `User` — không thuộc AC; query code có thể explicit join. Add nếu admin screens gặp N+1.
- Thiếu composite index `ix_gift_requests_status_created_at` cho admin hot path ("pending requests" ordered by created_at) — revisit trong Story 6-5 khi admin query pattern rõ.

## Deferred from: code review of story 6-2-backend-api-create-gift-checkout (2026-04-17)

- `/dashboard/0/purchase-success` trigger dashboard onboarding loop — `_get_gift_urls(0)` sinh URL tới search_space không tồn tại; frontend Story 6.6 cần handle `search_space_id=0` hoặc chuyển gift sang route riêng (`/gift/success`).
- `purchase-success/page.tsx` hard-coded "Tokens added!" copy — gift purchaser thấy message sai; frontend Story 6.6 cần branch theo `session.metadata.purchase_type`.
- Webhook chưa handle `purchase_type="gift"` — nếu Story 6.2 deploy mà 6.3 chưa ship, payment sẽ được Stripe charge nhưng không tạo gift_code (customer trả tiền không nhận hàng). Cần enforce deploy ordering: 6.3 trước/cùng với 6.2.
- `duration_months: int = Field(ge=1, le=12)` rộng hơn `GIFT_PRICING` keys (1/3/6/12) — 2/4/5/7-11 pass Pydantic rồi 400 ở lookup; tighten thành `Literal[1,3,6,12]` cho cleaner contract.
- `customer_email=user.email` tạo duplicate Stripe customer nếu user đã có Stripe customer linked — cross-cutting với token-topup/subscription; cần refactor `ensure_stripe_customer()` helper dùng chung.
- `checkout_url: str` (required) nhưng admin_approval_mode trả `""` — contract nên `Optional[str] = None`; cross-cutting với sibling `CreateTokenTopupResponse` và `CreateSubscriptionCheckoutResponse`.
- Gift checkout không có authorization/eligibility check — any active user có thể buy, không chống abuse/chargeback; cần policy story riêng cho gift-specific rules (rate limit, email verified, min account age).
- `_get_gift_urls` và `_get_token_topup_urls` trùng pattern (`rstrip("/")` + f-string template) — drift risk; refactor thành `_get_checkout_urls(search_space_id, flow_type)` hoặc helper.
- Không idempotency cho rapid double-clicks — tạo nhiều Stripe sessions với distinct `payment_intent_id`; nếu cả 2 paid → 2 gift_codes tạo (unique constraint trên `stripe_payment_intent_id` chỉ block fulfillment trùng PI). Cross-cutting với token-topup; cần `idempotency_key` ở Stripe API call.

## Deferred from: code review of story 6-3 (Webhook Gift Code Fulfillment) — 2026-04-17

- Admin alerting when `_fulfill_gift_purchase` returns 200 with an error-level log (missing/invalid metadata, pricing mismatch, non-recoverable IntegrityError, collision retries exhausted). Today the only signal is a log line; payment is captured but no gift code exists. Need out-of-band alert (email/Slack/Sentry) + an admin "stuck gift payments" reconciliation view.
- Unit + integration tests for `_fulfill_gift_purchase`: happy path, idempotency (duplicate payment_intent), collision retry, FK violation on deleted user, invalid metadata, pricing tampering. No tests exist for this module yet.
- Extract shared Stripe webhook idempotency helper — `_fulfill_token_topup` uses `User.fulfilled_topup_sessions` (CSV field), while `_fulfill_gift_purchase` now uses `SELECT ... WHERE stripe_payment_intent_id = :pi`. Two different idempotency strategies for semantically identical problem — pick one and unify (likely the second).
- Gift code storage — codes are stored in plaintext in `gift_codes.code`. If DB is leaked, all unredeemed gifts are compromised. Consider storing `code_hash` (bcrypt/argon2) and returning plaintext to purchaser only via the webhook-bound API response once. Cross-cutting with redeem flow (Story 6.4).
- `expires_at = now() + 365 days` anchored to webhook-receipt time, not payment-intent creation time. For audit parity with Stripe timestamps, compute from `checkout_session.created` or `payment_intent.created`.
- Missing `metadata.plan_id` / `metadata.duration_months` sanity caps (e.g., plan_id length ≤ 32, no unexpected characters). Pydantic validates request side but webhook metadata is unstructured.

## Deferred from: code review of story 6-4 (Backend API Redeem Gift Code) — 2026-04-17

- HTTP idempotency cho `POST /redeem-gift`: client retry sau khi commit thành công (network hiccup) hiện thấy 400 "đã được sử dụng" thay vì success. Cần project-wide `Idempotency-Key` header pattern (cross-cutting với `create-gift-checkout`, `create-token-topup-checkout`).
- Calendar-month extension math: `timedelta(days=30 * duration_months)` cho 12-month gift = 360 days (mất ~5 days so với 1 năm thực). Chuyển sang `dateutil.relativedelta(months=n)` để accuracy theo lịch; dateutil đã có trong deps transitively.
- i18n strategy: API error details bằng tiếng Việt, logger/docstring bằng English. Project-wide strategy decision cần thiết (error codes + i18n layer ở frontend? hay hardcoded Vietnamese?).
- `RedeemGiftResponse` enrichment: thêm `duration_months` / `extended_by_days` để frontend toast hiển thị "Gia hạn thêm X tháng" mà không cần recompute từ before/after expiry.
- `gift_codes.redeemer_id` FK `ON DELETE SET NULL` zombie state: nếu user bị xoá, gift row thành `status=REDEEMED, redeemer_id=NULL` — future cleanup job dựa vào `redeemer_id IS NULL` sẽ resurrect redeemed gift. Cần add check `status = ACTIVE` mọi nơi, hoặc đổi FK thành `RESTRICT`.

## Deferred from: code review of story 6-5 (Gift History & Admin Fallback) — 2026-04-17

- `GiftRequest.updated_at` không có autoupdate trigger/onupdate — khi admin approve/reject, `updated_at` không đổi → audit trail mất; REJECTED cooldown không implement được. Cần DB migration thêm trigger hoặc `onupdate=lambda: datetime.now(UTC)` trong model.
- REJECTED resubmission cooldown cho `POST /request-gift` (mirror `_queue_subscription_approval_request` 24h pattern): hiện user bị reject có thể spam PENDING mới ngay lập tức. Defer đến khi admin reject workflow được implement.
- Rate limiting cho `POST /request-gift` — authenticated user có thể enumerate `plan_id × duration_months` combos flood admin queue. Cross-cutting infra concern (chưa có global rate limiter trong codebase; `verify-checkout-session` có in-memory limiter riêng).
- Structured audit row/table cho admin-approval workflow — hiện chỉ `logger.info`, nếu logging backend drop message thì không còn trace ngoài DB row. Cần audit table dedicated cho gift/subscription admin actions.

## Deferred from: code review of story 6-8 (Admin Approve/Reject Gift Request) — 2026-04-17

- Coupling `admin_routes` → private helper `_mint_gift_code` trong `stripe_routes`: không phải circular hiện tại nhưng design smell. Refactor helper sang `app/services/gift_codes.py` (module dùng chung) để admin/webhook/future-callers import từ layer service thay vì route file.
- Orphan `gift_code_id` → silent `gift_code=None` trong `list_gift_requests`: nếu `GiftCode` bị xoá trực tiếp (chưa có cascade path, nhưng tương lai có thể có), response trả `gift_code_id` có giá trị nhưng `gift_code=null`. Admin UI không phân biệt được "chưa approve" vs "code bị mất" — cần sentinel hoặc warning log.
- `expires_at` cố định `now + 365 days` khi admin approve: không override được. Nếu admin phê duyệt trễ (e.g., 3 tháng sau khi user submit), vẫn 365d từ approve time. Thêm optional `expires_at` param vào endpoint để override khi cần.
- Không check `locked_user.is_active` khi approve: có thể mint gift code cho user đã bị deactivate → họ không thể redeem vì không login được. Minor UX, cần warning hoặc block.
- `GiftRequestItem.status: str` + `GiftCodeItem.status: str` thiếu type safety — đổi sang `Literal["pending", "approved", "rejected"]` / `Literal["active", "redeemed", "expired"]` để client có contract rõ.

## Deferred from: code review of story 6-9 (Frontend Admin Gift Requests UI) — 2026-04-17

- **F3 — Error UX after approve network drop**: Nếu Stripe/DB commit success nhưng network drop trước khi response về, admin thấy "Failed to approve" trong khi code đã mint. Recoverable qua Approved tab (code vẫn hiện), nhưng error message misleading. Cần refetch + auto-switch tab hoặc hint "check Approved tab".
- **F5 — Zod schemas unused at runtime**: `giftRequestItem` / `giftRequestListResponse` / `giftRequestApproveResponse` exported nhưng component hand-rolls duplicate TS interfaces và không `safeParse` response. Contract drift sẽ không phát hiện tại runtime. Refactor: replace local interfaces với Zod-inferred types + `schema.safeParse(await response.json())` trong `fetchRequests`.
- **F8 — `count` field misleading**: `list_gift_requests` returns `count=len(items)` (page size), không phải total count. Field name misleading cho future pagination. Cần separate `SELECT COUNT(*)` query hoặc rename field thành `returned`.
- **F9 — Sidebar `isActive` prefix-match brittleness**: `LayoutDataProvider.tsx:397` dùng `startsWith("/admin")` + explicit exclusion cho `/admin/gift-requests`. Thêm route `/admin/*` mới cần manual exclusion. Refactor dùng exact match per-item: `pathname === href || pathname.startsWith(href + "/")`.
- **F11 — Unknown `plan_id` fallback**: UI render `req.plan_id.replace(/_/g, " ")` trực tiếp. Backend thêm plan mới (e.g., `"enterprise"`) sẽ render raw string. Fit once F5 lands (Zod-validated union type).

## Deferred from: code review of story 7-1-chainlens-research-service-health-check (2026-04-19)

- **resp.text[:200] có thể leak sensitive data**: Nếu upstream error body chứa echo-back của Authorization header hoặc token, `f"HTTP {code}: {resp.text[:200]}"` sẽ log ra. Mitigate: redact patterns `Bearer\s+\S+` trước khi include vào error message. [chainlens_research_service.py:81]
- **httpx.AsyncClient tạo mới mỗi call — no connection pooling**: TLS handshake + pool setup overhead per request. Nên dùng module-level `AsyncClient` singleton với lifespan tied to FastAPI app. [chainlens_research_service.py:41, 72]
- **Tests mutate `_health_cache` class-level trực tiếp**: `_reset_cache()` function mutate class state thay vì dùng `monkeypatch.setattr` fixture. pytest-asyncio mặc định serial nên OK hiện tại, nhưng nếu bật `pytest-xdist` hoặc fixture scope thay đổi sẽ flaky. [test_chainlens_research_service.py:162, 191]

## Deferred from: code review of story 7-2-chainlens-deep-research-langgraph-tool (2026-04-19)

- **Bare `except Exception` quanh `dispatch_custom_event`**: Swallow mọi exception (TypeError/AttributeError từ signature change trong LangGraph future) → regression silent. Nên log ở DEBUG level thay vì `pass`. [chainlens_research.py:67-72, 83-89]
- **Provider name `"nowing"` hardcode**: Coupling tên brand với tool output. Branch hiện tại đang rename từ surfsense → nowing; nếu rename lần nữa sẽ break consumer. Đổi thành `"builtin"` / `"local"` để decouple. [chainlens_research.py:26]

## Deferred from: code review of story-7.3 (2026-04-19)

- Test file path lệch spec: `tests/unit/tasks/` thay vì `tests/tasks/chat/` — cosmetic, file đã chạy được
- AC#1 thiếu positive LLM-routing test (mock LLM trả tool_calls=[chainlens_deep_research]) — intent detection logic chính thuộc Story 7.2 `_TOOL_INSTRUCTIONS`
- AC#8 regression coverage shallow — chỉ test generate_report, thiếu web_search & KB-search regression. Full chat suite (522 tests) đã pass per dev notes
- AC#6 timeout test & AC#9 cancellation test thiếu — behavior delegate cho Story 7.1 (httpx 125s timeout) + LangGraph default cancellation
- Unicode/grapheme cluster split tại codepoint 80 (Vietnamese combining marks/emoji ZWJ) — cosmetic preview only

## Deferred from: code review of story-7.4 (2026-04-19)

- `CHAINLENS_HEALTH_CACHE_TTL ≤ 0` → DoS amplifier: every `is_available()` call hits the network. Pre-existing in Story 7.1; no clamp.
- Validator runs late in lifespan after `seed_nowing_docs()` — if the latter raises, the Chainlens startup audit log never emits. Lifespan ordering is a pre-existing architecture decision.
- `_validate_chainlens_config()` logs the API URL at INFO with no sanitizer — if operator embeds basic-auth or token in URL, it leaks to log aggregation. Low-probability operator mistake, deferred.
- `ChainlensResearchService._health_lock = asyncio.Lock()` bound to module-import event loop — cross-loop hazard in pytest-asyncio under parallel runners. Pre-existing Story 7.1 design.
- No `inspect`-based regression guard preventing future "cleanup" that hoists `from app.config import config` out of `_validate_chainlens_config()` body. Hoisting would silently break all patch-based unit tests. Acceptable safety net today via existing `test_lifespan_calls_validate_chainlens_config`.

## Deferred from: test-review (2026-04-20)

Review: `_bmad-output/test-artifacts/test-reviews/test-review.md` — Overall D (61/100), 35 violations.

### Maintainability (full dimension — requires structural refactor)

- Split 8 test files exceeding 500 LOC (top: `test_local_folder_pipeline.py` 1308 LOC)
- `test_dropbox_parallel.py` has 120 mock refs in chained fixture — extract to factories
- Migrate 24+ copy-paste test variants to `@pytest.mark.parametrize`
- Flesh out `tests/utils/helpers.py` (currently 223 LOC / 7 helpers for a 16k-LOC suite)
- ~~Central `tests/constants.py` for `TEST_EMAIL`/`TEST_PASSWORD`/route URLs~~ — **Closed as false positive**: `TEST_EMAIL`/`TEST_PASSWORD` already centralized in `tests/utils/helpers.py`; all callers import from there.
- ~~Extract `ss`/`result` inline setup into `@pytest.fixture` in `test_stream_new_chat_chainlens.py`; remove `_make_streaming_service()` helper~~ — **Fixed 2026-04-20**: 16 test functions now receive `ss` and `result` via fixtures; dead helper removed.

### Isolation (MEDIUM)

- Duplicate session-scoped `auth_token` fixture in `test_stripe_page_purchases.py:90` shadowing conftest
- Session-scoped autouse `_purge_test_search_space` only fires at session start — mid-session failures leave stale rows
- `page_limits` fixture in `tests/integration/conftest.py:239` mutates user row via raw asyncpg conn, bypassing savepoint
- Session-scoped `async_engine` shares schema — non-savepoint asyncpg writes can leak

### Determinism (MEDIUM — defer pending freezegun adoption)

- 9 `uuid.uuid4()` occurrences in `tests/integration/google_unification/conftest.py` and `tests/integration/retriever/conftest.py` — acceptable for opaque DB PKs, flag for future snapshot tests
- ~~`datetime.now(UTC)` in `tests/integration/retriever/conftest.py:117` and `test_knowledge_search_date_filters.py:39,53`~~ — **Fixed 2026-04-20**: Replaced with `_ANCHOR_NOW = datetime(2026, 1, 1, tzinfo=UTC)` fixed constant.
- ~~`datetime.now(UTC)` comparisons in `test_composio_credentials.py:31,55`~~ — **Closed as already fixed**: File uses `_FROZEN_NOW = datetime(2026, 1, 1, tzinfo=UTC)` static constant; wall-clock never called.

### Performance (HIGH — dependency addition)

- ~~Add `pytest-xdist>=3.5` to `pyproject.toml` dev dependencies for parallel execution~~ — Already present in dev deps.
- ~~Wire CI config to use `-n auto` for 542-test suite~~ — **Fixed 2026-04-20**: `.github/workflows/backend-tests.yml` unit test step now uses `uv run pytest -m unit -n auto`.
- Per-test `httpx.AsyncClient` fixture could be session-scoped (minor)

### Pre-existing test failures to triage (unrelated to review)

~~18 errors/failures existed before this review pass:~~
- ~~`tests/unit/tasks/test_dexscreener_indexer.py` — `sqlite3.OperationalError: unrecognized token: ":"` (fixture setup)~~ — **Fixed 2026-04-20**: Added `tests/unit/tasks/conftest.py` overriding `async_session` with `AsyncMock` (avoids SQLite + PG-specific DDL incompatibility). 10/10 passed.
- ~~`tests/unit/indexing_pipeline/test_index_batch_parallel.py` + `test_migrate_legacy_docs.py` — DB fixture errors~~ — **Fixed 2026-04-20**: Added `make_connector_document` factory fixture to `tests/unit/indexing_pipeline/conftest.py`. 38/38 passed.
- ~~`tests/unit/connectors/test_dexscreener_connector.py::test_init_creates_connector` + `::test_get_token_pairs_success` — `base_url` assertion drift vs current code~~ — **Fixed 2026-04-20**: Updated assertions to match current production values. 10/10 passed.


## Applied fixes from test-review follow-up (2026-04-21)

### MAINT — Parametrize copy-paste test variants

- **`test_etl_pipeline_service.py`** — Merged `test_extract_docm_with_docling_raises_unsupported` + `test_extract_eml_with_docling_raises_unsupported` → `test_extract_docling_raises_unsupported_for_parser_incompatible[docm/eml]`
- **`test_chainlens_config_validation.py`** — Merged `test_enabled_missing_api_key_logs_warning` + `test_enabled_missing_api_url_logs_warning` → `test_enabled_single_missing_var_logs_warning[missing_key/missing_url]`
- **`test_chainlens_config_validation.py`** — Merged `test_enabled_whitespace_only_url_treated_as_missing` + `test_enabled_whitespace_only_key_treated_as_missing` → `test_enabled_whitespace_only_var_treated_as_missing[whitespace_url/whitespace_key]`
- **`test_etl_pipeline_service.py`** + **`test_chainlens_config_validation.py`**: 514 unit tests pass, no regressions.

### MAINT — Earlier session (2026-04-20)

- `test_dexscreener_routes.py`: merged 2 validation variants → parametrize `[missing_address/missing_chain]`
- `test_stream_new_chat_chainlens.py`: merged empty/None query tests → parametrize `[empty_string/none]`
- `test_bookstack_connector.py`: merged no-exclusion variants → parametrize `[empty_list/none_default]`
- `test_update_memory_scope.py`: 3 separate merges (pref/instr marker, heading scope, malformed bullet format)
- `test_file_extensions.py`: deleted 2 redundant single-item tests covered by existing parametrized suite
- `test_dropbox_file_types.py`: merged folder + non-downloadable → parametrize `[folder/non_downloadable]`

### ISO-LOW1 — `caplog` investigation

- `test_chainlens_research_tool.py:158` — only 1 test uses `caplog`, single assertion block, no `.clear()` needed. **Closed as false positive.**

### ISO remaining (not fixed — architectural complexity)

- ISO-M1: `auth_token` override in `test_stripe_page_purchases.py` — confirmed intentional design for 302-redirect Stripe auth flow
- ISO-M2: `_purge_test_search_space` session-scoped — per-test cleanup handled by `_cleanup_documents` autouse; session purge is belt-and-suspenders. Risk: mid-session crashes leave stale rows until session end. Acceptable for integration suite.
- ISO-M3: `page_limits` raw asyncpg bypass — necessary for integration test that mutates actual DB state
- ISO-M4: session-scoped `async_engine` — architectural, pre-existing

## Deferred from: code review of story-0-1-crypto-tool-infrastructure (2026-04-23)

- No retry/backoff/`asyncio.wait_for` outer timeout — lệch pattern `chainlens_research.py`. Cân nhắc thêm exponential backoff với jitter cho tất cả 11 tool files.
- 429 không honor `Retry-After` header — surface header value trong error message để LLM defer correctly.
- Etherscan multi-file source `{{...}}` wrapper không strip → `source_code_preview` có thể chứa JSON wrapper [contract_analysis.py:117].
- Bare `except Exception` quá rộng — narrow to `(httpx.HTTPError, ValueError, KeyError)` để không nuốt `KeyError`/programming bugs.
- New `httpx.AsyncClient` mỗi call — không connection pooling/HTTP-2 reuse. Cân nhắc module-level singleton.
- Etherscan v1 endpoints sắp deprecate Q4-2025 → migrate sang unified v2 multichain endpoint với single API key.

## Deferred from: code review of story-9-FE-1 (2026-04-23)

- **P1#5** — Out-of-order SSE events silently dropped (reducers `if (!session) return state`); revisit if backend 9-1/9-4 re-orders agents. [atoms/chat/orchestra.atom.ts]
- **P1#6** — Duplicate `orchestra-spawn` resets agents to queued (overwrites unconditionally). Need backend replay semantics decision before fixing. [atoms/chat/orchestra.atom.ts:97-104]
- **P1#7** — `activeQueryHash` clobbered on every spawn → concurrent sessions hijack each other. Single-tab MVP per arch §9.7 Q5. [atoms/chat/orchestra.atom.ts:115]
- **P1#9** — i18n keys (26 in 5 locales) hardcoded VN/EN strings in components (`agent-row`, `degradation-notice`, `orchestra-strip` cancelled footnote). Wire keys in follow-up i18n pass.
- **P1#10** — AC11 Rocicorp Zero persistence not implemented (no subscription, no mutator, no hydration). Defer to Story 9-FE-2 — D1 decision: accept Jotai for v1.
- **P1#11** — `trackCitationClick` (AC10 event #6) exported but never invoked. Wire when AC7/AC8 conflict detection lands.
- **P2#12** — `failedCount` semantics inconsistent: streaming `failed` only vs. complete `failed+cancelled`. Fix when AC14 telemetry wiring happens.
- **P2#13** — `elapsedMs` derived from session-level `spawnedAt` (not per-agent start). Display says "session age" instead of "agent runtime". Revisit if UX surfaces.
- **P2#14** — AC4 `summary.fact_count` + `sources[]` chips never populated; `OrchestraDoneEvent.data` only has `citationIds?`. Coupled with backend payload extension.
- **P2#15** — AC9 milestone copy `"Đang tổng hợp từ {success_count} nguồn"` not interpolated; current renders `"Analysing in depth…"`. Part of i18n pass.
- **P2#16** — A11y: `aria-hidden="true"` + `aria-label` conflict on agent-row icons; no `role="status"`/`aria-live="polite"` wrapper for live updates.
- **P2#17** — `orchestra_sessions` schema deviates from AC11 (`agents: json`, `spawned_at: string`, `total_ms: string` vs spec `string[]`/`timestamp`/`number`). Migrate when Zero integration lands.
- **P2#18** — Three identical SSE switch blocks in `page.tsx` (handleSend / handleResume / handleRegenerate). Refactor to shared helper coupled with `streaming-state.ts`.
- **P2#19** — `orchestraStateAtom.sessions` Map never pruned across chats; `activeQueryHash` may point to deleted session. Revisit if memory growth observed.
- **P3#20** — Polish bundle: `errorCode as FailReason` unsafe cast → falls through to raw string; `p95Bucket` no `Number.isFinite` guard; `STATUS_LABELS` Vietnamese hardcode in `agent-row.tsx`; `detectConflict` mixed-type array cast.

## Deferred from: code review of story-0-2-base-sub-agents (2026-04-23)

- **#6 (AC5–AC8 functional spawn tests)** — Unit tests cover spec constants, token budget, and tool scoping only. Actual sub-agent spawn + tool-call routing (AC5 DeFiLlama spawn, AC6 sentiment spawn, AC7 news spawn, AC8 smart_contract spawn) require live LangGraph runtime + API keys (DeFiLlama/CMC/Reddit/GoPlus/Etherscan). Defer to DoD-8 integration suite once env keys are provisioned in CI. File: `tests/integration/agents/new_chat/test_crypto_subagent_spawn.py` (TBD).
- **#7 (AC9 / NFR-CS2 parallel execution ratio)** — Parallel ratio assertion (`parallel_ms / sum(sequential_ms) < 0.7`) needs LangGraph trace capture + synthetic multi-agent query. Coupled with OpenTelemetry span export (DoD-7). Defer until trace export pipeline lands. Reference: `_bmad-output/planning-artifacts/stories/0-2-base-sub-agents.md` AC9.
- **#8 (Chainlens fallback prompt update)** — Chainlens tool returns `{"status": "fallback", ...}` when upstream unavailable; current 4 prompts don't instruct sub-agents how to surface this degraded state to end-users (should flag "Chainlens unavailable, using primary-tool-only view"). Update needed in all 4 `*_ANALYST_PROMPT` strings once Chainlens fallback schema stabilizes. Watch: `app/agents/new_chat/tools/chainlens_research.py` response envelope.
- **Review note** — Finding #1 (shared `gp_middleware` list) resolved via factory `_build_gp_middleware()` creating fresh middleware instances per sub-agent (chosen over stateless-assumption path for NFR-CS4 safety). `_memory_middleware` intentionally shared (read-only context injection). See `app/agents/new_chat/chat_deepagent.py` ~lines 450–525.
