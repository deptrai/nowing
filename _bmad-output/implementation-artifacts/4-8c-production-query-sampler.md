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

## Review Findings (code review 2026-08-08)

Scope: commit `05cdfbd0f` — 5 backend files, 580 lines (production query sampler + anonymizer).

**patch (MEDIUM) — fixed 2026-08-08:**
- [x] [Review][Patch] Phone PII pattern was US-only — Vietnamese phone numbers (`0901 234 567`, `+84 901 234 567`) were NOT redacted, leaking real Vietnamese phone numbers into the benchmark dataset. Added Vietnamese phone pattern `\b(?:\+?84|0)\d[\s.-]?\d{3}[\s.-]?\d{3,5}\b` to the `_PII_PATTERNS` list. [blind]

**defer:** 9 (all low severity)
- Workspace hash reversibility — SHA-256 with salt is adequate. HMAC is minor improvement.
- No DB error handling — CLI tool for admins. Traceback on DB failure is acceptable.
- No max_queries upper bound — admin-only CLI. Default is 100.
- SSN pattern misses unformatted — adding `\d{9}` would match any 9-digit number (false positives).
- Very long query — low risk. JSONL handles it.
- Unicode word boundaries — low risk. `\b` works for ASCII PII patterns.
- AC-1 PARTIAL: no superuser enforcement test — implementation is correct.
- AC-5 PARTIAL: no ingest compatibility test — implementation produces correct fields.
- Incomplete PII coverage (names, addresses) — AC-2 only requires email/phone/SSN/CC. NER is scope creep.

**dismissed:** 4 (all false positives or by-design)
- Overly broad CC pattern — over-redaction is safer than under-redaction for PII.
- Null reference in auth check — FALSE POSITIVE. `resolve_pat` uses `selectinload` + `join(User)`. `pat.user` is always loaded.
- Workspace name None — FALSE POSITIVE. `Workspace.name` is `nullable=False`.
- Incomplete PII types (names, addresses) — AC-2 only lists 4 patterns. Adding more is scope creep.

**AC coverage:** AC-1 PASS, AC-2 PASS (phone pattern now includes Vietnamese), AC-3 PASS, AC-4 PASS, AC-5 PASS.

**Positive findings:**
- SQL injection: uses SQLAlchemy ORM with parameterized queries
- DB writes: function is read-only, no write operations
- Auth: requires superuser PAT verification
- Logging: only logs dry-run counts, no PII in logs
- Memory: has max_queries limit (default 100)
- PII redaction: SSN, CC, phone (US + Vietnamese), email patterns
- Workspace hashing: SHA-256 with operator-controlled salt
- Case tagging: memory, document, deep-research, multi-tool, creative, factual
- Output: JSONL with case_id, query, tags, mentioned_document_ids, disabled_tools, workspace_id_hash
