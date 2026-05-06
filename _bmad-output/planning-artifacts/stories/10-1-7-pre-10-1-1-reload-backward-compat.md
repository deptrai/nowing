# Story 10.1.7 — Pre-10.1.1 Message Reload Backward-Compatibility

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10.1.1 (Smart Money Integration)
**Status:** dismissed
**Created:** 2026-05-06
**Closed:** 2026-05-06

## ❌ Dismissed — No Legacy Data Exists

**Decision (2026-05-06):** SQL audit confirms `new_chat_messages` table has **no `metadata` column** in schema — only `content: jsonb`. Pre-10.1.1 implementation never persisted `smart_money_flow` to DB at all (React-side state only, lost on reload pre-10.1.1).

```sql
SELECT column_name FROM information_schema.columns WHERE table_name = 'new_chat_messages';
-- Returns: content (jsonb). NO metadata column exists.
```

→ **Zero legacy rows** to migrate. The hypothetical "pre-10.1.1 reload regression" scenario assumed there was persisted metadata to lose; reality is metadata was always React-only until story 10-1-1 introduced the `data-smart-money-flow` content part.

Story closed without implementation. Backward-compat is automatic since legacy reload path produced no Sankey anyway.
**Why:** Story 10.1.1 introduced `data-smart-money-flow` content part để persist Sankey data vào DB. Messages persisted **trước khi 10.1.1 ship** không có content part này → reload trang thread cũ làm Sankey biến mất. Cần migration path cho legacy data.

---

## Problem Statement

**Story 10.1.1 ship date:** 2026-05-04 (per sprint-status).
**Story 10.1.1 mechanism:** SSE event `data-smart-money-flow` → push vào `contentPartsState` → `buildContentForPersistence` lưu vào DB content column.

**Pre-10.1.1 messages:**
- Có thể đã được persist với `metadata.custom.smart_money_flow` trong some legacy path
- Hoặc không persist ở tất cả — Sankey chỉ tồn tại trong React state, mất khi reload
- DB content column không có `data-smart-money-flow` part

**Hiện trạng `convertToThreadMessage`** ([message-utils.ts](nowing_web/lib/chat/message-utils.ts)):
```typescript
// Build metadata ONLY from extracted content parts
const metadata = msg.author_id || citationMap || agentResults || smartMoneyFlow
    ? { custom: {...} }
    : undefined;
```

→ Nếu DB row có pre-existing `metadata.custom.smart_money_flow` (từ legacy code), code mới **discard** field đó vì rebuild metadata from scratch.

**User impact:**
- User reload thread đã chat smart money trước 10.1.1 → Sankey biến mất, chỉ còn text
- Confusion: "lúc nãy có chart, giờ mất rồi?"

---

## Acceptance Criteria

**AC1 — Backward-compat read:**
GIVEN DB row có `metadata.custom.smart_money_flow` field nhưng không có `data-smart-money-flow` content part
WHEN `convertToThreadMessage(msg)` được gọi
THEN final metadata vẫn chứa `metadata.custom.smart_money_flow` từ DB
AND Sankey/empty-state vẫn render

**AC2 — Forward-compat ưu tiên:**
GIVEN DB row có CẢ pre-existing `metadata.custom.smart_money_flow` AND `data-smart-money-flow` content part
THEN content part wins (forward-compat) — reflect latest schema
AND log debug warning để track legacy rows

**AC3 — One-shot DB migration script (optional):**
GIVEN scope time-bounded (e.g. 30 ngày sau ship 10.1.1)
THEN có thể chạy script `scripts/migrate_smart_money_metadata_to_content_part.py`:
1. Scan messages có `metadata.custom.smart_money_flow` nhưng không có `data-smart-money-flow` content part
2. Insert content part `{type: "data-smart-money-flow", data: <metadata>}` vào content column
3. Optionally clear `metadata.custom.smart_money_flow` (để source-of-truth duy nhất là content part)

**AC4 — Migration is idempotent:**
- Script có thể chạy nhiều lần safely
- Kiểm tra existing content part trước khi insert
- Dry-run mode (`--dry-run`) print summary mà không write

**AC5 — Migration script chạy với pagination:**
- Process 1000 messages per batch
- Print progress: `Processed 5000/12345 messages, 234 migrated, 0 errors`
- Resume from last checkpoint nếu fail

