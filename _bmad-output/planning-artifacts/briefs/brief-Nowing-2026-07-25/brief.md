---
title: "Product Brief: Nowing"
status: final
created: 2026-07-25
updated: 2026-08-06 (added §13 Marketing Strategy)
editorial: "bmad-editorial-review-structure + bmad-editorial-review-prose đã áp dụng 2026-07-25"
purpose: "Input cho README + landing + marketing strategy (đối tượng đọc: developer + marketing)"
audience: developer + marketing
output_language: "English only (README + landing) — xem §12.2"
decisions_locked: ["12.1 câu một dòng", "12.2 chỉ tiếng Anh", "12.3 chỉ Nowing public", "12.4 hoãn số metrics", "12.5 không gọi tên đối thủ", "12.6 Phase 1 cloud-only → Phase 2 metered"]
license_model: "BA TẦNG — Apache-2.0 core · BSL 1.1 cho nowing_backend/app/proprietary/** (crawler engine, KHÔNG phải OSS) · closed-source hosted cho deep-research engine. Xem §5.1"
open_items: ["ngưỡng 15 phút cho M1 (§9) — mục tiêu thiết kế, chưa validate bằng user thật", "target GitHub star / self-host install (§9) — chưa đặt số"]
resolved: ["M-1 → 12.6", "M-2 → H-1", "M-3 → giải bằng code 2026-07-25, xem §12"]
blocking_gates: ["eval gate recall (NFR-8/story 3-9) trước khi launch — story đang in-progress"]
resolved_gates: ["story 9.1a degradation done 2026-08-02", "story 9.2 real costDollars parsing done 2026-08-02"]
follow_ups: ["H-1 thứ tự 9.1 trước 9.2 — ĐÃ APPLY", "H-2 ranh giới OSS/Cloud sang PRD — ĐÃ APPLY", "H-3 defect provenance memory→scraper-run → FR-39 / Story 9.6 — ĐÃ ĐĂNG KÝ", "H-4 onboarding phải seed nội dung (§9 M1) — CHƯA có trong PRD"]
authors: "Mary (Business Analyst) + Luisphan (PO)"
sources:
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/prfaq-Nowing-distillate.md"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/epics.md"
  - "_bmad-output/implementation-artifacts/sprint-status.yaml"
  - "chainlens-research: direction-decision-brief-2026-07-24.md, technical-deep-research-quality-latency-roadmap-2026-07-25.md, epic-26-gate-tracking.md"
  - "web research 2026-07-25: landscape memory-layer (xem §4 để biết link nguồn)"
---

# Product Brief: Nowing

