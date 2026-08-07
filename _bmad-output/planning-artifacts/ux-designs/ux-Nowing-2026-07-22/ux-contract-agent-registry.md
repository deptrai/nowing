# UX Contract — Agent Registry: Admin CRUD for Vertical Client Agents

**Ngày:** 2026-08-08 (amended 2026-08-07 correct-course)
**Phạm vi:** UX cho trang `/admin/agent-registry` — quản lý agents (FR-57, Epic 18 Stories 18.3–18.4).
**Bám vào:** FR-57 · NFR-MULTI-1 · **AD-30** (AgentConfig registry) · **AD-29** (public surface) · **AD-31** (client tenancy) · AD-13 (ResearchThread linkage only)
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được, không định layout/màu.

---

## 1. Bài toán UX

Nowing mở rộng thành multi-vertical AI engine. Mỗi vertical client (bdsai.vn, tương lai) cần một agent riêng với:
- **System instructions** riêng (BĐS agent hiểu thuật ngữ BĐS, không phải HR/e-com)
- **Tool allowlist** riêng (BĐS agent được dùng `batdongsan_scrape`, không được dùng `vn_jobs_scrape`)
- **Model/model config** riêng (tùy vertical có thể dùng model khác)

Admin cần UI để:
- Xem tất cả agents đang có (platform registry — not end-user workspace CRUD)
- Tạo agent mới cho vertical client
- Chỉnh sửa system instructions, tools, model
- Bật/tắt agent (soft delete = `is_active=false`)
- Xem agent nào đang được dùng bởi vertical nào

Hệ quả UX:
- Admin phải hiểu rõ **agent → client** mapping để không config nhầm tools cho vertical sai.
- System instructions editor phải hỗ trợ preview — admin thấy ngay prompt sẽ được inject vào chat.
- Tool allowlist phải rõ ràng: tool nào **enabled**, nào **disabled**, nào **not available**.

---

## 2. Contract — các trạng thái UI bắt buộc

### 2A. Agent List (default view)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| A1 | **Agent table** — Danh sách agents dạng table, cột: Name, Client ID, Model, Tools count, Status (active/inactive), Last updated | ✅ |
| A2 | **Active/Inactive badge** — Visual indicator: green "Active" / gray "Inactive" | ✅ |
| A3 | **Seed indicator** — Agent mặc định (`bdsai-listing-assistant`) có nhãn "Seeded" để admin biết không nên xóa | ✅ |
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
| B8 | **Tool allowlist** — Multi-select hoặc toggle list. Section: "Enabled Tools" vs "Disabled Tools" | ✅ |
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
| D1 | **Tool list** — Checkbox list tools available for configuration | ✅ |
| D2 | **Tool description** — Mỗi tool có short description (1 dòng) | ✅ |
| D3 | **Select all / Clear all** — Buttons nhanh để toggle all tools | ✅ |
| D4 | **Selected count** — "N/M tools enabled" indicator | ✅ |
| D5 | **Unavailable tools** — Tools không available hiển thị grayed-out với tooltip | ✅ |

---

## 3. Ràng buộc kỹ thuật UX

- **Route:** `/admin/agent-registry` — platform-level route, yêu cầu `is_superuser` (giống Global Model Config) unless AD-30 chooses a narrower admin role.
- **Registry scope:** Superuser-managed platform registry (AD-30). Not end-user workspace settings.
- **Tenancy:** Agent rows carry `client_id` (AD-31). Runtime authorization still composes workspace + client scopes (AD-29).
- **Zero sync:** Không cần real-time sync cho agent list (low frequency changes).
- **Reuses:** Pattern từ `ux-contract-admin-global-model-config.md`.
- **Accessibility:** Form keyboard navigable, tool list có ARIA labels, color không phải signal duy nhất.
- **i18n:** Tool descriptions localize nếu cần.

---

## 4. User Flows

### Flow 1: Admin tạo agent cho BDS AI
1. Admin vào `/admin/agent-registry`
2. Thấy seeded agent `bdsai-listing-assistant` trong list
3. Click "Edit" để chỉnh sửa system instructions
4. Xem tool allowlist BĐS scrapers đã enabled
5. Admin chỉnh sửa system instructions → Preview → Save
6. BDS AI chat agent dùng custom prompt qua public API (Epic 18)

### Flow 2: Admin tạo agent mới cho vertical HR
1. Admin vào `/admin/agent-registry`
2. Click "Create Agent"
3. Điền name/client/display name + system instructions
4. Chọn tools + model + citations
5. Create → agent detail

### Flow 3: Admin deactivate agent
1. Admin vào agent detail
2. Delete → confirm consequences
3. `is_active=false`; public API with that `agent_id` → 404 fail closed

---

## 5. Truy vết

- Chặn: Story **18.3** (FR-57), Story **18.4** (prompt injection)
- Phụ thuộc: **AD-30**, **AD-29**, **AD-31**, AD-8 (Global Model Catalog), NFR-MULTI-1
- Reuses: `ux-contract-admin-global-model-config.md`
- Related: `ux-contract-canonical-entity.md` (admin patterns only — different epic)

---

## 6. Open Questions

1. **System instructions versioning** — Phase 2; MVP = current version only.
2. **Agent testing** — "Test Agent" button = Phase 2.
3. **Tool auto-discovery** — No; explicit allowlist only (AD-30).
4. **Agent ↔ Workspace tools** — Tool catalog for the admin UI must not silently imply every workspace has every tool. Prefer platform catalog + runtime enforcement of workspace-enabled tools.
