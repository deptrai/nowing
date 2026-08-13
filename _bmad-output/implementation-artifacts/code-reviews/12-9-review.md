# Code Review — Story 12.9 Job Market Alerts

**Commit:** `086dbcca2cedc7a7b6790c14de27156b84c73928`  
**Baseline:** `d9a21a5f5cc49c5138c949b1c76acfb1d744fdf5`  
**Reviewer:** SWE-1.7 Max  
**Date:** 2026-08-13  
**Review layers:** Blind Hunter (failed/empty), Edge Case Hunter ✅, Acceptance Auditor ✅  
**Spec file:** `_bmad-output/implementation-artifacts/stories/12-9-job-market-alerts.md`

---

## Verdict

**PASS with `decision-needed` + `patch` findings** — AC-1/AC-2/AC-3/AC-5/AC-6 are satisfied and tests are green. AC-4 is partially satisfied: backend grouping exists but the frontend panel does not render grouped alerts. One `patch` finding should be applied for robustness. Several edge cases are theoretical and dismissed.

---

## Triage Summary

| Bucket | Count | Notes |
|--------|-------|-------|
| `decision-needed` | 1 | AC-4 frontend grouping: implement now or formally defer? |
| `patch` | 1 | `group_alert_notifications` should guard against non-numeric `new_items_count` |
| `defer` | 4 | UX/navigation edge cases, salary validation, pre-existing or out-of-scope |
| `dismiss` | 7 | Theoretical edge cases or already handled by code contract |

---

## `decision-needed` Findings

### D1 — AC-4 frontend grouping is not wired

**Source:** acceptance-auditor  
**AC:** AC-4 — "Given multiple job alerts, when viewed in the notifications/alerts panel, then they are grouped by search query with a match count."  
**Evidence:**
- Backend `app/alerts/services/grouping.py` implements `group_alert_notifications`.
- The diff does not include any frontend code that calls the grouping helper or renders grouped alerts in the notifications/alerts panel.
- Story spec lists the frontend task as unchecked (`- [ ] Web: alerts panel renders grouped by saved-search name`) and marks AC-4 as 🟡 with the note "web grouping rendered in story 12.7 panel".

**Question:** Should the frontend grouping be implemented in this story, or is it intentionally deferred to a later UI story (e.g., 12.7 / alerts panel)?

---

## `patch` Findings

### P1 — `group_alert_notifications` can crash on malformed `new_items_count`

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/services/grouping.py:63-65`  
**Issue:** `group["match_count"] += int(_metadata(notification).get("new_items_count") or 0)` will raise `ValueError` if a caller passes a non-numeric string (e.g., `"5 items"`). The `or 0` fallback only handles `None`/falsy values, not invalid strings.  
**Severity:** medium — a malformed notification object crashes the entire grouping call, affecting any caller that groups notifications.  
**Suggested fix:**

```python
nc = _metadata(notification).get("new_items_count") or 0
try:
    group["match_count"] += int(nc)
except (TypeError, ValueError):
    pass
```

---

## `defer` Findings

### W1 — `NotificationsDropdown` silently ignores navigation if `workspace_id` is missing or `alert_rule_id` is empty

**Source:** edge-case-hunter  
**Location:** `nowing_web/components/layout/ui/sidebar/NotificationsDropdown.tsx:231-241`  
**Issue:** The click handler checks `if (item.workspace_id && alertRuleId)` and does nothing otherwise. If the inbox schema allows `workspace_id` to be null or an empty `alert_rule_id` is supplied, the user gets no feedback.  
**Reason for defer:** `inboxItem` schema in the same file defines `workspace_id` as `z.number()` (non-null), and the backend always sets both IDs. This is a defensive-UX gap, not a reachable bug.

### W2 — `SavedSearchDetailContent` only validates `alertRuleId` by length

**Source:** edge-case-hunter  
**Location:** `nowing_web/app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/saved-search-detail-content.tsx:28`  
**Issue:** `const validId = alertRuleId.length > 0;` does not enforce UUID format.  
**Reason for defer:** The API returns 404 for invalid IDs and the UI renders a not-found panel. Adding client-side UUID validation is polish.

### W3 — `SavedSearchDetailContent` falls back to "No runs yet" when the linked snapshot is missing

**Source:** edge-case-hunter  
**Location:** `nowing_web/app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/saved-search-detail-content.tsx:47-48`  
**Issue:** If the notification's `snapshot_id` points to a deleted/missing snapshot and there are no other snapshots, the UI shows "No runs yet".  
**Reason for defer:** Graceful fallback is acceptable; a specific "linked run not found" message is polish.

### W4 — `default_job_alert_query` does not validate `salary_min <= salary_max`

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/services/crud.py:44-47`  
**Issue:** The helper allows an inverted salary range.  
**Reason for defer:** The helper is not yet called from any route, and the downstream capability/input schema will validate the range when consumed. Add validation when the helper is wired to a user-facing flow.

