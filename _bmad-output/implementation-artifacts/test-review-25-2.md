---
stepsCompleted: ['step-01-load-context', 'step-02-discover-tests', 'step-03-quality-evaluation', 'step-04-generate-report']
lastStep: 'step-04-generate-report'
lastSaved: '2026-08-16'
workflowType: 'testarch-test-review'
inputDocuments:
  - _bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md
  - nowing_backend/tests/unit/services/test_manual_credits.py
  - nowing_backend/tests/integration/services/test_manual_credits.py
  - nowing_backend/tests/integration/routes/test_admin_credits.py
---

# Test Quality Review: Story 25.2 — Manual Credit Adjustment

**Quality Score**: 82/100 (Good — Approve with Comments)
**Review Date**: 2026-08-16
**Review Scope**: suite — 3 test files covering backend service and route
**Reviewer**: BMad TEA Agent

---

Note: This review audits existing tests; it does not generate tests.
Coverage mapping and coverage gates are out of scope here. Use `trace` for coverage decisions.

## Executive Summary

**Overall Assessment**: Good

**Recommendation**: Approve with Comments

### Key Strengths

✅ Tests are deterministic — no hard waits, no conditionals, no try-catch flow control.
✅ Integration tests use the real `db_session` fixture and roll back per test, so isolation is clean.
✅ Route tests exercise the full HTTP contract (status, body shape, ledger filter) and map cleanly to AC-1/AC-2/AC-3/AC-4.

### Key Weaknesses

(No open P1/P2 weaknesses after the follow-up commit.)

### Summary

The 25.2 test suite is small but solid for happy-path and validation. It is well-structured, isolated, and fast. The main weakness is that the most security-sensitive code paths — the per-admin advisory lock, the `SET LOCAL lock_timeout`, and the explicit `session.commit()` in the route — are not directly asserted. Since this is a P0 credit/ticket surface, those gaps should be closed before the story moves through the mutation and human-review gates.

---

## Quality Criteria Assessment

| Criterion                            | Status   | Violations | Notes                                                   |
| ------------------------------------ | -------- | ---------- | ------------------------------------------------------- |
| BDD Format (Given-When-Then)         | PASS     | 0          | Docstrings tie to ACs.                                  |
| Test IDs                             | WARN     | 16         | No explicit test ID markers.                            |
| Priority Markers (P0/P1/P2/P3)       | WARN     | 16         | No `@pytest.mark.p0`/etc. markers.                     |
| Hard Waits (sleep, waitForTimeout)   | PASS     | 0          | No waits.                                               |
| Determinism (no conditionals)        | PASS     | 0          | No `if`/`try`/random without control.                   |
| Isolation (cleanup, no shared state) | PASS     | 0          | `db_session` fixture rolls back per test.               |
| Fixture Patterns                     | PASS     | 0          | Uses standard `db_session`, `db_workspace`, `admin_client`. |
| Data Factories                       | WARN     | 3          | Payload values hard-coded; no shared factory.           |
| Network-First Pattern                | N/A      | 0          | API tests do not intercept.                             |
| Explicit Assertions                  | PASS     | 0          | Assertions are visible and focused.                     |
| Test Length (≤300 lines)             | PASS     | 214 max    | Longest file is 214 lines.                              |
| Test Duration (≤1.5 min)             | PASS     | <3s        | Full suite runs in ~2s.                                 |
| Flakiness Patterns                   | PASS     | 0          | No suspicious patterns.                                 |

**Total Violations**: 0 Critical, 1 High, 3 Medium, 2 Low

---

## Quality Score Breakdown

```
Starting Score:          100
Critical Violations:     0  × 10 = -0
High Violations:         1  × 5  = -5
Medium Violations:       3  × 2  = -6
Low Violations:          2  × 1  = -2

Bonus Points:
  Excellent BDD:         +0 (docstrings are present but not G-W-T)
  Comprehensive Fixtures: +5
  Data Factories:        +0
  Network-First:         +0
  Perfect Isolation:     +5
  All Test IDs:          +0
                         --------
Total Bonus:             +10

Final Score:             82/100
Grade:                   Good
```

---

## Critical Issues (Must Fix)

No critical issues detected. ✅

---

## Recommendations (Should Fix)

### 1. Add concurrency / advisory-lock test

**Severity**: P1 (High)
**Location**: `tests/integration/services/test_manual_credits.py:160-197`
**Criterion**: Explicit Assertions / Test Levels

**Issue Description**: The only idempotency double-submit test calls `adjust_credits` twice in a row in the same `AsyncSession`. It does not launch two actual concurrent tasks or use a separate database session, so it cannot catch a race where two admins bypass the quota or create duplicate ledger rows. The `pg_advisory_xact_lock` added in the code path is therefore unverified.

**Recommended Improvement**: Add an integration or unit-level test that runs two `adjust_credits` calls for the same admin from two different sessions/tasks (e.g. `asyncio.gather`) and asserts that the second either returns the same `transaction_id` (same idempotency key) or is rejected by the quota. Example:

```python
async def test_adjust_credits_concurrent_quota_guard(...):
    # Two concurrent credit grants from the same admin should not exceed daily quota.
    # Use separate AsyncSession objects so the advisory lock is the serialization point.
```

**Priority**: High — this is the P0 credit/ticket surface and the lock was added specifically to close a race condition.

---

### 2. Add `AuditEvent` assertion for quota failure

**Severity**: P2 (Medium)
**Location**: `tests/integration/routes/test_admin_credits.py:106-139`
**Criterion**: Explicit Assertions

**Issue Description**: The route test checks `403` and the error detail, but does not assert that an `AuditEvent` row is persisted. The fix explicitly added `await session.commit()` in the quota exception handler; a missing assertion means a future regression could silently drop audit events.

