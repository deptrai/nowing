# Edge Case Hunter Review — Story 26.7

**Project root:** `/Users/luisphan/Documents/GitHub/nowing`  
**Diff:** `_bmad-output/test-artifacts/review-26-7.diff`  
**Spec:** `_bmad-output/implementation-artifacts/26-7-hermetic-quality-gates-benchmark-anti-zombie.md`  
**Reviewer:** Edge Case Hunter  

## Summary

| Severity | Count | Notes |
|---|---:|---|
| critical | 1 |hallucination rate misclassifies +84 / obfuscated phones as hallucinations |
| high | 4 | tax-dot/space extraction, test-endpoint security, run-directory / cassette races, chaos harness not testing real scrapers |
| medium | 9 | CLI `--mode replay` for non-replay suites, case-schema validation, cassette validation, tax false positives, gate defaults, baseline/unratified, ps fail-open, workflow ignoring `mode`, backend path-trigger gap, missing `raw_path` in manifest |
| low | 8 | empty-set F1/MST, dot extraction not tested, company-name over-capture, gitignore PII, empty DSH secret, dead code, `run_72h_chaos.sh` arg validation, report missing per-tag breakdown |

**Top-line risks**
1. The benchmark will **pass on the current golden cassettes** (verified by running `nowing_evals run lead_extraction regression --mode replay` and `report --suite lead_extraction` in a temporary worktree), but the `hallucination_rate` function is **mathematically wrong** for any `+84`, `84`, or obfuscated (`O`/`o`/`l`/`I`) phone that is not also in the expected set.
2. The test endpoint can be accessed in production with a hardcoded fallback secret.
3. The anti-zombie harness does not exercise the actual Chromium/browser path and omits required CLI args / logging.
4. The tax-code extractor does not match dot- or space-formatted MSTs, although the validator handles them.

---

## Findings

### CRITICAL-1: `hallucination_rate` treats correctly-extracted `+84` / `84` / obfuscated phones as hallucinations

- **Severity:** critical
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:88` (`clean_source = re.sub(r"[^\d]", "", source_text)`)
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:32-52` (`normalize_vn_phone`)
- **Evidence:**
  ```python
  def hallucination_rate(...):
      ...
      p_phones = {normalize_vn_phone(p) for p in predicted_phones if normalize_vn_phone(p)}
      e_phones = {normalize_vn_phone(e) for e in expected_phones if normalize_vn_phone(e)}
      ...
      clean_source = re.sub(r"[^\d]", "", source_text)  # line 88
  ```
- **Unhandled edge case:** `normalize_vn_phone` correctly turns `+84 912 345 678` → `0912345678`, but the source text is *not* normalized the same way. `re.sub(r"[^\d]", "", "+84 912 345 678")` produces `84912345678`, which does **not** contain `0912345678`. Similarly, `O912.345.678` becomes `912345678`, losing the leading `0`. A predicted canonical phone that is genuinely present in the source is therefore counted as a hallucination if it is absent from the expected set (e.g., an over-extraction of a valid source phone).
- **Reproduction (temporary worktree):**
  ```
  source +84: 1.0
  source o: 1.0
  ```
- **Fix / test to add:**
  - Normalize `source_text` through the same phone/tax normalization pipeline before membership tests: map `O`/`o`/`l`/`I` to digits, collapse `+84`/`84` to `0`, apply legacy 11-digit conversion, then check.
  - Add tests in `test_lead_extraction_regression.py` for `hallucination_rate` with `+84`, `84`, `O`/`o` obfuscation, legacy `016x`, spaced digits, and the `lead-002`/`lead-005`/`lead-006` style inputs.

---

### HIGH-1: Tax code extractor cannot match dot- or space-formatted MSTs

- **Severity:** high
- **Files / Lines:**
  - `nowing_backend/app/proprietary/platforms/xactions/tax_code.py:42-45` (`_KEYWORD_TAX_PATTERN`, `_STANDALONE_TAX_PATTERN`)
