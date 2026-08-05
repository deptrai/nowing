# UX Contract — First-Run Onboarding

**Ngày:** 2026-08-05
**Phạm vi:** UX cho first-run value: workspace mới cần seed memory/research run để `nowing_recall` không rỗng (FR-40, E3.13).
**Bám vào:** FR-40 · Story 3.13 · AD-18 (memory bounds)
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được.

---

## 1. Bài toán UX

Workspace mới không có memory → `nowing_recall` session đầu rỗng theo cấu trúc. User lần đầu chat sẽ nhận "I don't know" hoặc kết quả kém. Cần first-run flow tạo memory trong ≤15 phút.

Hệ quả UX:
- Onboarding không được bắt user điền form dài.
- Phải cho user thấy tiến trình seed memory (search, extract, save).

## 2. Contract — các trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| O1 | **Welcome screen** — giải thích workspace mới, gợi ý 3 chủ đề/topic để bắt đầu | ✅ |
| O2 | **Quick research run prompt** — user nhập 1 câu hỏi/ngành hoặc chọn gợi ý; hệ thống chạy research + auto-extract memory | ✅ |
| O3 | **Progress-first seeding** — hiển thị "Đang tìm kiến thức cơ bản cho workspace…" với phase (search → extract → save) | ✅ |
| O4 | **Memory seed complete** — hiển thị số memory đã tạo và gợi ý câu hỏi tiếp theo | ✅ |
| O5 | **Skip option** — user có thể skip seeding, nhưng hiển thị warning "Workspace chưa có memory, chat sẽ kém hơn" | ✅ |
| O6 | **M1 gate** — nếu seeding không hoàn thành trong ≤15 phút, hiển thị "Đang chậm hơn dự kiến, bạn có thể tiếp tục dùng hoặc thử lại" | ✅ |

## 3. Ràng buộc kỹ thuật UX

- Dùng `MemoryExtractionService.extract_from_turn` sau khi research run hoàn thành.
- `AD-18` đảm bảo memory injection có bound để first-run chat không chậm.
- Phải hoạt động cả self-host (không engine) với degradation sang hybrid search nội bộ.

## 4. Truy vết

- Chặn: story 3.13 (FR-40)
- Phụ thuộc: E3.14 (memory bounds), 9.1a (degradation)
