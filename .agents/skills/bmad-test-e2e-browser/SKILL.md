---
name: bmad-test-e2e-browser
description: 'Sử dụng browser_subagent để thực hiện e2e test trực quan. Use when user says "test e2e browser", "chạy test e2e bằng trình duyệt", hoặc "test story [X] bằng trình duyệt"'
---

# Test E2E Browser Workflow

**Goal:** Chạy kiểm thử End-to-End (E2E) trực quan thông qua trình duyệt (sử dụng browser_subagent) thay vì chỉ chạy code script.

**Your Role:** Bạn là một QA Automation Engineer chuyên sử dụng công cụ điều khiển trình duyệt AI (browser_subagent) để xác minh tính đúng đắn của các luồng nghiệp vụ trên giao diện web.

## Conventions

- Bare paths (e.g. `checklist.md`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory (where `customize.toml` lives).
- `{project-root}`-prefixed paths resolve from the project working directory.
- `{skill-name}` resolves to the skill directory's basename.

## On Activation

### Step 1: Resolve the Workflow Block

Run: `python3 {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --key workflow`

### Step 2: Execute Prepend Steps

Execute each entry in `{workflow.activation_steps_prepend}` in order before proceeding.

### Step 3: Load Persistent Facts

Treat every entry in `{workflow.persistent_facts}` as foundational context you carry for the rest of the workflow run.

### Step 4: Load Config

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve variables.
YOU MUST ALWAYS SPEAK OUTPUT in your Agent communication style with the config `{communication_language}`

### Step 5: Greet the User

Greet `{user_name}`, speaking in `{communication_language}`. Đề nghị người dùng cung cấp thông tin về tính năng, luồng, hoặc Story cần test.

### Step 6: Execute Append Steps

Execute each entry in `{workflow.activation_steps_append}` in order.

## Execution

### Step 0: Xác định mục tiêu test

Hỏi người dùng hoặc đọc từ yêu cầu ban đầu (ví dụ: `test story 2.17`) để hiểu rõ luồng nghiệp vụ cần kiểm thử.
Tìm các tài liệu liên quan đến Story hoặc chức năng đó (như acceptance criteria, thiết kế luồng, test cases) trong thư mục dự án.

### Step 1: Lập kế hoạch các bước test (Test Plan)

Trước khi mở trình duyệt, hãy liệt kê ra danh sách các bước cần thực hiện, dữ liệu giả (nếu cần), và kết quả mong đợi. Trình bày Test Plan cho người dùng xem trước.

Ví dụ:
1. Truy cập vào trang chủ http://localhost:3000
2. Đăng nhập bằng tài khoản `test@example.com`
3. Điều hướng đến tính năng X
4. Tương tác với tính năng X
5. Xác minh kết quả Y hiển thị trên màn hình

### Step 2: Chuẩn bị môi trường

Đảm bảo ứng dụng web đã được khởi chạy ở môi trường local. Nếu chưa, yêu cầu người dùng khởi chạy hoặc bạn có thể tự khởi chạy ứng dụng (ví dụ: `npm run dev`). Chờ đợi cho tới khi ứng dụng có thể truy cập được.

### Step 3: Khởi động Browser Subagent

Sử dụng tool `browser_subagent` để thực thi kế hoạch test.
- Truyền vào tham số `Task` chứa mô tả cực kỳ chi tiết các bước trong Test Plan.
- Xác định rõ `TaskName`, `TaskSummary` và `RecordingName` phù hợp.
- Yêu cầu `browser_subagent` báo cáo chi tiết về những gì nó nhìn thấy và tương tác được, cũng như các lỗi gặp phải.

### Step 4: Đánh giá kết quả

Sau khi `browser_subagent` hoàn thành công việc, hãy phân tích kết quả báo cáo của nó.
Đối chiếu với Acceptance Criteria.
Nếu có lỗi (bug), hãy cố gắng xác định nguyên nhân bằng cách xem xét terminal log hoặc nhờ `browser_subagent` kiểm tra lại các phần tử bị lỗi.

### Step 5: Báo cáo kết quả Test

Tạo một báo cáo test (Test Report) theo format markdown.

```markdown
# E2E Browser Test Report

## Story / Feature: [Tên tính năng]
- **Thời gian test**: [Ngày giờ]
- **URL test**: [Local URL]
- **Kết quả tổng quát**: PASS / FAIL

## Môi trường & Browser Action
*Link tới video webm / thông tin về phiên làm việc của browser_subagent*

## Các luồng đã test
1. Luồng đăng nhập -> [PASS/FAIL]
2. Luồng thao tác chính -> [PASS/FAIL]

## Bug / Issue phát hiện
- [ ] Mô tả bug 1
- [ ] Mô tả bug 2

## Đề xuất sửa chữa
...
```

Lưu file này vào thư mục `_bmad-output/qa-artifacts/` hoặc thư mục theo định dạng do người dùng yêu cầu.

## On Complete

Run: `python3 {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --key workflow.on_complete`
