---
title: "Go-to-Market & Business Plan — Nowing"
status: "draft — merged from bmad-market-research + bmad-cis-innovation-strategy"
created: "2026-08-04"
merged_from:
  - "/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/business-plan-baseline-nowing-2026-08-04.md"
  - "/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/market-nowing-gtm-research-2026-08-04.md"
  - "/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/innovation-strategy-nowing-2026-08-04.md"
---

# Go-to-Market & Business Plan — Nowing

**Date:** 2026-08-04  
**Status:** Draft — merged from `bmad-market-research` and `bmad-cis-innovation-strategy`  
**Positioning freeze:** 2026-08-24 (per SCP 2026-07-25)

---

## 1. Executive Summary

Nowing is **open-source research memory for AI agents — it remembers what it went and found, not just what you told it.**

The go-to-market is **open-core PLG**: the Apache-2.0 core + BSL 1.1 crawler engine is free to self-host; the cloud is pay-as-you-go. The primary conversion lever is **deep multi-step open-web research**, which is cloud-only in Phase 1 and metered for self-host in Phase 2. The business model depends on converting self-hosters and agent builders to cloud usage, not on selling research data or competing with Perplexity in consumer search.

**Bottom line:**
- TAM ~$12–15B (2025) for AI agent memory + enterprise knowledge/research search.
- SAM ~$2.0–2.8B for self-hostable, developer/agent-builder, privacy-sensitive research tools.
- SOM ~$10–30M ARR by Year 3 if OSS → cloud conversion reaches 0.5–3%.
- Pricing: cloud pay-as-you-go credits for LLM/embedding/storage/deep-research, with 1.5–2.5× margin over fully-loaded cost.
- Beachhead: AI agent builders → research teams → data-sensitive self-hosters.
- Distribution: MCP registry, GitHub, Hacker News, self-host communities. No push-GTM.
- Critical gates before public launch: recall quality (NFR-8), degradation (FR-38), real cost metering (FR-37), auto-extract spend cap (8.7).

> **Tóm tắt:** Nowing theo mô hình open-core PLG: core mã nguồn mở miễn phí self-host, cloud trả theo dùng. Đòn bẩy conversion là deep-research — năng lực duy nhất self-host không có ở Phase 1, và trả tiền theo call ở Phase 2. TAM $12–15B, SAM $2.0–2.8B, SOM $10–30M ARR trong 2–3 năm. Phân phối qua MCP/GitHub/HN. Cần đóng cổng recall, degradation, cost metering trước khi public.

---

## 2. Vision & Positioning

### 2.1 One-liner

> *Nowing is open-source research memory for AI agents — it remembers what it went and found, not just what you told it.*

### 2.2 Why it is different

| Capability | Nowing | Memory-layer incumbents | Research workspaces |
|---|---|---|---|
| Live web / UGC into memory | ✅ | ❌ / limited | ✅ but no durable memory |
| Long-term, versioned memory | ✅ | ✅ | ❌ |
| Self-host / privacy | ✅ | partial | Onyx ✅, Perplexity ❌ |
| Citations / provenance | ✅ | becoming table stakes | ✅ |
| Multi-client (web/desktop/ext/Obsidian/MCP) | ✅ | ❌ | partial |

### 2.3 Reasons to pay

1. **Memory with provenance** — long-term memory with live web data and citations.
2. **Self-host / privacy** — data-sensitive teams keep research on their own infra.
3. **Integration depth** — connectors → citations → memory → deliverables → multi-client in one loop.

### 2.4 What we will NOT say or do

- Do not call the whole product “open source.” Say “Apache-2.0 core + BSL 1.1 crawler engine.”
- Do not compete on “cheaper than Perplexity.”
- Do not sell raw research data (no owned index, NG-1).
- Do not position as a Perplexity consumer clone (NG-2).
- Do not make ChainLens a standalone product (NG-3).
- Do not use ChainLens name in public. Say “Nowing's hosted deep-research engine.”

