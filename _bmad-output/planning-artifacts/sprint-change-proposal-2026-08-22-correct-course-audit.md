# Sprint Change Proposal — Correct-Course Audit 2026-08-22

**Workflow:** `bmad-correct-course` (batch mode)  
**Project:** Nowing  
**Date:** 2026-08-22  
**Author:** Agent + MCP code intelligence (vibervn-context-engine, serena, code-review-graph discovery)  
**Status:** ✅ **ADOPTED (PO Luisphan, 2026-08-22)** — implementation in progress.

**Artifacts bị ảnh hưởng:**
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `nowing_backend/app/db.py`, `nowing_backend/app/canonical/`, `nowing_backend/app/routes/canonical_entities_routes.py`

---

## 1. Issue Summary

Sau hai SCP `bmad-correct-course` trước (2026-07-22 và 2026-07-25), phần lớn docs-vs-code drift đã được sửa. Audit lần này dùng MCP code intelligence để đối chiếu lại toàn bộ PRD, epics, architecture-spine và sprint-status với code thực tế. Phát hiện **5 nhóm drift** còn sót, chủ yếu là "code đã chạy, docs chưa xác nhận done" hoặc "code dead cần dọn".

### 1.1 Bằng chứng đã thu (verifiable)

| # | Drift | Docs claim | Code reality | Severity |
|---|---|---|---|---|
| D1 | **Document retention / auto-archive** | PRD §OQ-3 ghi `[PARTIAL]` — schema có, enforcement job + UI chưa đầy đủ. | Migration 176, `Workspace.document_retention_days` / `auto_archive_enabled`, `Document.archived_at`, `app/tasks/celery_tasks/document_retention_task.py`, `nowing_web/components/settings/data-retention-manager.tsx`, `tests/unit/tasks/test_document_retention_task.py` đều đã có. | Low |
| D2 | **Assumption direct write-back** | PRD §9 assumption: *"Agent có thể thực hiện write-back bằng cách gọi Notion/Linear/Slack/Jira tools trong `agent_task`, nên direct write-back action không cần thiết cho MVP."* | `app/automations/actions/builtin/__init__.py` đăng ký 5 action type riêng: `write_back_jira`, `write_back_linear`, `write_back_notion`, `write_back_slack`, `write_back_telegram`. FR-18 / OQ-5 đã `[DONE/RESOLVED]`. | Low |
| D3 | **Epic 13 canonical entity dead code** | Epic 13 dropped từ SCP 2026-08-08; `deferred-work.md` ghi "schedule cleanup" nhưng chưa có story. | `CanonicalEntity` vẫn tồn tại trong `app/db.py:4336`, `app/canonical/services/`, `app/routes/canonical_entities_routes.py`, tests `tests/integration/canonical/`, migration `add_canonical_entities`. Code này không còn phục vụ FR nào trong PRD. | High |
| D4 | **Tech-debt tracker td-1..td-7** | Ghi `backlog` trong `sprint-status.yaml`. | Một số item có thể đã gián tiếp fix qua stories gần đây (ví dụ td-3 storage reconcile qua 8-12, td-5 title_gen qua chat 4.8 series), cần re-verify trước khi để backlog mãi. | Medium |
| D5 | **Multi-surface clients integration readiness** | PRD §1.1 / §4.7 mention Electron, Plasmo, Obsidian plugin. | Các project tồn tại (`nowing_desktop/`, `nowing_browser_extension/`, `nowing_obsidian/`) với implementation, nhưng chưa rõ integration test / release pipeline / self-host onboarding. | Medium |

### 1.2 Drift đã được sửa từ SCP trước (không cần hành động thêm)

- ✅ RBAC Admin role removed — PRD đã ghi `[REMOVED]`.
- ✅ AI File Sorting removed — PRD đã ghi `[REMOVED]`.
- ✅ Per-workspace MCP tool toggle — PRD OQ-4 `[RESOLVED]`, code `WorkspaceMcpToolSetting` + `mcp_server/server.py` filter.
- ✅ Usage/credit dashboard — PRD NFR-7 `[DONE]`, code `usage_routes.py` + `UsageService` + `nowing_web/app/dashboard/[workspace_id]/usage/page.tsx`.
- ✅ Direct write-back actions — PRD FR-18 `[DONE]`, OQ-5 `[RESOLVED]`.
- ✅ Citation full-editor highlight — PRD §1439 `[DONE]`, code `editorPanelAtom` + `chunkId`.
- ✅ ChainLens cost metering & degradation — PRD FR-37/FR-38/NFR-9 `[DONE]`, code parse `costDollars`, fallback `CHAINLENS_QUERY_MICROS_PER_CALL`, `engine_unavailable` degradation.
- ✅ Memory provenance — `Memory.source_run_id` (UUID), `source_capability`, `source_input` đã có; schema mismatch `source_id` Integer vs `Run.id` UUID đã được giải quyết bằng `source_run_id`.

