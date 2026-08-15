# SPRINT CHANGE PROPOSAL: HỢP NHẤT TOÀN DIỆN NEW CHAT VÀ LEADS MATRIX THÀNH SINGLE ORIGAMI CANVAS

**Mã đề xuất:** SCP-2026-08-16-ORIGAMI-UNIFIED-CANVAS  
**Ngày lập:** 2026-08-16  
**Dự án:** Nowing (Origami Vietnam Edition)  
**Phân loại mức độ ảnh hưởng:** **Moderate (Tái cấu trúc giao diện & Điều hướng không gian làm việc)**  
**Trạng thái đề xuất:** 🟢 ĐÃ ĐỒNG THUẬN (Hội đồng BMad: Sally, Mary, Winston, Amelia)

---

## 1. TỔNG QUAN VẤN ĐỀ (ISSUE SUMMARY)

### 1.1 Vấn đề phát sinh & Bối cảnh kích hoạt
Trong quá trình nghiệm thu Story 21.15 và 21.16, Founder Luis phát hiện giao diện Nowing bị chia tách thành 2 trang độc lập:
1. **Trang `/new-chat`:** Chạy full Assistant-UI engine (chọn model Claude/GPT, đính kèm file RAG, SSE streaming, @doc mention), nhưng không hiển thị bảng Leads Matrix.
2. **Trang `/leads`:** Cung cấp Split Canvas và Live Data Matrix, nhưng cột chat bên trái lại là một component tự chế sơ khai (`OrigamiChatCopilot`), thiếu hoàn toàn chọn model, không có upload file, không kết nối RAG.

### 1.2 Hậu quả nếu không điều chỉnh
- **Gãy vụn trải nghiệm người dùng (UX Friction):** Người dùng bị "lú lẫn" giữa 2 khung chat, không thể vừa đính kèm file hồ sơ năng lực vừa ra lệnh cào dữ liệu sống và hiển thị bảng.
- **Đi sai bản chất Origami:** Origami.chat chỉ có **MỘT KHÔNG GIAN LÀM VIỆC DUY NHẤT (Single Surface)**.
- **Tồn dư Technical Debt:** Duy trì 2 logic chat gây lãng phí tài nguyên và khó bảo trì.

---

## 2. PHÂN TÍCH TÁC ĐỘNG TOÀN DIỆN (IMPACT ANALYSIS)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            MA TRẬN ĐÁNH GIÁ TÁC ĐỘNG CÁC ARTIFACTS                               │
├───────────────────────┬───────────────────────────┬──────────────────────────────────────────────┤
│ TÀI LIỆU ARTIFACT     │ MỨC ĐỘ ẢNH HƯỞNG          │ NỘI DUNG THAY ĐỔI CỤ THỂ                     │
├───────────────────────┼───────────────────────────┼──────────────────────────────────────────────┤
│ 1. PRD (epics.md FRs) │ Nhẹ (Scope Refinement)    │ Khẳng định Nowing là Single Unified Workspace│
│                       │                           │ ("Prompt-to-Matrix" trên 1 màn hình).        │
├───────────────────────┼───────────────────────────┼──────────────────────────────────────────────┤
│ 2. Story 21.16        │ Trung bình (Refactor UI)  │ Chuyển target từ /leads sang /new-chat,      │
│                       │                           │ nhúng Full Assistant-UI Thread vào Canvas.   │
├───────────────────────┼───────────────────────────┼──────────────────────────────────────────────┤
│ 3. Architecture Spine │ Nhẹ (State Integration)   │ Áp dụng Jotai Atoms + URL Search Params      │
│                       │                           │ theo Winston Blueprint (INV-01 đến INV-06).  │
├───────────────────────┼───────────────────────────┼──────────────────────────────────────────────┤
│ 4. UX Design Tokens   │ Không đổi (Preserved)     │ Giữ nguyên Mint Green #10B981, Sọc Caro      │
│                       │                           │ Grid Paper, 3-Mode Switcher, Action Pills.   │
├───────────────────────┼───────────────────────────┼──────────────────────────────────────────────┤
│ 5. Frontend Codebase  │ Trung bình (5 Files)      │ Refactor OrigamiSplitCanvas, xóa ChatCopilot,│
│                       │                           │ nâng cấp new-chat page, redirect /leads.     │
└───────────────────────┴───────────────────────────┴──────────────────────────────────────────────┘
```

---

## 3. ĐỀ XUẤT ĐIỀU CHỈNH CỤ THỂ (DETAILED EDIT PROPOSALS)

### 3.1. Cập nhật Story 21.16: Origami Split-View Canvas & Workspace Modernization

```diff
# Story 21.16: Origami Split-View Canvas & Workspace Modernization
- Location: nowing_web/app/dashboard/[workspace_id]/leads/page.tsx
+ Location: nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx (Single Unified Entrypoint)

