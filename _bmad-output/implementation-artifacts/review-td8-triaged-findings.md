# Code Review Triage — td-8 Epic 13 canonical entity cleanup

## Review metadata

- **Tech-debt:** `td-8`
- **Commit:** `542b84d61` — "refactor: remove Epic 13 canonical entity dead code"
- **Diff source:** `_bmad-output/implementation-artifacts/review-td8-epic13-cleanup.diff`
- **Spec:** `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-22-correct-course-audit.md`
- **Review layers:** Blind Hunter (no structured result), Edge Case Hunter (no structured result), Acceptance Auditor (returned)
- **Triage date:** 2026-08-22
- **Status:** ✅ APPROVED — all patches applied, tracking updated, P6 test coverage restored.

## Triage summary

| Bucket | Count |
|---|---|
| `decision_needed` | 1 |
| `patch` | 7 |
| `defer` | 2 |
| `dismiss` | 0 |

## Findings

### D1 — [HIGH] `decision_needed`: Commit bỏ qua giai đoạn deprecation 1 sprint và DROP TABLE ngay; SCP/tracking sai lệch

- **id:** 1
- **source:** auditor+main
- **severity:** high
- **bucket:** decision_needed
- **title:** Epic 13 bị xoá sạch trong 1 commit duy nhất thay vì "deprecation 1 sprint rồi drop"; SCP §7 ghi "deprecation pass completed" không có thật trong git; tracking stale.
- **location:** `nowing_backend/alembic/versions/d33c362fa627_drop_canonical_entities.py:19-38`, `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-22-correct-course-audit.md:92-94,198-215`, `_bmad-output/implementation-artifacts/deferred-work.md:579`, `_bmad-output/implementation-artifacts/sprint-status.yaml:412`, `_bmad-output/planning-artifacts/epics.md:133`
- **detail:**
  - SCP §4 xác định rủi ro lớn nhất là "xóa canonical entities quá sớm mà vẫn còn test/edge case phụ thuộc" và mitigation "deprecation 1 sprint, sau đó drop".
  - SCP §5.4 ghi "Không xóa migration/table vội — chỉ khi td-8 được approve và run".
  - Nhưng commit `542b84d61` (2026-08-22, cùng ngày SCP adopted) gộp: (a) xoá package `app/canonical/`, routes, tests; (b) ship migration `d33c362fa627` DROP TABLE CASCADE + `downgrade()` raise `NotImplementedError`; (c) không có giai đoạn warning, không archival/export dữ liệu cho self-host deployments.
  - SCP §7 Implementation Log claim "deprecation warnings added to `app/canonical/__init__.py`, `canonical_persist_service.py`, `unified_search_service.py`, `canonical_entities_routes.py`, `pyproject filterwarnings`" — nhưng `git show 542b84d61~1` chỉ ra docstring trung tính, `grep warn/deprecat` trên parent rỗng, `git log --all -S "DeprecationWarning"` rỗng.
  - Ledger sai lệch ngay trong diff: `sprint-status.yaml` thêm `td-8: backlog` dù work đã xong; `deferred-work.md:579` nói "Deprecation warning added to `nowing_backend/app/canonical/__init__.py`. Next: identify all live call paths..." — file đó đã bị xoá; `epics.md` AR-16 vẫn viết ở dạng tương lai.
- **Resolution chọn:** **Fast-track approved** — code đã xoá sạch, migration `d33c362fa627` đã ship, `git grep` xác nhận zero live callers, và rollback sẽ gây data-migration pain. Đã apply: cập nhật `deferred-work.md:579`, `epics.md` AR-16, `sprint-status.yaml:412` (td-8 → done), và thêm note fast-track vào SCP §7.

### P1 — [HIGH] `patch`: Celery beat vẫn dispatch task `process_canonical_persist_outbox` đã bị xoá

- **id:** 2
- **source:** main
- **severity:** high
- **bucket:** patch
- **title:** Beat schedule `process-canonical-persist-outbox` gọi task không còn tồn tại.
- **location:** `nowing_backend/app/celery_app.py:372-377`
- **detail:** `grep` toàn repo chỉ tìm thấy `process_canonical_persist_outbox` duy nhất ở dòng 374 (beat entry). Worker sẽ log "Received unregistered task" mỗi 2 phút trên prod. Fix unambiguous: xoá beat entry.

