# Kế hoạch refactor toàn diện Nowing — giải quyết technical debt P0/P1

> Dựa trên báo cáo `AUDIT_TECHNICAL_DEBT_2026-08-30.md`

## 1. Ngữ cảnh

Nowing là monorepo lớn (5.287 file, backend ~1.218.565 LOC Python, frontend ~183.668 LOC TS/TSX). Sau audit, phát hiện nợ kỹ thuật nghiêm trọng tập trung ở:

- **Backend monolith**: `db.py` 6.955 dòng, `config/__init__.py` 1.948 dòng, các route/service khổng lồ (`search_source_connectors_routes.py` 3.284 dòng, `documents_routes.py` 2.074 dòng, `connector_service.py` 2.423 dòng).
- **Xử lý lỗi bừa bãi**: 1.753 lần `except Exception` toàn backend, 699 lần trong `routes/`/`services/`, cùng `print()` còn sót.
- **Frontend khổng lồ**: `use-connector-dialog.ts` 1.433 dòng, `thread.tsx` 2.413 dòng, `CampaignBuilder.tsx` 1.293 dòng, `nowing_web` 3.6 GB.
- **Bảo mật/observability**: `subprocess`/`Popen`/`web_builder` command execution chưa sandbox, metrics.py boilerplate, downgrade Alembic không được gọi/test.

Yêu cầu: **không làm quick wins**, mà lập kế hoạch **đầy đủ** để giải quyết các vấn đề then chốt.

## 2. Mục tiêu

1. Tách backend thành các module/domain rõ ràng, dễ maintain, test, và review.
2. Xây dựng exception hierarchy + error handling nhất quán.
3. Tách frontend thành các component/hook nhỏ, giảm bundle size, tăng testability.
4. Audit và sandbox các điểm chạy `subprocess`/`Popen`/`eval`.
5. Cải thiện testing/CI: coverage hub nodes, alembic downgrade smoke test, lint rules.

## 3. Kế hoạch thực hiện theo giai đoạn

### Giai đoạn A — Chuẩn bị nền tảng (1 tuần)

#### A.1 Tạo worktree riêng và branch `refactor/technical-debt-cleanup`
- Dùng `EnterWorktree` tạo worktree `tech-debt-cleanup` từ `develop`.
- Branch: `worktree-tech-debt-cleanup`.
- Cấu hình CI tạm để chạy test/lint trên branch.

#### A.2 Thiết lập công cụ & baseline
- Chạy test suite hiện tại để lấy baseline (pytest, Playwright smoke).
- Đo thời gian build `next build`, `uv run pytest --collect-only`.
- Chạy `ruff`/`biome` để lấy danh sách lỗi hiện tại.
- Chạy `code-review-graph` `detect_changes_tool` trước khi sửa để so sánh sau.

#### A.3 Viết ADR (Architecture Decision Records)
- ADR-1: Tổ chức lại `db.py` thành `models/`.
- ADR-2: Exception hierarchy và error handling.
- ADR-3: Tách route/service theo domain.
- ADR-4: Frontend component/hook refactoring convention.
- ADR-5: Subprocess sandbox policy.

---

### Giai đoạn B — Backend: tách `db.py` (2–3 tuần)

`db.py` là nợ kỹ thuật lớn nhất. Tách sai sẽ gây circular import và migration lỗi.

#### B.1 Phân loại nội dung `db.py`
- Enums (`DocumentType`, `SearchSourceConnectorType`, `Permission`, v.v.) → `app/db/enums.py` hoặc `app/enums/`.
- Mixins (`TimestampMixin`, `BaseModel`) → `app/db/mixins.py`.
- Base + engine/session → `app/db/base.py`.
- Models theo domain:
  - `app/models/users.py` (`User`, `WorkspaceMembership`, `PersonalAccessToken`)
  - `app/models/workspaces.py` (`Workspace`, `WorkspaceRole`, `Broadcast`)
  - `app/models/documents.py` (`Document`, `DocumentVersion`, `Chunk`, `Folder`)
  - `app/models/connectors.py` (`SearchSourceConnector`, `ConnectorCredential`)
  - `app/models/chat.py` (`NewChatThread`, `NewChatMessage`, `ChatComment`)
  - `app/models/billing.py` (`TokenUsage`, `CreditPurchase`, `PagePurchase`)
  - `app/models/external.py` (`ExternalChatAccount`, `ExternalChatBinding`)
  - `app/models/scraper.py` (`ScraperPlatformAccount`, `ScraperRule`)
  - `app/models/presentations.py` (`VideoPresentation`, `MeetingMinutes`, `Report`)
  - `app/models/memory.py` (`Memory*`, `Prompt`)

