# Kho Components Web (Component Inventory)

Tài liệu này liệt kê các nhóm components UI chính được sử dụng trong `nowing_web`.

## 1. UI Primitives (`components/ui`)
Dựa trên **Shadcn UI** và **Radix Primitives**. Các thành phần cơ bản này đảm bảo tính nhất quán về thiết kế và khả năng tiếp cận (accessibility).

- **Core**: `Button`, `Input`, `Select`, `Checkbox`, `Switch`.
- **Feedback**: `Toast` (thông báo), `Alert`, `Progress`, `Skeleton` (loading state).
- **Overlay**: `Dialog` (Modal), `Sheet` (Sidebar Drawer), `Popover`, `Tooltip`.
- **Layout**: `Card`, `Separator`, `ScrollArea`, `Resizable` (chia đôi màn hình).

## 2. Layout Components (`components/layout`)
Các thành phần cấu trúc dùng chung cho các trang.

- **`Sidebar`**: Menu điều hướng chính bên trái (collapsible).
- **`Header`**: Thanh trên cùng chứa User Menu, Theme Toggle, Breadcrumbs.
- **`UserNav`**: Dropdown menu tài khoản người dùng.
- **`ThemeToggle`**: Chuyển đổi Dark/Light mode.

## 3. Assistant UI (`components/assistant-ui`)
Các components chuyên biệt cho trải nghiệm AI Chat.

- **`ChatThread`**: Container chính quản lý danh sách tin nhắn.
- **`Composer`**: Khung nhập liệu thông minh (hỗ trợ slash commands, file attachment).
- **`MessageList`**: Hiển thị tin nhắn cuộn (scrollable).
- **`MessageBubble`**: Hiển thị nội dung tin nhắn (User/AI).
    - Hỗ trợ Markdown rendering.
    - Hỗ trợ hiển thị Code Block với syntax highlighting.
- **`ThreadHistory`**: Sidebar danh sách các cuộc hội thoại cũ.
- **`ToolResult`**: Hiển thị kết quả trả về từ tool (VD: Card thông tin thời tiết).

## 4. Feature Components
Các components đặc thù cho nghiệp vụ Nowing.

- **`DocumentCard`**: Hiển thị tóm tắt tài liệu trong danh sách tìm kiếm.
- **`ConnectorGrid`**: Lưới các icon ứng dụng để user kết nối (Gmail, Slack...).
- **`SearchFilters`**: Bộ lọc nâng cao cho tìm kiếm (theo ngày, loại file, nguồn).

## 5. Orchestra Components (`components/new-chat/orchestra`) — Story 9-FE-1

Multi-agent conductor strip hiển thị tiến trình phân tích theo thời gian thực.

- **`OrchestraStrip`** (`orchestra-strip.tsx`)
  - Entry point chính, đọc `activeOrchestraSessionAtom` từ Jotai.
  - Variant `default`: hiển thị danh sách `AgentRow` khi đang chạy.
  - Variant `collapsed`: tóm tắt "N/M done · Xms (bucket)" sau khi hoàn thành.
  - Variant `single-agent`: inline status không có border card.
  - Tích hợp `DegradationNotice` khi có agent thất bại.
  - `data-slot="orchestra-strip"`, `data-variant={variant}`.

- **`AgentRow`** (`agent-row.tsx`)
  - Hiển thị trạng thái từng agent: `queued` → `running` → `done` / `failed` / `cancelled`.
  - Icon: spinner (running), check (done), X (failed/cancelled), dot (queued).

- **`DegradationNotice`** (`degradation-notice.tsx`)
  - Amber `Alert` (`border-amber-500/50 bg-amber-50`) khi ≥1 agent thất bại.
  - Inline summary luôn hiển thị; expandable để xem từng agent thất bại.
  - Props: `failedAgents`, `successCount`, `totalCount`, `isComplete`, `sessionId`, `onRetry?`.
  - Analytics: `trackDegradationNoticeExpanded`, `trackDegradationRetryClicked`.

- **`ProgressMilestone`** (`progress-milestone.tsx`)
  - Hiển thị banner "Analysing in depth…" sau T+30s kể từ khi session spawn.
  - Dùng `useEffect` + `setTimeout` để set `milestone30sFired: true` trong atom.
  - Props: `sessionId`, `milestone?`, `milestone30sFired`, `elapsedMs`.

### Atoms
- **`orchestraStateAtom`** (`atoms/chat/orchestra.atom.ts`)
  - Jotai atom chứa `OrchestraState`: `sessions: Map<string, OrchestraSession>`, `activeQueryHash`.
  - `activeOrchestraSessionAtom`: derived atom trả về session đang active.
- **`applyOrchestraEvent(state, event): OrchestraState`** — pure reducer xử lý 6 SSE event types.
  - Event types: `orchestra-spawn`, `orchestra-update`, `orchestra-done`, `orchestra-fail`, `orchestra-cancel`, `orchestra-complete`.

### i18n Keys (`messages/en.json` → `orchestra.*`)
Namespace `orchestra` chứa 26 keys: strip titles, status labels, summary template, p95 bucket labels, milestone text, degradation strings, fail reason translations, cancelled footnote.
