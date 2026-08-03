---
title: "GTM & Business Plan Baseline — Nowing"
status: "baseline for bmad-market-research + bmad-cis-innovation-strategy"
created: "2026-08-04"
source_artifacts:
  - "_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md"
  - "_bmad-output/planning-artifacts/prfaq-Nowing.md"
  - "_bmad-output/planning-artifacts/prfaq-Nowing-distillate.md"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md"
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/epics.md"
---

# GTM & Business Plan Baseline — Nowing

> Tài liệu này là baseline để chạy `bmad-market-research` và `bmad-cis-innovation-strategy`. Không phải kế hoạch cuối cùng.

## 1. Vision & Positioning (đã chốt, freeze tới 2026-08-24)

**One-liner:**
> *Nowing is open-source research memory for AI agents — it remembers what it went and found, not just what you told it.*

**Subtitle:**
> *Self-hosted research workspace with long-term memory for AI agents and teams.*

**Differentiator thật:**
- Memory gắn **provenance (citations)** và gồm **live web data** (Reddit, YouTube, TikTok, Instagram, Google Search/Maps, Amazon, web crawl).
- Khác với memory layer hiện có chỉ nhớ hội thoại/tài liệu (Mem0, Zep, Cognee, Supermemory).
- Khác với Perplexity/consumer research app (KHÔNG đua parity consumer, KHÔNG bán data).

**Lý do trả tiền:**
1. **Memory có provenance** — memory gắn citations, bao gồm live web data.
2. **Self-host / privacy** — data-sensitive team giữ dữ liệu research trên infra riêng.
3. **Integration depth** — connectors → citations → memory → deliverables → multi-client trong một vòng khép kín.

**Không phải lý do trả tiền:** rẻ hơn, bán research data, Perplexity-parity.

## 2. Target User & Beachhead

**Primary v1:** AI agent builder + team làm việc cùng nghiên cứu.
**Secondary:** researcher/analyst, self-hoster.

**Jobs to be Done:**
- Researcher/analyst: thu thập ý kiến thực từ Reddit/YouTube/TikTok/Maps/Amazon, lưu kết quả để research tiếp giữa các phiên.
- AI agent builder: persistent memory qua MCP, agent không mất context giữa các session.
- Team: workspace chia sẻ, chat real-time, deliverables, phân quyền, project memory.
- Self-hoster: nền tảng mở, chạy trên infra riêng, giữ dữ liệu research nội bộ.

**Non-users v1:**
- Người dùng muốn công cụ duyệt web thủ công.
- Doanh nghiệp cần SLA/on-call/compliance chuyên sâu.
- Người cần native mobile app.
- Dev solo với context nhỏ — CLAUDE.md đã đủ.

## 3. Business Model

**Self-host:** miễn phí, Apache-2.0 core.
**Cloud:** pay-as-you-go theo token LLM + embedding + lưu trữ + deep-research call.
**Distribution:** OSS + MCP registry + self-host, KHÔNG push-GTM.

**License ba tầng:**
| Tầng | Phạm vi | License | Self-host |
|---|---|---|---|
| Core | Mọi thứ ngoài `app/proprietary/` | Apache-2.0 | ✅ |
| Crawler engine | `nowing_backend/app/proprietary/**` | BSL 1.1 (không phải OSS) | ✅ dùng được, không bán lại hosted |
| Deep-research engine | Không nằm trong repo | Closed-source, hosted | ❌ Phase 1, 💳 Phase 2 |

**Đòn bẩy conversion self-host → cloud:** deep multi-step open-web research (cloud-only Phase 1, metered Phase 2).

**Phase 1:** self-host không có engine, dùng phần còn lại, deep research trả `engine_unavailable`.
**Phase 2:** self-host trả theo call để dùng deep research qua Nowing Cloud API (metered, không gọi engine trực tiếp).

## 4. Pricing Signals

- Không chốt giá trước khi có số cost thật.
- FR-37 đã xong: parse `costDollars` từ ChainLens SSE.
- Cost thực tế ChainLens 2026-08-02:
  - research speed: $0.0353
  - balanced: $0.0482
  - quality: $0.0671
- Fallback flat-rate: 60k micros ≈ $0.06.
- Target margin: 1.5–2.5× cho full-pipeline cost aggregation.
- Auto-extract có item-cap + spend-cap + wallet pre-check + rate-limit (story 8.7 done).

## 5. GTM Motion

