# UX Contract — Public Agent-Chat API

**Date:** 2026-08-09  
**Scope:** Public API surface for vertical clients (BDS AI first) to create chat threads and send messages via PAT, with tenant isolation, rate limits, and cost correlation.  
**Binds to:** FR-56 · NFR-MULTI-1 · AD-29 · AD-30 · AD-31  
**Document type:** *contract* — behavior the UI/API must support, not layout/color.

---

## 1. Problem

External vertical clients need to embed Nowing chat in their own application. The public API must be PAT-authenticated, workspace-scoped, client-isolated, rate-limited, and auditable. The client must receive correlation IDs and understand degradation/429/503 states.

## 2. Contract — Required UI/API States

### 2A. PAT Mint & Consent

| # | State | Required |
|---|-------|----------|
| A1 | **Workspace owner can create a PAT** for a specific vertical client (`client_id`) and agent (`agent_id`) with a fixed `scopes` list (`agent_chat:thread:create`, `agent_chat:message:create`, `agent_chat:thread:read`) | ✅ |
| A2 | **PAT plaintext shown once**; token kind `agent_chat` requires `workspace_id` + `client_id` + non-empty scopes | ✅ |
| A3 | **Vertical client consent notice** in mint UI: "This token grants `{client_id}` access to chat in workspace `{workspace_id}` with the selected agent. It does not grant access to other clients, workspaces, or admin functions." | ✅ |
| A4 | **PAT list** shows kind, client, agent, scopes, expiry, last used; allows revoke | ✅ |

### 2B. Thread Create

| # | State | Required |
|---|-------|----------|
| B1 | `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` with PAT returns `thread_id` and `research_thread_id` | ✅ |
| B2 | Request may include `agent_id`, `client_id`, `platform_metadata` | ✅ |
| B3 | Client-supplied `client_id`/`agent_id` are intersected with PAT scope; escalation is rejected with 403/400 (fail-closed) | ✅ |
| B4 | Malformed body or missing required fields → 422 with field-level errors | ✅ |
| B5 | Invalid or expired PAT, or non-member workspace → 401/403 | ✅ |

### 2C. Message Send

| # | State | Required |
|---|-------|----------|
| C1 | `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` with PAT processes the message and returns the assistant response | ✅ |
| C2 | Response headers include `X-Run-Id` and, on 429, `Retry-After` | ✅ |
| C3 | `external_metadata` (e.g., `listing_id`, `broker_id`, `user_id`) is stored for cost attribution but never used for authorization | ✅ |
| C4 | Chat times out or is unavailable → 503 + `Retry-After` or `partial` status frame, not 500 | ✅ |
| C5 | Invalid `agent_id` for the `client_id` → 404 with clear message | ✅ |

### 2D. Rate Limit & Degradation

| # | State | Required |
|---|-------|----------|
| D1 | Exceeding per-workspace or per-client rate limit → 429 with `Retry-After` header | ✅ |
| D2 | `Retry-After` value is a positive integer in seconds | ✅ |
| D3 | Degraded response (`degraded=true`, `reason`, `next_action`) is rendered as a structured payload, not a crash | ✅ |
| D4 | Public endpoints are not accessible with session cookie (PAT-only by default) | ✅ |

### 2E. Audit & Cost Correlation

| # | State | Required |
|---|-------|----------|
| E1 | Every public call is logged with actor, workspace, client, agent, route, status, run id; message bodies are not logged by default | ✅ |
| E2 | Client can use `X-Run-Id` to correlate with usage/cost reports | ✅ |
| E3 | Usage dashboard can filter public agent-chat calls by `client_id` and `external_metadata` (Story 18.7) | ✅ |

## 3. Technical UX Constraints

- **Auth:** Bearer PAT only (`AD-29`, `epic-18-pat-scope-rls-threat-model.md §2.6`).
- **Tenant isolation:** `client_id` is a hard isolation key; all data access is filtered by `client_id` (`AD-31`).
- **PAT scope:** Client-supplied IDs cannot escalate beyond the token's `workspace_id`/`client_id`/`agent_id`/`scopes` (`epic-18-pat-scope-rls-threat-model.md §2.7`).
- **Rate limit:** Redis-backed, per-workspace + per-client, with `429` + `Retry-After`.
- **No message body logging:** Default; PII redaction.
- **Public surface behind feature flag:** `AGENT_CHAT_PUBLIC_ENABLED` default `False` until security review (Story 18.1).

## 4. Source Citations

- `prd.md:429-440` — FR-56 public agent-chat API
- `ARCHITECTURE-SPINE.md:727-737` — AD-29 public surface
- `ARCHITECTURE-SPINE.md:739-748` — AD-30 AgentConfig registry
- `ARCHITECTURE-SPINE.md:750-764` — AD-31 vertical `client_id` tenancy
- `epic-18-pat-scope-rls-threat-model.md §2.5` — PAT scope object and mint UX
- `epic-18-pat-scope-rls-threat-model.md §2.6` — 9-step authorization algorithm
- `epic-18-pat-scope-rls-threat-model.md §2.7` — client-supplied IDs are never authoritative
- `epic-18-pat-scope-rls-threat-model.md §4.5` — HTTP/PAT matrix H1-H12
- `epic-18-pat-scope-rls-threat-model.md §5.6` — production enablement checklist

## 5. Traceability

- Blocks: Story 18.1, Story 18.2
- Related: `ux-contract-agent-registry.md` (admin agent config), `ux-contract-usage-dashboard.md` (cost correlation)
