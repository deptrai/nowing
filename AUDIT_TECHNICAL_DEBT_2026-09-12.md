# Nowing — Re-audit tính năng & Technical-Debt (lần 2)

> Ngày: 2026-09-12
> Commit: `HEAD` (develop), so với audit trước `9d1fca0b8` ngày 2026-08-30
> Phạm vi: toàn repo `nowing` (backend, web, tests, docker, mcp, evals, desktop, obsidian)
> Phương pháp: code-review-graph incremental rebuild + đo lại toàn bộ metric của audit cũ + spot-check invariants

---

## 1. Tóm tắt điều hành

**Refactor plan ngày 30/8 đã được thực thi ở quy mô lớn.** Hầu hết các monolith P0/P1 của audit trước đã được tách thật — không phải rename. Đây là thay đổi kiến trúc quan trọng nhất kể từ khi có audit.

- **Codebase**: 5.758 file (+471), graph 40.063 node / 351.203 cạnh (+3.535 / +37K).
- **Backend**: 2.228 file `.py` / ~335.260 dòng trong `app/`; tests 1.152 file / ~204.254 dòng (822 unit + 294 integration + 30 e2e).
- **Frontend**: 1.440 file TS/TSX / ~214.972 dòng; 100 spec Playwright (+10).
- **Evals**: 171 file / ~37.979 dòng. MCP: 92 file / ~9.171 dòng. Alembic: 296 migrations.
- **246 commits** kể từ audit trước, phần lớn là campaign dọn "deferred items" + Epic 26/29/30/31.
- **File lớn nhất backend**: 1.496 dòng (trước: 6.955). **Frontend**: 1.427 dòng (trước: 2.413).
- **Quality gate CI thật sự tồn tại**: 17 workflows, pre-commit (detect-secrets + bandit + ruff + biome), `check_pr_guards.py` ratchet chặn nợ mới.

**Nợ còn lại tập trung ở**: `except Exception` vẫn tăng nhẹ (1.800 vs 1.753), exception hierarchy mới tạo nhưng chưa được adopt (<3%), 89 block nuốt lỗi thật, `check_permission` vẫn gọi thủ công 268 chỗ, dead files committed (`db.py.legacy` 7K dòng, `.bak`), 143 file rác ở root, và một mutation-gate baseline đang hỏng.

---

## 2. Scorecard — các phát hiện 30/8 giờ ra sao

