---
title: PRFAQ — Nowing Vietnam Job Market Research
project: Nowing
date: 2026-08-05
author: Mary (Business Analyst) for Luisphan
release_date: 2026-09-15
status: proposal
---

# PRFAQ: Nowing Vietnam Job Market Research

**Press Release Date:** 2026-09-15 (pilot / 8-week validation window)
**Author:** Mary (Business Analyst)
**Status:** Proposal — pending PO/team approval and pre-flight validation

---

## 1. Press Release

**Hà Nội, 15 tháng 9 năm 2026** — Nowing, nền tảng bộ nhớ nghiên cứu dài hạn mã nguồn mở cho AI agents và research teams, hôm nay mở **pilot Nowing Vietnam Job Market Research** — một **wedge thử nghiệm 8 tuần** giúp nhà tuyển dụng, headhunter và nhà phân tích nhân sự tại Việt Nam theo dõi thị trường việc làm theo thời gian thực, tổng hợp dữ liệu từ nhiều nguồn, và lưu lại dưới dạng research memory có nguồn trích dẫn.

Trong giai đoạn pilot, Nowing kết nối **ba nguồn chính: VietnamWorks, TopCV, và ITviec**. Người dùng có thể đặt câu hỏi tự nhiên như: *“Có bao nhiêu vị trí Data Engineer ở Hà Nội đang tuyển? Lương trung bình trên VietnamWorks, TopCV, ITviec khác nhau thế nào? Có tin nào trùng lặp giữa các nguồn?”* — Nowing sẽ gom dữ liệu từ 3 nguồn, chuẩn hóa, loại trùng, tính điểm tin cậy, và trả lời kèm URL nguồn gốc.

Tính năng này mở rộng từ kiến trúc aggregator đã được chứng minh với thị trường bất động sản Việt Nam (`vn_bds.aggregate`), áp dụng mô hình tương tự cho dữ liệu tuyển dụng: **multi-source aggregation + long-term memory + citations + self-host/cloud dual-license**.

“Thị trường tuyển dụng Việt Nam đang tăng trưởng nhưng dữ liệu bị phân mảnh,” — Luisphan, Product Owner của Nowing, cho biết. “Chúng tôi không xây thêm một job board nữa. Chúng tôi thử nghiệm một **lớp research memory** giúp người dùng so sánh nguồn, theo dõi xu hướng, và kiểm chứng từng dữ liệu qua 8 tuần pilot.”

Nowing Vietnam Job Market Research hiện khả dụng trong giai đoạn **pilot giới hạn** trên cloud pay-as-you-go và hoàn toàn miễn phí cho self-hosted deployments. Người dùng có thể truy cập qua web dashboard, API, hoặc MCP server để tích hợp vào Claude, Cursor, và các AI agent khác.

**Để bắt đầu, truy cập:** https://nowing.net/docs/connectors/native/vn_jobs

> **Lưu ý pilot:** Pilot này nhằm **validate demand và ToS compliance** chứ không phải ra mắt sản phẩm hoàn chỉnh. Sau 8 tuần, team sẽ quyết định: (a) mở rộng, (b) thu hẹp, hoặc (c) dừng.

---

## 2. Customer FAQ

### Q1: Nowing Vietnam Job Market Research khác gì so với VietnamWorks, TopCV, hay ITviec?

**A:** VietnamWorks, TopCV, ITviec là **job board** — nơi đăng tin tuyển dụng và ứng viên nộp hồ sơ. Mỗi nền tảng chỉ có dữ liệu của riêng mình. Nowing là **lớp research intelligence**.

Trong giai đoạn **pilot**, Nowing kết nối **VietnamWorks, TopCV, và ITviec**:
- Tổng hợp dữ liệu từ nhiều nguồn trong một workspace.
- Phát hiện tin đăng trùng lặp giữa các nguồn.
- So sánh lương và mô tả công việc giữa các nguồn.
- Gắn `conflict` flag khi các nguồn ghi khác nhau về lương hoặc địa điểm.
- Chuẩn hóa lương, địa điểm, loại công việc, kinh nghiệm.
- Lưu lại theo thời gian để theo dõi xu hướng.
- Mỗi dữ liệu có URL nguồn và timestamp để kiểm chứng.
- Hỗ trợ AI agents qua MCP.

Nowing **không phải ATS**: bạn không thể quản lý đơn ứng tuyển, lên lịch phỏng vấn, hoặc gửi offer qua Nowing.

### Q2: Tôi là HR manager, tôi dùng được gì?

