# Epic 21 Lead Gen Intelligence: Survey & Deep Dive Analysis (Explorer 2)

**Focus Areas:** PII Redaction & Governance, Contact Enrichment (Story 21.3), Scraper Platform Connectors, Data Governance & Audit Trails, Exact Interfaces & Schemas.

---

## 1. Executive Summary

This investigation surveys the `nowing_backend/` codebase to establish the complete architectural and implementation blueprint for **Contact Enrichment & PII Governance** under Epic 21 (Lead Gen Intelligence, Story 21.3), alongside governance boundaries, scraper connectors, and data protection mechanisms.

### Core Architectural Invariants:
1. **PII Isolation & Encryption-at-Rest (AD-25 / AD-49):**
   - `VerifiedContact` is the authoritative PII vault (`nowing_backend/app/db.py`). Raw contact fields (`name`, `title`, `email`, `phone`) are encrypted at rest using `TokenEncryption` (`app/utils/oauth_security.py`).
   - `VerifiedContact` raw data is **never** passed through `redact_pii`.
   - `redact_pii(..., context="lead_enrichment")` (`app/services/pii/redact.py`) is strictly applied to all derived artifacts: `Memory.content`, `Chunk[]`, audit logs, public UI surfaces, and general LLM prompts (`<NAME>`, `<EMAIL>`, `<PHONE>`).
2. **Waterfall Enrichment via External API (AD-36):**
   - Single contract integration (Cleanlist / BetterContact) via asynchronous Celery tasks (`enrich_lead_task`).
   - Local fallback verification (`FallbackVerifier`: DNS MX checks + regex validation).
   - Multi-tier Redis caching (key: `enrichment:v1:{workspace_id}:{client_id}:{lead_id}`, TTL: 30 days) to prevent duplicate API spend.
3. **Multi-Tenancy & Provenance (AD-31, AD-44, AD-45, AD-47):**
   - Multi-tenant tenant scoping via `workspace_id: Integer` (FK `workspaces.id`) and `client_id: CITEXT | None` with composite indexes.
   - Authoritative provenance stored in `Memory.source_uuid` + `Memory.source_entity_type` with `source_type=MemorySourceType.ENRICHMENT`.
4. **Billing & Ledger Separation (AD-42 / AD-10):**
   - All business events are billed to `BillingEvent` via `BillingEventService.record_contact_enrichment` with `event_entity_type="enrichment_request"`, `event_type="contact_enrichment"`.
   - Pre-check and wallet debit are executed via `app/services/wallet_credit.py`.
   - `TokenUsage` is strictly reserved for LLM token metering; capability `lead.enrich` sets `billing_unit=None`.
5. **Consent & Outbound Gating:**
   - `VerifiedContact` tracks `consent_status` (`explicit`, `legitimate_interest`, `none`) and `legal_basis` (`consent`, `legitimate_interest`, `contract`, `legal_obligation`).
   - The downstream Sequencer (Story 21.4) gates outbound prospecting on `VerifiedContact.consent_status` in `{"explicit", "legitimate_interest"}`.

---

## 2. PII Redaction & Governance Rules

### 2.1 PII Redaction Services in Nowing

The codebase provides three distinct redaction mechanisms designed for different boundaries:

| Redactor Module | Target Scope | Implementation / Rules |
|---|---|---|
| `app/services/pii/redact.py` | Unstructured text, Memory summaries, logs, public UI | Uses regex for Vietnamese phone numbers (`_PHONE_PATTERNS` for `+84...`, `0...`), emails (`_EMAIL_PATTERN`), and Vietnamese names (`_NAME_PATTERN` with 17 surnames: Nguyễn, Trần, Lê, Phạm, Hoàng, Huỳnh, Vũ, Võ, Phan, Trương, Bùi, Đặng, Đỗ, Ngô, Hồ, Dương, Đinh). Contexts: `job_data` (E12.5), `lead_enrichment` (E21.3), `default`. Replaces with `<PHONE>`, `<EMAIL>`, `<NAME>`. |
| `app/services/okf/redaction.py` | OKF Export ZIP archives & JSON provenance | `redact_secrets()` / `redact_text()` recursively scrubs credentials matching `_SENSITIVE_KEY_PATTERN` (`api_key`, `token`, `secret`, `password`, `bearer`, etc.), `_TOKEN_PATTERN` (`sk-...`, `pat_...`, `nw_pat_...`), and `_HEX_SECRET_PATTERN` (hex >= 20 chars), replacing them with `[REDACTED]`. |
| `app/canonical/services/canonical_pii.py` | Canonical multi-source entity persistence | `redact_canonical_data()` strips raw PII for BDS listings and VN jobs. `_one_way_digest` produces HMAC-SHA256 digests (`phone_key`) using `CANONICAL_PII_DIGEST_KEY` for entity matching while stripping plaintext. `redact_source_snapshot()` removes matching keys completely for provenance. |

