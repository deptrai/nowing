---
title: "PRD Review — PRFAQ Coverage Gap Analysis: Nowing (RE-CHECK sau cập nhật)"
type: review
scope: "PRFAQ re-evaluation coverage re-check (critique only, no PRD edits)"
reviewer: "prfaq-gap reviewer"
created: "2026-07-24"
updated: "2026-07-24"
revalidation: true
prior_result: "0 COVERED / 4 PARTIAL / 6 MISSING · 2 critical · 1 contradiction (unresolved)"
targets:
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
sources:
  - "_bmad-output/planning-artifacts/prfaq-Nowing.md"
  - "_bmad-output/planning-artifacts/prfaq-Nowing-distillate.md"
---

# PRD Review — PRFAQ Coverage Gap (RE-CHECK): Nowing

## Overall verdict

Bản PRD cập nhật (2026-07-24, sau PRFAQ re-evaluation) đã **nội hoá thực chất** các findings then chốt của PRFAQ — đây là bước nhảy lớn so với vòng trước. Trong 10 mục kiểm: **9 COVERED / 1 PARTIAL / 0 MISSING**, không còn mục critical nào. **Cả hai crack đỏ đã được đóng bằng requirement ràng buộc trước-ship**: migration path markdown-memory → `Memory` giờ là **FR-36** (có acceptance criteria "TRƯỚC-SHIP", gate không-bật-memory-mới-cho-user-hiện-hữu-khi-chưa-migrate, và đường rollback); recall-quality eval gate giờ là **NFR-8** (đo precision@k/noise trên `nowing_evals`, "không ship nếu chưa đạt") kèm metric chất lượng riêng **SM-10** tách khỏi các metric đếm volume (SM-7/8/9). Ba crack cam cũng đã xử lý: **dedupe + `confidence`** thành acceptance criteria MVP trong **FR-32**; **legal/retention/right-to-delete** được reframe đúng là rủi ro *pháp lý* (không phải storage) tại **OQ-3** với gate "trước GA cloud" và tách self-host vs cloud; **kỷ luật MVP "semantic facts first"** được KHOÁ tường minh (FR-32 + §6.1) với `MemoryRelation` giới hạn "tối giản, KHÔNG graph traversal" và auto-extract bị defer rõ ràng. Ngoài ra, **beachhead sequencing** (agent-builder OSS/MCP → team cloud) và **stale-artifacts flag** (OQ-6: README/docs/project-overview pre-pivot + `epics.md` chưa tồn tại) đã được thêm. Điểm còn lại duy nhất là **success metrics vẫn ở dạng placeholder** ("≥ X%") — nay đã được thừa nhận công khai bằng một `[NOTE]` và gắn điều kiện "chốt số trước khi dùng làm thước đo launch", nhưng chưa định lượng (severity thấp, có thể instrument trước). **Kết luận:** PRD giờ **đủ điều kiện đưa xuống architecture/epics**; residual còn lại không phải blocker downstream. So với vòng trước (Poor: 2 critical, 5 high, 1 contradiction), đây là chuyển biến từ "chưa nên cam kết" sang "PROCEED".

## Coverage table (RE-CHECK)

