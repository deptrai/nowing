---
title: "PRFAQ: Nowing"
status: "complete"
created: "2026-07-24"
updated: "2026-08-04"
stage: 5
inputs:
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-22-vision-pivot.md"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-22.md"
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
  - "docs/project-overview.md"
  - "README.md"
---

# Nowing — bộ nhớ nghiên cứu dài hạn, mã nguồn mở: agent và team của bạn nhớ được cả dữ liệu web sống, kèm nguồn trích dẫn.

## Dành cho dev và team xây trên AI agent — mọi phát hiện, quyết định và nguồn được lưu và liên kết một lần, rồi gọi lại qua MCP hoặc web, để Claude/Cursor/OpenCode hay đồng đội tiếp tục từ đúng chỗ đã dừng thay vì tìm lại từ đầu.

**{Thành phố}, 2026** — Nowing hôm nay phát hành bản mã nguồn mở của *long-term research memory*: nơi AI agent và cả team lưu lại những gì đã nghiên cứu — từ tài liệu nội bộ đến dữ liệu web sống như Reddit, YouTube, Google Maps — rồi gọi lại chính xác khi cần, kèm nguồn. Agent của bạn thôi bắt đầu mỗi phiên từ con số không.

Ngày nay, mỗi phiên mới là một lần quên sạch. Bạn dán lại bối cảnh, agent đọc lại cả repo và tài liệu, đốt token cho thứ nó đã "biết" hôm qua. Tệ hơn, thứ nó tìm được ngoài web — một luồng Reddit, một dải giá trên Amazon — bốc hơi ngay khi phiên đóng. Trong một team, mỗi người giữ nghiên cứu trong chat riêng, nên cùng một câu hỏi bị điều tra đi điều tra lại, và không ai chắc con số đến từ đâu.

Với Nowing, phát hiện được ghi nhớ ngay khi xuất hiện: một fact, một quyết định, một kết quả research lưu kèm nguồn, liên kết với thứ liên quan, và sửa được khi thực tế đổi. Lần sau agent — hoặc đồng đội — hỏi lại, câu trả lời có sẵn kèm trích dẫn, khỏi điều tra lại. Vì Nowing mở và tự host được, dữ liệu nghiên cứu ở lại hạ tầng của bạn, không đi qua cloud của một vendor AI.

> "Các memory layer khác nhớ cuộc trò chuyện của bạn. Nowing nhớ những gì bạn *tìm ra* — kể cả ở những nơi agent thường không với tới — và giữ lại nguồn để bạn tin được. Với đội nghiên cứu, đó là khác biệt giữa 'AI đoán' và 'AI nhớ'."
> — Luisphan, người tạo Nowing

### Cách hoạt động
- **Nối vào:** cắm agent/client của bạn (Claude, Cursor, OpenCode, hoặc chat của chính Nowing) vào Nowing qua MCP.
- **Nghiên cứu như thường:** hỏi, kéo dữ liệu web sống qua connector, tạo báo cáo. Nowing tự rút những phát hiện đáng nhớ từ mỗi lượt và lưu kèm nguồn.
- **Nhớ & tiếp tục:** phiên sau, agent gọi `nowing_recall` để lấy đúng ngữ cảnh, hoặc `nowing_continue_research` để nối lại mạch nghiên cứu đang dở — bạn không phải dán lại gì.
- **Sửa khi sai:** một fact hết đúng thì `nowing_update_fact` cập nhật và giữ lịch sử — bộ nhớ không thành bãi rác.

> "Tôi nối Cursor vào Nowing tối thứ Sáu. Sáng thứ Hai nó vẫn nhớ vì sao tuần trước tôi loại một thư viện — kèm link tôi đã đọc. Không phải kể lại câu chuyện đó lần nữa."
> — {tên}, kỹ sư nền tảng

