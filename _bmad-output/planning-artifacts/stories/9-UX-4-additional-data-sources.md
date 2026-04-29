---
storyId: 9-UX-4
storyTitle: Additional Data Sources — Nansen / CertiK / Dune / TokenInsight + Whale Tracker
epicParent: epic-9-crypto-orchestra
dependsOn: [Story 9-UX-1 DONE (SourceAttributionMiddleware), Story 9-UX-1b DONE, Story 9-UX-1c DONE, Story 9-UX-2 DONE (citation chips)]
blocks: []
relatedFRs: [FR27 Comprehensive Analysis, FR-new Whale Tracking, FR-new Premium Data Sources]
relatedNFRs: [NFR-Q1 Accuracy (cross-source verification), NFR-CS3 API Rate Awareness]
priority: P1 (Phase 2 — depth enhancement, not MVP)
estimatedEffort: 2 weeks (1 BE + 0.5 FE)
status: done
createdAt: 2026-04-25
author: Sally (UX) + Mary (BA)
---

# Story 9-UX-4: Additional Data Sources

## User Story

**As a** crypto professional needing institutional-grade analysis,
**I want** Nowing reports to incorporate smart-money flow data (Nansen), formal security audits (CertiK), custom on-chain queries (Dune), and third-party ratings (TokenInsight) — each properly cited —
**So that** my analysis matches what Messari/Nansen terminal users get, with Nowing's AI synthesizing across 10+ sources that no single tool covers.

**Bar to clear**: compared to a human analyst with Nansen + Messari + Dune seats, Nowing report covers ≥ 80% of the data points, with equal or better attribution.

---

## Context

### Current state (Story 9.1 + 9.4 DONE)

6 sub-agents use:
- CoinGecko (price, supply, metadata)
- DeFiLlama (TVL, yields)
- GoPlus (security basic)
- CryptoPanic (news, often 404s)
- Reddit (sentiment)
- CMC (fear/greed)
- Chainlens deep research (fallback)

