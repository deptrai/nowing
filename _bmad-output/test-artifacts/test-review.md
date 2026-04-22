# Test Review Report — API Test Suite

**Date:** 2026-04-22  
**Reviewer:** Murat (TEA — Test Architect)  
**Scope:** `nowing_backend/tests/api/`  
**Files reviewed:** `test_auth_api.py`, `test_search_spaces_api.py`, `test_stripe_api.py`, `test_example.py`, `conftest.py`  
**Total tests:** 34

---

## Overall Score: 79 / 100 — C+

| Dimension       | Weight | Score | Grade |
|-----------------|--------|-------|-------|
| Determinism     | 30%    | 85    | B     |
| Isolation       | 30%    | 72    | C     |
| Maintainability | 25%    | 80    | B     |
| Performance     | 15%    | 78    | C+    |

**Weighted total:** (85×0.30) + (72×0.30) + (80×0.25) + (78×0.15) = **79.2**

---

## Findings

### 🔴 HIGH — P0 Blockers

#### H1 — No teardown after CRUD tests (`test_search_spaces_api.py`)
- **Dimension:** Isolation
- **Risk:** Tests that create SearchSpaces do not delete them. With a shared DB and `-n auto` parallel execution, leftover rows can cause `len(body) >= 1` assertions to pass vacuously, and name collisions across runs.
- **Location:** `test_list_search_spaces_returns_list`, `test_create_search_space_returns_200`, and all CRUD helpers
- **Fix:**
  ```python
  # In conftest.py — add a session-scoped cleanup or use unique names via uuid
  import uuid
  
  async def _create_space(client, headers, name=None, ...):
      name = name or f"Test-{uuid.uuid4().hex[:8]}"
      ...
  
  # Or yield-fixture with teardown:
  @pytest_asyncio.fixture
  async def test_space(api_client, auth_headers):
      space = await _create_space(api_client, auth_headers)
      yield space
      await api_client.delete(f"/api/v1/searchspaces/{space['id']}", headers=auth_headers)
  ```

#### H2 — `auth_headers` is function-scoped → N×login overhead
- **Dimension:** Performance / Isolation
- **Risk:** Every test that uses `auth_headers` performs a full login round-trip. With 25+ tests using this fixture, that's 25+ `/auth/jwt/login` calls per CI run — adds ~10–30s and hammers the auth stack unnecessarily.
- **Location:** `conftest.py` — `auth_headers` fixture
- **Fix:** Upgrade to `session` scope (safe because access token is read-only within a test session):
  ```python
  @pytest_asyncio.fixture(scope="session")
  async def auth_headers(api_client: AsyncClient) -> dict[str, str]:
      ...
  ```
  > ⚠️ `api_client` must also be `session`-scoped for this to work. Check `conftest.py` scope chain.

---

### 🟡 MEDIUM — Technical Debt

#### M1 — `import os` inside test function bodies
- **Dimension:** Maintainability
- **Location:** `test_auth_api.py:test_login_valid_credentials_returns_tokens`, `test_login_invalid_password_returns_400`
- **Fix:** Move to module-level imports at the top of the file.

#### M2 — Assertion inside `_create_space()` helper
- **Dimension:** Maintainability / Determinism
- **Location:** `test_search_spaces_api.py:_create_space()` line 35
- **Issue:** `assert response.status_code == 200, f"create failed: {response.text}"` — assertions in helpers make failure attribution ambiguous. Pytest reports the failure at the helper, not the test.
- **Fix:** Return the response and let the caller assert, or raise a descriptive `RuntimeError` instead.

#### M3 — Misleading markers in `test_example.py`
- **Dimension:** Maintainability
- **Location:** `test_example.py` — `test_health_check` and `test_unauthenticated_returns_401` marked `@pytest.mark.unit` but use `api_client` fixture (requires running app)
- **Fix:** Change to `@pytest.mark.api` or move to a `test_smoke.py` file.

#### M4 — Hardcoded test data names (no uniqueness guarantee)
- **Dimension:** Isolation
- **Location:** Throughout `test_search_spaces_api.py` — `"API Test Space"`, `"List Test Space"`, etc.
- **Risk:** Parallel test runs (`-n auto`) on shared DB may collide on unique constraints.
- **Fix:** Append `uuid4().hex[:6]` to names, or use a `faker` fixture.

#### M5 — `test_example.py` duplicates coverage already in other files
- **Dimension:** Maintainability
- **Issue:** `test_authenticated_endpoint` and `test_unauthenticated_returns_401` in `test_example.py` test the same endpoint with the same logic as `test_auth_api.py`.
- **Fix:** Delete `test_example.py` or repurpose it as a true smoke/health check file.

#### M6 — `auth_headers` not reused via fixture chain in `test_revoke_token_returns_200`
- **Dimension:** Isolation
- **Location:** `test_auth_api.py:test_revoke_token_returns_200`
- **Issue:** Test revokes a token from `auth_headers`, then `test_logout_all_returns_200` tries to use the same (now-invalid) fixture. Function-scope partially masks this, but session-scope would break it.
- **Fix:** Create a separate `one_time_auth_headers` fixture for destructive token tests.

---

### 🔵 LOW — Nits

#### L1 — `assert response.status_code in (200, 503)` in delete test
- **Location:** `test_search_spaces_api.py:test_delete_search_space_returns_200`
- **Issue:** Accepting 503 as valid exit silently hides missing background worker in CI. Should be 200-only once worker lifecycle is handled in test env, or explicitly mark `xfail` with a reason.

#### L2 — Parallel execution with shared DB (`-n auto` in `addopts`)
- **Location:** `pyproject.toml` — `addopts = "... -n auto"`
- **Issue:** `api` tests write to a shared DB. Running them in parallel without DB isolation (separate schemas or txn rollback) risks race conditions.
- **Fix (short-term):** Add `-p no:xdist` override in the `api-tests` CI step (already done: `uv run pytest -m api` overrides `addopts`). Confirm `-n auto` is NOT inherited when running `pytest -m api` directly.

---

## Priority Fix Order

| Priority | Finding | Effort | Impact |
|----------|---------|--------|--------|
| 1 | H2 — session-scope `auth_headers` | Low (1 line) | High |
| 2 | H1 — CRUD teardown / unique names | Medium | High |
| 3 | M1 — `import os` at module level | Trivial | Low |
| 4 | M2 — remove assertion from `_create_space()` | Low | Medium |
| 5 | M3 — fix misleading markers in `test_example.py` | Trivial | Medium |
| 6 | M5 — delete/repurpose `test_example.py` | Low | Medium |
| 7 | M6 — separate fixture for destructive token tests | Medium | Medium |
| 8 | L1 — remove 503 fallback in delete test | Low | Low |

---

## What's Working Well ✅

- **Test naming:** Descriptive, follows `test_<action>_<context>_returns_<expected>` convention consistently
- **Coverage spread:** Auth, CRUD, RBAC, unauthenticated guard, filter params — good P0/P1 distribution
- **CI pipeline:** Alembic migration + seed user step correctly ordered; script injection prevented via `env:` intermediaries
- **Marker discipline:** All `api` tests correctly registered and filtered; `--strict-markers` won't fail
- **No hardcoded secrets:** `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` sourced from GitHub Secrets

---

*Generated by Murat — TEA (Test Architect) | BMAD framework*