#### B.2 Tái cấu trúc an toàn (không phá import cũ)
1. Tạng file mới.
2. Di chuyển class/function sang file mới.
3. Tại `db.py`, thay thế body bằng `from app.models.xxx import *` hoặc re-export cụ thể.
4. Đảm bảo `__all__` trong `db.py` giữ nguyên public API.
5. Chạy `pytest` sau mỗi domain move.
6. Sau khi toàn bộ di chuyển xong, mới đổi các file import từ `app.db` sang `app.models.xxx` theo từng PR nhỏ.

#### B.3 Kiểm tra migration
- Chạy `alembic history` để đảm bảo không thiếu import.
- Tạo migration test mới: `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` trên test DB.

#### B.4 Tách enum
- Các enum dùng chung nhiều nơi nên ở `app/enums/common.py`.
- Các enum chỉ dùng trong một domain nên ở domain đó (`app/models/connectors.py` hoặc `app/enums/connectors.py`).

---

### Giai đoạn C — Backend: exception hierarchy & error handling (1,5–2 tuần)

#### C.1 Xây dựng exception tree
- `app/exceptions.py` đã có `NowingError`. Mở rộng:
  - `NotFoundError`
  - `PermissionDeniedError`
  - `ValidationError` (không trùng Pydantic)
  - `ConnectorError` → `OAuthError`, `IndexingError`, `RateLimitError`
  - `DocumentError` → `UploadError`, `ParseError`, `StorageError`
  - `LLMError` → `ContextOverflowError`, `ModelUnavailableError`
  - `ExternalAPIError`
  - `ConfigurationError`

#### C.2 Viết lại global exception handler trong `app.py`
- Map từng exception class → status code + error code + client-safe message.
- Đảm bảo `request_id`, `workspace_id`, `user_id` được ghi log.

#### C.3 Thay thế `except Exception` trong route/service
- Không được dùng `except Exception` ở route/service trừ khi:
  - Là entrypoint cuối (handler global).
  - Có comment giải thích và log đầy đủ.
- Thay bằng:
  - Bắt exception cụ thể (`ValueError`, `HTTPException`, `IntegrityError`, `TimeoutError`).
  - Bắt domain exception (`ConnectorError`, `DocumentError`).
  - Cuối cùng catch `Exception` tại handler/middleware để trả lỗi chuẩn.

#### C.4 Xóa `print()` còn sót
- Thay `print()` trong `services/connector_service.py`, `services/kokoro_tts_service.py`, `routes/documents_routes.py`, `config/__init__.py` thành `logger`.
- Thêm `ruff` rule `T201` và CI.

#### C.5 Sửa `asyncio.set_event_loop_policy` side effect
- Đưa vào hàm `initialize_event_loop_policy()`.
- Gọi rõ ràng trong `app.py` lifespan hoặc Celery worker startup.
- Bỏ `print` trong except.

---

### Giai đoạn D — Backend: tách route/service khổng lồ (2–3 tuần)

#### D.1 `search_source_connectors_routes.py` (3.284 dòng)
- Tách thành:
  - `app/routes/connectors/crud.py` — CRUD connector.
  - `app/routes/connectors/indexing.py` — trigger/index connector content.
  - `app/routes/connectors/oauth.py` — OAuth callbacks.
  - `app/routes/connectors/mcp.py` — MCP connectors.
  - `app/routes/connectors/github.py` — GitHub repo list.
- Tạo `app/services/connectors/`:
  - `connector_manager.py` — CRUD + caching.
  - `indexing_dispatcher.py` — chọn indexer theo type.
  - `credential_service.py` — quản lý credentials.

