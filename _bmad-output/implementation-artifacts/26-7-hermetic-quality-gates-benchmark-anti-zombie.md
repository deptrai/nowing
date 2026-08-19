---
story_key: "26-7"
epic: "epic-26"
story: "26.7"
title: "Hermetic Quality Gates, Benchmark Suite & Anti-Zombie Chaos Testing"
status: "done"
baseline_commit: "f53475690"
---

# Story 26.7: Hermetic Quality Gates, Benchmark Suite & Anti-Zombie Chaos Testing

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Test surface for the `lead_extraction/regression` benchmark.**
   - `nowing_evals` has no existing suite that returns F1 Phone / Hallucination / MST Modulo 11.
   - The backend does **not** expose an HTTP endpoint that takes raw source text and returns extracted phones / tax IDs. `POST /workspaces/{workspace_id}/leads/batch-ingest` only stores pre-extracted fields (`phone`, `tax_id`) and `POST /workspaces/{workspace_id}/leads/{lead_id}/resolve-phone` only resolves an existing lead's phone (it may also call paid external APIs in Tier 2/3).
   - **Decision:** Add a small, read-only, test-only endpoint `POST /api/v1/test/extract-entities` (or `POST /api/v1/workspaces/{workspace_id}/leads/extract-entities` with `LEADS_READ`) that runs local extraction on `source_text` and returns extracted phones, tax IDs, and a company-name candidate. It does **not** persist, debit credits, or call external APIs.
   - `nowing_evals` `lead_extraction/regression` calls this endpoint in `live` mode and loads Golden Cassettes in `replay` mode. The cassettes are recorded `.sse.jsonl` artifacts (one JSON object per file, despite the name) that store the endpoint response.

2. **Hermetic transport — cassettes, not FastMCP, for this suite.**
   - AD-107 says CI/CD evals must use Golden Streaming Cassettes and in-memory Fake FastMCP transport.
   - This `nowing_evals` suite is over HTTP/cassettes because the extraction is exposed as a REST test endpoint. Fake FastMCP transport is implemented in the **backend** hermetic integration tests for `dsh_worker` / `nowing_mcp` (Task 7.2) and is reused from `tests/e2e/fakes/mcp_runtime.py`.

3. **Cassette format.**
   - A cassette is `nowing_evals/data/lead_extraction/regression/cassettes/{case_id}.sse.jsonl` with one JSON line:
     ```json
     {"type":"rest","status":200,"headers":{},"body":{"phones":["0908123456"],"tax_ids":["0123456789"],"tax_ids_valid":[true],"company_name":"Công ty TNHH ABC"}}
     ```
   - The `ReplayClient` in `nowing_evals` returns the cassette `body` instead of calling the test endpoint.
   - Cassettes must be sanitized (no real PII) before committing. Whitelist them in `nowing_evals/data/.gitignore`.

4. **Gate evaluation is benchmark-local, not through `core/gate.py`.**
   - `nowing_evals/src/nowing_evals/core/gate.py:42-63` has `GateThresholds` with `extra="forbid"` and fields only for `memory/recall` (`recall_at_5_min`, `mrr_min`, etc.). A `lead_extraction/gate.yaml` with `min_f1_phone` will be rejected.
   - **Decision:** Follow the `chat/regression` and `research/chainlens_latency` pattern: implement `_evaluate_lead_extraction_gate(metrics)` in the benchmark `runner.py`, load the benchmark's own `gate.yaml`, and raise `RuntimeError` if thresholds are missed. Do **not** call `core/gate.py` `evaluate_gate` and do **not** run `python -m nowing_evals gate --suite lead_extraction --benchmark regression`.

5. **Auth in `nowing_evals`.**
   - `Benchmark` defaults to `requires_auth_for_ingest = True` and `requires_auth_for_run = True` (`core/registry.py:174-175`). `chat/regression` sets `requires_auth_for_ingest = False` because `ingest` only writes JSONL.
   - **Decision:** Set `requires_auth_for_ingest = False`. Set `requires_auth_for_run = True` because `live` mode calls the test endpoint. In `replay` mode, set `NOWING_JWT=dummy` so `acquire_token` returns without a network call (`core/auth.py:78-83`).

6. **MST Modulo 11 validator.**
   - No `is_valid_vietnam_tax_code` exists in the backend.
   - **Decision:** Implement the validator in `nowing_backend/app/proprietary/platforms/xactions/tax_code.py` so the test endpoint can return `tax_ids_valid`. The `nowing_evals` benchmark does **not** re-implement or import the validator; it computes `mst_modulo11_accuracy` directly from the `tax_ids_valid` field in the endpoint/cassette response.

7. **Phone extraction already has unit tests; do not duplicate.**
   - `tests/unit/proprietary/platforms/xactions/test_phone_extractor.py` already covers 12+ phone variants, ReDoS, and entity extraction.
   - **Decision:** Extend the existing file with a `TestPhoneExtractionHermetic` class and a tax-code validator test. Do **not** create a new `test_phone_extractor_hermetic.py`.

8. **Container lifecycle (AD-108) is already implemented.**
   - `nowing_backend/Dockerfile:33` installs `tini`; line 225 sets it as PID 1. `docker/postgresql.conf:12-13` sets WAL limits.
   - **Decision:** 26.7 does **not** re-implement AD-108; it adds verification: a 72-hour stress harness plus a `ps aux` zombie monitor, and a short 5-minute CI version.

