# Blind Hunter Review — Story 26.7

**Project:** nowing  
**Reviewed diff:** `_bmad-output/test-artifacts/review-26-7.diff` (1713 lines)  
**Spec:** `_bmad-output/implementation-artifacts/26-7-hermetic-quality-gates-benchmark-anti-zombie.md`  
**Date:** 2026-08-19

---

## Executive Summary

This diff ships the **hermetic lead-extraction replay benchmark** mostly intact, but the **anti-zombie / 72-hour stress work is largely theatre**: the harness only spawns mock Python subprocesses and never exercises the real scraper, Chromium, `dsh_worker`, or the 60-second timeout paths. Several parts of the diff are *too good to be true* — the committed cassettes are byte-for-byte the expected dataset, the `mst_modulo11_accuracy` metric can pass with no tax extraction at all, and the new `POST /api/v1/test/extract-entities` endpoint is guarded by a hardcoded fallback secret and a `test`/`local` environment bypass.

Top concerns:
1. **Security:** the test-extraction endpoint is a public PII-extraction API with a weak header check and a default secret baked into source.
2. **CLI regression:** the new global `--mode` flag leaks into every benchmark's `**opts`, immediately breaking `chat/quality`.
3. **AC-2 is not verified:** no real scraper stress, no 60 s timeout audit, no tini/WAL checks, no CI workflow.
4. **Metric logic bugs:** hallucination over-counts `+84`/obfuscated numbers; MST accuracy is index-computed and can pass with zero tax output.
5. **Mirror tests:** the replay suite will always pass because the cassettes *are* the expected answers.

---

## Severity Counts

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 5 |
| Medium | 8 |
| Low | 6 |

---

## Critical

### 1. Test endpoint is a public PII-extraction API with a hardcoded default secret

**File / Line:** `nowing_backend/app/routes/extract_entities_routes.py:15, 31-34`

```python
router = APIRouter(prefix="/api/v1/test", tags=["test-entities"])
...
internal_secret = os.getenv("DSH_WORKER_SECRET", "test-internal-secret")
is_valid_header = (
    x_internal_test is not None and x_internal_test == internal_secret
) or os.getenv("ENVIRONMENT") in ("test", "local")
```

**Impact:** The endpoint is mounted in the public `crud_router` with no Nowing auth and no IP allowlist. It accepts up to 100 000 characters of arbitrary text and returns normalized phone numbers, tax IDs, and company names — i.e. a free, un-rate-limited PII extraction service. If `DSH_WORKER_SECRET` is unset, the default `test-internal-secret` is in the repo; anyone who reads the code can call it. In `test` or `local` `ENVIRONMENT`, the header is not required at all. The route also has `include_in_schema=False` missing, so it will appear in public OpenAPI docs.

**Fix:**
- Do not provide a default secret; fail closed when `DSH_WORKER_SECRET` is unset.
- Use a dedicated `TEST_EXTRACTION_SECRET`, not the worker secret.
- Remove the `ENVIRONMENT` bypass or restrict it to a separate integration-test launcher that never runs in production.
- Add `include_in_schema=False` to the decorator.
- Add rate limiting and request-size / concurrency throttling.

---

### 2. Global `--mode` flag leaks into benchmark `**opts` and breaks `chat/quality`

**File / Line:** `nowing_evals/src/nowing_evals/core/cli.py:546-550`, `568-569`, `594-596`, `1004-1009`; `nowing_evals/src/nowing_evals/suites/chat/quality/runner.py:475`

```python
# cli.py
extra_kwargs = {
    k: v
    for k, v in vars(args).items()
    if k not in {"_func", "_async", "command", "subcommand", "suite", "benchmark", "log_level"}
}
...
mode = getattr(args, "mode", "live")
...
ctx = registry.RunContext(..., mode=getattr(args, "mode", "live"))
artifact = await benchmark.run(ctx, **extra_kwargs)
```

```python
# chat/quality/runner.py
mode = str(opts.get("chat_mode") or opts.get("mode") or "balanced")
valid_modes = {"speed", "balanced", "quality", "auto"}
if mode not in valid_modes:
    raise RuntimeError(f"Invalid --mode: {mode}. Allowed: {', '.join(sorted(valid_modes))}.")
```

