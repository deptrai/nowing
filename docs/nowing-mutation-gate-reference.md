# Mutation Gate Reference — Nowing

The authority document for the 6 anti-patterns that AI-generated tests miss, plus `cosmic-ray` setup and CI gate configuration. Loaded by `bmad-nowing-mutation-gate`.

## Why this exists

AI-generated tests often reach high line coverage while missing real bugs. Mutation score measures whether the tests actually protect the code, not whether they execute it. This doc defines the 6 anti-patterns, the Nowing P0 surfaces, the `cosmic-ray` setup, and the triage matrix.

## The 6 Anti-Patterns

|| # | Anti-Pattern | What it looks like | Mutant that survives | Real bug if lapsed |
||---|--------------|--------------------|-----------------------|---------------------|
|| 1 | **Mirror Test** | Test asserts exactly what code returns, derived from reading the implementation — not what the spec says it should return | `return` value mutated and test still passes; `dict`/`dataclass` field changed and test still passes | Wrong API response, wrong tool/agent contract, provider spec returns wrong shape |
|| 2 | **Over-Mocking** | External dependency (OpenRouter, LLM, Supabase, vector DB) is mocked — but the mock never throws, so the catch block is never exercised | `try/except` block mutated, error path not exercised | LLM 500, DB timeout, embedding service down → unhandled crash |
|| 3 | **Happy Path Only** | Only the success path tested. Boundary values (`>`, `>=`), null/empty input, concurrent double-submit never exercised | `>` → `>=`, `and` → `or`, `if x:` → `if True:` survives | Double credit charge, auth bypass, infinite cooldown, duplicate multi-agent turn |
|| 4 | **Arithmetic Not Asserted** | Calculation result not asserted with specific inputs — only "returns a number" | `+` → `-`, `* 60` → `/ 60`, cost formula survives | Wrong token cost, wrong quota, wrong credit balance |
|| 5 | **Error Msg Not Asserted** | Error thrown but message content not checked — only the error type | Exception class replaced and test still passes | User/agent can't diagnose failure |
|| 6 | **SQL Mock Not Executed** | DB query mocked — SQL template never actually runs against Postgres | Query condition mutated and mock test still passes | Prod query fails or returns wrong data |

## Nowing-specific P0 surfaces (where these patterns hurt most)

|| P0 surface | Anti-patterns that bite | Why |
||------------|-------------------------|-----|
|| **Token tracking / quota / credit** (`token_tracking_service`, `token_quota_service`, `web_crawl_credit_service`, `platform_scrape_credit_service`) | 3, 4, 6 | Double charge, wrong cost, negative balance, credit leak |
|| **Auth** (`app/auth/`, `auth_routes`, auth middleware) | 2, 3, 5 | Auth bypass, token leak, wrong error handling |
|| **Provider / model routing** (`provider_registry`, `model_resolver`, `openrouter_integration_service`) | 1, 3, 4 | Wrong provider selected, wrong model spec, wrong cost conversion |
|| **Pricing registration** (`pricing_registration`) | 3, 4 | Wrong `cost_per_token`, wrong fallback, revenue leak |
|| **LLM service / router** (`llm_service`, `llm_router_service`) | 2, 3, 5 | LLM failure not handled, wrong retry/boundary |
|| **Multi-agent chat** (`multi_agent_chat` orchestrator, subagent composition) | 1, 3 | Wrong agent composition, missing subagent, infinite loop |
|| **RAG / connector sync** (embedding, indexing, KB sync services) | 2, 3, 6 | Wrong retrieval, FK violation, sync failure silently ignored |

## cosmic-ray + pytest setup

Nowing uses Python 3.12 and `pytest`. `cosmic-ray` is the mutation testing tool.

### Install

```sh
cd nowing_backend
uv add --dev cosmic-ray
```

For CI runners or one-off server runs, install into the existing venv without touching `pyproject.toml`:

```sh
cd nowing_backend
uv pip install --python .venv/bin/python cosmic-ray
```

### Per-service config

Generate a TOML config per target service. The config **must live in `nowing_backend/`** and use a relative `module-path`; cosmic-ray mutates code on disk in the directory it runs from, and the test command must import the same file.

Example for `token_quota_service`:

```toml
# nowing_backend/mutation-nowing-token_quota-20260722T120000Z.toml
[cosmic-ray]
module-path = "app/services/token_quota_service.py"
timeout = 120.0
excluded-modules = ["tests", "migrations", "proprietary"]
test-command = "uv run pytest tests/unit/services/test_token_quota_service.py -m unit -x"

[cosmic-ray.distributor]
name = "local"
```

For services that span multiple files or a package:

```toml
module-path = "app/services/token_tracking_service"
```

or

```toml
module-path = "app/auth"
```

### Run manually

```sh
cd nowing_backend
uv run cosmic-ray baseline mutation-nowing-token_quota.toml
uv run cosmic-ray init mutation-nowing-token_quota.toml ../_bmad-output/test-artifacts/mutation-nowing-token_quota.sqlite
uv run cosmic-ray exec mutation-nowing-token_quota.toml ../_bmad-output/test-artifacts/mutation-nowing-token_quota.sqlite
uv run cosmic-ray dump ../_bmad-output/test-artifacts/mutation-nowing-token_quota.sqlite > ../_bmad-output/test-artifacts/mutation-nowing-token_quota.jsonl
```

Timeout: up to 30 minutes for large services. `exec` resumes from the session if interrupted.

### Server / CI runner

A reusable Python runner is provided at `scripts/mutation-gate.py`. It generates the TOML, runs `baseline/init/exec/dump`, parses the results, triages surviving mutants, and writes a JSON report.