---

## Story

As a platform engineer,
I want `nowing_evals` regression benchmarks to run in hermetic `replay` mode at $0 external API cost and the scraping containers to survive a 72-hour stress test with zero defunct/zombie processes,
so that Epic 26 ships with automated quality gates (F1 Phone ≥ 98.0%, Hallucination ≤ 0.1%, MST Modulo 11 ≥ 99.5%) and production-grade container lifecycle stability.

---

## Acceptance Criteria

### AC-1: `nowing_evals` regression benchmark in `--mode=replay` (AD-107)

- **Given** `nowing_evals` executing the regression benchmark,
- **When** run with `--mode=replay`,
- **Then**:
  1. The benchmark runs with **$0 external token/API cost** (no OpenAI, no ChainLens, no masothue, no scraper browser calls).
  2. It loads **Golden Cassettes (`.sse.jsonl`)** from `nowing_evals/data/lead_extraction/regression/cassettes/`.
  3. It enforces the three quality gates: **F1 Phone ≥ 0.98**, **Hallucination ≤ 0.001**, **MST Modulo 11 ≥ 0.995**.
  4. A failing gate exits non-zero and emits a structured `run_artifact.json` with `passed: false` and `reasons`.

### AC-2: 72-hour continuous scraping stress test with 0 zombie Chromium processes (AD-108)

- **Given** a scraping workload running continuously for 72 hours on Dokploy,
- **When** monitored via `ps aux`,
- **Then**:
  1. The container has **exactly 0 defunct (`<defunct>`) and 0 zombie (`Z` state) Chromium/browser processes**.
  2. The container uses `tini` as PID 1.
  3. Every synchronous tool call / REST round-trip / `XREADGROUP` block enforces a **60s hard timeout** (raises/terminates, never hangs).
  4. PostgreSQL replica slots do not exhaust disk: `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB` remain in effect.

---

## Tasks / Subtasks

- [x] **Task 1: Add `--mode` and replay infrastructure to `nowing_evals` (AC-1)**
  - [x] Subtask 1.1: Add `--mode {live,replay}` to the global `nowing_evals run` parser in `nowing_evals/core/cli.py` and forward it to `RunContext`.
  - [x] Subtask 1.2: Create `nowing_evals/core/cassette.py` with a `Cassette` class that:
    - Loads `*.sse.jsonl` and `*.jsonl` cassette files.
    - For REST: returns `status`, `headers`, `body`.
    - Fails closed if a requested cassette is missing.
  - [x] Subtask 1.3: Add `mode: Literal["live", "replay"]` to `RunContext` (`nowing_evals/core/registry.py`) and a `replay_artifacts_dir()` helper.
  - [x] Subtask 1.4: Implement a `ReplayClient` that, in `replay` mode, returns cassette payloads instead of making HTTP calls.
  - [x] Subtask 1.5: Update the `Benchmark` protocol docstring and ensure any benchmark that does not implement replay rejects `mode=replay` with a clear `RuntimeError`.

- [x] **Task 2: Backend extraction test endpoint (AC-1)**
  - [x] Subtask 2.1: Create `nowing_backend/app/proprietary/platforms/xactions/tax_code.py` with:
    - `extract_tax_ids(text: str) -> list[str]` — returns candidate 10/13 digit tax IDs found in the text.
    - `is_valid_vietnam_tax_code(tax_id: str) -> bool` — implements the Vietnamese MST Modulo-11 check (10/13 digit variants). Validate against 100 known-good tax codes from masothue fixtures before ratifying.
  - [x] Subtask 2.2: Create `nowing_backend/app/services/lead_extraction_service.py` `LeadExtractionService.extract_from_text(text)`:
    - Uses `app.proprietary.platforms.xactions.phone_extractor.SocialEntityExtractor` for phones and company-name heuristics.
    - Uses `app.proprietary.platforms.xactions.tax_code` for tax IDs and validation.
    - Does **not** call external APIs, write to DB, or debit credits.
    - Returns `ExtractedEntities(phones, tax_ids, company_name, tax_ids_valid)`.
  - [x] Subtask 2.3: Create schemas in `nowing_backend/app/schemas/extract_entities.py`: `ExtractEntitiesRequest` (`source_text: str`, `source_url: str | None`) and `ExtractEntitiesResponse` (`phones: list[str]`, `tax_ids: list[str]`, `tax_ids_valid: list[bool]`, `company_name: str | None`).
  - [x] Subtask 2.4: Create a test-only route `POST /api/v1/test/extract-entities` in `nowing_backend/app/routes/extract_entities_routes.py`. Guard it with `X-Internal-Test` header or restrict to an internal API key so it is not exposed in production. Wire the router in `nowing_backend/app/routes/__init__.py`.

