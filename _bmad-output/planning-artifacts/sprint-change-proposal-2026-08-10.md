# Sprint Change Proposal — Epic 18 còn mở (2026-08-10)

## 1. Tóm tắt vấn đề

Epic 18 "Vertical Client Platform (Public Agent-Chat)" hiện có 7/8 story DONE; story 18.8 **Rate Limiting + Tenant Isolation** vẫn `in-progress`. Sau khi audit code và so sánh với `sprint-status.yaml`, `epics.md`, `ARCHITECTURE-SPINE.md` và `epic-18-pat-scope-rls-threat-model.md`, còn các vấn đề sau:

- **Bảng `memories` đã có `client_id`/`agent_id` nhưng chưa có RLS policy** → vi phạm AD-31 tenant isolation hard key.
- **Rate limiting** cho public agent-chat chưa được tích hợp hoàn chỉnh (`app/rate_limiter.py` có hàm nhưng chưa mount vào route đầy đủ).
- **Tenant context middleware** chưa có; hiện tại context được set thủ công tại các call site.
- **Test matrix L1–L5** từ threat model chưa được viết.
- **`GET /threads/{thread_id}`** bị defer từ 18.1 review (low priority).
- **`app.internal_service` bypass** mới dùng cho startup sweep, cần harden để không phụ thuộc GUC backdoor.

## 2. Phân tích impact

### Epic impact
- **Epic 18** không thể đóng nếu 18.8 chưa xong.
- **AD-29, AD-31** bị vi phạm nếu `memories` không có RLS.
- Các story 18.6/18.7 (memory tagging, cost traceability) đã implement nhưng bảo mật tenant chưa kín.

### Story impact
- **18.8 AC-1 (rate limit)**: partial → cần hoàn thiện route dependency + metric.
- **18.8 AC-2 (RLS context)**: partial → cần middleware hoặc patch tất cả call site.
- **18.8 AC-3 (RLS policy)**: gap → cần migration `memories` RLS, đồng thời audit `Memory` call sites.

### Artifact conflicts
- `epics.md` Story 18.8 vẫn ghi AC đơn giản; cần cập nhật status khi xong.
- `sprint-status.yaml` ghi `18-8: in-progress`, cần chuyển `done` sau khi test pass.
- Story file `18-8-rate-limiting-tenant-isolation.md` task list chưa check, cần cập nhật.

### Technical impact
- DB migration mới cho `memories` RLS.
- Nhiều call site trong `app/services/memory/`, `app/agents/chat/...`, `app/routes/` cần `set_request_tenant_context`.
- Cần thêm các test integration L1, L2, L3, L5 theo threat model.

## 3. Phương án đề xuất

**Phương án: Direct Adjustment (bổ sung scope cho Story 18.8)**

Không rollback, không giảm scope MVP. Cố gắng đóng 18.8 bằng cách:
1. Thêm RLS cho `memories`.
2. Audit và patch tất cả `Memory` call sites với tenant GUC.
3. Hoàn thiện rate limiter trên public agent-chat routes.
4. (Optional) Thêm middleware để đồng bộ GUC thay vì set tay — tuy nhiên do thời gian, ưu tiên patch call site trước.
5. Viết test L1/L3 tối thiểu để verify RLS & pool safety.

**Phân loại scope:** **Moderate** — cần nhiều file/thay đổi, nhưng infrastructure đã có, không phải làm lại từ đầu.

## 4. Đề xuất thay đổi cụ thể

### 4.1. Thêm migration `memories` RLS

**File mới:** `nowing_backend/alembic/versions/XXX_add_memories_rls_policies.py`

```python
# Tương tự f7471a265bc5 nhưng thêm workspace + client composite,
# tương thích với token_usage và runs.
```

**Rationale:** Bảng `memories` có `workspace_id`, `client_id`; AD-31 yêu cầu hard isolation.

### 4.2. Patch `Memory` call sites

**Files cần audit:**
- `app/services/memory/search.py`
- `app/services/memory/run_extraction.py`
- `app/services/memory/extraction.py`
- `app/services/memory/revalidation.py`
- `app/agents/chat/multi_agent_chat/subagents/shared/run_reader.py`
- `app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py`
- `app/routes/memory_routes.py` / `new_chat_routes.py` / `agent_chat_routes.py`

**Rationale:** Sau khi `FORCE RLS`, mọi `SELECT/INSERT/UPDATE/DELETE` trên `memories` phải có GUC `app.workspace_id` và `app.current_client_id`.

### 4.3. Rate limiter integration

**Files:** `app/rate_limiter.py`, `app/routes/agent_chat_routes.py`

**Thay đổi:**
- Mount `@limiter.limit(...)` hoặc dependency trên `POST /agent-chat/threads` và `POST /.../messages`.
- Thêm config `AGENT_CHAT_RATE_LIMIT_RPM`, `AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM`.

### 4.4. Test coverage

**Files mới:**
- `tests/integration/rls/test_composite_client_rls.py` (L1 R1-R10)
- `tests/integration/pool/test_tenant_guc_reset.py` (L3 P1-P4)
- `tests/integration/api/test_agent_chat_pat_matrix.py` (L2 H1-H12)
- `tests/integration/agent/test_agent_chat_rate_audit.py` (L5 A1-A5)

## 5. Implementation handoff

- **Scope:** Moderate.
- **Người thực hiện:** Developer agent (kn-implement / bmad-quick-dev).
- **Deliverables:**
  - Migration `memories` RLS đã `alembic upgrade head`.
  - `Memory` call sites patched + ruff clean.
  - Rate limiter route integration.
  - L1 + L3 tests pass (L2/L5 nếu còn thời gian).
  - `sprint-status.yaml` cập nhật `18-8: done`.
  - Story file `18-8-rate-limiting-tenant-isolation.md` cập nhật status + file list.

## 6. Checklist (từ `checklist.md`)

| Section | Item | Status |
|---------|------|--------|
| 1.1 | Trigger story: 18.8 | [x] Done |
| 1.2 | Core problem: security gap (memories RLS) + incomplete 18.8 | [x] Done |
| 1.3 | Evidence: `memories` migration 10127c164b44 has no RLS; `sprint-status.yaml` 18-8 in-progress | [x] Done |
| 2.1 | Epic 18 cannot close until 18.8 done | [x] Done |
| 2.2 | Modify 18.8 scope to include memories RLS | [x] Done |
| 2.3 | Dependencies: 18.6/18.7 already done; 18.8 blocks close | [x] Done |
| 2.4 | No epic obsolete; no new epic needed | [x] Done |
| 2.5 | Priority: keep 18.8 P1, finish before pilot | [x] Done |
| 3.1 | PRD MVP: no conflict, AD-31 already requires RLS | [x] Done |
| 3.2 | Architecture: AD-29/AD-31 already accepted | [x] Done |
| 3.3 | UX: no impact | [N/A] |
| 3.4 | Tests: need L1-L5 | [x] Done |
| 4.1 | Direct Adjustment: viable, effort medium | [x] Viable |
| 4.2 | Rollback: not viable (already invested) | [ ] Not viable |
| 4.3 | MVP review: not needed | [N/A] |
| 4.4 | Selected: Direct Adjustment | [x] Done |
| 5.1–5.5 | Proposal components | [x] Done |
| 6.1 | Comprehensive | [x] Done |

---

*Generated by bmad-correct-course workflow — 2026-08-10.*
