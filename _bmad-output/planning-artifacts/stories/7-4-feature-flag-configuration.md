# Story 7.4: Feature Flag & Configuration — Admin Control không cần Redeploy

Status: done

## Story

As an Admin/DevOps,
I want bật/tắt tích hợp Chainlens Deep Research bằng cách thay đổi env var `CHAINLENS_RESEARCH_ENABLED` và restart service (không rebuild/redeploy code), với startup log rõ ràng + `.env.example` documented + safe defaults,
So that có thể phản ứng nhanh khi Chainlens API có vấn đề (vd: vendor outage, key rotate, rate limit) hoặc cần rollback gracefully mà không ảnh hưởng end users.

## Acceptance Criteria

1. **Given** `CHAINLENS_RESEARCH_ENABLED=false` (hoặc env var không tồn tại — default safe)
   **When** user trigger deep research từ chat (gõ "deep research about X")
   **Then** `ChainlensResearchService.is_available()` return `False` ngay lập tức (không network call)
   **And** tool `chainlens_deep_research` return `{"status": "fallback", ...}` (Story 7.2)
   **And** LLM tự động gọi `generate_report(report_style="deep_research", ...)` (Story 7.2 instructions)
   **And** user nhận kết quả từ fallback — KHÔNG có log error, KHÔNG có UI error message liên quan vendor

2. **Given** `CHAINLENS_RESEARCH_ENABLED=true` và đầy đủ `CHAINLENS_RESEARCH_API_URL` + `CHAINLENS_RESEARCH_API_KEY`
   **When** service restart
   **Then** lifespan startup log INFO message: `"[Chainlens] Integration ENABLED — URL=<url>, health cache TTL=<ttl>s"`
   **And** lần đầu user trigger deep research → Chainlens API được sử dụng làm primary engine (không fallback)

3. **Given** `CHAINLENS_RESEARCH_ENABLED=true` **nhưng** `CHAINLENS_RESEARCH_API_KEY` bị thiếu/trống
   **When** service restart
   **Then** lifespan startup log **WARNING**: `"[Chainlens] CHAINLENS_RESEARCH_ENABLED=true but CHAINLENS_RESEARCH_API_KEY is missing — feature will fallback to built-in research"`
   **And** `is_available()` trả về `False` (đã handle ở Story 7.1) — service vẫn boot bình thường, không crash

4. **Given** `CHAINLENS_RESEARCH_ENABLED=true` **nhưng** `CHAINLENS_RESEARCH_API_URL` bị thiếu/trống
   **When** service restart
   **Then** lifespan startup log **WARNING**: `"[Chainlens] CHAINLENS_RESEARCH_ENABLED=true but CHAINLENS_RESEARCH_API_URL is missing — feature will fallback to built-in research"`
   **And** `is_available()` trả về `False` (đã handle ở Story 7.1) — service vẫn boot bình thường

5. **Given** `CHAINLENS_RESEARCH_ENABLED=false`
   **When** service restart
   **Then** lifespan startup log INFO: `"[Chainlens] Integration DISABLED (CHAINLENS_RESEARCH_ENABLED=false) — using built-in research only"`
   **And** không có warning về missing API_KEY/URL (vì feature đã tắt — không cần chúng)

6. **Given** file `nowing_backend/.env.example` được edit
   **When** developer/DevOps đọc file
   **Then** có section mới với 4 env vars + comment giải thích:
   ```env
   # Chainlens Deep Research Integration (optional)
   # External B2B research API. When ENABLED=false (default), deep research
   # falls back to built-in generate_report. Toggle without redeploy by
   # setting CHAINLENS_RESEARCH_ENABLED=true and restarting service.
   CHAINLENS_RESEARCH_ENABLED=false
   # CHAINLENS_RESEARCH_API_URL=https://api.chainlens.example.com
   # CHAINLENS_RESEARCH_API_KEY=your-b2b-api-key-here
   # CHAINLENS_HEALTH_CACHE_TTL=30
   ```
   **And** default value `CHAINLENS_RESEARCH_ENABLED=false` — **safe by default** (feature opt-in)
   **And** API_URL và API_KEY được comment out (không phải uncomment-ready) để tránh DevOps quên thay placeholder

