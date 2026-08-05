---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
documentsIncluded:
  prd:
    - _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md
  architecture:
    - _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md
  epics:
    - _bmad-output/planning-artifacts/epics.md
  ux:
    - _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05
**Project:** Nowing

## Step 1: Document Discovery

### PRD Files Found

**Whole Documents:**
- `prds/prd-Nowing-2026-07-22/prd.md` (108,836 bytes, 2026-08-05 10:24)

**Sharded Documents:**
- Folder: `prds/prd-Nowing-2026-07-22/`
  - `prd.md` (main)
  - `.memlog.md`
  - `review-prfaq-gap.md`
  - `review-rubric.md`
  - `validation-report.md`
  - `validation-report.html`

### Architecture Files Found

**Sharded Documents:**
- Folder: `architecture/architecture-Nowing-2026-07-22/`
  - `ARCHITECTURE-SPINE.md` (78,269 bytes, 2026-08-05 10:24)

**Note:** `epic-11-architecture-review-2026-08-03.md` was found but is a review artifact, not the core architecture document.

### Epics & Stories Files Found

**Whole Documents:**
- `epics.md` (102,052 bytes, 2026-08-05 15:07)

**Note:** `epic-11-architecture-review-2026-08-03.md` was found but is an architecture review, not an epics document.

### UX Design Files Found

**Whole / Review Documents:**
- `archive/ux-audit-improvement-spec-2026-07-27.md` (14,931 bytes, 2026-08-05 10:24)

**Sharded Documents:**
- Folder: `ux-designs/ux-Nowing-2026-07-22/`
  - `ux-contract-async-deep-research.md` (7,417 bytes, 2026-08-04 20:16)

### Issues Found

- **PRD:** One whole document with companion review/validation artifacts. No duplicate in a sharded folder outside the main PRD folder.
- **Architecture:** Only a sharded folder with `ARCHITECTURE-SPINE.md`. No whole architecture document found.
- **Epics:** One whole `epics.md` found.
- **UX:** One archived audit spec and one sharded UX contract for async deep research. Need user confirmation on which UX document is authoritative for the current assessment.

### Required Actions

- Confirm whether `archive/ux-audit-improvement-spec-2026-07-27.md` or `ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md` (or both) should be used for the UX assessment.
- Confirm whether the PRD companion files (`.memlog.md`, `review-prfaq-gap.md`, `review-rubric.md`, `validation-report.md`) should be included in the readiness assessment.

**Select an Option:** [C] Continue to File Validation

---

## Step 2: PRD Analysis

PRD analyzed: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (whole document).

### Functional Requirements

| ID | Title | Status |
|---|---|---|
| FR-1 | User Authentication | — |
| FR-2 | API Access for External Clients | — |
| FR-3 | Workspace Lifecycle | — |
| FR-4 | Workspace Invites & Memberships | — |
| FR-10 | RBAC với ba system roles | `[REMOVED]` |
| FR-6 | Built-in Scraper Connectors | — |
| FR-7 | External OAuth Connectors | — |
| FR-8 | External MCP Connectors | — |
| FR-9 | Document Upload, Parse & Index | — |
| FR-11 | Folders & Document Management | — |
| FR-12 | Hybrid Search over Knowledge Base | — |
| FR-13 | Citation Panel for Knowledge-base Chunks | — |
| FR-32 | Long-Term Research Memory | `[BUILT — PARTIAL]` |
| FR-33 | Research Continuity | `[BUILT — PARTIAL]` |
| FR-34 | Memory Correction | `[BUILT — GAP]` |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | `[RESOLVED 2026-07-25]` |
| FR-40 | First-Run Value — Research Runs Produce Memory | `[GAP — HIGH]` |
| FR-5 | AI File Sorting | `[REMOVED]` |
| FR-14 | Chat Threads & Messages | — |
| FR-15 | Multi-agent Runtime with Tools | `[PARTIAL]` |
| FR-16 | Real-time Collaborative Chat | — |
| FR-17 | Anonymous Chat with Quota | — |
| FR-42 | Chat Response Benchmark | — |
| FR-21 | Report Generation & Export | — |
| FR-22 | Podcast & Video Presentation | — |
| FR-23 | Image Generation | — |
| FR-18 | Automation Action Types | `[DONE]` |
| FR-19 | Automation Triggers | — |
| FR-20 | Automation Runs & Retries | — |
| FR-35 | Memory-Driven Automations | `[DONE]` |
| FR-25 | Web Client (Next.js) | — |
| FR-26 | Desktop Client (Electron) | — |
| FR-27 | Browser Extension (Plasmo) | — |
| FR-28 | Obsidian Plugin | — |
| FR-29 | MCP Server | `[BUILT]` |
| FR-30 | Token Usage Tracking | — |
| FR-31 | Credit Wallet & Purchases | `[GAP]` |
| FR-41 | Admin UI cho Global LLM Model Configuration | `[GAP — mới 2026-07-26]` |
| FR-24 | Deep Open-Web Research via ChainLens Engine | `[DONE]` |
| FR-37 | Deep-Research Cost Metering | `[DONE]` |
| FR-38 | Research Degradation & Self-Host Independence | `[DONE — P0]` |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | `[GAP — defect schema]` |