### P2 — [MEDIUM] `patch`: Metric + helper `record_canonical_persist_failure` dead

- **id:** 3
- **source:** main
- **severity:** medium
- **bucket:** patch
- **title:** Counter `nowing.canonical.persist.failed` và `record_canonical_persist_failure` không còn caller nhưng vẫn được tạo và export.
- **location:** `nowing_backend/app/observability/metrics.py:1481-1500` (và `__all__` dòng 1500)
- **detail:** `grep` chỉ thấy 3 tham chiếu: định nghĩa counter (1483), định nghĩa hàm (1488), export `__all__` (1500). Không còn caller. Fix: xoá counter, hàm, và tên trong `__all__`.

### P3 — [MEDIUM] `patch`: `epics.md` coverage map E1 không áp dụng

- **id:** 4
- **source:** auditor
- **severity:** medium
- **bucket:** patch
- **title:** Coverage map `OQ-3/AR-4 → E3.7 [PARTIAL]` mâu thuẫn với AR-4 vừa sửa thành document retention `[DONE]`.
- **location:** `_bmad-output/planning-artifacts/epics.md:249`
- **detail:** SCP §3.2 E1 yêu cầu đổi thành `[DONE for document retention; PARTIAL for memory retention]`. Diff chỉ sửa AR-4 (thêm `[DONE]`) nhưng bỏ sót dòng coverage map. Fix unambiguous: cập nhật dòng 249.

### P4 — [LOW] `patch`: `tenant_context.py` ghi `session.info["canonical_workspace_id"]` không còn reader

- **id:** 5
- **source:** main
- **severity:** low
- **bucket:** patch
- **title:** Key `canonical_workspace_id` trong `session.info` là dead data.
- **location:** `nowing_backend/app/tenant_context.py:71`
- **detail:** `grep` chỉ thấy 1 tham chiếu duy nhất tại dòng 71 (writer); không còn reader. Fix: bỏ dòng hoặc đổi thành `workspace_id` nếu cần. Cần kiểm tra tests không phụ thuộc.

### P5 — [LOW] `patch`: `_source_name_for_canonical` là dead helper

- **id:** 6
- **source:** main
- **severity:** low
- **bucket:** patch
- **title:** Hàm `_source_name_for_canonical` trong `rss_indexer.py` không còn caller.
- **location:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:127-140`
- **detail:** `grep` toàn repo chỉ thấy định nghĩa tại dòng 127. Fix unambiguous: xoá hàm.

### P6 — [MEDIUM] `patch`: Mất test coverage cho RSS prune/ingest khi xoá `test_rss_indexer_units.py` — RESOLVED

- **id:** 7
- **source:** main+auditor
- **severity:** medium
- **bucket:** patch
- **title:** `tests/unit/services/news/test_rss_indexer_units.py` (755 dòng cũ) bị xoá; đã rewrite 28 unit test case cho kiến trúc mới.
- **location:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py`, `nowing_backend/tests/unit/services/news/test_rss_indexer_units.py`
- **detail:** Đã tạo lại `test_rss_indexer_units.py` với 28 test case phù hợp post-cleanup: `_news_fingerprint`, `_format_pub_date`, `_build_source_markdown`, `_prune_stale_articles` (chỉ xoá `Chunk`/`Document`, batching, cutoff), `_persist_canonical_articles` (gọi `NowingIngestService.ingest` qua `to_chunks`), `index_rss_feeds` (error/heartbeat/dedup/pipeline). `uv run pytest tests/unit/services/news/test_rss_indexer_units.py -q`: **28 passed**; full unit suite: **5692 passed, 3 skipped**.

### P7 — [LOW] `patch`: Migration drop canonical entities không gọi `apply_publication`

- **id:** 8
- **source:** auditor
- **severity:** low
- **bucket:** patch
- **title:** Migration `d33c362fa627_drop_canonical_entities.py` thay đổi schema realtime nhưng không gọi `apply_publication`.
- **location:** `nowing_backend/alembic/versions/d33c362fa627_drop_canonical_entities.py:19-31`
- **detail:** `zero_publication.py:5` quy định "Future publication changes should update `ZERO_PUBLICATION` and call `apply_publication()` from a migration instead of hand-copying table lists". Hiện migration chỉ `DELETE FROM zero_publication` tay. Mặc dù Postgres tự động detach bảng bị DROP khỏi publication, việc không gọi `apply_publication` đi ngược quy ước. Fix low-risk: gọi `apply_publication(op.get_bind())` sau khi xoá bảng.

