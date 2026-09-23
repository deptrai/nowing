# Sprint Change Proposal: B2B Outbound AI SDR & Autonomous Revenue Engine (Phase Next)

**Date:** 2026-09-17  
**Author:** Luisphan & BMad Core Team (Mary - Business Analyst / Developer)  
**Status:** DRAFT (Under Review)  
**Trigger:** Market Research Deep-Recon (2026-09-17) & Cross-Artifact Audit to prevent feature duplication across Epics 21, 22, 24, 26, 27, 34.

---

## 1. Issue Summary

### 1.1. Context & Trigger
Sau khi hoàn thành nghiên cứu thị trường chuyên sâu (`market-dinh-gia-dung-luong-thi-truong-b2b-outbo-2026-09-17`), nhóm đề xuất mở rộng Nowing sang Phase tiếp theo tập trung vào **"B2B Outbound AI SDR & Revenue Engine"**. 
Tuy nhiên, qua rà soát toàn diện codebase (`nowing_backend/app/lead_intelligence/`, `app/services/sequencer/`, `nowing_web/`) và các artifact đã hoàn thành (Epic 21, 22, 24, 26, 27, 34), phát hiện **nhiều cấu phần đề xuất đã tồn tại ở mức hạ tầng hoặc backend, nhưng thiếu các mắt xích kết nối cuối cùng (last-mile workflows) hoặc chưa được đưa lên giao diện người dùng**.

Nếu không tiến hành phân tích tác động và điều chỉnh lộ trình (Course Correction), dự án sẽ mắc phải sai lầm nghiêm trọng: **Viết lại các module trùng lặp (duplication)** thay vì tận dụng và hoàn thiện các tài sản kỹ thuật sẵn có.

---

## 2. Impact & Gap Analysis (So sánh Tính năng Có sẵn vs. Điểm Gaps)

Dưới đây là ma trận đối chiếu chi tiết để ngăn chặn triệt để tình trạng "phát minh lại bánh xe":

| Lĩnh vực chức năng | Hiện trạng trong Codebase (ĐÃ CÓ) | Nguy cơ Duplicate nếu làm mới | Khoảng trống thực tế (REAL GAPS cần giải quyết) |
| :--- | :--- | :--- | :--- |
| **1. Buying Signals & Intent Radar** | • `SignalDetectionService` (`app/lead_intelligence/signals/service.py`) hỗ trợ 5 types: `funding`, `hiring`, `tech_stack`, `executive_move`, `news`.<br>• Lưu `SignalEvent` DB, có credit billing. | Viết lại model `SignalEvent` hoặc xây dựng lại bộ phân tích tin tuyển dụng VietnamWorks/TopCV. | **GAP-1:** Hiện tại chỉ là On-Demand/Query scan khi user kích hoạt.<br>👉 **Giải pháp:** Xây dựng **Background Radar Daemon** (quét Celery định kỳ) tự động đẩy tín hiệu biến động tuyển dụng/MST mới vào Live Matrix, nối với `stream:telegram:raw_events` (Epic 22) để bắt từ khóa mua hàng realtime trong group Telegram. |
| **2. Multi-Channel Drip Sequencer** | • `app/services/sequencer/` (Epic 24.1, 24.7) đã có Celery task, scheduling, step execution cho Email, Zalo ZNS, Telegram.<br>• `inbound.py` (Epic 24.6) có 2-way auto-reply. | Viết lại Sequencer engine hoặc database schema cho chiến dịch drip. | **GAP-2:** Prompt sequencer & auto-reply còn thô, thiếu **Vietnam Honorific/Hierarchy Engine** (xưng hô anh/chị/em chuẩn theo chức danh/tuổi tác từ LinkedIn/MST).<br>**GAP-3:** Chưa có **Smart Meeting Booker**: AI auto-reply chưa thể đồng bộ Google/Lark Calendar để gợi ý slot trống và chốt lịch tự động. |
| **3. Zalo Outbound & Personal Outreach** | • Zalo OA OpenAPI v3 + ZNS template (Epic 23.2).<br>• Zalo assisted link `zalo.me/{phone}` (Epic 21.6).<br>• Phone waterfall 3-tier (Epic 21.3, 24.2, 33.3). | Cố gắng build automation bot spam Zalo cá nhân (dẫn đến rủi ro bị Zalo khóa tài khoản vĩnh viễn). | **GAP-4:** Cần nâng cấp **Nowing Lead Clipper Extension (Epic 24.4)** thành **Zalo Web/Desktop Co-pilot**: Khi sales mở Zalo, extension tự động fill tin nhắn cá nhân hóa ngữ cảnh (1-click send an toàn 100% - Zero Ban Penalty). |
| **4. Visual Pitch & Artifacts** | • Epic 27.1: Full-stack Web Builder (Dokploy container deploy, AST mutator).<br>• Epic 27.2: Marp Presentation Studio.<br>• Epic 26.9b: Excel export sandbox. | Xây dựng lại template landing page hoặc presentation generator độc lập. | **GAP-5 (Mắt xích lớn nhất):** Web Builder và Slides đang đứng độc lập trong Chat, **CHƯA ĐƯỢC KẾT NỐI VÀO SEQUENCER!**<br>👉 Cần action tự động trong Sequencer: *"Sinh 1-Click Interactive Mini-Page cho prospect domain X"* và chèn link vào email/Zalo.<br>**GAP-6:** Chưa có **Realtime Engagement Heatmap/Tracking**: Báo về Telegram/Zalo cho sales khi prospect click mở xem slide/web. |
| **5. CRM Pipeline & Kanban** | • `app/services/lead_assignment_service.py` (Epic 24.3).<br>• `nowing_web/.../crm/page.tsx` (Deal Pipeline Kanban & Activity Timeline, Epic 34.1, 34.3). | Xây lại trang Kanban CRM hoặc lead assignment logic. | **GAP-7:** Kanban và Timeline đã có UI/API nhưng chưa có trigger kéo/thả tự động: Khi prospect reply trên Zalo/Email, tự động nhảy stage từ `Contacted` sang `Meeting Scheduled`. |
| **6. Định giá & Credit Ledger** | • Credit wallet, 2-phase transactional lock (Epic 33.3).<br>• VietQR instant payout (Epic 23.3, 21.18). | Viết lại cơ chế ví tín dụng hoặc cổng thanh toán. | **GAP-8:** Chưa đóng gói **Hybrid Packaging (990k / 2.490k / 5.990k VNĐ/tháng)** trên giao diện billing và chưa có chính sách **Pay-Per-Qualified-Meeting (PPQM) escrow lock**. |