### Bắt đầu (self-host miễn phí / cloud pay-as-you-go)
- **Self-host miễn phí:** `docker compose up`, cắm LLM/embedding model của bạn, dữ liệu ở lại máy bạn.
- **Cloud pay-as-you-go:** không muốn vận hành thì dùng bản cloud, trả theo lượng dùng.
- Nối agent trong vài phút qua MCP; hoặc dùng web/desktop/extension/Obsidian nếu cần giao diện.

---

## Customer FAQ

### Q1. Mem0/Cognee/Supermemory đã có memory + OSS và được rót vốn. Vì sao tôi dùng Nowing thay vì họ — hoặc tự ghép Mem0 + vài connector?
A: Trung thực: nếu bạn chỉ cần nhớ *hội thoại/agent state* thuần, Mem0 gọn hơn — dùng nó. Nowing khác ở chỗ memory **gắn liền nguồn (citation)** và **gồm cả live-data connectors + deliverables trong cùng một nơi**. Bạn *có thể* tự ghép Mem0 + connectors, nhưng khi đó bạn tự gánh: schema memory có provenance, hybrid search, correction/version, và giữ đám connector không vỡ. Nowing đóng gói sẵn. Ranh giới: **memory của bạn là "nghiên cứu có nguồn" → Nowing; memory là "chat/prefs" → incumbent.** (Đây là câu differentiator — phải chứng minh bằng demo, không chỉ tuyên bố.)

### Q2. Press release nói agent "tự nhớ, liên kết, sửa". Hôm nay bản mã nguồn mở làm được tới đâu — hay đó là roadmap?
A: Chỗ này mình trung thực nhất. **Đã build & đang chạy:** connectors, hybrid KB search, citations, MCP server, 4 MCP memory tools (`remember/recall/continue_research/update_fact`), automations, credit wallet. **Đang xây cho MVP:** eval gate recall (story `3-9`, in-progress) + migration path từ markdown-memory cũ. **Post-MVP (chưa có):** auto-extract mọi lượt chat, relation-graph phong phú, decay/TTL. Nói thẳng: phần *khác biệt* (live-data + citations) đã thật; "trí nhớ" core đã chạy nhưng chưa đóng cổng chất lượng. → **Quyết định trade-off:** 4 tool + facts save/recall/correct = **done**; eval-gated recall + migration = **launch blocker**; auto-extract + relations = **fast-follow**; decay/contradiction = **accepted (post-MVP)**.

### Q3. Tôi đang dùng CLAUDE.md / files + RAG tự dựng để giữ context. Vì sao phải đổi?
A: Nếu context của bạn nhỏ, tĩnh, một người → đừng đổi, files ổn. Nowing đáng đổi khi: context lớn/động, nhiều nguồn (web + nội bộ), cần provenance, hoặc nhiều người/agent dùng chung. Giá trị cụ thể: `recall` trả **top_k nhỏ đã rank** thay vì nhồi cả file → tiết kiệm token và giảm nhiễu. → **Accepted trade-off:** Nowing *không* nhắm người dùng solo/context nhỏ (khớp danh sách non-users).

### Q4. Dữ liệu nghiên cứu của tôi đi đâu? Self-host thì embedding/LLM có gọi ra ngoài không? Cloud thì ai đọc được?
A: **Self-host:** mọi thứ ở hạ tầng của bạn; embedding/LLM chạy qua model bạn cấu hình (có thể local). Nếu bạn *chọn* cắm OpenAI/Anthropic thì nội dung đi tới họ — đó là lựa chọn của bạn, Nowing không gửi lén. **Cloud:** dữ liệu ở cloud Nowing, phân quyền Owner/Editor/Viewer; **chưa có** SLA/compliance doanh nghiệp (đã liệt kê là non-user v1). → **Gap `[low-confidence]`:** chi tiết encryption-at-rest/khóa chưa có trong docs — **cần chốt trước GA cloud.**

