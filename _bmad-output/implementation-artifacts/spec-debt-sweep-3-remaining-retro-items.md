---
title: 'Debt-sweep 3: đóng 6 retro action items còn mở Epic 31–35 (router split, streaming dedup, MV3 E2E fixture, SecOps SOP, DNS probe, CdpBridge research)'
type: 'refactor'
created: '2026-10-13'
status: 'done'
baseline_commit: '8bfa607bf'
route: 'dispatch'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sau Debt-sweep 2, sprint-status còn 8 retro items `open` từ Epic 31–35. Sweep này đóng 6 items làm được trong repo: (31) god-file `dsh_routes.py` 809 dòng, (41) `SpatialWindowedDeduplicator` là dead code thiếu streaming interface, (32) thiếu Playwright MV3 fixture cho luồng `chrome.debugger.onDetach`/takeover, (29) thiếu synthetic DNS probe, (36) thiếu SecOps SOP xoay `SECRET_KEY`, (33) research multi-tab `CdpBridge`.

**Deferred (không làm — ghi lý do):**
- **Item 28** (cgroup telemetry Dokploy): cần quyền truy cập infra/production — ngoài phạm vi repo-local.
- **Item 35** (Credit Refund Policy): quyết định chính sách sản phẩm thuộc product-owner, không phải code task.

## Boundaries & Constraints

**Always:**
- Item 31: tách `app/routes/dsh_routes.py` → `app/routes/dsh/` package gồm `__init__.py` (định nghĩa `dsh_public_router`, `dsh_internal_router`), `deps.py` (shared helpers: `_verify_dsh_worker_secret`, `require_dsh_worker`, `_require_pat_workspace_scope`, `_require_mission_access`), `missions.py` (7 endpoints CRUD mission), `cdp.py` (`cdp_stream` + `cdp_result` + `_redact_cdp_result_value`), `takeover.py` (pause/resume/abort/sweep). URL path và router prefix giữ nguyên tuyệt đối — refactor thuần, không đổi API contract.
- Item 31: cập nhật `app/app/factory.py` import + tất cả test imports/patch targets (`test_takeover_abort_scheduler.py`, `test_browser_operator_cdp.py`, `test_dsh_cdp_stream.py`). Xóa `dsh_routes.py` cũ sau khi chuyển hết.
- Item 41: thêm streaming API `deduplicate_stream`/`iter_deduplicate` vào `SpatialWindowedDeduplicator` — memory bound O(largest bucket), không O(dataset); nếu cần input sorted-by-bucket thì ghi rõ contract trong docstring.
- Item 41: wire 1 call site production thật — ưu tiên nơi items đã là `dict` shape (native interface của module), vd `social_medirus_ingest` hoặc `chainlens/ingest` hoặc `bds_aggregator` raw-item pre-filter. Hành vi dedup phải additive-safe (chỉ lọc trùng trước persist/merge, không phá merge semantics hiện có).
- Item 32: fixture tải `nowing_browser_extension/build/chrome-mv3-prod` (Plasmo MV3) qua `chromium.launchPersistentContext` + `--load-extension`; spec kiểm thử được phần testable trong CI (service worker đăng ký, extensionId, popover/detach logic path có thể mock); skip graceful khi build chưa tồn tại (CI build extension trước).
- Item 29: `scripts/` synthetic DNS probe kiểm tra TXT `_nowing-verify.<domain>` + CNAME trên staging/prod — tái dùng logic từ `app/services/web_builder/deploy/custom_domain.py:172` và `service.py:538`.
- Item 36: `docs/ops/` SOP xoay vòng SECRET_KEY → OLD_SECRET_KEY: quy trình set env, chạy `rotate_encryption`, verify completion, rồi mới gỡ OLD key. Dựa trên `app/services/pii/verified_contact_encryption.py:131`.
- Item 33: research note (markdown artifact) về nâng cấp `activeDebuggeeTabId: number | null` → `Map<number, SessionContext>` trong `nowing_browser_extension/background/cdp-bridge.ts` — phân tích blast radius + đề xuất thời điểm thực hiện. Output là decision doc, không code.

**Never:**
- Không đổi URL path, response model, status code hay dependency signature nào của dsh endpoints.
- Không thay thế `bds_aggregator/dedupe.py` hay `jobs_aggregator/dedupe.py` — spatial dedup chỉ bổ sung ở điểm thích hợp.
- Không code multi-tab `CdpBridge` trong sweep này (item 33 là research).
- Không đụng item 28 (infra) và item 35 (product policy).

</frozen-after-approval>

## Code Map