---

## `dismiss` Findings

### R1 — `_should_skip_notification` combines counts across diff strategies

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/engine/execute.py:221`  
**Reason for dismissal:** `execute.py:176-178` always assigns `new_items_count`, `changed_items_count`, and `removed_items_count` from the normalized `delta` dict. The contract is enforced at the source. Future strategies must follow the same contract — this is not a bug in the current diff.

### R2 — Invalid `diff_strategy` produces a confusing "no matches" message

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/engine/execute.py:158-189`  
**Reason for dismissal:** When `diff_snapshots` raises `ValueError`, `run_status` is set to `"failed"`. `_should_skip_notification` returns `False` for failed runs, so `notify_alert_run` is called. `_notification_message` then returns `"Saved search 'X' failed."` (not "no matches") because `run_status == "failed"` is checked first. The edge case is therefore not reachable.

### R3 — Degraded runs with new items do not log `degraded_source`

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/engine/execute.py:196-204`  
**Reason for dismissal:** The docstring explicitly states: "degraded runs that DO surface new postings still notify so nothing real is missed." The `degraded_source` log is intentionally scoped to the skip path only. If observability for all degraded runs is desired, that is a feature request, not an AC violation.

### R4 — `group_alert_notifications` could skip a UUID object `alert_rule_id`

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/services/grouping.py:27-29`  
**Reason for dismissal:** The backend serializes `alert_rule_id` to `str(...)` before writing notification metadata, and the API response schema requires a string. UUID objects are not a realistic input.

### R5 — Frontend metadata schema is strict and could reject missing `rule_name`

**Source:** edge-case-hunter  
**Location:** `nowing_web/contracts/types/inbox.types.ts:143-150`  
**Reason for dismissal:** The backend `notify.py` always sets `rule_name = alert_rule.name`, and the DB column is non-null. The strict schema is correct for the actual producer. Permissive schemas are defensive but not required for this diff.

### R6 — Invalid `rule.id` in `_execute_claimed_rule` could raise instead of log

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/engine/tick.py:58-65`  **Reason for dismissal:** `_claim_due_rules` loads `AlertRule` objects directly from the DB via SQLAlchemy, so `rule.id` is always a valid UUID. Corrupted objects would be a data-integrity failure far outside this story's scope.

### R7 — `except Exception` in `notify_alert_run` does not catch `KeyboardInterrupt`/`SystemExit`

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/engine/notify.py:145-160`  **Reason for dismissal:** Catching `BaseException` would swallow `KeyboardInterrupt` and `SystemExit`, which is an anti-pattern in async worker code. `Exception` is the correct boundary for subscriber-isolation.

---

## Test & Lint Results

- `pytest tests/unit/alerts tests/integration/alerts` — **47 passed**
- `ruff check app/alerts app/notifications/types.py tests/unit/alerts tests/integration/alerts` — **clean**
- `pnpm tsc --noEmit` + `pnpm exec biome check` — reported clean by author (not re-verified in this review)
- Mutation gate — **not run** (tooling issue with module path for `app/alerts/engine/execute`)

---

## P0 / Human Review Gate

No P0 surfaces (token/credit, auth, provider/model routing, pricing, RAG/connector sync) were modified. The only connector touch is reusing the existing `vn_jobs.aggregate` capability. **Human review gate not required**.

---

## Recommended Next Steps

1. Resolve **D1** (AC-4 frontend grouping): implement now or confirm deferral.
2. Apply **P1** (defensive `int()` in grouping).
3. Re-run **Blind Hunter** in a fresh session with a smaller diff chunk if the empty result was due to context length.
4. Re-run **mutation gate** with correct flags once the tooling issue is resolved.
5. If all `decision-needed` and `patch` findings are resolved, update story status to `done`.