---

## 2. Epic Impact Assessment

| Check | Kết luận |
|---|---|
| **2.1** Epic hiện tại còn hoàn thành được? | **Có.** Không epic nào bị phá vỡ. D1–D2 là docs-stale; D3 là dead-code cleanup; D4/D5 là backlog/tracking. |
| **2.2** Thay đổi cấp epic | **Không thêm epic mới.** D3 có thể thành story trong tech-debt epic hiện tại. |
| **2.3** Epic tương lai bị ảnh hưởng | **Epic 3 (Knowledge Base)**: D1 nên xác nhận E3.7 `[DONE]` cho document retention; memory retention vẫn `[PARTIAL]` dưới OQ-3/FR-97. **Tech-debt epic**: D3/D4 cần cập nhật. |
| **2.4** Epic nào vô hiệu / cần mới? | Không. Epic 13 đã vô hiệu; cần **cleanup story** thay vì epic mới. |
| **2.5** Đổi thứ tự ưu tiên? | **Không đổi.** D3 (Epic 13 cleanup) nên chạy trước GA cloud để tránh data-migration pain — đã ghi trong `deferred-work.md` 2026-08-08. D4 nên re-verify trong 1 sprint. D5 theo dõi theo Epic 7. |

---

## 3. Artifact Conflict & Impact Analysis

### 3.1 PRD (`prd-Nowing-2026-07-22/prd.md`)

| # | Section | Thay đổi | Lý do |
|---|---|---|---|
| **P1** | §OQ-3 | Tách rõ **document retention** (`[DONE]`) vs **memory / scrape-data retention** (`[GAP]` → FR-97). Hiện tại gộp chung khiến độc giả tưởng document retention chưa xong. | Code document retention đã full-stack. Memory retention vẫn là vấn đề pháp lý (ToS/PII) cần FR-97. |
| **P2** | §9 Assumptions | Sửa hoặc xóa assumption: *"direct write-back action không cần thiết"* → `[CORRECTED 2026-08-22]` thành *"FR-18 đã implement direct write-back action type riêng; `agent_task` vẫn là lối tắt nhưng không phải primary path."* | Code và FR-18 đã done; assumption cũ gây hiểu nhầm. |

### 3.2 Epics (`epics.md`)

| # | Section | Thay đổi |
|---|---|---|
| **E1** | E3.7 coverage map | Cập nhật note: `E3.7 [DONE for document retention; PARTIAL for memory retention]` thay vì `[PARTIAL]` mơ hồ. |
| **E2** | Epic 13 / canonical index | Xác nhận Epic 13 dropped; thêm pointer đến cleanup story `td-8` hoặc `13-cleanup`. |

### 3.3 Architecture / Code

| # | File / Component | Thay đổi |
|---|---|---|
| **C1** | `nowing_backend/app/db.py` `CanonicalEntity` | Đánh dấu deprecated comment; lên lịch xóa sau khi `NowingIngestService` + `chainlens-research POST /v1/ingest/scraper` stable. |
| **C2** | `nowing_backend/app/canonical/`, `app/routes/canonical_entities_routes.py` | Thêm runtime warning khi import/call; chuẩn bị removal story. |
| **C3** | `sprint-status.yaml` tech-debt | Thêm `td-8` "Epic 13 canonical entity cleanup" P2; cập nhật status `td-1..td-7` sau re-verify. |

---

## 4. Recommended Approach

**Lựa chọn:** **Direct Adjustment** (không rollback, không replan).

**Lý do:**
- D1/D2 chỉ là docs-stale; code đã đúng.
- D3 là dead-code cleanup; có thể thực hiện từ từ với deprecation warnings trước khi drop tables.
- D4/D5 là tracking; không ảnh hưởng delivery path.

**Rủi ro:** Low–Medium. Rủi ro cao nhất là **D3** nếu xóa canonical entities quá sớm mà vẫn còn test/edge case phụ thuộc. Giải pháp: deprecation 1 sprint, sau đó drop.

**Timeline:** 1–2 ngày cho docs-update; 1 sprint cho Epic 13 cleanup; 1 ngày cho tech-debt re-verify.

---

## 5. Detailed Change Proposals

### 5.1 PRD updates

#### P1 — OQ-3 Document retention clarification

```
Section: §OQ-3 Retention, right-to-delete & phơi nhiễm pháp lý

OLD:
  Document retention schema đã có ... enforcement job + UI chưa xác nhận đầy đủ.
  Gap: [GAP] OQ-3 — Chưa có retention/right-to-delete cho memories; ... (Doc retention [PARTIAL])

NEW:
  ✅ Document retention (workspace-level `document_retention_days`, `auto_archive_enabled`,
     `Document.archived_at`, Celery enforcement job, UI `data-retention-manager`) → [DONE].
  🟠 Memory + scraped-data retention / right-to-delete / self-host vs cloud split → [GAP]
     (ToS/PII, PRFAQ RS-11, FR-97). Khác với document retention.
```

