# Story 8.7 Acceptance Audit — Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit

**Auditor:** Acceptance Auditor layer (code-review)  
**Scope:** `nowing_backend/app/services/memory/extract_budget.py`, `extraction.py`, `assistant_finalize.py`, `app/config/__init__.py`, `.env.example`, `app/db.py`, plus test files.  
**Baseline inspected:** Current working tree at `/Users/luisphan/Documents/GitHub/nowing` (clean `git status`).  
**Diff inspected:** `_bmad-output/implementation-artifacts/8-7-review-diff.patch`.  
**Story spec:** `_bmad-output/implementation-artifacts/8-7-auto-extract-spend-budget-cap.md`.

---

## Executive Verdict

**Overall: PASS with one documented design deviation (AC-7 / D2).**

All eight acceptance criteria are satisfied by the code as implemented, and the full relevant test suite passes with no skips. The only material deviation from the literal story wording is AC-7: the enqueue-side fast-path deliberately **does not** evaluate the wallet or anonymous checks (per Decision D2a), so it will not skip enqueue for a wallet-insufficient workspace. This is explicitly documented, tested, and leaves the authoritative service-side gate to make that call.

### Test Run Summary

```bash
cd nowing_backend
uv run --active python -m pytest tests/unit/memory/test_auto_extract_gate.py tests/integration/memory/test_auto_extract_spend_cap.py -q
```

Result:

```text
59 passed, 13 warnings in 2.60s
0 skipped
```

```bash
uv run --active ruff check nowing_backend/app/services/memory/extract_budget.py \
  nowing_backend/app/services/memory/extraction.py \
  nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py \
  nowing_backend/tests/unit/memory/test_auto_extract_gate.py
```

Result: `All checks passed!`

---

## AC-1 — Wallet pre-check before extraction LLM call; anonymous skip; order of gates

**Verdict: PASS**

### Evidence

- `MemoryExtractionService.extract_from_turn` resolves `created_by_id` from the user message (`nowing_backend/app/services/memory/extraction.py:160`), then calls `check_extract_allowed` **before** `get_agent_llm` and the `invoke_extraction_llm` call (`extraction.py:172-177`, `extraction.py:178`, `extraction.py:203`).
- The gate order is hard-coded and first-block-wins in `check_extract_allowed` (`nowing_backend/app/services/memory/extract_budget.py:373-418`):
  1. `attributed_user_id is None` → `anonymous_unbilled` (`extract_budget.py:375-381`).
  2. Wallet spendable `< MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` → `insufficient_wallet` (`extract_budget.py:386-406`).
  3. Budget `spent >= cap` → `budget_exceeded` (`extract_budget.py:408-413`).
  4. Rate `count >= max` → `rate_limited` (`extract_budget.py:415-418`).
- The chat path passes `attributed_user_id=created_by_id` (the turn author) **without** the `workspace.user_id` fallback, so anonymous turns stay anonymous (`extraction.py:173`; see also AC-4).
- On any block, `extract_from_turn` returns `[]` immediately and never reaches `invoke_extraction_llm` or `record_token_usage` (`extraction.py:175-176`).

### Tests

- Unit: `8.7-UNIT-001`, `8.7-UNIT-002` (wallet boundary), `8.7-UNIT-016` (anonymous order), `8.7-UNIT-018` (wallet seam error fail-closed).
- Integration: `8.7-INT-001` (empty wallet → no LLM, no usage, no memories), `8.7-INT-002` (funded wallet proceeds).

### Deviation / Note

The wallet pre-check is performed on the **message author's** wallet (`attributed_user_id=created_by_id`), not a hard-coded workspace-owner wallet. This is the deliberate decision in the story's Decisions section (anonymous-skip / D2), matches the pinned function contract `check_extract_allowed(session, *, workspace, attributed_user_id)`, and is covered by tests. The AC-1 prose says "owner wallet" but the implementation is more precise: it checks the wallet of the user the extraction cost will be attributed to.

---

## AC-2 — Per-workspace spend/budget cap with rolling window; disabled when 0

**Verdict: PASS**

### Evidence

- Config keys exist in `nowing_backend/app/config/__init__.py:704-714`:
  - `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` (default `0`)
  - `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW` (default `day`, validated via `_env_choice`).
- `_period_window_start` computes rolling lookbacks (`nowing_backend/app/services/memory/extract_budget.py:164-179`):
  - `day` → `now - timedelta(days=1)`
  - `week` → `now - timedelta(weeks=1)`
  - `month` → `now - timedelta(days=30)`
