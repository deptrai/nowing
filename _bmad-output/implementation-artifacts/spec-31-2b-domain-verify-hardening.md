---
title: '31-2b Custom-domain verify hardening — deferred gaps'
type: 'feature'
created: '2026-09-16'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'dfa4d5777'
context: ['_bmad-output/implementation-artifacts/spec-31-2-strict-cname-dns-ingress-ownership-verification.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Ba khoảng trống còn lại sau story 31.2: (1) `custom_domain_verify_token` chỉ sinh khi bind → CNAME modal không hiển thị TXT record trước lần bind đầu; (2) khi redeploy/Caddy fail sau verify, `custom_domain` bị ghi đè bởi domain fail (mất domain đang hoạt động); (3) thiếu token-rotation và unbind endpoint; "Application not found" trả 422 thay vì 404; message thiếu gợi ý DNS propagation/TTL.

**Approach:** Generate-on-read token trên `GET /apps/{id}`; preserve+restore domain cũ khi post-verify fail; thêm `POST .../custom-domain/rotate-token` và `DELETE .../custom-domain`; map app-not-found → 404; thêm TTL hint vào TXT-missing message.

## Boundaries & Constraints

**Always:**
- `GET /apps/{app_id}` (`apps.py:get_workspace_app`): nếu `app_entity.custom_domain_verify_token` NULL → generate `secrets.token_urlsafe(32)`, assign, `session.commit()`, refresh. Idempotent; chỉ khi app tồn tại.
- Trong `verify_and_bind_custom_domain` published path: lưu `previous_domain`/`previous_status`/`previous_container_id`/`previous_port` trước khi ghi `clean_domain`. Khi redeploy hoặc Caddy fail → restore `custom_domain`/`custom_domain_status`/`container_id`/`port` về giá trị cũ (và `error_message` vẫn ghi lỗi). `custom_domain_status` restore về `previous_status` (không phải "failed") để domain cũ vẫn active nếu nó đang active.
- app-not-found: `verify_and_bind_custom_domain` trả `verify_stage="not_found"`; route `configure_custom_domain` map `verify_stage=="not_found"` → `HTTPException(404)`. (Không phá vỡ: `"Application not found"` message giữ nguyên.)
- `POST /apps/{app_id}/custom-domain/rotate-token` (mới): generate token mới, persist, return `{"custom_domain_verify_token": new_token}` — cùng permission `WEB_BUILDER_CREATE` + membership. Khi app có `custom_domain_status=="active"` và rotate → set `custom_domain_status="pending_verification"` (buộc re-verify) — đây là hành vi an toàn.
- `DELETE /apps/{app_id}/custom-domain` (mới): clear `custom_domain`/`custom_domain_status`/`custom_domain_verify_token` → null, `session.commit()`, return 204. Cùng permission. (Không remove Caddy snippet — note trong response/log nếu cần, giới hạn scope.)
- TTL guidance: TXT-missing message nối thêm `"(DNS may take a few minutes to propagate; wait for the TTL to expire if you just added the record.)"`.
- Frontend modal: render TXT record block `_nowing-verify.{domain-input}` / `nowing-verify={token}` khi `selectedApp.custom_domain_verify_token` có giá trị (lấy từ `getApp` detail query). Hiển thị readonly `<code>` + copy hint. Không đổi error toast path.

**Ask First:**
- Rotate khi `active` → pending_verification (buộc re-verify): nếu muốn giữ active thì nói.

**Never:**
- Không expose `custom_domain_verify_token` qua list endpoint (giữ exclude hiện tại).
- Không regenerate token khi đã tồn tại (trừ rotate endpoint).
- Không đổi `_resolve_cname_ingress`/`_verify_txt_ownership` semantics.
- Không break contract `CustomDomainOutput` hiện có (chỉ thêm `verify_stage` value `"not_found"`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| detail GET no token | `custom_domain_verify_token IS NULL` | generate+persist, response chứa token | N/A |
| detail GET has token | token exists | reuse, không regenerate | N/A |
| redeploy fail w/ old domain | app có `custom_domain=old.com` active | restore `custom_domain=old.com`, status về previous | error_message ghi lỗi redeploy |
| redeploy fail no old domain | app chưa có domain | `custom_domain` về NULL, status failed | message redeploy |
| caddy fail w/ old domain | redeploy ok, caddy raise | restore domain cũ + status | error_message caddy |
| app not found | app_id sai | `verify_stage="not_found"` → HTTP 404 | giữ message |
| rotate token | POST rotate | token mới persisted + returned | active→pending_verification |
| unbind | DELETE | 3 fields → null, 204 | app not found → 404 |
| TXT missing message | DNS fail | message chứa TXT value + TTL hint | — |
| frontend modal | detail trả token | modal render `_nowing-verify.d / nowing-verify=tok` | token null → không render block |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/routes/web_builder/apps.py` — `get_workspace_app` (:371): generate-on-read token. `configure_custom_domain` (:181): `verify_stage=="not_found"`→404. Thêm `rotate_custom_domain_token` + `unbind_custom_domain` routes.
- `nowing_backend/app/services/web_builder/deploy/custom_domain.py` — preserve/restore previous domain trên redeploy/caddy fail (:~229-290); `verify_stage="not_found"` khi app None; TTL hint trong TXT-missing msg (:~185). Thêm `rotate_domain_token` + `unbind_custom_domain` service fns (hoặc inline trong route với session trực tiếp).
- `nowing_backend/app/services/web_builder/schemas.py` — thêm `CustomDomainTokenOutput`/`RotateTokenOutput` (`{custom_domain_verify_token: str}`) cho rotate; `WorkspaceAppRead.custom_domain_verify_token` đã có.
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx` — `selectedApp.custom_domain_verify_token` → render TXT record block trong domain modal (:~882-895); `WorkspaceApp` type thêm field.
- `nowing_web/contracts/types/web-builder.types.ts` — `WorkspaceApp`/`CustomDomainOutput` thêm `custom_domain_verify_token`/`verify_stage`.
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — tests: detail-generate-token, restore-on-fail, not_found stage, rotate, unbind, TTL-hint message.
- `nowing_backend/tests/integration/routes/test_web_builder_deploy_routes.py` — 404 app-not-found, rotate, unbind 204.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/web_builder/deploy/custom_domain.py` — `verify_stage="not_found"`; preserve+restore previous domain/container on post-verify fail; TTL hint in TXT-missing message — core fixes
- [x] `nowing_backend/app/routes/web_builder/apps.py` — `get_workspace_app` generate-on-read; `configure_custom_domain` not_found→404; `rotate-token` + `unbind` (DELETE) routes — API surface
- [x] `nowing_backend/app/services/web_builder/schemas.py` — `RotateTokenOutput`/`CustomDomainTokenOutput` — rotate response
- [x] `nowing_web/contracts/types/web-builder.types.ts` + `web-builder/page.tsx` — WorkspaceApp.verify_token field + modal TXT record block — UI surface
- [x] `nowing_backend/tests/unit/.../test_deploy_service.py` + `tests/integration/.../test_web_builder_deploy_routes.py` — cover I/O matrix

**Acceptance Criteria:**
- Given app chưa có token, when `GET /apps/{id}` chạy, then token được sinh+persist và trả về (modal hiển thị TXT ngay).
- Given app có domain `old.com` active, when re-bind `new.com` verify pass nhưng redeploy fail, then `custom_domain` giữ `old.com` và status về active (không mất domain đang chạy).
- Given app_id không tồn tại, when POST custom-domain, then HTTP 404 (không phải 422).
- Given rotate-token, when POST, then token mới persist+return; nếu domain đang active → status về pending_verification.
- Given unbind, when DELETE, then `custom_domain`/`status`/`token` → null, HTTP 204.
- Given TXT-missing, when verify fail, then message chứa expected TXT value + gợi ý TTL/propagation.

## Spec Change Log

## Design Notes

- Generate-on-read trên detail GET chọn vì: (a) idempotent, không cần endpoint riêng; (b) token là per-app secret-ish — chỉ cần khi user mở app detail/modal; (c) tránh backfill migration cho rows cũ. Commit trên GET là chấp nhận được (chỉ khi NULL, một lần).
- Restore-domain-on-fail: giữ `custom_domain` cũ + status trước đó vì domain đang chạy thật trên ingress — ghi đè bằng domain fail làm mất binding đang hoạt động.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/services/web_builder/test_deploy_service.py -m unit -q` — all pass
- `cd nowing_backend && uv run pytest tests/integration/routes/test_web_builder_deploy_routes.py -m integration -q` — all pass
- `cd nowing_backend && uv run ruff check app/services/web_builder/ app/routes/web_builder/apps.py app/services/web_builder/schemas.py` — clean
- `cd nowing_web && pnpm tsc --noEmit && pnpm exec biome check app/dashboard/` — clean
