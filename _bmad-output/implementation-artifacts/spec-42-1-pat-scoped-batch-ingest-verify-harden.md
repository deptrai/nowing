---
title: 'PAT-scoped REST batch ingest — verify & harden contract + document persistence guard'
type: 'feature'
created: '2026-11-16'
status: 'done'
baseline_revision: 'f0de102a923aea25d43e32f2e236110751b8265c'
review_loop_iteration: 1
followup_review_recommended: true
context: []
warnings: ['multiple-goals', 'oversized']
deferred:
  - summary: >-
      Sibling lead-write endpoints (unlock_contact, relock_contact,
      pii_opt_out) trong lead_batch_routes.py chưa enforce PAT scope — PAT
      bound workspace khác hoặc thiếu leads:write vẫn write được.
    evidence: |-
      verification-gap review: cả 3 endpoint dùng RequirePermission +
      get_auth_context, không có RequirePatScope; check_permission không
      check pat.scopes/workspace binding — cùng lỗ hổng story vừa vá cho
      batch-ingest. Ngoài scope story 42.1 (chỉ batch-ingest contract).
    location: >-
      nowing_backend/app/routes/lead_batch_routes.py:~230,299,414
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Route `POST /workspaces/{id}/leads/batch-ingest` chấp nhận PAT nhưng không enforce scope `leads:write`, không guard workspace-binding, không ghi attribution vào ledger — PAT lộ ra = quyền ghi lead trọn vẹn. Batch validation trả 422 shape lỏng (không `rejected_indexes`/`reason_map`). Doc-persist path: embed thất bại → cả document mất.

**Approach:** Verify + harden seam hiện có (KHÔNG rewrite): thêm một PAT-scope dependency duy nhất theo convention `agent_chat.py`, validation reject-all có cấu trúc tại funnel `LeadBatchService`, ghi `lead_activity_logs` cho PAT attribution, và embed-fail guard tái dùng `content_needs_reindexing` + `reindex_document_task` sẵn có.

## Boundaries & Constraints

**Always:** Mọi lead-write qua `LeadBatchService.ingest_batch` (AD-1); PAT authz qua MỘT seam đặt tên `enforce_pat_scope`/`RequirePatScope` (AD-2); batch có ≥1 lead degenerate → reject-all 422 `{status:'failed', rejected_indexes:[...], reason_map:{idx:reason}}` (AD-4); re-push cùng leads → idempotent no-op nhờ upsert `ON CONFLICT` + UNIQUE tồn tại; ingest qua PAT ghi `actor_pat_token_id` vào ledger; embed fail → document row vẫn commit + flag reindex + retry được schedule (không unindexed mãi, không mất doc); giữ nguyên `RequirePermission`/`check_permission` cho session/system.

**Never:** Không cơ chế auth mới (reuse `get_auth_context` + `resolve_pat`); KHÔNG thêm column `unindexed` mới — tái dùng `documents.content_needs_reindexing` (đã được `UploadDocumentAdapter.reindex` clear khi thành công); KHÔNG migration dedupe mới — `uq_leads_workspace_value_hmac` UNIQUE(workspace_id, value_hmac) ĐÃ TỒN TẠI và mạnh hơn `(client_id, value_hmac)` literal của AC vì `client_id` là namespace tự do (deviation documented); không sửa `app/auth/agent_chat.py` (surface `token_kind='agent_chat'` riêng); không đổi semantics billing/credit; không bỏ `_reject_degenerate_leads` service-level (nó là điểm validation duy nhất của funnel — REST save_leads/multi_source dùng chung).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_SESSION | Session auth, leads hợp lệ | 200 + ingested/skipped/failed counts + lead_ids | Không đổi behavior hiện có |
| PAT_OK | PAT có `leads:write`, workspace binding khớp hoặc `pat.workspace_id=None` | 200 + activity-log rows ghi `actor_pat_token_id`, `idempotency_key` | — |
| PAT_NO_SCOPE | PAT thiếu `leads:write` (kể cả legacy `scopes=[]`) | 403, detail nêu scope thiếu | Fail-closed, không rò token info |
| PAT_WRONG_WS | PAT bind workspace A, path workspace_id=B | 403 `workspace_id outside pat scope` | Trước hoặc sau membership đều 403 |
| PAT_NON_MEMBER | PAT user không phải member workspace | 403 từ `RequirePermission` (contract: PAT kế thừa membership của owning user) | — |
| DEGENERATE_BATCH | Batch ≥1 lead thiếu hết phone/email/domain/company_name | 422 `{status:'failed', rejected_indexes:[i,...], reason_map:{i:"..."}}`, TẤT CẢ index được collect, không silent drop | Toàn batch rollback |
| REPUSH_IDEMPOTENT | POST lại cùng payload (+ `Idempotency-Key` header) | 200, upsert no-op, không duplicate lead; key ghi vào activity-log details | Header tùy chọn |
| EMBED_FAIL_PERSIST | `embed_texts` raise trong doc-persist | Document row commit: `embedding=None`, không chunks mới, `content_needs_reindexing=True`, `document_metadata.index_status='embed_failed'`; sau commit `reindex_document_task.apply_async(countdown=30)` | Reindex success → flag tự clear (adapter hiện có); fail → flag còn, query-able cho sweep sau |
| EMBED_FAIL_UPDATE | Embed fail trên `_update_document` | Doc update vẫn commit (content mới), chunks cũ đã xóa → rebuild bởi reindex; cùng flag+dispatch | Như trên |