### 2.2 Encryption-at-Rest Architecture

- **Implementation:** `app/utils/oauth_security.py` -> `TokenEncryption`.
- **Cipher:** Fernet symmetric authenticated cryptography (AES-128-CBC + HMAC-SHA256 integrity verification).
- **Key Derivation:** Derived from `config.SECRET_KEY` via SHA-256 and base64 urlsafe encoding.
- **Dedicated Wrapper for Story 21.3:** `app/services/pii/verified_contact_encryption.py` wraps `TokenEncryption` to provide transparent `encrypt_contact` and `decrypt_contact` methods for `VerifiedContact` dictionaries and model attributes.

### 2.3 Boundary Invariant: The Verified Contact Vault

```
   [ External Waterfall API / Scraper / Fallback ]
                         │
                         ▼
        ┌───────────────────────────────────┐
        │       Raw Contact Extraction       │
        │  (name, title, email, phone)      │
        └─────────────────┬─────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│     VerifiedContact       │   │    Memory / Log / UI      │
│     (PII Vault)           │   │    (Derived Surfaces)     │
├───────────────────────────┤   ├───────────────────────────┤
│ • Raw PII Encrypted       │   │ • redact_pii() Applied    │
│   via Fernet Cipher       │   │ • <NAME>, <EMAIL>,        │
│ • Stored in DB            │   │   <PHONE> place-holders   │
│ • Decrypted ONLY for      │   │ • Used for RAG search,    │
│   authorized send/REST    │   │   provenance, public logs │
└───────────────────────────┘   └───────────────────────────┘
```

---

## 3. Contact Enrichment Workflows (Story 21.3)

### 3.1 End-to-End Workflow & Lifecycle

```
[ POST /workspaces/{id}/leads/{lead_id}/enrich ]
                         │
                         ▼
           ┌───────────────────────────┐
           │ 1. Tenancy & Auth Check   │
           │ (workspace_id, client_id) │
           └─────────────┬─────────────┘
                         │
                         ▼
           ┌───────────────────────────┐
           │ 2. Check 30-Day Cache     │
           │ (Redis enrichment:v1:...) │
           └─────────────┬─────────────┘
                  ┌──────┴──────┐
             Hit  │             │ Miss
                  ▼             ▼
       ┌────────────────┐ ┌────────────────────────────────┐
       │ Return Cached  │ │ 3. Pre-flight Wallet Check     │
       │ Contact IDs    │ │    (wallet_credit.check_balance)│
       └────────────────┘ └─────────────┬──────────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────┐
                          │ 4. Create EnrichmentRequest    │
                          │    (status="pending")          │
                          │    Enqueue Celery Task         │
                          │    Return 202 Accepted         │
                          └─────────────┬──────────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────┐
                          │ 5. Celery Worker Execution     │
                          │    (enrich_lead_task)          │
                          └─────────────┬──────────────────┘
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
          ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
          │ Primary API   │ ──► │ Secondary API │ ──► │ Fallback DNS  │
          │ (Cleanlist)   │     │(BetterContact)│     │  MX + Regex   │
          └───────────────┘     └───────────────┘     └───────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────┐
                          │ 6. Persist VerifiedContact     │
                          │    (Encrypted PII, status)     │
                          └─────────────┬──────────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────┐
                          │ 7. Record Billing & Debit      │
                          │    (BillingEventService)       │
                          │    (wallet_credit.apply_debit) │
                          └─────────────┬──────────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────┐
                          │ 8. Write Redacted Memory       │
                          │    (MemorySourceType.ENRICHMENT│
                          │    tags=["enriched_contact"])  │
                          └─────────────┬──────────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────┐
                          │ 9. Update Lead Flags & Cache   │
                          │    (Lead.enriched = True)      │
                          │    (Set Redis TTL 30 days)     │
                          └────────────────────────────────┘
```

### 3.2 Waterfall Provider Architecture

- **Primary Provider (`CleanlistClient`):** High-accuracy B2B email and phone discovery.
- **Secondary Provider (`BetterContactClient`):** Multi-source waterfall aggregator fallback.
- **Fallback Verification (`FallbackVerifier`):** Local DNS MX record lookup (`dns.resolver`), RFC 5322 email syntax validation, and E.164 phone formatting. Marks `verification_status="low_confidence"` and `source_provider="fallback"`.

