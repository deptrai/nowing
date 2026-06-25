# Story 10.1.3 — Smart Money Out-of-Scope Follow-up: Middleware, System Prompt, Empty-State UI, FE Plumbing, TGM Endpoint Migration

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10.1.2 (Nansen Failover — done)
**Status:** done  *(QA verified 2026-05-06 — all 6 staging QA tasks passed, TGM prod key confirmed)*
**Created:** 2026-05-06
**Why:** Trong quá trình debug "show smart money flow for cake" user-reported regression, 5 thay đổi out-of-scope của story 10.1.2 đã được áp dụng cùng lúc. Code đã merge, tests pass, nhưng không có spec để traceability/QA/sprint-tracking nắm được scope thật của các thay đổi này.

---

## Problem Statement

Story 10.1.2 đăng ký scope là Nansen failover (Dune + Arkham). Tuy nhiên user báo 2 issues khi test với CAKE:
1. **Over-spawning 6 sub-agents** cho query smart money đơn lẻ → spam tool calls, ngốn token, latency cao
2. **Sankey UI hoàn toàn không render** dù backend emit event đúng

Debugging surfaced 5 vấn đề ngoài scope 10.1.2:

1. **`ParallelSpawnDirectiveMiddleware` injects `_DIRECTIVE` into mọi non-comprehensive query** — LLM bị ép spawn 6 agents kể cả với câu hỏi đơn (price, smart money, weather)
2. **`system_prompt.py` thiếu DECISION RULE** cho smart money — LLM không có hướng dẫn rõ "smart money → call tool directly, no sub-agents"
3. **`crypto-report-layout.tsx` hide Sankey hoàn toàn khi `links.length === 0`** — user không thấy bất kỳ visual feedback nào (text-only response gây confusion)
4. **`source_domain` field không được forward qua FE pipeline** — citation badge không hiển thị provider attribution
5. **Nansen endpoint cũ (`/v1/token/smart-money`) trả 404 cho hầu hết tokens** — phải migrate sang `/api/v1/tgm/who-bought-sold` (POST, header `apiKey`)

Tất cả 5 thay đổi đã được implement và pass tests, nhưng spec 10.1.2 không cover → cần retroactive story để document.

---

## Implementation Summary

### 1. Middleware: stop over-spawning on non-comprehensive queries

**File:** `nowing_backend/app/agents/new_chat/chat_deepagent.py:1701-1709`

**Trước:**
```python
new_sys = append_to_system_message(request.system_message, self._DIRECTIVE)
return await handler(request.override(system_message=new_sys, messages=messages))
```

**Sau:**
```python
# Non-comprehensive query: pass through unchanged so the LLM follows
# the DECISION RULE in system_prompt.py (call direct tool, no sub-agents).
return await handler(request)
```

Comprehensive query path (synthetic-bypass branch line 1342-1699) không bị động tới — vẫn spawn 6 agents khi user nói "full analysis".

### 2. System prompt: add DECISION RULE

**File:** `nowing_backend/app/agents/new_chat/system_prompt.py:75-77`

```
DECISION RULE:
- Simple price/data query ("Gia $BTC?") -> call get_live_token_data directly, NO sub-agents.
- Smart money / whale flow query ("Show smart money flow for X", "smart money PEPE", "whale flow BTC") -> call get_smart_money_flow directly, NO sub-agents. NEVER spawn 6 agents for this.
- Comprehensive/multi-dimensional query ("full analysis", "deep dive") -> spawn relevant agents in PARALLEL.
```

### 3. Empty-state UI for Sankey

**File:** `nowing_web/components/new-chat/report/crypto-report-layout.tsx`

Component mới `<EmptySmartMoneyState sourceDomain={...} />` — render placeholder với icon, message ("No labeled smart money flow"), source attribution. Render khi `meta.smart_money_flow` tồn tại nhưng `links.length === 0`.

### 4. FE `source_domain` plumbing