---

## 3. Recommended Approach (Định hướng điều chỉnh)

Thay vì tạo ra các Epic cồng kềnh mới chồng chéo lên Epics 21, 24, 27, chúng ta áp dụng phương án **"Surgical Gap-Filling & Workflow Unification"** thông qua **Epic 37 (Tập trung toàn bộ các Last-Mile Gaps)**:

```
[Nowing Data & Scraper Assets] (Epics 10, 12, 16, 21, 22)
                 │
                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│     EPIC 37: NOWING REVENUE ENGINE — UNIFIED OUTBOUND WORKSTATION      │
├────────────────────────────────────────────────────────────────────────┤
│ 37.1: Proactive Signal Radar (Background Scanner & Telegram Listener)   │
│ 37.2: Vietnam Cultural & Honorific Tone Engine for Sequencer / Reply   │
│ 37.3: Calendar Smart Booker Integration for Auto-Reply (Google / Lark) │
│ 37.4: Zalo Co-pilot Overlay in Lead Clipper Extension (Zero Ban Risk)  │
│ 37.5: Sequencer ➔ 1-Click Visual Mini-Portal & Slide Pitch Generator   │
│ 37.6: Prospect Engagement Tracker (Realtime Telegram Ping on Open)     │
│ 37.7: Hybrid Pricing Tiers UI & Auto-Refund Guarantee SLA              │
└────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
[Automated Qualified Pipeline & Closed Deals]
```

---

## 4. Detailed Story Change Proposals

### Story 37.1: Proactive Intent Signal Radar (Background Ingestion & Alerting)
* **Kế thừa:** `SignalDetectionService` (`app/lead_intelligence/signals/service.py`) và Telegram Stream (`stream:telegram:raw_events`).
* **Đổi mới:**
  * Thêm Celery Beat task `scan_high_intent_companies_periodic` chạy 6 tiếng/lần quét các công ty có biến động tăng tuyển dụng trên TopCV/VietnamWorks hoặc mới thành lập theo MST.
  * Thêm worker lắng nghe Redis Stream Telegram để match các regex mua hàng ("cần tìm", "báo giá", "thuê ngoài"), tự động tạo lead vào Matrix của workspace.

### Story 37.2: Vietnam Cultural Honorific & Relationship Tone Engine
* **Kế thừa:** Sequencer email/message dispatch (`app/services/sequencer/services/executor.py`).
* **Đổi mới:**
  * Xây dựng `VietnamHonorificResolver`: Dựa vào năm sinh/tuổi ước tính từ CCCD/MST/LinkedIn và chức vụ (C-level, Trưởng phòng, Chuyên viên), tự động cấu hình cặp đại từ nhân xưng: `Anh - Em`, `Chị - Em`, hoặc `Quý đối tác - Chúng tôi`.
  * Đảm bảo mọi tin nhắn gửi đi qua Zalo/Email đạt độ tự nhiên bản địa, loại bỏ hoàn toàn văn phong dịch máy.

