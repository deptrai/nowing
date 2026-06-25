# Deferred Work

## Deferred from: code review of 10-1-4-cohort-taxonomy-reimplementation (2026-05-06)
- Misleading "Word-boundary matching" comment in `_classify_cohort` docstring — comment promises stricter matcher than substring `in` impl; will be obsolete after Patch 1 (regex word-boundary). [nansen_smart_money.py:62-63]
- Unicode lookalike obfuscation (`Bínance`, fullwidth `ＢＩＮＡＮＣＥ`) bypasses keyword matching → label-spoof CEX classified as retail. [nansen_smart_money.py:109]
- Same wallet appears in multiple Arkham `raw_links` (in + out) → `cohort_summary` count and net_flow inflated vs displayed Sankey nodes. [crypto_smart_money_flow.py:218-226]
- Dune > `_MAX_WALLETS_IN_SANKEY` rows: cohort_summary computed pre-truncation; legend totals can exceed displayed Sankey nodes. [crypto_smart_money_flow.py:269-308]
- `SankeyLegend` locale prop not forwarded from `crypto-report-layout` → currency format may diverge from chart in non-en locale. [crypto-report-layout.tsx:354-357]
- Test coverage for Arkham `fund`/`whale`/`dex` entity-type mappings — current tests cover only CEX-drop and `unknown` fallback. [test_smart_money_fallback.py]

## Deferred from: Story 10.1.1 smart money integration (2026-05-05)
- **Nansen 404 → empty Sankey for tokens not in Nansen index** (e.g., PEPE với mock key): Fixed 404→empty-wallets trong `nansen_smart_money.py` và added `links.length > 0` FE guard. Full solution cần Dune + Arkham fallback → **Story 10.1.2** (`_bmad-output/planning-artifacts/stories/10-1-2-nansen-failover-dune-arkham.md`).
- **Local dev luôn empty Sankey** vì `NANSEN_API_KEY=mock-key-for-testing`. Cần set `DUNE_API_KEY` hoặc `ARKHAM_API_KEY` để có real data → Story 10.1.2.

## Deferred from: code review of 10-1-entity-resolution-smart-money.md (2026-05-04)
- viewMode preference lost on Sheet remount: a11y user toggle "Table View" rồi đóng/mở mobile Sheet → chart view trở lại. Lift state lên context/localStorage. [nowing_web/components/crypto/SankeyFlowChart.tsx:245]
- `_ALL_TOOL_NAMES` thêm `get_certik_*`, `get_live_token_price` không liên quan Story 10.1: anticipates future stories, scope creep. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py:131-150]
- Tokenomics test docstring weakened: "exactly these tools" thay vì list cụ thể; thuộc Story 9.1 scope. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py:273-274]
- `min-h-[400px]` outer + `min-h-[300px]` inner double constraint trong Sheet `h-[calc(100%-60px)]`: layout NIT cần visual verification. [nowing_web/components/crypto/SankeyFlowChart.tsx]

## Deferred from: code review of 10-1-entity-resolution-smart-money.md (2026-05-01)
- Mobile Modal Rendering Crash Risk: The mobile view mounts the `ResponsiveSankey` inside a conditionally opened `<Sheet>`. Nivo charts historically fail to calculate their bounding boxes when mounted inside unmeasured portals/modals, often resulting in a `0x0` invisible chart until a window resize event is triggered. [nowing_web/components/crypto/SankeyFlowChart.tsx]
- Nivo Link Reference Error: `Nivo Sankey` throws fatal runtime error if link source or target ID missing from nodes array. Guard snippet: `<ResponsiveSankey data={{...data, links: data.links.filter(l => data.nodes.some(n => n.id === l.source) && data.nodes.some(n => n.id === l.target))}} />` [nowing_web/components/crypto/SankeyFlowChart.tsx:81]
- Poor Error Handling Strategy: The prompt instructs the LLM on how to handle tool errors. Relying on an LLM to reliably parse stringified JSON errors and self-regulate is a known anti-pattern. Error boundaries should be handled in the code's execution layer, not in the prompt text. [nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_spec.py]
- Brittle Unit Tests: `test_smart_money_analyst_spec_valid` asserts that exactly 5 tools are present (`len(...) == 5`). This is a lazy test that provides no value but guarantees the test suite will break if a valid tool is simply added or removed in the future. [nowing_backend/tests/unit/agents/new_chat/test_crypto_subagent_specs.py]

## Resolved 2026-04-25 — Lost partial work on rate-limit (Story 0.6b AC8/AC9)

- **Sub-agent 429 killed entire stream + discarded all completed sub-agents' outputs** — deepagents `atask()` had no try/except → exception killed LangGraph stream → user saw "Sorry, there was an error" despite N/6 agents succeeding. **Resolved** by Story 0.6b Layer 4: `SubAgentResilienceMiddleware` (AC8) retries + converts to error ToolMessage; `_extract_partial_analysis` (AC9) salvages from checkpointer when synthesis itself fails. User **always** sees graceful partial result.

## Resolved 2026-04-24 — Rate-limit sustained-pressure gap (Story 0.6b)