**Total FRs: 42**

### Non-Functional Requirements

| ID | Title | Status |
|---|---|---|
| NFR-1 | Performance (1a CRUD/scraper, 1b memory injection, 1c recall, 1d auto-extract) | `[GAP]` |
| NFR-2 | Security & Auth | — |
| NFR-3 | Observability | — |
| NFR-4 | Reliability | — |
| NFR-5 | Multi-tenancy Isolation | — |
| NFR-6 | Citation Full-Editor Highlight | `[DONE]` |
| NFR-7 | Usage & Credit Dashboard | `[GAP]` |
| NFR-8 | Recall Quality (eval-gated) | `[IN-PROGRESS]` |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) | `[PARTIAL]` |
| NFR-10 | Chat Response Regression Gate | — |

**Total NFRs: 10**

### Additional Requirements / Constraints

- **Direction-correction 2026-07-25 (ADOPTED):** Nowing = sản phẩm, ChainLens = engine. FR-24 rời §4.2 Connectors → §4.9. FR-37, FR-38, NFR-9 mới.
- **§2.4 Non-Goals:** bán research data (NG-1), parity consumer kiểu Perplexity (NG-2), ChainLens thành sản phẩm độc lập (NG-3).
- **FR-10 Admin role** đã xóa khỏi RBAC; README/public docs vẫn còn mention cần cập nhật.
- **FR-32 recall hit** hiện không áp dụng ngưỡng similarity (score bị bỏ, hardcode 0.0) — giao lại 3-14.
- **FR-40** phụ thuộc 9-6a (`AD-11.1` provenance) nhưng bản tối thiểu có thể chạy độc lập.
- **NFR-1b** memory injection chưa enforce ngân sách 8.000 chars ở đường đọc; chỉ có soft warning.

### PRD Completeness Assessment

- PRD có đầy đủ 42 FRs và 10 NFRs với acceptance criteria, consequences, status.
- Có nhiều `[GAP]`, `[PARTIAL]`, `[REMOVED]` được ghi rõ → tốt cho traceability.
- Rủi ro chính: FR-32/FR-40/NFR-1/NFR-8/NFR-9 còn mở hoặc partial; FR-41, FR-39 là gap mới; FR-10, FR-5 removed nhưng docs chưa cập nhật.
- Khuyến nghị: cập nhật `epics.md` coverage map cho FR-41, FR-42, NFR-10 (mới 2026-08-04) và xác nhận dependency FR-40 ↔ 9-6a.

---

**PROCEEDING TO EPIC COVERAGE VALIDATION**

**Select an Option:** [C] Continue to Epic Coverage Validation

---

