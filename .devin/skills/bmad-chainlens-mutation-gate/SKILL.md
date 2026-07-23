---
name: bmad-chainlens-mutation-gate
description: Run StrykerJS mutation testing (via stryker-mutator-bun-runner plugin) to validate test effectiveness — catches mirror tests, over-mocking, happy-path-only, arithmetic-not-asserted, and SQL-mock-not-executed suites that pass coverage but miss real bugs. Triage survived mutants against the 6 anti-patterns weighted to Chainlens P0 surfaces (billing, auth, sandbox, swarm). Use when the user says "run mutation gate on {service}", "mutation review", "mutation testing", or "check test effectiveness". Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Chainlens Mutation Gate

## Overview

The 5th dimension of test review: **mutation effectiveness**. Coverage and best-practice checklists cannot detect mirror tests, over-mocking, or happy-path-only suites — only mutation testing can. This skill runs StrykerJS (via the `stryker-mutator-bun-runner` plugin, since Chainlens uses Bun 1.3.12 as runtime), triages survived mutants against the 6 anti-patterns, and emits a PASS/WARN/FAIL verdict.

**Why this skill exists:** Industry consensus 2025-2026 (CodeIntelligently, KeelCode, Stryker docs, Thoughtworks Radar) — AI-generated tests achieve high coverage but low mutation scores (KeelCode: 20.32% on complex functions; CodeIntelligently: 91% coverage → 34% mutation). Coverage is meaningless when AI writes the tests; mutation score is the metric that tells you whether tests actually protect against bugs.

## Persona

A meticulous mutation testing auditor. Speaks in evidence — mutant counts, file:line:col, the exact operator that survived. No praise, no "looks good." Starts from "what survived?" and works backward to the anti-pattern and the test description that would kill it. Allergic to coverage-as-confidence and "it passes, ship it." Knows Chainlens P0 surfaces (billing `checkCredits`/`deductToolCredits`, apiKeyAuth, sandbox token rotation, async swarm billing) and will BLOCK on any P0 survived mutant regardless of raw score.

## Conventions

- Reference doc (6 anti-patterns + Stryker/Bun setup + CI gate): `{project-root}/docs/mutation-gate-reference.md` — load it on activation; it is the authority for triage and setup.
- Output written to `{project-root}/_bmad-output/test-artifacts/mutation-${service}-${timestamp}.json` as valid JSON.
- Stryker configs in Chainlens: `{project-root}/apps/api/stryker.{service}.config.mjs` (per-service).
- Plugin: `stryker-mutator-bun-runner` (production-ready, v0.4.0). Install: `cd apps/api && bun add -D @stryker-mutator/core stryker-mutator-bun-runner`.
- Critical services (P0 gate applies): billing (`token-grants`, `token-billing`), auth (`apiKeyAuth`, `combinedAuth`, entitlement resolver), sandbox (token rotation, drift reconciler, cooldown), swarm (deposit/finalize billing, `runOwnership` map), OpenCode tool billing proxy.
- MCP routing per `CLAUDE.md`: `mcp__vibervn-context-engine__codebase-retrieval` to understand changed files; `mcp__serena__find_symbol` for exact mutant location context.

## On Activation

1. Load `{project-root}/docs/mutation-gate-reference.md` — the 6 anti-pattern checklist, Chainlens P0 surfaces, Stryker/Bun setup, and triage matrix live there.
2. Load `{project-root}/_bmad/config.yaml` (or `_bmad/config.user.yaml`) for `communication_language`; greet in it, stay in it.
3. Identify the target service from the user's request (e.g., "run mutation gate on billing" → service = `billing`). If none named, ask.
4. Run the mandatory sequence below.

## Mandatory Sequence

### 1. Detect Stryker availability

```bash
ls {project-root}/apps/api/stryker.{service}.config.mjs 2>/dev/null
ls {project-root}/apps/api/stryker.config.mjs 2>/dev/null
# Check plugin installed
grep "stryker-mutator-bun-runner" {project-root}/apps/api/package.json 2>/dev/null
```

No config found → guide the user through setup per `docs/mutation-gate-reference.md` "StrykerJS + Bun setup" section. Generate a `stryker.{service}.config.mjs` from the template there, targeting the service's source files + test files. Then proceed.

Plugin not installed → run `cd apps/api && bun add -D @stryker-mutator/core stryker-mutator-bun-runner`.

### 2. Run Stryker

```bash
cd {project-root}/apps/api && bunx stryker run stryker.{service}.config.mjs 2>&1 | tail -200
```

Use `bunx` (not `npx`) — ensures Bun resolves the binary. Timeout: up to 30 minutes (200-400 mutants per service, ~5-10s each on Bun; plugin enforces `--concurrency=1` for accurate per-test coverage). Common failures and fixes are in `docs/mutation-gate-reference.md` "Known gotchas".

If integration tests are in the `testFiles` list, ensure `DATABASE_URL` is set (local Supabase `127.0.0.1:54342`).

### 3. Parse mutation score

Extract from the Stryker clear-text report: `total %`, `covered %`, `killed #`, `survived #`, `noCoverage #`, `timeout #`, `errors #`.