| # | Phát hiện cũ | Trạng thái | Bằng chứng |
|---|---|---|---|
| P0-1 | `db.py` 6.955 dòng | ✅ Đã tách | `db/` package (`__init__` 426 re-export, `base` 192, `enums` 667, `permissions` 81) + `models/` theo domain (workspaces 931, chat 792, billing 662, users 615, memory 582...). 804 file `from app.db import` vẫn chạy nhờ shim — strangler-fig đúng chuẩn. |
| P0-2 | `except Exception` 1.753 | ⚠️ Tệ hơn nhẹ | **1.800** hits / 559 file (+47). routes/+services/: 716 (trước 699). `exceptions.py` với `NowingError` hierarchy đã tồn tại nhưng chỉ **49 raise / 16 file** — adoption ~3%. 89 block `except: pass/continue` nuốt lỗi thật. PR guard chặn *dòng mới* trong routes/services — ratchet, không phải fix. |
| P0-3 | `set_event_loop_policy` ở module import | 🔶 Một phần | `documents_routes.py` đã sạch. Vị trí đúng: `app/lifespan.py:241`. Còn sót: `tasks/process_meeting_minutes.py:28`, `tasks/celery_tasks/video_presentation_tasks.py:27`. |
| P0-4 | `print()` 106 lần | ✅ Gần như xong | Còn 27 hits / 6 file. Ruff **T201 đã bật** kèm per-file-ignore cho testbench CLI + `zero_publication` (hợp lệ). Sót thật chỉ còn `connectors/luma_connector.py` (~10 prints trong auth/demo helper). |
| P0-5 | `use-connector-dialog.ts` 1.433 dòng | ✅ Đã tách | Thành `hooks/use-connector-dialog/` gồm creation (421), edit (412), indexing (367), index (352). |
| P1-6 | `search_source_connectors_routes.py` 3.284 | ✅ Đã tách | `routes/connectors/` package (`crud.py`, `indexing/core.py` 977, `mcp.py`, `_shared.py`). |
| P1-7 | `ConnectorService` 2.242 dòng | ✅ Đã tách | `connector_service.py` còn 11 dòng shim; logic chuyển vào `services/connectors/`. |
| P1-8 | `llm_router_service` singleton | ✅ Đã tách | File còn 116 dòng; có `services/llm_router/` package (chat_model 811...). Chưa verify sâu thread-safety mới. |
| P1-9 | `config/__init__.py` 1.948 dòng | ✅ Đã tách | Còn 140 dòng + 25 module theo domain (auth, billing, database, llm, gateway...). `os.getenv` 423/502 hits nằm trong `config/` — encapsulation đạt ~84%. |
| P1-10 | `documents_routes.py` 2.074 dòng | ✅ Đã tách | Còn 7 dòng shim. |
| P1-11 | `thread.tsx` 2.413 dòng | ✅ Đã tách | `components/assistant-ui/thread/` (Composer 848, ComposerAction 812...). `CampaignBuilder.tsx` → `campaign-builder/` + hook 503. |
| P2-12 | `nowing_web` 3.6 GB | 🔶 Không phải vấn đề repo | Giờ 6.1 GB nhưng gần hết là `node_modules` 3.3G + `.next` 2.5G — dev artifacts đã gitignore. Bundle-size audit vẫn chưa có bằng chứng. |
| P2-13 | Hub UI primitives (Button in-degree 788) | ❓ Chưa đo lại | Chưa thấy ADR freeze API. |
| P2-14 | Alembic `downgrade()` không test | 🔶 Một phần | Có roundtrip test cho vài migration (180, 186); chưa có CI job `downgrade -1` tổng quát. 296 versions. |
| P2-15 | `check_permission` gọi thủ công | ❌ Chưa | Vẫn **268 calls / 70 file**; `require_permission` dependency chỉ 6 hits / 1 file. |
| P2-16 | `web_builder` subprocess injection | ✅ Đã sandbox | `builder.py` giờ chạy `docker run --rm --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges --memory 1024m --cpus 2.0` + timeout + `killpg` cleanup + force `docker rm -f`. ADR-5 landed. |
| P2-17 | `Popen` trong admin scraper route | ✅ Đã fix | Chuyển sang `celery_tasks/scraper_capture_tasks.py` với `asyncio.create_subprocess_exec` + comment giải thích rõ. |
| P3-18 | `console.*` 262 lần | ⚠️ Tệ hơn nhẹ | **287** hits / 126 file (+25). |
| P3-19 | Test `.only`/`.skip` | 🔶 Một phần | **0 `.only(`** trong web (đã sạch). Còn 24 `.skip(`; backend `pytest.mark.skip` 46→32. PR guard chặn cái mới. |
| P3-20 | Biome `--max-diagnostics 500` | ❓ Chưa verify | — |
| P3-21 | `metrics.py` 1.532 dòng boilerplate | ✅ Đã xóa | File không còn; `observability/` package tồn tại (`bootstrap.py`...). |

**Tổng kết scorecard: 13 ✅ / 4 🔶 / 1 ⚠️ thật sự / 1 ❌ / 2 ❓** — tỉ lệ xử lý cao bất thường cho một refactor plan.

---

## 3. Kiến trúc hiện tại

### 3.1 Backend đã chuyển sang domain-packaging

Top-level packages mới so với audit cũ: `admin/`, `alerts/`, `automations/`, `event_bus/`, `file_storage/`, `gateway/`, `indexing_pipeline/`, `notifications/`, `observability/`, `reports/`, `retriever/`, `models/`, `db/`, `app/` (factory 594 / lifespan 388 / errors 280 — `app.py` root còn 5 dòng).

`app/app/` là tên package hơi khó đọc nhưng cấu trúc đúng: factory + lifespan + errors + rate_limiter tách khỏi module khởi động.

### 3.2 Invariants (project-context.md) — spot check

| Invariant | Kết quả |
|---|---|
| PII Dual-Vault (AD-25/49) | ✅ Thật: `TokenEncryption`/Fernet 345 refs / 68 file, `VerifiedContact` 194 refs / 30 file, `redact_pii` 37 uses / 15 file |
| NG-5 không canonical index | ✅ `canonical_entities`/`canonical_index` = **0 hits** |
| Zero URL parity, cookie domain | (config-level, không re-check lần này) |
| Structured error envelope | 🔶 `exceptions.py` + `app/errors.py` 280 dòng đã có — nhưng adoption thấp (xem P0-2) |

