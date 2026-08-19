# Story 26.7 Acceptance Auditor Findings Report

- **Project root:** `/Users/luisphan/Documents/GitHub/nowing`
- **Review diff:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/test-artifacts/review-26-7.diff`
- **Spec/story:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/26-7-hermetic-quality-gates-benchmark-anti-zombie.md`
- **Audit method:** Static diff/code review against the spec, acceptance criteria, and architecture invariants AD-107 / AD-108. No source code files were modified.

---

## 1. Executive summary

### 1.1 AC / invariant headline

| Criterion | Verdict | Notes |
|---|---|---|
| **AC-1.1** `$0` external cost in `--mode replay` | **PASS** | `ExtractorClient` returns cassette `body` without any HTTP call. No OpenAI/ChainLens/masothue/browser calls in replay. |
| **AC-1.2** Golden cassettes loaded from `data/lead_extraction/regression/cassettes/` | **PASS** | `Cassette.load` reads `{case_id}.sse.jsonl`; 10 cassettes committed and whitelisted in `.gitignore`. |
| **AC-1.3** F1 / Hallucination / MST gates at correct thresholds | **PARTIAL** | F1 and Hallucination look correct; **MST Modulo-11 metric is implemented as classification-vs-expected, not the spec-defined fraction of valid tax IDs**, so an invalid MST that the dataset expects to be invalid scores 1.0 and the gate can pass while returning invalid tax IDs. |
| **AC-1.4** Failing gate exits non-zero and emits `run_artifact.json` with `passed: false` and `reasons` | **PASS** | `run_artifact.json` is written before `RuntimeError` is raised; `extra.passed` / `gate_reasons` are populated. |
| **AC-2.1** 72h continuous scraping, 0 zombie Chromium processes | **FAIL** | The harness spawns mock `python -c` child processes, not Chromium, and only counts child zombies of the script itself. |
| **AC-2.2** `tini` as PID 1 | **NOT VERIFIED** | `Dockerfile` is unchanged and still uses `tini` at `ENTRYPOINT`; the new verification code does not check it. |
| **AC-2.3** 60s hard timeout on all sync/REST/XREADGROUP calls | **NOT VERIFIED** | No diff changes in `dsh_worker.py`, `phone_waterfall_service.py`, or `*/scraper.py`; story did not complete Task 6. Existing `dsh_worker` REST uses 60s, but the Redis `XREADGROUP` block is 5s and there is no `asyncio.wait_for` around message handling. |
| **AC-2.4** WAL limits `max_slot_wal_keep_size=4096MB`, `wal_keep_size=1024MB` | **NOT VERIFIED** | `docker/postgresql.conf` is unchanged and still has the limits; the new verification code does not check them. |
| **AD-107** Hermetic / $0 cost | **NO CONTRADICTION** | Cassettes satisfy the $0-cost intent. FastMCP transport is not used, but the spec explicitly documents this as a cassette-only suite. The planned backend FastMCP fake test (Task 7.2) is missing. |
| **AD-108** tini / timeout / WAL | **NO CONTRADICTION** | Nothing was removed. However, the added verification harness is too weak to demonstrate the invariant. |

### 1.2 company_name spec gap (Challenge Log Q3)

**Partially resolved, not verified.** A regex-based company-name extractor was added (`lead_extraction_service.py:35-48`), but the benchmark does not compare `expected_company_name` from the dataset, does not compute a metric, does not include the value in `raw.jsonl` / `run_artifact.json`, and does not mention it in `report_section`. The dataset and cassettes still carry `company_name`, so the spec gap has been "filled" with a heuristic but is not actually gated or tested.

---

## 2. AC-1: Hermetic `lead_extraction/regression` Replay (AD-107)

### 2.1 Critical

#### MST Modulo-11 metric is not the fraction of valid tax IDs required by the spec