- `nowing_backend/app/routes/dsh_routes.py` (809 dòng) — 2 routers `dsh_public_router` (mount `/api/v1`, tags dsh) + `dsh_internal_router` (mount `/v1`) tại `app/app/factory.py:58,525,528`. Route map: `post /workspaces/{wid}/dsh/missions` (~124), `get` public mission (~186), `get` list (~220), `get` control (~277), internal `get` mission (~311), internal `patch` checkpoint (~337), internal `post` notify high-fit (~394), `get /dsh/cdp/stream` (~430), `post /dsh/cdp/result` (~537), `post /dsh/missions/{id}/pause` (~635), `resume` (~679), `abort` (~756), `post` sweep takeovers (~790). Helpers ở đầu file: `_verify_dsh_worker_secret` (59), `require_dsh_worker` (68), `_require_pat_workspace_scope` (91), `_require_mission_access` (108).
- Test patch targets cần cập nhật: `tests/unit/tasks/dsh_worker/test_takeover_abort_scheduler.py:12` (`abort_mission, resume_mission, sweep_takeovers`), `tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py:226-227` (`patch app.routes.dsh_routes.get_redis_client`, `cdp_stream`), `tests/unit/routes/test_dsh_cdp_stream.py:14,73,75,127` (`cdp_stream`, `get_redis_client`, `time.monotonic`).
- `nowing_backend/app/services/dedup/spatial_windowed_dedup.py` (170 dòng) — `SpatialWindowedDeduplicator.deduplicate(Sequence[dict]) -> list[DeduplicatedGroup]`; `_default_bucket_fn` dùng `location/city/domain`, `_default_sort_key_fn` dùng `title/company_name` + `posted_at/created_at`, `_are_duplicates` = Jaccard ≥ 0.80 + price delta ≤ 15%. 0 production call site (chỉ `tests/unit/services/test_spatial_windowed_dedup.py`).
- Candidate call sites cho item 41: `nowing_backend/app/tasks/celery_tasks/social_medirus_ingest.py` (`_ingest_social_target` ~222, raw dicts), `nowing_backend/app/services/chainlens/ingest.py`, `nowing_backend/app/services/lead_batch_service.py` (`_prepare_lead_record` dict shape ~257). `bds_aggregator/dedupe.py:57 find_match_candidates` đã có pattern bucket+jaccard tương đương — KHÔNG refactor nó.
- `nowing_web/tests/extension/extension.fixture.ts` — pattern có sẵn (`launchPersistentContext`, `--disable-extensions-except`, `--load-extension`, `channel: "chrome"`, headless). Extension mục tiêu: `nowing_browser_extension` (Plasmo, build dir `build/chrome-mv3-prod`, manifest có permission `debugger` + `<all_urls>`). Playwright config: `nowing_web/playwright.config.ts` testDir `./tests`.
- `nowing_browser_extension/background/cdp-bridge.ts` (855 dòng) — `activeDebuggeeTabId` single-tab state (item 33 research).
- `nowing_backend/app/services/pii/verified_contact_encryption.py:131` — `rotate_encryption(contact)` method (SOP item 36).
- `nowing_backend/app/services/web_builder/deploy/custom_domain.py:172` + `service.py:538` — `_nowing-verify.<domain>` TXT verification logic (DNS probe item 29).

## Tasks & Acceptance

- [x] **Item 31** — `app/routes/dsh/` package; `dsh_routes.py` deleted; `factory.py` + 3 test files updated; `ruff check` + `pytest tests/unit/routes/test_dsh_cdp_stream.py tests/unit/tasks/dsh_worker -q` xanh; `uv run python -c "from app.app import app"` OK. (commit `75d048c98`)
- [x] **Item 41** — `deduplicate_stream`/`iter_deduplicate` (generator, bounded memory, contract ghi rõ); 1 production call site; unit test mới (streaming behavior + lazy eval + kết quả giống `deduplicate()`); `ruff` + pytest xanh. (commit `75d048c98`)
- [x] **Item 32** — `nowing_web/tests/extension/` MV3 fixture cho `nowing_browser_extension` + spec kiểm thử luồng onDetach/takeover phần testable; skip khi thiếu build; `biome check` + `tsc` xanh. (commit `75d048c98`)
- [x] **Item 29** — `scripts/dns_synthetic_probe.py` (hoặc tên tương đương) kiểm tra TXT `_nowing-verify` + CNAME; chạy được standalone, exit code phản ánh kết quả; có `--help`. (commit `75d048c98`)
- [x] **Item 36** — `docs/ops/secret-key-rotation-sop.md` (hoặc tên tương đương): quy trình đầy đủ rotate → verify → remove OLD_SECRET_KEY. (commit `75d048c98`)
- [x] **Item 33** — `_bmad-output/implementation-artifacts/epic-32-cdpbridge-multitab-research.md`: phân tích cdp-bridge.ts hiện tại, thiết kế `Map<number, SessionContext>`, blast radius, đề xuất khi nào implement. (commit `75d048c98`)
- [x] **Cập nhật `sprint-status.yaml`**: 6 items → `done` (ref spec file này); items 28 + 35 giữ `open` (ghi reason ở spec này).
- [x] **Cập nhật `deferred-work.md`**: thêm entry items 28 + 35 là blocked-outside-repo (infra/product decision).
- [x] Jev `code_review_gate.yaml` trước commit → nếu `needs_deep_review`/`needs_tests` thì **dừng, báo user trước, chờ xác nhận** rồi mới commit.

## Implementation Notes

- Đã đóng toàn bộ 6 items nợ kỹ thuật:
  - Item 31: Tách `dsh_routes.py` (809 dòng) thành module `app/routes/dsh/{__init__,deps,missions,cdp,takeover}.py`, xóa god-file cũ, import sạch trong `factory.py`.
  - Item 41: Thêm `deduplicate_stream` và `iter_deduplicate` vào `SpatialWindowedDeduplicator` với memory bound theo bucket, đấu nối vào `bds_aggregator/orchestrator.py:168-184`.
  - Item 32: Thêm Playwright fixture `extension.fixture.ts` tải MV3 persistent context và test spec `lead-clipper.spec.ts`.
  - Item 29: Thêm `scripts/dns_synthetic_probe.py` (TXT + CNAME verification) kèm 6 unit tests (`tests/unit/test_dns_synthetic_probe.py`).
  - Item 36: Thêm SOP `docs/ops/secret-key-rotation-sop.md` hướng dẫn chi tiết quy trình 4 pha xoay vòng `SECRET_KEY` và `SECONDARY_SECRET_KEY`.
  - Item 33: Thêm research artifact `_bmad-output/implementation-artifacts/epic-32-cdpbridge-multitab-research.md` phân tích `Map<number, SessionContext>` và khuyến nghị defer.
- Item 28 và 35 đã ghi nhận hoãn tại `deferred-work.md` (blocked-outside-repo).
- Trạng thái sprint-status đã chuyển 6 items sang `done`.