Acceptance Criteria Update:
- AC-1: Giao diện Split Canvas tích hợp trực tiếp Full Assistant-UI Thread Engine ở Panel Trái (hỗ trợ chọn Model, Đính kèm file, @doc mention, Suggested Action Pills).
- AC-2: Panel Phải là Dynamic Matrix (Live Leads Table, Sọc Caro Grid, Zero-cache sub-100ms, Multi-table Tabs, Floating Bulk Actions, Flyout Detail Drawer).
- AC-3: Route `/dashboard/[workspace_id]/leads` thực hiện server redirect về `/dashboard/[workspace_id]/new-chat?mode=leads`.
- AC-4: Bi-directional Context Bridge: Click chọn lead bên Matrix -> Chat Composer lập tức ghim badge context `[Đang chọn: <Tên Lead>]`.
```

---

## 4. KẾ HOẠCH BÀN GIAO TRIỂN KHAI CHO DEV (IMPLEMENTATION HANDOFF)

### Danh sách file cần sửa đổi & tạo mới:

| STT | File Path | Hành động | Mục đích |
| :--- | :--- | :--- | :--- |
| 1 | `nowing_web/components/leads/OrigamiSplitCanvas.tsx` | **MODIFY** | Nhận `chatSlot: React.ReactNode` động thay vì fix cứng chat giả. |
| 2 | `nowing_web/components/leads/OrigamiChatCopilot.tsx` | **DELETE** | Xóa bỏ file chat giả (Technical Debt). |
| 3 | `nowing_web/components/assistant-ui/thread.tsx` | **MODIFY** | Thêm `LeadContextBadge` và gắn metadata lead khi người dùng chọn row. |
| 4 | `nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx` | **MODIFY** | Bọc toàn bộ trang New Chat bên trong `OrigamiSplitCanvas` 50/50. |
| 5 | `nowing_web/app/dashboard/[workspace_id]/leads/page.tsx` | **MODIFY** | Thêm Next.js `redirect()` chuyển hướng sạch về `/new-chat?mode=leads`. |
| 6 | `nowing_web/components/sidebar/LayoutDataProvider.tsx` | **MODIFY** | Đổi tên điểm chạm Sidebar thành `🌿 Origami Canvas` trỏ về `/new-chat`. |

---

## 5. TIÊU CHÍ NGHIỆM THU (SUCCESS CRITERIA)

1. ✅ Truy cập `/dashboard/1/new-chat`: Màn hình Split-View 50/50 xuất hiện ngay lập tức.
2. ✅ Panel Trái có đầy đủ Model Selector (Claude 3.5, GPT-4o...), nút đính kèm file, RAG chat, Action Pills.
3. ✅ Panel Phải là Bảng Leads Matrix với nền Sọc Caro, Multi-table tabs, và Zero-cache live updates.
4. ✅ Click chọn 1 lead ở bảng $\rightarrow$ Chat bên trái xuất hiện Context Badge của lead đó ngay lập tức.
5. ✅ Truy cập `/dashboard/1/leads` $\rightarrow$ Tự động chuyển hướng về `/dashboard/1/new-chat?mode=leads`.
6. ✅ `pnpm tsc --noEmit` & `pnpm exec biome check`: **0 errors**.
