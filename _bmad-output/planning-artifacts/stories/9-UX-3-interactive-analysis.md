---
storyId: 9-UX-3
storyTitle: Interactive Analysis — Scenario Simulator + Coin Compare + Next Actions
epicParent: epic-9-crypto-orchestra
dependsOn: [Story 9-UX-2 DONE]
blocks: []
relatedFRs: [FR27 Comprehensive Analysis, FR-new Scenario Simulation, FR-new Coin Comparison]
relatedNFRs: [NFR-UX-3 Engagement, NFR-P1 Re-synthesis latency < 20s]
priority: P0 (Phase 2 UX — conversion driver)
estimatedEffort: 2 weeks (1 FE + 1 BE)
status: ready-for-dev
createdAt: 2026-04-25
author: Sally (UX) + Mary (BA)
---

# Story 9-UX-3: Interactive Analysis

## User Story

**As a** crypto investor who just read a Nowing report,
**I want** to (a) simulate bull/bear/stress scenarios with user-tunable assumptions, (b) compare the analyzed token side-by-side with peers, and (c) take immediate next actions (watchlist, alert, share, deep-dive),
**So that** I don't leave the report as a dead-end — I convert insights into decisions and explore further without re-typing queries.

**Bar to clear**: post-read engagement (time-in-app after report renders) increases from <1 min to ≥ 5 min.

---

## Context

### Current state (verified 2026-04-25)

After LDO analysis renders, user sees:
- Copy to clipboard button
- Download as Markdown button
- Regenerate response button

That's it. The journey dies. User closes tab.

### Desired state

Bottom of report:
```
┌─────────────────────────────────────────────────────────┐
│ 👀 Watchlist       │ 🔔 Price Alert                    │
│ Thêm LDO           │ Alert khi LDO > $0.5              │
│ ⌘W                 │ ⌘A                                 │
├─────────────────────────────────────────────────────────┤
│ 🆚 Compare         │ 🔬 Deep Dive                      │
│ So sánh LDO vs RPL │ Phân tích sâu fee switch          │
│ ⌘K                 │ ⌘D                                 │
└─────────────────────────────────────────────────────────┘

Follow-up suggestions:
[ Tại sao TVL giảm 46%? ] [ LDO vs RPL ai tốt hơn? ]
[ Fee switch proposal khả thi? ] [ Top 5 LDO whales? ]
```

Plus floating panels:
- **ScenarioSimulatorPanel** (top-right): tabs Base/Bull/Bear/Stress with sliders for assumptions
- **CoinComparisonOverlay** (slide-in right): side-by-side table

---

## Prerequisites

- [ ] Story 9-UX-2 DONE — report layout has slot for bottom action bar
- [ ] Story 0.6b DONE — scenario re-synthesis reuses gate + retry infrastructure
- [ ] Checkpointer + `_extract_partial_analysis` working (from Story 0.6b)

---

## Acceptance Criteria

### AC1 — NextActionBar component (FE)

New [next-action-bar.tsx](../../../nowing_web/components/new-chat/report/next-action-bar.tsx):
- Renders at bottom of `CryptoReportLayout`, after all sections
- 4 action cards in 2×2 grid (stack vertically on mobile)
- Each card: icon, title, 1-line description, keyboard shortcut hint
- Contextual copy based on token name from report metadata

### AC2 — 4 Action Card implementations (FE)

| Action | Handler | State change |
|--------|---------|--------------|
| 👀 Watchlist (⌘W) | `addToWatchlist(token)` | Jotai `watchlistAtom` update, localStorage persist, toast "Thêm LDO vào watchlist" |
| 🔔 Price Alert (⌘A) | Open `CreateAlertDialog` | Modal: threshold input + direction (above/below) + save to `priceAlertAtom` |
| 🆚 Compare (⌘K) | Open `CoinComparisonOverlay` | Drawer slide-in from right |
| 🔬 Deep Dive (⌘D) | Autofill chat input with deep-dive prompt | Focus + suggest, user can edit before submit |

### AC3 — Keyboard shortcuts (FE)

Global shortcut registration using existing shortcut pattern:
- `⌘W` / `Ctrl+W` → Watchlist action
- `⌘A` / `Ctrl+A` → Alert action (beware: conflicts with "select all" — use `⌘⇧A`)
- `⌘K` / `Ctrl+K` → Compare (existing command palette? check conflict)
- `⌘D` / `Ctrl+D` → Deep Dive

If conflicts exist, use `⌘⇧{letter}` variants.

### AC4 — FollowUpChips (FE)

New [follow-up-chips.tsx](../../../nowing_web/components/new-chat/report/follow-up-chips.tsx):
- 4-6 LLM-generated follow-up questions based on report content
- Rendered as horizontal scrollable chip row below NextActionBar
- Click chip → autofill chat input + focus (user can edit or submit)

### AC5 — Follow-up generation (BE)

