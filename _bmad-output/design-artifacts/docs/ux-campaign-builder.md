# UX Specification: Campaign Builder & SDR Lead Workbench (Story 21.15)
**Persona:** Sally — Lead UX Designer  
**Product:** Nowing Agent Team — B2B Lead Intelligence Platform  
**Target Audience:** SDRs, BDRs, Growth Leads, Sales Managers  
**Status:** Implemented & Scaffolded in `nowing_web`

---

## 1. Executive Summary & Design Philosophy

Nowing Lead Intelligence transforms raw, noisy multi-channel signals (Facebook Groups, Telegram Channels, Batdongsan, TopCV/ITviec, National Procurement Tender Portal) into verified, high-converting B2B pipeline opportunities.

The UX architecture is anchored on three core pillars:
1. **Speed & Ergonomics for SDRs:** Sub-second 1-click lead qualification (`Qualified`, `Not ICP`, `Bad Contact`, `Already Customer`) with optimistic UI and keyboard shortcuts.
2. **Glass-Box AI Explainability:** Every lead carries transparent fit scoring, weight breakdowns, intent extraction, hiring velocity evidence, and pre-crafted Vietnamese icebreakers in a slide-over drawer.
3. **Structured 3-Step Campaign Orchestration:** Guided campaign wizard with industry presets (B2B SaaS, Real Estate, Agency, FMCG, Gov Tenders), 1-Click Reverse-ICP URL extraction, and real-time VND budget/lead estimators.

---

## 2. User Flows & System Architecture

```
                                  [ Lead Generation Journey ]
                                                │
         ┌──────────────────────────────────────┴─────────────────────────────────────┐
         ▼                                                                            ▼
┌─────────────────────────────────┐                                        ┌─────────────────────────────────┐
│     Step 1: Campaign Builder     │                                        │     Step 2: Lead Workbench      │
│  (3-Step Wizard & ICP Presets)  │                                        │   (SDR High-Velocity Review)    │
└────────────────┬────────────────┘                                        └────────────────┬────────────────┘
                 │                                                                          │
  ┌──────────────┼──────────────┐                                            ┌──────────────┼──────────────┐
  ▼              ▼              ▼                                            ▼              ▼              ▼
[Step 1: ICP] [Step 2: Budget] [Step 3: Launch]                        [Stage Badges] [1-Click Qual] [AI Rationale]
 - Presets     - Sources      - Schedule (Once/Cron)                    - Raw          - Qualified     - Factor weights
 - Reverse-ICP - Lead Target  - Export (CRM/Lark/CSV)                   - Scored       - Not ICP       - Signal snippets
 - Intent/Tags - Max VND/Day  - Live Preview                            - Verified     - Bad Contact   - Zalo Icebreaker
```

---

## 3. Wireframes & Layout Specifications

### 3.1 3-Step Campaign Builder (`CampaignBuilder.tsx`)

