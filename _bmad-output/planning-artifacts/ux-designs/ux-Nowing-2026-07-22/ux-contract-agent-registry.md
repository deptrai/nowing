# UX Contract — Agent Registry: Admin CRUD for Vertical Client Agents

**Ngày:** 2026-08-08
**Phạm vi:** UX cho trang `/admin/agent-registry` — quản lý agents (FR-57, Story 13.6, 13.7).
**Bám vào:** FR-57 · NFR-MULTI-1 · AD-13 (amended) · Story 13.6 · Story 13.7
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được, không định layout/màu.

---

## 1. Bài toán UX

Nowing mở rộng thành multi-vertical AI engine. Mỗi vertical client (bdsai.vn, tương lai) cần một agent riêng với:
- **System instructions** riêng (BĐS agent hiểu thuật ngữ BĐS, không phải HR/e-com)
- **Tool allowlist** riêng (BĐS agent được dùng `batdongsan_scrape`, không được dùng `vn_jobs_scrape`)
- **Model/model config** riêng (tùy vertical có thể dùng model khác)

Admin cần UI để:
- Xem tất cả agents đang có (global, không workspace-scoped)
- Tạo agent mới cho vertical client
- Chỉnh sửa system instructions, tools, model
- Bật/tắt agent (soft delete = `is_active=false`)
- Xem agent nào đang được dùng bởi vertical nào

Hệ quả UX:
- Admin phải hiểu rõ **agent → client** mapping để không config nhầm tools cho vertical sai.
- System instructions editor phải hỗ trợ preview — admin thấy ngay prompt sẽ được inject vào chat.
- Tool allowlist phải rõ ràng: tool nào **enabled**, nào **disabled**, nào **not available** (không phải của workspace).

---

## 2. Contract — các trạng thái UI bắt buộc

### 2A. Agent List (default view)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| A1 | **Agent table** — Danh sách agents dạng table, cột: Name, Client ID, Model, Tools count, Status (active/inactive), Last updated | ✅ |
| A2 | **Active/Inactive badge** — Visual indicator: green "Active" / gray "Inactive" | ✅ |
| **A3** | **Seed indicator** — Agent mặc định (`bdsai-listing-assistant`) có nhãn "Seeded" để admin biết không nên xóa | ✅ |
| A4 | **Empty state** — "No agents registered. Create your first agent for a vertical client." + CTA "Create Agent" | ✅ |
| A5 | **Search/filter** — Filter theo client_id, status (all/active/inactive) | ✅ |

### 2B. Create Agent Form

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| B1 | **Agent name** — Text input, required, unique (e.g. `bdsai-listing-assistant`) | ✅ |
| B2 | **Client ID** — Text input, required (e.g. `bdsai.vn`). Placeholder: `client-domain.com` | ✅ |
| B3 | **Display name** — Text input, required (e.g. `BDS Listing Assistant`) | ✅ |
| B4 | **System instructions** — Textarea (min 20 rows), required. Placeholder hiển thị example prompt pattern | ✅ |
| B5 | **System instructions preview** — Toggle "Preview" hiển thị rendered markdown + injected vào default prompt pattern | ✅ |
| B6 | **Model selector** — Dropdown từ Global Model Catalog (AD-8). Mặc định = workspace default | ✅ |
| B7 | **Citations toggle** — Switch bật/tắt `citations_enabled` | ✅ |
| B8 | **Tool allowlist** — Multi-select hoặc toggle list từ available tools của workspace. Section: "Enabled Tools" vs "Disabled Tools" | ✅ |
| B9 | **Tool group by category** — Tools nhóm theo: Scrapers, Search, Research, Memory, Other | ✅ |
| B10 | **Form validation** — Required fields rõ ràng, submit disabled khi invalid, inline error messages | ✅ |
| B11 | **Cancel / Create actions** — Cancel quay về list, Create lưu và navigate đến agent detail | ✅ |

### 2C. Agent Detail & Edit

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| C1 | **Detail header** — Agent name, Client ID badge, Status badge, Edit/Delete actions | ✅ |
| C2 | **System instructions panel** — Read-only view với markdown render + "Edit" button | ✅ |
| C3 | **Model info** — Hiển thị model name, link đến Global Model Config | ✅ |
| C4 | **Tools panel** — Hiển thị enabled tools (green check) vs disabled tools (gray minus) | ✅ |
| C5 | **Citations status** — On/Off indicator | ✅ |
| C6 | **Edit mode** — Click "Edit" → inline edit hoặc slide-over form (same as Create form, pre-filled) | ✅ |
| C7 | **Save/Cancel edit** — Save cập nhật, Cancel discard changes | ✅ |
| C8 | **Delete agent** — Button "Delete" → confirmation dialog với consequences | ✅ |
| C9 | **Delete confirmation** — Dialog: "Delete agent {name}? This will deactivate the agent for {client_id}. Existing chat threads will fall back to default agent." | ✅ |