## Code Map

- `app/routes/lead_batch_routes.py:117-160` — `batch_ingest_leads`: thêm dep `RequirePatScope("leads:write")` (đặt SAU `_membership`), param `idempotency_key: str|None = Header(None, alias="Idempotency-Key")`, map structured `LeadItemValidationError` → 422 payload, ghi `LeadActivityLog` rows khi `auth.is_gated` (trước `session.commit()`).
- `app/routes/lead_batch_routes.py:~33-50` — `BatchLeadIngestRequest._reject_degenerate`: XÓA validator này (validation funnel duy nhất ở service — align REST với semantics save_leads/multi_source; `company_name` nay tính là contact field giống các caller khác — behavior change có chủ đích, ghi trong AC).
- `app/services/lead_batch_service.py:43-50` — `_reject_degenerate_leads`: loop collect `{idx: "phone, email, domain and company_name are all empty"}` → raise `LeadItemValidationError` mang `rejected_indexes`/`reason_map` (extend exception class, giữ `str(exc)` đọc được).
- `app/utils/rbac.py` (cuối, sau `check_permission`): `async def enforce_pat_scope(auth, workspace_id, required_scope)` — `if not auth.is_gated: return`; `pat.workspace_id is not None and pat.workspace_id != workspace_id → 403 "workspace_id outside pat scope"`; `required_scope not in (pat.scopes or []) → 403 "permission missing: {scope}"` (message convention theo `agent_chat.py:364-377`).
- `app/dependencies/auth.py` — `class RequirePatScope`: mirror `RequirePermission` (`workspace_id` + `auth` params), delegate `enforce_pat_scope`. Đây là seam duy nhất cho REST PAT scope (AD-2).
- `app/auth/agent_chat.py:22-47,317,364` — convention tham chiếu (workspace-match 403 + scope 403). KHÔNG reuse `validate_scopes` — catalog `agent_chat:*` khác namespace `leads:write`.
- `app/models/users.py:549-615` — `PersonalAccessToken`: `workspace_id` nullable (legacy/unbound), `scopes` JSONB default `[]`, `token_kind`. PAT resolve → owning `User` (`app/utils/pat.py:36-53`) → membership của user đó áp dụng.
- `app/models/leads/main.py:33-49` — `uq_leads_workspace_value_hmac` ĐÃ TỒN TẠI → dedupe constraint đủ, no migration. `:367-425` `LeadActivityLog`: `lead_id`, `workspace_id`, `client_id`, `actor_user_id`, `activity_type`, `title`, `details` JSONB → ledger ghi `{"actor_pat_token_id": pat.id, "idempotency_key": key, "pat_token_prefix": pat.token_prefix}`.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/kb_persistence/_helpers.py:212-229` (`_create_document`), `:265-284` (`_update_document`) — wrap khối embed (summary + chunk) trong try/except Exception: log, `doc.embedding=None`, bỏ chunk creation, `doc.content_needs_reindexing=True`, `doc.document_metadata={**meta, "index_status":"embed_failed"}`.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/kb_persistence/_commit.py:398,~362` — sau `_create_document`/`_update_document` collect `doc.id` khi `doc.content_needs_reindexing`; post-commit section `:645+` (đã có pattern deferred dispatch) → `reindex_document_task.apply_async(args=[doc_id, str(created_by_id or "system")], countdown=30)` (best-effort, try/except per dispatch).
- `app/tasks/celery_tasks/document_reindex_tasks.py` + `app/indexing_pipeline/adapters/file_upload_adapter.py:47,76` — task sẵn có, clear flag khi success. Dispatch convention: `editor_routes.py:318`.
- Tests: `tests/unit/routes/test_lead_batch_ingest.py`, `tests/unit/services/test_lead_batch_service.py`, `tests/unit/middleware/test_kb_persistence_*.py`, `tests/unit/test_pat_fail_closed_static.py` (convention fail-closed), `tests/integration/lead_batch/test_lead_batch_ingest.py` (real-DB dedupe/upsert).

