# Story 21.3: Enriched Contact Data

Status: ready-for-dev

## Story

As an SDR,
I want verified contact data (email, phone) for my target accounts,
So that I can reach out to the right decision-makers.

## Acceptance Criteria

- Given a company, when contact enrichment is requested, then decision-maker names, titles, emails, and phone numbers are returned with verification status
- Given contact data, when verified, then email is validated via waterfall (5+ providers) and phone via real-time validation (9+ providers)
- Given enrichment results, when stored, then they are cached (TTL: 30 days) and linked to the lead profile
- Given an external API failure, when fallback triggers, then basic verification (MX check + pattern matching) is used

## Tasks / Subtasks

- [ ] Task 1: Waterfall Enrichment Engine (AC: 1, 2)
  - [ ] 1.1 Integrate Cleanlist/BetterContact API for email + phone waterfall
  - [ ] 1.2 Create `EnrichmentRequest` and `VerifiedContact` models
  - [ ] 1.3 Implement fallback verification (MX check + pattern matching)
- [ ] Task 2: Caching Layer (AC: 3)
  - [ ] 2.1 Cache enrichment results in Redis (TTL: 30 days)
  - [ ] 2.2 Link enriched contacts to lead profiles via Memory layer
- [ ] Task 3: API and MCP Tools
  - [ ] 3.1 Create `POST /workspaces/{id}/leads/{lead_id}/enrich` endpoint
  - [ ] 3.2 Create MCP tools: `nowing_enrich_lead`, `nowing_get_contacts`
  - [ ] 3.3 Add TokenUsage tracking (usage_type='contact_enrichment')

## Dev Notes

- **AD-36:** Buy via API (Cleanlist/BetterContact), don't build 14+ integrations
- **Email waterfall:** Findymail → LeadMagic → Wiza → People Data Labs → Prospeo
- **Phone waterfall:** Bytemine → PDL → LeadMagic → Wiza → Findymail → Forager → Prospeo → ContactOut → Zeliq
- **Source:** `app/services/contact_enrichment.py`, `app/routes/enrichment_routes.py`

### References

- [Source: epics.md §FR-65]
- [Source: epic21-architecture-update.md §AD-36]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### File List

Created: 2026-08-10
