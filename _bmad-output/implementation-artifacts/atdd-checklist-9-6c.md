# ATDD Checklist — 9-6c

> Output target was `_bmad-output/test-artifacts/atdd-checklist-9-6c.md`, but `test-artifacts/` is gitignored. Saved here as fallback.

## AC-1: Run-derived memory populates source recipe

### Pattern 1 (Mirror)
- [ ] should set `source_type` to exactly `MemorySourceType.SCRAPER_RUN`, not `CHAT_MESSAGE` or `MANUAL`
- [ ] should set `source_run_id` to the exact `Run.id` UUID, not a string or null
- [ ] should set `source_capability` to exactly `run.capability`, not a hard-coded value
- [ ] should set `source_input` as a deep copy of `run.input`, not a reference that mutates later
- [ ] should set `source_id` to `None` for scraper-run memories

### Pattern 2 (Over-Mocking)
- [ ] should handle `run.input = None` and still set `source_type` / `source_capability`
- [ ] should handle `get_agent_llm` returning a mock that extracts zero facts
- [ ] should handle `get_agent_llm` raising and leave no memory

### Pattern 3 (Happy Path Only)
- [ ] Boundary: `run.input` is an empty dict `{}`
- [ ] Boundary: `run.input` is a list `[]`
- [ ] Null/empty: `run.input = None`
- [ ] Null/empty: `run.capability = ""`

### Pattern 4 (Arithmetic)
- [ ] N/A for AC-1

### Pattern 5 (Error message)
- [ ] should raise / log with `Run` id when extraction fails

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should insert `Memory` row with `source_type, source_run_id, source_capability, source_input` populated (real DB)
- [ ] should verify recipe persisted in Postgres JSONB

---

## AC-2: Post-cleanup revalidation succeeds using only the recipe

### Pattern 1 (Mirror)
- [ ] should return `MemoryRead` with `confidence` updated
- [ ] should create `MemoryVersion` with `previous_content` and `corrected_content` matching old and new text
- [ ] should NOT return the deleted `Run`
- [ ] should keep `source_input` unchanged after revalidation

### Pattern 2 (Over-Mocking)
- [ ] should handle executor raising `RuntimeError` → `RevalidationResult(status="failed")`, not 500
- [ ] should handle `execute_with_context` returning `None`
- [ ] should handle `execute_with_context` returning an empty string

### Pattern 3 (Happy Path Only)
- [ ] Boundary: memory `confidence` already at `1.0` → match clamps to `1.0`
- [ ] Boundary: memory `confidence` already at `0.1` → mismatch clamps to `0.1`
- [ ] Concurrent: two revalidations on the same memory

### Pattern 4 (Arithmetic)
- [ ] should compute match confidence as exactly `round(min(1.0, confidence + (1.0 - confidence) * 0.2), 4)`
- [ ] should compute mismatch confidence as exactly `max(0.1, confidence * 0.8)`
- [ ] should record `cost_micros` exactly equal to `charge_capability` return value

### Pattern 5 (Error message)
- [ ] should return 422 with `code="not_revalidatable"` when recipe missing
- [ ] should return 422 with `code="invalid_recipe"` when schema mismatch

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should delete source `Run` then revalidate and still update `Memory.confidence` (real DB)
- [ ] should create `MemoryVersion` row on mismatch (real DB)
- [ ] should create new `Run` row with `origin="revalidate"` and `cost_micros` (real DB)

---

## AC-3: Non-revalidatable sources return 422, not 500

### Pattern 1 (Mirror)
- [ ] should return 422 for `source_type=CHAT_MESSAGE` with `code="not_revalidatable"`
- [ ] should return 422 for `source_type=MANUAL` with `code="not_revalidatable"`
- [ ] should NOT return 500 for any non-scraper source
- [ ] should NOT touch `confidence` or `MemoryVersion`

### Pattern 2 (Over-Mocking)
- [ ] should handle `get_capability` throwing `KeyError` and still return 422

### Pattern 3 (Happy Path Only)
- [ ] Boundary: `source_type=SCRAPER_RUN` but `source_capability=None` and `source_input=None`
- [ ] Null/empty: `source_type=UNKNOWN`

### Pattern 4 (Arithmetic)
- [ ] N/A for AC-3

### Pattern 5 (Error message)
- [ ] should return error envelope with `code="not_revalidatable"` and message containing "does not support re-validation"

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should not create `MemoryVersion` or `Run` row (real DB)

---

## AC-4: Re-validate call is charged as a normal capability call

### Pattern 1 (Mirror)
- [ ] should call `gate_capability` exactly once before `execute_with_context`
- [ ] should call `charge_capability` exactly once after `execute_with_context` succeeds
- [ ] should pass the same `CapabilityContext` workspace to gate and charge
- [ ] should record `cost_micros` in the new `Run` row

### Pattern 2 (Over-Mocking)
- [ ] should handle `gate_capability` raising and return 422 without executing
- [ ] should handle `charge_capability` raising and return 422 `charge_failed`
- [ ] should handle `charge_capability` returning `0` for free capability

### Pattern 3 (Happy Path Only)
- [ ] Boundary: `capability.billing_unit = None` → free
- [ ] Boundary: user has `0` credits → `gate_failed`

### Pattern 4 (Arithmetic)
- [ ] should compute `cost_micros` exactly from `charge_capability`
- [ ] should record `TokenUsage.cost_micros` exactly equal to revalidation cost

### Pattern 5 (Error message)
- [ ] should return `code="charge_failed"` with message containing "Failed to charge"
- [ ] should return `code="gate_failed"` with message containing "billing gate"

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should persist `TokenUsage` row (real DB)
- [ ] should persist new `Run` row with `origin="revalidate"` and `cost_micros` (real DB)
- [ ] should NOT charge when `gate_capability` fails (real DB)

---

## AC-5: Invalid/missing recipe returns 422, not 500

### Pattern 1 (Mirror)
- [ ] should return 422 for `source_capability=None`
- [ ] should return 422 for `source_input=None`
- [ ] should return 422 for nonexistent capability
- [ ] should return 422 for `source_input` that fails schema validation
- [ ] should NOT return 500

### Pattern 2 (Over-Mocking)
- [ ] should handle `get_capability` raising `KeyError` and map to 422
- [ ] should handle `ValidationError` and map to 422

### Pattern 3 (Happy Path Only)
- [ ] Boundary: `source_input` is an empty dict `{}`
- [ ] Boundary: `source_input` is a list with missing required fields
- [ ] Null/empty: `source_input=None` but `source_capability` set

### Pattern 4 (Arithmetic)
- [ ] N/A for AC-5

### Pattern 5 (Error message)
- [ ] should return 422 with `code="not_revalidatable"` or `code="invalid_recipe"` (document which one)
- [ ] should include human-readable message

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should not execute `Run` or `MemoryVersion` SQL writes (real DB)

---

## Cross-AC Integration: End-to-End Gate

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] **E2E gate:** create `Run` → extract → delete `Run` → revalidate route → assert `confidence`/`MemoryVersion` (real DB)
- [ ] **E2E gate mismatch:** same flow with different fact → assert `MemoryVersion` content (real DB)
- [ ] **E2E gate metering:** same flow → assert new `Run` row `origin="revalidate"` and `cost_micros` (real DB)