- **Severity:** critical
- **AC/spec constraint violated or missing:** AC-1.3 requires `MST Modulo 11 >= 0.995`. Subtask 3.5 defines `mst_modulo11_accuracy(tax_ids_valid: list[bool])` as "**fraction of returned tax IDs where `tax_ids_valid[i] is True`** (computed by the backend endpoint; the benchmark does not re-implement the validator)". The implementation instead compares predicted validity flags against `expected_tax_ids_valid`, i.e. a per-case classification accuracy. With the committed dataset, `lead-009` returns an invalid MST (`0100109105`) that is expected to be invalid (`expected_tax_ids_valid: [false]`); the implementation returns `1.0` for that case because `False == False`, so the overall gate will almost always report `1.0` even though the extractor returned an invalid tax ID. This hides the very quality problem the gate is meant to catch.
- **Evidence:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:107-120` (`review-26-7.diff:1321-1334`); `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:249-255, 275` (`review-26-7.diff:1097-1102, 1123`); `nowing_evals/tests/suites/test_lead_extraction_regression.py:39-45` (`review-26-7.diff:1604-1610`).
- **Concrete fix or ask:** Re-implement `mst_modulo11_accuracy` as `sum(tax_ids_valid) / len(tax_ids_valid)` for non-empty cases (and `1.0` / skip for empty cases). Remove the `expected_valid` parameter from the metric. If the intent was actually "validator classification accuracy", rename the metric and the gate, reconcile the dataset (which cannot contain expected-invalid MSTs under a "fraction valid" threshold), and update the spec/AC accordingly.

### 2.2 High

#### company_name extraction is present but not evaluated, leaving the Challenge Log gap unverified

- **Severity:** high
- **AC/spec constraint violated or missing:** Challenge Log Q3 says "either (a) remove `company_name` from the endpoint, dataset, and metrics, or (b) add a company-name heuristic". The implementation chose (b) but never evaluates it. The dataset carries `expected_company_name` (e.g. `lead-001`: "Công ty TNHH Viễn Thông ABC"), the response schema includes `company_name`, and cassettes store it, but `run()` does not compare predictions/expected, no metric is defined, and `report_section` does not mention it.
- **Evidence:** `nowing_backend/app/services/lead_extraction_service.py:14-47` (`review-26-7.diff:257-291`); `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:33-124` (dataset, `review-26-7.diff:881-972`); `runner.py:257-267` (per-case row omits `company_name`, `review-26-7.diff:1105-1116`); `runner.py:329-356` (report, `review-26-7.diff:1177-1204`); `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py` has no company metric.
- **Concrete fix or ask:** Either add a `company_name` F1/accuracy metric, include it in `raw.jsonl` / `run_artifact.json` / `report_section`, and add tests; or remove `company_name` / `expected_company_name` from the schema, dataset, and cassettes and document it as out of scope.

### 2.3 Medium

#### Benchmark `requires_auth_for_run = False` contradicts the spec design decision

- **Severity:** medium
- **AC/spec constraint violated or missing:** Spec "Auth in nowing_evals" (line 38) decides to set `requires_auth_for_run = True` because live mode calls the test endpoint, and in replay use `NOWING_JWT=dummy` so `acquire_token` short-circuits. The implementation sets `requires_auth_for_run = False`, so the CLI never acquires a token and the `NOWING_JWT=dummy` hermetic pattern is bypassed.
- **Evidence:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:170` (`review-26-7.diff:1018`); `nowing_evals/src/nowing_evals/core/cli.py:42-44` (`review-26-7.diff:565-568`); spec line 38.
- **Concrete fix or ask:** Set `requires_auth_for_run = True`, and update `nowing_evals/scripts/run-hermetic-gate.sh` to set `NOWING_JWT=dummy`. If the test endpoint intentionally does not need a JWT, update the spec design decision and document the exception.

#### `evaluate_lead_extraction_gate` can fail-open when metrics are missing

- **Severity:** medium
- **AC/spec constraint violated or missing:** AC-1.4 requires a clear failed gate. Challenge Log Q4 warns: "`RunArtifact.metrics` missing keys: ... `_evaluate_lead_extraction_gate` must handle missing keys with clear failure reasons." The function uses `metrics.get(..., 1.0)` for `mst_modulo11_accuracy` (a minimize metric) and `metrics.get(..., 0.0)` for `hallucination_rate` (a maximize metric), both of which can make a broken/incomplete run pass. `f1_phone` defaults to `0.0` (fail-closed) and `total_cases` to `0` (fail-closed), but the MST and hallucination defaults are optimistic.
- **Evidence:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:127-158` (`review-26-7.diff:975-1006`).
- **Concrete fix or ask:** Make all required metrics mandatory. If any is missing, append a reason and fail the gate; do not use optimistic defaults for `mst_modulo11_accuracy` or `hallucination_rate`.

#### AD-107 FastMCP transport is not implemented in the backend hermetic test

- **Severity:** medium
- **AC/spec constraint violated or missing:** AD-107 requires "in-memory Fake FastMCP transport". The spec design decision (lines 20-22) says this suite uses cassettes for the `nowing_evals` regression, but the backend hermetic integration test for `dsh_worker` / `nowing_mcp` (Task 7.2) should reuse `tests/e2e/fakes/mcp_runtime.py`. The committed backend test only does an HTTP ASGI call.
- **Evidence:** `nowing_backend/tests/integration/routes/test_extract_entities_routes.py:1-53` (`review-26-7.diff:713-771`); spec design decision lines 20-22.
- **Concrete fix or ask:** Add a FastMCP fake integration test as planned, or explicitly document the AD-107 exception for this suite and note that no FastMCP coverage exists.

### 2.4 Low

#### `report_section` lacks the per-tag breakdown required by Subtask 3.8

- **Severity:** low
- **AC/spec constraint violated or missing:** Subtask 3.8: "Implement `report_section()` that renders a markdown table with the three metrics, **per-tag breakdown**, and pass/fail." The report only shows overall metrics.
- **Evidence:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:329-356` (`review-26-7.diff:1177-1204`).
- **Concrete fix or ask:** Aggregate and print per-tag F1, hallucination, and MST averages in the markdown report.

