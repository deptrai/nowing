# Blind Hunter Findings for Story 11.2

## 1. Missing null check in callback_query parsing
**File:** `nowing_backend/app/gateway/telegram/adapter.py`, lines 98-99
**Evidence:** `str(user["id"]) if user.get("id") is not None else None`
**Explanation:** The code accesses `user["id"]` with a null check, but then accesses `callback_query.get("data")` without checking if `callback_query` is None. If `callback_query.get("from")` returns None, `user` becomes `{}` and `user.get("id")` returns None, but the code still tries to access `callback_query.get("data")` which could fail if callback_query is malformed.

## 2. Duplicate fallback logic in _send_with_fallbacks
**File:** `nowing_backend/app/gateway/telegram/client.py`, lines 390-431
**Evidence:** Lines 390-402 and 412-424 contain nearly identical parse_mode fallback logic
**Explanation:** The function has duplicate code blocks for dropping parse_mode - one specific to parse errors and one generic fallback. This violates DRY and creates maintenance burden. The specific check at line 390 will never reach the generic fallback at line 412 for parse errors.

## 3. Overly broad exception handling in get_updates
**File:** `nowing_backend/app/gateway/telegram/client.py`, lines 511-517
**Evidence:** `except Exception:` catches all exceptions
**Explanation:** Catching bare `Exception` swallows critical errors like KeyboardInterrupt, SystemExit, or memory errors. Should catch specific exceptions (e.g., telegram.error.TelegramError, network errors) to allow proper error propagation for system-level failures.

## 4. Missing validation on reply_markup structure
**File:** `nowing_backend/app/gateway/telegram/client.py`, lines 249-271
**Evidence:** `_build_inline_keyboard_markup` only checks for `inline_keyboard` key being a list
**Explanation:** The function doesn't validate the structure of the inline_keyboard array itself. Malformed nested structures (e.g., non-dict items, missing required keys like "text") will fail at the Telegram API level instead of being caught early, making debugging harder.

## 5. Unsafe string interpolation in error message
**File:** `nowing_backend/app/gateway/telegram/client.py`, line 246
**Evidence:** `f"{name} must be a numeric string, got {value!r}"`
**Explanation:** While using `!r` is safer than raw interpolation, the value could still be extremely long or contain control characters, potentially causing log injection or excessive log size. Should truncate or sanitize the value in error messages.

## 6. Type inconsistency in reply_markup parameter
**File:** `nowing_backend/app/gateway/telegram/adapter.py`, line 118
**Evidence:** `reply_markup: dict | None = None`
**Explanation:** The type hint is `dict | None` but the actual expected structure is a specific JSON schema with `inline_keyboard` key. A more precise type hint or a TypedDict would catch structural errors at type-check time rather than runtime.

## 7. Potential infinite recursion in _send_with_fallbacks
**File:** `nowing_backend/app/gateway/telegram/client.py`, lines 400-402, 407-409, 422-424, 429-431
**Evidence:** Recursive calls to `_send_with_fallbacks` without depth limiting
**Explanation:** If Telegram returns BadRequest for reasons unrelated to parse_mode or reply_markup (e.g., chat not found), the function will recursively call itself after dropping fields. If the error persists, this could lead to stack overflow. Should add a max recursion depth counter.

## 8. Missing validation on chat_id format
**File:** `nowing_backend/app/gateway/telegram/client.py`, line 283
**Evidence:** Only validates `reply_to_message_id` as numeric, not `chat_id`
**Explanation:** The function validates `reply_to_message_id` is numeric but doesn't validate `chat_id`. Telegram chat IDs can be numeric or usernames (starting with @). The code should validate the format matches the expected pattern or let the API handle it consistently.

## 9. Inconsistent error handling in callback query parsing
**File:** `nowing_backend/app/gateway/telegram/adapter.py`, lines 61-90
**Evidence:** No validation that required fields exist before dictionary access
**Explanation:** The code uses `.get()` for some fields but directly accesses `chat["id"]` and `message["message_id"]` without checking if those keys exist. If Telegram sends malformed data, this will raise KeyError instead of handling it gracefully like the rest of the function.

## 10. Unused parameter in factory.py
**File:** `nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py`, line 1087
**Evidence:** `build_handler` accepts `ctx: ActionContext` but doesn't use it directly
**Explanation:** The `ctx` parameter is passed to the closure but only used by the inner `handle` function via closure capture. While not incorrect, this is confusing - either document that ctx is captured by closure or pass it explicitly to handle() for clarity.

## 11. Missing length validation on callback_data
**File:** `nowing_backend/app/gateway/telegram/adapter.py`, line 99
**Evidence:** `text=callback_query.get("data")` without length check
**Explanation:** Telegram callback_data has a 64-byte limit. The code doesn't validate this before passing to downstream systems, which could cause truncation or errors in routing logic that expects short command strings.

## 12. Hardcoded magic string "inline:" prefix
**File:** `nowing_backend/app/gateway/telegram/adapter.py`, lines 88, 135, 171
**Evidence:** `f"inline:{inline_message_id}"` and `startswith("inline:")`
**Explanation:** The "inline:" prefix is a magic string used in multiple places without being defined as a constant. This creates a maintenance burden if the prefix needs to change. Should be a module-level constant like `INLINE_MESSAGE_PREFIX = "inline:"`.

## 13. Inconsistent parse_mode handling between frontend and backend
**File:** `nowing_web/lib/automations/builder-schema.ts`, lines 628, 653-656
**Evidence:** Frontend uses "none" string, backend converts to null
**Explanation:** The frontend schema allows "none" as a string value but the backend expects null. The conversion logic at lines 653-656 is fragile - if the frontend sends "None" (capitalized) or other variations, it won't be converted. This creates a potential for parse_mode to be sent as a string when backend expects null.

## 14. Missing test for error case in formatting
**File:** `nowing_backend/tests/unit/gateway/test_formatting.py`, lines 595-597
**Evidence:** Only tests happy path for unescape_markdown_v2
**Explanation:** The test only validates that unescape works correctly but doesn't test edge cases like empty strings, strings without backslashes, or strings with invalid escape sequences. The regex could fail unexpectedly on malformed input.

## 15. Silent failure in JSON parsing UI
**File:** `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`, lines 847-852
**Evidence:** Empty catch block ignores JSON parse errors
**Explanation:** When users type invalid JSON in the reply_markup field, the error is silently ignored. This provides no feedback to the user that their input is invalid, leading to confusion when the keyboard doesn't appear. Should show an error message or validation state.
