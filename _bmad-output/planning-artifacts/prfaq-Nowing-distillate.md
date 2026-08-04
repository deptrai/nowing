---
title: "PRFAQ Distillate: Nowing"
type: llm-distillate
source: "prfaq-Nowing.md"
created: "2026-07-24"
updated: "2026-08-04"
purpose: "Token-efficient context for downstream PRD creation"
---

# PRFAQ Distillate — Nowing (post-pivot 2026-07-22)

## Vision & positioning (LOCKED)
- Vision đang dùng = POST-pivot 2026-07-22: "Open-source long-term research memory cho AI agents và team". KHÔNG dùng vision cũ "NotebookLM alternative / open web research".
- Định vị đã chốt (best-practice decision): **Framing B — research-memory wedge**: memory gắn **provenance (citations)** và gồm **live web data** (Reddit/YouTube/TikTok/Maps/Amazon), khác với memory hội thoại thuần của Mem0.
- Khách hàng chính (beachhead) = **dev/team xây trên AI agent**; MCP là bề mặt tích hợp, không phải lời hứa.
- Concept type = OSS + commercial cloud (self-host free, cloud pay-as-you-go).

## Rejected framings (và vì sao bỏ)
- **Framing A (agent-memory-first, "memory cho agent qua MCP"):** bỏ làm mũi nhọn — me-too Mem0/Cognee/Supermemory (đã có vốn + OSS), đánh vào sân của kẻ mạnh hơn.
- **Framing C (team-continuity-first, "team không nghiên cứu lại"):** không làm headline — rời lõi agent/MCP, đụng Notion AI; đẩy xuống How It Works/Getting Started (team/cloud tier). Vẫn là câu chuyện doanh thu hợp lệ.
- **Headline "nhớ, tiếp tục, hành động" thuần:** bỏ — mất differentiator (live-data + provenance).

## Requirements signals (đưa vào PRD)
- Auto-extract memory mỗi lượt (AD-14) phải **bật-theo-workspace + có ngân sách**, KHÔNG mặc định bật toàn bộ (kiểm soát chi phí).
- `recall` trả **top_k nhỏ đã rank** (mặc định ≤5) để tiết kiệm token/giảm nhiễu.
- **Dedupe + ngưỡng confidence** cần có NGAY từ MVP nhỏ (chống "memory rác").
- **Migration path** từ hệ markdown-memory cũ (`User.memory_md`, `Workspace.shared_memory_md`) → `Memory` rows: script migrate hoặc đọc song song, có cờ bật dần.
- **Retention + right-to-delete policy** cho dữ liệu scrape lưu dài hạn; tách rõ trách nhiệm self-host vs cloud.
- 4 MCP memory tools: `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact`.

## Technical context / constraints
- Tái dùng **Postgres + pgvector**; KHÔNG dựng graph DB mới (AD-11). Kỷ luật: "MCP tools trước, UI sau", "một memory type trước — semantic facts first".
- **Deep research cost thật 2026-08-02:** speed $0.0353 · balanced $0.0482 · quality $0.0671; parse `done.usage.costDollars` (AD-8/AD-15).
- Models mới: `Memory`, `MemoryVersion`, `MemoryRelation`, `ResearchThread`; package canonical `app/services/memory/`; memory-injection middleware trong agent loop; `MemoryExtractionService` (AD-14, auto-extract).
- Components: backend (Python 3.12/FastAPI), mcp (Python 3.11), web (Next.js 16/React 19), desktop (Electron 42), browser_extension (Plasmo), obsidian plugin, evals. Monorepo 7 phần.
- **Cổng chất lượng:** dùng `nowing_evals` để đo recall precision/noise TRƯỚC khi scale (eval-gated launch).
- Đã có sẵn & retained: auth+RBAC (Owner/Editor/Viewer — KHÔNG còn Admin), KB upload/index/hybrid-search + citation panel, scrapers qua REST+MCP, ChainLens Research tool, deliverables, schedule/event automations, credit wallet + token tracking.

