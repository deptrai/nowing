---
baseline_commit: de0a8d951
baseline_branch: develop
story_key: 20.3
status: done
priority: P1
epic: Epic 20 — Nowing Ecosystem Integration
---

# Story 20.3: `NowingPrivateProvider` for `POST /v1/private-data/search`

## Story

Là một người dùng Nowing,
tôi muốn dữ liệu riêng tư của mình ở lại Nowing trong khi vẫn được dùng để trả lời,
để bảo toàn quyền riêng tư.

## Acceptance Criteria

1. **Cho** `chainlens-research` gọi `POST /v1/private-data/search` với body hợp lệ `{ query, workspaceId, userId?, connectorId?, sources?, topK? }` cùng header `Authorization: Bearer <CHAINLENS_SERVICE_TOKEN>` và `X-Workspace-Id`, **khi** request đến, **thì** Nowing xác thực service auth token, khớp `workspaceId` với phạm vi token, thiết lập workspace RLS context, chạy tìm kiếm trên dữ liệu riêng tư `Document`/`Chunk`/`Memory` của workspace và trả về `200` với `PrivateDataSearchResponse { chunks: PrivateProviderChunk[], costDollars: 0 }`.
2. **Cho** service auth token bị thiếu, sai định dạng, không nằm trong token pool, hoặc header `X-Workspace-Id` bị thiếu/không hợp lệ, **khi** gọi `POST /v1/private-data/search`, **thì** trả về `401` và không có private chunks nào trong body.
3. **Cho** workspace RLS check thất bại (workspace không tồn tại, service principal không có quyền truy cập, hoặc `workspaceId` trong body không khớp `X-Workspace-Id` của token), **khi** gọi `POST /v1/private-data/search`, **thì** trả về `403` và không có private chunks nào trong body.
4. **Cho** request body không hợp lệ (thiếu `query`, `workspaceId` không phải số nguyên, `topK` ngoài phạm vi, hoặc `userId` sai định dạng), **khi** request đến, **thì** trả về `422` với chi tiết validation rõ ràng và không truy vấn private data.
5. **Cho** private search thực thi, **khi** thu thập kết quả, **thì** trả về `PrivateProviderChunk[]` với `metadata.source = 'private_provider'`, `sourceId` scoped theo document/connector, `metadata.url` theo mẫu `nowing://documents/{document_id}/chunks/{chunk_id}` khi chunk xuất phát từ document, và các citation locators (`document_id`, `chunk_id`, `connector_id`, `workspace_id`) trong `metadata` để Nowing resolve citation.
6. **Cho** `connectorId` được cung cấp, **khi** tìm kiếm, **thì** chỉ trả về các `Document` có `Document.connector_id == connectorId`; `SearchSourceConnector.config` chỉ được đọc khi cần live connector refresh một cách tường minh và OAuth tokens hoặc connector secrets không bao giờ xuất hiện trong response.
7. **Cho** request không có dữ liệu khớp, **khi** tìm kiếm hoàn tất, **thì** trả về `200` với `chunks: []` và `costDollars: 0`, không phải `404`.
8. **Cho** private search hoàn tất thành công, **khi** ghi usage, **thì** ghi một dòng `TokenUsage` với `usage_type = UsageType.CHAINLENS_PRIVATE_SEARCH`, `cost_micros = 0`, `workspace_id` từ token scope, và `user_id` là chủ workspace hoặc user được yêu cầu đã xác thực; không thực hiện wallet debit.

## Tasks / Subtasks

