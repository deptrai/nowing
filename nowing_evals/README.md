# Nowing Evals

Domain-agnostic eval harness for Nowing. Each benchmark is a Python subpackage under `suites/<domain>/<benchmark>/` that self-registers with the CLI; `core/` is the shared infrastructure (HTTP clients, arms, parsers, metrics, report writer, registry). The harness talks to Nowing over HTTP only — it does **not** import any backend Python module — so it ships in its own venv and never bloats the FastAPI runtime image.

## Benchmarks

| Benchmark                       | Shape                                            | Vision required? | Default ingest             |
|---------------------------------|--------------------------------------------------|------------------|----------------------------|
| `medical/medxpertqa` (headline) | Native PDF vs Nowing head-to-head, MCQ        | yes              | `vision=on, mode=basic`    |
| `medical/mirage`                | Nowing single-arm, MCQ                        | no               | `vision=off, mode=basic`   |
| `medical/cure`                  | Nowing single-arm retrieval (Recall/MRR/nDCG) | no               | `vision=off, mode=basic`   |
| `multimodal_doc/mmlongbench`    | Native PDF vs Nowing head-to-head, open-ended | yes              | `vision=on, mode=basic`    |
| `research/chainlens_latency`    | Nowing deep-research p50/p95 e2e + TTFB       | no               | none (live engine calls)   |
| `chat/regression`               | Chat response regression: latency, token/cost, citations, finish status | no | default sample dataset |

Future domains (`legal/`, `finance/`, `code/`, `scientific/`) drop into `suites/` without touching `core/` or the CLI.

## Install + auth

```bash
uv pip install -e ./nowing_evals
cp nowing_evals/.env.example nowing_evals/.env
# Edit .env: NOWING_API_BASE, OPENROUTER_API_KEY, and ONE of:
#   LOCAL  → NOWING_USER_EMAIL + NOWING_USER_PASSWORD
#   GOOGLE → NOWING_JWT (+ optional NOWING_REFRESH_TOKEN)
#            (lift both from browser localStorage after a normal Google login)
```

## Step-by-step: run all four benchmarks

The medical and multimodal_doc suites each get their own SearchSpace and pinned model, so they're independent — run them in any order. Both head-to-head benchmarks (`medxpertqa`, `mmlongbench`) require a **vision-capable** OpenRouter slug; pinning a text-only one (e.g. `openai/gpt-5.4-mini`) silently drops images and the runner emits a warning.

Recommended vision slugs (use `models list --grep <name>` to confirm one): `anthropic/claude-sonnet-4.5` (balanced cost), `anthropic/claude-opus-4.7` (strongest reasoning), `openai/gpt-5` (top-tier vision), `google/gemini-2.5-pro` (best for long PDFs, 1M-token context).

```bash
# 0. (optional) discover what's registered
python -m nowing_evals suites list
python -m nowing_evals benchmarks list

# 1. MEDICAL SUITE — one SearchSpace, three benchmarks
python -m nowing_evals setup --suite medical --provider-model anthropic/claude-sonnet-4.5

#  1a. headline head-to-head: Native PDF (vision) vs Nowing (vision RAG)
#      Downloads dev+test JSONL + images.zip, renders one PDF per question
#      (case + table + images + 5 options), uploads with use_vision_llm=True.
python -m nowing_evals ingest medical medxpertqa --split test
python -m nowing_evals run    medical medxpertqa --concurrency 4

#  1b. MIRAGE — single-arm Nowing MCQ accuracy
#      (MMLU-Med / MedQA-US / MedMCQA / PubMedQA / BioASQ)
python -m nowing_evals ingest medical mirage
python -m nowing_evals run    medical mirage

#  1c. CUREv1 — single-arm Nowing retrieval (Recall@k / MRR / nDCG@10)
python -m nowing_evals ingest medical cure --lang en
python -m nowing_evals run    medical cure --lang en

#  1d. write reports/medical/<UTC-ts>/summary.{md,json}
python -m nowing_evals report --suite medical

# 2. MULTIMODAL_DOC SUITE — long PDFs with embedded images, charts, tables
python -m nowing_evals setup  --suite multimodal_doc --provider-model google/gemini-2.5-pro
python -m nowing_evals ingest multimodal_doc mmlongbench           # ~660MB, resumable
python -m nowing_evals run    multimodal_doc mmlongbench --concurrency 4
python -m nowing_evals report --suite multimodal_doc

# 3. CLEANUP — soft-deletes the SearchSpaces; rendered PDFs stay cached
python -m nowing_evals teardown --suite medical
python -m nowing_evals teardown --suite multimodal_doc
```

