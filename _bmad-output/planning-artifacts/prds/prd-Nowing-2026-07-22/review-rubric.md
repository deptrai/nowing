# PRD Quality Review — Nowing (2026-07-22) · Re-validation sau update pass

## Overall verdict
Update pass đã **nâng chất lượng PRD lên rõ rệt và đúng chỗ**: canh bạc chiến lược trung tâm giờ là **một quyết định go/no-go tường minh** (`[NOTE FOR PM]` ở §0), bốn FR memory (FR-32/33/34/36) có **Acceptance Criteria cụ thể, kiểm chứng được**, scope honesty siết lại (§6.1 gắn nhãn "In Scope — CHƯA BUILD", §9 `[CORRECTED]` sửa mâu thuẫn retention), và NFR-8/SM-10 thêm một **eval gate chất lượng recall** — mà tôi đã verify là **có thật** (`nowing_evals` là harness thật trong monorepo, không phải aspirational). **Cả hai high rubric-level trước đây (memory-gamble chưa thành quyết định; done-ness memory mỏng) đều đã được giải quyết.** Điều **mới nổi lên và đáng lo**: FR-36 — chính cái gate data-safety thêm vào để vá "crack đỏ #1" — **không đối soát với migration `178_drop_legacy_memory_columns.py`**, vốn đã DROP đúng hai cột `User.memory_md` / `Workspace.shared_memory_md` mà FR-36 giả định vẫn còn để migrate; nhận thức migration của PRD dừng ở 172. PRD **không broken**, nhưng high này nên đóng trước khi scope epic memory-migration.

## Delta vs prior validation (prior aggregate = **Poor**: 2 critical + 5 high)
- **Critical: 2 → 0 (rubric-level).** Hai critical trước là của reviewer PRFAQ (F1 migration path, F2 recall eval gate); update đã nội hoá thành **FR-36** và **NFR-8** trong doc. (Coverage-adequacy do reviewer PRFAQ chấm; nhưng F1 nay có một crack thực thi — xem SF-1.)
- **High: 2 → 1 (rubric-only).** RESOLVED: (a) memory-gamble → `[NOTE FOR PM]` go/no-go; (b) done-ness FR-32/33/34 → Acceptance Criteria. NEW (từ verify code): **SF-1 FR-36 vs migration 178**.
- **Medium: 4 → 3.** RESOLVED: memory In-Scope chưa flag (§6.1 nay flag); FR-15 auto-recall mơ hồ (nay khoá "on-demand MVP"). PERSIST/NEW: FR-22 "dưới 20 giây"; lệch identity + SM-1 activity-metric (đã dịu); DN/​SF FR-32 undercount surface cũ.
- **Low: 6 → 5.** RESOLVED: FR ID phi tuyến (nay có "Chỉ mục FR" đầu §4, đã đối chiếu — chính xác). PERSIST: NFR-6/7 mislabel (nay tự-flag `[NOTE]`), NFR-1 bound mơ hồ, UJ-4 protagonist generic; brownfield-refs "chưa verify" nay ĐÃ verify → thăng thành SF-1 (high).
- **Dimension verdicts:** Decision-readiness `adequate → strong`; Done-ness `adequate(weak) → adequate` (high resolved); Shape fit `strong → adequate` (verify code lộ SF-1); còn lại giữ nguyên.
- **Kết luận delta:** cải thiện thực chất, từ "Poor" → rubric-level **solid adequate/good**; residual quan trọng nhất là 1 high mới (SF-1) và cần reviewer PRFAQ xác nhận coverage.

## Decision-readiness — strong *(↑ từ adequate)*
Prior high đã đóng dứt điểm. `[NOTE FOR PM]` ở §0 gọi đúng tension trung tâm bằng ngôn ngữ quyết định: định vị "long-term research memory" (§1) *"hiện dựa hoàn toàn vào lớp memory (FR-32/33/34/35) mà toàn bộ đang `[GAP]` chưa build"*, và tuyên bố *"Đây phải được coi là một quyết định go/no-go có chủ đích, không phải suy ra từ các tag GAP rải rác"* — kèm hai điều kiện trước-ship neo vào FR-36 + NFR-8. §2.1 bổ sung callout **`[Beachhead — ưu tiên]`** chỉ định primary = agent-builder + team và thứ tự rollout (OSS/MCP → cloud) — trade-off được phát biểu, không làm mờ. OQ-3/OQ-5/OQ-6 là câu hỏi mở thật, không tu từ.

Điểm còn thiếu (nhẹ): OQ-5 (write-back action architecture) và `[ASSUMPTION]` "agent_task đủ thay direct write-back" (§9) vẫn chưa có callout PM riêng. Không còn là high vì tension chủ đạo đã được đặt trước mặt PM.

