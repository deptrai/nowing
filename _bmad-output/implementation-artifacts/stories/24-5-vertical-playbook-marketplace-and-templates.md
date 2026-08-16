# Story 24.5: Vertical Playbook Marketplace & Community Workflow Templates

Status: `ready-for-dev`
Epic: `epic-24`

## Story Overview

As a new or non-technical business user,
I want to browse a curated Marketplace of industry-specific Playbook Templates (Real Estate, IT Recruitment, B2B SaaS, E-Commerce),
So that I can launch complex multi-step scraping, scoring, and outreach workflows with zero prompt-engineering friction.

---

## Architectural Invariants
- **INV-24.6 (Template Sandbox & Schema Validation):** Mọi playbook BẮT BUỘC khai báo `inputs_schema` (JSON Schema) và validate tham số đầu vào trước khi dispatch.

---

## Acceptance Criteria

1. **Marketplace UI (`/dashboard/[workspace_id]/playbooks/marketplace`):**
   - Phân loại theo danh mục: `Bất Động Sản`, `Tuyển Dụng`, `B2B Sales`, `E-Commerce & Dropshipping`.
   - Mỗi card hiển thị: Icon, Tiêu đề, Tác giả (Official / Community), Số lượt chạy, Ước tính thời gian & chi phí credits.
2. **Featured Official Playbooks:**
   - **BĐS Pro:** Săn BĐS giá ngộp khu vực ➔ Lọc môi giới chuyên nghiệp ➔ Soạn tin nhắn Zalo gửi báo giá.
   - **IT Headhunter:** Quét Senior Backend Go/Python ➔ Bóc tách tech stack ➔ Gợi ý JD tương thích.
   - **B2B Outreach:** Tìm công ty F&B/Retail mới thành lập ➔ Tra cứu MST và SĐT chủ doanh nghiệp ➔ Gửi kịch bản giới thiệu sản phẩm.
3. **1-Click Schema-Driven Modal:**
   - Bấm `Chạy ngay` ➔ Mở modal tự động sinh input form theo `inputs_schema` (Dropdown Tỉnh/Thành, Slider khoảng giá, Input từ khóa).
   - Bấm `Bắt đầu` ➔ Khởi động pipeline orchestrator.

---

## Technical Tasks
- [ ] Backend: Schema bảng `playbook_templates`, `playbook_categories`, `playbook_installations`.
- [ ] Backend: Seeder dữ liệu cho 12 playbook mẫu chuẩn doanh nghiệp Việt Nam.
- [ ] Frontend: Xây dựng Marketplace Hub và Dynamic Schema Form Modal.
- [ ] Unit Tests: Test validate schema input, test chạy playbook orchestrator.