- **Evidence:**
  ```python
  _KEYWORD_TAX_PATTERN = re.compile(
      r"(?i:\b(?:MST|...)[^0-9\n]{0,30}?)(?P<main>\d{10})(?:[- ]?(?P<branch>\d{3}))?\b"
  )
  _STANDALONE_TAX_PATTERN = re.compile(r"\b(?P<main>\d{10})(?:[- ]?(?P<branch>\d{3}))?\b")
  ```
- **Unhandled edge case:** Both patterns require **10 consecutive digits**. The validator accepts `0100.109.106`, `0100 109 106`, and `MST: 0100.109.106` (verified by `test_formatted_tax_code_with_spaces_or_dashes`), but the extractor returns `[]` for these inputs (verified by running the regexes directly). Sources commonly format MSTs with dots or spaces.
- **Fix / test to add:**
  - Replace the rigid `\d{10}` main group with a pattern that allows optional `[.\s-]?` between 4-3-3 digit groups, e.g. `\d{4}(?:[.\s-]?\d{3}){2}` for the main code and `(?:[.\s-]?\d{3})` for the branch.
  - Add unit tests for `extract_tax_ids` with `0100.109.106`, `0100 109 106`, `0100109106-001`, `0100-109-106`, and `MST: 0100.109.106-001`.
  - Remove or use the dead `_TAX_CODE_PATTERN` at line 11.

---

### HIGH-2: Test endpoint uses a hardcoded default secret and appears in OpenAPI docs

- **Severity:** high
- **Files / Lines:**
  - `nowing_backend/app/routes/extract_entities_routes.py:15, 31-40`
- **Evidence:**
  ```python
  router = APIRouter(prefix="/api/v1/test", tags=["test-entities"])
  ...
  internal_secret = os.getenv("DSH_WORKER_SECRET", "test-internal-secret")
  is_valid_header = (
      x_internal_test is not None and x_internal_test == internal_secret
  ) or os.getenv("ENVIRONMENT") in ("test", "local")
  ```
- **Unhandled edge case:** If `DSH_WORKER_SECRET` is not configured in production, the secret is the publicly known string `"test-internal-secret"`. Additionally, `ENVIRONMENT in ("test", "local")` opens the endpoint whenever `ENVIRONMENT` is misconfigured to one of those values. The router is also mounted with `include_in_schema` defaulted to `True`, so it is published in FastAPI/Swagger docs.
- **Fix / test to add:**
  - Require an explicitly configured `DSH_WORKER_SECRET` in non-test/non-local; reject empty secrets; remove the production fallback default.
  - Set `include_in_schema=False` on the `APIRouter`.
  - Add integration tests for: missing header in production, invalid header, empty `DSH_WORKER_SECRET`, `ENVIRONMENT="test"` bypass, and `ENVIRONMENT="production"` with correct secret.

---

### HIGH-3: Run-directory and cassette writes are racy / non-atomic

- **Severity:** high
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:190-192` (`ingest` writes `cases.jsonl` non-atomically)
  - `runner.py:219-220` (`runs_dir` based on 1-second `utc_iso_timestamp()`)
  - `runner.py:227-269` (`raw.jsonl` written incrementally without flush)
  - `nowing_evals/src/nowing_evals/core/cassette.py:39-48` (`save` uses `Path.write_text`)
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:45-53` (cassette recording)
- **Evidence:**
  ```python
  with cases_file.open("w", encoding="utf-8") as f:
      for case in _DEFAULT_DATASET:
          f.write(json.dumps(case, ensure_ascii=False) + "\n")
  ...
  run_ts = utc_iso_timestamp()
  runs_dir = ctx.runs_dir(run_timestamp=run_ts)
  ```
- **Unhandled edge case:** Two `run` or `ingest` invocations in the same second get the same `runs_dir` and overwrite each other. Recording cassettes in parallel can corrupt the single `.sse.jsonl` file. `ingest` and `run_artifact.json` writes are not atomic; a killed process leaves a truncated file.
- **Fix / test to add:**
  - Add a unique run-id suffix (e.g., PID or a short UUID) to the run directory or expose `--run-id`.
  - Use `tmp + os.replace` for `cases.jsonl`, `run_artifact.json`, and cassette files.
  - Add a file lock around `ingest` when `cases.jsonl` is being generated.

