# Sprint Change Proposal — Nowing AI gen lead / lead intelligence positioning

**Status:** ADOPTED 2026-08-10  
**Date:** 2026-08-10  
**Author:** Mary (Business Analyst)  
**Source:** `reviews/ai-gen-lead-gap-analysis-2026-08-10.md`

---

## 1. Tóm tắt vấn đề

Ngày 2026-08-10, PRD `prd.md` đã được cập nhật thêm `§1.0 Lead Intelligence`, 7 FR mới (FR-63..FR-69), Epic 21 — Lead Gen Intelligence, và AD-36..AD-42 trong `ARCHITECTURE-SPINE.md`. Đây là một thay đổi định vị lớn so với baseline.

Tuy nhiên, thay đổi này **chưa có SCP** trong khi:
- PRD §2.4 đang `FREEZE POSITIONING tới 2026-08-24` và yêu cầu "đổi phải qua SCP mới".
- Non-Goal NG-1 cấm bán research data, nhưng FR-65 (Enriched Contact Data) và FR-69 (Outcome-Based Pricing, `$0.50/lead enriched`) đang đi vào vùng bán structured contact/lead data.
- PII pipeline cho HR (FR-47 / AD-25: redact phone/email/names) mâu thuẫn với lead gen (AD-36 lưu `VerifiedContact` với email/phone).
- Các tài liệu chiến lược/GTM (product-definition, business-plan, GTM, marketing-plan, 3-year roadmap, domain-expansion research) vẫn ở trạng thái cũ, chưa phản ánh lead intelligence.
- `domain-expansion-research-report` khuyến nghị tránh Zalo/LinkedIn vì anti-bot + legal risk, trong khi Epic 21 chọn Zalo/LinkedIn làm kênh chính.

SCP này đề xuất cách xử lý các conflicts trên.

---

## 2. Phân tích impact

### Epic impact
- **Epic 21 (Lead Gen Intelligence)** — scope gồm 7 stories (21.1-21.7), mục tiêu thị trường Vietnam (white space, no AI-native lead gen player).
- **Epic 12 (HR/Recruitment Vertical)** — vẫn dùng VietnamWorks/TopCV/ITviec nhưng với mục đích nghiên cứu HR, không phải sales signal. Cần rõ ranh giới dữ liệu HR (redact PII) vs. lead data (enrichment).
- **Epic 18 (Vertical Client Platform)** — đang SCP riêng ngày 2026-08-10, không xung đột với SCP này.

### Product/Architecture impact
- Vision: từ "knowledge intelligence platform" sang "lead intelligence + knowledge intelligence platform".
- Target user: thêm sales team / SDR làm beachhead.
- Pricing: thêm outcome-based (`$0.50/lead enriched`, `$50/meeting booked`) bên cạnh seat/credit.
- PII: cần phân loại dữ liệu và chính sách riêng cho HR vs. lead gen.
- Scraper strategy: Zalo/LinkedIn, Crunchbase, job boards, company websites. Cần legal/ToS review.

### GTM/Business impact
- `product-definition`, `business-plan-baseline`, `gtm-business-plan`, `marketing-plan`, `nowing-3-year-roadmap`, `innovation-strategy`, `domain-expansion-research-report` cần cập nhật.
- Beachhead và messaging cần thống nhất: agent-builder/researcher vs. sales/SDR.

---

## 3. Phương án đề xuất

**Phương án: Direct Adjustment + Governance + Doc Sync**

Không rollback các FR/AD mới. Thay vào đó, bổ sung governance và sync docs theo thứ tự:

1. **Lift positioning freeze 2026-08-24 cho phần Vision/Target User/Beachhead** để chính thức hóa lead intelligence.
2. **Approve NG-1 exception** cho "structured lead-enrichment deliverables" trong vertical B2B sales tại Vietnam, với điều kiện:
   - Không bán raw web index / research corpus.
   - Chỉ bán verified contacts khi có legal basis và consent mechanism.
   - Có separate PII policy cho lead data vs. HR data.
3. **Đặt sales team / SDR làm beachhead #1 cho Epic 21**, nhưng giữ agent-builder/research team làm beachhead #1 cho core product (OSS/PLG). Rõ ràng phân chia: lead gen = cloud vertical; core = research memory + OSS.
4. **Yêu cầu legal/ToS review** cho Zalo OA, LinkedIn automation/scraping, Crunchbase feed, VietnamWorks/TopCV/ITviec reuse cho sales signals.
5. **Tách PII pipeline**:
   - HR/job data: redact trước memory (FR-47/AD-25).
   - Lead-enrichment data: lưu `VerifiedContact` với `consent_status`, `legal_basis`, retention policy, audit log.