**Impact:** `bp.add_argument("--mode", ...)` is added to *every* `run` subparser, and `extra_kwargs` forwards it to every `benchmark.run`. In `chat/quality`, `opts.get("mode")` is now `"live"`, which is not in `valid_modes`, so the runner raises. This is a regression in a completely unrelated suite. `python -m nowing_evals run chat quality --help` now shows two conflicting flags (`--mode` and `--chat-mode`).

**Fix:** Either (a) exclude `"mode"` from `extra_kwargs` in `_cmd_run` and rely on `ctx.mode`, or (b) remove the `opts.get("mode")` fallback in `chat/quality` and any other benchmark. The harness concept of `mode` should live on `RunContext`, not be forwarded as a benchmark option.

---

### 3. `LeadExtractionRegressionBenchmark` disables run auth in contradiction with the spec

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:170`

```python
class LeadExtractionRegressionBenchmark:
    ...
    requires_auth_for_run = False
```

**Impact:** The spec explicitly decided `requires_auth_for_run = True` because live mode calls the backend. Setting it to `False` means `nowing_evals run lead_extraction regression` (live) will use an unauthenticated `httpx.AsyncClient` and call the test endpoint without a Nowing bearer. Combined with finding #1, an operator can extract PII from arbitrary text with no user identity, no audit trail, and only the `X-Internal-Test` header.

**Fix:** Set `requires_auth_for_run = True`. The CLI already correctly short-circuits auth in replay via `mode != "replay"` (`cli.py:569`).

---

## High

### 4. `hallucination_rate` treats `+84` and obfuscated phones as hallucinations

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:88, 96-98`

```python
clean_source = re.sub(r"[^\d]", "", source_text)
...
for phone in p_phones:
    if phone not in e_phones and phone not in clean_source:
        hallucinated += 1
```

**Impact:** A phone present in the source as `+84 987 654 321` becomes `84987654321` in `clean_source`, while the normalized prediction is `0987654321`. The substring check fails, so a real phone can be counted as a hallucination unless it is in `expected_phones`. Spelled-out Vietnamese digits (`"không chín ..."`) are stripped to unrelated numbers, also producing false positives. **Confirmed:**

```text
$ cd nowing_evals && python -c "
from nowing_evals.suites.lead_extraction.regression.metrics import hallucination_rate
print(hallucination_rate(['0987654321'], [], 'Call +84 987 654 321', [], []))
"
1.0
```

**Fix:** Build a normalized token set from `source_text` using the same `phone_extractor` normalization (letter-to-digit map, `+84`/`84` conversion, legacy prefix conversion, delimiter stripping) and check set membership, not a raw digit-substring search. Do the same for tax IDs.

---

### 5. `mst_modulo11_accuracy` and runner aggregation are wrong and can pass with no tax output

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:107-120`; `runner.py:249-255, 275`

```python
# metrics.py
def mst_modulo11_accuracy(predicted_valid: list[bool], expected_valid: list[bool] | None = None) -> float:
    if not predicted_valid and not expected_valid:
        return 1.0
    ...
    correct = sum(1 for p, e in zip(predicted_valid, expected_valid, strict=True) if p == e)
```

```python
# runner.py
expected_tax_valid = case.get("expected_tax_ids_valid")
case_mst_acc = mst_modulo11_accuracy(tax_ids_valid, expected_tax_valid)
...
if expected_tax_valid is not None and (tax_ids_valid or expected_tax_valid):
    all_tax_valid.append(case_mst_acc)