### 2D. Tool Allowlist Selector (component)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| D1 | **Tool list** — Checkbox list tất cả tools available trong workspace | ✅ |
| D2 | **Tool description** — Mỗi tool có short description (1 dòng) để admin hiểu tool làm gì | ✅ |
| D3 | **Select all / Clear all** — Buttons nhanh để toggle all tools | ✅ |
| D4 | **Selected count** — "N/M tools enabled" indicator | ✅ |
| D5 | **Unavailable tools** — Tools không có trong workspace hiển thị grayed-out với tooltip "Not available in this workspace" | ✅ |

---

## 3. Ràng buộc kỹ thuật UX

- **Route:** `/admin/agent-registry` — platform-level route, yêu cầu `is_superuser` (giống Global Model Config).
- **Global scope:** Agent configs là global (không workspace-scoped). Admin ở bất kỳ workspace nào cũng thấy danh sách agents giống nhau.
- **RLS bypass:** Agent configs table không cần RLS (global read/write cho superuser).
- **Zero sync:** Không cần real-time sync cho agent list (low frequency changes).
- **Reuses:** Pattern từ `ux-contract-admin-global-model-config.md` (admin table, create/edit form, delete confirmation).
- **Accessibility:** Form keyboard navigable, tool list có ARIA labels, color không phải signal duy nhất (icon + text).
- **i18n:** Tool descriptions localize nếu tool name có tiếng Việt.

---

## 4. User Flows

### Flow 1: Admin tạo agent cho BDS AI
1. Admin vào `/admin/agent-registry`
2. Thấy seeded agent `bdsai-listing-assistant` trong list
3. Click "Edit" để chỉnh sửa system instructions
4. Xem tool allowlist: `batdongsan_scrape`, `chotot_bds_scrape`, `muaban_bds_scrape` đã enabled
5. Admin chỉnh sửa system instructions → Preview rendered prompt → Save
6. BDS AI chat agent giờ dùng custom prompt

### Flow 2: Admin tạo agent mới cho vertical HR
1. Admin vào `/admin/agent-registry`
2. Click "Create Agent"
3. Điền: Name=`hr-career-advisor`, Client ID=`hrsystem.vn`, Display Name=`HR Career Advisor`
4. Paste system instructions cho HR domain
5. Chọn tools: enable `vn_jobs_aggregate`, `cafef_scrape`; disable `batdongsan_scrape`
6. Chọn model: `claude-sonnet-4-20250514`
7. Enable citations
8. Click "Create" → navigate đến agent detail

### Flow 3: Admin deactivate agent
1. Admin vào agent detail của `old-client-agent`
2. Click "Delete"
3. Confirmation dialog hiện consequences
4. Admin confirm → agent `is_active=false`
5. Agent quay về list với badge "Inactive"
6. Vertical client gọi API với `agent_id` đó → nhận 404 (fail closed)

---

## 5. Truy vết

- Chặn: Story 13.6 (FR-57), Story 13.7 (FR-57 + prompt injection)
- Phụ thuộc: AD-13 amended (public endpoints), AD-8 (Global Model Catalog), NFR-MULTI-1 (tenant isolation)
- Reuses: `ux-contract-admin-global-model-config.md` (admin UI patterns)
- Related: `ux-contract-canonical-entity.md` (admin review queue pattern)

---

## 6. Open Questions

1. **System instructions versioning** — Có nên lưu history của system instructions để revert? (Gợi ý: Phase 2 — Phase 1 chỉ có current version)
2. **Agent testing** — Có nên có "Test Agent" button để admin test chat với agent config trước khi activate? (Gợi ý: Phase 2)
3. **Tool auto-discovery** — Khi workspace thêm connector mới, có nên auto-enable tool cho agents của workspace đó? (Gợi ý: Không, explicit allowlist only)
4. **Agent ↔ Workspace** — Agent global, nhưng tools available phụ thuộc workspace. Admin ở workspace A edit agent → thấy tools khác workspace B? (Gợi ý: Có — tools list theo workspace context)
