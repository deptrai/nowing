# Story 24.4: Nowing Lead Clipper — Chrome Extension for 1-Click Lead Capturing

Status: `ready-for-dev`
Epic: `epic-24`

## Story Overview

As a growth hacker, sourcer, or real estate broker browsing the web,
I want a lightweight Chrome Extension (Manifest V3) that detects listings and profiles on Facebook Groups, LinkedIn, Batdongsan, and TopCV with a 1-click "Clip to Nowing" action,
So that I can capture leads into my active Nowing Workspace without copy-pasting or switching tabs.

---

## Architectural Invariants
- **INV-24.5 (Clipper Extension Cryptographic Token):** Giao tiếp qua Personal Access Token (PAT) với scope `leads:write` và workspace-scoped CORS validation.
- **Client Sandbox:** Manifest V3 Content Script chạy trong isolated sandbox, không lưu trữ token người dùng ở storage không bảo mật.

---

## Acceptance Criteria

1. **Chrome Extension (Manifest V3):**
   - Đăng nhập 1-click bằng API Key / Personal Access Token của Nowing Workspace.
   - Hiển thị Workspace Selector để chọn đích lưu dữ liệu.
2. **Context-Aware Web Extractors:**
   - **Facebook Groups:** Trích xuất tên tác giả bài viết, link trang cá nhân, SĐT/Zalo trong bài, nội dung tóm tắt.
   - **Batdongsan / Chợ Tốt:** Trích xuất tiêu đề, giá, diện tích, quận/huyện, số điện thoại người bán.
   - **TopCV / LinkedIn:** Trích xuất chức danh, công ty, địa điểm, kỹ năng, thông tin liên hệ.
3. **Instant 1-Click Floating Button:**
   - Khi lướt qua một tin đăng/bài viết, hiện nút nổi `⚡ Clip to Nowing`.
   - Bấm nút ➔ Bắn REST payload tới `POST /api/v1/workspaces/{id}/leads/clip` ➔ Đẩy vào bảng Nowing trong < 500ms kèm hiệu ứng Toast báo thành công.

---

## Technical Tasks
- [ ] Extension Package: Khởi tạo project `apps/chrome-extension` (Manifest V3, Vite + React + Tailwind).
- [ ] Content Scripts: Xây dựng các extractor module cho Facebook Group, Batdongsan, TopCV.
- [ ] Backend: Endpoint `POST /api/v1/workspaces/{id}/leads/clip` xác thực PAT và ghi trực tiếp vào `leads`.
- [ ] E2E & Browser Tests: Test extension popup, test trích xuất DOM và đồng bộ về backend.
