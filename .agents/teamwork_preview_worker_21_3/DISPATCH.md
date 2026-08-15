# Dispatch History

## 2026-08-15T06:38:29Z
You are the Senior Software Engineer Worker implementing Story 21.3 (Contact Enrichment & PII Governance) following the BMad dev-story methodology (`bmad-dev-story` / `bmad-quick-dev`).
Your working directory is: /Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_worker_21_3
Read the original user request at: /Users/luisphan/Documents/GitHub/nowing/.agents/ORIGINAL_REQUEST.md
Read the Story 21.3 spec at: /Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/21-3-enriched-contact-data.md
Read the red-phase test files created by ATDD:
- `nowing_backend/tests/unit/lead_intelligence/test_contact_enrichment.py`
- `nowing_backend/tests/unit/capabilities/test_lead_enrich_capability.py`
- `nowing_backend/tests/integration/lead_intelligence/test_contact_enrichment.py`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A forensic auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your mission:
Implement all required code to turn the red-phase tests into green tests across all Acceptance Criteria (AC-1 to AC-10):
1. DB Models in `nowing_backend/app/db.py`:
   - Add `EnrichmentRequest` and `VerifiedContact` with AD-31 tenancy (`workspace_id: Integer`, `client_id: CITEXT`), composite indexes, FKs, and RLS.
   - Add `Permission.LEADS_ENRICH` and `Permission.CONTACTS_READ`.
2. Alembic Migration in `nowing_backend/alembic/versions/200_add_enrichment_tables.py`.
3. Config in `nowing_backend/app/config/__init__.py` (API keys, cache TTL, primary provider, cost per contact).
4. PII Encryption wrapper in `nowing_backend/app/services/pii/verified_contact_encryption.py` (Fernet symmetric encryption using config.SECRET_KEY).
5. Billing Event Service in `nowing_backend/app/services/billing_event_service.py` (`record_contact_enrichment`).
6. Enrichment Module in `nowing_backend/app/lead_intelligence/enrichment/`:
   - `schemas.py`: Pydantic request/response schemas.
   - `providers.py`: Waterfall providers (`cleanlist`, `bettercontact`) with exponential backoff retry.
   - `fallback.py`: `FallbackVerifier` (MX record check + regex).
   - `service.py`: `EnrichmentService` with Redis caching (30 days), waterfall orchestration, PII encryption at rest, PII redaction (`redact_pii(..., context="lead_enrichment")`) before `MemoryRepository` creation (`source_type=MemorySourceType.ENRICHMENT`, `source_uuid`, `source_entity_type="enrichment_request"`), billing event recording, wallet pre-check and debit.
   - `capability.py`: Register `lead.enrich` capability (`billing_unit=None`).
7. Celery Task in `nowing_backend/app/tasks/celery_tasks/enrichment_tasks.py` or `nowing_backend/app/lead_intelligence/tasks/enrichment_tasks.py`.
8. REST Routes in `nowing_backend/app/routes/enrichment_routes.py` (5 endpoints) and wire into `app/routes/__init__.py` and `app/app.py`.
9. MCP tools in `nowing_backend/app/mcp_tools.py` and `nowing_mcp/`.

Run verification commands:
- `cd nowing_backend && uv run pytest tests/unit/lead_intelligence/test_contact_enrichment.py tests/unit/capabilities/test_lead_enrich_capability.py tests/unit/lead_intelligence/ -q`
- `cd nowing_backend && ruff check app/lead_intelligence/ app/routes/enrichment_routes.py app/services/pii/ tests/unit/lead_intelligence/`
- `cd nowing_backend && ruff format app/lead_intelligence/ app/routes/enrichment_routes.py app/services/pii/ tests/unit/lead_intelligence/`