| # | Item (PRFAQ finding) | Verdict | PRD location | Severity | Note (delta vs prior) |
|---|---|---|---|---|---|
| 1 | Migration path markdown-memory (`User.memory_md`, `Workspace.shared_memory_md`) → `Memory` | **COVERED** | **FR-32** Gap (thừa nhận hệ markdown-memory cũ) + **FR-36** "Memory Migration & Data Safety" (AC TRƯỚC-SHIP: script migrate `source=legacy_md`, đọc song song sau flag, gate không-bật-khi-chưa-verify, rollback về `memory_md`); nhắc lại ở **[NOTE FOR PM]** + §6.1 | resolved | 🔴→✅ **Crack 1 đóng.** Prior MISSING/critical: PRD trước không thừa nhận `memory_md` tồn tại. Nay là FR chuyên biệt + `feature flag memory_v2_enabled` + verify job. Vẫn `[GAP]` = chưa build (đúng trạng thái), nhưng requirement đã đầy đủ |
| 2 | Recall-quality eval gate `nowing_evals` + precision threshold trước ship | **COVERED** | **NFR-8** "Recall Quality (eval-gated) — điều kiện TRƯỚC-SHIP" (precision@k + noise trên `nowing_evals`, "không ship nếu chưa đạt") + **SM-10** (ship-gate metric) + **[NOTE FOR PM]** điều kiện #2 + §6.1 | resolved | 🔴→✅ **Crack 2 đóng.** Prior MISSING/critical: `nowing_evals` không xuất hiện. Nay có NFR ràng buộc + metric chất lượng tách khỏi SM-7/8/9 (volume). Ngưỡng cụ thể "chốt cùng SM-10" — chấp nhận được ở tầng PRD |
| 3 | Dedupe + confidence threshold từ MVP | **COVERED** | **FR-32** Acceptance Criteria (MVP): `confidence` (0–1), dedupe cosine ≥ ngưỡng → merge/append, "không Memory nào ghi mà thiếu `source` hoặc `confidence`"; §6.1 "semantic facts + confidence + dedupe" | resolved | 🟠→✅ **Crack 5 đóng.** Prior MISSING/high: FR-32 không có `confidence`/dedupe. Nay là AC bắt buộc trong MVP scope |
| 4 | Legal/retention + right-to-delete cho scraped data dài hạn; self-host vs cloud split | **COVERED** | **OQ-3** reframed "retention KHÔNG chỉ là storage" (ToS/bản quyền/PII, right-to-delete, tách self-host/cloud, "chốt TRƯỚC GA cloud") + **§9 `[CORRECTED 2026-07-24]`** gạch bỏ assumption cũ | low (residual) | 🟠→✅ **Crack 4 đóng + contradiction RESOLVED.** Prior PARTIAL/high: chỉ chạm retention document/storage. Nay khung pháp lý đúng, right-to-delete + self-host/cloud split đủ. **Residual:** vẫn là OQ (chưa có policy cụ thể) — hợp lý vì cần legal review; PRD đã set gate đúng |
| 5 | Wedge (research-memory + provenance + live data, Framing B) + primary customer designated + MCP as surface | **COVERED** | §1 Vision (wedge + citations + live data + MCP-as-surface); **§2.1 `[Beachhead — ưu tiên]`** chỉ định "Primary v1 = AI agent builder + team; researcher/analyst + self-hoster = secondary" | low (residual) | 🟡→✅ Prior PARTIAL/medium: personas liệt kê phẳng, không chỉ primary. Nay Beachhead note chỉ định rõ. **Residual nhỏ:** Vision đoạn 2 vẫn liệt kê "workspace + deliverables + automations + đa client" hơi loãng wedge (stylistic, không blocker) |
| 6 | Stale artifacts (README/docs/project-overview pre-pivot; `epics.md` thiếu) được flag | **COVERED** | **OQ-6** "Đồng bộ docs & artifacts với vision mới" (README/`docs/`/`project-overview.md` pre-pivot "NotebookLM alternative"; `epics.md` "chưa tồn tại") + nhắc lại ở **[NOTE FOR PM]** | resolved | 🟠→✅ **Crack 3 đóng.** Prior PARTIAL/medium: chỉ flag lẻ RBAC + AI file sort. Nay OQ-6 flag đúng staleness tầm-vision + `epics.md` thiếu |
| 7 | Auto-extract cost control (per-workspace enable + budget, không default-on) | **COVERED** | **FR-15 "Fast-follow (KHÔNG thuộc MVP)"**: auto-extract "per-workspace opt-in + có ngân sách token, KHÔNG default-on... theo dõi qua SM-C2" + **§6.2** `[GAP]` lặp lại điều kiện; SM-C2 counter-metric | resolved | 🟡→✅ Prior MISSING/medium: `MemoryExtractionService`/AD-14 không xuất hiện. Nay điều kiện control chi phí ghi tường minh + gắn SM-C2 |
| 8 | Success metrics quantified vs placeholders | **PARTIAL** | §7: SM-3 & SM-8 vẫn literal "≥ X%"; SM-1/2/4/5/6/7/9 vẫn không có target; **`[NOTE]`** thừa nhận "targets là placeholder... phải chốt số trước khi dùng làm thước đo launch" | low | 🟡 Prior MISSING/low → PARTIAL. **Chưa định lượng** (substantive ask chưa xong), nhưng nay minh bạch bằng NOTE + gate pre-launch. Impact downstream thấp (instrument trước, chốt số sau). Điểm residual duy nhất |
| 9 | MVP discipline: semantic facts first + 4 MCP tools là boundary; auto-extract/relations/UI/decay deferred | **COVERED** | **FR-32 "Phạm vi MVP (KHOÁ): chỉ semantic facts (một memory type)... Defer: relation graph phong phú (`MemoryRelation` tối giản, KHÔNG graph traversal), auto-extract, memory type khác"**; **FR-15** (recall on-demand MVP; auto-recall/extract fast-follow); §6.1 (4 tools IN) + §6.2 (decay/TTL/contradiction + UI + relation traversal OUT) | resolved | 🟠→✅ Prior PARTIAL/high. Cả 3 mối lo cũ đóng: (a) "semantic facts first" nay tường minh; (b) auto-extract defer rõ; (c) `MemoryRelation` được scope "tối giản, KHÔNG traversal" — gỡ tension prior |
| 10 | Beachhead sequencing agent-builder → team tường minh | **COVERED** | **§2.1 `[Beachhead]`**: "Thứ tự rollout: agent-builder (OSS/MCP) → team (cloud)" | resolved | 🟡→✅ Prior MISSING/medium: không có ordering. Nay sequencing rõ ràng. **Residual nhỏ:** UJ-1..UJ-7 vẫn liệt kê không theo thứ tự ưu tiên, nhưng ý định rollout đã rõ |