## ChainLens research latency (NFR-9 / Story 9.3)

The `research/chainlens_latency` benchmark calls the Nowing deep-research REST endpoint and measures p50/p95 end-to-end and TTFB latency across modes. No setup/ingest is required; it only needs `NOWING_EVAL_WORKSPACE_ID` and a running backend with `CHAINLENS_API_KEY` configured.

```bash
# cp .env.example .env and fill NOWING_API_BASE + NOWING_EVAL_WORKSPACE_ID + auth.
python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality --concurrency 1 --n 3
python -m nowing_evals report --suite research --benchmark chainlens_latency
```

Notes:
- `quality` is the Nowing schema mode that maps to ChainLens `deep`/`deep-reasoning`.
- The benchmark defaults to 5 representative factual queries; use `--n` for a quick smoke run.
- Each mode report now includes `sources_partial_rate`, `engine_unavailable_rate`, `degraded_rate`, `degradation_reason_counts`, `fallback_kb_hits`, and `mean_cost_micros`.
- Targets live in `src/nowing_evals/suites/research/chainlens_latency/gate.yaml` and are provisional until `baseline_ratified` is flipped after a clean ChainLens benchmark.

## Chat response regression (Story 4.8)

The `chat/regression` benchmark replays a dataset of user queries through `POST /api/v1/new_chat`, creates a fresh thread per case, and records e2e latency, TTFB, token/cost, citation count, finish status, and optional keyword-match checks. It requires no `setup`/`SearchSpace`, but it needs a live backend and a `search_space_id` where the bot can create threads.

The benchmark also captures **operational / stability** metrics: scrape/search success rate, per-tool attempts/successes/drops, failure reason classification (captcha, rate-limit, timeout, 5xx, parse error, engine unavailable), fallback KB hits, and — with `--concurrency` or `--threads` — under-load p95 latency and error rates.

```bash
# 1. (optional) use the default sample dataset or provide your own JSONL
python -m nowing_evals ingest chat regression
python -m nowing_evals ingest chat regression --dataset my-cases.jsonl

# 2. run against a real SearchSpace
python -m nowing_evals run chat regression --search-space-id 42 --concurrency 1

# 3. stress mode: run each case in 4 parallel chat threads
python -m nowing_evals run chat regression --search-space-id 42 --concurrency 2 --threads 4

# 4. report
python -m nowing_evals report --suite chat
```

Dataset format (JSONL):

```jsonl
{"case_id": "chat-mem-001", "query": "What do we know about AlphaCorp?", "tags": ["memory"], "expected_contains": ["AlphaCorp"]}
{"case_id": "chat-doc-001", "query": "Summarize the NDA.", "tags": ["document"], "mentioned_document_ids": [123], "expected_contains": ["NDA"]}
{"case_id": "chat-multi-001", "query": "What is the budget?", "tags": ["memory"], "turns": [{"query": "What is the budget?", "expected_contains": ["Q3"]}, {"query": "And the forecast?", "expected_contains": ["forecast"]}], "expected_contains": ["forecast"]}
```