### Findings
- **low** OQ-5 + assumption write-back vẫn thiếu `[NOTE FOR PM]` (§8 OQ-5, §9) — tension kiến trúc thứ cấp chưa được nâng lên PM-facing. *Fix:* thêm `[NOTE FOR PM]` ngắn tại OQ-5.

## Substance over theater — adequate *(giữ nguyên; NFR-8 thêm substance thật)*
Personas vẫn drive quyết định (4 JTBD, mỗi persona → feature/FR cụ thể). Vision §1 đặc thù Nowing, không swap được. **NFR-8 là substance thật, không phải theater**: nêu `precision@k`, `noise rate`, harness `nowing_evals`, ngưỡng tối thiểu, ship-gate, chốt ngưỡng cùng SM-10 — và tôi đã verify `nowing_evals` tồn tại (package `nowing_evals/src/nowing_evals/`, CLI `python -m nowing_evals`, suites/arms/grader), nên `[GAP]` "nowing_evals chưa đo memory recall" là **chính xác** chứ không bịa.

Residual cũ vẫn còn nhưng nay **được tự-disclose**: NFR-6/NFR-7 mang `[NOTE]` thừa nhận *"Thực chất là feature-gap (không phải NFR)"* — trung thực hơn, nhưng vẫn để nguyên vị trí gây loãng danh mục NFR.

### Findings
- **low** NFR-6/NFR-7 vẫn là feature-gap dán nhãn NFR (§5) — nay tự-flag nhưng chưa move; trùng nội dung với `[GAP]` FR-13-adjacent và FR-31. *Fix:* chuyển thành `[GAP]` FR hoặc gộp vào FR-13/FR-31.
- **low** NFR-1 bound mơ hồ (§5 NFR-1) — "limit phù hợp" / scraper "vài giây" chưa kiểm chứng được. *Fix:* p95 latency mục tiêu cho hybrid search + timeout scraper.

## Strategic coherence — adequate *(mạnh hơn, verdict giữ nguyên)*
Thesis rõ hơn nhờ beachhead (§2.1) + **SM-10** (*"chất lượng, không phải volume"* — precision@k/noise của `nowing_recall`, phân biệt với SM-7/8/9 vốn đếm số lượng). Counter-metrics SM-C1/C2 còn nguyên. Feature prioritization giờ theo thesis (agent-builder → team).

Residual (đã dịu, chưa dứt): **SM-1 primary vẫn là activity-metric** (*"workspace active ≥1 chat/scraper run trong 7 ngày"* — sát DAU/MAU), trong khi metric validate thesis (SM-8/10) phụ thuộc feature chưa build; và Vision §1 vẫn phát biểu Nowing *"là bộ nhớ nghiên cứu lâu dài"* (identity) trong khi thân bài là platform-có-thêm-memory. `[NOTE FOR PM]` giảm nhẹ rủi ro này nhưng framing "thêm memory vào platform hiện có" chưa được đưa vào Vision.

### Findings
- **medium** Lệch identity + primary metric là activity, metric-thesis nằm trên FR chưa build (§1 vs §4; §7 SM-1 vs SM-8/10) — chưa rõ Nowing "là memory layer" hay "platform có thêm memory"; SM-1 đo hoạt động. *Fix:* đưa framing "memory bổ sung vào platform" vào §1; khi memory build xong, nâng SM-8/SM-10 lên primary kèm baseline.

## Done-ness clarity — adequate *(prior high RESOLVED; nâng từ "adequate/weak spot")*
Đây là nơi update pass tạo giá trị lớn nhất. FR-32/33/34/36 nay có **Acceptance Criteria (MVP)** cụ thể và kiểm chứng được:
- **FR-32**: field chốt (`content`, `type` mặc định `semantic`, `source`, `tags`, `confidence` 0–1, `embedding`, `workspace_id`); **dedupe** (cosine ≥ ngưỡng → merge/append); định nghĩa **"recall hit"** (top_k ≤5, hybrid rank, vượt ngưỡng similarity); ràng buộc "không `Memory` nào thiếu `source`/`confidence`".
- **FR-33**: `nowing_continue_research(thread_id)` trả N memory ranked + citations trước; thread không tồn tại → **lỗi rõ ràng, KHÔNG tạo ngầm**; recall theo cùng định nghĩa FR-32.
- **FR-34**: "correct" = `MemoryVersion` mới giữ `previous_content`/`corrected_content`/`corrected_by`/timestamp, **không hard-delete**; propagation MVP = chỉ chính memory (không đệ quy qua relation graph).
- FR-32 lifecycle nay chốt "decay/expire: post-MVP" (bỏ mơ hồ "cái gì trigger decay"). FR-15 nay khoá **"recall theo yêu cầu (agent gọi `nowing_recall`) trong MVP — auto-recall/auto-extract là fast-follow"** (giải quyết prior medium "tự động hoặc theo yêu cầu").