### 3.3 Graph structure

- Communities top vẫn là `services-fake`, `apis-handle`, `suites-gate` — backend vẫn là một cộng đồng lớn (kỳ vọng — graph theo import, domain packages vẫn liên kết chéo qua `app.db`/`app.config`).
- Graph báo **233 test gaps** (hub nodes chưa có test).
- Risk score 0.60 (medium). Blast radius của 246 commits: 3.262 file đổi → 7.915 node chạm trực tiếp.

---

## 4. Technical debt còn lại & phát hiện mới — P0–P3

### P0 — Critical

#### 1. `except Exception` vẫn tăng; `NowingError` hierarchy chưa được adopt
- **1.800** hits / 559 file (+47 so với audit cũ); routes+services 716. Guard chỉ chặn dòng mới ở routes/ và services/ — tăng trưởng dồn sang `tasks/`, `agents/`, `connectors/`, `proprietary/`, `gateway/`.
- `NowingError`/`ConnectorError`/`DatabaseError`... chỉ được raise **49 lần / 16 file** — hierarchy tồn tại nhưng gần như chưa dùng.
- **89 block `except Exception: pass/continue`** — nuốt lỗi thật, không log.
- Top: `gateway/telegram/callbacks.py` 25, `proprietary/platforms/batdongsan/fetch.py` 19, `rbac_routes.py` 16, `workspaces_routes.py` 16, `process_upload.py` 15, `config/_helpers.py` 15.
- **Đề xuất**: mở rộng PR guard sang `tasks/`, `agents/`, `gateway/`; viết codemod chuyển `except: pass` → `logger.debug` tối thiểu; adopt `NowingError` theo từng domain thay vì big-bang.

#### 2. Dead/backup files committed vào git
- `nowing_backend/app/db.py.legacy` — **7.041 dòng**, tên file không thể import → dead code hoàn toàn, chỉ gây nhiễu search/refactor.
- `nowing_backend/app/config/global_llm_config.yaml.bak` — file `.bak` trong git.
- **143 file rác tracked ở root**: ~15 screenshot PNG, `dump.rdb`, `mcp-26-9-test.js`, `mcp-route-test.js`, `new_chat_response.txt`, `session_*_transcript.md`.
- **Đề xuất**: xóa (đã gitignore `.local_object_store` 7.2G đúng cách); thêm `check-added-large-files` đã có nhưng cần dọn lịch sử.

### P1 — High

#### 3. `services/` vẫn flat — thế hệ giant files mới đang hình thành
- 127 entries ở `services/`, ~40 file >500 dòng: `admin_telemetry_service.py` 1.059, `workspace_limits.py` 1.030, `phone_waterfall_service.py` 1.012, `chat_comments_service.py` 946, `workspace_health_service.py` 919...
- `routes/` còn 116 entries; `workspaces_routes.py` 1.291, `rbac_routes.py` 1.260, `gateway_webhook_routes.py` 1.207, `web_builder_routes.py` 1.147.
- PR guard fail ở >2.000 dòng nên các file 1.000–2.000 cứ lớn dần.
- **Đề xuất**: tiếp tục pattern `connectors/` đã chứng minh — tách theo domain khi file chạm ~800 dòng, đừng chờ 2.000.

#### 4. `check_permission` vẫn gọi thủ công 268 chỗ / 70 file
- Không có FastAPI dependency `RequirePermission` được adopt (6 hits / 1 file).
- **Đề xuất**: giữ nguyên đề xuất cũ — dependency injection cho RBAC; 268 call sites là audit surface lớn cho authz bugs.

#### 5. Mutation-gate baseline đang hỏng
- `mutation-nowing-summary-latest.json` (2026-09-09): verdict **FAIL** — `cosmic-ray baseline failed` cho `proprietary/platforms/xactions/mcp_client` (exit 1). Gate không chạy được = không có tín hiệu test-effectiveness cho surface đó.
- **Đề xuất**: sửa baseline trước khi gate mất uy tín; thêm alert khi verdict=FAIL.

### P2 — Medium