#### P2 — Assumption index direct write-back

```
Section: §9 Assumptions Index

OLD:
  [ASSUMPTION] Agent có thể thực hiện write-back ... direct write-back action không cần thiết.

NEW:
  [CORRECTED 2026-08-22] Direct write-back action type riêng (FR-18, OQ-5) đã implement
  trong `app/automations/actions/builtin/` (notion/slack/linear/jira/telegram). `agent_task`
  vẫn là một lối tắt nhưng không phải primary path.
```

### 5.2 Epics updates

#### E1 — E3.7 status note

```
OLD: OQ-3/AR-4 → E3.7 [PARTIAL]
NEW: OQ-3/AR-4 → E3.7 [DONE for document retention; PARTIAL for memory/scraped-data retention]
```

#### E2 — Epic 13 cleanup pointer

```
ADD to Epic 3/AR-4 or Tech-debt section:
  Epic 13 (canonical_entities / multi-domain local index) [DROPPED 2026-08-08].
  Dead-code cleanup tracked as td-8 in sprint-status.yaml.
```

### 5.3 Sprint-status updates

```
# Tech-debt section

ADD:
  td-8: backlog  # Epic 13 canonical entity cleanup — deprecated tables/code/tests
                  # P2; run after chainlens-research ingest stable
```

```
# Re-verify td-1..td-7 status after recent stories:
# - td-3 (storage reconcile) — check if 8-12 workspace limits resolved it.
# - td-5 (title_gen timeout) — check if 4.8 series / title_gen refactor resolved it.
# - td-1, td-2, td-4, td-6, td-7 — keep backlog if still valid.
```

### 5.4 Code changes (D3)

- Thêm `warnings.warn("CanonicalEntity is deprecated; use chainlens-research POST /v1/ingest/scraper", DeprecationWarning, stacklevel=2)` trong `app/canonical/__init__.py` hoặc `canonical_entities_routes.py`.
- Không xóa migration/table vội — chỉ khi `td-8` được approve và run.

---

## 6. Implementation Handoff

| Scope | Phân loại | Người nhận | Nhiệm vụ |
|---|---|---|---|
| Docs update (P1, P2, E1, E2) | Minor | Developer agent | Edit PRD/epics; 1 MR. |
| Tech-debt re-verify (td-1..td-7) | Minor | Developer agent | Chạy grep/MCP + tests, cập nhật `sprint-status.yaml`. |
| Epic 13 cleanup (td-8) | Moderate | PO + Developer | PO approve scope; Developer implement deprecation, sau đó removal. |
| Multi-surface client integration (D5) | Moderate | PO + Developer | PO decide GA vs deferred; Developer kiểm tra CI/release. |

**Success criteria:**
- PRD/epics phản ánh đúng trạng thái document retention và direct write-back.
- `sprint-status.yaml` có `td-8` và status tech-debt chính xác.
- `CanonicalEntity` có deprecation warning, không còn dead code gọi mới.
- README/docs drift check vẫn PASS.

---

## 7. Implementation Log

- ✅ Approved by PO Luisphan 2026-08-22.
- ✅ PRD §OQ-3 updated: document retention `[DONE]`; memory/scraped-data retention `[GAP]`.
- ✅ PRD §9 Assumptions: direct write-back assumption corrected.
- ✅ `epics.md` AR-4 updated; AR-16 added for Epic 13 cleanup.
- ✅ `sprint-status.yaml` updated: `td-8` added; `td-1..td-7` re-verified and remain backlog.
- ✅ `deferred-work.md` Epic 13 tech-debt updated with `td-8` + deprecation warning status.
- ✅ Epic 13 deprecation pass completed:
  - `nowing_backend/app/canonical/__init__.py` docstring notes package deprecation.
  - `app/canonical/services/canonical_persist_service.py` warnings in `create_persist_outbox`, `upsert_canonical_entity`, `revert_canonical_entity`, `resolve_canonical_conflict`.
  - `app/canonical/services/unified_search_service.py` warning in `__init__`.
  - `app/routes/canonical_entities_routes.py` warnings in all 8 public route handlers.
  - `pyproject.toml` filterwarnings for canonical deprecation noise.
  - `ruff check` PASS.
  - `uv run pytest tests/unit/canonical -m unit -q` 69 passed.
  - `uv run pytest tests/integration/canonical -m integration -q` 42 passed.
- ✅ `scripts/check-docs-drift.py` still PASS.

## 8. Next Step

Remaining cleanup work is tracked as `td-8` and should be picked up by Developer agent:
1. Identify all live call paths touching Epic 13 tables (`canonical_entities`, merge history).
2. Add deprecation warnings to `app/canonical/services/`, `app/routes/canonical_entities_routes.py`, and any MCP tools.
3. Remove unused REST/MCP endpoints and UI routes after deprecation period.
4. Schedule migration to drop tables/columns.
