# Memory

_Curated long-term knowledge for Nowing E2E Browser Testing. Empty at birth — grows through testing sessions._

## Known Environment Quirks & Fixes
- **Zero Cache 401:** If Zero query fails with `401 TransformFailed`, ensure `NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848` and `POSTGRES_PORT=5434` are properly aligned.
- **Local Ports:** Postgres runs on `5434` and Redis on `6380` to avoid conflicts with host instances.

## Flaky Selectors & DOM Patterns
_Recorded across sessions as UI components evolve._

## High-Risk User Journeys
- Chat turns with SSE streaming and tool invocation widgets.
- Connector authentication and indexing pipelines.
- Workspace creation and Zero-cache state synchronization.