- [x] **Task 3: Create the `lead_extraction/regression` benchmark suite (AC-1)**
  - [x] Subtask 3.1: Create package `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/` with `__init__.py`, `runner.py`, `metrics.py`, `extractor_client.py`, and `gate.yaml`.
  - [x] Subtask 3.2: Define the dataset schema (JSONL) and a default sample dataset:
    ```jsonl
    {"case_id":"lead-001","source_markdown":"...","expected_phones":["0908123456"],"expected_tax_ids":["0123456789"],"expected_company_name":"Công ty TNHH ABC","tags":["bds"],"allow_hallucinated_phones":false}
    ```
  - [x] Subtask 3.3: Implement `ingest()` that writes `cases.jsonl` to `nowing_evals/data/lead_extraction/regression/cases.jsonl`. Set `requires_auth_for_ingest = False`.
  - [x] Subtask 3.4: Implement `extractor_client.py`:
    - `live`: `POST /api/v1/test/extract-entities` with `source_markdown`.
    - `replay`: load the cassette for `case_id` from `data/lead_extraction/regression/cassettes/`.
  - [x] Subtask 3.5: Implement `metrics.py`:
    - `f1_phone(predicted: set[str], expected: set[str])` — **entity-level** F1 over normalized 10-digit Vietnamese phone sets.
    - `hallucination_rate(predicted_phones: set[str], predicted_tax_ids: set[str], source_text: str, expected_phones: set[str], expected_tax_ids: set[str])` — fraction of predictions not present in `source_text` and not in the expected set.
    - `mst_modulo11_accuracy(tax_ids_valid: list[bool])` — fraction of returned tax IDs where `tax_ids_valid[i] is True` (computed by the backend endpoint; the benchmark does not re-implement the validator).
    - `normalize_vn_phone(phone: str) -> str | None` — use the same normalization as `phone_extractor.py` (10-digit, legacy 11-digit conversion, strip `+84`/`84`).
  - [x] Subtask 3.6: Implement `run()`:
    - Loads cases.
    - For each case, calls the extractor client (live or replay).
    - Computes F1 Phone, Hallucination, MST Modulo 11 per case and aggregates.
    - Writes `raw.jsonl` (per-case results) and `run_artifact.json`.
    - Calls `_evaluate_lead_extraction_gate(metrics)` with the benchmark's `gate.yaml` and raises `RuntimeError` if thresholds are not met.
  - [x] Subtask 3.7: Implement `gate.yaml`:
    ```yaml
    baseline_ratified: false
    thresholds:
      min_f1_phone: 0.98
      max_hallucination_rate: 0.001
      min_mst_modulo11_accuracy: 0.995
      min_cases: 10
    baseline_source: ""
    ```
  - [x] Subtask 3.8: Implement `report_section()` that renders a markdown table with the three metrics, per-tag breakdown, and pass/fail.
  - [x] Subtask 3.9: Register the benchmark and set `requires_auth_for_ingest = False`, `requires_auth_for_run = True`.

- [x] **Task 4: Record and ratify Golden Cassettes (AC-1)**
  - [x] Subtask 4.1: Run the suite in `live` mode (with a configured `NOWING_JWT`) to generate `data/lead_extraction/regression/cassettes/{case_id}.sse.jsonl`.
  - [x] Subtask 4.2: Sanitize cassettes: replace real PII/tax/company names with synthetic equivalents that preserve shape and relationships.
  - [x] Subtask 4.3: Verify `replay` mode passes the gate with `$0` cost (no live HTTP). Use a no-network assertion or `respx` in the benchmark unit test.
  - [x] Subtask 4.4: Whitelist committed cassettes in `nowing_evals/data/.gitignore`.

- [x] **Task 5: Anti-Zombie Chaos Testing harness (AC-2)**
  - [x] Subtask 5.1: Create `nowing_backend/scripts/chaos_scraper_stress.py`:
    - Args: `--duration-seconds` (default `72 * 3600`), `--ci` (sets default 300s), `--workers`.
    - Continuously enqueues synthetic scraping missions or calls a safe scraper test endpoint.
    - Every 60s runs `ps aux` and counts `Z` / `<defunct>` processes.
    - Exits non-zero if any zombie is detected; writes `zombie_log.jsonl`.
  - [x] Subtask 5.2: Add `scripts/docker/healthcheck_zombie.sh` that returns unhealthy if `ps aux | grep '[dD]efunct'` is non-empty.
  - [x] Subtask 5.3: Add a Dokploy/cron-compatible wrapper `scripts/run_72h_chaos.sh` that starts the stress test and tails the log.
  - [x] Subtask 5.4: Add a 5-minute CI version in `.github/workflows/chaos-gate.yml`.

- [x] **Task 6: Enforce and verify 60s hard context timeouts (AC-2)**
  - [x] Subtask 6.1: Audit `app/tasks/dsh_worker.py`, `app/proprietary/platforms/*/scraper.py`, and `app/services/phone_waterfall_service.py` for unbounded `httpx`/browser/Redis `XREADGROUP` calls.
  - [x] Subtask 6.2: Add a 60s timeout to any missing call using `asyncio.wait_for`, `httpx.Timeout(60.0)`, or context-manager wrappers. Do not silently swallow `TimeoutError`.
  - [x] Subtask 6.3: Add unit tests that simulate a 61s hang and assert the call is cancelled/terminated.