> **Mục đích tài liệu này:** nguồn để viết README + landing. Nó **không** phải PRD. PRD trả lời *"xây gì"*; brief này trả lời *"kể gì, và không được kể gì"*.
>
> **Nền tảng quyết định:** `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED, D1–D4). Positioning đang **frozen tới 2026-08-24**.

> ## 🛑 Hai điều kiện trước khi công bố bất cứ gì
>
> **1. Đừng launch trước khi eval gate recall đóng** (NFR-8, story `3-9` đang `review`). Toàn bộ định vị đứng trên chất lượng recall — chi tiết §11. Với OSS, ấn tượng đầu chỉ có một lần.
> **2. Đừng public repo trước khi story `9.1a` (degradation) xong.** Thiếu nó thì self-host không dùng được và đường OSS/PLG sụp — chi tiết §5.1, §12 H-1.

> **Nếu bạn đang viết README/landing, đọc theo thứ tự:** §1 (câu dùng thật) → §7 (luật nói/không nói) → §8 (nói được gì hôm nay) → bảng feature ở §5.1. Bốn phần đó là nội dung tác nghiệp. §2–§4 là *lý do*, đọc khi cần biện luận. §9–§12 là metrics và decision trail.

---

## 1. Một câu  `✅ CHỐT 2026-08-06`

> **Nowing (now + knowing) — knowledge intelligence platform nơi raw data từ mọi nguồn biến thành kiến thức thực sự. Mọi nguồn. Một sự thật. Nhớ mãi.**

**Bản tiếng Anh (dùng thật ở README/landing — ngôn ngữ duy nhất của README/landing, xem §12.2):**

> **Nowing (now + knowing) — where data from every source becomes knowledge. All sources. One truth. Forever.**

**Vì sao câu này:** Nowing không chỉ lưu trữ documents — nó dedup data từ nhiều nguồn thành canonical entities, track changes theo thời gian, và nhớ mọi thứ bạn đã research. Khác biệt cốt lõi: **entity-centric thay vì document-centric**.

**Subtitle (khi cần nói scope, không nói wedge):**
> *Knowledge intelligence platform — entity dedup, provenance, and compounding memory for researchers and AI agents.*

**Dòng trả lời "khác gì X" — dùng khi bị hỏi, không gọi tên ai:**
> *Others store documents. Nowing deduplicates data from every source into canonical entities, tracks changes over time, and remembers everything you've researched.*

---

## 2. Executive Summary

AI agent hôm nay mất trí nhớ mỗi lần mở session mới. Cách chống đỡ phổ biến — nhồi `CLAUDE.md`, đọc lại toàn bộ repo, copy-paste ngữ cảnh — tốn token, không chia sẻ được cho đồng đội, và không có nguồn để kiểm lại. Nowing biến nghiên cứu thành **tài sản bền**: mọi fact, quyết định và kết quả research được lưu lâu dài, gắn nguồn, và gọi lại được qua REST hoặc MCP từ bất kỳ agent nào — Claude Code, Cursor, OpenCode.

Điểm khác biệt nằm ở **memory nhớ cái gì**. Các memory layer hiện có nhớ hội thoại, tài liệu và SaaS nội bộ. Nowing nhớ thêm **dữ liệu web sống mà nó tự thu thập**: Reddit, YouTube, TikTok, Instagram, Google Search/Maps, Amazon, web crawl — cộng deep multi-step open-web research. Nghiên cứu về một đối thủ làm hôm nay không biến mất khi bạn đóng tab; nó thành thứ agent của bạn tra được tháng sau, kèm link nguồn.

**Vì sao là lúc này.** Memory đang trở thành tiện ích miễn phí của mọi platform lớn — OpenAI, Anthropic, Google, AWS, Oracle, Databricks đều đã ship memory managed trong nửa đầu 2026. Nghĩa là *bán memory như một API* không còn là mô hình kinh doanh. Nhưng không platform nào trong số đó đưa **dữ liệu web sống** vào memory, và không cái nào cho **self-host**. Đồng thời doanh thu đã kiểm chứng của category này nằm ở tầng **workspace nghiên cứu**, không ở tầng memory API (bằng chứng ở §11). Nowing đứng đúng chỗ đó — một workspace mở, tự host được, với bộ nhớ có nguồn sống.

**Mô hình.** Self-host miễn phí hoàn toàn. Cloud trả theo mức dùng. Phân phối bằng open-source + MCP registry, không bằng đội sales.

---

## 3. Vấn đề

**Với người xây AI agent.** Mỗi session mới là bắt đầu lại từ số không. Cách chống đỡ là nhồi file vào context — vừa đắt vừa không đủ, vì thứ agent cần thường không nằm trong repo mà nằm ở nghiên cứu bạn làm tuần trước. Đo được: chạy nhiều coding agent song song khiến dev mất **~4–7 giờ/tuần** chỉ để tái tạo ngữ cảnh (theo domain research ChainLens 2026-07-24).

**Với team nghiên cứu cùng nhau.** Mỗi người một chat riêng. Không ai thấy được đồng đội đã tìm ra gì, đã loại phương án nào, vì sao loại. Hai người research trùng nhau và không ai biết. Khi một fact hoá ra sai, không có cách nào sửa nó ở nơi nó được dùng.

**Với ai cần dữ liệu thật.** Muốn biết người dùng thật nói gì về một sản phẩm thì phải đọc Reddit, comment YouTube, review Amazon và Google Maps. Tự viết scraper cho từng nguồn, tự chống bot, tự bảo trì khi DOM đổi. Xong rồi kết quả nằm trong một file JSON không ai tra lại được.

**Với ai không được gửi dữ liệu ra ngoài.** Nghiên cứu nội bộ, tài liệu khách hàng, phân tích đối thủ — nhiều team đơn giản là không được phép đẩy những thứ đó qua cloud của một AI vendor.

**Cái giá của hiện trạng:** nghiên cứu là thứ đắt nhất một team tạo ra, và cũng là thứ bị mất nhanh nhất. Nó sống trong chat log rồi biến mất.

---

---

## 4. Điều làm nên khác biệt — bản trung thực

> Section này viết sau khi **kiểm chứng độc lập landscape ngày 2026-07-25**, và verify lại bằng code. Một differentiator đã mất; nó được ghi ở đây thay vì bị giấu.

### ✅ Còn nguyên: dữ liệu web sống đi vào memory

**Không một memory layer nào ingest Reddit / YouTube / TikTok / Amazon / Maps.** Gần nhất là [Supermemory với web crawler chung chung](https://supermemory.ai/docs/connectors/web-crawler) (~28/01/2026) — không có connector nào cho các nguồn trên. [Zep](https://help.getzep.com/concepts) ingest chat/business data/document. Mem0 không ingest web. Cognee: không tìm được tài liệu về live web connector.

Đây là phần **khó copy nhất** — và vì một lý do quan trọng: nó là bài toán **data-acquisition** — chi phí, chống bot, pháp lý — không phải bài toán kiến trúc. Thêm một trường `source_id` vào schema thì làm trong một sprint. Xây và bảo trì 14 scraping verb qua hệ thống chống bot thì không.

### ⚠️ ĐÃ MẤT: "memory có citation" không còn là điểm bán

Phải nói thẳng để không viết README sai. Trong ~90 ngày (05–07/2026), ít nhất 5 bên đã ship memory-kèm-nguồn:

| Ai | Khi nào | Gì |
|---|---|---|
| [OpenAI "Memory Sources"](https://help.openai.com/en/articles/8590148) | 05/05/2026, **mọi tier kể cả free** | Hiện memory/chat/file nào tạo ra câu trả lời; sửa/xoá tại chỗ |
| [Zep](https://blog.getzep.com/how-zep-tracks-provenance-in-agent-memory/) | ~14/07/2026 | Provenance **as-graph** — node/edge gắn episode gốc, `valid_at`/`invalid_at`, xoá lan truyền |
| [Oracle AI Agent Memory 26.6](https://www.dbta.com/Editorial/News-Flashes/Oracle-Releases-Oracle-AI-Agent-Memory-266-Delivering-%E2%80%98Memory-With-Receipts-175709.aspx) | ~15/07/2026 | Dùng đúng chữ *"memory with receipts"* |
| [AgentPrizm](https://www.financialcontent.com/article/accwirecq-2026-7-9-agentprizm-launches-governed-ai-agent-memory-platform-that-lets-agents-prove-what-they-remember) | 09/07/2026 | Citation + audit receipt + MCP, free tier 10K memories |
| [memcite](https://pypi.org/project/memcite/0.1.0/) (OSS) | ~07/03/2026 | Buộc cite nguồn **và re-validate trước khi dùng** |

**Hệ quả cho cách kể:** citations vẫn là *tính năng cần có* của Nowing, nhưng **không được dùng làm headline**. Nó là điều kiện cần, giống HTTPS.

**Chỗ dịch sang:** không phải *"memory có citation"* mà **"memory có nguồn sống, tự re-validate"** — freshness và staleness handling. Đây đúng là bài toán mà [chính báo cáo của Mem0 (~18/07/2026)](https://mem0.ai/blog/state-of-ai-agent-memory-2026) thừa nhận chưa giải được: memory staleness ở các fact có relevance cao, và temporal abstraction ở scale.

**Lợi thế cấu trúc của Nowing — verify code 2026-07-25: ĐÚNG VỀ THIẾT KẾ, CHƯA NỐI ĐƯỢC TRONG HIỆN TRẠNG.**

Nguyên lý đúng: `Run` (một dòng mỗi lần gọi scraper) lưu `capability` (ví dụ `reddit.scrape`) **và `input` JSONB** — tức đủ để **chạy lại đúng truy vấn cũ** và kiểm fact còn đúng không. `MemorySourceType` đã có giá trị `SCRAPER_RUN`. Không đối thủ nào có cái này, vì họ không sở hữu đường ingest.

Nhưng chuỗi provenance **chưa nối được**, vì ba lý do cụ thể:

| # | Vấn đề | Bằng chứng |
|---|---|---|
| 1 | **Lệch kiểu dữ liệu** — không lưu được id của Run vào Memory | `Run.id` = `UUID` (`db.py:3155`) nhưng `Memory.source_id` = `Integer` (`db.py:2077`) |
| 2 | **Không có code nào ghi `SCRAPER_RUN`** | `grep SCRAPER_RUN` chỉ ra khai báo enum ở `db.py:572`; không có writer |
| 3 | **Run bị xoá sau 30 ngày** | `RUNS_RETENTION_DAYS = 30` (`capabilities/core/runs.py:33`) → dù nối được thì re-validate cũng hỏng sau một tháng |

⇒ Differentiator mạnh nhất về sau **không phải "chưa build tính năng re-validate"** mà là **"chuỗi provenance đến nguồn sống đang bị chặn ở schema"**. Ba việc trên là tiền đề, và đều nhỏ. Đã đăng ký thành gap trong PRD/epics (xem §8, §12 H-3).

### ✅ Còn nguyên: combo đầy đủ chưa ai làm đủ

> **🔒 VŨ KHÍ NỘI BỘ — KHÔNG ĐƯA VÀO README/LANDING.** Bảng so sánh già rất nhanh: Onyx ship memory một lần là bảng lập tức thành sai. Luật đầy đủ ở §7; quyết định ở §12.5.

| | Live web/UGC → memory | Citation từng fact | Memory bền | Self-host | OSS |
|---|---|---|---|---|---|
| **Nowing** | ✅ | ✅ | ✅ | ✅ | ✅ |
| Perplexity | ✅ | ✅ | ✅ | ❌ | ❌ |
| Onyx (ex-Danswer) | ❌ | ✅ | **❌** | ✅ | ✅ |
| Zep | ❌ | ✅ | ✅ | ~ | ✅ |
| Mem0 | ❌ | ~ (chỉ actor attribution) | ✅ | ✅ | ✅ |
| Supermemory | ~ (crawler chung) | ? | ✅ | ~ (tier Scale) | ✅ |
| Gemini Notebook (ex-NotebookLM) | ✅ | ✅ | ~ (scope theo notebook) | ❌ | ❌ |

Đáng chú ý: **Onyx** — đối thủ gần nhất về hình dạng (MIT, 40+ connector, citations, air-gap, 29K★, 1,000+ enterprise) — **không có memory**. Đó là khoảng trống rõ nhất trong nhóm self-host research workspace.

### 🔻 Moat thật là gì — nói thẳng

Không phải công nghệ độc quyền. Moat của Nowing là:

1. **Head start + integration depth.** Vòng khép kín connectors → index → memory có nguồn → chat có citations → deliverables → 5 client surface. Từng mảnh copy được; cả vòng thì tốn thời gian.
2. **Data-acquisition capability — năng lực THẬT, nhưng KHÔNG phải moat của Nowing.** `[CẢI CHÍNH 2026-07-25 — xem `AD-16.1`, readiness `L-1`]`
   **Phần đúng, giữ nguyên:** **8 nền tảng / 14 scraping verb** (`amazon`, `google_maps`, `google_search`, `instagram`, `reddit`, `tiktok`, `web`, `youtube`) chạy thật trong production — fetcher riêng từng nền tảng, **YouTube InnerTube**, **CAPTCHA solving**, session/pool management, **stealth testbench**, proxy registry + rotation, GeoIP, chặn WebRTC, ẩn canvas fingerprint, DNS-over-HTTPS, headed browser qua Xvfb. Đây là năng lực vận hành có giá trị và nó hoạt động.
   **🔴 Phần SAI, đã gỡ:** bản trước ghi *"engine **tự xây**"*, xếp đây là **moat mạnh nhất**, và dẫn docstring *"the in-house undetectable crawler engine … that form the product's moat"* làm bằng chứng. **Cả ba đều không đứng được.** Nowing là **fork của SurfSense**, và đo bằng git: `app/proprietary/` có **84/84 file trùng đường dẫn**, **73/84 giống hệt byte-for-byte (87%)**, 11 file còn lại khác **2–4 dòng** — tổng **~26/16.600 dòng (0,16%)**, và 26 dòng đó **chỉ đổi chuỗi `SurfSense` → `Nowing`**. Chính **docstring được dẫn ở trên cũng là của SurfSense** — nó là SurfSense nói về code SurfSense, chỉ bị thay tên. Dẫn nó làm bằng chứng cho moat của Nowing là **vòng lặp tự chứng minh**.
   **🔴 "Bảo vệ pháp lý" cũng phải hạ giọng.** BSL 1.1 trên `app/proprietary/**` là thật về mặt file, nhưng `Licensor: Nowing` được đặt trên **code kế thừa**, và cấu trúc dual-license ba tầng cũng copy từ SurfSense. Attribution bị **thay** chứ không được bổ sung, không có `NOTICE`, README không credit. **Đây là cổng thứ hai trước public repo** (`L-1`) và **cần luật sư**, chứ không phải một điểm bán.
   **Cách nói đúng từ giờ:** *vận hành tốt* một crawler engine là năng lực; *sở hữu* nó thì không phải — vì Nowing không viết nó. Moat thật nằm ở mục 1 và 3, và ở research memory (§1). **Đừng dùng crawler engine để biện minh cho BSL.**
3. **Apache-2.0 core + self-host.** Không platform lớn nào cho self-host memory. Với team data-sensitive đây không phải tính năng, mà là điều kiện dự thầu. *(Dùng từ chính xác — §5.1: core Apache-2.0, crawler engine BSL 1.1. Đừng gọi cả sản phẩm là "open source".)*

**Không phải moat, và đừng nói là moat:** citations (table-stakes rồi), MCP-native (mọi người đều có), "rẻ hơn" (đấu free tier là tự thua).

**Rủi ro moat, ghi ở đây để không tự lừa mình:** nếu một incumbent quyết định thêm live-web ingestion, wedge mỏng đi. Đối sách duy nhất là chạy nhanh và đào sâu phần fused research + deliverables. Cửa sổ hẹp.

---

## 5. Giải pháp

Một workspace, gọi được từ mọi nơi.

**Nguồn dữ liệu.** Upload tài liệu (50+ định dạng). Connector OAuth cho Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, Confluence và nhiều nữa. Scraper built-in cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Deep multi-step open-web research.

**Index.** Hybrid — vector (pgvector) + full-text + reciprocal rank fusion. Không dựng graph DB riêng; Postgres là đủ.

**Memory.** Fact, quyết định, observation được lưu lâu dài, mỗi cái có `source_type`/`source_id`, `tags`, `confidence`, embedding. Sửa được, có version history, không xoá cứng. Research thread cho phép tiếp tục một dòng nghiên cứu qua nhiều session.

**Bề mặt.** REST API và **MCP server**. Bốn tool memory — `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact` — cắm vào Claude Code, Cursor, OpenCode. Chat đa agent trong Nowing với citation click được về đúng đoạn nguồn.

**Đầu ra.** Report (export PDF/DOCX/HTML/LaTeX/EPUB), podcast hai host, video presentation, ảnh. Automations theo lịch hoặc sự kiện.

**Chạy ở đâu.** Web, desktop (Electron), browser extension, Obsidian plugin, MCP server. Docker Compose để self-host.

### 5.1 Ranh giới license & OSS/Cloud  `✅ CHỐT 2026-07-25 · ⚠️ SỬA sau khi verify code`

> **Cải chính 2026-07-25.** Bản trước viết *"Nowing public/OSS"* — **không chính xác**. Repo đã dùng mô hình **dual-license** trong code: `LICENSE` ở root ghi rõ `nowing_backend/app/proprietary/**` chịu **Business Source License 1.1**, phần còn lại là **Apache-2.0**. Ranh giới thật là **ba tầng**, không phải hai. Gọi cả sản phẩm là "open source" ở README là **sai về license** — và đúng cái sai khiến dự án bị chỉ trích nặng trên HN.

**Ba tầng license:**

| Tầng | Phạm vi | License | Self-host dùng được? |
|---|---|---|---|
| **Core** | Mọi thứ ngoài `app/proprietary/` — memory, KB, chat, automations, deliverables, 5 client, billing | **Apache-2.0** (OSS thật) | ✅ tự do |
| **Crawler engine** | `nowing_backend/app/proprietary/**` — 84 file Python, ~16.6k dòng: fetcher từng nền tảng, InnerTube, CAPTCHA, session pool, stealth testbench, proxy registry | **BSL 1.1** *(không phải OSS)*. Additional Use Grant: **được** dùng production; **không được** đem chính nó — hoặc sản phẩm/dịch vụ mà giá trị chủ yếu bắt nguồn từ nó — bán cho bên thứ ba như commercial product hoặc **hosted/managed service**. Change Date: 4 năm → Apache-2.0 | ✅ dùng được, **kể cả production** — chỉ không được bán lại dạng hosted |
| **Deep-research engine** | Không nằm trong repo | **Closed-source, hosted** | ❌ Phase 1 · 💳 Phase 2 |

**Bảng feature (dùng cho README):**

| | Self-host (miễn phí) | Cloud (trả theo dùng) |
|---|---|---|
| Memory layer + 4 MCP tool | ✅ | ✅ |
| Knowledge base + hybrid search + citations | ✅ | ✅ |
| **8 nền tảng / 14 scraping verb** (Reddit/YouTube/TikTok/Instagram/Google Search+Maps/Amazon/web crawl) | ✅ *(BSL)* | ✅ |
| Chat đa agent + deliverables + automations | ✅ | ✅ |
| 5 client surface (web/desktop/extension/Obsidian/MCP) | ✅ | ✅ |
| **Deep multi-step open-web research** | Phase 1: ❌ · Phase 2: 💳 | ✅ |

**Ràng buộc kiến trúc:** biên license này được cố định bằng `AD-16` — code Apache-2.0 *được* import từ `app.proprietary`, nhưng đừng move logic Apache-2.0 vào trong biên, và đừng copy logic BSL ra ngoài.

**BSL là điểm bán, không phải điều phải giấu.** Nó cho self-hoster đúng thứ họ cần (chạy production, dữ liệu không rời hạ tầng) và đồng thời chặn việc ai đó đem Nowing đi bán thành SaaS cạnh tranh. Kể thẳng ra sẽ được tôn trọng; kể lấp liếm bằng chữ "open source" thì mất niềm tin.

Đây là ranh giới **sạch**, không phải crippleware: self-host giữ cả wedge chính — live data vào memory — và cloud giữ lại đúng một năng lực — cái đắt nhất về hạ tầng. Không bóp chức năng để bán; giữ lại thứ vốn dĩ tốn tiền chạy. Hệ quả: **deep research là đòn bẩy conversion** self-host → cloud (xem §9).

#### Hai phase

**Phase 1 — cloud-only (hôm nay).** Self-host gọi deep research thì nhận `engine_unavailable` và dùng phần còn lại. Không cần build gì mới; đây là điều FR-38 đã hàm ý. Story `9.1a` chỉ làm nó **trung thực** thay vì **vỡ**.

**Phase 2 — endpoint có metering cho self-host (sau).** Self-host trả tiền theo call để dùng deep research. Bịt lỗ lớn nhất của mô hình OSS/PLG: self-hoster trả $0 mãi mãi.

**Ràng buộc kiến trúc cho Phase 2:** self-host phải đi qua **Nowing Cloud API** (metered, key theo account), **không** gọi engine trực tiếp — cách đó phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5. Chi tiết kỹ thuật thuộc PRD §4.9 + `ARCHITECTURE-SPINE`, không thuộc brief này.

#### Vì sao 1 trước 2

**Phase 1 → Phase 2 là cộng thêm, không phải viết lại.** Chọn Phase 1 không mất gì; nâng lên Phase 2 thì self-host chỉ cần cấu hình thêm một key. Ngược lại, cam kết Phase 2 ngay là mở multi-tenant surface **trước khi** biết có ai self-host thật, và **trước khi** story `9-2` cho số cost để định giá nó.

*(Đã loại: phát hành binary/Docker closed-source cho self-host. Blob closed-source trong repo OSS là pattern bị ghét nhất trong cộng đồng OSS; engine gọi provider trả tiền nên self-hoster không có key của các provider đó thì chạy cũng ra rỗng; và doanh thu $0 kèm gánh nặng license enforcement.)*

#### Ba ràng buộc khi kể

1. **Nói thật trong README, ngay bảng feature.** Nói trước là tiering. Nói sau là bait. Người self-host cài xong mới phát hiện tính năng vỡ là cách phá niềm tin nhanh nhất trong OSS.
2. **Không nêu tên engine ra ngoài.** Nó là hạ tầng nội bộ, không phải sản phẩm (NG-3). Tài liệu công khai gọi là *"Nowing's hosted deep-research engine"*. Không link.
3. **Câu README viết một lần, đúng cho cả hai phase:**
   > *Deep open-web research runs on Nowing's hosted engine.*

   Đúng ở Phase 1 (phải dùng cloud) và vẫn đúng ở Phase 2 (dùng key gọi hosted engine). Không phải viết lại khi nâng cấp.

**Hệ quả cho thứ tự làm:** story `9.1a` (degradation) trở thành điều kiện tiên quyết trước khi public repo. Action item đầy đủ ở **§12 H-1**.

---

## 6. Phục vụ ai

**Chính: người xây AI agent.** Cắm `nowing_mcp` vào Claude Code hoặc Cursor. Agent gọi `nowing_remember` sau mỗi session, `nowing_recall` ở session sau. Thành công = không phải nhồi file vào context nữa, và agent nhớ được quyết định từ ba tuần trước kèm lý do.

**Thứ hai: team nghiên cứu cùng nhau.** Workspace chia sẻ, RBAC Owner/Editor/Viewer, chat real-time có comment và mention, memory dự án chung. Thành công = người mới vào đọc được vì sao team loại một phương án, không phải hỏi lại.

**Thứ ba: người tự host.** Chạy trên infra riêng, chọn LLM/embedding model tuỳ ý, dữ liệu nghiên cứu không rời khỏi hạ tầng của họ.

**Không dành cho:** người cần công cụ duyệt web thủ công (Nowing hướng agent). Doanh nghiệp cần SLA/on-call/compliance chuyên sâu. Người cần native mobile app. Dev solo với ngữ cảnh nhỏ — `CLAUDE.md` đã đủ, đừng cài Nowing.

---

## 7. Cách kể — điều được nói và điều không

> Section này là giá trị chính của brief với mục đích README/landing. Nó biến non-goal thành luật viết copy.

| ✅ NÓI | ❌ KHÔNG NÓI | Vì sao |
|---|---|---|
| "Memory nhớ cả dữ liệu web sống nó tự thu thập" | "Memory có citations" (làm headline) | Citations đã table-stakes — 5 bên ship trong 90 ngày |
| "Self-host miễn phí, dữ liệu không rời hạ tầng của bạn" | "Rẻ hơn Perplexity/Exa" | Đấu free tier là tự bào mòn; và cost chưa đo được |
| **"Apache-2.0 core + BSL 1.1 crawler engine"** — nói rõ hai license | **"Open source"** trần trụi cho cả sản phẩm | **Sai về license.** `app/proprietary/**` là BSL 1.1, BSL tự tuyên bố *không phải* OSS. Đây đúng cái sai khiến dự án bị flame trên HN (§5.1) |
| "Bạn chạy production được; chỉ không được bán lại thành hosted service" | Giấu BSL, để người ta tự phát hiện khi đọc `LICENSE` | BSL là **điểm bán** — nó bảo vệ cả bạn và họ. Nói thẳng thì được tôn trọng |
| "Research workspace có bộ nhớ" | "Memory API / memory layer" | Memory API đang bị bundle miễn phí; doanh thu ở tầng workspace |
| "Nghiên cứu thành tài sản bền, tra lại được" | "Nền tảng bán dữ liệu research" | NG-1: không có owned index; ChainLens *mua* từ Exa |
| "Chat có citations click về đúng đoạn nguồn" (tính năng) | "Perplexity mã nguồn mở" / "Perplexity alternative" | NG-2: red ocean; Perplexica/Vane đã chiếm chỗ đó |
| "Cắm vào Claude Code / Cursor / OpenCode qua MCP" | "MCP-native" (làm differentiator) | Mọi người đều có MCP server rồi |
| "Deep research đa nguồn có trích dẫn" — **kèm ghi rõ là cloud** | Hứa thời gian trả lời cụ thể | Latency chưa validated (NFR-9 State A) |
| "Most memory layers remember what you told them. Nowing also remembers what it went and found." | Gọi tên Mem0 / Zep / Onyx / Perplexity / Cognee / Supermemory | Bảng so sánh già nhanh; OSS phản ứng xấu; tặng đối thủ quyền framing (§4, §12.5) |
| Gọi tên **thứ mình cắm vào**: Claude Code, Cursor, OpenCode, Obsidian, Notion, Slack, Linear, Jira | | Đó là compatibility, không phải cạnh tranh — phải nêu rõ |
| "hosted deep-research engine" | Tên **ChainLens** ở bất kỳ tài liệu công khai nào | NG-3: ChainLens là hạ tầng nội bộ, không public (§5.1) |
| Bảng self-host vs cloud, nói thẳng deep research là cloud | Để người self-host tự phát hiện tính năng vỡ | Nói trước = tiering. Nói sau = bait (§5.1) |
| "NotebookLM alternative" — **gỡ khỏi mọi nơi** | | Định vị pre-pivot, còn sót trong README/`docs/` (OQ-6) |
| | Nhắc `Admin` role, AI File Sorting | Đã xoá ở migration 72 và 172 — nói là vaporware ngược |
| | Định vị VN/tiếng Việt, thanh toán Momo/VNPay | README/landing **tiếng Anh, không có bản Việt** (§12.2) → VN-localization không thuộc câu chuyện Nowing |

**Ngôn ngữ:** README và landing **chỉ tiếng Anh**. Không `README.vi.md`. Kênh beachhead (GitHub, HN, MCP registry) là tiếng Anh.

**Giọng:** nói với developer bằng bằng chứng, không bằng tính từ. Dẫn bằng vấn đề họ đã chịu (mất context, tốn token), không bằng kiến trúc. Show, don't tell.

---

## 8. Nói được gì hôm nay — bằng chứng vs lời hứa

> Với OSS, khoảng cách giữa README và code là thứ giết niềm tin nhanh nhất. Đây là ranh giới.

**✅ Nói được, đã ship (có ở cả self-host):** auth + RBAC 3 role · workspace + invite · upload/parse/index 50+ định dạng · hybrid search · citation panel có chunk window · **8 nền tảng / 14 scraping verb** · OAuth connectors · chat đa agent với tool + subagent · **memory layer** (bảng + endpoint + 4 MCP tool + HNSW/GIN index + `confidence`) · research thread · memory correction có version · deliverables (report/podcast/video/ảnh) · automations schedule+event · 5 client surface · credit wallet + token tracking.

**☁️ Nói được nhưng CHỈ CLOUD:** deep multi-step open-web research. Phải ghi rõ trong bảng feature (§5.1) — không để người self-host tự phát hiện.

**⚠️ Nói được nhưng phải kèm điều kiện:**
- Chất lượng recall — eval gate đang `in-progress` (story `3-9`). **Đừng công bố số precision trước khi gate đóng.**
- Auto-extract memory mỗi lượt — đã có; **spend cap** done (story `8-7`).
- Deep research — **không hứa thời gian**, latency chưa validated (NFR-9); **cost thật đã có**: speed $0.0353 · balanced $0.0482 · quality $0.0671 (2026-08-02).

**❌ Chưa nói được:**
- **Memory tự re-validate nguồn** — differentiator mạnh nhất về sau, nhưng hiện **bị chặn ở schema**, không chỉ là "chưa build": `Run.id` UUID vs `Memory.source_id` Integer · không có code ghi `SCRAPER_RUN` · `RUNS_RETENTION_DAYS = 30`. Xem §4 và §12 H-3
- **Provenance từ memory về đúng lần scrape** — cùng nguyên nhân trên. Hiện chỉ nối được về document/chat
- UI memory browser / research timeline
- Retention + right-to-delete cho memory *(OQ-3, cần chốt trước GA cloud)*

**🚫 Không bao giờ nói:** bán research data · owned web index · Perplexity-parity · tên ChainLens · định vị VN/tiếng Việt.

---

## 9. Thành công trông như thế nào

**Với người dùng — hai khoảnh khắc, không phải một.**

> **Cải chính 2026-07-25.** Bản trước ghi *"khoảnh khắc aha = agent trả lời bằng thứ bạn research tuần trước; nếu không xảy ra trong 15 phút đầu thì onboarding sai."* Câu đó **tự mâu thuẫn**: trải nghiệm "nhớ từ tuần trước" đòi hỏi ít nhất **hai session cách nhau**, nên nó **không thể** xảy ra trong 15 phút đầu. Tách thành hai mốc.

| Mốc | Nội dung | Khi nào | Thiết kế cần gì |
|---|---|---|---|
| **M1 — First-run value** (đo được ngay) | `nowing_recall` trả về thứ hữu ích mà agent **không có trong context** — từ tài liệu vừa upload hoặc một lần scrape | Trong session đầu, mục tiêu **≤15 phút** kể từ lúc cài | Onboarding phải **seed** sẵn nội dung để có gì mà recall. Không seed thì session 1 recall ra rỗng và người dùng kết luận sản phẩm không hoạt động |
| **M2 — Aha thật** (giá trị cốt lõi) | Agent trả lời bằng nghiên cứu từ **session trước** mà không ai paste lại gì | Session thứ 2 trở đi, tính theo ngày | Cần retention thật + recall đủ chính xác (NFR-8) |

**Hệ quả thiết kế, không chỉ là đo lường:** nếu onboarding không seed, **M1 không tồn tại**, và người dùng bỏ đi trước khi kịp tới M2. Đây là yêu cầu onboarding, chưa được ghi ở PRD. `[ASSUMPTION còn lại]` ngưỡng 15 phút cho M1 là mục tiêu thiết kế, chưa validate bằng người dùng thật.

**Với dự án — giai đoạn OSS/PLG:**
- GitHub star và số self-host install `[ASSUMPTION: chưa có target]`
- Số workspace active (≥1 chat hoặc scraper run trong 7 ngày)
- Số lần gọi MCP memory tool mỗi tuần
- **Precision@k và noise rate của `nowing_recall`** — đây là chỉ số chịu lực nhất, xem §11
- Tỷ lệ research thread được tiếp tục

**Với doanh thu:** conversion self-host → cloud. Và §5.1 cho biết **đòn bẩy conversion chính là deep research** — đó là năng lực duy nhất self-host không có.

**Số cụ thể: HOÃN CÓ CHỦ ĐÍCH** `✅ quyết định 2026-07-25`. Chưa chốt target nào, đợi **version cuối của engine deep-research** (ChainLens Epic 43: `43-1` eval-harness GATE 0 → `43-2` planner-DAG → `43-5` cache hit-rate). Lý do: cost và latency của deep research là **đòn bẩy conversion**, mà cả hai đều đang biến động — chốt số bây giờ là chốt trên nền chưa ổn định.

**Hai gate cứng trước khi chốt bất kỳ con số nào:**
1. Story `9-2` + `8-7` cho **số cost thật** — đã đo 2026-08-02: speed $0.0353 · balanced $0.0482 · quality $0.0671. Giá phẳng cũ **under-meter 2.1–3.3×** đã được thay bằng parse `done.usage.costDollars`.
2. Có baseline latency đo được từ phía Nowing (story `9-3`). Đặt ngưỡng trước khi đo là lặp lại đúng lỗi NFR6 phía engine.

**Counter-metric — đừng tối ưu:** số memory được tạo. Nhiều memory rác tệ hơn ít memory đúng. Và đừng nâng timeout để giấu tỷ lệ degradation.

---

## 10. Vision — 2–3 năm

Nếu thành công, Nowing là **nơi nghiên cứu của một team sống lâu hơn người làm ra nó.**

Một người rời công ty; hiểu biết họ tích luỹ vẫn tra được, kèm nguồn, kèm lý do đã loại những phương án nào. Một agent nhận task mới tự recall bối cảnh liên quan mà không ai phải brief. Một fact hoá ra sai được sửa **một lần** và mọi chỗ dùng nó biết điều đó — vì Nowing biết fact đó đến từ đâu và đi kiểm lại được.

Đó là chỗ "nguồn sống" đi từ tính năng thành đặc tính: memory không chỉ nhớ, nó **tự biết mình đã cũ**. Với nghiên cứu về thị trường, đối thủ, sản phẩm — thứ thay đổi mỗi tuần — đây là khác biệt giữa một bộ nhớ và một nhà kho.

Và vì nó mã nguồn mở, self-host được: những team quan tâm nhất đến việc này — team dữ liệu nhạy cảm, team làm nghiên cứu là sản phẩm — là những team dùng được nó mà không phải xin phép ai.

---

## 11. Điều chịu lực nhất — đọc trước khi viết README

Toàn bộ câu chuyện này đứng trên **chất lượng recall**.

Nếu `nowing_recall` trả về nhiễu, lời hứa "nhớ và tiếp tục được" sụp, và Nowing trở thành "một research workspace nữa" — cạnh Onyx (29K★, 1,000+ enterprise) và OpenWebUI (136K★). Đó là lý do NFR-8 / story `3-9` không phải một checkbox kỹ thuật: **nó là điều kiện tồn tại của định vị này** — story đang `in-progress`, baseline ratification pending.

**Hệ quả cho việc kể:** đừng launch ồn ào trước khi eval gate đóng. Với OSS, ấn tượng đầu tiên chỉ có một lần, và một `recall` cho ra rác sẽ được kể lại trên HN lâu hơn bất kỳ feature nào.

**Rủi ro thứ hai — thị trường, không phải tính năng.** Đây là chỗ đặt bằng chứng cho lập luận "doanh thu ở tầng workspace" mà §2 và §7 dựa vào:

- **Không tìm được ARR công khai của bất kỳ memory-layer nào** — Mem0, Zep, Cognee, Supermemory: không ai công bố. Trong khi memory đang bị bundle miễn phí bởi 6 platform lớn (OpenAI, Anthropic, Google, AWS, Oracle, Databricks).
- Doanh thu kiểm chứng được nằm ở tầng workspace: [Glean $300M ARR](https://www.glean.com/press/glean-surpasses-300m-arr-unrivaled-enterprise-context-fuels-ai-adoption) · [Exa ~$10M ARR](https://sacra.com/research/exa-at-10m-growing-11x-yoy/) · Onyx 1,000+ khách enterprise.

Hệ quả: cần **một cheap experiment thật** (landing + checkout + đo conversion) trước khi scale. Bán được hay không là ẩn số lớn hơn xây được hay không.

---

## 12. Quyết định đã chốt & việc còn mở

### ✅ Đã chốt 2026-07-25 (PO Luisphan)

| # | Việc | Quyết định |
|---|---|---|
| **12.1** | Câu một dòng | **Phương án A** — *"Open-source research memory for AI agents — it remembers what it went and found, not just what you told it."* Xem §1 cho subtitle + dòng trả lời "khác gì X" |
| **12.2** | Ngôn ngữ README/landing | **Chỉ tiếng Anh. Không cần bản tiếng Việt.** ⇒ Hệ quả: **VN-localization / Momo / VNPay KHÔNG thuộc câu chuyện Nowing** (nó là chuyện của phía engine, và cũng chưa từng có trong PRD Nowing). Đã ghi thành luật copy ở §7 |
| **12.3** | ChainLens public? | **Không. Chỉ Nowing public.** Engine deep-research closed-source, cloud-only. ⇒ Sinh ra §5.1 mới: ranh giới OSS/Cloud + 3 ràng buộc khi kể |
| **12.4** | Số cho success criteria | **Hoãn có chủ đích** — đợi version cuối của engine deep-research (Epic 43). Hai gate cứng ghi ở §9 |
| **12.5** | Gọi tên đối thủ ở README? | **Không.** Bảng §4 thành vũ khí nội bộ. README trả lời *cái gap, không gọi cái tên*. Nhưng **vẫn gọi tên thứ mình cắm vào** (Claude Code/Cursor/Obsidian/Notion/Slack) — đó là compatibility |
| **12.6** | Deep research cho self-host | **Phase 1 cloud-only → Phase 2 metered endpoint.** Phase 2 đi qua Nowing Cloud API, **không** để self-host gọi engine trực tiếp (phá ADR §4/§5). Loại nhánh binary/Docker closed-source. Chi tiết + lý do ở §5.1 |

> **Truy vết chéo:** 12.3 + 12.6 đã được ghi thành **quyết định D5** trong `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` §8, và propagate sang PRD §1.1 + §4.9 (FR-38) + §6, `AD-15`, `epics.md`, `sprint-status.yaml`. Brief này là **nguồn messaging**; PRD/spine là **nguồn yêu cầu**. Nếu hai bên lệch, PRD thắng về *xây gì*, brief thắng về *kể gì*.

### 📌 Hệ quả cần theo dõi

**H-1 — Story `9.1a` (degradation) đổi lý do tồn tại, và cần đổi thứ tự.** *(Story `9.1` gốc đã tách thành `9.1a` degradation + `9.1b` contract guard — readiness Q-3, 2026-07-25.)*
Trước 12.3 nó là P0 vì *reliability*. Sau 12.3/12.6 nó là P0 vì **mô hình kinh doanh**: thiếu engine mà Nowing hard-fail thì self-host không dùng được, và toàn bộ đường OSS/PLG sụp.

⇒ **`9.1a` đã done 2026-08-02** — public repo không còn bị block về degradation. `9.1b` (contract guard) và `9.2` (cost thật) đã done. `8-7` done.
⇒ Thứ tự cập nhật: `9.1a` → `9.1b` + `9.2` + `8-7` → đo số self-host thật → mở Phase 2 nếu có nhu cầu.
⇒ Cần cập nhật thứ tự trong `epics.md` và `sprint-status.yaml`.

**H-2 — Ranh giới OSS/Cloud đã propagate sang PRD/Spine.** FR-38 + AD-15 đã cập nhật 2026-08-04.

**H-3 — Chuỗi provenance memory → scraper run đang bị chặn ở schema (defect thật, phát hiện 2026-07-25).**
Ba việc, đều nhỏ, và là **tiền đề của differentiator "nguồn sống, tự re-validate"**:
1. `Memory.source_id` là `Integer` (`db.py:2077`) nhưng `Run.id` là `UUID` (`db.py:3155`) → không lưu được link. Cần polymorphic ref hoặc cột `source_uuid` riêng.
2. Không có code nào ghi `MemorySourceType.SCRAPER_RUN` — enum khai báo ở `db.py:572` rồi bỏ đó. Auto-extract từ kết quả scrape phải set nó.
3. `RUNS_RETENTION_DAYS = 30` (`capabilities/core/runs.py:33`) → dù nối được thì re-validate hỏng sau một tháng. Cần giữ Run nào đang được Memory tham chiếu (hoặc copy `capability` + `input` vào chính Memory).

⇒ Đã đăng ký thành **FR-39** (PRD §4.9) và **Story 9.6** (`epics.md`). Không phải P0 cho launch, nhưng **là P0 nếu muốn kể câu chuyện re-validation**.

**H-4 — Onboarding phải seed nội dung.** Xem §9 M1: không seed thì `nowing_recall` ở session đầu trả về rỗng và người dùng kết luận sản phẩm không hoạt động — trước khi kịp tới giá trị thật ở session 2. Yêu cầu onboarding này chưa có trong PRD.

### ✅ M-3 đã giải bằng code (2026-07-25)

Ba `[ASSUMPTION]` trước đó, nay đã kiểm chứng:

| Assumption | Kết luận | Bằng chứng |
|---|---|---|
| Khoảnh khắc "aha" trong 15 phút đầu | **❌ SAI về logic** — "nhớ từ tuần trước" cần ≥2 session, không thể xảy ra ở phút 15. Đã tách thành M1 (first-run, ≤15 phút, cần seeding) và M2 (aha thật, session 2+). | Suy luận, §9 |
| Lợi thế cấu trúc về re-validation | **⚠️ ĐÚNG thiết kế, CHƯA nối được** — `Run` lưu `capability` + `input` JSONB nên **chạy lại được đúng truy vấn cũ**; nhưng 3 blocker ở H-3 | `db.py:2077/3155/572`, `runs.py:33` |
| Data-acquisition là moat bậc 2 | 🔴 **CẢI CHÍNH 2026-07-25 — bản trước nâng lên "bậc 1" là SAI.** Năng lực thật (8 nền tảng / 14 verb, InnerTube + CAPTCHA + stealth testbench + proxy registry, chạy production) nhưng **không phải moat của Nowing**: `app/proprietary/` là **87% byte-identical với SurfSense**, 26/16.600 dòng khác biệt và chỉ là đổi tên. "BSL 1.1 bảo vệ" cũng phải hạ giọng — `Licensor: Nowing` đặt trên code kế thừa, attribution bị **thay**, là **cổng thứ hai trước public repo** (`L-1`) chứ không phải điểm bán. Xem `AD-16.1` | `app/proprietary/**`, `LICENSE`, `git show upstream/main:surfsense_backend/app/proprietary/` |
| Cost thật của deep research | ✅ **ĐÃ ĐO 2026-08-02** — speed $0.0353 · balanced $0.0482 · quality $0.0671. Parse `done.usage.costDollars`, fallback 60k micros. | PRD FR-37, story 9.2, AD-8/AD-15 |

### ⚠️ Còn mở

- **Ngưỡng 15 phút cho M1** — mục tiêu thiết kế, chưa validate bằng người dùng thật.
- **M-3 có thêm kết luận 2026-08-04 (cost thật).** Vẫn còn mở: ngưỡng M1, re-validation schema (H-3).

---

*Brief by Mary (Business Analyst) — 2026-07-25; updated 2026-08-04. Mục đích: input cho README + landing. Companion: `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`, `prd-Nowing-2026-07-22/prd.md`, `prfaq-Nowing-distillate.md`.*

---

## 13. Marketing Strategy

> **Purpose:** Từ "kể gì ở README" (§1-12) sang "tiếp cận ai, qua kênh nào, với thông điệp gì". Section này là cầu nối giữa product brief và execution plan.

### 13.1 Beachhead Expansion

| Phase | Segment | Value Prop | Entry Point |
|-------|---------|-----------|-------------|
| **1 (now)** | AI Agent Builder | "Memory cho agent — nhớ research tuần trước, không phải paste lại" | MCP registry, GitHub, Claude/Cursor community |
| **2 (next)** | Researcher / Analyst | "Research không duplicate, track changes theo thời gian, tự synthesize" | Academic communities, research Twitter, LinkedIn |
| **3 (later)** | Enterprise Team | "Team knowledge bền — người rời công ty, research ở lại" | Outbound sales, partnerships, conference talks |

**Thứ tự logic:** Agent-builder chịu được rough edges + tự spread (MCP/registry). Researcher cần polished UX + validation. Enterprise cần team features + SLA.

### 13.2 Positioning per Segment

| | Agent Builder | Researcher | Enterprise |
|---|---|---|---|
| **Headline** | "Give your AI agent a memory that lasts" | "Research without duplicates, track what changes" | "Your team's research memory, self-hosted" |
| **Pain** | Agent mất context mỗi session | Research trùng lặp, khó track xu hướng | Knowledge mất khi người rời |
| **Differentiator** | MCP-native, self-host, 50+ MCP tools | Entity dedup, cross-source timeline | RBAC, team memory, compliance |
| **Proof** | Claude Code / Cursor integration | Citation + confidence score | Self-host + audit log |

### 13.3 Go-to-Market: PLG + Community-Led

```
┌─────────────────────────────────────────────────────────────┐
│                    NOWING GTM MODEL                          │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │  GitHub OSS  │   │  Community   │   │  Content     │   │
│  │  (top-of-    │   │  (middle-of- │   │  (bottom-of- │   │
│  │   funnel)    │   │   funnel)    │   │   funnel)    │   │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
│         │                  │                  │            │
│         ▼                  ▼                  ▼            │
│  GitHub stars      Discord/Forum      Research reports    │
│  HN discussions    Reddit AMAs        Comparison posts    │
│  MCP registry      Twitter/X          Case studies        │
│  npm installs      LinkedIn           Tutorials           │
│         │                  │                  │            │
│         └──────────────────┴──────────────────┘            │
│                            │                               │
│                            ▼                               │
│                    Workspace signup                        │
│                    (free self-host)                        │
│                            │                               │
│                            ▼                               │
│                    Cloud conversion                        │
│                    (deep research = wedge)                 │
└─────────────────────────────────────────────────────────────┘
```

### 13.4 Marketing Channels (Prioritized)

| # | Channel | Segment | Effort | Impact | Tactics |
|---|---------|---------|--------|--------|---------|
| 1 | **GitHub** | Agent Builder | Low | High | README + discussions + good first issues + star campaign |
| 2 | **Hacker News** | Agent Builder | Low | High | Show HN (timing: Tue-Thu PST morning) |
| 3 | **Reddit** | Agent Builder | Medium | High | r/selfhosted, r/MachineLearning, r/ClaudeAI — value posts, not spam |
| 4 | **Twitter/X** | Agent Builder + Researcher | Medium | High | Research threads, product demos, engagement with AI community |
| 5 | **LinkedIn** | Researcher + Enterprise | Medium | Medium | Thought leadership, case studies, company page |
| 6 | **Email Outreach** | Researcher + Enterprise | High | High | Research → personalized email → gift link (see §13.6) |
| 7 | **Content/Blog** | All | Medium | Medium | "State of X" reports, comparisons, tutorials |
| 8 | **Partnerships** | Enterprise | High | High | AI agent platforms, research tools |

### 13.5 Launch Strategy

| Phase | When | Goal | Activities |
|-------|------|------|-----------|
| **0. Soft Launch** | Now → Beta | Build audience + feedback | GitHub README, HN Show, Discord, Reddit AMA |
| **1. Beta** | After Epic 13 complete | Validate with real users | Invite-only, gift (free credits), collect testimonials |
| **2. Public Launch** | After beta validation | Scale acquisition | Product Hunt, broader HN, PR, partnerships |
| **3. Enterprise** | Post-public | Revenue | Outbound sales, conference talks, case studies |

### 13.6 Growth Engine: Dogfooding Nowing

> **Key insight:** Nowing's own capabilities = marketing automation. Use Nowing to market Nowing.

| Marketing Activity | How Nowing Helps | Example |
|-------------------|-----------------|---------|
| **Prospect Research** | Use scrapers to find companies hiring researchers, using AI agents | Research "hiring data engineer" → find companies → track news |
| **Personalized Outreach** | Auto-synthesis → personalized email per prospect | "I saw you hired 3 data engineers this quarter — here's how Nowing tracks talent trends" |
| **Lead Tracking** | Canonical entities for prospects + timeline | Company X: funding → hiring → product launch → trigger outreach |
| **Content Creation** | Research → synthesis → blog post/thread | "State of AI Agent Memory 2026" generated by Nowing itself |
| **Social Automation** | Research → draft → schedule posts | Track trending topics → auto-draft Twitter threads |
| **Gift/promo campaigns** | Track who redeemed → follow up | Send gift link → track activation → personalized follow-up |

### 13.7 Email Outreach Playbook (Concrete)

```
Step 1: RESEARCH (Nowing scraper)
├── Find companies hiring researchers/analysts
├── Track funding news, product launches
├── Build lead list as canonical entities
│
Step 2: PERSONALIZE (Nowing synthesis)
├── Research each prospect's recent news
├── Generate personalized email draft
├── Include specific insight + gift link
│
Step 3: SEND (automation)
├── Schedule emails (personalized timing)
├── Track opens/clicks in workspace
│
Step 4: FOLLOW UP (automation)
├── If no response in 3 days → follow-up with new insight
├── If opened but no click → different angle
└── If clicked but no signup → offer help
```

**Gift strategy:**
- "Free deep research credits — no credit card"
- "Self-host free forever + 1000 cloud credits"
- "Enterprise pilot — free for 30 days"

### 13.8 Content Strategy

| Content Type | Frequency | Channel | Topic Examples |
|-------------|-----------|---------|----------------|
| **Research Reports** | Monthly | Blog, LinkedIn, Twitter | "State of AI Memory", "VN E-commerce Trends" |
| **Comparison Posts** | Bi-monthly | Blog, HN, Reddit | "Nowing vs Manual Research", "Entity vs Document" |
| **Case Studies** | Quarterly | Blog, LinkedIn | "How X company uses Nowing for Y" |
| **Product Demos** | Weekly | Twitter, YouTube | 2-min feature demos, before/after |
| **Tutorials** | Weekly | Blog, Docs | "Track competitor in 5 minutes", "Build research agent" |
| **Transparency Posts** | Monthly | HN, Reddit | Open revenue, open metrics (OSS credibility) |

### 13.9 Pricing/Packaging Strategy

| Tier | Price | Target | Includes |
|------|-------|--------|----------|
| **Self-Host** | Free | Agent Builder, Privacy-focused | All features except deep research |
| **Pro (Cloud)** | $29-49/mo | Individual researcher | + Deep research, more sources, team features |
| **Team** | $99-199/mo | Small team (5-20) | + RBAC, shared memory, analytics |
| **Enterprise** | Custom | Large org | + SLA, support, self-host option, compliance |

**Conversion wedge:** Deep research (cloud-only in Phase 1) → self-host users who need it convert to cloud.

### 13.10 Partnerships

| Partner Type | Examples | Value |
|-------------|----------|-------|
| **AI Agent Platforms** | Claude Code, Cursor, OpenCode | Distribution via MCP/registry |
| **Research Tools** | Zotero, Notion, Obsidian | Integration + cross-promotion |
| **Data Providers** | Exa, Tavily, Jina | Better search + co-marketing |
| **Communities** | AI meetups, research groups | Word-of-mouth + feedback |

### 13.11 Success Metrics (Marketing)

| Metric | Target (6 months) | Measurement |
|--------|-------------------|-------------|
| GitHub Stars | 5K+ | GitHub API |
| Self-Host Installs | 1K+ | Docker pulls + telemetry (opt-in) |
| Cloud Signups | 500+ | Stripe |
| Active Workspaces | 200+ | Backend analytics |
| Email Response Rate | 15%+ | Email tool |
| Content Reach | 50K/month | Analytics |

### 13.12 Immediate Next Actions

| # | Action | Owner | Timeline |
|---|--------|-------|----------|
| 1 | Create marketing workspace in Nowing | Luis | Day 1 |
| 2 | Set up prospect research (scrapers + entities) | Luis | Day 1-2 |
| 3 | Build lead list (50 prospects) | Luis + Nowing automation | Week 1 |
| 4 | Draft email templates + gift links | Luis | Week 1 |
| 5 | Set up content calendar (4 weeks) | Luis | Week 1 |
| 6 | Start GitHub community building (README, discussions) | Luis | Week 1-2 |
| 7 | Prepare HN Show post | Luis | Week 2 |
| 8 | Launch email outreach campaign | Luis + automation | Week 2 |

---

> **`[ASSUMPTION]`** segments: beachhead expansion theo thứ tự Agent Builder → Researcher → Enterprise. Có thể adjust nếu bạn prioritize khác.
>
> **`[ASSUMPTION]`** pricing: dựa trên competitor landscape + Nowing's value proposition. Chưa validate với users.
>
> **`[ASSUMPTION]`** timeline: Beta sau Epic 13 complete (~2-4 weeks). Có thể adjust.
>
> **`[ASSUMPTION]`** team: 1 person (Luis) + automation. Channels prioritized cho solo operator.