...
avg_mst_acc = round(sum(all_tax_valid) / len(all_tax_valid), 4) if all_tax_valid else 1.0
```

**Impact:**
- `mst_modulo11_accuracy([], [])` returns `1.0`.
- The runner **excludes** no-tax cases from `all_tax_valid` when both predicted and expected are empty, then falls back to `1.0` for the aggregate. A model that extracts zero tax IDs across all cases would pass the `0.995` MST gate.
- The metric compares `tax_ids_valid` to `expected_tax_ids_valid` by list index, not the spec-defined "fraction of returned tax IDs where `tax_ids_valid[i]` is True". If the model returns a different *valid* tax ID than expected, it is scored `0.0`.

**Confirmed:**

```text
$ cd nowing_evals && python -c "
from nowing_evals.suites.lead_extraction.regression.metrics import mst_modulo11_accuracy
print(mst_modulo11_accuracy([], []))
"
1.0
```

**Fix:** Implement the metric exactly as the spec states: `sum(tax_ids_valid) / len(tax_ids_valid)` for each case, with `1.0` when there are zero predicted tax IDs. Include every case in the aggregate; do not index-compare to `expected_tax_ids_valid`.

---

### 6. `extract_tax_ids` cannot extract spaced or formatted tax codes and may extract phone numbers

**File / Line:** `nowing_backend/app/proprietary/platforms/xactions/tax_code.py:42-45, 60-76`

```python
_KEYWORD_TAX_PATTERN = re.compile(
    r"(?i:\b(?:MST|Mã\s*số\s*thuế|...)[^0-9\n]{0,30}?)(?P<main>\d{10})(?:[- ]?(?P<branch>\d{3}))?\b"
)
_STANDALONE_TAX_PATTERN = re.compile(r"\b(?P<main>\d{10})(?:[- ]?(?P<branch>\d{3}))?\b")
```

**Impact:** Both regexes require 10 *contiguous* digits. `is_valid_vietnam_tax_code()` correctly strips spaces/dashes/prefixes, but `extract_tax_ids` will never match `Mã số thuế: 0100 109 106` or `0100-109-106` because the digits are not contiguous. The `test_tax_code.py` tests only validate the *validator*, not the *extractor*. Conversely, `_STANDALONE_TAX_PATTERN` will match any 10-digit number; if a phone number happens to pass Modulo-11 (≈9% chance), it becomes a tax ID. No timeout guard is applied while searching a 100 000-character input.

**Fix:** Pre-normalize the input by stripping common tax delimiters and prefixes before regex matching, or reuse a shared normalization function. Limit the standalone matcher to contexts with tax keywords or known numeric contexts, and add a per-call timeout.

---

### 7. Anti-zombie / 72-hour stress test does not exercise the real system under test

**File / Line:** `nowing_backend/scripts/chaos_scraper_stress.py:1-153`; `nowing_backend/scripts/run_72h_chaos.sh:1-18`; missing `.github/workflows/chaos-gate.yml`

```python
# chaos_scraper_stress.py
async def spawn_mock_scraper_worker(worker_id: int, duration_sec: float) -> int:
    ...
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time, sys; time.sleep(0.5); sys.exit(0)", ...
    )
```

**Impact:** AC-2 requires a 72-hour scraping stress test with 0 zombie Chromium processes, 60 s hard timeouts on `httpx`/browser/Redis `XREADGROUP`, tini PID 1, and WAL limits. The diff:
- Only spawns short `python -c "time.sleep(0.5)"` child processes.
- Never calls `dsh_worker`, a scraper capability, Playwright, or Redis.
- Has no `--duration-seconds`, `--ci`, or `--workers` flags per the spec.
- `run_72h_chaos.sh` runs only 8 concurrency × 3 iterations every 30 s, not continuous load.
- No `zombie_log.jsonl` is written.
- No `.github/workflows/chaos-gate.yml` exists.
- No verification of `tini` PID 1 or PostgreSQL `max_slot_wal_keep_size`/`wal_keep_size`.

**Fix:** Either make the harness actually drive the scraper/browser stack at production-like load, or rename it and add real verification tests for each AC-2 acceptance criterion. Add the missing CI workflow.

---

### 8. `ExtractorClient` records cassettes without sanitization and uses a hardcoded worker secret

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:33, 42-53`

```python
secret = os.getenv("DSH_WORKER_SECRET", "test-internal-secret")
headers = {"X-Internal-Test": secret}
...
should_record = (
    getattr(self.ctx, "record", False) or os.getenv("RECORD_CASSETTES") == "true"
)
if should_record:
    cassette = Cassette(type="rest", status=resp.status_code, headers=dict(resp.headers), body=body)
    cassette.save(cassette_path)
```

