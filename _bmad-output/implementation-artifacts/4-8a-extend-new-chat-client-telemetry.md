---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8a-extend-new-chat-client-telemetry
status: done
---

# Story 4.8a: Extend `NewChatClient` to capture benchmark telemetry

**Status:** done  
**Epic:** 4 — Chat & Agents  
**Priority:** HIGH  
**Requirements:** FR-42, NFR-10  
**Architecture:** `nowing_evals` harness, `AD-15` (nếu benchmark gọi ChainLens)

## Story

As a benchmark runner,
I want `NewChatClient` to capture token usage, TTFB, turn id and finish status from the `/api/v1/new_chat` SSE stream,
So that `nowing_evals` can measure chat cost, latency and outcome per turn without polling the database.

## Context

`nowing_evals/src/nowing_evals/core/clients/new_chat.py` already implements:

- `create_thread` / `delete_thread` for ephemeral threads.
- `ask` which POST to `/api/v1/new_chat` and consumes the Vercel AI SDK-flavoured SSE stream.
- `StreamedAnswer` currently captures: `text`, `raw_events`, `latency_ms`, `user_message_id`, `assistant_message_id`, `finished_normally`.

The backend emits additional SSE frames that the client currently ignores:

- `data-token-usage` — contains `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `call_details`, `usage` per model (see `nowing_backend/app/tasks/chat/streaming/flows/shared/finalize_emit.py:44-54`).
- `data-turn-info` — contains `chat_turn_id` (see `nowing_web/lib/chat/streaming-state.ts:541-543`).
- `data-user-message-id` / `data-assistant-message-id` — currently parsed with fallback, but message id is now `int` (`message_id`) not `id` (see `nowing_web/lib/chat/streaming-state.ts:556-573`).

The `NowingArm` (`nowing_evals/src/nowing_evals/core/arms/nowing.py`) populates `ArmResult` fields `input_tokens`, `output_tokens`, `cost_micros`, `latency_ms` but leaves them at `0` because the client does not surface token/cost. This gap is documented as intentional, but it makes chat benchmarking impossible.

## Acceptance Criteria

1. **Token usage capture**
   - **Given** a `/new_chat` stream emits `data-token-usage`,  
     **When** `NewChatClient._consume_sse` receives it,  
     **Then** `StreamedAnswer` exposes `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `call_details` and `model_breakdown`.

2. **TTFB capture**
   - **Given** a chat turn starts streaming,  
     **When** the first `text-delta` event arrives,  
     **Then** `StreamedAnswer.ttfb_ms` is set to the elapsed time from request start to that first delta.

3. **Turn id capture**
   - **Given** a `data-turn-info` event arrives,  
     **When** it contains `chat_turn_id`,  
     **Then** `StreamedAnswer.turn_id` is populated.

4. **Backward compatibility**
   - **Given** an older backend that does not emit `data-token-usage`,  
     **When** the client runs,  
     **Then** it does not crash; numeric fields default to `0`/`None` as appropriate.

5. **`NowingArm` telemetry pass-through**
   - **Given** `NowingArm.answer` receives a `StreamedAnswer`,  
     **When** it returns `ArmResult`,  
     **Then** `input_tokens`, `output_tokens`, `cost_micros`, `latency_ms` (and `extra` fields `turn_id`, `ttfb_ms`) are filled.

## Tasks / Subtasks

### `NewChatClient` telemetry

- [ ] Update `StreamedAnswer` dataclass:
  - Add `ttfb_ms: int | None = None`
  - Add `turn_id: str | None = None`
  - Add `prompt_tokens: int = 0`
  - Add `completion_tokens: int = 0`
  - Add `total_tokens: int = 0`
  - Add `cost_micros: int | None = None`
  - Add `model_breakdown: dict[str, Any] | None = None`
  - Add `call_details: list[dict[str, Any]] | None = None`
- [ ] In `_stream_once`, record start time and pass to `_consume_sse`.
- [ ] In `_consume_sse`:
  - Track time of first `text-delta` and compute `ttfb_ms`.
  - Parse `data-token-usage` event (`type == "token-usage"` or `type == "data-token-usage"` depending on wire shape).
  - Parse `data-turn-info` (`type == "turn-info"` or `type == "data-turn-info"`) for `chat_turn_id`.
  - Keep `user_message_id` / `assistant_message_id` parsing robust against both `id` and `message_id` keys.
- [ ] Ensure unknown event types are appended to `raw_events` but do not crash parsing.

### `NowingArm` pass-through

- [ ] In `NowingArm.answer`, map `StreamedAnswer` fields into `ArmResult`:
  - `input_tokens = answer.prompt_tokens`
  - `output_tokens = answer.completion_tokens`
  - `cost_micros = answer.cost_micros or 0`
  - `latency_ms = answer.latency_ms`
  - Add to `extra`: `ttfb_ms`, `turn_id`, `call_details`, `model_breakdown`.

### Tests

- [ ] Add/update unit tests in `nowing_evals/tests/core/test_clients.py`:
  - SSE stream with `data-token-usage` produces correct `StreamedAnswer`.
  - SSE stream without `data-token-usage` remains safe.
  - First `text-delta` sets `ttfb_ms`.
  - `data-turn-info` sets `turn_id`.
- [ ] Update `NowingArm` tests if they assert `extra` shape.

## Dev Notes

- Do **not** change the SSE wire format; only the client parser.
- Event type names: the backend `finalize_emit.py` emits `token-usage` (wrapped by `VercelStreamingService.format_data("token-usage", ...)`) and the frontend `streaming-state.ts` maps the shaped event to `data-token-usage`. The SSE line is `data: {"type":"token-usage", ...}` or `data: {"type":"data-token-usage", ...}`? Verify by looking at `app/services/streaming/envelope/sse.py` and the actual events in tests. Be defensive and accept both `token-usage` and `data-token-usage`.
- `cost_micros` from the backend is a `int`; if `0` from a sponsored/fallback run, still record it.
- TTFB is defined as time from request start to first `text-delta` byte. Do not confuse with HTTP TTFB (first byte of HTTP response); the client already holds the response when it starts reading SSE.

## Verification

```bash
cd nowing_evals
python -m pytest tests/core/test_clients.py -q
ruff check src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py
ruff format src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py
```

## References

- `nowing_evals/src/nowing_evals/core/clients/new_chat.py`
- `nowing_evals/src/nowing_evals/core/arms/nowing.py`
- `nowing_evals/src/nowing_evals/core/arms/base.py`
- `nowing_backend/app/tasks/chat/streaming/flows/shared/finalize_emit.py`
- `nowing_backend/app/schemas/new_chat.py` (`TokenUsageSummary`)
- `nowing_web/lib/chat/streaming-state.ts` (SSE event types)
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-04-chat-response-benchmark.md`
