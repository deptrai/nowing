---
status: blocked
---

# BMad Build Auto Result

Status: blocked
Blocking condition: version-control metadata not writable — dirty working tree

## Chi tiết

Working tree có 1 file đã modified:
- `nowing_web/tests/leads/lead-orchestrator.spec.ts` — fix brittle selectors từ phiên trước

Intent: "fix hết đi" — sửa tất cả lỗi dữ liệu lead đã phát hiện trong kiểm tra chất lượng:
1. Batdongsan: company_name bị gán bằng tiêu đề tin rao vặt thay vì tên công ty/môi giới
2. Batdongsan: thiếu trích xuất phone từ trường title (ví dụ: "LH 0973668873 Mr. Dương")
3. Batdongsan: source_url = None cho 100% leads mới
4. Location mismatch: leads từ TP.HCM/Đà Nẵng lọt vào khi yêu cầu "tại Hà Nội"
5. Industry = None cho 100% leads (38/38)
6. Domain = None cho 92% leads (35/38)

### Hành động cần thiết trước khi chạy lại
Commit hoặc stash thay đổi hiện tại trong working tree, sau đó chạy lại workflow.