**Tổng RE-CHECK: COVERED 9 (items 1,2,3,4,5,6,7,9,10) · PARTIAL 1 (item 8) · MISSING 0**

## Trạng thái contradiction (PRD ↔ PRFAQ)

- **[Item 4 — trực tiếp] Retention "storage-defer" ↔ "legal-before-GA": ĐÃ RESOLVED. ✅**
  - Prior: §9 `[ASSUMPTION]` khung retention là "storage chưa cấp bách, defer sau MVP" — trái PRFAQ IQ9/Crack 4.
  - Nay: §9 ghi `[CORRECTED 2026-07-24]` **gạch bỏ** (`~~...~~`) assumption cũ và thay bằng: *"Retention là vấn đề pháp lý (ToS/bản quyền/PII cho dữ liệu scrape lưu dài hạn), không chỉ dung lượng; phải chốt retention + right-to-delete + self-host/cloud split TRƯỚC GA cloud (xem OQ-3)."* OQ-3 cũng mang đúng framing pháp lý.
  - ⇒ Không còn hạ-cấp rủi ro pháp lý thành mối lo dung lượng. Tín hiệu "chốt trước GA cloud" được khôi phục ở cả OQ-3 lẫn §9.
- **[Item 9 — tension nhẹ prior] `MemoryRelation` trong MVP ↔ "relation graph = fast-follow": ĐÃ GỠ. ✅** FR-32 nay ghi rõ `MemoryRelation` "chỉ tồn tại ở mức tối giản trong MVP, KHÔNG xây graph traversal", và §6.2 liệt "relation graph traversal phong phú = fast-follow". Không còn nguy cơ epics kéo relation graph vào MVP.

**Không phát hiện contradiction mới nào phát sinh từ bản cập nhật.**

