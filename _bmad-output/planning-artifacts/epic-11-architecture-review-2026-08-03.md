---
title: Epic 11 — Architecture Review
status: review
createdAt: '2026-08-03'
---

# Epic 11 — Architecture Review (vs. Nowing Architecture Spine)

**Reviewer:** Devin (assisted by vibervn context engine / direct code read)
**Scope:** Epic 11 "Telegram Automation & Bot" in `_bmad-output/planning-artifacts/epics.md`
**Inputs:** `ARCHITECTURE-SPINE.md` (`/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`), `nowing_backend/app/automations/*`, `nowing_backend/app/gateway/telegram/*`, `nowing_backend/app/notifications/*`, `nowing_backend/app/db.py`, `nowing_backend/app/zero_publication.py`.

---

## 1. Tóm tắt

Epic 11 nhất quán với phần lớn AD của Architecture Spine: giữ nguyên monolith (`AD-1`), dùng `AsyncSession` + Alembic (`AD-2`), đồng bộ in-app notification qua Zero (`AD-5`), gọi Telegram Bot API như external HTTP dependency (`AD-1`/`AD-15`), không động đến license BSL (`AD-16`).

Tuy nhiên có **3 vấn đề cần giải quyết trước khi implement** và **4 vấn đề cần làm rõ** trong story specs.

---

## 2. Vấn đề blocker / cần giải quyết trước khi code

### 2.1 `/run <automation>` chưa có cơ chế fire automation (CRITICAL)

**Phát hiện:**
- `TriggerType` hiện tại chỉ có `SCHEDULE`, `EVENT`, `MEMORY_CHANGE`, `MANUAL`.
- `MANUAL` là "reserved" trong enum nhưng **chưa được register** trong `app/automations/triggers/builtin/`. `MANUAL` chưa có trigger definition, selector, hay cách tạo `AutomationTrigger`.
- `launch_run()` bắt buộc một `AutomationTrigger` object để tạo `AutomationRun`.
- Không có HTTP route hay service nào để "run now" một automation từ ngoài trigger scheduler.

**Hệ quả:** Story 11.10 nói "gọi automation fire service" nhưng service đó chưa tồn tại. Không thể implement `/run` như đã spec.

**Khuyến nghị (chọn 1):**
- **A.** Thêm `TriggerType.MANUAL` registration + `app/automations/triggers/builtin/manual/` để `/run` tạo một trigger tạm hoặc dùng trigger manual được tạo sẵn, rồi gọi `launch_run()`.
- **B.** Tách `launch_run()` thành `launch_run(..., trigger_id: int | None = None)` cho phép `trigger_id=None` khi fire từ external command, và tạo một `ManualLaunchService`.
- **C.** Thêm route `POST /automations/{automation_id}/runs` (manual run) và Telegram `/run` gọi route này qua `NowingClient` (nếu internal) hoặc tương đương.

### 2.2 `TelegramClient` chưa hỗ trợ `reply_markup` (CRITICAL cho Story 11.7)

**Phát hiện:**
- `TelegramClient.send_message` signature hiện tại: `chat_id, text, parse_mode, reply_to_message_id`.
- Không có tham số `reply_markup`.
- Không có `answer_callback_query`, `edit_message_reply_markup`.

**Hệ quả:** Story 11.7 (inline keyboard) và 11.8 (callback query) không thể implement mà không mở rộng client.

**Khuyến nghị:**
- Thêm `reply_markup: dict | None = None` vào `TelegramClient.send_message`.
- Thêm `answer_callback_query(callback_query_id, text=None, show_alert=False)`.
- Thêm `edit_message_reply_markup(chat_id, message_id, reply_markup)`.
- Cập nhật `TelegramAdapter.send_message` để chuyển `reply_markup`.

### 2.3 Thiếu Alembic migration cho `notification_preferences` (CRITICAL cho Story 11.1)

**Phát hiện:**
- Story 11.1 đề xuất `notification_preferences` JSONB trên `User` hoặc bảng riêng.
- `AD-2` quy định mọi thay đổi schema phải có migration Alembic.
- `epics.md` đã được sửa để ghi "kèm migration Alembic", nhưng migration chưa được lên kế hoạch trong story.

**Khuyến nghị:**
- Thêm AC: "Tạo migration Alembic `add_user_notification_preferences` hoặc bảng `user_notification_preferences`". Migration phải là một task riêng hoặc AC của 11.1.

---

## 3. Vấn đề nghiêm trọng / cần làm rõ

### 3.1 Sai tên permission `AUTOMATIONS_RUN` (đã sửa)

- `Permission` enum không có `AUTOMATIONS_RUN`, chỉ có `AUTOMATIONS_EXECUTE`.
- Đã sửa `epics.md` Story 11.10 từ `Permission.AUTOMATIONS_RUN` → `Permission.AUTOMATIONS_EXECUTE`.

### 3.2 `/status` cần kiểm tra permission

- `/status` đọc danh sách run của workspace. Cần kiểm tra `Permission.AUTOMATIONS_READ` hoặc `AUTOMATIONS_EXECUTE` tùy mức độ nhạy.
- Story 11.9 nên bổ sung AC về permission.

### 3.3 "Connector name" trong `write_back_telegram` là khái niệm mơ hồ

