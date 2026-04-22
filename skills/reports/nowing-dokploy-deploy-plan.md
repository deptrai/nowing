---
title: 'Nowing — Dokploy Deployment Plan'
status: 'complete'
module_name: 'Nowing DevOps'
module_code: 'dops'
module_description: 'Deploy toàn bộ stack Nowing lên Dokploy sử dụng Docker Compose từ GHCR images'
architecture: 'compose-based deployment'
standalone: true
created: '2026-04-23'
updated: '2026-04-23'
---

# Nowing — Dokploy Deployment Plan

## Tổng quan hạ tầng

### Stack hiện tại (từ `docker/docker-compose.yml`)

| Service | Image | Port |
|---|---|---|
| `db` | `pgvector/pgvector:pg17` | 5432 |
| `redis` | `redis:8-alpine` | 6379 |
| `searxng` | `searxng/searxng:2026.3.13-3c1f68c59` | 8080 (internal) |
| `backend` | `ghcr.io/modsetter/nowing-backend:latest` | 8929→8000 |
| `celery_worker` | `ghcr.io/modsetter/nowing-backend:latest` | - |
| `celery_beat` | `ghcr.io/modsetter/nowing-backend:latest` | - |
| `zero-cache` | `rocicorp/zero:0.26.2` | 5929→4848 |
| `frontend` | `ghcr.io/modsetter/nowing-web:latest` | 3929→3000 |

### CI/CD Pipeline (`.github/workflows/docker-build.yml`)
- **Trigger**: push lên `main`/`dev` khi có thay đổi trong `nowing_backend/**` hoặc `nowing_web/**`
- **Registry**: `ghcr.io/modsetter/nowing-backend` và `ghcr.io/modsetter/nowing-web`
- **Tags**: `latest`, `{APP_VERSION}`, `{APP_VERSION}.{BUILD_NUMBER}`, `git-{SHA}`
- **Multi-arch**: `linux/amd64` + `linux/arm64`
- **Auto-update**: Watchtower labels đã có sẵn trên tất cả containers

---

## Phương án deploy trên Dokploy

### Khuyến nghị: Dùng **Compose** type trong Dokploy

Dokploy hỗ trợ deploy Docker Compose nguyên file. Đây là cách phù hợp nhất vì stack đã có sẵn `docker-compose.yml` hoàn chỉnh.

---

## Các bước thực hiện

### Bước 1: Tạo Project mới trong Dokploy

1. Vào Dokploy dashboard → **New Project**
2. Đặt tên: `nowing`
3. Tạo environment: `production`

### Bước 2: Tạo Compose Service

1. Trong project `nowing` → **Add Service** → **Compose**
2. **Source**: chọn **Git** (GitHub repo)
   - Repository: `modsetter/nowing`
   - Branch: `main`
   - Compose path: `docker/docker-compose.yml`
3. **Hoặc** dùng nguồn **Raw** — paste nội dung `docker/docker-compose.yml` trực tiếp

> ⚠️ **Lưu ý về GHCR**: Images `ghcr.io/modsetter/nowing-*` là **private**. Cần cấu hình Docker registry credentials trong Dokploy.

### Bước 3: Cấu hình Docker Registry (GHCR)

Trong Dokploy → **Registry** → **Add Registry**:
- Registry URL: `ghcr.io`
- Username: `modsetter` (hoặc GitHub username)
- Password: GitHub Personal Access Token với scope `read:packages`

### Bước 4: Cấu hình Environment Variables

Tạo file `.env` cho Compose service trong Dokploy. Các biến **bắt buộc**:

```env
# Database
DB_USER=nowing
DB_PASSWORD=<strong-password>
DB_NAME=nowing
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Backend
BACKEND_PORT=8929
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# Frontend
FRONTEND_PORT=3929
NEXT_PUBLIC_FASTAPI_BACKEND_URL=https://<your-backend-domain>
NEXT_PUBLIC_ZERO_CACHE_URL=https://<your-zero-domain>
NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE=LOCAL
NEXT_PUBLIC_ETL_SERVICE=DOCLING
NEXT_PUBLIC_DEPLOYMENT_MODE=self-hosted

# ZeroCache
ZERO_CACHE_PORT=5929
ZERO_ADMIN_PASSWORD=<strong-password>
ZERO_NUM_SYNC_WORKERS=4
ZERO_UPSTREAM_MAX_CONNS=20
ZERO_CVR_MAX_CONNS=30

# SearXNG
SEARXNG_SECRET=<random-secret>

# App
NOWING_VERSION=latest
```

