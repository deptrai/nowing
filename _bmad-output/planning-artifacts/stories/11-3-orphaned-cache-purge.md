# Story 11.3: Automated Orphaned Cache Purge

Status: ready-for-dev

## Story

As a system operator,
I want `crypto_data_snapshots` của workspaces đã bị xóa được tự động dọn dẹp,
so that database không bị bloat bởi dead data vô chủ.

## Acceptance Criteria

1. **Given** Celery Beat đang chạy, **When** mỗi tuần (Sunday 4:00 AM UTC), **Then** task `cleanup_orphaned_snapshots` tự động execute.
2. **Given** `crypto_data_snapshots` record có `search_space_id` = X, **When** X không tồn tại trong bảng `searchspaces`, **Then** record bị xóa.
3. **Given** workspace Y vẫn active, **When** cleanup task chạy, **Then** snapshots của workspace Y KHÔNG bị ảnh hưởng.
4. **Given** orphaned snapshots > 10,000 rows, **When** cleanup chạy, **Then** xóa theo batch 1000 rows/lần để tránh long-running transaction lock.
5. **Given** cleanup task hoàn thành, **When** kiểm tra logs, **Then** log structured: `{"task": "cleanup_orphaned_snapshots", "deleted_count": N, "duration_ms": M}`.
6. **Given** `_CACHE_ENABLED=false`, **When** cleanup task triggered, **Then** task vẫn chạy bình thường (cleanup independent of cache feature flag).

## Tasks / Subtasks

- [ ] Task 1: Implement Celery task (AC: #1, #2, #3, #4, #5, #6)
  - [ ] 1.1 Thêm task `cleanup_orphaned_crypto_snapshots` vào `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py`
  - [ ] 1.2 SQL logic: `DELETE FROM crypto_data_snapshots WHERE search_space_id IS NOT NULL AND search_space_id NOT IN (SELECT id FROM searchspaces)` — execute in batches of 1000. Note: `search_space_id` is **nullable** (Integer, FK ondelete=CASCADE, nullable=True) — chỉ xóa records có `search_space_id` thực sự orphaned, không xóa records có `search_space_id IS NULL`.
  - [ ] 1.3 Wrap trong `asyncio.new_event_loop()` pattern (clone từ existing `cleanup_expired_crypto_snapshots`)
- [ ] Task 2: Register in Celery Beat (AC: #1)
  - [ ] 2.1 Thêm beat schedule entry `crypto-cleanup-orphaned-snapshots` vào `nowing_backend/app/celery_app.py`
  - [ ] 2.2 Schedule: `crontab(hour=4, minute=0, day_of_week=0)` (Sunday 4 AM UTC)
  - [ ] 2.3 Options: `expires: 3600` (1 hour)
- [ ] Task 3: Include task module (AC: #1)
  - [ ] 3.1 Verify `app.tasks.celery_tasks.crypto_refresh_tasks` đã có trong `celery_app.conf.include` — YES, already included
- [ ] Task 4: Tests
  - [ ] 4.1 Unit test: orphaned snapshots bị xóa, active snapshots giữ nguyên
  - [ ] 4.2 Unit test: batch deletion (mock 2500 orphans → verify 3 batches)
  - [ ] 4.3 Unit test: structured log output

## Dev Notes

### Architecture Compliance

- **Existing cleanup task**: `cleanup_expired_crypto_snapshots` đã tồn tại trong cùng file (`crypto_refresh_tasks.py`), chạy daily 3 AM UTC. Task mới chạy weekly 4 AM Sunday — KHÔNG overlap.
- **Pattern clone**: Clone pattern từ `_async_cleanup()` — dùng `get_celery_session_maker()`, `asyncio.new_event_loop()`, structured logging.
- **Table references**: `CryptoDataSnapshot` model (file `nowing_backend/app/db.py`) có `search_space_id = Column(Integer, FK("searchspaces.id", ondelete="CASCADE"), nullable=True)` và `project_id = Column(Integer, FK("crypto_projects.id", ondelete="CASCADE"), nullable=False)`. Orphan detection dựa trên `search_space_id` (workspace ownership), KHÔNG phải `project_id` (crypto project reference).
- **Celery task naming**: Follow convention `crypto.cleanup_orphaned_snapshots` (prefix `crypto.`).

### Existing Code to Modify

| File | Action | Notes |
|------|--------|-------|
| `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py` | UPDATE | Thêm task `cleanup_orphaned_crypto_snapshots` |
| `nowing_backend/app/celery_app.py` | UPDATE | Thêm beat schedule entry |

### Anti-patterns to Avoid

- **KHÔNG** dùng CASCADE DELETE — orphan detection qua explicit query, không phụ thuộc FK cascade
- **KHÔNG** xóa all-at-once — batch 1000 rows tránh lock escalation
- **KHÔNG** check `_CACHE_ENABLED` — cleanup chạy regardless of feature flag

### References

- [Source: _bmad-output/architecture-improvement-proposals-2026-05-01.md#3]
- [Source: nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py — existing cleanup pattern]
- [Source: nowing_backend/app/celery_app.py — beat schedule, line 191-206]
- [Source: nowing_backend/app/db.py — `CryptoDataSnapshot` model, line ~1384]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