Lưu ý: các ngưỡng ("ngưỡng cấu hình", "top_k mặc định ≤5", precision "ví dụ ≥") cố ý để mở, chốt số cùng NFR-8/SM-10 — hợp lý ở cấp PRD. Residual thực sự là một chỗ mơ hồ **cũ, chưa sửa**.

### Findings
- **medium** FR-22 "podcast 2 host... **dưới 20 giây**" (§4.5) — vẫn không rõ 20 giây là độ dài audio hay thời gian tạo; feature đã build nên rủi ro downstream thấp hơn nhưng vẫn không kiểm chứng được. *Fix:* nêu rõ ngữ nghĩa "20 giây".
- *(Xem thêm SF-1: Acceptance Criteria của FR-36 tốt về hình thức nhưng kế thừa một premise sai với migration 178 → engineer có thể build forward-migration cho dữ liệu đã bị drop.)*

## Scope honesty — strong *(giữ nguyên, được củng cố)*
Prior medium đã đóng: §6.1 nay ghi rõ **"Long-term research memory (In Scope — CHƯA BUILD, cần spec chi tiết + gate trước-ship)"**, tách rõ phần greenfield khỏi platform đã có, và liệt kê điều kiện trước-ship (FR-36 + NFR-8). §6.2 mở rộng đúng hướng: auto-extract (fast-follow, **per-workspace opt-in + ngân sách token, không default-on**) và relation graph traversal (fast-follow) nay OUT tường minh. §9 `[CORRECTED 2026-07-24]` **gạch bỏ** giả định cũ ("storage chưa cấp bách, defer") và thay bằng khung pháp lý (ToS/bản quyền/PII, chốt retention + right-to-delete + self-host/cloud split TRƯỚC GA cloud) — sửa đúng contradiction mà reviewer PRFAQ nêu, lại giữ vết struck-through để trace. Đây là scope honesty mẫu mực.

Cảnh báo (informational, không đổi verdict): open-items density nay **cao hơn** trước (thêm FR-36, NFR-8, OQ-6, SM-10). Chấp nhận được vì memory đã được gate tường minh là "chưa build-ready"; nhưng nếu doc này dùng để green-light build toàn bộ thì phần memory phải đi kèm spec riêng, không đưa thẳng xuống epics.

### Findings
- **low** Open-items density cao cho một doc feed-implementation (§6.1/§6.2/§8/§9) — hợp lệ vì memory được gate rõ, nhưng cần tách "phần build-ready ngay" khỏi "phần cần spec + gate". *Fix:* trong §6.1 phân tách hai nhóm scope theo trạng thái sẵn-sàng-build.

## Downstream usability — strong *(giữ nguyên)*
Prior low (FR ID phi tuyến) đã đóng: đầu §4 có **"Chỉ mục FR (theo số)"** — tôi đã đối chiếu từng số: index khớp section, và **FR 1–36 đủ, unique, không gap/dup** (FR-36 là số mới; ánh xạ §4.1→FR-1..4,10 / §4.3→FR-9,11,12,13,32,33,34,36,5 / … đều đúng). Glossary §3 nay bao gồm Memory, Research Thread, Memory Type, MCP Memory Tools, Role/Permission — domain noun cho lớp memory đã có, hỗ trợ source-extract xuống story. SM traceability giữ tốt; SM-10 → NFR-8.

Residual: UJ-4 protagonist vẫn generic.

### Findings
- **low** UJ-4 protagonist "Người dùng lên lịch automation" (§2.3) — vẫn chung chung, khác các UJ có role cụ thể. *Fix:* đổi thành role (vd "Researcher lên lịch automation").

## Shape fit — adequate *(↓ từ strong — verify code lộ sai lệch brownfield trên FR-36)*
Shape tổng thể vẫn khớp (platform brownfield đa-surface, UJ có protagonist là load-bearing và hiện diện). Kỷ luật `[GAP]`/`[REMOVED]` còn tốt. Nhưng rubric yêu cầu brownfield thì **existing-code references phải chính xác** — và lần này tôi đã verify thay vì để "chưa verify" như trước, và **phát hiện sai lệch load-bearing**:

