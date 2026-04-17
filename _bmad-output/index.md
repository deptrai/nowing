# Mục Lục Tài Liệu Tổng Hợp (Master Index)

Chào mừng đến với tài liệu kỹ thuật của Nowing. Đây là một nền tảng tìm kiếm và kiến thức AI đa thành phần.

## 🧭 Bắt Đầu
- **[Tổng Quan Dự Án](./project-overview.md)** - Tóm tắt cấp cao về hệ thống.
- **[Phân Tích Cây Mã Nguồn](./source-tree-analysis.md)** - Bản đồ các thư mục và tệp tin.
- **[Kiến Trúc Tích Hợp](./integration-architecture.md)** - Cách các thành phần giao tiếp với nhau.

## 📚 Hướng Dẫn Sử Dụng
- **[Hướng Dẫn Người Dùng](./user-guide.md)** - Cài đặt, sử dụng tính năng, troubleshooting.
- **[Hướng Dẫn Quản Trị](./admin-guide.md)** - Quản lý users, cấu hình hệ thống, monitoring.
- **[Hướng Dẫn Developer](./developer-guide.md)** - Setup môi trường, API reference, deployment.

## 🏗️ Tài Liệu Thành Phần

### 🐍 Backend (`nowing_backend`)
Bộ não của hệ thống. Python/FastAPI microservice.
- **[Kiến Trúc](./architecture-backend.md)** - DeepAgents, LangGraph, và RAG.
- **[Hợp Đồng API](./api-contracts-backend.md)** - Các REST Endpoints và Auth.
- **[Mô Hình Dữ Liệu](./data-models-backend.md)** - Database Schema & Thực thể.

### 💻 Web Dashboard (`nowing_web`)
Giao diện người dùng. Next.js 16 Web App.
- **[Kiến Trúc](./architecture-web.md)** - App Router, Server Actions, ElectricSQL.
- **[Inventory Component](./component-inventory-web.md)** - Phân tích thư viện UI.

### 🧩 Browser Extension (`nowing_browser_extension`)
Bộ thu thập dữ liệu. Plasmo/React Extension.
- **[Kiến Trúc](./architecture-extension.md)** - Popup, Background Services, Manifest V3.

## 📊 Báo Cáo
- **[Báo Cáo Quét Dự Án](./project-scan-report.json)** - Dữ liệu quét dạng máy đọc (machine-readable).
