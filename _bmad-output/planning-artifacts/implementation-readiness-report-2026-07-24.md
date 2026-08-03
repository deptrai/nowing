---
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
documentsUsed:
  - "prds/prd-Nowing-2026-07-22/prd.md (PRD)"
  - "architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md (Architecture)"
  - "epics.md (Epics & Stories)"
uxStatus: "MISSING — ux-designs/ux-Nowing-2026-07-22/ chỉ có scaffold rỗng, không DESIGN.md/EXPERIENCE.md"
contextDocs:
  - "prfaq-Nowing.md + prfaq-Nowing-distillate.md"
  - "sprint-change-proposal-2026-07-22.md + -vision-pivot.md"
---

# Implementation Readiness Assessment Report

**Date:** 2026-07-24
**Project:** Nowing

## Step 1 — Document Inventory

### PRD
- **Whole:** `prds/prd-Nowing-2026-07-22/prd.md` ✅ (đã reality-correct 2026-07-24)
- Sharded: không có. **Duplicate: không.**

### Architecture
- **Whole:** `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` ✅
- Sharded: không có. **Duplicate: không.**
- ⚠️ Lưu ý: spine đề 2026-07-22 (mô tả memory là *target/planned*); code (mig 177–179) landing sau → **nghi ngờ lệch với reality-correction** — sẽ kiểm ở bước phân tích.

### Epics & Stories
- **Whole:** `epics.md` ✅ (taxonomy E1–E8; 12 gap-stories có AC)
- Sharded: không có. **Duplicate: không.**

### UX Design
- ⚠️ **MISSING** — `ux-designs/ux-Nowing-2026-07-22/` chỉ có `.working/` + `imports/` rỗng, không có `DESIGN.md`/`EXPERIENCE.md`/index.
- Đánh giá: chấp nhận được cho MVP-critical path (không UI-heavy); nhưng các story có UI (3.6 citation jump, 8.3 dashboard) sẽ thiếu UX contract — ghi nhận rủi ro.

### Context (không phải 4 doc lõi, dùng để đối chiếu)
- `prfaq-Nowing.md` + `-distillate.md` (vision + requirements signals)
- `sprint-change-proposal-2026-07-22.md` + `-vision-pivot.md` (nguồn taxonomy epic + pivot)

## Issues Found
- **Duplicates:** Không có. ✅
- **Missing:** UX design contract (WARNING — chấp nhận cho MVP, flag cho story UI).
- **Cần kiểm ở bước sau:** độ đồng bộ Architecture spine ↔ code đã build (reality-correction).


## Step 2 — PRD Analysis

Nguồn: `prds/prd-Nowing-2026-07-22/prd.md` (reality-corrected 2026-07-24). Trạng thái: `[DONE]` đã có code · `[PARTIAL]` · `[GAP]` · `[REMOVED]`.