#### `run-hermetic-gate.sh` skips the `ingest` step and `NOWING_JWT=dummy`

- **Severity:** low
- **AC/spec constraint violated or missing:** Spec verification commands (lines 278-279) are `python -m nowing_evals ingest lead_extraction regression` then `NOWING_JWT=dummy python -m nowing_evals run lead_extraction regression --mode replay`. The committed script runs only the second command and omits `NOWING_JWT`.
- **Evidence:** `nowing_evals/scripts/run-hermetic-gate.sh:1-11` (`review-26-7.diff:1495-1512`); spec lines 278-279.
- **Concrete fix or ask:** Add the explicit `ingest` step and `NOWING_JWT=dummy` export (or align with the auth decision above).

#### `baseline_ratified` and `baseline_source` in `gate.yaml` are ignored

- **Severity:** low
- **AC/spec constraint violated or missing:** The committed `gate.yaml` contains `baseline_ratified: false` and `baseline_source`, but the runner only reads `thresholds`. The chat/chainlens pattern supports `--fail-on-unratified` and ratified handling. Challenge Log Q3 mentions `baseline_ratified=false` and `--fail-on-unratified`.
- **Evidence:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/gate.yaml:1-7` (`review-26-7.diff:1397-1408`); `runner.py:286-293` (`review-26-7.diff:1133-1141`).
- **Concrete fix or ask:** Either respect `baseline_ratified` (fail/warn until `true`) or remove the unused fields from `gate.yaml`.

#### Cassette loader does not match the Subtask 1.2 claim of supporting `*.jsonl` as well as `*.sse.jsonl`

- **Severity:** low
- **AC/spec constraint violated or missing:** Subtask 1.2: "Loads `*.sse.jsonl` and `*.jsonl` cassette files." `Cassette.load` accepts any path but `ExtractorClient` hardcodes `.sse.jsonl`. The loader itself does not treat the two extensions differently.
- **Evidence:** `nowing_evals/src/nowing_evals/core/cassette.py:21-37` (`review-26-7.diff:772-825`); `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:23` (`review-26-7.diff:1363`).
- **Concrete fix or ask:** Make `ExtractorClient` fall back from `.sse.jsonl` to `.jsonl`, or update the subtask text to reflect that only `.sse.jsonl` is used.

#### Global `--mode` can collide with benchmark-specific `add_run_args`

- **Severity:** low
- **AC/spec constraint violated or missing:** Subtask 1.1 adds a global `--mode {live,replay}` to every `run <suite> <benchmark>` subparser. The `chat/quality` runner already had a `--mode` flag and was renamed to `--chat-mode`. Other benchmarks with `add_run_args` adding `--mode` will now collide.
- **Evidence:** `nowing_evals/src/nowing_evals/core/cli.py:56-65` (`review-26-7.diff:56-68`); `nowing_evals/src/nowing_evals/suites/chat/quality/runner.py` rename (`review-26-7.diff:94-115`).
- **Concrete fix or ask:** Audit all `add_run_args` methods for `--mode` collisions, or make replay mode a hidden/core flag that does not conflict with benchmark-specific modes.

#### `ingest` does not validate required fields, duplicate `case_id`, or `allow_hallucinated_phones`

- **Severity:** low
- **AC/spec constraint violated or missing:** Dataset schema (spec lines 113-115) includes `allow_hallucinated_phones`; Challenge Log Q3 lists missing edge cases (duplicate `case_id`, missing required fields). `ingest` only writes the default dataset; there is no validation.
- **Evidence:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:185-194` (`review-26-7.diff:1033-1042`); spec lines 113-115.
- **Concrete fix or ask:** Add JSONL validation and define `allow_hallucinated_phones` semantics in the metric code.

