# Memory

_Curated long-term knowledge for Nowing E2E Browser Testing._

## Known Environment Quirks & Fixes
- **Zero Cache 401:** If Zero query fails with `401 TransformFailed`, ensure `NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848` and `POSTGRES_PORT=5434` are properly aligned.
- **Local Ports:** Postgres runs on `5434` and Redis on `6380` to avoid conflicts with host instances.

## Flaky Selectors & DOM Patterns
- **Header Auth Controls:** The `Sign In` link in the main navigation uses `hidden md:block`. When testing with browser MCP tools, always ensure viewport is set to desktop size (e.g. 1440x900 via `browser_resize`) or click the `Get Started` hero link if testing on small viewports.

## High-Risk User Journeys
- Chat turns with SSE streaming and tool invocation widgets.
- Connector authentication and indexing pipelines.
- Workspace creation and Zero-cache state synchronization.