#### D.2 `documents_routes.py` (2.074 dòng)
- Tách thành:
  - `app/services/documents/document_service.py` — CRUD.
  - `app/services/documents/upload_service.py` — file upload, storage, virus scan placeholder.
  - `app/services/documents/processing_service.py` — OCR, parse, chunk.
  - `app/services/documents/dispatch_service.py` — gửi task Celery.
- Route chỉ còn validate input, gọi service, trả response.

#### D.3 `connector_service.py` (2.423 dòng)
- Tách thành:
  - `ConnectorSearchService` — search files/youtube/extension.
  - `ChunkSourceBuilder` — build sources từ chunks.
  - `ConnectorCacheManager` — cache invalidation.
  - `ConnectorDiscoveryService` — discovery + doc types.

#### D.4 `config/__init__.py` (1.948 dòng)
- Tách thành module:
  - `app/config/database.py`
  - `app/config/llm.py`
  - `app/config/auth.py`
  - `app/config/connectors.py`
  - `app/config/billing.py`
  - `app/config/external_apis.py`
  - `app/config/storage.py`
- Dùng Pydantic `BaseSettings` với validation, default, và deprecated alias warning.
- Bỏ `print()` lỗi trong `_read_global_config_yaml`.

#### D.5 `llm_router_service.py`
- Thay singleton bằng module-level instance với `asyncio.Lock` hoặc DI container.
- Tách `LLMRouterService` thành:
  - `RouterConfigBuilder`
  - `ModelResolver`
  - `RetryHandler`

---

### Giai đoạn E — Frontend refactor (2–3 tuần)

#### E.1 Tách `use-connector-dialog.ts` (1.433 dòng)
- `useConnectorOAuth` — cookie OAuth, parse callback.
- `useConnectorIndexing` — date range, frequency, vision LLM, periodic sync.
- `useConnectorEdit` — update/delete connector.
- `useConnectorAccounts` — quản lý multiple accounts.
- `useMCPConnectors` — MCP list/connection.
- `useConnectorDialogState` — open/close/tab state.

#### E.2 Tách `thread.tsx` (2.413 dòng)
- `components/assistant-ui/Composer.tsx`
- `components/assistant-ui/Thread.tsx`
- `components/assistant-ui/ThreadMessage.tsx`
- `components/assistant-ui/ComposerAction.tsx`
- `components/assistant-ui/ThreadScroll.tsx`

#### E.3 Tách `CampaignBuilder.tsx` (1.293 dòng)
- Tách theo step: `AudienceStep`, `ContentStep`, `ScheduleStep`, `ReviewStep`.
- Tách state management ra `useCampaignBuilder()`.

#### E.4 Bundle size audit
- Chạy `next-bundle-analyzer`.
- Loại bỏ Plate plugins không dùng.
- Lazy-load icons, connector views, heavy editors.
- Kiểm tra `node_modules/.next` nặng 3.6 GB — dọn cache, duplicate dependencies.

#### E.5 Type/UI primitive policy
- Freeze `Button`, `cn`, `Input`, `Skeleton`, `Label` API.
- Không thêm prop mới mà không qua ADR.
- Dùng barrel export ổn định.

---

### Giai đoạn F — Bảo mật & sandbox (1 tuần)

#### F.1 Audit `subprocess`/`Popen`/`eval`
- `app/services/web_builder/builder.py`
- `app/services/web_builder/deploy_service.py`
- `app/routes/admin_scraper_platform_accounts_routes.py`
- `app/agents/video_presentation/nodes.py`
- `app/services/presentation/marp_driver.py`
- `app/templates/export_helpers.py`
- `app/agents/chat/multi_agent_chat/shared/middleware/filesystem/sandbox.py`

#### F.2 Các quy tắc áp dụng
- Không dùng `shell=True`.
- Không pass user input vào command/args.
- Dùng allow-list cho command và working directory.
- Chạy web builder/scraper trong Daytona sandbox hoặc container riêng.
- Timeout, kill orphan process.
- Đưa `Popen` ở admin route thành Celery task với timeout.

#### F.3 `ast.literal_eval` trong chat filesystem
- `app/tasks/chat/streaming/handlers/tools/filesystem/ls/thinking.py:38`.
- Đảm bảo input từ LLM/sandbox, không phải user raw.

---

### Giai đoạn G — Observability & metrics (3–5 ngày)