During final synthesis, the LLM emits follow-up suggestions in message metadata:
```json
{
  "follow_ups": [
    "Tại sao TVL của Lido giảm 46% từ ATH?",
    "So sánh LDO với Rocket Pool (RPL)",
    "Fee switch proposal có khả thi không?",
    "Top 5 whale holder của LDO là ai?"
  ]
}
```

Metadata flows via new SSE event `message-metadata` with `type: 'follow_ups'`.

### AC6 — ScenarioSimulatorPanel component (FE)

New [scenario-simulator-panel.tsx](../../../nowing_web/components/new-chat/simulator/scenario-simulator-panel.tsx):
- Floating panel, top-right of report (collapsible)
- Tabs: [Base Case] [🚀 Bull] [🐻 Bear] [⚠️ Stress Test]
- AssumptionInputs section (below tabs):
  - Slider: BTC Price Shock (-50% → +100%)
  - Toggle: Fee Switch Pass (for DeFi tokens)
  - Toggle: Regulatory Impact Adverse
  - Slider: Competitor Growth (-50% → +100%)
- "Re-synthesize" button (disabled when assumptions unchanged)

### AC7 — Scenario re-synthesis flow (BE)

New endpoint [scenario_routes.py](../../../nowing_backend/app/routes/scenario_routes.py) `POST /api/v1/scenarios/resynthesize`:
```json
{
  "thread_id": 30,
  "scenario": "bull",
  "assumptions": { "btc_shock": 0.5, "fee_switch": true, ... },
  "scope": "conclusion"  // or "full"
}
```

Backend:
1. Load checkpoint state from PostgresSaver (all sub-agent ToolMessages)
2. Construct scenario-specific synthesis prompt: "Based on the data below, re-synthesize the analysis assuming {scenario} with {assumptions}. Adjust price targets, yield expectations, risk assessment. Keep citations to existing tool results."
3. Call LLM with `tools=[]` (synthesis-mode, no new tool calls)
4. Stream result via new SSE: `scenario-text-delta`, `scenario-complete`
5. Persist scenario result in new DB table `scenario_results` (thread_id, scenario, content, created_at)

### AC8 — Scenario result caching (BE+FE)

- Cache scenario results per `(thread_id, scenario, assumptions_hash)` in DB
- On re-click same scenario → serve from cache instantly
- Toggle back to Base Case → show original final message from checkpointer

### AC9 — Scenario UI re-render (FE)

When scenario streams in:
- Conclusion section of report highlighted with subtle pulse
- Content swaps smoothly (fade 200ms)
- "Currently viewing: 🚀 Bull Case" badge in section header
- Diff marker: changed numbers highlighted vs Base (e.g., "$7.23 → $12-15 ⬆")
- "View Base Case" always-visible toggle

### AC10 — CoinComparisonOverlay component (FE)

New [coin-comparison-overlay.tsx](../../../nowing_web/components/new-chat/compare/coin-comparison-overlay.tsx):
- Slide-in drawer from right (Sheet component)
- Header: "Compare LDO with ___" — TokenPicker autocomplete
- TokenPicker: search by symbol, show top-10 with logos, debounced CoinGecko search API
- On selection → trigger comparison flow

### AC11 — Comparison data flow (BE)

New endpoint [comparison_routes.py](../../../nowing_backend/app/routes/comparison_routes.py) `POST /api/v1/compare/tokens`:
```json
{ "primary_token": "LDO", "secondary_token": "RPL" }
```

Backend:
1. Check cache `compare_results` table for recent (<30min) result
2. If miss: spawn lightweight 2-agent analysis for secondary token (tokenomics + defillama only)
3. Stream results via SSE
4. Generate "verdict" synthesis comparing both tokens

### AC12 — ComparisonTable component (FE)

New [comparison-table.tsx](../../../nowing_web/components/new-chat/compare/comparison-table.tsx):
- Side-by-side table, 2 columns (primary | secondary)
- Rows: Price, Market Cap, TVL, APY, Holders, Security Score, Sentiment, Unlock Schedule, Catalysts
- Auto-highlight differences (green for better, red for worse) per metric
- Below table: `<OverlayChart>` dual-line price chart (Recharts)
- Bottom: `<VerdictBox>` with LLM-generated "X is better for Y use-case because…"

### AC13 — Watchlist & Alert atoms (FE)

New files:
- [watchlist-atom.ts](../../../nowing_web/lib/crypto/watchlist-atom.ts) — Jotai + localStorage persistence, max 50 tokens
- [price-alert-atom.ts](../../../nowing_web/lib/crypto/price-alert-atom.ts) — same pattern, with threshold + direction

No backend persistence v1 (local-first). Stretch: sync to DB if logged in.

### AC14 — Toast + confirmation UX

All actions emit toast via existing Sonner integration:
- "LDO added to watchlist" + "Undo" action
- "Alert created: LDO > $0.5" + "View alerts"
- "Comparison loaded: LDO vs RPL"

### AC15 — Variable agent count support [patch-6 GAP-7]

