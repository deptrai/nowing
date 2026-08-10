# Epic 18 Context: Vertical Client Platform (Public Agent-Chat)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Provide a public, PAT-authenticated agent-chat API so external vertical clients can run scoped chat agents against a Nowing workspace. The epic enforces hard tenant isolation (workspace + client), cost attribution, rate limiting, and an AgentConfig registry.

## Stories

- Story 18.1: Public Agent-Chat Endpoints
- Story 18.2: NewChatRequest Extension
- Story 18.3: Agent Registry
- Story 18.4: AgentConfig Prompt Injection
- Story 18.5: ResearchThread Auto-Linkage
- Story 18.6: Memory Tagging + RAG Filter
- Story 18.7: Cost Traceability
- Story 18.8: Rate Limiting + Tenant Isolation

## Requirements & Constraints

- Public endpoints under `/api/v1/workspaces/{workspace_id}/agent-chat/...` use PAT auth with workspace/client/agent scope enforcement.
- `client_id` is a hard isolation key orthogonal to `workspace_id`; tenant context must be set before any tenant-scoped DB query.
- PostgreSQL RLS policies enforce filtering by `workspace_id` and `client_id` on `memories`, `new_chat_threads`, `research_threads`, `token_usage`, `runs`.
- Rate limits apply per workspace and per client; 429 with `Retry-After` when exceeded.
- Audit log records actor, workspace, client, agent, route, status, run id; no message PII by default.
- `client_id` absent means internal/Nowing chat; RLS must treat NULL or empty consistently.

## Technical Decisions

- Tenant context is set via PostgreSQL GUCs (`app.workspace_id`, `app.current_client_id`, optional `app.current_agent_id`) using `SET LOCAL` per transaction/connection.
- Composite RLS policy: `workspace_id` matches AND (`client_id` matches current client OR current client unset and row `client_id` IS NULL).
- `ALTER TABLE ... FORCE ROW LEVEL SECURITY` ensures even table owner respects policies.
- Public agent-chat surface must reject session cookies; only PAT auth.
- Rate limiter uses Redis with keys `agent-chat:ws:{workspace_id}:client:{client_id}` and `agent-chat:ws:{workspace_id}`.
- AgentConfig is global (client-scoped, not workspace-scoped) so the same agent can run across workspaces.

## UX & Interaction Patterns

- No public-facing UI; behavior contract in `ux-contract-public-agent-chat-api.md` covers API error framing and rate-limit responses for client integrations.

## Cross-Story Dependencies

- 18.1 depends on AD-29 (public surface) and AD-13 (ResearchThread linkage).
- 18.2/18.3/18.4/18.5 depend on AD-30 (AgentConfig registry).
- 18.6/18.7/18.8 depend on AD-31 (vertical `client_id` tenancy).
- 18.8 must complete before Epic 18 can close; it requires all prior 18.x stories done.
