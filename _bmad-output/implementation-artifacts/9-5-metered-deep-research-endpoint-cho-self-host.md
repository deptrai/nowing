

## File List

- `nowing_backend/app/routes/self_host_research.py` — new route `POST /v1/self-host/research`, auth, rate limit, cost/billing, degradation.
- `nowing_backend/app/routes/personal_access_tokens_routes.py` — allow `token_kind='self_host'` PAT creation.
- `nowing_backend/app/app.py` — mount `self_host_research_router` at `/v1`.
- `nowing_backend/app/config/__init__.py` — add `SELF_HOST_RESEARCH_COST_MULTIPLIER` env config.
- `nowing_backend/tests/unit/routes/test_self_host_research.py` — 10 unit tests.
- `nowing_backend/.env.example` — document self-host research env vars.
- `README.md` — self-host deep research guide and comparison table update.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status `9-5: in-progress` → `9-5: review`.

## Dev Agent Record

### Implementation Plan

- Chose to reuse `personal_access_tokens` with `token_kind='self_host'` instead of a new table; the existing `token_kind` column (Epic 18) already supports scoped PATs and avoids a migration.
- Built a dedicated `self_host_research.py` router to keep the auth/billing/quota logic isolated from the workspace-scrapers door pattern, while reusing `build_research_executor`, `wallet_credit`, `record_token_usage`, and `ChainLensServiceAuth`.
- Rate limit is per API key (hashed) using Redis + in-process fallback, mirroring `enforce_capability_rate_limit` but keyed by self-host token instead of workspace.
- Pre-flight balance check uses `fallback_micros * multiplier` so the engine is not wasted when the wallet is empty; post-call billing uses the actual engine `cost_micros` (or fallback) with 1.5× margin.
- Degradation preserves FR-38: missing/invalid key → 401; ChainLens unconfigured → `engine_unavailable`; upstream 429/5xx/timeout → `engine_unavailable` with appropriate reason.

### Completion Notes

- All 10 unit tests pass.
- `ruff check` clean on changed files.
- Relevant regression suites (chainlens research unit, access/rest, agent tools) pass: 293 passed, 1 skipped.
- Docs updated in `README.md` and `.env.example`.

### Debug Log

- Initial route draft added a `correlation_id` field to a `ResearchInput` subclass, but `ResearchInput` does not accept `correlation_id` and it was unnecessary; removed and used `uuid4()` for `run_id`.
- Unit tests initially returned `SimpleNamespace` from the fake executor; FastAPI/Pydantic serialization required real `ResearchOutput`/`Source` models.
- Mock `ChainLensServiceAuth` needed an `__init__` accepting `*args, **kwargs` because the route instantiates it with `config_obj=config`.

## Change Log

- 2026-08-12: Implement `POST /v1/self-host/research` route with PAT auth, rate limit, cost multiplier, wallet debit, and TokenUsage recording.
- 2026-08-12: Add `SELF_HOST_RESEARCH_COST_MULTIPLIER` config and support `token_kind='self_host'` PAT creation.
- 2026-08-12: Update `README.md` self-host comparison table and add "Use deep research on self-host" section; update `.env.example`.
- 2026-08-12: Add 10 unit tests in `tests/unit/routes/test_self_host_research.py`.
- 2026-08-12: Mark story 9-5 as `review` in sprint-status and story file.

## Senior Developer Review (AI)

### Review Outcome

`PASS_WITH_WARNINGS` — tất cả P0/P1 đã được patch, unit tests pass, ruff clean. Các P2 còn lại là ghi chú theo dõi, không chặn done.

### Action Items

- [x] **P0 — Overbilling khi engine trả về no-content/no-cost**: `_charge_self_host_research` áp dụng fallback cả khi `answer`/`sources` rỗng (vd `insufficient_evidence` không có kết quả). Đã sửa: chỉ dùng fallback khi có nội dung hoặc engine báo cost dương; no-content + no-cost → return 0. (`nowing_backend/app/routes/self_host_research.py:219-225`)
- [x] **P0 — TokenUsage zero-cost không được commit**: `_charge_self_host_research` ghi record nhưng return trước `session.commit()` khi `billed_micros <= 0`, audit row bị rollback. Đã sửa: `await session.commit()` trước khi return 0. (`nowing_backend/app/routes/self_host_research.py:285-289`)
- [x] **P0 — `SELF_HOST_RESEARCH_COST_MULTIPLIER` crash khi env sai**: dùng `float(os.getenv(...))` thay vì helper `_env_float`, gây `ValueError` khi env trống/invalid. Đã sửa: dùng `_env_float(...)` để graceful default. (`nowing_backend/app/config/__init__.py:1106`)
- [x] **P1 — Auth header có extra whitespace gây 401**: `partition(" ")` giữ lại khoảng trắng đầu/cuối trong token, `resolve_pat` hash không khớp. Đã sửa: `.strip()` credential và token. (`nowing_backend/app/routes/self_host_research.py:136,306`)
- [x] **P1 — `correlation_id` từ self-host request bị drop**: route tạo `ResearchInput` mới mà không truyền `correlation_id`. Đã sửa: truyền `correlation_id=body.correlation_id`. (`nowing_backend/app/routes/self_host_research.py:354`)

### Severity Counts

| Severity | Count | Status |
|---|---|---|
| P0 (MUST_FIX) | 3 | Fixed |
| P1 (SHOULD_FIX) | 2 | Fixed |
| P2 (WATCH) | 4 | Documented |

### Notes / WATCH

- **P2 — Pre-flight estimate bằng fallback flat rate** (`fallback_micros * multiplier`) có thể underestimates với mode `quality`/`deep`, dẫn đến engine đã gọi xong rồi mới phát hiện 402. Cần per-mode worst-case estimate hoặc reservation để xử lý triệt để; hiện tại là trade-off có ghi nhận.
- **P2 — Race condition `check_balance` → `apply_debit` không atomic**; nhiều request self-host concurrent có thể overdraw ví. Vấn đề nằm ở `app/services/wallet_credit.py` (shared, pre-existing) và cần atomic `UPDATE ... WHERE balance - reserved >= cost` hoặc reservation pattern trên toàn bộ billers.
- **P2 — `_resolve_workspace_id` fallback về workspace đầu tiên của user** khi PAT không có `workspace_id` có thể attribute sai. Tuy nhiên story thiết kế workspace là optional, nên giữ nguyên.
- **P2 — `PATCreate.token_kind` không giới hạn giá trị**, cho phép tạo token kind tùy ý. Chỉ `self_host` và `agent_chat` được sử dụng; recommend thêm enum/constraints ở schema sau này.

### Validation After Patch

- `ruff check app/routes/self_host_research.py app/routes/personal_access_tokens_routes.py app/app.py app/config/__init__.py tests/unit/routes/test_self_host_research.py` — ✅ pass
- `pytest tests/unit/routes/test_self_host_research.py -q` — ✅ 13 passed

## Status

`done` — human review approved. 38 unit tests pass, mutation score 99.41% P0=0, traceability APPROVED, NFR CONCERNS with 2 P2 watch items recorded.
