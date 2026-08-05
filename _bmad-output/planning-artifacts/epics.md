---
title: Nowing - Epic Breakdown
description: ''
createdAt: '2026-07-28T12:47:48.297Z'
updatedAt: '2026-07-28T15:17:33.175Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-epics-md
---

---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
inputDocuments:
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/prfaq-Nowing-distillate.md (context)"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-22.md (epic taxonomy)"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-22-vision-pivot.md (epic taxonomy)"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md (Epic 9 + FR-24 re-bind)"
---

# Nowing - Epic Breakdown

## Overview

Phân rã epic/story cho Nowing từ PRD (reality-corrected 2026-07-24), Architecture spine, và 2 sprint-change-proposal (nguồn taxonomy epic).

> **Bối cảnh (đã verify code):** Nowing là **brownfield** — taxonomy **Epic 1–8 đã tồn tại và phần lớn ĐÃ IMPLEMENT** (migration tới 179; memory layer đã build: mig 177 tables/enums/confidence/HNSW+GIN/RBAC, 179 auto-extract, endpoints `memories_routes.py`, 4 MCP tools). Tài liệu này **không tạo epic mới đè lên epic đã xong**, mà: (a) ghi lại taxonomy thật với trạng thái `[DONE]`/`[PARTIAL]`/`[GAP]`, (b) thêm story **mới** chỉ cho phần còn thiếu (recall eval-gate, data-loss recovery, dedupe tuning, cost guardrails, docs sync).
>
> **Epic 9 (mới 2026-07-25)** là **ngoại lệ có chủ đích** của nguyên tắc trên: nó là epic *mới thật*, không phải retag. Lý do: ChainLens được thăng từ "một connector trong Epic 2" lên **external dependency hạng nhất** (`AD-15`), và ba việc trong đó (contract guard, cost metering, degradation) là **lỗi đang chạy trong production path**, không phải tính năng chưa build. Xem SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`.

## Requirements Inventory

### Functional Requirements
`[DONE]` FR-1 Auth · FR-2 API/PAT · FR-3 Workspace lifecycle · FR-4 Invites/memberships · FR-10 RBAC 3 roles · FR-6 Scrapers · FR-7 OAuth connectors · FR-8 MCP connectors · FR-9 Doc upload/index · FR-11 Folders · FR-12 Hybrid search · FR-13 Citation panel · FR-14 Chat threads · FR-15 Multi-agent runtime (+auto-extract) · FR-16 Realtime chat · FR-17 Anonymous chat · FR-21 Reports · FR-22 Podcast/video · FR-23 Image · FR-19 Automation triggers · FR-20 Automation runs · FR-25 Web · FR-26 Desktop · FR-27 Extension · FR-28 Obsidian · FR-29 MCP server · FR-30 Token tracking · FR-32 Memory storage/retrieval · FR-33 Research continuity · FR-34 Memory correction · **FR-18 Automation actions** *(cải chính 2026-07-25: registry có `agent_task` + `continue_research` + `write_back_jira/linear/notion/slack`)* · **FR-31 Credit wallet** *(dashboard `8-3` = done)* · **FR-35 Memory-driven automations** *(cải chính 2026-07-25: trigger `memory_change` + action `continue_research` + `AutomationRun.research_thread_id` đều có)*.
`[PARTIAL]` FR-32 (dedupe tune + recall-quality gap) · **FR-24 Deep-research via ChainLens engine** (đã wire + `2-4` done; thiếu contract regression guard + mode default còn `quality`) → **E9**.
`[DONE]` **FR-37 Deep-research cost metering** (`costDollars` parser done; fallback ~$0.06; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671) → **E9.2 P0**.

`[GAP]` **FR-38 Research degradation & self-host independence** (chỉ raise timeout, không degrade) → **E9.1 P0, tiền đề trước public repo** · **FR-39 Memory→scraper-run provenance & re-validation** (defect schema: `Memory.source_id` Integer vs `Run.id` UUID; không có writer cho `SCRAPER_RUN`; retention 30 ngày) → **E9.6** · **FR-40 First-run value: research run sinh memory** *(mới 2026-07-25, readiness P-4/C-2 — chỉ có `extract_from_turn`, workspace mới không seed gì ⇒ `nowing_recall` session đầu **rỗng theo cấu trúc**, M1 không tồn tại)* → **E3.13 HIGH** · **FR-41 Admin UI cho Global LLM Model Configuration** *(mới 2026-07-26 — global model config hiện chỉ sửa qua YAML/`.env` + restart backend; không UI, không hot-reload)* → **E8.11**.
`[GAP — NFR]` **NFR-1b/1c/1d Memory latency & injection bound** *(mới 2026-07-25, readiness C-1/P-5 — `MemoryInjectionMiddleware` **chặn mọi lượt chat**, `SELECT` không LIMIT, bỏ qua cả HNSW + GIN index đã có; `MEMORY_HARD_LIMIT` chỉ validate 1 `content` ở đường ghi ⇒ aggregate không có chặn trên)* → **E3.14**, `AD-18`.
`[RESOLVED]` FR-36 Legacy memory data-loss (2026-07-25 — không mất dữ liệu; 178 chưa apply prod, `memory_md` rỗng, snapshot đã tạo; guard + backfill + 5 test qua `3-10a`/`3-10b`).
`[REMOVED]` FR-5 AI File Sorting.

> **⚠️ Re-bind 2026-07-25 (SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`, ✅ ADOPTED):** **FR-24 rời Epic 2 (Connectors) sang Epic 9.** ChainLens không phải connector/scraper ngang hàng Reddit — nó là external dependency hạng nhất (`AD-15`). FR-37, FR-38, NFR-9 là mới. Story `2-4` giữ `done` làm lịch sử (nó đã ship tool thật), không revert.

### NonFunctional Requirements
`[DONE]` NFR-2 Security · NFR-3 Observability · NFR-4 Reliability · NFR-5 Multi-tenancy isolation · **NFR-6 Citation jump-to-source** *(cải chính 2026-07-25: `editorPanelAtom` CÓ `chunkId`; `AD-DEFER-1` đã đóng)* · **NFR-7 Usage dashboard** *(story `8-3` = done)* · **NFR-8 Recall quality eval-gate** *(story `3-9` = **`done`**; implementation complete; baseline ratification pending)*. `[PARTIAL]` NFR-1 Performance (bounds mơ hồ — **và không có epic nào nhận**, xem readiness C-1). `[PARTIAL]` **NFR-9 Deep-research latency & availability budget** (hai trạng thái A/B; đường async deliverable State A đã có; ChainLens benchmark 2026-08-01 p95 35s/70s/115s speed/balanced/deep — vượt target; rerun focused 2026-08-02 p95 27.5s/44.3s/43.7s — speed/deep PASS, balanced FAIL; benchmark `report-per-mode.md` 2026-08-02 (31 queries) ghi cost thực tế: research speed $0.0353 / balanced $0.0482 / quality $0.0671, avg $0.0519; full 69-query benchmark đang lên lịch; ngưỡng cổng A→B chưa đạt) → **E9.3**.

### Additional Requirements
Starter template: **KHÔNG — brownfield**. Component mới thật sự duy nhất trong Structural Seed: `nowing_evals/` (đã tồn tại, cần thêm memory suite).
- **AR-1** Thêm **suite memory-recall** vào `nowing_evals` (**DONE**: suite + dataset + oracle + metrics + gate đã có; 168 tests passed; `baseline_ratified: false` chờ baseline live measured).
- **AR-2** Backfill/recovery markdown→`Memory` (mig 178 drop `memory_md`/`shared_memory_md` KHÔNG backfill; `downgrade` chỉ tạo cột rỗng → data-loss có thể đã xảy ra).
- **AR-3** Dedupe/confidence *validation & tuning* (primitive đã có: `repository.py` cosine<0.08 + `update_on_duplicate`, đã wire vào auto-extract) — bench + tune qua eval.
- **AR-4** Retention + right-to-delete cho `Memory`/versions/relations + scrape data (doc retention đã có mig 176; memory chưa).
- **AR-5** Observability + cost/turn quantification (spans extraction/recall + aggregate).
- **AR-6** Auto-extract cost control — **DONE**: kill-switch/global + per-workspace flags, wallet pre-check, spend/budget cap, rate-limit thời gian; 59 tests passed.
- **AR-7** Legacy memory bridge parity tests (`/…/memory`, `/users/me/memory` backed by `Memory`).
- **AR-8** MCP tool contract/selfcheck CI (`EXPECTED_TOOLS`, e2e smoke), toggle-aware.
- **AR-9** Memory security: verify `memory:*` RBAC enforced + workspace/user isolation + audit-log writes (hiện chỉ `logger.warning`).
- **AR-10** Docs/README/epics sync sang research-memory (Fumadocs) + CI docs-drift.

**Requirements signals:** RS-1 auto-extract budget (item-cap + spend-cap + wallet pre-check + rate-limit done) · RS-2 recall top_k≤5 (verify) · RS-3 beachhead agent-builder→team · RS-4 "MCP trước UI sau"/"semantic facts first" · RS-5 docs-sync bắt buộc · RS-6 right-to-delete + self-host/cloud split · RS-7 eval-gated launch + chốt số SM · RS-8 data export · RS-9 "project memory"=`ResearchThread`? · RS-10 cost/turn beta trước pricing.

### UX Design Requirements
**N/A** — UX design contract chưa tồn tại (`ux-designs/ux-Nowing-2026-07-22/` chỉ có scaffold rỗng). Story có UI (3.6 citation jump, 8.3 dashboard) cần UX spec riêng trước khi build UI chi tiết — ghi nhận là tiền đề, không chặn backend/eval.

### FR Coverage Map
- FR-1/2/3/4/10 → **E1** [DONE] · FR-6/7/8 → **E2** [DONE] · **FR-6 mở rộng → E10.1** [ready-for-dev] (batdongsan scraper) · FR-9/11/12/13 → **E3** [DONE] · FR-14/15/16/17 → **E4** [DONE] · FR-21/22/23 → **E5** [DONE] · FR-19/20 → **E6** [DONE] · FR-25/26/27/28/29 → **E7** [DONE] · FR-30 → **E8** [DONE] · **FR-41 → E8.11** [GAP, mới 2026-07-26]
- **FR-24/37/38/39 + NFR-9 → E9** (mới 2026-07-25; tách story theo readiness Q-3/Q-4): FR-38 → **E9.1a** [DONE, P0] · FR-24 → **E9.1b** [DONE, P0] · FR-37 → **E9.2** [DONE, P0, parser `done.usage.costDollars` + fallback 60k micros; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671] · NFR-9 → **E9.3** [PARTIAL, P1 — baseline ChainLens có, State B chưa đạt] · OQ-6/AR-10 (phần Nowing↔engine) → **E9.4** [DONE, P1] · D5-Phase2 → **E9.5** [deferred] · **FR-39 → E9.6a** (provenance) **+ E9.6b** (re-validate) [GAP, defect schema]
- FR-32 → E3 (3.8 done; quality→3.9, dedupe→3.11) · FR-33 → E4 (4.6 done) · FR-34 → E3/E4 (done)
- FR-36 → **E3.10a/b** [RESOLVED 2026-07-25] · FR-18 → **E6.4** [DONE] · FR-31/NFR-7 → **E8.3** [DONE] · FR-35 → **E6.5** [DONE — cải chính 2026-07-25]
- NFR-8 → **E3.9** [DONE — implementation complete; baseline ratification pending] · NFR-6 → **E3.6** [DONE] · OQ-3/AR-4 → **E3.7** [PARTIAL] · OQ-4 → **E2.5** [DONE] · **OQ-5 → E6.4 [DONE]** *(2026-07-25: `6-4` = done; 4 action type `write_back_notion/slack/linear/jira` đã có ⇒ câu hỏi "action type riêng vs `agent_task`" **code đã trả lời: action type riêng**)* · OQ-6/AR-10 → **E8.10 + E9.4** [GAP] · **OQ-7 (4 câu hỏi từ ChainLens `42-3`) → E9.1b/E9.2/E9.3** [GAP] · FR-5 → [REMOVED]
- **Mới 2026-07-25 (readiness Nhóm 3 — trước đây KHÔNG có FR lẫn epic):** **FR-40** (first-run value: research run sinh memory; M1; brief §9 H-4) → **E3.13** [DONE, HIGH] · **NFR-1b/1c/1d** (bound cho memory injection + recall + auto-extract; `AD-18`) → **E3.14** [DONE, đi kèm E3.13]
  - ⚠️ **NFR-1 trước đây KHÔNG map sang epic nào** (readiness C-1) và không phủ memory (P-5). Nay: **NFR-1a** (CRUD/scraper) = nền tảng, không cần story riêng · **NFR-1b/1c/1d → E3.14**.
  - ⚠️ **Ràng buộc thứ tự mới:** **E3.14 nên chạy trước khi chốt số SM-10 của E3.9** (`AD-18` rule 6) — baseline recall quality đo trên lượng inject phụ thuộc N thì không tái lập được.
- AR-1/AR-3/AR-8 → E3.9/3.11 · AR-2/AR-7 → E3.10a/b · AR-9 → E3.12 · AR-5 → E8.9 · AR-6 → E8.8/8.7 · RS-5→E8.10 · RS-6/8→E3.7 · RS-7→E3.9 · RS-10→E8.9
- **NG-1/NG-2/NG-3 (§2.4 PRD Non-Goals)** → không map sang epic nào; là ràng buộc chặn phạm vi. Owned index = `AD-DEFER-7`.
- **Defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default toggle) → backlog.

## Epic List

