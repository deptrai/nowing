---
story_key: "24-5"
epic: "epic-24"
story: "24.5"
title: "Vertical Playbook Marketplace & Community Workflow Templates"
status: "ready-for-dev"
baseline_commit: "6ac305274"
---

# Story 24.5: Vertical Playbook Marketplace & Community Workflow Templates

## Story Overview

As a new or non-technical business user,
I want to browse a curated Marketplace of industry-specific Playbook Templates (Real Estate, IT Recruitment, B2B SaaS, E-Commerce),
So that I can launch complex multi-step scraping, scoring, and outreach workflows with zero prompt-engineering friction.

---

## Architectural Invariants (INV-24.6)
- **INV-24.6 (Template Sandbox & AST Security):** Vertical Playbooks BẮT BUỘC khai báo `inputs_schema` (JSON Schema) với giới hạn cứng `max_leads_per_run <= 200` để tránh cạn kiệt tài nguyên. Community Playbooks phải qua kiểm duyệt (`is_approved = True`) trước khi hiển thị trên marketplace.

---

## Acceptance Criteria

1. **Categorized Marketplace Gallery:**
   - **Given** `/dashboard/[workspace_id]/playbooks/marketplace`,
   - **When** viewed,
   - **Then** it renders responsive cards grouped by vertical: `Bất Động Sản`, `Tuyển Dụng Nhân Sự`, `B2B Sales`, `E-Commerce & Bán Lẻ`, showing verified author badges, run counts, and estimated credit costs.

2. **Official High-Value Playbooks:**
   - **Given** the initial launch,
   - **When** browsing official playbooks,
   - **Then** at least 4 battle-tested templates are available:
     1. *BĐS Ngộp & Môi Giới Pro:* Săn BĐS chính chủ/ngộp giá ➔ Lọc SĐT ➔ Soạn tin nhắn Zalo gửi báo giá.
     2. *IT Headhunter Săn Senior:* Quét TopCV/ITviec ➔ Bóc tách Tech Stack ➔ So khớp JD ứng viên.
     3. *B2B Sales Doanh Nghiệp Mới:* Quét doanh nghiệp mới thành lập ➔ Tra cứu MST & SĐT ➔ Gửi kịch bản giới thiệu.
     4. *E-Commerce Flash Price Tracking:* Theo dõi biến động giá Shopee/Lazada ➔ Bắn cảnh báo Telegram.

3. **Dynamic Schema-Driven Input Form & Cost Preview:**
   - **Given** a selected playbook,
   - **When** clicking `Chạy Playbook`,
   - **Then** the UI renders a dynamic form derived from `inputs_schema` with parameter bounds (Tỉnh/Thành bắt buộc, Slider khoảng giá, Giới hạn số lượng), showing an upfront Credit Estimation Preview before triggering the orchestrator.

---

## Technical Tasks

### Backend Implementation
- [ ] Schema: Tạo bảng `playbook_templates`, `playbook_categories`, `playbook_runs` với Composite PK `(id, workspace_id)`.
- [ ] Seed Data: Nạp 12 template chính thức chuẩn hóa cho thị trường Việt Nam.
- [ ] Service: Xây dựng `PlaybookExecutionEngine` validate schema và điều phối qua `LeadGenOrchestrator`.

### Frontend Implementation
- [ ] UI: Xây dựng Marketplace Hub (`nowing_web/app/dashboard/[workspace_id]/playbooks/marketplace/page.tsx`).
- [ ] Dynamic Form: Xây dựng `SchemaDrivenPlaybookModal.tsx` tự động render input theo JSON Schema.

---

## Verification Commands

```bash
# Backend tests
cd nowing_backend
uv run ruff check app/services/playbook_template_service.py tests/unit/services/test_playbook_templates.py
uv run pytest tests/unit/services/test_playbook_templates.py -q

# Frontend check
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/dashboard/\[workspace_id\]/playbooks/marketplace/
```
