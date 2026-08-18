# Marcus Active Memory — Cross-Project Ecosystem State

**Last Updated:** 2026-08-17  
**Ecosystem Projects:**
1. **Nowing Platform:** `/Users/luisphan/Documents/GitHub/nowing` (FastAPI + Next.js 16 + Zero-Cache + PostgreSQL 16/17 pgvector)
2. **ChainLens-Research Engine:** `/Users/luisphan/Documents/chainlens-research` (NestJS + Next.js + BullMQ + Stdio MCP Server + Drizzle ORM)

---

## 1. Active Architecture Decisions & Invariants
- **AD-101:** Stateless ChainLens Engine (`POST /api/v1/search`) streaming chunks to Nowing `POST /v1/chainlens/ingest` with deterministic `UUIDv5`.
- **AD-102:** `dsh-worker` Sidecar container consuming Redis Streams `nowing:dsh:tasks` with `XAUTOCLAIM` and DLQ after 3 retries.
- **AD-103:** 4-Tier Hybrid LLM Router:
  1. Google Gemini Flash (Free Tier / $0.00 COGS) for fast routine parsing & tool dispatch.
  2. Qwen 3.8-27B AWQ (Local vLLM / $0.00 COGS) on 1x 24GB GPU.
  3. DeepSeek-V4-Flash ($0.14 In / $0.28 Out) for high-volume burst extraction.
  4. DeepSeek-V4-Pro-0813 ($0.435 In / $0.87 Out with Thinking: High) for deep CoT reasoning.
- **AD-104:** Zero-Cache CDC (< 10ms) reactive sync on `leads` table (excluding heavy `chunks`).
- **AD-105:** PII Vault (AES-256-GCM + blind HMAC-SHA256) and Decree 13/2023 compliance.
- **AD-108:** Dokploy infrastructure protection (`max_slot_wal_keep_size = 4096MB`, `wal_keep_size = 1024MB`, `tini` PID 1).
- **AD-109:** FastMCP Ingest Gateway (`/mcp/v1/tools/batch_ingest_leads`) with `ORDER BY value_hmac ASC` deadlock prevention.
- **AD-110:** PII Opt-out Blacklist (`pii_blacklists`), Anti-Fraud Refund Cap (max 15%), and Two-Tier Phone Unlock UX.

---

## 2. Sprint Status Across Both Repositories

### 🔵 Nowing Platform Sprints (Backend 95% Done, Còn Lại UI Split Canvas & Bot)
- **Story 26.1 (FastMCP Batch Ingest & Chunks):** Backend & Migration `ac475d54f6a2` `[DONE ✅]`
- **Story 26.2 (dsh-worker & Redis Streams):** Backend & Migration `49988ab02307` `[DONE ✅]`
- **Story 26.3 (4-Tier Hybrid Router Gemini $0):** Backend `hybrid_llm_routes.py` `[DONE ✅]`
- **Story 26.4 (PII Vault AES-256 & Opt-Out):** Backend & Migration `8f0e6aa7aa87` `[DONE ✅]`
- **Story 26.5 (Split Canvas Glass Box UI):** `[ACTIVE — CẦN HOÀN THIỆN UI FRONTEND ⏳]`
- **Story 26.6 (Telegram Checkpoint Bot UI):** `[ACTIVE — CẦN HOÀN THIỆN INLINE CARDS ⏳]`
- **Story 26.7 (Hermetic CI Quality Gates):** Unit & Integration Test Suites `[DONE ✅]`

### 🟢 ChainLens-Research Platform (Hoàn Thành 100% Cả Engine & Exa Dashboard ✅)
- **Story 48-4:** Cost Sub-breakdown in `costDollars` emitted in SSE done frame `[DONE ✅]`
- **Story 48-3:** Table/CSV/Share output in unified `POST /api/v1/search` `[DONE ✅]`
- **Story 44-0 / 44-5:** v4 Contract Regression Guard `[DONE ✅]`
- **Story 44-4:** MCP research/answer/contents tools `[DONE ✅]`
- **Epic 49 (Exa-like Dev Dashboard):** Playground (`/dashboard/playground`), API Keys (`/dashboard/api-keys`), Templates, Usage `[DONE ✅]`
- **Trạng thái:** 🟢 **PRODUCTION READY 100% — Đang chạy ổn định, sẵn sàng cấp dữ liệu cho Nowing!**

---

## 3. Immediate Coordination Roadmap (Next 48 Hours)
1. **Nowing:** Amelia executes Story 26.1 (Migration 218, FastMCP Batch Tool, Lead Batch Service, UUIDv5 chunk ingest).
2. **ChainLens:** Trigger Story 44-5 regression test and verify `chainlens_contents` tool in `apps/mcp`.
3. **Cross-Test:** Run hermetic integration test between Nowing and ChainLens fixture.