**Phát hiện:**
- Telegram gateway dùng `ExternalChatAccount` (`is_system_account` hoặc BYO), không dùng "connector" như Notion/Slack MCP connector.
- Story 11.4/11.6 dùng `connector_name` để chọn bot, nhưng hệ thống hiện có `account_id`/`is_system_account`.

**Khuyến nghị:**
- Đổi param thành `account_id: int | None` hoặc `account_name: str | None` hoặc `use_system_bot: bool = True`.
- Nếu muốn dùng "connector", cần định nghĩa rõ Telegram connector ở đâu (`ExternalChatAccount` có `name`? hiện chưa có `name` field).

### 3.4 Telegram Bot API là external dependency — cần failure discipline

**Phát hiện:**
- `AD-15` bắt external dependency phải có: contract versioned, cost accounting, degrade, rate limit.
- Telegram Bot API free, nhưng vẫn có rate limit (30 msg/sec cho cùng chat, 20 msg/sec toàn bot).
- `TelegramClient` đã retry `RetryAfter`, nhưng không có circuit breaker, timeout rõ, hay fallback policy khi Telegram down.

**Khuyến nghị:**
- Thêm `timeout` rõ ràng (ví dụ 30s) trong `TelegramClient`.
- Log/metric số lỗi Telegram để observability.
- Xác định `on_failure` behavior: lỗi gửi Telegram không được làm automation run fail (Story 11.2 AC đã có, 11.4 cần tương tự).

### 3.5 Có nên track `TokenUsage` cho Telegram? (Open question)

**Phát hiện:**
- `AD-8` unified credit wallet và `AD-10` token usage tracking yêu cầu mọi tác vụ có chi phí phải ghi `TokenUsage`.
- Telegram Bot API free, nhưng gọi API vẫn tốn infra/observability.

**Khuyến nghị:**
- Tạo `usage_type = "telegram_message"` trong `TokenUsage` để tracking, không nhất thiết debit wallet (miễn phí). Hoặc quyết định PO: có tính phí user không?

---

## 4. Kiểm tra AD-by-AD

| AD | Kết luận | Ghi chú |
|---|---|---|
| **AD-1** Monolith | ✅ PASS | Mọi code mới nằm trong `nowing_backend/app/automations/` và `app/gateway/telegram/`, không microservice. |
| **AD-2** Async SQLAlchemy + Alembic | ⚠️ CONDITIONAL | Cần migration cho `notification_preferences` (11.1) và `TokenUsage` nếu tracking Telegram. Các thay đổi khác không cần schema mới. |
| **AD-3** Scraper self-register | ✅ N/A | `write_back_telegram` là action, không phải scraper capability. Không vi phạm. |
| **AD-4** Multi-agent tool registry + permission | ⚠️ NEED CLARIFY | `/run` và `/status` phải kiểm tra permission. `/run` cần cơ chế fire ngoài agent tool registry. |
| **AD-5** Zero sync | ✅ PASS | `notifications` và `automation_runs` đã có trong `zero_publication`. In-app notification sẽ realtime. |
| **AD-6** Next.js proxy | ✅ PASS | UI mới dùng route `/api/v1/...` đã có. |
| **AD-7** MCP stateless | ✅ N/A | Không liên quan. |
| **AD-8** Unified credit wallet | ⚠️ OPEN | Telegram miễn phí, nhưng nên tracking usage. Quyết định PO. |
| **AD-9** RBAC 3 roles | ✅ PASS | Dùng `Permission.AUTOMATIONS_EXECUTE`/`AUTOMATIONS_READ` là đúng (đã sửa). |
| **AD-10** Token usage tracking | ⚠️ OPEN | Tương tự AD-8. |
| **AD-11** Memory | ✅ N/A | Không liên quan. |
| **AD-15** External dependency discipline | ⚠️ PARTIAL | Telegram là external HTTP API; NFR-TELE đã có rate limit/retry, nhưng chưa có contract test hay degrade policy tường minh. |
| **AD-16** License boundaries | ✅ PASS | Telegram code ở `app/gateway/telegram/` (Apache-2.0), không động `app/proprietary/`. |
| **AD-17** Async door | ✅ PASS | Notification gửi qua Celery; `/run` nên dùng `launch_run()` (async enqueue). |
| **AD-19** Anti-bot/CAPTCHA | ✅ N/A | Không liên quan. |
| **AD-20** Screenshot-as-evidence | ✅ N/A | Không liên quan. |

---

## 5. Cập nhật đã thực hiện

- ✅ `epics.md` dòng 1077: `Permission.AUTOMATIONS_RUN` → `Permission.AUTOMATIONS_EXECUTE`.
- ✅ `epics.md` dòng 957: thêm ghi chú "kèm migration Alembic" vào Story 11.1.

---

## 6. Khuyến nghị tiếp theo

1. **Giải quyết blocker 2.1** trước khi implement `/run`: chọn cơ chế fire automation (manual trigger, `launch_run` refactor, hoặc route mới).
2. **Lên spec chi tiết cho `TelegramClient` mở rộng** (reply_markup, callback query, answer callback) trước Story 11.7/11.8.
3. **Làm rõ `connector_name` → `account_id`/`use_system_bot`** trong `write_back_telegram`.
4. **Quyết định PO** về tracking `TokenUsage` cho Telegram.
5. **Bổ sung migration** vào story spec 11.1.