### 3.3 Verification States & Confidence Model

- `verified` (confidence >= 80.0): Confirmed active mailbox / working phone from primary or secondary waterfall provider.
- `low_confidence` (confidence 30.0 - 79.0): Syntactically valid + MX domain verified, or scraped unmasked number without carrier ping.
- `unverified` (confidence < 30.0): Pattern matching only or unreachable MX.

---

## 4. Existing Scraper Platforms & Connectors

Nowing contains **19 proprietary platform scrapers** in `app/proprietary/platforms/` connected to standard capability executors (`app/capabilities/`):

### 4.1 Platform Classification & Lead Signals

| Category | Platform Modules | Extracted Contact / Lead Attributes | Phone / Contact Unmasking Mechanics |
|---|---|---|---|
| **Real Estate** | `batdongsan`, `chotot`, `muaban_bds` | Seller name, phone number, listing detail URL, property price/location, agent agency | `batdongsan/parsers.py` -> `parse_detail_phone` extracts masked `phone_display` or unmasked `phone` behind `js__phone-event` / `re__btn-phone-icon`. SSR listing fallback for detail URLs. |
| **Recruitment / Jobs** | `itviec`, `topcv`, `vietnamworks`, `indeed` | Company name, job title, tech stack keywords, hiring volume, recruiter emails | Scrapes active postings, sanitizes recruiter contacts, feeds `hiring.signal` detection (Story 21.1). |
| **Corporate Registers** | `masothue` | `tax_code`, `name` (legal name), `tax_address`, `legal_representative`, `phone`, `main_industry`, `active_date` | `masothue/parsers.py` extracts enterprise registration records, tax authority details, and corporate representative contacts. |
| **Places & Search** | `google_maps`, `google_search` | Business title, address, phone number, website URL, social media links (FB, IG, YT, TikTok, Twitter), reviews, opening hours | Full Apify-compatible schema (`GoogleMapsScrapeInput`). Extracts verified business phone and corporate website domain. |
| **Social & Media** | `instagram`, `tiktok`, `youtube`, `reddit` | Channel/account handles, bio links, emails in bio/descriptions, comment sentiment | Extracts public social links and contact info from channel metadata. |
| **Finance & Markets** | `cafef`, `vietstock` | Corporate ticker, executive moves, financial filings, funding announcements | Feeds `funding.signal` and `executive_move.signal` detection. |
| **E-commerce** | `amazon`, `walmart` | Merchant name, storefront URL, brand ratings | Merchant discovery and product intelligence. |

### 4.2 Scraper Platform Account Rotation & Rate Limiting

- **Service:** `app/services/scraper_platform_account_service.py`
- **DB Model:** `ScraperPlatformAccount` in `app/db.py`
  - `encrypted_credentials`: Fernet-encrypted JSON (cookies, session tokens, JWTs).
  - `is_enabled`, `is_default`, `last_used_at`, `usage_state` (JSONB).
- **Rotator:** `ScraperPlatformAccountRotator` implements token-bucket sliding-window rate limiting:
  - `RateLimit(requests_per_minute=5.0, burst=2, cooldown_seconds=300.0, max_consecutive_failures=3)`.
  - Automatically isolates banned/restricted accounts on cooldown (`banned_until`) and balances load across healthy credentials.
  - Cookie normalizer supports Playwright extension exports and standard `CookieJar` strings.

---

## 5. Data Governance, Consent Tracking & Audit Trails

### 5.1 Multi-Tenant Isolation (AD-31 & AD-45)

- Every Epic 21 table includes:
  - `workspace_id`: `Integer`, FK `workspaces.id` on delete CASCADE (indexed).
  - `client_id`: `CITEXT`, nullable, case-insensitive string representing vertical/agency client scope (indexed).
  - Composite indexes: `ix_<table_name>_workspace_lookup` on `(workspace_id, client_id, lead_id, created_at DESC)`.

### 5.2 Provenance Chain (AD-44 & AD-47)

- Every enrichment and scoring run creates a durable `Memory` row:
  - `source_uuid`: UUID of `EnrichmentRequest.id` or `LeadScore.id`.
  - `source_entity_type`: String `"enrichment_request"` or `"lead_score"`.
  - `source_type`: `MemorySourceType.ENRICHMENT` (enum value `"enrichment"`).
  - `tags`: `["enriched_contact"]` or `["lead_score"]`.
  - `content`: Redacted JSON summary (PII-free).