FR-36 (và premise của `[NOTE FOR PM]`) giả định dữ liệu markdown-memory cũ **vẫn còn để migrate**: `[GAP]` FR-36 ghi *"hệ markdown-memory cũ chưa được xử lý"*. Đối chiếu code:
- Hệ cũ **có thật**: `121_add_memory_md_columns.py` thêm `user.memory_md` + `searchspaces.shared_memory_md`; `122_migrate_and_drop_old_memory_tables.py` đổ `user_memories`/`shared_memories` vào markdown; và **route đang sống** `app/routes/memory_routes.py` + `team_memory_routes.py` (`read_memory`, `MemoryScope.USER/TEAM`). → mối lo data-safety là **chính đáng**.
- NHƯNG repo cũng có **`178_drop_legacy_memory_columns.py`** (`revision 178`, revises 177) `upgrade()` chạy `ALTER TABLE "user" DROP COLUMN IF EXISTS memory_md;` và `ALTER TABLE workspaces DROP COLUMN IF EXISTS shared_memory_md;`. **PRD không nhắc migration 178 ở bất kỳ đâu** (nhận thức migration của doc dừng ở 172). Nếu 178 đã apply ở prod, dữ liệu legacy **đã mất** → gate "migrate trước khi bật Memory mới" trở nên vô nghĩa (đóng cửa chuồng sau khi ngựa đã sổng); nếu 178 chưa apply, FR-36 vẫn phải **điều phối/hoãn 178** cho tới khi migrate + verify xong — điều PRD không nói.

Hệ quả: FR-36 — cái gate cốt lõi vá crack #1 — có Acceptance Criteria tốt về hình thức nhưng **xây trên bức tranh migration đã lỗi thời**, làm suy yếu chính sự tự tin của `[NOTE FOR PM]`. Đây là high (impact lên usefulness: downstream có thể build forward-migration cho dữ liệu đã bị drop, hoặc bỏ sót nhu cầu gate/revert 178).

Ngoài ra, `[GAP]` FR-32 khẳng định *"Hiện chỉ có `Document`/`Chunk` và `ChatThread`/`ChatMessage`"* — **undercount**: đã tồn tại `memory_routes.py`/`team_memory_routes.py` + service `read_memory`/`MemoryScope` (chính là markdown-memory surface). Nội bộ mâu thuẫn nhẹ với FR-36 (vốn thừa nhận hệ cũ tồn tại).

### Findings
- **high** **SF-1: FR-36 không đối soát với migration `178_drop_legacy_memory_columns.py`** (§4.3 FR-36 + §0 `[NOTE FOR PM]`; glossary §3 dừng ở migration 172) — 178 đã DROP đúng `user.memory_md`/`workspaces.shared_memory_md` mà FR-36 giả định còn tồn tại; PRD không cite 178. Gate data-safety có thể đã vô hiệu (nếu 178 đã chạy) hoặc thiếu bước điều phối/hoãn 178. *Fix:* cập nhật FR-36 + glossary để (1) cite 178 và xác định trạng thái đã-apply hay chưa ở prod; (2) nếu chưa apply → gate/hoãn 178 tới khi migrate `Memory` + verify xong; (3) nếu đã apply → chuyển FR-36 thành "khôi phục/đánh giá mất mát từ backup" thay vì forward-migrate.
- **medium** `[GAP]` FR-32 undercount surface memory hiện có (§4.3 FR-32) — bỏ sót `memory_routes.py`/`team_memory_routes.py` + `read_memory`/`MemoryScope`; mâu thuẫn nhẹ với FR-36. *Fix:* sửa câu "hiện chỉ có Document/Chunk/Chat…" để phản ánh markdown-memory routes đang sống.

## Mechanical notes
- **Migration lineage staleness (load-bearing):** Glossary §3 tham chiếu tới ~172; repo có ≥ 178. Vì 178 trực tiếp liên quan FR-36, staleness này không còn "vô hại" (xem SF-1). Nên refresh danh sách migration được cite.
- **Assumptions Index roundtrip:** §9 vẫn **index-only** — không có tag `[ASSUMPTION]` inline trong thân FR để trace ngược; thêm `[CORRECTED 2026-07-24]` (một mục strikethrough có chủ đích, hợp lệ). Roundtrip vẫn một chiều.
- **ID continuity:** FR **1–36 đủ, unique, không gap/dup**; thứ tự phi tuyến (gộp theo area) nay có "Chỉ mục FR" bù. UJ-1..7, SM-1..10 + SM-C1/C2 contiguous; SM-10 mới, trỏ NFR-8.
- **Glossary drift:** "Research Thread" (§3) vs "research threads" (UJ-7, SM-8) — lệch hoa/số nhiều, nhẹ. Bổ sung 5 term memory nhất quán với FR.
- **Verify facts (không rubber-stamp):** `nowing_evals` **tồn tại** (NFR-8 hợp lệ); `epics.md` **không tồn tại** trong `_bmad-output/planning-artifacts/` (chỉ có architecture/, prds/, ux-designs/ + prfaq + sprint-change-proposal) → OQ-6 **đúng**; `memory_md`/`shared_memory_md` **tồn tại** nhưng có `178_drop_legacy_memory_columns.py` (→ SF-1).
- **Required sections:** đầy đủ cho stakes/product type; `[NOTE FOR PM]`, FR-36, NFR-8, OQ-6, SM-10 bổ sung đúng chỗ.
