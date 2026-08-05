---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8c-production-query-sampler
status: done
---

# Story 4.8c: Production query sampler + anonymizer

**Status:** done  
**Epic:** 4 — Chat & Agents  
**Priority:** HIGH  
**Requirements:** FR-42, NFR-10  

## Story

As an eval operator,
I want a safe way to extract a sample of production chat queries, remove PII, and tag them by case type,
So that the `chat/regression` benchmark can run against realistic queries without leaking user data.

## Context

- `chat/regression` (4.8b) already exists and uses a **synthetic default dataset** (`_DEFAULT_DATASET`).
- Production queries live in `NewChatMessage` (`nowing_backend/app/db.py`) with `role='user'`, linked to `NewChatThread` and `SearchSpace`.
- PII risk is P0: queries may contain names, emails, credit card numbers, workspace secrets.
- The sampler must run against a **read-replica or sanitized backup**, never the primary write path.

## Acceptance Criteria

1. **Admin-only endpoint/script**
   - **Given** a superuser/admin token,  
     **When** they call the sampler,  
     **Then** it returns a JSONL of sampled queries and never writes to the DB.

2. **PII redaction**
   - **Given** a query containing email/phone/SSN/credit-card,  
     **When** it is sampled,  
     **Then** those patterns are replaced with `<EMAIL>`, `<PHONE>`, `<SSN>`, `<CC>`.

3. **Case tagging**
   - **Given** a sampled query,  
     **When** the sampler runs,  
     **Then** it assigns `tags` based on lightweight heuristics:
     - `memory` — if the query references "we", "our", "team", "remember", "memory".
     - `document` — if the thread has `mentioned_document_ids`.
     - `deep-research` — if the turn invoked the `chainlens.research` tool.
     - `multi-tool` — if multiple tool calls in the turn.
     - `creative` — if the query asks to draft/summarize in open-ended form.
     - `factual` — default / catch-all.

4. **Anonymize metadata**
   - **Given** a query from workspace W,  
     **When** exported,  
     **Then** `workspace_name` is hashed to `w-<hash>` and `user_id` is omitted.

5. **Output compatibility**
   - **Given** the JSONL output,  
     **When** `python -m nowing_evals ingest chat regression --dataset output.jsonl` runs,  
     **Then** it is accepted without manual editing.

## Tasks / Subtasks

### Backend or standalone script

- [x] Decide location: `nowing_backend/app/admin/chat_query_sampler.py` (library) + `scripts/sample_chat_queries.py` (CLI).
- [x] Query `NewChatMessage` for `role='user'`, `created_at` within the last N days, limit M, ordered by `func.random()`.
- [x] Join `NewChatThread` to get `workspace_id`. `search_space_id` is not a column on `NewChatThread`; `mentioned_document_ids` are inferred from `AgentActionLog` tool-call `args` where present.
- [x] Join `AgentActionLog` to infer `deep-research` / `multi-tool` / `document` tags.
- [x] Implement regex PII redaction.
- [x] Hash workspace name with a stable salt (env var `QUERY_SAMPLER_SALT`).
- [x] Write JSONL with fields: `case_id`, `query`, `tags`, `mentioned_document_ids`, `disabled_tools`, `workspace_id_hash`.

### Tests

- [x] Unit tests for redaction regex on synthetic PII.
- [x] Unit tests for tag heuristics on a small labeled corpus.
- [x] Integration test in `tests/integration/admin/test_chat_query_sampler.py` against a seeded DB.

### Privacy & ops

- [x] CLI warns when not using a local DB; docstring mentions read-replica / sanitized backup.
- [x] Add `--dry-run` and `--max-queries` flags.
- [x] Update `.env.example` with `QUERY_SAMPLER_SALT` and `QUERY_SAMPLER_PAT`.

## Verification

```bash
cd nowing_backend
ruff check app/admin/chat_query_sampler.py scripts/sample_chat_queries.py tests/integration/admin/test_chat_query_sampler.py
ruff format app/admin/chat_query_sampler.py scripts/sample_chat_queries.py tests/integration/admin/test_chat_query_sampler.py
pytest tests/integration/admin/test_chat_query_sampler.py -q
```

Usage:

```bash
cd nowing_backend
python scripts/sample_chat_queries.py --pat "$QUERY_SAMPLER_PAT" --salt "$QUERY_SAMPLER_SALT" --max-queries 100 --days 30 --output /tmp/sampled.jsonl
cd ../nowing_evals
python -m nowing_evals ingest chat regression --dataset /tmp/sampled.jsonl
```

## Code status note

Implemented and merged. `app/admin/chat_query_sampler.py` and `scripts/sample_chat_queries.py` sample recent `NewChatMessage` rows for `role='user'`, redact PII, infer tags from `AgentActionLog` tool calls, and hash workspace names with `QUERY_SAMPLER_SALT`. Output is a JSONL that `nowing_evals ingest chat regression --dataset` accepts directly. The CLI requires an admin PAT (`QUERY_SAMPLER_PAT`) and warns when not using a local DB. `.env.example` includes both env vars. Integration tests exist at `tests/integration/admin/test_chat_query_sampler.py`.

## References

- `nowing_backend/app/db.py` — `NewChatMessage`, `NewChatThread`
- `nowing_backend/app/schemas/new_chat.py`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