### 5.3 Consent Tracking & Outreach Gating

- `VerifiedContact` stores:
  - `consent_status`: `explicit` | `legitimate_interest` | `none`.
  - `legal_basis`: `consent` | `legitimate_interest` | `contract` | `legal_obligation`.
- **Governance Gate:** Upstream enrichment services do not fabricate consent. The downstream Sequencer (Story 21.4) **must reject** first-touch sequence enrollments unless `VerifiedContact.consent_status` is in `{"explicit", "legitimate_interest"}`.

### 5.4 Access Control & Audit Trails

- **RBAC Permissions:**
  - `Permission.LEADS_ENRICH = "leads:enrich"` (Editor / Owner)
  - `Permission.CONTACTS_READ = "contacts:read"` (Viewer / Editor / Owner)
  - `Permission.LEADS_READ = "leads:read"`
  - `Permission.LEADS_SCORE = "leads:score"`
  - `Permission.SIGNALS_READ = "signals:read"`
  - `Permission.SIGNALS_DETECT = "signals:detect"`
- **Financial Audit Ledger:** `BillingEvent` records every enrichment event (`event_entity_type="enrichment_request"`, `event_type="contact_enrichment"`, `event_id=EnrichmentRequest.id`, `cost_basis="actual"`).
- **Tool Execution Audit:** `AgentActionLog` captures agent tool calls and descriptors.
- **Export Redaction Controls:** `ExportService` (`app/services/export_service.py`) automatically strips secrets and sensitive keys via `redact_secrets` before exporting OKF bundles.

---

## 6. Exact Interfaces & Schemas for Contact Enrichment (Story 21.3)

### 6.1 Database Models (`app/db.py`)

```python
class EnrichmentRequest(Base, TimestampMixin):
    """Tracks an asynchronous contact enrichment waterfall request."""
    __tablename__ = "enrichment_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")  # pending/processing/completed/failed
    provider_results = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    contact_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=text("now()"))

    __table_args__ = (
        Index("ix_enrichment_requests_workspace_lookup", "workspace_id", "client_id", "lead_id", "created_at"),
    )

    workspace = relationship("Workspace")
    lead = relationship("Lead")
    contacts = relationship("VerifiedContact", back_populates="enrichment_request", cascade="all, delete-orphan")


class VerifiedContact(Base, TimestampMixin):
    """Authoritative PII vault storing encrypted contact details for outreach."""
    __tablename__ = "verified_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    enrichment_request_id = Column(UUID(as_uuid=True), ForeignKey("enrichment_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Raw PII columns - encrypted at rest via Fernet (TokenEncryption)
    name = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    
    verification_status = Column(String(20), nullable=False, default="unverified", server_default="unverified")
    confidence = Column(Float, nullable=False, default=0.0, server_default="0.0")
    source_provider = Column(String(50), nullable=False)
    consent_status = Column(String(50), nullable=True)
    legal_basis = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=text("now()"))

    __table_args__ = (
        Index("ix_verified_contacts_workspace_lookup", "workspace_id", "client_id", "lead_id", "created_at"),
    )

    workspace = relationship("Workspace")
    lead = relationship("Lead")
    enrichment_request = relationship("EnrichmentRequest", back_populates="contacts")
```

### 6.2 Pydantic Schemas (`app/lead_intelligence/enrichment/schemas.py`)

```python
class EnrichmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_id: UUID
    requested_count: int = Field(default=5, ge=1, le=20)
    lead_ids: list[UUID] | None = None  # For bulk endpoint

class VerifiedContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: int
    client_id: str | None = None
    lead_id: UUID
    name: str | None = None  # Decrypted for authorized caller
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    verification_status: str
    confidence: float
    source_provider: str
    consent_status: str | None = None
    legal_basis: str | None = None
    created_at: datetime

class EnrichmentRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: int
    client_id: str | None = None
    lead_id: UUID
    status: str
    contact_count: int
    cost_micros: int
    created_at: datetime

class EnrichmentOutput(BaseModel):
    enrichment_request_id: UUID | None = None
    lead_id: UUID
    contact_count: int = 0
    cost_micros: int = 0
    verified_contact_ids: list[UUID] = Field(default_factory=list)
    degraded: bool = False
    degradation_reasons: list[str] | None = None

class EnrichmentCostOutput(BaseModel):
    cost_per_contact_micros: int
    estimated_cost_micros: int
    lead_count: int
```

### 6.3 REST Endpoints (`app/routes/enrichment_routes.py`)

