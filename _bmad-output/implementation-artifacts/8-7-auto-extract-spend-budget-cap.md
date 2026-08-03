---
baseline_commit: bcc862e66
story_key: 8-7-auto-extract-spend-budget-cap
---

# Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit (New Gap)

**Status:** done  *(P0 human-review gate closed 2026-08-01: 5 patch findings fixed, 3 items deferred, all 59 tests pass.)*
**Epic:** 8 — Người dùng thấy và kiểm soát được chi phí
**Source:** <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md" /> (Story 8.7, AR-6, RS-1)
**Related PRD:** FR-15 (multi-agent + auto-extract), FR-30/FR-31 (token tracking / credit wallet) in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />
**Related Architecture:** AR-6 (auto-extract cost control), AR-5 (cost/turn observability) in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
**Dependency:** Story **8.8** (kill-switch + `MEMORY_AUTO_EXTRACT_ENABLED` global flag + `workspaces.memory_auto_extract_enabled` per-workspace flag) — **DONE**. *(Story này trước đây mang số `8.4a`; epics.md đã đánh lại `8.4a → 8.8` ngày 2026-07-25 theo readiness C-C để hết xung đột với `8-4` trong sprint-status. Mọi tham chiếu "8.4a" ở tài liệu cũ = `8.8` = sprint-status key `8-8-auto-extract-kill-switch-safe-default`.)*

> **Ops framing (đã verify 2026-07-25):** migration 179 (auto-extract) **CHƯA lên production** (`alembic_version=174` trên prod; 175–179 ở branch `develop`). Vì vậy story này là **cổng TRƯỚC KHI merge/bật auto-extract trên prod**, KHÔNG phải sự cố prod đang bleed. Mục tiêu: chi phí per-turn phải **dự đoán được** và **fail-safe** trước khi feature được bật.
>
> Story này là **gate G4** trong `merge-to-prod-checklist.md`. Gate còn mở song song: **G3** = story `3-9` (eval gate). Khuyến nghị vận hành đã ghi ở checklist: deploy với `MEMORY_AUTO_EXTRACT_ENABLED=false`, chỉ bật sau khi G3+G4 xong.

> ## ⛔ ĐỌC TRƯỚC KHI VIẾT CODE: test đã tồn tại và đã pin sẵn contract
>
> **Test scaffolds cho story này ĐÃ được viết và ĐÃ commit** (commit `b6744a1aa`). **KHÔNG viết lại chúng.** Việc của dev là: implement gate → **xoá `@pytest.mark.skip`** trên từng test của task đang làm → làm nó xanh.
>
> - `nowing_backend/tests/unit/memory/test_auto_extract_gate.py` — **12 test**, tất cả đang `skip`
> - `nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py` — **11 test**, tất cả đang `skip`
> - Trạng thái hiện tại: `23 skipped` (đã verify tại `bcc862e66`)
>
> **Các test này import theo tên cụ thể. Implement sai tên = test không chạy được.** Contract bắt buộc:
>
> | Thành phần | Tên chính xác (test đang import) |
> |---|---|
> | Module | `app.services.memory.extract_budget` |
> | Hàm | `async def check_extract_allowed(session, *, workspace, attributed_user_id) -> ExtractGateResult` |
> | Kết quả | `ExtractGateResult` — có `.allowed: bool`, `.reason: str \| None`; khởi tạo được bằng kwargs: `ExtractGateResult(allowed=False, reason="budget_exceeded")` |
> | Seam 1 | `async def _wallet_spendable_micros(session, user_id) -> int` |
> | Seam 2 | `async def _period_spend_micros(session, workspace_id) -> int` |
> | Seam 3 | `async def _rate_count(workspace_id) -> int` |
> | Reason strings | `anonymous_unbilled` · `insufficient_wallet` · `budget_exceeded` · `rate_limited` |
> | Config keys | `MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` · `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` · `MEMORY_AUTO_EXTRACT_RATE_MAX` · `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS` |
>
> **Thứ tự gate bắt buộc (first block wins)** — test `test_gate_reasons_are_stable_identifiers` và các test `_defaults()` phụ thuộc thứ tự này:
> `1. anonymous → 2. wallet < min_reserve → 3. period_spend >= budget → 4. rate_count >= rate_max`
>
> **Cả ba seam là `async def`** (test monkeypatch chúng bằng `async def`), kể cả `_rate_count` dù client Redis bên dưới là sync — bọc lại (hoặc `asyncio.to_thread`).
>
> Ba chi tiết nữa mà test đã khoá:
> - `_wallet_spendable_micros` raise → gate phải trả `allowed=False, reason="insufficient_wallet"` và **không được raise** (`test_gate_fails_closed_on_wallet_check_error`).
> - `budget=0` và `rate_max=0` là **tắt hoàn toàn**, kể cả khi `spent=999_999_999` / `rate=10_000` (`test_gate_budget_disabled_by_default_no_gating`, `test_gate_rate_limit_disabled_by_default`).
> - Ngưỡng là `>=`, không phải `>`: `spent == cap` → block; `rate == max` → block. `spent = cap - 1` → allow.

## Story

As a workspace owner (and platform operator),
I want a spend/budget cap, a wallet pre-check **before** the auto-extract LLM call, and a time-based rate-limit,
So that memory auto-extraction cost is predictable and can never silently drain a workspace's credit wallet when the feature is enabled.

## [BUILT] vs [GAP]

### [BUILT] — verified in code at baseline `bcc862e66`

Line numbers below were re-verified at this baseline. `extraction.py` shifted since the first draft (Story 6.5 appended `flush_pending_memory_changed()` at the tail), so use these, not the older ones.

- **Auto-extract is live and wired per-turn.** `finalize_assistant_message` enqueues `extract_memory_after_chat_turn.delay(message_id)` after every finalized assistant turn, gated by the two flags below. — `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py:153-184`
- **Extraction service.** `MemoryExtractionService.extract_from_turn` loads the assistant+user messages, resolves the workspace, calls the workspace chat model, parses JSON facts, filters by confidence, caps item count, dedupes, persists, records token usage, then flushes `memory.changed` events. — `nowing_backend/app/services/memory/extraction.py:118-306`
- **Constructor.** `MemoryExtractionService(*, session, workspace_id=None, user_id=None)` — all keyword-only, `workspace_id`/`user_id` optional. — `extraction.py:77-86`
- **Global kill-switch (8.8).** `config.MEMORY_AUTO_EXTRACT_ENABLED` (env `MEMORY_AUTO_EXTRACT_ENABLED`, default **ON/"true"**). — `nowing_backend/app/config/__init__.py:607-609`
- **Per-workspace toggle (8.8).** `Workspace.memory_auto_extract_enabled` (default `True`, mig 179). — `nowing_backend/app/db.py:1815-1817`; `alembic/versions/179_add_workspace_memory_auto_extract.py`
- **Item cap + confidence + dedupe (RS-1 item side).** `config.MEMORY_AUTO_EXTRACT_MAX_ITEMS` (default 3, `config/__init__.py:613-615`) + `config.MEMORY_AUTO_EXTRACT_CONFIDENCE` (default 0.7, `config/__init__.py:610-612`); dedupe via `MemoryRepository.create_memory(..., update_on_duplicate=True)`.
- **Cost is tracked (post-hoc).** After the call, `record_token_usage(usage_type="memory_create", workspace_id, user_id, thread_id, ..., cost_micros=...)` writes a `TokenUsage` row inside a `scoped_turn()` accumulator. — `extraction.py:206` (`scoped_turn`), `extraction.py:279-290` (attribution + record), `token_tracking_service.py`
- **Credit wallet + quota primitives exist.** `User.credit_micros_balance` / `User.credit_micros_reserved`; `TokenQuotaService.credit_reserve/credit_finalize/credit_release/credit_get_usage` (`token_quota_service.py:536, 603, 660, 688`) + `estimate_call_reserve_micros` (`token_quota_service.py:36`); `_QUOTA_MIN_RESERVE_MICROS = 100` (`token_quota_service.py:33`). Reserve→finalize→release lifecycle used by chat in `premium_quota.py`.
- **Owner attribution already resolved.** `attributed_user_id = created_by_id or workspace.user_id`, and `record_token_usage` is already skipped when it is `None`. — `extraction.py:279-281`
- **Idempotency + transient retry.** Idempotency guard keyed on `source_type == CHAT_MESSAGE AND source_id == assistant_message_id` (`extraction.py:147-166`); Celery `autoretry_for` transient LLM errors (`memory_extraction_task.py`).
- **Anonymous chat already bypasses the memory stack** at the agent layer (deep-agent/memory middleware disabled for anon). — `app/agents/chat/anonymous_chat/agent.py`
- **A Redis fixed-window rate limiter already exists — reuse this pattern.** `app/capabilities/core/access/rate_limit.py`: lazy `redis.from_url(config.REDIS_APP_URL, decode_responses=True)`, `INCR` + `EXPIRE` on first hit, and an in-memory per-worker fallback when Redis is down. Note it uses the **sync** `redis` client, not `redis.asyncio`.
- **`TokenUsage` shape for the budget SUM.** `workspace_id` (indexed, `nullable=False`), `usage_type` (indexed, `String(50)`), `cost_micros` (`BigInteger`), `created_at` (from `TimestampMixin`), `user_id` (indexed, **`nullable=False`**). Single-column indexes only — **no composite** `(workspace_id, usage_type, created_at)`. — `db.py:1129-1190`
- **Test scaffolds are committed and skip-marked** (see the contract box above). — commit `b6744a1aa`

### [GAP] — to build in this story

1. **No wallet pre-check BEFORE the extraction LLM call.** `extract_from_turn` calls `llm.ainvoke(prompt)` first (`extraction.py:208-211`) and records usage *after* (`extraction.py:281-290`). A workspace owner with `credit_micros_balance <= 0` (or below a minimum reserve) still incurs the extraction LLM cost every turn → **cost bleed**. There is no `credit_*` check on the extraction path.
2. **No spend/budget cap per period.** Nothing aggregates `TokenUsage.cost_micros` for `usage_type="memory_create"` per workspace over a rolling window and compares it to a ceiling. The only cost control is `MAX_ITEMS=3` per turn (item cap, not spend cap).
3. **No time-based rate-limit.** Beyond `MAX_ITEMS=3` *within one turn*, there is no per-workspace throttle across turns (e.g., N extractions per hour). A burst of cheap turns can each trigger an LLM call.
4. **Anonymous-chat attribution is implicit, not enforced.** On the extraction path, an anon turn (no `created_by_id`) falls back to `workspace.user_id`; nothing explicitly *skips* extraction for anonymous turns. Needs an explicit, tested decision (FR-17) so anon turns can never bleed credit against an owner.
5. **New gates must be config-driven and default-safe.** Following the repo's billing convention (`WEB_CRAWL_CREDIT_BILLING_ENABLED`, `PLATFORM_SCRAPE_BILLING_ENABLED` — all default `FALSE`), the budget cap and rate-limit must default to **disabled/unset = no behavior change**; only the wallet pre-check is always-on (skip when the wallet cannot afford a minimum reserve).

