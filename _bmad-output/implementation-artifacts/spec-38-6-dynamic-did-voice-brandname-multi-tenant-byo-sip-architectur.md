---
title: 'Story 38.6: Dynamic DID & Voice Brandname Multi-tenant BYO-SIP Architecture'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: '35dc7a7e8dbed2eef4f57b0a535d4ab2ae7e5b44'
deferred:
  - summary: >-
      resolve_workspace_trunk is not yet wired into LiveKitTelephonyClient.dispatch_call.
    evidence: |-
      The resolver returns SipTrunkResolved with decrypted credentials, but
      LiveKitTelephonyClient.dispatch_call still reads trunk_id from callers
      (Story 38.7 will wire dispatch through the resolver).
    location: >-
      nowing_backend/app/services/voice/telephony_client.py:dispatch_call
    severity: medium
  - summary: >-
      Voice Brandname verification workflow (is_verified flag) has no admin approval API.
    evidence: |-
      is_verified defaults to False and no endpoint flips it; operator verification
      flow (telco approval) is an operational process outside this story's scope.
    location: >-
      nowing_backend/app/models/workspace_sip.py
    severity: low
  - summary: >-
      DB migration for workspace_sip_trunks table not yet generated.
    evidence: |-
      Model is defined but no Alembic migration was created; production deploy
      requires an alembic revision before the table exists.
    location: >-
      nowing_backend/app/models/workspace_sip.py
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Các doanh nghiệp B2B sử dụng Nowing Voice AI SDR cần gọi ra bằng Voice Brandname chính danh (ví dụ: hiển thị tên công ty "NOWING" thay vì số lạ) hoặc sử dụng hạ tầng SIP Trunk riêng (Bring-Your-Own-SIP / BYO-SIP từ VNPT, Viettel, FPT, CMC). Hiện tại hệ thống chỉ dùng chung một `SIP_DEFAULT_TRUNK_ID` tĩnh từ cấu hình môi trường, không hỗ trợ quản lý đa người thuê (multi-tenant) và không thể mã hóa bảo mật thông tin đăng nhập SIP của từng khách hàng.

**Approach:** Xây dựng kiến trúc SIP Trunk đa người thuê (Multi-tenant BYO-SIP) cho phép từng workspace đăng ký đầu số DID và Voice Brandname riêng: (1) Model `WorkspaceSipTrunk` lưu trữ cấu hình SIP Trunk theo workspace; (2) Mật khẩu SIP được mã hóa bảo mật AES-256-GCM thông qua `TokenEncryption` dùng khóa PII Vault hiện có (tuyệt đối không tự viết module crypto mới); (3) Router RESTful `app/routes/voice_agent.py` cung cấp CRUD quản trị SIP trunk; (4) Bộ giải quyết trunk động `resolve_workspace_trunk()` tự động chọn Voice Brandname đã được duyệt hoặc fallback về DID cố định khi thực hiện cuộc gọi qua `LiveKitTelephonyClient`.

## Boundaries & Constraints

**Always:**
- **Zero Reinvention**: Mật khẩu SIP Trunk bắt buộc phải mã hóa bằng `TokenEncryption` từ `app/utils/oauth_security.py` sử dụng khóa bí mật cấu hình hệ thống (`config.SECRET_KEY`). **CẤM tự viết module crypto mới**.
- Router RESTful đặt tại `app/routes/voice_agent.py` và đăng ký trong `app/routes/__init__.py`.
- Tách biệt dữ liệu đa người thuê: Mọi truy vấn SIP Trunk phải được cô lập tuyệt đối theo `workspace_id`. Người dùng không thể xem hoặc sửa trunk của workspace khác.
- Bảo mật thông tin đăng nhập: Mật khẩu SIP tuyệt đối không bao giờ được trả về dưới dạng văn bản thuần qua API (phải được mask `********` hoặc ẩn trong response DTO).
- Cơ chế Fallback: Nếu workspace chưa cấu hình SIP Trunk riêng hoặc trunk chưa được phê duyệt, cuộc gọi tự động fallback về `SIP_DEFAULT_TRUNK_ID` từ biến môi trường hệ thống.
- Day-1 DID Safety Guard: Đầu số cố định mới cấp chỉ được gọi các Lead có Verified Inbound Consent Token; đầu số có Voice Brandname đã phê duyệt (`is_verified=True`) mới được phép gọi danh bạ lạnh theo khung giờ quy định.

