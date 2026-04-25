---
storyId: 9-UX-2
storyTitle: Crypto-Native Report Layout — Messari-grade presentation
epicParent: epic-9-crypto-orchestra
dependsOn: [Story 9-UX-1 DONE]
blocks: [Story 9-UX-3]
relatedFRs: [FR27 Comprehensive Analysis, FR35 Graceful Degradation]
relatedNFRs: [NFR-Q1 Accuracy (citations improve verifiability), NFR-UX-2 Professional Presentation]
priority: P0 (Phase 2 UX — core deliverable)
estimatedEffort: 3 weeks (1 FE + 0.5 BE) — 2 weeks layout + 1 week charts
status: ready-for-dev
createdAt: 2026-04-25
author: Sally (UX) + Mary (BA)
---

# Story 9-UX-2: Crypto-Native Report Layout

## User Story

**As a** crypto investor/researcher reading a Nowing comprehensive analysis,
**I want** the report presented like a Messari research doc — Token Hero card, sticky TOC, source-cited numbers, embedded charts, slide-in source detail —
**So that** I trust the analysis (verifiable), navigate efficiently (TOC), and extract insights quickly (charts + citations) instead of reading plain markdown walls.

**Bar to clear**: a user on Twitter would screenshot a section and say "wow, this looks professional."

---

## Context

### Current state (verified 2026-04-25)

The LDO token analysis renders as pure markdown: headings, tables, bullet lists. It's informative but NOT differentiated from ChatGPT-style output. Every number is bare (e.g., "TVL $3.2B") with zero source attribution.

### Desired state

- **Token Hero Card** at top (logo + live price + risk badge + conviction score + action buttons)
- **Sticky TOC** left sidebar, auto-highlights section in viewport
- **Every number** has Citation Chip 2.0 — click opens Source Detail Panel
- **Chart blocks** embedded (price history TradingView, TVL Recharts line, holder pie, yield bars)
- **Section attribution** badges ("Processed by tokenomics_analyst · Claude-4.6 · 2m ago")
- **Crypto color system**: gain/loss, risk tiers, per-source brand colors

### Reference standard

Messari Pro research report, Nansen Query wizard, Perplexity Pro citation style. Not ChatGPT.

---

## Prerequisites

- [ ] Story 9-UX-1 DONE — Research Lab collapses cleanly when report renders
- [ ] Recharts + lightweight-charts packages installed (add to package.json)
- [ ] TokenLogo source — TrustWallet assets CDN registered with CORS

---

## Acceptance Criteria

### AC1 — CryptoReportLayout entry routing (FE)

New file [crypto-report-layout.tsx](../../../nowing_web/components/new-chat/report/crypto-report-layout.tsx) renders instead of bare MarkdownText when:
- Message metadata `report_type === 'comprehensive_crypto'`, OR
- Markdown content contains `<!-- crypto-report-v2 -->` sentinel

Fallback: existing MarkdownText for non-comprehensive queries.

### AC2 — TokenHeroCard (FE)

New [token-hero-card.tsx](../../../nowing_web/components/new-chat/report/token-hero-card.tsx) displays:
- Token logo (48×48, TrustWallet CDN, fallback first letter in colored circle)
- Symbol + Full name + Live price (mocked OK for v1 — polling via CoinGecko /simple/price every 30s)
- 24h change (emerald/red)
- PriceSparkline (7d, TradingView Lightweight Charts)
- Risk Badge (🟢 LOW / 🟡 MED / 🔴 HIGH — from smart_contract_analyst section)
- Conviction Score (0-100, derived formula — stretch)
- HeroActionBar: Watchlist / Alert / Share / Export (wired in Story 9-UX-3)

### AC3 — ReportTOC sticky sidebar (FE)

New [report-toc.tsx](../../../nowing_web/components/new-chat/report/report-toc.tsx):
- Parses rendered markdown for H1/H2 headings
- Sticky left on `lg:` breakpoint (≥1024px); collapses to top dropdown on mobile
- IntersectionObserver highlights current section
- Click item → smooth scroll to section
- Icons per section type (🦄 overview, 📦 tokenomics, 🏗️ DeFi, 🛡️ security, etc.)

### AC4 — Citation Chip 2.0 (FE)

New [citation-chip-v2.tsx](../../../nowing_web/components/new-chat/report/citation-chip-v2.tsx), extends existing Citation:

Visual variants:
- **Default**: `[$3.2B 🦙 DeFiLlama · 2m ago]` — chip clickable
- **Verified**: `[$3.2B ✓ 🦙🟠]` — 2+ sources cross-check
- **Conflict**: `[$3.2B ⚠️ 🦙 · $3.05B 🟠]` — amber border, split value
- **Stale**: `[$3.2B 🦙 · 12m ago ⏰]` — muted gray

Data contract per plan file § CryptoDataCitation type.

### AC5 — Markdown transformer for citation syntax (FE)