## Step 3: Epic Coverage Validation

Epics analyzed: `_bmad-output/planning-artifacts/epics.md`

### Epic FR Coverage Extracted

| FR | Epic | Status | Note |
|---|---|---|---|
| FR-1 | E1 | DONE | |
| FR-2 | E1 | DONE | |
| FR-3 | E1 | DONE | |
| FR-4 | E1 | DONE | |
| FR-10 | E1 | DONE | Admin role removed, docs gap |
| FR-6 | E2 / E10.1 | DONE / ready-for-dev | E10.1 = batdongsan scraper extension |
| FR-7 | E2 | DONE | |
| FR-8 | E2 | DONE | |
| FR-9 | E3 | DONE | |
| FR-11 | E3 | DONE | |
| FR-12 | E3 | DONE | |
| FR-13 | E3 | DONE | |
| FR-32 | E3 (3.8, 3.9, 3.11) | DONE | dedupe/recall quality → 3.14 |
| FR-33 | E4 (4.6) | DONE | |
| FR-34 | E3/E4 | DONE | |
| FR-36 | E3.10a/b | RESOLVED | 2026-07-25 |
| FR-40 | E3.13 | DONE | HIGH, mới 2026-07-25 |
| FR-14 | E4 | DONE | |
| FR-15 | E4 | DONE | `[PARTIAL]` per PRD |
| FR-16 | E4 | DONE | |
| FR-17 | E4 | DONE | |
| FR-21 | E5 | DONE | |
| FR-22 | E5 | DONE | |
| FR-23 | E5 | DONE | |
| FR-18 | E6.4 | DONE | |
| FR-19 | E6 | DONE | |
| FR-20 | E6 | DONE | |
| FR-35 | E6.5 | DONE | |
| FR-25 | E7 | DONE | |
| FR-26 | E7 | DONE | |
| FR-27 | E7 | DONE | |
| FR-28 | E7 | DONE | |
| FR-29 | E7 | DONE | `[BUILT]` per PRD |
| FR-30 | E8 | DONE | |
| FR-31 | E8.3 | DONE | `[GAP]` per PRD |
| FR-41 | E8.11 | GAP | mới 2026-07-26 |
| FR-24 | E9.1b | DONE | P0 |
| FR-37 | E9.2 | DONE | P0 |
| FR-38 | E9.1a | DONE | P0 |
| FR-39 | E9.6a/b | GAP | defect schema |
| FR-5 | — | REMOVED | AI File Sorting removed |

**Total FRs in epics: 41**

### Coverage Analysis

