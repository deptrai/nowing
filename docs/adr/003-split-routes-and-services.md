# ADR-003: Tách route/service khổng lồ theo domain

## Status

Accepted — dự kiến thực hiện (Giai đoạn D)

## Context

Một số file backend phình to:
- `app/routes/search_source_connectors_routes.py` — 3.284 dòng
- `app/routes/documents_routes.py` — 2.074 dòng
- `app/services/connector_service.py` — 2.423 dòng
- `app/config/__init__.py` — 1.948 dòng
- `app/services/llm_router_service.py` — singleton phức tạp

Các file này chứa nhiều responsibility khác nhau, khó review, khó test, khó maintain.

## Decision

### Routes
- `app/routes/search_source_connectors_routes.py` → tách thành package `app/routes/connectors/`:
  - `crud.py` — CRUD connector.
  - `indexing.py` — trigger/index connector content.
  - `oauth.py` — OAuth callbacks.
  - `mcp.py` — MCP connectors.
  - `github.py` — GitHub repo list.
- `app/routes/documents_routes.py` → package `app/routes/documents/` hoặc route ngắn gọi service.

### Services
- `app/services/connectors/`:
  - `connector_manager.py` — CRUD + caching.
  - `indexing_dispatcher.py` — chọn indexer theo type.
  - `credential_service.py` — quản lý credentials.
- `app/services/documents/`:
  - `document_service.py` — CRUD.
  - `upload_service.py` — file upload, storage, virus scan placeholder.
  - `processing_service.py` — OCR, parse, chunk.
  - `dispatch_service.py` — gửi task Celery.
- `app/services/connector_service.py` → tách thành:
  - `ConnectorSearchService`
  - `ChunkSourceBuilder`
  - `ConnectorCacheManager`
  - `ConnectorDiscoveryService`
- `app/config/__init__.py` → package `app/config/`:
  - `database.py`, `llm.py`, `auth.py`, `connectors.py`, `billing.py`, `external_apis.py`, `storage.py`
- `app/services/llm_router_service.py` → DI container hoặc module-level instance với lock; tách `RouterConfigBuilder`, `ModelResolver`, `RetryHandler`.

## Consequences

- Route < 500 dòng, service < 800 dòng trừ khi có lý do rõ ràng.
- Unit test có thể import từng service domain độc lập.
- Cần hoàn thành ADR-001 trước để tránh circular import khi service import models.

## Related

- [[ADR-001-split-db-py-into-models]]
- [[ADR-002-exception-hierarchy]]
- [[ADR-004-frontend-component-convention]]