> **⚠️ RECONCILED 2026-07-24 với `implementation-artifacts/sprint-status.yaml` (nguồn chân lý tiến độ):** một sprint đã chạy — **E1,2,5,7 = done; E3/E4/E6/E8 gần done**. Nhiều story dưới đây gắn `[GAP]` ở phiên planning này THỰC RA ĐÃ DONE (2.5, 3.6, 3.7, 6.4, 8.3, 3.11 dedupe, 3.12 security, 8.4a kill-switch, 8.5 obs) — đã retag `[DONE]`.
> **Việc CÒN LẠI thật sự:**
> - Từ sprint cũ: ~~4-6~~ research-continuity (done) · ~~6-5~~ memory-driven-automations (done) — cả hai đã verify code.
> - **Đã đóng 2026-08-01:** 3.9 memory recall eval-gate (implementation done; baseline ratification pending) · 3.10a/3.10b legacy data-loss recovery · 8.7 auto-extract spend/budget cap · 8.8 kill-switch · 8.9 observability.
> **✅ Cập nhật 2026-08-01 (ops):** memory (mig 177–179) **CHƯA lên production** (prod=`alembic 174`; 175–179 ở branch `develop`). ⇒ Các gap memory là **cổng TRƯỚC KHI merge memory lên prod**, KHÔNG phải sự cố prod đang chạy. 3.10a **done** (không mất dữ liệu) · 3.10b **done** (guard + backfill command + 5 test; deploy-order `mig177→backfill→mig178`) ⇒ **FR-36 RESOLVED**. **3.9** eval-gate (**`done`** — implementation complete; baseline ratification pending) · **8.7** spend-cap (**`done`** — 59 tests passed; cổng trước khi bật auto-extract trên prod). *(auto-extract KHÔNG đang bleed trên prod vì 179 chưa deploy.)*
>
> **🆕 2026-07-25 — Epic 9 *(Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng)*:** SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED). **FR-24 rời E2 → E9.** Các việc P0/P1, đều là lỗi thương mại/kiến trúc đang chạy trong production path chứ không phải tính năng mới: **9.1a** degradation + self-host độc lập (P0, **chặn public repo**) · **9.1b** contract regression guard (P0, không chặn) · **9.2** cost metering thật — **DONE**: parser `done.usage.costDollars` + fallback 60k micros (~$0.06), cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671 (P0) · **9.3** latency budget State A/B + mode default `quality`→`balanced` (P1) · **9.4** docs (P1) · **9.6a/9.6b** provenance + re-validate. **Gate:** pricing có thể bắt đầu định hình dựa trên số thật, vẫn giữ margin 1.5–2.5× cho full-pipeline cost aggregation.

### Epic 1: Identity, Auth & Workspace RBAC — ✅ DONE
Đăng ký/đăng nhập/OAuth/PAT + workspace RBAC Owner/Editor/Viewer. **FRs:** FR-1,2,3,4,10.

### Epic 2: Connectors — ✅ DONE
Built-in scrapers + OAuth connectors + external MCP connectors; connectors là memory ingestion source. **FRs:** FR-6,7,8. **Open:** 2.6 Indeed `[ready-for-dev]`, 2.7 Walmart `[ready-for-dev]`, 2.8 Amazon EU `[ready-for-dev]`, 2.9 input validation `[DONE]`.
> **⚠️ 2026-07-25: FR-24 (ChainLens) đã rời Epic 2 → Epic 9.** ChainLens không phải connector. Story `2-4-chainlens-research-mcp-tool` giữ `done` làm lịch sử — nó đã ship tool thật; việc còn lại thuộc Epic 9.

### Epic 3: Knowledge Base + Long-Term Memory — ✅ DONE
KB + long-term research memory. **FRs:** FR-9,11,12,13,32,33,34, **FR-40** *(mới)*, **NFR-1b/1c/1d** *(mới)*. **Open:** 3.15 run citations `[ready-for-dev]`, 3.16 OKF export `[ready-for-dev]`.
> **🆕 2026-07-25 (readiness Nhóm 3):** hai story mới, cả hai đều là **gap trước đây không có FR lẫn epic**. **3.13** — `MemoryExtractionService` chỉ có `extract_from_turn` và workspace mới không seed gì ⇒ `nowing_recall` session đầu **rỗng theo cấu trúc**, **M1 (first-run value ≤15 phút) không tồn tại**. **3.14** — `MemoryInjectionMiddleware` **chặn mọi lượt chat** với `SELECT` không LIMIT, bỏ qua cả HNSW + GIN index đã có sẵn ⇒ chi phí mỗi lượt tăng tuyến tính theo mức dùng. **3.14 nên chạy trước khi chốt số SM-10 của 3.9.**

### Epic 4: Chat & Agents — ✅ DONE
Multi-agent runtime + memory tools + research continuity. **FRs:** FR-14,15,16,17 (+4.5, 4.6). **Open:** 4.7 pointer-based tabs `[ready-for-dev]`.

### Epic 5: Deliverables — ✅ DONE
Report/podcast/video/image. **FRs:** FR-21,22,23.

