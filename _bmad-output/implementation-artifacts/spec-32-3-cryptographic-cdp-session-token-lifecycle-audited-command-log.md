# Story 32.3 Spec: Cryptographic CDP Session Token Lifecycle & Audited Command Log

## Intent

As a Security Auditor, I want all browser operator CDP commands authenticated via cryptographic session tokens and persisted to an audit log, so that automation runs can be traced for security compliance.

## Acceptance Criteria

- **Given** an incoming CDP command from an external agent, **When** verified against the session secret, **Then** the execution metadata is logged to `browser_operator_audit_events`.

## Technical Design

### 1. Session Token Generation & Validation

- **Token format**: `cdp_sess_{mission_id}_{timestamp}_{hmac_signature}`
- **HMAC-SHA256** signed with `CDP_SESSION_SECRET` env var
- **TTL**: 5 minutes (same as mission TTL)
- **Validation**: Backend verifies signature and expiry before accepting CDP result

### 2. Audit Log Table

```sql
CREATE TABLE browser_operator_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id UUID NOT NULL REFERENCES dsh_missions(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL,
    user_id UUID NOT NULL,
    command_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL,
    target_url TEXT,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    challenge VARCHAR(64),
    requires_human BOOLEAN DEFAULT FALSE,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_browser_audit_mission ON browser_operator_audit_events(mission_id);
CREATE INDEX idx_browser_audit_workspace ON browser_operator_audit_events(workspace_id);
CREATE INDEX idx_browser_audit_created ON browser_operator_audit_events(created_at);
```

### 3. Backend Changes

- `app/models/browser_operator_audit.py`: New SQLAlchemy model
- `app/services/browser_operator_audit_service.py`: Audit logging service
- `app/routes/dsh_routes.py`: 
  - Generate session token on mission creation
  - Validate token on `/dsh/cdp/result`
  - Log audit events
- `app/tasks/dsh_worker_browser_operator.py`: Include session token in commands

### 4. Extension Changes

- `cdp-bridge.ts`: 
  - Store session token from SSE handshake
  - Include token in result POST body
  - Reject commands without valid session context

### 5. Security Constraints

- Token bound to mission_id + user_id
- Audit log immutable (INSERT only, no UPDATE/DELETE)
- PII redaction on target_url before logging
- Failed auth attempts logged as audit events

## I/O Matrix

| Input | Validation | Output |
|-------|-----------|--------|
| CDP command via SSE | Session token + mission_id | Audit event row |
| CDP result POST | Token signature + expiry | 200 OK + audit logged |
| Invalid token | Signature mismatch | 401 Unauthorized + audit attempt logged |
| Expired token | Timestamp check | 401 Unauthorized + audit attempt logged |

## Edge Cases

- Token replay attack → timestamp validation + single-use enforcement
- Mission abort mid-command → audit event still logged with error
- Redis unavailable → fail-closed (no command execution without audit)
- Extension reconnect → new session token issued on SSE handshake
