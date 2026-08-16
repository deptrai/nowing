---
story_key: "24-6"
epic: "epic-24"
story: "24.6"
title: "Two-Way AI Outreach Auto-Reply Agent"
status: "ready-for-dev"
baseline_commit: "6ac305274"
---

# Story 24.6: Two-Way AI Outreach Auto-Reply Agent

## Story Overview

As a busy founder or sole sales representative,
I want an AI Auto-Reply Agent that listens to incoming messages from prospects on Zalo OA and Telegram, understands their questions, answers accurately based on my Workspace Knowledge Base documents, and alerts me on hot buying signals,
So that no customer inquiry is left unanswered 24/7 while my time is focused on closing deals.

---

## Architectural Invariants (INV-24.7, INV-24.8, INV-23.11)
- **INV-24.7 (Inbound Auto-Reply Grounding & Async ACK SLA):** Webhook Zalo/Telegram BẮT BUỘC trả về `HTTP 200 OK` trong `< 100ms` và đẩy payload vào Redis Queue. AI Auto-Reply Bot chạy bất đồng bộ với `temperature = 0.0`, RAG Embedding Cosine Threshold `>= 0.75`, tuyệt đối từ chối tự ý cam kết giá/chiết khấu/hợp đồng ngoài tài liệu tham chiếu.
- **INV-24.8 (Human Escalation Handover & Auto-Reply Pause):** Khi phát hiện ý định mua hàng (Buying Signals) hoặc khi Sales Rep nhắn tin thủ công/nhận tư vấn, bot tự động tạm dừng (`auto_reply_paused`) 24 giờ cho cuộc hội thoại đó và bắn thông báo khẩn qua Telegram Bot.

---

## Acceptance Criteria

1. **Async Webhook Ingest & Redis Rapid-Fire Debouncing:**
   - **Given** rapid incoming webhook events (burst messages in < 3s),
   - **When** received,
   - **Then** Webhook returns `HTTP 200` in < 100ms, and Redis Inbound Debounce Buffer aggregates the messages into a single synthesized prompt before invoking the LLM.

2. **RAG-Grounded Factual Answering & Anti-Hallucination Guard:**
   - **Given** a prospect asking product or service questions,
   - **When** `AutoReplyAgent` generates a reply,
   - **Then** it retrieves verified chunks from Workspace Knowledge Base. If RAG similarity score < 0.75 or pricing is ungrounded, it politely defers to human sales without inventing numbers.

3. **High-Intent Detection & Telegram Escalation:**
   - **Given** prospect intent indicating hot buying signal (e.g. *"Báo giá cho tôi"*, *"Hẹn xem nhà"*),
   - **When** detected by `InboundIntentClassifier`,
   - **Then** it dispatches a high-priority alert to the sales rep's Telegram with inline `[Nhận Tư Vấn]` button and pauses AI auto-reply for 24h.

4. **Human-in-the-Loop Takeover Sync:**
   - **Given** an active conversation,
   - **When** a human sales rep types a message in the inbox,
   - **Then** the system automatically sets Redis key `auto_reply_paused:{thread_id}` for 24 hours, preventing AI interference.

---

## Technical Tasks

### Backend Implementation
- [ ] Service: Xây dựng `AutoReplyAgent` (`nowing_backend/app/services/auto_reply_agent.py`) kết nối RAG retriever và intent classifier.
- [ ] Worker & Debounce: Xây dựng Celery task xử lý inbound message queue với Redis 3s debouncing buffer.
- [ ] Notification: Tích hợp Telegram interactive alert (`app/gateway/telegram/formatting.py`) với callback `[Nhận Tư Vấn]`.

### Frontend Implementation
- [ ] Settings: Bổ sung Auto-Reply Toggle và Knowledge Base connection status trong cài đặt kênh giao tiếp.

---

## Verification Commands

```bash
# Backend tests
cd nowing_backend
uv run ruff check app/services/auto_reply_agent.py tests/unit/gateway/test_auto_reply_agent.py
uv run pytest tests/unit/gateway/test_auto_reply_agent.py tests/unit/gateway/test_zalo_webhook_hmac.py -q
uv run pytest tests/integration/gateway/test_auto_reply_pipeline.py -q

# Frontend check
cd ../nowing_web
pnpm tsc --noEmit
```