- [ ] Định nghĩa contract và schema cho `NowingPrivateProvider` (AC: #1, #5)
  - [ ] Tạo `nowing_backend/app/services/chainlens/schemas.py` với:
    - `PrivateDataSearchRequest`
    - `PrivateProviderChunkMetadata`
    - `PrivateProviderChunk`
    - `PrivateDataSearchResponse` (alias của `SearchProviderResult`)
  - [ ] Thêm `PrivateProviderService` vào `nowing_backend/app/services/chainlens/private_provider.py` với `PrivateProviderService.search(...)`
  - [ ] Thay thế stub `private_data_search_for_chainlens` trong `nowing_backend/app/routes/chainlens_internal.py`
- [ ] Xác thực service-to-service và workspace RLS (AC: #1, #2, #3)
  - [ ] Tái sử dụng `chainlens_auth_dependency` (`nowing_backend/app/routes/chainlens_internal.py`), hàm này trả về `ChainLensAuthContext(workspace_id, correlation_id, token)` sau khi `ChainLensServiceAuth.validate_inbound_token(request)` (`nowing_backend/app/services/chainlens/auth.py`)
  - [ ] Trong route, lấy `AsyncSession` qua `Depends(get_async_session)`
  - [ ] Xây dựng `AuthContext` tối thiểu từ `Workspace.user` và gọi `check_workspace_access(session, auth, workspace_id)` (`nowing_backend/app/utils/rbac.py`)
  - [ ] Thiết lập tenant GUCs bằng `set_request_tenant_context(session, workspace_id=workspace_id, client_id=None, user_id=None)` (`nowing_backend/app/canonical/tenant_context.py`) trước mọi private query
- [ ] Tìm kiếm private data sources (AC: #1, #5, #7)
  - [ ] Gọi `ChucksHybridSearchRetriever.hybrid_search(query_text, top_k, workspace_id, document_type, ...)` (`nowing_backend/app/retriever/chunks_hybrid_search.py`)
  - [ ] Gọi `DocumentHybridSearchRetriever.hybrid_search(query_text, top_k, workspace_id, document_type, ...)` (`nowing_backend/app/retriever/documents_hybrid_search.py`)
  - [ ] Gọi `MemoryHybridSearch.search(workspace_id=workspace_id, query=query, top_k=..., ...)` (`nowing_backend/app/services/memory/search.py`)
  - [ ] Merge và deduplicate kết quả document-level và chunk-level; giới hạn danh sách cuối cùng ở `topK`
- [ ] Tìm kiếm theo connector scope và redact OAuth (AC: #6)
  - [ ] Nếu `connector_id` được cung cấp, post-filter hoặc query `Document.connector_id == connector_id`
  - [ ] Fetch `SearchSourceConnector` theo `id` chỉ khi cần live refresh; không bao giờ expose `config` trong response
  - [ ] Map connector type sang `DocumentType` từ `nowing_backend/app/db.py` khi `sources` chứa tên connector
- [ ] Xây dựng `PrivateProviderChunk` và cost contract (AC: #5, #7, #8)
  - [ ] Map mỗi document result thành `PrivateProviderChunk` với `metadata.source = 'private_provider'`
  - [ ] Đặt `sourceId` thành giá trị scoped ổn định như `nowing://documents/{document_id}/chunks/{chunk_id}` hoặc `nowing://connectors/{connector_id}/documents/{document_id}/chunks/{chunk_id}`
  - [ ] Bao gồm `document_id`, `chunk_id`, `connector_id`, `workspace_id` trong `metadata` để resolve citation
  - [ ] Trả về `costDollars: 0` và `chunks: []` khi không có kết quả
  - [ ] Gọi `record_token_usage(..., usage_type=UsageType.CHAINLENS_PRIVATE_SEARCH, cost_micros=0, ...)` (`nowing_backend/app/services/token_tracking_service.py`) mà không debit wallet
- [ ] Quan sát (observability) (AC: #8)
  - [ ] Tùy chọn thêm counter/histogram `record_chainlens_private_search` trong `nowing_backend/app/observability/metrics.py` theo pattern `record_chainlens_*`
  - [ ] Phát `record_chainlens_auth_failed` khi auth/RLS thất bại với low-cardinality reasons
- [ ] Tests
  - [ ] Unit test `PrivateProviderService` query parsing, tenant context, result mapping, và empty-result contract
  - [ ] Unit test connector-scoped search và redaction của `SearchSourceConnector.config`
  - [ ] Cập nhật `nowing_backend/tests/integration/routes/test_chainlens_internal.py` để test `POST /v1/private-data/search` với valid/invalid service tokens
  - [ ] Integration test empty results trả về `200` với `chunks: []` và `costDollars: 0`
  - [ ] Integration test cross-workspace access bị từ chối (`403` và không leak data)

## Dev Notes

- Architecture patterns và ràng buộc liên quan
  - `AD-15` (Nowing sở hữu private data, `chainlens-research` là external engine) yêu cầu provider chạy trong Nowing và trả về chunks theo yêu cầu; không đẩy private data sang `chainlens-research` để index.
  - `AD-35` (Nowing không xây public/vertical search corpus) khẳng định private search là surface tìm kiếm duy nhất do workspace sở hữu.
  - `AD-5` / `AD-31` (workspace RLS) — cô lập tenant phải được thiết lập trước mọi query thông qua `set_request_tenant_context(session, workspace_id=workspace_id, client_id=None, user_id=None)`, không dùng raw `SET LOCAL`.
  - `AD-16` (ranh giới license) — logic OAuth/connector và proprietary fetchers nằm trong `nowing_backend/app/proprietary/`; contract endpoint và RBAC của `NowingPrivateProvider` nằm trong code Apache-2.0 bên ngoài `app/proprietary/`.
  - `AD-34` (canonical chunk schema) — mọi chunk trả về phải có `metadata.source`, `sourceId`, `domain`, `fetchedAt`, `contentType`. `private_provider` là giá trị hợp lệ trong enum `source` do chainlens sở hữu.
  - `FR-60` và PRD §4.10 định nghĩa product contract; `FR-61` yêu cầu service-to-service auth và cost attribution.
  - `ux-contract-private-data-provider.md` định nghĩa UX trust indicators và citation behavior.

- Các thành phần source tree cần chạm
  - `nowing_backend/app/services/chainlens/private_provider.py` — `PrivateProviderService` mới
  - `nowing_backend/app/services/chainlens/schemas.py` — `PrivateDataSearchRequest`, `PrivateProviderChunk`, `PrivateDataSearchResponse`
  - `nowing_backend/app/services/chainlens/auth.py` — `ChainLensAuthContext`, `ChainLensServiceAuth`, `ChainLensServiceAuth.validate_inbound_token`
  - `nowing_backend/app/routes/chainlens_internal.py` — `chainlens_auth_dependency`, `private_data_search_for_chainlens`, `POST /v1/private-data/search`
  - `nowing_backend/app/services/chainlens/__init__.py` — export new public symbols
  - `nowing_backend/app/app.py` — đã mount `chainlens_internal_router` tại `prefix="/v1"` (không thay đổi)
  - `nowing_backend/app/retriever/chunks_hybrid_search.py` — `ChucksHybridSearchRetriever.hybrid_search`
  - `nowing_backend/app/retriever/documents_hybrid_search.py` — `DocumentHybridSearchRetriever.hybrid_search`
  - `nowing_backend/app/services/memory/search.py` — `MemoryHybridSearch.search`
  - `nowing_backend/app/services/connector_service.py` — `ConnectorService.get_connector_by_type` và pattern `ConnectorService._combined_rrf_search`
  - `nowing_backend/app/services/token_tracking_service.py` — `record_token_usage` và `UsageType.CHAINLENS_PRIVATE_SEARCH`
  - `nowing_backend/app/db.py` — `SearchSourceConnector`, `Document`, `Chunk`, `Memory`, `Workspace`, `User`, `TokenUsage`
  - `nowing_backend/app/canonical/tenant_context.py` — `set_request_tenant_context`
  - `nowing_backend/app/utils/rbac.py` — `check_workspace_access`
  - `nowing_backend/app/auth/context.py` — `AuthContext`
  - `nowing_backend/app/observability/metrics.py` — pattern `record_chainlens_*`

- Request/response schemas (code)

```python
# nowing_backend/app/services/chainlens/schemas.py
# ruff: noqa: N815
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrivateDataSearchRequest(BaseModel):
    """Body of `POST /v1/private-data/search`."""

    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, max_length=500)
    workspaceId: int = Field(..., gt=0)
    userId: UUID | None = Field(default=None)
    connectorId: int | None = Field(default=None, gt=0)
    sources: list[str] | None = Field(default=None)
    topK: int = Field(default=20, ge=1, le=100)

    @field_validator("query", mode="before")
    @classmethod
    def _strip_query(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class PrivateProviderChunkMetadata(BaseModel):
    """Canonical metadata for a chunk returned by the private provider."""

    model_config = ConfigDict(extra="allow")

    source: Literal["private_provider"] = "private_provider"
    sourceId: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    fetchedAt: str = Field(..., min_length=1)
    contentType: str = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1)
    url: str | None = Field(default=None, min_length=1)
    document_id: int | None = None
    chunk_id: int | None = None
    connector_id: int | None = None
    workspace_id: int | None = None

    @field_validator("fetchedAt")
    @classmethod
    def _validate_fetched_at(cls, value: str) -> str:
        if value:
            datetime.fromisoformat(value)
        return value


class PrivateProviderChunk(BaseModel):
    """One private search result chunk."""

    content: str = Field(..., min_length=1)
    metadata: PrivateProviderChunkMetadata


class PrivateDataSearchResponse(BaseModel):
    """Nowing alias for the chainlens `SearchProviderResult` contract."""

    chunks: list[PrivateProviderChunk] = Field(default_factory=list)
    costDollars: float = Field(default=0.0, ge=0.0)
```

- Auth và RLS flow

```python
# nowing_backend/app/routes/chainlens_internal.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.canonical.tenant_context import set_request_tenant_context
from app.db import get_async_session, Workspace
from app.services.chainlens.auth import ChainLensAuthContext
from app.services.chainlens.private_provider import PrivateProviderService
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateDataSearchResponse,
)
from app.services.token_tracking_service import UsageType, record_token_usage
from app.utils.rbac import check_workspace_access

# `chainlens_auth_dependency` is defined in this same module and returns a
# `ChainLensAuthContext` after `ChainLensServiceAuth.validate_inbound_token`.


async def private_data_search_for_chainlens(
    request: Request,
    context: ChainLensAuthContext = Depends(chainlens_auth_dependency),
    body: PrivateDataSearchRequest = ...,
    session: AsyncSession = Depends(get_async_session),
) -> PrivateDataSearchResponse:
    ...
```

- `ChainLensAuthContext` không mang end-user, nên route phải xây dựng `AuthContext` từ chủ workspace:

```python
result = await session.execute(
    select(Workspace)
    .options(selectinload(Workspace.user))
    .where(Workspace.id == context.workspace_id)
)
workspace = result.scalar_one_or_none()
if workspace is None or body.workspaceId != context.workspace_id:
    raise HTTPException(status_code=403, detail="Forbidden")

auth = AuthContext.system(user=workspace.user, source="chainlens")
await check_workspace_access(session, auth, context.workspace_id)

await set_request_tenant_context(
    session,
    workspace_id=context.workspace_id,
    client_id=None,
    user_id=None,
)
```

- Search retriever signatures cần gọi

```python
# ChucksHybridSearchRetriever.hybrid_search
async def hybrid_search(
    self,
    query_text: str,
    top_k: int,
    workspace_id: int,
    document_type: str | list[str] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    query_embedding: list | None = None,
) -> list[dict]

# DocumentHybridSearchRetriever.hybrid_search
async def hybrid_search(
    self,
    query_text: str,
    top_k: int,
    workspace_id: int,
    document_type: str | list[str] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    query_embedding: list | None = None,
    w_vector: float = 0.7,
    w_fts: float = 0.3,
    statuses: list[str] | None = None,
) -> list[dict]

# MemoryHybridSearch.search
async def search(
    self,
    *,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    query: str,
    query_embedding: list[float] | np.ndarray | None = None,
    top_k: int = 5,
    type: str | None = None,
    tags: list[str] | None = None,
    research_thread_id: int | None = None,
    client_id: str | None = None,
) -> list[ScoredMemory]
```

- `set_request_tenant_context` signature

```python
async def set_request_tenant_context(
    session: AsyncSession,
    workspace_id: int | None = None,
    client_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    memory_id: int | None = None,
    user_id: str | None = None,
) -> None
```

- `check_workspace_access` signature

```python
async def check_workspace_access(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> WorkspaceMembership
```

- `record_token_usage` call cho cost/observability contract

```python
await record_token_usage(
    session,
    usage_type=UsageType.CHAINLENS_PRIVATE_SEARCH,
    workspace_id=context.workspace_id,
    user_id=workspace.user_id,
    prompt_tokens=0,
    completion_tokens=0,
    total_tokens=0,
    cost_micros=0,
    call_details={
        "correlation_id": context.correlation_id,
        "query": body.query,
        "connector_id": body.connectorId,
        "sources": body.sources,
        "requested_user_id": str(body.userId) if body.userId else None,
    },
)
```

- Xử lý `userId`
  - `userId` trong request body là trường correlation/audit, không phải trường xác thực hoặc ủy quyền.
  - Service token và `X-Workspace-Id` là trust boundary; RBAC sử dụng chủ workspace (`Workspace.user`) để xây dựng `AuthContext` tối thiểu.
  - Nếu `userId` được cung cấp và user là thành viên workspace, nó có thể dùng cho user-scoped `MemoryHybridSearch` và `TokenUsage.user_id`; ngược lại, ghi vào `call_details` và bỏ qua.
  - Private chunks được lọc theo workspace và, khi có `connectorId`, theo connector; không chunk nào leak sang workspace khác.

- Error-handling contract
  - `401` — `Authorization` header thiếu/sai định dạng, token không nằm trong pool, `X-Workspace-Id` thiếu, hoặc `X-Workspace-Id` không dương.
  - `403` — workspace không tồn tại, workspace RLS check thất bại, hoặc `body.workspaceId` không khớp `context.workspace_id`.
  - `422` — Pydantic validation failure trên request body.
  - `200` — tìm kiếm thực thi thành công, kể cả khi không có kết quả; body response luôn chứa `chunks` và `costDollars`.

- Hành vi connector và OAuth
  - `Document.connector_id` là integer foreign key tới `SearchSourceConnector.id`.
  - Khi `connectorId` được cung cấp, kết quả được lọc về các document có `connector_id` khớp.
  - `SearchSourceConnector.config` là JSON column, có thể chứa OAuth tokens. Chỉ đọc khi cần live connector refresh (ví dụ: gọi `*_kb_sync_service.py`); không bao giờ trả về `chainlens-research`.
  - Đường tìm kiếm mặc định dùng các dòng `Document`/`Chunk` đã được index, không gọi live connector API.

- Testing standards summary
  - Mock cuộc gọi inbound của `chainlens-research` với valid/invalid `Authorization: Bearer <service-token>` và `X-Workspace-Id`.
  - Assert mọi response chunk có `metadata.source = 'private_provider'` và `sourceId` ổn định.
  - Assert không có `config`, OAuth token, hoặc credential raw nào rời response.
  - Assert cross-workspace request trả về `403` và không có data.
  - Assert empty results là `200 OK` với `chunks: []` và `costDollars: 0`.
  - Assert dòng `TokenUsage` được ghi với `usage_type = 'chainlens_private_search'` và `cost_micros = 0`.

### Project Structure Notes

- `NowingPrivateProvider` là một service, không phải capability, nên nó thuộc về `nowing_backend/app/services/chainlens/` cùng với `ingest.py` và `auth.py`.
- Public endpoint được expose trong `nowing_backend/app/routes/chainlens_internal.py` và được mount tại `prefix="/v1"` trong `nowing_backend/app/app.py` (không phải `nowing_backend/app/routes/__init__.py`).
- Stub endpoint hiện tại trong `chainlens_internal.py` trả về `{"status": "accepted", "workspace_id": context.workspace_id}`; cần thay thế bằng route đầy đủ.
- Private data search tái sử dụng các module `app/retriever/` và `app/services/memory/search.py` hiện có thay vì xây dựng index mới.

### Conflicts or Variances

- `TokenUsage.user_id` là non-nullable, nhưng chainlens service token không có end-user principal. Implementation phải derive user từ chủ workspace hoặc xác thực `userId` tùy chọn trong request.
- `chainlens-research` `SearchProviderResult` chunk schema có thể khác với internal `Chunk` model của Nowing; cần một adapter layer trong `private_provider.py` để xây dựng `PrivateProviderChunk`.
- `sourceId` cho private chunks phải ổn định trong workspace và scoped theo document/connector để `chainlens-research` có thể merge kết quả mà không lưu private data.
- `MemoryHybridSearch` bắt buộc chỉ một trong `workspace_id` hoặc `user_id` được set; provider gọi nó với `workspace_id` và tùy chọn một lần gọi thứ hai với `user_id` nếu user hợp lệ được cung cấp.
- Connector `config` lưu OAuth tokens và credentials trong `JSONB`; provider chỉ đọc khi cần live sync và không bao giờ forward.
- Đường dẫn route là `/v1/private-data/search` theo cross-project contract; nó không nằm dưới `/api/v1/`.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Epic 20 / Story 20.3]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-5, AD-15, AD-16, AD-31, AD-34, AD-35]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-60, FR-61]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-private-data-provider.md`]
- [Source: `nowing_backend/app/routes/chainlens_internal.py` §existing stub]
- [Source: `nowing_backend/app/services/chainlens/auth.py` §`ChainLensAuthContext`, `ChainLensServiceAuth`]
- [Source: `nowing_backend/app/routes/chainlens_internal.py` §`chainlens_auth_dependency`, `private_data_search_for_chainlens`]
- [Source: `nowing_backend/app/retriever/chunks_hybrid_search.py` §`ChucksHybridSearchRetriever.hybrid_search`]
- [Source: `nowing_backend/app/retriever/documents_hybrid_search.py` §`DocumentHybridSearchRetriever.hybrid_search`]
- [Source: `nowing_backend/app/services/memory/search.py` §`MemoryHybridSearch.search`]
- [Source: `nowing_backend/app/services/connector_service.py` §connector lookup]
- [Source: `nowing_backend/app/services/token_tracking_service.py` §`record_token_usage`, `UsageType.CHAINLENS_PRIVATE_SEARCH`]
- [Source: `nowing_backend/app/db.py` §`SearchSourceConnector`, `Document`, `Chunk`, `Memory`, `Workspace`, `User`, `TokenUsage`]
- [Source: `nowing_backend/app/canonical/tenant_context.py` §`set_request_tenant_context`]
- [Source: `nowing_backend/app/utils/rbac.py` §`check_workspace_access`]
- [Source: `nowing_backend/app/auth/context.py` §`AuthContext`]
- [Source: `nowing_backend/app/observability/metrics.py` §`record_chainlens_*`]

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### File List

- `nowing_backend/app/services/chainlens/private_provider.py` (new)
- `nowing_backend/app/services/chainlens/schemas.py` (new)
- `nowing_backend/app/services/chainlens/__init__.py` (update exports)
- `nowing_backend/app/routes/chainlens_internal.py` (replace stub)
- `nowing_backend/tests/unit/services/chainlens/test_private_provider.py` (new)
- `nowing_backend/tests/integration/routes/test_chainlens_internal.py` (update / extend)
- `nowing_backend/app/observability/metrics.py` (optional new metric helper)

### Debug Log References

- Verified current `develop` HEAD `de0a8d951`.
- Verified `chainlens_internal_router` is mounted at `prefix="/v1"` in `nowing_backend/app/app.py`.
- Verified `ChainLensAuthContext` fields (`workspace_id`, `correlation_id`, `token`) and `chainlens_auth_dependency` signature.
- Verified `UsageType.CHAINLENS_PRIVATE_SEARCH` already exists in `token_tracking_service.py`.
- Verified `set_request_tenant_context` uses `set_config('app.workspace_id', ...)`; it accepts `user_id` and `client_id`.
- Verified `check_workspace_access` requires `AuthContext` with a `User`; resolved by building from `Workspace.user`.
- Verified `ChucksHybridSearchRetriever.hybrid_search` and `DocumentHybridSearchRetriever.hybrid_search` full signatures.
- Verified `MemoryHybridSearch.search` signature and workspace/user exclusivity.

### Completion Notes List

- Refreshed the story to use the current codebase as the baseline.
- Corrected request/response Pydantic schemas with all fields, types, defaults, and validation rules.
- Corrected the RLS pattern to `set_request_tenant_context(session, workspace_id=workspace_id, client_id=None, user_id=None)`.
- Corrected workspace access to use `check_workspace_access(session, auth, workspace_id)` with a minimal `AuthContext` built from the workspace owner.
- Aligned with the existing 20.4 implementation: `chainlens_auth_dependency` and `ChainLensAuthContext`.
- Updated file paths to include the `nowing_backend/` prefix and corrected the route mounting location (`app.app`, not `app/routes/__init__.py`).
- Provided exact retriever function signatures.
- Clarified `userId` as audit/correlation only.
- Added the 401/403/400/200 error-handling contract and the missing AC for auth/RLS failure.
- Added the cost/observability contract (`costDollars: 0`, optional `TokenUsage` with `UsageType.CHAINLENS_PRIVATE_SEARCH`, no wallet debit).
- Included the existing stub endpoint that must be replaced.
- Added concrete subtasks with exact files/functions.
- Added verification commands section.

## Verification Commands

```bash
cd nowing_backend
ruff check app/services/chainlens/private_provider.py \
          app/services/chainlens/schemas.py \
          app/routes/chainlens_internal.py \
          app/services/chainlens/auth.py \
          app/observability/metrics.py
ruff format app/services/chainlens/private_provider.py \
           app/services/chainlens/schemas.py \
           app/routes/chainlens_internal.py
pytest tests/unit/services/chainlens/test_private_provider.py -q
pytest tests/integration/routes/test_chainlens_internal.py -q
```

If the dedicated unit-test file does not exist yet, run the broader service-level suite:

```bash
pytest tests/unit/services/chainlens/ -q
pytest tests/integration/routes/test_chainlens_internal.py -q
```