### Q5. Ai đứng sau Nowing? Đây là pivot thứ 2 — nếu dự án chết hoặc bạn đổi hướng lần nữa, tôi mất gì? Lock-in tới đâu?
A: Câu khó và đúng. Đây *là* pivot thứ 2 → rủi ro niềm tin có thật. Giảm lock-in bằng: **OSS + self-host** (bạn giữ được cả khi dự án dừng), dữ liệu nằm trong **Postgres của bạn**, có export. → **Gap C4 lộ ra:** hiện README/docs vẫn là bản cũ, `epics.md` chưa tồn tại, và có hệ markdown-memory cũ đang bị bỏ *không có migration path*. **Quyết định:** cam kết public (đồng bộ README/docs) + **data export + migration path** = **fast-follow bắt buộc** — không có thì câu này giết niềm tin.

### Q6. Nó chạy với agent/tool nào? Cursor, Claude Code, OpenCode? Bắt buộc MCP à — client của tôi chưa hỗ trợ MCP thì sao?
A: Chạy với bất kỳ client nói **MCP** (Claude Desktop/Code, Cursor, OpenCode…). Client chưa hỗ trợ MCP → dùng **REST API**, hoặc giao diện web/desktop/extension/Obsidian. Trung thực: trải nghiệm "agent tự nhớ" tỏa sáng nhất qua MCP; ngoài MCP thì thao tác thủ công hơn.

### Q7. Cloud pay-as-you-go tính theo gì? Auto-extract mỗi lượt chat có làm hoá đơn phình ra không?
A: Tính theo token LLM + embedding + lưu trữ. **Deep research cloud** cost thật 2026-08-02: speed $0.0353 · balanced $0.0482 · quality $0.0671 (parse `done.usage.costDollars`). Và đúng — **auto-extract mỗi lượt = chi phí LLM cộng thêm mỗi lượt**, có thể phình. → **Requirements signal:** auto-extract nên **bật theo workspace + có ngân sách**, không mặc định bật toàn bộ; counter-metric SM-C2 (cost/turn) canh chừng. **Accepted trade-off nhưng phải có control.**

### Q8. Làm sao memory không biến thành bãi rác — nhớ nhầm, nhớ trùng, nhớ thứ lỗi thời — rồi recall trả về nhiễu?
A: Chống bằng: **typed facts + confidence + citation** (biết nguồn), **correction/version** (sửa được), **recall trả top_k nhỏ đã rank**. Trung thực: chống "rác" là bài toán *chưa giải xong* — MVP cố ý hẹp ("semantic facts first") đúng để tránh "dump everything into vector DB" (rủi ro docs tự nêu). Dedupe/decay/contradiction = post-MVP. → **Requirements signal:** cần **dedupe + ngưỡng confidence ngay từ MVP nhỏ**, không đợi. Đây là rủi ro sản phẩm số 1.

### Q9. Nếu tôi không phải agent builder — tôi là analyst dùng web UI — memory có đổi được ngày làm việc của tôi không, hay chỉ là plumbing?
A: Trung thực: hôm nay memory tỏa sáng qua **agent/MCP + chat recall**; **UI memory browser / research timeline là post-MVP (deferred)**. Nên analyst thuần-UI cảm nhận giá trị *chậm hơn* agent builder. → **Quyết định:** chấp nhận agent-builder + team là **beachhead trước**; analyst-UI = **fast-follow**. Khớp với Framing B đã chốt.

---

## Internal FAQ

### IQ1. Bài toán kỹ thuật khó nhất là gì — và cái gì ta CHƯA biết cách xây?
A: Khó nhất KHÔNG phải lưu trữ (Postgres+pgvector đã có), mà là **chất lượng recall** (trả đúng thứ liên quan, top_k nhỏ, ít nhiễu) và **chất lượng auto-extraction** (`MemoryExtractionService`/AD-14 rút fact đáng nhớ mà không tạo rác). Chưa biết chắc: ngưỡng confidence/dedupe và cách rank hybrid cho *memory* (khác với KB). → **What would it take to find out:** dựng eval trên `nowing_evals` đo recall precision/noise trên tập thật **trước khi scale** — không đoán bằng cảm tính.

