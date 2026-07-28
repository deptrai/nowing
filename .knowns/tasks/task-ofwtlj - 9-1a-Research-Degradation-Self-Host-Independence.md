---
id: ofwtlj
title: 'Story 9.1a: Research Degradation & Self-Host Independence'
status: todo
priority: high
labels:
  - epic-9
  - p0
  - ready-for-dev
createdAt: '2026-07-28T09:23:41.477Z'
updatedAt: '2026-07-28T13:39:45.221Z'
timeSpent: 4
assignee: '@codex'
parent: nspcxd
spec: stories/story-9-1a-research-degradation-self-host-independence
order: 0
---
# Story 9.1a: Research Degradation & Self-Host Independence

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
P0 — FR-38 public-repo gate; honest engine_unavailable + bounded KB fallback.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No-key self-host returns engine_unavailable without 500 or uncaught error.
- [ ] #2 Timeout/unreachable/upstream failures fall back to bounded workspace KB retrieval.
- [ ] #3 Fallback is tenant-isolated, bounded (top_k <= 5), and never leaks workspace info.
- [ ] #4 KB fallback citations use real document_id/chunk_id, no fabricated URLs.
- [ ] #5 Parse explicit partial, insufficientEvidence, and heartbeat events; heartbeat is liveness.
- [ ] #6 REST sync, async, agent, and MCP doors return the same typed degradation contract.
- [ ] #7 Observability includes degradation reason, fallback hit count, and blocked URL coverage counters without secrets.
- [ ] #8 No fake billing for engine_unavailable no-content responses.
- [ ] #9 Public-repo gate evidence reproducible with ChainLens unconfigured.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Spec/story: _bmad-output/implementation-artifacts/9-1a-research-degradation-selfhost-independence.md
<!-- SECTION:NOTES:END -->