**A:** Bạn có thể:
- Tìm kiếm và so sánh việc làm theo kỹ năng, địa điểm, lương.
- Theo dõi xu hướng tuyển dụng của đối thủ hoặc ngành.
- Benchmark lương theo chức danh, cấp bậc, khu vực.
- Lưu kết quả vào workspace và cài đặt automation gửi báo cáo định kỳ.
- Xuất dữ liệu kèm nguồn để chia sẻ với quản lý.

### Q3: Dữ liệu có chính xác và cập nhật không?

**A:** Dữ liệu được lấy trực tiếp từ các job board công khai, có timestamp. Mỗi kết quả đi kèm `confidence_score` (0–1) dựa trên:
- Số nguồn cùng ghi nhận (overlap).
- Độ tương đồng lương giữa các nguồn (salary consistency).
- Độ mới của tin đăng (freshness).
- Độ tin cậy của từng nguồn.

Nếu các nguồn mâu thuẫn về lương, Nowing sẽ gắn `salary_conflict` flag và hiển thị khoảng lương từ từng nguồn.

### Q4: Tôi có thể tự host miễn phí không?

**A:** Có. Nowing giữ nguyên mô hình **open-core**:
- **Self-host**: miễn phí, bạn chạy trên infra riêng, giữ dữ liệu.
- **Cloud**: trả theo dùng, phù hợp khi không muốn tự quản lý hạ tầng.

Fetchers job board nằm trong `app/proprietary/platforms/` theo BSL 1.1 — được dùng production nhưng không được bán lại dưới dạng hosted service.

### Q5: Có hỗ trợ tiếng Việt không?

**A:** Có. Hệ thống xử lý tiếng Việt có dấu, từ khóa tìm kiếm có thể dùng tiếng Việt, và agent chat có thể trả lời bằng tiếng Việt.

### Q6: Nowing có lưu trữ CV hoặc thông tin cá nhân của ứng viên không?

**A:** **Không.** Trong MVP, Nowing chỉ thu thập **tin tuyển dụng công khai** (title, công ty, địa điểm, lương, mô tả công việc, yêu cầu, ngày đăng). Chúng tôi không scrape CV, số điện thoại, email, hoặc thông tin cá nhân của ứng viên.

Mặc dù tin đăng là công khai, pipeline của chúng tôi vẫn áp dụng **PII detection/redaction** cơ bản (regex phone/email, named-entity candidates) để tránh lưu trữ thông tin cá nhân vô tình. Dữ liệu có PII sẽ bị loại bỏ hoặc mask trước khi vào memory.

### Q7: Giá như thế nào?

**A:** Trong giai đoạn **pilot**, cloud pay-as-you-go theo số query và số item trả về. Ví dụ ước tính (cần xác nhận sau technical spike):
- 1 query tổng hợp 50 tin từ VietnamWorks: ~$0.03–$0.08.
- Có thể mua gói credits với giá ưu đãi.
- Self-host hoàn toàn miễn phí (tự trả chi phí infra).

Giá chính thức sẽ được công bố **sau khi xác nhận rate limit, cost thực tế, và ToS của VietnamWorks**. Trong pilot, mục tiêu là thu thập usage data để định giá.

### Q8: Tôi có thể tích hợp vào hệ thống của mình không?

**A:** Có. Nowing expose qua:
- REST API
- MCP server (cho Claude, Cursor, OpenCode, v.v.)
- Web dashboard

Bạn có thể gọi `vn_jobs.aggregate` từ automation hoặc agent của riêng mình.

### Q9: Pilot có giới hạn gì?

**A:** Pilot kéo dài **8 tuần**, kết nối **VietnamWorks, TopCV, và ITviec** trong P0, và hỗ trợ tối đa **2,000 job listings/ngày** để kiểm soát cost/risk. Một số nguồn có thể bị degrade (tạm dừng) nếu gặp anti-bot hoặc ToS issue. Sau 8 tuần, Nowing sẽ đánh giá:
- Số workspace active và tần suất sử dụng.
- Phản hồi người dùng về giá trị.
- ToS compliance và rate-limit từ VietnamWorks.

Quyết định tiếp theo: mở rộng sang TopCV/ITviec, thu hẹp, hoặc dừng.

### Q10: Dữ liệu của tôi có an toàn không?

**A:** Nowing không lưu CV hoặc thông tin cá nhân của ứng viên. Dữ liệu thu thập là tin tuyển dụng công khai. Trong pilot, dữ liệu được xử lý qua pipeline PII detection/redaction và lưu trong workspace của bạn (cloud hoặc self-host). Bạn có thể xóa workspace hoặc export dữ liệu bất kỳ lúc nào.

---

## 3. Internal FAQ