```sh
python scripts/mutation-gate.py \
  --services token_quota_service,token_tracking_service,pricing_registration \
  --timeout 120.0 \
  --project-root .
```

Outputs:

- `_bmad-output/test-artifacts/mutation-nowing-{service}-{timestamp}.json` — per-service report
- `_bmad-output/test-artifacts/mutation-nowing-{service}-{timestamp}.sqlite` — cosmic-ray session
- `_bmad-output/test-artifacts/mutation-nowing-{service}-{timestamp}.jsonl` — `cosmic-ray dump` output
- `_bmad-output/test-artifacts/mutation-nowing-summary-latest.json` — combined summary

A GitHub Actions workflow is available at `.github/workflows/mutation-gate.yml`. It runs weekly on Sunday (or manually via `workflow_dispatch`) and parallelizes services into a matrix. Each job uploads its artifacts. The workflow fails if any service scores < 60% or has a P0 survived mutant.

### Machine-readable output

`cosmic-ray dump <session.sqlite>` emits one JSON array per line, where the array is `[mutation_meta, result]`. Merge them to get the full record. Key fields:

- `mutations[0].module_path` — source file
- `mutations[0].operator_name` — e.g. `core/ReplaceComparisonOperator_Gt_GtE`
- `mutations[0].start_pos` / `end_pos` — `[line, col]`
- `test_outcome` — `killed`, `survived`, `timeout`, `incompetent`
- `diff` — unified diff of the mutation

`cr-report <session.sqlite> --surviving-only --show-diff` is useful for human review; `dump` is for automated triage.

### Known gotchas (cosmic-ray + pytest)

1. **`module-path` must be relative and the config must run from `nowing_backend/`** — cosmic-ray mutates on disk; absolute or out-of-tree paths can cause the test command to import the unmutated original.
2. **`test-command` runs per mutant in a subprocess** — keep it fast: `-x` (exit on first failure) and `-m unit`.
3. **`timeout` must be higher than the normal test-suite runtime** because cosmic-ray uses it for the baseline run too. Start with `120.0` and raise for slow services.
4. **SQL / DB tests** — exclude integration tests unless `DATABASE_URL` points at a real Postgres. Pattern 6 mutants are best killed with real-DB integration tests.
5. **Session files are SQLite** — they can grow large; keep them in `_bmad-output/test-artifacts/` (already gitignored).

## CI gate

Use `.github/workflows/mutation-gate.yml` to run mutation gate on GitHub Actions. Trigger manually or on the weekly schedule. The workflow:

- syncs dependencies with `uv sync`,
- installs `cosmic-ray` into the project venv,
- runs `scripts/mutation-gate.py` for each configured service in parallel,
- uploads session, JSONL, and JSON reports as artifacts.

Promote to a required merge gate once mutation scores stabilize ≥80% across critical services and no P0 survived mutants remain.

## Triage matrix (used by bmad-nowing-mutation-gate)

|| Priority | Criteria | Action |
||----------|----------|--------|
|| **P0** | Pattern 3 (boundary/security) OR Pattern 4 (money/credit) OR Pattern 6 (SQL) on a critical service | **BLOCK** — test suite rejected, must add test |
|| **P1** | Pattern 1, 2, 5, OR Pattern 3/4 on non-critical service | **WARN** — log as tech debt, recommend fix |
|| **P2** | `StringLiteral` in logs, cosmetic | **ACCEPT** — note in report |

## Verdict thresholds

- **FAIL** if: `mutationScore < 60%` OR `p0SurvivedCount > 0`
- **PASS_WITH_WARNINGS** if: `60% <= mutationScore < 80%` AND `p0SurvivedCount === 0`
- **PASS** if: `mutationScore >= 80%` AND `p0SurvivedCount === 0`

A high mutation score with P0 survived is still FAIL — raw score is necessary but not sufficient.

## Equivalent mutant patterns (Nowing-specific)

These mutants survive because the code's observable behavior is identical with or without the mutation. They are NOT killable via any test. Documenting them prevents wasted effort.

### 1. Provider registry fallback string (`provider_registry.py`)

**Mutant:** provider label string `openai` → `openai_`.

**Why equivalent:** Tests that assert on `spec_for(...).provider` already use the same constant; the mutated label is still compared against itself.

**Where:** `app/services/provider_registry.py`

### 2. Log context dict (`token_tracking_service.py`)

**Mutant:** `{ run_id=..., model=... }` → `{}` in a `logger.info()` call.

**Why equivalent:** Log output is not asserted by behavior tests.

**Where:** `app/services/token_tracking_service.py`

### 3. Optional key access on a guaranteed non-None value (`model_resolver.py`)

**Mutant:** `spec.get("input_cost_per_token")` → `spec["input_cost_per_token"]` where the spec is validated at load time.

**Why equivalent:** The key is always present after `pricing_registration` validation.

**Where:** `app/services/model_resolver.py`

---

## Process: How to verify suspected equivalent mutants

1. Write a 5-line runtime script that exercises the mutant's code path with the mutated value.
2. Compare output — if identical to original, the mutant is equivalent.
3. Document in this file + the mutation gate JSON report.
4. Skip kill-test writing — do not waste effort on unkillable mutants.

Example verification script:
```python
from app.services.provider_registry import spec_for
s1 = spec_for("gpt-4o")
# simulate mutated label
s2 = {**s1, "provider_label": "openai_"}
print(s1["provider"] == s2["provider"])  # true → equivalent if tests only compare the same field
```