#### Tax-code unit tests do not cover the 100 fixtures required before ratifying

- **Severity:** low
- **AC/spec constraint violated or missing:** Open Questions / Risks #1: "Validate against 100 known-good tax codes from masothue fixtures before ratifying. If the fixtures are not available, treat this as a design subtask and do not flip `baseline_ratified`." The new test has only 2 valid + 1 branch/invalid examples.
- **Evidence:** `nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py:1-83` (`review-26-7.diff:565-654`).
- **Concrete fix or ask:** Add a fixture-driven corpus (or a synthetic 100-case set) and do not set `baseline_ratified: true` until that is done.

#### `nowing_evals` suite tests do not cover replay flow or `ExtractorClient`

- **Severity:** low
- **AC/spec constraint violated or missing:** Subtask 7.4 / AC-1.2: tests should cover "metric math, missing cassette handling, and gate pass/fail." The tests cover metrics and gate only; they do not test `ExtractorClient` replay, missing cassettes, or an end-to-end `run()` in replay mode.
- **Evidence:** `nowing_evals/tests/suites/test_lead_extraction_regression.py:1-93` (`review-26-7.diff:1560-1659`); `nowing_evals/tests/core/test_cassette.py` tests missing/malformed cassettes at the loader level only (`review-26-7.diff:1513-1559`).
- **Concrete fix or ask:** Add replay tests that run the benchmark against the committed cassettes and assert no HTTP calls are made (e.g. with `respx` or a no-network assertion).

#### Test endpoint default secret is hardcoded and predictable

- **Severity:** low
- **AC/spec constraint violated or missing:** Challenge Log Q4: guard the test endpoint with an internal API key. The route falls back to `os.getenv("DSH_WORKER_SECRET", "test-internal-secret")`, so a predictable default is embedded in the source and can be used if the env var is not set.
- **Evidence:** `nowing_backend/app/routes/extract_entities_routes.py:31-34` (`review-26-7.diff:344-347`).
- **Concrete fix or ask:** Remove the default; require `DSH_WORKER_SECRET` to be explicitly set and fail closed if missing.

#### `RunContext.mode` is typed as `str`, not `Literal["live","replay"]`

- **Severity:** low
- **AC/spec constraint violated or missing:** Subtask 1.3: "Add `mode: Literal["live", "replay"]` to `RunContext`." The implementation uses `mode: str`.
- **Evidence:** `nowing_evals/src/nowing_evals/core/registry.py:50` (`review-26-7.diff:77`).
- **Concrete fix or ask:** Change to `Literal["live", "replay"]` or add runtime validation in `cli.py` / `extractor_client.py`.

---

## 3. AC-2: tini, 60s Timeout, WAL, Anti-Zombie Chaos (AD-108)

### 3.1 Critical

#### The anti-zombie "stress harness" is not a 72h scraping stress test and cannot find Chromium zombies

- **Severity:** critical
- **AC/spec constraint violated or missing:** AC-2.1: "Given a scraping workload running continuously for 72 hours ... 0 defunct (`<defunct>`) and 0 zombie (`Z` state) Chromium/browser processes." Subtask 5.1 requires args `--duration-seconds` (default `72*3600`), `--ci` (300s), `--workers`; continuously enqueues synthetic scraping missions or calls a safe scraper test endpoint; every 60s runs `ps aux` and counts `Z`/`<defunct>`; writes `zombie_log.jsonl`. The implementation spawns `python -c "time.sleep(0.5); sys.exit(0)"` mock children, has no duration-based loop, no `--duration-seconds`/`--ci`/`--workers`, no `zombie_log.jsonl`, and only counts zombies whose PPID matches the script PID.
- **Evidence:** `nowing_backend/scripts/chaos_scraper_stress.py:1-153` (`review-26-7.diff:364-522`); `nowing_backend/scripts/run_72h_chaos.sh:1-18` (`review-26-7.diff:541-565`).
- **Concrete fix or ask:** Rewrite `chaos_scraper_stress.py` to (a) use a duration-based loop with `--duration-seconds` and `--ci` flags, (b) drive the real scraping stack or call `POST /api/v1/test/extract-entities` as a safe mission, (c) snapshot `ps aux` every 60s and append to `zombie_log.jsonl`, (d) count **all** `Z`/`<defunct>` processes in the container, not just the script's children, and (e) exit non-zero on any zombie.