### W1 — [MEDIUM] `defer`: NG-5 residual — `cafef` và `rss_indexer` chưa feed đúng vào chainlens-research

- **id:** 9
- **source:** auditor
- **severity:** medium
- **bucket:** defer
- **title:** `cafef` scraper vẫn index cục bộ KB; `rss_indexer` dual-write (local + chainlens). Đây là pre-existing, không phải regression của commit.
- **location:** `nowing_backend/app/capabilities/cafef/scrape/executor.py:50-93`, `nowing_backend/app/tasks/connector_indexers/rss_indexer.py`
- **detail:** Commit đạt phần cốt lõi của NG-5 (không còn writer vào `canonical_entities`). Tuy nhiên `cafef` chưa forward `Chunk[]` sang chainlens, `rss_indexer` vừa ghi local `Document/Chunk` vừa feed chainlens. Cần theo dõi trong story cải thiện consistency scraper feed.

### W2 — [LOW] `defer`: `ChainLensIngestJob` mất observability (cần xác minh chủ đích)

- **id:** 10
- **source:** main
- **severity:** low
- **bucket:** defer
- **title:** `ChainLensIngestJob` có vẻ mất observability/metrics tại ingest path (có thể chủ đích).
- **location:** `nowing_backend/app/services/chainlens/ingest.py` / `ingest_reception.py`
- **detail:** Ghi nhận từ main thread — cần xác minh xem metrics/observability cho `ChainLensIngestJob` bị bỏ sót hay là do refactor chủ đích. Không đủ evidence để patch ngay.

## Re-run blind-hunter + edge-case-hunter findings (2026-08-23)

Subagent quota đã hết nên chạy 2 layer bằng tay theo skill instructions. Đã triage thành 8 findings mới (P8–P15 patched, W3–W8 deferred/accepted).

### P8 — [LOW] `patch`: `_prune_stale_articles` docstring stale

- **id:** 11
- **source:** blind-hunter
- **severity:** low
- **bucket:** patch
- **title:** Docstring vẫn nói xoá "canonical provenance rows and any canonical entities" trong khi code chỉ xoá `Chunk`/`Document`.
- **location:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:193-198`
- **detail:** Đã patch docstring thành "remove their local `Document` and `Chunk` rows. Canonical indexing is owned by `chainlens-research`."

### P9 — [MEDIUM] `patch`: RSS prune có thể xoá article từ feed bị transient failure

- **id:** 12
- **source:** edge-case-hunter
- **severity:** medium
- **bucket:** patch
- **title:** `_prune_stale_articles` chạy khi một feed thành công và một feed khác thất bại, `seen_links` không chứa link feed bị lỗi, article cũ của feed đó bị xoá.
- **location:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:409-420`
- **detail:** Đã thêm guard `if not fetch_errors:` quanh `_prune_stale_articles`, chỉ prune khi mọi feed đều fetch thành công, khớp với ghi chú `deferred-work.md:672`. Đã thêm test mới `test_index_rss_feeds_partial_failure_skips_prune`.

### P10 — [MEDIUM] `patch`: `bds_aggregator` / `jobs_aggregator` truyền `session=None` vào `NowingIngestService.ingest`

- **id:** 13
- **source:** blind-hunter + edge-case-hunter
- **severity:** medium
- **bucket:** patch
- **title:** `_persist_bds_aggregates` và `_persist_jobs_aggregates` bỏ qua `AsyncSession` có sẵn, không persist `ChainLensIngestJob`.
- **location:** `nowing_backend/app/services/bds_aggregator/orchestrator.py:220-224`, `nowing_backend/app/services/jobs_aggregator/orchestrator.py:210-214`
- **detail:** Đã truyền `session=session` (với guard `isinstance(session, AsyncSession)` để test `SimpleNamespace` vẫn `not_attempted`) và map `IngestResult.status` sang `persistence_status` (`ok`/`partial`/`failed`). Unit test `test_orchestrator_persist.py` đã cập nhật mock trả về `SimpleNamespace(status="ok", error=None)`.