- [x] **Task 7: Hermetic backend unit/integration tests**
  - [x] Subtask 7.1: Extend `tests/unit/proprietary/platforms/xactions/test_phone_extractor.py`:
    - Add `TestPhoneExtractionHermetic` covering F1-style phone sets (legacy 11-digit, punctuation, +84 prefix, non-phone noise).
    - Add `TestTaxCodeValidation` with known-good and known-bad MSTs if the validator is placed in `xactions/tax_code.py`.
  - [x] Subtask 7.2: Add `tests/integration/services/test_lead_extraction_hermetic.py`:
    - Tests `LeadExtractionService.extract_from_text` with the test endpoint.
    - Uses `tests/e2e/fakes/mcp_runtime.py` to fake any MCP calls if `dsh_worker` is involved.
  - [x] Subtask 7.3: Add `tests/unit/proprietary/platforms/xactions/test_tax_code.py` for `is_valid_vietnam_tax_code`.
  - [x] Subtask 7.4: Add `nowing_evals/tests/suites/test_lead_extraction_regression.py` covering metric math, missing cassette handling, and gate pass/fail.

- [x] **Task 8: CI / quality pipeline wiring**
  - [x] Subtask 8.1: Create `.github/workflows/lead-extraction-regression-gate.yml`:
    ```bash
    python -m nowing_evals ingest lead_extraction regression
    NOWING_JWT=dummy python -m nowing_evals run lead_extraction regression --mode replay
    ```
  - [x] Subtask 8.2: Create `nowing_evals/scripts/run-hermetic-gate.sh` for local reproduction.
  - [x] Subtask 8.3: Update `_bmad/custom/nowing-quality-pipeline.md` with 26.7 verification commands.

---

### Review Findings

#### Decision-needed

- [x] [Review][Patch] `company_name` extraction scope — Resolved to add a `company_name` accuracy/F1 metric; included in `raw.jsonl`, `run_artifact.json`, `report_section`, and tests.
- [x] [Review][Patch] Anti-zombie / 72-hour stress harness scope — Resolved to rewrite `chaos_scraper_stress.py` to drive the hermetic `POST /api/v1/test/extract-entities` endpoint in a long-duration loop with `--duration-seconds`, `--ci`, `--workers`, `zombie_log.jsonl`, and all-container zombie detection.

#### Patch (applied)

