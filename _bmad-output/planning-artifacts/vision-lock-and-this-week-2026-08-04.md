---
title: "Vision Lock — bdsai.vn + Nowing engine — & việc tuần này"
status: "chốt để thực thi"
created: "2026-08-04"
one_line: "Pivot sang sàn rao vặt BĐS + AI (bdsai.vn); Nowing = engine/tools sau lưng. ĐÚNG hướng — chỉ cần đảo THỨ TỰ: validate cầu TRƯỚC, re-architect/mobile/CRM SAU."
---

# Vision Lock + Việc tuần này

## A. Vision (CHỐT) — 4 điểm của bạn: đúng đích

| Điểm bạn nêu | Trạng thái | Ghi chú |
|---|---|---|
| 1. Pivot Nowing research → **bdsai.vn (sàn BĐS + AI)** | ✅ **Chốt** | Đúng hội tụ cả thread |
| 2. Web+mobile app rao vặt + core AI Nowing bên trong (như CRM riêng) | ⚠️ **Đúng ý, sai thứ tự** | Xem §B-2 + kiến trúc §C |
| 3. **Kiến trúc lại toàn bộ hệ thống** | ⚠️ **KHÔNG phải việc trước/tuần này** | Xem §B-1 — đây là bẫy |
| 4. Marketing test, nghe user, free, tìm partner, freemium dần | ✅ **Chốt — và làm TRƯỚC TIÊN** | Chính là việc tuần này §D |

**North star (một câu):** bdsai.vn = sàn rao vặt BĐS có AI cho thị trường VN; **Nowing = engine AI (tools) chạy sau lưng toàn hệ thống**, không còn là research platform độc lập. Thắng BĐS → nhân engine sang vertical khác. Freemium.

## B. Hai chỉnh về THỨ TỰ (đây là phần quan trọng nhất)

**B-1. ❌ "Kiến trúc lại toàn bộ hệ thống" — KHÔNG làm trước, KHÔNG làm tuần này.**
Đây là **bẫy số 1 của founder solo**: rebuild toàn hệ thống *trước khi* biết có ai dùng = tốn hàng tháng, 0 validation, dễ bỏ cuộc. Sửa: **validate cầu trước (pilot 2 tuần) → re-architect DẦN, chỉ cái pilot chứng minh cần.** Không đập lại toàn bộ khi chưa có tín hiệu retention.

**B-2. ❌ Web + mobile app cùng lúc — KHÔNG phải bây giờ.**
Pilot cần **một kênh, lát mỏng nhất** (group Zalo test — bạn đã chọn). **Mobile app + full CRM = SAU** khi có tín hiệu. Xây app trước cầu = cùng một bẫy B-1.

> **Vì sao:** cả 4 điểm đúng ĐÍCH, nhưng điểm 3 và "web+mobile" đang đặt **sai thứ tự** — chúng là **hệ quả của việc CÓ cầu**, không phải điều kiện tiên quyết. Đảo lại: **cầu → rồi mới xây/re-arch.**

## C. Giải phân vân kiến trúc & UX của bạn (chốt luôn)
Bạn phân vân "app rao vặt + AI bên trong như CRM riêng" — chốt:
- **bdsai = SẢN PHẨM** (sở hữu): listings, tìm kiếm, auth/đăng nhập DUY NHẤT, SEO, billing, kiểm duyệt. **"CRM riêng" = workspace của từng môi giới** (leads/tin/Deal-Radar/memory của họ).
- **Nowing = ENGINE headless qua API** (agent, memory, matching, automation) — ẩn sau, không phải app thứ hai user thấy.
- **Không gộp codebase, không nhúng iframe.** (Đã phân tích: cô lập pháp lý + tốc độ + SEO + reversibility.)
- CRM/app đầy đủ = **xây DẦN sau pilot**, không phải tuần này.

## D. Việc THẬT tuần này (demand-first — map đúng thứ tự)

**Mục tiêu tuần: có tín hiệu cầu thật, KHÔNG xây hệ thống.**

| # | Việc | Ghi chú |
|---|---|---|
| D1 | **Lập list 30 môi giới** Bình Thạnh 3-4 tỷ (tracker + sourcing đã có) | Ngày 0 |
| D2 | **Nhắn tay 10-15/ngày** bằng script + hook Deal-Radar; onboard concierge | Ngày 1-7 |
| D3 | **Kênh test = group Zalo private** (zca-js tài khoản burner): nhận filter → gửi Deal-Radar alert **+ link** | Thin slice; đọc-thôi, KHÔNG auto lấy SĐT, KHÔNG kho tập trung |
| D4 | **Wire tối thiểu:** automation/Deal-Radar (đã có) → đẩy tin khớp vào group Zalo | Không build app/CRM/mobile |
| D5 | **Đo retention tuần 2** (chỉ số vàng) + số match + "sẽ trả tiền?" | Vào tracker CSV |
| D6 | *(song song, không chặn)* gửi **3 câu hỏi luật sư** | Chạy nền |

**KHÔNG làm tuần này (cố ý hoãn):** re-architect toàn hệ thống · mobile app · full CRM · thu phí · tích hợp licensed-API · gỡ/viết lại crawler. Tất cả **gated sau khi pilot xanh**.

## E. Cổng quyết định (cuối tuần 2)
- **Pilot XANH** (≥10 môi giới quay lại tuần 2 + ≥2 match + ≥3 nói sẽ trả tiền) → **MỚI** bắt đầu: re-architect *incremental* (chỉ phần cần), tính mobile/CRM/licensed-data, thu phí dần.
- **Pilot ĐỎ** → chỉnh hook/ngách, chạy lại 1 vòng. **Chưa xây gì lớn.**

## Tóm tắt một dòng
**Hướng đã chốt: bdsai.vn (sàn BĐS + AI), Nowing = engine sau lưng, nhân vertical sau, freemium. Nhưng ĐẢO THỨ TỰ: tuần này KHÔNG re-architect / không xây web+mobile — mà chạy pilot kéo 30 môi giới qua group Zalo test, đo retention tuần 2. Chỉ khi pilot xanh mới re-architect dần và xây app/CRM. Cầu trước, xây sau.**