> **Tóm tắt định vị:** Differentiator thật là live web/UGC vào memory tự host có nguồn. Lý do trả tiền là memory + provenance + self-host + integration depth. Không đua giá, không bán data, không dùng tên ChainLens.

---

## 3. Market Opportunity

### 3.1 Market size

| Layer | 2025 TAM | 2030/31 Forecast | CAGR | Source |
|---|---|---|---|---|
| Agentic AI orchestration & memory | $6.27–6.49B | $28.45–33.54B | 35–39% | Mordor / Research and Markets |
| Generative AI in enterprise knowledge/search | $6.18B | $27.43B (2031) | 28.6% | Mordor |
| AI enterprise search | $8.6B | $36.2B (2034) | 17.4% | DataIntelo |

**TAM (2025): $12–15B** — combined agentic memory + enterprise knowledge/research search.

**SAM (2025): ~$2.0–2.8B** — the subset that is self-host/on-premise, developer/agent-builder heavy, and MCP/open-core friendly.

**SOM (Years 2–3): $10–30M ARR** — bottom-up from 1,000–5,000 paying workspaces at $100–$800/mo, assuming 0.5–3% OSS-to-cloud conversion.

### 3.2 Competitive landscape

**Memory-layer competitors** (Mem0, Zep, Cognee, Supermemory, Letta): raised >$40M, racing to be the default memory API. None openly market live Reddit/YouTube/TikTok/Maps/Amazon ingest into self-hosted memory.

**Research-workspace competitors** (Onyx, Perplexity, OpenWebUI, LibreChat, Vane, NotebookLM): shape expectations for chat-with-citations, connectors, self-host. Onyx is the closest structural analog but has no long-term memory. Perplexity/NotebookLM validate paid research but are proprietary.

**Platform risk:** OpenAI, Google, Microsoft, Anthropic, AWS are bundling cross-session memory for free. A thin “memory API” business is not defensible; the workspace + self-host + data-control bundle is.

### 3.3 Customer segments & jobs

1. **AI agent builders (primary beachhead)**
   - Job: give agents persistent memory across sessions, reduce token spend, expose memory via MCP.
   - Pain: stateless agents force re-prompting; context windows are “whiteboards that get erased.”
   - Evidence: 68% of production agent deployments now include a dedicated memory layer; Mem0 case studies report 3–4 weeks saved and 40% token cost reduction.

2. **Research teams / analysts**
   - Job: collect real-world opinions from Reddit/YouTube/TikTok/Maps/Amazon; continue research across sessions; share findings.
   - Pain: research lives in individual chat threads; duplicate effort; no shared memory.

3. **Data-sensitive organizations / self-hosters**
   - Job: keep research data inside own infra; avoid cloud AI vendor lock-in.
   - Pain: most AI tools require sending docs to vendor cloud; open-source UIs lack durable research memory.

> **Tóm tắt thị trường:** TAM $12–15B, SAM $2.0–2.8B. Khe cửa là live web/UGC vào memory tự host. Đối thủ tầng memory không có live web; đối thủ workspace không có durable memory. Platform lớn miễn phí memory API nhưng không thể self-host hay workspace.

---

## 4. Business Model & Pricing

### 4.1 Open-core, three-tier license

| Tier | Scope | License | Self-host | Cloud |
|---|---|---|---|---|
| Core | Memory, KB, chat, automations, deliverables, clients, billing | Apache-2.0 | ✅ free | ✅ |
| Crawler engine | `app/proprietary/**` fetchers, YouTube InnerTube, CAPTCHA, stealth, proxy registry | BSL 1.1 | ✅ production, no resale | ✅ |
| Deep-research engine | Multi-step open-web research | Closed-source, hosted | ❌ Phase 1, 💳 Phase 2 | ✅ |

### 4.2 Revenue streams