**Impact:** `getattr(self.ctx, "record", False)` is always `False` because `RunContext` has no `record` attribute. Recording is only possible via an undocumented `RECORD_CASSETTES` environment variable. When recording happens, the response body is written as-is to `data/lead_extraction/regression/cassettes/`; real PII is not sanitized before being written, and the directory is whitelisted in `.gitignore`, creating a real risk of committing unsanitized PII.

**Fix:** Add a `--record` / `--record-cassettes` CLI flag wired to `RunContext`. Implement a sanitizer that replaces phone/tax/company values with synthetic equivalents while preserving shape. Add a pre-commit / CI check that rejects real-looking PII in cassettes.

---

## Medium

### 9. `case_id` is used directly in a filesystem path, allowing cassette path traversal

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:23, 46`

```python
cassette_path = self.cassettes_dir / f"{case_id}.sse.jsonl"
```

**Impact:** A malicious or malformed `cases.jsonl` containing `case_id = "../../../etc/passwd"` will cause the replay client to try to load `data/lead_extraction/regression/cassettes/.../.../.../etc/passwd.sse.jsonl`. This is a local file-read primitive.

**Fix:** Validate `case_id` against a strict allowlist (e.g. `^[a-zA-Z0-9_-]+$`) and/or `Path.resolve()` within `self.cassettes_dir` and reject paths that escape.

---

### 10. `test_extract_entities_routes.py` does not cover the actual attack surface

**File / Line:** `nowing_backend/tests/integration/routes/test_extract_entities_routes.py:38-53`

**Impact:** The integration tests only check (a) success with correct header and (b) failure with an *invalid* header in `ENVIRONMENT=production`. They do **not** test:
- Missing header in production.
- The default `DSH_WORKER_SECRET` fallback (`test-internal-secret`).
- `ENVIRONMENT=test` or `ENVIRONMENT=local` bypassing the header entirely.
- `include_in_schema=False` behavior.
- Large / malformed payloads.
- Whether the route is rate-limited.

**Fix:** Add adversarial tests for missing header, default secret, and environment bypass. Add a test that asserts the route is *not* in the public OpenAPI schema.

---

### 11. `test_tax_code.py` uses only two known-good tax codes and does not test extraction edge cases

**File / Line:** `nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py:11-83`

```python
# Known valid tax codes
assert is_valid_vietnam_tax_code("0100109106") is True  # Viettel Group
assert is_valid_vietnam_tax_code("0300588569") is True  # FPT HCM
```

**Impact:** The spec requires validating against 100 known-good masothue fixtures before ratification. The test has only two. It also tests `is_valid_vietnam_tax_code()` on formatted strings but does **not** test that `extract_tax_ids()` can recover spaced/dashed/prefixed tax IDs, or that it does not extract phone numbers.

**Fix:** Load the masothue fixture set and run positive/negative cases. Add extraction tests for `MST: 0100 109 106`, `0100-109-106`, `MST: 0100109106-001`, and phone numbers that happen to be 10 digits.

---

### 12. `LeadExtractionRegressionBenchmark` tests are mostly mirror tests

**File / Line:** `nowing_evals/tests/suites/test_lead_extraction_regression.py:1-93`; `nowing_evals/data/lead_extraction/regression/cassettes/*.sse.jsonl`

**Impact:** The unit tests only exercise `f1_phone`, `hallucination_rate`, `mst_modulo11_accuracy`, and `evaluate_lead_extraction_gate` with hand-picked inputs. The committed cassettes are byte-for-byte the expected outputs from `cases.jsonl`, so running `nowing_evals run lead_extraction regression --mode replay` is tautological:

```text
$ cd nowing_evals && uv run python -m nowing_evals run lead_extraction regression --mode replay
run OK lead_extraction/regression → .../raw.jsonl
$ cat data/lead_extraction/runs/.../regression/run_artifact.json
{ "metrics": { "f1_phone": 1.0, "hallucination_rate": 0.0, "mst_modulo11_accuracy": 1.0 }, "extra": { "passed": true } }
```

There is no test for `ExtractorClient.live()`, `ExtractorClient.replay()`, missing cassettes, or the `run()` method end-to-end.

**Fix:** Add a test that records a live cassette, scrubs it, replays it, and asserts the run still passes. Add tests for missing cassettes, 403 from the endpoint, and a mock HTTP client with respx.

---

### 13. `extract_entities_routes.py` violates the route-prefix convention, producing duplicate mount paths

**File / Line:** `nowing_backend/app/routes/extract_entities_routes.py:15`; `nowing_backend/app/routes/__init__.py:255`; `nowing_backend/app/app.py:1193-1195`

```python
router = APIRouter(prefix="/api/v1/test", tags=["test-entities"])
```

```python
# app.py
app.include_router(crud_router, prefix="/api/v1", tags=["crud"])
app.include_router(crud_router, prefix="/api", tags=["crud"])
app.include_router(crud_router)
```

**Impact:** No other route file in `app/routes/` hard-codes an `/api/v1` prefix. Because `crud_router` is mounted at `/api/v1`, `/api`, and root, this creates the unintended paths `/api/v1/api/v1/test/extract-entities` and `/api/api/v1/test/extract-entities` in addition to the intended `/api/v1/test/extract-entities`. This is confusing and brittle.

**Fix:** Change the router prefix to `/test` (or nothing) so `crud_router` mounting produces the correct path consistently, matching the rest of the codebase.

---

### 14. `LeadExtractionService.extract_from_text` has no timeout guard for tax extraction

**File / Line:** `nowing_backend/app/services/lead_extraction_service.py:50-64`

```python
def extract_from_text(self, text: str | None) -> ExtractedEntities:
    ...
    phones = self.extractor.extract_phones(text)
    tax_ids = extract_tax_ids(text)
    tax_ids_valid = [is_valid_vietnam_tax_code(t) for t in tax_ids]
    company_name = self.extract_company_name(text)
```

**Impact:** `extract_phones` has a 50 ms ReDoS guard and 200 k character cap. `extract_tax_ids` and `extract_company_name` have no equivalent guard. A 100 000-character adversarial input could hang the FastAPI worker long enough to violate the 60 s hard-timeout requirement (which itself is not implemented anywhere in this diff).

**Fix:** Wrap the tax/company extraction in `asyncio.to_thread` with `asyncio.wait_for(timeout=60.0)`, or add an explicit per-call timeout to the regex functions.

---

### 15. `LeadExtractionRegressionBenchmark` does not validate the dataset or gate baseline

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:185-194, 203-215, 285-291`

**Impact:**
- `ingest()` blindly overwrites `cases.jsonl` from `_DEFAULT_DATASET` without validating required fields or `case_id` uniqueness.
- `run()` accesses `case["case_id"]` and `case["source_markdown"]` directly; a malformed row raises `KeyError`.
- `gate.yaml` has `baseline_ratified: false` and a `baseline_source` field, but `evaluate_lead_extraction_gate()` and `run()` ignore them. There is no `--fail-on-unratified` behavior as in `chat/quality`.

**Fix:** Add `pydantic` or manual validation for the dataset schema. Respect `baseline_ratified` and `fail_on_unratified`.

---

### 16. `Cassette` loader is fragile and the `.sse.jsonl` format is misleading

**File / Line:** `nowing_evals/src/nowing_evals/core/cassette.py:21-37, 39-48`

```python
@dataclass
class Cassette:
    type: str = "rest"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)

content = p.read_text(encoding="utf-8").strip()
first_line = content.splitlines()[0]
data = json.loads(first_line)
```

**Impact:** The spec says cassettes are `.sse.jsonl` but each file contains a single JSON object. The loader only reads the first line and does not validate that `body` contains the expected `phones`, `tax_ids`, `tax_ids_valid`, and `company_name` keys. It also does not implement loading generic `*.jsonl` multi-line cassettes as mentioned in the spec.

**Fix:** Add a schema validator for cassette bodies. Support multi-line JSONL or rename the extension to `.json`. Reject cassettes with unexpected top-level keys.

---

## Low

### 17. `nowing_evals` and backend share the same fallback secret

**File / Line:** `nowing_backend/app/routes/extract_entities_routes.py:31`; `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:33`

**Impact:** The eval client reuses `DSH_WORKER_SECRET` as its auth header for the test endpoint. This conflates two different trust boundaries (worker internal auth and benchmark test auth) and means a leak of either secret exposes both.

**Fix:** Use a separate `TEST_EXTRACTION_SECRET` environment variable and never fall back to a default.

---

### 18. `run_72h_chaos.sh` and `chaos_scraper_stress.py` hardcode parameters and are sparse

**File / Line:** `nowing_backend/scripts/run_72h_chaos.sh:12-15`; `nowing_backend/scripts/chaos_scraper_stress.py:132-136`; `nowing_backend/scripts/docker/healthcheck_zombie.sh:5-6`

**Impact:** The 72-hour "stress" is just 3 short iterations every 30 seconds. `healthcheck_zombie.sh` counts any `Z` state process, not specifically Chromium/browser processes, which can make a Dokploy container unhealthy for unrelated zombie noise.

**Fix:** Implement the `--duration-seconds`, `--ci`, and `--workers` CLI per the spec. Make the healthcheck filter for `chrome`, `chromium`, or browser PPID relationships.

---

### 19. `metrics.py` duplicates phone-normalization logic instead of reusing `phone_extractor`

**File / Line:** `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/metrics.py:7-52`

**Impact:** The legacy 11-digit map and `+84`/`84` normalization are duplicated from `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py`. If the production extractor changes (e.g. new prefixes), the benchmark will drift out of sync and report false F1/hallucination scores.

**Fix:** Export a shared `normalize_vn_phone()` from `phone_extractor.py` and import it in `metrics.py`.

---

### 20. Workflow dispatch `mode` input is unused

**File / Line:** `.github/workflows/lead-extraction-regression-gate.yml:18-21, 47-49`

```yaml
workflow_dispatch:
  inputs:
    mode:
      description: 'Benchmark execution mode (replay or live)'
      required: true
      default: 'replay'
...
- name: Run hermetic replay gate
  working-directory: nowing_evals
  run: ./scripts/run-hermetic-gate.sh
```

**Impact:** The manual workflow allows selecting `mode` but always runs the hardcoded replay script. This is dead UI.

**Fix:** Pass the input to the script (`./scripts/run-hermetic-gate.sh ${{ inputs.mode }}`) or remove the input.

---

### 21. Dead code and style issues

**File / Line:**
- `nowing_backend/app/proprietary/platforms/xactions/tax_code.py:11` — `_TAX_CODE_PATTERN` is compiled but never used.
- `nowing_backend/scripts/chaos_scraper_stress.py:41-55` — `spawn_mock_scraper_worker` is defined but never called.
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/runner.py:341` — `report_section` uses emoji (`✅ PASS` / `❌ FAIL`) in CLI markdown.
- `nowing_evals/src/nowing_evals/suites/lead_extraction/regression/extractor_client.py:43` — `getattr(self.ctx, "record", False)` is always `False` because `RunContext` has no `record` field.

**Fix:** Remove unused symbols or use them; remove emojis unless explicitly required; add `record: bool = False` to `RunContext` if the recording path is meant to be CLI-driven.

---

## Verdict

**Do not merge as-is.**

The hermetic replay benchmark is structurally sound and will pass in CI, but it is currently a self-fulfilling prophecy (golden cassettes == expected outputs) with a dangerously weak endpoint guard. The `chat/quality` CLI regression and the global `--mode` leak are blockers. The anti-zombie / 72-hour stress work does not satisfy AC-2 and gives false assurance.

Minimum acceptance before merge:
1. Fix or remove the `extract-entities` endpoint exposure; no hardcoded default, no `ENVIRONMENT` bypass, `include_in_schema=False`.
2. Stop leaking `--mode` into `extra_kwargs` and fix `chat/quality`.
3. Implement the MST metric per the spec (fraction of returned valid tax IDs, not index-compare to expected).
4. Fix `hallucination_rate` source normalization.
5. Make the chaos harness real or scope it honestly: either drive the actual scraper/browser stack and verify 60 s timeouts, tini PID 1, and WAL limits, or drop the AC-2 claims and the `72h` naming.
6. Add adversarial tests for the endpoint, the cassette loader, and the metric edge cases.