- **`chat_deepagent.py` Tier 2 still fails on strict-RPM providers** — E2E smoke against TrollLLM 10 RPM showed Tier 2 natural sequential is still faster than rolling RPM window once KB planner + synthesis calls accumulate. **Resolved** by Story 0.6b (Tier 3 paced sequential with `asyncio.sleep(7)` + retry on synthesis). See [0-6b-rate-limit-paced-escalation.md](../planning-artifacts/stories/0-6b-rate-limit-paced-escalation.md).

## Still deferred from Story 0.6b (scope-limited follow-up)

- **Unit tests for escalation + resilience logic** [tests/integration/agents/test_rate_limit_escalation.py] — Story 0.6b T5 marked optional. E2E smoke verified (2026-04-25, scenario: 0/6 agents completed → partial analysis rendered, no crash), but unit coverage not yet written: `test_consecutive_events_promote_level`, `test_paced_emission_sleeps`, `test_synthesis_retries_on_rate_limit`, `test_subagent_resilience_retry_then_error_toolmessage`, `test_extract_partial_analysis_from_checkpoint`.
- **Grafana dashboard rows** — new metric labels emitted (`rate_limit_paced`, `rate_limit_reduced_scope`, `subagent_retry`, `subagent_exhausted`) but dashboard panels not yet updated. Owner: DevOps (Week 3 telemetry setup per sprint plan).
- **Resumable partial analysis FE button** — BE endpoint `stream_resume_chat` already loads checkpoint state, but no FE UI yet to trigger resume after partial. User currently re-sends full query. Defer to Phase 2 UX polish.

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

## Deferred from: code review of 0-2-base-sub-agents (2026-04-23)

- `news_analyst` prompt reference `sentiment_signal`/`positive_ratio` field — cần confirm output shape của `get_crypto_news` có thực sự trả field này.
- tiktoken dùng `gpt-4` encoding cho budget test nhưng runtime model có thể là Claude/Gemini — conservative approximation, không phải bug runtime.
- Agent name hyphen vs underscore (`general-purpose` vs `defillama_analyst`) — consistency nhỏ, không block functionality.
- `description` length/uniqueness không có test validate — nice-to-have cho planner routing quality.
- Tool scope filter dùng `t.name` attribute access — nếu registry trả dicts sẽ fail ở chỗ khác trước đó.

## Deferred from: code review of story 0-3-main-agent-prompt (2026-04-24)

- **Weak assertion scoping (pre-fix)** [tests/unit/agents/new_chat/test_system_prompt.py] — original tests grep agent names on whole `NOWING_SYSTEM_INSTRUCTIONS`; fixed inline by scoping to `<crypto_orchestration>` body via regex.
- **`get_live_token_data` not registered in `_TOOL_INSTRUCTIONS`** [app/agents/new_chat/system_prompt.py] — prompt example references the tool but registry entry missing. Covered by Story 0.4 (API integration tests) or raise follow-up.
- **Shared team-thread prompt missing crypto orchestration** [`_SYSTEM_INSTRUCTIONS_SHARED`] — team threads cannot spawn crypto sub-agents. Requires product decision (intentional vs gap); raise with PM.
- **Working-tree leak — Story 0.2 artifacts** — uncommitted files from prior story add noise; housekeeping.

## Deferred from: code review of story 0-5-parallel-execution-validation (2026-04-24)

- **DoD-6 P95 benchmark not yet executed** — `TestParallelismRatioBenchmark` + `TestSpeedGate` require ~50 min + real API budget for 100 queries × 4 agents. Blocked on decision about how to gate slow-LLM tests (env flag / VCR / mocked LLM).
- **DoD-7 Grafana/Datadog dashboard + alerts** — 2 histogram metrics (`crypto_orchestra_parallelism_ratio`, `crypto_orchestra_full_suite_duration_seconds`) are defined but no dashboard panel or P95-ratio-alert config exists. Out-of-code infra artifact; deferred until Phase 1 goes live.
- **DoD-8 Parallelism ratio interpretation doc** — Ops runbook explaining what P50/P75/P95 values mean, common causes of elevated ratio, and fallback when gate fails. Doc task, deferred.

## Deferred from: code review of story 0-6-error-handling-fallback (2026-04-24)

- **respx catch-all `.pass_through()` with real HTTP in tests** — testing infra concern; structural orchestration tests pass-through unmocked URLs which could hit real services. Not story scope. [test_graceful_degradation.py]
- **Counter label cardinality risk with free-form `agent_name="unknown"`** — speculative TSDB bloat risk if agent names vary per request; monitor in production. [chat_deepagent.py:_track_degradation]
- **Pure-LLM failures (no ToolMessages) invisible to `GRACEFUL_DEGRADATION_COUNTER`** — design decision: current scope tracks tool-layer degradation only. Revisit if LLM-level failures become common. [chat_deepagent.py:_track_degradation]
- **`respx>=0.23.1` added only to `dev` dep group** — tests are dev-only, prod `ImportError` at collection not a real path. [pyproject.toml]
- **Dashboard panel "Degradation Rate" gauge (DoD-8)** — Grafana artifact not in diff; ops needs panel showing `sum(rate(crypto_orchestra_graceful_degradation_total{outcome=~"success|partial"})) / sum(rate(crypto_orchestra_graceful_degradation_total))` ≥ 98%. Out-of-code infra task. [spec:DoD-8]
- **AC9 anti-hallucination assertion missing** — spec requires "KHÔNG hallucinate fake data"; automatic verification hard without a golden-response dataset. [test_graceful_degradation.py:test_catastrophic_failure_returns_honest_message]
- **AC2 `<35s` timing assertion missing** — respx raises immediately so timing is naturally bounded; adding `time.perf_counter()` wrap would be belt-and-suspenders. [test_graceful_degradation.py:test_goplus_timeout_returns_error_dict]
- **AC4/AC5/AC6 content-verification tests** — LLM-guarded tests exist but aren't enforced. Defer to nightly pipeline with `ANTHROPIC_API_KEY`; structural tests fill the "no crash" gap. (Decision D1 from code review) [test_graceful_degradation.py:TestAgentLevelFallback]