- [x] [Review][Patch] `mst_modulo11_accuracy` does not match the spec [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:107-120`]. It compares `tax_ids_valid` against `expected_tax_ids_valid` by index, so an expected-invalid tax ID scores 1.0. It should be `sum(tax_ids_valid) / len(tax_ids_valid)` per the spec; remove the `expected_valid` parameter and the index-comparison logic.
- [x] [Review][Patch] Test endpoint is a public PII-extraction API with a hardcoded fallback secret and `ENVIRONMENT` bypass [`nowing_backend/app/routes/extract_entities_routes.py:15-40`]. Use a dedicated `TEST_EXTRACTION_SECRET` (no default fallback), remove the `ENVIRONMENT` bypass, set `include_in_schema=False`, and add rate limiting/request-size throttling.
- [x] [Review][Patch] Global `--mode` flag leaks into `extra_kwargs` and breaks `chat/quality` [`nowing_evals/src/nowing_evals/core/cli.py:1004-1009`, `nowing_evals/src/nowing_evals/suites/chat/quality/runner.py:475`]. Exclude `"mode"` from `extra_kwargs` in `_cmd_run` and rely on `ctx.mode`; or remove the `opts.get("mode")` fallback in chat/quality.
- [x] [Review][Patch] `requires_auth_for_run = False` contradicts the spec design decision [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:170`]. Set `True`, use `NOWING_JWT=dummy` for replay, and update `run-hermetic-gate.sh`.
- [x] [Review][Patch] `hallucination_rate` treats `+84` / `84` / obfuscated phones as hallucinations [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:88`, `metrics.py:32-52`]. Normalize the source text with the same letter-to-digit, `+84`/`84`, and legacy-prefix pipeline before membership tests.
- [x] [Review][Patch] `extract_tax_ids` cannot match spaced/dashed tax codes and may extract arbitrary 10-digit numbers [`nowing_backend/app/proprietary/platforms/xactions/tax_code.py:42-45, 60-76`]. Allow optional `[.\s-]` delimiters inside the main 10-digit group; exclude phone-pattern matches; add per-call timeout.
- [x] [Review][Patch] Cassette recording writes unsanitized PII and has no usable `--record` flag [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:33, 42-53`]. Add a `--record` / `--record-cassettes` CLI flag wired to `RunContext`, sanitize phones/tax/company, and add a CI pre-commit check.
- [x] [Review][Patch] `case_id` is used directly in a filesystem path, allowing cassette path traversal [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:23, 46`]. Validate `case_id` against `[a-zA-Z0-9_-]+` or `Path.resolve()` within `cassettes_dir` and reject escapes.
- [x] [Review][Patch] CLI `--mode replay` is accepted by every benchmark, even those without replay support [`nowing_evals/src/nowing_evals/core/cli.py:1004-1012`]. Add `supports_replay: bool = False` to the `Benchmark` protocol; reject `mode=replay` for benchmarks that do not opt in.
- [x] [Review][Patch] `ingest` and `run_artifact.json` writes are non-atomic; `runs_dir` is keyed on 1-second timestamp, causing collisions under parallel runs [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:190-192, 219-220, 227-269`, `nowing_evals/src/nowing_evals/core/cassette.py:39-48`]. Use `tmp + os.replace`, add a unique run-id suffix or expose `--run-id`, and add file locking around `ingest`.
- [x] [Review][Patch] `evaluate_lead_extraction_gate` can fail-open when metrics are missing [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:127-158`]. Treat missing `mst_modulo11_accuracy` and `hallucination_rate` as gate failures with explicit reasons; do not use optimistic defaults.
- [x] [Review][Patch] Task 6 (60s hard timeout audit) is not implemented. No changes to `dsh_worker.py`, `*/scraper.py`, or `phone_waterfall_service.py`. Audit each, wrap unbounded calls with `httpx.Timeout(60.0)` / `asyncio.wait_for(timeout=60.0)`, and add 61s-hang tests.
- [x] [Review][Patch] Missing `.github/workflows/chaos-gate.yml` and tini/WAL verification [`nowing_backend/scripts/chaos_scraper_stress.py:1-153`, `nowing_backend/Dockerfile:225`, `docker/postgresql.conf:12-13`]. Add the workflow, verify `ps -p 1 -o comm=` is `tini`, and verify `SHOW max_slot_wal_keep_size; SHOW wal_keep_size;` in Postgres.
- [x] [Review][Patch] `healthcheck_zombie.sh` is not wired into the Docker image [`nowing_backend/scripts/docker/healthcheck_zombie.sh:1-13`]. Add a `HEALTHCHECK` instruction to `nowing_backend/Dockerfile`.
- [x] [Review][Patch] `Cassette.load` does not validate that JSON is a dict or that `body` is a dict [`nowing_evals/src/nowing_evals/core/cassette.py:21-37`]. Add `isinstance(data, dict)` / `isinstance(data.get("body"), dict)` checks and raise `ValueError` with the cassette path.
- [x] [Review][Patch] `run()` does not validate the `cases.jsonl` schema or `case_id` safety [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:203-230`]. Add `_validate_case` for required fields, safe `case_id`, coerced `tags`, and `max-cases >= 0`; guard `hallucination_rate` for `source_text is None`.
- [x] [Review][Patch] `baseline_ratified` and `--fail-on-unratified` are ignored [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:286-291`]. Respect `baseline_ratified` and add the `--fail-on-unratified` run arg; handle empty `gate.yaml` safely.
- [x] [Review][Patch] `extract_entities_routes.py` hard-codes `/api/v1/test` prefix, duplicating mount paths [`nowing_backend/app/routes/extract_entities_routes.py:15`, `nowing_backend/app/routes/__init__.py:255`, `nowing_backend/app/app.py:1193-1195`]. Change prefix to `/test` or nothing so `crud_router` mounting produces a consistent path.
- [x] [Review][Patch] No timeout guard in `LeadExtractionService` for tax/company extraction [`nowing_backend/app/services/lead_extraction_service.py:50-64`]. Wrap `extract_tax_ids` and `extract_company_name` with `asyncio.to_thread` + `asyncio.wait_for(timeout=60.0)`.
- [x] [Review][Patch] `test_extract_entities_routes.py` does not cover the actual attack surface [`nowing_backend/tests/integration/routes/test_extract_entities_routes.py:38-53`]. Add tests for missing header in production, the default secret fallback, `ENVIRONMENT` bypass, `include_in_schema=False`, and large/malformed payloads.
- [x] [Review][Patch] `run-hermetic-gate.sh` skips the `ingest` step and `NOWING_JWT=dummy` [`nowing_evals/scripts/run-hermetic-gate.sh:1-11`]. Add the explicit `ingest` step and `NOWING_JWT=dummy` export (or align with the auth decision).
- [x] [Review][Patch] `RunContext.mode` is typed as `str`, not `Literal["live", "replay"]` [`nowing_evals/src/nowing_evals/core/registry.py:50`]. Use `Literal` or add runtime validation in `cli.py`.
- [x] [Review][Patch] `run_artifact.json` omits `raw_path` [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:311-322`]. Include `raw_path` and use an atomic write helper.
- [x] [Review][Patch] `test_tax_code.py` only uses 2 known-good fixtures and does not test `extract_tax_ids` edge cases [`nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py:1-83`]. Add extraction tests for dot/space/dash/prefix MSTs and negative phone false-positives.
- [x] [Review][Patch] `nowing_evals` suite tests do not cover replay flow or `ExtractorClient` [`nowing_evals/tests/suites/test_lead_extraction_regression.py:1-93`]. Add end-to-end replay tests against committed cassettes, missing cassette handling, and a no-network/live-call assertion with `respx`.
- [x] [Review][Patch] GitHub workflow `mode` input is ignored [`.github/workflows/lead-extraction-regression-gate.yml:17-21, 47-49`]. Pass the input to the script or remove it.
- [x] [Review][Patch] `report_section` lacks the per-tag breakdown required by Subtask 3.8 [`nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:329-356`]. Aggregate and print per-tag F1, hallucination, and MST averages.

#### Deferred