7. **Given** documentation file `docs/chainlens-integration.md` (flat layout — convention hiện tại của `docs/` chứa các file như `architecture-backend.md`, `deployment-guide.md`) cần update
   **When** DevOps cần biết cách bật Chainlens
   **Then** có section **"Chainlens Deep Research Integration"** mô tả:
   - Mục đích feature flag (rollback gracefully)
   - Cách lấy API key (link tới Chainlens onboarding flow hoặc note "contact Chainlens team")
   - 3 bước bật: (1) set 4 env vars, (2) restart service, (3) verify startup log
   - 1 bước tắt (rollback): set `CHAINLENS_RESEARCH_ENABLED=false` + restart
   - Health check cách nào: `GET <CHAINLENS_RESEARCH_API_URL>/api/v1/b2b/health` từ command line trước

8. **Given** lifespan startup function (`app/app.py`)
   **When** function chạy
   **Then** `_validate_chainlens_config()` được gọi (function mới — Task 1) trước khi `yield`
   **And** function chỉ log message — KHÔNG raise exception (failure-tolerant)
   **And** function gọi `from app.config import config` để đọc 4 env vars

9. **Given** `CHAINLENS_HEALTH_CACHE_TTL` được set giá trị invalid (vd: chữ "abc" thay vì số)
   **When** `Config` class load env (Story 7.1)
   **Then** raise `ValueError` từ `int()` conversion ở module load time → service KHÔNG boot
   **And** error log rõ ràng để DevOps biết sửa env var
   **Note:** Đây là behavior `int()` mặc định ở Story 7.1 — Story 7.4 chỉ document trong README để DevOps biết.

## Tasks / Subtasks