## Deferred from: code review of story 0-1-tokenomics-analyst (2026-04-24)

- **Test regex fragility in registration check** — `test_subagent_middleware_registers_six_agents` uses non-greedy `.*?` + split-by-comma; would break on nested brackets or multi-line spec bodies. Consolidate with the sibling `test_crypto_subagent_wiring.py::test_subagent_middleware_registers_six_specs` via a single AST-walk helper. [tests/unit/agents/new_chat/]
- **8-char uuid4 hex in synthetic task_call IDs** — 32-bit collision-prone at ~65k IDs. Pre-existing from Story 0.5, not introduced in 9.1. Consider full `uuid4().hex` or a monotonic counter. [chat_deepagent.py:ParallelSpawnDirectiveMiddleware]
- **`SubAgent` TypedDict `# type: ignore[typeddict-unknown-key]`** — pattern inherited from Epic 0.2. Narrow the ignore to the specific offending key or file upstream issue against deepagents. [chat_deepagent.py]
- **Synthetic `short_q` f-string** — user-controlled content interpolated into tool_call description. Low practical risk today (sub-agent description is just hint text) but should be `json.dumps`-escaped for defense-in-depth. [chat_deepagent.py:ParallelSpawnDirectiveMiddleware]
- **`FULL_SUITE_DURATION_HISTOGRAM` bucket `"4+"` semantics** — now mixes 4-agent and 5-agent durations. Rename to `"full_suite"` or split into explicit buckets when Phase 2-3 add stories 9.2, 9.3, 9.5, 9.6. [metrics.py + chat_deepagent.py]
- **AC4-AC8 LLM-budget-dependent content verification** — functional spawn, parallelism ratio for 5 agents, 50-query QA, graceful degradation content assertions. Deferred to nightly LLM pipeline. [story 9.1 scope]

## Deferred from: code review of 9-UX-1-live-research-lab (2026-04-25)

- **Storybook infrastructure missing** — `@storybook/react` package not installed in `nowing_web/`. Story files for orchestra lab components were created in-place ([orchestra-lab.stories.tsx](nowing_web/components/new-chat/orchestra/orchestra-lab.stories.tsx)) ready for when Storybook is added. Pre-existing project setup gap, not caused by this story.
- **Playwright `route` implicit-any TS errors** — [research-lab.spec.ts](nowing_web/playwright/e2e/research-lab.spec.ts) inherits the same 11 pre-existing TS errors as [orchestra-strip.spec.ts](nowing_web/playwright/e2e/orchestra-strip.spec.ts). Root cause: project tsconfig doesn't include `@playwright/test` types; needs separate `tsconfig.playwright.json`. Affects all Playwright specs in the project.

## Deferred from: code review v2 of 9-UX-1-live-research-lab (2026-04-25)

- **Orchestra-spawn BE pipeline missing** — root cause of "Research Lab works in Playwright mock but invisible in prod". When the BE never emits `orchestra-spawn`, FE reducers' `if (!session) return state;` early-return for ALL 5 new orchestra events. Documented in [chat_deepagent.py SourceAttributionMiddleware docstring](nowing_backend/app/agents/new_chat/chat_deepagent.py). Needs follow-up story to wire spawn emission for sub-agent dispatch.
- **Sub-agent task ContextVar isolation** — `_stream_writer_var.set()` in parent task may not propagate to child Tasks if LangGraph dispatches sub-agents via raw `asyncio.create_task`. Needs integration test exercising real `astream_events` flow with parallel sub-agents to confirm rate-gate event delivery. AC13 marked done with caveat.

## Deferred from: code review of 9-UX-1b-background-agent-resume (2026-04-25)