- `_period_spend_micros` aggregates `TokenUsage.cost_micros` for `usage_type='memory_create'` and `workspace_id` within the window (`extract_budget.py:182-194`).
- `_check_budget` short-circuits when `budget_cap <= 0` (`extract_budget.py:275-277`) and blocks when `spent >= budget_cap` (`extract_budget.py:294`).

### Tests

- Unit: `8.7-UNIT-005` (>= cap blocks), `8.7-UNIT-006` (under cap allows), `8.7-UNIT-007` (cap `0` disables), `8.7-UNIT-008` (rolling window mapping).
- Integration: `8.7-INT-003` (workspace over budget → skip, no new spend), `8.7-INT-004` (under enabled budget proceeds), `8.7-INT-005` (default budget = baseline).

### Deviation

None.

---

## AC-3 — Time-based rate-limit per workspace; disabled when 0; threshold `>=`

**Verdict: PASS**

### Evidence

- Config keys in `nowing_backend/app/config/__init__.py:715-722`:
  - `MEMORY_AUTO_EXTRACT_RATE_MAX` (default `0`)
  - `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS` (default `3600`, clamped `>= 1`)
- `_check_rate` short-circuits when `rate_max <= 0` (`extract_budget.py:315-317`) and blocks when `rate >= rate_max` (`extract_budget.py:334`).
- `_rate_count` reads the Redis key `nowing:memory_extract_rate:{workspace_id}` (`extract_budget.py:118-119`, `extract_budget.py:197-226`) and falls back to a per-worker in-memory window on any Redis exception.
- `record_extraction` increments the counter **only after** the LLM call succeeds and **only when** `MEMORY_AUTO_EXTRACT_RATE_MAX > 0` (`extract_budget.py:247-262`). The TTL is refreshed on **every** increment (`extract_budget.py:234`), not only the first.
- `_rate_count` and `record_extraction` are wrapped in `asyncio.to_thread` so the sync Redis client does not block the API event loop (`extract_budget.py:226`, `extract_budget.py:262`).

### Tests

- Unit: `8.7-UNIT-009` (>= max blocks), `8.7-UNIT-010` (under allows), `8.7-UNIT-011` (rate `0` disables), `8.7-UNIT-012` (Redis key format), `8.7-UNIT-013` (TTL refresh), `8.7-UNIT-014` (disabled = no Redis traffic), `8.7-UNIT-015` (in-memory fallback), `8.7-UNIT-031` (`rate_max=1` is enabled), `8.7-UNIT-032` (strictly over max), `8.7-UNIT-033` (rate seam error fail-closed).
- Integration: `8.7-INT-006` (rate-limited → skip), `8.7-INT-007` (failed LLM does not burn slots), `8.7-INT-008` (success increments exactly once).

### Deviation

None.

---

## AC-4 — Config-driven and default-safe; env var names and defaults; clamping

**Verdict: PASS**

### Evidence

All five new settings are in `nowing_backend/app/config/__init__.py:686-722`:

| Env var | Default | Clamping / validation |
|---|---|---|
| `MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS` | `100` | `max(1, ...)` — cannot be `0` or negative. |
| `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` | `0` | `0`/`negative` = disabled. |
| `MEMORY_AUTO_EXTRACT_BUDGET_WINDOW` | `day` | `_env_choice(..., ("day", "week", "month"))`; unknown values warn and fall back to `day`. |
| `MEMORY_AUTO_EXTRACT_RATE_MAX` | `0` | `0`/`negative` = disabled. |
| `MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS` | `3600` | `max(1, ...)` — prevents Redis `EXPIRE 0` from silently deleting the key. |

- `_env_choice` helper logs a warning and uses the default for invalid enum values (`app/config/__init__.py:54-76`).
- `.env.example` documents every new variable, its semantics, and the default-safe design (`nowing_backend/.env.example:648-701`).

### Tests

- Unit: `8.7-UNIT-030` (negative caps treated as disabled), `8.7-UNIT-008` (window mapping with fallback).
- Integration: `pinned_gate_config` autouse fixture pins all values in `test_auto_extract_spend_cap.py:79-102`.

### Deviation

None. The shipped defaults match the repo's billing-flag convention (`0`/`unset` = disabled).

---

## AC-5 — Cost still tracked post-hoc without debiting wallet

