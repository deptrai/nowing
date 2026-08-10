# Nowing Backend

FastAPI backend for Nowing.

## Local development

```bash
cd nowing_backend
uv sync
ENVIRONMENT=development uv run alembic upgrade head
ENVIRONMENT=development uv run python -m app
```

## Tests

```bash
# Unit tests (no DB required)
uv run pytest tests/unit -q

# Integration tests (requires Postgres + Redis)
docker compose -f docker/docker-compose.deps-only.yml up -d db redis
uv run alembic upgrade head
uv run pytest tests/integration -q
```

## Agent Registry

The Agent Registry stores `AgentConfig` rows keyed by `(client_id, slug)`.
Each row controls the system prompt, model, citations, enabled/disabled
main-agent tools, and active state for a vertical-specific chat agent.

### Seed the default BDS AI agent

```bash
ENVIRONMENT=development uv run --active python scripts/seed_agent_configs.py
```

`--force` bypasses the dev-environment safety check:

```bash
ENVIRONMENT=production uv run --active python scripts/seed_agent_configs.py --force
```

### Admin API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/v1/admin/agent-registry` | List agents; `?client_id=` filter |
| POST   | `/api/v1/admin/agent-registry` | Create an agent |
| GET    | `/api/v1/admin/agent-registry/{id}` | Get one agent |
| PATCH  | `/api/v1/admin/agent-registry/{id}` | Update an agent |
| DELETE | `/api/v1/admin/agent-registry/{id}` | Soft-deactivate an agent |

The `client_id` must match an existing active `VerticalClient` row before an
`AgentConfig` can be created.
