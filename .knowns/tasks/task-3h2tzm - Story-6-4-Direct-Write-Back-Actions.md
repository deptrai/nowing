---
id: 3h2tzm
title: 'Story 6.4: Direct Write-Back Actions'
status: done
priority: medium
labels:
  - bmad
  - bmad-key-6-4-direct-write-back-actions-new-gap
  - epic-6
createdAt: '2026-07-28T15:10:18.731Z'
updatedAt: '2026-07-28T15:20:07.556Z'
completedAt: '2026-07-28T15:10:18.731Z'
timeSpent: 0
parent: jw240f
spec: stories/story-6-4-direct-write-back-actions
---
# Story 6.4: Direct Write-Back Actions

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Status: done


As a workspace member,
I want automation actions to write directly to Notion, Slack, Linear, or Jira,
so that research outputs land in the tools my team already uses.


1. **Action registry accepts new types**
   - `write_back_notion`, `write_back_linear`, `write_back_jira`, `write_back_slack` are registered as `ActionDefinition` entries.
   - Each has its own `params_model` and handler package under `app/automations/actions/builtin/`.

2. **Each action writes through the connecte
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

