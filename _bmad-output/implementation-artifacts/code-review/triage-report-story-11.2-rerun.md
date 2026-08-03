# Code Review Triage — Story 11.2 Re-run

**Review spec:** `_bmad-output/implementation-artifacts/11-2-telegram-write-back-and-builder.md`  
**Diff:** `_bmad-output/implementation-artifacts/code-review/diff-story-11.2-rerun.md`  
**Findings files:**
- `blind-hunter-findings-story-11.2-rerun.md` (15 raw findings)
- `edge-case-hunter-findings-story-11.2-rerun.json` (13 raw findings)
- `acceptance-auditor-findings-story-11.2-rerun.md` (PASS)

## Summary

Acceptance Auditor verified all AC-1 through AC-8. Blind Hunter and Edge Case Hunter raised 28 additional observations. After triage, **one low-severity patch was applied** and the rest were dismissed as out of 11.2 scope, pre-existing/deferred, or acceptable implementation choices.

## Triaged findings

### patch (1) — applied

1. **`writeBackParamsFromParams` did not validate the `parse_mode` string when hydrating an existing definition** `[builder-schema.ts:558-563]`
   - Any non-`null` value was cast to the narrow `"Markdown" | "MarkdownV2" | "none"` union. An invalid legacy value would flow through to the backend and fail at Telegram API time.
   - Fixed by guarding against the three allowed literals and falling back to `"none"` for anything else.

### dismiss (27)

| # | Source | Title | Rationale |
|---|--------|-------|-----------|
| 2 | blind | Duplicate fallback logic in `_send_with_fallbacks` | The targeted `_is_parse_mode_error` branch returns immediately; the generic branch is a deliberate catch-all. Recursion is bounded by the presence of `parse_mode`/`reply_markup` (≤ 3 API calls). |
| 3 | blind | `get_updates` catches bare `Exception` | Already tracked as a deferred 11.3 item in `deferred-work.md`; long-polling is outside 11.2's `write_back_telegram` scope. |
| 4 | blind | Missing validation of `reply_markup` nested structure | `_build_inline_keyboard_markup` calls `InlineKeyboardMarkup.de_json` and catches `TypeError`/`ValueError`, logging the offending payload. Pre-validation is unnecessary. |
| 5 | blind | Unsafe string interpolation in `_raise_if_not_numeric` | `!r` is used; the inputs are small user-supplied numeric strings, not arbitrary payloads. |
| 6 | blind | `reply_markup: dict` type too broad | Raw JSON is the intended public surface; runtime validation via `InlineKeyboardMarkup.de_json` handles shape. |
| 7 | blind | Infinite recursion in `_send_with_fallbacks` | Recursion depth is bounded by the number of optional fields that can be dropped (parse_mode, reply_markup). Unrelated `BadRequest` is re-raised after fallbacks are exhausted. |
| 8 | blind | Missing `chat_id` format validation | Telegram accepts numeric IDs, `@channelusername`, and `t.me/...` style strings; client-side regex would be brittle and is not required by AC. |
| 9 | blind | Inconsistent callback_query dictionary access | Out of 11.2 scope; belongs to Story 11.8 callback handling. |
| 10 | blind | Unused `ctx` in `factory.build_handler` | False positive; `ctx` is captured by the returned closure and used by `write_back_telegram`. |
| 11 | blind | Missing `callback_data` length validation | 64-byte limit is Telegram-specific; out of 11.2 scope and belongs to 11.8 routing. |
| 12 | blind | Hardcoded `inline:` prefix in `TelegramAdapter` | Out of 11.2 scope; belongs to 11.7/11.8 inline message editing. |
| 13 | blind | Inconsistent `parse_mode` handling frontend/backend | The builder `Select` only emits the three allowed values; `buildWriteBackParams` converts `"none"` to `null` for the backend. The only remaining gap was the re-hydration cast, now fixed. |
| 14 | blind | Missing error-case tests for `unescape_markdown_v2` | Coverage is sufficient for the 11.2 happy-path behavior; edge cases can be added in 11.3 if needed. |
| 15 | blind | Silent failure in `task-item.tsx` JSON parse | Intentional UX choice while the user is typing; the field reverts to the last valid value and the placeholder shows the expected format. |
| 1 | edge | `edit_message` returns `"None"` when `msg is True` and `message_id` is None | `msg is True` only happens for `inline_message_id` edits, and `inline_message_id` is non-null in that branch. |
| 2 | edge | `edit_message` returns `"None"` when `inline_message_id` is None and `msg is True` | `msg is True` cannot occur when `inline_message_id` is None; PTB returns a `Message` object for `chat_id`+`message_id` edits. |
| 3 | edge | `_is_keyboard_error` may drop `reply_markup` for non-keyboard errors containing `url` | The `_is_parse_mode_error` branch is checked first; the heuristic is acceptable for 11.2. |
| 4 | edge | `_is_keyboard_error` may drop `reply_markup` for non-keyboard errors containing `inline` | Same as above; acceptable heuristic. |
| 5 | edge | Invalid `parse_mode` string in `writeBackParamsFromParams` | Fixed (see patch #1). |
| 6 | edge | Invalid JSON in `reply_markup` field silently ignored | Same as blind #15; intentional while-typing behavior. |
| 7 | edge | `edit_message` with `external_peer_id` starting `inline:` but `external_message_id` is None | `external_message_id` is a required parameter; passing `None` is a caller bug. |
| 8 | edge | `edit_message_reply_markup` with `external_peer_id` starting `inline:` but `external_message_id` is None | Same as above. |
| 9 | edge | `callback_query` with no `message` and no `inline_message_id` returns `None` peer_id | Out of 11.2 scope; belongs to 11.8 callback handling. |
| 10 | edge | `answer_callback_query` with empty `callback_query_id` | Out of 11.2 scope; belongs to 11.8. |
| 11 | edge | `get_updates` offset resets to 0 when `update_id` is missing | Already deferred to 11.3. |
| 12 | edge | Multiple system Telegram accounts; `.first()` is arbitrary | Spec implies a single system account; picking the first is deterministic enough for the expected configuration. |
| 13 | edge | Multiple `ExternalChatBinding`s; `.first()` is arbitrary | Spec implies one active binding per creator/account/workspace; picking the first is acceptable. |

## Counts

- 0 `decision-needed`
- 1 `patch` (low) — applied
- 0 `defer`
- 27 `dismiss`

## Verdict

**APPROVED.** Story 11.2 now satisfies all acceptance criteria. Builder schema round-trip, action resolution/fallback behavior, and test coverage are all in place. The one re-run finding was a defensive `parse_mode` guard that has been applied and verified with `tsc` and `biome`.

## Status

- Story file `_bmad-output/implementation-artifacts/11-2-telegram-write-back-and-builder.md` updated to `status: done`.
- `sprint-status.yaml` updated: `11-2-telegram-write-back-and-builder: done`.