- [x] [Review][Defer] Pre-compile regex token pattern at module level in `phone_extractor.py` [`nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py:220-224`] — deferred, pre-existing
- [x] [Review][Defer] Validate `is_valid_vietnam_tax_code` against 100 known-good masothue fixtures before ratifying [`nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py:1-83`] — deferred, fixtures not yet available
- [x] [Review][Defer] Add FastMCP hermetic integration test for `dsh_worker` / `nowing_mcp` reusing `tests/e2e/fakes/mcp_runtime.py` — deferred, out of scope for the `nowing_evals` cassette suite; revisit when FastMCP transport is explicitly required

---

## Dev Notes

### Reuse existing patterns

- **Benchmark protocol:** `nowing_evals/src/nowing_evals/core/registry.py:165-189` and `nowing_evals/src/nowing_evals/core/cli.py:993-1004` (dynamic `run` subparser).
- **Chat regression runner as a template for local gate + reporting:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`. Copy `_load_chat_gate`, `_evaluate_chat_gate`, `_Case`, `_CaseResult`, `_load_cases`, `_gather_with_limit`, and `report_section` patterns; replace chat-specific fields with lead-extraction fields.
- **Cassette storage convention:** `nowing_evals` data is organized under `data/<suite>/<benchmark>/`. Use `ctx.benchmark_data_dir()` for cases and `ctx.benchmark_data_dir() / "cassettes"` for cassettes.
- **Hermetic fakes in backend tests:** `tests/e2e/fakes/mcp_runtime.py:117-151` for any `dsh_worker` FastMCP tests.

### Architecture invariants to preserve

- **AD-107 ($0 cost):** The `replay` path must not make any live external call. The test endpoint itself must be local/no-cost (no OpenAI, no masothue, no ChainLens, no browser). All cassettes must be sanitized.
- **AD-108 (tini + timeout + WAL):** Do not remove `tini` from `nowing_backend/Dockerfile` or the WAL limits from `docker/postgresql.conf`. 26.7 only adds verification/healthchecks.
- **AD-104 (Zero-Cache):** The new test endpoint does not write `leads`, so it does not affect `zero_publication`.
- **AD-109 (deterministic ordering):** If the endpoint or benchmark uses `batch_ingest_leads` in any follow-up, sort fixtures by `value_hmac ASC`.

### What must **not** be done

- Do **not** call `python -m nowing_evals gate --suite lead_extraction --benchmark regression`; the generic `evaluate_gate` cannot load the custom `gate.yaml` fields.
- Do **not** create a new `test_phone_extractor_hermetic.py`; extend the existing `test_phone_extractor.py`.
- Do **not** import `tests/e2e.fakes.mcp_runtime` or `tests.fixtures.masothue_mock` from `nowing_evals`; those live in the backend venv. Copy the minimal fake patterns or rely on cassettes.

### Files expected to be created

- `nowing_evals/src/nowing_evals/core/cassette.py`
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/__init__.py`
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py`
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py`
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/gate.yaml`
- `nowing_evals/data/lead_extraction/regression/cases.jsonl` (generated by `ingest`)
- `nowing_evals/data/lead_extraction/regression/cassettes/*.sse.jsonl` (recorded in live, sanitized, committed)
- `nowing_evals/tests/suites/test_lead_extraction_regression.py`
- `nowing_evals/scripts/run-hermetic-gate.sh`
- `nowing_backend/app/proprietary/platforms/xactions/tax_code.py`
- `nowing_backend/app/services/lead_extraction_service.py`
- `nowing_backend/app/schemas/extract_entities.py`
- `nowing_backend/app/routes/extract_entities_routes.py`
- `nowing_backend/scripts/chaos_scraper_stress.py`
- `nowing_backend/scripts/docker/healthcheck_zombie.sh`
- `nowing_backend/scripts/run_72h_chaos.sh`
- `.github/workflows/lead-extraction-regression-gate.yml`
- `.github/workflows/chaos-gate.yml` (or merge into the above)

### Files expected to be modified

- `nowing_evals/src/nowing_evals/core/cli.py` — add `--mode`.
- `nowing_evals/src/nowing_evals/core/registry.py` — add `mode` to `RunContext`.
- `nowing_evals/data/.gitignore` — whitelist cassettes.
- `nowing_backend/app/routes/__init__.py` — wire `extract_entities_routes`.
- `nowing_backend/tests/unit/proprietary/platforms/xactions/test_phone_extractor.py` — extend.
- `nowing_backend/app/tasks/dsh_worker.py` — add 60s timeouts if missing.
- `nowing_backend/app/proprietary/platforms/*/scraper.py` — add 60s browser/page timeouts if missing.
- `nowing_backend/app/services/phone_waterfall_service.py` — add 60s timeout if missing.

---

## References

- **Story source:** `_bmad-output/planning-artifacts/epics.md` lines 3409-3418.
- **AD-107 / AD-108:** `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` lines 152-162.
- **Sprint change proposal:** `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-17-unified-nowing-chainlens-dsh.md` lines 52-54.
- **Quality pipeline:** `_bmad/custom/nowing-quality-pipeline.md`.
- **Benchmark protocol:** `nowing_evals/src/nowing_evals/core/registry.py:165-189`.
- **CLI parser:** `nowing_evals/src/nowing_evals/core/cli.py:993-1004`.
- **Chat regression gate pattern:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:504-514` and `1087-1090`.
- **Generic gate limitation:** `nowing_evals/src/nowing_evals/core/gate.py:42-63`.
- **Extraction code:** `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py`.
- **Batch ingestion contract:** `nowing_backend/app/routes/lead_batch_routes.py:61-107`.
- **Resolve phone endpoint (existing, not suitable for the benchmark):** `nowing_backend/app/routes/leads_routes.py:664-746`.
- **Docker/tini/WAL (already in place):**
  - `nowing_backend/Dockerfile:33` and `:225`.
  - `docker/postgresql.conf:12-13`.