- **C7 `/regenerate` byte-equivalence parity not implemented** — `/regenerate` endpoint left untouched; spec required calling `start_run` + emitting `run-meta` first event for Vercel-format byte-equivalence with `/runs/{id}/stream`. Recommend tracking as 9-UX-1c follow-up. Existing `/regenerate` still works as backward-compat path.
- **AC8/AC9 multi-strip rendering + `activeRunSessionsAtom` migration** — `orchestra.atom.ts` not modified to add `activeRunSessionsAtom` (Map keyed by run_id) or rename `activeQueryHash → lastSpawnedSessionId`; orchestra-strip not modified to render N strips. Required for genuine multi-run UI when 2 queries fire concurrently (current single-strip handles single-run only).
- **AC11/T19 Resume button in orchestra strip header** — Current `page.tsx` shows abandoned-runs banner above `<Thread />` as functional substitute; spec wanted Resume button inside strip header.
- **T5 `_stream_session_id_var: ContextVar[str]` refactor** — 10+ session_id derivation sites in chat_deepagent unchanged; not blocking because `langgraph_thread_id_override` covers the primary detached path.
- **T10/T11/T12 integration tests missing** — cancel-mid-stream + final orchestra-cancel; FE disconnect with task survival; 2 runs same thread with distinct langgraph_thread_id. Require Postgres+Redis fixtures (currently 21 unit tests pass, integration suite gated by `SKIP_INTEGRATION_TESTS` env).
- **T13 `/regenerate` byte-equivalence regression test** — blocked by C7 deferral.
- **T20 FE component unit tests** for multi-strip rendering + resume button — blocked by AC8/AC9/T19 deferrals.
- **T21/T22 Playwright E2E** — refresh-mid-stream replay test and 2 concurrent queries multi-strip test missing; current `resume-agent.spec.ts` covers only "running run replays on mount" + "abandoned run shows Resume banner".
- **Migration downgrade dangling FK** — alembic 134 downgrade drops `chat_runs` but `NewChatThread.chat_runs = relationship(...)` ORM mapping still references it; manual fixup needed if rollback is exercised.
- **AC7 startup hook order + count log at call site** — `await mark_abandoned_runs_on_startup()` runs before `initialize_llm_router()` and discards return count at caller; function logs internally. Cosmetic.

## Deferred from: code review of story 9-UX-1c (2026-04-25)

- **Redis connection leak if SSE generator not `aclose()`d** — `new_chat_routes.py:1831` creates Redis client before `try` block; cleanup depends on Starlette StreamingResponse behavior on client disconnect. Pre-existing pattern.
- **`hashtextextended` is internal PG function** — `run_event_writer.py:317`; portability concern for PG <11. Acceptable for current deployment (PG 15+).
- **`orchestraStateAtom` abandoned sessions never evicted** — `orchestra.atom.ts:380`; sessions with `completedAt: null` (abandoned, never completed) grow unbounded in Map. Eviction only runs on `orchestra-complete`.
- **`asyncio.get_event_loop()` deprecated** — `run_event_writer.py:143,235`; should be `get_running_loop()`. Cosmetic until Python 3.14.
- **T15 resume dedup integration test** — Spec-required `test_resume_dedup.py` not implemented. Requires live Postgres + Redis.
- **T23 FE component unit tests** — `multi-strip.test.tsx`, `resume-button.test.tsx`, `orchestra-multi-run.test.ts` not created.
- **T24 concurrent-queries E2E scenario** — `resume-agent.spec.ts` covers wire format + resume button but not multi-run strip rendering.
- **AC1/T3 `/regenerate` share generator refactor** — byte-equivalent SSE across `/regenerate` and `/runs/*/stream` via shared Python generator. Scope: extract `_stream_run_events()`, wire `/regenerate` to call it.
- **AC5 `activeRunSessionsAtom` include abandoned sessions** — spec says `outcome === 'running' || 'abandoned'`; current filter is `running` only. Merge logic in `assistant-message.tsx` works as workaround.
- **AC7 sync-INSERT fallback on deque overflow** — direct DB INSERT for non-text events when deque full. Currently all types drop oldest on overflow.
- **T14 byte-equivalence regression test** — linked to AC1/T3; test `/regenerate` vs `/runs/*/stream` byte-level output equivalence.

## Resolved 2026-04-29 — Story 9 audit sync (spec-vs-code gap closure)

- ~~**MAJ-8 — Persist `data-agent-result` to DB via ContentPart lifecycle**~~ — **Fixed**: Added `data-agent-results` ContentPart type to `streaming-state.ts` union + `buildContentForPersistence`. Wired `collectedAgentResults` accumulator (including missing `.push()` bug) in all three SSE handlers (`handleSend`, `handleResume`, `handleRegenerate`) in `page.tsx`. Added extraction in `message-utils.ts` → exposed via `metadata.custom.agent_results` for consumers. Page-reload persistence complete.
- ~~**F16/F19 — CoinGecko API called client-side without API key**~~ — **Fixed**: Added `GET /compare/coingecko-price/{coin_id}` proxy endpoint in `comparison_routes.py` (authenticated, validates coin_id regex). `token-hero-card.tsx` now calls BE proxy instead of CoinGecko directly. Rate limit risk eliminated.
- ~~**Missing `eth_shock` slider**~~ — **Fixed**: Added ETH Price Shock slider between BTC and Competitor Growth in `scenario-simulator-panel.tsx`. Updated `DEFAULT_ASSUMPTIONS` for bull (+0.4), bear (-0.35), stress (-0.5).
- ~~**P1#9 — i18n keys hardcoded VN/EN strings in components**~~ — **Fixed** (English-only commitment, not i18n framework): All Vietnamese strings in production code converted to English across 8 files: `agent-lane.tsx` (4), `orchestra-strip.tsx` (1), `rate-gate-banner.tsx` (2), `coin-comparison-overlay.tsx` (2), `next-action-bar.tsx` (3), `follow-up-chips.tsx` (1), `stream_new_chat.py` (3). Stories files and bilingual regex patterns in `report-toc.tsx` left untouched (intentional).

