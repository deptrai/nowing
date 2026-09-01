# Sprint Change Proposal — Tích hợp Clarification / Multi-Option Question UI vào hệ thống HITL

- **Ngày tạo:** 2026-09-02
- **Người đề xuất:** Luisphan
- **Trạng thái:** Proposed
- **Mức độ ảnh hưởng (Scope):** Minor / Feature Enhancement (Frontend UI Component & Backend HITL Tool Schema)

---

## 1. Tóm tắt vấn đề & Động lực thay đổi (Issue Summary)

- **Hiện trạng:**
  - Hệ thống hiện có hạ tầng Human-In-The-Loop (HITL) hoàn chỉnh qua `features/chat-messages/hitl/` và `PendingInterruptProvider`.
  - Tuy nhiên, giao diện hiện tại chủ yếu phục vụ **Tool Action Approval / Parameter Editing** (Approve / Reject / Edit params).
  - Khi Agent đang suy luận hoặc lập kế hoạch cần **làm rõ ý định (Clarification)** hoặc **yêu cầu người dùng chọn 1 trong nhiều phương án (Single/Multi Select)**, Agent chưa có một Tool UI trực quan (trắc nghiệm / danh sách lựa chọn bấm 1-click) mà phải in ra văn bản thường và chờ người dùng gõ lại, làm đứt gãy trải nghiệm tương tác liền mạch.

- **Mục tiêu:**
  - Nâng cấp cơ chế HITL để hỗ trợ loại tương tác **"Interactive Question / Option Selector Card"** (tương tự như `AskUserQuestion` của Claude Code).
  - Cho phép người dùng bấm chọn nhanh phương án hoặc nhập thêm ghi chú / prompt bổ sung trực tiếp trên thẻ tương tác của luồng chat.

---

## 2. Phân tích tác động (Impact Analysis)

### 2.1. Kiến trúc Backend (`nowing_backend`)
- **Tác động:** Không phá vỡ kiến trúc hiện tại, tái sử dụng 100% cơ chế `LangGraph State Interrupt` và stream event protocol:
  - Bổ sung định nghĩa tool `ask_user_question` (hoặc `prompt_clarification_tool`) với schema:
    ```python
    class UserQuestionOption(BaseModel):
        label: str
        description: str | None = None
        preview: str | None = None

    class UserQuestionPayload(BaseModel):
        question: str
        header: str | None = None
        multi_select: bool = False
        options: list[UserQuestionOption]
        allow_custom_input: bool = True
    ```
  - Khi Agent gọi tool này, engine phát ra `InterruptResult` có `interrupt_type: "question"` và danh sách `options`.
  - Khi nhận `hitl-decision`, engine unblock và truyền câu trả lời đã chọn vào context của Agent để tiếp tục sinh câu trả lời.

### 2.2. Giao diện Người dùng (`nowing_web`)
- **Tác động:** Thêm component hiển thị thẻ câu hỏi tương tác trong module HITL:
  - **Tạo mới:** `features/chat-messages/hitl/approval-cards/question-choice-approval.tsx`.
  - Đăng ký component mới trong `features/chat-messages/hitl/approval-cards/index.ts` và tích hợp vào `FallbackToolBody` / `HitlApprovalCard`.
  - **UI / UX:**
    - Render câu hỏi + Header chip badge.
    - Danh sách Options dạng radio card hoặc checkbox card (khi `multi_select: true`).
    - Khung nhập "Khác / Tùy chỉnh" (Custom input text) khi cần nhập prompt bổ sung.
    - Nút "Xác nhận lựa chọn" (Submit Choice) kích hoạt `onDecision({ type: 'approve', message: selectedAnswer })`.

---

## 3. Kế hoạch triển khai chi tiết (Detailed Implementation Proposals)

### 3.1. Frontend Component: `QuestionChoiceApprovalCard`
1. Thiết kế card bo góc `rounded-2xl border bg-card/80 p-4 shadow-sm`.
2. Hiển thị badge Icon dấu hỏi / Brainstorming 💡.
3. Hỗ trợ phím tắt: Bấm số `1`, `2`, `3` hoặc phím mũi tên để chọn nhanh và `Enter` để gửi.
4. Trạng thái sau khi submit: Chuyển sang hiển thị badge phương án đã chọn gọn gàng (`Đã chọn: Option A`).

### 3.2. Đăng ký Tool Schema & Tích hợp
1. Bổ sung `isQuestionInterrupt` helper trong `features/chat-messages/hitl/types.ts`.
2. Tích hợp render tự động khi tool name là `ask_user_question` hoặc `interrupt_type === "question"`.

---

## 4. Kế hoạch bàn giao & Kiểm thử (Verification Plan)
1. **Kiểm thử Unit & Storybook / Local Preview:** Tạo fixture `mockQuestionInterrupt` kiểm tra việc render options và chọn lựa chọn.
2. **Kiểm thử E2E trên Playwright:** Mô phỏng luồng Agent gọi tool hỏi ý kiến, người dùng bấm chọn Option 1 và Agent tiếp tục chạy thành công.