### Epic 6: Automations — ✅ CORE DONE (4 gap mới: playbook layer)
Schedule/event/**memory_change** trigger + `agent_task`/`continue_research`/**write_back_notion|slack|linear|jira** action. **FRs:** FR-19, FR-20, **FR-18**, **FR-35**. **Open:** 6.6/6.7/6.9/6.10 (playbook reuse + schema-driven UI + workspace vertical + library) — **gated sau pilot BĐS**.
> **⚠️ Cải chính 2026-07-25:** header trước ghi *"DONE (2 gap)"* với 6.4 `[GAP]` và 6.5 `[GAP, post-MVP]` — **cả hai đều đã DONE** (verify code; xem Story 6.4/6.5).
> **➕ Bổ sung 2026-08-05 (pivot bdsai):** core automation đã đủ, nhưng thiếu **lớp playbook** — user hiện phải mô tả lại `intent` mỗi lần, không dùng được cho nghiệp vụ vertical lặp lại.
> **⚠️ Cải chính kiến trúc 2026-08-05 (architect review — Winston).** Bản đầu của 6.6 ghi *"thêm parameterization"* — **SAI**: `AutomationDefinition.inputs` + `Inputs.schema_` (JSON Schema 2020-12) + `PlanStep.params` render-at-execute + Jinja sandboxed `{run, inputs, steps}` **đã tồn tại** ⇒ automation vốn đã là template có tham số. 6.6 đổi thành **"expose cơ chế đã có"** (phạm vi nhỏ hơn nhiều), **cấm thêm lớp params thứ hai**. Thêm **6.9 (workspace `vertical`)** vì khái niệm này chưa tồn tại và nó **chặn** library; story library đổi số thành **6.10**. Bổ sung vào 6.7: **`x-ui` hints** (giữ một renderer, vẫn bản địa hoá được) và **validate output LLM bằng schema** trước khi lưu.
> **ADR cần chốt:** *tool = code (subagent builtin) · nghiệp vụ = data (playbook definition)* — hiện có hai đường mở rộng song song (`registry.py` import tĩnh vs automation JSON); không chốt sẽ dẫn tới nghiệp vụ nửa code nửa data.
> Cả bốn story **KHÔNG build trước pilot 2 tuần**.

### Epic 7: Multi-surface Clients — ✅ DONE
Web/desktop/extension/Obsidian/MCP. **FRs:** FR-25,26,27,28,29. **Open:** 7.4 dedicated connectors layout `[ready-for-dev]`.

### Epic 8: Người dùng thấy và kiểm soát được chi phí — ✅ DONE (2026-08-02)
Token tracking, ví credit, dashboard usage, guardrail chi phí, docs/vision sync, và admin UI cho global LLM model config. **FRs:** FR-30, FR-31, **FR-41** *(mới)*. 8.10 và 8.11 **done**. **Open:** 8.12 workspace limits `[ready-for-dev]`, 8.13 PostHog analytics `[ready-for-dev]`.
> **⚠️ Đổi tên + đánh lại số hiệu 2026-07-25 (readiness Q-7 + C-C).** Tên trước *"Platform Operations (Billing/Usage/Token)"* là framing ops. **Và quan trọng hơn — số hiệu story đã bị xung đột với `sprint-status.yaml`:** `8.4a`/`8.5`/`8.6` trong tài liệu này nghĩa **khác** `8-4`/`8-5`/`8-6` trong sprint-status (observability-logging / security-permissions / multi-tenant-isolation). Đã đánh lại theo số **chưa dùng**: `8.4a → 8.8` · `8.5 → 8.9` · `8.6 → 8.10`. Từ giờ số hiệu ở hai tài liệu khớp 1-1.

### Epic 9: Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng — ✅ DONE (2026-08-02)
Người dùng research sâu được mà **không vỡ** khi engine chết (9.1a), **không treo** cả chat turn khi engine chậm (9.3, State A mặc định), và **trả đúng tiền** cho thứ mình dùng (9.2). **FRs:** FR-38 [DONE,P0], FR-24 [DONE,P0], FR-37 [DONE,P0, parser `done.usage.costDollars` + fallback 60k micros ≈ $0.06; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671], FR-39 [DONE, 9.6a provenance recipe + 9.6b re-validation API], NFR-9 [DONE — baseline ChainLens đo, State A làm default; State B chat-mode sync vẫn tắt cho đến khi p95 `balanced` đạt 30s]. **Deferred / Post-MVP:** **9.5** metered self-host endpoint (chưa phê duyệt). **Governed by:** `AD-15` · `AD-16` (license — cho 9.4) · **`AD-11.1`** (provenance recipe — cho 9.6a/b) · **`AD-17`** (async door — cho 9.3) · **`AD-19`** (trang khó: anti-bot ở Nowing, engine không gọi ngược inline, escalation async — cho 9.1a/9.3) · **`AD-20`** (screenshot-as-evidence, không adopt visual-RAG stack) · AD-7, AD-8 amended.
> **✅ Cập nhật 2026-08-02:** 9.1a, 9.1b, 9.2, 9.3, 9.4, 9.6a, 9.6b **done**. 9.5 **deferred**.
>
> **🆕 2026-08-03 — Epic 10: Connector & Scraper Expansion** (Vietnam BĐS + broader scraper port). **Open:** 10.1 batdongsan `[review]`, 10.2 chotot `[done]`, 10.3 muaban `[done]`, 10.4 cross-source aggregator `[backlog]`.
> **⚠️ Đổi tên 2026-07-25 (readiness Q-1).** Tên trước — *"Deep-Research Engine Integration (ChainLens)"* — là **technical epic**: nó mô tả hạ tầng, không mô tả điều user làm được. Ba mệnh đề trong tên mới map thẳng vào ba story P0/P1.
>
> **🆕 2026-08-03 — Epic 11: Telegram Automation & Bot** (notification, write-back, inline keyboard, commands). **Open:** 11.1 notification foundation `[done]`, 11.2 write-back & builder `[done]`, 11.3 interactive bot & commands `[done]`.

---

## Epic 2: Connectors

### Story 2.5: Per-Workspace MCP Tool Enable/Disable Toggle  `[DONE per sprint-status: 2-5]`
As a workspace owner,
I want to enable/disable từng MCP tool theo workspace,
So that tôi kiểm soát agent được dùng tool nào (vd tắt `nowing_reddit_scrape`).

**Acceptance Criteria:**
**Given** owner mở workspace MCP settings, **When** tắt một tool, **Then** `tools/list` của MCP server lọc bỏ tool đó cho workspace này (server-side), workspace khác không đổi.
**And** selfcheck `EXPECTED_TOOLS` (AR-8) phải toggle-aware — không fail khi tool bị ẩn hợp lệ.
_OQ-4 · AD-DEFER-3._

### Story 2.6: Indeed Jobs Scraper  `(mới 2026-07-30)`  `[ready-for-dev]`
As a recruiter or market researcher,
I want to scrape job listings and job details from Indeed,
So that I can track hiring trends, competitor headcount, and job market signals in my workspace.

**Acceptance Criteria:**
**Given** a search query (title, location, radius, sort), **When** I call the Indeed scraper, **Then** it returns paginated job cards with title, company, location, salary, summary, and posting date.
**Given** a job detail URL (`/viewjob`), **When** I scrape it, **Then** it returns full job description, requirements, benefits, and apply link.
**And** blocked/paginated pages fail gracefully with a typed `block_type`; **And** billing is metered per `INDEED_JOB` unit.

**Kỹ thuật:** tái dùng pattern scraper hiện có (URL resolver, warmed browser, parse, billing unit). Tạo `indeed.scrape` capability với REST + agent subagent + MCP tool.
_FR-6 · upstream PR #1605._

### Story 2.7: Walmart Product + Reviews Scraper  `(mới 2026-07-30)`  `[ready-for-dev]`
As an e-commerce analyst,
I want to scrape Walmart product listings and reviews,
So that I can monitor competitor pricing, ratings, and customer feedback.

**Acceptance Criteria:**
**Given** a product search or product page URL, **When** I call the Walmart scraper, **Then** it returns product title, price, rating, seller, availability, and review summary.
**Given** a product with reviews, **When** I request reviews, **Then** it returns paginated review text, rating, date, and verified status.
**And** the capability is exposed via REST, agent subagent (`walmart` specialist), and MCP tool.

**Kỹ thuật:** parse `__NEXT_DATA__`, rotate proxies on block, add `walmart.scrape` + `walmart.reviews` verbs, register billing units.
_FR-6 · upstream PR #1614._

### Story 2.8: Amazon EU Marketplaces  `(mới 2026-07-30)`  `[ready-for-dev]`
As a seller watching European markets,
I want the Amazon scraper to support EU marketplaces (`amazon.de`, `amazon.fr`, `amazon.co.uk`, etc.),
So that I can track prices and listings across regions.

**Acceptance Criteria:**
**Given** an Amazon product URL on an EU domain, **When** I scrape it, **Then** it returns localized product metadata, price, currency, and availability.
**And** URL validator accepts EU TLDs; **And** region/currency are exposed in output schema.
_FR-6 · upstream PR #1628._

### Story 2.9: Scraper API Input Validation & Error Handling  `(mới 2026-07-30)`  `[done]`
As an API consumer,
I want clear 422 validation errors and inline feedback when I submit invalid scrape URLs,
So that I can fix my request without guessing.

**Acceptance Criteria:**
**Given** an invalid or unsupported URL for any scraper, **When** I submit, **Then** the response returns structured field errors with the offending field and a human-readable hint.
**Given** the playground UI, **When** a validation error occurs, **Then** it surfaces inline and persists a toast.
**And** all scrapers (web, amazon, walmart, youtube, reddit, tiktok, google maps, indeed) reuse a shared URL validator and `HttpUrlStr` type.
_FR-6 · upstream PR #1623._

---

## Epic 3: Knowledge Base + Long-Term Memory

_Đã DONE: 3.1 upload/index, 3.2 folders, 3.3 hybrid search, 3.4 citation panel, 3.5 AI-file-sort [REMOVED], 3.8 long-term memory storage/retrieval (FR-32, mig 177 + `memories_routes.py` + MCP)._
_Mới 2026-07-25 (readiness Nhóm 3): **3.13** first-run value (FR-40) · **3.14** memory injection bound (`AD-18`)._

### Story 3.6: Citation Scroll-to-Highlight in Full Document Editor  `[DONE per sprint-status: 3-6]`
As a researcher,
I want click citation nhảy đúng đoạn chunk trong full editor,
So that tôi lần ngược câu trả lời về nguồn chính xác.

**Acceptance Criteria:**
**Given** một citation trong chat, **When** bấm "Open" mở full editor, **Then** editor scroll tới + highlight đúng chunk (truyền `chunkId`, không chỉ `documentId`).
**And** `editorPanelAtom` có trường `chunkId` + highlight state; **And** không có chunk match thì fallback về đầu document + thông báo.
**UX Notes (nhẹ, brownfield):** bám component `nowing_web/components/citation-panel/citation-panel.tsx` (đã có scroll/highlight chunk) + editor hiện có — chỉ mở rộng state, KHÔNG thiết kế mới. Cần contract đầy đủ → `bmad-ux`.
_NFR-6 · AD-DEFER-1._

### Story 3.7: Memory Retention, Right-to-Delete & Legal Readiness  `[DONE retention: 3-7; memory right-to-delete/legal → xác nhận khi GA cloud]`
As a workspace owner / DPO,
I want retention + right-to-delete cho memory và dữ liệu scrape lưu dài hạn,
So that Nowing đáp ứng ToS/bản quyền/PII và người dùng kiểm soát dữ liệu (chốt TRƯỚC GA cloud).

**Acceptance Criteria:**
**Given** một `Memory` có `memory_versions`/`memory_relations`/embedding, **When** thực hiện right-to-delete (erasure), **Then** memory + versions + relations + embedding bị purge (hoặc anonymize theo policy) — test e2e: create→correct→cite→erase→assert sạch mọi bảng.
**Given** dữ liệu phái sinh từ scrape, **When** có ToS takedown theo nguồn, **Then** bulk-delete theo `source_type`/`source_id` (cần provenance tag).
**And** policy tách rõ **self-host vs cloud** (RS-6); **And** data export (RS-8); **And** doc retention (mig 176) được nối vào cùng policy.
_OQ-3 · AR-4 · AD-DEFER-4._

### Story 3.9: Memory Recall Eval-Gate  `(mới)`  `[DONE — SHIP-GATE implementation complete; baseline ratification pending]`
As a platform team,
I want một eval gate đo chất lượng recall của memory trên `nowing_evals`,
So that không ship recall rác (agent "đoán" thay vì "nhớ").

**Acceptance Criteria:**
**Given** harness `nowing_evals` (đã có `retrieval.py` recall@k/MRR/nDCG + `wilson_ci`), **When** thêm **suite memory-recall** nhắm `nowing_recall`/`/memories/search`, **Then** suite chạy được qua CLI với dataset gán nhãn.
**Given** cần đo chất lượng, **When** định nghĩa oracle "recall hit" (top_k≤5 + ngưỡng similarity, verify RS-2) + thêm metric **noise-rate**, **Then** đo được precision@5 và noise với Wilson CI.
**Given** baseline đã đo, **When** chốt **số SM-10** (precision@5 ≥ X, noise ≤ Y) — **cấm placeholder "≥X%"**, **Then** gate chặn ship nếu chưa đạt (RS-7).
**And** MCP selfcheck CI (AR-8) chạy trong pipeline.
_NFR-8 · AR-1 (re-scoped: extend harness, KHÔNG bootstrap) · AR-3 · AR-8 · RS-2 · SM-10._
**Phối hợp (KHÔNG hard forward-dep):** dựng suite/harness/label dataset chạy độc lập được; chỉ **đo baseline cuối** trên corpus sau 3.10b (recovery) và sau khi 8.4a đông cứng auto-extract. 3.10a & 8.4a là **P0 theo ưu tiên** (mitigate rủi ro prod), không chặn khởi động story này.

### Story 3.10a: Legacy Memory Data-Safety Spike (forensic + freeze backup)  `(mới)`  `[DONE 2026-07-25]`
As a platform engineer,
I want xác định trạng thái mig 178 + bảo vệ cửa sổ khôi phục,
So that ta biết memory cũ còn cứu được không TRƯỚC khi cửa sổ backup hết hạn.

**Acceptance Criteria:**
**Given** production DB, **When** truy vấn `alembic_version` + lịch sử deploy, **Then** ghi rõ 178 đã apply prod chưa (ops ticket **trong ngày** — time-sensitive).
**Given** cấu hình backup/PITR, **When** kiểm tra retention, **Then** gia hạn retention phủ mốc trước-178 + chụp snapshot "pre-memory-remediation", verify restorable trên non-prod.
**Then** ra **quyết định nhánh cho 3.10b**: "recoverable — window=[dates]" HOẶC "recovery impossible".
**And** ràng buộc: KHÔNG deploy migration ≥178 lên env có user cho tới khi 3.10b hoàn tất.
_FR-36 · AR-2._
> **✅ KẾT QUẢ (ops 2026-07-25):** 178 **CHƯA apply prod** (`alembic_version=174`; 175–179 chỉ ở branch `develop`); cột `memory_md`/`shared_memory_md` còn, nội dung **RỖNG** (0/3 users, 0/3 workspaces); bảng `memories` chưa tồn tại trên prod. Snapshot `pre-memory-remediation` (pg_dump -Fc, 18MB) đã tạo. **Kết luận: KHÔNG mất dữ liệu.** ⇒ 3.10b đổi từ *recovery* sang *prevention*.

### Story 3.10b: Migration 178 Data-Safe Backfill (pre-merge to production)  `(mới)`  `[DONE 2026-07-25 per sprint-status: 3-10b]`

> **✅ ĐÓNG (sprint-status 2026-07-25):** G1.2 guard trong `178.upgrade()` (raise nếu legacy data chưa backfill) + G1.1 app-level command `scripts/backfill_legacy_memory.py` (embeddings không chạy được trong raw migration) + **5 integration test xanh** (backfill create / idempotent / dry-run + guard block / drop-after). **Ràng buộc còn lại: deploy-order `mig177 → backfill → mig178`.** ⇒ **FR-36 RESOLVED.** AC dưới đây giữ làm ngữ cảnh.
As a platform engineer,
I want `178.upgrade()` backfill `memory_md`/`shared_memory_md` → `memories` NGAY TRƯỚC khi DROP cột,
So that khi 175–179 merge/deploy lên production, không mất memory nào (hiện 0, nhưng user có thể ghi trước lúc deploy vì feature memory_md vẫn sống ở code prod hiện tại).

**Acceptance Criteria:**
**Given** `178_drop_legacy_memory_columns.py` trên `develop`, **When** sửa `upgrade()`, **Then** thêm bước backfill: đọc `memory_md`/`shared_memory_md` non-empty → parse → insert `memories` (`source_type='manual'`) **TRƯỚC** `DROP COLUMN`, kèm verify count.
**Given** ngay trước khi deploy 178 lên prod, **When** re-check `users_with_memory`/`workspaces_with_shared_memory`, **Then** =0 (an toàn drop) HOẶC đã được backfill cover.
**And** gate: KHÔNG merge/deploy 178 lên production nếu `upgrade()` chưa có backfill.
_FR-36 · AR-2. **Dep: 3.10a (done).**_

### Story 3.11: Memory Dedupe & Confidence Tuning  `(mới)`  `[DONE dedupe (đã wire cosine<0.08); tuning ngưỡng optional qua 3.9]`
As a platform team,
I want validate/tune ngưỡng dedupe + confidence qua eval,
So that memory không thành "bãi rác" (nhớ trùng/nhiễu) mà cũng không merge nhầm.

**Acceptance Criteria:**
**Given** dedupe primitive đã có (`repository.py` cosine<0.08 + `update_on_duplicate`, đã wire auto-extract `extraction.py`), **When** chạy bench dedupe precision/recall trên `nowing_evals`, **Then** đo được tỷ lệ merge đúng/sai.
**And** tune ngưỡng cosine + confidence default (0.7) dựa trên số đo; **And** phủ cả path auto-extract lẫn manual create.
_AR-3 · gắn với 3.9._

### Story 3.12: Memory Security — RBAC Enforcement, Isolation & Audit  `(mới)`  `[DONE — sprint 8-5 security + IDOR fix (deferred-work 4.5)]`
As a security-conscious team,
I want memory an toàn multi-tenant + có audit,
So that recall không rò rỉ cross-tenant và mọi memory write có vết.

**Acceptance Criteria:**
**Given** quyền `memory:*` đã backfill (mig 177), **When** gọi mọi memory endpoint + MCP tool, **Then** permission được enforce (test khẳng định, không chỉ tin backfill).
**Given** 2 workspace/user khác nhau, **When** recall/search, **Then** không trả memory cross-tenant (test isolation, NFR-5).
**And** mọi memory write (create/correct/delete) ghi **audit log** (hiện chỉ `logger.warning`).
_AR-9 · NFR-2/NFR-5 (memory-scoped)._

---

### Story 3.13: First-Run Value — Research Run sinh ra Memory  `(mới 2026-07-25)`  `[DONE — HIGH]`

**Là** người dùng mới của Nowing,
**tôi muốn** hành động research **đầu tiên** của mình để lại memory,
**để** `nowing_recall` có nội dung ngay trong session đầu — thay vì trả rỗng và làm tôi nghĩ sản phẩm không chạy.

> **Vì sao story này tồn tại (readiness P-4 / C-2).** Verify code 2026-07-25: `MemoryExtractionService` chỉ có **`extract_from_turn`** (`app/services/memory/extraction.py:118`) — không có đường extract từ scrape run, deep research, hay document. Workspace mới **không seed gì** (grep `seed|sample|onboarding|welcome|starter|template` trên `workspaces_routes.py` = rỗng). ⇒ **recall session đầu rỗng theo cấu trúc**, và **M1 (first-run value ≤15 phút) không tồn tại**. Đồng thời câu headline của brief — *"it remembers what it went and found, not just what you told it"* — hiện **chỉ đúng nửa sau**.

**Quyết định:** làm research run sinh memory. **KHÔNG seed dữ liệu mẫu** — memory giả dạy sai mental model, và sẽ đổ rác vào đường inject chưa có chặn trên (xem `3.14`).

**Acceptance Criteria:**
**Given** người dùng mới vừa tạo workspace, **When** chạy **một** research/scrape run (8 platform / 14 verb sẵn có, hoặc deep research), **Then** run sinh memory `source_type = SCRAPER_RUN` + provenance — **không cần chat trước**.
**Given** run vừa xong, **When** gọi `nowing_recall`, **Then** trả fact **có citation trỏ về run gốc**, không rỗng.
**Given** người dùng mới hoàn toàn, **When** đo signup → run đầu → recall có nội dung, **Then** **≤ 15 phút** (M1).
**And** tôn trọng kill-switch `MEMORY_AUTO_EXTRACT_ENABLED` + `workspaces.memory_auto_extract_enabled` (`8-8` done) và spend cap (`8-7`).
**And** memory sinh ra đếm vào ngân sách 8.000 chars của **NFR-1b** — đây là ràng buộc, không phải ghi chú.

**Ghi chú kỹ thuật:**
- Story này chính là **writer còn thiếu** cho `MemorySourceType.SCRAPER_RUN` (khai báo `app/db.py:572`, **hiện không ai ghi**).
- ⚠️ **`Memory.source_id` là `Integer` (`app/db.py:2077`) còn `Run.id` là `UUID` (`app/db.py:3155`)** ⇒ **không dùng `source_id` cho run**; đi qua `source_run_id` của `AD-11.1`.
- ⚠️ `RUNS_RETENTION_DAYS = 30` (`app/capabilities/core/runs.py:33`) ⇒ memory phải **tự chứa** ngữ cảnh; `Run` gốc sẽ biến mất.
- **Dep mềm với `9-6a`:** provenance đầy đủ (`source_capability` + `source_input`) cần `9-6a`. Bản tối thiểu (`source_type` + `source_run_id`) chạy độc lập ⇒ **không chờ**.

_FR-40 · M1 · brief §9 H-4 · `AD-11.1`._

---

### Story 3.14: Memory Injection — chặn trên & ngân sách latency  `(mới 2026-07-25)`  `[DONE — đi kèm 3.13]`

**Là** người dùng dùng Nowing càng lâu càng nhiều memory,
**tôi muốn** mỗi lượt chat có chi phí ổn định,
**để** sản phẩm không tệ dần đúng theo mức tôi dùng nó nhiều.

> **Vì sao (readiness C-1 / P-5, verify 2026-07-25).** Có **hai** đường recall, PRD chỉ mô tả một:
> - `nowing_recall` / `/memories/search` → bounded top_k ≤5, hybrid. **Có** trong FR-32.
> - `MemoryInjectionMiddleware.abefore_agent` → **chặn mọi lượt chat**, chạy `SELECT * FROM memories WHERE workspace_id=? ORDER BY created_at` **không LIMIT**, **bỏ qua cả `ix_memories_embedding` (HNSW) lẫn `ix_memories_content_search` (GIN)** đã có sẵn. **Không** có trong PRD, **không** có bound.
>
> `MEMORY_HARD_LIMIT = 25.000` chỉ validate **một** `content` ở đường **ghi** — aggregate của N fact **chưa từng bị kiểm tra**. Phanh duy nhất là `<memory_warning>` ở 18.000 nhờ LLM tự consolidate, mà `extract_from_turn` (Celery) ghi row nhanh hơn LLM dọn.
>
> **Cải chính P-5:** P-5 ghi "auto-extract cộng latency mỗi turn" — **sai**. Caller duy nhất là `memory_extraction_task.py` (Celery, ngoài request) ⇒ **không** trên critical path. Nửa còn lại của P-5 đúng, và nặng hơn dự kiến.

**Acceptance Criteria:**
**Given** workspace có N memory bất kỳ, **When** chạy một lượt chat, **Then** memory injection dùng **top-k bounded** qua HNSW/GIN — chi phí **O(top-k), không O(N)**.
**Given** tổng memory render vượt ngân sách, **When** inject, **Then** **cắt ở đường đọc tại ≤ 8.000 chars** (không dựa vào `<memory_warning>`).
**Given** ngân sách đã chốt, **When** đo, **Then** DB p95 **≤ 150ms** cho injection và **≤ 300ms** cho recall tool — assert trong test, dùng hook **đã có** `_perf_log "[memory_injection] ... db=%.3fs total=%.3fs"`.
**Given** injection lỗi, **When** rơi vào `except → return None`, **Then** phát **counter** (hiện chỉ `logger.exception` ⇒ degrade im lặng).
**Given** auto-extract, **When** chạy một lượt chat, **Then** **regression test** khẳng định nó **không** nằm trên critical path (hiện đúng nhờ Celery, nhưng không test nào giữ).
**And** metric + tài liệu **tách tên** `memory_injection` ≠ `memory_recall`.

**Given** `/memories/search` và `nowing_recall`, **When** trả kết quả, **Then** **expose RRF score thật** thay cho `score=0.0` hardcode — để vế *"vượt ngưỡng similarity"* của FR-32 / NFR-1c **áp được**. `[thêm 2026-07-25 — nhận việc treo]`

> **Vì sao việc này ở đây.** `search.py:97` **có** tính RRF score và `order_by(text("score DESC"))`, nhưng cùng file `return [row[0] for row in rows]` bỏ score đi, và `memories_routes.py:117` hardcode `score=0.0`. Không client nào thấy similarity. `nowing_evals/.../memory/recall/gate.yaml` buộc phải đặt `required_oracle_mode: rank_only`.
>
> **Việc này từng bị hoãn sang `3-11`, nhưng `3-11` đã `done` mà không làm** (*"dedupe đã wire; tuning ngưỡng optional qua 3-9"*). Hai note trỏ vòng vào nhau ⇒ mất chủ. Nhận về `3-14` vì `3-14` đã sửa đúng `search.py` và `AD-18` rule 1 (bounded top-k) **buộc** phải làm việc với score.
>
> ✅ Cập nhật 2026-08-01: `gate.yaml` đã trỏ đúng `Story 3.14`; `3-14` done.

**Thứ tự:** nên chạy **trước khi chốt số SM-10** của `3-9`, vì **hai** lý do độc lập:
1. `AD-18` rule 6 — baseline đo trên lượng inject phụ thuộc N thì không tái lập được.
2. **Oracle đang bị làm yếu.** `rank_only` chỉ hỏi *"có trong top 5 không"*, không hỏi *"có đủ giống không"* ⇒ gate **PASS được với kết quả rác** tình cờ rank cao. Chốt SM-10 dưới oracle này sẽ ra số dễ hơn thực tế.

Và là **điều kiện đi kèm** của `3.13`, vì `3.13` làm N tăng nhanh hơn.

_NFR-1b/1c/1d · `AD-18` · tiền đề của NFR-8 · nhận việc treo từ `3-11` (expose RRF score)._

### Story 3.15: Run Citations as Verifiable Sources  `(mới 2026-07-30)`  `[ready-for-dev]`
As a researcher,
I want scraper runs to be citable sources in chat,
So that I can trace claims back to the exact run that produced them.

**Acceptance Criteria:**
**Given** a chat answer that references data from a scraper run, **When** the model emits a citation, **Then** the citation points to the `Run` record (run id + capability + input snapshot) and renders as `run_<uuid>`.
**Given** a run citation in the UI, **When** I click it, **Then** it opens the run detail / citation panel showing the run output.
**And** citations carry a new `source_type = RUN` with structured fields; **And** the `RUN` source type is supported by citation renderers and the citation panel.

**Kỹ thuật:** add `RUN` to citation source enum, mint run citation from capability tool, parse `run_<uuid>` tokens in chat, render citation chip, open run in citation panel.
_FR-13 · FR-39 · upstream PR #1619._

### Story 3.16: Open Knowledge Format (OKF) Export  `(mới 2026-07-30)`  `[ready-for-dev]`
As a data owner or integrator,
I want to export my workspace knowledge base in Open Knowledge Format (OKF),
So that I can move, archive, or integrate Nowing knowledge with other tools.

**Acceptance Criteria:**
**Given** a workspace with documents, memories, and source provenance, **When** I request an OKF export, **Then** it produces a valid OKF bundle (documents, chunks, facts, relations, citations) that can be validated against the OKF schema.
**Given** the export, **When** inspected, **Then** it does not leak data from other workspaces and redacts API keys / secrets.

**Kỹ thuật:** build an export job over workspace-scoped `Document`, `Chunk`, `Memory`, `MemoryRelation`; serialize to OKF JSON; stream/limit size for large KBs.
_FR-32 · RS-8 · upstream PR #1617._

---

## Epic 6: Automations

_Đã DONE: 6.1 triggers, 6.2 runs/retries, 6.3 agent_task._

### Story 6.4: Direct Write-Back Actions  `[DONE per sprint-status: 6-4]`
As a workspace owner,
I want automation ghi trực tiếp Notion/Slack/Linear/Jira như action type,
So that workflow không phải đi vòng qua `agent_task`.

**Acceptance Criteria:**
**Given** automation definition, **When** thêm action type write-back (Notion/Slack/Linear/Jira), **Then** chạy được với retry + audit + **compensating action / best-effort undo** (KHÔNG phải true rollback — không un-send Slack được; nêu rõ giới hạn).
**And** quyết định kiến trúc OQ-5 (action type riêng vs agent_task tool) được ghi lại.
_FR-18 · OQ-5 · AD-DEFER-2. Lưu ý: agent_task đã cho phép write-back → đây là nâng cấp, không chặn beachhead._

### Story 6.5: Memory-Driven Automations  `[DONE per sprint-status: 6-5 — cải chính 2026-07-25]`

> **⚠️ Cải chính 2026-07-25 (readiness check C-B).** Header trước ghi `[GAP, post-MVP]` — **SAI**. Verify code: trigger `memory_change` (`app/automations/triggers/builtin/memory_change/`, đăng ký trong `triggers/builtin/__init__.py`) · action `continue_research` (`actions/builtin/continue_research/`, đăng ký trong `actions/builtin/__init__.py`) · `AutomationRun.research_thread_id` (`db.py:712` + relationship `db.py:746`) · resolve qua `dispatch/launch.py:44`. `sprint-status.yaml` (`6-5: done`) là bên đúng.
As a workspace owner,
I want automation trigger khi memory đổi / tiếp tục research thread theo lịch,
So that workflow nghiên cứu chạy liên tục không cần prompt tay.

**Acceptance Criteria:**
**Given** automation có trigger `memory_change` hoặc schedule, **When** memory mới match query/tags **OR** cron đến hạn, **Then** `AutomationRun` chạy với `research_thread_id` + memory context; action `continue_research`/`agent_task` write-back kết quả.
_FR-35 · AD-DEFER-6._

### Story 6.6: Playbook Reuse — expose `inputs.schema` đã có  `[GAP — P1, gated sau pilot BĐS]`

> **⚠️ Cải chính kiến trúc 2026-08-05 (Winston / architect review).** Bản đầu của story này viết *"thêm parameterization + `params_model` cho playbook"* — **SAI hiện trạng**. Verify code: `AutomationDefinition.inputs: Inputs | None` **đã tồn tại** và `Inputs.schema_` chính là *"JSON Schema (draft 2020-12) for accepted inputs"* (`schemas/definition/inputs.py`); `PlanStep.params` *"rendered at execute time"* (`plan_step.py:21-23`); `build_run_context()` expose namespace `{run, inputs, steps}` cho Jinja **sandboxed** (`templating/context.py:39`, `environment.py` — `SandboxedEnvironment` + `StrictUndefined`).
> ⇒ **Automation ĐÃ là template có tham số.** Story này KHÔNG xây cơ chế mới, mà **expose cơ chế đã có** thành playbook tái dùng được. **Tuyệt đối không thêm lớp params thứ hai** (sẽ tạo hai đường render — nợ kiến trúc tệ nhất).

As a workspace user (môi giới BĐS),
I want lưu một nghiệp vụ thành playbook tái dùng và chạy lại bằng cách điền biến,
So that tôi không phải mô tả lại toàn bộ yêu cầu nghiệp vụ mỗi lần.

**Acceptance Criteria:**
**Given** một `AutomationDefinition` đã chạy đúng, **When** user lưu nó thành playbook, **Then** hệ thống lưu definition đó làm template và **dùng chính `inputs.schema` sẵn có** làm hợp đồng tham số (KHÔNG sinh model params song song).
**And** **Given** một playbook, **When** user tạo instance mới với bộ inputs khác, **Then** automation mới sinh ra không cần viết lại `intent`, inputs được **validate theo `inputs.schema`** trước khi lưu, và audit ghi rõ `derived_from_playbook_id`.
**And** **Given** playbook được sửa sau khi đã có instance, **When** template đổi, **Then** hành vi versioning là tường minh: instance đang chạy **pin theo version cũ**, không bị đổi ngầm (tránh drift âm thầm).
**And** playbook có **ownership rõ ràng**: `workspace` (user tạo) vs `system` (Nowing ship sẵn) — không rò rỉ giữa workspace.
**And** playbook khai **tool-scoping**: chỉ subagent/tool cần thiết được phép gọi (giảm cost + tăng ổn định vs để agent tự chọn trong toàn bộ registry).
_Nền tảng đã có (dùng lại, không xây mới): `AutomationDefinition.inputs` + `Inputs.schema_` · `PlanStep.params` render-at-execute · `templating/` (Jinja sandboxed, `{run, inputs, steps}`) · `ActionDefinition.params_schema` (`actions/types.py`) · `all_actions()` (`actions/store.py`) · `WorkspaceMcpToolSetting` (tiền lệ scope per-workspace)._
_⚠️ Gate: KHÔNG build trước khi pilot BĐS 2 tuần cho tín hiệu retention — chưa biết `inputs.schema` cần field nào cho môi giới thì chưa build (xem `vision-lock-and-this-week-2026-08-04.md`)._

### Story 6.7: Schema-Driven Form UI cho playbook & action  `[GAP — P1, dep: 6.6]`

> **Vấn đề UX cần giải một lần cho mọi vertical.** Nowing có ~17 subagent builtin + MCP tools, và sẽ thêm nữa (xe, thiết bị B2B, tuyển dụng). Nếu mỗi tool phải code UI riêng → nợ UI tăng theo số tool.
> **Điểm mạnh kiến trúc:** cả `ActionDefinition.params_schema` (action) và `AutomationDefinition.inputs.schema` (playbook) đều là **JSON Schema draft 2020-12** ⇒ **một renderer dùng được cho cả hai**.

As a workspace user,
I want thao tác nghiệp vụ bằng form/filter thay vì viết prompt dài,
So that tôi dùng được mọi tool mà không cần học prompt, và tool mới có UI ngay.

**Acceptance Criteria:**
**Given** một action/playbook có JSON Schema (`params_schema` hoặc `inputs.schema`), **When** UI render nó, **Then** form được **tự sinh từ schema** (không hard-code UI cho từng tool) — thêm tool mới = thêm schema, **không thêm UI**.
**And** **Given** schema cần trải nghiệm bản địa (chọn quận, khoảng giá VNĐ, nhãn tiếng Việt), **When** render, **Then** renderer đọc **`x-ui` hints trong schema** (widget · label · options · đơn vị) để tùy biến — **giữ một renderer duy nhất**, không fork UI theo tool. *(Không có lớp hint này thì dự án sẽ bị kéo về hard-code UI từng tool — đúng thứ story muốn tránh.)*
**And** **Given** user gõ yêu cầu tự nhiên (web hoặc Zalo/Telegram bot), **When** LLM parse thành inputs, **Then** inputs **BẮT BUỘC validate lại bằng schema (Pydantic) trước khi lưu** — không tin trực tiếp output LLM — rồi hiện form/xác nhận gọn để user sửa (chat → parse → **validate** → confirm).
**And** **Given** một nghiệp vụ tần suất cao (Deal-Radar BĐS), **When** cần trải nghiệm tối ưu, **Then** cho phép override bằng filter UI chuyên biệt + nút **"Lưu tìm kiếm này thành cảnh báo"** (tái dùng thói quen filter sẵn có của môi giới, không bắt học prompt).
**And** danh sách tool KHÔNG phơi ra dạng menu kỹ thuật: gom theo vertical + ẩn sau tên nghiệp vụ người dùng hiểu.
_⚠️ Gate: dep 6.6; và chỉ build sau pilot xanh._

### Story 6.9: Workspace `vertical` — tiền đề cho playbook library  `[GAP — P2, dep: none — chặn 6.10]`

> **Phát hiện từ architect review:** khái niệm `vertical` **chưa tồn tại** trong schema. Không có nó thì không thể "gom playbook theo ngành".

As a platform operator,
I want mỗi workspace khai báo vertical của nó,
So that playbook, tool và UI có thể lọc theo ngành thay vì phơi tất cả cho mọi user.

**Acceptance Criteria:**
**Given** một workspace, **When** tạo hoặc cập nhật, **Then** nó có thuộc tính `vertical` (ví dụ `real_estate` · `auto` · `b2b_equipment` · `general`), mặc định `general` để backward-compatible.
**And** **Given** một playbook/tool khai `verticals[]`, **When** user duyệt, **Then** chỉ thấy item khớp vertical của workspace (hoặc `general`).
_ADR cần chốt kèm: **tool = code (subagent builtin), nghiệp vụ = data (playbook definition)** — tránh tình trạng nghiệp vụ nửa nằm ở `registry.py` nửa nằm ở JSON._

### Story 6.10: Playbook Library theo vertical  `[GAP — P2, dep: 6.6, 6.7, 6.9]`

As a workspace user,
I want chọn playbook làm sẵn theo ngành của tôi rồi điền biến,
So that tôi bắt đầu ngay mà không phải tự thiết kế nghiệp vụ.

**Acceptance Criteria:**
**Given** workspace có `vertical` (6.9), **When** user mở thư viện playbook, **Then** chỉ thấy playbook của vertical đó (BĐS: Deal-Radar · Verify tin đa nguồn · Tìm khách khớp · Viết mô tả tin).
**And** **Given** vertical mới cần mở, **When** thêm playbook, **Then** chỉ cần khai **definition + schema (data)**, không sửa code UI và không thêm subagent — đúng điều kiện `G6` của lộ trình nhân bản vertical.
_Tham chiếu: `vertical-expansion-roadmap-2026-08-04.md` (G6: mở vertical mới bằng config, ≤2-4 tuần)._

---

## Epic 8: Platform Operations (Billing / Usage / Token)

_Đã DONE: 8.1 token usage tracking (FR-30), 8.2 credit wallet + Stripe (FR-31)._

### Story 8.3: Usage & Credit Dashboard  `[DONE per sprint-status: 8-3]`
As a user,
I want dashboard xem usage/chi phí theo workspace/model/thời gian,
So that tôi hiểu mình tiêu gì (dữ liệu `TokenUsage`/`credit_micros_balance` đã có, thiếu UI).

**Acceptance Criteria:**
**Given** `TokenUsage` đã ghi, **When** mở usage dashboard, **Then** hiển thị aggregate theo workspace/model/`usage_type`/thời gian (gồm `memory_create`).
**And** buy-credits page hiển thị lịch sử, không chỉ current balance.
**UX Notes (nhẹ, brownfield):** bám pattern settings/buy-credits page hiện có trong `nowing_web/`; dashboard = bảng + biểu đồ aggregate theo workspace/model/thời gian. Cần contract đầy đủ → `bmad-ux`.
_NFR-7 · FR-31 · AD-DEFER-5._

### Story 8.8: Auto-Extract Kill-Switch & Safe Default  `(mới)` `(đánh lại số từ 8.4a — C-C)`  `[DONE — flags MEMORY_AUTO_EXTRACT_ENABLED (global) + workspaces.memory_auto_extract_enabled (per-ws) đã có]`
As a platform engineer,
I want kill-switch tin cậy + default an toàn cho auto-extract,
So that chi phí per-turn không kiểm soát dừng ngay lập tức.

**Acceptance Criteria:**
**Given** `MEMORY_AUTO_EXTRACT_ENABLED` + `workspaces.memory_auto_extract_enabled`, **When** đặt global kill-switch OFF, **Then** không task extraction nào enqueue ở bất kỳ turn (verify `assistant_finalize`); không cần redeploy; có test.
**Given** một workspace, **When** owner tắt riêng, **Then** extraction dừng cho workspace đó, không ảnh hưởng khác.
**Given** default an toàn, **When** tạo workspace mới, **Then** `memory_auto_extract_enabled` default phản ánh policy đã chốt (OFF tới khi gates ship).
_AR-6 · FR-15. **Dep: none** (P0)._

### Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit  `(mới)`  `[DONE — 59 tests passed; gate before auto-extract goes to prod]`
As a workspace owner,
I want spend budget cap + wallet pre-check + rate-limit theo thời gian cho auto-extract,
So that chi phí dự đoán được khi auto-extract bật.

**Acceptance Criteria:**
**Given** một workspace, **When** vượt **spend budget cap** trong kỳ HOẶC ví không đủ (wallet pre-check **TRƯỚC** khi enqueue LLM call phụ), **Then** extraction bị skip + log, không âm thầm đốt credit.
**And** rate-limit theo thời gian (ngoài `MAX_ITEMS=3` sẵn có); **And** edge anonymous-chat (FR-17) attribution rõ ràng.
_AR-6 · RS-1. **Dep: 8.4a** (kill-switch/flags đã có)._

### Story 8.9: Memory Cost/Turn Observability  `(mới)` `(đánh lại số từ 8.5 — C-C)`  `[DONE — code-complete qua sprint story 8-4 observability-logging]`
As a team,
I want cost/turn của memory extraction/recall được đo,
So that định lượng unit economics cloud trước khi pricing (SM-C2/RS-10).

**Acceptance Criteria:**
**Given** turn có extraction/recall, **When** hoàn tất, **Then** ghi span + cost với `usage_type="memory_create"`, attribute workspace+user.
**And** aggregate cost/turn (auto-extract ON vs OFF) đo trên staging/beta → input cho pricing.
_AR-5 · SM-C2 · RS-10._

### Story 8.10: Docs / README / Vision Sync  `(mới)` `(đánh lại số từ 8.6 — C-C)`  `[GAP — optional, chưa track trong sprint]`
As an OSS beachhead user (agent-builder),
I want README/docs phản ánh đúng vision research-memory + trạng thái đã ship,
So that mở repo không thấy định vị cũ / feature đã gỡ (tránh cảm giác vaporware).

**Acceptance Criteria:**
**Given** README/`docs/`/`project-overview.md` còn pre-pivot, **When** sync, **Then** phản ánh "long-term research memory" + gỡ mô tả sai (Admin role removed mig 72, AI File Sorting removed mig 172, "NotebookLM alternative").
**And** publish one-sentence promise + MCP quickstart; **And** **CI docs-vs-code drift check** chặn feature đã gỡ tái xuất hiện.
_OQ-6 · AR-10 · RS-5._

---

### Story 8.11: Admin UI for Global LLM Model Configuration  `(mới 2026-07-26)`  `[GAP — backlog]`

**Là** platform admin (vai trò mới, cấp toàn hệ thống — khác Workspace Owner/Editor/Viewer của FR-10),
**tôi muốn** thêm/sửa/xoá/bật-tắt global chat model (model dùng chung cho Auto mode) qua một trang settings trên web UI,
**để** không phải decode/sửa/encode base64 YAML trong `.env` rồi restart backend mỗi lần đổi model — quy trình hiện tại chỉ có thể thao tác thủ công qua terminal.

> **Vì sao story này tồn tại (phát hiện 2026-07-26, khi vận hành thực tế thêm model GLM-5.2/Gemini-3.6-Flash/GPT-5.6 cho Auto mode).** `global_llm_configs` chỉ đọc được từ file YAML (gitignored) hoặc `GLOBAL_LLM_CONFIG_B64` trong `.env`, parse **một lần lúc import** `app/config/__init__.py`. Không có UI, không hot-reload. `GET /global-model-connections` (`model_connections_routes.py`) đã cho xem, nhưng mọi endpoint viết (`POST/PUT/DELETE /model-connections*`) tường minh raise lỗi khi `scope == ConnectionScope.GLOBAL` ("GLOBAL connections are YAML-only"). Đồng thời hệ thống **chưa có khái niệm platform-admin** — chỉ có RBAC cấp workspace (FR-10). Field `User.is_superuser` đã tồn tại (fastapi-users) và đã lộ ra ở FE (`user.types.ts`, dùng cho PostHog identify) nhưng **không gate route nào**.

**Acceptance Criteria:**

**Given** một user có `is_superuser = false` (bao gồm Workspace Owner)
**When** gọi endpoint quản lý global model config
**Then** nhận **403** — route yêu cầu `is_superuser = true`, tách biệt hoàn toàn với RBAC workspace (FR-10 không đổi).

**Given** một platform admin (`is_superuser = true`) mở trang admin settings
**When** xem danh sách global model
**Then** thấy **hợp nhất** cả hai nguồn trong một danh sách: model từ YAML/`.env` (file-backed, nguồn hiện tại) **và** model tạo qua UI (DB-backed, mới) — có nhãn phân biệt nguồn ("Managed" vs "From config file")
**And** không có `api_key` thật nào trả về client (giữ nguyên pattern `has_api_key: boolean` đã dùng ở `ConnectionRead`).

**Given** platform admin điền form tạo global model mới (provider, model_name, api_key, api_base, cost per 1k input/output tokens, rpm/tpm)
**When** submit
**Then** model mới được tạo với `Connection.scope = GLOBAL` trong DB, và xuất hiện trong Auto mode pool **ngay lập tức** — không cần restart backend, không cần sửa `.env`.

**Given** một global model do UI tạo (DB-backed)
**When** admin sửa (tên, giá, enabled) hoặc xoá
**Then** thay đổi có hiệu lực ngay cho các chat call tiếp theo; model bị xoá không còn xuất hiện trong Auto mode pool.

**Given** một global model do YAML/`.env` quản lý (file-backed)
**When** admin xem trong UI
**Then** chỉ xem được + toggle enable/disable tạm thời — **không** sửa được field khác, **không** xoá được qua UI (giữ nguyên nguyên tắc operator-owned hiện tại cho nguồn file).

**Given** platform admin vừa nhập xong provider + api key + model_name cho một global model draft
**When** bấm "Test connection"
**Then** hệ thống gọi model thật một lần (tái dùng `verify_connection`/`test_model` đã có ở `model_connection_service.py`) và báo rõ thành công/lỗi trước khi cho lưu.

**Kỹ thuật (không phải AC, ghi để dev không phải đoán):**
- Thêm dependency `require_superuser()` trong `app/users.py`, song song `require_session_context`/`get_auth_context` hiện có — kiểm tra `AuthContext.user.is_superuser`.
- Mở endpoint mới (không sửa route cũ đang chặn `GLOBAL` cho user thường) dưới path riêng, ví dụ `/admin/global-model-connections`, dùng `require_superuser()` làm dependency; hoặc thêm nhánh rẽ trong route hiện có khi `scope == GLOBAL` **và** caller là superuser — chọn một, ghi lại trong story file.
- Mở rộng `materialize_global_model_catalog()` (`app/services/global_model_catalog.py`) để merge thêm `Connection`/`Model` rows có `scope == GLOBAL` từ DB vào cùng `GLOBAL_CONNECTIONS`/`GLOBAL_MODELS`, bên cạnh nguồn YAML/env hiện tại.
- Sau mỗi CRUD của admin, gọi `refresh_global_model_catalog()` (đã tồn tại, hiện chỉ gọi sau OpenRouter refresh ở `initialize_openrouter_integration()`) để hot-reload — đây là seam có sẵn, không cần dựng mới.
- Billing: field cost phải map đúng vào `litellm_params.input_cost_per_token`/`output_cost_per_token` để `pricing_registration.py` đăng ký giá cho LiteLLM (đúng cơ chế `AD-8`, không phải giá phẳng).
- FE: trang mới, tái dùng component ở `nowing_web/components/settings/model-connections/` (provider picker, connect form) nhưng đặt ở route cấp platform (không phải `/dashboard/[workspace_id]/...`), gate bằng `user.is_superuser` phía client (defense-in-depth, không thay cho check backend).

_FR-41 · AD-8 (cost registration) · AD-9 (mở rộng — không đổi 3 role cấp workspace) · `model_connections_routes.py` · `app/config/__init__.py` (`load_global_llm_configs`, `refresh_global_model_catalog`) · `app/services/global_model_catalog.py`._

### Story 8.12: Workspace Limits  `(mới 2026-07-30)`  `[ready-for-dev]`
As a platform admin,
I want to enforce per-workspace limits (documents, members, storage, runs),
So that I can offer tiered plans and prevent abuse on the cloud offering.

**Acceptance Criteria:**
**Given** a workspace on a free/team/enterprise plan, **When** it reaches a limit, **Then** subsequent operations are blocked with a clear upgrade message.
**Given** the workspace settings, **When** an admin opens it, **Then** they see current usage vs limits and an upgrade CTA.
**And** limits are enforced backend-side (not just UI); **And** anonymous/self-host defaults keep existing behavior.

**Kỹ thuật:** add `WorkspaceLimit` / plan config, gate document upload, member invite, and run creation; expose usage/limit API; build settings UI.
_FR-3 · FR-30 · upstream PR #1609._

### Story 8.13: PostHog Product Analytics  `(mới 2026-07-30)`  `[ready-for-dev]`
As a product team,
I want PostHog analytics integrated into the web app,
So that I can understand user flows, feature adoption, and retention.

**Acceptance Criteria:**
**Given** `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` are configured, **When** the web app loads, **Then** PostHog is initialized and captures pageviews and key events.
**Given** a superuser, **When** viewing analytics, **Then** identifiable data is hashed/anonymized and no API keys or workspace content is sent.

**Kỹ thuật:** add `@posthog-js` (if not already), initialize in layout, wrap key events, keep server-side observability separate.
_NFR-3 · upstream PR #1622._

---

## Epic 9: Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`

> **Nguồn:** `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED, D1–D4). **Governed by:** `AD-15` (+ AD-7; AD-8 amended cho cost; AD-3 amended bỏ FR-24).
> **Đối ứng phía ChainLens:** Epic 42 (`42-1` costDollars-in-SSE *spec ready*, `42-2` contract regression-guard, `42-3` verify Nowing needs) + Epic 43 (`43-1` eval-harness GATE 0, `43-2` planner-DAG, `43-5` cache hit-rate).
> **Gate quan trọng:** không chốt bất kỳ con số pricing/subscription nào trước khi **9.2** và **8.7** có số cost đo thật.
> **🔒 Thứ tự cứng (D5, 2026-07-25 · cập nhật sau khi tách story):** **`9.1a`** → **public repo** → `9.1b` + `9.2` + `8-7` → `9.3` → `9.4` → *(tuỳ chọn)* `9.6a` → `9.6b`. **Chỉ `9.1a` chặn public repo** — vì lý do **mô hình kinh doanh**, không phải kỹ thuật: engine closed-source + Nowing public ⇒ **mọi self-host instance chạy ở trạng thái không có engine**; thiếu degradation thì self-host không dùng được và đường OSS/PLG sụp. `9.1b` (contract guard) là P0 nhưng **không** chặn. Nguồn: SCP §8 D5, PRD §1.1 + §4.9 FR-38, `AD-15`.

> **⚠️ Tách story 2026-07-25 (readiness Q-3).** `9.1` cũ gộp **hai concern khác nhau**: (a) contract regression test — bảo vệ Nowing khỏi việc engine đổi format; (b) degradation — bảo vệ **mô hình kinh doanh** self-host. Khác mục đích, khác rủi ro, khác file, test được độc lập. Quan trọng hơn: chỉ **(b)** mới thật sự chặn public repo; gộp lại làm public repo bị chặn oan bởi (a). ⇒ tách thành **`9.1a`** (chặn public repo) và **`9.1b`** (P0, không chặn).

### Story 9.1a: Research Degradation & Self-Host Independence  `(mới)`  `[DONE — P0, tiền đề trước khi public repo]`
As a self-hoster,
I want Nowing dùng được đầy đủ **mà không cần** deep-research engine, và deep research **không hard-fail** khi engine chậm/chết/chưa cấu hình,
So that tôi không cài xong mới phát hiện một tính năng vỡ, và đường OSS/PLG không sụp.

**Acceptance Criteria:**

**Given** ChainLens timeout (`CHAINLENS_REQUEST_TIMEOUT_SECONDS`, default 300s) hoặc trả 5xx
**When** request deep research
**Then** Nowing **degrade** sang hybrid search (`app/retriever/`) và trả trạng thái tường minh `partial` (có evidence một phần) hoặc `engine_unavailable` (không có)
**And** **không bịa citation**, không giả vờ là câu trả lời đầy đủ; trạng thái degrade hiển thị được cho user/agent.

**Given** self-host không cấu hình ChainLens (`CHAINLENS_API_KEY` rỗng)
**When** user dùng Nowing
**Then** mọi tính năng khác hoạt động bình thường; deep research trả `engine_unavailable` kèm hướng dẫn cấu hình
**And** không có exception chưa bắt, không có 500.

**Given** engine gửi tường minh `{type:'partial', state:'insufficient_evidence', reason}` và `{type:'insufficientEvidence', partial, reason}` *(verify code ChainLens `api.ts:1299-1309`)*
**When** parse SSE
**Then** Nowing **đọc và dùng** hai event đó cho trạng thái `partial`
**And** **bỏ heuristic đang suy đoán lại** — hiện `executor.py` đoán bằng `if not answer and not sources: if saw_done → insufficient_evidence else → timeout`, tức **gộp "không tìm ra bằng chứng" với "stream chết giữa đường"** vào một phép đoán, trong khi engine đã phân biệt sẵn kèm `reason`
**And** `reason` từ engine được truyền lên user/agent, không bị nuốt.

**Given** engine gửi `{type:'heartbeat'}` *(verify code ChainLens)*
**When** stream đang chạy
**Then** Nowing dùng heartbeat để phân biệt **"đang chạy"** vs **"đã chết"** — thay vì chỉ dựa vào timeout 300s.

**Given** ba nhánh success / timeout-degrade / unconfigured
**When** chạy test suite
**Then** cả ba đều có test.

**Given** engine closed-source và Nowing public (ranh giới OSS/Cloud, D5) — nghĩa là **mọi self-host instance đều ở trạng thái không có engine**
**When** review trước khi public repo
**Then** story này PHẢI done trước; docs/README/`docker/`/`.env.example` ghi rõ **deep research là năng lực cloud** (Phase 1)
**And** không để người self-host cài xong mới tự phát hiện tính năng vỡ.

_FR-38 · AD-15 · D5. Files: `app/capabilities/chainlens/research/executor.py`, `app/retriever/`, `tests/unit/capabilities/chainlens/`, `docker/`, `.env.example`._

### Story 9.1b: Research Contract Regression Guard  `(mới)`  `[DONE — P0, không chặn public repo]`
As a Nowing maintainer,
I want contract với deep-research engine được khoá bằng test trong CI,
So that engine đổi format thì tôi biết trước khi vỡ production, chứ không phát hiện qua báo lỗi của user.

**Acceptance Criteria:**

**Given** contract `POST /api/v1/search` SSE — request `{query, optimizationMode, sources, history, systemInstructions?, chatId?}`; response block-SSE (`type:block` / `type:updateBlock` RFC6902 patch / `data:[DONE]` / `event:error`)
**When** CI chạy
**Then** có **contract regression test** khoá cả request shape và SSE parse: block create/replace, RFC6902 patch trên `/data`, `[DONE]`, `event:error`, metadata `chatId`/`webUrl`
**And** test **fail** nếu engine đổi format → biết trước khi vỡ prod.

**Given** query dài hơn `MAX_QUERY_LENGTH` (500)
**When** gửi request
**Then** bị clamp trước khi gọi engine (engine tự clamp ở 500; query rỗng bị engine trả 400).

**Given** một câu trả lời có nhiều source
**When** parse SSE
**Then** `sources[]` giữ **nguyên thứ tự trích dẫn** để map đúng về citation UI.

**Given** contract đang bị **document SAI** ở phía Nowing *(OQ-7, verify 2026-07-25)*
**When** viết test và sửa tài liệu
**Then** sửa PRD §4.9 FR-24 + `AD-15` + SCP §3: **KHÔNG có dòng `event:`** — NestJS `@Sse()` chỉ phát **data-only frame**, `type` nằm **bên trong** JSON; và terminal marker thật là `{"type":"done"}`, **không** phải `data: [DONE]`
**And** gỡ (hoặc ghi rõ là defensive-only) nhánh xử lý `event:` trong `_parse_sse` — nhánh đó **không bao giờ chạy**
**And** test phải bám format **thật**, không bám tài liệu cũ.

**Given** ChainLens `42-2` đã có `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` — bản **mirror parser của Nowing**, dùng **chính** `rfc6902 applyPatch` mà `session.ts updateBlock` dùng
**When** viết contract test phía Nowing
**Then** **tham chiếu/đồng bộ fixture đó**, không viết fixture thứ hai (hai fixture sẽ lệch dần theo thời gian)
**And** đề xuất ChainLens export golden JSON dùng chung được.

_FR-24 · AD-15 · OQ-7(1)+(4). Files: `tests/unit/capabilities/chainlens/research/test_executor.py`, `app/capabilities/chainlens/research/executor.py` (gỡ nhánh `event:`), PRD §4.9, `AD-15`. **Đối ứng ChainLens:** `42-2`._

### Story 9.2: Deep-Research Cost Metering (cost thật, không giá phẳng)  `(mới)`  `[DONE — P0, parser + fallback in place; waits ChainLens 42-1 costDollars in production]`
As a PO định giá cloud,
I want cost mỗi deep-research call được ghi theo **cost thật engine báo về**, không theo hằng số env,
So that pricing/subscription có cost basis thật thay vì phỏng đoán sai 2–3×.

**Bối cảnh (verified 2026-07-25):** `CHAINLENS_QUERY_MICROS_PER_CALL = 5000` → **$0.005 phẳng/call bất kể mode** (`app/config/__init__.py:806`), trong khi `mode` default = `"quality"` (`schemas.py:38`) có target cost **$0.0105** (deep research $0.0164) → **under-meter 2.1–3.3×**. Và các số target đó tính trên DeepSeek stack **chưa vào prod** (ChainLens `DEFAULT_MODEL_POLICY` = 100% `ag/` Gemini, output đắt hơn DeepSeek ~3.5×). `grep costDollars` trong `nowing_backend/` = **0 hits**.

**Acceptance Criteria:**

**Given** ChainLens emit `costDollars` ở SSE terminal event (dependency: ChainLens `42-1`, *spec ready*)
**When** một deep-research call hoàn tất
**Then** executor parse `costDollars` → ghi `TokenUsage` với `usage_type="deep_research"` + `workspace_id`/`user_id`/`thread_id`
**And** wallet debit dùng **cost thật**.

**Given** engine **không** emit cost (version cũ / lỗi)
**When** call hoàn tất
**Then** fallback về `CHAINLENS_QUERY_MICROS_PER_CALL` **và log warning** (để đo tần suất fallback)
**And** `BillingUnit.CHAINLENS_QUERY` không còn là nguồn chân lý.

**Given** đã có dữ liệu
**When** truy vấn aggregate
**Then** cost thật/call **theo mode** đo được (SM-11a) + tỷ lệ fallback; nối vào dashboard NFR-7 khi có.

**Given** chưa có SM-11a
**When** ai đó đề xuất chốt giá subscription
**Then** **chặn** — gate: cần 9.2 + 8.7 có số thật trước.

_FR-37 · AD-8(amended) · AD-15 · SM-11a · OQ-7(3). Files: `app/capabilities/chainlens/research/executor.py`, `app/capabilities/core/billing.py`, `app/capabilities/core/types.py`, `app/services/token_tracking_service.py`._

### Story 9.3: Latency Budget & State A→B Gate  `(mới)`  `[GAP — P1]`
As a product owner,
I want đo latency deep-research **từ phía Nowing** và có đường async deliverable làm sàn,
So that không cược vào giả định latency theo chiều nào, và biết đúng lúc nào được bật sync chat-mode.

**Bối cảnh:** baseline ChainLens cuối (2026-07-18) FAIL (Ask 57–136s, quality 198s) **nhưng có thể stale** — `ADR-DEEP-RESEARCH-SPEED` phases 1-7 đã ship mà `20-0`/`20-8` chưa đo lại. Trạng thái đúng = **"chưa biết"**. Lộ trình giảm latency: ChainLens `43-1` (GATE 0) → `43-2` planner-DAG + `43-5` cache hit-rate. **Không** phụ thuộc owned index (Epic 26, `AD-DEFER-7`).

**Acceptance Criteria:**

**Given** deep research chạy qua Nowing
**When** hoàn tất hoặc fail
**Then** Nowing ghi p50/p95 latency **per mode** từ phía mình (SM-11b) + fallback rate (SM-11c) — không chờ engine tự báo.

> **✅ Thu hẹp theo `AD-17` (2026-07-25, giải readiness U-1/U-2).** **Cải chính:** hạ tầng async **đã có end-to-end** — `?mode=async` → 202 + `X-Run-Id`, SSE `GET .../runs/{id}/events`, ring buffer replay 500 event, cancel, history; và **web đã có typed client** (`scrapers-api.service.ts:68`). `chainlens.research` **đã nằm sau door đó**. ⇒ Story này **KHÔNG xây flow mới**, chỉ làm 3 việc còn thiếu thật (dưới) + đo lường + ngưỡng.
> **U-2 chốt:** delivery đi **SSE**; **KHÔNG** thêm `runs` vào `ZERO_PUBLICATION` (bảng log lớn, TTL 30 ngày, `output_text` JSONL — `AD-5` giữ nguyên phạm vi).

**Given** State A và async door đã tồn tại
**When** user/agent yêu cầu deep research
**Then** dùng **đúng door sẵn có** (`?mode=async` + SSE `runs/{id}/events`) — không tạo bảng job mới, không tạo endpoint progress mới.

**Given** `run_event_bus` hiện **single-process** (`events.py` tự ghi: *"a multi-worker deployment needs Redis pub/sub … behind this same interface"*)
**When** API chạy nhiều replica/worker
**Then** đặt **Redis pub/sub** sau **cùng interface** `run_event_bus` (Redis đã có cho Celery, `AD-4`); **không đổi call-site**
**And** có test: client tail SSE ở replica A **thấy được** event của run chạy ở replica B
**And** đây là **tiền đề trước khi bật deep-research async trên môi trường nhiều replica** — thiếu nó thì mất event **im lặng, không lỗi**.

**Given** agent door hiện **SYNC** (`app/capabilities/core/access/agent.py` gọi executor inline, không có `mode`)
**When** agent gọi deep research trong một chat turn
**Then** agent **submit rồi trả về** `run_id` + thông báo đang chạy; chat turn kết thúc, **không** chặn tới 300s
**And** đây là **phần khó nhất của story này** — transport đã xong, chỗ block nằm ở agent door.

**Given** `run.finished` chỉ là event trên bus (grep `Notification|notify` trong `rest.py`/`runs.py` = 0 hit) và kết quả nằm trong `runs.output_text` (TTL 30 ngày)
**When** một deep research hoàn tất
**Then** emit `Notification` (bảng `notifications` đã có ở `app/notifications/persistence.py` và **đã nằm trong `ZERO_PUBLICATION`** → realtime sẵn)
**And** nếu user yêu cầu, persist kết quả thành **deliverable hạng nhất**, không dựa vào TTL của `runs`.

**Given** mode default hiện là `quality` (D3: đổi sang `balanced`)
**When** apply đổi default
**Then** `balanced` là default; `quality` là opt-in tường minh (deep-research/deliverable request)
**And** validate chất lượng trên `nowing_evals`; nếu hồi quy đáng kể → revert `quality` và **ghi lại lý do**
**And** reversible qua env var.

**Given** State B đủ điều kiện
**When** bật sync chat-mode
**Then** bật **sau feature flag**, giữ nguyên đường async.

**Deliverable tài liệu (không phải AC — sửa readiness Q-5):** story này **xuất ra** một quyết định ngưỡng p95 + định nghĩa cổng A→B, ghi vào NFR-9. Trước đây điều này bị viết thành AC (*"Then định nghĩa ngưỡng cụ thể"*) → AC tự tham chiếu, không verify được. Ngưỡng vẫn phải đặt **sau** khi có baseline đo được (kỷ luật đúng: không đặt ngưỡng trước khi đo — đó là lỗi của NFR6 phía ChainLens); nhưng nó là *sản phẩm đầu ra*, không phải *tiêu chí nghiệm thu*.

> **✅ Cải chính U-3 (2026-07-25, sau khi verify code ChainLens — OQ-7 câu 4 đã RÚT).** Readiness ghi *"progress chỉ có 2 event, phải chờ engine emit thêm"*. **Sai.** ChainLens **đã emit progress từ trước**: `api.ts:414` (`requestAcceptedAt`, `firstProgressAt`) · `api.ts:1298` (`+evidenceReadyAt`) · `api.ts:221` (`+firstFactualChunkAt`) · `api.ts:1299` (`evidence_ready` kèm `sources`) · cộng `synthesizing`, `heartbeat`. **Parser Nowing bỏ hết** — `_parse_sse` chỉ dispatch 4 type (`error`/`done`/`block`/`updateBlock`), block chỉ đọc `text` + `source`. ⇒ **Không chờ ChainLens.** Đây là việc của story này.

**Given** ChainLens đã emit `{type:'progress', requestAcceptedAt, firstProgressAt, evidenceReadyAt?, firstFactualChunkAt?}`, `{type:'evidence_ready', sources}`, `{type:'synthesizing'}`
**When** Nowing parse SSE
**Then** map các event đó sang `emit_progress(phase, message)` để chúng chảy vào `run_event_bus` (`AD-17`) và tới UI
**And** UX progress-first có nội dung thật để hiển thị, không phải *"Researching…"* rồi đứng im vài phút
**And** `firstFactualChunkAt` dùng làm mốc TTFB đo được cho SM-11b.

**Given** parser hiện bỏ im lặng mọi `type` không biết
**When** thêm mapping
**Then** giữ nguyên tính **forgiving** — `type` lạ vẫn bỏ qua, không raise (để ChainLens ship event mới mà không làm vỡ Nowing).

_NFR-9 · **`AD-17`** · FR-24(mode default, D3) · SM-11b/c · AD-4 (Redis) · AD-5 (giữ nguyên — `runs` không vào Zero). Tiền đề UX: `ux-designs/` chỉ có scaffold rỗng → cần UX spec async/progress-first trước khi build UI deep-research._

### Story 9.4: Docs — Quan hệ Nowing ↔ ChainLens  `(mới)`  `[DONE — P1, README/docs/.env.example synced]`
As an OSS user / self-hoster,
I want docs nói rõ Nowing là sản phẩm, deep research là năng lực hosted, và Nowing dùng được mà không có nó,
So that tôi không cài xong mới phát hiện một tính năng vỡ.

> **⚠️ AC đã sửa 2026-07-25 theo D5.** Bản trước ghi *"docs hướng dẫn self-host chạy ChainLens hoặc chấp nhận degradation"* — **sai**: engine closed-source nên self-host **không thể chạy nó**. Docs phải nói deep research là **năng lực cloud** (Phase 1), không phải một biến môi trường cần cấu hình.

**Acceptance Criteria:**

**Given** README/`docs/` hiện pre-pivot và không nói gì về ranh giới
**When** sync
**Then** có mục **Nowing = sản phẩm** + **deep research chạy trên hosted engine của Nowing**
**And** gọi engine là *"Nowing's hosted deep-research engine"* — **KHÔNG** nêu tên ChainLens ở bất kỳ tài liệu công khai nào (NG-3, D5)
**And** nêu **non-goals** (NG-1 không bán research data / không owned index; NG-2 không parity consumer).

**Given** ranh giới OSS/Cloud (D5)
**When** người self-host đọc README
**Then** có **bảng feature self-host vs cloud** ghi thẳng: deep open-web research là năng lực cloud (Phase 1)
**And** `docker/` + `.env.example` nói rõ Nowing chạy đầy đủ **không cần** engine; nếu không cấu hình thì deep research trả `engine_unavailable` (FR-38)
**And** không có hướng dẫn nào ngụ ý self-host tự dựng được engine.

**Given** repo dùng dual-license (`AD-16`): Apache-2.0 cho core, **BSL 1.1** cho `nowing_backend/app/proprietary/**`
**When** viết README/landing/docs
**Then** **KHÔNG** gọi cả sản phẩm là "open source" — BSL tự tuyên bố không phải OSS; dùng *"Apache-2.0 core + BSL 1.1 crawler engine"*
**And** nói rõ BSL cho phép production use nhưng cấm bán lại dạng hosted/managed service — kể thẳng, không lấp liếm.

**Given** luật messaging ở `briefs/brief-Nowing-2026-07-25/brief.md` §7
**When** viết README/landing
**Then** copy tuân thủ bảng NÓI/KHÔNG NÓI: chỉ tiếng Anh · không gọi tên đối thủ · không dẫn bằng "citations" · không định vị VN/tiếng Việt · không nêu tên engine.

_OQ-6(mở rộng) · AR-10 · FR-38 · D5 · NG-1/2/3. Phối hợp với Story 8.10 (vision sync) — nên làm cùng một lượt. Nguồn copy: `briefs/brief-Nowing-2026-07-25/brief.md` §1, §5.1, §7, §8._

### Story 9.5: Metered Deep-Research Endpoint cho Self-Host  `(mới)`  `[POST-MVP — CHƯA PHÊ DUYỆT, đăng ký để không bị mất]`
As a self-hoster,
I want trả tiền theo call để dùng deep research trên bản self-host,
So that tôi không phải chuyển sang cloud chỉ vì một năng lực.

> **Trạng thái: deferred.** Đây là **Phase 2** của D5. Mở khi (a) có số self-host thật, và (b) story `9.2` cho số cost để định giá. Không build trước hai điều đó.

**Acceptance Criteria (nháp — cần SCP phê duyệt trước khi dev):**

**Given** Phase 2 được phê duyệt
**When** self-host gọi deep research
**Then** request đi theo đường `self-host Nowing → Nowing Cloud API (metered, key theo account) → engine (vẫn 1 service key)`
**And** **CẤM** `self-host → engine trực tiếp` — cách đó biến engine thành public multi-tenant SaaS có end-user auth, phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 và SCP v4 de-scope
**And** metering/quota/chống abuse nằm ở Nowing Cloud (tái dụng account + credit wallet, `AD-8`), không nằm ở engine.

**Given** self-host không có key Nowing Cloud
**When** gọi deep research
**Then** hành vi giữ nguyên như Phase 1 — `engine_unavailable`, không hard-fail (FR-38).

_D5 · AD-15 · AD-8 · FR-37/FR-38. **Đã loại (không mở lại mà không có SCP mới):** phát hành binary/Docker closed-source của engine._

> **⚠️ Tách story 2026-07-25 (readiness Q-4).** `9.6` cũ gộp **bốn việc**: (1) migration source ref · (2) writer set `SCRAPER_RUN` · (3) quyết định retention · (4) API `revalidate()`. Việc (4) là một feature riêng và **phụ thuộc** (1)+(2). Việc (3) đã được chốt ở `AD-11.1` nên không còn là việc của story. ⇒ tách **`9.6a`** (provenance recipe) → **`9.6b`** (re-validation API).

### Story 9.6a: Memory Provenance Recipe (nền của re-validation)  `(mới)`  `[GAP — defect schema, phát hiện 2026-07-25]`
As an agent hoặc người dùng,
I want một memory sinh ra từ dữ liệu scrape trỏ được về đúng lần scrape và chạy lại được truy vấn đó,
So that hệ thống biết fact nào đã cũ thay vì trả về thông tin hết hạn kèm citation trông đáng tin.

> **Đây là tiền đề của differentiator "memory có nguồn sống, tự re-validate"** — thứ phân biệt Nowing sau khi "memory có citation" thành table-stakes (5 bên ship trong 90 ngày, xem brief §4). Nền tảng đắt nhất **đã có**: `Run` lưu `capability` + `input` JSONB nên re-execute được chính xác. Chỉ bị chặn ở 3 chỗ nhỏ.

**Vấn đề (verified 2026-07-25):**
1. `Memory.source_id` = `Integer` (`db.py:2077`) vs `Run.id` = `UUID` (`db.py:3155`) → không lưu được link
2. Không có code nào ghi `MemorySourceType.SCRAPER_RUN` — enum khai báo ở `db.py:572` rồi bỏ đó
3. `RUNS_RETENTION_DAYS = 30` (`capabilities/core/runs.py:33`) → re-validate hỏng sau một tháng

**Acceptance Criteria:**

> **✅ Quyết định kiến trúc đã chốt — `AD-11.1` (2026-07-25, giải readiness Q-2).** AC trước đây chứa *"chọn một trong hai, ghi lý do trong ADR"* → không testable, dev không biết verify gì. Nay đã chốt: **`Memory` tự chứa recipe**; **KHÔNG** dùng retention có điều kiện cho `runs`.
> *Lý do:* cleanup `runs` hiện là cơ hội (~1% insert, `runs.py:33-37`) — làm nó có điều kiện biến một cleanup rẻ thành truy vấn có khoá; `runs.output_text` (JSONL) giữ vô hạn là đắt sai chỗ (cần *recipe*, không cần *payload*); và AD-11 đã nói memory là first-class persistence layer nên nó **không được** phụ thuộc lifecycle của bảng log.

**Given** `Memory.source_id` là Integer (`db.py:2077`) vs `Run.id` = UUID (`db.py:3155`)
**When** thêm khả năng re-validate
**Then** `Memory` có **`source_capability`** (String), **`source_input`** (JSONB), **`source_run_id`** (UUID nullable, **không FK cứng** — `Run` được phép biến mất)
**And** `Memory.source_id` (Integer) **giữ nguyên** cho nguồn `document`/`chat_message` — không đổi kiểu cột đó
**And** có migration + test không hồi quy cho hai nguồn cũ.

**Given** auto-extract chạy trên một chat turn có kết quả scrape
**When** tạo memory từ đó
**Then** set `source_type = SCRAPER_RUN` + **sao chép** `capability` và `input` từ `Run` vào `Memory` + ghi `source_run_id`.

**Given** `RUNS_RETENTION_DAYS = 30` và cleanup cơ hội `_maybe_cleanup`
**When** `Run` bị xoá sau 30 ngày
**Then** memory tham chiếu nó **vẫn re-validate được** (đã có recipe riêng)
**And** cleanup `runs` **KHÔNG** được sửa thành có điều kiện — không join sang `memories`.

**Given** `source_input` là snapshot bất biến
**When** ai đó muốn đổi truy vấn
**Then** tạo memory mới, **không** mutate recipe cũ (mutate làm "re-validate" mất nghĩa).

_FR-39 (phần provenance) · **`AD-11.1`** · FR-32. **Dep:** không. **Ưu tiên:** không chặn launch; là **tiền đề của 9.6b**._

### Story 9.6b: Source Re-Validation API  `(mới)`  `[GAP — dep: 9.6a]`
As an agent hoặc người dùng,
I want hệ thống chạy lại được truy vấn gốc của một memory để biết fact còn đúng không,
So that memory không trả về thông tin đã cũ kèm citation trông đáng tin — thứ tệ hơn là không trả gì.

> Đây là phần **kể được câu chuyện** *"memory có nguồn sống, tự re-validate"* (brief §4). `9.6a` chỉ mở đường; story này mới là tính năng.

**Acceptance Criteria:**

**Given** một memory có `source_capability` + `source_input` (từ `9.6a`)
**When** gọi `revalidate(memory_id)`
**Then** chạy lại capability với input đó → so sánh kết quả với `content`
**And** nếu khớp → cập nhật timestamp "last verified"; nếu lệch → hạ `confidence` **và** tạo `MemoryVersion` ghi lại thay đổi
**And** **không** tự động xoá memory cũ (giữ kỷ luật FR-34 — không xoá cứng).

**Given** memory nguồn `document`/`chat_message` (không có recipe)
**When** gọi `revalidate`
**Then** trả trạng thái tường minh "không re-validate được cho nguồn này", **không** lỗi 500.

**Given** re-validate gọi lại một capability có phí
**When** chạy
**Then** chi phí được meter như một capability call bình thường (`AD-8`) — không có đường tính phí ẩn.

**Given** `Run` gốc đã bị xoá sau 30 ngày
**When** gọi `revalidate`
**Then** vẫn chạy được (recipe nằm trong `Memory` theo `AD-11.1`) — đây là AC chứng minh quyết định `AD-11.1` đúng.

_FR-39 (phần re-validate) · **`AD-11.1`** · FR-34 · AD-8. **Dep: 9.6a.** **Ưu tiên:** không chặn launch, nhưng **P0 nếu muốn kể câu chuyện re-validation** — xem brief §4, §8, §12 H-3._

---

## Epic 4: Chat & Agents

_Đã DONE: 4.5 MCP memory tools, 4.6 research continuity._

### Story 4.7: Pointer-Based Tabs with Live Title Resolution  `(mới 2026-07-30)`  `[ready-for-dev]`
As a user with many open documents and chats,
I want tabs to be lightweight pointers that resolve titles from the live source,
So that tab state is fast to save/load and titles stay up to date without stale snapshots.

**Acceptance Criteria:**
**Given** a workspace with documents and chats open in tabs, **When** a document/chat title changes, **Then** the tab bar reflects the new title without a full refresh.
**Given** many tabs, **When** the app loads, **Then** tab state is small (pointer: entity id + kind) and titles are fetched via `useResolvedTabs`.
**And** tab state uses the v2 storage key; **And** fallback navigation works for pointer tabs.

**Kỹ thuật:** refactor `Tab` to pointer-only state, add `useResolvedTabs` hook, resolve document/chat title via Zero/`react-query`, render `TabBar` from resolved tabs.
_FR-14 · upstream PR #1609._

---

## Epic 7: Multi-surface Clients

_Đã DONE: 7.1 web, 7.2 desktop, 7.3 browser extension, 7.5 Obsidian, 7.6 MCP server._

### Story 7.4: Dedicated Connectors Layout  `(mới 2026-07-30)`  `[ready-for-dev]`
As a workspace member,
I want a dedicated page (not a modal) for managing connectors,
So that I can search, group, view health, and connect new data sources in a focused UI.

**Acceptance Criteria:**
**Given** I open workspace settings, **When** I click "Connectors", **Then** I navigate to a dedicated route with a sidebar panel and a searchable grid/list of connectors.
**Given** the connectors page, **When** I view a connector, **Then** I see its type, health, indexing state, and grouped rows by category.
**And** the layout supports live connectors without a saved config; **And** the MCP icon masks `currentColor`.

**Kỹ thuật:** add `/connectors` route, build `useConnectorRows` hook, group connectors by type, add mobile drawer for adding connectors.
_FR-25 · FR-7/8 · upstream PR #1624._

---

## Epic 10: Connector & Scraper Expansion

_Tạo 2026-08-03 để chứa các scraper/capability mới ngoài phạm vi epic cũ._

### Story 10.1: Batdongsan.com.vn Scraper  `[review]`

As a real-estate researcher or investor in Vietnam,  
I want to scrape property listings from batdongsan.com.vn,  
So that I can track market trends, prices, supply, and locations in my workspace.

**Acceptance Criteria:**
- Gọi mobile API `https://apimap.batdongsan.com.vn/api/p_sync` và giải mã response obfuscate (`gzip → base64 → nibble-swap → Latin-1 JSON`).
- Trả về danh sách listing đã typed: `listing_id`, `title`, `price`, `area`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `phone`, `phone_display`.
- Hỗ trợ phân trang, `max_pages`/`max_items`, rate limit 0.5s/proxy.
- Trả về `degraded=true` khi API thay đổi, rate limit, hoặc decode lỗi; không hard-fail.
- Billing per listing qua `BATDONGSAN_ITEM`; expose qua REST, agent, MCP.
- Mở trang chi tiết bằng `AsyncStealthySession`, thực thi XHR `DecryptPhone` trong page context để lấy `phone` đầy đủ khi có authenticated cookies.
- Admin UI `/admin/scraper-accounts` hỗ trợ paste JSON cookies và tự động extract bearer token; `scripts/capture_batdongsan_session.py` hỗ trợ CDP / headed Playwright capture.
- Tự động pre-warm session (ghé `/dang-nhap`) khi `con.ses.id` sắp hết hạn để duy trì phone unmask trong suốt `accessToken` lifetime.

**Kỹ thuật:** thêm `app/proprietary/platforms/batdongsan/` (BSL 1.1) cho fetcher/parser và `app/capabilities/batdongsan/scrape/` (Apache-2.0) cho capability/executor/definition, theo pattern `reddit.scrape`. Xem story file `10-1-batdongsan-scraper.md`.

_FR-6 · AD-3 · AD-16 · AD-19 · `technical-batdongsan-scraper-research-2026-08-02.md`._

### Story 10.2: Chotot.vn / Nhà Tốt Scraper  `[done]`

As a real-estate researcher or investor in Vietnam,  
I want to scrape property listings from `chotot.com` (Nhà Tốt),  
So that I can cross-compare classified listings with batdongsan.com.vn and identify real market prices.

**Acceptance Criteria:**
- Scrape public listing pages from `chotot.com` mục Nhà Tốt (`nha-dat`, `ban-can-ho`, `ban-nha-rieng`, `cho-thue`).
- Trả về danh sách listing đã typed: `listing_id`, `title`, `price`, `area`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `seller_type`.
- Xử lý JS-rendered pages và anti-bot bằng headless browser; retry với proxy rotation khi gặp block.
- Hỗ trợ phân trang, `max_pages`/`max_items`, rate limit 1s/proxy.
- Trả về `degraded=true` khi gặp CAPTCHA, layout thay đổi, hoặc block; không hard-fail.
- Billing per listing qua `CHOTOT_BDS_ITEM`; expose qua REST, agent, MCP.

**Kỹ thuật:** thêm `app/proprietary/platforms/chotot/` (BSL 1.1) cho fetcher/parser và `app/capabilities/chotot/scrape/` (Apache-2.0) cho capability/executor/definition, theo pattern `reddit.scrape`.

_FR-6 · AD-3 · AD-16 · AD-19 · `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`._

### Story 10.3: Muaban.net BĐS Scraper  `[done]`

As a real-estate researcher or investor in Vietnam,  
I want to scrape property listings from `muaban.net` (mục BĐS),  
So that I can broaden cross-compare coverage beyond batdongsan and chotot.

**Acceptance Criteria:**
- Scrape public listing pages từ `muaban.net` mục `nha-dat` (bán/cho thuê, căn hộ, nhà riêng, đất).
- Trả về danh sách listing đã typed: `listing_id`, `title`, `price`, `area`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `seller_type`.
- Xử lý phân trang dạng sub-category + region; reuse pattern anti-bot từ chotot nếu có.
- Hỗ trợ `max_pages`/`max_items`, rate limit 1s/proxy.
- Trả về `degraded=true` khi gặp block, layout thay đổi, hoặc decode lỗi; không hard-fail.
- Billing per listing qua `MUABAN_BDS_ITEM`; expose qua REST, agent, MCP.

**Kỹ thuật:** thêm `app/proprietary/platforms/muaban/` (BSL 1.1) cho fetcher/parser và `app/capabilities/muaban/scrape/` (Apache-2.0) cho capability/executor/definition.

_FR-6 · AD-3 · AD-16 · AD-19 · `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`._

### Story 10.4: Vietnam BĐS Listing Aggregator & Cross-Source Trust Score  `[backlog]`

As a real-estate researcher,  
I want the system to merge and score listings from multiple Vietnamese BĐS sources,  
So that I can trust the price and detect fake/duplicate listings.

**Acceptance Criteria:**
- Normalize listings từ `batdongsan`, `chotot`, `muaban` (và tương lai P1/P2 sources) vào schema chung.
- Tính `confidence_score` dựa trên nguồn xác thực, số nguồn trùng, `post_date`, và độ tương đồng giá.
- Flag conflict khi cùng địa chỉ/title nhưng giá khác >20%.
- Deduplicate theo phone, địa chỉ chuẩn hóa, hoặc image hash.
- Expose qua REST/MCP với query theo location, price range, source filter.

**Kỹ thuật:** thêm `app/services/bds_aggregator/` hoặc mở rộng `Memory`/`ResearchThread` để lưu aggregated listing với provenance.

_FR-6 · FR-32 · FR-39 · AD-11.1 · `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`._

---

## Epic 11: Telegram Automation & Bot `[done]`

_Tạo 2026-08-03 để mở rộng gateway Telegram hiện có thành automation notification channel, write-back action, và bot tương tác._

**FRs:** FR-TELE-1 (automation run notification), FR-TELE-2 (notification preference), FR-TELE-3 (`write_back_telegram`), FR-TELE-4 (inline keyboard), FR-TELE-5 (bot commands), FR-TELE-6 (UI builder + settings), FR-TELE-7 (rate limit & error handling). **NFRs:** NFR-TELE-1 (async), NFR-TELE-2 (rate limit), NFR-TELE-3 (token encryption), NFR-TELE-4 (4096-char limit), NFR-TELE-5 (webhook/longpoll). **Governed by:** `AD-15` (gateway là shared dependency), `AD-16` (license), `AD-19` (anti-bot/escalation async).

> **🆕 2026-08-03 — Epic 11** là epic *mới thật* dựa trên request PO; reuse `app/gateway/telegram/` đã có (`TelegramClient`, `TelegramAdapter`, `TelegramStreamTranslator`, `TelegramGatewayCommands`). Không xây gateway từ đầu. Crypto `market_data` pending sau Telegram.

### Story 11.1: Telegram Notification Foundation `[done]`

As a user,
I want to enable or disable Telegram notifications for automation runs and receive a clear message with a deep link when a run completes or fails,
So that I can control whether Nowing messages me on Telegram and quickly review results without keeping the dashboard open.

**Acceptance Criteria:**
- Toggle visible in User Settings only when the user has an active `ExternalChatBinding` for Telegram.
- Turning the toggle on/off persists immediately; off stops future Telegram notifications but still creates an in-app notification.
- When `AutomationRun` reaches `succeeded`/`failed`, create `Notification` type `automation_run_complete`.
- If the user has an active Telegram binding and preference is enabled, send a Telegram message within 30 seconds.
- If no binding or preference is off, only in-app notification is created.
- Message chunked/truncated to fit Telegram 4096 UTF-16 units; `RetryAfter` handled; delivery failure does not fail the automation run.
- Success messages start with `✅ Automation '<name>' finished successfully`; failure messages start with `❌ Automation '<name>' failed` and include the first error line.
- Markdown formatting: bold automation name, status highlight, deep link to `/dashboard/{workspace_id}/automations/{automation_id}/runs/{run_id}`.
- Long messages split into multiple parts, with summary and link in the first part.

**Kỹ thuật:** Alembic migration thêm `notification_preferences` JSONB vào `User` (hoặc bảng riêng) (`AD-2`); endpoint `PATCH /api/v1/users/me/notification-preferences`; UI toggle trong `MessagingChannelsContent`; hook vào `app/automations/runtime/executor.py` sau `mark_succeeded`/`mark_failed`; dispatch gửi Telegram qua Celery task; reuse `NotificationService` + `TelegramAdapter` + `chunk_message` và rate-limit.

### Story 11.2: Telegram Write-Back, Builder UI & Chat Resolution `[done]`

As an automation builder,
I want a "Send Telegram message" action that authors a custom message and automatically resolves the right bot and chat,
So that I can push results or alerts to Telegram without writing JSON or looking up chat IDs.

**Acceptance Criteria:**
- Action `write_back_telegram` registered with params `text`, optional `chat_id`, `parse_mode` (default `Markdown`), `reply_markup`, `account_id`, `use_system_bot` (default `true`).
- Resolve bot token: explicit `account_id` BYO → system bot if `use_system_bot=true` → fail otherwise.
- Resolve default `chat_id` from the automation creator's active `ExternalChatBinding` for the resolved account; fail if absent and `chat_id` missing.
- Invalid Markdown / malformed `reply_markup` falls back to plain text / no keyboard.
- Missing token or chat fails the step with a clear error; run continues based on `on_failure` config.
- Builder action list shows "Send Telegram message" with fields text, chat ID hint, parse mode; serializes as `write_back_telegram`/`writeBackParams` provider `telegram`.

**Kỹ thuật:** package `app/automations/actions/builtin/write_back_telegram/` (`definition.py`, `params.py`, `factory.py`, `invoke.py`); reuse `TelegramAdapter`; mở rộng `nowing_web/lib/automations/builder-schema.ts` và `app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`.

### Story 11.3: Telegram Interactive Bot & Commands `[done]`

As a Telegram user,
I want inline keyboards and `/status`, `/run` commands so I can view runs and trigger automations directly from the chat,
So that I can take action without opening the dashboard.

**Acceptance Criteria:**
- `TelegramClient.send_message` and `edit_message` accept `reply_markup` dict with `inline_keyboard`; `url` opens URL, `callback_data` triggers `callback_query`.
- Invalid `reply_markup` falls back to message without keyboard and logs a warning.
- `TelegramAdapter.parse_inbound` recognizes `callback_query` and `inline_message_id`.
- Callback persisted and dispatched by `inbox_processor`.
- `view_run:` callback fetches run details and edits/sends message.
- `rerun:` callback triggers automation and confirms.
- Bot calls `answerCallbackQuery` to remove loading spinner.
- `/status` checks `Permission.AUTOMATIONS_READ` and returns latest run or "No recent runs".
- `/run <name>` checks `Permission.AUTOMATIONS_EXECUTE`, triggers automation, replies "Run started...".
- Missing name lists available automations; non-existent automation replies "Automation '<name>' not found".
- Respect workspace visibility/permissions and unpaired onboarding.

**Kỹ thuật:** `TelegramClient` methods `answer_callback_query`, `edit_message_reply_markup`; `TelegramAdapter.edit_message` handles `inline:` peer prefix; `inbox_processor` callback dispatch; `app/gateway/telegram/commands.py` handlers; transient `AutomationTrigger(type=MANUAL)` + `launch_run`.

---

## Ghi chú
- **Mồ côi/defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default enable/disable) → backlog.
- **RS-9** ("project memory" của team = `ResearchThread`?) → resolve trong scope 3.9/3.7.
- Story `[DONE]` không liệt kê AC (đã implement); chỉ story `[GAP]`/`(mới)` có AC để dev thực thi.