6. **Sync docs**: cập nhật hoặc tạo version mới cho product-definition, business-plan, GTM, marketing-plan, roadmap, innovation-strategy, domain-expansion research để phản ánh lead intelligence.
7. **Reconcile Epic 21 architecture**:
   - Validate hoặc loại bỏ assumptions trong `epic21-architecture-update.md`.
   - Thống nhất schema `SignalEvent`, `LeadScore`, `VerifiedContact` giữa draft và Spine.
   - Align FR-67 (bidirectional CRM sync) với AD-40 (phased read-first → write-back → bidirectional).

---

## 4. Đề xuất thay đổi cụ thể

### 4.1. PRD `prd.md`

- Cập nhật `updated:` date trong frontmatter thành `2026-08-10`.
- Thêm reference tới SCP này trong note ở line 17-18.
- Sửa `§2.1 Target User` rõ ràng beachhead #1 cho lead gen.
- Sửa `§2.4 Non-Goals` (NG-1) ghi exception cho structured lead-enrichment deliverables.

### 4.2. `product-definition-nowing-2026-08-06.md`

- Cập nhật tagline thành "lead intelligence + knowledge intelligence platform".
- Thêm persona Sales Manager / SDR.
- Cập nhật data strategy: lead gen sources có thể vượt 30-50 built-in scrapers nếu qua ChainLens/external APIs.

### 4.3. `business-plan-baseline-nowing-2026-08-04.md` & `gtm-business-plan-nowing-2026-08-04.md`

- Thêm revenue stream outcome-based pricing.
- Cập nhật beachhead: sales/SDR (Vietnam B2B SaaS, IT outsourcing, agency, local business).
- Cập nhật hard gates: thêm legal/PII, Zalo OA, LinkedIn ToS gates.

### 4.4. `marketing-plan-nowing-2026-08-07.md`

- Thêm persona Sales Manager / SDR.
- Cập nhật positioning, promise, và channel priority (Zalo, LinkedIn, B2B communities).

### 4.5. `nowing-3-year-roadmap-2026-08-06.md`

- Year 1: thêm Epic 21 lead gen pilot (Vietnam).
- Year 2-3: mở rộng lead gen SEA.

### 4.6. `domain-expansion-research-report-2026-08-06.md`

- Sửa hoặc ghi chú exception cho Zalo/LinkedIn: dùng cho lead gen với legal review, không dùng cho generic scraper expansion.

### 4.7. `epics.md`

- Xóa/archive stories 13.1-13.3 của Epic 13 [DROPPED].
- Cập nhật Epic 12 note: rõ HR data không dùng cho lead enrichment.

### 4.8. `ARCHITECTURE-SPINE.md` & `epic21-architecture-update.md`

- Đóng assumptions hoặc chuyển thành open risks.
- Thống nhất schema `SignalEvent`, `LeadScore`, `VerifiedContact`.
- Đối chiếu FR-67 và AD-40.

### 4.9. Implementation readiness reports

- Cập nhật `implementation-readiness-report-v2` và `final`:
  - Không tuyên bố READY cho đến khi assumptions validated, PII policy approved, legal/ToS review xong.
  - Sửa "Next Step: Add Epic 21 to epics.md" vì Epic 21 đã tồn tại.

---

## 5. Checklist

| Section | Item | Status |
|---|---|---|
| 1.1 | Trigger: positioning freeze + NG-1 conflict + PII conflict | [x] Done |
| 1.2 | Core problem: lead gen direction added without SCP | [x] Done |
| 1.3 | Evidence: gap analysis file | [x] Done |
| 2.1 | Epic 21 impacted | [x] Done |
| 2.2 | Epic 12 PII boundary needs update | [x] Done |
| 2.3 | Strategic/GTM docs impacted | [x] Done |
| 3.1 | Direct Adjustment selected | [x] Viable |
| 3.2 | Rollback not viable (market research + AD/FR already merged) | [x] Done |
| 4.1-4.9 | Proposed doc updates listed | [x] Done |
| 5.1 | Owner approve SCP | [ ] Pending |
| 5.2 | Legal review NG-1 exception + Zalo/LinkedIn ToS | [ ] Pending |
| 5.3 | Apply PRD + product-definition updates | [ ] Pending |
| 5.4 | Sync business/GTM/marketing/roadmap/domain docs | [ ] Pending |
| 5.5 | Reconcile architecture draft + Spine | [ ] Pending |
| 5.6 | Update implementation readiness reports | [ ] Pending |

---

## 6. Implementation handoff

- **Scope:** Governance + documentation sync; không phải code change.
- **Người thực hiện:** Mary (BA) + owner/decision maker + legal counsel.
- **Deliverables:**
  - PRD cập nhật freeze/NG-1/beachhead.
  - Product definition + business plan + GTM + marketing plan + roadmap + domain expansion research được sync.
  - Epic 21 architecture assumptions đóng rõ ràng.
  - PII policy phân biệt HR và lead gen.
  - Implementation readiness reports cập nhật status.

---

*Generated from gap analysis `reviews/ai-gen-lead-gap-analysis-2026-08-10.md`.*