### IQ2. Ta đang bỏ hệ markdown-memory cũ (`User.memory_md`, `Workspace.shared_memory_md`) mà KHÔNG có migration path. User hiện tại mất memory cũ à? *(câu đang bị né)*
A: Đúng, đây là câu bị bỏ qua trong PRD lẫn proposal. Không thể bật `Memory` mới rồi để memory cũ bốc hơi. Cần **script migrate markdown → Memory rows** (hoặc đọc song song trong giai đoạn chuyển) + cờ bật dần. → **Feasibility risk, quyết định:** migration path = **phải có trước khi bật memory mới cho user hiện hữu**; nếu bỏ qua sẽ thành sự cố mất dữ liệu + đòn niềm tin thứ hai.

### IQ3. Timeline thực tế? Proposal nói +1–2 sprint MVP, 3–4 sprint full. Có ảo với team hiện tại không?
A: MVP = 4 MCP tool + facts CRUD trên hạ tầng sẵn có → **1–2 sprint khả thi** NẾU giữ đúng "semantic facts first" và **không** ôm auto-extract/relations/UI cùng lúc. Nguồn trượt lịch số 1: scope creep vào AD-14 (auto-extract) và relation graph. → **Quyết định:** đóng băng MVP = *facts + 4 tool + eval + migration*; nói **KHÔNG** với: UI memory browser, decay/TTL, memory-driven automations, per-workspace toggle (tất cả fast-follow/post-MVP).

### IQ4. Moat là provenance + live-data. Nếu Mem0/Supermemory thêm citations + vài connector thì sao? Moat sống được bao lâu?
A: Citations họ thêm được trong vài tuần. Cái khó copy nhanh là **tích hợp dọc research đã có sẵn**: connectors → citations → memory → deliverables → multi-client, cộng OSS/self-host cho khách data-sensitive. Trung thực: moat = **head start + integration depth**, không phải công nghệ độc quyền → cửa sổ hẹp, phải chạy nhanh và "own" nhóm research-memory trước khi incumbent lấn sang.

### IQ5. Kinh tế cloud thế nào? Auto-extract mỗi lượt + embedding + LLM recall — biên có âm không?
A: Chi phí biến đổi theo token (LLM + embedding + storage). Rủi ro rõ: **auto-extract đốt LLM mỗi lượt** → có thể âm biên ở workspace nặng. → **Requirements:** auto-extract bật-theo-workspace + ngân sách; pricing phải cover extract+embedding+storage, không chỉ chat. **Cost thật 2026-08-02:** deep research speed $0.0353 · balanced $0.0482 · quality $0.0671; `done.usage.costDollars` parsed, fallback 60k micros. Cloud beta cần đo SM-C2 trên usage thật.

### IQ6. Lấy 100 user đầu ở đâu?
A: OSS motion: phân phối qua **hệ sinh thái MCP** (người dùng Claude/Cursor/OpenCode), GitHub, và cộng đồng memory-MCP đang nóng; beachhead = agent builder (Framing B). Rủi ro: **install OSS ≠ active use** → cần onboarding self-host mượt (`docker compose up` chạy được trong 10 phút) và một "aha" recall đầu tiên nhanh. Cloud đến sau khi OSS chứng minh retention.

### IQ7. Why us, why now — và cái này cannibalize gì của Nowing?
A: **Why now:** cửa sổ memory-layer đang mở + ta đã có building blocks. **Why us:** hiếm ai có sẵn connectors + citations + research workspace để hợp nhất thành "research memory". **Cannibalize:** không — nó *mở rộng* workspace hiện có (đúng "extend not rollback"). **Rủi ro chiến lược thật:** phân tán — team nhỏ ôm 7 component *và* dựng memory layer mới.