### Functional Requirements (36; FR-5 removed → 35 active)
- FR-1 User Authentication `[DONE]`
- FR-2 API Access for External Clients (PAT/API key) `[DONE]`
- FR-3 Workspace Lifecycle `[DONE]`
- FR-4 Workspace Invites & Memberships `[DONE]`
- FR-10 RBAC 3 system roles (Owner/Editor/Viewer; Admin removed mig 72) `[DONE]`
- FR-6 Built-in Scraper Connectors `[DONE]`
- FR-7 External OAuth Connectors `[DONE]`
- FR-8 External MCP Connectors `[DONE]`
- FR-24 ChainLens Research MCP Tool `[DONE]`
- FR-9 Document Upload, Parse & Index (50+ formats) `[DONE]`
- FR-11 Folders & Document Management `[DONE]`
- FR-12 Hybrid Search over KB `[DONE]`
- FR-13 Citation Panel for KB Chunks `[DONE]`
- FR-32 Long-Term Research Memory (Memory/versions/relations, hybrid, confidence) `[DONE core; PARTIAL dedupe-tune/recall-quality]`
- FR-33 Research Continuity (ResearchThread, nowing_continue_research) `[DONE]`
- FR-34 Memory Correction (memory_versions, PATCH, nowing_update_fact) `[DONE]`
- FR-36 Legacy Memory Data-Loss Assessment & Recovery `[GAP]`
- FR-5 AI File Sorting `[REMOVED]` (mig 172)
- FR-14 Chat Threads & Messages `[DONE]`
- FR-15 Multi-agent Runtime with Tools (+ auto-extract mig 179) `[DONE]`
- FR-16 Real-time Collaborative Chat `[DONE]`
- FR-17 Anonymous Chat with Quota `[DONE]`
- FR-21 Report Generation & Export `[DONE]`
- FR-22 Podcast & Video Presentation `[DONE]` (ràng buộc "20 giây" mơ hồ)
- FR-23 Image Generation `[DONE]`
- FR-18 Automation Action Types (agent_task done; direct write-back missing) `[PARTIAL]`
- FR-19 Automation Triggers `[DONE]`
- FR-20 Automation Runs & Retries `[DONE]`
- FR-35 Memory-Driven Automations `[GAP, post-MVP]`
- FR-25 Web Client / FR-26 Desktop / FR-27 Extension / FR-28 Obsidian `[DONE]`
- FR-29 MCP Server (scraper/KB/memory/research; 4 memory tools) `[DONE]`
- FR-30 Token Usage Tracking `[DONE]`
- FR-31 Credit Wallet & Purchases (dashboard missing) `[DONE; dashboard GAP]`

**Total FRs:** 36 (35 active + FR-5 removed).

### Non-Functional Requirements (8)
- NFR-1 Performance (API<500ms CRUD; bounds "limit phù hợp"/scraper "vài giây" mơ hồ) `[PARTIAL]`
- NFR-2 Security & Auth (JWT/cookie/PAT, per-endpoint permission) `[DONE]`
- NFR-3 Observability (OpenTelemetry, Log, SlowAPI, Celery) `[DONE]`
- NFR-4 Reliability (async DB, Celery+Redis, retry) `[DONE]`
- NFR-5 Multi-tenancy Isolation (workspace_id filter) `[DONE]`
- NFR-6 Citation Full-Editor Highlight (jump-to-source) `[GAP]`
- NFR-7 Usage & Credit Dashboard `[GAP]`
- NFR-8 Recall Quality (eval-gated, nowing_evals, precision@k/noise, ship-gate) `[GAP]`

**Total NFRs:** 8.

### Additional Requirements / Constraints
- Open Questions: OQ-1 MCP marketplace, OQ-2 agent-tool default toggle, OQ-3 retention/right-to-delete/legal, OQ-4 per-workspace MCP tool toggle, OQ-5 write-back architecture, OQ-6 docs/epics sync.
- Assumptions (§9): self-host billing off; MCP no per-workspace toggle v1; agent_task đủ thay write-back; `[CORRECTED]` retention = legal (trước GA cloud); `[CONFIRMED]` memory pgvector no graph-DB, 4 MCP tools exposed, memory_versions correction.
- Success Metrics SM-1..SM-10 + counter SM-C1/C2 — **nhiều target còn placeholder "≥ X%"** (chưa định lượng).

### PRD Completeness Assessment
- **Mạnh:** FR/NFR đánh số toàn cục, unique; traceability SM→FR; trạng thái `[BUILT]`/`[GAP]` rõ; brownfield refs (migration/model/path) cụ thể; `[NOTE FOR PM]` đóng khung reality.
- **Yếu (đã biết từ validate, grade Fair):** SM targets chưa định lượng (RS-7); NFR-1 bounds mơ hồ; NFR-6/7 là feature-gap dán nhãn NFR; SF-1 lineage (glossary cite ~172, code ≥179) — cần đảm bảo đã sửa.
- **Kết luận:** PRD đủ để làm nguồn traceability cho IR (đã qua validate Fair + reality-correct).


## Step 3 — Epic Coverage Validation

Nguồn: `epics.md` §FR Coverage Map + §Epic sections, đối chiếu FR list ở Step 2.

### Coverage Matrix (gộp theo nhóm)