### P11 — [LOW] `patch`: `masothue.scrape` mutate input dict in place

- **id:** 14
- **source:** blind-hunter
- **severity:** low
- **bucket:** patch
- **title:** Executor gán `item["title"] = ...` trực tiếp lên dict đầu vào.
- **location:** `nowing_backend/app/capabilities/masothue/scrape/executor.py:129-130`
- **detail:** Đã copy dict trước khi set `title`, tránh sửa caller data. Simplified with ternary theo gợi ý `ruff SIM108`.

### P12 — [LOW] `patch`: `rss_indexer._prune_stale_articles` xoá `Document` không batch

- **id:** 15
- **source:** edge-case-hunter
- **severity:** low
- **bucket:** patch
- **title:** `Chunk` được xoá theo batch 500, `Document` xoá trong 1 statement duy nhất.
- **location:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:228-235`
- **detail:** Đã chuyển `Document` delete vào trong cùng vòng lặp batch với `Chunk`. Cập nhật test `test_prune_stale_articles_batches_chunk_deletes` kỳ vọng từ 3 thành 4 statements.

### P13 — [LOW] `patch`: `bds_aggregator.aggregate` bắt `BaseException`

- **id:** 16
- **source:** edge-case-hunter
- **severity:** low
- **bucket:** patch
- **title:** `asyncio.gather(return_exceptions=True)` trả về `BaseException`; code bắt cả `KeyboardInterrupt`/`SystemExit`.
- **location:** `nowing_backend/app/services/bds_aggregator/orchestrator.py:294-296`
- **detail:** Đã thu hẹp thành `isinstance(result, Exception)` và dùng `logger.error` thay vì `logger.exception`.

### P14 — [LOW] `patch`: `scraper_chunks/serializer.py` module docstring stale

- **id:** 17
- **source:** blind-hunter
- **severity:** low
- **bucket:** patch
- **title:** Docstring gọi output là "canonical `Chunk[]` objects" trong khi canonical index đã chuyển sang `chainlens-research`.
- **location:** `nowing_backend/app/services/scraper_chunks/serializer.py:1`
- **detail:** Đã đổi thành "Normalize heterogeneous scraper output into `Chunk[]` for chainlens-research."

### P15 — [LOW] `defer-patch`: `_persist_canonical_articles` tên hàm misleading

- **id:** 18
- **source:** blind-hunter
- **severity:** low
- **bucket:** defer (cosmetic; will rename in follow-up cleanup)
- **title:** `_persist_canonical_articles` thực chất gửi sang `chainlens-research`, không persist local.
- **location:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:126`, `tests/unit/services/news/test_rss_indexer_units.py`
- **detail:** Tên gây hiểu nhầm. Không rename trong vòng này để tránh churn test; để lại story cleanup tên hàm RSS.

### W3 — [LOW] `defer`: migration `d33c362fa627` `downgrade()` `NotImplementedError`

- **id:** 19
- **source:** blind-hunter
- **severity:** low
- **bucket:** defer
- **title:** Không có rollback tự động cho việc xoá bảng canonical.
- **location:** `nowing_backend/alembic/versions/d33c362fa627_drop_canonical_entities.py:38-42`
- **detail:** Là intentional (canonical thuộc về chainlens-research). Nếu cần, phải restore từ backup chứ không recreate từ migration. Để follow-up doc hướng dẫn rollback.

### W4 — [MEDIUM] `defer`: `NowingIngestService.ingest` chiếm transaction boundary

- **id:** 20
- **source:** edge-case-hunter
- **severity:** medium
- **bucket:** defer
- **title:** `NowingIngestService.ingest` gọi `session.commit()`/`rollback()` bên trong service, ảnh hưởng transaction caller.
- **location:** `nowing_backend/app/services/chainlens/ingest.py:479-498`
- **detail:** Hiện là contract by design (test `test_ingest_returns_ingest_job_id_and_persists_mapping` expect `session.commit`). Để design review khi chuẩn hoá ingest pattern cho toàn bộ scraper.

### W5 — [MEDIUM] `defer`: `IngestResult` bị ignore ở `masothue` và `rss_indexer`

