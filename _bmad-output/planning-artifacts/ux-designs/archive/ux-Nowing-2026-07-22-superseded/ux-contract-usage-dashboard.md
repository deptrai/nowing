# UX Contract — Usage & Credit Dashboard

**Ngày:** 2026-08-05
**Phạm vi:** UX cho dashboard usage/credit theo workspace (FR-31, NFR-7) + workspace limits (8.12).
**Bám vào:** FR-31 · NFR-7 · Story 8.3 · Story 8.12
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được.

---

## 1. Bài toán UX

Người dùng cần hiểu mình tiêu gì, còn bao nhiêu credit, và khi nào bị chặn bởi workspace limits.

Hệ quả UX:
- Dashboard cần hiển thị số có nguồn gốc rõ ràng (model, capability, deep-research mode).
- Workspace limits cần hiển thị current usage vs limit và upgrade CTA.

## 2. Contract — các trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| U1 | **Credit balance** — credit_micros còn lại theo workspace | ✅ |
| U2 | **Usage by time** — bar/line chart theo ngày/tuần/tháng | ✅ |
| U3 | **Usage by model/capability** — phân bổ cost theo model và capability (chat, deep-research, scraper, image, etc.) | ✅ |
| U4 | **Deep-research cost** — cost thật từ `costDollars` theo mode (speed/balanced/quality/auto), không phẳng | ✅ |
| U5 | **Workspace limits card** — documents, members, storage, runs: current / limit với progress bar | ✅ |
| U6 | **Limit exceeded state** — block message + upgrade CTA khi vượt limit | ✅ |
| U7 | **Anonymous/self-host defaults** — hiển thị unlimited hoặc local-only tùy môi trường | ✅ |

## 3. Ràng buộc kỹ thuật UX

- Dữ liệu từ `TokenUsage`/`credit_micros_balance` đã có.
- Deep-research cost lấy từ `costDollars` parse (FR-37, story 9.2) — đến khi 9.2 xong, dashboard có thể hiển thị fallback với warning.
- Limits enforced backend-side, UI là reflection.

## 4. Truy vết

- Chặn: story 8.3 (done), story 8.12 (ready-for-dev)
- Phụ thuộc: FR-37 (cost thật), AD-8 (billing unit mapping)