Notes:
- Use `--tags memory,document` to run only cases with those tags.
- Multi-turn cases reuse a single thread and produce per-turn latency/TTFB/citation/keyword hits plus a `context_drift_score`.
- The report includes an **"Operational / Stability"** table with the new metrics.
- Gate thresholds live in `src/nowing_evals/suites/chat/regression/gate.yaml` and are provisional until `baseline_ratified` is flipped.
- See `docs/benchmark-stability.md` for a stability-metric reference.

## Asymmetric scenarios — the "vision-extract once, answer cheap" play

The walkthrough above is `--scenario head-to-head` (default): both arms answer with the same vision-capable slug. Nowing's actual architectural value-prop is that the **ingestion-time vision LLM and the runtime LLM are completely independent** — you can pay a vision LLM *once*, at ingest, to convert every embedded image into text (per-image OCR **and** semantic description, inlined where the image actually appears in the document — see [What `--use-vision-llm` produces](#what---use-vision-llm-produces) below). Then every query is served by a cheap text-only model that sees that extracted text natively. Two extra scenarios make this explicit:

| `--scenario`       | Native arm answers with                | Nowing arm answers with     | Question being measured                                                                  |
|--------------------|----------------------------------------|--------------------------------|------------------------------------------------------------------------------------------|
| `head-to-head`     | `--provider-model` (vision)            | `--provider-model` (vision)    | Pure RAG quality at parity. (Default.)                                                   |
| `symmetric-cheap`  | `--provider-model` (cheap, text-only)  | `--provider-model` (same)      | Does pre-extracted image context let a non-vision LLM reason over image-heavy docs?      |
| `cost-arbitrage`   | `--native-arm-model` (vision)          | `--provider-model` (cheap)     | How close does Nowing get to a vision-native baseline at a fraction of per-query cost?|

In all three modes the **ingest-time** vision LLM is set on the SearchSpace's `vision_model_id` (auto-picked from the strongest registered global OpenRouter vision-capable model — `claude-sonnet-4.5` > `claude-opus-4.7` > `gpt-5` > `gemini-2.5-pro`, override with `--vision-llm <slug>`). What changes is which slug the *answering* models hit per arm.

### Ingest with vision, evaluate with a non-vision LLM (`symmetric-cheap`)

This is the answer to *"does Nowing give a non-vision LLM enough context to reason over image-heavy docs?"*. Both arms hit the same cheap text-only slug. The native arm is structurally blind to images (text-only LLM + raw PDFs). The Nowing arm reads chunks that already contain the per-image OCR and visual descriptions, written there by the vision LLM at ingest time.

```bash
python -m nowing_evals setup --suite medical \
  --scenario symmetric-cheap \
  --provider-model openai/gpt-5.4-mini
  # vision LLM at ingest = auto-picked (claude-sonnet-4.5 by default)
  # answer LLM for BOTH arms = openai/gpt-5.4-mini (text-only)

python -m nowing_evals ingest medical medxpertqa --split test  # vision=on by default
python -m nowing_evals run    medical medxpertqa --concurrency 4
python -m nowing_evals report --suite medical
# Δ accuracy on image-required MCQs is the headline number; native arm
# baseline is "what a text-only LLM gets without seeing the images".
```

### Cheap Nowing vs vision-native baseline (`cost-arbitrage`)

```bash
python -m nowing_evals setup --suite medical \
  --scenario cost-arbitrage \
  --provider-model openai/gpt-5.4-mini \
  --native-arm-model anthropic/claude-sonnet-4.5
  # vision LLM at ingest = auto-picked claude-sonnet-4.5
  # native arm = sonnet (vision); Nowing arm = gpt-5.4-mini (text-only)

python -m nowing_evals ingest medical medxpertqa --split test
python -m nowing_evals run    medical medxpertqa --concurrency 4
python -m nowing_evals report --suite medical
# Report header reads:
#   Scenario: cost-arbitrage — native arm answers with `anthropic/claude-sonnet-4.5`
#   (vision); Nowing answers with `openai/gpt-5.4-mini` over chunks vision-extracted
#   at ingest by `anthropic/claude-sonnet-4.5`.
```