[markdown-text.tsx](../../../nowing_web/components/assistant-ui/markdown-text.tsx) extended:
- Preprocess: replace `[[cite:id]]value[[/cite]]` with `<CitationChipV2 id="id" value="value" />`
- Preserve surrounding text + inline flow
- Register `id → CryptoDataCitation` map from message metadata

### AC6 — Chart code-block transformer (FE)

New transformer in markdown renderer recognizes:
```
​```chart:id
type: line | pie | bar | area
source: defillama | coingecko | ...
data: [JSON array]
​```
```
And renders the appropriate `<EmbeddedChart>` component.

### AC7 — Embedded charts (FE)

New folder [nowing_web/components/new-chat/report/embedded-charts/](../../../nowing_web/components/new-chat/report/embedded-charts/):
- `price-chart.tsx` — TradingView Lightweight candle/line
- `tvl-chart.tsx` — Recharts Line (dark-mode support)
- `holder-pie.tsx` — Recharts Pie with legend + percentage labels
- `yield-bars.tsx` — Recharts Bar (APY comparison)
- `vesting-chart.tsx` — Recharts Area (supply over time with unlock cliffs marked)
- All charts accept `data` prop + respect tailwind CSS variables for theming
- All charts code-split via `next/dynamic({ ssr: false })`

### AC8 — SourceDetailPanel slide-in (FE)

New [source-detail-panel.tsx](../../../nowing_web/components/new-chat/report/source-detail-panel.tsx):
- Triggered on Citation Chip click
- Slides in from right (drawer pattern, existing `Sheet` from shadcn)
- Shows: raw JSON API response (collapsible), fetch timestamp, agent attribution, "View on {provider}" external link
- For conflict chips: ConflictResolver — shows all source values side-by-side

### AC9 — Section attribution badges (FE)

Each Section header gets a small badge:
```
🏗️ DeFi Protocol — Lido Finance       🤖 defillama_analyst · claude-4.6 · 2m ago
```

### AC10 — Synthesis directive update (BE) [patch-6 GAP-3 simplification]

[chat_deepagent.py](../../../nowing_backend/app/agents/new_chat/chat_deepagent.py) `_SYNTHESIS_DIRECTIVE` updated:
- Instruct LLM to emit `[[cite:unique-id]]value[[/cite]]` syntax for every numeric fact — using IDs from the `citation_map` injected by `CitationHarvesterMiddleware` (AC14)
- Instruct LLM to emit ` ```chart:id ` code blocks for visual data
- Pass `citation_map: dict[str, CryptoDataCitation]` as metadata with final message (populated by AC14, not by LLM)
- Update each sub-agent system prompt to return **structured JSON** with `metric_name`, `value`, `unit`, `source`, `timestamp` for each numeric fact. Citation IDs are generated post-hoc by `CitationHarvesterMiddleware` (AC14) — **LLM never generates citation IDs**.

### AC11 — Crypto design tokens (FE)


[tailwind.config.js](../../../nowing_web/tailwind.config.js) + CSS vars per plan file:
- `--crypto-gain`, `--crypto-loss`, `--crypto-neutral`
- `--risk-low`, `--risk-medium`, `--risk-high`
- `--source-*` per provider

Used consistently across Hero, chips, charts, risk badges.

### AC14 — CitationHarvesterMiddleware (BE) [patch-6 GAP-3, GAP-4]

New middleware registered in BOTH main agent chain AND `_build_gp_middleware()` sub-agent chains. Scans each ToolMessage for numeric values (regex `\$[\d.]+[KMB]?`, `\d+(\.\d+)?%`, etc.), creates canonical citation objects:

```python
citation_id = sha256(f"{metric_name}:{provider}:{value}:{yyyymmdd}")
citation = CryptoDataCitation(
    id=citation_id,
    value=formatted_value,
    sources=[{provider, favicon, fetchedAt, rawValue, rawUrl}],
    conflict=detect_conflict_across_sources(metric_name),  # BE-side conflict detection
    agentAttribution=current_agent,
    confidence=min(3, source_count),
)
```

Aggregates into session-level `citation_map: dict[str, CryptoDataCitation]`. Synthesis prompt receives injected table: "Use IDs from this table when citing: [generated table]". LLM picks existing ID, never invents one. **Conflict detection runs backend-side** (CitationHarvester groups citations by `metric_name`, detects delta > 10% across sources) — frontend just renders `citation.conflict` field variant.

### AC12 — Responsive behavior

| Breakpoint | Layout |
|-----------|--------|
| `<640px` | Hero full-width, TOC dropdown, charts stack vertically, SourceDetailPanel full-screen takeover |
| `640-1023px` | Hero + sections stacked, TOC inline-top, 2-col charts where possible |
| `1024-1279px` | Hero + sticky TOC left, SourceDetailPanel slide-in |
| `1280px+` | Full: Hero + sticky TOC + report + SourceDetailPanel permanent-right when active |

### AC13 — Regression: non-crypto queries

When `report_type !== 'comprehensive_crypto'`, message renders with existing MarkdownText. No regression in non-crypto chat.

---

## Tasks

- [ ] **T1** (deps) — `pnpm add recharts lightweight-charts` + verify tree-shaking
- [ ] **T2** (FE) — Build `CryptoReportLayout` container + routing
- [ ] **T3** (FE) — Build `TokenHeroCard` + TokenLogo CDN wrapper + live-price hook
- [ ] **T4** (FE) — Build `ReportTOC` with IntersectionObserver
- [ ] **T5** (FE) — Build `CitationChipV2` + variants (default/verified/conflict/stale)
- [ ] **T6** (FE) — Extend markdown transformer for `[[cite:]]` syntax
- [ ] **T7** (FE) — Extend markdown transformer for ` ```chart: ` code blocks
- [ ] **T8** (FE) — Build 5 embedded-chart components (price, tvl, holder, yield, vesting)
- [ ] **T9** (FE) — Build `SourceDetailPanel` slide-in drawer
- [ ] **T10** (FE) — Section header + attribution badge pattern
- [ ] **T11** (FE) — Add crypto design tokens to tailwind.config + CSS
- [ ] **T12** (FE) — Responsive testing: mobile / tablet / desktop / wide
- [ ] **T13** (BE) — Update `_SYNTHESIS_DIRECTIVE` with citation + chart syntax instructions
- [ ] **T14** (BE) — Update each sub-agent system prompt to return `citation_id` + structured facts in ToolMessage
- [ ] **T15** (BE) — Build `CitationHarvesterMiddleware`: numeric extractor + canonical ID generator + conflict detector + `citation_map` aggregator; register in both main + sub-agent chains
- [ ] **T16** (E2E) — Playwright: send "phân tích toàn diện" → verify Hero + TOC + citations render
- [ ] **T17** (BE) — Update `_SYNTHESIS_DIRECTIVE` to inject `citation_map` table so LLM references existing IDs (no ID invention)

