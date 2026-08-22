# Marcus Active Memory — 3-Repo Ecosystem State

**Last Updated:** 2026-08-23  
**Ecosystem Projects:**
1. **Nowing Platform:** `/Users/luisphan/Documents/GitHub/nowing` (FastAPI + Next.js 16 + Zero-Cache + PostgreSQL 16/17 pgvector — Lead Intelligence & AI Workstation)
2. **XActions Microservice:** `/Users/luisphan/Documents/GitHub/XActions` (Node.js/TS + Prisma + Playwright Signer Pool + SocksNode Proxy — Universal Scraping Engine)
3. **ChainLens-Research Engine:** `/Users/luisphan/Documents/GitHub/chainlens-research` (NestJS + Next.js + BullMQ + Vector Retrieval & Citation Hub)

---

## 1. Active Architecture Decisions & Invariants Across Ecosystem

### 🌐 Cross-Repo Invariants (The Trinity Contracts)
- **AD-SOC-1 & AD-SOC-9 (Universal Scraping Delegation):** Nowing delegates all raw web crawling to XActions (Daemon Port 3001 MCP & Redis Stream `stream:social:raw_posts`). Nowing focuses on Normalization, Confidence Gate, and CRM Hub.
- **AD-SOC-3 & AD-SN-3 (Sticky SOCKS5 Proxy):** SocksNode residential proxy with 1-to-1 sticky mapping per account in Redis `xactions:proxy_bindings`.
- **AD-101 & AD-47 (Stateless Ingestion):** Nowing Ingest Client `POST /v1/ingest/scraper` streams normalized chunks with deterministic `UUIDv5` to ChainLens-Research vector store.
- **AD-119 (Deterministic-First Lead Parsing):** Pass 1 pure regex/deterministic (0 tokens) + Pass 2 selective Micro-LLM fallback worker (Story 21.21).

### 🔺 TRINITY Invariants (Cross-Repo Laws — Canonical: `PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md`)
- **TRINITY-1:** Single Responsibility per Repo — XActions = Cào thô, ChainLens = Nghiên cứu, Nowing = Sản phẩm & CRM.
- **TRINITY-6:** Research-First Lead Generation — Trước khi gen lead hàng loạt, Nowing PHẢI gọi ChainLens để Market GPS.
- **TRINITY-7:** Best-Effort Cross-Service — Mọi luồng liên dự án có Degradation Fallback. Không dự án nào crash khi dự án kia offline.
- **TRINITY-10:** ChainLens DualProduct — vừa là Microservice cho Nowing, vừa là Standalone Platform (Exa-like).

## 2. Sprint Status Across All Three Repositories

### 🔵 1. Nowing Platform (`nowing`)
- **Epic 21 (Lead Gen Intelligence & CRM Hub):** Stories 21.1–21.20 `[DONE ✅]`. **Story 21.21 (Confidence Gate & Micro-LLM Worker):** `[READY-FOR-DEV ⏳]`.
- **Epic 24 (Enterprise Lead Conversion & Team CRM):** Stories 24.1–24.7 `[DONE ✅]`. Story 24.8 (CDP Browser Tool) `[BACKLOG]`.
- **Epic 25 (Admin & Telemetry):** Stories 25.1–25.3 `[DONE ✅]`. Stories 25.4–25.6 `[READY-FOR-DEV ⏳]`.
- **Epic 26 (Autonomous Missions & DSH):** Stories 26.1–26.9b `[DONE ✅]`. LangGraph DSH Mission Executor integrated.

### 🟣 2. XActions Microservice (`XActions`)
- **Epic 10 (Data & Platform Foundation):** Stories 10.1–10.5 `[DONE / STABLE ✅]`.
- **Epic 11 (Proxy Pool & Adaptive Governor):** Stories 11.1–11.7 `[DONE / STABLE ✅]`.
- **Epic 12 (Authentication - Terminal QR & CDP):** Stories 12.1–12.2 `[DONE ✅]`.
- **Epics 13–18 (Multi-Domain Crawlers):** Social (13, 15), Ecom (16), BĐS (17), HR (18) `[IN-PROGRESS / EXPANDING ⏳]`.
- **Epic 19 (Operator Dashboard & Admin CLI/MCP):** Stories 19.1–19.8 `[DONE ✅]`.
- **Epic 20 (Nowing Cutover & Legacy Decommissioning):** Shadow-run parity $\ge 99\%$ in staging $\rightarrow$ Decommission legacy scrapers in Nowing `[READY-FOR-CUTOVER ⏳]`.
- **Epics 21–22 (B2B Registry, Automotive, F&B, Healthcare, Legal):** `[READY-FOR-DEV / BACKLOG 📋]`.

### 🟢 3. ChainLens-Research Platform (`chainlens-research`)
- **Epic 19 & 44 (Cost Telemetry & MCP Tools):** `[DONE ✅]`.
- **Epic 48 & 49 (Exa-like Dev Dashboard & Search API):** Playground, API Keys, Templates, Table/CSV/Share output `[DONE ✅]`.
- **Trạng thái:** 🟢 **PRODUCTION READY 100% — Đang chạy ổn định, phục vụ Search & Deep Research cho Nowing!**

---

## 3. Critical Path & Immediate Cross-Repo Handshakes
1. **[Nowing]:** Triển khai **Story 21.21** (Deterministic Confidence Gate & Selective Micro-LLM Fallback Worker) để chốt chặn chất lượng Lead F1 $\ge 95\%$.
2. **[XActions ↔ Nowing]:** Kết nối MCP Daemon Port 3001 và Redis Stream `stream:social:raw_posts` cho các phễu cào Shopee (16.1), Chợ Tốt SĐT (17.1) và B2B Registry (21.1).
3. **[Nowing ↔ ChainLens]:** Đảm bảo `POST /v1/ingest/scraper` tiếp nhận chunks và tự động đồng bộ citation vào Chat & Deep Research.
4. **[ChainLens ↔ XActions]:** Sau khi XActions Epic 14 (MCP Daemon) hoàn thành, ChainLens triển khai `XActionsLiveProvider` (Luồng A: Live Domain Grounding) để lấy dữ liệu thực địa từ MXH/Ecom khi Deep Research.