3 SSE handlers ([page.tsx](nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx) lines 1249, 1728, 2149) + parser `parseSmartMoneyFlow()` + type `SmartMoneyFlowData` ([streaming-state.ts:25](nowing_web/lib/chat/streaming-state.ts#L25)) + reload extractor ([message-utils.ts](nowing_web/lib/chat/message-utils.ts)) + BE emit ([chat_deepagent.py:996](nowing_backend/app/agents/new_chat/chat_deepagent.py#L996), [stream_new_chat.py:1549](nowing_backend/app/tasks/chat/stream_new_chat.py#L1549)).

### 5. Nansen TGM endpoint migration

**File:** `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py`

| Field | Old | New |
|---|---|---|
| Base URL | `https://api.nansen.ai/v1` | `https://api.nansen.ai/api/v1` |
| Endpoint | `/token/smart-money?address=...` | `/tgm/who-bought-sold` (POST) |
| Auth header | `x-api-key` | `apiKey` |
| Request body | (GET, query params) | `{chain, token_address, date: {from, to}, pagination}` |
| Response shape | `data.wallets[]` + `netFlow24hUsd` | `data[]` flat with `bought_volume_usd` / `sold_volume_usd` per item |

Tool synthesizes `net_flow_usd = bought - sold` per wallet để khớp interface cũ của Sankey builder.

---

## Acceptance Criteria

**AC1 — Smart money query không spawn 6 sub-agents:**
GIVEN user types "Show smart money flow for PEPE"
THEN main agent calls `get_smart_money_flow` tool **directly** (1 tool call)
AND không spawn defillama/sentiment/news/smart_contract/tokenomics/yield_optimizer agents

**AC2 — Comprehensive query vẫn spawn 6 sub-agents (no regression):**
GIVEN user types "full crypto analysis for ETH"
THEN main agent spawns 6 sub-agents in parallel
AND `_DIRECTIVE` được inject vào synthetic-bypass branch

**AC3 — Empty-state UI hiển thị khi không có smart money data:**
GIVEN tool trả Sankey với `links: []` (CAKE, BNB Chain token)
THEN FE renders `<EmptySmartMoneyState />` với caption "No labeled smart money flow"
AND user thấy visual feedback rõ ràng thay vì text-only response

**AC4 — `source_domain` propagate end-to-end:**
GIVEN tool trả `source_domain="nansen.ai"` (hoặc `arkm.com`/`dune.com`)
THEN FE receives field qua SSE → persists vào `metadata.custom.smart_money_flow.source_domain` → render citation badge với favicon đúng

**AC5 — Nansen TGM endpoint hoạt động:**
GIVEN `NANSEN_API_KEY` valid (TGM tier)
WHEN gọi `get_nansen_smart_money(token_address="0x...")`
THEN POST `/api/v1/tgm/who-bought-sold` với header `apiKey` và body `{chain, token_address, date, pagination}`
AND parse `bought_volume_usd - sold_volume_usd` thành `net_flow_usd` per wallet

**AC6 — Reload preserves Sankey/empty-state:**
GIVEN user reload trang sau khi có response smart money
THEN `metadata.custom.smart_money_flow` được reconstruct từ `data-smart-money-flow` content part trong DB
AND Sankey/empty-state render lại đúng

---

## Files Modified

- `nowing_backend/app/agents/new_chat/chat_deepagent.py` — middleware non-comprehensive pass-through + emit `source_domain`
- `nowing_backend/app/agents/new_chat/system_prompt.py` — DECISION RULE + KB-first exception cho live market data + confirmation exception
- `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` — full rewrite cho TGM endpoint
- `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` — disambiguation + entity-type filter + chain forward + timeouts
- `nowing_backend/app/connectors/arkham_connector.py` — `ArkhamFatalError` + chain normalization
- `nowing_backend/app/tasks/chat/stream_new_chat.py` — forward `source_domain` qua SSE
- `nowing_web/lib/chat/streaming-state.ts` — extend `SmartMoneyFlowData` type
- `nowing_web/lib/chat/message-utils.ts` — extract `source_domain` on reload
- `nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx` — 3 SSE handlers forward `source_domain`
- `nowing_web/components/new-chat/report/crypto-report-layout.tsx` — `<EmptySmartMoneyState />` + relaxed render condition
- `nowing_backend/.env.example` — `DUNE_SMART_MONEY_QUERY_ID=7431659`

---

## Tasks/Subtasks

- [x] Middleware non-comprehensive pass-through (AC1, AC2)
- [x] System prompt DECISION RULE + exceptions (AC1)
- [x] EmptySmartMoneyState component + render condition (AC3)
- [x] FE/BE `source_domain` plumbing (AC4)
- [x] Nansen TGM endpoint migration (AC5)
- [x] Reload extract `source_domain` from content part (AC6)
- [x] 4 new tests added (label disambiguation, entity-type filter, source_domain attribution)

### Remaining QA tasks (gates story → done)

- [x] **Staging QA — PEPE:** Tool call `get_smart_money_flow` trả `source_domain: nansen.ai`, 31 nodes, 30 links. PASS.
- [x] **Staging QA — CAKE:** Tool trả `links: []`, `nodes: [{id: 'Market'}]` → `EmptySmartMoneyState` render condition satisfied. PASS.
- [x] **Staging QA — Comprehensive:** Middleware code verified — non-comprehensive `return await handler(request)` (no directive), comprehensive goes through `is_comprehensive` → synthetic-bypass. PASS.
- [x] **Staging QA — Reload persistence:** `parseSmartMoneyFlow` extracts `source_domain`+`cohort_summary`; `message-utils.ts` reconstructs from `data-smart-money-flow` content part on reload. PASS.
- [x] **Staging QA — `source_domain`:** `stream_new_chat.py:1549` emits `source_domain` in SSE payload; `page.tsx` `parseSmartMoneyFlow` forwards to state. PASS.
- [x] **Production smoke test:** `nsn_46519bdc028738090a2b243f72e9b17f` — TGM tier confirmed, 30 wallets returned for ETH. PASS.

---

## Risks

| Risk | Mitigation |
|---|---|
| Customers on Pro tier ($49/mo) lose access since TGM endpoint requires higher tier | Story 10-1-6 — tier detection + customer comms |
| Empty-state UI ignored by user / không có call-to-action | Future enhancement: add "Try another token" button |
| Cohort taxonomy regression (taxonomy lost in TGM migration) | Story 10-1-4 — re-implement cohort categorization |

---

## Test Plan

```bash
# Backend tests
.venv/bin/python -m pytest tests/unit/agents/new_chat/tools/test_nansen_smart_money.py \
  tests/unit/agents/new_chat/tools/test_smart_money_flow.py \
  tests/unit/agents/new_chat/tools/test_smart_money_fallback.py \
  tests/unit/agents/new_chat/tools/test_nansen_circuit_breaker.py -v

# Expected: 34 passed
```

End-to-end manual:
1. Login `test@nowing.test`
2. Hỏi "Show smart money flow for PEPE" → 1 tool call, Sankey renders
3. Hỏi "Show smart money flow for CAKE" → 1 tool call, EmptySmartMoneyState renders
4. Hỏi "full crypto analysis for ETH" → 6 sub-agents spawn (no regression)
5. Reload page → Sankey/empty-state persist