| FR | Trạng thái PRD | Epic coverage | Kết quả |
|---|---|---|---|
| FR-1,2,3,4,10 | DONE | E1 (baseline) | ✓ |
| FR-6,7,8,24 | DONE | E2 (baseline) | ✓ |
| FR-9,11,12,13 | DONE | E3 (baseline) | ✓ |
| FR-14,15,16,17 | DONE | E4 (baseline) | ✓ |
| FR-21,22,23 | DONE | E5 (baseline) | ✓ |
| FR-19,20 | DONE | E6 (baseline) | ✓ |
| FR-25,26,27,28,29 | DONE | E7 (baseline) | ✓ |
| FR-30 | DONE | E8 (baseline) | ✓ |
| FR-32 | DONE core / PARTIAL | E3 (3.8 done; 3.9 eval, 3.11 dedupe) | ✓ |
| FR-33 | DONE | E4 (4.6) | ✓ |
| FR-34 | DONE | E3/E4 | ✓ |
| FR-36 | GAP | **E3.10** (data-loss, P0) | ✓ |
| FR-18 | PARTIAL | **E6.4** (write-back) | ✓ |
| FR-31 | dashboard GAP | **E8.3** | ✓ |
| FR-35 | GAP post-MVP | **E6.5** | ✓ |
| FR-5 | REMOVED | — | ✓ (đúng, không cần story) |

### NFR Coverage
| NFR | Epic coverage | Kết quả |
|---|---|---|
| NFR-2,3,4,5 | baseline (DONE) | ✓ |
| NFR-6 | E3.6 (citation jump) | ✓ |
| NFR-7 | E8.3 (dashboard) | ✓ |
| NFR-8 | **E3.9 (eval-gate)** | ✓ |
| NFR-1 Performance | — không story riêng | ⚠️ minor (che bởi NFR-3 observability; khuyến nghị chốt p95 khi chạm) |

### Missing Requirements
- **FR uncovered: KHÔNG.** Mọi FR có đường truy vết tới epic/story (hoặc `[REMOVED]`).
- **FR trong epics mà không có trong PRD: KHÔNG.**
- **Minor:** NFR-1 (performance bounds) chưa có story chuyên trách — accept (quality attribute; đề nghị định lượng p95 khi làm story chạm hiệu năng).

### Coverage Statistics
- Total PRD FRs: **36** (35 active + FR-5 removed).
- FRs covered in epics: **36 (100%)**.
- NFRs: 8; covered 7 đầy đủ + NFR-1 partial (no dedicated story). **NFR coverage ~94% (7/8 có story/baseline; NFR-1 accept).**
- **Kết luận Step 3: PASS** — traceability đầy đủ, không FR mồ côi.


## Step 4 — UX Alignment Assessment

### UX Document Status
**NOT FOUND** — `ux-designs/ux-Nowing-2026-07-22/` chỉ có `.working/` + `imports/` rỗng; không có `DESIGN.md`/`EXPERIENCE.md`/index.

### UX có được hàm ý không? — CÓ (một phần)
- Nowing **đã có UI client shipped**: web (Next.js), desktop (Electron), extension (Plasmo), Obsidian → là sản phẩm user-facing, patterns UI đã tồn tại trong `nowing_web/`.
- **Story GAP có UI mới:** 3.6 citation jump-to-source (full editor highlight), 8.3 usage/credit dashboard. Hai story này **thực sự cần UX**.

### Alignment Issues
- UX ↔ PRD / UX ↔ Architecture: **N/A** — không có UX doc để đối chiếu.
- Không phát hiện mâu thuẫn (vì không có UX artifact), nhưng có **khoảng trống**: 3.6 và 8.3 thiếu UX contract.

### Warnings
- ⚠️ **WARNING (scoped, không phải blocker toàn cục):** thiếu UX design contract cho **Story 3.6** (citation jump-to-source) và **Story 8.3** (usage/credit dashboard). Trước khi build 2 story này nên: (a) tạo UX spec nhẹ qua `bmad-ux`, HOẶC (b) bám pattern UI có sẵn trong `nowing_web/` (brownfield — đã có editor + settings pages).
- ✅ **KHÔNG chặn MVP-critical path:** P0 (3.10 data-loss, 8.4 cost) + ship-gate (3.9 eval) + 3.11/3.12/8.4/8.5/8.6/6.4 đều là **backend/eval/ops**, không cần UX.
- Kết luận: UX gap là **rủi ro có kiểm soát**, giới hạn ở 2 story UI, xử lý được khi tới lượt.