**AC6 — Test coverage:**
- `test_convertToThreadMessage_with_legacy_metadata`: DB row có `metadata.custom.smart_money_flow`, no content part → final metadata still has field
- `test_convertToThreadMessage_with_both_sources`: DB row có cả legacy metadata AND content part → content part wins
- `test_migration_script_dry_run`: dry-run identifies candidates without writes
- `test_migration_script_idempotent`: run twice → second run no-op

---

## Files to Modify / Create

| File | Action | Notes |
|---|---|---|
| `nowing_web/lib/chat/message-utils.ts` | UPDATE | Read pre-existing `msg.metadata?.custom?.smart_money_flow` as fallback when content part missing |
| `nowing_web/lib/chat/message-utils.test.ts` | CREATE/UPDATE | Add 2 backward-compat test cases |
| `nowing_backend/scripts/migrate_smart_money_metadata_to_content_part.py` | CREATE | One-shot migration script |
| `nowing_backend/tests/scripts/test_smart_money_migration.py` | CREATE | Migration script tests (dry-run + idempotency) |
| `_bmad-output/implementation-artifacts/runbooks/smart-money-migration.md` | CREATE | Runbook for ops to run migration |

---

## Tasks/Subtasks

- [ ] Update `convertToThreadMessage` to read legacy metadata as fallback
- [ ] Add 2 unit tests for backward-compat read
- [ ] Investigate DB: count messages có `metadata.custom.smart_money_flow` nhưng không có content part
  - Query: `SELECT COUNT(*) FROM messages WHERE metadata->'custom' ? 'smart_money_flow' AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(content) WHERE jsonb_typeof(value) = 'object' AND value->>'type' = 'data-smart-money-flow')`
- [ ] Decide: migrate hay không? Nếu < 100 affected messages, có thể skip migration script (FE backward-compat đủ)
- [ ] Implement migration script (nếu cần)
- [ ] Migration tests
- [ ] Runbook
- [ ] Coordinate ops to run migration trong off-peak window

---

## Risks

| Risk | Mitigation |
|---|---|
| Legacy `metadata.custom.smart_money_flow` shape khác content part shape | Validate shape trước khi adopt; log warning on mismatch |
| Migration writes corrupt content (script bug) | Dry-run mandatory + backup table dump before run |
| FE backward-compat fork code path → maintenance burden | Migration script eliminates legacy path → schedule cleanup story to remove fork after migration |
| Customer queries thread cũ trong middle of migration → temporary inconsistency | Migration runs in single transaction per batch; migrate during low-traffic window |

---

## Test Plan

```typescript
// message-utils.test.ts
describe('convertToThreadMessage backward-compat', () => {
  it('preserves legacy smart_money_flow from metadata when no content part', () => {
    const msg = {
      id: 1,
      role: 'assistant',
      content: 'text only',  // no content array, no content part
      metadata: { custom: { smart_money_flow: { nodes: [...], links: [...] } } },
      author_id: null,
    };
    const result = convertToThreadMessage(msg);
    expect(result.metadata?.custom?.smart_money_flow).toBeDefined();
  });

  it('forward-compat content part wins over legacy metadata', () => {
    const msg = {
      content: [{type: 'data-smart-money-flow', data: {nodes: ['new'], ...}}],
      metadata: { custom: { smart_money_flow: { nodes: ['old'], ... } } },
    };
    const result = convertToThreadMessage(msg);
    expect(result.metadata.custom.smart_money_flow.nodes).toEqual(['new']);
  });
});
```

```python
# test_smart_money_migration.py
def test_migration_dry_run_identifies_candidates():
    # Setup: insert 5 legacy messages
    # Run: script in --dry-run mode
    # Assert: stdout shows "5 candidates", DB unchanged

def test_migration_idempotent():
    # Run migration twice
    # Assert: second run reports "0 migrated, 5 skipped (already migrated)"
```

---

## Decision Point

Trước khi implement, cần khảo sát: **bao nhiêu messages thực sự bị affected?**

```sql
SELECT
    COUNT(*) AS legacy_count,
    MIN(created_at) AS oldest,
    MAX(created_at) AS newest
FROM messages
WHERE metadata->'custom' ? 'smart_money_flow'
  AND NOT EXISTS (
    SELECT 1
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(content) = 'array' THEN content ELSE '[]'::jsonb END
    )
    WHERE value->>'type' = 'data-smart-money-flow'
  );
```

Nếu `legacy_count < 100`: chỉ ship FE backward-compat (no migration script needed).
Nếu `legacy_count >= 100`: ship cả 2.
Nếu `legacy_count == 0`: dismiss this story entirely (no legacy data to migrate).
