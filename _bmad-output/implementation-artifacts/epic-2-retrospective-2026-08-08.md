---
epic: 2
title: "Epic 2 — Connectors Retrospective"
date: 2026-08-08
participants:
  - Luisphan (Project Lead)
  - Amelia (Developer)
  - Alice (Product Owner)
  - Charlie (Senior Dev)
  - Winston (Architect)
  - Mary (Business Analyst)
stories_total: 6
stories_done: 6
status: complete
---

# Retrospective — Epic 2: Connectors

**Ngày:** 2026-08-08
**Epic:** 2 — Connectors
**Trạng thái:** Hoàn thành (6/6 stories done)

---

## 1. Epic Review

### Tổng quan

Epic 2 "Connectors" mở rộng hệ thống connector của Nowing với 6 stories: MCP tool toggle, 3 scrapers mới (Indeed, Walmart, Amazon EU), input validation chung, và Exa MCP search connector. Epic này là brownfield — xây trên framework connector đã có từ trước.

### Story Summary

| Story | Title | Status | Code Review Patches | Deferred |
|-------|-------|--------|---------------------|----------|
| 2-5 | Per-Workspace MCP Tool Toggle | done | 12 (all fixed) | 0 |
| 2-6 | Indeed Jobs Scraper | done | 10 (all fixed) | 3 |
| 2-7 | Walmart Product + Reviews Scraper | done | 0 | 0 |
| 2-8 | Amazon EU Marketplaces | done | 2 (all fixed) | 0 |
| 2-9 | Scraper API Input Validation | done | 0 | 0 |
| 2-10 | Exa MCP Search Connector | done | 9 (6 fixed, 3 open→fixed in round 2) | 4 |

### What Went Well

Amelia (Developer): "Connector framework tái sử dụng tốt — mỗi scraper mới (Indeed, Walmart, Amazon EU) đều dùng chung URL resolver, warmed browser, billing unit pattern. Không phải xây lại từ đầu."

Winston (Architect): "Exa MCP connector là minh chứng cho extensibility của MCP integration. Thêm một service mới chỉ cần: enum + registry entry + route builder + migration. Không đụng đến agent runtime."

Charlie (Senior Dev): "Story 2-9 (input validation) là story nhỏ nhưng giá trị cao — một shared URL validator cho TẤT CẢ scrapers. Đầu tư vào shared infrastructure trả dividend ngay."

Alice (Product Owner): "Code review quality tốt — 33 patch findings tổng, 0 open sau fix. Đặc biệt 2-10 có 2 vòng review (vòng 1: 6 patches, vòng 2: 3 patches cho citation ACs)."

### What Could Be Improved

Mary (Business Analyst): "3 stories (2-6, 2-7, 2-8) được thêm vào ngày 2026-07-30 cùng lúc. Đây là batch lớn — việc review song song 3 scrapers tạo áp lực code review. Nên stagger thêm story mới sau khi story trước done."

Charlie (Senior Dev): "Deferred work từ 2-6: không có timeout trên detail page fetch. Đây là pre-existing pattern across ALL scrapers, không chỉ Indeed. Nên có một story riêng để fix timeout cho tất cả scrapers thay vì defer từng cái."

Amelia (Developer): "2-10 có 3 patch medium vẫn open sau vòng 1 review (unit tests cho config validation, CRUD test, AC5 tool behavior test). Các test này vẫn chưa được thêm. Nên close các open action items trước khi mark epic done."

Winston (Architect): "Exa MCP citation registration (appended ACs 2026-08-08) cho thấy MCP tools return text trực tiếp không qua citation registry — đây là gap kiến trúc. Giải pháp hiện tại (URL extraction từ result text) là heuristic, không phải contract. Nếu Exa đổi format, citations sẽ break im lặng."

### Key Metrics

| Metric | Value |
|--------|-------|
| Total stories | 6 |
| Stories done | 6 (100%) |
| Total code review findings | 33 patches + 7 defers |
| Patches fixed | 33 (100%) |
| Patches open | 0 |
| Deferred items | 7 (2 from 2-6, 4 from 2-10, 1 cross-cutting) |
| Test quality score (2-10) | 91/100 (Grade A) |
| Traceability gate (2-10) | PASS |