---

### HIGH-4: Anti-zombie harness does not test the real scraper / Chromium lifecycle

- **Severity:** high
- **Files / Lines:**
  - `nowing_backend/scripts/chaos_scraper_stress.py:71-80, 111-125, 132-141`
  - `nowing_backend/scripts/run_72h_chaos.sh:5-18`
  - `nowing_backend/scripts/docker/healthcheck_zombie.sh:1-13`
- **Evidence:**
  ```python
  code = "import time, sys; time.sleep(0.5); sys.exit(0)"
  p = await asyncio.create_subprocess_exec(
      sys.executable, "-c", code, ...
  )
  ...
  # Filter only child zombies belonging to current process
  current_pid = os.getpid()
  child_zombies = []
  for z in zombies:
      parts = z.split()
      if len(parts) >= 2 and parts[1] == str(current_pid):
          child_zombies.append(z)
  ```
- **Unhandled edge case:** The harness spawns mock `python -c time.sleep(0.5)` workers, not real browser/scraper subprocesses. It only counts zombies whose PPID equals the stress script, which will not catch Chromium zombies that are children of the app or `tini`. It also lacks the spec-required `--duration-seconds`, `--ci`, and `--workers` arguments, does not write `zombie_log.jsonl`, and the healthcheck script is not wired into the Dockerfile.
- **Fix / test to add:**
  - Replace the mock loop with calls to a safe scraper test endpoint or a hermetic browser-launch loop.
  - Detect **all** `<defunct>` / `Z`-state processes in the container, not only direct children.
  - Add `--duration-seconds`, `--ci`, `--workers`, and `--zombie-log` arguments; make `--ci` default to 300s and the long run to `72*3600`.
  - Add `HEALTHCHECK --interval=30s CMD scripts/docker/healthcheck_zombie.sh` to the backend `Dockerfile`.
  - Create `.github/workflows/chaos-gate.yml` for the 5-minute CI version.

---

### MEDIUM-1: `run` does not validate the case schema before using it

- **Severity:** medium
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:203-230, 209-215`
- **Evidence:**
  ```python
  cases.append(json.loads(line))
  ...
  case_id = case["case_id"]
  source_text = case["source_markdown"]
  ...
  tag_filter = opts.get("tag")
  if tag_filter:
      cases = [c for c in cases if tag_filter in c.get("tags", [])]
  ```
- **Unhandled edge case:** A `cases.jsonl` entry missing `case_id` or `source_markdown` raises `KeyError`. `tags: null` causes `tag_filter in None` → `TypeError`. A `null` `source_text` reaches `hallucination_rate` and crashes `re.sub` on `None`. `case_id` containing `/` or `..` is used directly in `Path / f"{case_id}.sse.jsonl"` and can read outside `cassettes/`. Negative `--max-cases` slices from the end of the list.
- **Fix / test to add:**
  - Add a `_validate_case` helper that requires `case_id`, `source_markdown`, and coerces `tags` to a list.
  - Validate `--max-cases >= 0` and `case_id` is a safe filename.
  - Guard `hallucination_rate` for `source_text is None`.
  - Add tests for `tags: null`, `max-cases -1`, missing `case_id`, and `source_markdown: null`.

---

### MEDIUM-2: `Cassette.load` does not validate that JSON is a dict or that `body` is a dict

- **Severity:** medium
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/core/cassette.py:21-37`
- **Evidence:**
  ```python
  data = json.loads(first_line)
  return cls(
      type=data.get("type", "rest"),
      status=data.get("status", 200),
      headers=data.get("headers", {}),
      body=data.get("body", {}),
  )
  ```
- **Unhandled edge case:** If the first line is a JSON array or string, `data.get` raises `AttributeError` rather than a clear `ValueError`. If a cassette `body` is a non-dict, `ExtractorClient` returns it and the runner's `extracted.get("phones", [])` fails.
- **Fix / test to add:**
  - Add `isinstance(data, dict)` and `isinstance(data.get("body"), dict)` checks; raise `ValueError` with the cassette path.
  - Add tests for `[]`, `123`, `"string"`, and `{"type":"rest","status":200,"body":[]}` cassettes.

