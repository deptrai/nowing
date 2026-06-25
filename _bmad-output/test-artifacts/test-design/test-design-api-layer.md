# Test Design — API Layer Coverage Strategy

**Ngày:** 2026-04-22  
**Kiến trúc sư:** Murat (TEA — Test Architect)  
**Scope:** Toàn bộ API surface — `nowing_backend/app/routes/`  
**Trigger:** Coverage gap được phát hiện từ RV report (79/100, C+)  
**Mode:** Epic-Level — tất cả 7 epics đã `done`, retrospective + gap-fill

---

## 1. API Surface Inventory

| Domain | Route File | Size | Tests hiện có | Test File |
|--------|-----------|------|---------------|-----------|
| Auth | `auth_routes.py` | 2.8KB | 11 tests | `test_auth_api.py` ✅ |
| SearchSpaces | `search_spaces_routes.py` | 28KB | 11 tests | `test_search_spaces_api.py` ⚠️ |
| Stripe/Billing | `stripe_routes.py` | 54KB | 12 tests | `test_stripe_api.py` ⚠️ |
| Documents | `documents_routes.py` | 62KB | 0 | — 🔴 |
| Chat/RAG | `new_chat_routes.py` | 57KB | 0 | — 🔴 |
| RBAC | `rbac_routes.py` | 36KB | 0 | — 🔴 |
| Admin | `admin_routes.py` | 13KB | 0 | — 🔴 |
| Connectors | `search_source_connectors_routes.py` | 136KB | 0 | — 🔴 |
| Folders | `folders_routes.py` | 17KB | 0 | — 🔴 |
| Notes/Editor | `notes_routes.py`, `editor_routes.py` | 22KB | 0 | — 🟡 |
| Export | `export_routes.py` | 1.9KB | 0 | — 🟡 |
| LLM Config | `new_llm_config_routes.py` | 12KB | 0 | — 🟡 |
| Memory | `memory_routes.py` | 4.9KB | 0 | — 🟡 |
| Chat Comments | `chat_comments_routes.py` | 3.4KB | 0 | — 🟡 |
| Public Chat | `public_chat_routes.py` | 7.9KB | 0 | — 🟡 |
| Reports | `reports_routes.py` | 17KB | 0 | — 🟡 |
| Image Gen | `image_generation_routes.py` | 23KB | 0 | — 🟡 |
| 15+ Connectors | `*_add_connector_route.py` | varies | 0 | — 🟡 |

**Tổng:** 34 tests / ~30 route files. **Gap ước tính: >80% API surface chưa có test.**

---

## 2. Risk Assessment Matrix

> **Công thức:** Risk = Probability (1–3) × Impact (1–3)  
> **Thang điểm:** 1–2 = DOCUMENT | 3–4 = MONITOR | 5–6 = MITIGATE | 7–9 = BLOCK

| Domain | P | I | Risk Score | Mức độ | Lý do |
|--------|---|---|-----------|--------|-------|
| **RBAC** | 3 | 3 | **9** | 🔴 BLOCK | Zero tests; sai RBAC = data leak giữa users. Security P0. |
| **Chat/RAG** | 3 | 3 | **9** | 🔴 BLOCK | Core feature; SSE, streaming, context window — nhiều code path phức tạp. Revenue-critical. |
| **Documents/Upload** | 3 | 3 | **9** | 🔴 BLOCK | Celery worker, file parsing, ETL pipeline — zero test coverage. Epic-2 core. |
| **Auth** *(existing)* | 1 | 3 | **3** | ✅ DOCUMENT | Covered tốt, nhưng H2 (session-scope) và M6 (destructive token) chưa fix. |
| **SearchSpaces** *(existing)* | 2 | 3 | **6** | 🟠 MITIGATE | Covered nhưng H1 (no teardown) + H2 chưa fix. Data leak giữa test runs. |
| **Stripe/Billing** *(existing)* | 2 | 3 | **6** | 🟠 MITIGATE | Webhook sig verification và billing portal có acceptance too broad (in 200,400,500). |
| **Admin** | 2 | 3 | **6** | 🟠 MITIGATE | Admin-only endpoints — superuser gate phải được test. No tests hiện tại. |
| **Folders** | 2 | 2 | **4** | 🟡 MONITOR | CRUD + permission scoped — tương tự SearchSpaces nhưng ít user-facing hơn. |
| **Gift Codes** | 2 | 2 | **4** | 🟡 MONITOR | Redemption logic nằm trong stripe_routes. Đã có 2 tests nhưng còn thiếu double-use guard. |
| **Notes/Editor** | 1 | 2 | **2** | 📄 DOCUMENT | Low complexity, low coupling. |
| **Memory** | 1 | 2 | **2** | 📄 DOCUMENT | Session-scoped context, minimal blast radius. |
| **Export** | 1 | 1 | **1** | 📄 DOCUMENT | Output-only, no side effects. |
| **Connectors** | 2 | 1 | **2** | 📄 DOCUMENT | External service dependent; mock-heavy, diminishing returns cho API layer. |
| **LLM Config** | 1 | 2 | **2** | 📄 DOCUMENT | Config CRUD, thấp impact. |
| **Image Gen** | 1 | 2 | **2** | 📄 DOCUMENT | External AI calls, khó test ở API layer thuần. |