**Verdict: PASS**

### Evidence

- On the success path, `extract_from_turn` still calls `record_token_usage` with `usage_type="memory_create"` (`extraction.py:254-264`).
- `record_token_usage` in `app/services/token_tracking_service.py:503-554` only does `session.add(TokenUsage(...))`; it never updates `User.credit_micros_balance`.
- `apply_debit` in `app/services/wallet_credit.py:73-104` (the actual wallet-debit primitive) is **not** called anywhere in the extraction path.
- When the gate blocks, `extract_from_turn` returns `[]` before `record_token_usage` is reached, so no `memory_create` row is written on a skip (`extraction.py:175-176`).

### Tests

- Integration: `8.7-INT-001` (wallet skip → `memory_create` count `0`), `8.7-INT-002` (proceeds → exactly one `memory_create` row).

### Deviation

None. This is the corrected D1 understanding: the wallet pre-check is an eligibility gate, not a spend meter, because extraction is deliberately excluded from the AD-8 wallet-debit surface.

---

## AC-6 — Fail-closed behavior; `gate_error`; unreadable workspace

**Verdict: PASS**

### Evidence

- `check_extract_allowed` is fully contained (`extract_budget.py:347-428`):
  - `workspace.id` access is wrapped and returns `gate_error` on any exception (`extract_budget.py:361-371`).
  - Wallet-seam error returns `insufficient_wallet` (`extract_budget.py:386-395`).
  - `_check_budget` is called with `fail_closed=True` in the service gate and returns `budget_exceeded` on query failure (`extract_budget.py:408-413`, `extract_budget.py:565-592`).
  - `_check_rate` is called with `fail_closed=True` and returns `rate_limited` on seam failure (`extract_budget.py:415-418`, `extract_budget.py:607-632`).
  - A final outer `except Exception` returns `gate_error` (`extract_budget.py:419-426`).
- `check_workspace_gates` (the enqueue fast-path) is called with `fail_closed=False` and catches all exceptions, falling through to `allowed=True` (`extract_budget.py:431-460`).

### Tests

- Unit: `8.7-UNIT-018/019/033` (seam errors), `8.7-UNIT-034` (outer catch-all), `8.7-UNIT-021` (unreadable workspace), `8.7-UNIT-025/026` (enqueue never fails closed).
- Integration: `8.7-INT-015` (fast-path error still enqueues).

### Deviation

None. The rate-limit itself is intentionally fail-open at the Redis layer (abuse guard, not cost guard), while the authoritative service-side gate is fail-closed for budget/wallet and has `gate_error` as a final containment verdict.

---

## AC-7 — Enqueue-side workspace-scoped gates never fail closed; no user/wallet lookup

**Verdict: PASS with design deviation**

### Evidence

- `finalize_assistant_message` uses `check_workspace_gates` (budget + rate only) inside the existing pre-enqueue block (`nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py:171-200`).
- It does **not** look up a `User` or call `_wallet_spendable_micros`; `user_id` from the streaming caller is not passed into the gate.
- The whole block is wrapped in `try/except Exception`; on any internal failure it logs and falls through to enqueue (`assistant_finalize.py:201-211`).
- On `skip_enqueue=True` (workspace missing, kill-switch disabled, over budget, or rate-limited) the task is not enqueued (`assistant_finalize.py:213-214`).

### Tests

- Unit: `8.7-UNIT-022` (no wallet lookup), `8.7-UNIT-023/024` (budget/rate still enforced), `8.7-UNIT-025/026` (never fail closed).
- Integration: `8.7-INT-012` (over-budget → no enqueue), `8.7-INT-013` (allowed → exactly one enqueue), `8.7-INT-014` (empty owner wallet **still enqueues**), `8.7-INT-015` (pre-check error still enqueues).

### Deviation

The literal AC-7 in the story says the enqueue side should avoid enqueueing when the workspace is "disabled, over budget, rate-limited, **or wallet-insufficient**". The implemented fast-path evaluates only the workspace-scoped caps (budget, rate) and the kill-switch, **not** the wallet. This is the documented Decision D2a: the streaming caller is not guaranteed to be the turn's message author, so a wallet verdict at enqueue could incorrectly drop a turn the authoritative service-side gate would allow, and it would add a per-turn `User` lookup to the shielded SSE teardown path. The authoritative `extract_from_turn` re-checks the wallet later. This deviation is covered by `8.7-INT-014`.

---