| FR | PRD Requirement | Epic Coverage | Status |
|---|---|---|---|
| FR-1 | User Authentication | E1 | ✓ |
| FR-2 | API Access | E1 | ✓ |
| FR-3 | Workspace Lifecycle | E1 | ✓ |
| FR-4 | Workspace Invites | E1 | ✓ |
| FR-6 | Built-in Scraper Connectors | E2 / E10.1 | ✓ |
| FR-7 | External OAuth Connectors | E2 | ✓ |
| FR-8 | External MCP Connectors | E2 | ✓ |
| FR-9 | Document Upload, Parse & Index | E3 | ✓ |
| FR-10 | RBAC | E1 | ✓ (role removed, docs gap) |
| FR-11 | Folders & Document Management | E3 | ✓ |
| FR-12 | Hybrid Search | E3 | ✓ |
| FR-13 | Citation Panel | E3 | ✓ |
| FR-14 | Chat Threads | E4 | ✓ |
| FR-15 | Multi-agent Runtime | E4 | ✓ (partial per PRD) |
| FR-16 | Real-time Collaborative Chat | E4 | ✓ |
| FR-17 | Anonymous Chat | E4 | ✓ |
| FR-18 | Automation Action Types | E6.4 | ✓ |
| FR-19 | Automation Triggers | E6 | ✓ |
| FR-20 | Automation Runs | E6 | ✓ |
| FR-21 | Report Generation | E5 | ✓ |
| FR-22 | Podcast & Video | E5 | ✓ |
| FR-23 | Image Generation | E5 | ✓ |
| FR-24 | Deep Open-Web Research | E9.1b | ✓ |
| FR-25 | Web Client | E7 | ✓ |
| FR-26 | Desktop Client | E7 | ✓ |
| FR-27 | Browser Extension | E7 | ✓ |
| FR-28 | Obsidian Plugin | E7 | ✓ |
| FR-29 | MCP Server | E7 | ✓ |
| FR-30 | Token Usage Tracking | E8 | ✓ |
| FR-31 | Credit Wallet | E8.3 | ✓ (GAP per PRD) |
| FR-32 | Long-Term Research Memory | E3 (3.8/3.9/3.11) | ✓ (partial per PRD) |
| FR-33 | Research Continuity | E4 (4.6) | ✓ |
| FR-34 | Memory Correction | E3/E4 | ✓ |
| FR-35 | Memory-Driven Automations | E6.5 | ✓ |
| FR-36 | Legacy Memory Data-Loss | E3.10a/b | ✓ |
| FR-37 | Deep-Research Cost Metering | E9.2 | ✓ |
| FR-38 | Research Degradation | E9.1a | ✓ |
| FR-39 | Memory Provenance | E9.6a/b | ✓ (GAP) |
| FR-40 | First-Run Value | E3.13 | ✓ |
| FR-41 | Admin UI Global LLM | E8.11 | ✓ (GAP) |
| **FR-42** | **Chat Response Benchmark** | **NOT FOUND** | ❌ **MISSING** |
| FR-5 | AI File Sorting | — | REMOVED |

### Missing FR Coverage

#### Critical Missing FR

**FR-42: Chat Response Benchmark**
- **PRD Text:** Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated. Hỗ trợ `chat/regression`, `chat/quality` (LLM-as-judge), và nền tảng lấy mẫu query production đã anonymize.
- **Impact:** PRD ghi FR-42 mới 2026-08-04. `epics.md` chưa map FR-42 vào epic/story nào. NFR-10 (Chat Response Regression Gate) cũng phụ thuộc FR-42.
- **Recommendation:** Tạo epic mới hoặc gán FR-42 vào Epic 4 (Chat) hoặc Epic 10 (Evals/Quality), với stories cho `chat/regression`, `chat/quality`, `production query sampler + anonymizer`.

### Coverage Statistics

- Total PRD FRs: **42** (including FR-5, FR-10 removed)
- FRs covered in epics: **41**
- Coverage percentage: **97.6%**
- Missing: **FR-42**

### Coverage Observations

- FR-41 được map vào E8.11 với status GAP — chính xác với PRD.
- FR-39 được map vào E9.6a/b với status GAP — chính xác.
- FR-32 được map vào E3 với status DONE, nhưng PRD ghi `[BUILT — PARTIAL]` do dedupe/recall quality — cần align.
- FR-15 được map vào E4 DONE, nhưng PRD ghi `[PARTIAL]` — cần align.
- **FR-42 hoàn toàn thiếu** trong `epics.md` coverage map.

---

**PROCEEDING TO UX ALIGNMENT**

**Select an Option:** [C] Continue to UX Alignment

---

## Step 4: UX Alignment Assessment

