---
title: '31-2 Strict CNAME DNS/Ingress Ownership Verification'
type: 'feature'
created: '2026-09-16'
baseline_commit: '94a75a76592de09042d2af759319b2ee7e09616b'
status: 'done'
review_loop_iteration: 0
context: ['_bmad-output/implementation-artifacts/spec-31-1-dokploy-container-cgroup-network-isolation.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `verify_and_bind_custom_domain` chỉ kiểm tra CNAME trỏ tới ingress host — một domain bất kỳ trỏ CNAME đúng là bind được, kể cả khi user không sở hữu nó (phishing / domain-squatting lên infra Nowing). Không có proof-of-ownership bằng mật mã trước khi Traefik/Caddy được cấu hình.

**Approach:** Thêm TXT-record ownership gate vào bên trong `verify_and_bind_custom_domain`, chạy trước cả CNAME check và trước khi ghi route. Sinh một per-app verification token (cột mới trên `WorkspaceApp`), yêu cầu user đặt `TXT _nowing-verify.{domain} = "nowing-verify={token}"`, và resolve TXT qua dnspython. Cả TXT ownership VÀ CNAME đều bắt buộc; verify-fail trả HTTP 400, các lỗi khác giữ 422.

## Boundaries & Constraints

**Always:**
- Token là per-app, sinh một lần, lưu cột `custom_domain_verify_token` (String, nullable) trên `WorkspaceApp` qua migration Alembic mới (down_revision = `da41e2aa02d9`). Dùng `secrets.token_urlsafe(32)` — không dùng uuid4 thô.
- TXT record phải đặt ở label `_nowing-verify.{clean_domain}` với giá trị `nowing-verify={token}` (so sánh constant-time `secrets.compare_digest`, strip quotes/whitespace của rdata). dnspython TXT rdata trả về chuỗi có quote — phải `.strip('"')`.
- Thứ tự trong `verify_and_bind_custom_domain`, bên trong `domain_lock`, SAU collision check và TRƯỚC `_resolve_cname_ingress`: (1) đảm bảo token tồn tại cho app (generate+persist nếu NULL), (2) `_verify_txt_ownership` fail → `status="failed"`, `verify_stage="txt"`; (3) `_resolve_cname_ingress` fail → `verify_stage="cname"`. Một trong hai fail → không ghi route.
- Thêm `custom_domain_verify_token` vào `WorkspaceAppRead` (schemas.py) để CNAME modal hiển thị TXT record cần thiết. Không lộ token qua list endpoint nếu không cần — chỉ detail GET `/apps/{app_id}`.
- Route `apps.py` `configure_custom_domain`: khi `result.status=="failed"` và `result.verify_stage in {"txt","cname"}` → `HTTPException(400)`; các lỗi khác (redeploy, caddy) giữ `422`. Thêm trường `verify_stage: str | None` vào `CustomDomainOutput`.
- DNS verify fail-closed: mọi exception/timeout của `dns.resolver` → coi như chưa verify (`False`), không raise. Mirror pattern `asyncio.to_thread(resolver.resolve, ..., "TXT")` + `resolver.lifetime=5` đã dùng ở `_resolve_cname_ingress`.
- Giữ nguyên toàn bộ validate FQDN/label/blacklist/IP/localhost hiện có và `_acquire_domain_lock`/`_release_domain_lock` (finally).

**Ask First:**
- Thay đổi label TXT (`_nowing-verify`) hoặc giá trị prefix (`nowing-verify=`) — phải khớp với CNAME modal copy ở frontend.
- Expose token qua một endpoint riêng thay vì `WorkspaceAppRead` detail (nếu frontend cần refresh token độc lập).

**Never:**
- Không cho phép chỉ-TXT hoặc chỉ-CNAME — cả hai đều bắt buộc (AC + decision).
- Không config route (Traefik label / Caddy snippet / set `custom_domain_status="active"`) khi chưa qua cả hai vòng verify.
- Không sinh token mới mỗi lần verify — token phải ổn định để user đặt TXT một lần (chỉ generate khi NULL).
- Không thay `custom_domain_status` thành `active` khi verify fail; không ghi `custom_domain` vào entity trước khi verify pass.
- Không đổi `_resolve_cname_ingress` semantics (CNAME chain + A/AAAA apex fallback) — chỉ thêm TXT gate song song.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| happy path | token tồn tại, TXT `_nowing-verify.d=nowing-verify=tok`, CNAME→ingress | status `active`/`pending_verification`, route ghi | N/A |
| missing TXT | không có TXT record | `failed`, `verify_stage="txt"`, HTTP 400 | message nêu label + value cần đặt |
| wrong TXT | TXT khác token | `failed`, `verify_stage="txt"`, HTTP 400 | không lộ token đúng trong message |
| TXT ok, CNAME sai | TXT đúng, CNAME trỏ chỗ khác | `failed`, `verify_stage="cname"`, HTTP 400 | message nêu CNAME target |
| token NULL lần đầu | `custom_domain_verify_token IS NULL` | generate `token_urlsafe(32)`, persist, rồi verify | N/A |
| DNS timeout/exception | resolver raise/timeout | fail-closed `False` → `verify_stage` tương ứng | không 500 |
| token reuse | app đã có token, user re-bind | dùng lại token cũ (không rotate) | N/A |
| redeploy/caddy fail sau khi verify pass | verify ok, redeploy raise | `failed`, `verify_stage=None` → HTTP 422 | giữ nguyên path hiện tại |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/services/web_builder/deploy/custom_domain.py` — `verify_and_bind_custom_domain` (:21). Chèn TXT gate sau collision check (:~133), trước `_resolve_cname_ingress` (:140). Persist token khi NULL trước verify. Truyền `verify_stage` vào `CustomDomainOutput`.
- `nowing_backend/app/services/web_builder/deploy/service.py` — thêm `_verify_txt_ownership(domain, token)` mirror `_resolve_cname_ingress` (:534, dnspython qua `asyncio.to_thread`, `lifetime=5`, fail-closed). `_is_system_domain` (:507) và `_acquire_domain_lock` (:784) giữ nguyên. `import asyncio`, `contextlib` đã có sẵn (:1-2).
- `nowing_backend/app/models/workspaces.py:832-834` — `custom_domain`/`custom_domain_status`; thêm `custom_domain_verify_token = Column(String(255), nullable=True)` ngay sau.
- `nowing_backend/alembic/versions/` — migration mới `down_revision="da41e2aa02d9"`, `add_column` `custom_domain_verify_token`; mirror pattern `_table_exists` guard từ `c50707287216`.
- `nowing_backend/app/services/web_builder/schemas.py` — `CustomDomainOutput` (:119) thêm `verify_stage: str | None`; `WorkspaceAppRead` (:191) thêm `custom_domain_verify_token: str | None`.
- `nowing_backend/app/routes/web_builder/apps.py:181-213` — `configure_custom_domain`: nhánh `verify_stage in {"txt","cname"}` → `HTTPException(400)`, else `422` (:208-211).
- `nowing_backend/app/config/web_builder.py` — optional: `WEB_BUILDER_TXT_VERIFY_LABEL` (default `_nowing-verify`) + `WEB_BUILDER_TXT_VERIFY_PREFIX` (default `nowing-verify=`); thêm vào `__all__` (:296).
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — conventions: `mock_db_session.execute.side_effect`, patch `_resolve_cname_ingress`/`_verify_txt_ownership` (:378,:399,:433), `deploy_service` fixture. Thêm class `TestTxtOwnershipVerification`.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/alembic/versions/8f3b4c1a2d5e_add_custom_domain_verify_token.py` — `add_column(workspace_apps, custom_domain_verify_token String(255) nullable)` — persist per-app token
- [x] `nowing_backend/app/models/workspaces.py` — thêm cột `custom_domain_verify_token` sau :834 — ORM mapping
- [x] `nowing_backend/app/config/web_builder.py` — thêm `WEB_BUILDER_TXT_VERIFY_LABEL`/`_PREFIX` env knobs + `__all__` — label/prefix dễ đổi không sửa code
- [x] `nowing_backend/app/services/web_builder/deploy/service.py` — `_verify_txt_ownership()` dnspython TXT lookup, `compare_digest`, fail-closed — core verify
- [x] `nowing_backend/app/services/web_builder/deploy/custom_domain.py` — ensure-token + TXT gate + `verify_stage` threading — orchestration
- [x] `nowing_backend/app/services/web_builder/schemas.py` — `verify_stage` trên Output, `custom_domain_verify_token` trên Read — surface cho route + modal
- [x] `nowing_backend/app/routes/web_builder/apps.py` — map verify-fail → 400 — AC HTTP 400
- [x] `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — `TestTxtOwnershipVerification` cho toàn bộ I/O matrix — edge cases

**Acceptance Criteria:**
- Given user nhập custom CNAME, when DNS verification chạy, then backend check TXT ownership token (`_nowing-verify.{domain}` = `nowing-verify={token}`) trước khi cấu hình Traefik/Caddy — và CNAME cũng phải trỏ đúng.
- Given TXT hoặc CNAME verify fail, when route `POST /apps/{id}/custom-domain` nhận, then trả HTTP 400 (không ghi route, `custom_domain_status` không thành `active`).
- Given token chưa tồn tại, when bind được gọi, then token được sinh+persist một lần và ổn định cho các lần verify sau.
- Given DNS resolver lỗi/timeout, when verify chạy, then fail-closed (coi như chưa verify), không ném 500.

## Spec Change Log

## Design Notes

- TXT ở label `_nowing-verify.{domain}` thay vì apex: apex domain thường đã có TXT (SPF/verifications khác) và một số DNS provider không cho TXT cùng CNAME ở apex — label riêng tránh xung đột và cho phép nhiều app cùng verify trên các subdomain khác nhau.
- Cả TXT + CNAME bắt buộc vì chúng chứng minh hai thứ khác nhau: TXT = sở hữu (chỉ owner đặt được record vào zone), CNAME = routing đúng tới ingress. TXT-only không đảm bảo user trỏ traffic đúng; CNAME-only không chứng minh sở hữu.
- Token persist (không regenerate) để TXT record user đặt một lần vẫn valid khi họ re-bind/re-deploy — rotate chỉ khi có yêu cầu rõ ràng (ngoài scope).
- `verify_stage` tách TXT-fail vs CNAME-fail để frontend/modal hiển thị đúng record còn thiếu, và để route map đúng 400 vs 422.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/services/web_builder/test_deploy_service.py -m unit -q` — expected: all pass (existing + TestTxtOwnershipVerification)
- `cd nowing_backend && uv run pytest tests/integration/routes/test_web_builder_deploy_routes.py -m integration -q` — expected: custom-domain verify-fail returns 400 (cần Postgres 5434 + Redis 6380)
- `cd nowing_backend && uv run ruff check app/services/web_builder/ app/config/web_builder.py app/models/workspaces.py app/routes/web_builder/apps.py` — expected: clean
- `cd nowing_backend && uv run alembic heads` — expected: single head = new migration revision

## Suggested Review Order

**DNS ownership gate (entry point)**

- Per-app token generated+persisted once, row-locked against concurrent binds.
  [`custom_domain.py:150`](../../nowing_backend/app/services/web_builder/deploy/custom_domain.py#L150)
- TXT gate runs before CNAME; fail returns `verify_stage="txt"` with the record to set.
  [`custom_domain.py:177`](../../nowing_backend/app/services/web_builder/deploy/custom_domain.py#L177)
- CNAME still required after TXT; fail returns `verify_stage="cname"`.
  [`custom_domain.py:200`](../../nowing_backend/app/services/web_builder/deploy/custom_domain.py#L200)

**Core TXT verification**

- Constant-time `compare_digest`, quote/whitespace strip, fail-closed, empty-token + >253-octet guards.
  [`service.py:535`](../../nowing_backend/app/services/web_builder/deploy/service.py#L535)

**HTTP contract**

- `verify_stage in {"txt","cname"}` maps verify-fail to 400; deploy errors keep 422.
  [`apps.py:209`](../../nowing_backend/app/routes/web_builder/apps.py#L209)
- Token surfaced on detail GET, excluded from list.
  [`apps.py:346`](../../nowing_backend/app/routes/web_builder/apps.py#L346)

**Schema & config**

- New nullable column backing the persisted token.
  [`workspaces.py:836`](../../nowing_backend/app/models/workspaces.py#L836)
- Migration adds the column (down_revision `da41e2aa02d9`).
  [`8f3b4c1a2d5e_add_custom_domain_verify_token.py:52`](../../nowing_backend/alembic/versions/8f3b4c1a2d5e_add_custom_domain_verify_token.py#L52)
- `verify_stage` + `custom_domain_verify_token` on the read/output schemas.
  [`schemas.py:128`](../../nowing_backend/app/services/web_builder/schemas.py#L128)
- `WEB_BUILDER_TXT_VERIFY_LABEL`/`_PREFIX` env knobs.
  [`web_builder.py:25`](../../nowing_backend/app/config/web_builder.py#L25)

**Tests**

- `TestTxtOwnershipVerification`: full I/O matrix incl. split-string, single-quote, empty-token, oversize-host.
  [`test_deploy_service.py:1603`](../../nowing_backend/tests/unit/services/web_builder/test_deploy_service.py#L1603)