- [x] Task 1: Implement startup config validation (AC: #2, #3, #4, #5, #8)
  - [x] 1.1 Mở `nowing_backend/app/app.py`, locate `lifespan()` function (dòng 21)
  - [x] 1.2 Tạo helper function `_validate_chainlens_config()` ở cùng file (hoặc tách ra `app/config/chainlens_validator.py`)
  - [x] 1.3 Implement logic 4 nhánh:
    - `ENABLED=false` → log INFO "DISABLED, using built-in research only"
    - `ENABLED=true` + URL+KEY đủ → log INFO "ENABLED — URL=..., TTL=...s"
    - `ENABLED=true` + missing URL → log WARNING
    - `ENABLED=true` + missing KEY → log WARNING
  - [x] 1.4 Wrap trong try/except — never raise (graceful)
  - [x] 1.5 Gọi `_validate_chainlens_config()` trong `lifespan()` trước `yield` (sau `seed_nowing_docs()`)

- [x] Task 2: Update `.env.example` (AC: #6)
  - [x] 2.1 Mở `nowing_backend/.env.example`
  - [x] 2.2 Thêm section mới ở cuối file (sau Ollama section) với 4 env vars + comment block
  - [x] 2.3 `CHAINLENS_RESEARCH_ENABLED=false` (uncomment, safe default)
  - [x] 2.4 3 vars còn lại comment out với placeholder rõ ràng
  - [x] 2.5 Verify syntax `.env.example` vẫn valid: `python -c "from dotenv import dotenv_values; dotenv_values('.env.example')"` không raise

- [x] Task 3: Documentation (AC: #7)
  - [x] 3.1 Tạo file mới `docs/chainlens-integration.md` (flat convention — xem `docs/deployment-guide.md`, `docs/integration-architecture.md` làm pattern reference). **KHÔNG** tạo sub-folder `docs/CODEMAPS/`.
  - [x] 3.2 Viết section "Chainlens Deep Research Integration" với 5 phần:
    - Mục đích
    - Cách lấy API key
    - 3 bước bật
    - 1 bước rollback
    - Verify health check command line
  - [x] 3.3 Cross-link tới architecture.md section "Deep Research — Chainlens Integration Architecture"
  - [x] 3.4 Thêm link từ `docs/index.md` → `chainlens-integration.md`

- [x] Task 4: Unit test cho startup validation (AC: #2-#5, #8)
  - [x] 4.1 Tạo `nowing_backend/tests/unit/app/test_chainlens_config_validation.py`
  - [x] 4.2 Test 6 scenarios dùng `types.SimpleNamespace` mock (tránh `load_dotenv` interference):
    - Test 1: `ENABLED=false` → log có "DISABLED"
    - Test 2: `ENABLED=true` + đủ key+url → log có "ENABLED"
    - Test 3: `ENABLED=true` + thiếu key → log WARNING
    - Test 4: `ENABLED=true` + thiếu url → log WARNING
    - Test 5: `ENABLED=false` + thiếu key → KHÔNG có warning
    - Test 6: exception → graceful, không raise
  - [x] 4.3 Test exception trong validator KHÔNG crash lifespan (mock `config` to raise)

- [x] Task 5: Integration test rollback flow (AC: #1, #2)
  - [x] 5.1 Test end-to-end: `ENABLED=true` → `is_available()` = True (mock HTTP 200)
  - [x] 5.2 Set `ENABLED=false` (rollback) → `is_available()` = False, no network call
  - [x] 5.3 Rollback flow test: phase 1 enabled → phase 2 disabled
  - [x] 5.4 `research()` raises `ChainlensUnavailableError` khi disabled (service contract)
  - [x] 5.5 Startup validator silent, no ERROR-level log khi disabled (FR25)

## Dev Notes

### CRITICAL Design Decisions (PHẢI tuân theo)

**1. Safe-by-default**

`CHAINLENS_RESEARCH_ENABLED=false` là default. Lý do:
- Existing deployments không bị bật feature mới đột ngột khi pull code
- DevOps phải opt-in bằng cách đổi env + restart → có audit trail rõ ràng
- Feature flag không mặc định bật → giảm risk khi production rollout

**2. Validation chỉ LOG — không RAISE**

`_validate_chainlens_config()` chỉ log warning, KHÔNG raise exception. Lý do:
- Service phải boot ngay cả khi Chainlens config sai (graceful degradation)
- Story 7.1 đã handle runtime: `is_available()` return False → fallback path
- Crash service vì 1 feature flag sai = poor DX

**3. Không có FE thay đổi**

Story 7.4 thuần backend config + docs. Admin/DevOps tương tác qua:
- `.env` file (chỉnh tay hoặc CI/CD secrets)
- Service restart command (vd: `docker compose restart backend`)

KHÔNG có admin UI để toggle (out of scope — yêu cầu FE story riêng nếu cần sau này).

### Codebase Patterns — PHẢI tuân theo

**Lifespan startup pattern** (xem `app/app.py` dòng 20-32):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    await setup_checkpointer_tables()
    initialize_llm_router()
    await seed_nowing_docs()
    # ← Story 7.4: thêm validation ở đây
    _validate_chainlens_config()
    yield
    await close_checkpointer()
```

**Config singleton import**:
```python
from app.config import config  # lowercase singleton
```

**`.env.example` pattern** (xem các section hiện có như Residential Proxy, Ollama):
- Section header comment với mô tả
- Mặc định an toàn uncomment, options comment out
- Comment giải thích khi nào uncomment

### File Locations

```
nowing_backend/app/
    app.py                                      # [EDIT] +call _validate_chainlens_config() trong lifespan, +helper function (~25 dòng)
nowing_backend/.env.example                     # [EDIT] +1 section, 4 env vars (~10 dòng)
docs/chainlens-integration.md                   # [NEW] DevOps guide (~80 dòng, flat layout)
docs/index.md                                   # [EDIT] +1 link entry
nowing_backend/tests/unit/app/
    test_chainlens_config_validation.py         # [NEW] unit tests (folder `tests/unit/` đã tồn tại, subfolder `app/` sẽ tạo mới nếu chưa có)
```

### Implementation Reference

**Task 1 — Helper function trong `app/app.py`:**

```python
# nowing_backend/app/app.py — thêm function này gần đầu file (sau imports)
import logging

logger = logging.getLogger(__name__)


def _validate_chainlens_config() -> None:
    """Validate Chainlens integration config at startup.
    
    Logs INFO when feature is enabled with valid config, WARNING when
    enabled but misconfigured. Never raises — service must boot regardless
    so the fallback path (built-in research) remains available.
    """
    try:
        from app.config import config
        
        if not config.CHAINLENS_RESEARCH_ENABLED:
            logger.info(
                "[Chainlens] Integration DISABLED "
                "(CHAINLENS_RESEARCH_ENABLED=false) — using built-in research only"
            )
            return
        
        # Feature is enabled — verify required vars
        missing: list[str] = []
        if not config.CHAINLENS_RESEARCH_API_URL:
            missing.append("CHAINLENS_RESEARCH_API_URL")
        if not config.CHAINLENS_RESEARCH_API_KEY:
            missing.append("CHAINLENS_RESEARCH_API_KEY")
        
        if missing:
            logger.warning(
                "[Chainlens] CHAINLENS_RESEARCH_ENABLED=true but %s "
                "%s missing — feature will fallback to built-in research",
                ", ".join(missing),
                "is" if len(missing) == 1 else "are",
            )
            return
        
        logger.info(
            "[Chainlens] Integration ENABLED — URL=%s, health cache TTL=%ss",
            config.CHAINLENS_RESEARCH_API_URL,
            config.CHAINLENS_HEALTH_CACHE_TTL,
        )
    except Exception as exc:  # noqa: BLE001 — never crash lifespan
        logger.warning(
            "[Chainlens] Config validation failed: %s — feature disabled",
            type(exc).__name__,
        )
```

Sau đó update `lifespan()`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    await setup_checkpointer_tables()
    initialize_llm_router()
    await seed_nowing_docs()
    _validate_chainlens_config()  # ← NEW
    yield
    await close_checkpointer()
```

**Task 2 — `.env.example` addition:**

```env
# ============================================================================
# Chainlens Deep Research Integration (optional)
# ============================================================================
# External B2B research API providing high-quality multi-source web research.
# When CHAINLENS_RESEARCH_ENABLED=false (default), the deep research feature
# falls back to built-in generate_report — users see no errors.
# 
# To enable:
#   1. Obtain a B2B API key from Chainlens (contact your Chainlens admin)
#   2. Set CHAINLENS_RESEARCH_API_URL and CHAINLENS_RESEARCH_API_KEY below
#   3. Set CHAINLENS_RESEARCH_ENABLED=true
#   4. Restart the backend service (no rebuild needed)
#   5. Verify startup log: "[Chainlens] Integration ENABLED — URL=..."
#
# To rollback: set CHAINLENS_RESEARCH_ENABLED=false and restart.
# ============================================================================
CHAINLENS_RESEARCH_ENABLED=false
# CHAINLENS_RESEARCH_API_URL=https://api.chainlens.example.com
# CHAINLENS_RESEARCH_API_KEY=your-b2b-api-key-here
# CHAINLENS_HEALTH_CACHE_TTL=30
```

**Task 3 — `docs/CODEMAPS/chainlens-integration.md`:**

````markdown
# Chainlens Deep Research Integration

## Mục đích

Chainlens Deep Research là engine nghiên cứu web chuyên sâu bên ngoài (B2B API) — Nowing tích hợp như một upgrade cho tính năng deep research, với cơ chế **graceful fallback** về `generate_report` built-in khi Chainlens không khả dụng.

Feature flag `CHAINLENS_RESEARCH_ENABLED` cho phép Admin/DevOps:
- Bật/tắt feature **không cần redeploy code**
- Rollback nhanh khi vendor có vấn đề (outage, rate limit, key rotate)
- Phased rollout (bật trên staging trước, sau đó production)

## Cách lấy API Key

Liên hệ Chainlens team để được cấp B2B API key:
- Email: `b2b@chainlens.example.com` (placeholder — thay bằng contact thật)
- Hoặc generate qua Chainlens admin dashboard nếu bạn có access

API key có format string dài (~64 chars), lưu cẩn thận như credential.

## Cách bật

```bash
# 1. Edit .env (hoặc CI/CD secrets)
CHAINLENS_RESEARCH_API_URL=https://api.chainlens.example.com
CHAINLENS_RESEARCH_API_KEY=<paste-your-key-here>
CHAINLENS_RESEARCH_ENABLED=true
CHAINLENS_HEALTH_CACHE_TTL=30  # default, optional

# 2. Restart backend
docker compose restart backend
# hoặc nếu local dev:
# ctrl+c rồi `uvicorn app.app:app --reload`

# 3. Verify startup log có dòng:
# [Chainlens] Integration ENABLED — URL=https://..., health cache TTL=30s
```

## Cách rollback

```bash
# 1. Edit .env
CHAINLENS_RESEARCH_ENABLED=false

# 2. Restart backend
docker compose restart backend

# 3. Verify startup log:
# [Chainlens] Integration DISABLED — using built-in research only
```

User KHÔNG bị gián đoạn — deep research tự động dùng `generate_report` built-in, không có error UI.

## Verify Health Check (manual)

Trước khi bật flag trong production, verify Chainlens API reachable:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.chainlens.example.com/api/v1/b2b/health
# Expected: 200
```

Nếu 200 OK → safe to enable. Nếu khác → contact Chainlens team trước khi bật.

## Troubleshooting

| Triệu chứng | Nguyên nhân | Cách fix |
|-------------|-------------|----------|
| Startup log "WARNING ... missing" | Thiếu API_URL hoặc API_KEY | Set đầy đủ env, restart |
| `ValueError` khi boot | `CHAINLENS_HEALTH_CACHE_TTL` không phải số | Set giá trị int hợp lệ (vd: `30`) |
| User vẫn không thấy Chainlens result | Health check fail (Chainlens down) | Check `curl ... /api/v1/b2b/health` |
| FE hiển thị "Chainlens" hoặc "fallback" | FR25 violation — bug | Báo cho dev team — KHÔNG được leak vendor name |

## Related

- Architecture: `_bmad-output/planning-artifacts/architecture.md` — section "Deep Research — Chainlens Integration Architecture"
- Service code: `nowing_backend/app/services/chainlens_research_service.py` (Story 7.1)
- Tool code: `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` (Story 7.2)
- Stream handler: `nowing_backend/app/tasks/chat/stream_new_chat.py` (Story 7.3)
````

### Testing Patterns

**CRITICAL:** `Config` class là singleton load env một lần ở module-import time. Để test thấy env var thay đổi, mỗi test PHẢI reload cả `app.config` và `app.app` sau `monkeypatch.setenv()`.

```python
# tests/unit/app/test_chainlens_config_validation.py
import importlib
import logging
import pytest
from unittest.mock import patch, MagicMock


def _reload_config_and_app():
    """Reload config singleton + app module after env change.
    
    Required because Config class reads env at module-load time.
    """
    import app.config
    import app.app
    importlib.reload(app.config)
    importlib.reload(app.app)
    return app.app._validate_chainlens_config


def test_disabled_logs_info(caplog, monkeypatch):
    """AC #5: ENABLED=false → INFO log 'DISABLED'."""
    monkeypatch.setenv("CHAINLENS_RESEARCH_ENABLED", "false")
    validator = _reload_config_and_app()
    
    with caplog.at_level(logging.INFO):
        validator()
    
    assert "DISABLED" in caplog.text
    # Must NOT have WARNING level records
    assert not any(r.levelname == "WARNING" for r in caplog.records)


def test_enabled_with_full_config_logs_enabled(caplog, monkeypatch):
    """AC #2: ENABLED=true + URL+KEY → INFO log 'ENABLED'."""
    monkeypatch.setenv("CHAINLENS_RESEARCH_ENABLED", "true")
    monkeypatch.setenv("CHAINLENS_RESEARCH_API_URL", "https://api.example.com")
    monkeypatch.setenv("CHAINLENS_RESEARCH_API_KEY", "test-key")
    validator = _reload_config_and_app()
    
    with caplog.at_level(logging.INFO):
        validator()
    
    assert "ENABLED" in caplog.text
    assert "https://api.example.com" in caplog.text


def test_enabled_missing_key_logs_warning(caplog, monkeypatch):
    """AC #3: ENABLED=true + missing KEY → WARNING."""
    monkeypatch.setenv("CHAINLENS_RESEARCH_ENABLED", "true")
    monkeypatch.setenv("CHAINLENS_RESEARCH_API_URL", "https://api.example.com")
    monkeypatch.delenv("CHAINLENS_RESEARCH_API_KEY", raising=False)
    validator = _reload_config_and_app()
    
    with caplog.at_level(logging.WARNING):
        validator()
    
    assert any(r.levelname == "WARNING" for r in caplog.records)
    assert "CHAINLENS_RESEARCH_API_KEY" in caplog.text


def test_enabled_missing_url_logs_warning(caplog, monkeypatch):
    """AC #4: ENABLED=true + missing URL → WARNING."""
    monkeypatch.setenv("CHAINLENS_RESEARCH_ENABLED", "true")
    monkeypatch.delenv("CHAINLENS_RESEARCH_API_URL", raising=False)
    monkeypatch.setenv("CHAINLENS_RESEARCH_API_KEY", "test-key")
    validator = _reload_config_and_app()
    
    with caplog.at_level(logging.WARNING):
        validator()
    
    assert any(r.levelname == "WARNING" for r in caplog.records)
    assert "CHAINLENS_RESEARCH_API_URL" in caplog.text


def test_validator_does_not_raise_on_exception(caplog, monkeypatch):
    """AC #8: validator wraps in try/except — never crash lifespan.
    
    Simulate a broken config access by patching the imported config object
    with a MagicMock that raises AttributeError on any attribute access.
    """
    monkeypatch.setenv("CHAINLENS_RESEARCH_ENABLED", "true")
    validator = _reload_config_and_app()
    
    # Replace the `config` name that `_validate_chainlens_config` imports at call time.
    # Since the function does `from app.config import config` INSIDE the body,
    # patch the source module.
    broken_config = MagicMock()
    # Accessing any attribute raises
    broken_config.CHAINLENS_RESEARCH_ENABLED = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    
    with patch("app.config.config", broken_config):
        # Must NOT raise — graceful degradation
        try:
            validator()
        except Exception:
            pytest.fail("Validator raised — must always be graceful")
```

**Lưu ý test isolation:** Mỗi test reload config — sẽ có side effect cho tests chạy sau nó. Dùng `pytest` fixture `autouse` cleanup để restore original env nếu cần:

```python
@pytest.fixture(autouse=True)
def _restore_env_after_test(monkeypatch):
    """Auto-restore env changes (monkeypatch đã handle, nhưng cần reload config lần cuối)."""
    yield
    importlib.reload(__import__("app.config"))
```

### Previous Story Intelligence

**Story 7.1 đã cung cấp:**
- 4 env vars trong `Config` class: `CHAINLENS_RESEARCH_ENABLED`, `CHAINLENS_RESEARCH_API_URL`, `CHAINLENS_RESEARCH_API_KEY`, `CHAINLENS_HEALTH_CACHE_TTL`
- Runtime fallback đã handle: `is_available()` return False khi flag tắt hoặc URL trống
- Story 7.4 chỉ cần ADD startup log layer (UX cho DevOps), runtime đã work sẵn

**Story 7.2 đã cung cấp:**
- Tool fallback tag `{"status": "fallback"}` 
- Tool docstring + system prompt instruct LLM gọi `generate_report` khi fallback
- Story 7.4 không cần touch tool layer

**Story 7.3 đã cung cấp:**
- Event handler emit "Deep researching" thinking step
- `research_status` event forward qua SSE
- Story 7.4 không cần touch event handler

**Tổng impact của Story 7.4:** chỉ thuần config/docs, không change runtime behavior nào (đã được handle qua 7.1-7.3).

### Project Structure Notes

- Story 7.4 là **last story** của Epic 7 — không có story tiếp theo phụ thuộc vào nó
- Khi 7.4 done → Epic 7 transition `done` (manual update sprint-status.yaml)
- Không có DB migration, không có API endpoint mới, không có FE change

### Dependencies

- **Story 7.1 PHẢI done trước** — Story 7.4 đọc 4 env vars từ `Config` class do 7.1 add
- 7.2 và 7.3 không phải prerequisite về mặt code, nhưng UX-wise nên done trước (để verify end-to-end khi rollback)

### NFR Compliance

- **No-Redeploy Toggle (FR26):** Achieved qua env var + restart (không cần rebuild image hay redeploy code)
- **FR25 Silent Fallback:** Reinforced — startup log dùng key prefix `[Chainlens]` chỉ ở backend log (không leak ra FE)

### Edge Cases cần handle

1. **`.env` không có `CHAINLENS_RESEARCH_ENABLED`**: Story 7.1 default = `"FALSE"` → ENABLED=False → log "DISABLED" (case AC #5 vẫn đúng)
2. **`CHAINLENS_RESEARCH_ENABLED` value lạ** (vd: "1", "yes", "True"): Story 7.1 chỉ accept `"TRUE"` (uppercase) → các value khác → ENABLED=False → log DISABLED. Cần document trong README để DevOps biết phải dùng `true`/`TRUE`.
3. **`CHAINLENS_HEALTH_CACHE_TTL` không phải số**: Story 7.1 dùng `int()` → `ValueError` raise ở module load → service crash. Document trong troubleshooting.
4. **Hot reload env (không restart)**: KHÔNG support — env chỉ được đọc 1 lần khi `Config` class load. Phải restart service. Document rõ trong README.

### References

- Epics file: `_bmad-output/planning-artifacts/epics.md` — Story 7.4 section
- Architecture: `_bmad-output/planning-artifacts/architecture.md` — section "Configuration"
- Story 7.1 (dependency): `_bmad-output/implementation-artifacts/7-1-chainlens-research-service-health-check.md`
- Story 7.2 (related): `_bmad-output/implementation-artifacts/7-2-chainlens-deep-research-langgraph-tool.md`
- Story 7.3 (related): `_bmad-output/implementation-artifacts/7-3-agent-intent-detection-streaming.md`
- Lifespan pattern: `nowing_backend/app/app.py` dòng 20-32
- `.env.example` reference: `nowing_backend/.env.example` (Residential Proxy section là pattern gần nhất)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

- `types.SimpleNamespace` mock approach used for Task 4 unit tests — avoids `load_dotenv` interference from `.env` file at module load time
- `app.services.chainlens_research_service.config` must be patched (not `app.config.config`) for Task 5 integration tests — service imports `config` at module level

### Completion Notes List

- All 5 tasks completed; 11 unit + integration tests pass
- Story 7.4 is the final story of Epic 7 — all ACs verified

### File List

- `nowing_backend/app/app.py` (edited — add `_validate_chainlens_config()` helper + lifespan call)
- `nowing_backend/.env.example` (edited — add Chainlens section at end)
- `docs/chainlens-integration.md` (new — DevOps guide, flat layout)
- `docs/index.md` (edited — add Chainlens integration link)
- `nowing_backend/tests/unit/app/test_chainlens_config_validation.py` (new — 6 unit tests)
- `nowing_backend/tests/unit/app/test_chainlens_rollback_integration.py` (new — 5 integration tests)

### Review Findings

- [x] [Review][Patch] Whitespace-only API_KEY/URL bypasses validator intent [nowing_backend/app/services/chainlens_research_service.py:42,87] — validator `.strip()`s but `is_available()`/`research()` don't, so whitespace KEY/URL lets the service attempt real HTTP with `Bearer    ` header → 401 + cooldown noise, contradicting FR25 silent fallback
- [x] [Review][Patch] Grammar: two-item missing list reads "X, Y are missing" [nowing_backend/app/app.py:53-58] — should use "and" (affects log regex / operator alerts)
- [x] [Review][Patch] Doc claim that only `true`/`TRUE` accepted is misleading [docs/chainlens-integration.md:Troubleshooting] — Story 7.1's `.upper() == "TRUE"` means `True`/`tRuE`/etc. all work; doc should say "case-insensitive `true`"
- [x] [Review][Defer] `CHAINLENS_HEALTH_CACHE_TTL ≤ 0` → DoS amplifier (every `is_available()` call hits network) — deferred, pre-existing Story 7.1 behavior, no clamp
- [x] [Review][Defer] Validator runs late in lifespan — if `seed_nowing_docs()` raises, the audit log never emits — deferred, lifespan ordering is pre-existing architecture
- [x] [Review][Defer] API URL logged at INFO with no sanitizer — credential leak risk if operator embeds basic-auth/token in URL — deferred, speculative low-probability
- [x] [Review][Defer] `asyncio.Lock` created at class-definition time — cross-event-loop hazard in pytest-asyncio — deferred, pre-existing Story 7.1
- [x] [Review][Defer] No regression guard for local `from app.config import config` inside validator — if future refactor hoists it, all 9 unit tests silently pass but `patch("app.config.config", ...)` stops affecting the validator — deferred, acceptable safety net via existing `test_lifespan_calls_validate_chainlens_config`