### Story 37.3: Smart Meeting Booking Engine for AI Auto-Reply
* **Kế thừa:** `app/services/sequencer/inbound.py` (Epic 24.6).
* **Đổi mới:**
  * Tích hợp Google Calendar API và Lark Calendar API qua OAuth token trong Workspace Settings.
  * Khi prospect phản hồi tích cực ("tuần sau rảnh", "gửi thêm thông tin rồi trao đổi"), AI trích xuất thời gian trống trong tuần của Sales Rep và gửi đề xuất 2 khung giờ lựa chọn. Tự động book event khi prospect đồng ý.

### Story 37.4: Zalo Desktop/Web Co-pilot Overlay in Nowing Lead Clipper
* **Kế thừa:** Chrome Extension `nowing_browser_extension/` (Epic 24.4) và `zalo.me/{phone}` assisted link.
* **Đổi mới:**
  * Content script trên `chat.zalo.me`: Khi mở cuộc trò chuyện với số điện thoại đã unlock từ Nowing, hiển thị Floating Drawer gợi ý kịch bản mở đầu và nút "1-Click Chèn Nội Dung".
  * Thao tác gửi do người dùng bấm gửi thật trên trình duyệt -> 100% không vi phạm chính sách của Zalo, không lo bị khóa tài khoản.

### Story 37.5: Sequencer-to-Artifact Generator (1-Click Mini-Pitch Portal)
* **Kế thừa:** Web Builder Engine (`app/services/web_builder/`, Epic 27.1).
* **Đổi mới:**
  * Bổ sung step loại `generate_pitch_portal` trong Visual Cadence Builder: Hệ thống tạo ra một trang static portal tại `pitch.nowing.ai/{workspace_slug}/{lead_id}` chứa logo prospect, audit vấn đề và giải pháp đề xuất.
  * URL này được tự động chèn vào biến `{{pitch_portal_url}}` trong email/Zalo.

### Story 37.6: Realtime Prospect Engagement Tracker & Telegram Alert
* **Kế thừa:** Telegram Alert Bot (Epic 22.3, 26.6).
* **Đổi mới:**
  * Gắn lightweight tracking script vào `pitch.nowing.ai` và Marp presentation slides.
  * Bắn alert tức thì qua Telegram bot cho Sales Rep: *"🔥 Khách hàng Nguyễn Văn A (Công ty B) vừa mở xem Mini-Pitch của bạn được 2 phút tại trang Báo Giá!"*.

### Story 37.7: Hybrid Pricing Packaging & Auto-Refund Guarantee UI
* **Kế thừa:** `nowing_web/app/dashboard/[workspace_id]/buy-tokens/`, `app/services/wallet_credit.py`.
* **Đổi mới:**
  * Triển khai giao diện bảng giá 3 gói chuẩn: **Starter (990k)**, **Professional (2.490k)**, **Business (5.990k)** kèm thanh toán tự động qua VietQR.
  * Kích hoạt chính sách tự động hoàn credit 100% (Zero-Risk SLA) vào ví người dùng nếu số điện thoại sau khi unlock không có Zalo hoặc phản hồi số không tồn tại.

---

## 5. Implementation Handoff & Governance

* **Phân loại phạm vi (Scope Classification):** **Moderate (Trung bình)** — Không làm thay đổi cấu trúc dữ liệu gốc, không phá vỡ các migration cũ, chỉ bổ sung orchestration và các mắt xích kết nối.
* **Định tuyến thực thi:**
  * **Product Owner / Business Analyst (Mary):** Cập nhật `epics.md` bổ sung Epic 37 với 7 stories trên; giữ nguyên tính toàn vẹn của Epics 1–36.
  * **Developer Agent (Amelia):** Triển khai theo thứ tự ưu tiên: Story 37.1 & 37.2 (Backend) ➔ 37.4 & 37.5 (Fullstack & Extension) ➔ 37.3 & 37.6 (Integration).
* **Tiêu chí nghiệm thu cốt lõi (Success Criteria):**
  1. Không viết thêm bất kỳ bảng Database mới nào nếu các bảng `SignalEvent`, `Sequence`, `Lead`, `VerifiedContact` hiện có đã đáp ứng được.
  2. Toàn bộ 7 stories đều có unit test và integration test bao phủ, tương thích 100% với transactional session test suite của Nowing.
  3. UI tuân thủ thiết kế hiện đại Emerald Green / Sọc Caro của Nowing Split Canvas.