## Deferred from: Story 9 audit (2026-04-29)

- **Dune real query IDs needed** — `queries/dune/*.json` contain placeholder IDs 12345-12348 (now guarded: IDs < 100k are skipped at load time with `logger.warning`). To activate `run_dune_query` tool, replace JSON `query_id` values with real Dune Analytics query IDs (≥ 100k range). Requires Dune Basic plan account ($99/mo) and publishing 4 queries (Uniswap DEX volume, Lido staking flows, whale concentration, NFT floor). Owner: Data team.



## Deferred from: code review of 9-UX-2-crypto-report-layout (2026-04-27)

- **F11** — `CryptoReportLayout` wraps ALL messages (non-crypto pay `useAuiState` overhead). Pre-existing pattern, perf impact negligible.
- **F16** — CoinGecko API called from client without API key. Rate limiting risk. Needs BE proxy. Phụ thuộc TokenHeroCard viability (F3).
- **F19** — CoinGecko polling indefinitely for all historical messages. 5 reports = 5×30s polls. Phụ thuộc F3.
- **F27** — `IntersectionObserver` stale closures in ReportTOC. Blocked by F2 (TOC id fix).
- **F28** — Two charting libraries (recharts 200KB + lightweight-charts 45KB) with overlapping capabilities. Bundle optimization.
- **F29** — Module-level mutable state `_pendingUrlCitations` / `_urlCiteIdx` race in concurrent rendering. Pre-existing, not caused by 9-UX-2.
- **F32** — No E2E Playwright tests for crypto report layout. Post-implementation task.

## Deferred from: code review of story-9-UX-3 (2026-04-28)

- **DeFiLlama `/protocols` full-list scan (~5MB)** — `comparison_routes.py:517-535`. Cold compare downloads entire protocols list per request. Needs cached snapshot or paginated source. Performance debt.
- **`format_data` event-name BE/FE coupling brittle** — `VercelStreamingService.format_data` prepends `data-`; FE consumers depend on this implicit prefix. No immediate breakage but a refactor target risk. Document the contract.
- **NFR-P1 cold compare `<90s` benchmark** — Spec target unverified. Needs production benchmark, not pre-merge gate.
- **`useAui` import path smoke-test** — `follow-up-chips.tsx`, `next-action-bar.tsx` import `useAui` from `@assistant-ui/react`; project elsewhere uses `useAuiState`. Likely works but unverified pre-merge.
- **Missing `eth_shock` slider** — Spec `ScenarioAssumptions` includes `eth_shock` but UI only renders `btc_shock`. Minor schema-vs-UI gap.
- **Compare prompt-injection on token name** — `comparison_routes.py` builds verdict prompt with raw `primary_token`/`secondary_token`. After P2 patch (regex `^[A-Za-z0-9-]+$`), surface area is minimal. Defense-in-depth follow-up.
- **Cross-tab race (same user, 2 windows)** — Watchlist/alert atoms across tabs. Uncommon and converges via localStorage events.
- **DD2 — Compare endpoint sub-agent architecture (AC11)** — `comparison_routes.py` uses direct `httpx` instead of spec's "lightweight 2-agent" pattern. Current code is functionally equivalent; defer architectural rewrite. Update spec to reflect direct-call simplification.
- **DD3 — ComparisonTable additional rows (AC12)** — APY, Holders, Security Score, Sentiment, Unlock Schedule, Catalysts. Deferred to 9-UX-4 (Additional Data Sources) which adds whale_tracker + governance_analyst agents.
- **DD4 — `<OverlayChart>` Recharts dual-line price chart (AC12)** — `comparison-table.tsx`. Current table conveys quantitative compare. Implement post-launch if user feedback warrants.
- **DD5 (diff-marker portion) — Numeric diff highlighting in scenario UI (AC9)** — Spec example: "$7.23 → $12-15 ⬆". Requires LLM-side numeric extractor or markdown diff post-processor. Out-of-scope for current story; revisit as separate enhancement.

## Deferred from: code review of story 10-3-thundering-herd-protection (2026-04-30)

- **F3: `_local_locks` dict grows unboundedly** — `crypto_cache_lock.py:8`. One `asyncio.Lock` per unique key, never evicted. Bounded by unique tool+args combos (~1000 max). Add LRU eviction if process uptime or query diversity becomes concern.
- **F7: Lock retry backoff totals ~8.8s** — `crypto_cache_lock.py:37`. By design per story spec. Consider reducing max wait or adding user-facing timeout notification if chat latency complaints arise.
- **F9: Graceful degradation bypasses herd protection** — `crypto_cache_lock.py:42`. When lock not acquired after retries, proceeds unlocked — disables thundering herd protection. DB double-check still runs, reducing but not eliminating duplicates. Acceptable for launch.
- **F11: No integration-level thundering herd test** — Lock tested in isolation, middleware tested in isolation. Full concurrent middleware test (10 `awrap_tool_call` in parallel) belongs in integration suite.
- **F12: AC4 TTL expiry recovery not directly tested** — Unit test only covers fail-to-acquire path (mock `set` returns False). Real TTL expiry recovery relies on Redis server behavior; requires integration env to test.

## Deferred from: code review of story 10-4 (2026-05-01)

