# SM-10 Ratification & NFR-9 State A Lock

## SM-10 — Memory Recall Gate

The memory-recall ship gate (`nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml`) is now ratified against the 2026-07-28 live run.

**Baseline source:**
`nowing_evals/data/memory/runs/2026-07-28T16-28-54Z/recall/run_artifact.json`
(copied from `_bmad-output/implementation-artifacts/evidence/3-14-eval-20260728T230000Z/memory/runs/2026-07-28T16-28-54Z/recall/run_artifact.json`)

**Observed metrics vs. thresholds:**

| Metric | Observed | Threshold | Pass |
|---|---|---|---|
| recall@5 | 0.986 | >= 0.900 | yes |
| MRR | 1.000 | >= 0.700 | yes |
| distractor noise rate | 0.067 | <= 0.100 | yes |
| off-corpus rate | 0.033 | <= 0.050 | yes |
| queries | 36 | >= 30 | yes |
| failed queries | 0 | == 0 | yes |

**Verification command:**

```bash
python -m nowing_evals gate --suite memory --benchmark recall
```

**Result:** `gate PASS artifact=2026-07-28T16-28-54Z`

## NFR-9 State A Lock

Deep research in chat remains in State A (async) by default:

- `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` defaults to `False` in `nowing_backend/app/config/__init__.py`.
- `nowing_backend/app/capabilities/core/access/agent.py:145-179` and `nowing_backend/app/capabilities/core/access/rest.py:201-205` force `chainlens.research` to async when the flag is off.
- State B (synchronous, blocking) is explicitly opt-in and gated by a ratified p95 <= 30s baseline. Current ChainLens benchmark shows balanced p95 at 44.3s, so State B is not viable for launch.

## Files touched

- `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml` (baseline ratified + source)
- `nowing_evals/data/memory/runs/2026-07-28T16-28-54Z/recall/run_artifact.json` (ratified artifact)
- `nowing_evals/data/memory/runs/2026-07-28T16-28-54Z/recall/raw.jsonl` (companion raw file)
- `_bmad-output/implementation-artifacts/sm10-state-a-ratification-2026-08-04.md` (this artifact)