## Acceptance Criteria

> ### ⚠️ What the wallet pre-check is, and is not (corrected by code review 2026-07-26)
>
> AC-1 below is an **eligibility** gate: *do not perform optional background work for an owner who cannot pay for their foreground work.* It is **not** a spend meter for extraction, and it cannot bound extraction spend.
>
> The first draft of this story asserted that "*a lightweight pre-check (read spendable balance) + existing post-hoc `record_token_usage` is sufficient*". That rests on a false premise: `record_token_usage` only does `session.add(TokenUsage(...))` (`token_tracking_service.py:524-547`) — it never debits the wallet. Verified during review: `usage_type="memory_create"` appears exactly once in the codebase, and no code under `app/services/memory/` writes to `User.credit_micros_balance`. The wallet-debit callers are `web_crawl_credit_service`, `platform_scrape_credit_service`, `premium_quota.finalize_credit` and `billable_calls` — and `premium_quota.needs_credit_quota()` gates on `agent_config.is_premium`, so for a non-premium workspace model the balance never moves at all.
>
> This is **by design, not a defect**:
> - **AD-8** (`ARCHITECTURE-SPINE.md:110`) enumerates the wallet-debit surface as "ETL/premium model calls trừ qua `wallet_credit.py`" (+ `deep_research` per the 2026-07-25 amendment). Memory extraction is deliberately excluded, as is FR-31's scope ("ETL pages, premium model calls, Stripe, incentive tasks").
> - `usage_type="memory_create"` belongs to **Story 8.9** (DONE), whose AC is "*ghi span + cost … attribute workspace+user*" — an **observability** record feeding SM-C2 / RS-10, not a billing hook.
> - Cost of `billing_tier: "free"` GLOBAL models (platform's own key) is unmetered platform cost by design; no doc in the PRD, epics or spine caps it.
>
> ⇒ **The bounds that actually apply to auto-extract spend are the kill-switch (`MEMORY_AUTO_EXTRACT_ENABLED` / `workspaces.memory_auto_extract_enabled`, Story 8.8) and the opt-in budget cap in AC-2.** That is exactly the containment **G4** prescribes (`merge-to-prod-checklist.md:29`: "*Khuyến nghị: deploy với flag = false trước, chỉ bật sau khi G3+G4 xong*") — G4 requires the cap and pre-check to **exist**, not to be enabled.
>
> **Risk R1 is restated accordingly:** the residual risk is not "cost bleed if shipped without the wallet pre-check" but *"auto-extract enabled on a paid model with `MEMORY_AUTO_EXTRACT_BUDGET_MICROS=0` has no spend ceiling"*. The cap ships at `0` because AD-8's amendment forbids fixing a cost figure before this story and FR-37 produce measured numbers; setting a real default is tracked in `deferred-work.md` and must be coordinated with Story 3-9 re-measuring its SM-10 baseline.

1. **Wallet pre-check before the extraction LLM call** (AR-6, RS-1)
   - **Given** a workspace whose owner wallet spendable balance (`credit_micros_balance - credit_micros_reserved`) is below the required minimum reserve for one extraction call,
   - **When** an assistant turn triggers `MemoryExtractionService.extract_from_turn`,
   - **Then** extraction is skipped **before** any `llm.ainvoke` call, a structured skip is logged (reason=`insufficient_wallet`, `workspace_id`), **no** `memory_create` `TokenUsage` row is written, and **no** `Memory` rows are created (returns `[]`).
   - **And Given** the wallet can afford the minimum reserve, **When** extraction runs, **Then** it proceeds exactly as today (LLM called, qualifying facts persisted, usage recorded).

2. **Per-workspace spend/budget cap over a rolling period** (AR-6, RS-1)
   - **Given** `config.MEMORY_AUTO_EXTRACT_BUDGET_MICROS > 0` and the sum of the workspace's `memory_create` `cost_micros` within the current period window is **>=** the cap,
   - **When** a new turn triggers extraction,
   - **Then** extraction is skipped **before** the LLM call + logged (reason=`budget_exceeded`, `workspace_id`, `spent`, `cap`); no new spend or memories.
   - **And Given** period spend is under the cap, **When** extraction runs, **Then** it proceeds.
   - **And Given** the cap is unset/`0` (**default**), **Then** no budget gating is applied (back-compat).

3. **Time-based rate-limit per workspace** (AR-6, RS-1)
   - **Given** `config.MEMORY_AUTO_EXTRACT_RATE_MAX > 0` per `config.MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS`, and the workspace has already reached that many extractions in the current window,
   - **When** a new turn triggers extraction,
   - **Then** extraction is skipped **before** the LLM call + logged (reason=`rate_limited`, `workspace_id`).
   - **And Given** the workspace is under the limit, **When** extraction runs, **Then** it proceeds and the window counter is incremented.
   - **And Given** the rate-limit is unset/`0` (**default**), **Then** no throttling is applied.

4. **Anonymous-chat attribution edge** (FR-17)
   - **Given** an assistant turn with no resolvable owner/user for billing (anonymous session),
   - **When** auto-extract is considered,
   - **Then** the behavior is explicit and tested: extraction is **skipped** (reason=`anonymous_unbilled`) so no spend is charged against a null/owner, and no `Memory`/`TokenUsage` rows are created.

5. **Kill-switch / flags remain authoritative** (regression — Dep 8.4a)
   - **Given** `MEMORY_AUTO_EXTRACT_ENABLED=False` **or** `workspace.memory_auto_extract_enabled=False`,
   - **When** a turn completes,
   - **Then** no extraction task is enqueued (`assistant_finalize`) **and** `extract_from_turn` returns `[]` without an LLM call. The new gates must not weaken this behavior.

6. **Fail-safe & no-regression defaults** (AR-6)
   - **Given** all new caps/limits at defaults (budget `0`/unset, rate `0`/unset) and a funded wallet,
   - **When** extraction runs, **Then** behavior is identical to baseline (no regression); the only always-on new gate is the wallet pre-check.
   - **And Given** a gate check itself errors (e.g., DB/Redis hiccup), **Then** the failure is contained (never breaks the chat turn) and the documented policy is applied consistently (see Dev Notes → *Fail-open vs fail-closed*).

7. **Enqueue-side short-circuit (defense in depth)** (AR-6)
   - **Given** a workspace that is disabled, over budget, rate-limited, or wallet-insufficient,
   - **When** `finalize_assistant_message` runs,
   - **Then** it avoids enqueueing the Celery task (cheap fast-path), while `extract_from_turn` remains the **authoritative** gate for Celery redelivery/races (so the checks are duplicated on both sides, not moved).

8. **Observability of skips** (AR-5, ties to 8.5)
   - **Given** any skip (wallet / budget / rate / anon / disabled),
   - **Then** a single structured log line with a machine-parseable `reason` and `workspace_id` is emitted, and **no** `memory_create` `TokenUsage` row is written for that turn.

## Tasks / Subtasks

- [x] **Config: new cost-control settings** (AC 2, 3, 6)
  - [x] Add to `nowing_backend/app/config/__init__.py` (near the existing `MEMORY_AUTO_EXTRACT_*` block, lines 606-615), all **default-safe**:
    - `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` (int, default `0` = disabled) — per-workspace spend ceiling per period.
    - `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW` (str/enum, default `"day"`; one of `day`/`week`/`month`) — rolling budget window.
    - `MEMORY_AUTO_EXTRACT_RATE_MAX` (int, default `0` = disabled) — max extractions per window per workspace.
    - `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS` (int, default `3600`).
    - `MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` (int, default `100`, mirrors `_QUOTA_MIN_RESERVE_MICROS`) — minimum spendable balance required to attempt one extraction.
  - [x] Use the existing `_env_int` helper; document each with a comment block like the surrounding billing flags.
- [x] **Gate module: `nowing_backend/app/services/memory/extract_budget.py`** (AC 1, 2, 3, 4, 6, 8)
  - [x] `async def check_extract_allowed(session, *, workspace, attributed_user_id) -> ExtractGateResult` returning `allowed: bool` + `reason: str | None`.
  - [x] Wallet pre-check: read spendable balance for `attributed_user_id`; block when `< MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` (reuse `TokenQuotaService.credit_get_usage` or a direct `select(User.credit_micros_balance, User.credit_micros_reserved)`).
  - [x] Budget check: when `BUDGET_MICROS > 0`, `SELECT COALESCE(SUM(cost_micros),0) FROM token_usage WHERE workspace_id=:ws AND usage_type='memory_create' AND created_at >= :window_start`; block when `>= cap`.
  - [x] Rate check: when `RATE_MAX > 0`, use a Redis fixed-window counter keyed `nowing:memory_extract_rate:{workspace_id}`; block when count `>= RATE_MAX`. Increment only on `allowed` (in the service, after the gate passes).
    - **Copy the pattern from `app/capabilities/core/access/rate_limit.py`** (lazy `redis.from_url(config.REDIS_APP_URL, decode_responses=True)`, `INCR` then `EXPIRE` when count == 1, in-memory fallback on any Redis exception). `token_quota_service.py` contains **no Redis code** — do not look for a counter pattern there.
    - `_rate_count(workspace_id)` must be `async def` (the tests patch it as async) even though the `redis` client is sync.
  - [x] Anonymous check: block (reason=`anonymous_unbilled`) when no owner/user is resolvable for billing.
  - [x] Contain all internal errors → return a single documented verdict (see *Fail-open vs fail-closed*); never raise into the caller.
- [x] **Wire the gate into `MemoryExtractionService.extract_from_turn`** (AC 1, 2, 3, 4, 5, 8)
  - [x] After resolving `workspace` + `created_by_id`/`attributed_user_id` and **before** `get_agent_llm` / `llm.ainvoke` (`extraction.py:189-205`), call `check_extract_allowed(...)`. On block: log structured skip + `return []`.
  - [x] Keep the existing flag check (`extraction.py:142-144`) as-is; the new gate runs after it.
  - [x] Do not write a `memory_create` `TokenUsage` row on skip.
- [x] **Enqueue-side short-circuit in `finalize_assistant_message`** (AC 7)
  - [x] Extend the existing pre-enqueue block (`assistant_finalize.py:150-181`) to also consult `check_extract_allowed(...)` (best-effort) before `.delay(...)`; on block, skip enqueue + log. Keep the authoritative gate in the service.
- [x] **Tests — the scaffolds already exist and are committed; turn them green** (all ACs)
  - [x] **Do not author new files for these.** Remove `@pytest.mark.skip` per test as you activate its task, then make it pass:
    - `nowing_backend/tests/unit/memory/test_auto_extract_gate.py` (12 tests) — gate contract in isolation via the three patched seams.
    - `nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py` (11 tests) — same contract through `extract_from_turn` + the enqueue short-circuit.
  - [x] Final state must be **0 skipped** in these two files; `23 skipped` today means nothing is verified yet.
  - [x] Two integration tests (`test_finalize_skips_enqueue_when_gate_blocks`, `test_finalize_enqueues_when_gate_allows`) currently only assert `hasattr(fin, "finalize_assistant_message")` — they are placeholders. When you un-skip them, **strengthen them** to actually assert on `.delay` being called / not called, otherwise AC-7 stays unverified while looking green.
- [x] **Lint & verify**
  - [x] `uv run --active ruff check --fix nowing_backend/app/services/memory/extract_budget.py nowing_backend/app/services/memory/extraction.py nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py nowing_backend/tests/unit/memory/test_auto_extract_gate.py`
  - [x] `uv run --active python -m pytest tests/integration/memory/test_auto_extract_spend_cap.py tests/unit/memory/test_auto_extract_gate.py -q`
- [x] **Docs / decision log**
  - [x] Record the *fail-open vs fail-closed* decision and the *anonymous = skip* decision in this file's Decisions section and (if applicable) `deferred-work.md`.

### Review Findings

Code review 2026-07-26 (3-layer adversarial: Blind Hunter + Edge Case Hunter + Acceptance Auditor). Baseline `bcc862e66..a60dab746`, scoped to `nowing_backend/`. Independently verified: 12 unit + 11 integration pass, 0 skipped.

**Decisions resolved (Luisphan, 2026-07-26):**

- [x] [Review][Decision] **D1 — Wallet pre-check is an eligibility gate, not a spend meter → resolved as option (c), hardened.** Resolution rationale, grounded in docs read during review: **AD-8** (`ARCHITECTURE-SPINE.md:110`) enumerates the wallet-debit surface as "ETL/premium model calls trừ qua `wallet_credit.py`" (+ `deep_research` per the 2026-07-25 amendment) — memory extraction is deliberately **not** in it, and FR-31 (`prd.md:527`) scopes the wallet to "ETL pages, premium model calls, Stripe, incentive tasks". `usage_type="memory_create"` is owned by **Story 8.9** (DONE) whose AC is "*ghi span + cost … attribute workspace+user*" — a **measurement** mechanism, so `record_token_usage` not debiting is by design, not a bug. Cost of `billing_tier: "free"` GLOBAL models (platform's own key) is unmetered platform cost by design: no doc in PRD/epics/SPINE caps it; it is framed as a measurement problem (SM-C2, RS-10). **G4** (`merge-to-prod-checklist.md:29`) requires the cap + pre-check to **exist**, and prescribes containment via the kill-switch ("*Khuyến nghị: deploy với flag = false trước, chỉ bật sau khi G3+G4 xong*"), not via a non-zero budget. No document anywhere states that auto-extract should debit the wallet. ⇒ Option (a) *debit the wallet* was rejected as contradicting AD-8 and introducing new billing behaviour (charging users for unrequested background work) beyond this story's scope. Option (b) *ship a non-zero budget default* was rejected as contradicting AD-8's amendment ("*không chốt con số pricing/subscription nào trước khi FR-37 và story `8-7` có số đo thật*") — picking a micro-USD figure now is exactly the "cost basis phỏng đoán làm nguồn chân lý" that amendment exists to prevent — and because a `cost_micros`-fed cap cannot bind when pricing is unresolvable (see deferred item). Resulting actions are the three D1 patches below plus one new deferred item.
- [x] [Review][Decision] **D2 — Principal drift between the two gate call sites → resolved as "drop the principal from the enqueue-side check".** Divergence confirmed reachable: `resume_chat` (`new_chat_routes.py:2384`) authorizes at **workspace** level, not thread/author level, so any sufficiently-privileged member can resume a thread whose last user message was authored by someone else. The existing attribution convention is the **message author** (`extraction.py` computed `created_by_id or workspace.user_id` for `record_token_usage`, and Story 8.9's AC attributes to workspace+user), so the authoritative service-side gate is already correct and the enqueue side is the outlier. Option 1 (load `author_id` on the enqueue side too) was rejected: it adds a query on exactly the shielded SSE teardown path that Story 3.14/NFR-1d constrains. Decisive argument for option 3: the enqueue-side wallet fast-path is **net-negative** — it costs a `User` SELECT on 100% of turns inside `anyio.CancelScope(shield=True)` to save one Celery message for the small fraction of owners with an exhausted wallet. Dropping it removes the false-skip class, removes an always-on query from the hot path (which also resolves the deferred "extra per-turn DB work" item and de-risks Story 3.14), and keeps the fast-path for the two workspace-scoped caps (budget + rate) that need no user id. See the D2 patch below.

**Patch (fix is unambiguous):**

- [x] [Review][Patch] **D1a — Re-scope AC-1 and R1 to state what the wallet pre-check actually is** — an *eligibility* gate ("do not perform optional background work for an owner who cannot pay for their foreground work"), **not** a spend meter. Remove the claim that it is "the P0 guard against cost bleed" from the module docstring, since it cannot bound extraction spend. [`extract_budget.py:13-15`, story AC-1 + Risks R1]
- [x] [Review][Patch] **D1b — Correct the false premise in Dev Notes** — "*a lightweight pre-check (read spendable balance) + existing post-hoc `record_token_usage` is sufficient*" assumes `record_token_usage` debits the wallet. It does not; it only does `session.add(TokenUsage(...))` (`token_tracking_service.py:524-547`). State explicitly that extraction spend on platform-key models is unmetered by design per AD-8, bounded operationally by the kill-switch plus the opt-in cap. [story Dev Notes → "Reserve vs post-hoc debit"]
- [x] [Review][Patch] **D1c — Document the 5 new `MEMORY_AUTO_EXTRACT_*` keys in `.env.example`** (promoted from `defer` as part of the D1 resolution) — the opt-in cap is now the only real bound on extraction spend, so a knob that appears in no operator-facing surface means the bound effectively does not exist. [`nowing_backend/.env.example`]
- [x] [Review][Patch] **D2a — Drop the principal from the enqueue-side gate call** — remove the `UUID(str(user_id))` conversion and stop passing `attributed_user_id` from `finalize_assistant_message`; let the enqueue-side consult only the workspace-scoped gates (flag + budget + rate) and leave the wallet/anonymous determination to the authoritative service-side gate. Eliminates the principal-drift false skip, the malformed-`user_id`-becomes-anonymous drop, and the always-on `User` SELECT inside `anyio.CancelScope(shield=True)`. Requires a way to ask the gate for workspace-scoped checks only (e.g. an explicit `skip_wallet_check` flag or a separate `check_workspace_gates`) while keeping `check_extract_allowed`'s pinned signature intact for the service side and Story 3.13. [`assistant_finalize.py:164-184`, `extract_budget.py:167-259`]
- [x] [Review][Patch] AC-8 violated: the `disabled` skip emits no structured `reason` log on either side — `logger.debug("Memory auto-extraction disabled for workspace %s")` has no `reason=` token and is DEBUG-level; the enqueue side returns silently. No `REASON_DISABLED` exists. AC-8 explicitly enumerates `disabled` as one of the 5 skip kinds. [`extraction.py:144`, `assistant_finalize.py:175-179`, `extract_budget.py:60-64`]
- [x] [Review][Patch] `record_extraction` runs unconditionally — no `if config.MEMORY_AUTO_EXTRACT_RATE_MAX > 0` guard, so a Redis `INCR` fires on every extraction even when the rate limit is disabled. Contradicts AC-6 ("behavior identical to baseline at defaults; the only always-on new gate is the wallet pre-check"). [`extraction.py:223`]
- [x] [Review][Patch] Rate counter over-counts on Celery retry — `record_extraction` fires **before** `llm.ainvoke`; `extraction.py:239-256` re-raises the six transient LLM errors that `memory_extraction_task.py:52-63` lists in `autoretry_for` with `max_retries=3`, and the idempotency guard cannot fire (nothing committed). Up to 4 increments per logical turn. Directly contradicts the story's Decisions claim that the increment happens "only after the gate passes AND the turn is actually going to call the LLM". [`extraction.py:223`]
- [x] [Review][Patch] Sync Redis I/O inside `async def`, on the SSE teardown path inside a non-cancellable shield — `_rate_count` and `record_extraction` use the sync `redis` client with no `to_thread` wrap. `check_extract_allowed` is awaited from `assistant_finalize.py:180`, reached from `new_chat/orchestrator.py:824` and `resume_chat/orchestrator.py:593`, both inside `with anyio.CancelScope(shield=True)` in the `finally` of a Starlette SSE generator — i.e. the API event loop, uncancellable. The pinned-contract box required the opposite in the same sentence as the `async def` requirement: "*bọc lại (hoặc `asyncio.to_thread`)*". Reachable only when `RATE_MAX > 0`. Brushes Story 3.14 / NFR-1d. [`extract_budget.py:133-138, 153-160`]
- [x] [Review][Patch] New Redis client + `ConnectionPool` per call, never closed — every other Redis site in the repo caches the client in a module global for exactly this reason (`access/rate_limit.py:26-34`, `gateway/ratelimit.py:52-59`, `utils/indexing_locks.py`, `gateway/thread_lock.py`, `app.py`, `document_tasks.py`). The Task said to copy `rate_limit.py`, whose whole point is the cached client. [`extract_budget.py:136, 156`]
- [x] [Review][Patch] Task claims an in-memory fallback that was not implemented — Task `[x]` says "copy the pattern from `rate_limit.py` (… in-memory fallback on any Redis exception)"; the code returns `0` with a WARNING and has no `_incr_memory` equivalent. Fail-open is a defensible documented choice — the inaccurate checkbox is the defect. Either add the fallback or correct the Task text. [`extract_budget.py:139-143, 161-164`]
- [x] [Review][Patch] `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW` accepted unvalidated — any value that is not exactly `week`/`month` silently falls through to a rolling 24h window, so `BUDGET_WINDOW=monthly` yields a cap 30x tighter than intended with no warning. The sibling `_env_int` helper does log invalid input. Also `month` is hardcoded to 30 days, not a calendar month. [`config/__init__.py:630-632`, `extract_budget.py:95-101`]
- [x] [Review][Patch] `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS <= 0` makes the rate limit a permanent silent no-op — Redis `EXPIRE key 0` deletes the key, so every `INCR` returns 1 and self-destructs. No clamp, unlike `MAX_ITEMS` which uses `max(1, ...)`. [`extract_budget.py:159-160`, `config/__init__.py:637-639`]
- [x] [Review][Patch] `MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS = 0` silently disables the only always-on guard — unclamped, and `_wallet_spendable_micros` returns `max(0, ...)` so `spendable < 0` is unreachable. [`config/__init__.py:621-623`]
- [x] [Review][Patch] `INCR` lands but `EXPIRE` is lost → TTL-less key → workspace throttled permanently — the TTL is set only in the `count == 1` branch. `rate_limit.py` shares the flaw but with a 60s window; here the default window is 3600s and a key that misses its `EXPIRE` never decays at all. Set the TTL unconditionally or use a pipeline/Lua. [`extract_budget.py:157-160`]
- [x] [Review][Patch] An enqueue-side gate *error* permanently drops the work, so the "authoritative" service-side gate never runs — the gate call sits inside the same `try` whose `except Exception: logger.exception("Failed to resolve workspace..."); return`. Any gate failure means no enqueue at all, inverting AC-7's stated defense-in-depth (enqueue = best-effort, service = authoritative). It also logs a message that misdescribes what failed. On gate error the enqueue side should fall through and enqueue. [`assistant_finalize.py:180-192`]
- [x] [Review][Patch] `_wallet_spendable_micros` duplicates `wallet_credit.spendable_micros` with divergent semantics — same columns, same query, but the canonical version raises `ValueError` for a missing user and returns the raw (possibly negative) difference, while the copy returns `0` and clamps with `max(0, ...)`. Two functions named "spendable micros" that answer differently is a future billing bug, and the canonical one is what the credit doors already trust. [`extract_budget.py:68-86` vs `wallet_credit.py:33-48`]
- [x] [Review][Patch] Zero test coverage for every Redis-touching line, the window helper, and the key format — `record_extraction`, `_rate_count`, `_period_window_start` and `_RATE_LIMIT_KEY_PREFIX` appear nowhere under `tests/`. All 12 unit tests stub all three seams; the one rate integration test monkeypatches `_rate_count` too; `RATE_MAX=0` short-circuits the rest. Key format, INCR/EXPIRE, TTL and the fail-open path all ship unexecuted. [`extract_budget.py:118-165`]
- [x] [Review][Patch] `test_gate_reasons_are_stable_identifiers` is near-tautological and is AC-8's only unit test — configures `budget=1`/`spent=1_000` so the correct answer is specifically `budget_exceeded`, then asserts only `reason in allowed_reasons`. Any of the four passes, so a gate-ordering or wrong-reason regression stays green. Asserts nothing about a log line, which is AC-8's actual substance. [`tests/unit/memory/test_auto_extract_gate.py:279-300`]
- [x] [Review][Patch] `test_finalize_skips_enqueue_when_gate_blocks` cannot distinguish "gate blocked" from "block raised" — the gate sits inside `try/except Exception: ...; return`, so a broken import, a changed UUID conversion, or a failing `ws.get` all satisfy `delay.assert_not_called()`. Add a `caplog` assertion that no `logger.exception` fired. (Its companion `test_finalize_enqueues_when_gate_allows` **was** genuinely strengthened, so only half of the spec's placeholder warning was addressed.) [`tests/integration/memory/test_auto_extract_spend_cap.py:402-431`]
- [x] [Review][Patch] The AC-8 integration test asserts less than AC-8 states — checks only that some record contains `insufficient_wallet`; no `workspace_id` assertion, no "single line" assertion, and 1 of the 5 skip kinds AC-8 enumerates. [`tests/integration/memory/test_auto_extract_spend_cap.py:469-490`]
- [x] [Review][Patch] `raising=False` on every `monkeypatch.setattr` makes the suite typo-tolerant — renaming a config key or moving `extract_memory_after_chat_turn` silently creates a phantom attribute and leaves the real value unpatched, at which point `delay.assert_not_called()` passes vacuously. Drop it where the attribute genuinely exists. [`test_auto_extract_gate.py:61-62, 79`; `test_auto_extract_spend_cap.py:214, 241, 251, 262, 380, 412`]
- [x] [Review][Patch] Integration tests depend on ambient env for the thresholds they assert on — the wallet and both `finalize` tests never pin `MIN_RESERVE_MICROS` or `RATE_MAX`, so an operator `.env` can turn the "funded" cases red or make the gate open a real Redis connection from inside the test process. [`tests/integration/memory/test_auto_extract_spend_cap.py:152-196, 402-461`]
- [x] [Review][Patch] `workspace_id = workspace.id` and the config reads sit outside any `try`, contradicting the Decisions claim that "every branch is caught" — benign for today's two callers (both pre-check `workspace is None`), but Story 3.13 must reuse this gate path-agnostically, where a detached/expired ORM `Workspace` would raise `MissingGreenlet`/`DetachedInstanceError` straight into the caller. [`extract_budget.py:178, 214, 237`]
- [x] [Review][Patch] Docstring claims the collaborator needs `.user_id`; the function never reads it — only `workspace.id` is used. Passing the whole ORM entity to extract one integer also forces the Story 3.13 scraper path to materialize a `Workspace` it may not have. [`extract_budget.py:19-20` vs `:178`]
- [x] [Review][Patch] `_period_window_start(now=...)` is a dead seam — the only caller never passes `now`, so the window boundary cannot be pinned in a test, which is presumably why the window mapping has no test at all. [`extract_budget.py:89, 108`]
- [x] [Review][Patch] A comment asserts an invariant that makes the adjacent code provably dead — "created_by_id passed the gate above, so it is not None here" makes the `or workspace.user_id` fallback on the next line unreachable. Drop the fallback or drop the claim; keeping both leaves the next reader unable to tell which invariant is load-bearing. [`extraction.py:301-304`]

**Deferred (real, not actionable in this story):**

- [x] [Review][Defer] Budget cap is fed exclusively by `cost_micros`, which is legitimately `0` whenever pricing cannot be resolved — deferred, pre-existing [`token_tracking_service.py:285-288, 434-441`]
- [x] [Review][Defer] Budget cap and rate counter are read-then-act with no reservation, so concurrent turns overshoot both caps — deferred, explicitly out of scope per Dev Notes "Reserve vs post-hoc debit" [`extract_budget.py:217, 240` vs `extraction.py:223, 306`]
- [x] [Review][Defer] Set a real `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` default once this story yields measured cost/turn numbers — deferred per the D1 resolution: AD-8's amendment forbids chốt a cost figure before `8-7` + FR-37 produce real measurements, so the cap ships at `0`. When the numbers exist, the flip must be coordinated with Story 3-9 re-measuring its SM-10 baseline (this story's Dev Notes freeze the gate defaults as 3-9's input) [`config/__init__.py:626`]
- [x] [Review][Defer] Every chat turn pays a `token_usage` aggregate when the cap is on, inside the shielded SSE teardown — deferred, this is the AC-7 tradeoff the spec deliberately accepted, and the always-on `User` SELECT half is removed by patch D2a; Story 3.14 will re-examine the remainder under NFR-1d [`assistant_finalize.py:177-184`]

### P0 Human Review Findings (2026-08-01)

Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) on the committed `develop` implementation. `59 passed, 0 skipped` before and after fixes.

**Patch findings (fixed in this pass):**

- [x] [Review][Patch] **False `memory_extract_skip` logs on fast-path gate failures** — `_check_budget` and `_check_rate` logged `memory_extract_skip reason=budget_exceeded/rate_limited` when a seam errored during `fail_closed=False` (enqueue path), even though `check_workspace_gates` fell through and enqueued. This contradicted the AC-8 observability contract. Fixed by logging `memory_extract_enqueue_gate_error ... fall_through=true` instead when the enqueue path is uncertain. [`extract_budget.py:281-298, 327-344`]
- [x] [Review][Patch] **Rate counter was sliding, not the documented fixed window** — `_record_extraction_sync` refreshed `EXPIRE` on every `INCR`, and `test_record_extraction_increments_and_refreshes_ttl` encoded the sliding behavior. The story spec and `.env.example` both call it a fixed-window counter, matching `app.capabilities.core.access.rate_limit`. Fixed to set `EXPIRE` only on `count == 1`; renamed the test to `test_record_extraction_increments_and_sets_ttl_on_first` and asserted that later increments do not re-set the TTL. [`extract_budget.py:229-244`, `tests/unit/memory/test_auto_extract_gate.py:369-397`]
- [x] [Review][Patch] **`record_extraction` called before `session.commit()`** — if the DB transaction rolled back after the Redis counter was incremented, Celery retry would burn rate slots for a turn that was never durable. Moved the increment to after `await self.session.commit()` so the counter only counts durable extractions. [`extraction.py:219` → `extraction.py:268`]
- [x] [Review][Patch] **Wallet pre-check docs said "workspace owner" while implementation checks the turn author** — `.env.example` and module docstrings described the pre-check as an owner gate; the code correctly passes `created_by_id` (turn author) per D2. Fixed the docs to say "attributed user" / "turn author". [`.env.example:680-683`, `extract_budget.py:12-14, 142`]
- [x] [Review][Patch] **Redis client had no socket/connect timeout** — a blackholed Redis could hang the worker for the OS default timeout. Added `socket_connect_timeout=5` and `socket_timeout=5` to `redis.from_url` in `extract_budget._redis_client`. [`extract_budget.py:114-119`]

**Deferred findings (pre-existing or out of scope):**

- [x] [Review][Defer] **Budget cap and rate counter are read-then-act with no reservation** — concurrent turns can overshoot both caps. Already deferred in the story Dev Notes "Reserve vs post-hoc debit"; requires an AD-8 amendment and a reservation ledger to fix properly. [`extract_budget.py:217, 240` vs `extraction.py:268`]
- [x] [Review][Defer] **Budget cap under-counts when pricing is unresolvable** — `TokenUsage.cost_micros` can legitimately be `0` for unregistered models. Already deferred; pre-existing token-tracking limitation. [`token_tracking_service.py:285-288, 434-441`]
- [x] [Review][Defer] **Budget aggregate lacks a composite/partial index on `token_usage`** — intentionally shipped without one per Dev Notes; add only if the query shows up hot in production. [`db.py:1125-1190`]

**Dismissed findings (noise, already handled, or out of scope):**

- `Global model catalog refresh / startup pricing registration` concerns raised by the Blind Hunter are not part of Story 8.7; they appear in the diff because the review baseline spanned multiple commits. Track under the relevant global-model/startup stories.
- `In-memory rate fallback is per-process` is documented behavior (`.env.example`) and acceptable for an abuse-guard fallback.
- `Wallet check on turn author` is the documented D2 decision, not a bug.
- `MemoryExtractionService.__init__ still accepts unused user_id` is cosmetic cleanup, deferred as low-priority.

## Dev Notes

### Verified current state (read before editing)

**`extraction.py` — `MemoryExtractionService.extract_from_turn` (line numbers verified at `bcc862e66`):**

| Line | What happens |
|---|---|
| 118 | `async def extract_from_turn(self, thread_id, turn_id, assistant_message_id)` |
| 127-136 | load assistant message → load thread (early `return []` if missing) |
| 139-144 | load `workspace` → **flag check** (`config.MEMORY_AUTO_EXTRACT_ENABLED and workspace.memory_auto_extract_enabled`) |
| 147-166 | **idempotency guard** (`source_type == CHAT_MESSAGE AND source_id == assistant_message_id`) |
| 169-181 | find the paired user message for `turn_id` |
| 183 | `created_by_id = user_message.author_id` ← **gate goes right after this** |
| 185 | `get_agent_llm(...)` ← **gate must be before this** |
| 187-200 | extract text, empty-check, build prompt |
| 206 | `async with scoped_turn() as acc:` |
| 208-211 | **`await asyncio.wait_for(llm.ainvoke(prompt), timeout=...)`** ← the spend |
| 279-290 | `attributed_user_id = created_by_id or workspace.user_id`; `record_token_usage(...)` only when not `None` |
| 297-305 | `await self.session.commit()` then `await repo.flush_pending_memory_changed()` |

- **Insertion point for the gate:** between **line 183** (`created_by_id` resolved) and **line 185** (`get_agent_llm`). Earliest point where `workspace` + `attributed_user_id` are both known and nothing has been spent.
- Compute `attributed_user_id = created_by_id or workspace.user_id` **early** (before the gate) and pass it in; do not wait for line 279.
- **Blocking the gate also suppresses `memory.changed` events for free** — no memories created ⇒ nothing buffered ⇒ `flush_pending_memory_changed()` is never reached. Do not add a separate event suppression path.

**`assistant_finalize.py` — enqueue path (lines verified at `bcc862e66`):**
- Lines **153-173** already open a `shielded_async_session()`, load `Workspace`, and `return` early when the flags are off; lines **175-184** do the `.delay(...)`.
- **Reuse that same `ws` session for the gate call** — the `Workspace` object is already loaded there, so AC-7 costs zero extra sessions and zero extra round trips beyond the gate's own queries. Do not open a second session.
- The whole block is already wrapped in `try/except Exception: logger.exception(...); return` — keep that containment.

**Wallet / quota primitives to reuse (do not reinvent):**
- `TokenQuotaService.credit_get_usage(session, user_id)` → `QuotaResult` with `.balance`, `.reserved`, `.remaining` (micro-USD), where `remaining = max(0, balance - reserved)` is the spendable amount, and a `user is None` miss returns `allowed=False`. — `token_quota_service.py:688-717`
- `estimate_call_reserve_micros(...)` → worst-case micros for one call, clamped to `[_QUOTA_MIN_RESERVE_MICROS, QUOTA_MAX_RESERVE_MICROS]`. Optional; the flat floor `MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` is sufficient for MVP. — `token_quota_service.py:36`
- Billing-flag convention to mirror (default `FALSE`/`0` = free/no-op): `WEB_CRAWL_CREDIT_BILLING_ENABLED`, `PLATFORM_SCRAPE_BILLING_ENABLED` (`config/__init__.py`), and the gate/charge split in `app/capabilities/core/billing.py` (`gate_capability` raises `InsufficientCreditsError`; `charge_capability` = post-hoc debit). Auto-extract is best-effort/background, so it must **skip silently + log**, never raise.
- Redis counter: `app/capabilities/core/access/rate_limit.py` (see [BUILT]). Sync `redis`, fixed window, in-memory fallback.

### Cross-story constraints (new since the first draft — do not break these)

- **Story 3.13 (FR-40, `[GAP — HIGH]`) will add a second extraction path.** Research/scrape runs will produce memories with `source_type = SCRAPER_RUN`, and its AC explicitly requires respecting *"kill-switch `MEMORY_AUTO_EXTRACT_ENABLED` + `workspaces.memory_auto_extract_enabled` (`8-8` done) và spend cap (`8-7`)"*. ⇒ **Keep `check_extract_allowed` path-agnostic.** Its signature already is (`session`, `workspace`, `attributed_user_id` — nothing chat-specific); resist the temptation to pass `thread_id`/`assistant_message_id` into it or to read chat tables inside it.
- **Story 3.14 (NFR-1b/1c/1d, `AD-18`) will assert auto-extract is not on the chat critical path.** Its AC: *"regression test khẳng định nó **không** nằm trên critical path"*. Auto-extract is off-path today only because it runs in Celery. Your AC-7 enqueue-side check runs inside `finalize_assistant_message`, which is post-response in the streaming task — safe — but it must stay **cheap and non-blocking**: reuse the already-open session, and never let it raise into the turn.
- **Story 3-9 (eval gate, G3) measures its SM-10 baseline after auto-extract is frozen.** epics.md: the final baseline is measured *"sau khi 8.4a[=8.8] đông cứng auto-extract"*. So once this story lands, treat the gate's default config as frozen input for 3-9 — flipping `MEMORY_AUTO_EXTRACT_*` defaults afterward invalidates that baseline.

**Period window (budget):** compute `window_start` from `datetime.now(UTC)` per `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW` (`day` = midnight UTC, or rolling `now - 1 day`; pick rolling to avoid a midnight cliff — document the choice). Aggregate over `TokenUsage` filtered by `workspace_id` + `usage_type='memory_create'` + `created_at >= window_start`.

### Design — where each gate lives

```
finalize_assistant_message (assistant_finalize.py:153-184)   [AC7 cheap fast-path]
  ├─ flag check (BUILT, :162-163)                          → return (no enqueue)
  └─ check_extract_allowed(same ws session, best-effort)    → return + log
        │ .delay(message_id)                      (:178)
        ▼
extract_memory_after_chat_turn (celery)  → extract_from_turn (extraction.py:118)
  ├─ flag check (BUILT, :142)                              → return []
  ├─ idempotency guard (BUILT, :147-166)                   → return []
  ├─ created_by_id resolved (:183)
  ├─ check_extract_allowed(AUTHORITATIVE)  [AC1/2/3/4]     → return [] + log
  │     ├─ 1. anonymous?            → block(anonymous_unbilled)
  │     ├─ 2. wallet spendable < min→ block(insufficient_wallet)   ← fail-closed on error
  │     ├─ 3. period spend >= cap   → block(budget_exceeded)
  │     └─ 4. rate count >= max     → block(rate_limited)
  ├─ get_agent_llm (:185) + llm.ainvoke (:208)  ← only if allowed
  ├─ persist qualifying facts
  ├─ rate-counter increment (on allowed)
  ├─ record_token_usage(memory_create) (:281)
  └─ commit + flush_pending_memory_changed() (:297-305)
        └─ blocked gate ⇒ nothing buffered ⇒ no memory.changed events (free)
```

The gate is duplicated on both sides on purpose: the enqueue-side check saves a Celery round-trip in the common case; the service-side check is authoritative because Celery is at-least-once and workspace state can change between enqueue and execution.

### New config (all default-safe)

```python
# Memory auto-extraction cost controls (Story 8.7 / AR-6 / RS-1).
# All default to disabled/no-op so enabling auto-extract introduces no new
# gating until an operator opts in; the wallet pre-check floor is the only
# always-on guard.
MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS = _env_int(
    "MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS", 100
)
MEMORY_AUTO_EXTRACT_BUDGET_MICROS = _env_int("MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 0)
MEMORY_AUTO_EXTRACT_BUDGET_WINDOW = os.getenv(
    "MEMORY_AUTO_EXTRACT_BUDGET_WINDOW", "day"
).strip().lower()
MEMORY_AUTO_EXTRACT_RATE_MAX = _env_int("MEMORY_AUTO_EXTRACT_RATE_MAX", 0)
MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS = _env_int(
    "MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS", 3600
)
```

### Edge cases & decisions

- **Fail-open vs fail-closed (AC 6):** if a gate's own query errors, prefer **fail-closed for the wallet/budget checks** (skip extraction) so an outage can't turn into unbounded spend, and **fail-open only where a miss is harmless**. Whatever is chosen must be applied consistently and covered by a test. Never let a gate error break the chat turn (the turn already succeeded; extraction is best-effort). *(Recommended: fail-closed on wallet + budget errors, since the whole point of 8.7 is bounded cost.)*
- **Anonymous = skip (AC 4):** anon chat already bypasses the memory middleware stack (`anonymous_chat/agent.py`), so in practice anon turns rarely reach here — but the extraction path must **explicitly** skip when no billable owner is resolvable, so a future wiring change can't start charging an owner for anon traffic.
- **Rate-counter increment placement:** increment only after the gate passes and the turn is actually going to call the LLM (inside the service, not the enqueue path) to avoid double-counting the enqueue-side check.
- **Reserve vs post-hoc debit — corrected by code review 2026-07-26:** the chat path uses a full reserve→finalize→release dance (`premium_quota.py`), but only for premium models (`needs_credit_quota()` gates on `agent_config.is_premium`). The extraction path does **neither**: it reads the spendable balance as an eligibility pre-check and then calls `record_token_usage`, which **writes a `TokenUsage` row without debiting the wallet**. The earlier claim that this pairing is "sufficient" was wrong about what `record_token_usage` does; it is nonetheless the **intended** design, because AD-8 excludes memory from the wallet-debit surface and `memory_create` is Story 8.9's observability record. Consequence to hold in mind: extraction spend is **not** metered against the wallet, so the wallet pre-check never self-limits — the ceiling comes from the kill-switch and the opt-in budget cap (AC-2). A full reservation remains out of scope; adding one would be a new billing behaviour requiring an AD-8 amendment, not a story-level change. See the boxed note above AC-1.
- **Budget source of truth:** `TokenUsage` rows with `usage_type="memory_create"` are already written today, so the budget aggregate needs **no new table** — only a `SUM(cost_micros)`. `workspace_id`, `usage_type` and `created_at` each have a single-column index; there is **no composite** `(workspace_id, usage_type, created_at)`. Ship without one (same call as story 8.3, which explicitly deferred a composite index until proven slow) and only add it in a later migration if the query shows up hot.
- **`TokenUsage.user_id` is `nullable=False`**, so an anonymous turn physically cannot get a usage row — which is exactly why AC-4 skips rather than trying to bill a null owner. The existing `if attributed_user_id is not None:` guard at `extraction.py:280` is the current implicit behaviour; AC-4 makes it explicit and tested.
- **No schema migration required** for MVP (config + service logic + `TokenUsage` reads + Redis counter). Confirmed by the readiness report: *"`8.7` không cần schema mới"*.

### Risks

- **R1 — No spend ceiling when auto-extract is enabled on a paid model with the cap at its default.** *(Restated by code review 2026-07-26; the original wording — "cost bleed if shipped without the wallet pre-check" — assumed the wallet meters extraction spend, which it does not. See the boxed note above AC-1.)* The wallet pre-check (AC 1) is an eligibility gate and never self-limits; the only real ceilings are the kill-switch (Story 8.8) and `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` (AC 2), which ships at `0`/disabled per AD-8's no-guessed-cost-figures amendment. Mitigation as shipped is therefore operational, and matches gate **G4**: deploy with `MEMORY_AUTO_EXTRACT_ENABLED=false`, and set a measured budget cap before enabling on a paid model. Tracked in `deferred-work.md`.
- **R2 — Double-gate drift.** Enqueue-side and service-side checks can diverge; keep both calling the *same* `check_extract_allowed` to avoid two code paths.
- **R3 — Redis dependency for rate-limit.** If Redis is unavailable, the rate-limit gate must degrade per the fail-open/closed policy without breaking the turn.
- **R4 — Midnight-cliff on budget window.** A calendar-day window resets abruptly; prefer a rolling window or document the reset behavior.

### ATDD Artifacts

- Checklist: `_bmad-output/test-artifacts/atdd-checklist-8-7-auto-extract-spend-budget-cap.md`
- Integration scaffolds: `nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py`
- Unit scaffolds: `nowing_backend/tests/unit/memory/test_auto_extract_gate.py`

## Decisions

Finalized as implemented in `app/services/memory/extract_budget.py`.

- **Fail-open vs fail-closed (AC 6):** Per-check policy, not one blanket rule.
  - **Wallet check** (`_wallet_spendable_micros` error) → **fail-closed**. Blocks with `reason="insufficient_wallet"`. This is the AR-6 cost-bleed guard; an outage here must never turn into unbounded spend. Covered by `test_gate_fails_closed_on_wallet_check_error`.
  - **Budget check** (`_period_spend_micros` error) → **fail-closed**, same rationale, same reason as its normal block path (`budget_exceeded`), only reached when `MEMORY_AUTO_EXTRACT_BUDGET_MICROS > 0`.
  - **Rate check** (`_rate_count` / Redis error) → **fail-open** at the Redis layer itself: `_rate_count` swallows any Redis exception internally and returns `0` (never blocks), because the rate-limit is an abuse guard, not the cost-bleed guard — an unreachable counter must not stop legitimate extraction. `check_extract_allowed`'s own `try/except` around the rate check is defense-in-depth only, for the case a test or future change substitutes the seam directly with something that raises; the intended path never reaches it since `_rate_count` itself doesn't raise. Only reached when `MEMORY_AUTO_EXTRACT_RATE_MAX > 0`.
  - No gate error ever propagates out of `check_extract_allowed` — every branch is caught before it would raise into `MemoryExtractionService.extract_from_turn` or the enqueue-side check, so a gate failure can never break the chat turn itself.
- **Anonymous = skip (AC 4):** `check_extract_allowed` receives `attributed_user_id=created_by_id` (the turn's author), **not** the `created_by_id or workspace.user_id` fallback used later for token-usage attribution. This is deliberate: passing the fallback would make every anonymous turn silently resolve to the workspace owner and never trigger `anonymous_unbilled`. The gate is checked first with the un-fallen-back value; only once it passes (guaranteeing `created_by_id is not None`) does the fallback apply for billing.

## File List

**New:**
- `nowing_backend/app/services/memory/extract_budget.py` — gate module. Exports `check_extract_allowed`, `ExtractGateResult`, `record_extraction`, and the reason constants (`REASON_ANONYMOUS_UNBILLED`, `REASON_INSUFFICIENT_WALLET`, `REASON_BUDGET_EXCEEDED`, `REASON_RATE_LIMITED`); defines the three seams `_wallet_spendable_micros` / `_period_spend_micros` / `_rate_count` and the rolling-window helper `_period_window_start`.

**Modified:**
- `nowing_backend/app/config/__init__.py` — added the 5 new `MEMORY_AUTO_EXTRACT_*` cost-control settings next to the existing block.
- `nowing_backend/app/services/memory/extraction.py` — import `check_extract_allowed`/`record_extraction`; call the gate right after `created_by_id` is resolved and before `get_agent_llm`; increment the rate counter once the turn is committed to calling the LLM; reused the already-computed `created_by_id` for the later token-usage attribution fallback instead of recomputing it.
- `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py` — enqueue-side short-circuit inside the existing pre-enqueue block, reusing the open `ws` session; converts the incoming `user_id: str | None` to `UUID | None` before passing it to the gate.

**Turned green (un-skipped; not re-authored):**
- `nowing_backend/tests/unit/memory/test_auto_extract_gate.py` — 12 tests, `@pytest.mark.skip` removed from all.
- `nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py` — 11 tests, `@pytest.mark.skip` removed from all; the two AC-7 placeholder tests (`test_finalize_skips_enqueue_when_gate_blocks`, `test_finalize_enqueues_when_gate_allows`) were rewritten from bare `hasattr(...)` assertions into genuine end-to-end calls of `finalize_assistant_message` against a real (transactional, rolled-back) DB session, asserting on `.delay(...)` being called or not.

## References

- Epic/AC source: `_bmad-output/planning-artifacts/epics.md` → "Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit"; "Story 8.4a" (dep); AR-6 / RS-1 in Requirements Inventory.
- Sibling billing pattern: `nowing_backend/app/capabilities/core/billing.py` (`gate_capability`/`charge_capability`), `nowing_backend/tests/unit/capabilities/test_billing.py`.
- Wallet/quota: `nowing_backend/app/services/token_quota_service.py`, `nowing_backend/app/tasks/chat/streaming/flows/shared/premium_quota.py`.
- Existing memory extraction tests: `nowing_backend/tests/integration/memory/test_memory_extraction.py`.

## Change Log

- 2026-07-25: Story drafted (ready-for-dev). Verified [BUILT] vs [GAP] against baseline `8ff548dae`; authored ACs (wallet pre-check, spend cap, rate-limit, anon attribution, kill-switch regression, fail-safe defaults, enqueue short-circuit, observability), tasks, dev notes, and RED-PHASE ATDD scaffolds.
- 2026-07-26: Re-verified against baseline `bcc862e66` and refreshed. Changes:
  - **Added the pinned-contract box.** The ATDD scaffolds are now committed (`b6744a1aa`) and they import exact names — module path, `check_extract_allowed` signature, `ExtractGateResult` fields, the three `async` seams, the 4 reason strings, `>=` threshold semantics, and gate ordering. Implementing different names would leave the tests uncollectable. Also flagged the two placeholder AC-7 tests that need strengthening when un-skipped.
  - **Corrected a wrong pointer:** the previous draft told the dev to copy "Lua counters in `token_quota_service`". That file contains **no Redis code at all**. The real reusable fixed-window limiter is `app/capabilities/core/access/rate_limit.py` (sync `redis` client, `INCR`+`EXPIRE`, in-memory fallback).
  - **Refreshed all line numbers** in `extraction.py` / `assistant_finalize.py` / `config/__init__.py` / `token_quota_service.py`; `extraction.py` shifted when Story 6.5 appended `flush_pending_memory_changed()`. Added a line-by-line table for the hot path.
  - **Renamed the dependency** `8.4a → 8.8` per the epics.md renumbering (readiness C-C), with a note mapping old references.
  - **Added cross-story constraints** absent from the first draft: Story 3.13 will add a second (scrape-run) extraction path that must reuse this gate ⇒ keep it path-agnostic; Story 3.14 will assert auto-extract stays off the chat critical path ⇒ the AC-7 check must reuse the already-open session and stay non-raising; Story 3-9 freezes its SM-10 baseline on this gate's defaults.
  - **Added** the free-suppression note (blocked gate ⇒ no `memory.changed` events, no separate path needed), the `TokenUsage.user_id nullable=False` rationale for AC-4, the missing-composite-index finding, and the G4 merge-gate framing.
- 2026-07-26 (dev-story): Implemented all 8 ACs. Created `app/services/memory/extract_budget.py` with `check_extract_allowed` (4 ordered gates: anonymous → wallet → budget → rate) and `record_extraction` (rate-counter increment). Wired the gate into `extraction.py` between `created_by_id` resolution and `get_agent_llm`, and into `assistant_finalize.py`'s pre-enqueue block (reusing the open session; converts `user_id: str|None` → `UUID|None`). Added the 5 config keys. Turned all 23 committed red-phase tests green (0 skipped) — un-skipped 21 as-is and 2 were fixed during activation, since the placeholder AC-7 tests (`test_finalize_skips_enqueue_when_gate_blocks`/`test_finalize_enqueues_when_gate_allows`) only asserted `hasattr(...)` and were rewritten to genuinely call `finalize_assistant_message` end-to-end. Ruff clean on all touched files. Full regression pass: unit 3404 passed (1 pre-existing unrelated failure in `test_memory.py::test_repository_dedup_updates_existing_memory`, confirmed zero-diff since baseline — Story 6.5 bug, not touched by this story); integration 421 passed (3 pre-existing unrelated failures in `document_upload` PDF/ETL tests, confirmed zero-diff since baseline). No regressions introduced.

## Dev Agent Record

### Agent Model Used

Claude (Kiro dev-story workflow), 2026-07-26.

### Debug Log References

- Verified `redis` is a sync client in `app.capabilities.core.access.rate_limit` (the only existing precedent) before choosing to wrap it the same way in `_rate_count`/`record_extraction`, rather than introducing `redis.asyncio` as a second Redis client style in the codebase.
- During wiring (Task 3), caught and fixed a bug before it reached a test failure: the gate must receive `created_by_id` directly, not the `created_by_id or workspace.user_id` fallback used for later token-usage attribution — passing the fallback would make every anonymous turn silently resolve to the workspace owner and never trigger `anonymous_unbilled`.
- `finalize_assistant_message`'s `user_id` parameter is `str | None` at the call site but the gate/wallet queries need a `UUID`; added a local, best-effort `UUID(str(user_id))` conversion inside the existing `try/except Exception` block so a malformed id degrades to `attributed_user_id=None` (→ `anonymous_unbilled`, safe) rather than raising.
- `pyproject.toml`'s `addopts` includes `-x` (stop on first failure); regression runs needed `-o addopts=""` to see the full picture across the whole suite instead of stopping at the first (unrelated) failure.
- Confirmed both pre-existing regression-suite failures (`test_memory.py::test_repository_dedup_updates_existing_memory`, and 3 tests under `tests/integration/document_upload/`) are unrelated to this story via `git diff --name-only bcc862e66 -- <paths>` returning empty for every file involved in each failure.

### Completion Notes List

- All 8 acceptance criteria implemented and verified by the (already-committed) ATDD test suite: 12 unit tests in `test_auto_extract_gate.py` + 11 integration tests in `test_auto_extract_spend_cap.py`, all passing, 0 skipped.
- Gate ordering matches the pinned contract exactly: anonymous → wallet pre-check → budget cap → rate-limit, first block wins.
- Wallet and budget checks fail-closed on internal error (block extraction); the rate check fails open at the `_rate_count` seam itself (returns `0`, i.e. "not rate-limited") since it is an abuse guard, not the AR-6 cost-bleed guard — see the story's new Decisions section for the full rationale.
- The gate is called from two places using the identical `check_extract_allowed` function (no duplicated logic): the enqueue-side best-effort check in `assistant_finalize.py` (AC 7, saves a Celery round-trip in the common case) and the authoritative check in `extraction.py` (handles Celery at-least-once redelivery / workspace-state races).
- No schema migration was needed — confirmed by design (budget aggregates over the existing `TokenUsage` table; rate-limit uses Redis, not Postgres).
- Full regression suite run with zero net-new failures (see Change Log entry for counts).
- 2026-07-26 (code review, 3-layer adversarial): 30 findings raised, 2 dismissed as noise. **2 decisions resolved + 26 patches applied + 4 deferred.**
  - **D1 (resolved as "correct the framing, not the billing").** The review's headline finding was that the wallet pre-check reads a balance extraction never debits. Confirmed true, but confirmed **by design**: AD-8 enumerates the wallet-debit surface (ETL / premium model calls / deep-research) and excludes memory; `usage_type="memory_create"` is Story 8.9's observability record; free-tier GLOBAL model cost is unmetered platform cost with no documented cap anywhere; and G4 requires the cap + pre-check to *exist*, prescribing the kill-switch as the pre-enable containment. Debiting the wallet (option a) would contradict AD-8 and invent new billing behaviour; shipping a non-zero cap default (option b) would contradict AD-8's amendment forbidding a guessed cost figure before this story produces measurements. So the code's behaviour stands and the **documentation was wrong**: added the boxed note above AC-1, restated Risk R1, corrected the "post-hoc `record_token_usage` is sufficient" premise in Dev Notes, and documented all five keys in `.env.example` (the opt-in cap being the only real bound makes operator discoverability load-bearing). Setting a measured cap default is deferred, coupled to Story 3-9 re-measuring SM-10.
  - **D2 (resolved as "drop the principal from the enqueue-side check").** `resume_chat` authorizes at workspace level, so the streaming caller and the turn's message author can differ, and the enqueue-side gate could permanently drop a turn the authoritative gate would allow. The enqueue-side wallet fast-path was also net-negative: a `User` SELECT on 100% of turns inside `anyio.CancelScope(shield=True)` to save one Celery message for the few owners with an exhausted wallet. Added `check_workspace_gates()` (budget + rate only, never fails closed) for the enqueue side; `check_extract_allowed()` keeps its pinned signature for the service side and Story 3.13.
  - **Correctness patches.** Rate counter moved to *after* a successful `llm.ainvoke` (it previously fired before, so each Celery `autoretry_for` retry re-incremented — up to 4 slots per logical turn, contradicting the story's own Decisions). `record_extraction` now no-ops while `RATE_MAX=0`, restoring AC-6's "identical to baseline at defaults". Enqueue-side gate errors now fall through and enqueue instead of returning, so a fast-path failure can no longer bypass the authoritative gate. Dropped the dead `created_by_id or workspace.user_id` fallback that a comment had already declared unreachable.
  - **AC-8 closed.** `disabled` — one of the five skip kinds AC-8 enumerates — emitted no structured reason on either side (service side logged at DEBUG with no `reason=`; enqueue side was silent). Added `REASON_DISABLED` + `REASON_GATE_ERROR` to the shared vocabulary and a `stage=service|enqueue` discriminator, so every skip is one parseable line that says which gate produced it.
  - **Redis layer rebuilt.** Sync client now cached in a module global (was a fresh `ConnectionPool` per call, leaked, unlike every other Redis site in the repo); sync work off-loaded via `asyncio.to_thread` (the pinned contract asked for this and it had been skipped — a blocking socket read was running on the API event loop inside a non-cancellable shield); per-worker in-memory fallback added as the Task claimed; TTL now refreshed on every `INCR`, not only the first, so a lost `EXPIRE` can no longer leave a TTL-less key throttling a workspace forever.
  - **Config hardening.** New `_env_choice` helper: `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW` was unvalidated, so `monthly` silently meant a 1-day window (a 30x tighter cap). `MIN_RESERVE_MICROS` and `RATE_WINDOW_SECONDS` clamped to `>= 1` (0 disabled the always-on gate / made `EXPIRE 0` delete the key on every increment).
  - **Consistency.** `_wallet_spendable_micros` now delegates to the canonical `wallet_credit.spendable_micros` instead of duplicating the query with divergent missing-user and negative-balance semantics.
  - **Test suite: 23 → 47 tests, still 0 skipped** (unit 12 → 29, integration 11 → 18). `test_gate_reasons_are_stable_identifiers` asserted only `reason in {...}` — any of the four passed, so a gate-ordering regression stayed green; now asserts the exact reason plus a single structured log line. `test_finalize_skips_enqueue_when_gate_blocks` could not distinguish "gate blocked" from "block raised"; now blocks via the budget cap (the enqueue side no longer sees the wallet) and asserts no exception was swallowed. Added coverage for everything that previously shipped unexecuted: the Redis key format, `INCR`/`EXPIRE`/TTL refresh, the in-memory fallback, `record_extraction`'s disabled no-op, `_period_window_start`'s day/week/month mapping, `check_workspace_gates`' principal-free and never-fail-closed contracts, gate containment of a detached `Workspace`, the `disabled` log line, an *enabled* cap with spend under it, and the retry-inflation regression. Dropped blanket `raising=False` from `monkeypatch.setattr` (it made the suite typo-tolerant) and pinned all cost-control settings via an autouse fixture (they had depended on the ambient `.env`).
  - **Verification.** `ruff check` clean on all 7 touched files. Story tests: 29 unit + 18 integration passed, 0 skipped. Full regression: unit **3421 passed / 1 failed**, integration **475 passed / 3 failed** — all 4 failures pre-existing and re-confirmed unrelated: `test_repository_dedup_updates_existing_memory` fails on a `MemoryChangedPayload` `ValidationError` at `repository.py:180` (Story 6.5 bug; `repository.py` is zero-diff from baseline and the test references nothing this story touches), and the 3 `document_upload` tests fail on `assert 'failed' == 'ready'` in local PDF/ETL processing (source zero-diff from baseline). `test_assistant_finalize_citations.py` 7 passed, confirming the `finalize_assistant_message` restructure broke nothing.
  - **⚠️ Gate still open.** Per `_bmad/custom/nowing-quality-pipeline.md`, `bmad-nowing-human-review-gate` (4.13) is the one hard gate and it has **not** run. This diff changes `memory_create` `TokenUsage` attribution and reads the credit wallet, so treat it as credit-adjacent P0 and do not merge on the strength of this review alone. Story 8.7 also remains merge-gate **G4**: deploy with `MEMORY_AUTO_EXTRACT_ENABLED=false` and set a measured `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` before enabling on a paid model.
- 2026-07-26 (test quality review + remediation): ran `bmad-testarch-test-review` (pipeline 4.9) over both story test files with 4 **independent** sub-agent workers, since the tests had been authored by the same session during the code review above and self-assessment would have been worthless. Scored **79/100 (Acceptable)** — determinism 66, isolation 90, maintainability 70, performance 98. Full report: `_bmad-output/test-artifacts/test-reviews/test-review-8-7-auto-extract-spend-budget-cap.md`.
  - **All 17 violations fixed** (3 HIGH, 6 MEDIUM, 8 LOW) plus both adjacent items the review scoped out. A separate verification sub-agent then audited the remediation and confirmed **none regressed**; the 4 items it graded PARTIAL and the 2 new defects it found were also fixed.
  - **The serious one.** Two rate-counter integration tests set `MEMORY_AUTO_EXTRACT_RATE_MAX=5` without stubbing `_rate_count`, so the gate opened a real client against `config.REDIS_APP_URL` and read `nowing:memory_extract_rate:<workspace_id>` — a key nothing seeds or cleans, whose workspace ids restart at 1 each session and collide with any locally running app. They were **passing in CI only because CI has no Redis service**: the read failed, the in-memory fallback returned 0, and the tests went green for a reason nobody asserted. Fixed structurally rather than per-test: new shared double `tests/utils/fake_redis.py` installed by an **autouse** `no_real_redis` fixture in *both* files, so the mistake is no longer reintroducible. `test_extract_skips_when_rate_limited` now seeds the double instead of stubbing the seam, which exercises the real `_rate_count` → key-format → `GET` path for the first time.
  - `monkeypatch.setattr(gate, "_memory_hits", gate._memory_hits)` was a **no-op** — it rebound the attribute to the same object, so the in-memory fallback container was never restored and residue leaked forward. `install_fake_redis` now installs a fresh `defaultdict(list)`.
  - `pinned_gate_config` claimed to pin "every cost-control setting these tests reason about" but omitted `MEMORY_AUTO_EXTRACT_CONFIDENCE`, which is env-overridable to 1.0 while the fixture fact carries 0.95 — an operator value above that would silently empty `extraction.py`'s qualifying filter and turn four "proceeds" assertions red. Now pinned (all 8 `MEMORY_AUTO_EXTRACT_*` keys are), the fact JSON is built from the constant, and a module-level assert fails at collection if the threshold ever exceeds the fact's confidence.
  - **Duplication removed:** wallet funding was copy-pasted 8× (inconsistently — half the sites zeroed `credit_micros_reserved`, half did not), `TokenUsage` seeding 3×, the spy closure 2×. Replaced with `funded_wallet` / `empty_wallet` / `disabled_workspace` / `seed_memory_spend` / `record_extraction_spy` / `_service`. Wallet mutation now lives in exactly two fixtures.
  - **Test ids + priorities:** every test in both files now carries `{EPIC}.{STORY}-{LEVEL}-{SEQ} - P{n}/AC{n}` (29 unit + 18 integration, unique and gap-free). This closes the review's Test-IDs warning and matters for `trace` (4.11), which consumes ids. Previously 16 of 44 docstrings had no priority tag, making `grep P0/` quietly wrong.
  - Also fixed: `_assert_no_swallowed_exception` narrowed to the `assistant_finalize` logger (it had been failing on ambient ERROR from any logger and any test phase) **and** its docstring corrected — it had claimed a crash could yield a false "no task enqueued", which the production code contradicts since an exception falls through and enqueues; four bundled unit tests split/parametrized; the "five skip kinds" docstring corrected (it asserted six constants) and `gate_error` re-attributed to the service-side gate only, since `check_workspace_gates` cannot produce it; `_FACT_CONFIDENCE` dead constant wired up; caplog-scanning idiom collapsed to one helper; `raising=False` gone from every `monkeypatch.setattr`.
  - **Outside the story's own files** (both flagged by the review as adjacent): `tests/integration/memory/conftest.py` set `limiter.enabled = False` at *import* time — an unrestored global leaking to every module in the process — now an autouse fixture; and `pyproject.toml`'s `addopts` `-x` → `--maxfail=5`, so a single red test no longer hides the rest of the matrix (the dev-story notes show `-x` had already forced regression sweeps to run with `-o addopts=""`). The addopts change affects every developer and CI — flagged deliberately.
  - **Verification:** ruff clean; story suite **53 passed, 0 skipped** (up from 47); passes under the project's real `addopts` including `--strict-markers`; `tests/integration/memory` dir 54 passed; full regression unit **3427 passed / 1 failed** and integration **475 passed / 3 failed** — the same 4 pre-existing failures as baseline, re-verified unrelated, with the unit passed count rising by exactly the 6 tests added.
  - **⚠️ Commit note:** `nowing_backend/tests/utils/fake_redis.py` is a **new file** that both test modules import at module scope. A commit staging only the modified files will break collection in both — `git add` it.
- 2026-07-26 (survivor fix, pre-4.10): before running the mutation gate, hand-verified a mutation-testing survivor spotted while scoping the pipeline decision. `MEMORY_AUTO_EXTRACT_RATE_MAX <= 0` mutated to `< 0` in `extract_budget.py:260` left all 53 story tests green — a live survivor on the exact `>=`/`<=` boundary the pinned contract calls out ("ngưỡng là `>=`, không phải `>`"). Root cause: `test_record_extraction_is_noop_when_rate_limit_disabled` asserted only `client.store == {}` / `client.ttls == {}` on the Redis double; with the mutant, `record_extraction` doesn't return early, calls through, the failing Redis client raises, and execution falls to the in-memory fallback — leaving the Redis-side assertions vacuously true while `_memory_hits` was silently mutated. Fixed by adding `assert await _rate_count(7) == 0` after the call, which reads whichever backend the guard actually reached. Verified end to end: reintroduced the identical mutant → new assertion fails (`1 failed, 34 passed`); reverted → `35/35` unit, `53/53` full story suite. Full regression unchanged: unit 3427 passed/1 pre-existing (`test_repository_dedup_updates_existing_memory`, Story 6.5, zero-diff from baseline), ruff clean.
- 2026-07-26 (mutation gate, pipeline 4.10): ran `cosmic-ray` (v8.4.6) against `app/services/memory/extract_budget.py`. Session artifact: `_bmad-output/test-artifacts/mutation-nowing-extract_budget-scoped-20260726T130000Z.sqlite`.
  - **Scoping.** Full-module init produced 304 mutants; local-distributor exec measured ~20-30s/mutant (each mutant re-imports the full app stack), so an unscoped run would cost ~2 hours. Scoped to the 3 functions carrying the pinned-contract thresholds (`_check_budget`, `_check_rate`, `check_extract_allowed`) via a new reusable tool `scripts/scope_mutation_session.py` (marks out-of-scope work items `SKIPPED` in-place using cosmic-ray's own `WorkDB`/`WorkResult` API, no raw SQL). Also skipped `ReplaceBinaryOperator_*`/`ReplaceUnaryOperator_*` mutants within scope: with `from __future__ import annotations`, `int | None`-style hints parse as a BinOp AST node that is never evaluated at runtime, so mutating it is a guaranteed-equivalent mutant, not a test gap. Net: 67 meaningful mutants exec'd (237 skipped).
  - **Result: 54 killed / 13 survived on first pass (80.6%).** Full regression while triaging: unit 3427/1 pre-existing, integration 475/3 pre-existing (both re-confirmed as before) — the gate itself does not regress anything, it only adds tests.
  - **Triage of the 13 survivors** (per `docs/nowing-mutation-gate-reference.md`'s triage matrix; this file is not in the P0-surface list, so severity is capped at P1/WARN regardless, but each was fixed anyway since the pinned contract explicitly calls out `>=`/`<=` direction):
    - **11 real gaps, closed with 5 new unit tests** (`8.7-UNIT-030`..`034`, added to `tests/unit/memory/test_auto_extract_gate.py`):
      - `test_gate_treats_a_negative_cap_as_disabled` (parametrized over budget+rate) — `<=` mutated to `==` survived because no existing test used a *negative* config value; `==0` and `<=0` agree on every value the suite exercised (0, and positive numbers).
      - `test_gate_enabled_rate_max_of_one_blocks_at_the_threshold` — `<= 0` mutated to `<= 1` survived because no test set `RATE_MAX=1` specifically; the mutant would treat the smallest *enabled* rate limit as disabled.
      - `test_gate_blocks_when_rate_strictly_exceeds_max` — `rate >= rate_max` mutated to `== ` and to `is` both survived because the existing at-the-boundary test (`rate == rate_max`) can't distinguish `>=` from `==`/`is` there; only a rate *strictly above* the max does.
      - `test_gate_fails_closed_on_rate_check_error` — the rate branch's fail-closed logic (`ExceptionReplacer`, `AddNot` on `fail_closed`, `allowed=False`->`True`, and the `fail_closed=True`->`False` argument at the call site) had no direct test; the analogous budget-branch test existed but nothing exercised `_check_rate` raising through `check_extract_allowed`.
      - `test_gate_contains_an_error_raised_by_check_budget_itself` — `check_extract_allowed`'s own outer `except Exception`/`allowed=False`->`True` had no test where the *whole helper* raises (as opposed to a seam one level down, which `_check_budget`'s own try/except catches first).
    - **2 equivalent mutants, no test needed:** both `ReplaceTrueWithFalse` on `exc_info=True` (lines 369, 424) only toggle whether a logged warning attaches a traceback — no return value, message content, or control flow depends on it. Verified by re-deriving each with `cosmic-ray apply` and confirming the full suite still passes with the mutant in place (not just asserting it by inspection).
  - **Verification.** All 13 survivor mutations individually re-derived via `cosmic-ray apply <module> <operator> <occurrence>` (not by hand-editing) and re-tested one at a time against a from-disk backup, restoring after each — confirmed **11/13 now KILLED**, 2 confirmed equivalent. `ruff` clean. Story suite **59 passed, 0 skipped** (up from 53). Full regression re-run after the fix: unit **3433 passed / 1 pre-existing failed**, integration **475 passed / 3 pre-existing failed** — same 4 failures as every prior baseline in this story, unit passed count up by exactly the 6 tests added (one test is parametrized ×2).
  - **Process note (no code impact, recorded for the record):** while manually re-deriving survivors, a `git checkout -- <module>` used as a "revert this probe mutation" step reverted the file all the way to the pre-code-review git HEAD, wiping every uncommitted patch from this story's code review and test review passes in one shot (git HEAD predates them; nothing in this story had been committed). Caught by a post-step assertion, recovered from an in-memory/on-disk backup taken before mutation probing began, and re-verified byte-identical to the pre-probe file before re-running the full suite. **No source or test change from earlier in this story was lost**, but it is the reason this story's history has no unstaged commits: **commit the working tree after every review-and-fix pass, before running any tool that touches files on disk** (cosmic-ray, `git checkout`, etc.).
- 2026-08-01 (P0 human-review gate): re-ran 3-layer adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) on the committed `develop` implementation. Fixed 5 unambiguous patch findings: false `memory_extract_skip` logs on the enqueue fast-path, rate counter fixed-window semantics, `record_extraction` moved after `session.commit`, wallet pre-check docs aligned to turn-author attribution, and Redis socket/connect timeouts. Rejected/dismissed global-catalog concerns as out of scope. Re-affirmed 3 deferred items (concurrency reservations, unresolved pricing under-count, optional composite index). All 59 story tests pass, ruff clean. Status moved from `review` to `done` in `sprint-status.yaml`.
