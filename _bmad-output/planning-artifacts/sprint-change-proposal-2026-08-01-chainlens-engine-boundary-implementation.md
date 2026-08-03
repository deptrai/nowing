---
workflow: bmad-correct-course
project: Nowing
change_trigger: Nowing = Sản phẩm, ChainLens = Engine (2026-07-25)
status: adopted_by_po
mode: batch
author: BMad Correct Course Agent
---

# Sprint Change Proposal — Nowing = Sản phẩm, ChainLens = Engine

**Date:** 2026-08-01
**Project:** Nowing
**Author:** Luisphan (PO) + Mary (BA)
**Status:** ✅ ADOPTED (PO Luisphan, 2026-07-25)
**Scope:** Major — strategic pivot / cross-repo engine boundary alignment

---

## 1. Issue Summary

ChainLens đã tái định vị thành **deep-research microservice / engine** cho Nowing (SCP v4 + ADR, ADOPTED 2026-07-25). Nowing chưa đối ứng trong PRD, epics và architecture-spine:

- PRD Nowing vẫn coi ChainLens là `FR-24` — một MCP tool trong **Epic 2 "Connectors"**, ngang hàng scraper Reddit/YouTube.
- PO đã loại hướng "research app giống Perplexity + bán data giống Exa" vì thiếu owned index và GTM muscle.
- Quyết định: **OSS/PLG-led**, **Nowing = sản phẩm**, **ChainLens = engine phía sau**.

### Bằng chứng (verifiable)

- `chainlens-research/.../sprint-change-proposal-2026-07-25-v4-nowing-microservice.md` — ✅ ADOPTED.
- `chainlens-research/.../architecture/ADR-CHAINLENS-AS-NOWING-MICROSERVICE.md` — ✅ ACCEPTED.
- `chainlens-research/.../epic-26-gate-tracking.md` — 0/7 gates passing.
- NFR6 final 20.8 v2 postfix — latency/cost chưa đạt.
- Code: `CHAINLENS_QUERY_MICROS_PER_CALL` flat $0.005, `costDollars` chưa parse, chỉ timeout 300s không fallback.

---

## 2. Change Navigation Checklist

### 2.1 Understand the Trigger and Context

- [x] **Triggering issue:** SCP v4/ADR ADOPTED 2026-07-25 — ChainLens is an engine, not a product.
- [x] **Problem type:** Strategic pivot + cross-repo misalignment.
- [x] **Evidence:** PRD §4.2 FR-24, `epics.md` L68, flat cost, missing cost parse, no degradation.

### 2.2 Epic Impact Assessment

- [x] **2.1 Current epic completion:** Epic 2 (`2-4-chainlens-research-mcp-tool`) `done` — giữ nguyên lịch sử, không revert.
- [x] **2.2 Epic-level changes:** Thêm **Epic 9** "Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng"; re-bind FR-24 sang Epic 9.
- [x] **2.3 Future epics:** Epic 8 (`8-7-auto-extract-spend-budget-cap`) chạy song song 9.2; Epic 3 (`3-9-memory-recall-eval-gate`) không xung đột.
- [x] **2.4 Obsolete/new:** Không epic nào vô hiệu; cần 1 epic mới.
- [x] **2.5 Priority resequence:** `9.1a` (degradation) và `9.2` (cost metering) là P0 tiền đề trước monetization.

### 2.3 Artifact Conflict and Impact Analysis

- [x] **3.1 PRD conflicts:** §1 Vision, §2 thêm Non-Goals, §3 Glossary, §4.9 Deep-Research Engine Integration, NFR-9 Latency & Availability Budget, §6 Out of Scope.
- [x] **3.2 Architecture conflicts:** ARCHITECTURE-SPINE cần engine boundary, contract `POST /api/v1/search`, IN/OUT table, degradation path.
- [x] **3.3 UI/UX conflicts:** Không có thay đổi giao diện chính; user-facing tính năng chat với citations giữ nguyên.
- [x] **3.4 Other artifacts:** README, `docs/`, `docker/`, `.env.example` cần sync quan hệ Nowing↔engine và license.

### 2.4 Path Forward Evaluation

- [x] **4.1 Direct Adjustment:** Viable — thêm Epic 9, re-bind FR-24, cập nhật PRD/Architecture. Effort: Medium. Risk: Medium.
- [x] **4.2 Rollback:** Not viable — `2-4` đã ship và dùng làm tool, không cần revert.
- [x] **4.3 MVP Review:** Viable — MVP không thay đổi về tính năng chat/research, chỉnh framing và governance. Effort: Medium. Risk: Low.
- [x] **4.4 Selected approach:** **Hybrid** — Direct Adjustment + MVP framing update. Rationale: Giữ code đã ship, thêm governance/cost/degradation đúng tầng.

### 2.5 Sprint Change Proposal Components

- [x] **5.1 Issue summary:** Đã ghi ở §1.
- [x] **5.2 Epic/artifact impact:** Đã ghi ở §2.2–2.3.
- [x] **5.3 Recommended path:** Đã ghi ở §4.4.
- [x] **5.4 MVP impact:** MVP vẫn đạt; thêm ràng buộc P0 trước monetization.
- [x] **5.5 Agent handoff:** See §6.

### 2.6 Final Review and Handoff

- [ ] **6.1 Checklist completion:** Pending final review.
- [ ] **6.2 Proposal accuracy:** Pending final review.
- [ ] **6.3 User approval:** Pending.
- [ ] **6.4 sprint-status.yaml update:** Pending approval.
- [ ] **6.5 Handoff confirmation:** Pending approval.

---

## 3. Epic 9 — Deep Research đáng tin cậy

### Mục tiêu