1. **Cloud credit wallet** — pay-as-you-go for LLM tokens, embedding tokens, storage, deep-research calls.
2. **Auto-reload of credits**.
3. **Phase 2: metered deep-research for self-host** via Nowing Cloud API.
4. **Future: team/enterprise subscription** — per-seat fee + usage credit allowance.

### 4.3 Cost basis (2026-08-02)

| Deep-research mode | Avg cost per call |
|---|---|
| speed | $0.0353 |
| balanced (default) | $0.0482 |
| quality | $0.0671 |

Fallback flat-rate: $0.06 when `costDollars` is not emitted.

### 4.4 Pricing principles

- Price at 1.5–2.5× fully-loaded cost aggregation.
- Do not finalize public pricing until FR-37 and 8.7 are ratified.
- Default mode: `balanced` (validated on `nowing_evals`).
- Cloud pay-as-you-go is primary; subscription is an anchor for revenue stability.

### 4.5 Pricing packaging recommendation

- **Self-host:** free, unlimited core memory + connectors + chat + scrapers.
- **Cloud:** free tier + pay-as-you-go credits; deep research is the metered premium feature.
- **Team/Enterprise:** per-seat or commit-based tier for SSO, audit, BYOC, SLA, and bundled usage credits.

> **Tóm tắt mô hình kinh doanh:** Open-core PLG. Self-host free. Cloud trả theo dùng, deep-research là đòn bẩy. Giá căn cứ trên `costDollars` thật, margin 1.5–2.5×. Gói team/enterprise là future anchor.

---

## 5. Go-to-Market Strategy

### 5.1 Beachhead & sequencing

**Primary:** AI agent builders (via MCP).
**Secondary:** research teams and analysts.
**Tertiary:** data-sensitive self-hosters.

Sequence: agent builder (OSS/MCP) → research team (cloud workspace) → enterprise managed self-host.

### 5.2 Distribution channels

| Channel | Priority | Tactic |
|---|---|---|
| MCP Registry / Smithery / Glama | 1 | Publish `nowing_mcp` as first-class server; one-command install |
| GitHub | 2 | Clear README, docker-compose one-liner, public roadmap, license transparency |
| Hacker News / r/selfhosted / r/LocalLLaMA | 3 | “Show HN” with live self-host demo; technical hook, not marketing speak |
| Obsidian / Zotero / academic communities | 4 | Plugins and tutorials for existing researcher toolchains |
| Cloud PLG | 5 | Bottom-up conversion from self-host to cloud via deep-research usage |

### 5.3 Messaging do's and don'ts

**Do:**
- “Memory remembers what it went and found.”
- “Self-host free, cloud pay-as-you-go.”
- “Apache-2.0 core + BSL 1.1 crawler engine.”
- “Deep open-web research runs on Nowing's hosted engine.”

**Don't:**
- “Open source” as a blanket term.
- “Cheaper than Perplexity.”
- “Perplexity alternative.”
- Name ChainLens.

### 5.4 First-run value (M1)

Goal: `nowing_recall` returns something useful within ≤15 minutes of first install.

Requires:
- Onboarding seeds content (upload or a scraper run).
- Research/scrape run produces `Memory` with `source_type = SCRAPER_RUN`.
- Clear MCP install + `nowing_remember` / `nowing_recall` example.

### 5.5 Conversion motion

Funnel:
1. GitHub star / MCP registry discovery.
2. Self-host install (docker-compose).
3. First-run value (M1) within 15 minutes.
4. Active workspace (≥1 chat/scraper run per 7 days).
5. Cloud account created for deep research or team features.
6. Deep-research usage or team subscription.

Conversion benchmark: OSS → paid typically 0.5–3%; best-in-class PLG reaches 8–12%.

> **Tóm tắt GTM:** Phân phối qua MCP registry, GitHub, HN, self-host communities. Beachhead là agent builder. Conversion từ self-host → cloud qua deep-research. M1 ≤ 15 phút. Messaging minh bạch license.