---

### MEDIUM-3: CLI `--mode replay` is accepted by every benchmark, even those without replay support

- **Severity:** medium
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/core/cli.py:1004-1012`
  - `nowing_evals/src/nowing_evals/core/cli.py:568-569`
- **Evidence:**
  ```python
  bp.add_argument(
      "--mode",
      choices=["live", "replay"],
      default="live",
      help="Execution mode: live (calls APIs) or replay (uses golden cassettes).",
  )
  ...
  mode = getattr(args, "mode", "live")
  needs_auth = getattr(benchmark, "requires_auth_for_run", True) and mode != "replay"
  ```
- **Unhandled edge case:** The spec (Subtask 1.5) says benchmarks that do not support replay must reject `mode=replay`. The current CLI silently passes `mode='replay'` to all benchmarks. For `chat/quality` the flag is ignored (it uses `--chat-mode`), but `RunContext.mode` is still `replay`, which is misleading and could cause non-replay suites to make live calls while the user believes they are replaying. This breaks the `$0 external API cost` guarantee for those suites.
- **Fix / test to add:**
  - Add `supports_replay: bool = False` to the `Benchmark` protocol.
  - In `_cmd_run`, raise `RuntimeError(f"{suite}/{benchmark} does not support --mode replay")` when `mode == "replay"` and `getattr(benchmark, "supports_replay", False)` is false.
  - Set `supports_replay = True` in `LeadExtractionRegressionBenchmark`.
  - Add a CLI test that tries `run chat quality --mode replay` and expects a clear error.

---

### MEDIUM-4: Standalone tax extraction can false-positive on arbitrary 10-digit numbers

- **Severity:** medium
- **Files / Lines:**
  - `nowing_backend/app/proprietary/platforms/xactions/tax_code.py:70-76`
- **Evidence:**
  ```python
  for match in _STANDALONE_TAX_PATTERN.finditer(text):
      ...
      if candidate not in seen and is_valid_vietnam_tax_code(candidate):
          seen.add(candidate)
          results.append(candidate)
  ```
- **Unhandled edge case:** About 1 in 11 random 10-digit numbers will pass the Modulo-11 check. A phone number, bank account, or order ID that happens to be valid will be extracted as a tax ID without any tax context.
- **Fix / test to add:**
  - Restrict standalone extraction to numbers near a tax keyword, company name, or other business context; or exclude numbers that match the phone regex.
  - Add a test that runs `extract_tax_ids` on 1,000 synthetic 10-digit numbers and asserts the false-positive rate is below a configured threshold, and another test that verifies known phone numbers are not extracted as tax IDs.

---

### MEDIUM-5: `evaluate_lead_extraction_gate` uses forgiving defaults for missing metrics

- **Severity:** medium
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:145-150`
- **Evidence:**
  ```python
  mst_acc = metrics.get("mst_modulo11_accuracy", 1.0)
  ```
- **Unhandled edge case:** If a run artifact is partial or a future bug causes `mst_modulo11_accuracy` to be missing, the gate defaults to `1.0` and may pass. `hallucination_rate` defaults to `0.0` (also passing) and only `f1_phone` defaults to a failing `0.0`.
- **Fix / test to add:**
  - Treat missing metrics as a gate failure: use `None` as default and append `"<metric> missing"` to `reasons` if it is `None`.
  - Add a test where `metrics = {}` and assert `passed is False` with reasons for all missing metrics.

---

### MEDIUM-6: Baseline `baseline_ratified` and `--fail-on-unratified` are ignored

- **Severity:** medium
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:286-291`
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:127-158`
- **Evidence:**
  ```python
  if gate_path.exists():
      with gate_path.open("r", encoding="utf-8") as f:
          gate_config = yaml.safe_load(f)
          thresholds = gate_config.get("thresholds", {})
  ```
