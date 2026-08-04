# Task list — 2 tuần (bdsai pilot BĐS)

## Ngày 0 — Chuẩn bị
- [ ] Chốt hook Deal-Radar + 3 biến thể (đã có)
- [ ] Quay demo 60s "AI Deal-Radar"
- [ ] Import tracker CSV vào Google Sheets
- [ ] Lập danh sách ≥30 môi giới Bình Thạnh 3-4 tỷ (FB group / Chợ Tốt / Zalo / TikTok)
- [ ] Tạo tài khoản Zalo burner + group Zalo private cho pilot
- [ ] Viết/chạy script zca-js: gửi tin vào group Zalo (test gửi 1 tin)
- [ ] Gắn 5 sự kiện đo: signup, tool_used, filter_created, alert_sent, return

## Tuần 1 (Ngày 1-7) — Tuyển + kích hoạt
- [ ] Ngày 1: nhắn 10-15 môi giới (script mở đầu) → mục tiêu 3-5 rep
- [ ] Ngày 2: onboard người rep vào group + tạo Deal-Radar filter đầu cho họ; nhắn 10-15 người mới
- [ ] Ngày 3: follow-up người chưa rep; phỏng vấn nhanh 2-3 người đã dùng
- [ ] Ngày 4: vá 1-2 điểm ma sát onboarding; tiếp tục nhắn
- [ ] Ngày 5: bật seed aggregator (tóm tắt facts + nguồn + link) để group có tin khớp gửi vào
- [ ] Ngày 6: chạm mốc 30 người thử; ghi ai kích hoạt
- [ ] Ngày 7: review tuần 1 — đếm kích hoạt (mục tiêu 15-20), 3 phỏng vấn sâu

## Tuần 2 (Ngày 8-14) — Retention + match + tín hiệu giá
- [ ] Ngày 8: nhắn từng người tuần 1 một lý do cụ thể để quay lại
- [ ] Ngày 9: gửi ≥1 match thật vào group (Deal-Radar → alert + link)
- [ ] Ngày 10: hỏi 5 môi giới "sẽ trả tiền không?" (chỉ hỏi, chưa thu)
- [ ] Ngày 11: vá điểm ma sát retention; tạo thêm 1 match
- [ ] Ngày 12: nhờ 2-3 người hài lòng giới thiệu 1 đồng nghiệp
- [ ] Ngày 13: tổng hợp số (retention tuần 2, match, WTP) vào tracker
- [ ] Ngày 14: GATE go/no-go + viết retro 1 trang

## Wire kỹ thuật tối thiểu (trong Ngày 0-5, không hơn)
- [ ] Deal-Radar automation nhận filter mô tả bằng lời (verify đã chạy)
- [ ] Aggregator: schema chỉ facts (giá/diện tích/quận), badge nguồn + link, KHÔNG SĐT, KHÔNG rehost ảnh
- [ ] Kết nối: filter (Zalo) → Deal-Radar → alert + link → gửi vào group Zalo
- [ ] Matching cơ bản: người mua đăng nhu cầu → gợi ý tin khớp (aggregated + first-party)

## Song song (không chặn pilot)
- [ ] Gửi 3 câu hỏi cho luật sư: dùng code crawler kế thừa thương mại · ToS/robots 3 sàn khi aggregate · PDPD khi lưu tin trong workspace
- [ ] Hỏi thử 1-2 portal về licensed feed / đối tác referral

## KHÔNG làm 2 tuần này (guardrail)
- [ ] ❌ Re-architect toàn bộ hệ thống
- [ ] ❌ Mobile app / full CRM
- [ ] ❌ Thu phí
- [ ] ❌ Tài khoản ảo / đóng vai môi giới / scrape-viết-lại-giấu-nguồn
- [ ] ❌ Auto lấy số điện thoại / kho PII tập trung

## Cổng Ngày 14
- [ ] GO nếu: ≥10 quay lại tuần 2 + ≥2 match thật + ≥3 nói sẽ trả tiền
- [ ] Không đạt → chỉnh hook/ngách, chạy lại 1 vòng (chưa xây gì lớn)
