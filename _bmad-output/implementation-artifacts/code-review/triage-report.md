# Code Review Triage — Telegram Client/Adapter (Story 11.7 & 11.8)

**Review spec:** `_bmad-output/implementation-artifacts/code-review/review-spec-telegram.md`  
**Findings files:**
- `blind-hunter-findings.md`
- `edge-case-hunter-findings.md`
- `acceptance-auditor-findings.md`

## Triaged findings

### decision-needed (1)

1. **Callback query dispatch scope** `[decision-needed]`  
   `view_run:` / `rerun:` handlers and `inbox_processor` callback routing are not implemented. This means the `callback_query` is parsed and persisted, but never answered or actioned.  
   *Question:* Implement the full Story 11.8 wiring (answer callback, route `view_run:`/`rerun:`, update `inbox_processor`) in this change, or defer to a follow-up story?  
   *Evidence:* `inbox_processor.py:356-435`, `commands.py`, `adapter.py:174-185`, `client.py:162-173`.

### patch (regressions / unambiguous fixes in scope)

2. **Unknown Telegram updates misclassified as `message`** `[patch]`  
   `adapter.py:22-44` now defaults `event_kind = "message"` and falls through to a blank message for unsupported update types.  
   *Fix:* restore `event_kind = "other"` fallback and ensure the empty `message` branch uses `"other"`.

3. **Edit/reply-markup flows force `chat_id` and `message_id` to `int`** `[patch]`  
   `client.py:92-94`, `:184-185` call `int(chat_id)`/`int(message_id)`, while `send_message` keeps `chat_id` as a string. This breaks channel usernames and string IDs.  
   *Fix:* pass `chat_id`/`message_id` as received; let `python-telegram-bot` coerce.

4. **`edit_message_reply_markup` is not wrapped by `_send_with_fallbacks`** `[patch]`  
   `client.py:175-187` has no `RetryAfter` or bad-keyboard fallback.  
   *Fix:* route through `_send_with_fallbacks` or add an `edit_message_reply_markup_text` wrapper.

5. **`_build_inline_keyboard_markup` swallows all exceptions and hides payload** `[patch]`  
   `client.py:31-35` catches broad `Exception`, making debugging hard.  
   *Fix:* catch `TypeError`/`ValueError` only, log the offending `reply_markup` snippet.

6. **New `reply_markup` params not declared in `BasePlatformAdapter`** `[patch]`  
   `adapter.py:140-172` adds `reply_markup` but the abstract interface does not.  
   *Fix:* add `reply_markup: dict | None = None` to `BasePlatformAdapter.send_message`/`edit_message` (other adapters can ignore).

7. **Tests miss `url` buttons and `edit_message` with `reply_markup`** `[patch]`  
   `test_telegram_client.py`/`test_telegram_adapter.py` cover only `callback_data` buttons.  
   *Fix:* add tests for `url` buttons and `edit_message(..., reply_markup=...)` forwarding.

8. **Markdown/keyboard fallback uses fragile English substrings** `[patch]`  
   `client.py:120-139` matches `"can't parse"`, `"button"`, etc.  
   *Fix:* use more robust detection — e.g., try drop parse_mode on any `BadRequest` when parse_mode was set, then try drop keyboard when keyboard was set, rather than inspecting message text. (Keep current as interim.)

### defer (pre-existing or out of current scope)

9. **`inbox_processor` does not call `answer_callback_query`** `[defer]`  
   Requires Story 11.8 wiring. Not introduced by this diff.

10. **`view_run:` / `rerun:` handlers absent** `[defer]`  
    Requires Story 11.8 command/routing implementation.

11. **Webhook persistence does not extract `external_message_id` from `callback_query["message"]`** `[defer]`  
    Related, but `gateway_webhook_routes.py` was not modified.

12. **Callback queries from `inline_message_id` cannot be dispatched** `[defer]`  
    Requires `inbox_processor` and possibly `edit_message` changes to support inline message identifiers.

13. **Only one `RetryAfter` retry** `[defer]`  
    Pre-existing pattern; not a regression.

14. **Long-poll `get_updates` loop has no exception recovery** `[defer]`  
    Pre-existing.

15. **Streaming translator chunk overwrite / final re-edit / escaped plain text / concurrency issues** `[defer]`  
    Located in `translator.py`, pre-existing and outside the current diff scope.

### dismiss (noise / acceptable)

16. **`callback_query` silently wins over `message`/`edited_message`** `[dismiss]`  
    Telegram updates do not contain both top-level keys simultaneously.

17. **Empty inbound text becomes `None`** `[dismiss]`  
    Pre-existing behavior, acceptable for downstream checks.

18. **Telegram length/empty-text limits not validated** `[dismiss]`  
    Pre-existing; callers are responsible for chunking/validating.

## Counts

- 1 `decision-needed`
- 7 `patch`
- 7 `defer`
- 3 `dismiss`
