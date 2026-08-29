# File Mapping & Architecture Changes: Upstream Sync

Tài liệu này mô tả chi tiết danh sách các tệp thay đổi từ upstream `SurfSense` và vị trí tương ứng trong `Nowing`.

## 1. Backend: Scrapers & Platforms (`nowing_backend/app/proprietary/platforms/`)

| Thành phần | Upstream Path (`surfsense_*`) | Nowing Path (`nowing_*`) | Hành động |
| :--- | :--- | :--- | :--- |
| **Walmart Scraper** | `surfsense_backend/app/proprietary/platforms/walmart/` | `nowing_backend/app/proprietary/platforms/walmart/` | Nâng cấp `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, `url_resolver.py` |
| **Walmart Capabilities** | `surfsense_backend/app/capabilities/walmart/` | `nowing_backend/app/capabilities/walmart/` | Bổ sung capabilities `reviews/` và `scrape/` |
| **Indeed Scraper** | `surfsense_backend/app/proprietary/platforms/indeed_jobs/` | `nowing_backend/app/proprietary/platforms/indeed/` | Cập nhật `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, `url_resolver.py` |
| **Indeed Capabilities** | `surfsense_backend/app/capabilities/indeed/` | `nowing_backend/app/capabilities/indeed/` | Cập nhật `scrape/` executor và schemas |
| **Reddit Scraper** | `surfsense_backend/app/proprietary/platforms/reddit/` | `nowing_backend/app/proprietary/platforms/reddit/` | Thêm hỗ trợ `community-only` cào không cần `search_queries` |
| **Browser Loop Manager** | `surfsense_backend/app/proprietary/platforms/crawler/` | `nowing_backend/app/proprietary/platforms/crawler/` | Tối ưu hóa vòng đời lifecycle headless browser pool |

---

## 2. MCP Server (`nowing_mcp/`)

| Thành phần | Upstream Path | Nowing Path | Hành động |
| :--- | :--- | :--- | :--- |
| **Walmart Tool** | `surfsense_mcp/mcp_server/features/scrapers/platforms/walmart.py` | `nowing_mcp/mcp_server/features/scrapers/platforms/walmart.py` | Cập nhật định nghĩa tool và review parameters |
| **Indeed Tool** | `surfsense_mcp/mcp_server/features/scrapers/platforms/indeed.py` | `nowing_mcp/mcp_server/features/scrapers/platforms/indeed.py` | Cập nhật định nghĩa tool |
| **Reddit Tool** | `surfsense_mcp/mcp_server/features/scrapers/platforms/reddit.py` | `nowing_mcp/mcp_server/features/scrapers/platforms/reddit.py` | Cho phép optional query khi có community |

---

## 3. Frontend & Chat UI (`nowing_web/`)

| Thành phần | Upstream Path | Nowing Path | Hành động |
| :--- | :--- | :--- | :--- |
| **Timeline Indicator Component** | `surfsense_web/components/ui/timeline-activity-indicator.tsx` | `nowing_web/components/ui/timeline-activity-indicator.tsx` | Tạo mới component activity indicator |
| **Timeline Styles** | `surfsense_web/app/globals.css` | `nowing_web/app/globals.css` | Thêm CSS keyframes và styles cho timeline indicator |
| **Reasoning Auto-scroll** | `surfsense_web/features/chat-messages/` | `nowing_web/features/chat-messages/` | Cải tiến scroll container cho thinking steps |
| **Activity Journal** | `surfsense_web/lib/chat/activity-journal.ts` | `nowing_web/lib/chat/activity-journal.ts` | Quản lý state activity client-side mượt mà |
