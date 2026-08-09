# UX Contract — Private Data Provider (`NowingPrivateProvider`)

**Ngày:** 2026-08-08  
**Phạm vi:** UX cho chat/agent khi `chainlens-research` gọi Nowing để lấy private workspace data (`POST /v1/private-data/search`) và merge vào kết quả public.  
**Bám vào:** FR-60, AD-15, AD-35.  
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được, không định layout/màu.

---

## 1. Bài toán UX

Private data (documents, OAuth connectors, workspace memory) phải ở lại Nowing theo AD-15/AD-35. Nhưng agent cần kết hợp private + public data để trả lời câu hỏi cross-corpus (ví dụ: "so sánh giá căn hộ Thủ Đức trong tài liệu của tôi với thị trường").

Hệ quả UX:
- User cần biết khi nào câu trả lời dùng private data.
- User cần đảm bảo data không bị leak ra ngoài workspace.
- Citation private phải dẫn về đúng document/connector chunk.
- `chainlens-research` không lưu private chunks; chỉ dùng để rerank trong phiên đó.

---

## 2. Contract — các trạng thái UI bắt buộc

### 2A. Privacy & Trust Indicators

| # | Trạng thái | Bắt buộc |
|---|---|---|
| A1 | **Private data badge** — Citation từ private source có badge `private` hoặc workspace icon | ✅ |
| A2 | **Visibility note** — Tooltip/text "This result uses your private workspace data and is not stored by the research engine" | ✅ |
| A3 | **No cross-workspace leak** — UI không hiển thị private data của workspace khác; nếu có lỗi RBAC, hiển thị "Access denied" thay vì data | ✅ |
| A4 | **Private source list** — Drawer "Private sources" liệt kê documents/connectors đã dùng (chỉ tên, không nội dung full) | 🟡 optional |

### 2B. Citation Behavior

| # | Trạng thái | Bắt buộc |
|---|---|---|
| B1 | **Click private citation** — Mở document detail / chunk panel (nếu user có quyền view) | ✅ |
| B2 | **No public URL** — Private citation không có external link; hover chỉ hiển thị workspace source name | ✅ |
| B3 | **Grouped by source** — Nhiều chunks từ cùng document được group dưới 1 citation badge với số lượng | 🟡 optional |

### 2C. Query Scope Control

| # | Trạng thái | Bắt buộc |
|---|---|---|
| C1 | **Scope toggle** — Chat input có toggle/checkbox "Include my workspace data" (default ON nếu user có private data) | ✅ |
| C2 | **Scope hint** — Khi OFF, agent chỉ dùng public `chainlens-research` index | ✅ |
| C3 | **Scope mismatch feedback** — Nếu user hỏi về private doc nhưng scope OFF, agent nhắc bật | 🟡 optional |

### 2D. Error / Empty States

| # | Trạng thái | Bắt buộc |
|---|---|---|
| D1 | **No permission** — Khi `POST /v1/private-data/search` trả 403, hiển thị "You don't have access to some requested data" | ✅ |
| D2 | **Private provider timeout** — Timeout không block public results; hiển thị banner "Private data unavailable; showing public results only" | ✅ |
| D3 | **Empty private results** — "No matching private documents. Results are from public web only" | ✅ |

---

## 3. Ràng buộc kỹ thuật UX

- **Citation component** — Tái dùng `CitationBadge` với `variant="private"`; icon là `Lock` hoặc workspace icon.
- **RBAC filtering** — `NowingPrivateProvider` phải lọc theo workspace membership + document permissions; UI chỉ nhận kết quả đã lọc.
- **No preview leak** — Private source drawer chỉ hiển thị metadata (title, connector type, updated at), không preview nội dung chunk.
- **i18n** — Badge "private" localize.

---

## 4. User Flows

### Flow 1: Compare market price with private portfolio
1. User has a document "Danh sách BĐS đang xem".
2. User asks: "căn hộ Thủ Đức trong tài liệu của tôi đắt hơn thị trường không?"
3. Agent calls `chainlens-research` public search + `POST /v1/private-data/search`.
4. Agent response includes citations:
   - `[1] batdongsan.vn · public`
   - `[2] Danh sách BĐS đang xem · private`
5. Click `[2]` opens document detail.

### Flow 2: User disables private scope
1. User toggles OFF "Include my workspace data".
2. User asks: "căn hộ Thủ Đức giá bao nhiêu".
3. Agent only calls public `chainlens-research`.
4. Response does not include private citations.
5. Badge "Public results only" appears.

---

## 5. Truy vết

- Chặn: Epic 47 (chainlens-research), FR-60.
- Phụ thuộc: AD-15 (Nowing owns private data), AD-35 (no public corpus in Nowing).
- Reuses: `ux-contract-ecosystem-search` (citation pattern), `ux-contract-async-deep-research` (async state).

---

## 6. Open Questions

1. **Default scope** — Nên default ON hay OFF cho sensitive workspaces?
2. **Private data in shared thread** — Khi nhiều member cùng workspace, private data có hiển thị với mọi người trong thread không?
3. **Retention message** — Cần giải thích rõ "not stored by research engine" ở đâu?
