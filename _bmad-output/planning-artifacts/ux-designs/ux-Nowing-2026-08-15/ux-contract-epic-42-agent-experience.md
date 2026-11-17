# UX Contract — Epic 42: Agent Experience & Lead Pipeline Hardening

Ngày: 2026-11-16 · Nguồn: `ux-plan-agent-experience-improvements-2026-11-16.md` (v4, Sally review + party-room). Personas: P1 external agent (API consumer), P2 internal agent (chat), P3 human operator.

## Bối cảnh bằng chứng

- Hermes agent mất **46 browser calls** để tìm trang leads (`/leads` 404 → `/tables` thiếu → `/leads/pipeline` sai → `new-chat?mode=leads`).
- dryRun stub nhìn y hệt success → agent báo "không có lead" khi kênh chết.
- `save_leads` trả `table_id=NULL` → 109 lead không hiển thị trên canvas.
- Turn 21 phút, 54 tool calls, bị step-cap → `text=0` — mất toàn bộ output.
- HITL approve → turn chết (Gemini functionResponse mismatch); regenerate trên thread crash → 400.

## UX-DR-42.1 — Real route `/dashboard/{id}/leads`

Trang leads là **route thật** (không alias vào `new-chat?mode=leads`): URL riêng, shareable, deep-link tới một table cụ thể (`?table=<id>`). Mode switcher 🎯 Leads và nav item cùng trỏ về route này. `new-chat?mode=leads` giữ hoạt động (redirect sang route mới, không 404 link cũ).

## UX-DR-42.2 — Status visibility: kết quả phải phân biệt 3 trạng thái

Mọi tool/scrape result hiển thị badge phân biệt:
- `empty_result` — kênh sống, không có data (vd: không ai bán trầm trên batdongsan).
- `degraded` — trả về được một phần (kèm `degraded_sources` list).
- `failed` — kênh chết, kèm **recovery hint** (credential nào cần, ở đâu set, lệnh retest) — MEDIRUS_4010 → "cần cookie c_user/xs trong Medirus/.env"; MEDIRUS_4030 → "bot challenge, cần proxy".

Không bao giờ render `data:[]` như "0 lead" — phải render "kênh X lỗi, cần Y".

## UX-DR-42.3 — Step-cap partial synthesis

Khi turn chạm cap: agent buộc tổng hợp kết quả đã có thành partial answer + banner `partial: true` ("Đã xử lý 3/5 video — gửi 'tiếp tục' để hoàn thành"). Không bao giờ kết thúc turn với `text=0`.

## UX-DR-42.4 — HITL recovery path

Approve → turn chết là lỗi (C1 fix). Regenerate trên thread bị crash giữa chừng: thay vì `400 No conversation history`, offer action "Gửi như tin nhắn mới" — dead end nào cũng phải có đường thoát.

## UX-DR-42.5 — Leads empty state

Khi bảng trống: empty state dạy cách săn lead ("Chưa có lead — bắt đầu bằng câu mô tả khách hàng trong chat", ví dụ query mẫu). Leads từ mọi nguồn (chat, API, MCP) tự gắn table — không có khái niệm "lead vô chủ".

## UX-DR-42.6 — External agent = service consumer

P1 (external agent như Hermes) không đi qua UI — họ cần: `POST /leads/batch-ingest` (PAT `leads:write`), `GET /scrapers/health`, `nowing_mcp` tools. UX của P1 = contract + error hint, không phải trang web. Response format dùng chung `ToolResultEnvelope` (AD-42-3).

## Non-goals UX

- Không đổi token/màu/layout hiện có (DESIGN.md Origami system giữ nguyên).
- Không làm credential onboarding UI trong epic này (ghi nhận là highest-friction journey point — đề xuất epic sau: form paste `c_user`/`xs` + test button).
