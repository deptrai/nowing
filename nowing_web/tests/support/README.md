# Test Support

Shared testing support code for the Playwright E2E suite.

## Structure

```
tests/support/
├── fixtures/          # Re-exported Playwright fixtures + data factories
│   └── factories/     # @faker-js/faker based data factories
├── helpers/           # Optional additional helper modules
└── page-objects/      # Page Object Models (POMs) when UI-only tests grow
```

## Factories

Factories live in `tests/support/fixtures/factories/` and use `@faker-js/faker` to create realistic, deterministic test data. They follow the pattern:

- `Factory.create(overrides)` — deterministic defaults.
- `Factory.random()` — random but realistic data.
- `Factory.build(...)` — create remote entities via API.
- `Factory.cleanup(entity)` — remove from tracked list.
- `Factory.cleanupAll(...)` — batch cleanup remote entities.

Current factories:

- `UserFactory` — E2E test credentials.
- `WorkspaceFactory` — isolated workspace creation and cleanup.

## Migration Notes

The original `tests/fixtures/` and `tests/helpers/` directories are still the
active source of truth for fixtures and helpers. `tests/support/` is the new
home for factory-based patterns and will gradually absorb shared helpers and
page objects as the test suite grows.