### 3.2 High

#### Task 6 (60s hard timeout audit) is not implemented

- **Severity:** high
- **AC/spec constraint violated or missing:** AC-2.3: "Every synchronous tool call / REST round-trip / `XREADGROUP` block enforces a 60s hard timeout (raises/terminates, never hangs)." Subtask 6.1-6.3: audit `dsh_worker.py`, `*/scraper.py`, and `phone_waterfall_service.py`; add 60s timeouts; add unit tests for a 61s hang. The diff contains no changes to those files. Existing `dsh_worker.py` already uses `httpx.Timeout(DSH_SYNC_TIMEOUT_SECONDS=60s)` for REST and `XREADGROUP` block `DSH_REDIS_BLOCK_MS=5000ms`, but there is no `asyncio.wait_for` around message processing. `phone_waterfall_service.py` has only 2s/0.05s timeouts.
- **Evidence:** no `dsh_worker.py`, `phone_waterfall_service.py`, or `*/scraper.py` hunks in `review-26-7.diff`; `nowing_backend/app/tasks/dsh_worker.py:999-1005` (`XREADGROUP` with 5s block), `nowing_backend/app/services/phone_waterfall_service.py:238` (`wait=False, timeout=2.0`).
- **Concrete fix or ask:** Complete the audit, wrap unbounded calls with `asyncio.wait_for` / `httpx.Timeout(60.0)`, and add tests that inject a 61s hang and assert cancellation/termination.

#### No `.github/workflows/chaos-gate.yml` and no tini/WAL verification

- **Severity:** high
- **AC/spec constraint violated or missing:** Subtask 5.4: "Add a 5-minute CI version in `.github/workflows/chaos-gate.yml`." AC-2.2 and AC-2.4 require verification that `tini` is PID 1 and WAL limits are in effect. No CI workflow exists and the harness does not check either.
- **Evidence:** missing file in `review-26-7.diff`; `nowing_backend/scripts/chaos_scraper_stress.py` has no `ps -p 1` or PostgreSQL check; `nowing_backend/Dockerfile:225` and `docker/postgresql.conf:12-13` are unchanged.
- **Concrete fix or ask:** Create `.github/workflows/chaos-gate.yml` that runs a 300s stress test, asserts `ps -p 1 -o comm=` == `tini`, and runs `psql -c 'SHOW max_slot_wal_keep_size; SHOW wal_keep_size;'` to verify WAL limits.

### 3.3 Medium

#### `healthcheck_zombie.sh` is not wired into the Docker image

- **Severity:** medium
- **AC/spec constraint violated or missing:** Subtask 5.2 added the healthcheck script, but `Dockerfile` has no `HEALTHCHECK` instruction referencing it, so the script is dead code.
- **Evidence:** `nowing_backend/scripts/docker/healthcheck_zombie.sh:1-13` (`review-26-7.diff:523-540`); no `Dockerfile` diff.
- **Concrete fix or ask:** Add `HEALTHCHECK --interval=60s --timeout=10s CMD /app/scripts/docker/healthcheck_zombie.sh` to `nowing_backend/Dockerfile`.

#### `run_72h_chaos.sh` passes duration/interval args to a script that does not accept them

- **Severity:** medium
- **AC/spec constraint violated or missing:** Subtask 5.3 wrapper should drive the harness. The harness only accepts `--concurrency` and `--iterations`; the wrapper defines `DURATION_HOURS` and `INTERVAL_SEC` but never passes them.
- **Evidence:** `nowing_backend/scripts/run_72h_chaos.sh:5-15` (`review-26-7.diff:541-565`); `nowing_backend/scripts/chaos_scraper_stress.py:132-136` (`review-26-7.diff:500-504`).
- **Concrete fix or ask:** Add `--duration-seconds` and `--interval-seconds` (or `--workers`) to `chaos_scraper_stress.py` and have the wrapper pass them.

### 3.4 Low

#### `chaos_scraper_stress.py` filters zombies to its own children, missing cross-process zombies