#### G.1 `metrics.py` 1.532 dòng
- Tạo decorator/factory `@metric("name", unit, description)`.
- Chuyển 70+ hàm `_metric_name()` sang factory.
- Sử dụng OpenTelemetry semantic conventions nếu phù hợp.

#### G.2 Distributed tracing
- Thêm trace context qua chat flow, connector indexing, research, billing.
- Đảm bảo `request_id` xuyên suốt FastAPI → Celery → external API.

---

### Giai đoạn H — Testing & CI (song song với các giai đoạn trên)

#### H.1 Tăng coverage cho hub nodes
- `get_async_session` — test connection pool, rollback.
- `get_auth_context` — test session, PAT, impersonation.
- `check_permission` — test wildcard, full_access, missing permission.
- `Button`, `cn`, `Input` — snapshot tests.

#### H.2 CI improvements
- `alembic downgrade -1` smoke test.
- Lint rule `T201` (no print in production).
- Lint rule chống `except Exception` trong routes/services (bằng `ruff` custom hoặc grep).
- CI check file size > 1.000 dòng warn, > 2.000 dòng block.
- CI chống `.only` / `@pytest.mark.skip` mới.

#### H.3 Test Alembic downgrade
- Chạy trên test container PostgreSQL trong CI.
- Đảm bảo `downgrade()` scripts không bị lỗi thời.

---

## 4. Thứ tự ưu tiên thực hiện

| Thứ tự | Giai đoạn | Thời gian ước tính | Tại sao trước |
|---|---|---|---|
| 1 | A — Chuẩn bị | 1 tuần | Baseline, worktree, ADR |
| 2 | C — Exception + print + event loop | 1.5 tuần | Foundation, ít file phụ thuộc, ROI cao |
| 3 | B — Tách `db.py` | 2.5 tuần | Nút thắt lớn nhất, chạm mọi thứ |
| 4 | D — Tách route/service | 2.5 tuần | Sau khi db tách xong, tránh circular import |
| 5 | F — Bảo mật/sandbox | 1 tuần | Song song với D, rủi ro bảo mật |
| 6 | E — Frontend refactor | 2.5 tuần | Độc lập với backend, có thể song song |
| 7 | G — Observability | 4 ngày | Sau D/E để biết metrics cần trace |
| 8 | H — Testing/CI | xuyên suốt | Đảm bảo không regression |

**Tổng thời gian ước tính: 10–12 tuần** (với 1–2 người full-time).

---

## 5. Cách tổ chức PR

- Mỗi giai đoạn con là 1 PR riêng, merge vào `develop` qua worktree.
- Không merge trực tiếp vào `main`.
- Mỗi PR phải có:
  - Mô tả scope rõ ràng.
  - Danh sách file thay đổi.
  - Test pass (pytest + Playwright smoke + lint).
  - `detect_changes_tool` trước và sau.
  - Không có `except Exception` mới, không có `print()` mới.

---

## 6. Rủi ro & cách giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Circular import khi tách `db.py` | Di chuyển từng domain, giữ re-export, chạy test liên tục |
| Regression do đổi exception handling | Thay từng module, bắt exception cụ thể trước, test integration |
| Migration lỗi | Thêm `alembic upgrade/downgrade` smoke test trong CI |
| Frontend build break | Chạy `next build` sau mỗi component tách, snapshot tests |
| Subprocess sandbox làm chậm web builder | Test với Daytona local trước khi bật buộc |
| Scope creep | Giới hạn mỗi PR, không tách thêm ngoài ADR |

---

## 7. Cách xác nhận hoàn thành (Definition of Done)

- `db.py` không còn quá 1.000 dòng (chỉ re-export + engine/session helpers).
- Không còn `except Exception` trong `routes/` và `services/` (trừ entrypoint handler).
- Không còn `print()` trong production code.
- `search_source_connectors_routes.py` < 500 dòng.
- `documents_routes.py` < 400 dòng.
- `use-connector-dialog.ts` < 300 dòng.
- `thread.tsx` < 400 dòng.
- 100% `subprocess`/`Popen` qua allow-list hoặc sandbox.
- CI pass: pytest, Playwright smoke, alembic downgrade, lint T201, no `.only`.
- Code-review-graph risk score giảm so với baseline.
