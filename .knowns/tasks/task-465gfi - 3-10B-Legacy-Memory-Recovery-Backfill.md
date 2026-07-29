---
id: 465gfi
title: 3 10B Legacy Memory Recovery Backfill
status: done
priority: medium
labels:
  - bmad
  - bmad-key-3-10b-legacy-memory-recovery-backfill
  - epic-3
createdAt: '2026-07-28T15:10:18.448Z'
updatedAt: '2026-07-28T15:19:58.654Z'
completedAt: '2026-07-28T15:10:18.448Z'
timeSpent: 0
parent: i5cw4u
---
# 3 10B Legacy Memory Recovery Backfill

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
G1.2 guard trong 178.upgrade() (raise nếu legacy data chưa backfill) + G1.1 app-level command scripts/backfill_legacy_memory.py (embeddings không chạy được trong raw migration) + 5 integration tests xanh (backfill create/idempotent/dry-run + guard block/drop-after). Deploy-order: mig177 → backfill → mig178.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

