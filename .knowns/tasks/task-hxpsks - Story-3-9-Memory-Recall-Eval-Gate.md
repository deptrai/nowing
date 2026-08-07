---
id: hxpsks
title: Story 3.9 — Memory Recall Eval-Gate
status: done
priority: medium
labels:
  - bmad
  - bmad-key-3-9-memory-recall-eval-gate
  - epic-3
createdAt: '2026-07-28T15:10:18.408Z'
updatedAt: '2026-08-07T05:34:24.707Z'
completedAt: '2026-08-07T05:34:24.707Z'
timeSpent: 0
parent: i5cw4u
spec: stories/story-3-9-memory-recall-eval-gate
---
# Story 3.9 — Memory Recall Eval-Gate

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
code review 2026-07-25: 4 decisions + 43 patches applied (ship-gate moved off unreachable precision@5>=0.80 onto recall@5/MRR/distractor-noise/off-corpus; AC-3 denominator fixed; gate fail-closed while baseline unratified; CI split PR-proof vs live release gate). 413 passed/1 skipped, ruff clean, MCP selfcheck+memory tools green. Blocked from `done` on measuring the SM-10 baseline, which waits on 8-7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-07: re-ran memory-recall hermetic tests (171 passed) and SM-10 release gate against baseline artifact at _bmad-output/implementation-artifacts/evidence/3-14-eval-20260728T230000Z; gate PASS (recall@5=0.986, mrr=1.000, distractor_noise=0.067, off_corpus=0.033, n_queries=36).
<!-- SECTION:NOTES:END -->

