---
story_key: 30-5-title_gen-py-lacks-timeout-retry-on-litellm-acompletion
status: done
epic: 30
---

# Story 30.5: title_gen.py lacks timeout/retry on litellm.acompletion

**Status:** `done`  
**Epic:** Epic 30 — Technical Debt

## Story

As a chat user,  
I want chat title generation to have explicit timeout and retry settings,  
so that a slow or hanging model cannot block the chat for 120s+.

## Acceptance Criteria

- **Given** `title_gen.py` calls `litellm.acompletion()` for a new chat title, **When** the call is made, **Then** it passes explicit `timeout` and `num_retries` parameters.
- **Given** a transient litellm timeout, **When** `num_retries` is configured > 0, **Then** it retries with backoff and returns a fallback title instead of hanging.
- **Given** all retries are exhausted, **When** title generation fails, **Then** the chat session falls back to a default title and logs the error without crashing the turn.

## Dev Notes

- Module: `app/tasks/chat/streaming/flows/new_chat/title_gen.py`
- Recommended: `timeout=30`, `num_retries=2`
- This was originally tracked as a standalone micro-story and consolidated into Story 30.9.

## Verification

- Module: `app/tasks/chat/streaming/flows/new_chat/title_gen.py`
- Tests: timeout parameter presence, fallback on repeated failure