---

## 6. Strategic Options & Recommendation

### 6.1 Options considered

**Option A — Open-Core PLG with Usage-Based Cloud (recommended)**
- Self-host free, cloud pay-as-you-go, deep-research as conversion lever.
- Matches team capabilities, low CAC, authentic OSS trust.

**Option B — Cloud-First Team Workspace with Freemium Trial**
- Launch cloud first, subscription per seat, self-host later.
- Requires GTM muscle the team lacks; contradicts OSS-first positioning.

**Option C — MCP-First Ecosystem + Premium Research Marketplace**
- Default memory layer for MCP, monetize connectors/deliverables.
- Requires ecosystem scale and could distract from core value prop.

### 6.2 Recommendation

**Adopt Option A with three refinements:**
1. Add a team/enterprise subscription anchor once cost is ratified.
2. Make provenance re-validation (FR-39) a P0 narrative project.
3. Follow a strict gate-based launch sequence.

> **Tóm tắt đề xuất:** Chọn Option A — open-core PLG + cloud trả theo dùng. Bổ sung subscription team khi có số cost. FR-39 là P0 cho câu chuyện differentiator. Launch theo cổng cứng.

---

## 7. Execution Roadmap

### Phase 1: OSS Launch & Cloud Soft Open

**Goal:** Public repo with credible first-run value; cloud available for early paying users.

**Deliverables:**
- Close NFR-8 recall eval gate (SM-10).
- Ship FR-38 degradation (self-host usable without engine).
- Ship FR-37 cost metering (`costDollars` parser).
- Ship story 8.7 spend cap.
- Implement FR-40 first-run value (scraper run → memory).
- Update README/landing/docs with license and feature table.
- List `nowing_mcp` in MCP registries.
- Soft-launch cloud pay-as-you-go.

**Gates:** NFR-8, FR-38, FR-37, 8.7.

### Phase 2: Cloud Conversion & Metered Self-Host

**Goal:** Prove conversion hypothesis; open revenue path for self-hosters.

**Deliverables:**
- Ratify pricing at 1.5–2.5× cost.
- Publish cloud pricing for tokens, storage, deep-research per mode.
- Add team workspace subscription tier.
- Open Phase 2 metered deep research for self-host via Nowing Cloud API.
- Stay in NFR-9 State A (async) until latency gates close.
- Ship FR-39 provenance re-validation.
- Resolve OQ-3 legal retention / right-to-delete.

**Gates:** SM-11a/b/c stable, OQ-3 closed, evidence of self-host demand.

### Phase 3: Scale & Optimization

**Goal:** Scale distribution, improve margins, expand revenue streams.

**Deliverables:**
- Scale OSS distribution (HN, MCP, community, contributor program).
- Vertical research packs (competitive intelligence, product research, academic).
- Automated monitoring / agent loops.
- Enterprise managed self-host support tier.
- Optimize deep-research cost (provider routing, cache, parallelization).
- Open State B (sync chat-mode) only after p95 targets met.

**Gates:** cloud gross margin, conversion rate, NRR, State B latency/cost.

> **Tóm tắt lộ trình:** Phase 1 đóng cổng chất lượng và launch OSS/cloud. Phase 2 chốt giá, mở metered self-host, subscription team. Phase 3 scale, pack theo vertical, tối ưu margin.

---

## 8. Success Metrics & Decision Gates

### 8.1 Leading indicators

| Metric | Validates |
|---|---|
| SM-1 — Active workspaces (≥1 chat/scraper run in 7 days) | Engagement |
| SM-2 — Successful scraper runs per week | Connector value |
| SM-7 — Memory operations per week | Memory adoption |
| SM-8 — % research threads continued | Research continuity |
| SM-9 — MCP memory tool calls per week | Agent-builder adoption |
| SM-3 — % chat messages with citation | Citation UX |
| SM-10 — `nowing_recall` precision@k / noise rate | Recall quality (ship gate) |
| SM-11a — Cost per deep-research call by mode | Pricing basis |
| SM-11b — p50/p95 latency per mode | State A/B gate |
| SM-11c — Degradation / fallback rate | Self-host reliability |
| M1 — Time to first useful recall | First-run value |

