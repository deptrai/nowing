---
stepsCompleted: ['step-01-document-discovery', 'step-02-prd-analysis', 'step-03-epic-coverage-validation', 'step-04-ux-alignment', 'step-05-epic-quality-review', 'step-06-final-assessment']
readinessStatus: 'NEEDS WORK (phân theo tuyến: merge-to-prod READY · Epic 9 NEEDS WORK · public repo NOT READY · launch NOT READY)'
issuesFound: 29  # 28 từ 6 step + L-1 (phát hiện 2026-07-25 NGOÀI phạm vi 6 step, khi thiết lập versioning artifact)
publicRepoGates:
  gate-1: '9-1a — FR-38 research degradation + self-host độc lập (backlog)'
  gate-2: 'L-1 — attribution của fork SurfSense chưa xử lý (MỚI 2026-07-25, cần luật sư). Chủ: action item AI-2026-07-25-7 (Founder + Legal, P0). Độc lập với gate-1, chạy song song được'
criticalIssues: ['L-1 Nowing là FORK của SurfSense — app/proprietary/ 87% byte-identical, attribution bị THAY không phải bổ sung, AD-16 gọi sai là tự xây, D5 bán BSL như moat trên code không tự viết => CỔNG THỨ HAI trước public repo', 'Q-1 Epic 9 là technical epic', 'Q-2 Story 9.6 có quyết định architecture trong AC', 'P-4/C-2 onboarding seeding không có ở PRD lẫn epics', 'C-A/C-B/U-4 ba tài liệu báo GAP cho việc đã build', 'C-C Epic 8 xung đột số hiệu story', 'U-1/U-3 NFR-9 State A không có AD + engine chỉ emit 2 progress event']
codeVerifiedFindings: ['FR-18 đã build (write_back_notion/slack/linear/jira)', 'FR-35 đã build (memory_change trigger + continue_research action)', 'NFR-6 đã build (editorPanelAtom có chunkId)', 'runs KHÔNG có trong ZERO_PUBLICATION', 'chainlens executor chỉ emit starting/done', 'Memory.source_id Integer vs Run.id UUID']
remediationProgress:
  nhom-1-lech-tai-lieu: 'ĐÓNG 2026-07-25'
  nhom-2-critical-va-epic-quality: 'ĐÓNG 2026-07-25 (Q-1…Q-5, Q-7, C-C, C-D, U-1, U-2 + OQ-7 gửi ChainLens)'
  nhom-3-gap-that: 'ĐÓNG 2026-07-25 — FR-40 + 3-13 (P-4/C-2) · NFR-1a-1d + AD-18 + 3-14 (C-1/P-5) · UX contract 1 viết + 2 hoãn có trigger (item 16)'
  nhom-4-cosmetic: 'ĐÓNG 2026-07-25 — P-6 (OQ sắp 1→7; phát hiện OQ-4 + OQ-5 ĐÃ BUILD, PRD còn ghi GAP) · C-F (rename 2 file ở 2 thư mục + 6 tham chiếu). CẢ HAI đều KHÔNG cosmetic như phân loại ban đầu'
remediationComplete: true  # Nhóm 1, 2, 3, 4 đã đóng 2026-07-25. Còn lại là việc thi công, không phải việc tài liệu.
nhom3CodeVerifiedFindings:
  - 'HAI đường recall, PRD chỉ mô tả một: MemoryInjectionMiddleware.abefore_agent CHẶN mọi lượt chat, SELECT không LIMIT, bỏ qua cả ix_memories_embedding (HNSW) và ix_memories_content_search (GIN) đã có sẵn'
  - 'MEMORY_HARD_LIMIT=25000 chỉ validate MỘT content ở đường GHI (validate_memory_size) => aggregate N fact KHÔNG có chặn trên; phanh duy nhất là <memory_warning> ở 18000 phụ thuộc LLM tự consolidate'
  - 'CẢI CHÍNH P-5: auto-extract KHÔNG cộng latency mỗi turn — caller duy nhất là memory_extraction_task.py (Celery, ngoài request)'
  - 'CẢI CHÍNH U-3: ChainLens CÓ emit progress (api.ts:414/1298/221/1299); lỗi là _parse_sse của Nowing bỏ 6 event (progress, insufficientEvidence, partial, synthesizing, heartbeat, noop) => OQ-7 Q4 đã RÚT'
  - 'MemoryExtractionService CHỈ có extract_from_turn; workspace mới không seed gì => nowing_recall session đầu rỗng theo CẤU TRÚC, M1 không tồn tại'
  - 'MemorySourceType.SCRAPER_RUN (db.py:572) khai báo nhưng KHÔNG có writer — FR-40 là writer đó'
  - 'Hook đo đã CÓ: _perf_log "[memory_injection] ... db=%.3fs total=%.3fs" => 3-14 là chốt ngân sách + cắt + assert, không phải dựng instrumentation'
assessedDocuments:
  prd: '_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md'
  architecture: '_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md'
  epics: '_bmad-output/planning-artifacts/epics.md'
  ux: '_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md'  # tạo 2026-07-25 (Nhóm 3 item 16); lúc đánh giá là null. Phủ hạng mục UX ĐANG CHẶN (9-3); 2 hạng mục còn lại hoãn có trigger
  sprintStatus: '_bmad-output/implementation-artifacts/sprint-status.yaml'
supportingDocuments:
  - '_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md'
  - '_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md'
  - '_bmad-output/planning-artifacts/prfaq-Nowing-distillate.md'
  - '_bmad-output/implementation-artifacts/merge-to-prod-checklist.md'
  - '_bmad-output/implementation-artifacts/deferred-work.md'
priorReport: '_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-24.md'
---

# Implementation Readiness Assessment Report

**Date:** 2026-07-25
**Project:** Nowing

**Bối cảnh trigger:** artifact vừa qua một lượt thay đổi lớn cùng ngày — SCP `chainlens-engine-boundary` (D1–D5) thêm **Epic 9** với 6 story mới, thêm **FR-37/38/39** + **NFR-9**, thêm **AD-15/AD-16/AD-DEFER-7** và amend AD-1/AD-3/AD-8/AD-11. Đây là lượt validate trước khi tạo story file cho Epic 9.

---

## Step 1 — Document Discovery

### Kiểm kê