### IQ8. Cái gì GIẾT dự án này?
A: (a) **Recall kém chất lượng** → "AI đoán" thay vì "AI nhớ" → mất niềm tin ngay lần dùng đầu; (b) **pivot thứ 3** → cạn tín nhiệm; (c) **team nhỏ dàn mỏng** trên 7 component + memory → không cái nào tới nơi. → Mitigation: **eval-gated launch** (không ship recall chưa đạt ngưỡng), **focus tàn nhẫn**, và **cam kết công khai** cho pivot này để nó không giống một thử nghiệm nữa.

### IQ9. Rủi ro pháp lý? Nowing scrape Reddit/YouTube/TikTok/Amazon và **lưu lại lâu dài** (memory). Lưu trữ dài hạn dữ liệu scrape có phơi nhiễm ToS/bản quyền/PII không? *(câu bị bỏ quên)*
A: Câu quan trọng chưa ai đặt. Memory *bền* khác dữ liệu *ephemeral*: lưu dài hạn nội dung bên thứ 3 có thể đụng ToS/bản quyền/PII. **Self-host** đẩy trách nhiệm sang user; **cloud** thì Nowing chịu. → **Unknown `[legal]`, what would it take:** review ToS các nguồn + đặt **retention/right-to-delete policy** và tách rõ trách nhiệm self-host vs cloud **trước GA cloud**.

---

## The Verdict

**Phán quyết tổng: 🟡 NEEDS MORE HEAT (nghiêng tích cực) — ĐÁNG LÀM, có điều kiện.**

Vision post-pivot đứng vững hơn hẳn vision cũ. Định vị (research-memory có provenance + gồm live web data) sắc và phòng thủ được, dựng trên đúng building blocks Nowing đã có. **Cập nhật 2026-08-04:** 4 MCP memory tools đã chạy; deep-research cost thật đã đo (speed $0.0353 · balanced $0.0482 · quality $0.0671); degradation khi engine chết đã done (`9.1a`). **Vẫn mở:** "trí nhớ" cốt lõi chưa đóng cổng chất lượng (recall eval `3-9` in-progress), migration path từ markdown-memory cũ, và legal/retention. Đây là concept nên tiến hành — nhưng **chưa nên cam kết toàn lực cho tới khi vá lỗ và dựng cổng chất lượng.** Không phải "cracked" (không có deal-breaker), cũng chưa "forged" (quá nhiều gap execution + lõi chưa đóng gate).

### 🗡️ Forged in steel (đã thành thép)
- **Wedge B:** "memory có nguồn + gồm live web data" — khác biệt thật, không me-too Mem0; dựng trên connectors/citations/KB/MCP đã có.
- **Problem thật & cấp bách,** được thị trường xác nhận (Mem0 $24M / Cognee $7.5M / Supermemory $2.6M).
- **Kiến trúc pragmatic:** tái dùng Postgres+pgvector, không graph DB mới; kỷ luật "MCP tools trước, semantic facts first".
- **OSS + self-host** = đòn giảm lock-in thật cho khách data-sensitive.
- **Đã có `nowing_evals`** → sẵn cổng đo chất lượng recall.

### 🔥 Needs more heat (cần thêm lửa)
- **One-sentence promise** còn hai-tầng (wedge + who) — cần một câu sắc hơn.
- **Beachhead dứt khoát:** agent-builder (giá trị nhanh) vs team/cloud (doanh thu) — cần lộ trình rõ ai trước, ai sau.
- **Unit economics cloud** chưa có số thật (cost/turn); auto-extract là ẩn số chi phí.
- **GTM "install ≠ active use"** — cần định nghĩa "aha moment" recall đầu tiên.
- **Dateline PR** (`{Thành phố}`) — dữ kiện nhỏ còn treo.

