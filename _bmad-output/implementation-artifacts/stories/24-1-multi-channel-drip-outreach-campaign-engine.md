# Story 24.1: Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)

Status: `ready-for-dev`
Epic: `epic-24`

## Story Overview

As an enterprise sales team, agency or growth marketer,
I want to design and launch multi-channel automated drip campaigns (Zalo ZNS, Telegram Bot, and Email) with conditional delays and AI-personalized content,
So that leads discovered across Nowing are automatically nurtured into booked appointments and qualified opportunities without manual repetitive outreach.

---

## Architectural Invariants
- **INV-24.1 (Stateful Cadence Scheduler):** Bảng `campaign_steps` lưu trữ trạng thái execution step, dispatch qua Celery Beat / Redis delayed sets.
- **INV-24.2 (Anti-Spam & DNC Check):** Kiểm tra opt-out / DNC trước mọi bước gửi tin. Khi nhận phản hồi `STOP` / `HUY`, hủy campaign ngay lập tức.
- **INV-23.2 (Sending Window):** Khung giờ gửi Zalo ZNS / Email tuân thủ 08:00 – 21:30.

---

## Acceptance Criteria

1. **Visual Cadence Builder UI:**
   - Cung cấp giao diện thiết lập kịch bản nuôi dưỡng đa bước:
     - `Step 1`: Gửi tin nhắn mở đầu Zalo ZNS / Telegram Bot với biến số cá nhân hóa (`{customer_name}`, `{company}`, `{property_title}`).
     - `Step 2`: Điều kiện chờ (Wait 24h/48h) nếu chưa có phản hồi.
     - `Step 3`: Gửi Email follow-up hoặc thông báo cho nhân viên kinh doanh phụ trách.
2. **AI-Personalized Generation:**
   - LLM tự động điều chỉnh văn phong tin nhắn phù hợp với từng nhóm đối tượng (môi giới, chủ doanh nghiệp, ứng viên) dựa trên dữ liệu trích xuất từ scraper.
3. **Automated Two-Way Status Interruption:**
   - Khi prospect phản hồi qua bất kỳ kênh nào (Zalo Webhook `user_send_text` hoặc Telegram update), chiến dịch cho lead đó tự động chuyển trạng thái sang `responded` và ngắt các bước gửi tự động tiếp theo.
4. **Analytics & Conversion Dashboard:**
   - Thống kê tỷ lệ gửi thành công (Sent), Đã đọc (Delivered/Read), và Phản hồi (Responded).

---

## Technical Tasks
- [ ] Backend: Tạo schema bảng `drip_campaigns`, `campaign_steps`, `campaign_enrollments` trong Alembic migration.
- [ ] Backend: Xây dựng `DripCampaignSchedulerService` điều phối lịch gửi qua Celery Beat.
- [ ] Backend: Tích hợp `InboundWebhookInterceptor` ngắt chuỗi tự động khi nhận phản hồi.
- [ ] Frontend: Xây dựng `VisualCadenceBuilder` component trong `/dashboard/[workspace_id]/automations/campaigns`.
- [ ] Unit & Integration Tests: Test kịch bản 3 bước, test ngắt bước khi có phản hồi, test tuân thủ DNC blacklist.
