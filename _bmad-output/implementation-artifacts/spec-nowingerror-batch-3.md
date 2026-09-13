---
title: NowingError & Exception Narrowing — Batch 3 (External Integrations & Connectors Services)
type: refactor
created: '2026-09-13'
status: done
baseline_commit: bfa7e31a690e53a3915bc674d86a6358c9716616
review_loop_iteration: 0
context:
  - nowing_backend/app/exceptions.py
  - nowing_backend/app/services/composio/
  - nowing_backend/app/services/news/
  - nowing_backend/app/services/chainlens/
  - nowing_backend/app/services/google_calendar/
  - nowing_backend/app/services/gmail/
  - nowing_backend/app/services/confluence/
  - nowing_backend/app/services/linear/
  - nowing_backend/app/services/notion/
  - nowing_backend/app/services/google_drive/
  - nowing_backend/app/services/onedrive/
  - nowing_backend/app/services/dropbox/
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Có 89 vị trí `except Exception` trong các dịch vụ tích hợp bên thứ ba (Composio, News extraction, ChainLens, Google Calendar/Drive/Gmail, Confluence, Linear, Notion, OneDrive, Dropbox). Nhiều khối nuốt lỗi hoặc che giấu các lỗi kết nối API bên ngoài (401 token hết hạn, 429 rate limit, network timeout).

**Approach:** Refactor Batch 3 gồm 89 call-sites `except Exception` trên 25 files thuộc nhóm External Integrations & Connectors:
1. Với KB sync services: bắt cụ thể lỗi API / HTTP, phân biệt lỗi token/auth (cần re-raise hoặc đánh dấu invalid token) vs lỗi sync từng document (log warning và tiếp tục sync các file khác).
2. Với tool metadata services: bắt lỗi load / reflect tool schema, log cảnh báo rõ ràng, không làm crash connector initialization.
3. Với Composio integrations: phân biệt lỗi action execution vs entity conversion, trả về fallback an toàn hoặc re-raise `ConnectorError` / `ExternalServiceError`.
4. Với News entity extraction & budget: bảo đảm rate limit và budget tracking không bị bypass khi gặp lỗi; annotate rõ ràng lý do cho các khối best-effort NLP/regex extraction.
5. Với ChainLens: xử lý network / upstream synthesis failure với log chi tiết, fallback hoặc re-raise.

## Boundaries & Constraints

**Always:**
- Giữ nguyên contract và data types trả về của các connectors và tools.
- Với sync loops: lỗi trên 1 resource không được làm dừng toàn bộ sync process (best-effort item processing).
- Với token/auth errors (401/403 từ OAuth upstream): log warning để trigger re-auth.
- Chạy tests liên quan sau khi sửa.

**Never:**
- Không nuốt lỗi xác thực (OAuth token expired) mà không ghi log.
- Không thay đổi interface của ToolMetadataService hay KBSyncService.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Upstream OAuth token expired (401) | Connector sync | Ghi log token error, dừng sync connector đó | Đánh dấu connection status degraded |
| 1 document bị lỗi format | KB sync batch | Bỏ qua document lỗi, tiếp tục sync các document còn lại | Best-effort per-item, log error |
| Tool schema reflection fail | Tool metadata init | Bỏ qua tool lỗi, nạp các tool hợp lệ | Log warning, không crash boot |
| News NLP extraction fail | Parse article | Trả về entities rỗng hoặc partial | Best-effort NLP fallback |

</frozen-after-approval>

## Code Map

- `app/exceptions.py` — `ConnectorError`, `OAuthError`, `ExternalServiceError`.
- `app/services/composio/` (25 sites): `drive.py` (9), `gmail.py` (6), `base.py` (5), `calendar.py` (4), `email.py` (1).
- `app/services/news/` (22 sites): `entity_extractor.py` (13), `extract_budget.py` (8), `entities.py` (1).
- `app/services/chainlens/` (7 sites): `gap_fill.py` (3), `ingest.py` (2), `private_provider.py` (2).
- Connector `tool_metadata_service.py` (23 sites): `google_calendar` (5), `gmail` (5), `confluence` (4), `linear` (3), `notion` (3), `google_drive` (3).
- Connector `kb_sync_service.py` (11 sites): `google_calendar` (2), `confluence` (2), `linear` (2), `notion` (2), `gmail` (1), `google_drive` (1), `onedrive` (1), `dropbox` (1).
- `app/services/news/entities.py` (1 site).

## Tasks & Acceptance

**Execution:**
- [x] Connector `kb_sync_service.py` (11 sites across 8 files)
- [x] Connector `tool_metadata_service.py` (23 sites across 6 files)
- [x] `app/services/composio/` (25 sites across 5 files)
- [x] `app/services/news/` (22 sites across 3 files)
- [x] `app/services/chainlens/` (7 sites across 3 files)
- [x] `app/services/news/entities.py` (1 site)
- [x] Verify tests & ruff check

**Acceptance Criteria:**
- 100% các call-sites `except Exception` được narrow hoặc annotate rationale chuẩn.
- Các bài test unit và integration liên quan pass 100%.
- `ruff check` pass không có lỗi.
