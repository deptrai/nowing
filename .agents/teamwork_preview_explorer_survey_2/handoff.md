# Handoff Report — Explorer Survey 2: Contact Enrichment & PII Governance (Epic 21)

**Agent:** Survey Explorer 2  
**Working Directory:** `/Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_explorer_survey_2`  
**Milestone:** Epic 21 Lead Gen Intelligence (Survey & Deep Dive)  
**Target:** Orchestrator (`50a7ac8d-3de4-4fdf-bf6c-27623b1509b7`)  

---

## 1. Observation

Direct observations and evidence from the codebase:

1. **PII Redaction Engine (`app/services/pii/redact.py:1-94`):**
   - Lines 5-8 explicitly define the governance contract:
     ```python
     # ``lead_enrichment`` (E21.3): redact phone, email, person names from
     # ``Memory.content``, ``Chunk[]``, audit logs, and non-privileged UI surfaces.
     # ``VerifiedContact`` stores raw values encrypted at rest and is the
     # authoritative source for outreach; it is never passed through this function.
     ```
   - Functions `redact_pii(text, context="lead_enrichment")` and `_apply_redaction` replace Vietnamese phone numbers matching `_PHONE_PATTERNS` (`+84...`, `0...`, `0xx-...`), emails (`_EMAIL_PATTERN`), and Vietnamese names (`_NAME_PATTERN`) with `<PHONE>`, `<EMAIL>`, and `<NAME>`.

2. **Secrets Redaction (`app/services/okf/redaction.py:1-72`):**
   - `redact_secrets(value)` recursively redacts sensitive dictionary keys (`api_key`, `token`, `secret`, `password`, `bearer`, etc.) and token patterns (`sk-...`, `pat_...`, `Bearer ...`, hex >= 20 chars) to `[REDACTED]` before writing export bundles.

3. **Encryption Cipher (`app/utils/oauth_security.py:155-232`):**
   - `TokenEncryption(secret_key)` provides standard Fernet symmetric authenticated encryption/decryption derived from `config.SECRET_KEY`.

4. **Existing Lead & Scoring Models (`app/db.py:4380-4478`):**
   - `Lead` (`id: UUID`, `workspace_id: Integer`, `client_id: CITEXT`, `company_name`, `domain`, `industry`, `fit_score`, `intent_score`, `composite_score`, `status`, `enriched: Boolean`, `consent_status: String(50)`, `legal_basis: String(50)`).
   - `LeadScore` (`id: UUID`, `workspace_id: Integer`, `client_id: CITEXT`, `lead_id: UUID`, `score`, `fit_score`, `intent_score`, `classification`, `factors_json`, `trend`, `converted_similarity`).
   - `MemorySourceType.ENRICHMENT` exists at `app/db.py:599`.

5. **Scraper Platform Suite & Rotation (`app/proprietary/platforms/` & `app/services/scraper_platform_account_service.py:1-423`):**
   - 19 platforms present: `batdongsan`, `chotot`, `masothue`, `google_maps`, `itviec`, `topcv`, `vietnamworks`, `muaban_bds`, `cafef`, `vietstock`, etc.
   - `batdongsan/parsers.py:287-335` (`parse_detail_phone`) unmasks contact phone numbers behind contact buttons.
   - `ScraperPlatformAccountService` and `ScraperPlatformAccountRotator` manage credentials encryption, token-bucket rate limits (`RateLimit(5.0 rpm, burst 2, cooldown 300s)`), and anti-bot escalation.

6. **Billing & Ledger (`app/services/billing_event_service.py:1-156`):**
   - `BillingEventService` records non-LLM business charges into `BillingEvent` and debits the owner's wallet via `wallet_credit.py`.

7. **Implementation Blueprint (`_bmad-output/implementation-artifacts/stories/21-3-enriched-contact-data.md` & `_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md`):**
   - Details AD-36 (Waterfall buy-vs-build via Cleanlist/BetterContact, 30-day Redis cache), AD-25/AD-49 (PII vault vs redaction), AD-31/AD-45 (Tenancy with `workspace_id` + `client_id: CITEXT`), AD-44/AD-47 (`Memory.source_uuid` + `Memory.source_entity_type` provenance), and AD-42 (Billing via `BillingEvent`).

---

## 2. Logic Chain

