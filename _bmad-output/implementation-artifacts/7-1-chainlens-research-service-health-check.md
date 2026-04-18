# Story 7.1: Backend Service Layer — ChainlensResearchService & Health Check

Status: done

## Story

As a Kỹ sư Backend,
I want xây dựng `ChainlensResearchService` với các method `is_available()` và `research()`, đồng thời thêm 4 biến cấu hình vào `Config` class,
So that các layer phía trên (LangGraph tool ở Story 7.2) có thể gọi service một cách đáng tin cậy và biết trạng thái Chainlens API mọi lúc.

## Acceptance Criteria

1. **Given** file `nowing_backend/app/services/chainlens_research_service.py` được tạo (~100 LOC)
   **When** `ChainlensResearchService.is_available()` được gọi
   **Then** method kiểm tra `Config.CHAINLENS_RESEARCH_ENABLED` trước — nếu `False` trả về `False` ngay lập tức (không có network call)
   **And** nếu flag bật nhưng `CHAINLENS_RESEARCH_API_URL` trống → trả về `False` không raise exception

2. **Given** `CHAINLENS_RESEARCH_ENABLED=TRUE` và `CHAINLENS_RESEARCH_API_URL` được set
   **When** `ChainlensResearchService.is_available()` được gọi
   **Then** gọi `GET {CHAINLENS_RESEARCH_API_URL}/api/v1/b2b/health` với timeout 3 giây
   **And** kết quả (True/False) được cache in-process theo `Config.CHAINLENS_HEALTH_CACHE_TTL` (default 30s)
   **And** nếu lần gọi tiếp theo trong TTL → return cached value, không gọi network

3. **Given** `CHAINLENS_RESEARCH_API_URL` và `CHAINLENS_RESEARCH_API_KEY` được set trong env
   **When** `ChainlensResearchService.research(query: str, sources: list[str] | None = None)` được gọi
   **Then** gửi `POST {URL}/api/v1/b2b/research` với header `Authorization: Bearer {API_KEY}` và body `{"query": query, "sources": sources or ["web"], "stream": false}`
   **And** timeout là 125 giây (buffer cho NFR-P4 ≤ 120s)
   **And** nếu HTTP 200 → return `resp.json()` dạng `dict` cho caller

4. **Given** Chainlens API trả về lỗi (non-200, timeout, exception mạng)
   **When** `research()` hoặc health check gặp lỗi
   **Then** invalidate health cache (`_health_cache = (False, time.monotonic())`)
   **And** raise `ChainlensUnavailableError` với message mô tả (không expose stack trace lên caller)
   **And** log warning server-side (không log error — chỉ warning)

5. **Given** `CHAINLENS_RESEARCH_API_URL` không được set hoặc rỗng
   **When** `ChainlensResearchService` được import/khởi tạo
   **Then** không raise exception — chỉ log warning một lần (startup warning)
   **And** `is_available()` trả về `False` ngay không thực hiện network call

6. **Given** 4 biến env mới cần thêm vào Config
   **When** `nowing_backend/app/config/__init__.py` được load
   **Then** class `Config` có các attribute sau (KHÔNG dùng type annotation — nhất quán với existing pattern trong class):
   ```python
   CHAINLENS_RESEARCH_API_URL = os.getenv("CHAINLENS_RESEARCH_API_URL", "")
   CHAINLENS_RESEARCH_API_KEY = os.getenv("CHAINLENS_RESEARCH_API_KEY", "")
   CHAINLENS_RESEARCH_ENABLED = os.getenv("CHAINLENS_RESEARCH_ENABLED", "FALSE").upper() == "TRUE"
   CHAINLENS_HEALTH_CACHE_TTL = int(os.getenv("CHAINLENS_HEALTH_CACHE_TTL", "30"))
   ```

## Tasks / Subtasks

