---
id: e29qvu
title: 9 2 Deep Research Cost Metering
status: done
priority: high
labels:
  - bmad
  - bmad-key-9-2-deep-research-cost-metering
  - epic-9
createdAt: '2026-07-28T15:10:19.216Z'
updatedAt: '2026-08-10T20:20:18.945Z'
completedAt: '2026-08-10T20:20:18.945Z'
timeSpent: 0
parent: rzwqza
---
# 9 2 Deep Research Cost Metering

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
P0 — FR-37. Parse costDollars → TokenUsage(usage_type=deep_research); hiện under-meter 2.1-3.3x. Dep: ChainLens 42-1 + OQ-7(3)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified implementation and tests 2026-08-11.
- ruff check app/capabilities/chainlens/research/executor.py app/capabilities/chainlens/research/schemas.py app/capabilities/core/billing.py app/services/token_tracking_service.py: passed
- pytest tests/unit/capabilities/chainlens/research/test_executor.py -q: 40 passed
- pytest tests/unit/capabilities/test_billing.py -q: 65 passed
- pytest tests/integration/capabilities/chainlens/research/test_research_cost_metering.py -q: 5 passed
- pytest tests/integration/capabilities/chainlens/research/test_research_fallback.py -q: 10 passed
- pytest tests/unit/capabilities/chainlens/research -q: 250 passed, 1 skipped
Implementation artifact: _bmad-output/implementation-artifacts/9-2-deep-research-cost-metering.md (status done).
<!-- SECTION:NOTES:END -->