### 8.2 Lagging indicators

- Cloud gross margin.
- Net revenue per active workspace.
- Team subscription MRR.
- Self-host → cloud / metered conversion rate.
- LTV / CAC.
- Net revenue retention.
- Deep-research call volume.

### 8.3 Decision gates

| Gate | Go / No-Go |
|---|---|
| NFR-8 recall eval | No public repo/launch if not closed. |
| FR-38 degradation | No public repo if self-host hard-fails. |
| FR-37 cost metering | No pricing finalized. |
| Story 8.7 spend cap | No auto-extract on production. |
| OQ-3 legal retention | No GA cloud. |
| SM-11 price ratification | Phase 2 pricing public. |
| State B latency gate | No sync chat-mode by default. |

> **Tóm tắt metrics:** Leading = active workspace, MCP calls, recall precision, cost/latency/degradation. Lagging = margin, MRR, conversion, LTV/CAC, NRR. Gates = recall, degradation, cost metering, spend cap, legal, latency.

---

## 9. Risks & Mitigation

| # | Risk | Mitigation |
|---|---|---|
| 1 | Recall quality fails ship gate | Do not launch until NFR-8 is closed. |
| 2 | Self-hosters never convert to cloud | Deep research cloud-only Phase 1, metered Phase 2; team features in cloud. |
| 3 | Cost bleed / under-metering | FR-37 `costDollars`, $0.06 fallback, spend caps, balanced default. |
| 4 | Legal exposure from long-term scrape data | OQ-3 before GA; retention + right-to-delete; self-host/cloud split. |
| 5 | License / open-source backlash | Say “Apache-2.0 core + BSL 1.1 crawler engine.” |
| 6 | Incumbent adds live-web ingestion to memory | Move faster on FR-39 re-validation, deliverables, automations. |
| 7 | GTM-thin team cannot drive top-of-funnel | Double down on MCP, GitHub, HN, example-driven content. |
| 8 | Deep-research latency/cost volatility | Stay State A async until benchmarks prove State B. |
| 9 | Provenance schema gaps | FR-39 schema fix; do not market live-source before ready. |
| 10 | Scope creep into consumer search or data sale | Enforce NG-1/2/3; formal SCP for exceptions. |

> **Tóm tắt rủi ro:** Rủi ro lớn nhất là recall kém, self-host không convert, cost bleed, và pháp lý dữ liệu scrape. Mitigation = cổng chất lượng, deep-research là conversion, metering chặt, OQ-3, license trung thực.

---

## 10. Next Steps

1. **Confirm this GTM/business plan** with PO and team.
2. **Lock pricing model** after FR-37 + 8.7 are ratified.
3. **Close hard gates** in this order: NFR-8 → FR-38 → FR-37 → 8.7.
4. **Draft README/landing copy** using the messaging do's/don'ts.
5. **Prepare MCP registry listing** and example prompts for Claude Code / Cursor / OpenCode.
6. **Plan “Show HN” launch** for public repo day.
7. **Legal review** of OQ-3 before GA cloud.

---

## 11. Sources & Artifacts

- `business-plan-baseline-nowing-2026-08-04.md`
- `market-nowing-gtm-research-2026-08-04.md`
- `innovation-strategy-nowing-2026-08-04.md`
- `prd-Nowing-2026-07-22/prd.md`
- `briefs/brief-Nowing-2026-07-25/brief.md`
- `prfaq-Nowing.md`
- `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`
- `epics.md`

Market research sources (63 URLs) are preserved in `market-nowing-gtm-research-2026-08-04.md`.