## Spec Tasks

**Execution:**
- `app/services/lead_batch_service.py` — `_reject_degenerate_leads` collect-all → `LeadItemValidationError(rejected_indexes, reason_map)` — single validation point của funnel.
- `app/utils/rbac.py` + `app/dependencies/auth.py` — `enforce_pat_scope` + `RequirePatScope` — named seam AD-2.
- `app/routes/lead_batch_routes.py` — wire dep + `Idempotency-Key` + 422 structured map + LeadActivityLog writes; xóa `_reject_degenerate` pydantic — surface contract.
- `kb_persistence/_helpers.py` + `_commit.py` — embed-fail guard + post-commit reindex dispatch — persistence guard.
- `tests/unit/routes/test_lead_batch_ingest.py`, `tests/unit/services/test_lead_batch_service.py`, `tests/unit/middleware/` — cover mọi hàng I/O matrix (PAT scope/ws/member, 422 shape, idempotent re-push, embed fail flag+dispatch).

**Acceptance Criteria:**
- Given PAT `leads:write` bound đúng workspace, When POST batch-ingest leads hợp lệ, Then 200 + counts + `lead_activity_logs` rows chứa `actor_pat_token_id`.
- Given PAT thiếu scope / bound workspace khác / user non-member / legacy scopes=[], When POST, Then 403 (session path không đổi).
- Given batch có lead degenerate ở index 1 và 3, When POST, Then 422 body có `status:'failed'`, `rejected_indexes=[1,3]`, `reason_map` đủ 2 entry, không lead nào persist.
- Given leads đã ingest, When POST lại payload giống (+ Idempotency-Key), Then 200, không lead mới (upsert conflict), không double-debit.
- Given `embed_texts` mocked raise, When commit_staged_filesystem_state create doc, Then document row tồn tại với `embedding=None`, `content_needs_reindexing=True`, `index_status='embed_failed'` và `reindex_document_task.apply_async` được gọi.
- Given doc có `content_needs_reindexing=True`, When `reindex_document_task` chạy thành công, Then flag về False (adapter hiện có).

## Spec Change Log

## Review Triage Log

