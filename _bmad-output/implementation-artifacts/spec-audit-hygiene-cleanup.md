---
title: 'Audit hygiene cleanup — xóa dead files, root clutter, chốt ignore rules'
type: 'chore'
created: '2026-09-12'
status: 'done'
review_loop_iteration: 0
baseline_commit: '92028fe862072331da05ff9fd70afb97c90d7237'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Audit 2026-09-12 phát hiện repo còn dead files đã commit (`db.py.legacy` 7.041 dòng, 2 file `.bak`), 15 file rác ở root (screenshot debug, transcript, response dump), và `.tgrep/` index local chưa được ignore — gây nhiễu search, refactor và review.

**Approach:** Xóa các file đã verify 0 reference; move 1 doc playbook vào `docs/`; bổ sung `.gitignore` và ruff per-file-ignore cho `__main__` CLI demo hợp lệ. Không sửa logic runtime nào.

## Boundaries & Constraints

**Always:**
- Chỉ `git rm`/`git mv` file đã verify 0 reference (bằng chứng trong Code Map).
- `e2e-prompt-playbook-global-model.md` là doc thật — move vào `docs/`, KHÔNG xóa.
- Commit `AUDIT_TECHNICAL_DEBT_2026-09-12.md` cùng đợt (là record của cleanup này).

**Ask First:**
- Phát hiện bất kỳ reference nào tới file sắp xóa mà audit bỏ sót → HALT, liệt kê lại cho user.

**Never:**
- Không đụng các file Epic 31 đang uncommitted (`web_builder/*`, `sprint-status.yaml`, `docker-compose.yml`, `epic-31-context.md`, `spec-31-1-*`, `stories/31-1-*`).
- Không xóa untracked/ignored files (`dump.rdb`, `mcp-*.js`, `.local_object_store/` 7.2G — local dev data).
- Không sửa/xóa block `set_event_loop_policy(WindowsProactorEventLoopPolicy)` trong `tasks/process_meeting_minutes.py:24-30` và `tasks/celery_tasks/video_presentation_tasks.py:23-30` — đó là workaround Windows có chủ đích cho async subprocess trong Celery worker, đã gate bằng `sys.platform.startswith("win")` và log đúng.
- Không đổi `print()` trong `luma_connector.py` thành logger — chúng nằm trong `if __name__ == "__main__"` CLI demo, đúng convention; thay vào đó thêm per-file-ignore.

</frozen-after-approval>

## Code Map

- `nowing_backend/app/db.py.legacy` — 7.041 dòng, tên file không thể import (dấu `.` trong tên). Superseded bởi `app/db/` package + `app/models/` (commit `720fc952f`). `git grep db.py.legacy` → 0 refs ngoài chính nó.
- `nowing_backend/app/config/global_llm_config.yaml.bak`, `_bmad/config.toml.bak` — backup files, 0 refs.
- Root junk (0 refs đã verify): `chat-chainlens-cost-fixed.png`, `chat-issues-overlay.png`, `chat-real-response{,-55s}.png`, `chat-research-cost-fixed{,-75s,-105s}.png`, `chat-research-real-60s.png`, `chat-research-response{,-55s}.png`, `chat-response-{5s,20s}.png`, `saved-search-detail.png`, `new_chat_response.txt`, `session_acidic-stallion_transcript_clean.md`.
- `e2e-prompt-playbook-global-model.md` — prompt playbook doc, 0 refs → `docs/`.
- `.gitignore` — đã có `*.rdb`, `mcp-*.png`; cần thêm `.tgrep/` (trigram index local).
- `nowing_backend/pyproject.toml` — `[tool.ruff.lint.per-file-ignores]` ~dòng 217, đã có pattern ignore T201 cho testbench/`zero_publication.py`; thêm `app/connectors/luma_connector.py` (prints tại `__main__` block, dòng ~396-434).

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/db.py.legacy` — `git rm` — dead code 7K dòng, 0 refs
- [x] `nowing_backend/app/config/global_llm_config.yaml.bak` + `_bmad/config.toml.bak` — `git rm` — backup files không thuộc repo
- [x] 15 root files (Code Map) — `git rm` — debug artifacts, 0 refs
- [x] `e2e-prompt-playbook-global-model.md` — `git mv` vào `docs/` — giữ nội dung doc
- [x] `.gitignore` — thêm `.tgrep/` + `*.bak` — chặn index local & backup files bị commit nhầm
- [x] ~~`nowing_backend/pyproject.toml` — thêm T201 per-file-ignore~~ **đã revert trong review**: block `__main__` của `luma_connector.py` nằm trong `"""` comment string, không phải code thực thi — ruff không flag, không cần ignore
- [x] `AUDIT_TECHNICAL_DEBT_2026-09-12.md` — `git add` — record của cleanup

**Acceptance Criteria:**
- Given repo ở HEAD mới, when `git ls-files -- '*.legacy' '*.bak' '*.png' '*.txt' | grep -E '^[^/]+$'` chạy, then 0 kết quả ở root.
- Given `nowing_backend`, when `uv run python -c "from app.app import app"` chạy, then import thành công không lỗi.
- Given `docs/`, when kiểm tra, then `docs/e2e-prompt-playbook-global-model.md` tồn tại và bản root đã hết.

## Spec Change Log

## Verification

**Commands:**
- `cd nowing_backend && uv run python -c "from app.app import app; print('app import OK')"` — expected: `app import OK`
- `cd nowing_backend && uv run pytest tests/unit/db -q` — expected: pass (smoke cho `app.db` package sau khi xóa legacy)
- `git grep -l "db.py.legacy\|global_llm_config.yaml.bak\|config.toml.bak"` — expected: 0 kết quả
- `git ls-files -- '*.legacy' '*.bak' '*.png' '*.txt' | grep -cE '^[^/]+$'` — expected: 0
- `ls docs/e2e-prompt-playbook-global-model.md` — expected: tồn tại
- `cd nowing_backend && ruff check app/connectors/luma_connector.py` — expected: pass (prints trong comment string, không cần ignore)

**Manual checks:**
- `git status --short` sau commit: chỉ còn đúng các file Epic 31 uncommitted của user.

## Suggested Review Order

**Dead code & clutter removal** (tất cả đã verify 0 refs — xem commit `357f71c65`)

- Record kiến trúc cho toàn bộ cleanup — đọc trước để hiểu "vì sao xóa"
  [`AUDIT_TECHNICAL_DEBT_2026-09-12.md:92`](../../AUDIT_TECHNICAL_DEBT_2026-09-12.md#L92)

- `db.py.legacy` 7.041 dòng + 2 `.bak` + 15 root files — deletion-only, verify bằng `git show 357f71c65 --stat`
  [`spec-audit-hygiene-cleanup.md:36`](./spec-audit-hygiene-cleanup.md#L36)

**Tooling guards**

- `.tgrep/` + `*.bak` — chặn index local & backup files tái phạm
  [`.gitignore:68`](../../.gitignore#L68)

- Deferred items B/C được ghi sổ với `source_spec` trỏ về đây — audit trail cho phần việc chưa làm
  [`deferred-work.md`](./deferred-work.md)

**Docs**

- Playbook doc được giữ lại, chỉ move vị trí
  [`e2e-prompt-playbook-global-model.md`](../../docs/e2e-prompt-playbook-global-model.md)
