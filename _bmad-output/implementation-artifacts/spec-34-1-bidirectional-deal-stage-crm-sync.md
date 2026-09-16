# Story 34.1 Spec: Bi-Directional Deal Stage & Activity Synchronization for HubSpot/Salesforce

## Intent

As a Sales Representative, I want leads discovered in Nowing to sync bi-directionally with HubSpot and Salesforce deal pipelines, so that stage updates in the external CRM reflect back into Nowing and vice versa.

## Acceptance Criteria

- **Given** a deal stage change in HubSpot/Salesforce, **When** webhook arrives, **Then** Nowing updates the corresponding `Lead.status` and logs an activity timeline entry.
- **And** signature verification validates incoming webhooks against provider secret.

## Technical Design

### 1. Webhook Endpoints

- `POST /api/v1/crm/webhooks/hubspot`
- `POST /api/v1/crm/webhooks/salesforce`
- Public endpoints with provider-specific signature verification:
  - HubSpot: `X-HubSpot-Signature-v3` HMAC verification
  - Salesforce: Bearer token or HMAC signature

### 2. Stage Mapping

| External Stage (HubSpot/Salesforce) | Internal Lead Status |
|-------------------------------------|----------------------|
| appointmentscheduled / Prospecting   | contacted            |
| qualifiedtobuy / Qualification       | qualified            |
| presentationscheduled / Proposal     | qualified            |
| closedwon / Closed Won               | converted            |
| closedlost / Closed Lost             | lost                 |

### 3. Service Implementation

- `app/services/crm_webhook_service.py`:
  - Verify webhook signature
  - Extract external deal ID, stage name, contact email/phone
  - Find matching `Lead` by external CRM reference or verified contact email
  - Update `Lead.status`
  - Record entry in `CrmSyncLog`
  - Emit real-time update / invalidate lead cache

### 4. Safety Constraints

- Idempotent webhook processing (dedup by event ID / timestamp)
- Fail-soft: unknown stage logs warning and leaves lead status unchanged
- Signature verification required in production mode