Quản trị ChainLens như external deep-research dependency hạng nhất: contract ổn định, cost thật, degradation an toàn, latency budget trung thực.

| Story | Nội dung | Bind | Ưu tiên | Status |
|---|---|---|---|---|
| **9.1a** | Research degradation & self-host independence | FR-24, FR-38, AD-15 | **P0** | ready-for-dev |
| **9.2** | Cost metering thật | FR-37, AD-8, AD-15 | **P0** | ready-for-dev |
| **9.3** | Latency budget + State A/B gate | NFR-9 | **P1** | backlog |
| **9.4** | Docs sync quan hệ Nowing↔engine | AR-10, D5, AD-16 | **P1** | backlog |
| **9.5** | Metered endpoint cho self-host | D5, AD-15, AD-8 | *deferred* | backlog |
| **9.6** | Memory→scraper-run provenance & re-validation | FR-39, AD-11 | P0 nếu kể re-validation | backlog |

---

## 4. Detailed Change Proposals

### 4.1 PRD (`prd-Nowing-2026-07-22/prd.md`)

| ID | Section | Change | Rationale |
|---|---|---|---|
| P1 | §1 Vision | Thêm: Nowing = sản phẩm/bề mặt phân phối + billing/account; ChainLens = engine deep-open-web-research phía sau. Lý do trả tiền: memory + provenance + self-host/privacy + integration depth. OSS/PLG-led. | Thiếu engine boundary và "reason to pay" |
| P2 | §2.2 → **§2.4 Non-Goals** | Thêm NG-1..NG-4: không bán research data, không consumer parity, ChainLens không độc lập, giữ non-users cũ | Chống re-litigate |
| P3 | §3 Glossary | Thêm Deep-Research Engine, Research Degradation | Từ vựng chuẩn |
| P4 | §4.2 FR-24 → **§4.9** | Viết lại FR-24 thành Deep-Research Engine Integration; có contract/mode/cost/failure-mode | FR-24 sai tầng |
| P5 | §4.9 | Thêm FR-37 Cost Metering | Under-meter 2.1–3.3× |
| P6 | §4.9 | Thêm FR-38 Research Degradation & Self-Host Independence | Không có fallback |
| P7 | §5 | Thêm NFR-9 Latency & Availability Budget — State A/B | Hệ quả sản phẩm lớn nhất |
| P8 | §4.3/§5/§8 | Cập nhật FR-36, NFR-8, OQ-6 status | PRD đang báo đỏ về việc đã xong |
| P9 | §6.2 Out of Scope | Thêm standalone research-data sale; owned index; Perplexity parity | Đồng bộ AD-DEFER-7 |
| P10 | §1.1 + §4.9 | Bảng license 3 tầng; FR-38 reframe mô hình kinh doanh; FR-39 provenance | Bổ sung 2026-07-25 |

### 4.2 Epics (`epics.md`)

- Thêm **Epic 9** section ở cuối hoặc sau Epic 2.
- Re-bind FR-24 từ Epic 2 sang Epic 9.
- Epic 2 giữ `2-4 done` làm lịch sử.

### 4.3 Architecture (`ARCHITECTURE-SPINE.md`)

- Thêm **ChainLens engine boundary** section.
- IN/OUT table tương ứng ADR-CHAINLENS-AS-NOWING-MICROSERVICE.
- Contract `POST /api/v1/search` SSE, `costDollars`, terminal event.
- Degradation path: ChainLens fail → Nowing hybrid search + `partial`/`engine_unavailable`.

### 4.4 Sprint Status (`sprint-status.yaml`)

- Thêm Epic 9 entry với stories 9.1a, 9.2, 9.3, 9.4, 9.5, 9.6.
- Đánh dấu 9.1a và 9.2 `ready-for-dev` / `in-progress`.
- Cập nhật Epic 2 nếu cần cross-reference.

### 4.5 Secondary Artifacts

- `README.md`: Nowing = sản phẩm, engine hosted, self-host vs cloud.
- `docs/`: sync vision.
- `docker/`, `.env.example`: license, engine boundary.

---

## 5. Implementation Handoff

### Scope classification

- **Major** — PRD, Architecture, Epics, Sprint Status, Docs.

### Handoff recipients

| Role | Responsibility |
|---|---|
| **Product Manager / PO** | Approve PRD §1, §2.4, §4.9, NFR-9; xác nhận license và out-of-scope. |
| **Solution Architect** | Cập nhật ARCHITECTURE-SPINE với engine boundary, contract, degradation. |
| **Product Owner** | Cập nhật `epics.md` và `sprint-status.yaml` với Epic 9. |
| **Tech Writer** | Sync README, `docs/`, `.env.example`, `docker/`. |
| **Developer agents** | Implement 9.1a, 9.2, 9.3 theo thứ tự. |

### Success criteria

- PRD phản ánh rõ Nowing = product, ChainLens = engine.
- Epic 9 tồn tại với 6 stories và binding đúng.
- Architecture-spine có engine boundary và degradation path.
- `sprint-status.yaml` cập nhật.
- `9.1a` và `9.2` có thể bắt đầu dev.

---

## 6. Next Steps / Routing

1. **PO/PM review & approve** proposal này.
2. **Tech Writer / Architect agents** cập nhật PRD, Architecture, Epics, README.
3. **PO** cập nhật `sprint-status.yaml`.
4. **Route to `bmad-create-epics-and-stories`** nếu cần viết lại story 9.x chi tiết.
5. **Route to `bmad-dev-story`** cho 9.1a hoặc 9.2.

---

## 7. Approval

**Approved by:** ___________________  **Date:** ___________________

**Conditions / notes:**

---

*Generated by BMad `bmad-correct-course` — Batch mode.*