---

## Verification Commands

```bash
# Backend unit/integration tests
cd nowing_backend
uv run ruff check .
uv run pytest tests/unit/proprietary/platforms/xactions/test_phone_extractor.py -q
uv run pytest tests/unit/proprietary/platforms/xactions/test_tax_code.py -q
uv run pytest tests/integration/services/test_lead_extraction_hermetic.py -q

# Eval suite tests
cd nowing_evals
python -m pytest tests/suites/test_lead_extraction_regression.py -q

# Ingest and run the lead-extraction benchmark in replay mode (no external cost)
cd nowing_evals
python -m nowing_evals ingest lead_extraction regression
NOWING_JWT=dummy python -m nowing_evals run lead_extraction regression --mode replay

# Chaos smoke test (5 minutes, CI-safe)
cd nowing_backend
python scripts/chaos_scraper_stress.py --duration-seconds 300 --ci

# Manual 72-hour Dokploy run
cd nowing_backend
./scripts/run_72h_chaos.sh
```

---

## Open Questions / Risks

1. **MST Modulo-11 algorithm:** The exact algorithm for 10-digit and 13-digit Vietnamese tax codes must be verified against the Ministry of Finance circular and 100 known-good masothue fixtures before the gate is ratified. If the fixtures are not available, treat this as a design subtask and do not flip `baseline_ratified`.
2. **Test endpoint exposure:** `POST /api/v1/test/extract-entities` must be guarded so it cannot be used in production to extract data without auth/authorization. Use an internal API key or environment flag. Do not expose in public docs.
3. **Cassette PII hygiene:** Cassettes recorded in `live` mode will contain real PII. Sanitization must normalize phone/tax/company names while preserving shape and relationships. Never commit unsanitized cassettes.
4. **Replay determinism:** The test endpoint is deterministic (no timestamps/randomness), so cassettes should be stable. If non-determinism is introduced later (e.g., random model sampling), stub those sources.
5. **72-hour Dokploy cost:** The long stress test may consume real DataImpulse/CapSolver budget if it calls real scrapers. The default script should be opt-in (`--duration-seconds`) and use a safe test endpoint in CI. The CI variant must be capped at 5 minutes.
6. **FastMCP scope:** AD-107 calls for Fake FastMCP transport. This suite satisfies the hermetic/$0-cost intent via REST cassettes. A follow-up should add FastMCP hermetic tests for `dsh_worker` (Task 7.2 already uses the existing fake pattern).

---

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **Phone extraction helper exists in two places.** `app/proprietary/platforms/xactions/phone_extractor.py` (`SocialEntityExtractor`) is the most comprehensive (legacy 11-digit, obfuscated letters, ReDoS guard). `app/proprietary/platforms/telegram/entity_extractor.py` has a similar but less capable phone extractor. **Recommendation:** The test endpoint must use `xactions/phone_extractor.py`; do not create a third extractor or silently fall back to the Telegram version.
- **Tax code extraction regex exists in masothue.** `app/proprietary/platforms/masothue/parsers.py:104-111` has `_extract_tax_code` (regex `\d{10,}` with dash stripping, no Modulo-11 validation). **Recommendation:** Refactor this into `app/proprietary/platforms/xactions/tax_code.py` and import it from masothue to avoid two regex sources of truth. If not, at least align the regexes.
- **No cassette/replay system exists in `nowing_evals`.** Safe to add new `core/cassette.py` and `ReplayClient`.
- **No chaos/zombie monitor script exists.** `scripts/stress_google_search.py` is a live stress test but does not monitor `ps aux`; the new `chaos_scraper_stress.py` should reuse its logging/arg style but not its live scraping logic.

**Verdict:** No exact duplicate that blocks the story, but extraction helpers are scattered. Dev must pick the canonical `xactions` phone extractor and decide whether to unify tax-code extraction with `masothue`.

### Q2 — Simpler alternative?

- **Phone:** `SocialEntityExtractor` from `xactions/phone_extractor.py` is the right tool; no simpler alternative.
- **Tax code:** The regex already exists in `masothue/parsers.py`; the simpler alternative is to extract a shared `xactions/tax_code.py` and import it. This is simpler than writing a brand-new private regex and later discovering divergence.
- **Stress test:** `scripts/stress_google_search.py` provides a proven pattern for long-running scraper stress tests; use it as a template for argument parsing and logging.
- **Cassette loading:** `nowing_evals` suites already write JSONL artifacts and `RunArtifact` objects; a small `Cassette` dataclass in `core/cassette.py` is simpler than adding a full VCR-like dependency.

