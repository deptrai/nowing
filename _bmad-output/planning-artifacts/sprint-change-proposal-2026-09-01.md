# Sprint Change Proposal — Thu phí Global Models & Tối giản hóa UI Quản lý Model

- **Ngày tạo:** 2026-09-01
- **Người đề xuất:** Luisphan
- **Trạng thái:** Approved
- **Mức độ ảnh hưởng (Scope):** Minor (Front-end & Backend Config Direct Implementation)

---

## 1. Tóm tắt vấn đề (Issue Summary)
- Hai model global (`claude-opus-5`, `claude-sonnet-5`) và model image generation (`GPT Image 2`) hiện tại đang ở trạng thái `billing_tier: "free"`, khiến hệ thống chỉ audit mà không trừ credit người dùng.
- Giao diện người dùng vẫn còn hiển thị nút chọn model hình ảnh (`ImageModelSelector`), nút "Manage models" trong selector và tab "Models" trong Workspace Settings (`/workspace-settings/models`). Các nút này cần được ẩn đi để tối giản hóa trải nghiệm và thống nhất luồng chọn model.

---

## 2. Phân tích tác động (Impact Analysis)
- **Backend Model Policy & Billing:** Kích hoạt `billing_tier: "premium"` / `tier_required: "pro"` để thực hiện trừ credit thông qua `TokenQuotaService` (`credit_reserve` & `credit_finalize`).
- **Frontend UI/UX:**
  - `ChatHeader`: Loại bỏ icon/dropdown chọn model ảnh.
  - `ModelSelector`: Loại bỏ nút "Manage models" ở footer popover/drawer.
  - `WorkspaceSettingsLayoutShell`: Loại bỏ tab "Models" khỏi danh mục menu cài đặt workspace.

---

## 3. Chi tiết các thay đổi (Detailed Proposals)

### 3.1. Backend Configuration (`nowing_backend/.env` & `global_llm_config.yaml`)
- Chuyển `tier_required: pro` / `billing_tier: premium` cho:
  - `id: -1` (`claude-opus-5`)
  - `id: -2` (`claude-sonnet-5`)
  - `id: -101` (`GPT Image 2`)
  - `id: -2001`, `id: -2002` (`Gemini Flash Image`)

### 3.2. Frontend UI
- `nowing_web/components/new-chat/chat-header.tsx`: Bỏ `ImageModelSelector`.
- `nowing_web/components/new-chat/model-selector.tsx`: Bỏ nút `Manage models`.
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx`: Bỏ tab `models`.

---

## 4. Kế hoạch bàn giao & Kiểm thử (Implementation & Verification)
1. Cập nhật file `.env` và `global_llm_config.yaml`.
2. Chỉnh sửa code React components.
3. Khởi động lại backend và xác nhận qua endpoint `/api/v1/global-model-connections`.
