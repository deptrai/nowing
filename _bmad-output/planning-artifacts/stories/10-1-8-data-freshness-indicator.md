# Story 10.1.8 — Data Freshness Indicator (Per-Widget Live/Delayed/Stale Tag)

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10-1-x (Smart Money flow stack — done/in-progress)
**Status:** backlog
**Priority:** P1 — required before stories 10-2, 10-3, 10-4, 10-5 ship to avoid UX regression
**Created:** 2026-05-06
**Source:** IR report 2026-05-06 § UX-HI-2

---

## Problem Statement

UX spec (`ux-design-specification.md` Phụ lục B § 3, line 836-839) mandates per-widget data freshness indicator on Institutional Research Terminal:
- 🟢 **Live** — receiving realtime data
- 🟡 **Delayed** — data is N minutes old
- 🔴 **Stale** — connection lost, displaying cached

**Current state:** Backend không expose `data_freshness` field trong SSE/WebSocket events for crypto widgets (Sankey, future Heatmap, Sandbox). FE chỉ có raw payload với data → không thể classify freshness.

**Impact if shipped without:**
- Stories 10-2 đến 10-5 ship widgets không có freshness indicator → UX regression vs UX spec
- Institutional users (target persona) lose trust signal — "is this 24h-old data hay realtime?"
- Customer support load: "Tại sao Sankey không update?" tickets

---

## Acceptance Criteria

**AC1 — Backend `data_freshness` field per widget:**
GIVEN tool returns crypto data response
WHEN building SSE event payload (Sankey / Heatmap / Sandbox / Risk panel)
THEN payload includes:
```json
{
  "data_freshness": {
    "status": "live" | "delayed" | "stale",
    "fetched_at": "2026-05-06T14:32:00Z",
    "age_seconds": 45,
    "ttl_seconds": 300,
    "source": "nansen.ai" | "arkm.com" | "dune.com" | "system"
  }
}
```

**Status derivation rule:**
- `live`: `age_seconds <= ttl_seconds * 0.5` (still in first half of TTL window)
- `delayed`: `ttl_seconds * 0.5 < age_seconds <= ttl_seconds` (in second half)
- `stale`: `age_seconds > ttl_seconds` (returned from cache after TTL expired due to API failure)

**AC2 — TTL configuration per data category:**
Reuse existing `crypto_data_categories.py` mapping (story 9-DF-1). New defaults:
- Smart Money flow (Nansen): TTL 300s (5 min)
- Smart Money flow (Arkham fallback): TTL 600s (10 min — heavier endpoint)
- Smart Money flow (Dune fallback): TTL 1800s (30 min — query rate limit)
- Tokenomics revenue (DefiLlama): TTL 3600s (1 hour)
- Vesting schedule: TTL 86400s (24 hours)
- Narrative sentiment: TTL 1800s (30 min)
- Macro correlation: TTL 3600s (1 hour)

**AC3 — FE freshness chip component:**
GIVEN any institutional research widget mounts (`<SankeyFlowChart>`, `<TokenomicsSandbox>`, `<NarrativeHeatmap>`, `<RiskMatrix>`)
WHEN data has `data_freshness` field
THEN component renders `<FreshnessChip>` ở góc top-right của widget:
- 🟢 Live (green dot + "Live")
- 🟡 Delayed (yellow dot + "Updated 4m ago")
- 🔴 Stale (red dot + "Stale — last update 12m ago")
AND tooltip on hover shows: "Source: nansen.ai · Fetched: 14:32 UTC · TTL: 5min"

**AC4 — Auto-refresh on stale:**
GIVEN widget shows status `stale` for > 30s
WHEN user is actively viewing widget (via IntersectionObserver)
THEN FE silently re-fetches data via dedicated refresh endpoint OR triggers tool re-invocation
AND chip animates briefly (pulse) to indicate refresh in progress

**AC5 — Fallback when no freshness available:**
GIVEN payload lacks `data_freshness` field (legacy data, untested provider)
THEN chip không render (no broken UI)
AND warning logged client-side: "Widget X missing data_freshness — please update tool to emit field"

**AC6 — Backward-compat:**
Existing Sankey widget (story 10-1-4 shipped) doesn't have `data_freshness` yet. AC5 ensures graceful absence — no crash. Implementation tasks include retrofit for Smart Money Sankey (story 10-1-x).

---

## Files to Modify / Create

