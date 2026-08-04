---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8c-production-query-sampler
status: ready-for-dev
---

# Story 4.8c: Production query sampler + anonymizer

**Status:** ready-for-dev  
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

- [ ] Decide location: `nowing_backend/app/admin/chat_query_sampler.py` (library) + `scripts/sample_chat_queries.py` (CLI), or a new `/admin/chat-query-sampler` endpoint.
- [ ] Query `NewChatMessage` for `role='user'`, `created_at` within the last N days, limit M, random sample or stratified by tag.
- [ ] Join `NewChatThread` to get `search_space_id`, `workspace_id`, and `mentioned_document_ids`.
- [ ] Join `AgentActionLog` or tool-call records to infer `deep-research` / `multi-tool` tags.
- [ ] Implement regex PII redaction.
- [ ] Hash workspace name with a stable salt (env var `QUERY_SAMPLER_SALT`).
- [ ] Write JSONL with fields: `case_id`, `query`, `tags`, `mentioned_document_ids`, `disabled_tools`, `workspace_id_hash`.

### Tests

- [ ] Unit tests for redaction regex on synthetic PII.
- [ ] Unit tests for tag heuristics on a small labeled corpus.
- [ ] Integration test against a seeded DB in `tests/integration/admin/` or `tests/integration/chat/`.

### Privacy & ops

- [ ] Document required DB permissions (read-replica / backup).
- [ ] Add `--dry-run` and `--max-queries` flags.
- [ ] Update `.env.example` with `QUERY_SAMPLER_SALT`.

## Verification

```bash
cd nowing_backend
ruff check app/admin/chat_query_sampler.py scripts/sample_chat_queries.py tests/integration/admin/test_chat_query_sampler.py
ruff format ...
pytest tests/integration/admin/test_chat_query_sampler.py -q
```

Usage:

```bash
python scripts/sample_chat_queries.py --max-queries 100 --days 30 --output /tmp/sampled.jsonl
cd ../nowing_evals
python -m nowing_evals ingest chat regression --dataset /tmp/sampled.jsonl
```

## References

- `nowing_backend/app/db.py` — `NewChatMessage`, `NewChatThread`
- `nowing_backend/app/schemas/new_chat.py`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
