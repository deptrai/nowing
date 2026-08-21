# Bond

## Basics
- **Name:** Luis
- **Role:** Founder & Lead Developer of XActions
- **Language:** Tiếng Việt

## Working Preferences
- Present test results as concise tables with clear Passed/Failed metrics and error snippets.
- Use Playwright MCP or Chrome MCP for real browser E2E workflows.
- Auto-manage server lifecycle (start Express API server and MCP daemon on test start, graceful cleanup after).
- Differentiate between code bugs, DOM selector updates, and rate-limit issues during test failures.

## Things to Remember
- Workspace: XActions project root (`/Users/luisphan/Documents/GitHub/XActions`).
- API Server: `api/server.js` (default port 3000).
- MCP Server: `src/mcp/server.js` (port 3001 daemon mode).
- Key env variables: `XACTIONS_SESSION_COOKIE`, `DATABASE_URL`, `JWT_SECRET`.
- Verified selector guide: `docs/agents/selectors.md`.

## Things to Avoid
- Writing unit tests with mocks or fakes.
- Leaving orphan server processes or background terminals running after tests.
- Ignoring browser console warnings or uncaught JavaScript exceptions.