### Q1: Tại sao chọn HR/recruitment là vertical tiếp theo — và tại sao chỉ là pilot?

**A:**
- Thị trường tuyển dụng Việt Nam lớn, tăng trưởng, và đau đớn vì dữ liệu phân mảnh.
- Pain point rõ: 80% employer khó tìm ứng viên, 86% lo lương tăng (Reeracoen 2026).
- Có public data source sẵn (VietnamWorks API no-auth) giúp P0 nhanh.
- Reuse kiến trúc `vn_bds.aggregate` vừa ship, giảm rủi ro kỹ thuật.
- Không đụng độ trực tiếp với job board hay ATS — định vị research layer khác biệt.

**Tuy nhiên, chúng ta chưa validate:**
- Willingness-to-pay cho cross-platform research (thay vì miễn phí report).
- ToS của VietnamWorks/TopCV/ITviec.
- Anti-bot feasibility cho TopCV/ITviec.
- Pháp lý Việt Nam (có bị xếp là employment service provider không?).
- Cost thực tế và rate-limit.

Vì vậy, đây không phải "ra mắt vertical" mà là **wedge thử nghiệm 8 tuần** để thu thập bằng chứng. P0 bao gồm cả 3 nguồn để validate đúng giá trị cross-platform. Nếu validation thất bại, chúng ta dừng hoặc xoay.

### Q2: Tính năng này khớp với direction Nowing = sản phẩm, ChainLens = engine không?

**A:** Khớp. HR vertical sử dụng **Nowing's own connectors and scrapers**, không phụ thuộc ChainLens. Đây là **vertical expansion của product surface**, không phải engine work. Trong pilot, nó là một **use case mới cho agent builder / research team** — không phải pivot khỏi beachhead hiện tại.

### Q3: Có vi phạm Non-Goals NG-1, NG-2, NG-3 không?

**A:**
- **NG-1 (không bán research data kiểu Exa):** Cần phân biệt rõ.
  - **Không bán:** raw job-posting database, bulk export, hoặc API trả về danh sách tin đăng để khách hàng tự dùng làm data feed.
  - **Có thể bán (subject to SCP):** sử dụng job data bên trong research tool / agent — người dùng trả tiền cho **query, analysis, và memory**, không phải cho dữ liệu thô.
  - Đề xuất: **raise SCP trước khi pilot go-live** để xác nhận business model pilot không vi phạm NG-1.
- **NG-2 (không đua Perplexity parity):** Đây là vertical research B2B, không phải consumer search. Đảm bảo non-goal: không làm job seeker consumer search trong pilot.
- **NG-3 (ChainLens không thành sản phẩm độc lập):** Không liên quan ChainLens.

### Q4: Kỹ thuật, có nên generalize `bds_aggregator` thành `vertical_aggregator` ngay?

**A:** **Không.** Lý do:
- BDS aggregator vừa ship, pattern chưa được validate trên vertical thứ hai.
- Jobs và BDS có domain khác biệt lớn (salary vs price, skills vs area, company vs project).
- Theo `ponytail` rule: copy-modify trước, abstract sau khi có 2–3 vertical stable.
- Effort P0 ước tính **18–24 dev-days**: 3 scrapers (VietnamWorks API + TopCV/ITviec anti-bot), PII redaction, copy-modify aggregator, tests, MCP/billing wiring. Cần spike TopCV/ITviec anti-bot để xác nhận.

### Q5: P0 scope cụ thể là gì?

**A:**
1. `vietnamworks.scrape` capability (public API no-auth).
2. `topcv.scrape` capability (HTML/JSON scraping + anti-bot).
3. `itviec.scrape` capability (HTML/JSON scraping + anti-bot).
4. `vn_jobs.aggregate` capability với 3 nguồn.
5. Capability/MCP/billing wiring.
6. PII detection/redaction pipeline (basic regex/NER).
7. Unit + integration tests.

**P1 (deferred sau pilot):** research playbook — chỉ triển khai nếu pilot đạt go/no-go.

### Q6: Cost và pricing dự kiến?

**A:**
- **Cost P0 ước tính:**
  - VietnamWorks API: ~1,000 micros/item.
  - TopCV/ITviec scraping: ~2,000–5,000 micros/item (bao gồm anti-bot/proxy cost).
- **Aggregate query fee:** Tạm để **5,000 micros/query** + child scraper costs.
- **Ví dụ:** query 50 items (trung bình 17/source) = $0.005 + 50×$0.003 = ~$0.20 (chưa tính fixed cost).
- **Pricing pilot:** cung cấp **miễn phí hoặc heavily discounted credits** để thu thập usage + feedback. Không bán với margin cố định cho đến khi có cost thực.
- **Go-live pricing:** sẽ quyết định sau 8 tuần dựa trên unit economics thực.

