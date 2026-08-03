# Validation Report — Nowing PRD (2026-07-22) · re-run

- **PRD:** `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- **Rubric:** `.kiro/skills/bmad-prd/assets/prd-validation-checklist.md`
- **Run at:** 2026-07-24T00:00:00 (re-validation sau update pass)
- **Grade:** Fair  *(trước đó: Poor)*

## Delta
- Critical **2 → 0** · High **5 → 1** · Medium 4 → 3 · Low 6 → 5 (rubric).
- PRFAQ coverage **0 COVERED/4 PARTIAL/6 MISSING → 9 COVERED / 1 PARTIAL / 0 MISSING**, 0 critical.
- Retention contradiction: **RESOLVED**.

## Overall verdict

Update pass nâng chất lượng PRD rõ rệt và đúng chỗ: canh bạc chiến lược nay là quyết định go/no-go tường minh (`[NOTE FOR PM]` §0); FR-32/33/34/36 có Acceptance Criteria kiểm chứng được; scope honesty siết lại; NFR-8/SM-10 thêm eval gate chất lượng recall (đã verify `nowing_evals` có thật). Hai high rubric-level trước đã resolved; Decision-readiness lên strong.

Coverage PRFAQ: 9 COVERED / 1 PARTIAL / 0 MISSING (từ 0/4/6 + 2 critical) → reviewer tuyên bố **PROCEED** xuống architecture/epics; cả 2 crack đỏ đóng bằng requirement trước-ship (FR-36 + NFR-8); contradiction retention resolved.

**Vì sao Fair chứ chưa Good:** verify code lộ 1 high mới (SF-1) — FR-36 giả định cột markdown-memory cũ còn để migrate, nhưng migration `178_drop_legacy_memory_columns.py` đã DROP đúng hai cột đó (nhận thức migration của PRD dừng ở 172). Đóng SF-1 là việc duy nhất giữa Fair và Good.

## Dimension verdicts
- Decision-readiness — strong ↑ (từ adequate)
- Substance over theater — adequate
- Strategic coherence — adequate
- Done-ness clarity — adequate (prior high resolved)
- Scope honesty — strong
- Downstream usability — strong
- Shape fit — adequate ↓ (từ strong — verify code lộ SF-1)

## Findings by severity

### Critical (0)
Không còn.

### High (1)
**[Shape fit]** — SF-1: FR-36 không đối soát với migration `178_drop_legacy_memory_columns.py` (§4.3 FR-36 + §0 [NOTE FOR PM])
178 (upgrade) DROP `memory_md`/`shared_memory_md` — đúng hai cột FR-36 giả định còn để migrate; PRD chỉ biết tới migration 172.
Fix: cite 178 + xác định đã-apply-prod hay chưa; nếu chưa → gate/hoãn 178 tới khi migrate Memory + verify; nếu rồi → chuyển FR-36 sang "khôi phục/đánh giá mất mát từ backup".

### Medium (3)
**[Strategic]** — Lệch identity + SM-1 activity-metric, metric-thesis (SM-8/10) nằm trên FR chưa build (§1/§4/§7). Fix: framing "memory bổ sung vào platform" vào §1; nâng SM-8/10 lên primary + baseline khi build xong.
**[Done-ness]** — FR-22 "podcast dưới 20 giây" mơ hồ (§4.5). Fix: nêu rõ ngữ nghĩa.
**[Shape fit]** — `[GAP]` FR-32 undercount surface memory hiện có (`memory_routes.py`/`team_memory_routes.py`/`read_memory`/`MemoryScope`) (§4.3). Fix: sửa câu "hiện chỉ có Document/Chunk/Chat…".

### Low (8)
**[Decision-readiness]** — OQ-5 + assumption write-back thiếu `[NOTE FOR PM]` (§8/§9).
**[Substance]** — NFR-6/7 vẫn feature-gap dán nhãn NFR (nay tự-flag) (§5).
**[Substance]** — NFR-1 bound mơ hồ (§5).
**[Scope honesty]** — Open-items density cao; tách build-ready khỏi cần-spec (§6.1).
**[Downstream]** — UJ-4 protagonist generic (§2.3).
**[PRFAQ-gap]** — F1 Success metrics chưa định lượng (item 8, PARTIAL) (§7).
**[PRFAQ-gap]** — F2 Legal/retention vẫn là OQ, chưa có policy nội dung (OQ-3).
**[PRFAQ-gap]** — F3 Vision đoạn 2 liệt kê "everything" làm loãng wedge (§1).

## Mechanical notes
- Migration lineage staleness load-bearing: glossary cite ~172, repo ≥178 (liên quan SF-1) — refresh danh sách migration.
- Verify facts: `nowing_evals` tồn tại (NFR-8 hợp lệ); `epics.md` không tồn tại (OQ-6 đúng); `memory_md`/`shared_memory_md` tồn tại nhưng có migration 178 (→ SF-1).
- FR 1–36 đủ/unique; "Chỉ mục FR" bù thứ tự. SM-1..10 + counter contiguous.
- Assumptions Index index-only + mục `[CORRECTED 2026-07-24]` strikethrough hợp lệ.

## Reviewer files
- `review-rubric.md`
- `review-prfaq-gap.md`
