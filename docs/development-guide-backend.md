# Hướng dẫn phát triển - SurfSense Backend

**Ngày tạo:** 2026-07-21 16:59:34

## Yêu cầu

- Python 3.12+
- uv hoặc pip
- PostgreSQL 15+ với pgvector extension
- Redis

## Cài đặt

```bash
cd surfsense_backend
uv sync
# hoặc
pip install -e .
```

## Môi trường

```bash
cp .env.example .env
# chỉnh sửa DATABASE_URL, REDIS_URL, BACKEND_URL, NEXT_FRONTEND_URL, các API keys
```

## Chạy local

```bash
uv run python main.py --reload
# hoặc
uv run uvicorn app.app:app --reload --host 0.0.0.0 --port 8000
```

## Celery worker

```bash
uv run celery -A celery_worker worker -l info
```

## Database migrations

```bash
alembic upgrade head
```

## Test

```bash
uv run pytest tests/unit
uv run pytest tests/integration -m integration
```

## Docker

```bash
cd ../docker
# làm theo README hoặc chạy install.sh / install.ps1
```

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