### Q7: TAM/SAM/SOM?

**A:** Các con số dưới đây là **giả định cần validate** trong 8 tuần pilot, không phải số cam kết.

| Metric | Hypothesis | Validation Method |
|---|---|---|
| **TAM** | Recruitment data/tools tại VN ~$50–100M/năm | Top-down từ báo cáo thị trường; cần cross-check với độ lớn HR-tech VN ($110M) |
| **SAM** | SMB/mid-market employers + recruiters cần cross-platform intelligence ~$5–15M/năm | Customer interviews: 10–15 HR manager / recruiter xác nhận nhu cầu và budget |
| **SOM Year 1** | 100–300 workspaces active, ~$1,000–$2,000 MRR trực tiếp | Pilot usage data, waitlist, pre-commit |

**Strategic value (chưa định lượng):** tăng conversion, retention, và mở rộng use case cho agent builder. Sẽ đo lường qua activation rate của workspace có bật `vn_jobs`.

### Q8: Rủi ro pháp lý?

**A:**
- **ToS review (pre-condition):** Phải review ToS của VietnamWorks, TopCV, và ITviec trước khi pilot. Cần trả lời: API/scraping có cho phép automated access? Có cho phép commercial use? Có yêu cầu attribution?
- **PII:** Chỉ scrape public job postings, không CV/contact. Tuy nhiên JD có thể chứa PII (tên, số điện thoại, email). Áp dụng PII detection/redaction.
- **Employment Law 2013 / Decree 23/2021:** Cần legal counsel opinion để xác nhận Nowing không bị xếp vào "dịch vụ môi giới việc làm" (vì không matching, không giới thiệu, không thu phí từ người tìm việc).
- **BSL 1.1:** Fetchers nằm trong `app/proprietary/platforms/`. Cloud offering phải đảm bảo giá trị nằm ở aggregator + memory + citations (Apache-2.0 core), không phải bán lại BSL fetchers.

### Q9: Metrics thành công (pilot)?

**A:**
| Metric | Target (8 tuần) | Why |
|---|---|---|
| Workspaces active ≥3 days/week | 10+ | Validate real demand |
| Aggregate queries | 100+ | Usage signal |
| Job listings indexed/day (3 sources) | 2,000+ | Coverage |
| Cross-source deduped listings/day | 1,000+ | Quality coverage |
| Confidence score top 80% | ≥0.6 | Quality |
| Dedupe accuracy | ≥90% | Quality |
| Cost per aggregate query | xác định baseline | Không target cố định, chỉ đo thực |
| Customer interviews | 10+ | Validate willingness-to-pay |
| ToS/legal review | complete for all 3 | Gate go/no-go |
| Anti-bot POC | pass for TopCV + ITviec | Gate go/no-go |

### Q10: Có cần thay đổi PRD/epics không?

**A:** Nếu phê duyệt pilot, cần:
- Thêm FR mới hoặc mở rộng FR-6 (scrapers) và FR-39 (provenance) trong PRD.
- Thêm Epic 11 (pilot scope) và `epics.md`.
- Cập nhật sprint-status khi story được giao.
- Thêm validation tasks và go/no-go criteria vào sprint-status.

### Q11: Kế hoạch validate thị trường?

**A:**
1. **Customer discovery interviews:** 10–15 HR manager, recruiter, talent analyst tại Hà Nội / TP.HCM.
2. **Landing page / waitlist:** trang "Vietnam Job Market Research on Nowing" với CTA đăng ký pilot; đo conversion.
3. **Pilot usage:** mở 3 scrapers cho 20–50 workspace beta; theo dõi tần suất và retention.
4. **Willingness-to-pay test:** khảo sát giá $0.03–$0.08/query xem phản ứng.

Chi tiết trong `_bmad-output/planning-artifacts/research/market-validation-hr-vertical-2026-08-05.md` (tạo sau).

### Q12: Kế hoạch ToS và legal review?

**A:**
1. **Week 1:** Thu thập ToS VietnamWorks, TopCV, ITviec; tóm tắt clauses liên quan automated access, data reuse, commercial use.
2. **Week 1–2:** Technical spike VietnamWorks API; anti-bot POC cho TopCV/ITviec.
   - VietnamWorks spike: **DONE** — API 200, pagination `hitsPerPage`, no CAPTCHA, rate limit OK in short test.
   - ITviec spike: **DONE** — HTML parseable, no Cloudflare, salary hidden.
   - TopCV spike: **BLOCKED by Cloudflare** — cần headless/residential proxy/bypass service POC.
