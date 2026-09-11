# Prompt: E2E Verify Playbook Instantiate with Free Global Model

## Mission
Dùng Playwright MCP hoặc Chrome DevTools MCP để chạy E2E trên live browser, verify rằng user có thể instantiate một playbook với **free global model** được chọn thủ công, backend chấp nhận snapshot đó, và automation được tạo thành công.

## Context cần biết trước
- Feature vừa implement: `allow_global_model_selection` cho playbook instantiation.
- Mục tiêu: kiểm tra full flow — frontend dialog → API → backend policy → runtime backstop.
- Các ID convention: `id == 0` = Auto mode (blocked), `id < 0` = global model, `id > 0` = BYOK.

## Preconditions
1. App đang chạy tại `{{base_url}}` (mặc định `http://localhost:3000`).
2. User đã login và có quyền vào workspace `{{workspace_id}}`.
3. Workspace đã có ít nhất một playbook có thể instantiate (có thể tạo mới từ automation nếu chưa có).
4. Hệ thống đang có ít nhất một **free global model** với `supports_chat: true` trong `GLOBAL_MODELS` config (id < 0, billing_tier = "free").

## Test Data cần chuẩn bị
- `{{workspace_id}}`: ID của workspace test.
- `{{playbook_id}}` (optional): ID playbook sẵn có. Nếu không có, tạo mới từ automation sample.
- `{{free_global_chat_model_id}}`: ID âm của free global model hợp lệ cho chat, ví dụ `-10`.
- `{{byok_image_model_id}}` / `{{byok_vision_model_id}}`: ID dương nếu muốn test mixed models (free global chat + BYOK image/vision).

## Capability sử dụng
- `pilot` — navigate, click, fill, select.
- `observe` — snapshot, screenshot, console logs, network requests.
- `inspect` — xác định semantic selectors.

## Test Steps

### Step 0: Pre-flight
1. Navigate đến `{{base_url}}/dashboard/{{workspace_id}}/playbooks`.
2. Chụp full-page screenshot.
3. Lấy accessibility snapshot để xác định danh sách playbook cards / buttons.
4. Kiểm tra console — không có lỗi 500, hydration, hoặc runtime error.

### Step 1: Mở PlaybookInstantiateDialog
1. Tìm playbook card có tên hoặc button "Chạy" / "Khởi tạo".
2. Click vào nút instantiate (thường là `button` bên trong playbook card hoặc trong action menu).
3. Verify dialog mở: tìm heading chứa tên playbook hoặc text "Khởi tạo" / "Chạy Kịch Bản".
4. Chụp screenshot của dialog.

### Step 2: Kiểm tra AutomationModelFields (playbook mode)
1. Trong dialog, xác định component `AutomationModelFields` với `mode="playbook"`.
2. Kiểm tra select/chat model:
   - Có group "Global" hoặc "Free".
   - Có option với badge "Free" (free global model).
   - Không bị disabled.
3. Screenshot trước khi chọn.

### Step 3: Chọn free global model
1. Mở chat model select.
2. Chọn free global model có `id = {{free_global_chat_model_id}}`.
3. Nếu image/vision cũng là global free, chọn tương ứng. Nếu không, để default BYOK/premium.
4. Verify UI phản ánh selection đúng: select hiển thị tên model đã chọn, badge "Free" xuất hiện.
5. Screenshot sau khi chọn.

### Step 4: Submit instantiate
1. Nếu playbook có inputs schema, điền giá trị hợp lệ (ví dụ `{"query": "test global model"}`).
2. Click nút "Khởi Tạo & Kích Hoạt Playbook" hoặc "Chạy Kịch Bản Ngay".
3. Wait for navigation hoặc API response.

### Step 5: Verify Network
1. Kiểm tra request `POST /api/v1/playbooks/{{playbook_id}}/instantiate`:
   - Status `201 Created`.
   - Request body chứa:
     ```json
     {
       "workspace_id": {{workspace_id}},
       "inputs": { ... },
       "models": {
         "chat_model_id": {{free_global_chat_model_id}},
         "image_gen_model_id": ...,
         "vision_model_id": ...
       }
     }
     ```
   - Response body chứa `definition.models.chat_model_id == {{free_global_chat_model_id}}`.
2. Không được thấy request nào về `/api/v1/playbooks/.../instantiate` trả `422` với lỗi model policy.
3. Không được thấy slot nào bị gửi là `0` (Auto mode) trong `models`.

### Step 6: Verify Redirect
1. Kiểm tra URL redirect đến `/dashboard/{{workspace_id}}/automations/{automation_id}`.
2. Page hiển thị automation detail mới tạo.
3. Kiểm tra model snapshot trong UI (nếu có) — chat model là free global model đã chọn.

### Step 7: Console & error check
1. Kiểm tra `browser_console_messages`:
   - Không có `error` hoặc `unhandledrejection`.
   - Không có lỗi liên quan React / hydration / `modelSelection`.

### Step 8: (Optional) Runtime backstop
1. Nếu có thể trigger run automation ngay (hoặc chờ schedule), verify step `agent_task` load thành công mà không bị `DependencyError` do model policy.
2. Kiểm tra logs backend — không có error `AutomationModelPolicyError` ở `build_dependencies`.

## Expected Results Summary
- [ ] Dialog mở đúng.
- [ ] Free global model xuất hiện trong select playbook mode.
- [ ] Submit trả về `201` với `chat_model_id` là free global id âm.
- [ ] Không có slot nào bị gửi `0`.
- [ ] Redirect đến automation detail thành công.
- [ ] Console sạch.

## Failure Modes cần ghi lại
- Nếu thấy `422` sau submit: chụp response payload, ghi rõ message model policy.
- Nếu select không có free global model: chụp dropdown, ghi danh sách options.
- Nếu `useEffect` ghi đè selection khi submit: ghi lại state trước/sau click submit.
- Nếu console có `unhandledrejection`: copy stack trace.

## Output
Trả về report bao gồm:
1. Tóm tắt pass/fail.
2. Các screenshot/snapshot chụp được.
3. Network request/response liên quan (đặc biệt `POST /instantiate`).
4. Console log nếu có lỗi.
5. Gợi ý fix nếu phát hiện bug.
