# Story 24.6: Two-Way AI Outreach Auto-Reply Agent

Status: `ready-for-dev`
Epic: `epic-24`

## Story Overview

As a busy founder or sole sales representative,
I want an AI Auto-Reply Agent that listens to incoming messages from prospects on Zalo OA and Telegram, understands their questions, answers accurately based on my Workspace Knowledge Base documents, and alerts me on hot buying signals,
So that no customer inquiry is left unanswered 24/7 while my time is focused on closing deals.

---

## Architectural Invariants
- **INV-24.7 (Inbound Auto-Reply Grounding):** AI Auto-Reply Bot chỉ được trả lời dựa trên verified documents trong Knowledge Base của Workspace (`search_workspace_docs`). Tuyệt đối không bịa đặt thông tin cam kết ngoài dữ liệu.
- **INV-24.8 (Human Escalation Handover):** Khi phát hiện ý định mua hàng hoặc khi khách yêu cầu gặp nhân viên, bot tự động tạm dừng (pause auto-reply) và gửi thông báo khẩn qua Telegram/Zalo cho chủ Workspace.

---

## Acceptance Criteria

1. **Inbound Webhook Listener & Intent Classifier:**
   - Khi nhận webhook tin nhắn đến (`user_send_text` trên Zalo hoặc message trên Telegram), phân loại ý định: `Hỏi thông tin`, `Báo giá`, `Khiếu nại/Hủy`, `Ý định mua cao (Hot Lead)`, `Hẹn lịch`.
2. **RAG-Grounded AI Response Generation:**
   - Tra cứu tài liệu sản phẩm / FAQ trong Workspace Knowledge Base.
   - Sinh câu trả lời ngắn gọn, lịch sự, đúng sự thật và gửi lại qua Zalo OA / Telegram Bot trong < 3 giây.
3. **Hot Lead Escalation & Human Takeover:**
   - Khi khách nói *"Gặp tư vấn viên"*, *"Tôi muốn mua"* ➔ Gửi thông báo Telegram Bot có nút `[Nhận Tư Vấn]`.
   - Khi Sales Rep bấm nhận hoặc nhắn tin thủ công, AI tạm ngừng tự động trả lời cho cuộc hội thoại đó trong 24 giờ.

---

## Technical Tasks
- [ ] Backend: Xây dựng `AutoReplyAgent` kết nối RAG Knowledge Base.
- [ ] Backend: Tích hợp `InboundIntentClassifier` nhận diện Buying Signals.
- [ ] Backend: Cơ chế Human Escalation qua Telegram notification webhook.
- [ ] Frontend: Toggle bật/tắt Auto-reply trong `/dashboard/[workspace_id]/user-settings` và Conversation Inbox.
- [ ] Unit & Integration Tests: Test RAG grounding, test phân loại intent, test escalation webhook.