Notes:
- `cost-arbitrage` requires both `--provider-model` (the cheap Nowing slug) AND `--native-arm-model <vision slug>`.
- `--vision-llm <slug>` is optional; if omitted the harness queries `GET /api/v1/model-connections/global` and auto-picks the strongest registered vision-capable model. Pass `--no-vision-llm-setup` if you want to keep whatever vision model is already attached to the SearchSpace.
- The runner's "looks text-only" warning is suppressed (or relabelled as informational) for `symmetric-cheap` so intentional asymmetry doesn't read as a misconfiguration.
- All three scenario fields (`scenario`, `provider_model`, `native_arm_model`, `vision_provider_model`) are persisted to `state.json` and recorded in `run_artifact.extra` + the report header — no need to retrace what was set.

## Per-benchmark useful flags

`medical/medxpertqa` (`run`):
- `--split {test,dev,all}` — pick a subset (default `test`)
- `--task "Diagnosis"` / `--body-system "Cardiovascular"` — slice the report
- `--require-images` — drop rare rows where every image filename failed to resolve
- `--n 100` — quick smoke run
- `--no-mentions` — let Nowing retrieve unscoped ("did the @-mention matter?")

`multimodal_doc/mmlongbench`:
- `--max-docs N` (ingest) — cap downloads at the first N unique PDFs
- `--format {str,int,float,list,none}` (run) — slice by answer format; `none` = the ~22% intentionally unanswerable hallucination probes
- `--skip-unanswerable` (run) — drop unanswerable questions
- `--docs <a.pdf>,<b.pdf>` (run) — scope to specific docs

## Ingestion knobs (vision LLM, processing mode)

The harness exposes `POST /api/v1/documents/fileupload`'s ingest knobs on every `ingest` subcommand:

| Flag pair                                  | Effect                                                                                  |
|--------------------------------------------|-----------------------------------------------------------------------------------------|
| `--use-vision-llm` / `--no-vision-llm`     | Walk every embedded image in the PDF and inline image-derived text at the image's position (see below). |
| `--processing-mode {basic,premium}`        | `premium` carries a 10× page multiplier and routes to a stronger ETL (e.g. LlamaCloud). |

The "Default ingest" column in the benchmarks table is what runs if you don't pass any flag. Whatever was actually used is recorded as a `__settings__` header in the doc map (`data/<suite>/maps/<benchmark>_*_map.jsonl`) and as `extra.ingest_settings` in `run_artifact.json`, then surfaced in the report — no need to hunt through CLI history.

> The backend's `ETL_SERVICE` env var (`DOCLING` | `UNSTRUCTURED` | `LLAMACLOUD`) is **not** per-upload. Restart the backend with a different `ETL_SERVICE` and re-ingest to compare ETLs (route through `--processing-mode premium` if your backend uses that mode for the stronger ETL).

### What `--use-vision-llm` produces

When vision is on, the backend's ETL pipeline (`app/etl_pipeline/picture_describer.py`) does, **per embedded image** in the PDF:

1. Extract the raw image bytes via `pypdf` (deduped by sha256, size-capped to match the vision LLM's per-image limit).
2. **Per-image OCR** — re-feed the image as a standalone upload through the configured ETL service (Docling / Azure DI / LlamaCloud) with `vision_llm=None`, so the ETL's OCR engine extracts the literal text-in-image.
3. **Visual description** — call the vision LLM on the image with a description-only prompt (it's explicitly told *not* to transcribe text — that's OCR's job). Steps 2 and 3 run in parallel per image.
4. Splice a horizontal-rule-delimited section **at the image's original position** in the parser markdown (replacing Docling's `<!-- image -->` placeholder + caption, or the bare `Image: <name>` caption a stripped-image parser leaves behind):

   ```markdown
   ---

   **Embedded image:** `MM-130-a.jpeg`

   **OCR text:**
   Slice 24 / 60
   L  R

   **Visual description:**

   - Axial contrast-enhanced CT showing a large cystic mass in the left upper quadrant.
   - Mass effect on the adjacent stomach; left kidney displaced inferiorly.

   ---
   ```

This is what makes `--scenario symmetric-cheap` and `--scenario cost-arbitrage` work: a non-vision LLM reading Nowing's chunks sees the image's text and semantic content as plain markdown, alongside the surrounding case text, in the same retrieved chunk. Without it the cheap LLM would have nothing extra to read.

### A/B testing the same corpus with different settings

Nowing dedupes uploads by `(filename, search_space_id)` — **not** by content hash and **not** by ingestion settings. Re-uploading the same filename to the same SearchSpace with a different `--use-vision-llm` flag silently skips re-processing. Give each variant its own SearchSpace:

```bash
# Baseline arm (vision off)
python -m nowing_evals setup    --suite medical --provider-model anthropic/claude-sonnet-4.5
python -m nowing_evals ingest   medical medxpertqa --no-vision-llm
python -m nowing_evals run      medical medxpertqa --n 100
python -m nowing_evals teardown --suite medical

# Vision arm (the benchmark default)
python -m nowing_evals setup    --suite medical --provider-model anthropic/claude-sonnet-4.5
python -m nowing_evals ingest   medical medxpertqa
python -m nowing_evals run      medical medxpertqa --n 100
python -m nowing_evals report   --suite medical
```

Both runs land in `data/medical/runs/<ts>/medxpertqa/` with their settings recorded; rendered PDFs stay cached under `data/medical/medxpertqa/pdfs/` so the second `ingest` is upload-only.

## Environment variables

- `NOWING_API_BASE` (default `http://localhost:8000`)
- `OPENROUTER_API_KEY` — required for the `native_pdf` arm and for `models list`
- One of `NOWING_USER_EMAIL` + `NOWING_USER_PASSWORD` (LOCAL), **or** `NOWING_JWT` (+ optional `NOWING_REFRESH_TOKEN`) for GOOGLE/pre-issued JWT
- `EVAL_DATA_DIR` (default `<project>/data`) — datasets, rendered PDFs, ingestion id maps, run outputs, `state.json`
- `EVAL_REPORTS_DIR` (default `<project>/reports`)
- `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`) — only if you proxy OpenRouter

## Adding a new domain suite

1. Create `nowing_evals/src/nowing_evals/suites/<domain>/<benchmark>/` with `__init__.py`, `ingest.py`, `runner.py`, optional `prompt.py`.
2. Implement a `Benchmark` subclass (see `core/registry.py`); compose with `core.clients.*`, `core.arms.*`, `core.parse.*`, `core.metrics.*`.
3. Call `register(MyBenchmark())` at the bottom of `<benchmark>/__init__.py`. Auto-discovery picks it up; `setup --suite <domain>` and `ingest/run <domain> <benchmark>` work immediately.

Each suite gets its own SearchSpace (`eval-<suite>-<UTC-ts>`), `state.json` slot, data dir, reports dir, and pinned LLM. Suites never share a SearchSpace.

## Out of scope (follow-up PRs)

- Docker service for `docker compose run evals run medical medxpertqa`.
- Multi-model sweeps (one slug per `setup` for now; aggregate reports come later).
- A long-context-stuffing arm (give the model the same retrieved chunks Nowing saw).
- LLM-judge grader for MMLongBench-Doc (paper uses GPT-4 as judge; we ship a deterministic rule-based grader).
- MedXpertQA-MM accuracy by image modality — dataset doesn't tag modality directly; we slice by `medical_task` and `body_system`.
- A `--slot <name>` flag that decouples the state-slot key from the benchmark registry's `suite` attribute, so parallel SearchSpaces with different ingestion settings can coexist on the same benchmark without `teardown` between A/B arms.

See `c:/Users/91882/.cursor/plans/medical_rag_evals_(mirage_+_curev1)_e797a324.plan.md` for the full design rationale.
