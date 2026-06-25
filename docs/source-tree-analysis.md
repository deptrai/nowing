# Báo Cáo Source Tree (Monorepo)

## 1. Cấu trúc Root (Monorepo)
Dự án Nowing sử dụng mô hình Monorepo (quản lý ở cấp độ thư mục gốc) chứa tất cả Client và Backend, giúp dễ dàng chia sẻ Scripts và Docker Configurations. Cấu trúc gồm 4 cột trụ chính và các files bổ trợ:

```text
Nowing/
├── .agent/              # Cấu hình BMad Framework (Agent settings, prompts)
├── .github/             # GitHub Actions CI/CD workflows
├── _bmad/               # Dữ liệu phục vụ BMAD chạy nội bộ
├── _bmad-output/        # Nơi lưu kết quả, sprints, architect docs của BMAD
├── docker/              # Nơi chứa config deploy Docker & Compose
├── docs/                # [Mục lục này] Output docs đã generate/review
├── scripts/             # Bash scripts để setup, format, chạy tools cục bộ
├── nowing_backend/   # Core FastAPI, Python Codebase
├── nowing_browser_extension/ # Extension build folder
├── nowing_desktop/   # Native Web-wrappers Desktop / Electron-Tauri
└── nowing_web/       # Next.js Web App Core
```

## 2. Chi Tiết Từng Phân Hệ Core

### 2.1 Backend (`nowing_backend`)
Bao gồm App FastAPI có cấu trúc Layered Architecture cổ điển. Python version yêu cầu 3.12+. Dependency được quản lý qua `poetry` hoặc `requirements.txt`. (Chi tiết tại `architecture-backend.md`).

### 2.2 Frontend Web (`nowing_web`)
Bao gồm một lượng lớn UI/UX logic bằng NextJS 16 App Router. Đi kèm với nó là Setup Shadcn UI tĩnh. (Chi tiết tại `architecture-web.md`).

### 2.3 Phân hệ Setup Nội Bộ
- `.secrets.baseline`: Công cụ phát hiện secret rò rỉ (Yelp detect-secrets).
- `.pre-commit-config.yaml`: Các pre-commit hooks khi lập trình viên submit code (biome, ruff...).
- `biome.json`: Sử dụng BiomeJS làm Formatter / Linter chính thay thế cho Prettier/ESLint cho Frontend nhằm đem lại hiệu năng vượt trội.