- **Severity:** low
- **AC/spec constraint violated or missing:** AC-2.1 is about the whole container. The script only keeps zombies whose `PPID == os.getpid()`.
- **Evidence:** `nowing_backend/scripts/chaos_scraper_stress.py:113-119` (`review-26-7.diff:480-487`).
- **Concrete fix or ask:** Count all `Z`/`<defunct>` processes and optionally restrict to browser/Chromium process names.

---

## 4. Architecture invariants (AD-107 / AD-108)

### AD-107 — Hermetic / $0 cost

- **Contradiction?** No direct contradiction in the data path. The `nowing_evals` replay path loads cassettes and returns `body` without any network call (`extractor_client.py:22-29`), satisfying the $0-cost requirement. The committed cassettes contain synthetic PII. The design decision explicitly overrides the FastMCP requirement for this suite.
- **Gaps:** As noted in Section 2.3, the planned FastMCP backend test is missing; the default test-endpoint secret is predictable; and `requires_auth_for_run = False` bypasses the `NOWING_JWT=dummy` short-circuit pattern.

### AD-108 — tini / 60s timeout / WAL

- **Contradiction?** No code was removed. `nowing_backend/Dockerfile:33` still installs `tini` and `nowing_backend/Dockerfile:225` still sets `ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/docker/entrypoint.sh"]`. `docker/postgresql.conf:12-13` still sets `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB`.
- **Gaps:** The new verification code does not demonstrate any of the three invariants. The chaos harness is a mock child-process reaper, not a container-level 72h scraper test; no tini-PID-1 or WAL checks were added; Task 6 was not completed. Therefore the story does not verify AD-108, even though it does not violate it.

---

## 5. Spec task completion summary

| Task | Verdict | Notes |
|---|---|---|
| **Task 1** Replay infrastructure in `nowing_evals` | Mostly done | `--mode`, `RunContext.mode`, `Cassette`, `ReplayClient`, `replay_artifacts_dir` are present; replay rejection for non-replay benchmarks (1.5) missing. |
| **Task 2** Backend extraction test endpoint | Done | `tax_code.py`, `lead_extraction_service.py`, schemas, route, guard all present. |
| **Task 3** `lead_extraction/regression` benchmark | Mostly done | Package, dataset, client, metrics, run, gate all present; `company_name` unverified; per-tag report missing; MST metric wrong; `requires_auth_for_run` deviates. |
| **Task 4** Record & ratify cassettes | Done | 10 cassettes committed and whitelisted; but no respx/no-network test in the suite tests. |
| **Task 5** Anti-zombie chaos testing | Rework needed | `chaos_scraper_stress.py` does not match Subtask 5.1; `chaos-gate.yml` (5.4) missing. |
| **Task 6** 60s hard timeouts | Not done | No diff changes to `dsh_worker`, scrapers, or `phone_waterfall_service`; no 61s hang tests. |
| **Task 7** Hermetic backend tests | Partial | `test_tax_code.py` and `test_lead_extraction_service.py` added; `test_extract_entities_routes.py` HTTP-only; `test_phone_extractor.py` not extended (7.1); `test_lead_extraction_hermetic.py` not created (7.2). |
| **Task 8** CI / quality pipeline | Partial | `lead-extraction-regression-gate.yml` and `run-hermetic-gate.sh` added; `chaos-gate.yml` and `_bmad/custom/nowing-quality-pipeline.md` update missing. |

---

## 6. Concrete asks for the author / reviewer

1. **Fix the MST metric** before accepting the gate as correct; decide whether "MST Modulo-11" means "fraction of extracted tax IDs that are valid" or "validator classification accuracy" and reconcile the dataset.
2. **Resolve the `company_name` spec gap** by either adding a metric/test or removing the field from the schema/dataset/cassettes.
3. **Rewrite the anti-zombie harness** to be a real 72h/5m container-level stress test that exercises the scraping stack, logs `zombie_log.jsonl`, and checks all `Z`/`<defunct>` processes.
4. **Complete Task 6** (60s timeout audit + tests) and **Task 5.4** (`chaos-gate.yml` with tini/WAL checks).
5. **Set `requires_auth_for_run = True`** (or update the spec) and make `run-hermetic-gate.sh` use `NOWING_JWT=dummy`.
6. **Add the missing tests** (`test_phone_extractor.py` extension, `test_lead_extraction_hermetic.py` / FastMCP fake, replay-level suite tests).
7. **Remove the hardcoded `DSH_WORKER_SECRET` default** in the test route.

---

*End of report. No source code files were modified during this audit.*