### 2026-11-17 — Review pass
- verdicts: 29 findings — high 0, medium 4, low 10, false 15, maybe-false 0
- findings:
  - `[medium]` `[patch]` blind-hunter: ledger ghi `LeadActivityLog` trên `result["lead_ids"]` gồm cả lead conflict-updated + blacklisted — `accepted_lead_ids` (exclude blocked) tồn tại ở service:399-415; fix: loop trên `accepted_lead_ids` (re-push vẫn được audit — đúng thiết kế ledger).
  - `[false]` `[reject]` blind-hunter: `Idempotency-Key` chỉ lưu không dedupe — by design: dedupe do `uq_leads_workspace_value_hmac` + upsert đảm nhiệm, key là audit-only (spec Design Notes; intent E1).
  - `[medium]` `[patch]` blind-hunter: thiếu test update-path ở commit level — `test_commit_schedules_reindex...` chỉ cover create path; xoá append ở update branch vẫn pass (verification-gap chứng minh).
  - `[false]` `[reject]` blind-hunter: thiếu test PAT_NON_MEMBER — đã có `test_batch_ingest_non_member_forbidden` (integration, đã chạy pass): PAT đi qua `RequirePermission` trước scope check, cùng seam.
  - `[low]` `[patch]` blind-hunter: try/except quá rộng trong `_create/_update_document` — bọc `delete(Chunk)`, `add_all`, `chunk_text`; lỗi non-embed bị dán nhãn `embed_failed`; fix: thu hẹp try chỉ quanh embed calls.
  - `[medium]` `[patch]` blind-hunter + edge-case + intent-alignment: `_update_document` — `delete(Chunk)` sau summary embed → summary-embed fail để lại chunks cũ searchable với content mới; chunk-embed fail thì `_mark_embed_failed` vứt summary embedding vừa tạo; fix: delete chunks trước try, bảo toàn embedding khi chỉ chunk-stage fail.
  - `[false]` `[reject]` blind-hunter: `RequirePatScope.__call__` couple tên `workspace_id` — cùng convention với `RequirePermission.__call__` (verified signature dependencies/auth.py:63-67); không phải khuyết điểm mới.
  - `[low]` `[reject]` blind-hunter: dead branch `pat is None` + detail shape không đồng nhất — defensive branch vô hại, cosmetic.
  - `[low]` `[patch]` blind-hunter + intent-alignment: 422 payload thừa key `detail` lệch AD-4 literal `{status, rejected_indexes, reason_map}` (reason_map keys stringify là JSON-bắt buộc, chấp nhận); fix: bỏ `detail` khỏi `as_payload()`.
  - `[low]` `[patch]` blind-hunter: `details` dict dùng chung mutable cho mọi `LeadActivityLog` row — mutation leak giữa ORM instances; fix: `{**details}` per row.
  - `[low]` `[reject]` blind-hunter: `idempotency_key` không giới hạn độ dài — HTTP server đã cap header size, surface PAT-authenticated, negligible.
  - `[false]` `[reject]` blind-hunter: `"leads:write"` trùng tên hai lớp authz — by design: PAT phải qua cả scope check lẫn membership của owner (spec PAT_NON_MEMBER); double-gate là ý đồ.
  - `[low]` `[reject]` blind-hunter: `_commit.py` guard `updated is not None` lặp hai lần — cosmetic, không harm.
  - `[low]` `[reject]` blind-hunter: log `_mark_embed_failed` hứa "scheduling reindex" — cosmetic, caller context rõ.
  - `[medium]` `[patch]` edge-case: stale old chunks khi summary-embed fail trên update path — cùng root cause với nhóm try-guard ở trên, chung fix.
  - `[low]` `[patch]` edge-case: orphan `reindex_doc_ids` khi IntegrityError nổ ở savepoint release (append chạy trong `begin_nested`, except→continue giữ id mồ côi → dispatch reindex cho doc không tồn tại); fix: append sau khi savepoint exit thành công.
  - `[low]` `[patch]` edge-case: import `reindex_document_task` ngoài try — lỗi import lan ra post-commit thành exception; fix: bọc import + dispatch trong guard.
  - `[low]` `[patch]` edge-case: success path không reset `content_needs_reindexing`/`index_status` — doc flagged trước + edit embed OK vẫn giữ flag → reindex dư thừa + marker `embed_failed` tồn tại mãi trong metadata; fix: update success path clear flag + pop marker.
  - `[medium]` `[patch]` edge-case: blacklisted leads được log "batch_ingested" — cùng root cause `lead_ids` vs `accepted_lead_ids`, chung fix.
  - `[false]` `[reject]` edge-case: `LeadActivityLog` insert fail → rollback cả batch — fail-closed ĐÚNG ý đồ audit (AD-2/PDPD): không ghi được ledger thì không persist un-audited leads; retry an toàn nhờ upsert idempotent.
  - `[medium]` `[patch]` verification-gap: commit-level update-path test thiếu (pre-verified, demonstration: xoá append → suite vẫn xanh).
  - `[medium]` `[defer]` verification-gap: `unlock_contact`/`relock_contact`/`pii_opt_out` cùng file chưa có `RequirePatScope` — PAT bound ws-B vẫn write được qua 3 endpoint đó; ngoài scope story 42.1 (chỉ batch-ingest), follow-up riêng.
  - `[low]` `[patch]` verification-gap: test assert `actor_pat_token_id is not None` thay vì `== pat.id` — code ghi sai field vẫn pass; fix mock pat id thành int + assert bằng.
  - `[false]` `[reject]` verification-gap: ledger tích luỹ row mỗi re-push — by design: ledger ghi theo CALL (attribution), không phải net-new lead.
  - `[false]` `[reject]` intent-alignment: session-path đổi behavior (company_name-only lead giờ 200 thay 422) — sanctioned bởi D2 + task list + matrix; ghi trong Design Notes.
  - `[low]` `[patch]` intent-alignment: `detail` key thừa + reason_map stringify — gộp vào row BH8 (stringify là JSON constraint, giữ; bỏ `detail`).
  - `[medium]` `[patch]` intent-alignment: delete-in-try semantics — gộp vào row EC1.
  - `[medium]` `[patch]` intent-alignment: attribution gồm blacklisted — gộp vào row BH1.
  - `[low]` `[reject]` intent-alignment: dead branch `pat is None` — gộp vào row BH7.
  - `[low]` `[patch]` intent-alignment: coverage end-to-end các leg mới (unbound PAT, repush+header) chỉ mocked — fix: thêm unit test unbound PAT; phần real-DB dedupe đã có integration suite.