**Verdict:** No blocker, but the tax-code extraction should be centralized.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Company name extraction is not implemented anywhere.** `SocialEntityExtractor.extract_all` does not return a company name. The story's dataset, endpoint schema, and `expected_company_name` field cannot be verified. **Fix before implement:** either (a) remove `company_name` from the endpoint, dataset, and metrics, or (b) add a company-name heuristic (e.g., first line after "Công ty"/"CTY"/"TNHH").
- [ ] **Legacy 11-digit phones:** must normalize `016x...` → `03x...`/`07x...` etc. `phone_extractor.py` supports this; `telegram/entity_extractor.py` does not.
- [ ] **+84 / 84 / 0 prefixes and punctuation:** phone extractor covers this; verify F1 metric normalizes all variants.
- [ ] **Tax ID formats:** 10-digit vs 13-digit, with/without dashes, with/without spaces. `masothue/parsers` regex already missed spaced MST; the new validator must handle these.
- [ ] **Empty / whitespace-only source text:** endpoint must return empty lists, not 500/422.
- [ ] **`mode=replay` missing cassette:** fail closed with clear `FileNotFoundError` / `RuntimeError`.
- [ ] **`mode=replay` malformed cassette:** fail closed with `json.JSONDecodeError`.
- [ ] **`ingest` duplicate `case_id`:** define behavior (overwrite, skip, or error).
- [ ] **`ingest` missing required fields:** validate and fail fast.
- [ ] **`min_cases` threshold:** if fewer cases match filters, gate must fail, not silently pass.
- [ ] **`baseline_ratified=false` and `--fail-on-unratified`:** chat/chainlens pattern; preserve it.
- [ ] **Long source text / ReDoS:** `phone_extractor` has 50ms timeout; the endpoint should keep it and the F1 metric must count a timeout as a miss, not ignore it.
- [ ] **`allow_hallucinated_phones` semantics:** define whether a hallucinated phone is counted in `hallucination_rate` even if it happens to be a valid VN number.
- [ ] **Concurrent `run` on same `data/lead_extraction/regression/runs/`:** `RunContext.runs_dir` uses ISO timestamp, but parallel runs can race. Consider a `--run-id` suffix or lock.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **Test endpoint exposed unguarded:** if `POST /api/v1/test/extract-entities` reaches production, anyone can extract PII from arbitrary text. Guard with `X-Internal-Test` header or internal API key and add a test that rejects unauthenticated calls.
- [ ] **`is_valid_vietnam_tax_code` wrong:** all tax IDs become invalid (MST gate 0%) or all valid (MST gate 100%). Add unit tests against 100 known-good fixtures and 100 known-bad/synthetic cases.
- [ ] **`SocialEntityExtractor` timeout / ReDoS attack:** returns `[]`. The benchmark must record this as a `failed` case, not a 100% hallucination, and it must not crash.
- [ ] **Cassette contains unsanitized PII:** commit risk. Add a `sanity-check-cassettes` script or CI step that rejects real phone/tax patterns.
- [ ] **`NOWING_JWT` missing in CI:** even `replay` mode `acquire_token` may raise `CredentialError`. Verify `Config.has_jwt_mode()` works with `NOWING_JWT=dummy` or set `requires_auth_for_run = False` for this suite.
- [ ] **72-hour stress hits live scrapers:** budget/credit burn. CI must default to the safe test endpoint or hermetic loop; the long Dokploy run must be opt-in.
- [ ] **`ps aux` false positive:** process names or grep matching "defunct" in command line. Parse `STAT` column (`Z` state) and PID/PPID.
- [ ] **`tini` not actually PID 1 in Dokploy:** entrypoint override. Add a CI check in `chaos-gate.yml` that verifies `ps -p 1 -o comm=` is `tini`.
- [ ] **60s timeout not enforced in `dsh_worker` / scraper / `phone_waterfall_service`:** hang leading to zombie accumulation. Audit each `httpx.AsyncClient` request and `XREADGROUP` block.
- [ ] **PostgreSQL WAL config drift:** `max_slot_wal_keep_size` / `wal_keep_size` changed. Add a smoke test that reads `SHOW max_slot_wal_keep_size`.
- [ ] **`RunArtifact.metrics` missing keys:** if a run fails, metrics may be `None`/empty. `_evaluate_lead_extraction_gate` must handle missing keys with clear failure reasons.
- [ ] **Hallucination rate denominator zero:** if the endpoint returns zero predictions, the rate should be `0.0` (no hallucination), not `ZeroDivisionError`.

### Triage

- **Q1:** Similar helpers found in `telegram/entity_extractor.py` and `masothue/parsers.py`. Not an exact duplicate, but dev must reuse/centralize to avoid divergence. **Continue with note.**
- **Q2:** `masothue/parsers._extract_tax_code` is a simpler tax-code extraction source to build on. **Continue with recommendation to centralize.**
- **Q3:** `company_name` extraction is a spec gap; several boundary/empty/concurrency edge cases are unspecified. **Non-critical, continue, add to test skeleton.**
- **Q4:** Security, cost, timeout, and PII failure modes are unspecified. **Non-critical, continue, add to test skeleton.**
- **Overall verdict:** **Continue** — no hard HALT, but the `company_name` field and tax-code duplication should be resolved before or during implementation, not after.
