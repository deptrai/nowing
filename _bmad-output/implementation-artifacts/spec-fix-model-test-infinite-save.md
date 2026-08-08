---
title: 'Fix model test-preview infinite save'
type: 'bugfix'
created: '2026-08-08'
status: 'done'
route: 'one-shot'
---

# Fix model test-preview infinite save

## Intent

**Problem:** Adding an OpenAI-compatible model connection hangs for ~90 seconds ("infinite save") because `test_model()` calls `litellm.acompletion()` without `num_retries`, causing LiteLLM to retry 3 times × 30s timeout each before returning an error.

**Approach:** Add `num_retries=0` to the `litellm.acompletion()` call in `test_model()` and reduce `TEST_TIMEOUT_SECONDS` from 30s to 15s, so the test-preview endpoint fails fast instead of hanging.

## Suggested Review Order

1. [Changed: test_model() retry + timeout](nowing_backend/app/services/model_connection_service.py) — the 2-line fix
2. [Deferred: title_gen.py same-class bug](_bmad-output/implementation-artifacts/deferred-work.md) — td-5, pre-existing

### Review Findings

- [x] [Review][Patch] kwargs override — TypeError if extra.litellm_params contains num_retries/timeout [model_connection_service.py:482-483] — fixed in commit 622bab8d7
- [x] [Review][Defer] No unit test coverage for test_model function [tests/unit/services/test_model_connections.py] — deferred, pre-existing
- [x] [Review][Defer] Other direct LiteLLM calls lack timeout/retry (title_gen, verify scripts) — deferred, already tracked as td-5/td-6
