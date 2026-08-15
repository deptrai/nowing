# Memory

_Curated long-term knowledge for Nowing E2E Browser Testing._

## Known Environment Quirks & Fixes
- **Zero Cache 401:** If Zero query fails with `401 TransformFailed`, ensure `NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848` and `POSTGRES_PORT=5434` are properly aligned.
- **Local Ports:** Postgres runs on `5434` and Redis on `6380` to avoid conflicts with host instances.

## Flaky Selectors & DOM Patterns
- **Header Auth Controls:** The `Sign In` link in the main navigation uses `hidden md:block`. When testing with browser MCP tools, always ensure viewport is set to desktop size (e.g. 1440x900 via `browser_resize`) or click the `Get Started` hero link if testing on small viewports.
- **Chat Prompt & Turn Trace:** Chat prompt input is accessible via `getByRole('textbox')`. Tool trace details and execution steps expand via `getByRole('button', { name: 'Reviewed' })` or `getByRole('button', { name: 'Open agent action log' })`. Modals can be safely dismissed with `keyboard.press('Escape')`.
- **Suggested Action Pills (Story 21.11):** Suggested execution pills mount directly below assistant messages via container `[data-testid='suggested-action-pills']` and buttons `button[data-action-type]`. Supports 1-click prompt dispatch and keyboard shortcuts `Alt+Digit1`, `Alt+Digit2`, `Alt+Digit3` when composer input is unfocused. Emits window custom event `nowing:action-dispatched` triggering `.cell-pulse` highlight.

## High-Risk User Journeys
- Chat turns with SSE streaming, tool invocation widgets, and contextual suggested action pills (`data-suggested-actions`).
- Connector authentication and indexing pipelines.
- Workspace creation and Zero-cache state synchronization.
- Recruitment & B2B Lead Intelligence (Story 12.10 & 21.9): Public guest scraping and PostgreSQL idempotent ingestion (`LinkedinJob`, `LinkedinCompany`).
- Public Procurement & Tender Intelligence (Story 16.5): National tender search (`procurement.search`), E-HSMT dossier S3 streaming and qualification summary (`procurement.summarize`).


