# Story 10.1.5 — Nansen Pagination: Multi-Page Fetch for Accurate Net Flow

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10.1.3 (TGM endpoint migration)
**Status:** backlog
**Created:** 2026-05-06
**Why:** Sau migrate TGM endpoint, `get_nansen_smart_money` chỉ fetch first page (`per_page: 30`). `net_flow_24h_usd` và `signal` (accumulating/distributing/neutral) được derive từ partial data. Tokens với hơn 30 active smart money wallets có signal sai/misleading.

---

## Problem Statement

**Current code** ([nansen_smart_money.py:148](nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py#L148)):
```python
"pagination": {"page": 1, "per_page": 30}
```

Response shape:
```json
{
  "data": [...30 items...],
  "pagination": {"page": 1, "per_page": 30, "is_last_page": false}
}
```

`is_last_page: false` được trả nhưng code không loop sang page 2.

**Impact:**
- ETH có thể có 100+ smart money wallets active 24h → tool trả 30 wallets đầu tiên (sorted by Nansen's default — usually descending volume)
- `net_flow_24h_usd = sum(wallet.net for top-30 wallets)` — không phản ánh tổng thực
- Signal "accumulating" có thể sai nếu top-30 đang distribute nhưng tail-70 đang accumulate

---

## Acceptance Criteria

**AC1 — Multi-page fetch loop:**
GIVEN response trả `is_last_page: false`
THEN tool fetch page+1 cho đến khi `is_last_page: true` HOẶC chạm `_MAX_PAGES` cap
AND tất cả items được aggregate vào `smart_money_wallets`

**AC2 — Cap on max pages:**
- `_MAX_PAGES = 10` (= 300 wallets max) để tránh runaway fetches
- Khi chạm cap: log warning, đính kèm `is_partial: true` flag vào tool result
- FE có thể display "showing top 300 of N wallets" caption

**AC3 — Per-page rate limit compliance:**
GIVEN Nansen rate limit 100 req/min (Pro tier)
THEN multi-page fetch must `await _nansen_rl.acquire()` cho mỗi request
AND không vi phạm budget — 10-page fetch (10 reqs) consume 10/100 budget per call

**AC4 — Accurate `net_flow_24h_usd`:**
GIVEN N wallets across M pages
THEN `net_flow_24h_usd = sum(bought - sold for all wallets across all fetched pages)`
AND signal được derive từ tổng thực, không phải partial

**AC5 — Sankey cap remains 30 wallets:**
Sankey visualization vẫn cap `_MAX_WALLETS_IN_SANKEY = 30` (UI readability) — nhưng chọn 30 wallets có `|net_flow_usd|` lớn nhất từ ALL fetched wallets, không phải 30 đầu tiên.

**AC6 — Partial fetch fallback:**
GIVEN page 5 fail (5xx, timeout, network error)
THEN tool returns aggregated data từ pages 1-4 với `is_partial: true`
AND không fail toàn bộ tool call

**AC7 — Test coverage:**
- `test_pagination_fetches_all_pages_until_is_last`: mock 3-page response, assert all 90 wallets aggregated
- `test_pagination_caps_at_max_pages`: mock 15-page response, assert stop at page 10 with `is_partial: true`
- `test_pagination_partial_fetch_on_page_error`: mock page 3 returning 500, assert pages 1-2 returned with `is_partial: true`
- `test_pagination_signal_derives_from_full_data`: mock 2-page response where page 1 distributing + page 2 accumulating → assert signal correctly reflects aggregate

---

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | Add pagination loop + `_MAX_PAGES` constant + `is_partial` flag |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Forward `is_partial` qua Sankey result |
| `nowing_web/lib/chat/streaming-state.ts` | UPDATE | Add `is_partial?: boolean` to `SmartMoneyFlowData` |
| `nowing_web/components/new-chat/report/crypto-report-layout.tsx` | UPDATE | Display "showing top 300 of N wallets" khi `is_partial` |
| `nowing_backend/tests/unit/agents/new_chat/tools/test_nansen_pagination.py` | CREATE | 4 test cases (xem AC7) |

---

## Tasks/Subtasks

- [ ] Add `_MAX_PAGES = 10` constant
- [ ] Refactor `get_nansen_smart_money` body to fetch loop:
  ```python
  all_items = []
  page = 1
  is_partial = False
  while page <= _MAX_PAGES:
      body["pagination"]["page"] = page
      await _nansen_rl.acquire()
      resp = await client.post(url, json=body, headers=_auth_headers())
      # ... handle errors with is_partial fallback ...
      data = resp.json()
      all_items.extend(data.get("data", []))
      if data.get("pagination", {}).get("is_last_page", True):
          break
      page += 1
  else:
      is_partial = True
      logger.warning("Nansen pagination capped at %d pages for %s", _MAX_PAGES, token_address)
  ```
- [ ] Aggregate `net_flow` and `wallets` from `all_items`
- [ ] Sankey selection: top-30 by `|net_flow_usd|`, not by API order
- [ ] FE: show partial-data caption when `is_partial`
- [ ] Unit tests (4 cases)
- [ ] Manual QA: ETH (likely 50+ wallets) → verify multi-page fetch

---

## Risks

| Risk | Mitigation |
|---|---|
| Multi-page fetch consumes 10x rate budget per call → quota exhaustion under load | `_MAX_PAGES = 10` cap + monitor `nansen_rl.in_use_ratio` metric |
| Page 1 success + page 2-10 timeout → aggregation lopsided | `is_partial: true` signals user; signal derived from available data |
| Loop accidentally triggers infinite fetch (bad `is_last_page` from API) | Hard cap `_MAX_PAGES` regardless of API response |
| Large response (300 wallets × ~500 bytes JSON) may exceed agent context budget | Sankey selection caps to 30 wallets before serialization |

---

## Test Plan

```python
@pytest.mark.asyncio
async def test_pagination_fetches_all_pages_until_is_last():
    """3-page response: each page returns 30 items, last_page only on page 3."""
    pages = [
        {"data": [...30 items...], "pagination": {"page": 1, "is_last_page": False}},
        {"data": [...30 items...], "pagination": {"page": 2, "is_last_page": False}},
        {"data": [...30 items...], "pagination": {"page": 3, "is_last_page": True}},
    ]
    # ... mock httpx to return pages in sequence ...
    result = await tool.ainvoke({"token_address": "0x..."})
    assert len(result["smart_money_wallets"]) == 90
    assert result.get("is_partial") is None or result["is_partial"] is False
```

E2E:
1. Hỏi "smart money flow for ETH" (hot token, likely many wallets)
2. Verify tool fetches ≥2 pages (check logs)
3. Sankey hiển thị 30 wallets sorted by absolute flow
4. `net_flow_24h_usd` reflects total across all fetched pages
