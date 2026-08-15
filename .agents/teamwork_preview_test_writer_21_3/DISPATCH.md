## 2026-08-15T06:34:20Z
<USER_REQUEST>
You are the ATDD Test Architect for Story 21.3 (Contact Enrichment & PII Governance).
Your working directory is: /Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_test_writer_21_3
Read the original user request at: /Users/luisphan/Documents/GitHub/nowing/.agents/ORIGINAL_REQUEST.md
Read the Story 21.3 specification at: /Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/21-3-enriched-contact-data.md
Read the ATDD skill instructions at: /Users/luisphan/Documents/GitHub/nowing/.agents/skills/bmad-testarch-atdd/SKILL.md

Your mission:
Apply BMad ATDD methodology (`bmad-testarch-atdd`) to create comprehensive red-phase acceptance test scaffolds covering all Acceptance Criteria (AC-1 to AC-10) of Story 21.3:
1. `nowing_backend/tests/unit/lead_intelligence/test_contact_enrichment.py`:
   - AC-1: Request enrichment (EnrichmentRequest creation, status=pending, 202 Accepted).
   - AC-2: Waterfall verification (`cleanlist` -> fallback `bettercontact` -> `fallback` MX check/regex).
   - AC-3: `VerifiedContact` persistence with PII encryption via `TokenEncryption`, `Lead.enriched=True`.
   - AC-4: Redaction of raw PII via `redact_pii(..., context="lead_enrichment")` before creating `Memory(source_type=MemorySourceType.ENRICHMENT, source_uuid=..., source_entity_type="enrichment_request")`.
   - AC-5: 30-day Redis cache key `enrichment:v1:{workspace_id}:{client_id}:{lead_id}` (cache hit returns contacts and skips API/billing).
   - AC-6: `BillingEvent` recording via `BillingEventService.record_contact_enrichment` with `cost_micros`, pre-check wallet debit. No `TokenUsage`.
   - AC-7: Consent & legal basis fields.
   - AC-8: REST endpoint behaviors (`POST /enrich`, `POST /bulk`, `GET /enrichments`, `GET /contacts`, `GET /cost`).
   - AC-10: Degradation handling (`insufficient_wallet`, `provider_unavailable`, `lead_not_found`).
2. `nowing_backend/tests/unit/capabilities/test_lead_enrich_capability.py`:
   - AC-9: Capability `lead.enrich` registration, `billing_unit=None`, metadata, and schemas.
3. `nowing_backend/tests/integration/lead_intelligence/test_contact_enrichment.py`:
   - Integration test with DB sessions, tenancy scoping (AD-31 `workspace_id` + `client_id: CITEXT`), RLS, composite index query efficiency, and memory provenance (AD-44/AD-47).

Run the tests (e.g. `uv run pytest tests/unit/lead_intelligence/test_contact_enrichment.py`) to confirm the red-phase test scaffolds exist and fail expectedly prior to implementation.
Write your handoff report to:
`/Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_test_writer_21_3/handoff.md`
and notify the orchestrator (id: 50a7ac8d-3de4-4fdf-bf6c-27623b1509b7) via `send_message`.
</USER_REQUEST>
