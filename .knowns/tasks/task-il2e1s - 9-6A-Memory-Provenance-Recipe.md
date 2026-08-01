---
id: il2e1s
title: 9 6A Memory Provenance Recipe
status: done
priority: medium
labels:
  - bmad
  - bmad-key-9-6a-memory-provenance-recipe
  - epic-9
createdAt: '2026-07-28T15:10:19.294Z'
updatedAt: '2026-08-01T10:34:29.585Z'
completedAt: '2026-08-01T10:25:26.778Z'
timeSpent: 0
parent: rzwqza
---
# 9 6A Memory Provenance Recipe

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
FR-39 phần provenance + AD-11.1. Memory tự chứa source_capability/source_input/source_run_id. KHÔNG sửa retention của runs. Tách từ 9-6 (Q-4)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Story context created and validated. File: _bmad-output/implementation-artifacts/9-6a-memory-provenance-recipe.md
Implemented 9.6a. Migration 186, Memory model, repository, run_extraction, schemas, tests. Focused suite 147 passed. Full suite has 4 unrelated env failures (CHAINLENS_API_KEY, PDF).
All code review findings applied. Migration backfill added; tests for None input and recipe immutability added. Focused suite 44/44 passed.
Re-review complete: 1 patch applied (backfill NULL input test), 1 decision deferred (source_input size cap). Full memory/db/workspaces suite 151/151 passed.
<!-- SECTION:NOTES:END -->

