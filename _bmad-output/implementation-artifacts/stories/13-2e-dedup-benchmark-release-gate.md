# Story 13.2e: Dedup Benchmark & Release Gate

**Status:** in-progress
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing
**Priority:** P1

## Story

As a researcher,
I want a dedup benchmark with hard precision/recall/F1 gates,
So that canonical persistence is not released until matching quality is proven.

## Acceptance Criteria

- **Dependency:** Stories 13.2a–d; Jobs fixtures additionally depend on Epic 12 pilot data.
- **Given** BDS and Jobs fixtures at 15%, 30% and 70% entity-level cross-source overlap, **Then** each domain/tier reports precision, recall and F1 with hard gates `precision ≥ 0.95`, `recall ≥ 0.90`, and `F1 ≥ 0.92`.
- **Given** benchmark metadata, **Then** `overlap_rate = multi_source_ground_truth_entities / total_ground_truth_entities`; fixture counts must satisfy that equation and raw-record totals independently.
- **Given** the Nowing eval harness, **Then** fixtures live under `nowing_evals/data/canonical/fixtures/`, benchmark packages under `nowing_evals/src/nowing_evals/suites/canonical/`, and execution uses `python -m nowing_evals ...`.

## Validation

- Unit tests: `test_canonical_fixture_counts.py`, `test_canonical_dedup_metrics.py`.
- Eval run: `python -m nowing_evals run canonical dedup --fixtures bds-30,jobs-30`.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-27, benchmark, dedup, canonical, precision, recall, F1, nowing_evals