### Backend

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/middleware/data_freshness.py` | CREATE | Helper `compute_data_freshness(fetched_at, ttl_seconds, source)` returns dict |
| `nowing_backend/app/agents/new_chat/tools/crypto_data_categories.py` | UPDATE | Add `ttl_seconds` per category if not already present |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Emit `data_freshness` trong Sankey response |
| `nowing_backend/app/agents/new_chat/chat_deepagent.py` | UPDATE | Forward `data_freshness` qua `smart-money-flow` SSE event |
| `nowing_backend/app/tasks/chat/stream_new_chat.py` | UPDATE | Forward `data_freshness` qua SSE payload |
| `nowing_backend/tests/unit/middleware/test_data_freshness.py` | CREATE | Unit tests for status derivation rule |

### Frontend

| File | Action | Notes |
|---|---|---|
| `nowing_web/lib/chat/streaming-state.ts` | UPDATE | Add `DataFreshness` interface + extend `SmartMoneyFlowData` |
| `nowing_web/components/crypto/FreshnessChip.tsx` | CREATE | Reusable chip with status derivation client-side (so chip updates as time passes without re-fetch) |
| `nowing_web/components/crypto/SankeyFlowChart.tsx` | UPDATE | Mount `<FreshnessChip>` top-right |
| `nowing_web/components/crypto/TokenomicsSandbox.tsx` | UPDATE (when story 10-2 ships) | Same |
| `nowing_web/components/crypto/NarrativeHeatmap.tsx` | UPDATE (when story 10-3 ships) | Same |
| `nowing_web/lib/chat/message-utils.ts` | UPDATE | Forward `data_freshness` on reload |

---

## Tasks/Subtasks

- [ ] BE: Implement `compute_data_freshness` helper với status derivation logic
- [ ] BE: Audit `crypto_data_categories.py` — add `ttl_seconds` cho missing categories
- [ ] BE: Wire freshness vào `get_smart_money_flow` response
- [ ] BE: Forward field qua SSE event chain (`chat_deepagent.py` → `stream_new_chat.py`)
- [ ] BE: Unit tests for status derivation (4 cases: live/delayed/stale/no-data)
- [ ] FE: TypeScript types (`DataFreshness` interface)
- [ ] FE: `<FreshnessChip>` component với 3 visual states + tooltip
- [ ] FE: Mount on `SankeyFlowChart` (retrofit story 10-1-4 widget)
- [ ] FE: Auto-refresh logic with IntersectionObserver
- [ ] FE: Component tests with React Testing Library (3 status states + missing-field fallback)
- [ ] Documentation: Update Phụ lục B § 3 in UX spec với specific status thresholds

---

## Test Plan

### Backend
```python
# test_data_freshness.py
@pytest.mark.parametrize("age,ttl,expected", [
    (30, 300, "live"),       # 30s old, 5min TTL → 10% age
    (200, 300, "delayed"),   # 200s old, 5min TTL → 67% age
    (350, 300, "stale"),     # 350s old, 5min TTL → 117% age
    (0, 300, "live"),        # just fetched
])
def test_freshness_status_derivation(age, ttl, expected):
    fetched_at = datetime.now(timezone.utc) - timedelta(seconds=age)
    result = compute_data_freshness(fetched_at, ttl, "nansen.ai")
    assert result["status"] == expected
```

### Frontend
```tsx
// FreshnessChip.test.tsx
describe('FreshnessChip', () => {
  it('renders Live state with green dot', () => {
    render(<FreshnessChip data_freshness={{status:"live", age_seconds:30, ...}} />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
  it('renders Stale state with red dot', () => { ... });
  it('renders nothing when data_freshness is undefined', () => { ... });
});
```

### Manual QA
1. Hỏi "smart money flow for PEPE" → freshness = Live (just fetched)
2. Wait 3 minutes → chip transitions to Delayed (yellow)
3. Wait 6+ minutes → chip transitions to Stale + auto-refresh triggers
4. Disconnect network mid-session → next query: Stale chip + tooltip explains "no fresh data available"

---

## Risks

| Risk | Mitigation |
|---|---|
| Auto-refresh on stale spams external API → cost spike | IntersectionObserver gating (only refresh visible widgets) + debounce 30s minimum between refreshes |
| Freshness chip clutters UI on small viewports | Collapse to color-dot-only on mobile (< 640px), full chip on desktop |
| Status derivation drift (BE clock vs FE clock skew) | Compute status client-side using `fetched_at` ISO string (BE clock authoritative); FE clock only used for "X minutes ago" relative display |
| TTL guessing wrong cho new categories (10-2/3/4/5) | Each new story (10-2..10-5) MUST define TTL trong its AC + crypto_data_categories.py |

---

## Why P1 (Blocker for 10-2, 10-3, 10-4, 10-5)

If story 10-2 ships TokenomicsSandbox without freshness indicator → UX regression vs spec → user complaints → retrofit cost. Better to ship 10-1-8 first as foundational widget primitive, then 10-2/3/4/5 inherit pattern.

**Recommended sequencing:** 10-1-8 → (retrofit 10-1-4 Sankey) → 10-2 → 10-3 → 10-4 → 10-5