### 🧱 Cracks in the foundation (nứt móng — phải xử lý có chủ đích)
- 🔴 **Migration path** từ markdown-memory cũ chưa tồn tại → rủi ro mất dữ liệu. *Vá:* script migrate + đọc song song, **trước khi bật memory mới**.
- 🔴 **Recall quality chưa chứng minh** → nếu nhiễu, toàn bộ "AI nhớ" sụp. *Vá:* eval-gate trên `nowing_evals` với ngưỡng precision **trước khi ship**.
- 🟠 **Vision chưa kể ra thế giới:** README/docs pre-pivot, `epics.md` đã cập nhật 2026-08-04. *Vá:* đồng bộ README/docs sang vision mới + cam kết công khai (chống nhận thức "pivot thứ 3").
- 🟠 **Legal/retention** dữ liệu scrape lưu dài hạn chưa xử lý. *Vá:* ToS review + retention/right-to-delete **trước GA cloud**.
- 🟠 **"Memory rác"** (rủi ro docs tự nêu). *Vá:* dedupe + ngưỡng confidence ngay từ MVP nhỏ.

**Khuyến nghị:** PROCEED — nhưng đóng băng MVP đúng (facts + 4 MCP tool + eval + migration), vá 2 crack đỏ trước khi ship, và đồng bộ docs/epics để pivot này "thành thật".

---

<!-- coaching-notes-stage-1 -->
## Coaching Notes — Stage 1 (Ignition)

**Concept type:** Open-source product + commercial cloud (self-host miễn phí, cloud pay-as-you-go). Hai nhóm audience: builder/self-hoster (OSS) và team trả tiền (cloud).

**Vision đang pressure-test:** POST-pivot 2026-07-22 = "Open-source long-term research memory cho AI agents và team" (KHÔNG phải vision cũ "NotebookLM alternative").

**4 yếu tố cốt lõi:** (1) khách hàng — 4 persona, mũi nhọn = AI agent builder cần persistent memory qua MCP; (2) vấn đề — agent không có bộ nhớ bền, mất context, tốn token, team silo; (3) stakes — làn sóng memory-layer được rót vốn (Mem0 $24M/Cognee $7.5M/Supermemory $2.6M), Nowing có building blocks nhưng thiếu memory model+tools, rủi ro "dump into vector DB"; (4) giải pháp — Memory/ResearchThread trên Postgres+pgvector + 4 MCP tools + auto-extract, giữ workspace nghiên cứu.

**Top tensions:** C1 hai-sản-phẩm-trong-một; C2 khác-gì-Mem0; C3 v1 hẹp hơn vision (semantic facts first); C4 vision chưa kể ra thế giới (README/docs pre-pivot, epics.md thiếu, markdown-memory cũ bị bỏ âm thầm); C5 agent builder vs researcher ai cảm nhận trước.

<!-- coaching-notes-stage-2 -->
## Coaching Notes — Stage 2 (Press Release)

**QUYẾT ĐỊNH ĐỊNH VỊ (agent tự quyết theo best practice):** **Framing B dẫn dắt** = research-memory wedge (memory có nguồn + gồm live web data). Khách hàng chính = **dev/team xây trên agent**. MCP = bề mặt, không phải lời hứa.
- **Loại A (agent-memory-first):** me-too Mem0, đánh vào sân kẻ có vốn → loại làm mũi nhọn.
- **Đẩy C (team-continuity) xuống** How It Works / Getting Started (team/cloud tier), không phải headline.
- **Rejected framing/copy:** headline "nhớ, tiếp tục, hành động" thuần (mất differentiator); subhead quá tải khi cố nhét cả wedge + who.
- **3 claim rủi ro nhất trong PR (feasibility):** auto-extract mỗi lượt (AD-14), relation-graph, correction+history — đều `[GAP]`. Differentiator (live-data + citations) đã có thật.
- **Dateline `{Thành phố}`** = placeholder duy nhất cần dữ kiện thật từ user.

<!-- coaching-notes-stage-3 -->
## Coaching Notes — Stage 3 (Customer FAQ)