- **asyncio loop lifecycle** — `crypto_refresh_tasks.py:29-33,126-130`. `set_event_loop(None)` and `shutdown_asyncgens()` not called before `loop.close()`. Pre-existing pattern from `stale_notification_cleanup_task.py`. Address as codebase-wide cleanup if event loop issues arise.
- **No rate limiting on prefetch calls** — `crypto_refresh_tasks.py:68-79`. Sequential API calls without throttle or semaphore. Acceptable for current scale (~10-20 expiring snapshots per cycle). Add concurrency limiter (e.g. `asyncio.Semaphore(3)`) if upstream APIs start rate-limiting refresh cycles.
- **`NOT IN (SELECT ... LIMIT)` prune SQL** — `crypto_refresh_tasks.py:173-203`. Potentially slow on large tables. Consider window function (`ROW_NUMBER()`) + CTE-based delete when data grows beyond 10k rows per pair.

## Deferred from: code review of 10-5-workspace-watchlist-api (2026-05-01)

- F4: `data: dict` trong SnapshotResponse expose raw JSONB blob trực tiếp — sensitive fields không được filter trước khi trả về client. Pre-existing design decision, output schema chưa defined.
- F5: `category` query param không validate giá trị hợp lệ — typo silently trả 0 results thay vì 422. Low priority, no enum constraint on DB column.
- F6: Watchlist endpoint không có upper-bound limit — workspace với nhiều projects trả toàn bộ trong 1 response. Không phải concern hiện tại với workspace size thực tế.

## Deferred from: code review of story 11-1-sse-heartbeat-auto-reconnect & 11-2-redis-circuit-breaker (2026-05-02)

