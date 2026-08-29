# UX Spec — Mở rộng Right Dock toàn màn hình

## Context

Trong dashboard chat (`/dashboard/:workspace_id/new-chat/:chat_id`), panel bên phải là **Contextual Dock** (`ContextualDock.tsx`) với các tab: **Leads**, **Images**, **Media**, **Artifacts**. Dock hiện đang có kích thước mặc định:

- `dockWidthAtom = 840px` (`DEFAULT_DOCK_WIDTH`)
- `MIN_DOCK_WIDTH = 360px`
- `MAX_DOCK_WIDTH = window.innerWidth - leftWidth - 6 - 16`

Với bảng leads có nhiều cột (`FIT SCORE`, `TÊN DOANH NGHIỆP`, credit, export actions...), 840px vẫn chưa đủ rộng. User muốn xem toàn bộ nội dung bảng nhưng phải cuộn ngang hoặc kéo resizer từng pixel.

## Problem Statement

> Người dùng muốn xem toàn bộ nội dung right panel mà không bị cắt bớt, đặc biệt khi làm việc với bảng dữ liệu leads hoặc media gallery.

## Design Goal

Cho phép user **mở rộng right panel chiếm toàn bộ chiều rộng còn lại của viewport** (hoặc gần full màn hình), vẫn giữ khả năng thu nhỏ về trạng thái sidebar khi cần tập trung vào chat.

## Proposed Solution

### 1. Toggle "Expand / Collapse" trên header right panel

Thêm một nút toggle ở header của right panel (bên cạnh nút đóng X hiện tại):

- **Icon:** `PanelRightOpen` (expand) / `PanelRightClose` (collapse)
- **Tooltip:**
  - "Mở rộng panel" khi đang thu nhỏ
  - "Thu nhỏ panel" khi đang mở rộng
- **Behavior:**
  - Mở rộng: right panel chiếm toàn bộ chiều rộng của `DesktopWorkspaceRegion` trừ đi sidebar trái.
  - Thu nhỏ: về kích thước theo `PANEL_WIDTHS` hiện tại.

### 2. Kích thước mở rộng

Khi mở rộng:

```
width = viewportWidth - leftRailWidth - leftSidebarWidth - chatMainMinWidth
```

Hoặc đơn giản hơn:

```
width = min(100vw - 56px - 240px - 400px, 1200px)
```

Trong đó:
- `56px`: right rail
- `240px`: workspace sidebar / playground sidebar
- `400px`: main chat area tối thiểu

### 3. Trạng thái (state)

Thêm một Jotai atom mới:

```ts
// atoms/layout/dock.atom.ts
export const dockExpandedAtom = atom(false);
```

Atom này độc lập với `dockOpenAtom`, nhưng ưu tiên như sau:
- Nếu `dockOpenAtom = false` → dock ẩn hoàn toàn.
- Nếu `dockOpenAtom = true` và `dockExpandedAtom = true` → dock mở rộng full width.
- Nếu `dockOpenAtom = true` và `dockExpandedAtom = false` → dock theo `dockWidthAtom`.

### 4. Animation

Dùng `framer-motion` (`motion.aside`) đã có sẵn. Khi toggle expand:

- `width: PANEL_WIDTHS[effectiveTab] → expandedWidth`
- `x: 0`
- `opacity: 1`
- `transition: PANEL_SLIDE_TRANSITION`

Không làm mất focus hoặc reset scroll của nội dung panel.

### 5. Responsive behavior

- **Desktop (≥1024px):** cho phép expand/collapse.
- **Tablet (<1024px):** right panel chuyển thành drawer/modal chiếm toàn màn hình, nút expand không cần thiết.
- **Mobile:** panel hiển thị như bottom sheet, không áp dụng expand.

### 6. A11y

- Nút toggle có `aria-label` rõ ràng.
- Khi panel expand, cập nhật `aria-expanded="true"`.
- Giữ `Escape` để đóng panel hiện tại.
- Đảm bảo tab order hợp lý: nút toggle nằm trước nút close trong header.

## Interaction Flow

1. User click tab "Leads" → panel mở ở 420px.
2. User thấy bảng bị cắt → click icon mở rộng trên header.
3. Panel trượt mở rộng sang trái, main chat area thu hẹp lại tối thiểu.
4. User có thể xem toàn bộ cột leads, sort, export.
5. User click icon thu nhỏ hoặc `Escape` để trở về sidebar.

## Edge Cases

- Khi không có đủ không gian (viewport < 1024px), ẩn nút expand.
- Khi panel đang mở rộng và user chuyển tab, giữ nguyên trạng thái expand.
- Khi user reload trang, trạng thái expand có thể không persist (tùy decision); mặc định **không persist** để tránh layout bất ngờ.
- Nếu main chat có active call / stream, không tự động thu nhỏ panel.

## Files to Modify

- `nowing_web/features/dock/components/DockResizer.tsx`
- `nowing_web/features/dock/components/DockHeader.tsx`
- `nowing_web/features/dock/components/ContextualDock.tsx`
- `nowing_web/atoms/layout/dock.atom.ts`
- `nowing_web/features/dock/components/DockContent.tsx` (nếu cần table tận dụng full width)

## Success Metrics

- User có thể xem toàn bộ các cột trong lead table mà không cần cuộn ngang.
- Thời gian hoàn thành tác vụ xem/xuất leads giảm.
- Không có regression trên mobile/tablet layout.

## Mockup Text

Header right panel:

```
[Tab: Leads (12)]  [🔽 Mở rộng]  [✕ Đóng]
```

Tooltip: "Mở rộng panel / Thu nhỏ panel"

---

*Sally — UX Designer, 2026-08-28*