- [ ] Task 1: Thêm 4 env vars vào `Config` class (AC: #6)
  - [ ] 1.1 Mở `nowing_backend/app/config/__init__.py`, tìm class `Config` (dòng 246)
  - [ ] 1.2 Insert 4 dòng **sau block STT_SERVICE_API_KEY (dòng ~530), trước block VIDEO_PRESENTATION** — giữ nhóm service configs liền nhau
  - [ ] 1.3 Verify với `python -c "from app.config import config; print(config.CHAINLENS_RESEARCH_ENABLED)"`

- [ ] Task 2: Tạo file `chainlens_research_service.py` (AC: #1, #2, #3, #4, #5)
  - [ ] 2.1 Tạo `nowing_backend/app/services/chainlens_research_service.py` (~100 LOC)
  - [ ] 2.2 Import `time`, `httpx`, `logging` và `from app.config import config`
  - [ ] 2.3 Định nghĩa `ChainlensUnavailableError(Exception)`
  - [ ] 2.4 Implement class `ChainlensResearchService` với class-level cache `_health_cache: tuple[bool, float]`
  - [ ] 2.5 Implement `is_available()` classmethod với TTL cache logic (sử dụng `time.monotonic()`)
  - [ ] 2.6 Implement `research()` classmethod với `httpx.AsyncClient(timeout=125.0)`
  - [ ] 2.7 Đảm bảo cả hai method là `async` (pattern nhất quán với codebase)

- [ ] Task 3: Unit tests (AC: tất cả)
  - [ ] 3.1 Tạo `nowing_backend/tests/unit/services/test_chainlens_research_service.py` (folder `tests/unit/services/` đã tồn tại — xem `test_docling_image_support.py` làm pattern reference)
  - [ ] 3.2 Test `is_available()` với flag=FALSE → return False không gọi network (mock httpx)
  - [ ] 3.3 Test `is_available()` với URL rỗng → return False
  - [ ] 3.4 Test cache TTL: gọi 2 lần trong TTL → chỉ 1 network call
  - [ ] 3.5 Test `research()` thành công: mock HTTP 200 response, verify headers/payload
  - [ ] 3.6 Test `research()` timeout: verify `ChainlensUnavailableError` raised + cache invalidated
  - [ ] 3.7 Test `research()` HTTP 500: verify `ChainlensUnavailableError` raised
  - [ ] 3.8 Test khởi tạo không có URL: verify không raise exception, chỉ log warning

## Dev Notes

### Codebase Patterns — PHẢI tuân theo

**Service pattern hiện tại** (`web_search_service.py` là reference tốt nhất):
- Import `from app.config import config` (lowercase singleton, không phải `Config` class)
- Dùng `httpx.AsyncClient` cho async HTTP calls — **đã có trong dependencies**
- `logger = logging.getLogger(__name__)` — không dùng `print()`
- Class-level cache dùng `time.monotonic()` (không phải `time.time()` — monotonic chính xác hơn cho elapsed time)

**Không được dùng:**
- Redis cho health check cache — dùng in-process class variable (`_health_cache`) như trong architecture.md
- `requests` library — project dùng `httpx` async throughout
- `asyncio.timeout()` — dùng `httpx.AsyncClient(timeout=X)` thay thế
- ⚠️ **`verify=False`** — KHÔNG copy flag `verify=False` từ `web_search_service.py` (nó chỉ dùng cho internal SearXNG). Chainlens là public HTTPS endpoint → dùng default `verify=True`

### File Locations

```
nowing_backend/app/config/__init__.py          # [EDIT] insert 4 dòng sau STT_SERVICE_API_KEY (dòng ~530), trước VIDEO_PRESENTATION block
nowing_backend/app/services/
    chainlens_research_service.py              # [NEW] ~100 LOC
nowing_backend/tests/unit/services/
    test_chainlens_research_service.py         # [NEW] unit tests (folder đã tồn tại)
```

### Config Class Pattern

Xem `nowing_backend/app/config/__init__.py` dòng 246+. Class `Config` dùng class-level attributes trực tiếp:

```python
class Config:
    # ... existing attributes ...
    SEARXNG_DEFAULT_HOST = os.getenv("SEARXNG_DEFAULT_HOST")  # ← pattern
    
    # Chainlens Research Integration (thêm sau TTS/STT service configs)
    CHAINLENS_RESEARCH_API_URL = os.getenv("CHAINLENS_RESEARCH_API_URL", "")
    CHAINLENS_RESEARCH_API_KEY = os.getenv("CHAINLENS_RESEARCH_API_KEY", "")
    CHAINLENS_RESEARCH_ENABLED = os.getenv("CHAINLENS_RESEARCH_ENABLED", "FALSE").upper() == "TRUE"
    CHAINLENS_HEALTH_CACHE_TTL = int(os.getenv("CHAINLENS_HEALTH_CACHE_TTL", "30"))
```

Config được access qua singleton: `from app.config import config` (lowercase `config` instance).

**Lưu ý về "log warning một lần" (AC #5):** Do `Config` class được import 1 lần khi module load, module-level warning log sẽ tự động chỉ chạy 1 lần. Không cần tự implement guard (pattern: để `logger.warning(...)` ở module-level của `chainlens_research_service.py` khi detect missing URL tại import time).

### Service Implementation Reference

Architecture đã cung cấp full implementation blueprint (xem `architecture.md` section "Service Layer — ChainlensResearchService"):

```python
# nowing_backend/app/services/chainlens_research_service.py
import time
import logging
import httpx
from app.config import config  # lowercase singleton

logger = logging.getLogger(__name__)


class ChainlensUnavailableError(Exception):
    """Raised when Chainlens API is unreachable or returns non-success response."""
    pass


class ChainlensResearchService:
    """Proxy service gọi Chainlens Research B2B API với health check cached."""

    _health_cache: tuple[bool, float] = (False, 0.0)  # (is_live, timestamp)

    @classmethod
    async def is_available(cls) -> bool:
        """Health check với in-process cache TTL. Timeout 3s để không block."""
        # 1. Feature flag check
        if not config.CHAINLENS_RESEARCH_ENABLED or not config.CHAINLENS_RESEARCH_API_URL:
            return False

        # 2. Check cache
        now = time.monotonic()
        is_live, cached_at = cls._health_cache
        if now - cached_at < config.CHAINLENS_HEALTH_CACHE_TTL:
            return is_live

        # 3. Fresh health check
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{config.CHAINLENS_RESEARCH_API_URL}/api/v1/b2b/health"
                )
                live = resp.status_code == 200
                cls._health_cache = (live, now)
                return live
        except Exception:
            cls._health_cache = (False, now)
            return False

    @classmethod
    async def research(cls, query: str, sources: list[str] | None = None) -> dict:
        """Gọi Chainlens B2B research endpoint. Raise ChainlensUnavailableError nếu fail."""
        if not await cls.is_available():
            raise ChainlensUnavailableError("Chainlens API not available or disabled")

        if not config.CHAINLENS_RESEARCH_API_KEY:
            raise ChainlensUnavailableError("CHAINLENS_RESEARCH_API_KEY not configured")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.CHAINLENS_RESEARCH_API_KEY}",
        }
        payload = {
            "query": query,
            "sources": sources or ["web"],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=125.0) as client:
                resp = await client.post(
                    f"{config.CHAINLENS_RESEARCH_API_URL}/api/v1/b2b/research",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    raise ChainlensUnavailableError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return resp.json()
        except httpx.TimeoutException:
            cls._health_cache = (False, time.monotonic())
            raise ChainlensUnavailableError("Chainlens API request timed out (>120s)")
        except ChainlensUnavailableError:
            raise  # re-raise as-is
        except Exception as e:
            cls._health_cache = (False, time.monotonic())
            raise ChainlensUnavailableError(f"Chainlens request failed: {type(e).__name__}")
```

### Chainlens B2B API Contract

```
# Health check (public, no auth)
GET /api/v1/b2b/health
Response 200: { "data": { "status": "available" }, ... }

# Research (requires Bearer auth)
POST /api/v1/b2b/research
Headers: Authorization: Bearer <api_key>, Content-Type: application/json
Body: { "query": string, "sources": ["web"|"discussions"|"academic"], "stream": false }
Response 200: { "message": string, "sources": [...] }
Error: 400 (validation), 500 (internal), 504 (timeout)
Timeout: 120 seconds (server-side)
```

### NFR Compliance

- **NFR-P4 (Deep Research ≤ 120s):** Client timeout = 125s (5s buffer). Server-side Chainlens timeout = 120s. Nếu vượt quá → `httpx.TimeoutException` → `ChainlensUnavailableError` → Story 7.2 fallback.

### Testing Patterns

Xem `nowing_backend/tests/unit/services/test_docling_image_support.py` và `tests/unit/agents/new_chat/tools/test_update_memory_scope.py` cho pytest async patterns. Dùng **`pytest-asyncio` + `unittest.mock.AsyncMock`** (stick with 1 mocking library — KHÔNG mix `respx` để tránh confusion).

```python
# Pattern test cache TTL
import pytest
from unittest.mock import AsyncMock, patch
import time

@pytest.mark.asyncio
async def test_health_check_cached():
    # Reset cache
    ChainlensResearchService._health_cache = (False, 0.0)
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=AsyncMock(status_code=200)
        )
        # Call twice
        await ChainlensResearchService.is_available()
        await ChainlensResearchService.is_available()
        
        # Should only call network once (second call hits cache)
        assert mock_client.return_value.__aenter__.return_value.get.call_count == 1
```

### Project Structure Notes

- File mới `chainlens_research_service.py` nằm trực tiếp trong `app/services/` (không cần sub-folder — service đơn giản ~100 LOC, không có sub-modules)
- Không cần thêm vào `app/services/__init__.py` — Story 7.2 sẽ import trực tiếp từ module path
- Story này là **pure backend service layer** — không có API endpoint mới, không có DB migration, không có frontend change

### References

- Architecture blueprint: `docs/../_bmad-output/planning-artifacts/architecture.md#Service Layer — ChainlensResearchService`
- Config pattern: `nowing_backend/app/config/__init__.py` dòng 246-530
- httpx pattern: `nowing_backend/app/services/web_search_service.py` (httpx.AsyncClient usage)
- Tool registry (Story 7.2 sẽ dùng): `nowing_backend/app/agents/new_chat/tools/registry.py`

## Dev Agent Record

### Agent Model Used

_pending_

### Debug Log References

### Completion Notes List

### File List

- `nowing_backend/app/config/__init__.py` (edited)
- `nowing_backend/app/services/chainlens_research_service.py` (new)
- `nowing_backend/tests/services/test_chainlens_research_service.py` (new)

### Review Findings (2026-04-19)

- [x] [Review][Decision] Cache poisoning từ research() errors — mỗi lỗi request lẻ invalidate `_health_cache` → chặn tất cả user 30s dù `/health` vẫn OK. Spec AC#4 yêu cầu invalidate nhưng không bàn đến amplification. Cần quyết: giữ nguyên / dùng penalty TTL ngắn (5s) / tách failed-call cache khỏi health cache.
- [x] [Review][Decision] Không retry trên transient 5xx / network glitch — khác biệt với `web_search_service.py:206-227` (retry 1 lần). Một blip = full failure (125s timeout). Cần quyết: thêm retry 1 lần / giữ nguyên vì caller (Story 7.2) tự fallback.
- [x] [Review][Patch] Thundering herd — concurrent coroutines cùng miss cache gọi nhiều health GET song song; thiếu `asyncio.Lock` [chainlens_research_service.py:34-47]
- [x] [Review][Patch] `resp.json()` trên body 200 malformed → `JSONDecodeError` rơi vào `except Exception` → cache poisoning vì parse-bug [chainlens_research_service.py:83]
- [x] [Review][Patch] Bare `except Exception` ở `is_available()` nuốt config bug (AttributeError/TypeError) & lost stack trace — dùng `logger.exception(..., exc_info=True)` + narrow tới `httpx.HTTPError` [chainlens_research_service.py:48-50, 90-95]
- [x] [Review][Patch] Thiếu validation `sources` ({web, discussions, academic}) → upstream 400 opaque + cache poison [chainlens_research_service.py:53, 67]
- [x] [Review][Patch] Thiếu validation `query` (empty/whitespace) → upstream 400 + cache poison [chainlens_research_service.py:53]
- [x] [Review][Patch] Module-level warning chỉ trigger khi URL rỗng — miss case flag OFF nhưng URL set, và stale khi config thay đổi runtime [chainlens_research_service.py:9-12]
- [x] [Review][Patch] Timeout message ">120s" không khớp client timeout 125s [chainlens_research_service.py:86-87]
- [x] [Review][Patch] Non-200 HTTP raise nhưng không `logger.warning` — thiếu nhất quán với AC#4 "log warning server-side" [chainlens_research_service.py:76-82]
- [x] [Review][Patch] Test `test_import_without_url_does_not_raise` không reload module → branch warning ở line 9-12 thực tế không được cover (module đã import với real config trước khi patch) [test_chainlens_research_service.py:215-229]
- [x] [Review][Defer] `resp.text[:200]` có thể echo response body chứa token/header nhạy cảm khi upstream lỗi [chainlens_research_service.py:81] — deferred, low risk
- [x] [Review][Defer] `httpx.AsyncClient` tạo mới mỗi call — không reuse connection pool, TLS handshake overhead [chainlens_research_service.py:41, 72] — deferred, performance optimization
- [x] [Review][Defer] Tests mutate `_health_cache` class-level trực tiếp thay vì dùng monkeypatch fixture [test_chainlens_research_service.py:162, 191] — deferred, pytest-asyncio default serial