---

## 3. Gap Analysis & Priority Matrix

### P0 — BLOCK (phải làm trước khi merge tiếp)

#### Gap 1: RBAC API — Zero coverage [Risk 9]
- **Không có test nào** verify permission boundary giữa users
- `test_get_search_space_non_member_returns_403` hiện tại dùng ID offset synthetic — không phải real RBAC test
- **Cần:** Two-user fixture + real ownership scenario

#### Gap 2: Document Upload API — Zero coverage [Risk 9]  
- Endpoint upload → ETL → indexing là core value proposition của product
- Không có smoke test cho upload path, file validation, size limits
- **Cần:** Upload happy path + rejection cases (wrong type, oversized)

#### Gap 3: Chat/RAG API — Zero coverage [Risk 9]
- Toàn bộ chat functionality (create, message, SSE stream, context) không có test
- Revenue-critical: người dùng trả tiền để dùng chat
- **Cần:** Create conversation, send message, basic response guard

### P1 — MITIGATE (sprint hiện tại)

#### Gap 4: Fix isolation issues trong existing tests (từ RV)
- H1: Add teardown/uuid names trong `test_search_spaces_api.py`
- H2: Upgrade `auth_headers` lên `session` scope
- M6: Tách `one_time_auth_headers` fixture cho destructive token tests

#### Gap 5: Admin API — Zero coverage [Risk 6]
- Superuser-only endpoints phải có explicit 403 test cho regular user
- **Cần:** Auth gate test (regular user → 403) cho tất cả admin routes

#### Gap 6: Stripe webhook — acceptance quá rộng
- `test_webhook_invalid_signature_returns_400`: chấp nhận cả 403 — nên lock xuống 400
- `test_billing_portal_no_customer_id_returns_400`: chấp nhận 200/400/404/500 — quá permissive

### P2 — MONITOR (next sprint)

#### Gap 7: Folders API
- CRUD + permission model tương tự SearchSpaces
- 1 test file mới, ~8-10 tests

#### Gap 8: Gift code double-redemption guard
- Code bị dùng 2 lần phải return 409 hoặc 400
- Hiện tại: chỉ test invalid code (404)

---

## 4. Test Strategy per Domain

### 4.1 RBAC API — Chiến lược two-user [P0]

**Vấn đề cốt lõi:** Không thể test real RBAC với 1 user.

**Giải pháp — Two-user fixture:**
```python
# conftest.py thêm vào
@pytest_asyncio.fixture(scope="session")  
async def second_user_headers(api_client: AsyncClient) -> dict[str, str]:
    """Headers cho user thứ 2 — dùng để test cross-user isolation."""
    # Seed second user trong CI hoặc dùng existing second test account
    email = os.environ.get("TEST_USER2_EMAIL", "test2@nowing.test")
    password = os.environ.get("TEST_USER2_PASSWORD", "test-password-2")
    ...
```

**Test cases cần viết (`test_rbac_api.py`):**