- **Unhandled edge case:** `gate.yaml` contains `baseline_ratified: false`. The runner never reads this key, so there is no `--fail-on-unratified` behavior. Also, if `gate.yaml` is empty, `yaml.safe_load` returns `None`, and `gate_config.get` raises `AttributeError`.
- **Fix / test to add:**
  - Handle `gate_config is None` by setting `thresholds = {}`.
  - Add `fail_on_unratified` run arg; if `gate_config.get("baseline_ratified") is False` and the flag is set, fail even if thresholds pass.
  - Add tests for empty `gate.yaml`, `baseline_ratified: false`, and `--fail-on-unratified`.

---

### MEDIUM-7: Chaos `check_zombie_processes` fails open when `ps` cannot be queried

- **Severity:** medium
- **Files / Lines:**
  - `nowing_backend/scripts/chaos_scraper_stress.py:21-29`
- **Evidence:**
  ```python
  except Exception as e:
      print(f"Warning: failed to query ps table: {e}", file=sys.stderr)
      return []
  ```
- **Unhandled edge case:** If `ps` is missing or raises, the harness prints a warning and returns an empty list, causing `run_chaos_stress_cycle` to report the iteration as clean. This is a fail-open path.
- **Fix / test to add:**
  - Return a dedicated sentinel or raise an exception and propagate failure. The 72h wrapper should exit non-zero if `ps` is unavailable.
  - Add a unit test that monkeypatches `subprocess.check_output` to raise and asserts the stress cycle fails.

---

### MEDIUM-8: GitHub workflow `mode` input is ignored

- **Severity:** medium
- **Files / Lines:**
  - `.github/workflows/lead-extraction-regression-gate.yml:17-21, 47-49`
  - `nowing_evals/scripts/run-hermetic-gate.sh:6`
- **Evidence:**
  ```yaml
  workflow_dispatch:
    inputs:
      mode:
        description: 'Benchmark execution mode (replay or live)'
        required: true
        default: 'replay'
  ...
  run: ./scripts/run-hermetic-gate.sh
  ```
  ```bash
  uv run python -m nowing_evals run lead_extraction regression --mode replay
  ```
- **Unhandled edge case:** A manual workflow dispatch with `mode: live` silently runs in `--mode replay`.
- **Fix / test to add:**
  - Pass `mode` to the script and the benchmark: `run: NOWING_JWT=dummy uv run python -m nowing_evals run lead_extraction regression --mode ${{ github.event.inputs.mode }}`.
  - Or remove the input if the gate is intended to always be replay.

---

### MEDIUM-9: Backend path triggers do not catch extractor regressions in replay-only CI

- **Severity:** medium
- **Files / Lines:**
  - `.github/workflows/lead-extraction-regression-gate.yml:8-15`
- **Evidence:** The workflow runs `--mode replay` against committed cassettes. It triggers on changes to `tax_code.py`, `phone_extractor.py`, and `lead_extraction_service.py`.
- **Unhandled edge case:** If a PR changes the backend extractor, the CI still replays old cassettes and may pass even though the live endpoint would now produce different output. The cassettes will silently drift from the backend.
- **Fix / test to add:**
  - On backend path changes, run the benchmark in `--mode live` (or with `RECORD_CASSETTES=true`) and fail if the live output differs from the committed cassettes by more than a tolerance.
  - Alternatively, record cassettes as an artifact and run a diff check in CI.

---

### MEDIUM-10: `run_artifact.json` omits `raw_path`

