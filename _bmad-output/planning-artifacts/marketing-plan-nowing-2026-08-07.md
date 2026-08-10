---
title: "Nowing — Marketing Plan & Execution Package"
project: Nowing
date: 2026-08-07
author: Luis (Founder) + Mary (Business Analyst)
status: final
---

# Nowing — Marketing Plan & Execution Package

**Purpose:** Concrete, actionable marketing plan to acquire first 500 workspace users and 5,000 GitHub stars in 6 months.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Target Segments & Personas](#2-target-segments--personas)
3. [Positioning & Messaging](#3-positioning--messaging)
4. [Marketing Channels](#4-marketing-channels)
5. [Content Calendar — 4 Weeks](#5-content-calendar--4-weeks)
6. [Email Templates](#6-email-templates)
7. [Launch Checklist](#7-launch-checklist)
8. [Budget & Resources](#8-budget--resources)
9. [KPIs & Tracking](#9-kpis--tracking)
10. [Dogfooding Strategy](#10-dogfooding-strategy)

---

## 1. Executive Summary

**Vision:** Nowing = "From data to leads" — the lead intelligence + knowledge intelligence platform where raw data from every source becomes leads and actionable knowledge.

**Beachhead (core):** AI Agent Builders (MCP-native, self-host, 50+ tools) → expand to BDS professionals → market researchers → enterprise teams.

**Beachhead (lead-gen pilot):** Sales team / SDR (Vietnam B2B SaaS, IT outsourcing, agency, local business) via Zalo/LinkedIn/B2B communities → expand to SEA.

**Goal:** 500 active workspaces + 5,000 GitHub stars in 6 months.

**Strategy:** PLG + Community-Led growth. Dogfood everything — use Nowing to market Nowing.

---

## 2. Target Segments & Personas

### Persona 1: Tùng (AI Agent Builder)
- **Age:** 28, Software Engineer at fintech startup, HCMC
- **Pain:** Agent mất context mỗi session, phải paste lại toàn bộ
- **Behavior:** Active on GitHub, HN, Twitter; uses Claude Code/Cursor
- **Need:** Persistent memory + MCP tools
- **WTP:** $29-49/mo
- **Reach:** GitHub stars, HN Show, MCP registry, Twitter/X

### Persona 2: Mai (BDS Sales Agent)
- **Age:** 35, Real estate agent, mobile-first, HCMC
- **Pain:** Track giá nhà trên 3 site, không biết tin nào mới
- **Behavior:** Posts on batdongsan, uses Zalo for clients, Facebook groups
- **Need:** Price tracking, competitor monitoring, client CRM
- **WTP:** $29-99/mo
- **Reach:** Facebook groups, Zalo communities, batdongsan.com.vn

### Persona 3: Phúc (Market Researcher)
- **Age:** 32, Senior Analyst at consulting firm, Hanoi
- **Pain:** Research trùng lặp, khó track xu hướng theo thời gian
- **Behavior:** Uses Excel + manual search, values citations
- **Need:** Entity dedup, cross-source synthesis, temporal tracking
- **WTP:** $49-199/mo
- **Reach:** LinkedIn, research communities, Zalo

### Persona 4: Enterprise Team Lead
- **Age:** 40, Head of Research at corporation
- **Pain:** Team knowledge siloed, people leave → knowledge lost
- **Behavior:** LinkedIn active, prefers demo before trial
- **Need:** Team memory, RBAC, compliance, self-host
- **WTP:** $99-999/mo
- **Reach:** LinkedIn outbound, partnerships, conferences

---

## 3. Positioning & Messaging

### One-Sentence Promise
> **Nowing (now + knowing) — where data from every source becomes leads and knowledge. All sources. One truth. Forever.**

### Tagline Options
| Option | Tagline |
|--------|---------|
| A | "From data to knowing" |
| B | "All sources. One truth. Forever." |
| C | "Research without duplicates. Memory without limits." |

### Positioning per Segment

| Segment | Headline | Pain Hook |
|---------|----------|-----------|
| Agent Builder | "Give your AI agent a memory that lasts" | "Stop rebuilding context every session" |
| BDS Sales | "Track every listing. Never miss a deal." | "3 sources → 1 golden record" |
| Sales / SDR (Epic 21) | "Know your next buyer before they know you" | "Real-time signals, verified contacts, and Zalo/LinkedIn outreach in one loop" |
| Researcher | "Research without duplicates" | "4-7 hours/week wasted on manual cross-referencing" |
| Enterprise | "Your team's research memory, self-hosted" | "People leave. Knowledge shouldn't." |

### Key Messages
1. **Lead Intelligence:** "Find the right buyer at the right moment — real-time signals, verified contacts, and CRM sync."
2. **Entity-Centric:** "Others store documents. Nowing deduplicates data from every source into canonical entities."
3. **Provenance Built-In:** "Every fact links to source URL — verify in one click."
4. **Temporal Tracking:** "See price changes, hiring trends, news sentiment, and buyer intent over time."
5. **Self-Host / OSS:** "Apache-2.0 core. Your data never leaves your infrastructure."
6. **MCP-Native:** "50+ tools for AI agents. Works with Claude Code, Cursor, OpenCode."

### "Khác gì X" (Competitive Response)

| Competitor | Their Claim | Our Response |
|------------|-------------|--------------|
| Mem0 | "Memory for agents" | "Không có live web ingestion, không có entity dedup" |
| Zep | "Temporal knowledge graph" | "Không self-host, expensive, không có nguồn Việt Nam" |
| Onyx | "Open-source research" | "Không có memory layer" |
| Manual Excel | "Miễn phí" | "4-7 giờ/tuầng lãng phí → $29/tháng tiết kiệm hơn" |

---

## 4. Marketing Channels

### Channel Priority Matrix

| Priority | Channel | Segment | Effort | Impact | Weekly Tactics |
|----------|---------|---------|--------|--------|----------------|
| **1** | GitHub | Agent Builder | Low | High | README optimization, discussions, good first issues, star campaign |
| **2** | Hacker News | Agent Builder | Low | High | Show HN (Tue-Thu PST), comment engagement |
| **3** | Reddit | Agent Builder | Medium | High | r/selfhosted, r/MachineLearning, r/ClaudeAI — value posts |
| **4** | Twitter/X | All | Medium | High | Research threads, demos, AI community engagement |
| **5** | LinkedIn | Researcher + Enterprise | Medium | Medium | Thought leadership, case studies |
| **6** | Email Outreach | BDS + Researcher + Enterprise | High | High | Personalized research → email → gift link |
| **7** | Zalo/Facebook Groups | BDS | Medium | Medium | Group participation, value-add posts |
| **8** | Zalo/Facebook B2B Groups | Sales / SDR | Medium | High | Value-add posts, signal alerts, pitch decks in local communities |
| **9** | LinkedIn | Sales / SDR + Researcher + Enterprise | Medium | High | Case studies, signal notifications, SDR outreach templates |
| **10** | Content/Blog | All | Medium | Medium | SEO-optimized tutorials, comparisons, Vietnam lead-gen playbooks |
| **11** | Partnerships | Enterprise | High | High | AI agent platforms, research tools, sales/CRM partners |

### Channel-Specific Tactics

#### GitHub (Primary)
- [ ] README: compelling demo GIF, one-sentence value prop, quickstart
- [ ] Discussions: enable, seed with FAQ, show roadmap
- [ ] Good First Issues: label 10+ beginner-friendly issues
- [ ] Star campaign: ask friends, HN visitors to star
- [ ] Release notes: every release = marketing opportunity

#### Hacker News
- [ ] **Show HN:** Launch on Tuesday-Thursday 8-10 AM PST
- [ ] Title: "Nowing: Open-source entity dedup for AI agents (self-hosted)"
- [ ] Engage comments actively for first 4 hours
- [ ] Follow-up: "Thank you HN" post with community feedback

#### Twitter/X
- [ ] Daily: 1 research thread or demo
- [ ] 3x/week: Engage with AI agent community
- [ ] Weekly: Progress update (GitHub stars, features shipped)
- [ ] Hashtags: #opensource #aiagents #mcp #selfhosted

#### Email Outreach
- [ ] Build lead list: 50 prospects/day via Nowing scrapers
- [ ] Personalize: research each prospect's recent news
- [ ] Gift link: free beta access + 1000 credits
- [ ] Follow-up: Day 3, Day 7, Day 14

---

## 5. Content Calendar — 4 Weeks

### Week 1: Foundation

| Day | Content | Channel | Owner |
|-----|---------|---------|-------|
| Mon | "Why I built Nowing" personal story | Twitter thread | Luis |
| Tue | Show HN post + engage comments | HN + GitHub | Luis |
| Wed | README optimization + demo GIF | GitHub | Luis |
| Thu | "Entity deduplication explained" blog post | Blog + LinkedIn | Luis |
| Fri | Setup Zalo/Facebook group presence | Social | Luis |
| Sat | Build lead list (50 prospects) | Nowing workspace | Automation |
| Sun | Draft email templates | Email | Luis |

### Week 2: Community Building

| Day | Content | Channel | Owner |
|-----|---------|---------|-------|
| Mon | "State of AI Memory 2026" research report | Blog + Twitter | Luis |
| Tue | Engage r/selfhosted, r/MachineLearning | Reddit | Luis |
| Wed | "Track BDS prices with Nowing" tutorial | Blog + Facebook groups | Luis |
| Thu | GitHub good first issues + discussions | GitHub | Luis |
| Fri | First email outreach batch (50 emails) | Email | Automation |
| Sat | Partner outreach: Claude, Cursor, Obsidian | Email/LinkedIn | Luis |
| Sun | Analytics: Week 1 metrics review | Dashboard | Luis |

### Week 3: Partnership + Expansion

| Day | Content | Channel | Owner |
|-----|---------|---------|-------|
| Monday | "Nowing + Claude Code" integration tutorial | Blog + Twitter | Luis |
| Tuesday | LinkedIn article: "Research without duplication" | LinkedIn | Luis |
| Wednesday | Engage AI agent Twitter community | Twitter | Luis |
| Thursday | Partnership demo calls | Zoom | Luis |
| Friday | Second email batch + follow-ups | Email | Automation |
| Saturday | Content: "Vietnam job market trends" (using Nowing data) | Blog + LinkedIn | Luis |
| Sunday | Analytics: Week 2 metrics review | Dashboard | Luis |

### Week 4: Launch Prep

| Day | Content | Channel | Owner |
|-----|---------|---------|-------|
| Monday | Product Hunt launch prep (screenshots, video) | PH | Luis |
| Tuesday | Pre-launch email to waitlist | Email | Luis |
| Wednesday | "How Nowing uses Nowing" dogfooding post | Blog + Twitter | Luis |
| Thursday | Final launch checklist review | Internal | Luis |
| Friday | **LAUNCH DAY** (Product Hunt + HN + Twitter) | All | Luis |
| Saturday | Launch follow-up + engagement | All | Luis |
| Sunday | Month 1 retrospective + Month 2 planning | Internal | Luis |

---

## 6. Email Templates

### Template A: AI Agent Builder (Tùng)

```
Subject: Your agent forgot everything again?

Hi [Name],

I noticed you're building with [Claude Code/Cursor] — same problem I had: every session starts from zero.

I built Nowing to fix this: persistent memory for AI agents + entity deduplication across sources.

Quick demo: [2-min video link]

Gift: Free beta access + 1000 deep-research credits → [gift link]

Worth 2 minutes to try?

— Luis
Founder, Nowing
```

### Template B: BDS Professional (Mai)

```
Subject: Track giá BĐS không cần mở 3 tab

Chào [Name],

Em thấy chị đang bán BĐS trên batdongsan — việc theo dõi giá + tin mới mỗi ngày tốn nhiều thời gian.

Anh Luis xây Nowing để tự động: gộp tin từ 3 site → 1 golden record, cảnh báo khi giá thay đổi.

Demo: [video link]

Quà tặng: Truy cập beta miễn phí + 1000 credits → [link gift]

Có 2 phút thử không ạ?

— Luis
Founder, Nowing
```

### Template C: Researcher (Phúc)

```
Subject: Research without duplication (save 4-7 hrs/week)

Hi [Name],

Manual cross-referencing across sources is the hidden tax on research — 4-7 hours/week per analyst.

Nowing auto-deduplicates entities across sources, tracks changes over time, and links every fact to its origin.

Case study: [link]

Gift: Free beta + 1000 credits → [link]

Best,
Luis
Founder, Nowing
```

### Template D: Enterprise Lead

```
Subject: Team research memory that compounds

Hi [Name],

When analysts leave, their research leaves with them. Nowing makes team knowledge persistent and searchable.

Self-hosted, RBAC, SOC 2-ready. Used by [X] teams.

Worth a 15-min demo?

— Luis
Founder, Nowing
P.S. Free pilot for teams under 20 people.
```

### Follow-Up Sequence

| Day | Content |
|-----|---------|
| +3 | "Chắc bạn bận — câu hỏi ngắn: team [company] research kiểu gì?" |
| +7 | "New feature: Entity Dedup — 3 nguồn → 1 golden record" |
| +14 | "Last try — beta access còn mở" |

---

## 7. Launch Checklist

### 2 Weeks Before Launch

- [ ] README: demo GIF, quickstart, feature badges
- [ ] Landing page: clear value prop + CTA
- [ ] Demo video: 2 minutes, screen recording + voiceover
- [ ] Product Hunt assets: logo, gallery images, first comment
- [ ] Email waitlist: landing page with signup form
- [ ] Social media: profile optimized, pinned post ready
- [ ] Press kit: logo, screenshots, founder bio, fact sheet
- [ ] Analytics: install PostHog/Plausible on website

### 1 Week Before Launch

- [ ] Draft all launch posts (HN, Twitter, Reddit, LinkedIn)
- [ ] Prepare email announcement to waitlist
- [ ] Reach out to 10 friends for initial stars/comments
- [ ] Test full onboarding flow (install → first search → upgrade)
- [ ] Prepare "Thank you HN" follow-up post
- [ ] Schedule social media posts for launch week

### Launch Day (Friday recommended)

| Time | Action |
|------|--------|
| 00:01 PST | Product Hunt launch |
| 00:30 PST | HN Show post |
| 01:00 PST | Twitter thread |
| 02:00 PST | LinkedIn post |
| 03:00 PST | Reddit r/selfhosted + r/MachineLearning |
| 08:00 PST | Email waitlist announcement |
| All day | Engage every comment (HN, Twitter, PH, Reddit) |
| Evening | "Thank you" post with Day 1 stats |

### Post-Launch (Week 1)

- [ ] Daily engagement on all platforms
- [ ] Collect feedback → GitHub issues
- [ ] Write "What I learned from launching" post
- [ ] Reach out to bloggers/YouTubers for reviews
- [ ] Start content calendar (Week 2-4)

---

## 8. Budget & Resources

### Monthly Budget (Solo Operator)

| Item | Cost | Notes |
|------|------|-------|
| **Nowing Cloud** | $0 | Use own product (dogfooding) |
| **Email tool** | $0 | Resend free tier (100 emails/day) |
| **Analytics** | $0 | PostHog free tier |
| **Design** | $0 | Figma free + Canva |
| **Video** | $0 | OBS + Descript free tier |
| **Proxies (scraping)** | $50 | Residential proxies for prospect research |
| **Domain + hosting** | $20 | nowing.net + Vercel |
| **Total** | **$70/month** | |

### Time Allocation (Luis — 20 hrs/week marketing)

| Activity | Hours/Week | Notes |
|----------|-----------|-------|
| Content creation | 6 | Threads, blog posts, demos |
| Community engagement | 4 | HN, Reddit, Twitter, GitHub |
| Email outreach | 4 | Personalized research + send |
| Analytics + optimization | 2 | Track metrics, adjust |
| Partnership outreach | 2 | AI platforms, research tools |
| Planning + learning | 2 | Competitive research, trends |
| **Total** | **20 hrs** | |

---

## 9. KPIs & Tracking

### North Star Metrics

| Metric | 3-Month Target | 6-Month Target |
|--------|---------------|----------------|
| GitHub Stars | 2,000 | 5,000 |
| Active Workspaces | 100 | 500 |
| Weekly Active Users | 200 | 1,000 |
| Cloud Signups | 50 | 200 |
| Email List | 500 | 2,000 |

### Channel Metrics

| Channel | Metric | Target |
|---------|--------|--------|
| GitHub | Stars + forks | 2K stars |
| HN | Upvotes + comments | 500+ upvotes |
| Twitter | Impressions + followers | 100K impressions |
| Reddit | Upvotes + comments | 200+ upvotes |
| Email | Open rate + response | 40% open, 15% response |
| Blog | Organic traffic | 5K visits/month |

### Tracking Dashboard

| Tool | What it tracks |
|------|---------------|
| PostHog | Website events, signups, conversions |
| GitHub | Stars, forks, clones, issues |
| Twitter Analytics | Impressions, followers, engagement |
| Email (Resend) | Sends, opens, clicks, bounces |
| Manual spreadsheet | Channel attribution, CAC, LTV |

### Weekly Review Checklist

- [ ] GitHub stars growth rate
- [ ] New workspaces created
- [ ] Email metrics (opens, clicks, responses)
- [ ] Social media engagement
- [ ] Top-performing content this week
- [ ] Adjust next week's plan based on data

---

## 10. Dogfooding Strategy

### "Nowing Markets Itself"

| Marketing Activity | How Nowing Helps | Automation |
|-------------------|-----------------|-------------|
| **Prospect Research** | Scrapers (BDS, Jobs) + entity profiles | Daily scrape → entity enrichment |
| **Lead Scoring** | Confidence score + source count | Auto-score → threshold alert |
| **Email Personalization** | Synthesis per prospect | Generate draft per prospect |
| **Content Creation** | Research → synthesis → blog post | Weekly news fetch → commentary |
| **Social Monitoring** | Track trending topics + sentiment | Daily scan → auto-draft tweets |
| **Partnership Tracking** | Company news + funding alerts | Weekly scan → outreach trigger |

### Automation Workflow

```
Every day (automated):
1. Scrape target domains for new data
2. Enrich entity profiles (tax, social, news)
3. Score leads (tech + budget + need)
4. Trigger outreach if score > threshold

Every hour (automated):
1. Check for new high-score leads
2. Research prospect (Nowing synthesis)
3. Generate personalized email draft
4. Queue for Luis to review + send

Every week (automated):
1. Fetch latest domain news (BDS, Jobs, Tech)
2. Generate market commentary
3. Draft blog post / Twitter thread
4. Queue for Luis to review + publish
```

### Dogfooding KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Marketing workspace entities | 1,000+ | Canonical entity count |
| Automated emails sent | 50/week | Email queue |
| Auto-generated content pieces | 4/week | Blog + social queue |
| Time saved vs manual | 80% | Hours comparison |

---

## Appendix: Quick Reference

### Elevator Pitch (30 seconds)

> "Nowing is open-source research memory for AI agents. It deduplicates data from every source into canonical entities, tracks changes over time, and lets agents remember across sessions. Self-hosted, MCP-native, 50+ connectors. We help researchers, analysts, and sales teams stop wasting 4-7 hours/week on manual cross-referencing."

### One-Liner for Social Bio

> "Nowing — from data to knowing. Entity dedup + provenance + team memory for researchers and AI agents. Self-hosted, OSS."

### Launch Hashtags

`#opensource` `#aiagents` `#mcp` `#selfhosted` `#entityresolution` `#researchmemory` `#deduplication`

### Key URLs

- Website: https://nowing.net
- GitHub: https://github.com/deptrai/nowing
- Docs: https://nowing.net/docs
- Demo: https://nowing.net/demo

---

**Document Status:** Final
**Next Review:** 2026-09-07 (30 days)
**Owner:** Luis (Founder)

_Planning is guessing. Execute, measure, iterate._
