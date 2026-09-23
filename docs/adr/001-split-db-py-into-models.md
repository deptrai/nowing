# ADR-001: Tách `db.py` thành các module `models/`

## Status

Accepted — đang thực hiện (Giai đoạn B)

## Context

`app/db.py` hiện có 6.955 dòng, chứa:
- SQLAlchemy `Base`, engine, session factory
- Mixins (`TimestampMixin`, `BaseModel`, v.v.)
- Enums (`DocumentType`, `SearchSourceConnectorType`, `Permission`, v.v.)
- Toàn bộ ORM models cho mọi domain (users, workspaces, documents, connectors, chat, billing, scraper, v.v.)

File này là nút thắt lớn nhất của codebase:
- Thời gian import lâu, circular import dễ xảy ra khi thêm model mới.
- Khó review vì diff lớn.
- Không thể tái sử dụng domain models ở tools/tests mà không kéo theo toàn bộ SQLAlchemy stack.

## Decision

Tổ chức lại theo các lớp:
- `app/db/base.py` — `Base`, `get_async_session`, `async_session_maker`, engine/session helpers.
- `app/db/mixins.py` — `TimestampMixin`, `BaseModel`, soft-delete, slug mixins.
- `app/db/enums.py` hoặc `app/enums/common.py` — các enum dùng chung nhiều domain.
- `app/models/{domain}.py` — models theo domain:
  - `users.py`, `workspaces.py`, `documents.py`, `connectors.py`, `chat.py`, `billing.py`, `external.py`, `scraper.py`, `presentations.py`, `memory.py`
- `app/db.py` (giữ lại) sẽ chỉ re-export public API và engine helpers, giữ `__all__` ổn định.

Quy trình di chuyển:
1. Tạng file mới, copy class + imports liên quan.
2. Cập nhật `db.py` để re-export từ file mới.
3. Chạy `alembic history` + `pytest` sau mỗi domain.
4. Sau khi toàn bộ di chuyển xong, mới sửa các import cụ thể trong route/service từ `app.db` sang `app.models.xxx` theo từng PR nhỏ.

## Consequences

- Giảm kích thước `db.py` xuống < 1.000 dòng.
- Mỗi domain có module riêng, dễ tìm, dễ test, dễ review.
- Cần tránh circular import: tách base/mixins/enums trước, model phụ thuộc vào sau.
- Alembic vẫn import metadata từ `Base` nên phải đảm bảo metadata được tập hợp đầy đủ từ `app.models.*`.

## Related

- [[ADR-002-exception-hierarchy]]
- [[ADR-003-split-routes-and-services]]