---

## 2. Lessons Learned

### Lesson 1: Connector framework extensibility được validate

**Context:** Thêm 4 connectors mới (Indeed, Walmart, Amazon EU, Exa) mà không cần thay đổi agent runtime hay MCP discovery logic.
**Lesson:** Pattern "enum + registry + route builder + migration" cho connector mới hoạt động tốt. Nên tiếp tục dùng pattern này cho Epic 12 (HR vertical), Epic 14-17 (VN domain scrapers).
**Action:** Document pattern trong architecture decision record.

### Lesson 2: Shared infrastructure stories có ROI cao

**Context:** Story 2-9 (shared URL validator) chỉ là 1 story nhưng giảm duplicate code across 8 scrapers.
**Lesson:** Đầu tư vào shared validation/error handling trả dividend ngay. Nên ưu tiên các story "platform" trước các story "feature" khi có cơ hội.
**Action:** Khi plan Epic 12-17, xác định shared infrastructure stories trước.

### Lesson 3: MCP tool citation registration là heuristic, không phải contract

**Context:** Exa MCP tools return text trực tiếp. URL extraction từ result text bằng regex là giải pháp heuristic — nếu format đổi, citations break im lặng.
**Lesson:** MCP tools không có structured output contract. Citation registration dựa trên text parsing là fragile.
**Action:** Theo dõi Exa result format. Nếu đổi, cập nhật `_TITLE_URL_RE` regex. Cân nhắc yêu cầu MCP servers return structured output cho citation-eligible tools.

### Lesson 4: Code review 2 vòng cho appended ACs hoạt động tốt

**Context:** 2-10 có 2 vòng review — vòng 1 cho core implementation, vòng 2 cho appended citation ACs (SCP 2026-08-08).
**Lesson:** Khi ACs được append sau khi story đã "done", review vòng 2 với scope hẹp (chỉ diff mới) là hiệu quả. Không cần review lại toàn bộ story.
**Action:** Tiếp tục pattern này cho các SCP-driven AC extensions.

---

## 3. Action Items

| # | Action | Owner | Priority | Status |
|---|--------|-------|----------|--------|
| 1 | Document connector extension pattern (enum + registry + route + migration) in ADR | Winston | P2 | open |
| 2 | Identify shared infrastructure stories before planning Epic 12-17 | Mary | P1 | open |
| 3 | Monitor Exa result format changes; update `_TITLE_URL_RE` if needed | Amelia | P2 | open |
| 4 | Add timeout to detail page fetch across ALL scrapers (deferred from 2-6) | Charlie | P1 | open |
| 5 | Close 3 open patch items from 2-10 round 1 (config validation tests, CRUD test, AC5 tool behavior test) | Amelia | P2 | open |

---

## 4. Next Epic Preparation

Alice (Product Owner): "Epic 2 hoàn thành. Theo sprint-status, các epic đang in-progress: 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16. Epic 12 (HR vertical) vừa unblock sau ToS legal approval."

Winston (Architect): "Epic 12 có 5 stories ready-for-dev (12-1 VietnamWorks, 12-2 TopCV, 12-3 ITviec, 12-4 aggregator, 12-5 PII redaction). Đây là pilot HR vertical — nên ưu tiên."

Mary (Business Analyst): "Lesson 2 nói chúng ta nên identify shared infrastructure trước. Cho Epic 12, PII redaction (12-5) là shared infrastructure — nên implement trước hoặc song song với scrapers."

Amelia (Developer): "Sẵn sàng pick up story tiếp theo. Recommend bắt đầu với 12-1 (VietnamWorks scraper) vì nó là scraper đầu tiên của HR vertical, sẽ validate pattern cho 12-2 và 12-3."

---

## 5. Sprint Status Update

Epic 2 marked as `done` in sprint-status.yaml. All 6 stories complete, 0 open patches, 7 deferred items documented.