Missing high-signal sources:
- ❌ Smart money flows (who's accumulating/dumping?)
- ❌ Formal audits + incident history
- ❌ Custom Dune queries (DEX volume by address cohort, NFT floor dynamics)
- ❌ Third-party ratings

### Desired state

- **Nansen integration**: smart money wallet flows surfaced in new "Whale Tracker" section
- **CertiK Skynet**: audit score cross-referenced with GoPlus (triggers conflict citation when scores diverge)
- **Dune Analytics**: custom pre-registered queries fetched on-demand (with deeplink to Dune page for user to remix)
- **TokenInsight rating**: shown as badge next to Risk Badge (A/B/C/D/F)

New sub-agent: **whale_tracker** (rolls in Story 9.2 from deferred Phase 2 plan)

---

## Prerequisites

- [ ] Story 9-UX-1 DONE — `SourceAttributionMiddleware` must exist (citations won't work otherwise)
- [ ] Story 9-UX-2 DONE — Citation Chip 2.0 needs per-provider brand colors
- [ ] API keys procured: NANSEN_API_KEY (paid tier), DUNE_API_KEY, TOKENINSIGHT_API_KEY (CertiK is free)

---

## Acceptance Criteria

### AC1 — Nansen tool integration (BE)

New [nansen_smart_money.py](../../../nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py) exposing:
- `get_nansen_smart_money(token_address: str) → dict` — top wallets labeled "Smart Money", accumulating/distributing flags, 24h net flow
- `get_nansen_wallet_label(address: str) → dict` — label (e.g. "Binance Hot Wallet", "Ethereum Foundation")
- `get_nansen_token_god_mode(token_address: str) → dict` — holder distribution by cohort

Returns dict with `source_domain: "nansen.ai"` so SourceAttributionMiddleware emits citation events.

### AC2 — CertiK Skynet tool integration (BE)

New [certik_skynet.py](../../../nowing_backend/app/agents/new_chat/tools/certik_skynet.py) exposing:
- `get_certik_audit_score(token_address: str, chain: str) → dict` — overall score, categories (code, market, governance, community)
- `get_certik_incident_history(project_name: str) → list[Incident]` — past hacks, timelines

Free API tier sufficient for non-commercial.

### AC3 — Dune Analytics tool integration (BE)

New [dune_query.py](../../../nowing_backend/app/agents/new_chat/tools/dune_query.py):
- Pre-registered queries for common crypto analyses stored in [queries/dune/](../../../nowing_backend/app/agents/new_chat/tools/queries/dune/)
- Common queries:
  - DEX volume by pool (Uniswap)
  - NFT collection floor + volume (OpenSea)
  - Staking flows (Lido, RocketPool)
  - Whale concentration (top 10 holders %)
- Tool signature: `run_dune_query(query_id: int, params: dict) → { data, dune_url }`
- `dune_url` deeplinks to Dune page for user to customize + remix

### AC4 — TokenInsight tool integration (BE)

New [tokeninsight_rating.py](../../../nowing_backend/app/agents/new_chat/tools/tokeninsight_rating.py):
- `get_tokeninsight_rating(token_symbol: str) → dict` — overall rating (A/B/C/D/F), category breakdown
- `get_tokeninsight_research_snippet(token_symbol: str) → str` — latest research note excerpt

### AC5 — whale_tracker sub-agent (BE)

New [whale_tracker.py](../../../nowing_backend/app/agents/new_chat/subagents/crypto/whale_tracker.py) sub-agent spec:
- Tools: nansen_smart_money, nansen_wallet_label, arkham (if exists), etherscan_whale_alerts
- System prompt: "Identify top 10 holders, smart money flows, accumulation vs distribution signals over last 7 days. Report with wallet labels and transaction counts."
- Added to `_COMPREHENSIVE_AGENTS` list in [chat_deepagent.py](../../../nowing_backend/app/agents/new_chat/chat_deepagent.py)

Feature-flagged via `CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true|false`. When off, whale_tracker not added to priority list; Research Lab shows 6 agents as before.

### AC6 — smart_contract_analyst extension with CertiK (BE)

Existing `smart_contract_analyst` sub-agent spec updated:
- Add `get_certik_audit_score` to tools
- Update system prompt: "Cross-reference CertiK and GoPlus results. When scores diverge > 15 points, emit conflict citation with both values."

### AC7 — Cross-source conflict detection (BE)

Extend synthesis prompt in `_SYNTHESIS_DIRECTIVE`:
- When 2+ sources report same metric with delta > 10%, emit conflict citation
- Example: GoPlus audit: 20/100 vs CertiK: 45/100 → `[[cite:audit-conflict-goplus-certik]]20-45/100[[/cite]]` with conflict variant

### AC8 — Citation chip brand colors (FE)

Add to design tokens from Story 9-UX-2:
- `--source-nansen`: teal (existing `188 75% 42%`)
- `--source-certik`: purple (new: `262 83% 58%`)
- `--source-dune`: orange (new: `25 95% 53%`)
- `--source-tokeninsight`: indigo (new: `239 84% 67%`)

Favicon fetched from each provider's domain via DuckDuckGo proxy.

### AC9 — SourceDetailPanel — Dune integration (FE)

When Citation Chip is from Dune:
- Show "View on Dune Analytics →" prominent button
- Deeplinks to original Dune query with params pre-filled
- Encourages user to remix query for their own thesis

### AC10 — Whale section in report (FE)

When `whale_tracker` sub-agent runs, new section renders in report:
```
🐋 Whale Tracker — Smart Money Flows

Top 10 holders concentration: [[cite:whale-conc]]42.3%[[/cite]]
Smart money net flow (7d): [[cite:smart-money-flow]]+$12M[[/cite]] 🟢 Accumulating
Notable wallets:
- [[wallet-label:0x123...]]Jump Trading[[/wallet-label]] — added 1.2M tokens
- [[wallet-label:0x456...]]a16z[[/wallet-label]] — holding, no movement
```

New `<WalletLabel>` component extending Citation pattern for on-chain addresses.

### AC11 — TokenInsight rating badge in Hero (FE)

TokenHeroCard gains secondary badge:
```
🟢 LOW RISK   🅰️ A+ Rating
```

Badge sources data from `tokeninsight_rating` tool result via message metadata.

### AC12 — Environment variables

Add to [.env.example](../../../nowing_backend/.env.example):
```bash
# Phase 2 data sources
NANSEN_API_KEY=                          # Paid — Smart money flows
CERTIK_API_KEY=                           # Free
DUNE_API_KEY=                             # Paid tier for custom queries
TOKENINSIGHT_API_KEY=                     # Free+paid tiers
CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=false  # default off until API keys ready
```

### AC13 — Graceful unavailable handling

When any new tool returns 401/403 (API key missing) or 429 (quota), emit ToolMessage with `status="error"` content explaining "Source unavailable — paid tier required" or similar. Main agent synthesizes without that source + notes "Nansen data unavailable in this analysis (free tier)."

### AC15 — Layout compatibility [patch-6 GAP-6]

When `CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true`, verify Story 9-UX-1 Research Lab renders 7 agents correctly in the dynamic grid (2×4 on `md`). E2E test: enable flag → send comprehensive query → assert 7 agent lanes visible, no overflow or layout break. Regression: disable flag → assert 6 lanes (no ghost 7th lane).

### AC14 — Rate-limit awareness

- Nansen: 100 req/min free tier, 500/min paid — use existing `_global_rate_bucket` if shared quota, OR per-tool rate limiter if separate
- CertiK: 60 req/min free
- Dune: 40 req/min on Basic plan
- TokenInsight: 100 req/min free

Each tool wraps httpx call with its own rate-limit budget tracking (separate from LLM gate).

---

## Tasks

- [x] **T1** (BE) — Build `nansen_smart_money.py` with 3 functions + error handling
- [x] **T2** (BE) — Build `certik_skynet.py` with 2 functions
- [x] **T3** (BE) — Build `dune_query.py` + seed 4 pre-registered queries
- [x] **T4** (BE) — Build `tokeninsight_rating.py` with 2 functions
- [x] **T5** (BE) — Build `whale_tracker_spec.py` sub-agent spec + register in `_COMPREHENSIVE_AGENTS` (feature-flagged)
- [x] **T6** (BE) — Extend `smart_contract_analyst` system prompt with CertiK cross-reference
- [x] **T7** (BE) — Update `_SYNTHESIS_DIRECTIVE` with cross-source conflict detection rule
- [x] **T8** (BE) — Unit tests for each tool (with httpx mocks)
- [x] **T9** (BE) — Integration test for whale_tracker spawn flow + wiring
- [x] **T10** (FE) — Add 4 new `--source-*` design tokens (light + dark) to globals.css
- [x] **T11** (FE) — `<WalletLabel>` + `<WalletLabelList>` components (extends citation pattern)
- [x] **T12** (FE) — TokenInsight rating badge in TokenHeroCard
- [x] **T13** (FE) — Dune "View on Dune Analytics →" prominent button in SourceDetailPanel
- [x] **T14** (E2E) — Playwright: feature-flag ON → verify 7 agents in Lab, whale section renders
- [x] **T15** (E2E) — Playwright: verify dynamic grid layout at `md` breakpoint shows 7 lanes without overflow

---

## Dev Notes

### API rate limits (as of 2026-04)

| Provider | Free | Paid | Per-query cost |
|----------|------|------|----------------|
| Nansen | — (none) | $150/mo Pro | ~$0 per query |
| CertiK | 60 rpm | N/A | Free |
| Dune | 40 rpm Basic ($99/mo) | 180 rpm Plus | ~100 credits per query |
| TokenInsight | 100 rpm | custom | Free or paid |

**Budget guidance**: start with CertiK (free) + TokenInsight (free) + Dune Basic ($99/mo). Defer Nansen until value proven.

### Feature flag strategy

Phase rollout:
1. v1 (ship this story): CertiK + TokenInsight enabled default, Nansen + Dune behind feature flags
2. v2 (post-launch): enable Dune after evaluating query credit burn
3. v3 (premium tier): enable Nansen as paid-tier-only feature

### Dune query registry

Store queries as JSON files:
```
nowing_backend/app/agents/new_chat/tools/queries/dune/
  ├── uniswap-dex-volume.json          (query_id: 12345)
  ├── lido-staking-flows.json          (query_id: 12346)
  ├── whale-concentration.json         (query_id: 12347)
  └── nft-collection-floor.json        (query_id: 12348)
```

Each JSON file:
```json
{
  "query_id": 12345,
  "name": "Uniswap DEX Volume by Pool",
  "params_schema": { "pool_address": "string" },
  "description": "...",
  "dune_url": "https://dune.com/queries/12345"
}
```

### Wallet label data source strategy

Nansen provides labels for ~200K known wallets (exchanges, MMs, funds, VCs). For non-labeled addresses, show shortened address `0x1234...abcd` with copy button.

### Citation chip color assignment

```css
/* Extend Story 9-UX-2 tokens */
--source-nansen: hsl(188 75% 42%);      /* teal */
--source-certik: hsl(262 83% 58%);      /* purple */
--source-dune: hsl(25 95% 53%);         /* orange */
--source-tokeninsight: hsl(239 84% 67%); /* indigo */
```

### Testing notes

- Mock Nansen/CertiK/Dune/TokenInsight with `respx` (already in dev deps from Story 0.6)
- Golden dataset for cross-source conflict detection (GoPlus 20/100 vs CertiK 45/100 scenarios)
- Whale tracker integration test needs Ethereum token address (use UNI: `0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984`)

---

## Definition of Done

- [ ] All 15 ACs verified
- [ ] Each tool has unit test + integration test
- [ ] Feature flag works: ON → 7 agents, OFF → 6 agents (regression)
- [ ] Cost monitoring: Dune query credits + Nansen req counts logged to Prometheus
- [ ] Documentation: update [architecture-backend.md](../../../docs/architecture-backend.md) with new tool list
- [ ] Product brief updated: premium tier offering "unlocks Nansen + Dune" as selling point

---

## Traceability

- Design spec: `.claude/plans/harmonic-cuddling-glacier.md` § Sub-Epic 9-UX-4
- Supersedes: Story 9.2 (whale_tracker from Phase 2 backlog)
- Depends: Story 9-UX-1 (SourceAttributionMiddleware) + Story 9-UX-2 (Citation Chip 2.0 + design tokens)
- Impact: changes Epic 9 `_COMPREHENSIVE_AGENTS` from 6 → 7 when feature flag on

---

## Review Findings

(To be filled post-dev)
