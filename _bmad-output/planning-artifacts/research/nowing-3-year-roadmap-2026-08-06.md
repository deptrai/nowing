---
title: "Nowing — Long-Term Roadmap (3-Year Vision)"
project: Nowing
date: 2026-08-06
author: Mary (Business Analyst)
status: draft
---

# Nowing — Long-Term Roadmap (3-Year Vision)

**Purpose:** Strategic roadmap for Nowing from Year 1 (Prove) to Year 3 (Lead).

---

## Executive Summary

Nowing's 3-year journey: **Prove the lead intelligence + knowledge intelligence model in Vietnam → Scale across SEA → Lead in Asia with AI-native knowledge intelligence.**

| Year | Focus | Key Result |
|------|-------|-----------|
| **Y1** | Prove (Vietnam) | Entity-centric model works, lead-intelligence pilot live, 7+ domains |
| **Y2** | Scale (SEA) | 4 countries, domain depth, platform maturity |
| **Y3** | Lead (Asia) | AI agents, knowledge graph, industry verticals |

---

## Year 1: PROVE (Vietnam)

### Phase 1: Infrastructure (chainlens-research + shared conventions)

| What | Why | Success Criteria |
|------|-----|------------------|
| Canonical entity indexing (chainlens-research) | Transform from document storage to knowledge platform | Dedup F1 ≥ 0.92, Search recall ≥ 0.85 |
| AD-27 Convention | fingerprint/merge/search_text pattern for all domains | All domains follow convention |
| RLS at DB level | Workspace isolation | 0 cross-tenant incidents |

### Phase 2: Quick Wins (Epics 14-16)

| Epic | Domain | Effort | Value |
|------|--------|--------|-------|
| 14 | News (VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet) | 1-2d | Immediate search value |
| 15 | Finance (CafeF, Vietstock) | 2-4hrs + 1-2w | Investment research |
| 16 | Company (masothue, business.gov.vn) | 2-3d | Business intelligence |

### Phase 3: Expansion (Epic 17)

| Epic | Domain | Effort | Value |
|------|--------|--------|-------|
| 17 | E-commerce VN (Lazada, Shopee) | 4-6w + 8-12w | Pricing intelligence |

> **Code audit 2026-08-06:** Epics 18-20 removed — YouTube, Reddit, Instagram, TikTok, Google Search, Google Maps, Amazon, Walmart scrapers already exist in codebase. No new scrapers needed for these domains.

### Year 1 End State

- 10+ active domains (including existing 18 scrapers + lead-gen signal sources)
- Epic 21 lead-intelligence pilot launched in Vietnam (sales/SDR beachhead, Zalo/LinkedIn outreach, outcome-based pricing)
- 500+ workspaces using entity search
- Entity-centric model proven
- "From data to leads" vision demonstrated
- Legal/ToS + PII/consent gates for lead gen closed

---

## Year 2: SCALE (SEA)

### Phase 4: Geographic Expansion (Y2 Q1-Q2)

| Country | Priority | Sources | Effort |
|---------|----------|---------|--------|
| **Thailand** | P0 | Pantip, Kaidee, SET | 4-6 weeks |
| **Indonesia** | P1 | Kaskus, Tokopedia, IDX | 6-8 weeks |
| **Philippines** | P2 | Reddit PH, Shopee PH, PSE | 4-6 weeks |

**Key insight:** chainlens-research + AD-27 convention makes geographic expansion mechanical — new country = new scraper plugins, same infrastructure. Lead-intelligence expansion reuses the same signal-detection and enrichment pipeline.

### Phase 5: Domain Depth (Y2 Q2-Q3)

| Feature | What | Value |
|---------|------|-------|
| **Alerts** | Price drop alerts, news notifications | Proactive research |
| **Analytics** | Price trends, sentiment trends, hiring trends | Insights over time |
| **Predictions** | Historical data → likely outcomes | AI-powered foresight |

### Phase 6: Platform Maturity (Y2 Q3-Q4)

| Feature | What | Value |
|---------|------|-------|
| **API Marketplace** | Users publish custom connectors | Ecosystem growth |
| **Connector SDK** | Build-your-own-connector toolkit | Unlimited extensibility |
| **Team Analytics** | Research activity, coverage gaps | Team productivity |

### Year 2 End State

- 4 countries (VN + 3 SEA)
- 100+ active connectors
- Domain depth (alerts, analytics, predictions)
- Platform ecosystem live

---

## Year 3: LEAD (Asia)

### Phase 7: AI-Native Research (Y3 Q1-Q2)

| Feature | What | Value |
|---------|------|-------|
| **Autonomous Agents** | Agents research topics using Nowing MCP tools | Hands-off research |
| **Multi-step Research** | Planner → Executor → Verifier agent pipeline | Complex research automation |
| **Agent Memory** | Agents remember past research across sessions | Compounding knowledge |

### Phase 8: Knowledge Graph (Y3 Q2-Q3)

| Feature | What | Value |
|---------|------|-------|
| **Entity Relations** | Company → News → Finance → Social | Cross-entity intelligence |
| **Graph Queries** | "Show me all companies in X industry hiring Y role" | Relationship insights |
| **Graph Visualization** | Interactive entity relationship map | Visual discovery |

### Phase 9: Industry Verticals (Y3 Q3-Q4)

| Vertical | Features | Value |
|----------|----------|-------|
| **Finance** | Stock screening, portfolio tracking, earnings analysis | Investment professionals |
| **Legal** | Case law, regulatory tracking, compliance | Legal researchers |
| **Healthcare** | Clinical trials, drug data, practitioner directories | Medical researchers |
| **Sales / Lead Intelligence** | Signal detection, contact enrichment, multi-channel outreach, CRM sync | Sales teams and SDRs |

### Year 3 End State

- 10K+ autonomous agent tasks/day
- 1M+ knowledge graph entities
- Industry-specific features for Finance, Legal, Healthcare
- Nowing = knowledge layer for Asia

---

## Success Metrics

| Phase | Metric | Target |
|-------|--------|--------|
| Y1 End | Active domains | 10+ (including existing 18 scrapers + lead-gen signal sources) |
| Y1 End | Workspaces using entity search | 500+ |
| Y2 End | Countries | 4 |
| Y2 End | Active connectors | 100+ |
| Y3 End | Autonomous agent tasks/day | 10K+ |
| Y3 End | Knowledge graph entities | 1M+ |

---

## Strategic Principles

1. **Entity-first, not document-centric** — Every feature builds on canonical entities
2. **Lead intelligence + knowledge intelligence** — Lead gen is a first-class vertical, not a bolt-on
3. **Infrastructure before scale** — chainlens-research + Epic 21 data pipelines enable everything
4. **Quick wins before hard targets** — Prove model with News/Finance/Company + Vietnam lead-gen pilot first
5. **Convention over configuration** — AD-27 pattern makes new domains mechanical
6. **AI-native from day one** — MCP tools for agents and sales workflows, not just human UI
7. **Compliance-by-design** — Separate PII/consent pipelines for research and lead data

---

**Document Status:** Draft
**Author:** Mary (Business Analyst)
**Date:** 2026-08-06