| Loại | Dạng | Đường dẫn | Kích thước | Sửa lần cuối |
|---|---|---|---|---|
| **PRD** | folder (1 file chính) | `prds/prd-Nowing-2026-07-22/prd.md` | ~78 KB | 2026-07-25 |
| **Architecture** | folder (1 file chính) | `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | ~40 KB | 2026-07-25 |
| **Epics** | whole | `epics.md` | 42.3 KB | 2026-07-25 22:17 |
| **UX** | folder **RỖNG** | `ux-designs/ux-Nowing-2026-07-22/` | **0 file** | — |
| **Sprint status** | yaml | `implementation-artifacts/sprint-status.yaml` | — | 2026-07-25 |
| **Story files** | 11 file | `implementation-artifacts/*.md` | — | — |

**Tài liệu phụ trợ của PRD** (cùng folder, không phải PRD trùng lặp): `.memlog.md`, `review-prfaq-gap.md`, `review-rubric.md`, `validation-report.md`.

### ✅ Không có trùng lặp

Mỗi loại tài liệu chỉ tồn tại **một** dạng. Không có trường hợp vừa whole vừa sharded → không cần giải quyết xung đột.

### ⚠️ Vấn đề phát hiện ở bước discovery

**D1 — UX artifact rỗng hoàn toàn (0 file).**
`ux-designs/ux-Nowing-2026-07-22/` chỉ có hai thư mục rỗng (`.working/`, `imports/`). Bước 4 (UX Alignment) sẽ không có gì để đối chiếu. Đây không phải lỗi discovery mà là gap thật, vì hiện có **ba** hạng mục phụ thuộc UI:
- **NFR-9 State A** — deep research cần pattern async/progress-first (brief đã ghi là tiền đề)
- **Story 3.6** — citation jump-to-source trong full editor
- **Story 8.3** — usage & credit dashboard

**D2 — Phát hiện hai artifact vận hành không nằm trong danh sách chuẩn, nhưng chi phối readiness:**
- **`implementation-artifacts/merge-to-prod-checklist.md`** (2026-07-25) — checklist merge `develop` → `production` với **5 pre-merge gate G1–G5**. Quan trọng: **prod đang ở `alembic 174`, `develop` ở `179`** → toàn bộ memory layer **chưa live**. Sprint-status `done` = code-complete trên `develop`, **không phải** đã live prod. Sẽ đưa vào đánh giá.
- **`implementation-artifacts/deferred-work.md`** — ledger cross-story các vấn đề hoãn từ code review (có mục IDOR, non-idempotent extraction, memory poisoning).

**D3 — Lệch trạng thái giữa hai nguồn (cần xác nhận):**
`merge-to-prod-checklist.md` ghi *"2 story chưa xong (4-6 ready-for-dev, 6-5 backlog)"*, nhưng `sprint-status.yaml` ghi **cả hai đều `done`**. Hai tài liệu cùng ngày 2026-07-25. Cần chốt nguồn chân lý trước khi đánh giá coverage.

**D4 — Story file cho Epic 9: chưa có cái nào.** 6 story (`9-1`…`9-6`) đều ở `backlog`, không có file. Bình thường với trạng thái backlog, nhưng có nghĩa Step 5 (Epic Quality Review) sẽ đánh giá **spec trong `epics.md`**, không phải story file.

### Không thiếu tài liệu bắt buộc nào

PRD ✅ · Architecture ✅ · Epics ✅ · UX ⚠️ *(tồn tại nhưng rỗng — xử lý ở Step 4)*

---

## Step 2 — PRD Analysis

**Nguồn:** `prds/prd-Nowing-2026-07-22/prd.md` — 817 dòng / 75 KB, đọc toàn bộ. Không có file sharded nào bị bỏ qua (folder chỉ chứa 1 PRD + 4 tài liệu phụ trợ: `.memlog.md`, `review-prfaq-gap.md`, `review-rubric.md`, `validation-report.md`).

### Functional Requirements — 39 FR, đánh số FR-1 … FR-39, KHÔNG có lỗ

| Section | FR | Trạng thái |
|---|---|---|
**§4.1** Identity/Auth/RBAC | FR-1 User Authentication · FR-2 API Access for External Clients · FR-3 Workspace Lifecycle · FR-4 Workspace Invites & Memberships · FR-10 RBAC ba system roles | shipped *(FR-10 kèm `[REMOVED]` Admin role — mig 72)* |
**§4.2** Connectors | FR-6 Built-in Scraper Connectors · FR-7 External OAuth Connectors · FR-8 External MCP Connectors | shipped |
**§4.3** Knowledge Base & Memory | FR-9 Document Upload/Parse/Index · FR-11 Folders & Document Management · FR-12 Hybrid Search · FR-13 Citation Panel | shipped |
| | FR-32 Long-Term Research Memory | `[BUILT]` schema/endpoints/tools · `[PARTIAL]` dedupe + recall-quality |
| | FR-33 Research Continuity | `[BUILT]` · `[PARTIAL]` chất lượng recall phụ thuộc NFR-8 |
| | FR-34 Memory Correction | `[BUILT]` · `[GAP]` propagate qua relation graph (post-MVP) |
| | FR-36 Legacy Memory Data-Loss | **`[RESOLVED 2026-07-25]`** không mất dữ liệu |
| | FR-5 AI File Sorting | **`[REMOVED]`** mig 172 |
**§4.4** Chat & Agents | FR-14 Chat Threads & Messages · FR-15 Multi-agent Runtime with Tools · FR-16 Real-time Collaborative Chat · FR-17 Anonymous Chat with Quota | shipped *(FR-15 kèm `[PARTIAL]` auto-recall ngầm cần verify)* |
**§4.5** Deliverables | FR-21 Report Generation & Export · FR-22 Podcast & Video Presentation · FR-23 Image Generation | shipped |
**§4.6** Automations | FR-19 Automation Triggers · FR-20 Automation Runs & Retries | shipped |
| | FR-18 Automation Action Types | `[PARTIAL]` — chỉ `agent_task`; `[GAP]` direct write-back |
| | FR-35 Memory-Driven Automations | `[GAP]` post-MVP |
**§4.7** Multi-surface Clients | FR-25 Web · FR-26 Desktop · FR-27 Browser Extension · FR-28 Obsidian · FR-29 MCP Server | shipped |
**§4.8** Billing/Credits | FR-30 Token Usage Tracking | shipped |
| | FR-31 Credit Wallet & Purchases | `[PARTIAL]` — `[GAP]` usage/credit dashboard |
**§4.9** Deep-Research Engine *(mới 2026-07-25)* | FR-24 Deep Open-Web Research via ChainLens Engine | `[PARTIAL]` đã wire, thiếu contract-guard + mode default |
| | FR-37 Deep-Research Cost Metering | `[GAP]` P0 — under-meter 2.1–3.3× |
| | FR-38 Research Degradation & Self-Host Independence | `[GAP]` **P0 — tiền đề trước public repo** |
| | FR-39 Memory→Scraper-Run Provenance & Re-Validation | `[GAP]` defect schema |

**Tổng: 39 FR.** Shipped 27 · `[BUILT/PARTIAL]` 3 · `[PARTIAL]` 3 · `[GAP]` 4 · `[RESOLVED]` 1 · `[REMOVED]` 1.

### Non-Functional Requirements — 9 NFR, NFR-1 … NFR-9, không có lỗ

| NFR | Nội dung | Trạng thái |
|---|---|---|
**NFR-1** | Performance — API CRUD < 500ms; hybrid search pgvector có limit | `[PARTIAL]` bounds mơ hồ |
**NFR-2** | Security & Auth — JWT/cookie + PAT; permission check mọi workspace-scoped endpoint; secrets qua `.env` | satisfied |
**NFR-3** | Observability — OpenTelemetry trace, `Log` model, SlowAPI rate limiter, Celery monitoring | satisfied |
**NFR-4** | Reliability — async DB I/O, Celery+Redis, retry policy | satisfied |
**NFR-5** | Multi-tenancy Isolation — mọi query lọc `workspace_id`; `api_access_enabled` | satisfied |
**NFR-6** | Citation Full-Editor Highlight | `[GAP]` + PRD tự ghi `[NOTE]` đây là feature-gap, không phải NFR |
**NFR-7** | Usage & Credit Dashboard | `[GAP]` + PRD tự ghi `[NOTE]` trùng FR-31 |
**NFR-8** | Recall Quality (eval-gated) — **điều kiện TRƯỚC-SHIP** | `[PARTIAL — in review]` story `3-9` |
**NFR-9** | Deep-Research Latency & Availability Budget (State A/B) *(mới)* | `[GAP]` story `9.3` |

### Additional Requirements & ràng buộc khác

- **Non-Goals (§2.4, 🔒 frozen tới 2026-08-24):** NG-1 không bán research data / không owned index · NG-2 không parity consumer kiểu Perplexity · NG-3 ChainLens không thành sản phẩm độc lập · NG-4 non-users cũ.
- **Hoãn có điều kiện (§6.2):** `[STATE B]` deep research sync chat-mode · `[PHASE 2]` metered endpoint cho self-host · `[LOẠI]` binary closed-source.
- **Success Metrics:** SM-1…SM-11 (SM-11a/b/c) + counter-metrics SM-C1/SM-C2.
- **Open Questions:** OQ-1, OQ-2, OQ-3 (retention/legal — chốt trước GA cloud), OQ-4, OQ-5, OQ-6 `[PARTIAL]`, OQ-7 (3 câu hỏi ChainLens đang chờ — chặn `42-1`/`42-3`).
- **Assumptions Index:** 16 mục, gồm 3 `[CORRECTED 2026-07-25]` và 1 `[RESOLVED 2026-07-25]`.
- **Ranh giới license ba tầng (§1.1, D5):** Apache-2.0 core · BSL 1.1 `app/proprietary/**` · closed-source hosted deep-research engine.

### PRD Completeness Assessment

**✅ Mạnh**
- **Đánh số FR/NFR liền mạch, không lỗ** (FR-1…39, NFR-1…9) — traceability hygiene tốt, dễ map sang epic.
- **Mọi FR `[GAP]`/`[PARTIAL]` đều có bằng chứng code kèm đường dẫn + số dòng.** Đây là mức chứng cứ cao hơn hầu hết PRD.
- **Phân biệt rõ non-goal vĩnh viễn vs hoãn có điều kiện** (§6.2) — chống re-litigate.
- **Assumptions có lịch sử** (`[CORRECTED]`/`[RESOLVED]` giữ nguyên bản gạch bỏ) — người đọc sau thấy được vì sao đổi ý.

**⚠️ Vấn đề phát hiện (đưa vào đánh giá cuối)**

| # | Vấn đề | Mức |
|---|---|---|
**P-1** | **§6.1 In Scope còn dòng stale:** vẫn liệt kê *"đánh giá mất dữ liệu legacy (FR-36)"* là việc **còn lại (open)** — nhưng FR-36 đã `[RESOLVED]` ở §4.3. Nội bộ tài liệu tự mâu thuẫn | Medium |
**P-2** | **NFR-8 Gap text nói story `3-9` = `review`**, nhưng `sprint-status.yaml` hiện là **`in-progress`** (đã lùi lại). PRD stale so với nguồn chân lý tiến độ | Medium |
**P-3** | **NFR-6 và NFR-7 bị phân loại sai — và PRD tự thừa nhận** bằng `[NOTE]`. NFR-7 còn trùng nội dung với `[GAP]` FR-31. Đã tự flag từ trước nhưng chưa ai giải quyết | Low-Medium |
**P-4** | **Thiếu requirement cho onboarding seeding.** `briefs/brief-Nowing-2026-07-25/brief.md` §9 xác định: không seed nội dung thì `nowing_recall` ở session đầu trả rỗng → người dùng kết luận sản phẩm không chạy, bỏ đi trước khi tới giá trị thật ở session 2. **Không có FR/NFR nào phủ việc này** (brief gọi là H-4) | **High** — ảnh hưởng trực tiếp adoption |
**P-5** | **NFR-1 không phủ memory operations.** Chỉ nói "API CRUD < 500ms". Không có bound nào cho `recall` (nằm trên đường agent) hay cho auto-extract (cộng latency **mỗi turn**, default ON). Với một sản phẩm mà recall là lõi, đây là lỗ NFR đáng kể | Medium-High |
**P-6** | **Thứ tự OQ bị đảo:** OQ-1, 2, 3, **6, 7**, 4, 5. OQ-6/OQ-7 chèn trước OQ-4/OQ-5 | ~~Cosmetic~~ → ✅ **ĐÓNG 2026-07-25 — và KHÔNG cosmetic.** Thứ tự nay 1→7. Nhưng lý do OQ-4/OQ-5 nằm cuối là **bị append rồi không ai quay lại**, nên nội dung đã stale: **cả hai đã BUILD**. OQ-4 → `workspace_mcp_tool_settings` (`db.py:1945`, `uq_workspace_mcp_tool`), story `2-5` = done. OQ-5 → 4 action type `write_back_notion/slack/linear/jira`, story `6-4` = done ⇒ câu hỏi "action type riêng vs `agent_task`" **code đã trả lời: action type riêng**. Cùng lớp với C-A/C-B/U-4 ở Nhóm 1 |
**P-7** | **SM-3 và SM-8 còn "≥ X%"** chưa định lượng. Đây là **hoãn có chủ đích** (D4) và đã ghi rõ trong `[NOTE]` — ghi nhận là *accepted deferral*, không tính là defect | Accepted |

---

## Step 3 — Epic Coverage Validation

**Nguồn:** `epics.md` — 485 dòng, đọc toàn bộ. Có section `### FR Coverage Map` tường minh + 22 story header.

### Coverage Matrix — FR

| FR | Epic / Story | Trạng thái trong epics | Khớp PRD? |
|---|---|---|---|
FR-1, 2, 3, 4, 10 | **E1** | [DONE] | ✅ |
FR-6, 7, 8 | **E2** | [DONE] | ✅ |
FR-9, 11, 12, 13 | **E3** | [DONE] | ✅ |
FR-14, 15, 16, 17 | **E4** | [DONE] | ✅ |
FR-21, 22, 23 | **E5** | [DONE] | ✅ |
FR-19, 20 | **E6** | [DONE] | ✅ |
FR-25, 26, 27, 28, 29 | **E7** | [DONE] | ✅ |
FR-30 | **E8** | [DONE] | ✅ |
FR-32 | E3 (3.8 done → quality 3.9, dedupe 3.11) | [BUILT/PARTIAL] | ✅ |
FR-33 | E4 (4.6) | [DONE] | ✅ |
FR-34 | E3/E4 | [DONE] | ✅ |
FR-36 | **E3.10a/b** | [RESOLVED] | ✅ |
FR-18 | **E6.4** | [DONE] | ⚠️ **PRD nói `[GAP]`** — xem C-A |
FR-31 | **E8.3** | [DONE] | ✅ |
FR-35 | **E6.5** | [GAP, post-MVP] | ⚠️ **code đã có** — xem C-B |
FR-24 | **E9.1** | [PARTIAL] | ✅ |
FR-37 | **E9.2** | [GAP, P0] | ✅ |
FR-38 | **E9.1** | [GAP, P0, tiền đề trước public repo] | ✅ |
FR-39 | **E9.6** | [GAP, defect schema] | ✅ |
FR-5 | — | [REMOVED] | ✅ |

### Coverage Statistics

- **Tổng FR trong PRD: 39**
- **FR có đường triển khai trong epics: 39**
- **Coverage: 100%** — ✅ **không FR nào rơi qua kẽ**
- NFR có epic: **4/9** (NFR-6→E3.6 · NFR-7→E8.3 · NFR-8→E3.9 · NFR-9→E9.3)
- Story trong epics không map về FR nào: **0 orphan** — tất cả đều trace về AR-1…AR-10, RS-*, OQ-*, hoặc D5

### Missing Coverage

#### C-1 — `[MEDIUM]` NFR-1…NFR-5 không có mặt trong FR Coverage Map
Bốn NFR *satisfied* (NFR-2/3/4/5) bỏ qua được vì là cross-cutting đã đạt. Nhưng **NFR-1 Performance được đánh `[PARTIAL]` ("bounds mơ hồ") trong Requirements Inventory của chính `epics.md`, mà không có epic/story nào nhận nó.** Một requirement `[PARTIAL]` không có đường triển khai = việc sẽ không bao giờ được làm.

Cộng với **P-5** (NFR-1 không phủ memory operations): `recall` nằm trên đường agent và auto-extract cộng latency **mỗi turn** với default ON, nhưng không có bound nào.

**Đề nghị:** hoặc gán NFR-1 vào một story trong Epic 8 (observability đã có → thêm latency budget cho `recall`/`extract`), hoặc tuyên bố tường minh là accepted deferral.

#### C-2 — `[HIGH]` H-4 (onboarding seeding) không có ở CẢ PRD lẫn epics
Đã ghi ở **P-4**. Đây là gap kép: không có FR nên cũng không có epic. `brief` §9 kết luận không seed thì `nowing_recall` session đầu trả rỗng → user bỏ đi trước khi tới giá trị thật. **Không tài liệu nào chịu trách nhiệm cho việc này.**

### Bất nhất truy vết — 6 phát hiện

> Đây là phần giá trị chính của Step 3. FR coverage đạt 100%, nhưng **trạng thái** thì lệch giữa các tài liệu, và mình đã verify bằng code để phân xử.

#### C-A — `[HIGH]` PRD FR-18 stale: direct write-back actions ĐÃ ĐƯỢC BUILD
PRD §4.6 FR-18 vẫn viết *"Direct write-back actions (Notion, Slack, Linear, Jira) chưa được implement dưới dạng action type riêng"* và `app/automations/actions/builtin/__init__.py` *"chỉ import agent_task"*. **Sai.** Code thực tế:
```
app/automations/actions/builtin/ →
  agent_task/  continue_research/  write_back/
  write_back_jira/  write_back_linear/  write_back_notion/  write_back_slack/
```
`epics.md` coverage map ghi đúng (`FR-18 → E6.4 [DONE]`); **PRD là bên stale.** §6.2 cũng còn `[GAP] Direct Notion/Slack/Linear/Jira write-back actions`.

#### C-B — `[HIGH]` FR-35 stale ở BA tài liệu: memory-driven automations ĐÃ ĐƯỢC BUILD
PRD FR-35 `[GAP]` · epics Story 6.5 `[GAP, post-MVP]` · epics coverage map `[GAP,post-MVP]` · `merge-to-prod-checklist.md` "6-5 backlog". **Cả bốn đều sai.** Code:
```
app/automations/triggers/builtin/memory_change/   ← params.py + selector.py (docstring tham chiếu AC-2)
app/automations/actions/builtin/continue_research/
```
`sprint-status.yaml` (`6-5: done`) là bên **đúng**. ⇒ Kết luận D3 ở Step 1 được phân xử: **sprint-status.yaml là nguồn chân lý; `merge-to-prod-checklist.md` stale.**

#### C-C — `[HIGH]` Epic 8: xung đột số hiệu story giữa `epics.md` và `sprint-status.yaml`
Ba số nghĩa khác nhau ở hai tài liệu:

| Số | `epics.md` | `sprint-status.yaml` | |
|---|---|---|---|
8.3 / `8-3` | Usage & Credit Dashboard | usage-credit-dashboard | ✅ khớp |
**8.4a / `8-4`** | Auto-Extract Kill-Switch & Safe Default | **observability-logging** | ❌ |
**8.5 / `8-5`** | Memory Cost/Turn Observability | **security-permissions** | ❌ |
**8.6 / `8-6`** | Docs / README / Vision Sync | **multi-tenant-isolation** | ❌ |
8.7 / `8-7` | Auto-Extract Spend Cap | auto-extract-spend-budget-cap | ✅ khớp |

`epics.md` tự biết và cross-reference thủ công (*Story 8.5 `[DONE — sprint 8-4 observability-logging]`*, *Story 3.12 `[DONE — sprint 8-5 security]`*), nhưng đó là cách chống đỡ mong manh: **chạy `bmad-create-story` cho "8.6" sẽ lấy sai việc.**

#### C-D — `[MEDIUM]` Story trong `epics.md` không có entry trong `sprint-status.yaml`
`3.11` Memory Dedupe · `3.12` Memory Security · `8.4a` Auto-Extract Kill-Switch · `8.5` Memory Cost Observability · `8.6` Docs/Vision Sync.
Cả năm được `epics.md` đánh DONE bằng cách trỏ sang story sprint **khác**. Hệ quả: chúng **không xuất hiện trong bất kỳ báo cáo tiến độ nào**, và `8.6` (docs sync) đang là việc thật chưa làm mà không được track.

#### C-E — `[MEDIUM]` Story 3.9 có BA trạng thái khác nhau
`epics.md` header `[GAP — SHIP-GATE]` · `epics.md` coverage map `[PARTIAL — review]` · `sprint-status.yaml` `in-progress`. Đây là **cổng chặn launch** (NFR-8) nên trạng thái mơ hồ là rủi ro thật, không phải chuyện hình thức.

#### C-F — `[LOW]` Naming không nhất quán ở story file — ✅ **ĐÓNG 2026-07-25**
`3.8-long-term-research-memory.md` dùng **dấu chấm**; mọi file khác dùng **gạch ngang** (`3-10a-…`, `8-7-…`). Sẽ làm lệch mọi script khớp theo pattern.

**Đã xử lý.** Lệch này **rộng hơn** mức finding mô tả — nó có ở **hai** thư mục, không phải một:
- `implementation-artifacts/3.8-…md` → `3-8-…md` *(11 file khác trong thư mục này đã dùng gạch ngang)*
- `test-artifacts/atdd-checklist-3.8-…md` → `atdd-checklist-3-8-…md` *(10 file ATDD khác đã dùng gạch ngang)*

Cộng **6 tham chiếu** trong 4 file phải sửa theo, nếu không rename sẽ làm hỏng link: `story_key` frontmatter · `storyKey`/`storyFile`/`atddChecklistPath` trong ATDD checklist · 2 chỗ "Previous story" ở `4-5-agent-memory-tools-via-mcp.md` · 3 chỗ ở `test-artifacts/test-design-progress.md`.

⇒ Toàn repo giờ **không còn** file artifact nào dùng `<số>.<số>` trong tên. Dòng mô tả ở trên giữ nguyên làm lịch sử.

---

## Step 4 — UX Alignment Assessment

### UX Document Status: ❌ **NOT FOUND**

`ux-designs/ux-Nowing-2026-07-22/` tồn tại nhưng chứa **0 file** — chỉ hai thư mục rỗng `.working/` và `imports/`. Không có UX artifact nào để đối chiếu.

### UX có được hàm ý không? — **CÓ, rất mạnh**

Đây không phải backend service. PRD định nghĩa **năm bề mặt client**:

| FR | Bề mặt | UI |
|---|---|---|
FR-25 | Web (Next.js 16) — landing, dashboard, chat, connectors, settings, docs | ✅ |
FR-26 | Desktop (Electron 42) — global shortcut, quick assist, screenshot assist | ✅ |
FR-27 | Browser Extension (Plasmo) | ✅ |
FR-28 | Obsidian Plugin | ✅ |
FR-29 | MCP Server | — (không UI) |

Cộng các hạng mục UI tường minh: **FR-13** citation panel (`citation-panel.tsx`, chunk window ±5, highlight, auto-scroll) · **NFR-6** citation jump-to-source · **NFR-7** usage & credit dashboard · **NFR-9 State A** async/progress-first · **§6.2** UI memory browser / research timeline.

⇒ **`[WARNING]` Ứng dụng user-facing với 5 client surface, không có một dòng UX spec nào.**

### UX ↔ Architecture Alignment

**Architecture CÓ hỗ trợ tầng client** — không phải gap: `AD-5` Zero sync cho real-time state · `AD-6` Next.js server proxy · capability map có dòng cho web/desktop/extension/obsidian · Stack ghi Next.js 16, React 19, Tailwind v4, Jotai/Zustand, Tanstack Query, Plate.js, Electron 42, Plasmo.

Vấn đề không phải "architecture thiếu UI" mà là **không có UX spec để validate architecture ngược lại**. Bốn chỗ cụ thể:

#### U-1 — `[HIGH]` NFR-9 State A không có architecture decision nào đỡ
NFR-9 buộc Nowing có đường **async deliverable** (submit → progress → notify → deliverable). **Không AD nào định nghĩa flow này.** `AD-15` chỉ nói về dependency engine.

Các mảnh rời **đã tồn tại** nhưng chưa được ghép bằng một quyết định:

| Mảnh | Trạng thái code |
|---|---|
progress | ✅ `emit_progress` (`capabilities/core/progress.py`) có 3 mode: REST async door → **SSE live per run bus channel**; REST sync + agent door → buffer vào `runs.progress` + `scraper_progress` event trên thinking step; ngoài run → no-op |
notify | ✅ `notifications` **có** trong `ZERO_PUBLICATION` |
deliverable | ⚠️ model deliverable có (`Report`/`Podcast`/…) nhưng deep-research result hiện **trả về caller**, không persist thành deliverable |
submit (fire-and-forget) | ❌ executor gọi **đồng bộ** trong một capability call với timeout 300s |

⇒ Story `9.3` sẽ phải **tự phát minh** flow này lúc dev. Đây đúng loại quyết định nên chốt ở architecture trước, không phải trong story.

#### U-2 — `[MEDIUM]` `runs` không nằm trong Zero publication
`ZERO_PUBLICATION` (`app/zero_publication.py:81-94`) gồm: `notifications`, `documents`, `folders`, `search_source_connectors`, `new_chat_threads`, `new_chat_messages`, `chat_comments`, `chat_session_state`, `user`, `automations`, **`automation_runs`**, `podcasts`.

**Không có `runs`.** Deep research tạo một `Run` (capability `chainlens.research`), nên `runs.progress` **không được real-time sync** về web. Có đường SSE cho "REST async door", nhưng không có đường Zero. Với UX progress-first của State A, đây là quyết định phải chốt: mở Zero cho `runs`, hay đi SSE, hay polling.

#### U-3 — `[HIGH]` Chainlens executor chỉ emit **2** progress event → UX progress-first không có gì để hiển thị
`executor.py:189` emit `"starting"`, `executor.py:206` emit `"done"`. Giữa hai mốc đó **không có event nào**, trong khi thao tác có thể mất tới 300s (timeout mặc định).

⇒ Một UI "progress-first" sẽ hiện *"Researching…"* rồi **đứng im vài phút**. Đó là chính xác trải nghiệm mà State A ra đời để tránh. Cần engine emit phase trung gian (classifier → planner → researcher → writer → reflection), tức **phụ thuộc ChainLens** — và điều này **chưa có trong OQ-7** (3 câu hỏi gửi ChainLens hiện không hỏi về progress event granularity).

#### U-4 — `[MEDIUM]` `AD-DEFER-1` STALE — và đây là bất nhất 4 chiều
Architecture `AD-DEFER-1` nêu lý do hoãn: *"`editorPanelAtom` không có trường `chunkId` hay highlight state"*. **Đã sai.** Code:
- `nowing_web/atoms/editor/editor-panel.atom.ts` — `chunkId: number | null` (dòng 12, 23, 38, 64, 79, 93)
- `components/editor-panel/editor-panel.tsx` + `components/editor/plugins/citation-kit.tsx` có logic dùng `chunkId`

Bốn tài liệu nói bốn kiểu về cùng một việc:

| Nguồn | Nói gì |
|---|---|
`ARCHITECTURE-SPINE` `AD-DEFER-1` | **DEFERRED** — lý do đã lỗi thời |
PRD `NFR-6` | **`[GAP]`** |
`epics.md` coverage map | **`[DONE]`** |
`sprint-status.yaml` `3-6` | **`done`** |

Code phân xử: **đã xong**. ⇒ Cần đóng `AD-DEFER-1` và sửa PRD NFR-6.

### Warnings

1. **`[WARNING]` UX artifact rỗng trong khi có 5 client surface.** Ba hạng mục UI đang cần spec trước khi build: **NFR-9 State A** (async/progress-first — chặn story `9.3`), **UI memory browser / research timeline** (§6.2), và **usage dashboard** (`8.3` đánh done — cần verify UI thật hay chỉ API).
2. **`[WARNING]` Không có accessibility requirement nào** trong toàn bộ PRD/NFR. Với sản phẩm OSS hướng developer trên 5 bề mặt, đây là lỗ trống đáng ghi — không phải blocker MVP, nhưng nên là quyết định tường minh chứ không phải bỏ sót.
3. **`[NOTE]` U-3 phát sinh một câu hỏi mới cho ChainLens** chưa nằm trong OQ-7: engine có thể emit progress event theo phase (classifier/planner/researcher/writer/reflection) không? Nếu không thì State A không có nội dung progress để hiển thị. Nên gộp vào bản trả lời OQ-7.

---

## Step 5 — Epic Quality Review

Áp chuẩn `create-epics-and-stories` không nhượng bộ, **bao gồm cả Epic 9 do phiên `bmad-correct-course` cùng ngày tạo ra**.

### A. Epic Structure — User Value Focus

| Epic | Tiêu đề | User value? |
|---|---|---|
E1 | Identity, Auth & Workspace RBAC | 🟡 borderline — auth thường được miễn, nhưng tiêu đề vẫn là tên hệ thống |
E2 | Connectors | ✅ user kết nối được nguồn dữ liệu |
E3 | Knowledge Base + Long-Term Memory | ✅ |
E4 | Chat & Agents | ✅ |
E5 | Deliverables | ✅ |
E6 | Automations | ✅ |
E7 | Multi-surface Clients | ✅ |
E8 | **Platform Operations (Billing/Usage/Token)** | 🟠 **framing kỹ thuật/ops** — "Platform Operations" không nói user làm được gì |
E9 | **Deep-Research Engine Integration (ChainLens)** | 🔴 **epic kỹ thuật** — xem Q-1 |

### 🔴 Critical Violations

#### Q-1 — Epic 9 là một **technical epic**, vi phạm chuẩn "epic phải deliver user value"
Tiêu đề *"Deep-Research Engine Integration (ChainLens)"* và epic goal *"Quản trị ChainLens như external deep-research dependency hạng nhất: contract ổn định, cost thật, degradation an toàn, latency budget trung thực"* — **cả hai đều mô tả hạ tầng, không mô tả điều user làm được.** Đúng dạng red-flag mà chuẩn liệt kê ("API Development", "Infrastructure Setup").

Nghịch lý: **các story bên trong LẠI có user value thật** — `9.1` "Nowing dùng được không cần engine", `9.3` "deep research không block chat turn". Vấn đề nằm ở **framing epic**, không ở nội dung.

**Đề nghị:** đổi tên Epic 9 thành hướng người dùng, ví dụ **"Deep Research đáng tin cậy và tính phí đúng"** hoặc **"Deep Research: dùng được, đo được, không vỡ"**. Giữ nguyên story. Đây là sửa 1 dòng, và nó quan trọng vì tên epic là thứ team đọc mỗi ngày.

*(Tự phê: lỗi này do mình tạo ra ở phiên correct-course — mình đặt tên epic theo boundary kiến trúc thay vì theo giá trị người dùng.)*

#### Q-2 — Story 9.6 có **quyết định kiến trúc chưa chốt nằm trong AC** → AC không testable
AC ghi: *"`Run` **không bị xoá** khi còn `Memory` tham chiếu — **hoặc** `Memory` tự sao `capability` + `input` để độc lập với retention. **Chọn một**, ghi rõ trong ADR."*

Một AC không thể chứa "chọn một trong hai". Dev không biết verify cái gì; QA không biết test cái gì. Đây là **quyết định architecture bị đẩy xuống story**.

**Đề nghị:** chốt phương án trong `AD-11` **trước** khi tạo story file. Khuyến nghị **sao `capability` + `input` vào `Memory`** — nó làm memory độc lập với `RUNS_RETENTION_DAYS`, không cần retention có điều kiện (phức tạp hơn và dễ rò rỉ), và khớp nguyên tắc "memory là first-class persistence layer" của AD-11.

### 🟠 Major Issues

#### Q-3 — Story 9.1 gộp **hai concern khác nhau** vào một story
Story chứa: (a) **contract regression test** — bảo vệ Nowing khỏi việc ChainLens đổi format; (b) **degradation** — bảo vệ mô hình kinh doanh self-host. Khác nhau về mục đích, khác nhau về rủi ro, khác nhau về file, test được độc lập.

Hệ quả thực tế: `9.1` là **tiền đề chặn public repo** — nhưng chỉ phần (b) mới thật sự chặn. Gộp lại nghĩa là public repo bị chặn bởi cả phần (a) vốn không cần chặn.

**Đề nghị:** tách `9.1a` Degradation & Self-Host Independence *(chặn public repo)* và `9.1b` Contract Regression Guard *(P0 nhưng không chặn)*.

#### Q-4 — Story 9.6 quá lớn: 4 việc riêng biệt
(1) migration source ref · (2) writer set `SCRAPER_RUN` trong extraction · (3) quyết định + thực thi retention · (4) API `revalidate(memory_id)`. Việc (4) là một feature riêng, và nó phụ thuộc (1)+(2)+(3).

**Đề nghị:** tách `9.6a` provenance link (1+2+3) và `9.6b` re-validation API (4).

#### Q-5 — Story 9.3 có AC tự tham chiếu
AC ghi *"**Then** định nghĩa **ngưỡng p95 cụ thể** + cổng chuyển A→B"*. AC yêu cầu story tự định nghĩa tiêu chí nghiệm thu của chính nó → không verify được cho tới khi story hoàn thành. Vòng tròn.

**Đề nghị:** tách phần "đặt ngưỡng" thành một **spike/decision** riêng (hoặc đưa vào 9.3 như một deliverable *tài liệu*, không phải AC), rồi AC còn lại mới đo được. Lưu ý: kỷ luật "không đặt ngưỡng trước khi đo" là **đúng** — vấn đề chỉ là nó không nên nằm ở dạng AC.

#### Q-6 — Story 9.5 có AC nháp nhưng đã ở `backlog` trong sprint-status
Story tự ghi *"AC (nháp — cần SCP phê duyệt trước khi dev)"* và `[POST-MVP — CHƯA PHÊ DUYỆT]`, nhưng `sprint-status.yaml` ghi `9-5-…: backlog`. Trong định nghĩa status của chính file đó, `backlog` = *"Epic/story not yet started"* — hàm ý sẵn sàng để nhặt. Không có trạng thái nào diễn tả "chưa được phê duyệt".

**Đề nghị:** thêm comment `# CHƯA PHÊ DUYỆT — không nhặt` (đã có) **và** cân nhắc không đưa vào `development_status` cho tới khi có SCP; hoặc đề xuất một status `deferred` cho tracking system.

### 🟡 Minor Concerns

- **Q-7** — Epic 8 framing ops ("Platform Operations"). Cân nhắc đổi thành hướng user, ví dụ *"Người dùng thấy và kiểm soát được chi phí"*.
- **Q-8** — Story `[DONE]` không có AC. `epics.md` tự ghi quy ước này (*"Story [DONE] không liệt kê AC (đã implement)"*). Hợp lý cho brownfield retro-doc, **nhưng** nó khiến không thể audit ngược "story đã done có đạt AC gì" — và đúng chỗ này vừa sinh ra ba bất nhất C-A/C-B/U-4.
- **Q-9** — Story numbering trong Epic 3 dùng cả `3.10a`/`3.10b` (chữ cái) và Epic 8 dùng `8.4a`. Không nhất quán với phần còn lại; cộng với C-C (xung đột số hiệu) làm tracking dễ sai.

### B. Epic Independence — ✅ PASS

| Kiểm tra | Kết quả |
|---|---|
E9 phụ thuộc E3 (`app/retriever/` cho degradation fallback) | ✅ epic **trước** — hợp lệ |
E9 phụ thuộc E8 (`TokenUsage`/wallet cho cost metering) | ✅ epic **trước** — hợp lệ |
E9.6 phụ thuộc memory layer E3 | ✅ epic trước |
E9.5 phụ thuộc E9.2 | ✅ story trước trong cùng epic |
E9.4 phụ thuộc E9.1 (hành vi Phase 1 để viết docs) | ✅ story trước |
**Forward dependency nào không?** | ✅ **không tìm thấy** — không epic nào cần epic sau, không story nào cần story sau |

**Phụ thuộc ngoài (không phải forward dependency, nhưng phải track):** `9.2` chờ ChainLens `42-1` (costDollars) · `9.3` State B chờ ChainLens `43-1`→`43-2`+`43-5` · `9.1`/`9.2` chờ **OQ-7** được trả lời. Cả ba đều ghi tường minh trong story ✅ — nhưng **không có cái nào xuất hiện trong `sprint-status.yaml`**, nên chúng vô hình với báo cáo tiến độ.

### C. Database/Entity Creation Timing — ✅ PASS

Migration được tạo **khi story cần**, không dồn lên trước: `9.6` tự tạo migration cho source ref của `memories`; `3.8` tạo bảng memory; `8.7` không cần schema mới. Không có anti-pattern "Epic 1 Story 1 tạo hết bảng".

### D. Starter Template & Brownfield — ✅ PASS

`epics.md` ghi rõ *"Starter template: **KHÔNG — brownfield**"*, khớp `ARCHITECTURE-SPINE` Structural Seed (mô tả cây thư mục **đã tồn tại**). Có đủ chỉ dấu brownfield: story migration (`3.10a/b`), integration point với hệ thống ngoài (`9.1`–`9.4`), tương thích ngược (`FR-39` AC *"không hồi quy memory nguồn document/chat_message"*).

### E. Best Practices Compliance Checklist

| Tiêu chí | E1–E8 | E9 |
|---|---|---|
Epic deliver user value | 🟡 E8 framing ops | 🔴 **Q-1** technical epic |
Epic độc lập được | ✅ | ✅ |
Story sizing hợp lý | ✅ | 🟠 **Q-3** (9.1 gộp 2 concern) · **Q-4** (9.6 gộp 4 việc) |
Không forward dependency | ✅ | ✅ |
Bảng tạo khi cần | ✅ | ✅ |
AC rõ ràng, testable | 🟡 **Q-8** story DONE không có AC | 🔴 **Q-2** (9.6 chứa quyết định) · 🟠 **Q-5** (9.3 tự tham chiếu) |
Traceability tới FR | ✅ 100% coverage | ✅ |

---

## Summary and Recommendations

### Overall Readiness Status: 🟠 **NEEDS WORK** — nhưng có phân biệt quan trọng

Không phải một verdict chung. Trạng thái khác nhau theo từng tuyến việc:

| Tuyến việc | Trạng thái | Ghi chú |
|---|---|---|
**Merge memory layer lên prod** (`3-9`, `8-7`) | 🟢 **READY** | Có story file, có `merge-to-prod-checklist.md` với G1–G5. Không bị chặn bởi phát hiện nào ở lượt này |
**Epic 9 — tạo story file & dev** | 🟠 **NEEDS WORK** | 2 critical (Q-1, Q-2) + 4 major phải xử trước khi `bmad-create-story` |
**Public repo** | 🔴 **NOT READY** | ~~`9.1` chưa làm; và UX/onboarding gap (P-4, C-2) chưa có chủ~~ → `9-1a` chưa làm (cổng 1) · **và CỔNG 2 MỚI: attribution của fork SurfSense chưa xử lý — xem `L-1` bên dưới**. P-4/C-2 đã có chủ (FR-40 + `3-13`) nên không còn chặn cổng này |
**Launch / công bố** | 🔴 **NOT READY** | `3-9` eval gate chưa đóng (NFR-8) |

**Điểm mạnh cần ghi nhận:** **FR coverage 100% (39/39)**, không forward dependency, không orphan story, đánh số FR/NFR liền mạch, mọi `[GAP]` đều có bằng chứng code kèm đường dẫn + số dòng. Đây là mức traceability trên trung bình rõ rệt. Vấn đề của dự án **không phải** thiếu spec — mà là **spec bị lệch trạng thái so với code**.

### Phát hiện quan trọng nhất của lượt này

> **Ba tài liệu đang báo `[GAP]` cho việc đã được BUILD.** Verify bằng code:
>
> - **C-A** — PRD FR-18: *"direct write-back actions chưa implement"* → code có `write_back_notion/slack/linear/jira` là action type riêng
> - **C-B** — PRD FR-35 + epics Story 6.5 + `merge-to-prod-checklist`: *"chưa có `memory_change` trigger và `continue_research` action"* → code có **cả hai**
> - **U-4** — `AD-DEFER-1`: *"`editorPanelAtom` không có `chunkId`"* → code có (`editor-panel.atom.ts:12`)
>
> Đây là **loại lỗi tốn kém nhất**: team sẽ lập kế hoạch làm lại thứ đã có, hoặc mất niềm tin vào tài liệu rồi bỏ đọc. Và nó lý giải vì sao `sprint-status.yaml` phải là nguồn chân lý tiến độ — nó là bên **đúng** trong cả ba trường hợp.

### Critical Issues Requiring Immediate Action

| # | Vấn đề | Chặn cái gì |
|---|---|---|
**Q-1** | Epic 9 là technical epic — tên/goal mô tả hạ tầng, không mô tả user value | Chất lượng epic; sửa 1 dòng |
**Q-2** | Story 9.6 có quyết định architecture *bên trong* AC ("chọn một, ghi trong ADR") → AC không testable | `bmad-create-story` cho 9.6 |
**P-4 / C-2** | **Onboarding seeding không có ở CẢ PRD lẫn epics.** Không seed → `nowing_recall` session đầu trả rỗng → user bỏ đi trước khi tới giá trị thật ở session 2 | Adoption. Không tài liệu nào chịu trách nhiệm |
**C-A / C-B / U-4** | Ba tài liệu báo `[GAP]` cho việc đã build | Kế hoạch sai + mất niềm tin vào tài liệu |
**C-C** | Epic 8 xung đột số hiệu story giữa `epics.md` và `sprint-status.yaml` (8.4a/8.5/8.6 ≠ 8-4/8-5/8-6) | `bmad-create-story` sẽ lấy sai việc |
**U-1 / U-3** | NFR-9 State A không có AD nào đỡ; và engine chỉ emit **2** progress event ("starting"/"done") cho thao tác tới 300s → UX progress-first không có gì hiển thị | Story `9.3` |

### Recommended Next Steps

**Nhóm 1 — Sửa lệch tài liệu (30 phút, không chặn ai, giá trị cao nhất)**
1. PRD **FR-18** → `[DONE]`; xoá dòng `[GAP]` write-back ở §6.2.
2. PRD **FR-35** → `[DONE]`; epics Story 6.5 + coverage map → `[DONE]`; xoá `[GAP]` memory-driven automations ở §6.2.
3. PRD **NFR-6** → `[DONE]`; đóng **`AD-DEFER-1`** trong `ARCHITECTURE-SPINE` (lý do đã lỗi thời).
4. PRD §6.1 bỏ dòng stale *"đánh giá mất dữ liệu legacy (FR-36)"* (**P-1**); NFR-8 sửa `review` → `in-progress` (**P-2**).
5. `merge-to-prod-checklist.md` sửa mục "4-6 ready-for-dev / 6-5 backlog" → cả hai `done` (**C-D**).

**Nhóm 2 — Sửa trước khi tạo story file cho Epic 9**
6. Đổi tên **Epic 9** theo hướng user value (**Q-1**).
7. Chốt quyết định retention trong **`AD-11`** rồi mới viết `9.6` (**Q-2**). *Khuyến nghị: sao `capability` + `input` vào `Memory`* — độc lập với `RUNS_RETENTION_DAYS`, đơn giản hơn retention có điều kiện.
8. Tách **`9.1`** → `9.1a` degradation *(chặn public repo)* + `9.1b` contract guard *(P0, không chặn)* (**Q-3**).
9. Tách **`9.6`** → `9.6a` provenance link + `9.6b` re-validation API (**Q-4**).
10. Sửa AC tự tham chiếu của **`9.3`** (**Q-5**).
11. Giải quyết **C-C** — đổi số hiệu Epic 8 để hai tài liệu khớp nhau (khuyến nghị: đánh lại `epics.md` theo `sprint-status.yaml` vì nó là nguồn chân lý), và thêm entry cho 5 story đang không được track (**C-D**).

**Nhóm 3 — Gap thật cần chủ sở hữu** — ✅ **ĐÓNG 2026-07-25**
12. ~~**Thêm requirement onboarding seeding** vào PRD (**P-4**) + story tương ứng.~~ → ✅ **FR-40** + story **`3-13`**. Xem §Nhóm 3 bên dưới.
13. ~~**Gán NFR-1 cho một story**; bổ sung bound cho `recall` và auto-extract (**C-1**, **P-5**).~~ → ✅ **NFR-1 viết lại thành NFR-1a / NFR-1b / NFR-1c / NFR-1d** + **`AD-18`** + story **`3-14`**. ⚠️ Một tiền đề của P-5 **đã được cải chính** — xem bên dưới.
14. ~~**Viết AD cho async deliverable flow** (**U-1**/**U-2**).~~ → ✅ đã đóng ở **Nhóm 2** (`AD-17`).
15. ~~**Bổ sung câu hỏi thứ 4 vào OQ-7**.~~ → ✅ **RÚT** — engine đã emit progress; lỗi ở parser Nowing. Xem cải chính **U-3**.
16. ~~**Tạo UX spec tối thiểu** cho ba hạng mục UI.~~ → ✅ **1 viết / 2 hoãn tường minh**: `ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md`.