## Step 5 — Epic Quality Review

Đối chiếu `epics.md` với best practices của create-epics-and-stories.

### Compliance checklist (E1–E8)
- [x] **User value, không phải technical milestone** — E1 Auth … E8 Platform Ops đều là domain năng lực/giá trị user; KHÔNG có epic kiểu "Setup DB"/"API Development". *(Bản nháp sai "Epic 1: Stop-the-Bleed" đã bị gỡ — nếu còn sẽ là vi phạm technical-milestone.)*
- [x] **Epic independence** — epic `[DONE]` độc lập; việc còn lại là story trong E3/E8/E2/E6, không epic nào cần epic tương lai.
- [x] **No forward dependency** — đã gỡ 3.9→3.10 (hard-dep → priority-coordination); còn lại backward hợp lệ (3.11 gắn 3.9; 8.5 gắn 8.4).
- [x] **DB/entity tạo khi cần** — memory tables đã có (177); story mới chỉ tạo cái nó cần (3.10 migration backfill, 8.4 config, 3.9 dataset). Không tạo bảng upfront.
- [x] **Brownfield-appropriate** — không có greenfield setup story sai; story là integration/migration/hardening.
- [x] **AC Given/When/Then + edge cases** — có nhánh lỗi (recovery-impossible, no-match fallback, anonymous-chat attribution).
- [x] **Traceability tới FR** — duy trì (Step 3: 100% FR).

### Findings by severity

**🔴 Critical:** KHÔNG. (Không technical-milestone epic; không hard forward-dep; không epic-sized story không thể hoàn thành.)

**🟠 Major (nên xử trước khi dev, không chặn cứng):**
- **Story sizing — vài story đa-concern, nên tách để vừa 1 dev-session:**
  - **3.10** (forensic 178 + freeze backup + backfill + recovery-impossible branch + bridge parity) → tách **3.10a "Data-safety spike"** (forensic + freeze backup, P0, giờ/ngày) khỏi **3.10b "Recovery/backfill"** (phụ thuộc kết quả 3.10a).
  - **8.4** (kill-switch + budget cap + wallet pre-check + rate-limit + default policy) → tách **8.4a "Kill-switch + default OFF"** (P0, nhanh, chặn bleed ngay) khỏi **8.4b "Budget cap + wallet pre-check + rate-limit"** (lớn hơn).
  - **3.7** (retention + right-to-delete + cascade + self-host/cloud split + export + legal review) → cân nhắc tách legal-review (external dep) khỏi delete-path engineering.
- **E8 naming** "Platform Operations" hơi thiên kỹ thuật — có thể đổi "Billing & Usage Transparency" cho user-value rõ hơn (tùy chọn).

**🟡 Minor:**
- NFR-1 (performance bounds) chưa có story riêng (accept; che bởi NFR-3).
- 3.9 để ngưỡng SM-10 "chốt sau baseline" — hợp lý ở spec, cần track không để trôi thành placeholder.
- UX contract thiếu cho 3.6/8.3 (Step 4).
- Story `[DONE]` không kèm AC — có chủ đích (đã implement), không tính defect.

### Remediation
- Tách 3.10/8.4 (và tùy chọn 3.7) khi tạo story chi tiết (bmad-create-story) hoặc ngay bây giờ — để P0 spike (3.10a, 8.4a) bốc được độc lập, chặn thiệt hại sớm.
- Còn lại: chấp nhận, xử khi tới lượt.

**Kết luận Step 5: PASS (có Major sizing cần tách, không có Critical).**


## Summary and Recommendations

### Overall Readiness Status: 🟢 **READY — CÓ ĐIỀU KIỆN**

Planning artifacts (PRD ↔ Architecture ↔ Epics) **đồng bộ và khả thi để implement**. Không có Critical blocker ở tầng tài liệu: FR coverage 100%, epic quality PASS, traceability đầy đủ. Điều kiện còn lại là *thao tác/tách story*, không phải lỗ hổng planning.