**Gaps lộ ra qua câu hỏi khách hàng:**
- **G1 (Q2):** "trí nhớ" cốt lõi chưa build — cần chốt ranh giới MVP rõ (facts save/recall/correct + 4 tool).
- **G2 (Q4):** encryption-at-rest/compliance cloud chưa có trong docs (`[low-confidence]`).
- **G3 (Q5):** README/docs pre-pivot, epics.md thiếu, KHÔNG có migration path từ markdown-memory cũ → rủi ro niềm tin (2 pivot).
- **G4 (Q8):** dedupe + confidence threshold để tránh "memory rác" — rủi ro sản phẩm #1.
- **G5 (Q9):** UI cho analyst deferred → human-researcher story yếu hơn agent story.

**Quyết định trade-off:**
- **Launch blocker:** 4 MCP memory tools + save/recall/correct semantic facts (Q2); dedupe + ngưỡng confidence tối thiểu (Q8).
- **Fast-follow (bắt buộc):** đồng bộ README/docs với vision mới + data export + migration path (Q5); auto-extract + relation graph (Q2); UI memory browser cho analyst (Q9).
- **Accepted trade-off (post-MVP):** decay/TTL/contradiction resolution (Q8); SLA/compliance doanh nghiệp (Q4).
- **Requirements signal:** auto-extract phải bật theo workspace + có ngân sách (Q7); solo/context-nhỏ KHÔNG phải target (Q3).

**Competitive intel:** wedge phòng thủ được = provenance (citations) + memory gồm live-data mà pure-memory incumbent (Mem0/Supermemory) không có; rủi ro nếu họ thêm citations → wedge mỏng, cần đào sâu "fused research + deliverables".


<!-- coaching-notes-stage-4 -->
## Coaching Notes — Stage 4 (Internal FAQ)

**Feasibility risks:**
- **FR1 (IQ1):** rủi ro lõi = chất lượng recall + auto-extraction, KHÔNG phải storage. Phải eval-gate bằng `nowing_evals` trước khi scale.
- **FR2 (IQ2):** thiếu migration path từ markdown-memory cũ (`User.memory_md`, `Workspace.shared_memory_md`) → rủi ro mất dữ liệu + đòn niềm tin. **Phải có trước khi bật memory mới cho user hiện hữu.**
- **FR3 (IQ9) `[legal]`:** lưu trữ dài hạn dữ liệu scrape (Reddit/YT/TikTok/Amazon) → phơi nhiễm ToS/bản quyền/PII; cần retention + right-to-delete policy trước GA cloud.

**Resource/timeline:**
- MVP memory (4 tool + facts CRUD + eval + migration) = **1–2 sprint khả thi** nếu giữ "semantic facts first".
- Full vision = 3–4 sprint. Nguồn trượt lịch: auto-extract (AD-14) + relation graph → **để fast-follow**.
- **Nói KHÔNG (MVP):** UI memory browser, decay/TTL, memory-driven automations, per-workspace toggle.

**Unknowns + how to resolve:**
- `[finance]` cost/turn thật (IQ5) → đo SM-C2 trên cloud beta trước khi định giá.
- `[legal]` ToS/retention (IQ9) → review pháp lý + policy trước GA.
- Recall precision ngưỡng nào là "đủ tốt" (IQ1) → eval harness định lượng.

**Strategic positioning:**
- Moat = head start + integration depth (connectors→citations→memory→deliverables→multi-client) + OSS/self-host; KHÔNG phải công nghệ độc quyền → cửa sổ hẹp, chạy nhanh, own nhóm research-memory trước.
- 3 thứ giết dự án (IQ8): recall kém → mất niềm tin; pivot thứ 3; team nhỏ dàn mỏng 7 component. Mitigation: eval-gated launch + focus + public commitment.
- GTM: OSS/MCP ecosystem → agent builder beachhead; cloud sau khi OSS chứng minh retention.