| Test | Mức | Assertion |
|------|-----|-----------|
| User A tạo space, User B GET → 403 | P0 | status 403 |
| User A tạo space, User B DELETE → 403 | P0 | status 403 |
| User A mời User B → User B GET → 200 | P1 | status 200 |
| User A kick User B → User B GET → 403 | P1 | status 403 |
| Non-member POST document → 403 | P0 | status 403 |

**Ước tính:** 8-12 tests, 1-2 ngày implement (cần CI secret thứ 2).

---

### 4.2 Documents API — Smoke tests [P0]

**Scope:** Upload flow, không test ETL sâu (integration test territory).

**Strategy:** Mock Celery task dispatch, test HTTP contract.

```python
# test_documents_api.py
@pytest.fixture
def mock_celery(mocker):
    return mocker.patch("app.tasks.process_document.delay", return_value=Mock(id="task-123"))
```

**Test cases cần viết:**

| Test | Mức | Assertion |
|------|-----|-----------|
| Upload PDF hợp lệ → 200/202 + {document_id} | P0 | status in (200, 202) |
| Upload không auth → 401 | P0 | status 401 |
| Upload wrong MIME type → 400/422 | P0 | status in (400, 422) |
| Upload file quá lớn → 413 | P1 | status 413 |
| GET document by id → 200 + metadata | P0 | status 200 |
| GET document không phải member → 403 | P0 | status 403 |
| DELETE document → 200/202 | P1 | status in (200, 202) |
| List documents in space → 200 + list | P0 | isinstance(body, list) |

**Ước tính:** 10-14 tests, 2-3 ngày (cần tạo test PDF fixture).

---

### 4.3 Chat/RAG API — Smoke + contract [P0]

**Scope:** HTTP contract chỉ. Không test RAG quality (không deterministic).

**SSE challenge:** SSE endpoint trả về `text/event-stream` — httpx không handle native. Cần collect và parse events.

```python
# Helper cho SSE collection
async def collect_sse_events(client, url, headers, timeout=10):
    events = []
    async with client.stream("POST", url, headers=headers, ...) as r:
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events
```

**Test cases cần viết:**

| Test | Mức | Assertion |
|------|-----|-----------|
| POST /chat/conversations → 200 + {id} | P0 | has conversation_id |
| POST message (non-streaming) → 200 + response | P0 | status 200, has content |
| POST message no auth → 401 | P0 | status 401 |
| POST message SSE → stream opens, events emitted | P0 | len(events) > 0 |
| POST message vào space không phải member → 403 | P0 | status 403 |
| GET chat history → 200 + list | P1 | isinstance(body, list) |

**Ước tính:** 8-10 tests, 2-3 ngày (SSE helper phức tạp).

---

### 4.4 Admin API — Auth gate [P1]

**Strategy đơn giản:** Chỉ verify auth gate. Không test business logic admin (cần superuser fixture riêng).

**Test cases cần viết (`test_admin_api.py`):**

