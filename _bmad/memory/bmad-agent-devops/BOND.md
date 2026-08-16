# Bond

## Basics
- **Name:** Luis
- **Call them:** Luis
- **Language:** Tiếng Việt

## Hạ tầng họ đang giữ

**Dokploy org:** `P9JMOFnYd5bQlfaC0tjJV` — chứa 11 project. nowing chỉ là một trong đó.
Anh em cùng máy: chainlens, chainlens-research, vibe-trading, mmomarket, medirus, Reso, appflowy, mattermost, XActions, omniroute.
**Không bao giờ chạm sang project khác.** Địa bàn của tôi chỉ là nowing.

**Project nowing:** `w-k-cq8AzW_kC9G1t5eEd`
**Environment production:** `v9OCYwAqJSpDHuyf4DoGf` (isDefault, chỉ có 1 env — không có staging)

| Service | App ID | appName | Domain | Port | Nguồn |
|---|---|---|---|---|---|
| frontend | `Z3MYiB0npy5zJf0Q4MHT` | nowing-frontend | nowing.net | 3000 | github deptrai/nowing @production, path /nowing_web |
| backend-api | `yqNCh43qjq9rqWAysLUQ` | nowing-backend-api | api.nowing.net | 8000 | github deptrai/nowing @production, path /nowing_backend (`SERVICE_ROLE=api`) |
| backend-worker | `EFAToldKb2zL7A7roXGZA` | nowing-backend-worker | — | — | github deptrai/nowing @production, path /nowing_backend (`SERVICE_ROLE=worker`) |
| backend-beat | `F5SXyqJAPgme1w6vtAgwr` | nowing-backend-beat | — | — | github deptrai/nowing @production, path /nowing_backend (`SERVICE_ROLE=beat`) |
| zero-cache | `mrLWR0r2leCDee0d7Lmy` | nowing-zero-cache | zero.nowing.net | 4848 | docker rocicorp/zero:1.6.0 |
| postgres | `95TnauTU0vCLJsBWLsoF` | nowing-postgres | — | 5432 | pgvector/pgvector:pg17 |
| redis | `LtR77Ku3zl8DQpnUWe5Z` | nowing-redis | — | 6379 | — |
| searxng (compose) | `z6BmLrpFEEqP8tsuHTHQ` | searxng | — | — | compose, status done |

Cả 3 domain (`nowing.net`, `api.nowing.net`, `zero.nowing.net`) đều `letsencrypt` + https, path `/`, stripPath=false.

**Postgres chi tiết:** db `nowing`, user `nowing`, volume `nowing-postgres-data` mount `/var/lib/postgresql/data`.
Chạy với `wal_level=logical`, `max_replication_slots=10`, `max_wal_senders=10`, `max_connections=200` — WAL logical là **bắt buộc** cho zero-cache, không được đổi.
backend-api dùng `postgresql+asyncpg://`, frontend + zero-cache dùng `postgresql://`. Không nhầm driver.

**Cụm backend đã được tách rời (Decoupled):**
- `backend-api` (`yqNCh43qjq9rqWAysLUQ`): Chỉ chạy FastAPI Uvicorn, port 8000. Chạy Alembic migrations trước khi Uvicorn boot.
- `backend-worker` (`EFAToldKb2zL7A7roXGZA`): Chỉ chạy Celery Worker tiêu thụ hàng đợi cào web, OCR, AI indexing.
- `backend-beat` (`F5SXyqJAPgme1w6vtAgwr`): Chỉ chạy Celery Beat scheduler cho các cron job định kỳ.

## Cách họ muốn tôi vận hành
{Chưa hỏi — ranh giới tự quyết là câu quan trọng nhất còn thiếu. Tới khi có câu trả lời, tôi mặc định: đọc thoải mái, không ghi gì lên production mà chưa hỏi.}

## Quy ước deploy của họ
- Branch `production` → cả frontend và backend-api, `autoDeploy=true`, `triggerType=push`. Push vào production là deploy thật.
- zero-cache `autoDeploy=false`, deploy tay (docker image).
- frontend có `watchPaths=["nowing_web/**"]`; backend-api có `watchPaths=["nowing_backend/**"]`.
- backend-api `cleanCache=true`, frontend `cleanCache=false`.
{Cửa sổ tránh deploy: chưa hỏi. Ai được deploy: chưa hỏi.}

## Backup và dữ liệu
**`backups: []` — Postgres production KHÔNG có backup nào được cấu hình trong Dokploy.** Xác nhận bằng `postgres-one` ngày 2026-07-25, không phải suy đoán.
Repo có `scripts/backup/pg_backup.sh` nhưng không có cron nào chạy nó.
Chưa từng có bằng chứng về một lần restore thử.
{Mức chấp nhận mất dữ liệu: chưa hỏi.}

## Điểm đau đã có
{Chưa hỏi. Nhưng xem `incidents.md` — tôi đã mang sẵn 6 bài học từ thế hệ trước.}

## Things They've Asked Me to Remember
{Chưa có.}

## Things to Avoid
{Chưa biết. Kể cả cách họ muốn nghe tin xấu.}
