# Story 34.3 Spec: Dedicated CRM Deal Pipeline & Customer Activity Timeline UI Tabs

## Intent

As a Sales Lead, I want dedicated CRM Pipeline and Activity Timeline tabs in the web workspace, so that I can manage sales pipelines directly within Nowing.

## Acceptance Criteria

- **Given** the workspace has CRM enabled, **When** navigating to the CRM section, **Then** a Kanban deal board and unified chronological interaction timeline are rendered.
- **And** users can switch between "Pipeline (Kanban)" and "Activity Timeline" views.

## Technical Design

### 1. New Route & Page

- `/dashboard/[workspace_id]/crm/page.tsx`
- Tabbed interface using Radix / shadcn `Tabs`:
  - Tab 1: "Deal Pipeline" (embeds `LeadKanbanBoard`)
  - Tab 2: "Activity Timeline" (renders `WorkspaceActivityTimeline`)

### 2. Activity Timeline Component

- `components/crm/WorkspaceActivityTimeline.tsx`:
  - Fetches CRM sync logs and activity events across workspace
  - Chronological grouped list (Today, Yesterday, Older)
  - Event types: deal stage changes, contact enrichments, inbound webhooks, notes
  - Filters: by provider (HubSpot, Salesforce, Zalo), event type, date range

### 3. Backend Endpoint

- `GET /api/v1/workspaces/{workspace_id}/crm/activity-timeline`:
  - Aggregates `CrmSyncLog` and `LeadActivityTimeline` records
  - Returns paginated unified chronological events
