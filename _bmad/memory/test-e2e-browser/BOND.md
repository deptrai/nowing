# Bond

## Basics
- **Name:** Luisphan
- **Role:** Founder & Lead Developer of Nowing
- **Language:** Việt Nam

## Working Preferences
- Prioritize practical code examples and clear diagnostic steps over theory.
- Use Playwright MCP tools directly for real-time validation when feasible.
- Preserve test determinism and prevent test flakiness.

## Things to Remember
- Local development stack runs with Frontend on `:3000`, Backend on `:8000`, Zero Cache on `:4848`, Postgres on `:5434`, and Redis on `:6380`.
- Standard test user: `e2e-test@nowing.net` / `E2eTestPassword123!`.

## Things to Avoid
- Guessing selectors from source code when the live DOM snapshot can be inspected.
- Running flaky tests without proper auto-waiting or assertion bounds.
- Skipping pre-commit hooks (`--no-verify`).
