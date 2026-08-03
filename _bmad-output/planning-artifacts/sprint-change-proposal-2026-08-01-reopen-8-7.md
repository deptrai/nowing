---
date: 2026-08-01
story_key: 8-7
proposed_by: Devin (bmad-correct-course)
status: proposed
---

# Sprint Change Proposal — Reopen Story 8.7 for P0 Human-Review Gate

## 1. Issue Summary

Story **8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit** was marked `done` after code review on 2026-07-26 (2 decisions resolved + 26 patches applied). However, the story file explicitly notes:

> **Not yet through the P0 human-review gate** — see Change Log.

The P0 human-review gate has not been completed. Marking the story `done` in `sprint-status.yaml` before the human review is closed creates an incorrect sprint signal and risks the gate being skipped.

## 2. Impact Analysis

| Area | Impact |
|---|---|
| **Epic 8** | Epic 8 status remains `in-progress`; reopening 8.7 does not change epic status. |
| **Sprint status** | `8-7` must revert from `done` to `review`. |
| **Story artifact** | `8-7-auto-extract-spend-budget-cap.md` status line updated to `review` with note about P0 gate. |
| **Dependencies** | Story 8.8 (kill-switch) is still `done` and remains a prerequisite. Story 8.7 itself is a gate for auto-extract on production (migration 179). |
| **merge-to-prod-checklist.md** | Gate G4 remains open until 8.7 passes P0 human review. |
| **Other stories** | No impact on 8.10, 8.11, 9.3, etc. |

## 3. Recommended Approach

1. Reopen Story 8.7 by changing its status to `review` in both:
   - `_bmad-output/implementation-artifacts/sprint-status.yaml`
   - `_bmad-output/implementation-artifacts/8-7-auto-extract-spend-budget-cap.md`
2. Assign / schedule the P0 human-review gate (architecture + cost-control + ops review).
3. Once the P0 human-review gate passes, move 8.7 back to `done`.
4. Until then, keep `MEMORY_AUTO_EXTRACT_ENABLED=false` in production as already recommended.

## 4. Decisions

- **D1 — Reopen, not split:** No new story is created; the existing 8.7 artifact is returned to `review` because the implementation is complete and only the human gate remains.
- **D2 — Status = `review`:** `review` is the correct status for a story awaiting human sign-off, as distinct from `in-progress` (active coding) or `done` (complete).

## 5. Files Changed

- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/8-7-auto-extract-spend-budget-cap.md`
- This proposal file.
