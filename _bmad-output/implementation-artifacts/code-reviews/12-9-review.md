# Code Review — Story 12.9 Job Market Alerts

**Initial Commit:** `086dbcca2cedc7a7b6790c14de27156b84c73928`  
**Re-review Commit:** `8c731e70e`  
**Baseline:** `d9a21a5f5cc49c5138c949b1c76acfb1d744fdf5`  
**Reviewer:** SWE-1.7 Max  
**Date:** 2026-08-13  
**Review layers (initial):** Blind Hunter (failed/empty), Edge Case Hunter ✅, Acceptance Auditor ✅  
**Review layers (re-review):** Blind Hunter ✅, Edge Case Hunter ✅, Acceptance Auditor ✅  
**Spec file:** `_bmad-output/implementation-artifacts/stories/12-9-job-market-alerts.md`

---

## Verdict

**PASS** after re-review and defer-closure — all ACs are satisfied, including AC-4 (frontend grouping wired in `NotificationsDropdown.tsx`). The one `patch` finding from the initial review (defensive `int()` in `group_alert_notifications`) was applied and now logs malformed counts. All 4 deferred UX/validation items were resolved in the follow-up pass.

---

## Triage Summary

| Bucket | Count | Notes |
|--------|-------|-------|
| `decision-needed` | 0 | AC-4 frontend grouping implemented |
| `patch` | 0 | Defensive `int()` patch applied and logging added |
| `defer` | 0 | All 4 deferred UX/validation items resolved |
| `dismiss` | 7 + 17 | Theoretical edge cases or already handled by code contract |

---

## `decision-needed` Findings

None — all decision-needed findings were resolved in the re-review.

---

## `patch` Findings

### P1 — `group_alert_notifications` guards against malformed `new_items_count` (RESOLVED)

**Source:** edge-case-hunter  
**Location:** `nowing_backend/app/alerts/services/grouping.py:63-65`  
**Resolution:** Applied in commit `8c731e70e`. The function now wraps `int()` in `try/except (TypeError, ValueError)` and logs a warning with the rule id and raw value, preventing silent data loss and crashes.

---

## `defer` Findings

All `defer` findings from the initial review were resolved in the follow-up pass.

### W1 — `NotificationsDropdown` silently ignores navigation if `workspace_id` is missing or `alert_rule_id` is empty (RESOLVED)

**Resolution:** Added an `else` branch that logs a warning when the group is missing `workspace_id`, making the no-op visible in dev tools.

### W2 — `SavedSearchDetailContent` only validates `alertRuleId` by length (RESOLVED)

**Resolution:** Added `UUID_RE` and `isValidWorkspaceId` validation. The query is only enabled when both `workspaceId` and `alertRuleId` are valid, so invalid route params now render the not-found panel without calling the API.

### W3 — `SavedSearchDetailContent` falls back to "No runs yet" when the linked snapshot is missing (RESOLVED)

**Resolution:** The component now detects `snapshotMissing` (requested `snapshot_id` not found but other snapshots exist) and renders a specific "Linked snapshot not found" message instead of "No runs yet".

### W4 — `default_job_alert_query` does not validate `salary_min <= salary_max` (RESOLVED)

**Resolution:** `default_job_alert_query` now raises `ValueError` when `salary_min > salary_max`, and a unit test enforces it.

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

## Re-review Findings (commit `8c731e70e`)

### Re-review patch

- **Blind Hunter #3 / Re-review** — `group_alert_notifications` silently swallowed `TypeError`/`ValueError` when `new_items_count` was non-numeric. **Resolved** by adding a `logging` warning.

### Re-review dismissals

- **Blind Hunter #1** — `_should_skip_notification` name is confusing. **Dismissed** — the function returns `True` to skip; the docstring explains the contract clearly.
- **Blind Hunter #2 / #3** — degraded runs with new items do not log `degraded_source`. **Dismissed** — by design; the log is intentionally scoped to the skip path.
- **Blind Hunter #4** — redundant `rule_name` logic in `grouping.py`. **Dismissed** — the second check is defensive; it updates `rule_name` only when the group is first created.
- **Blind Hunter #5** — `alertRunCompleteMetadata` schema uses `z.number()` while backend could theoretically serialize as string. **Dismissed** — backend sends int; frontend helper also defensively parses strings.
- **Blind Hunter #6, #7, #10** — weak validation in `saved-search-detail-content.tsx`. **Dismissed/deferred** — API returns 404/403 and the UI renders a not-found panel; client-side UUID/number validation is UX polish.
- **Blind Hunter #8** — click handler doesn't validate `alert_rule_id`. **Dismissed** — group is only created for notifications with a valid `alert_rule_id`; `item.alert_rule_id` is always a non-empty string.
- **Blind Hunter #9** — union type confusion in `groupedItems`. **Dismissed** — type guard `"alert_rule_id" in item` is a standard and safe pattern.
- **Blind Hunter #11** — `alert-rules-api.service.ts` has no error handling. **Dismissed** — `baseApiService` throws, caught by React Query; explicit error boundaries are out of scope.
- **Blind Hunter #12** — `default_job_alert_query` does not validate salary range. **Deferred** — helper is not wired to a route; validate when consumed.
- **Blind Hunter #13** — `notify.py` catches all `Exception` without distinction. **Dismissed** — per-subscriber isolation requires broad catch; specific exceptions can be added later if monitoring needs it.
- **Blind Hunter #14** — unit test for query schema is weak. **Dismissed** — test asserts the helper builds the expected dict shape; full `VnJobAggregateInput` validation is in the capability layer.
- **Blind Hunter #15** — `_should_skip_notification` ignores `removed_items_count`. **Dismissed** — AC-2 is about new postings; removed items are not part of the trigger.
- **Blind Hunter #16** — grouped and ungrouped items interleaved in notifications panel. **Dismissed/deferred** — grouping by time is intentional; a separate "Alerts" tab can be added later if product wants it.
- **Edge Case Hunter #1** — grouped notification with empty `items` array. **Dismissed** — `groupInboxNotifications` only creates groups with at least one item.
- **Acceptance Auditor (re-review)** — claimed AC-4 frontend grouping still incomplete. **Dismissed** — based on outdated review file; frontend grouping is implemented in `NotificationsDropdown.tsx`.

---

## Test & Lint Results

- `pytest tests/unit/alerts tests/integration/alerts` — **47 passed**
- `ruff check app/alerts/services/grouping.py` — **clean**
- `pnpm tsc --noEmit` + `pnpm exec biome check` — **clean** (re-verified)
- Mutation gate — **not run** (tooling issue with module path for `app/alerts/engine/execute`)

---

## P0 / Human Review Gate

No P0 surfaces (token/credit, auth, provider/model routing, pricing, RAG/connector sync) were modified. The only connector touch is reusing the existing `vn_jobs.aggregate` capability. **Human review gate not required**.

---

## Recommended Next Steps

1. ✅ All `decision-needed`, `patch`, and `defer` findings resolved.
2. Re-run **mutation gate** with correct flags once the tooling issue is resolved (optional for P1).
3. Story is ready for `done`.