```
+-----------------------------------------------------------------------------------------------+
|  [Rocket] Tao Chien Dich Lead Generation                               [X] Dong Wizard         |
|  Thiet lap bo loc ICP, ngan sach da kenh va lich trinh thu thap                                |
+-----------------------------------------------------------------------------------------------+
|  (1) Bo Loc ICP (Dinh Vi)  ━━━>  (2) Nguon & Ngan Sach  ━━━>  (3) Khoi Chay & Len Lich        |
+-----------------------------------------------------------------------------------------------+
|  [ Step 1: ICP Builder Content ]                                                              |
|                                                                                               |
|  * Chon mau nganh nhanh (Vertical Presets):                                                  |
|  [ B2B SaaS ]  [ Bat Dong San ]  [ Recruitment Agency ]  [ Dau Thau Cong ]  [ FMCG ]         |
|                                                                                               |
|  * 1-Click Reverse-ICP tu Website/Landing Page doi thu:                                       |
|  [ https://example.com/pricing                          ] [✨ Phan tich ICP tu dong]         |
|                                                                                               |
|  * Nganh nghe muc tieu (Industries): [ Cong nghe thong tin x ] [ Thuong mai dien tu x ]       |
|  * Khu vuc dia ly: [ Ha Noi x ] [ TP. Ho Chi Minh x ] [ Da Nang x ]                           |
|  * Intent muc tieu: [ (x) BAN ] [ (x) MUA ] [ ( ) TUYEN ] [ ( ) DAU THAU ]                    |
|  * Tu khoa loai tru (Negative): [ sinh vien, gia re, tuyen dung gap ]                         |
+-----------------------------------------------------------------------------------------------+
|  [ Quay lai ]                                              [ Tiep tuc: Nguon & Ngan sach -> ]  |
+-----------------------------------------------------------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------------+
|  [ Step 2: Nguon Du Lieu & Du Toan Ngan Sach ]                                                |
|                                                                                               |
|  * Nguon thu thap kich hoat:                                                                 |
|  [x] Facebook Groups    [x] TopCV / ITviec    [x] Batdongsan.com    [x] Dau Thau Cong         |
|                                                                                               |
|  * Muc tieu so Lead: [==== 150 Lead ====]                                                     |
|  * Ngan sach toi da / ngay: [ 500,000 VND ] (Uoc tinh chi phi: ~750,000 VND tong chien dich) |
|  * Diem Fit toi thieu: [ 70 / 100 ]            * Diem Intent toi thieu: [ 60 / 100 ]          |
|                                                                                               |
|  * Compliance & Bao ve:                                                                       |
|  [X] Tu dong loai tru so dien thoai thuoc danh sach Do-Not-Call (DNC Viet Nam)                |
|  [ ] Tu dong Mo khoa (Unlock) so dien thoai da xac thuc Zalo/CSDL                             |
+-----------------------------------------------------------------------------------------------+
|  [ <- Quay lai Step 1 ]                                        [ Tiep tuc: Khoi chay -> ]     |
+-----------------------------------------------------------------------------------------------+
```

### 3.2 SDR Lead Workbench (`LeadWorkbench.tsx`)

```
+-----------------------------------------------------------------------------------------------+
|  [Search Lead / Cong ty...] [Nguon: All v] [Pipeline: Scored v] [SDR Status: All v] [Refresh]  |
+-----------------------------------------------------------------------------------------------+
| [ ] | DOANH NGHIEP / NGUOI DANG | NGUON & INTENT | FIT SCORE | TIEN TRINH | SDR QUALIFY | ACT |
+-----+---------------------------+----------------+-----------+------------+-------------+-----+
| [x] | FPT Software              | TopCV          | 92/100 🔥 | [Scored]   | [👍][👎][🚫]| [...]|
|     | Nguyen Van A - CTO        | TUYỂN DỤNG     | High Fit  | (Badge)    | Qualified   | [🔍]|
+-----+---------------------------+----------------+-----------+------------+-------------+-----+
| [x] | Vingroup JSC              | Batdongsan     | 88/100 🟢 | [Enriched] | [👍][👎][🚫]| [...]|
|     | Tran Thi B - Mua hang     | MUA BÁN        | Good Fit  | (Badge)    | Reviewing   | [🔍]|
+-----+---------------------------+----------------+-----------+------------+-------------+-----+
| [ ] | Techcombank Solution      | Dau Thau Cong  | 95/100 🔥 | [Verified] | [👍][👎][🚫]| [...]|
|     | Le Van C - GD Mua sam     | ĐẤU THẦU       | High Fit  | (Badge)    | Qualified   | [🔍]|
+-----------------------------------------------------------------------------------------------+
| ⚡ FLOATING BULK BAR: Da chon 2 leads  │ [🔓 Unlock Phones] [💬 Bulk Zalo] [📤 Xuat CRM/CSV]  |
+-----------------------------------------------------------------------------------------------+
```

### 3.3 Explainable AI Rationale Drawer (Slide-Over)