3. **Week 2:** Legal counsel review về employment service provider classification.
4. **Week 3:** SCP về NG-1 ambiguity.
5. **Go/No-Go:** Pilot chỉ bắt đầu sau khi ToS cả 3 nguồn cho phép, anti-bot POC pass cho TopCV, và legal counsel xác nhận không cần license môi giới.

### Q13: Cách xử lý PII trong job data?

**A:**
- **Input:** chỉ thu thập public job postings.
- **Detection:** regex cho phone (Vietnam), email; NER nhẹ cho tên người trong JD.
- **Spike findings (VietnamWorks, 100 samples):**
  - 0 phone/email trong `jobDescription` / `jobRequirement`.
  - Field `emailAddress` không xuất hiện.
  - `contactName` xuất hiện 96%, nhưng thường là tên bộ phận ("People Department"), không phải cá nhân — vẫn cần audit.
- **Action:** mask hoặc drop phone/email; flag bài đăng có chứa tên ứng viên cá nhân; lưu `contactName` chỉ nếu không phải tên người.
- **Storage:** không lưu raw HTML đầy đủ; chỉ lưu normalized fields đã redact.
- **Audit:** log PII detection stats (không log nội dung PII).
- **Retention:** theo AR-4, xóa job data khi workspace bị xóa hoặc theo policy.

### Q14: Điều kiện go/no-go sau pilot?

**A:**

**Go (mở rộng P1):**
- ≥10 workspaces active ≥3 ngày/tuần.
- ≥100 aggregate queries trong 8 tuần.
- ToS cả 3 nguồn cho phép; legal counsel xác nhận không cần license môi giới.
- Anti-bot POC pass cho TopCV/ITviec (hoặc source đó bị disable gracefully).
- Unit economics khả thi: cost/query ≤$0.10 và ≥3/10 người được phỏng vấn sẵn sàng trả ≥$0.05/query.

**No-go (dừng hoặc xoay):**
- <5 workspaces active.
- Bất kỳ nguồn nào thay đổi API/ToS cấm.
- Legal counsel xác định cần license môi giới việc làm.
- Anti-bot TopCV/ITviec không vượt qua và không thể degrade một cách hợp lý.
- Cost/query >$0.15 hoặc không ai sẵn sàng trả.

---

## 4. Customer Quote (placeholder)

> *“Trước đây tôi phải mở 4 tab VietnamWorks, TopCV, ITviec, LinkedIn để so sánh. Giờ tôi hỏi Nowing một câu, nó gom hết, chỉ rõ nguồn nào, lương khoảng bao nhiêu, và còn lưu lại để tuần sau tôi hỏi tiếp.”*
>
> — HR Manager, công ty công nghệ 80 người, Hà Nội

---

## 5. Call to Action

**Người dùng:** Đăng ký tại https://nowing.net và tạo workspace để thử Vietnam Job Market Research.

**Developers:** Cài `nowing_mcp` và gọi `nowing_vn_jobs_aggregate` từ Claude, Cursor, hoặc agent framework của bạn.

**Self-hosters:** Kéo repo mới nhất, chạy Docker Compose, bật `vietnamworks.scrape` và `vn_jobs.aggregate`.

---

## 6. Evidence Summary

- VietnamWorks public API: `POST https://ms.vietnamworks.com/job-search/v1.0/search`, no auth, ~11.5k active postings for "Data Engineer" (spike confirmed 200 OK, `hitsPerPage` max 100, no CAPTCHA, rate limit OK in short test).
- ITviec: `GET https://itviec.com/it-jobs/{keyword}` trả 200, HTML server-rendered, parseable, salary hidden for non-logged-in users.
- TopCV: `GET https://www.topcv.vn/viec-lam/{keyword}` trả 403 Cloudflare "Just a moment..." challenge — cần anti-bot POC.
- Open-source reference: `kalil0321/ats-scrapers`, `epsi10nvn/vn-job-data-crawler`, `vnk8071/goodjobs`.
- Market data: Reeracoen Employer Hiring Study 2026, ManpowerGroup MEOS Q3 2026, VietnamWorks Q2/2026 Hiring Market Report.
- Adversarial review: `_bmad-output/planning-artifacts/review-prfaq-hr-vertical-adversarial-2026-08-05.md`
- Market research: `_bmad-output/planning-artifacts/research/market-vietnam-hr-recruitment-research-2026-08-05.md`
- Market validation plan: `_bmad-output/planning-artifacts/research/market-validation-hr-vertical-2026-08-05.md`
- VietnamWorks API spike: `_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md`
- TopCV/ITviec spike: `_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md`
- Feature brief: `_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md`
