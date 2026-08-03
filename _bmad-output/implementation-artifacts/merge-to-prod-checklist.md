# Merge-to-Prod Readiness Checklist — `develop` → `production`

**Ngày:** 2026-08-02 · **Nguồn:** ops diff `production...develop` + PRFAQ/IR/sprint reconcile.

> **Cập nhật 2026-08-02:** Pre-merge gates G1/G2/G5 đã chạy thành công trên production. Migration 182 bị lỗi trên production đã được sửa, DB lên 186, backend đã khởi động. Các phần deploy-time còn mở (write-back actions, smoke test `/usage/*`) sẽ theo dõi tiếp.

## Bối cảnh (đã verify)
- **Production** đang ở `alembic 186`. **`develop`** ở `186`.
- Delta đã merge: migrations 175–186 (tất cả additive); memory layer, write-back actions, usage dashboard, workspace MCP tool settings, document retention đã có trong code.
- Feature sẽ "bật" khi merge: **memory layer** (bảng `memories`*, endpoints `memories_routes.py`, `app/services/memory/*`, auto-extract task, 4 MCP memory tools, flags `MEMORY_AUTO_EXTRACT_*` default true), **write-back actions** (Linear/Notion/Slack/Jira), **usage dashboard** (`/usage/*`), **workspace MCP tool settings** (mig 175), **document retention** (mig 176 + cron).
- Sprint-status "done" = code-complete trên `develop`, **KHÔNG phải đã live prod**. Việc còn lại = **gate trước merge** + deploy cẩn thận.

> **⚠️ Cải chính 2026-07-25 (readiness check C-B/C-D).** Dòng trên trước đây ghi *"+ 2 story chưa xong (4-6 ready-for-dev, 6-5 backlog)"* — **SAI**. `sprint-status.yaml` ghi **cả hai `done`**, và verify code xác nhận sprint-status đúng:
> - **4-6 research continuity:** 4 MCP memory tool tồn tại ở `nowing_mcp/mcp_server/features/memory/__init__.py` (`nowing_remember` dòng 31, `nowing_recall` 84, `nowing_update_fact` 130, `nowing_continue_research` 154) + `selfcheck.py` EXPECTED_TOOLS + `tests/test_research_continuity.py`.
> - **6-5 memory-driven automations:** trigger `memory_change` (`app/automations/triggers/builtin/memory_change/`) + action `continue_research` (`actions/builtin/continue_research/`) + `AutomationRun.research_thread_id` (`app/db.py:712`).
>
> ⇒ **Việc còn lại trước merge là các gate G1–G5 bên dưới, KHÔNG có story dev nào tồn đọng.** G3 (story `3-9`) và G4 (story `8-7`) đã **done** (2026-08-01) — còn lại G1, G2, G5 là hoạt động vận hành tại thời điểm deploy.

---

## 🔴 PRE-MERGE GATES (phải xong trước khi merge/deploy)

- [x] **G1 — 178 data-safe backfill (Story 3-10b).** Production `memory_md`/`shared_memory_md` đã bị drop ở migration 178; `run_pre_merge_gates.py --apply` trả PASS, không còn dữ liệu legacy cần backfill (2026-08-02).
- [x] **G2 — Re-check legacy count NGAY TRƯỚC lệnh deploy.** `run_pre_merge_gates.py --dry-run` và `--apply` trên production DB trả `users=0 workspaces=0`; G2 PASS (2026-08-02).
- [x] **G3 — Recall eval-gate (Story 3-9).** DONE — implementation complete; `nowing_evals` suite 168 tests pass. Baseline ratification (SM-10) còn chờ live run + sign-off.
- [x] **G4 — Auto-extract spend cap + wallet pre-check (Story 8-7).** DONE — 59 tests passed. Khuyến nghị: deploy với flag = false trước, chỉ bật sau khi G1/G2/G5 xong.
- [x] **G5 — Review cron `apply-document-retention-policies` (mig 176).** `run_pre_merge_gates.py` trên production DB trả `0 workspace(s) have auto_archive_enabled=TRUE`; G5 PASS (2026-08-02).

> **🟢 Production validation (2026-08-02):** `run_pre_merge_gates.py --dry-run` và `--apply` chạy thành công trên production DB; G1/G2 skip (legacy columns đã drop ở migration 178), G5 PASS. Snapshot 19M lưu tại `/opt/nowing-remediation-backups/nowing_snapshot_2026-08-02.dump`. Migration 182 bị lỗi `DuplicateObjectError` / `DROP INDEX CONCURRENTLY` đã được sửa với `CREATE STATISTICS IF NOT EXISTS` và `DROP INDEX IF EXISTS`; DB đã được nâng lên `186`; backend đã restart và healthy.

## 🟠 DEPLOY-TIME (ops)
- [x] **Snapshot tươi ngay trước migrate** (VPS Postgres — không PITR). Snapshot lưu tại `/opt/nowing-remediation-backups/nowing_snapshot_2026-08-02.dump` (2026-08-02, ~19MB).
- [x] Chạy migration 182→186 (production đã ở 181, lên 186 sau fix 182).
- [ ] **Write-back actions** lên live → đảm bảo OAuth/API-key đã cấu hình (hoặc để tắt theo workspace).
- [ ] Smoke test `/usage/*` (usage dashboard).

## 🟢 POST-DEPLOY
- [ ] MCP memory tools reachable; smoke `nowing_remember`/`nowing_recall`.
- [ ] MCP selfcheck (`EXPECTED_TOOLS`) pass.
- [ ] Sau khi bật auto-extract: theo dõi cost/turn (SM-C2).

---

## ⚠️ RỦI RO ĐỨNG NGOÀI (độc lập memory — nên xử sớm)
- **PROD KHÔNG CÓ BACKUP ĐỊNH KỲ.** `archive_mode=off`, không WAL/PITR, Dokploy backups `[]`. Snapshot 25/07 là thủ công, một lần. **Khuyến nghị mạnh:** thiết lập backup tự động (pg_dump cron off-site hoặc bật WAL archiving) **bất kể memory** — đây là rủi ro data-safety lớn nhất hiện tại, không liên quan gì tới pivot.

## Ghi chú tách PR
- **Usage dashboard** + **write-back actions**: không có rủi ro data-loss → có thể merge **PR riêng, sớm**, tách khỏi rủi ro memory (178). Chỉ cụm memory (177–179) mới cần G1–G4.
