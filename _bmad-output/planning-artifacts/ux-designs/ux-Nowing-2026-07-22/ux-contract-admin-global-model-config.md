# UX Contract — Admin Global LLM Model Configuration

**Ngày:** 2026-08-05
**Phạm vi:** UX cho trang `/admin/global-model-connections` — quản lý global model config (FR-41).
**Bám vào:** FR-41 · AD-8 · AD-9 · Story 8.11
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được, không định layout/màu.

---

## 1. Bài toán UX

Platform admin hiện phải sửa YAML/`.env` + restart backend để thêm/sửa global model. Story 8.11 mang chức năng này lên UI với hot-reload.

Hệ quả UX:
- UI phải phân biệt rõ model từ **file-backed** (operator-owned) và **DB-backed** (UI-managed) để admin không xoá/sửa nhầm nguồn config.
- Admin cần test connection trước khi lưu — một lần gọi model thật, không lưu nếu fail.
- Cost fields phải hiển thị đúng đơn vị ($ / 1K tokens) và map vào `pricing_registration`.

## 2. Contract — các trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| A1 | **Danh sách hợp nhất** — cả file-backed và DB-backed model trong cùng bảng, có nhãn "From config file" / "Managed" | ✅ |
| A2 | **Ẩn API key thật** — chỉ hiển thị `has_api_key: boolean` và cho phép "Update key" mà không reveal | ✅ |
| A3 | **Tạo model mới** — form gồm provider, model_name, api_key, api_base, input/output cost per 1K tokens, rpm/tpm | ✅ |
| A4 | **Test connection** — button gọi model thật một lần, hiển thị success/fail trước khi lưu | ✅ |
| A5 | **Edit / delete DB-backed model** — thay đổi có hiệu lực ngay cho chat call tiếp theo | ✅ |
| A6 | **File-backed model read-only** — chỉ xem và toggle enable/disable tạm thời; không sửa field khác, không xoá | ✅ |
| A7 | **Auto mode pool preview** — sau CRUD, danh sách Auto mode pool cập nhật tức thì | ✅ |

## 3. Ràng buộc kỹ thuật UX

- Backend gating bằng `require_superuser()` — UI cũng kiểm `user.is_superuser` client-side (defense-in-depth, không thay backend check).
- Trang đặt ở route cấp platform, không nằm trong `/dashboard/[workspace_id]/...`.
- Tái dùng component `model-connections` ở `nowing_web/components/settings/model-connections/` nhưng đặt ở route admin.

## 4. Truy vết

- Chặn: story 8.11 (FR-41)
- Phụ thuộc: AD-8 (cost registration), AD-9 (RBAC không đổi 3 role workspace)
