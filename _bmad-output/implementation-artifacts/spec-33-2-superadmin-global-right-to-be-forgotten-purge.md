# Story 33.2 Spec: Superadmin Cross-Workspace Global Right-to-be-Forgotten (DNC) Purge Engine

## Intent

As a Compliance Administrator, I want a unified API to purge an individual's phone/email across all workspaces simultaneously, so that Decree 13 and GDPR deletion requests are fully honored enterprise-wide.

## Acceptance Criteria

- **Given** a verified opt-out request, **When** executed by Superadmin, **Then** all `VerifiedContact`, `Lead`, and `SocialPost` records containing the phone/email hash across all workspaces are purged and refunded.
- **And** the phone/email HMAC is permanently appended to `global_dnc_records`.
- **And** all affected workspace DNC caches are invalidated.

## Technical Design

### 1. API Endpoint

- `POST /api/v1/admin/compliance/purge`
- Requires Superadmin role (or `FULL_ACCESS` / `COMPLIANCE_ADMIN`)
- Request body:
  ```json
  {
    "record_type": "phone" | "email",
    "value": "+84908123456" | "user@example.com",
    "reason": "GDPR / Decree 13 Right-to-be-Forgotten request",
    "ticket_ref": "DPO-2026-09-001"
  }
  ```
- Response:
  ```json
  {
    "status": "purged",
    "record_type": "phone",
    "value_hmac": "sha256_hash",
    "purged_counts": {
      "verified_contacts": 5,
      "leads": 3,
      "social_posts": 0
    },
    "workspaces_affected": [1, 2, 5],
    "credits_refunded": 250000,
    "global_dnc_id": "uuid"
  }
  ```

### 2. Service Implementation

- `app/services/compliance_purge_service.py`:
  - Normalize value to canonical format (E.164 for phone, lowercase for email)
  - Compute HMAC using `hash_phone_hmac` / `hash_domain_hmac`
  - Find all `VerifiedContact` matching `phone_hmac` or `email_hmac`
  - Delete matching `VerifiedContact` records
  - Find all `Lead` records with matching phone/email
  - Find and purge `SocialPost` records if applicable
  - Insert into `GlobalDncRecord` (if not already present)
  - Invalidate DNC cache for all affected workspaces
  - Log audit event in `admin_audit_logs`

### 3. Safety Constraints

- Immutable audit trail
- Hard purge (no soft-delete) for GDPR compliance
- Atomic transaction (rollback on failure)
- Re-index / cache invalidation across all affected tenants
