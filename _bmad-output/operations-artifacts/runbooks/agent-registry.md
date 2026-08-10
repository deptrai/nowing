# Runbook: Agent Registry

## Purpose

Onboard and manage vertical-client agents (e.g. BDS AI) in the `AgentConfig`
registry.

## Prerequisites

- `AgentConfig` table exists and migrations are current.
- Target `client_id` is registered and active in `vertical_clients`.

## Seed a default agent

```bash
cd nowing_backend
ENVIRONMENT=development uv run --active python scripts/seed_agent_configs.py
```

Options:
- `--client-id` — defaults to `bdsai.vn`
- `--slug` — defaults to `bdsai-listing-assistant`
- `--name` — unique name, defaults to `bdsai-listing-assistant`
- `--display-name` — human-readable label, defaults to `BDS AI Listing Assistant`
- `--force` — skip `ENVIRONMENT` safety check

## Onboard a new vertical client

1. Ensure the `VerticalClient` row exists (or create via admin API / migration).
2. Run the seed script with the new `--client-id`.
3. Verify via admin API:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE_URL/api/v1/admin/agent-registry?client_id=newclient.vn"
```

## Rotate or update an agent

Use the admin API. `PATCH` with `is_active: false` to soft-retire, or
`DELETE` to soft-delete.

```bash
curl -X PATCH -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_name": "gpt-4o", "citations_enabled": true}' \
  "$BASE_URL/api/v1/admin/agent-registry/$AGENT_ID"
```

## Validation notes

- `client_id` and `slug` are stored as lowercase slugs.
- `enabled_tools` / `disabled_tools` must be known tool names in the
  main-agent / catalog union.
- `citations_enabled` defaults to `true` for new agents.
