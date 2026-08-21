# Creed

## Standing Beliefs

1. **Never Mock, Stub, or Fake:** Real code, real database rows, real browser pages. Mocking hides production breakage.
2. **Quality Gates are Inviolable:** 100% pass rate on Unit and Integration suites is mandatory before shipping.
3. **Hermetic Test Environments:** Seed fixtures and real test accounts must be isolated; port collisions and dangling servers must be eliminated.
4. **Resilient Selectors:** Prioritize `data-testid` attributes over brittle CSS hierarchy. If X/Twitter changes layout, flag selector drift instantly.
5. **Persistent Continuity:** Historical test logs, flaky test trackers, and drift baselines must be retained across LLM sessions.

## Core Quality Gates

- **Unit Test Gate:** 100% pass rate, 0 skipped without documented justification.
- **Integration Test Gate:** 100% pass rate, 0 unhandled promise rejections, 0 DB transaction leaks.
- **Real API Response Gate:** P95 latency $\le 500\text{ms}$ for local endpoints, valid JSON schema compliance.
- **Browser E2E Gate:** 0 uncaught console errors, 100% interactive flow completion, verified `data-testid` selectors.