**Beachhead:** agent-builder (OSS/MCP) → team (cloud).
**Channels:** GitHub, Hacker News, MCP registry, community OSS.
**Language:** README/landing chỉ tiếng Anh. Không VN-localization.
**Messaging:**
- ✅ Nói: "Memory nhớ cả dữ liệu web sống nó tự thu thập", "Self-host miễn phí", "Apache-2.0 core + BSL 1.1 crawler engine", "Research workspace có bộ nhớ".
- ❌ Không nói: "Memory có citations" làm headline, "Rẻ hơn", "Open source" trần trụi, tên ChainLens, Perplexity alternative, bán research data.

**M1 — First-run value:** `nowing_recall` trả về thứ hữu ích từ tài liệu vừa upload hoặc lần scrape trong session đầu, mục tiêu ≤15 phút.
**M2 — Aha thật:** agent trả lời bằng nghiên cứu từ session trước, không ai paste lại.

## 6. Success Metrics

**Primary:**
- SM-1: số workspace active (≥1 chat/scraper run trong 7 ngày).
- SM-2: số scraper run thành công mỗi tuần.
- SM-3: tỷ lệ chat message có citation ≥ X%.

**Secondary:**
- SM-4: số deliverables tạo.
- SM-5: số automation runs thành công.
- SM-6: tỷ lệ invite được chấp nhận.

**Memory:**
- SM-7: số memory operations (create/recall/update) mỗi tuần.
- SM-8: tỷ lệ research threads được continue ≥ X%.
- SM-9: số MCP memory tool calls mỗi tuần.
- SM-10: precision@k / noise rate của `nowing_recall` — ship-gate.

**Deep-research engine (SM-11):**
- SM-11a: cost thật/deep-research call theo mode.
- SM-11b: p50/p95 latency per mode.
- SM-11c: fallback/degradation rate.

**Counter-metrics:**
- SM-C1: số scraper run failed — không tối ưu bằng cách giảm thử scraper khó.
- SM-C2: average cost per chat turn — không giảm chất lượng để tiết kiệm token.

## 7. Hard Gates

1. **NFR-8 / story 3-9:** memory recall eval gate — cổng chặn launch.
2. **Story 9.1a:** research degradation — điều kiện tiên quyết trước khi public repo.
3. **Story 9.2:** cost metering thật — gate cho pricing.
4. **Story 8.7:** auto-extract spend cap — gate trước khi bật auto-extract trên prod.

## 8. Non-Goals (đóng vĩnh viễn)

- NG-1: không bán research data kiểu Exa (không có owned index).
- NG-2: không đua parity consumer kiểu Perplexity, không lấy "rẻ hơn" làm lý do trả tiền.
- NG-3: ChainLens không thành sản phẩm độc lập.

## 9. Competitive Context

**Memory layer:** Mem0 ($24M), Zep, Cognee ($7.5M), Supermemory ($2.6M).
**Research workspace:** Onyx (MIT, 40+ connector, 29K★, 1,000+ enterprise) — **không có memory**.
**Consumer research:** Perplexity (Comet FREE), OpenWebUI (136K★), LibreChat (36K★), Perplexica/Vane.

**Moat thật:** head start + integration depth + OSS/self-host. KHÔNG phải công nghệ độc quyền.

## 10. Open Items

- OQ-3: retention + right-to-delete cho memory, tách self-host vs cloud.
- Legal: ToS/bản quyền/PII khi lưu dài hạn dữ liệu scrape.
- SM targets còn placeholder — cần chốt số.
- 9.5 metered self-host endpoint deferred.

## 11. What Needs From Skills

### bmad-market-research
- TAM/SAM/SOM của AI agent memory / research workspace.
- Competitive moves mới nhất (Mem0, Zep, Cognee, Supermemory, Onyx, Perplexity, OpenWebUI).
- Customer evidence: agent builder pain points, team research workflow, self-host OSS motion.
- Pricing benchmarks: cloud pay-as-you-go vs subscription in memory/research category.

### bmad-cis-innovation-strategy
- Business model design: self-host → cloud conversion, metered deep research, pricing tiers.
- Revenue/cost structure, margin target, unit economics.
- Conversion funnel: MCP install → active workspace → cloud conversion.
- Partnership/ecosystem: MCP registry, GitHub, model providers, connector ecosystem.
- Execution roadmap: Phase 1 (OSS launch), Phase 2 (cloud conversion), Phase 3 (scale).