## Findings — ordered by severity

### 🟡 Low (residual — không blocker downstream)

1. **F1 (Item 8) — Success metrics chưa định lượng.** SM-3/SM-8 còn "≥ X%"; SM-1/2/4/5/6/7/9 chưa có target số. PRD nay thừa nhận công khai bằng `[NOTE]` và gắn điều kiện chốt số trước launch — minh bạch nhưng **quantification vẫn chưa làm**. *Đề xuất (không sửa ở đây):* chốt số baseline khi có dữ liệu beta; có thể instrument trước. Đây là mục PARTIAL duy nhất.

2. **F2 (Item 4 — residual) — Legal/retention vẫn ở dạng Open Question, chưa có policy cụ thể.** OQ-3 đã reframe đúng + set gate "trước GA cloud", nhưng chưa có FR/NFR/policy ràng buộc nội dung retention/right-to-delete. Hợp lý ở tầng PRD (cần legal review để soạn policy thật), nhưng cần theo dõi để không trôi qua GA cloud. *Đề xuất:* nâng thành NFR/policy có nội dung trước mốc GA cloud.

3. **F3 (Item 5 — residual) — Vision đoạn 2 vẫn liệt kê "everything" làm loãng wedge.** Primary customer đã được chỉ định (Beachhead note), nhưng đoạn 2 §1 tái liệt kê workspace + deliverables + automations + đa client — đúng kiểu framing mà PRFAQ đã reject dẫn đầu. Thuần stylistic, ưu tiên thấp. *Đề xuất:* tiết chế đoạn 2 để wedge (memory có nguồn + live data) nổi rõ hơn.

### ✅ Resolved since prior validation (delta chi tiết — chứng minh coverage thật, không giả định)

- **F(prior-critical-1) → RESOLVED:** Migration path (Item 1) nay là **FR-36** với AC trước-ship + gate + rollback + `feature flag memory_v2_enabled`. Prior "vắng hoàn toàn".
- **F(prior-critical-2) → RESOLVED:** Recall eval gate (Item 2) nay là **NFR-8** + **SM-10** trên `nowing_evals`. Prior "vắng hoàn toàn".
- **F(prior-high-3, Item 9) → RESOLVED:** "semantic facts first" KHOÁ; auto-extract defer; `MemoryRelation` scope tối giản.
- **F(prior-high-4, Item 3) → RESOLVED:** dedupe + `confidence` thành AC bắt buộc MVP (FR-32).
- **F(prior-high-5, Item 4) → RESOLVED:** legal/retention reframed + contradiction đã sửa (còn residual F2 low).
- **F(prior-medium, Items 6/7/10) → RESOLVED:** OQ-6 (stale artifacts + epics.md), FR-15/§6.2 (auto-extract cost control), Beachhead sequencing.

## Note on method
- Đối chiếu dựa trên bản đọc đầy đủ **PRD hiện tại** (`updated: 2026-07-24`, kết thúc sạch tại §9 Assumptions Index — không bị cắt) so với `prfaq-Nowing.md` (Verdict + Coaching Notes Stage 1–4) và `prfaq-Nowing-distillate.md` (Requirements/Scope/Verdict findings), và so với chính review vòng trước (prior baseline 0/4/6, 2 critical).
- Coverage = "PRD có nội hoá finding thành requirement/scope/OQ đủ để downstream (epics/architecture) hành động". Nhiều FR memory mang `[GAP]` = **chưa build** — đây là trạng thái implementation đúng đắn, KHÔNG phải gap coverage; PRD đã đóng khung go/no-go ở [NOTE FOR PM].
- Grep không index được `_bmad-output/` (gitignored); các khẳng định "COVERED/RESOLVED" dựa trên đọc toàn văn PRD, có trích dẫn vị trí (FR/NFR/OQ/SM id) cho từng mục.
- Review này **chỉ critique**, không chỉnh sửa PRD.