### Điểm mạnh
- FR coverage **100%** (36/36; FR-5 removed hợp lệ); không FR mồ côi, không forward-dependency, epic độc lập.
- Trạng thái `[BUILT]`/`[GAP]` chính xác sau reality-correction; brownfield refs cụ thể.
- **Architecture ↔ code: ALIGNED** — AD-11..14 (memory/MCP/research-thread/auto-extract) mô tả đúng thứ đã build (mig 177–179). Spine không "sai", chỉ nên thêm marker `[REALIZED]` (gộp vào Story 8.6 docs-sync).

### Critical Issues Requiring Immediate Action
- **KHÔNG có Critical ở tầng tài liệu.**
- ⚠️ **1 blocker NGOÀI phạm vi tài liệu (bạn/ops):** xác nhận **migration 178 đã apply prod chưa + backup còn phủ trước-178 không** — *time-sensitive* (cửa sổ backup), quyết định nhánh Story 3.10. Không skill nào thay được.

### Major (xử khi story-prep, không chặn cứng)
1. Tách story P0 đa-concern: **3.10 → 3.10a** (forensic+freeze backup, P0 spike) **/ 3.10b** (recovery); **8.4 → 8.4a** (kill-switch+default OFF, P0 nhanh) **/ 8.4b** (budget cap+wallet). Cân nhắc tách legal khỏi 3.7.
2. UX spec nhẹ cho **3.6** (citation jump) & **8.3** (dashboard) trước khi build UI (hoặc bám pattern `nowing_web/`).

### Minor
- NFR-1 chốt p95 khi chạm hiệu năng; SM-10 chốt số sau baseline (đừng để trôi); thêm `[REALIZED]` vào spine ADs.

### Recommended Next Steps
1. **NGAY:** hỏi ops trạng thái **178 + backup** (gate 3.10).
2. **Sprint Planning (`bmad-sprint-planning`)** — sinh sprint plan; đưa P0 (3.10a, 8.4a) lên đầu.
3. **Story cycle:** `bmad-create-story` (tách 3.10/8.4 lúc này) → `bmad-dev-story` → `bmad-code-review`.
4. Fast-path tùy chọn: chặn cháy ngay bằng `bmad-dev-story` cho **8.4a** (kill-switch) song song sprint planning.

### Final Note
Assessment tìm thấy **0 Critical (tài liệu) · 2 Major (story sizing, UX) · vài Minor · 1 blocker ngoài-tài-liệu (ops 178/backup)** trên 5 nhóm kiểm. Có thể tiến sang Phase 4 (Sprint Planning) ngay; xử P0 spike sớm để chặn rủi ro prod đang chạy.

**Assessor:** John (PM) · **Date:** 2026-07-24


---

## Post-IR Resolution (2026-07-24)

Đã xử ngay các Major từ IR (không đẩy sang sprint-prep):
- ✅ **Tách story P0:** `3.10 → 3.10a` (data-safety spike: forensic 178 + freeze backup, P0, Dep:none) + `3.10b` (recovery/backfill, Dep:3.10a). `8.4 → 8.4a` (kill-switch + default OFF, P0, Dep:none) + `8.4b` (budget cap + wallet pre-check + rate-limit, Dep:8.4a). → mỗi story vừa 1 dev-session, P0-part bốc độc lập được.
- ✅ **UX nhẹ (brownfield):** thêm UX Notes cho `3.6` (bám `citation-panel.tsx` + mở rộng `editorPanelAtom`) và `8.3` (bám settings/buy-credits page trong `nowing_web/`). Cần contract đầy đủ → `bmad-ux`.
- ✅ Cập nhật cross-refs (epic list, P0/order, coverage map, dòng phối hợp 3.9) — verified nhất quán, không ref cũ.

**Còn lại (không chặn):** blocker ops **178/backup** (việc của bạn); minor (NFR-1 p95, SM-10 số, spine `[REALIZED]` markers). **Readiness: 🟢 READY** — sẵn sàng Sprint Planning.