#### 6. Frontend: file >1.000 dòng còn 7 file
- `lib/chat/stream-engine/engine.ts` 1.427, `DocumentsSidebar.tsx` 1.364, `roles-manager.tsx` 1.274, `logs page` 1.257, `global-model-connections page` 1.257, `editor-panel.tsx` 1.105, `scraper-accounts page` 1.069.
- `console.*` 287 (+25). Cần `no-console` lint rule như đề xuất cũ.

#### 7. Alembic downgrade vẫn chưa có smoke test tổng quát
- 296 versions; chỉ vài migration có roundtrip test riêng. Đề xuất cũ đứng nguyên: CI job `alembic downgrade -1` trên test DB.

#### 8. `os.getenv` ngoài `config/` — 79 hits
- Đã giảm mạnh (423/502 trong config/) nhưng 79 chỗ đọc env trực tiếp ngoài config — bỏ qua validation/default tập trung. Đáng sweep một lần.

#### 9. `set_event_loop_policy` sót 2 file tasks
- `tasks/process_meeting_minutes.py:28`, `tasks/celery_tasks/video_presentation_tasks.py:27` — side-effect global khi import.

### P3 — Low / hygiene

#### 10. `print()` sót `luma_connector.py` (~10 prints) — chuyển `logger`.
#### 11. `app/app/` naming — nên đổi thành `app/server/` hoặc `app/bootstrap/` khi có dịp (non-blocking).
#### 12. 24 `.skip(` frontend + 32 `pytest.mark.skip` backend — lập danh sách review định kỳ.
#### 13. `observability/bootstrap.py` còn 12 `os.getenv` — module observability tự đọc env, nên qua `config/`.

---

## 5. Điều hành & process (mới so với audit trước)

- **Pre-commit pipeline**: check-yaml/json/toml, merge-conflict, large-files (10MB), debug-statements, detect-secrets (có baseline), bandit, ruff (+T201), ruff-format, biome.
- **`check_pr_guards.py`**: file-size limit (>2.000 fail existing / >2.500 fail new), cấm `.only(`, cấm `pytest.mark.skip` mới, cấm `except Exception` mới trong routes/services — **ratchet mechanism đúng chuẩn**, đây là lý do nợ không bùng nổ dù code tăng 471 file.
- **17 CI workflows**: code-quality, backend-tests, e2e, mutation-gate, chaos-gate, chat-regression, memory-recall, lead-extraction-regression, docker-build...
- **Docs drift check**: PASS — `docs/` đang đồng bộ với code.
- **Mutation testing** đang chạy định kỳ (artifact mới nhất 09/09) — nhưng xem P1-5.

---

## 6. Khuyến nghị ưu tiên

1. **Xóa dead files** (`db.py.legacy`, `*.bak`, 143 file rác root) — 1 giờ, diff âm lớn.
2. **Mở rộng PR guard** `except Exception` sang `tasks/`, `agents/`, `gateway/`, `connectors/` — nửa ngày, chặn điểm tăng trưởng thật.
3. **Codemod 89 block `except: pass`** → `logger.debug`/`logger.exception` — 1–2 ngày, khôi phục observability.
4. **Fix mutation-gate baseline** xactions/mcp_client — gate hỏng lâu sẽ bị ignore.
5. **`RequirePermission` dependency** — giảm 268 call-site authz thủ công, đây là attack surface thật.
6. **Tiếp tục tách `services/`/`routes/` theo domain** ở ngưỡng ~800 dòng — duy trì đà refactor đang rất tốt, đừng để thế hệ giant mới hình thành.
7. **`no-console` rule + alembic downgrade CI** — quick wins còn nợ từ audit trước.

## 7. Kết luận

Khác hẳn audit trước: **refactor plan không chỉ được viết mà đã được thực thi**. Monolith `db.py`/`config`/routes khổng lồ/component khổng lồ đều đã tách thật; subprocess đã sandbox; quality gate CI đã vận hành với cơ chế ratchet chống nợ mới.

Rủi ro còn lại không nằm ở cấu trúc nữa mà ở **độ sâu convention**: exception hierarchy có nhưng chưa ai dùng; error-swallowing còn 89 điểm; authz check phân tán thủ công. Đây là loại nợ "soft" — không chặn feature nhưng làm giảm reliability và auditability theo thời gian. Ba việc ở mục 6.1–6.4 đều là việc nhỏ, ROI cao, nên làm ngay.