| Method | Path | RBAC Permission | Description |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/leads/{lead_id}/enrich` | `Permission.LEADS_ENRICH` | Start enrichment, return `EnrichmentRequestRead` (202 Accepted) or cached contacts |
| `POST` | `/workspaces/{workspace_id}/leads/enrich` | `Permission.LEADS_ENRICH` | Bulk lead enrichment for `lead_ids: list[UUID]` |
| `GET` | `/workspaces/{workspace_id}/leads/{lead_id}/enrichments` | `Permission.LEADS_READ` | List `EnrichmentRequest` rows with pagination |
| `GET` | `/workspaces/{workspace_id}/leads/{lead_id}/contacts` | `Permission.CONTACTS_READ` | List decrypted `VerifiedContactRead` items for lead |
| `GET` | `/workspaces/{workspace_id}/leads/enrich/cost` | `Permission.LEADS_READ` | Get cost projection per contact and total estimate |

### 6.4 Capability & Tool Integration

- **Capability:** `app/lead_intelligence/enrichment/capability.py` registers `lead.enrich` with `billing_unit=None`, `context_aware=True`, `metadata={"emits_leads": false, "requires_pii_redaction_context": "lead_enrichment"}`.
- **MCP Tools:** `nowing_enrich_lead(lead_id, requested_count)` and `nowing_list_contacts(lead_id, limit, offset)` in `nowing_mcp/mcp_server/features/enrichment/tools.py`.
- **Celery Task:** `app/tasks/celery_tasks/enrichment_tasks.py` -> `enrich_lead_task(enrichment_request_id)`.

---

## 7. Synthesis & Architectural Alignment

| Cross-Cutting Requirement | Design Decision | Verification Standard |
|---|---|---|
| **PII Protection** | Dual model: Encrypted Vault (`VerifiedContact`) + Masked Derived (`Memory` / `Chunk` / Logs via `redact_pii`). | No unencrypted PII in DB plaintext; zero raw PII in `Memory.content` or stdout. |
| **Waterfall Buy-vs-Build** | Buy external waterfall (Cleanlist / BetterContact); fallback to MX check; cache 30 days in Redis. | Single HTTP adapter interface; cache hits skip billable external calls. |
| **Financial Ledger** | Charge via `BillingEvent` with `event_entity_type="enrichment_request"`; debit owner wallet. | `BillingEvent` matches `cost_micros`; wallet balance decremented accurately. |
| **Tenancy Isolation** | Scoped by `workspace_id: Integer` and `client_id: CITEXT`. | Cross-tenant queries return 404/empty. |
| **Outbound Gating** | Store `consent_status` / `legal_basis` on `VerifiedContact` to gate Story 21.4 Sequencer. | Sequence enrollment blocks on unverified consent status. |

---

## 8. Summary of Files Examined

- `nowing_backend/app/db.py` (models: `Lead`, `LeadScore`, `Memory`, `MemorySourceType`, `BillingEvent`, `ScraperPlatformAccount`, `Permission`, `DEFAULT_ROLE_PERMISSIONS`)
- `nowing_backend/app/services/pii/redact.py` (`_apply_redaction`, `redact_pii`, `RedactedText`, `context="lead_enrichment"`)
- `nowing_backend/app/services/okf/redaction.py` (`redact_secrets`, `redact_text`, `_SENSITIVE_KEY_PATTERN`)
- `nowing_backend/app/canonical/services/canonical_pii.py` (`redact_canonical_data`, `_one_way_digest`)
- `nowing_backend/app/utils/oauth_security.py` (`TokenEncryption`, `Fernet` cipher)
- `nowing_backend/app/services/scraper_platform_account_service.py` (`ScraperPlatformAccountService`, `ScraperPlatformAccountRotator`, `RateLimit`)
- `nowing_backend/app/capabilities/batdongsan/scrape/executor.py` & `app/proprietary/platforms/batdongsan/parsers.py` (phone unmasking & detail resolution)
- `nowing_backend/app/lead_intelligence/signals/service.py` & `app/lead_intelligence/scoring/service.py` (existing lead intelligence architecture)
- `nowing_backend/app/services/billing_event_service.py` (`BillingEventService`, `_record_business_event`)
- `nowing_backend/app/services/export_service.py` (`ExportService`, OKF ZIP generation)
- `_bmad-output/implementation-artifacts/stories/21-3-enriched-contact-data.md` (Story 21.3 specification & tasks)
- `_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md` (Epic 21 architectural decisions AD-36 to AD-42)