---

## Dev Notes

### Reusable components (existing)

- [Citation schema.ts](../../../nowing_web/components/tool-ui/citation/schema.ts) — extend `CryptoDataCitation` from existing `Citation` interface
- [Sheet component (shadcn)](../../../nowing_web/components/ui/sheet.tsx) — reuse for SourceDetailPanel drawer
- [MarkdownText](../../../nowing_web/components/assistant-ui/markdown-text.tsx) — extend transformer, don't fork
- KaTeX + GFM support unchanged

### Live price strategy v1

- Client-side polling CoinGecko `/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd&include_24hr_change=true` every 30s
- Rate limit: CoinGecko free tier = 30 req/min — fine for one token per report
- Cache result in TanStack Query with `staleTime: 30_000`
- Optional v2: WebSocket via Binance public stream (free) for real-time ticks

### Chart data strategy

Backend LLM emits chart code-block with JSON data array. Do NOT fetch additional API on render. All data flows through the already-captured tool results.

Example emission from sub-agent:
```markdown
### TVL Trend (7 days)

​```chart:tvl-uniswap-7d
type: line
source: defillama
xKey: date
yKey: tvlUsd
data: [{"date":"2026-04-18","tvlUsd":3.1e9}, ...]
​```
```

### Citation ID pattern

Format: `{metric}-{provider}-{yyyyMMdd}[-{hash}]`
Examples:
- `tvl-defillama-20260425`
- `price-coingecko-20260425`
- `holders-goplus-20260425-a3b9`

Ensures dedup across re-runs of the same query.

### Conflict detection

Extend existing `detectConflict()` in citation/schema.ts:
- Numeric delta > `CONFLICT_NUMERIC_DELTA` (currently 0.05)
- Categorical mismatch (e.g. "audit: passed" vs "audit: failed")
- Time-staleness: any source >10min from freshest

### Performance budget

- Bundle delta <150KB gzip (Recharts ~100KB + Lightweight Charts ~45KB)
- First contentful paint of report < 600ms after final-message received
- Citation chip hover delay: 0ms (popover should be instant)
- Chart render: lazy, skeleton while loading

---

## Definition of Done

- [ ] All 14 ACs verified
- [ ] 17 tasks done
- [ ] Storybook coverage: TokenHero, 4 chip variants, each chart, SourceDetailPanel
- [ ] E2E Playwright passes
- [ ] Responsive testing passes on sm/md/lg/xl
- [ ] Lighthouse: Performance ≥ 85, Accessibility ≥ 95, Best Practices ≥ 90
- [ ] Visual comparison: screenshot-diff against Figma mockups (TBD)
- [ ] Screen-reader: NVDA / VoiceOver announces citations + chart alt-text correctly

---

## Traceability

- Design spec: `.claude/plans/harmonic-cuddling-glacier.md` § Sub-Epic 9-UX-2
- Depends on: Story 9-UX-1 (Lab) — MUST be done first
- Blocks: Story 9-UX-3 (Interactive — needs report layout to add action bar + scenario panels into)
- Architecture doc update: new section "Report Rendering Pipeline" needed post-implementation

---

## Review Findings

(To be filled post-dev)