---

### 🔻 Nhóm 3 — kết quả chi tiết (2026-07-25)

Cả ba hạng mục đều được **verify bằng code trước khi quyết**, và việc verify **đổi kết luận** ở hai chỗ.

#### 12 · P-4 / C-2 — onboarding seeding → **FR-40** + `3-13`

**Verify:** `MemoryExtractionService` chỉ có **`extract_from_turn`** (`app/services/memory/extraction.py:118`). Không có đường extract từ scrape run / deep research / document. `grep seed|sample|onboarding|welcome|starter|template app/routes/workspaces_routes.py` = **rỗng**; `scripts/` không có seed script.

⇒ **`nowing_recall` session đầu rỗng theo CẤU TRÚC, không phải bug.** M1 (first-run value ≤15 phút) **không tồn tại**. Và câu headline của brief — *"it remembers what it went and found, not just what you told it"* — **chỉ đúng nửa sau**; nửa `what it went and found` **chưa có writer nào**.

**Quyết định: research run sinh memory. KHÔNG seed dữ liệu mẫu.**

| Phương án | Phán quyết | Lý do |
|---|---|---|
| Research run → memory | ✅ **CHỌN** | Chứng minh đúng differentiator; recall có nội dung sau **một** hành động |
| Seed sample workspace | ❌ | Memory giả dạy sai mental model; và đổ rác vào đường inject **chưa có chặn trên** (phát hiện ở #13) |
| Onboarding tour thuần UI | ❌ | Không tạo memory ⇒ recall **vẫn** rỗng |

Đóng thêm **hai** thứ ngoài P-4: `MemorySourceType.SCRAPER_RUN` (`app/db.py:572`) **có writer** lần đầu, và headline brief thành đúng.

#### 13 · C-1 / P-5 — NFR-1 → **NFR-1a/1b/1c/1d** + **`AD-18`** + `3-14`

**Phát hiện lớn nhất của Nhóm 3: có HAI đường recall, PRD chỉ mô tả một.**

| Đường | Code | Chặn lượt chat? | Dùng index? | LIMIT? | Trong PRD? |
|---|---|---|---|---|---|
| Memory injection | `MemoryInjectionMiddleware.abefore_agent` | ✅ **mọi lượt** | ❌ | ❌ | ❌ |
| Recall tool | `nowing_recall` · `/memories/search` | chỉ khi agent gọi | ✅ | ✅ ≤5 | ✅ FR-32 |

Đường nóng chạy `SELECT * FROM memories WHERE workspace_id=? ORDER BY created_at` **không LIMIT**, **bỏ qua cả hai index chuyên dụng đã có sẵn** (`ix_memories_embedding` HNSW + `ix_memories_content_search` GIN), rồi render toàn bộ vào prompt. `Memory` là store **fact-level** (docstring: *"A single, embedded long-term memory fact"*), **không** unique constraint trên `workspace_id` ⇒ **N tăng vô hạn**.

`MEMORY_HARD_LIMIT = 25.000` chỉ validate **một** `content` ở đường **ghi** ⇒ aggregate N fact **chưa từng bị kiểm tra**. Phanh duy nhất là `<memory_warning>` ở `MEMORY_SOFT_LIMIT = 18.000` nhờ LLM tự consolidate — **một vòng lặp phụ thuộc LLM hợp tác**, và nó **không thể thắng** `extract_from_turn` (Celery) vốn ghi row nhanh hơn LLM dọn.

⇒ **Chi phí mỗi lượt chat tăng tuyến tính theo mức người dùng dùng sản phẩm nhiều.** Im lặng, không lỗi.

> **⚠️ Cải chính P-5.** P-5 ghi *"auto-extract cộng latency **mỗi turn**"*. **Sai.** Caller duy nhất của `extract_from_turn` là `app/tasks/celery_tasks/memory_extraction_task.py` → **Celery, ngoài request** ⇒ **không** trên critical path. Nửa còn lại của P-5 (thiếu bound cho recall) **đúng**, và **nặng hơn** mức P-5 đánh giá.

**Tin tốt về phạm vi:** hook đo **đã tồn tại** — `_perf_log.info("[memory_injection] scope=%s injected=%d db=%.3fs total=%.3fs")`. `3-14` là **chốt ngân sách + cắt ở đường đọc + assert**, không phải dựng instrumentation.

**Thứ tự mới phát sinh:** `3-14` **nên chạy trước khi chốt số SM-10** của `3-9` (`AD-18` rule 6) — baseline recall quality đo trên lượng inject phụ thuộc N thì không tái lập được. Và `3-14` **đi kèm** `3-13`, vì `3-13` làm N tăng nhanh hơn.

#### 16 · UX — 1 viết / 2 hoãn tường minh

`ux-designs/ux-Nowing-2026-07-22/` xác nhận **0 file**. Chỉ **một** trong ba hạng mục có story đang chờ ⇒ viết một, hoãn hai **có trigger**.

| Hạng mục | Xử lý | Trigger mở lại |
|---|---|---|
| Async deep-research progress-first | ✅ `ux-contract-async-deep-research.md` — 10 trạng thái bắt buộc (S1–S10) + 3 rule | — (chặn `9-3`) |
| Memory browser / research timeline | ⏸️ Hoãn | `3-14` + `3-13` done — chưa chốt top-k thì chưa biết browser hiển thị **cái gì** |
| Usage dashboard | ⏸️ Hoãn | `9-2` (FR-37) có số cost thật — rủi ro là **số đang sai**, không phải thiếu design |

Cả hai hạng mục hoãn đều **phụ thuộc quyết định kỹ thuật chưa chốt**; vẽ bây giờ tạo artifact phải bỏ. **Không chặn launch gate nào.**

> **⚠️ Cải chính U-3.** U-3 ghi *"engine chỉ emit 2 progress event ⇒ UX progress-first không có gì hiển thị"*. **Sai** — ChainLens **có** emit progress (`apps/api/src/search/api.ts:414`, `:1298`, `:221`, `:1299`). Nowing `_parse_sse` chỉ dispatch `error`/`done`/`block`/`updateBlock`, **bỏ 6 event**: `progress`, `insufficientEvidence`, `partial`, `synthesizing`, `heartbeat`, `noop`. ⇒ Nguyên liệu **đã có**; cần sửa parser (`9-1b`), không cần xin engine. Đây là lý do **OQ-7 Q4 đã RÚT**.

**Artifact Nhóm 3 đã sửa:** `prd.md` (NFR-1 viết lại, FR-40 mới) · `ARCHITECTURE-SPINE.md` (`AD-18`) · `epics.md` (Story 3.13, 3.14) · `sprint-status.yaml` (`3-13`, `3-14` = backlog, parse OK) · `ux-contract-async-deep-research.md` (mới).

**Nhóm 4 — Nhỏ**
17. ~~Sắp lại thứ tự OQ (**P-6**); đổi tên file `3.8-…` → `3-8-…` (**C-F**); cân nhắc đổi framing Epic 8 (**Q-7**).~~ → ✅ **ĐÓNG 2026-07-25.** Q-7 đã đóng ở Nhóm 2. **Cả hai việc "cosmetic" đều hoá ra không cosmetic** — xem §Nhóm 4 bên dưới.

---

### 🔻 Nhóm 4 — kết quả chi tiết (2026-07-25)

Cả hai finding được xếp `[LOW]`/`Cosmetic`. Khi thực sự sửa, **cả hai đều lớn hơn mô tả** — theo hai kiểu khác nhau.

#### 17a · P-6 — sắp thứ tự OQ → phát hiện **hai OQ đã stale**

Thứ tự nay **1 → 7** (trước: 1, 2, 3, **6, 7**, 4, 5).

Nhưng *vì sao* OQ-4/OQ-5 nằm cuối mới là điều đáng kể: chúng bị **append rồi không ai quay lại**, nên nội dung đứng yên trong khi code đi tiếp. **Cả hai đã build:**

| OQ | PRD ghi | Thực tế trong code | Story |
|---|---|---|---|
| **OQ-4** per-workspace MCP tool toggle | `[GAP]` *"Chưa có cơ chế… MCP server hiện expose toàn bộ tools cho mọi workspace"* | Bảng **`workspace_mcp_tool_settings`** (`app/db.py:1945`) — `(workspace_id, tool_name, enabled)` + unique `uq_workspace_mcp_tool` (`:1950`) + relationship (`:1919`, `:1965`) | **`2-5` = done** |
| **OQ-5** write-back action architecture | Câu hỏi để ngỏ: *"action type riêng hay `agent_task`?"* | **Code đã chọn: action type riêng** — `write_back_notion`, `write_back_slack`, `write_back_linear`, `write_back_jira` | **`6-4` = done** |

`epics.md` coverage map đã tag `OQ-4 → E2.5 [DONE]` từ trước ⇒ **chỉ PRD còn sót**. Đây **cùng lớp** với C-A/C-B/U-4 ở Nhóm 1 (tài liệu báo GAP cho việc đã build), nên P-6 lẽ ra không nên bị xếp `Cosmetic`.

**Hai thứ kéo theo:**
- `[ASSUMPTION]` §9 *"MCP server không cần per-workspace tool toggle trong v1"* → **`[SUPERSEDED]`**. Nó bị **vượt qua**, không phải bị bác bỏ: chọn workspace (`nowing_select_workspace`) và bật/tắt từng tool là hai việc khác nhau, và cái thứ hai hoá ra vẫn cần.
- **Thêm cảnh báo chống đóng nhầm OQ-2.** OQ-2 và OQ-4 đọc gần như giống hệt nhau nhưng **khác bề mặt**: OQ-4 = **MCP tools**, lưu **DB** ✅ resolved · OQ-2 = **agent tools** (chat UI), lưu **localStorage** (`nowing_web/atoms/agent-tools/agent-tools.atoms.ts`) 🟠 vẫn mở. Và nội dung thật của OQ-2 được làm rõ hơn: localStorage **đã** key theo `workspaceId` ⇒ "per-workspace" **không** phải phần thiếu; phần thiếu là nó **không chia sẻ được** (mỗi user mỗi browser một bản, owner không đặt default cho team, xoá browser data là mất).

#### 17b · C-F — rename file → lệch ở **hai** thư mục, kéo **6 tham chiếu**

Finding chỉ nêu một file. Thực tế cùng một lệch có ở hai nơi:
- `implementation-artifacts/3.8-…md` → **`3-8-…md`** *(11 file khác đã dùng gạch ngang)*
- `test-artifacts/atdd-checklist-3.8-…md` → **`atdd-checklist-3-8-…md`** *(10 file ATDD khác đã dùng gạch ngang)*

Và **6 tham chiếu** phải sửa theo, nếu không rename sẽ **làm hỏng link**: `story_key` frontmatter · `storyKey`/`storyFile`/`atddChecklistPath` trong ATDD checklist · 2 chỗ "Previous story" ở `4-5-agent-memory-tools-via-mcp.md` · 3 chỗ ở `test-artifacts/test-design-progress.md`.

⇒ Toàn repo **không còn** file artifact nào dùng `<số>.<số>` trong tên.

**Artifact Nhóm 4 đã sửa:** `prd.md` (OQ sắp 1→7, OQ-4/OQ-5 RESOLVED, OQ-2 disambiguation, `[ASSUMPTION]`→`[SUPERSEDED]`) · `epics.md` (OQ-5 → E6.4 tag `[DONE]`) · rename 2 file + 6 tham chiếu trong 4 file.

### Accepted Deferrals — không tính là defect

- **SM-3 / SM-8 còn "≥ X%"** và target SM-11 chưa đặt số — hoãn có chủ đích theo **D4**, đợi version cuối của engine deep-research. Đã ghi rõ trong PRD `[NOTE]`.
- **Story 9.5** (Phase 2 metered endpoint) — đăng ký để không mất, chưa phê duyệt.
- **State B** (deep research sync chat-mode) — mở khoá theo điều kiện đã ghi ở NFR-9.
- **Story `[DONE]` không có AC** — quy ước brownfield retro-doc (**Q-8**), có ghi rõ.

### Final Note

Lượt đánh giá này tìm ra **28 vấn đề** trên **5 nhóm**: PRD completeness (P-1…P-7), coverage & traceability (C-1, C-2, C-A…C-F), UX alignment (U-1…U-4), epic quality (Q-1…Q-9).

**Hai critical (Q-1, Q-2) và cụm lệch tài liệu (C-A/C-B/U-4) nên xử trước khi chạy `bmad-create-story` cho Epic 9.** Nhóm 1 mất khoảng 30 phút và không chặn ai — nên làm trước.

Ba việc **không** bị chặn bởi báo cáo này và có thể chạy song song ngay: đóng `3-9` (eval gate), dev `8-7` (spend cap), và trả lời **OQ-7** cho team ChainLens (đang chặn `42-1`/`42-3` của họ).

---

### 🔴 L-1 — `[CRITICAL]` Nowing là FORK của SurfSense; attribution chưa xử lý → **CỔNG THỨ HAI trước public repo**

**Phát hiện 2026-07-25, ngoài phạm vi 6 step của lượt đánh giá này** — nó lộ ra khi thiết lập versioning cho artifact, không phải khi đọc tài liệu. Đó chính là điểm đáng chú ý: **không step nào của readiness check có thể bắt được nó**, vì cả 6 step đều so sánh tài liệu với tài liệu, mà mọi tài liệu đều nhất quán trong việc **không nhắc tới fork**.

`git remote -v` → `upstream = https://github.com/MODSetter/SurfSense.git` (tại tag `0.0.34.1`, commit `bea603e22`).

#### Đo bằng git, không suy đoán

So `nowing_backend/app/proprietary/` với `upstream/main:surfsense_backend/app/proprietary/`:

| Phép đo | Kết quả |
|---|---|
| Số file `.py` | **84 vs 84** |
| Đường dẫn trùng | **84 / 84 (100%)** |
| **Giống hệt byte-for-byte** | **73 / 84 (87%)** |
| File khác biệt | 11 — mỗi file **2–4 dòng** |
| Tổng dòng khác | **~26 / ~16.600 (0,16%)** |
| **26 dòng đó là gì** | **chỉ đổi chuỗi `SurfSense` → `Nowing`** (comment, docstring, `name = "surfsense_site"` → `"nowing_site"`). **Không thay đổi chức năng nào** |

Hai file license cũng vậy — attribution bị **thay**, không phải bổ sung: root `LICENSE` `Copyright (c) SurfSense` → `Copyright (c) Nowing`; BSL `Licensor: SurfSense` → `Licensor: Nowing`; `Licensed Work is (c) 2026 SurfSense` → `(c) 2026 Nowing`. `Change Date`, `Change License`, `Additional Use Grant` **giống hệt**. **Không có `NOTICE`**, README **không credit** SurfSense.

#### Vì sao đây là CRITICAL, không phải chuyện giấy tờ

1. **Tiền đề của `AD-16` sai.** AD-16 mô tả `app/proprietary/` là *"crawler engine **tự xây**"*. Sai về thực tế. Đã cải chính bằng **`AD-16.1`** và sửa câu sai inline.
2. **Lập luận thương mại của `D5` bị ảnh hưởng.** D5 và brief bán BSL 1.1 như **"moat"** và **"điểm bán"**. Moat đó là **99,84% code Nowing không viết**. Lập luận "bảo vệ crawler engine tự xây" **không đứng được** ở dạng hiện tại.
3. **Nowing tự đặt mình làm BSL `Licensor`** trên khối code kế thừa.
4. **Thời điểm sai nhất có thể.** `D5` dự định public repo, và `9-1a` đang được coi là **cổng duy nhất**. Public repo là lúc attribution bị soi kỹ nhất.

#### ⇒ Cổng thứ hai trước public repo

| | Cổng | Trạng thái |
|---|---|---|
| **Cổng 1** | `9-1a` — FR-38 degradation + self-host độc lập | `backlog` |
| **Cổng 2** | **`L-1` — attribution của fork được luật sư xem xét và xử lý** | **MỚI** — đã có chủ: `AI-2026-07-25-7` (`Founder + Legal`, P0, `blocks: public-repo`) |

Hai cổng **độc lập**, chạy song song được. `L-1` không cần chờ `9-1a`.

**Rule hiệu lực ngay:** không tài liệu nào được gọi `app/proprietary/` là *"tự xây" / "self-built" / "our own crawler engine"* cho tới khi có kết luận — áp cho PRD, brief, README, và mọi marketing copy.

**Câu hỏi cần luật sư — báo cáo này KHÔNG kết luận thay:** (a) Apache-2.0 §4 yêu cầu giữ attribution tới mức nào, và **thay** dòng copyright có thoả không; (b) Nowing có quyền đặt mình làm **BSL Licensor** cho code kế thừa không, và BSL gốc của SurfSense ràng buộc gì; (c) cần `NOTICE` + credit dạng nào.

**Nếu kết luận pháp lý đòi sửa code hoặc đổi cấu trúc license** (ví dụ phải trả lại attribution trong header 84 file, hoặc xem lại BSL Licensor) thì `L-1` **phải nâng thành story**, không còn là action item.

**Tái lập:** `git remote -v` · `git show upstream/main:LICENSE` · `git show upstream/main:surfsense_backend/app/proprietary/LICENSE` · so `git hash-object` từng file với `git rev-parse upstream/main:<path>`.

---

### Cập nhật sau remediation — 2026-07-25

**Cả bốn nhóm remediation đã đóng.** Không còn việc tài liệu nào tồn đọng từ báo cáo này.

Việc verify code ở Nhóm 3 **cải chính hai finding** của chính báo cáo này — cả hai theo hướng *báo cáo đã chẩn đoán sai nguyên nhân*:

- **P-5** cho rằng auto-extract cộng latency mỗi turn → **không**, nó chạy trên Celery. Nhưng lỗ thật (memory injection unbounded trên critical path) **nặng hơn** mức P-5 mô tả.
- **U-3** cho rằng engine không emit đủ progress → **không**, engine emit đủ; parser Nowing bỏ 6 event. OQ-7 Q4 đã **rút** khỏi danh sách gửi ChainLens.

**Hai story mới sinh ra từ Nhóm 3, và chúng đổi thứ tự thi công:**
- `3-13` (FR-40, first-run value) — gap sản phẩm nghiêm trọng nhất của lượt đánh giá, giờ đã có chủ.
- `3-14` (`AD-18`, bounded injection) — **đi kèm `3-13`**, và **nên chạy trước khi chốt số SM-10 của `3-9`**. Đây là ràng buộc thứ tự **mới**, chưa có trong báo cáo gốc: `3-9` hiện `in-progress` và đang bị chặn ở việc đo baseline; đo baseline trên lượng inject phụ thuộc N sẽ cho số không tái lập được.

**Việc tiếp theo:** `bmad-create-story` cho `9-1a` (**cổng 1** trước public repo) · và giao chủ cho **`L-1`** (**cổng 2**, cần luật sư — độc lập, chạy song song). Remediation tài liệu **đã xong cả 4 nhóm**.

**Một nhận xét về chính lượt đánh giá này.** Bảy finding bị phân loại quá nhẹ, và mọi trường hợp đều lệch cùng một hướng — **đánh giá thấp**, không có trường hợp nào đánh giá cao. `P-5` và `U-3` chẩn đoán **sai nguyên nhân** (đúng triệu chứng), `P-6` và `C-F` bị gắn `Cosmetic`/`[LOW]` nhưng khi sửa thì lộ ra việc đã build không được ghi nhận và link sẽ hỏng. Lý do chung: các finding này được rút ra từ **đọc tài liệu**, và tài liệu chính là thứ đang lệch. **Chỉ verify bằng code mới bắt được.** Kết luận vận hành: readiness check nên **verify code cho mọi finding**, kể cả finding trông như chuyện hình thức.

**Assessor:** Mary (Business Analyst) · **Date:** 2026-07-25
**Method:** đọc toàn bộ PRD (817 dòng), `epics.md` (485 dòng), `ARCHITECTURE-SPINE`, `sprint-status.yaml`, `merge-to-prod-checklist.md`, `deferred-work.md`; **verify 6 phát hiện bằng source code** (`nowing_backend/app/`, `nowing_web/`, `nowing_mcp/`).

---

## Remediation Log — Nhóm 1 (áp dụng 2026-07-25, sau khi báo cáo hoàn tất)

PO phê duyệt xử Nhóm 1 ngay. Mọi thay đổi trạng thái đều **verify bằng code trước khi sửa**, không sửa từ sai này sang sai khác.

| # | Finding | Đã làm | Bằng chứng verify |
|---|---|---|---|
1 | **C-A** FR-18 | PRD FR-18 → `[DONE]` + cải chính tường minh; `epics.md` chuyển FR-18 sang danh sách `[DONE]`; xoá `[GAP]` ở §6.2 | `actions/builtin/__init__.py` import **6 action**: `agent_task`, `continue_research`, `write_back_jira`, `write_back_linear`, `write_back_notion`, `write_back_slack`. Ghi nhận thêm: **OQ-5 đã được trả lời trong thực thi** — chọn action type riêng, không phải `agent_task` gọi tool |
2 | **C-B** FR-35 | PRD FR-35 → `[DONE]`; `epics.md` Story 6.5 header + coverage map + FR inventory → `[DONE]`; xoá `[GAP]` ở §6.2 | `triggers/builtin/__init__.py`: `from . import event, memory_change, schedule` · `actions/builtin/continue_research/` · `AutomationRun.research_thread_id` (`db.py:712`, relationship `db.py:746`) · `dispatch/launch.py:44` `resolve_research_thread_id` · guard chống vòng lặp trong `selector.py` |
3 | **U-4** NFR-6 | PRD NFR-6 → `[DONE]`; **`AD-DEFER-1` ĐÓNG** trong `ARCHITECTURE-SPINE` (gạch bỏ lý do lỗi thời, ghi verify); `epics.md` NFR inventory → `[DONE]` | `editor-panel.atom.ts` có `chunkId` (dòng 12, 23, 38, 64, 79, 93) · logic ở `components/editor-panel/editor-panel.tsx` + `components/editor/plugins/citation-kit.tsx` |
4 | **P-1** §6.1 stale | Bỏ *"đánh giá mất dữ liệu legacy (FR-36)"* khỏi danh sách open; thay bằng hai open item thật (`3-9` eval gate, `8-7` spend cap) | FR-36 đã `[RESOLVED]` từ trước ở §4.3 |
5 | **P-2** NFR-8 stale | Sửa `review` → **`in-progress`** ở **4 chỗ** (PRD §0 note, PRD NFR-8, PRD FR-32 status, `epics.md` ×2) + gắn nhãn **cổng chặn launch** | `sprint-status.yaml`: `3-9-memory-recall-eval-gate: in-progress` |
6 | **C-D** merge-checklist | Sửa dòng *"2 story chưa xong (4-6 ready-for-dev, 6-5 backlog)"* → cả hai `done`, kèm bằng chứng; ghi rõ **không còn story dev tồn đọng**, chỉ còn gate G1–G5 (thật sự mở: **G3** `3-9`, **G4** `8-7`) | 4 MCP memory tool ở `features/memory/__init__.py` (dòng 31/84/130/154) + `selfcheck.py` + `tests/test_research_continuity.py`; FR-35 như hàng 2 |

**Phát sinh ngoài Nhóm 1, xử luôn vì cùng nguyên nhân:** `[GAP]` ở §6.2 cho **OQ-4** (per-workspace MCP tool toggle, story `2-5` = done) và **NFR-7/FR-31** (usage dashboard, story `8-3` = done) cũng stale — đã chuyển sang danh sách "đã ra khỏi out-of-scope". Xoá 2 dòng `[GAP]` trùng lặp trong cùng section.

### Còn lại sau Nhóm 1 — ✅ **tất cả đã đóng 2026-07-25**

| Nhóm | Việc | Chặn gì | Trạng thái |
|---|---|---|---|
**2** | Q-1 đổi tên Epic 9 · Q-2 chốt retention trong AD-11 · Q-3 tách 9.1 · Q-4 tách 9.6 · Q-5 sửa AC 9.3 · C-C xung đột số hiệu Epic 8 · C-D thêm entry cho 5 story không được track | `bmad-create-story` cho Epic 9 | ✅ **ĐÓNG** |
**3** | P-4/C-2 onboarding seeding · C-1/P-5 NFR-1 · U-1/U-2 AD cho async flow · U-3 câu hỏi thứ 4 cho OQ-7 · UX spec tối thiểu | Story `9.3`, và adoption | ✅ **ĐÓNG** — FR-40 + `3-13` · NFR-1a–1d + `AD-18` + `3-14` · `AD-17` · U-3 **rút** · UX contract (1 viết, 2 hoãn có trigger) |
**4** | P-6 thứ tự OQ · C-F rename `3.8-…` · Q-7 framing Epic 8 | — | ✅ **ĐÓNG** — và **cả hai đều không cosmetic**: P-6 lộ ra OQ-4 + OQ-5 **đã build** mà PRD còn ghi `[GAP]`; C-F lệch ở **2** thư mục + **6** tham chiếu |

**Không bị chặn, chạy được ngay:** đóng `3-9` · dev `8-7` · trả lời **OQ-7** (đang chặn `42-1`/`42-3` phía ChainLens).

⚠️ **Ràng buộc thứ tự mới sinh ra từ Nhóm 3:** `3-14` **nên chạy trước khi chốt số SM-10 của `3-9`** (`AD-18` rule 6) — baseline recall quality đo trên lượng inject phụ thuộc N thì không tái lập được. Điều này **đổi** dòng "đóng `3-9`" ở trên: `3-9` chạy được tiếp, nhưng **chốt số** thì chờ `3-14`.

### Nhóm 1 — Bổ sung (phát hiện khi PO hỏi "architecture có cần update không?")

Lượt Nhóm 1 đầu tiên **làm thiếu**: mình sửa các `[GAP]` lỗi thời trong PRD và `epics.md`, nhưng chỉ đóng **1 trong 5** mục lỗi thời tương ứng ở `ARCHITECTURE-SPINE` section `## Deferred / Gaps`. Cùng một loại lỗi, sót ở tài liệu thứ ba.

| AD | Trước | Sau | Verify code |
|---|---|---|---|
`AD-DEFER-1` | DEFERRED | ✅ ĐÓNG *(đã làm lượt đầu)* | `editor-panel.atom.ts` có `chunkId` |
**`AD-DEFER-2`** | DEFERRED | ✅ **ĐÓNG** | `actions/builtin/__init__.py` import `write_back_jira/linear/notion/slack` |
**`AD-DEFER-3`** | DEFERRED | ✅ **ĐÓNG** | bảng `workspace_mcp_tool_settings` (`db.py:1945`) + mig `175_add_workspace_mcp_tool_settings.py` + `McpToolGroup` (`mcp_tools.py:16`) |
**`AD-DEFER-4`** | DEFERRED | ⚠️ **PARTIAL** | mig `176_add_document_retention.py` + `Workspace.document_retention_days` (`db.py:1804`) + cron. **Còn mở thật:** right-to-delete cho `memories` + ToS/PII (OQ-3) |
**`AD-DEFER-5`** | DEFERRED | ✅ **ĐÓNG** | `app/routes/usage_routes.py` (`prefix="/usage"`) + UI `nowing_web/app/dashboard/[workspace_id]/usage/` |
**`AD-DEFER-6`** | DEFERRED | ✅ **ĐÓNG** | `triggers/builtin/memory_change/` + `actions/builtin/continue_research/` + `AutomationRun.research_thread_id` (`db.py:712`) |

**Hai lỗi cấu trúc sửa kèm:**
- **`AD-16` bị đặt lạc vào `## Deferred / Gaps`** (giữa AD-DEFER-6 và AD-DEFER-7) — nó là invariant đang hoạt động, không phải mục hoãn. → chuyển về `## Invariants & Rules`, cạnh `AD-15`. *(Lỗi do lượt thêm AD-16 chèn sai vị trí.)*
- **`### AD-REMOVED — AI File Sorting` trùng lặp hai chỗ** (Invariants + Deferred) → giữ một bản ở Invariants.

**`epics.md`:** Epic 6 header sửa từ *"✅ DONE (2 gap)"* → **"✅ DONE"**, cập nhật FR list thành `FR-19, FR-20, FR-18, FR-35` và liệt kê trigger/action thật (`memory_change`, `continue_research`, `write_back_*`).

**Trạng thái spine sau khi dọn:** 16 invariant (AD-1…AD-16) + AD-REMOVED trong `## Invariants & Rules`; `## Deferred / Gaps` còn **2 mục sống**: `AD-DEFER-4` (PARTIAL — legal) và `AD-DEFER-7` (NON-GOAL owned index). 5 mục đã đóng giữ lại dạng gạch bỏ kèm bằng chứng để không ai mở lại.

**Còn thiếu ở spine — chưa làm, đã ghi vào banner đầu file:**
- **Q-2** — `AD-11` chưa chốt phương án retention cho FR-39; quyết định đang nằm trong AC của `9.6`.
- **U-1 / U-2** — chưa có AD nào cho async deliverable flow (NFR-9 State A) và quyết định delivery (`runs` vào Zero publication / SSE / polling).

### Nhóm 2 — Hai AD đã viết (2026-07-25, đợt 3)

Giải nốt ba finding: **Q-2**, **U-1**, **U-2**. Cả hai AD đều **verify bằng code trước khi quyết**, và một trong hai lật ngược kết luận của chính báo cáo này.

#### `AD-11.1` — Memory tự chứa recipe *(giải Q-2)*
**Chốt:** `Memory` **sao chép** `source_capability` + `source_input` (JSONB) + soft `source_run_id` (UUID, **không FK cứng**). **Loại bỏ** phương án retention có điều kiện cho `runs`.

**Lý do (bốn điểm):** (a) cleanup `runs` là **cơ hội** (~1% insert, `runs.py:33-37`) — thêm điều kiện biến một cleanup rẻ thành truy vấn có khoá join sang `memories`; (b) `runs.output_text` là JSONL cỡ lớn, giữ vô hạn vì memory là **đắt sai chỗ** — cái cần giữ là *recipe*, không phải *payload*; (c) AD-11 đã định nghĩa memory là first-class persistence layer nên nó **không được** phụ thuộc lifecycle của bảng log; (d) memory sống 2 năm vẫn re-validate được dù `Run` bị xoá 23 tháng trước.

**Thêm ràng buộc mới:** `source_input` là **snapshot bất biến** — muốn đổi truy vấn thì tạo memory mới. Nếu mutate được thì "re-validate" mất nghĩa. `Memory.source_id` (Integer) **giữ nguyên** cho `document`/`chat_message` (chống hồi quy).

⇒ AC của story `9.6` giờ **xác định**, không còn "chọn một trong hai". Q-2 đóng.

#### `AD-17` — Deep research chạy trên async door SẴN CÓ *(giải U-1 + U-2)*

> **⚠️ Cải chính chính báo cáo này.** Step 4 kết luận *"NFR-9 State A không có architecture decision nào đỡ"* và ngụ ý phải xây flow mới. **Sai.** Async door cho capability **đã build end-to-end**, và `chainlens.research` **đã nằm sau nó** (nó là capability đăng ký qua `register_capability`).

| Mảnh | Đã có ở đâu |
|---|---|
Submit fire-and-forget | `?mode=async` → insert `Run` `running`, spawn background task, **202** + `X-Run-Id` (`rest.py:312-330`) |
Progress live | SSE `GET .../runs/{run_id}/events` (`rest.py:493`) |
Replay khi reconnect | ring buffer **500 event** per run (`events.py`) |
Terminal + snapshot | event `run.finished`; client muộn đọc hàng `runs` |
Cancel | `POST .../runs/{run_id}/cancel` (`rest.py:559`) |
History | `GET .../runs`, `GET .../runs/{run_id}` |
**Typed client ở web** | `scrapers-api.service.ts:68` đã build `?mode=async`; `scraper.types.ts:56` type 202 |

**U-2 chốt:** delivery đi **SSE**; **KHÔNG** thêm `runs` vào `ZERO_PUBLICATION` — `runs` là bảng log khối lượng lớn TTL 30 ngày với `output_text` JSONL; Zero sync dành cho state client theo dõi liên tục. `AD-5` giữ nguyên phạm vi. Cũng loại polling (SSE + ring buffer đã giải bài toán reconnect).

**Ba việc CÒN THIẾU thật — đây mới là nội dung story `9.3`:**
1. **`run_event_bus` chỉ chạy trong MỘT process.** `events.py` tự ghi: *"single-process only — a multi-worker deployment needs Redis pub/sub … behind this same interface"*. Nhiều replica → client tail SSE ở replica A **không thấy** event của run ở replica B, **im lặng, không lỗi**. Cần Redis pub/sub sau **cùng interface** (Redis đã có cho Celery). **Tiền đề trước khi bật async trên môi trường nhiều replica.**
2. **Agent door đang SYNC** (`access/agent.py` gọi executor inline, không có `mode`) → **đây mới là chỗ block chat turn** tới 300s. Phần khó nhất của `9.3`, không phải transport.
3. **Không có notify khi xong** (grep `Notification|notify` trong `rest.py`/`runs.py` = **0 hit**) và kết quả chỉ nằm trong `runs.output_text` (TTL 30 ngày), chưa thành deliverable hạng nhất. Bảng `notifications` đã có (`app/notifications/persistence.py`) và **đã trong `ZERO_PUBLICATION`** → realtime sẵn, chỉ cần emit.

⇒ Story `9.3` **thu hẹp** đáng kể: không xây flow, chỉ 3 việc trên + đo p50/p95 + ngưỡng cổng A→B.

#### Sửa kèm
- **Q-5** — AC tự tham chiếu của `9.3` (*"Then định nghĩa ngưỡng p95"*) chuyển thành **deliverable tài liệu**, không phải AC. Kỷ luật "không đặt ngưỡng trước khi đo" giữ nguyên.
- **U-3** — bổ sung **câu hỏi thứ 4** vào OQ-7 gửi ChainLens: engine emit progress theo phase được không? Transport đã xong nhưng chỉ có 2 event (`starting`/`done`) nên **không có gì để truyền** trong 57–198s.
- Sắp lại thứ tự AD-16/AD-17 trong spine; cập nhật capability map (+3 dòng: async door, multi-replica bus, provenance).

#### Trạng thái Nhóm 2 sau đợt này

| Finding | Trạng thái |
|---|---|
**Q-2** `9.6` AC chứa quyết định | ✅ **đóng** — `AD-11.1` |
**U-1** không có AD cho async flow | ✅ **đóng** — `AD-17` (và cải chính: hạ tầng đã có) |
**U-2** quyết định delivery | ✅ **đóng** — SSE, không mở Zero cho `runs` |
**Q-5** AC tự tham chiếu `9.3` | ✅ **đóng** |
**U-3** progress granularity | 🟠 chuyển thành OQ-7 câu 4 — chờ ChainLens |
**Q-1** Epic 9 technical epic | ⏳ còn — đổi tên, 1 dòng |
**Q-3** tách `9.1` | ⏳ còn |
**Q-4** tách `9.6` | ⏳ còn |
**C-C** xung đột số hiệu Epic 8 | ⏳ còn |

**Spine hiện tại:** 17 invariant (AD-1…AD-17) + AD-REMOVED; `Deferred / Gaps` còn 2 mục sống (`AD-DEFER-4` legal, `AD-DEFER-7` NON-GOAL).

### Nhóm 2 — Hoàn tất (2026-07-25, đợt 4): Q-1, Q-3, Q-4, C-C, C-D, Q-7

| Finding | Đã làm |
|---|---|
**Q-1** Epic 9 là technical epic | Đổi tên → **"Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng"**. Ba mệnh đề map thẳng vào ba story: *không vỡ* = `9.1a` degradation · *không treo* = `9.3` async · *tính phí đúng* = `9.2` cost metering |
**Q-7** Epic 8 framing ops | Đổi tên → **"Người dùng thấy và kiểm soát được chi phí"** (trước: *"Platform Operations (Billing/Usage/Token)"*) |
**Q-3** `9.1` gộp 2 concern | Tách **`9.1a`** Research Degradation & Self-Host Independence *(P0, **chặn public repo**, FR-38)* + **`9.1b`** Research Contract Regression Guard *(P0, **không chặn**, FR-24)*. Lý do: chỉ phần degradation mới thật sự chặn; gộp lại làm public repo bị chặn oan bởi contract test |
**Q-4** `9.6` gộp 4 việc | Tách **`9.6a`** Memory Provenance Recipe *(nền)* + **`9.6b`** Source Re-Validation API *(dep 9.6a)*. Việc thứ ba (quyết định retention) đã bị `AD-11.1` hấp thụ nên không còn là việc của story |
**C-C** xung đột số hiệu Epic 8 | Đánh lại theo số **chưa dùng** trong `sprint-status.yaml`: `8.4a → 8.8` · `8.5 → 8.9` · `8.6 → 8.10`. Từ giờ số hiệu hai tài liệu **khớp 1-1** |
**C-D** 5 story không được track | Thêm vào `sprint-status.yaml`: `3-11` (done) · `3-12` (done) · `8-8` (done) · `8-9` (done) · **`8-10` (backlog — việc thật chưa làm, trước đây không được track ở đâu cả)** |

**AC mới đáng chú ý ở `9.6b`:** *"Given `Run` gốc đã bị xoá sau 30 ngày · When gọi `revalidate` · Then vẫn chạy được"* — đây là AC **chứng minh quyết định `AD-11.1` đúng**, không chỉ mô tả tính năng. Thêm AC về metering: re-validate gọi lại capability có phí nên phải đi qua `AD-8`, không có đường tính phí ẩn.

**Đồng bộ chéo:** tên epic mới + số hiệu story mới đã propagate sang `epics.md` (coverage map + Epic list + story header + cross-ref), `sprint-status.yaml` (8 entry Epic 9 + 5 entry bổ sung), PRD (§4.9 FR-24/FR-38/FR-39, §6.1, §0 note), `ARCHITECTURE-SPINE` (AD-11.1, banner), SCP (§2.2, §2.5, §5 sequencing, §8 D5), và `brief.md` (callout + §5.1 + §12 H-1/H-2). Sweep xác nhận **0** tham chiếu còn dùng số cũ.

**`sprint-status.yaml`:** parse OK, **62 story**. Epic 9 có 8 entry (`9-1a`, `9-1b`, `9-2`, `9-3`, `9-4`, `9-5`, `9-6a`, `9-6b`).

### Trạng thái toàn bộ readiness findings

| Nhóm | Trạng thái |
|---|---|
**Nhóm 1** — lệch tài liệu (C-A, C-B, U-4, P-1, P-2, C-D-merge-checklist) + 5 AD-DEFER lỗi thời + 2 lỗi cấu trúc spine | ✅ **đóng** |
**Nhóm 2** — Q-1, Q-2, Q-3, Q-4, Q-5, Q-7, C-C, C-D, U-1, U-2 | ✅ **đóng** |
**Nhóm 3** — P-4/C-2 onboarding seeding · C-1/P-5 NFR-1 · U-3 · UX spec | ✅ **đóng** — FR-40 + `3-13` · NFR-1a–1d + `AD-18` + `3-14` · U-3 **rút** (lỗi parser Nowing, không phải engine) · UX contract 1 viết + 2 hoãn có trigger |
**Nhóm 4** — P-6 thứ tự OQ · C-F rename `3.8-…` · Q-8/Q-9 quy ước | ✅ **đóng** — OQ sắp 1→7 **và** OQ-4/OQ-5 đánh lại `[RESOLVED]` (đã build, PRD còn ghi `[GAP]`) · rename 2 file + 6 tham chiếu · Q-8/Q-9 là quy ước brownfield, giữ nguyên (accepted) |

**Epic 9 giờ sẵn sàng cho `bmad-create-story`.** Không còn AC chứa quyết định treo, không còn story gộp concern, không còn xung đột số hiệu, mọi story có AD chi phối rõ ràng.

### OQ-7 đã trả lời (2026-07-25, đợt 5) — ba trong bốn câu LẬT

Deliverable: **`planning-artifacts/oq7-answers-to-chainlens-2026-07-25.md`** (ready-to-send). Phương pháp: đọc code **cả hai repo** trước khi kết luận, không trả lời theo phỏng đoán.

| Câu | Kết luận | Ai còn phải làm gì |
|---|---|---|
**Q1** endpoint riêng | **Không.** Nowing có runtime multi-agent riêng → thêm `answer`/`reason` tạo **hai lớp reasoning xếp lên nhau** (đắt gấp đôi, khó truy nguyên citation). Cần độ sâu khác → thêm giá trị `optimizationMode` | ChainLens: đóng câu |
**Q2** geo-access `41-2` | **Hạ ưu tiên**, và **có trùng lặp**: Nowing đã có proxy registry/rotation + GeoIP match + WebRTC block + canvas hiding + DNS-over-HTTPS + CAPTCHA trong crawler BSL riêng. Chưa có khiếu nại cụ thể → đừng build speculatively | ChainLens: hạ ưu tiên, ưu tiên `42-1`→`43-1`→`43-5` |
**Q3** format `costDollars` | ✅ **Shape ChainLens đã thiết kế là đúng** — tìm thấy ở `sse-contract-fixtures.ts:168`. Xin thêm `resolvedMode` (vì `auto` khiến Nowing không biết mode thật → SM-11a chia theo mode) + `estimated`, đặt `usage` trước `done` | **ChainLens: ship `42-1`** — việc duy nhất còn lại của họ |
**Q4** progress theo phase | 🔄 **Nowing RÚT.** ChainLens **đã emit** `progress` từ trước (`api.ts:414/1298/221`) + `evidence_ready` + `synthesizing` + `heartbeat`. Parser Nowing chỉ dispatch 4 type nên bỏ hết | ChainLens: không gì |

### 🔴 Ba defect quay ngược về backlog Nowing

**1. Nowing đang bỏ 6 loại SSE event engine gửi** — `progress`, `insufficientEvidence`, `partial`, `synthesizing`, `heartbeat`, `noop`. `_parse_sse` chỉ dispatch `error`/`done`/`block`/`updateBlock`, và trong block chỉ đọc `text` + `source`. → AC mới ở `9.1a` (partial/insufficientEvidence/heartbeat) và `9.3` (progress mapping).

**2. Nowing suy đoán lại thứ engine đã nói rõ — nặng nhất.**
Engine gửi tường minh `{type:'partial', state:'insufficient_evidence', reason}` (`api.ts:1309`). Nowing lại đoán:
```python
if not answer and not sources:
    if saw_done: status = "insufficient_evidence"
    else:        status = "timeout"
```
Tức **gộp "không tìm ra bằng chứng" với "stream chết giữa đường"** vào một phép đoán, trong khi engine đã phân biệt sẵn kèm `reason`. Đây đúng là trạng thái mà **FR-38** cần tường minh. → `9.1a`.

**3. Contract bị document SAI trong tài liệu Nowing.** Docstring fixture của ChainLens ghi rõ: *"NestJS `@Sse()` emits data-only frames — there is NO separate `event:` line"* và *"terminal marker là `{\"type\":\"done\"}`, KHÔNG phải `data: [DONE]`"*. Nhưng PRD §4.9 FR-24, `AD-15`, SCP §3 đều mô tả `event:`/`data:`. Nowing có nhánh xử lý `event:` **không bao giờ chạy**. Nguy hiểm vì ai viết regression test theo tài liệu Nowing sẽ test một format không tồn tại. → `9.1b`.

### 🎁 Ghi nhận phía ChainLens

`42-2` của họ đã làm đúng cách khó nhất: `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` là **bản mirror parser của Nowing**, dùng **chính** `rfc6902 applyPatch` mà `session.ts updateBlock` dùng → parity chính xác, không phải xấp xỉ.
⇒ AC mới ở `9.1b`: **tham chiếu/đồng bộ fixture đó**, không viết fixture thứ hai (hai fixture sẽ lệch dần).

### Action items cập nhật

| ID | Owner | Trạng thái |
|---|---|---|
`AI-2026-07-25-1` | PO | ✅ **done** — OQ-7 đã trả lời |
`AI-2026-07-25-4` | PO | 🔵 open — **gửi file cho ChainLens team** |
`AI-2026-07-25-5` | Backend | 🔵 open — 6 SSE event bị bỏ + heuristic suy đoán (→ `9.1a`, `9.3`) |
`AI-2026-07-25-6` | Architect | 🔵 open — sửa contract document sai (→ `9.1b`) |
`AI-2026-07-25-2` | PO | 🔵 open — giữ freeze positioning tới 2026-08-24 |
`AI-2026-07-25-3` | Backend | 🔵 open — deploy-order mig177→backfill→mig178 |

**Đường găng liên-team giờ chỉ còn một mắt:** ChainLens `42-1` (`costDollars`) → chặn Nowing `9-2` → chặn việc chốt giá cloud. Ba câu còn lại của OQ-7 đã đóng và **không** cần ChainLens làm gì.
