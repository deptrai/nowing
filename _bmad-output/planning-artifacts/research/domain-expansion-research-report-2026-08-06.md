---
title: "Nowing Domain Expansion Research Report"
project: Nowing
date: 2026-08-06
author: Paige (Technical Writer) + Research Team
status: final
---

# Nowing Domain Expansion Research Report

**Date:** 2026-08-06
**Author:** Paige (Technical Writer) + Research Team
**Purpose:** Comprehensive analysis of scrapable domains for Nowing expansion, with priority matrix and implementation roadmap.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State](#current-state)
3. [Domain Analysis](#domain-analysis)
   - [E-commerce Vietnam](#e-commerce-vietnam)
   - [Finance Vietnam](#finance-vietnam)
   - [Company Data](#company-data)
   - [News & Content](#news--content)
   - [Social Listening](#social-listening)
   - [Education](#education)
4. [Priority Matrix](#priority-matrix)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Risk Assessment](#risk-assessment)
7. [Recommendations](#recommendations)
8. [Appendix: Platform Details](#appendix-platform-details)

---

## Executive Summary

Nowing currently covers 14 platforms across BĐS, Jobs, Social, Search, and Web. This report analyzes 20+ additional platforms across 6 domains to identify the highest-value expansion targets.

**Key findings:**
- **Quick wins (2-3 weeks):** News RSS (1 day), CafeF Finance (2-4 hours), masothue.com Company Data (2-3 days)
- **Medium effort (1-2 weeks each):** Lazada E-commerce, Forums, Coursera/edX
- **Hard targets (defer):** Shopee (8-12w), TikTok Shop (12-16w), Vietstock (1-2w)
- **Avoid for generic scraper expansion:** Facebook, Zalo, LinkedIn (high anti-bot + legal risk) — but these are approved as lead-intelligence signal/outreach channels under Epic 21 with legal/ToS review and provider contracts (see SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`).

**Recommendation:** Start Phase 1 (News + Finance + Company) in parallel. Run Epic 21 lead-gen signal/outreach channels (Zalo/LinkedIn) as a separate legal-gated workstream, not as general scraper expansion.

---

## Current State

### Existing Scrapers (14 platforms)

| Domain | Platforms | Aggregator |
|--------|-----------|------------|
| **BĐS** | batdongsan, chotot, muaban_bds | `vn_bds` ✅ |
| **Jobs** | vietnamworks, topcv, itviec | `vn_jobs` ✅ |
| **Social** | reddit, instagram, tiktok, youtube | ❌ |
| **Search** | google_search, google_maps | ❌ |
| **E-commerce** | amazon, walmart | ❌ |
| **Web** | web (generic crawl) | ❌ |
| **Deep Research** | chainlens (engine) | ❌ |

### Infrastructure Ready

- **AD-27 Convention:** fingerprint/merge/search_text pattern for new domains
- **chainlens-research canonical index:** persistence layer for cross-source dedup (Epic 13 dropped, canonical storage moved to chainlens-research per SCP 2026-08-08)
- **RLS:** workspace isolation at DB level
- **Celery:** async task pipeline for embedding backfill
- **nowing_evals:** test harness for benchmark validation

---

## Domain Analysis

### E-commerce Vietnam

**Market context:** Vietnam B2C e-commerce ~$32B (12% of total retail). Duopoly: Shopee (56% GMV) + TikTok Shop (41% GMV). Top-4 platforms generated $16.4B GMV in 2025 (+34.75% YoY).

| Platform | Market Share | Scrape Difficulty | Effort | API? | Legal Risk |
|----------|-------------|-------------------|--------|------|------------|
| **Shopee** | 56% | 🔴 Hard | 8-12w | Seller-only | Medium-High |
| **TikTok Shop** | 41% | 🔴🔴 Very Hard | 12-16w | Partner-only | High |
| **Lazada** | ~2% | 🟡 Medium | 4-6w | Seller-only | Medium |

**Key findings:**
- Shopee search is login-gated; product pages partially accessible
- TikTok Shop is app-locked (no public web catalog)
- Lazada has public product pages with moderate anti-bot
- All platforms require residential proxies + anti-detect browsers for production scraping
- Official APIs are seller-only (no marketplace-wide catalog access)

**Existing tools:** Apify, Bright Data, ScrapingBee, Oxylabs offer paid scrapers ($49-200/mo).

**Recommendation:** Start with Lazada (medium effort, public data). Defer Shopee/TikTok Shop until Phase 1-2 prove ROI. Consider third-party APIs as faster MVP.

---

### Finance Vietnam

**Market context:** Vietnam financial data is highly centralized. CafeF and Vietstock dominate. IFRS convergence (2025-2028) means financial statement formats will change.

| Platform | Data Coverage | Scrape Difficulty | Effort | API? |
|----------|--------------|-------------------|--------|------|
| **CafeF** | Prices, financials, news | 🟢 Easy | 2-4 hrs | ✅ Unofficial (no key) |
| **Vietstock** | 3000+ companies, 130K+ statements | 🔴 Hard | 1-2w | ⚠️ Auth tokens |
| **TradingView** | Technical indicators, screener | 🟡 Medium | 3-5d | ⚠️ WebSocket lib |

**Key findings:**
- CafeF has unofficial public API (no auth needed) — financial statements, news, market data
- Vietstock is most comprehensive but requires cookie-based auth + anti-forgery tokens
- TradingView covers HOSE tickers only (limited VN-specific fundamentals)
- SSC (State Securities Commission) data is PDF-heavy, requires OCR

**Existing tools:** `vnstock` Python lib, `cafef-financial-mcp` server, `VietFin` modern wrapper.

**Recommendation:** Start with CafeF (2-4 hours via unofficial API). Add Vietstock for deep financials (1-2 weeks). Use TradingView for technical analysis (3-5 days).

---

### Company Data

**Market context:** Vietnam has 1M+ registered companies. Data is scattered across government portals and private directories.

| Source | Data | Scrape Difficulty | Effort | Method |
|--------|------|-------------------|--------|--------|
| **masothue.com** | 2M+ businesses, tax codes | 🟢 Easy | 2-3d | HTML scrape |
| **business.gov.vn** | Official registration | 🟡 Medium | 1w | Government portal |
| **doanhnghiep.vn** | Company profiles + news | 🟢 Easy | 1-2d | RSS + HTML |
| **LinkedIn** | Company profiles, employee count | 🔴🔴 Very Hard | 2-4w | High legal risk |

**Key findings:**
- masothue.com is most scrapeable (2M+ businesses, simple HTML)
- Government portals have official data but complex forms + CSRF tokens
- LinkedIn is very high risk (aggressive anti-bot, CFAA concerns, ToS enforcement)

**Recommendation:** Start with masothue.com (2-3 days). Add doanhnghiep.vn via RSS (1-2 days). Avoid LinkedIn.

---

### News & Content

**Market context:** Vietnam has 4 major news portals with excellent RSS support. This is the highest signal-to-effort ratio domain.

| Source | RSS Feeds | Scrape Difficulty | Effort | Data |
|--------|-----------|-------------------|--------|------|
| **VnExpress** | ✅ 30+ categories | 🟢 Easy (RSS) | 1d | Full article + metadata |
| **Tuổi Trẻ** | ✅ RSS + sitemap | 🟢 Easy (RSS) | 1d | Full article + metadata |
| **Dân Trí** | ✅ RSS | 🟢 Easy (RSS) | 1d | Full article + metadata |
| **Vietnamnet** | ✅ RSS | 🟢 Easy (RSS) | 1d | Full article + metadata |

**Key findings:**
- All 4 major portals have official RSS feeds (zero anti-bot)
- RSS is officially provided — safe to use, no ToS violation
- VnExpress has Cloudflare for HTML scraping but RSS bypasses it
- Sitemaps provide full URL lists with timestamps for incremental crawling

**Recommendation:** Integrate all 4 portals via RSS in 1-2 days. This is the quickest win with immediate user value.

---

### Social Listening

**Market context:** Facebook dominates VN social media, but is extremely hard to scrape. Forums offer high sentiment value with low effort.

| Platform | Data Value | Scrape Difficulty | Effort | Legal Risk |
|----------|-----------|-------------------|--------|------------|
| **Facebook** | ★★★★★ | 🔴🔴 Very Hard | 2-4w | High (ToS) |
| **Zalo** | ★★★★☆ | 🔴🔴 Very Hard | 4+w | High (closed) |
| **Forums (Tinh Tê/Voz)** | ★★★★☆ | 🟡 Medium | 1-2w | Low |
| **Twitter/X** | ★★★☆☆ | 🟡 Medium | 1-2w | Medium |

**Key findings:**
- Facebook: very aggressive anti-bot, PPCA permission required for API, high legal risk
- Zalo: closed ecosystem, unofficial APIs unstable, 4+ weeks for unreliable access
- Forums: long-form discussions, rich sentiment data, low legal risk
- Twitter: low VN penetration, paid API now ($100-5000/mo), third-party APIs available

**Recommendation:** Start with forums (Tinh Tê, Voz) — highest signal-to-effort ratio. Avoid Facebook/Zalo. Twitter via third-party APIs if needed.

---

### Education

**Market context:** Online education growing rapidly. Course metadata is public and factual.

| Platform | Data | Scrape Difficulty | Effort | API? |
|----------|------|-------------------|--------|------|
| **Coursera** | Courses, skills, ratings | 🟡 Medium | 1-2w | Limited/Beta |
| **edX** | Courses, providers | 🟡 Medium | 1-2w | Beta (JWT) |
| **TopCV/Local** | VN-specific courses | 🟢 Easy | 1w | None |
| **University Catalogs** | Course codes, descriptions | 🟢 Easy | 1-2w | None |

**Key findings:**
- Coursera/edX have undocumented public API endpoints
- Apify has ready-made scrapers for both platforms
- Vietnamese platforms (TopCV, Unica, Kyna) have low anti-bot
- University catalogs are explicitly public information (very low legal risk)

**Recommendation:** Start with TopCV/local platforms (1 week, easy). Add Coursera/edX via Apify or undocumented APIs (1-2 weeks).

---

## Priority Matrix

### By Effort-Value Ratio

| Priority | Domain | Target | Effort | Value | Risk |
|----------|--------|--------|--------|-------|------|
| **P0** | News | VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet | 1-2d | ★★★★★ | Low |
| **P0** | Finance | CafeF | 2-4hrs | ★★★★☆ | Low |
| **P0** | Company | masothue.com | 2-3d | ★★★★☆ | Low |
| **P1** | E-commerce | Lazada | 4-6w | ★★★★☆ | Medium |
| **P1** | Social | Forums (Tinh Tê, Voz) | 1-2w | ★★★★☆ | Low |
| **P1** | Education | TopCV, Coursera, edX | 1-2w | ★★★☆☆ | Low |
| **P2** | E-commerce | Shopee | 8-12w | ★★★★★ | Medium-High |
| **P2** | Finance | Vietstock | 1-2w | ★★★★☆ | Medium |
| **P3** | E-commerce | TikTok Shop | 12-16w | ★★★★★ | High |
| **Avoid** | Social | Facebook, Zalo, LinkedIn | 4+w | ★★★★☆ | High |

---

## Implementation Roadmap

### Phase 1: Quick Wins (2-3 weeks)

```
Week 1:
├── Day 1-2: News RSS integration (VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet)
├── Day 2-3: CafeF Finance integration (unofficial API)
└── Day 3-5: masothue.com company data (HTML scrape)

Week 2-3:
├── Testing + validation (nowing_evals canonical suite)
├── Documentation + user-facing features
└── Release Phase 1
```

**Deliverables:**
- 4 news portals via RSS (30+ category feeds)
- CafeF financial data (prices, statements, news)
- masothue.com company directory (2M+ businesses)
- Canonical entity persistence for all Phase 1 sources

### Phase 2: Medium Effort (3-6 weeks)

```
Week 3-4: Lazada scraper (public product pages, moderate anti-bot)
Week 4-5: Forum scrapers (Tinh Tê, Voz — sentiment analysis)
Week 5-6: Education platforms (TopCV, Coursera, edX)
```

**Deliverables:**
- Lazada product data (price, seller, ratings)
- Forum sentiment data (long-form discussions)
- Education course data (skills trends)

### Phase 3: Hard Targets (defer until Phase 1-2 prove ROI)

```
Week 7+: Shopee scraper (8-12 weeks, residential proxies + anti-detect)
Week 10+: Vietstock (1-2 weeks, auth token management)
Week 14+: TikTok Shop (12-16 weeks, app-level parsing)
```

---

## Risk Assessment

### Legal Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ToS violation (scraping prohibited) | Medium | High | Use RSS APIs where possible; respect rate limits |
| PII exposure | Low | Critical | AD-25 redaction pipeline; no PII in golden records |
| Cross-workspace data leak | Low | Critical | RLS at DB level; raw SQL bypass test |
| Copyright infringement (news content) | Medium | Medium | RSS is official; don't republic full text commercially |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Anti-bot blocking | High | Medium | Residential proxies, anti-detect browsers, rate limiting |
| API/DOM changes | High | Medium | Monitor + alert; graceful degradation |
| Fingerprint drift | Medium | High | Stable keys (address + area, not content-hash) |
| Concurrent write races | Low | High | `SELECT ... FOR UPDATE` or upsert with ON CONFLICT |
| Embedding dimension mismatch | Low | Medium | Store `embedding_model_name`; backfill on change |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Maintenance burden | High | Medium | Start with RSS/API sources; defer HTML scraping |
| Storage bloat (MergeHistory) | Medium | Medium | Retention policy (90 days); compress old snapshots |
| Source reliability | Medium | Low | Degrade gracefully; `degraded=true` flag |

---

## Recommendations

### Immediate Actions

1. **Start Phase 1 in parallel** — News RSS (1d), CafeF (2-4hrs), masothue.com (2-3d)
2. **Use existing infrastructure** — AD-27 convention, Epic 13 canonical entity, Celery async pipeline
3. **Validate with nowing_evals** — 9 P0 tests before release

### Strategic Decisions

1. **Avoid Facebook/Zalo/LinkedIn** — high anti-bot + legal risk, low ROI
2. **Use third-party APIs for hard targets** — Apify, Bright Data for Shopee/TikTok Shop
3. **Prioritize RSS/API sources** — lower maintenance burden than HTML scraping
4. **Defer Phase 3** — until Phase 1-2 prove user value and ROI

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Phase 1 ship time | ≤ 3 weeks | Calendar time |
| Dedup F1 score | ≥ 0.92 | nowing_evals benchmark |
| Search recall@10 | ≥ 0.85 | nowing_evals benchmark |
| Search p95 latency | < 500ms | Performance test |
| Cross-tenant incidents | 0 | Security audit |
| PII leaks | 0 | Automated PII scan |

---

## Appendix: Platform Details

### E-commerce Platforms

**Shopee Vietnam** (shopee.vn)
- URL: `shopee.vn/product/{shop_id}/{product_id}`
- Data: product name, price, rating, sold count, shop info
- Anti-bot: Login-gated search, CAPTCHA, fingerprinting, rate limiting
- Legal: ToS prohibits scraping; Vietnam Cybersecurity Law applies

**Lazada Vietnam** (lazada.vn)
- URL: `lazada.vn/products/{product-name}-i{product_id}.html`
- Data: product ID, title, price, rating, seller, variants
- Anti-bot: Moderate protection, more lenient than Shopee
- Legal: ToS prohibits scraping; lower enforcement posture

**TikTok Shop Vietnam** (shop.tiktok.com)
- Data: product name, price, sold count, rating, shop metadata
- Anti-bot: App-locked, signed requests, device attestation
- Legal: ToS prohibits scraping; bypassing app protections = higher risk

### Finance Platforms

**CafeF** (cafef.vn)
- API: Unofficial public API (no key needed)
- Endpoints: `get_balance_sheet`, `get_income_statement`, `get_cash_flow`
- Rate limit: ~20 req/min (guest)
- Tooling: `cafef-financial-mcp` server, `vnstock` Python lib

**Vietstock** (vietstock.vn)
- Data: 3000+ companies, 130K+ financial statements, 20+ years market data
- API: Unofficial only (requires cookies + anti-forgery tokens)
- Report types: CDKT, KQKD, LC, CSTC, CTKH
- Tooling: `Scrape-Finance-Data-v2` (Scrapy)

### News Platforms

**VnExpress** (vnexpress.net)
- RSS: `https://vnexpress.net/rss` (30+ category feeds)
- Data: title, link, description, pubDate, category
- Anti-bot: Cloudflare for HTML; RSS bypasses it

**Tuổi Trẻ** (tuoitre.vn)
- RSS: `https://tuoitre.vn/rss.htm`
- Sitemap: `https://tuoitre.vn/sitemaps/category.rss`

**Dân Trí** (dantri.com.vn)
- RSS: Category-based feeds available

**Vietnamnet** (vietnamnet.vn)
- RSS: Category-based feeds available

---

**Document Status:** Final
**Research Period:** 2026-08-06
**Source Verification:** All platform data verified against live sources and existing tooling.