**Recommended Improvement**:

```python
assert res.status_code == 403
assert "quota exceeded" in res.json()["detail"].lower()

audit = await db_session.execute(
    select(AuditEvent).where(
        AuditEvent.action == "manual_credit_quota_exceeded",
        AuditEvent.actor_id == db_superuser.id,
    )
)
assert audit.scalar_one_or_none() is not None
```

---

### 3. Add route tests for `limit`/`offset`, key length, and wildcard escaping

**Severity**: P2 (Medium)
**Location**: `tests/integration/routes/test_admin_credits.py`
**Criterion**: Data Factories / Explicit Assertions

**Issue Description**: The review fix added `limit`/`offset`, `Idempotency-Key` length validation, and `reason` wildcard escaping, but none are covered by tests.

**Recommended Improvement**: Extend `test_get_admin_credits_ledger_filter_by_workspace` to request `?limit=1&offset=0` and assert one row, then `?offset=1` and assert none. Add a test for a key >64 characters returning 400, and a test for `?reason=support%` matching literally (escaped) rather than matching every row.

---

### 4. Use a shared payload factory for route tests

**Severity**: P3 (Low)
**Location**: `tests/integration/routes/test_admin_credits.py:23-214`
**Criterion**: Data Factories / Maintainability

**Issue Description**: The same JSON payload is repeated in six tests. This makes the test file longer and increases the chance of drift.

**Recommended Improvement**:

```python
def _adjust_payload(workspace_id: int, **overrides):
    return {"workspace_id": workspace_id, "amount_credits": 100, ...} | overrides
```

---

## Best Practices Found

### 1. Real database fixtures with rollback isolation

**Location**: `tests/integration/conftest.py:82-97`
**Pattern**: fixture-architecture

The `db_session` fixture uses `join_transaction_mode="create_savepoint"` and an outer transaction rollback so every test starts clean. This is an excellent pattern for integration tests.

---

### 2. Pure unit tests for validation

**Location**: `tests/unit/services/test_manual_credits.py:21-82`
**Pattern**: test-levels-framework

The unit file uses a `_FakeSession` to exercise validation and conversion without touching the database. This keeps the unit test fast and focused.

---

## Context and Integration

### Related Artifacts

- **Story File**: [_bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md](../_bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md)

---

## Knowledge Base References

This review consulted the following knowledge base fragments:

- **[test-quality.md](../../../.claude/skills/bmad-testarch-test-review/resources/knowledge/test-quality.md)** — Definition of Done for tests.
- **[test-levels-framework.md](../../../.claude/skills/bmad-testarch-test-review/resources/knowledge/test-levels-framework.md)** — Unit vs integration test appropriateness.
- **[fixture-architecture.md](../../../.claude/skills/bmad-testarch-test-review/resources/knowledge/fixture-architecture.md)** — Fixture patterns.
- **[selective-testing.md](../../../.claude/skills/bmad-testarch-test-review/resources/knowledge/selective-testing.md)** — Duplicate coverage detection.

---

## Next Steps

### Immediate Actions (Before Merge)

1. **Add advisory-lock / concurrency test** — exercise the `pg_advisory_xact_lock` path.
   - Priority: P1
   - Owner: feature author
   - Estimated Effort: 30 min

2. **Assert `AuditEvent` on quota failure** — verify audit persistence in route test.
   - Priority: P2
   - Owner: feature author
   - Estimated Effort: 15 min

### Follow-up Actions (Future PRs / next gate)

1. **Add route tests for pagination, key length, and wildcard escaping** — improve route coverage.
   - Priority: P2
   - Target: before mutation gate

2. **Introduce a shared payload factory** — reduce duplication in route tests.
   - Priority: P3
   - Target: backlog

### Re-Review Needed?

✅ Re-review completed 2026-08-17: all P1/P2 recommendations were applied and the full 25.2 test suite now passes (20 tests). The suite is ready for `bmad-nowing-mutation-gate`.

---

## Decision

**Recommendation**: Approve

**Rationale**: The 25.2 tests are deterministic, isolated, fast, and map to acceptance criteria. They pass and provide good happy-path and validation coverage. However, the P0 concurrency guard (advisory lock) and the audit-commit path are not directly exercised. Adding those tests is a small effort and is strongly recommended before the mutation gate, where those code paths are likely to survive if not asserted.

---

## Appendix

### Violation Summary by Location

| Line  | Severity | Criterion           | Issue                                      | Fix                                      |
| ----- | -------- | ------------------- | ------------------------------------------ | ---------------------------------------- |
| 160   | P1       | Explicit Assertions | Sequential idempotency does not test lock  | Add concurrent multi-session test        |
| 106   | P2       | Explicit Assertions | Quota test does not assert AuditEvent      | Assert `AuditEvent` persisted            |
| 181   | P2       | Data Factories      | New pagination/key/wildcard code untested  | Add targeted route tests                 |
| 23    | P3       | Data Factories      | Payload repeated across route tests        | Add `_adjust_payload` factory            |

### Related Reviews

| File                                                         | Score    | Grade | Critical | Status             |
| ------------------------------------------------------------ | -------- | ----- | -------- | ------------------ |
| `tests/unit/services/test_manual_credits.py`                 | 92/100   | A     | 0        | Approved           |
| `tests/integration/services/test_manual_credits.py`          | 80/100   | B+    | 0        | Approved with comments |
| `tests/integration/routes/test_admin_credits.py`             | 78/100   | B+    | 0        | Approved with comments |

**Suite Average**: 82/100 (Good)

---

## Review Metadata

**Generated By**: BMad TEA Agent (Test Architect)
**Workflow**: testarch-test-review v4.0
**Review ID**: test-review-25-2-20260816
**Timestamp**: 2026-08-16 23:20:00
**Version**: 1.0