> **Triage 2026-05-02 (Sprint Change Proposal):**
> - 2 items → **PROMOTED → 11-6** (HTTP/2, Cloudflare CDN — pre-launch blockers)
> - 1 item → **PROMOTED → 11-7** (heartbeat cancel safety — post-launch)
> - 1 item → REMAINS deferred (BE doesn't emit quota mid-stream yet)

- [PROMOTED → 11-7] **`_with_heartbeat` cancel `next_task` mid-await có thể leak DB session/LangGraph state** [nowing_backend/app/tasks/chat/stream_new_chat.py:318-355] — Khi consumer disconnect, `task.cancel()` propagates `CancelledError` vào inner generator tại điểm `await` bất kỳ trong `_stream_new_chat_inner` (DB/LLM work). Cần redesign cancellation strategy (e.g. structured concurrency / sentinel) — không phải trivial fix, deferred cho hardening pass riêng.
- [PROMOTED → 11-6] **AC#5 (Story 11-1) HTTP/2 multiplexing 3+ tabs** — Skipped trong môi trường dev per Task 3.1 dev note. Cần verify Traefik/reverse proxy config khi deploy production.
- [PROMOTED → 11-6] **`Cache-Control: no-transform` có thể không hiệu quả với một số CDN** [nowing_backend/app/services/new_streaming_service.py] — Cloudflare free tier ignore `no-transform` cho SSE và có thể recompress làm hỏng framing. Verify deployment-specific khi go-live.
- **`streamWithRetry` không handle quota error qua SSE event payload** [nowing_web/lib/apis/chat-runs-api.service.ts:877-880] — Hiện chỉ check 402 ở HTTP response. Nếu BE emit quota event giữa stream, FE sẽ retry vô ích. Defer vì BE hiện không emit quota event giữa stream.

## Deferred from: code review of 11-3-orphaned-cache-purge (2026-05-02)

> **Triage 2026-05-02 (Sprint Change Proposal): DROPPED — pre-existing pattern across all celery tasks; round 2 already hardened the orphan task itself; codebase-wide refactor not scoped to Epic 11.**

- [DROPPED 2026-05-02] **Sử dụng `asyncio.new_event_loop()` thay vì `asyncio.run()`** [nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py] — Deferred do đây là pre-existing pattern được yêu cầu bắt buộc clone theo spec. Cần đợt refactor riêng để chuyển toàn bộ các celery tasks sang dùng `asyncio.run()`.


## Deferred from: code review of story 11-3-orphaned-cache-purge round 2 (2026-05-02)

> **Triage 2026-05-02 (Sprint Change Proposal):**
> - 2 items → **PROMOTED → 11-7** (NOT EXISTS scan analysis, search-space scoping ADR-013)
> - 6 items → REMAIN deferred (pre-existing patterns or speculative concerns)

- **`td.factory({})` empty config in `_prefetch_category`** [nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py:118] — Tools instantiated với empty dict config có thể overwrite cached snapshots với data sai (thiếu API keys/region). Refresh task, không thuộc scope 11-3 chặt chẽ.
- [PROMOTED → 11-7] **`NOT EXISTS` subquery có thể full-scan trên large table** [crypto_refresh_tasks.py:261-271] — Trên 10M-row `crypto_data_snapshots`, mỗi batch có thể vài phút. Cần index analysis (`ix_crypto_snapshots_cache_lookup` có cover hết không?) + có thể thêm `statement_timeout` ở DB-side config.
- **Test SQL string-match không verify semantics** [test_story_11_3_orphaned_cache_purge.py:43-51] — `"not exists" in stmt_str` pass kể cả khi correlation sai (`searchspaces.id = searchspaces.id` self-join bug). Cần integration test với Postgres seeded để verify.
- **`crypto_data_snapshots.search_space_id` đã có `ondelete=CASCADE`** [app/db.py:1390-1392] — "orphan" set chỉ tồn tại từ bypassing FK hoặc pre-migration legacy. Đặt câu hỏi: 11-3 có giải quyết bug thật hay che giấu integrity issue khác?
- **`loop.shutdown_asyncgens()` chưa await** [crypto_refresh_tasks.py:235-241] — Pre-existing pattern cho cả 3 cleanup tasks; leak async generators qua nhiều Celery worker run. Nên consolidate khi refactor.
- **`_async_cleanup` (daily 3 AM) thiếu try/finally** [crypto_refresh_tasks.py:195-219] — Pre-existing trong daily cleanup; nếu DELETE đầu tiên throw, JSON metric log bị mất. Pre-existing, không thuộc scope 11-3.
- **`passive_deletes` thiếu trên `SearchSpace.crypto_snapshots` relationship** [app/db.py SearchSpace model] — ORM-level delete của SearchSpace sẽ load all snapshots vào memory. Tangential to 11-3.
- [PROMOTED → 11-7] **Search-space scoping mismatch giữa refresh & cleanup path** [crypto_refresh_tasks.py:88-174 vs 248-289] — `_prefetch_category` ghi snapshots với `search_space_id=NULL`, cleanup chỉ purge `search_space_id IS NOT NULL`. Có thể đều đúng theo intent riêng (refresh = global popular tokens, cleanup = per-workspace), nhưng cần document rõ hai loại snapshot. **Owner: PM/Architect via ADR-013.**

## Deferred from: code review of story 11-4-per-api-token-buckets round 2 (2026-05-02)

> **Triage 2026-05-02 (Sprint Change Proposal):**
> - 1 item → **PROMOTED → 11-7** (Token release API on exception)
> - 1 item → **PROMOTED → 11-6** (Redis-flap state-mirror, ADR-011)
> - 4 items → REMAIN deferred (perf optimizations, speculative concerns)

- [PROMOTED → 11-7] **Token wasted khi tool exception/timeout sau acquire** [nowing_backend/app/agents/new_chat/tools/utils.py:48-71] — `crypto_tool_decorator` không có return-token API. Khi tool raise sau khi đã acquire, token bị mất → quota double-penalty (provider chỉ count successful 200s, ta count mọi attempt). Cần thêm `release()` API cho `TokenBucketRateLimiter` hoặc accept tradeoff.
- [PROMOTED → 11-6] **Local fallback bursts at capacity sau Redis flap** [rate_limiter.py:79-101] — Khi Redis up→down→up, local bucket starts fresh while Redis was drained → 1 request có thể consume token cả 2 stores. AC#5 chấp nhận over-count nên defer, nhưng nên document. **Owner: ADR-011 + 11-6 T4.**
- **No EVALSHA caching → perf overhead** [rate_limiter.py:85-91] — Mỗi tool call ship ~600B Lua script qua wire. redis-py asyncio support `register_script()` / `Script` để auto-EVALSHA. Optimization, không phải bug.
- **`get_limiter` registry race** [rate_limiter.py:140-153] — Plain `dict` không lock, race nếu mixed asyncio + threadpool. Asyncio-only deployment hiện tại safe.
- **Bucket pre-filled at startup → thundering herd** [rate_limiter.py:67] — N workers boot đồng thời có thể burst N× capacity. AC#5 accepts over-count nhưng có thể giảm cold-start risk bằng `capacity * 0.5`.
- **wait_step floor 100ms vs fast refill** [rate_limiter.py:113] — Etherscan refill 200ms nhưng wait_step floor 100ms; minor latency tax. Pre-existing perf tradeoff.

## Deferred from: code review of story 11-5-client-quota-enforcement (2026-05-02)

> **Triage 2026-05-02 (Sprint Change Proposal):**
> - 1 item → **PROMOTED → 11-6** (PRO_PLANS shared contract via ADR-012)
> - 4 items → REMAIN deferred (intentional CSS, no-i18n, test smell, no production signal yet)

- **Duplicate ProContentGate on responsive breakpoints** [nowing_web/components/new-chat/report/crypto-report-layout.tsx:259-307] — `2xl:hidden` + `hidden 2xl:block` cả 2 mount + render skeleton kể cả khi chỉ 1 visible. CSS responsive pattern hiện có; cả 2 mount là intentional. Có thể consolidate sang dùng `useBreakpoint()` hook nếu muốn skip mount inactive copy.
- **Offline check one-shot, không reactive** [ProContentGate.tsx:30] — `navigator.onLine` đọc 1 lần per render, không listen `online`/`offline` events. AC#6 chỉ require cold-mount behavior nên acceptable.
- [PROMOTED → 11-6] **`PRO_PLANS` không shared giữa FE và BE** [nowing_web/lib/entitlements.ts:1 + nowing_backend/app/schemas/stripe.py:14-17 + nowing_backend/app/config/__init__.py:317-348] — Hardcoded list trùng 3 nơi. Nếu BE thêm SKU mới (ví dụ `team_yearly`), FE silently deny → silent revenue loss. **Owner: ADR-012 + 11-6 T3.**
- **Test mock `vi.mock("jotai")` globally** [__tests__/hooks/use-subscription-gate.test.tsx:7-9] — Replace tất cả jotai exports → Provider/useSetAtom undefined trong test. Hidden coupling; chỉ catch bug nếu SUT literally call useAtomValue. Refactor sang dùng test wrapper với Provider.
- **CTA `/pricing` không locale-prefixed** [ProContentGate.tsx:62] — Hard-code `<Link href="/pricing">`. Nếu project sau add i18n routing (`/en/pricing`, `/vi/pricing`), CTA broken silently. No i18n yet nên defer.

## Deferred from: code review of story-10.1.1 (2026-05-05)

- **Stale closure `assistantMsgId` trong page.tsx handlers** — pre-existing pattern trong tất cả SSE handlers, không phải lỗi do story 10.1.1 introduce. Fix sẽ touch nhiều handler khác (citation_map, agent_results, report_type). [page.tsx:1190]
- **Net flow sign convention vs link magnitude** — `net_flow_usd` (signed) vs links dùng `abs(flow)`. Có thể là design intentional (Sankey magnitude vs net flow indicator) — cần verify với UX/PO trước khi đổi. [crypto_smart_money_flow.py:79-99]
- **Singleton `nansen_tool` factory closure** — `nansen_tool = create_nansen_smart_money_tool()` ở module-level closure là pre-existing pattern; refactor cần touch nhiều tools wrapper khác. [crypto_smart_money_flow.py:13-15]
- **Circuit breaker race condition (is_open → request)** — minor probabilistic gap (~ms): circuit có thể mở giữa `is_open()` check và HTTP request. Cần distributed lock để fix triệt để — không justified cho tool latency. [nansen_smart_money.py:108-110]
- **`record_success` reset failure counter trên 404** — Trong `nansen_smart_money.py:227-228`, 404 được treat như success → reset failure counter. Debatable: có thể là intentional (404 không phải lỗi service) hoặc bug (che health issue). Cần product decision. [nansen_smart_money.py:227-228]
- **`import re` inside function body** — Cosmetic; không ảnh hưởng behavior, nhưng pattern không idiomatic Python. [crypto_smart_money_flow.py:17]

## Deferred from: code review of 10-1-2-nansen-failover-dune-arkham.md (2026-05-05)
- Unbounded Cascading Timeouts — Sequential fallback chain might exceed total reasonable limits if every provider stalls.
- Dune Connector Interface Mismatch (Missing Chain parameter) — Drops chain parameter for Dune fallback query.
- Arkham 'Base Address' Semantic Confusion — Arkham transfers might not perfectly mimic curated smart money behavior.
- Flawed Circuit Breaker Success Metric — Records success purely based on missing exceptions, even if logical API errors occurred.

## Deferred from: code review of 10-1-2-nansen-failover-dune-arkham.md (2026-05-06)
- Nansen pagination only first page (per_page: 30) — net_flow_24h_usd and signal derived from partial data
- Arkham 401/403/429 collapsed to None — no differentiation between auth, rate-limit, server errors
- addr[:8] 8-char label collision risk for Sankey nodes (Nansen uses (addr) suffix; Arkham/Dune don't)
- tag: "" hardcoded — old Nansen endpoint preserved entityTag; new endpoint silently drops it
- system_prompt.py duplicate <knowledge_base_only_policy> block at lines 48 and 134
- Test plan partial (3/5 tests; source_domain attributions tested inline rather than as separate cases)
- Dune query ID drift — spec recommended 3493826, code defaults to 7431659
- Spec recommended get_latest_result cache check before triggering new execution (cost optimization)
- Spec recommended Arkham entity-type filter (entity.type in ["fund", "whale"]) — not implemented
- Arkham chain parameter dropped — _try_arkham accepts chain but get_transfers doesn't forward it
- Empty Nansen success falls through to Arkham+Dune — burns rate-limit budget on every empty Ethereum query
- Multi-worker rate limit: _ApiRateLimiter is per-process module singleton, not Redis-coordinated
- Arkham usd_gte=1000 hidden filter — silently filters sub-$1k whale activity for low-cap tokens
- _safe_circuit_is_open fail-open on Redis exception (cost vs availability tradeoff)
- Cohort taxonomy removed — old code categorized wallets; new code uses raw labels
- Arkham label collision: same entity name across multiple transfers collapses into single Sankey node
- Pre-10.1.1 messages may lose Sankey on reload — convertToThreadMessage rebuilds metadata from content parts only
- Nansen TGM endpoint (/api/v1/tgm/who-bought-sold) requires higher subscription tier than Pro — backward-compat concern
- source_domain="system" displayed in EmptySmartMoneyState — broken citation badge URL
- Sub-agent emits smart-money-flow event tied to wrong assistant message — clobbers main metadata
- pyproject.toml not updated for dune-client — uses raw httpx instead (justified in connector docstring)
- .env.example claimed updated in spec File List but not visible in this diff
- Out-of-scope changes for 10.1.2: middleware sub-agent fix, system_prompt rules, empty-state UI, FE source_domain plumbing, Nansen TGM endpoint migration — needs follow-up story