| Test | Mức | Assertion |
|------|-----|-----------|
| Regular user GET /admin/* → 403 | P0 | status 403 |
| No auth GET /admin/* → 401 | P0 | status 401 |
| Superuser GET /admin/* → 200 | P1 | status 200 (cần superuser fixture) |

**Ước tính:** 5-8 tests, 1 ngày.

---

### 4.5 Existing Tests — Fix isolation [P1]

Từ RV findings H1, H2, M6 (chi tiết trong `test-review.md`):

**Thứ tự fix:**
1. Upgrade `auth_headers` → `scope="session"` + upgrade `api_client` → `scope="session"` (1 line each)
2. Thêm `uuid4().hex[:8]` vào tất cả hardcoded space names
3. Thêm yield-fixture teardown hoặc DELETE sau mỗi CRUD test
4. Tách `one_time_auth_headers` fixture cho `test_revoke_token_returns_200`

---

## 5. Implementation Roadmap

### Sprint hiện tại (tuần này)

| Việc | File | Effort | Risk giảm |
|------|------|--------|-----------|
| Fix H2: session-scope auth_headers | `conftest.py` | 30 phút | Performance +20% |
| Fix H1: uuid names + teardown | `test_search_spaces_api.py` | 2 giờ | Isolation BLOCK → MONITOR |
| Fix M6: one_time_auth_headers | `conftest.py`, `test_auth_api.py` | 1 giờ | Isolation gap đóng |
| Fix M1: move imports | `test_auth_api.py` | 15 phút | Maintainability |
| Xóa/repurpose test_example.py | `test_example.py` | 30 phút | Duplicate coverage |

### Tuần tới (P0 gaps)

| Việc | File mới | Effort |
|------|---------|--------|
| RBAC two-user fixture + 10 tests | `test_rbac_api.py` + `conftest.py` | 2 ngày |
| Document upload smoke tests | `test_documents_api.py` | 2-3 ngày |

### Sprint +2 (P1 gaps)

| Việc | File mới | Effort |
|------|---------|--------|
| Chat/RAG + SSE helper + 8 tests | `test_chat_api.py` | 2-3 ngày |
| Admin auth gate tests | `test_admin_api.py` | 1 ngày |
| Tighten Stripe webhook assertions | `test_stripe_api.py` | 2 giờ |

### Sprint +3 (P2 gaps)

| Việc | File mới | Effort |
|------|---------|--------|
| Folders CRUD tests | `test_folders_api.py` | 1 ngày |
| Gift code double-use guard | `test_stripe_api.py` | 2 giờ |

---

## 6. Coverage Projection

| Thời điểm | Tests | Domains covered | API Risk Level |
|-----------|-------|-----------------|----------------|
| **Hiện tại** | 34 | 3/18 | 🔴 HIGH (3×BLOCK gaps) |
| Sau sprint hiện tại | 34 (quality up) | 3/18 | 🟠 MEDIUM (isolation fixed) |
| Sau tuần tới | ~60 | 5/18 | 🟠 MEDIUM (P0 gaps closed) |
| Sau sprint +2 | ~80 | 7/18 | 🟡 LOW-MEDIUM |
| Sau sprint +3 | ~95 | 9/18 | 🟢 ACCEPTABLE |

**Target:** ≥ 9 domains covered với P0 assertions trên tất cả revenue paths.

---

## 7. Fixture Architecture (Target State)

```
conftest.py (session scope)
├── api_client          [scope="session"] ← cần upgrade
├── auth_headers        [scope="session"] ← cần upgrade  
├── second_user_headers [scope="session"] ← cần tạo mới (RBAC)
├── superuser_headers   [scope="session"] ← cần tạo mới (Admin)
└── one_time_auth_headers [scope="function"] ← cần tạo mới (destructive tests)

helpers/
├── sse_collector.py    ← cần tạo mới (Chat tests)
└── test_fixtures/
    └── sample.pdf      ← cần tạo mới (Document tests)
```

---

## 8. CI Considerations

- **Secrets cần thêm:** `TEST_USER2_EMAIL`, `TEST_USER2_PASSWORD` (cho RBAC two-user tests)
- **Seed script mở rộng:** Thêm second user seed trong `api-tests` job
- **Timeout:** Chat/SSE tests có thể chậm — thêm `@pytest.mark.timeout(30)` 
- **Marker mới đề xuất:** `@pytest.mark.rbac` để isolate RBAC tests khi cần debug

---

## 9. Gate Decision

**Tình trạng hiện tại: ❌ KHÔNG ĐẠT P0 threshold**

> Coverage rule: P0 flows (auth, RBAC, core feature) phải có ≥1 happy-path + ≥1 auth-gate test.

| Domain P0 | Happy path | Auth gate | Verdict |
|-----------|-----------|-----------|---------|
| Auth | ✅ | ✅ | PASS |
| SearchSpaces | ✅ | ✅ | PASS (isolation issue) |
| RBAC | ❌ | ❌ | **FAIL** |
| Documents | ❌ | ❌ | **FAIL** |
| Chat | ❌ | ❌ | **FAIL** |

**Recommendation:** Chặn merge feature branches mới cho đến khi 3 P0 domains được cover.  
Có thể cấu hình `test-gate` trong CI hiện tại để enforce via path-based triggers.

---

*Generated by Murat — TEA (Test Architect) | BMAD framework | 2026-04-22*