## Competitive intelligence
- Đối thủ trực tiếp: Mem0 ($24M), Cognee ($7.5M), Supermemory ($2.6M) + nhiều OSS MCP memory servers. Không gian đang nóng và có vốn.
- Moat của Nowing = **head start + integration depth** (connectors→citations→memory→deliverables→multi-client) + OSS/self-host cho khách data-sensitive. KHÔNG phải công nghệ độc quyền.
- Rủi ro moat: nếu incumbent thêm citations → wedge mỏng đi. Đối sách: đào sâu "fused research + deliverables", chạy nhanh, own nhóm research-memory.

## Scope signals
- **MVP (in):** save/recall/correct **semantic facts** + 4 MCP tools + eval gate + migration path + dedupe/confidence tối thiểu.
- **Fast-follow (bắt buộc):** đồng bộ README/docs với vision mới; `epics.md` đã cập nhật 2026-08-04; data export; auto-extract mỗi lượt (AD-14); relation graph; UI memory browser/research timeline cho analyst.
- **Out / post-MVP (accepted):** decay/TTL/contradiction resolution; memory-driven automations (`memory_change`, `continue_research`); per-workspace MCP toggle; SLA/compliance doanh nghiệp; native mobile.
- **Non-users:** người cần browser thủ công; enterprise SLA/compliance; mobile app; người dùng solo/context nhỏ (files/CLAUDE.md đã đủ).

## Resource & timeline
- MVP memory layer (facts + 4 tool + eval + migration) = **1–2 sprint** (khả thi trên hạ tầng sẵn có, nếu giữ đúng "semantic facts first").
- Full vision = **3–4 sprint**. Nguồn trượt lịch chính: scope creep vào auto-extract + relation graph → giữ ở fast-follow.
- Rủi ro nhân lực: team nhỏ dàn mỏng trên 7 component + memory layer.

## Open questions & unknowns (từ FAQ)
- `[finance]` cost/turn thật của cloud (auto-extract + embedding + recall) → deep-research cost đã đo 2026-08-02: speed $0.0353 · balanced $0.0482 · quality $0.0671; còn cần SM-C2 trên cloud beta cho auto-extract + recall.
- `[legal]` ToS/bản quyền/PII khi lưu dài hạn dữ liệu scrape → review pháp lý + policy trước GA cloud.
- Ngưỡng recall precision nào là "đủ tốt" để ship → định lượng bằng eval harness.
- Success metrics còn placeholder ("≥ X%") — cần chốt số cho SM-1..SM-9.
- OQ-1..OQ-5 trong PRD: MCP connector marketplace; default agent-tool enable/disable; retention/archive policy; per-workspace MCP toggle; write-back là automation action hay agent_task tool.
- Ranh giới "project memory" của team có = `ResearchThread` không (chưa nêu rõ).

## Verdict findings — actionable
- **Overall: NEEDS MORE HEAT (nghiêng tích cực) — PROCEED có điều kiện.**
- 🔴 **Crack 1 — Migration:** làm script migrate markdown→Memory + đọc song song, TRƯỚC khi bật memory mới cho user hiện hữu.
- 🔴 **Crack 2 — Recall quality:** eval-gate trên `nowing_evals` (story `3-9` in-progress), đặt ngưỡng precision, không ship nếu chưa đạt.
- 🟠 **Crack 3 — Vision chưa kể:** đồng bộ README/docs/project-overview sang vision mới; `epics.md` đã cập nhật 2026-08-04.
- 🟠 **Crack 4 — Legal:** retention + right-to-delete policy; tách trách nhiệm self-host vs cloud.
- 🟠 **Crack 5 — Memory rác:** dedupe + confidence threshold ngay MVP.
- 🔥 **Needs heat:** một-câu-promise sắc hơn; lộ trình beachhead agent-builder→team; số unit economics cloud (cost thật deep research đã đo 2026-08-02); định nghĩa "aha moment" recall đầu tiên; điền dateline PR.
