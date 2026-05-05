# Test E2E Browser - Validation Checklist

## Chuẩn bị
- [ ] Xác định rõ luồng hoặc tính năng cần test.
- [ ] Xây dựng Test Plan (các bước tuần tự) chi tiết và hiển thị cho người dùng.
- [ ] Kiểm tra môi trường test (ứng dụng đã chạy và có thể truy cập qua URL local).

## Thực thi Test (Browser Subagent)
- [ ] Khởi chạy `browser_subagent` thành công.
- [ ] Prompt được truyền vào `browser_subagent` chi tiết, đầy đủ hướng dẫn thực thi từ Test Plan.
- [ ] Browser Subagent tương tác được với giao diện, nhập liệu và điều hướng đúng như dự kiến.
- [ ] Đã nhận được báo cáo phản hồi từ Browser Subagent.

## Báo cáo & Kết quả
- [ ] Tạo báo cáo markdown tổng hợp kết quả (E2E Browser Test Report).
- [ ] Báo cáo ghi rõ trạng thái PASS / FAIL của từng luồng.
- [ ] (Nếu có) Ghi chú các lỗi (bug) phát hiện trong quá trình test và các gợi ý để fix bug.
- [ ] File báo cáo được lưu vào vị trí phù hợp (VD: `_bmad-output/qa-artifacts/`).

## Validation
Kết quả test phản ánh đúng hành vi của ứng dụng hiện tại trên browser.

**Expected**: Quá trình chạy browser mượt mà, báo cáo rõ ràng. ✅