## Design Notes

- `unindexed:true` của AC literal = `content_needs_reindexing=True` (flag sẵn có từ migration 43, semantics "content mới hơn index" — đúng ý đồ; tránh schema churn).
- Dedupe giữ `(workspace_id, value_hmac)` thay `(client_id, value_hmac)`: client_id là namespace tự do — cùng lead từ 2 campaign đáng lẽ dedupe; AD-4 intent = idempotent, constraint mạnh hơn thỏa.
- Validation move pydantic→service: `company_name` nay tính contact field (đồng nhất với non-REST callers) — lead chỉ-có-company_name được chấp nhận thay vì 422; ghi rõ đây là alignment có chủ đích.
- `Idempotency-Key`: minimal — accept + ghi ledger `details`; dedupe thực tế do upsert đảm nhiệm (không cần key-store mới).
- Reindex retry: 1 `apply_async(countdown=30)`; flag persist = marker bền cho sweep sau (sweep job nằm ngoài scope story).

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_lead_batch_ingest.py tests/unit/services/test_lead_batch_service.py -x -q` — expected: pass
- `.venv/bin/python -m pytest tests/unit/middleware/ -k kb_persistence -x -q` — expected: không regression
- `.venv/bin/python -m pytest tests/integration/lead_batch/test_lead_batch_ingest.py -x -q` — expected: pass (real-DB dedupe + non-member)

## Auto Run Result

- **Baseline:** `f0de102a923aea25d43e32f2e236110751b8265c` (HEAD lúc viết spec, sau commit planning artifacts).
- **Implementer:** subagent fresh-context (sonnet); diff 10 files trước review, re-engaged cho patch round 1.
- **Review:** 4 lớp đầy đủ (blind-hunter 13 · edge-case 6 · verification-gap 4 · intent-alignment 6 deltas) — 29 rows, verdict: 3 medium patched + 10 low patched + 1 medium deferred, 15 false/reject.
- **Patched-medium (3):** ledger log trên `accepted_lead_ids` (bỏ blacklisted); `_update_document` try-guard semantics (delete-chunks-trước + bảo toàn summary embedding); commit-level update-path reindex test.
- **Verification (coordinator re-run, sau patch):** `pytest tests/unit/routes/test_lead_batch_ingest.py tests/unit/services/test_lead_batch_service.py tests/unit/middleware/test_kb_persistence_embed_fail.py` → **35 passed**; `pytest tests/unit/middleware/ -k kb_persistence` → **22 passed**; `pytest tests/integration/lead_batch/test_lead_batch_ingest.py` → **5 passed**; enum `LEADS_WRITE == "leads:write"` ✓.
- **Matrix audit:** cả 9 hàng có bằng chứng — HAPPY_SESSION (unit), PAT_OK + unbound-PAT (unit mới), PAT_NO_SCOPE/PAT_WRONG_WS/PAT_NON_MEMBER (unit + integration), DEGENERATE_BATCH (unit service + route shape), REPUSH_IDEMPOTENT (integration dedupe + ledger-per-call by design), EMBED_FAIL_PERSIST/UPDATE (helper + commit-level unit tests).
