# Story 21.5: CRM Integration & Write-Back

Status: ready-for-dev

## Story

As a sales operations manager,
I want lead intelligence data synced with our CRM,
So that reps work from a single source of truth.

## Acceptance Criteria

- Given a CRM connection (Salesforce, HubSpot, Pipedrive), when lead data changes, then it syncs bidirectionally
- Given a new lead in Nowing, when pushed to CRM, then it creates a lead/contact record with mapped fields
- Given a lead update in CRM, when received, then Nowing updates the lead profile and score
- Given sync conflicts, when detected, then last-write-wins with audit log

## Tasks / Subtasks

- [ ] Task 1: CRM Connection (AC: 1)
  - [ ] 1.1 Create `CrmConnection` model (id, workspace_id, provider, credentials_encrypted, sync_config)
  - [ ] 1.2 OAuth flow for Salesforce, HubSpot, Pipedrive
  - [ ] 1.3 Store credentials encrypted (reuse existing pattern)
- [ ] Task 2: Read-Only Dedup (Phase 1)
  - [ ] 2.1 Match incoming leads against existing CRM contacts (email, domain)
  - [ ] 2.2 Flag duplicates before they reach CRM
  - [ ] 2.3 Generate CRM context document for agent
- [ ] Task 3: Write-Back (Phase 2)
  - [ ] 3.1 Push verified leads to CRM
  - [ ] 3.2 Map Nowing fields to CRM properties (configurable)
  - [ ] 3.3 Support lead assignment rules
- [ ] Task 4: Bidirectional Sync (Phase 3)
  - [ ] 4.1 Webhook receivers for CRM updates
  - [ ] 4.2 Conflict detection + resolution (last-write-wins)
  - [ ] 4.3 Sync audit log (`CrmSyncLog` model)

## Dev Notes

- **AD-40:** CRM integration pattern — read-first, then write-back
- **Source:** `app/services/crm_sync.py`, `app/routes/crm_routes.py`
- **Security:** Encrypt credentials at rest (reuse existing pattern)

### References

- [Source: epics.md §FR-67]
- [Source: epic21-architecture-update.md §AD-40]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### File List

Created: 2026-08-10