1. **Premise 1:** Contact enrichment deals with sensitive personal data (names, phone numbers, corporate/personal emails) that must be protected against unauthorized data leaks and compliance violations.
2. **Premise 2:** Nowing requires semantic search (RAG), audit trails, and multi-tenant isolation, but embedding raw PII into shared vector stores violates privacy invariants (AD-25).
3. **Inference 1:** The architecture cleanly separates the authoritative outreach vault (`VerifiedContact`, raw PII encrypted with Fernet at rest) from derived search/log surfaces (`Memory`, `Chunk[]`, audit logs, public UI) where `redact_pii(..., context="lead_enrichment")` strips all PII.
4. **Premise 3:** Building and maintaining 14+ independent email/phone scrapers is cost-prohibitive and fragile (AD-36).
5. **Inference 2:** The waterfall enrichment service integrates a single unified external API contract (Cleanlist / BetterContact) through an asynchronous Celery task (`enrich_lead_task`), backed by a 30-day Redis cache (`enrichment:v1:{workspace_id}:{client_id}:{lead_id}`) and a local fallback verifier (`FallbackVerifier`: MX lookup + regex).
6. **Premise 4:** Multi-tenancy and audit compliance require strict scoping and ledgering (AD-31, AD-42).
7. **Inference 3:** All new tables (`EnrichmentRequest`, `VerifiedContact`) include composite indexes on `(workspace_id, client_id, lead_id, created_at DESC)`, use `CITEXT` for `client_id`, bill via `BillingEvent` (`event_entity_type="enrichment_request"`, `event_type="contact_enrichment"`), and link to `Memory` via `source_uuid` + `source_entity_type`.
8. **Premise 5:** Downstream automated prospecting (Sequencer in Story 21.4) must comply with consent regulations (e.g. Decree 13, GDPR, CAN-SPAM).
9. **Inference 4:** `VerifiedContact` captures `consent_status` and `legal_basis`, providing the authoritative gate for outbound prospecting enrollment.

---

## 3. Caveats

1. **Vendor API Key Availability:** In local development and hermetic test environments, `CLEANLIST_API_KEY` and `BETTERCONTACT_API_KEY` will default to empty strings. The implementation must cleanly route to `FallbackVerifier` or test mock providers without raising unexpected errors.
2. **Redis Dependency for Caching:** The 30-day caching mechanism relies on Redis. In unit test suites, Redis calls must be mocked or fall back gracefully to direct execution if Redis is absent.
3. **CITEXT Extension:** AD-45 requires `CITEXT` PostgreSQL extension. Ensure `CREATE EXTENSION IF NOT EXISTS citext;` is present in migration scripts.

---

## 4. Conclusion

The architectural, schema, and operational specifications for **Contact Enrichment & PII Governance (Story 21.3)** are completely defined, fully consistent with existing patterns across `nowing_backend`, and ready for immediate implementation.

### Implementation Checklist for Milestone R2 (Story 21.3):
- **DB Migration (`alembic/versions/200_add_enrichment_tables.py`):** Create `enrichment_requests` and `verified_contacts` with `workspace_id`, `client_id` (CITEXT), composite indexes, and FKs. Add `Permission.LEADS_ENRICH` and `Permission.CONTACTS_READ`.
- **PII Encryption (`app/services/pii/verified_contact_encryption.py`):** Fernet encryption wrapper for `VerifiedContact` fields.
- **Enrichment Module (`app/lead_intelligence/enrichment/`):** `service.py`, `schemas.py`, `capability.py`, `providers.py`, `fallback.py`.
- **Celery Task (`app/tasks/celery_tasks/enrichment_tasks.py`):** `enrich_lead_task`.
- **Billing (`app/services/billing_event_service.py`):** Add `record_contact_enrichment`.
- **REST Endpoints (`app/routes/enrichment_routes.py`):** 5 endpoints (`POST /enrich`, `POST /bulk`, `GET /enrichments`, `GET /contacts`, `GET /cost`).
- **MCP Tools (`nowing_mcp`):** Register `nowing_enrich_lead` and `nowing_list_contacts`.

---

## 5. Verification Method

To independently verify these findings and test the future implementation:

1. **PII Redaction Unit Verification:**
   ```bash
   cd nowing_backend
   uv run pytest tests/unit/services/pii/ -q
   uv run pytest tests/unit/canonical/test_canonical_pii.py -q
   ```
2. **Scraper Account & Encryption Verification:**
   ```bash
   cd nowing_backend
   uv run pytest tests/unit/services/test_scraper_platform_account_service.py -q
   ```
3. **Story 21.3 Test Suite Execution (when built):**
   ```bash
   cd nowing_backend
   uv run pytest tests/unit/lead_intelligence/ -q
   uv run pytest tests/integration/lead_intelligence/ -q
   ```
4. **Code Quality & Linter Gates:**
   ```bash
   cd nowing_backend
   ruff check app/lead_intelligence/ app/services/pii/ app/routes/enrichment_routes.py
   ruff format --check app/lead_intelligence/ app/services/pii/ app/routes/enrichment_routes.py
   ```