## AC-8 — Machine-parseable reason strings and logging

**Verdict: PASS**

### Evidence

- All required reason strings exist as module constants in `extract_budget.py:88-93`:
  - `REASON_ANONYMOUS_UNBILLED = "anonymous_unbilled"`
  - `REASON_INSUFFICIENT_WALLET = "insufficient_wallet"`
  - `REASON_BUDGET_EXCEEDED = "budget_exceeded"`
  - `REASON_RATE_LIMITED = "rate_limited"`
- The module also exports `REASON_DISABLED` and `REASON_GATE_ERROR` so all skip kinds share one vocabulary (`extract_budget.py:92-93`, `__all__` lines 463-473).
- Every block emits a single structured `memory_extract_skip` log line containing `reason=...` and `workspace_id=...`:
  - Anonymous: `extract_budget.py:376-380`
  - Wallet: `extract_budget.py:397-405`
  - Budget: `extract_budget.py:596-602`
  - Rate: `extract_budget.py:635-643`
- `extract_from_turn` logs `reason=disabled` when the kill-switch is off (`extraction.py:116-120`).
- `assistant_finalize.py` logs `reason=disabled` and lets `check_workspace_gates` log its own `reason` for budget/rate (`assistant_finalize.py:193-197`).

### Tests

- Unit: `8.7-UNIT-027` (vocabulary), `8.7-UNIT-028` (single line with `reason=`, `workspace_id=`, `spent=`, `cap=`), `8.7-UNIT-029` (all four block reasons logged once).
- Integration: `8.7-INT-017` (wallet skip log + no usage), `8.7-INT-018` (disabled skip log).

### Deviation

None.

---

## Summary of Changes Made (from diff inspection)

- **New module** `nowing_backend/app/services/memory/extract_budget.py`: gate module with `check_extract_allowed`, `check_workspace_gates`, `record_extraction`, `ExtractGateResult`, reason constants, and the three monkeypatchable seams.
- **Modified** `nowing_backend/app/services/memory/extraction.py`:
  - Removed inline LLM invocation / parsing logic; now imports from the shared `app/services/memory/pipeline.py`.
  - Calls `check_extract_allowed` after resolving `created_by_id` and before the LLM call.
  - Calls `record_extraction` only after a successful LLM invocation.
  - Uses `created_by_id` directly for `record_token_usage` (no owner fallback, preserving AC-4).
- **Modified** `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`:
  - Principal-free enqueue fast-path using `check_workspace_gates`.
  - Logs `reason=disabled` for kill-switch and falls through (not raises) on fast-path errors.
- **Modified** `nowing_backend/app/config/__init__.py`:
  - Added `_env_choice` helper and the five `MEMORY_AUTO_EXTRACT_*` cost-control settings with safe defaults and clamping.
- **Modified** `nowing_backend/.env.example`:
  - Added the Story 8.8 / 8.7 documentation block.
- **Tests un-skipped and strengthened**:
  - `nowing_backend/tests/unit/memory/test_auto_extract_gate.py` and `nowing_backend/tests/integration/memory/test_auto_extract_spend_cap.py` together contain 59 test items, all green (some via `@pytest.mark.parametrize`).

---

## Known Limitations / Follow-ups

1. **Wallet pre-check is on the turn author, not the workspace owner.** This is the intended design (D2 / anonymous-skip decision) and matches the pinned contract, but it means a member-authored turn is gated by the member's wallet, not the owner's. Consider whether the AC-1 prose should be tightened.
2. **Budget cap is fed by `TokenUsage.cost_micros`, which may legitimately be `0`** when pricing is unresolvable. This is a pre-existing deferred item, not a regression introduced here.
3. **Budget cap and rate counter are read-then-act without reservation**, so concurrent turns can overshoot both caps. Also deferred/explicitly out of scope per the story's Dev Notes.
4. **`MemoryExtractionService.__init__` still accepts `user_id`** but it is no longer used in `extract_from_turn`; it could be removed or deprecated in a cleanup pass.

---

## Final Sign-off

All acceptance criteria are implemented and verified by the relevant test suite. The implementation is safe to merge **provided the D2 deviation (enqueue side does not block on wallet) is accepted** by the product owner / code review. The recommended operational posture — deploy with `MEMORY_AUTO_EXTRACT_ENABLED=false` and set a measured `MEMORY_AUTO_EXTRACT_BUDGET_MICROS` before enabling — is preserved.