Scenario re-synthesis loads ToolMessages from **all available sub-agents** in checkpoint state, not a hardcoded 6. Comparison lightweight-agent pair (tokenomics + defillama) may expand to 3 agents (+ whale_tracker) when `CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true` — `ComparisonTable` rows render based on available data keys, not a fixed schema. Story does not assume `len(sub_agents) == 6`.

---

## Tasks

- [ ] **T1** (FE) — Build `NextActionBar` + 4 action card components
- [ ] **T2** (FE) — Register keyboard shortcuts (handle conflicts)
- [ ] **T3** (FE) — Build `FollowUpChips` + autofill-chat hook
- [ ] **T4** (BE) — LLM synthesis prompt emits `follow_ups` metadata; wire to SSE `message-metadata` event
- [ ] **T5** (FE) — Build `ScenarioSimulatorPanel` + assumption sliders + tabs
- [ ] **T6** (BE) — Build `POST /api/v1/scenarios/resynthesize` endpoint + `stream_scenario.py` task
- [ ] **T7** (BE) — DB migration: `scenario_results` table
- [ ] **T8** (FE) — Wire scenario panel to endpoint + streaming consume
- [ ] **T9** (FE) — Scenario UI re-render w/ section swap + diff highlight
- [ ] **T10** (FE) — Build `CoinComparisonOverlay` + `TokenPicker` autocomplete
- [ ] **T11** (BE) — Build `POST /api/v1/compare/tokens` + `compare_results` cache table
- [ ] **T12** (FE) — Build `ComparisonTable` + `OverlayChart` + `VerdictBox`
- [ ] **T13** (FE) — Build watchlist-atom + price-alert-atom + localStorage sync
- [ ] **T14** (FE) — Toast integration for all 4 actions
- [ ] **T15** (E2E) — Playwright: full journey — read report → click each action → verify behavior
- [ ] **T16** (BE/FE) — Verify scenario re-synthesis + comparison handle N agents dynamically (test with 6 and 7 agent sessions)

---

## Dev Notes

### Reusable infrastructure

- Checkpointer: existing from Story 0.6b, use `agent.aget_state()`
- Sub-agents: reuse tokenomics + defillama only for compare (lightweight)
- Rate gate: works automatically for scenario synthesis + comparison agents
- Toast: existing Sonner from `sonner` package

### Scenario assumption schema

```ts
type ScenarioAssumptions = {
  btc_shock?: number;          // -0.5 to 1.0 (percentage delta)
  eth_shock?: number;
  fee_switch_passes?: boolean;  // DeFi-governance token specific
  regulatory_adverse?: boolean;
  competitor_growth?: number;   // -0.5 to 1.0
  tvl_shock?: number;
};
```

Hash function: `sha256(JSON.stringify(sorted(assumptions)))` for cache key.

### Scenario prompt template

```
You previously analyzed {token_name} using data from 6 sub-agents. Now re-synthesize
the conclusion section under this scenario:

Scenario: {scenario_label}
Assumptions:
{formatted_assumptions}

Data available:
{tool_message_summaries}

Rewrite only the Conclusion and Recommendation sections. Adjust:
- Price targets (explicitly state calculation basis)
- Yield expectations
- Risk level (may shift up/down)
- Catalysts (which still apply? which change?)

Keep all citation chips ([[cite:id]]...[[/cite]]) from the original analysis — reference
same data, new interpretation.

Start with: "### Kịch bản: {scenario_label}" as the first line.
```

### Comparison verdict prompt

```
Two crypto tokens have been analyzed. Based on the data below, provide a nuanced
comparison covering:

1. Which is stronger fundamentally (protocol metrics)?
2. Which has better tokenomics (distribution, inflation, utility)?
3. Which is safer (security, decentralization)?
4. Which has better short-term catalysts?
5. Verdict: which is better for a {risk_profile} investor?

Do NOT give financial advice. Frame as "based on these metrics…"

{primary_token_data}

vs.

{secondary_token_data}
```

### Performance targets

- Scenario re-synthesize: < 20s end-to-end (with gate warm)
- Compare (cached): < 100ms
- Compare (fresh, 2-agent): < 90s at 8 RPM
- Shortcut response: < 50ms

---

## Definition of Done

- [ ] All 15 ACs verified
- [ ] 16 tasks done
- [ ] Storybook: all new components
- [ ] E2E Playwright: watchlist add, alert create, scenario toggle, compare flow
- [ ] Scenario caching works (toggle same scenario twice → instant second time)
- [ ] Mobile: action bar stacks vertically, comparison drawer full-screen
- [ ] Regression: Story 9-UX-2 report rendering unchanged

---

## Traceability

- Design spec: `.claude/plans/harmonic-cuddling-glacier.md` § Sub-Epic 9-UX-3
- Depends: Story 9-UX-2 (needs report layout)
- Adjacent: Story 9-UX-4 (additional data sources — whale tracker enhances Compare verdict)

---

## Review Findings

(To be filled post-dev)
