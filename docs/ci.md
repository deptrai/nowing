# CI/CD Pipeline Guide

## Overview

The main test pipeline is defined in `.github/workflows/test.yml`.
It runs on every push/PR to `main`/`dev`, on a weekly schedule, and can be triggered manually via `workflow_dispatch`.

## Stages

1. **Lint** — backend (`ruff`) and web (`biome`) quality checks.
2. **Backend Unit Tests** — `pytest -m unit`, sharded into 4 parallel jobs, producing JUnit XML.
3. **Backend Integration Tests** — `pytest -m integration` against a Postgres service.
4. **Frontend Build** — `pnpm build` smoke test for `nowing_web`.
5. **Burn-In** — repeats unit tests 10 times (configurable) to detect flakiness.
6. **Report** — downloads artifacts and writes a GitHub Step Summary.
7. **Quality Gate** — parses JUnit XML, computes pass rate, enforces P1 threshold (>= 95%).

## Existing Workflows

Other workflows remain active:

- `.github/workflows/code-quality.yml` — pre-commit based checks.
- `.github/workflows/backend-tests.yml` — backend unit/integration tests.
- `.github/workflows/e2e-tests.yml` — Docker-backed Playwright E2E journey tests.

You may retire or consolidate these once `test.yml` is verified.

## Local CI Simulation

Run `scripts/ci-local.sh` to execute the same core checks locally.

## Secrets

See `docs/ci-secrets-checklist.md`.