Các biến **cần thêm từ** `.env.example`:
```bash
cat docker/.env.example
```

### Bước 5: Cấu hình Domains trong Dokploy

Cần tạo domains cho 3 services exposed:

| Service | Domain gợi ý | Port target |
|---|---|---|
| `frontend` | `app.nowing.yourdomain.com` | 3000 |
| `backend` | `api.nowing.yourdomain.com` | 8000 |
| `zero-cache` | `sync.nowing.yourdomain.com` | 4848 |

Trong Dokploy → Compose → **Domains** → Add domain cho từng service với:
- Certificate: Let's Encrypt
- HTTPS: enabled
- serviceName: tên service trong compose (e.g., `frontend`, `backend`, `zero-cache`)

### Bước 6: Deploy lần đầu

1. Dokploy → Compose → **Deploy**
2. Theo dõi logs, thứ tự healthy services:
   ```
   db → redis → searxng → backend → celery_worker → celery_beat → zero-cache → frontend
   ```
3. Backend cần `start_period: 200s` để run DB migrations trước

### Bước 7: Cấu hình Auto-deploy (Watchtower / Webhook)

**Option A: Watchtower** (đã sẵn sàng)
- Tất cả containers đã có label `com.centurylinklabs.watchtower.enable=true`
- Deploy Watchtower service riêng hoặc trong cùng compose
- Tự động pull image mới từ GHCR khi có push

**Option B: Dokploy Webhook** (khuyến nghị)
1. Dokploy → Compose → **Deployments** → **Deploy webhook URL**
2. Copy webhook URL
3. Thêm vào GitHub Actions workflow sau step `create_manifest`:
   ```yaml
   - name: Trigger Dokploy redeploy
     run: |
       curl -X POST "${{ secrets.DOKPLOY_WEBHOOK_URL }}"
   ```
4. Add `DOKPLOY_WEBHOOK_URL` vào GitHub Secrets

---

## Lưu ý quan trọng

### Shared Volume `nowing-shared-temp`
`backend` và `celery_worker` dùng chung volume `/shared_tmp` cho file uploads. Đảm bảo Dokploy mount đúng volume này cho cả 2 containers.

### Frontend runtime env substitution
`nowing-web` image build với placeholder `__NEXT_PUBLIC_*__` và swap tại runtime qua `docker-entrypoint.sh`. Các `NEXT_PUBLIC_*` env vars **phải set đúng** trong Compose env — không hardcode vào image.

### Database migrations
Backend chạy migrations tự động khi `SERVICE_ROLE=api`. Không cần can thiệp thủ công nếu dùng đúng `docker-compose.yml`.

### Zero-cache requires PostgreSQL publications
Lần đầu setup zero-cache, cần chạy migration tạo `zero_publication` trong DB. Check backend logs nếu zero-cache không start.

---

## Checklist deploy

- [ ] Tạo project `nowing` trong Dokploy
- [ ] Cấu hình GHCR registry credentials
- [ ] Copy và điền đầy đủ `.env` từ `docker/.env.example`
- [ ] Tạo Compose service từ `docker/docker-compose.yml`
- [ ] Cấu hình domains cho frontend, backend, zero-cache
- [ ] Deploy lần đầu, verify health checks
- [ ] Setup webhook từ GitHub Actions → Dokploy
- [ ] Test auto-deploy bằng cách push commit nhỏ lên `main`

---

## Tài liệu tham khảo dự án

| File | Mô tả |
|---|---|
| `docs/deployment-guide.md` | Deployment guide chính thức |
| `docker/docker-compose.yml` | Production compose stack |
| `docker/docker-compose.dev.yml` | Dev compose stack |
| `docker/.env.example` | Tất cả biến env cần thiết |
| `nowing_backend/Dockerfile` | Backend image build |
| `nowing_web/Dockerfile` | Frontend image build |
| `.github/workflows/docker-build.yml` | CI/CD pipeline |
| `nowing_backend/scripts/docker/entrypoint.sh` | Container entrypoint logic |