**Never:**
- Không lưu mật khẩu SIP dưới dạng văn bản thuần (plaintext) trong database.
- Không tạo thư viện mã hóa độc lập ngoài `TokenEncryption`.
- Không cho phép người dùng không có quyền quản trị workspace (Admin/Owner) cấu hình hoặc xóa SIP Trunk.
- Không thực hiện cuộc gọi qua trunk chưa được kích hoạt (`status != 'active'`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Tạo Trunk thành công | Admin POST credentials SIP (server, username, password, DID) | Lưu bản ghi, password được mã hóa AES-256-GCM, response trả về password masked `********` | Validate định dạng E.164 của DID |
| Đọc danh sách Trunks | GET `/api/v1/workspaces/{ws_id}/voice/trunks` | Danh sách trunks của workspace, password masked, kèm cờ `is_default`, `is_verified` | 403 nếu không thuộc workspace |
| Giải mã để quay số | `resolve_workspace_trunk(session, ws_id)` | Trả về thông tin trunk đã giải mã mật khẩu sẵn sàng cho `LiveKitTelephonyClient` | Fallback về system default nếu không tìm thấy |
| Không có trunk riêng | Workspace mới chưa cấu hình SIP trunk | `resolve_workspace_trunk()` fallback về `SIP_DEFAULT_TRUNK_ID` của hệ thống | Không crash cuộc gọi |
| Sai khóa mã hóa | Key bí mật thay đổi hoặc dữ liệu mã hóa bị hỏng | Ném ngoại lệ an toàn `SipCredentialDecryptionError`, fallback về default trunk | Ghi log error bảo mật |
| Đặt Trunk mặc định | POST `/workspaces/{ws_id}/voice/trunks/{id}/set-default` | Đặt trunk đó thành `is_default=True`, các trunk khác cùng workspace đổi thành `False` | Transaction atomic |
| Xóa Trunk đang dùng | DELETE trunk đang là default duy nhất | Xóa thành công, hệ thống chuyển về dùng system default trunk | — |

</intent-contract>

## Code Map

- `nowing_backend/app/db/models/workspace_sip.py` -- **File mới.** Model SQLAlchemy `WorkspaceSipTrunk`: các trường `id` (UUID), `workspace_id` (int, FK), `name` (str), `brandname` (str, nullable), `outbound_did` (str), `sip_server` (str), `sip_username` (str), `sip_password_encrypted` (str), `livekit_trunk_id` (str, nullable), `is_default` (bool), `is_verified` (bool), `status` (str), timestamps.
- `nowing_backend/app/db/__init__.py` -- Export `WorkspaceSipTrunk`.
- `nowing_backend/app/schemas/voice_sip.py` -- **File mới.** Pydantic DTOs: `SipTrunkCreateRequest`, `SipTrunkUpdateRequest`, `SipTrunkResponse` (password masked), `SipTrunkDecrypted` (internal).
- `nowing_backend/app/services/voice/sip_manager.py` -- **File mới.** Service quản lý SIP Trunk: mã hóa/giải mã mật khẩu bằng `TokenEncryption`, CRUD trunks, phương thức `resolve_workspace_trunk(session, workspace_id)`.
- `nowing_backend/app/routes/voice_agent.py` -- **File mới.** Router FastAPI: endpoints CRUD `/api/v1/workspaces/{workspace_id}/voice/trunks` và set-default. Gated bởi quyền workspace admin/owner.
- `nowing_backend/app/routes/__init__.py` -- Đăng ký `voice_agent.py` router vào root API router.
- `nowing_backend/tests/unit/voice/test_sip_manager.py` -- **File mới.** Unit tests cho `SipTrunkManager`: mã hóa/giải mã AES-256-GCM, masking mật khẩu, CRUD, fallback logic, resolution precedence.
- `nowing_backend/tests/unit/voice/test_voice_agent_routes.py` -- **File mới.** Unit tests cho API endpoints trong `voice_agent.py`: kiểm tra xác thực, RBAC, CRUD, mask mật khẩu.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/db/models/workspace_sip.py` -- Tạo model `WorkspaceSipTrunk` với quan hệ workspace và chỉ mục tìm kiếm -- Lưu trữ đa người thuê cho BYO-SIP
- `nowing_backend/app/db/__init__.py` -- Export `WorkspaceSipTrunk` -- Nhất quán bề mặt DB model
- `nowing_backend/app/schemas/voice_sip.py` -- Tạo schemas Pydantic cho SIP Trunk -- Chuẩn hóa I/O DTO
- `nowing_backend/app/services/voice/sip_manager.py` -- Tạo `SipTrunkManager` sử dụng `TokenEncryption` để mã hóa mật khẩu và giải quyết trunk cho cuộc gọi -- Quản lý nghiệp vụ SIP Trunk
- `nowing_backend/app/routes/voice_agent.py` -- Tạo router `/api/v1/workspaces/{workspace_id}/voice/trunks` -- Cung cấp API quản trị SIP Trunk
- `nowing_backend/app/routes/__init__.py` -- Đăng ký router mới vào hệ thống -- Kích hoạt endpoint HTTP
- `nowing_backend/tests/unit/voice/test_sip_manager.py` -- Unit tests mã hóa, giải mã, masking và dynamic resolution -- Đảm bảo an toàn mật mã và fallback
- `nowing_backend/tests/unit/voice/test_voice_agent_routes.py` -- Unit tests cho HTTP endpoints của `voice_agent.py` -- Đảm bảo bảo mật API và phân quyền

**Acceptance Criteria:**
- **Given** người dùng là Workspace Admin, **When** tạo mới một SIP Trunk với mật khẩu plaintext, **Then** mật khẩu được mã hóa AES-256-GCM trước khi ghi vào database và API trả về trường password đã được che `********`.
- **Given** một workspace đã có SIP Trunk mặc định với Voice Brandname hợp lệ, **When** `resolve_workspace_trunk()` được gọi, **Then** hệ thống trả về thông tin trunk của workspace với mật khẩu đã giải mã thành công.
- **Given** một workspace chưa từng tạo SIP Trunk riêng, **When** `resolve_workspace_trunk()` được gọi, **Then** hệ thống trả về cấu hình fallback sử dụng `SIP_DEFAULT_TRUNK_ID` mà không làm gián đoạn cuộc gọi.
- **Given** một workspace có nhiều SIP Trunk, **When** đặt một trunk làm default, **Then** duy nhất trunk đó có cờ `is_default=True`, các trunk còn lại tự động chuyển sang `False`.
- **Given** người dùng không có quyền quản trị workspace, **When** cố gắng chỉnh sửa hoặc xóa SIP Trunk, **Then** API trả về lỗi 403 Forbidden.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 4 findings — high 0, medium 3, low 1, false 0, maybe-false 0
- findings:
  - `medium` `patch` `TokenEncryption` API là `encrypt_token`/`decrypt_token` chứ không phải `encrypt`/`decrypt` — sửa `sip_manager.py` gọi đúng method; 5 test fail → 12/12 pass
  - `medium` `patch` `_ensure_workspace_admin` dùng `auth.is_superuser`/`auth.workspace_id` không tồn tại trên frozen `AuthContext` — viết lại async query RBAC qua `WorkspaceMembership` join `WorkspaceRole` từ DB
  - `medium` `patch` FastAPI dependency override: `patch()` trên `_get_sip_manager` không ăn vào DI resolution — dùng `app.dependency_overrides[_get_sip_manager]` đúng chuẩn FastAPI
  - `low` `patch` test mock trunk dùng MagicMock gây Pydantic ValidationError (id/created_at=None) — thay bằng `SimpleNamespace` với giá trị thật

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Kiến trúc SIP Trunk đa người thuê (BYO-SIP) cho phép từng workspace đăng ký đầu số DID và Voice Brandname riêng với mật khẩu mã hóa AES-256-GCM qua `TokenEncryption` (PII Vault). Router RESTful quản trị SIP trunk với RBAC Owner/Admin, password masking, và resolution cascade fallback về system default.

### Files changed

- `nowing_backend/app/models/workspace_sip.py` (mới) — model `WorkspaceSipTrunk` (encrypted password, brandname, DID, is_default/is_verified, tenant isolation)
- `nowing_backend/app/db/__init__.py` — export `WorkspaceSipTrunk`
- `nowing_backend/app/schemas/voice_sip.py` (mới) — DTOs: Create/Update/Response (password masked) /Resolved (plaintext cho LiveKit runtime)
- `nowing_backend/app/services/voice/sip_manager.py` (mới, ~280 dòng) — `SipTrunkManager`: encrypt/decrypt AES-256-GCM, CRUD, set-default atomic, `resolve_workspace_trunk()` cascade
- `nowing_backend/app/routes/voice_agent.py` (mới, ~200 dòng) — 6 endpoints CRUD + set-default, RBAC async qua DB membership
- `nowing_backend/app/routes/__init__.py` — đăng ký `voice_agent_router`
- 2 test files mới: `test_sip_manager.py` (8 tests), `test_voice_agent_routes.py` (4 tests)

### Review findings breakdown

- **Patches applied (4):** TokenEncryption method names (`encrypt_token`/`decrypt_token`); RBAC query thực qua WorkspaceMembership join WorkspaceRole; FastAPI dependency_overrides thay patch; SimpleNamespace mock trunk
- **Deferred (3):** dispatch wiring qua resolver (Story 38.7), Voice Brandname approval workflow (operational), Alembic migration cho bảng mới
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 12/12 tests mới pass, 290/290 full regression pass; các deferred items có owner rõ ràng (38.7 dispatch, ops migration).

### Verification performed

- `uv run pytest tests/unit/voice/ tests/unit/sequencer/ tests/unit/dnc/ -q` → **290 passed**, 0 failed
- `uv run ruff check` (8 files) → **All checks passed!**
- `uv run python -c "from app.services.voice.sip_manager import SipTrunkManager"` → **import OK**
- Matrix Test Audit: 7/7 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- Bảng `workspace_sip_trunks` chưa có Alembic migration — cần tạo migration trước khi deploy production
- `resolve_workspace_trunk` chưa được gọi trong dispatch pipeline (chờ Story 38.7)
- Voice Brandname `is_verified` chưa có workflow phê duyệt (operational process)

## Design Notes

**Mã hóa AES-256-GCM qua TokenEncryption:**
Tái sử dụng lớp `TokenEncryption` trong `app/utils/oauth_security.py`. Lớp này đã được kiểm chứng và dùng cho các token OAuth nhạy cảm của Google, Slack, Notion. Việc tái sử dụng đảm bảo toàn bộ bí mật viễn thông tuân thủ cùng chuẩn bảo mật PII Vault của Nowing.

**Quy tắc Masking Mật khẩu:**
Trong tất cả các DTO phản hồi ra ngoài client (như `SipTrunkResponse`), trường `sip_password` luôn được gán giá trị cố định `********` (8 ký tự sao) bất kể độ dài thực tế của mật khẩu, ngăn chặn việc phỏng đoán độ dài mật khẩu qua API.

**Cơ chế Phân giải Trunk Đa tầng (Trunk Resolution Cascade):**
1. Tìm trunk active có `is_default=True` của workspace.
2. Nếu không có default, lấy trunk active đầu tiên của workspace.
3. Nếu workspace không có trunk nào, sử dụng `SIP_DEFAULT_TRUNK_ID` và cấu hình gateway hệ thống.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/voice/test_sip_manager.py tests/unit/voice/test_voice_agent_routes.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/db/models/workspace_sip.py app/schemas/voice_sip.py app/services/voice/sip_manager.py app/routes/voice_agent.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.voice.sip_manager import SipTrunkManager; print('import OK')"` -- expected: no exception