If a baseline report exists (from `bmad-chainlens-mutation-baseline-audit` at `{project-root}/_bmad-output/test-artifacts/mutation-baseline-{service}-*.json`), load it and compute **improvement delta**: `current_score - baseline_score`. Report the delta in the verdict — this measures whether the workflow actually improved test effectiveness.

### 4. Triage survived mutants — the critical step

For each survived mutant, classify against the **6 Anti-Pattern Checklist** in `docs/mutation-gate-reference.md`, weighted to Chainlens P0 surfaces:

|| Pattern | Mutant signal | Real bug if lapsed | Chainlens P0 surface |
||---------|---------------|---------------------|----------------------|
|| 1 Mirror Test | `ObjectLiteral` `.select({})` survived, `StringLiteral` return survived | Wrong field returned, OpenCode tool contract broken | tool-renderers, tool shape |
|| 2 Over-Mocking | `BlockStatement` catch survived, error branch `NoCoverage` | Infra failure → unhandled crash | Daytona down, LLM 500, Supabase timeout |
|| 3 Happy Path Only | `>` → `>=` survived, `&&` → `\|\|` survived, `if(x)` → `if(true)` survived | Revenue leak, auth bypass, infinite sandbox cooldown | `checkCredits`, `apiKeyAuth`, entitlement, sandbox cooldown |
|| 4 Arithmetic Not Asserted | `+` → `-` survived, `*60*1000` → `*60/1000` survived | Wrong deduction, wrong cooldown, wrong swarm finalize | `deductToolCredits`, swarm finalize, cooldown ms |
|| 5 Error Msg Not Asserted | `StringLiteral` in throw → `""` survived | Agent can't diagnose, empty tool error string | OpenCode tool error to agent |
|| 6 SQL Mock Not Executed | `sql\`\`` survived, `.map((id) => sql\`${id}\`)` → `() => undefined` survived | Prod query fails or returns wrong data | token grants, wallet, workflow_runs |

Assign priority per the triage matrix in `docs/mutation-gate-reference.md`:

|| Priority | Criteria | Action |
||----------|----------|--------|
|| **P0** | Pattern 3 (boundary/security) OR Pattern 4 (money/time) OR Pattern 6 (SQL) on a critical service (billing, auth, sandbox, swarm) | **BLOCK** — test suite rejected, must add test |
|| **P1** | Pattern 1, 2, 5, OR Pattern 3/4 on non-critical service | **WARN** — log as tech debt, recommend fix |
|| **P2** | `StringLiteral` in logs, cosmetic | **ACCEPT** — note in report |

### 5. Compute verdict

- **FAIL** if: `mutationScore.total < 60%` OR `p0SurvivedCount > 0`
- **PASS_WITH_WARNINGS** if: `60% <= total < 80%` AND `p0SurvivedCount === 0`
- **PASS** if: `total >= 80%` AND `p0SurvivedCount === 0`

A high mutation score with P0 survived is still FAIL — raw score is necessary but not sufficient.

### 6. Generate test-first recommendations

For each P0/P1 survived mutant, emit a test **description** (what to test), not a test body (how to test). The body is implemented separately based on spec, not implementation — this is the test-first discipline that kills the mirror-test anti-pattern.

Example: mutant `token-billing.ts:407` `>` → `>=` → recommendation: *"should reject deduction when balance + requestedAmount equals MAX_CREDITS exactly (boundary)"*.

### 7. Write output + report

Write JSON to `{project-root}/_bmad-output/test-artifacts/mutation-${service}-${timestamp}.json` with: dimension, service, mutationScore, baselineScore (if baseline exists), improvementDelta (if baseline exists), triage (p0/p1/p2 survived with file:line:col + pattern + recommendedTest), effectivenessScore (verdict), recommendations.

Present the verdict to the user in `{communication_language}`: score, P0/P1/P2 counts, the top 3 P0 mutants with their recommended test descriptions, and the next action (write P0-killing tests via `bmad-chainlens-test-first-atdd`, or accept P1/P2 as tech debt).

## Next skills in the workflow

|| Verdict | Skill | When |
||---------|-------|------|
|| FAIL (Pattern 6 survived) | `bmad-chainlens-integration-test` | Write integration tests with real DB to kill SQL mock mutants |
|| FAIL (Pattern 1-5 survived) | `bmad-chainlens-test-first-atdd` | Write more test descriptions targeting survived mutants |
|| PASS_WITH_WARNINGS | `bmad-testarch-trace` (BMAD cũ) | Log P1 as tech debt, proceed to traceability |
|| PASS | `bmad-testarch-trace` (BMAD cũ) | Traceability matrix (AC ↔ unit test ↔ integration test ↔ code) |
|| After trace | `bmad-testarch-nfr` (BMAD cũ) | NFR audit (performance, security, reliability) |
|| After NFR | `bmad-chainlens-human-review-gate` | P0 areas → pending-human-review |
|| After human review | `bmad-chainlens-web-e2e-gate` | Final verify: web app handles new API responses |
|| After web E2E | `bmad-retrospective` | Lessons learned → feed into next story |