UX documents analyzed:
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md`
- `archive/ux-audit-improvement-spec-2026-07-27.md`

### UX Document Status

**Found.** UX coverage hiện tại là **mỏng và tập trung**:
- Một contract chi tiết cho **async deep-research progress-first** (`9-3`) đã có.
- Một audit draft rộng hơn nêu nhiều gap ở Phase 2, Epic 11, admin, onboarding, dashboard.

### UX ↔ PRD Alignment

| PRD Requirement | UX Coverage | Alignment |
|---|---|---|
| FR-24 — Deep Open-Web Research | ✅ `ux-contract-async-deep-research.md` | Contract định nghĩa 10 trạng thái UI từ `run_id` → `done`/`error`/`cancel` | ✓ |
| FR-38 — Research Degradation | ✅ S9 "degrade sang hybrid search nội bộ" | R2 yêu cầu ghi nhãn nguồn kết quả tường minh | ✓ |
| NFR-9 — Deep-Research Latency State A | ✅ `AD-17` async flow, SSE delivery, no polling | U-1/U-2 resolved; 10 state contract hỗ trợ State A | ✓ |
| FR-16 — Real-time Collaborative Chat | ⚠️ `AD-5` Zero sync | UX audit chỉ ra sync/offline indicator thiếu, zero-cache single point of failure | ⚠️ |
| FR-41 — Admin UI Global LLM | ❌ Không có UX spec | Audit ghi Epic 11/5.6 chưa có UX | ❌ |
| FR-42 — Chat Response Benchmark | ❌ Không có UX spec | ResearchTimeline cần UI spec | ❌ |
| FR-31/FR-30 — Credit/Usage | ⚠️ Usage dashboard UX hoãn | Audit ghi dashboard cần sửa sau khi `9-2` có cost thật | ⚠️ |
| FR-40 — First-Run Value | ⚠️ Memory browser/timeline hoãn | Trigger: chờ `3-14` + `3-13` | ⚠️ |

### UX ↔ Architecture Alignment

| Architecture Decision | UX Coverage | Assessment |
|---|---|---|
| **AD-5** — Zero sync cho real-time client state | `ux-contract-async-deep-research.md` tôn trọng: `runs` KHÔNG vào Zero publication | ✓ |
| **AD-15** — ChainLens = external deep-research engine | S9 degradation, S5/S8 phân biệt engine vs fallback | ✓ |
| **AD-17** — Async door sẵn có; SSE delivery | 10 state contract dùng `run_event_bus` SSE + ring buffer 500 event | ✓ |
| **AD-18** — Bounded memory (NFR-1b) | UX hoãn memory browser/timeline cho tới khi `3-14` chốt top-k | ✓ (hoãn có chủ) |
| **AD-21** — Client tab state pointer-only | UX audit P0-4/P2 nhắc storage guard, purge IndexedDB | ⚠️ cần chi tiết hóa |

### Warnings

1. **UX coverage rất hẹp:** Chỉ có một contract cho `9-3`. PRD có 42 FRs, nhiều hạng mục UI chưa có UX spec.
2. **Phase 2 UX Overhaul thiếu spec:** `9-UX-1..4` (Live Research Lab, Crypto-Native Report, Interactive Analysis) không có tài liệu thiết kế.
3. **Admin/Settings UX thiếu:** FR-41 (global model config), admin gift requests, settings treo spinner — chưa có UX.
4. **First-run dashboard trống:** F3 trong audit — `/dashboard` chưa có empty state, user menu, onboarding.
5. **Sync/offline indicator thiếu:** F6 vi phạm PRD Risk Mitigation và FR-41 pattern.
6. **Memory browser hoãn có lý do hợp lý** (chờ `3-14` + `3-13`) nhưng cần track rõ ràng.
7. **Usage dashboard hoãn có lý do hợp lý** (chờ `9-2` cost thật) nhưng cần track.

### UX Readiness Verdict

- **Async deep-research (`9-3`):** ✅ ready — có contract rõ ràng, architecture hỗ trợ.
- **Core app UX (onboarding, dashboard, settings, sync):** ⚠️ partial — có audit findings nhưng chưa có story/UX spec đầy đủ.
- **Phase 2 / Admin / Benchmark UX:** ❌ missing — cần bổ sung spec trước khi dev.

---

**PROCEEDING TO EPIC QUALITY REVIEW**

**Select an Option:** [C] Continue to Epic Quality Review

---

## Step 5: Epic Quality Review

Epics analyzed: `_bmad-output/planning-artifacts/epics.md`

### Method

Reviewed 11 epics and ~35 stories against create-epics-and-stories best practices: user value, independence, dependencies, story sizing, acceptance criteria (Given/When/Then), database creation timing, brownfield context, and FR traceability.

### Critical Violations (🔴)

| ID | Epic/Story | Issue | Remediation |
|---|---|---|---|
| 1 | **Story 3.10b** (line 258) | Forward dependency: `Dep: 3.10a (done)` | Merge 3.10a + 3.10b thành một story "Legacy Memory Data Safety" |
| 2 | **Story 9.6b** (line 882) | Forward dependency: `Dep: 9.6a` | Merge 9.6a + 9.6b thành một story "Memory Provenance & Re-validation" |
| 3 | **Story 6.7** (line 433) | Forward dependency: `Gate: dep 6.6; chỉ build sau pilot xanh` | Xóa gate hoặc chuyển vào deferred |
| 4 | **Story 6.10** (line 448) | Forward dependency: `Gate: dep 6.6, 6.7, 6.9` | Tách hoặc gộp thành epic độc lập |
| 5 | **Epic 9** (line 596) | Hard ordering constraint: `9.1a → public repo → 9.1b+9.2+8-7 → 9.3 → 9.4 → 9.6a → 9.6b` | Xem xé tách Epic 9 thành các epic nhỏ hơn (Deep Research Reliability / Cost / Latency / Provenance) |
| 6 | **Story 3.10a** (lines 234-244) | Là spike/forensic task, không deliver user value trực tiếp | Chuyển sang engineering task hoặc merge với 3.10b |

### Major Issues (🟠)

| # | Vấn đề | Ví dụ | Khuyến nghị |
|---|---|---|---|
| 1 | AC không đúng Given/When/Then | Stories **10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3** dùng bullet points | Rewrite to Given/When/Then |
| 2 | AC không testable | Story **9.3** ghi "Deliverable tài liệu (không phải AC)" | Chuyển ngưỡng thành quy trình có thể verify hoặc vào decision record |
| 3 | Implementation details trong AC | Stories **8.11, 9.1a, 9.1b, 9.2** liệt kê file path trong AC | Tách phần kỹ thuật ra "Technical Notes" |
| 4 | Soft/conditional dependencies | Story **3.13** dep mềm với `9-6a`; **3.14** ordering với `3.9` | Làm rõ independent hoặc chuyển thành hard dep và merge |
| 5 | Gate/blocking conditions | **6.6**, **6.7**, **9.5** bị block bởi pilot/cost/self-host | Chuyển sang Deferred section hoặc xóa gate |

### Minor Concerns (🟡)

- Story 3.6, 3.7 AC cần cụ thể hóa error message / anonymize policy.
- Một số story mix tiếng Việt và English (ví dụ Story 2.5).
- Story 3.14 có scope creep từ 3.11 (expose RRF score).
- Epic 8 header ghi note về rename/renumbering → cần single source of truth cho story numbering.
- Một số story 9.x có nhiều context notes trước AC.

### Per-Epic Checklist Summary

| Epic | User Value | Independence | Story Quality | AC Format | DB Creation | Brownfield | Traceability | Overall |
|---|---|---|---|---|---|---|---|---|
| E1: Identity/Auth | ✅ | ✅ | N/A | N/A | ✅ | ✅ | ✅ | ✅ |
| E2: Connectors | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E3: Knowledge Base | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ | 🟠 |
| E4: Chat & Agents | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E5: Deliverables | ✅ | ✅ | N/A | N/A | ✅ | ✅ | ✅ | ✅ |
| E6: Automations | ✅ | 🔴 | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 |
| E7: Multi-surface | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E8: Platform Ops | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | 🟠 |
| E9: Deep Research | ✅ | 🔴 | ✅ | ⚠️ | ✅ | ✅ | ✅ | 🔴 |
| E10: Scraper Expansion | ✅ | ✅ | ✅ | 🔴 | ✅ | ✅ | ✅ | 🔴 |
| E11: Telegram | ✅ | ✅ | ✅ | 🔴 | ✅ | ✅ | ✅ | 🔴 |

### Quality Statistics

- **Total Epics Reviewed:** 11
- **Total Stories Reviewed:** ~35
- **Critical Violations:** 6
- **Major Issues:** 5
- **Minor Concerns:** 5
- **Epics with Issues:** 6 / 11 (E3, E6, E8, E9, E10, E11)

### Recommendations

1. **Gộp các story phụ thuộc:** 3.10a+b, 9.6a+b.
2. **Xóa/chuyển gate conditions:** 6.6, 6.7, 9.5.
3. **Tách Epic 9** thành 4 epic nhỏ hơn, hoặc chấp nhận hard ordering là kiến trúc hạng nhất và ghi rõ.
4. **Chuẩn hóa AC** cho 10.1-10.4, 11.1-11.3 theo Given/When/Then.
5. **Tách implementation notes** ra khỏi AC trong 8.11, 9.1a, 9.1b, 9.2.
6. **Làm testable** AC của 9.3.
7. **Single source of truth** cho story numbering giữa `epics.md` và `sprint-status.yaml`.

---

**PROCEEDING TO FINAL ASSESSMENT**

**Select an Option:** [C] Continue to Final Assessment

---

## Step 6: Final Assessment

### Overall Readiness Status

**NEEDS WORK**

Nowing có PRD và Epics khá đầy đủ, architecture decisions rõ ràng, và UX contract cho async deep-research đã sẵn sàng. Tuy nhiên, nhiều vấn đề nghiêm trọng về epic/story quality, FR coverage, và UX coverage khiến giai đoạn implementation chưa thể bắt đầu an toàn mà không có hành động khắc phục.

### Critical Issues Requiring Immediate Action

1. **FR-42 hoàn toàn thiếu trong Epics coverage map** — Chat Response Benchmark (mới 2026-08-04) không được map vào epic/story nào, mặc dù NFR-10 phụ thuộc nó.
2. **Epic 9 có hard ordering constraint** `9.1a → public repo → 9.1b+9.2+8-7 → 9.3 → 9.4 → 9.6a → 9.6b` — vi phạm nguyên tắc epic independence. Cần tách epic hoặc ghi rõ đây là kiến trúc hạng nhất.
3. **Forward dependencies trong stories** — 3.10b→3.10a, 9.6b→9.6a, 6.7→6.6, 6.10→6.6/6.7/6.9. Cần gộp hoặc làm story độc lập.
4. **AC không chuẩn Given/When/Then** ở stories 10.1-10.4, 11.1-11.3 — khó test và verify.
5. **Implementation details trong AC** ở 8.11, 9.1a, 9.1b, 9.2 — ràng buộc implementation thay vì behavior.
6. **AC không testable** ở 9.3 — deliverable tài liệu không phải AC.
7. **Story 3.10a là spike/forensic** — không deliver user value trực tiếp.
8. **UX coverage rất hẹp** — chỉ có contract cho 9-3; admin (FR-41), benchmark (FR-42), Phase 2 UX Overhaul, dashboard/settings/sync chưa có UX spec.

### Recommended Next Steps

1. **Bổ sung FR-42 vào epics.md** — tạo epic mới (Evals/Quality) hoặc gán vào Epic 4/10, với stories cho `chat/regression`, `chat/quality`, production query sampler.
2. **Tách hoặc ghi rõ Epic 9 ordering** — nếu hard ordering là bắt buộc, ghi thành architecture dependency sequence; nếu không, tách thành 4 epic nhỏ.
3. **Gộp các story phụ thuộc** — 3.10a+b, 9.6a+b thành single stories; xử lý 6.6/6.7/6.9/6.10.
4. **Chuẩn hóa AC** — viết lại stories 10.x, 11.x theo Given/When/Then; tách technical notes ra khỏi AC của 8.11, 9.1a, 9.1b, 9.2; làm testable AC của 9.3.
5. **Mở rộng UX specs** — viết UX cho admin global model config (FR-41), chat benchmark (FR-42), dashboard/settings, sync/offline indicator, first-run onboarding.
6. **Align status FR-15, FR-32** giữa PRD và epics.md (PRD ghi PARTIAL, epics ghi DONE).
7. **Thiết lập single source of truth** cho story numbering giữa `epics.md` và `sprint-status.yaml`.
8. **Cập nhật docs công khai** loại bỏ mention FR-5 (AI File Sorting) và FR-10 Admin role đã removed.

### Final Note

Assessment này phát hiện **hơn 20 vấn đề** xuyên suốt 5 danh mục: document inventory, PRD completeness, epic coverage, UX alignment, và epic/story quality. Phần lớn là khắc phục được nhanh (viết lại AC, bổ sung coverage map, tách technical notes). Tuy nhiên, 8 vấn đề critical cần giải quyết trước khi bắt đầu Phase 4 implementation để tránh rework, scope creep, và mất traceability.

Báo cáo hoàn thành ngày **2026-08-05**.

---

## Remediation Log (2026-08-05)

All critical and recommended issues identified above have been addressed:

| # | Issue | Status | Evidence |
|---|-------|--------|----------|
| 1 | FR-42 missing from epics.md | **FIXED** | Added to Epic 4 with stories 4.8a–4.8g; added to Functional Requirements and FR/NFR coverage map. |
| 2 | NFR-10 missing from epics.md | **FIXED** | Added to Non-Functional Requirements and coverage map; linked to 4.8b/4.8e/4.8f/4.8g. |
| 3 | Epic 9 hard ordering constraint | **FIXED** | Reframed as an architecture/deploy sequence (AD-15 §D5), not an epic-ordering constraint; other Epic 9 stories can dev in parallel. |
| 4 | Forward dependencies | **FIXED** | Merged 3.10a+b → 3.10, 9.6a+b → 9.6, 6.9+6.10 → 6.9; clarified 6.7 and 6.9 are business-gated, not technically dependent. |
| 5 | AC not Given/When/Then (10.1–10.4, 11.1–11.3) | **FIXED** | All listed stories now use Given/When/Then. |
| 6 | AC not testable (9.3) | **FIXED** | Document deliverable moved out of AC; remaining ACs are measurable. |
| 7 | Story 3.10a spike / no user value | **FIXED** | Reframed and merged into user-valued story 3.10. |
| 8 | UX coverage gaps | **FIXED** | Added UX contracts for admin global model config, chat benchmark, usage dashboard, sync/offline indicator, and first-run onboarding. |
| 9 | FR-15 / FR-32 status misalignment | **FIXED** | PRD and epics.md now both report FR-15 DONE and FR-32 PARTIAL. |
| 10 | Single source of truth for story numbering | **FIXED** | Sprint-status header documents dot vs. dash convention and the merge rule; all numbers are consistent. |
| 11 | Implementation details in AC (8.11, 9.1a, 9.1b, 9.2) | **FIXED** | Technical field names, file paths, service names, and env vars moved to `Implementation hints` / `Implementation context` sections outside AC; ACs now describe behavior. |
| 12 | Public docs mention removed FR-5 / FR-10 admin role | **FIXED** | `scripts/check-docs-drift.py` PASSED; changelog entry updated to clarify AI File Sorting was shipped and later removed; no public docs assert admin role. |

### Verification Performed

- `python3 scripts/check-docs-drift.py` — **PASSED**.
- Subagent review of `epics.md`, `sprint-status.yaml`, `prd.md`, and new UX contracts confirmed all 12 issues are resolved.

---

## Appendix: Documents Included in This Assessment

- PRD: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- Epics: `_bmad-output/planning-artifacts/epics.md`
- UX: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md` + `archive/ux-audit-improvement-spec-2026-07-27.md`

---

**Implementation Readiness Assessment Complete**