- **id:** 21
- **source:** blind-hunter
- **severity:** medium
- **bucket:** defer
- **title:** `masothue` và `rss_indexer` không dùng `IngestResult` để báo `degraded`/warning khi chainlens thất bại.
- **location:** `nowing_backend/app/capabilities/masothue/scrape/executor.py:143-154`, `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:404-407`
- **detail:** `bds`/`jobs` đã sử dụng. Cần design cho propagation status lên capability output / indexing warning mà không phá billing/tests.

### W6 — [LOW] `defer`: thiếu metric ingest failure theo scraper domain

- **id:** 22
- **source:** blind-hunter
- **severity:** low
- **bucket:** defer
- **title:** Mất `record_canonical_persist_failure` nhưng chưa thay bằng metric per-domain chainlens ingest.
- **location:** `nowing_backend/app/observability/metrics.py` + các call site `NowingIngestService.ingest`
- **detail:** `NowingIngestService.ingest` đã emit `record_chainlens_ingest_failed` chung. Cần theo dõi thêm domain dimension trong story observability scraper feed.

### W7 — [LOW] `defer`: `masothue` chỉ feed chainlens khi `ctx is not None`

- **id:** 23
- **source:** blind-hunter
- **severity:** low
- **bucket:** defer
- **title:** Nếu gọi executor không có `CapabilityContext`, scraper chạy nhưng không gửi chunk.
- **location:** `nowing_backend/app/capabilities/masothue/scrape/executor.py:126`
- **detail:** Là design (capability luôn có ctx trong production). Cần xác định rõ contract test/direct-call.

### W8 — [LOW] `defer`: `bds`/`jobs` vẫn charge khi `persistence_status` = failed

- **id:** 24
- **source:** blind-hunter
- **severity:** low
- **bucket:** defer
- **title:** `cost_micros` tính trước khi persist; nếu `persistence_status` = failed, user bị charge dù dữ liệu không vào index.
- **location:** `nowing_backend/app/services/bds_aggregator/orchestrator.py:322-326`, `nowing_backend/app/services/jobs_aggregator/orchestrator.py:281-282`
- **detail:** Pre-existing; cần quyết định business rule (charge scraper cost vs charge chỉ khi ingest ok) trong story billing/payment.

### A1 — [LOW] `accept`: `CASCADE` trong migration là an toàn

- **id:** 25
- **source:** edge-case-hunter
- **severity:** low
- **bucket:** accept
- **title:** `DROP TABLE ... CASCADE` có thể xoá FK từ bảng ngoài.
- **location:** `nowing_backend/alembic/versions/d33c362fa627_drop_canonical_entities.py:20-25`
- **detail:** Kiểm tra `app/db.py`, `alembic/versions/193`, `194` — các canonical table chỉ FK đến `workspaces` và lẫn nhau, không có FK ngoài. `CASCADE` an toàn.

## Verdict

**APPROVED — patches extended (P1–P14 applied, P15 deferred), W1–W8 documented, tracking updated, P6 test coverage restored.**

`D1` resolved as **fast-track approved**: `deferred-work.md:579`, `epics.md` AR-16, `sprint-status.yaml:412`, và SCP §7 đã cập nhật phản ánh reality.

`P6` đã xử lý trong 4.9: rewrite `tests/unit/services/news/test_rss_indexer_units.py` với 28 test case, `ruff` PASS, `pytest` 28 passed, full unit suite **5692 passed, 3 skipped**. `W1-W2` vẫn defer. `blind-hunter` + `edge-case-hunter` không trả kết quả nên review có thể thiếu góc nhìn adversarial/path-tracing.

## Next steps in Nowing quality pipeline

**Vừa xong:** `bmad-code-review` — triage hoàn tất, chờ decision + patch handling.

**Bước tiếp theo (BẮT BUỘC):**
- [4.7] `bmad-dev-story` / `bmad-quick-dev` — apply patches theo lựa chọn user (nếu user chọn apply).

**Bước tiếp theo (recommended):**
- [4.9] `bmad-testarch-test-review` — verify lại test coverage sau khi `test_rss_indexer_units.py` được thay thế hoặc rewrite.
- [4.10] `bmad-nowing-mutation-gate` — chỉ áp dụng nếu patch chạm P0 files (diff này không touch token/credit/auth/pricing/RAG).

**Còn lại trong pipeline:** xem `nowing-quality-pipeline.md`.