- **Severity:** medium
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:311-322`
- **Evidence:**
  ```python
  json.dump(
      {
          "suite": self.suite,
          "benchmark": self.name,
          "run_timestamp": run_ts,
          "metrics": metrics,
          "extra": extra,
      },
      f,
      indent=2,
  )
  ```
- **Unhandled edge case:** The manifest does not contain `raw_path`. The `report` command happens to default to `bench_dir / "raw.jsonl"`, but this is inconsistent with `chat/regression` and `chat/quality`, which write `raw_path: "raw.jsonl"` explicitly. Future consumers or a change in raw-path layout will break.
- **Fix / test to add:**
  - Include `"raw_path": str(raw_path.name)` (or `"raw.jsonl"`) in the JSON.
  - Use the existing `_write_json_atomic` helper pattern from `chat/regression/runner.py`.

---

### LOW-1: `f1_phone` and `mst_modulo11_accuracy` return 1.0 when both sets/lists are empty

- **Severity:** low
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:60-61`
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:111-112`
- **Evidence:**
  ```python
  if not p_set and not e_set:
      return 1.0
  ...
  if not predicted_valid and not expected_valid:
      return 1.0
  ```
- **Unhandled edge case:** A dataset of 10 cases with no phones and no tax IDs will report `f1_phone=1.0` and `mst_modulo11_accuracy=1.0` and can pass the gate with `total_cases=10`, even though no extraction was exercised.
- **Fix / test to add:**
  - Add `min_phone_cases` and `min_tax_cases` thresholds to `gate.yaml`, or weight the averages by actual entity counts.
  - Add tests for an all-empty dataset that should fail.

---

### LOW-2: Dot- and space-formatted MSTs are tested in `is_valid` but not in `extract_tax_ids`

- **Severity:** low
- **Files / Lines:**
  - `nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py:30-38`
- **Evidence:** The test `test_formatted_tax_code_with_spaces_or_dashes` calls `is_valid_vietnam_tax_code`, not `extract_tax_ids`.
- **Unhandled edge case:** The suite tests the validator but never verifies the extractor handles the same formats.
- **Fix / test to add:**
  - Add an `extract_tax_ids` test for the same dot/space/dash/prefix formats.

---

### LOW-3: Company-name extraction may capture generic keywords without an actual name

- **Severity:** low
- **Files / Lines:**
  - `nowing_backend/app/services/lead_extraction_service.py:35-48`
- **Evidence:**
  ```python
  candidate = match.group(0).strip()[:255]
  if len(candidate) > 4:
      return candidate
  ```
- **Unhandled edge case:** A line such as `Công ty TNHH` with no following name produces a candidate longer than 4 characters and is returned as the company name.
- **Fix / test to add:**
  - Require the match to contain at least one additional token after the company keyword (e.g., ensure there are at least 2 words and one is not a keyword).
  - Add tests for `Công ty`, `TNHH`, and a valid company line.

---

### LOW-4: Cassettes can be committed with unsanitized PII

- **Severity:** low
- **Files / Lines:**
  - `nowing_evals/data/.gitignore:40-44`
- **Evidence:**
  ```gitignore
  !lead_extraction/regression/cassettes/
  !lead_extraction/regression/cassettes/*.sse.jsonl
  ```
- **Unhandled edge case:** The gitignore whitelists any `.sse.jsonl` in the cassettes directory. A `live` recording run can overwrite golden cassettes with real PII, and a `git add .` would commit them.
- **Fix / test to add:**
  - Add a `nowing_evals/scripts/sanity-check-cassettes.py` script (or CI step) that rejects real-looking VN phone/tax patterns, requires `company_name` to be synthetic, and run it in `lead-extraction-regression-gate.yml` before the gate.

---

### LOW-5: Benchmark client falls back to hardcoded `DSH_WORKER_SECRET` too

- **Severity:** low
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:33-34`
- **Evidence:**
  ```python
  secret = os.getenv("DSH_WORKER_SECRET", "test-internal-secret")
  headers = {"X-Internal-Test": secret}
  ```
- **Unhandled edge case:** If `DSH_WORKER_SECRET` is unset during a live run, the client uses the same public fallback. If it is empty, the header is empty and may be accepted by the backend if the backend secret is also empty.
- **Fix / test to add:**
  - Do not default in `extractor_client.py`; raise `RuntimeError` when `DSH_WORKER_SECRET` is unset or empty in live mode.
  - Add tests for unset and empty secrets.

---

### LOW-6: Dead / unused code in `chaos_scraper_stress.py`

- **Severity:** low
- **Files / Lines:**
  - `nowing_backend/scripts/chaos_scraper_stress.py:41-55, 68-69`
- **Evidence:**
  ```python
  async def spawn_mock_scraper_worker(worker_id: int, duration_sec: float) -> int:
      ...
  ```
- **Unhandled edge case:** The function is defined and the `tasks` / `worker_id` variables are unused. It is confusing and may be a leftover from a planned implementation.
- **Fix / test to add:**
  - Remove `spawn_mock_scraper_worker` and the unused `tasks` list, or integrate it into the stress cycle.

---

### LOW-7: `run_72h_chaos.sh` does not validate numeric arguments

- **Severity:** low
- **Files / Lines:**
  - `nowing_backend/scripts/run_72h_chaos.sh:5-6`
- **Evidence:**
  ```bash
  DURATION_HOURS="${1:-72}"
  INTERVAL_SEC="${2:-30}"
  ```
- **Unhandled edge case:** Passing a non-numeric value (e.g., `abc`) causes `END_TIME=$((...))` to fail with an unhelpful shell error.
- **Fix / test to add:**
  - Validate both args with a regex or `case` statement and print usage on invalid input.

---

### LOW-8: Report does not include per-tag breakdown

- **Severity:** low
- **Files / Lines:**
  - `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:329-356`
- **Evidence:** The `report_section` renders only aggregate metrics.
- **Unhandled edge case:** The spec (Subtask 3.8) asks for per-tag breakdown and pass/fail. A failing tag can be hidden in the aggregate.
- **Fix / test to add:**
  - Compute per-tag F1, hallucination, and MST accuracy and include a markdown table in `report_section`.
  - Add a test asserting per-tag keys are present in `body_json`.

---

## Unimplemented / Out-of-Scope Spec Items

The following tasks from the spec were not addressed in the diff and are not edge cases of the added code, but they are required for AC-2:

- **Task 6 (60s hard timeouts):** `nowing_backend/app/tasks/dsh_worker.py`, scraper modules, and `app/services/phone_waterfall_service.py` are unchanged. The test endpoint has the `httpx` default 60s only on the client side, not a server-side guarantee.
- **Task 5.4 (CI chaos workflow):** `.github/workflows/chaos-gate.yml` is missing.
- **Task 7.1:** The existing `tests/unit/proprietary/platforms/xactions/test_phone_extractor.py` is not extended with the `TestPhoneExtractionHermetic` class.
- **Task 7.2:** `tests/integration/services/test_lead_extraction_hermetic.py` is missing.

---

## Appendix: Temporary Worktree Validation

A copy of the repo was patched into `/tmp/nowing-review-26-7` for line-number extraction and targeted runtime checks. Relevant commands run:

```bash
cd /tmp/nowing-review-26-7/nowing_evals
uv run pytest tests/core/test_cassette.py tests/suites/test_lead_extraction_regression.py -q  # 9 passed
uv run python -m nowing_evals run lead_extraction regression --mode replay  # run OK
uv run python -m nowing_evals report --suite lead_extraction  # report OK
uv run python -c "
from nowing_evals.suites.lead_extraction.regression.metrics import hallucination_rate
print('source +84:', hallucination_rate({'0987654321'}, set(), 'Alo ngay +84 987 654 321', set(), set()))
print('source o:', hallucination_rate({'0912345678'}, set(), 'Hotline O912.345.678', set(), set()))
"
# source +84: 1.0
# source o: 1.0

uv run python -c "
import re
p1 = re.compile(r'(?i:\b(?:MST|Mã\\s*số\\s*thuế|Mã\\s*số\\s*DN|MSDN|Mã\\s*số\\s*doanh\\nghiệp|Tax\\s*ID|Tax\\s*code)[^0-9\\n]{0,30}?)(?P<main>\d{10})(?:[- ]?(?P<branch>\d{3}))?\b')
p2 = re.compile(r'\b(?P<main>\d{10})(?:[- ]?(?P<branch>\d{3}))?\b')
for text in ['MST: 0100 109 106', 'MST: 0100.109.106']:
    print(text, [m.groupdict() for m in p1.finditer(text)] + [m.groupdict() for m in p2.finditer(text)])
"
# MST: 0100 109 106 []
# MST: 0100.109.106 []
```

The worktree is not part of the delivered source tree and can be safely removed.