```
+───────────────────────────────────────────────────────────────+
| 🔍 AI Fit & Signal Rationale                      [X] Đóng    |
| Phân tích độ tương thích và bằng chứng thu thập               |
+───────────────────────────────────────────────────────────────+
| 🏢 FPT Software  •  Fit Score: 92/100 (High Confidence: 94%) |
|                                                               |
| 💡 Đánh Giá Tổng Quan:                                         |
| "FPT Software có độ tương thích cao nhờ quy mô >1000 nhân sự, |
| đang tuyển dụng 15 vị trí AI Engineer và có nhu cầu mua sắm." |
|                                                               |
| 📊 Phân Rã Trọng Số Tương Thích (Fit Factor Breakdown):       |
| • Ngành nghề & Quy mô (Trọng số 35%):  95/100  [ Khớp ICP ]   |
| • Tín hiệu Mua / Tuyển (Trọng số 30%): 90/100  [ Intent Cao ] |
| • Kênh & Liên hệ (Trọng số 20%):       88/100  [ Đã xác minh] |
| • Pháp lý & DNC Check (Trọng số 15%): 100/100  [ An toàn ]    |
|                                                               |
| 📡 Bằng Chứng Thu Thập (Source Evidence):                     |
| Nguồn: TopCV.vn | 2 giờ trước                                 |
| Trích đoạn: "Cần tìm đối tác cung cấp giải pháp Cloud Server  |
| và AI LLM Gateway cho dự án Banking quy mô 50k CCU..."        |
|                                                               |
| 💬 Gợi Ý Mở Đầu Zalo (Contextual Icebreaker):                 |
| "Chào anh A, em thấy FPT đang mở rộng đội ngũ AI Gateway..."   |
| [ Sao chép tin nhắn ]  [ Gửi ZNS / Tin nhắn Zalo ngay ]       |
+───────────────────────────────────────────────────────────────+
```

---

## 4. Component Architecture & State Management

| Component File | Role | State & Dependencies |
| :--- | :--- | :--- |
| `CampaignBuilder.tsx` | 3-Step Wizard for launching lead generation campaigns | Local multi-step form state, vertical presets, live budget estimator, `leadsApiService.createCampaign` & `launchCampaign`. |
| `LeadWorkbench.tsx` | High-density SDR workbench for qualifying leads | Selection atoms, optimistic SDR status mapping, pipeline stage progression, AI drawer slide-over. |
| `LeadsContent.tsx` | Master view switcher for Lead Intelligence module | Tab navigation across `LeadWorkbench`, `CampaignBuilder`, `NowingLeadMatrix`, and `LeadCard` grid. |
| `campaign.types.ts` | Zod contracts & TypeScript schemas | Defines `Campaign`, `IcpConfig`, `SourceBudgetConfig`, `WorkbenchLead`, `AiRationale`, `SdrQualificationStatus`. |
| `leads-api.service.ts` | Frontend API client | Full CRUD and lifecycle methods for campaigns (`list`, `create`, `launch`, `pause`) and SDR lead qualification (`qualifyLead`). |

---

## 5. SDR Interaction Guidelines & Ergonomics

1. **Progressive Pipeline Stages:**
   - `raw` (Xám): Thu thập thô từ webhook/crawler chưa qua xử lý.
   - `deduped` (Xanh biển nhạt): Đã khử trùng lặp qua MST và Số điện thoại.
   - `scored` (Vàng): Đã tính toán Fit Score và Intent Score qua LLM/Embedding.
   - `enriched` (Tím): Đã làm giàu dữ liệu qua Company Graph và thông tin đăng ký kinh doanh.
   - `verified` (Xanh ngọc): Đã kiểm tra trạng thái DNC và số điện thoại tồn tại thực tế trên Zalo/Telco.

2. **1-Click Rapid Qualification:**
   - `Qualified` (`👍`): Đánh dấu lead hợp lệ, tự động kích hoạt workflow bàn giao cho AE hoặc đẩy sang CRM.
   - `Not ICP` (`👎`): Ghi nhận feedback để tinh chỉnh prompt/embedding weights của Workspace.
   - `Bad Contact` (`🚫`): Đánh dấu số rác/thuê bao, đưa vào blacklist để không tốn chi phí unlock.
   - `Already Customer` (`🤝`): Trùng khách hàng hiện tại, bảo vệ mối quan hệ kinh doanh.

3. **Floating Multi-Lead Batch Bar:**
   - Xuất hiện linh hoạt ở đáy màn hình khi SDR chọn từ 1 lead trở lên.
   - Hỗ trợ Mở khóa hàng loạt số điện thoại (Batch Unlock).
   - Tạo kịch bản cá nhân hóa Zalo cho toàn bộ danh sách đã chọn.
   - Xuất nhanh ra CSV hoặc đồng bộ sang Lark Base / Hubspot.
