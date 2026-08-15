# Edge Case Hunter Report — Story 21.6 Zalo Integration

This report walks the branching paths and boundary conditions of the Story 21.6 / AD-41 Zalo integration diff and lists the unhandled edge cases. Each item has a one-line title, the scenario, evidence (file:line), and a proposed guard.

## Unhandled Edge Cases

### 1. OAuth app secret is conflated with the webhook secret
- **Scenario:** `ZaloClient.from_connection` sets `secret_key` from `connection.webhook_secret` (or global `ZALO_APP_SECRET`). `refresh_access_token` then uses that value as the Zalo OA OAuth `secret_key`. A webhook secret and an OAuth app secret are different credentials; storing only `webhook_secret` means token refresh may use the wrong secret or fall back to an empty global. There is no `app_secret` column on `ZaloConnection`.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:196-198`, `nowing_backend/app/db.py:5131-5138`, `nowing_backend/app/routes/outbound_routes.py:432-443`
- **Proposed guard:** Add an `app_secret_encrypted` column to `ZaloConnection` and `ZaloConnectionCreate`; use that for `secret_key` in `from_connection`; reserve `webhook_secret` only for inbound signature verification.

### 2. Token refresh has no distributed lock, causing races and stale tokens
- **Scenario:** `ensure_valid_token` checks expiry, calls `refresh_access_token`, updates the DB, and commits without any lock. Two concurrent `send_zns_message` calls for the same connection can both see an expired token, both refresh, and both commit; the second commit may overwrite a newly issued refresh token, invalidating the first and possibly sending with a revoked token.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:269-299`, `nowing_backend/app/routes/outbound_routes.py:305-308`
- **Proposed guard:** Acquire a distributed lock keyed by `zalo:refresh:{connection.id}` before checking expiry; re-check inside the lock, refresh once, then commit.

### 3. No retry/backoff on Zalo API transient errors
- **Scenario:** `refresh_access_token`, `send_zns`, and `send_cs_message` catch all exceptions and immediately re-raise. Network blips, 429, 502, 503, or 504 responses from Zalo are never retried, so a single transient failure aborts the ZNS send or token refresh.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:247-267`, `client.py:340-347`, `client.py:369-375`
- **Proposed guard:** Classify HTTP status codes and exceptions; retry idempotent calls with exponential backoff on retryable failures.

### 4. Rate limiter loses cross-process coordination when Redis is unavailable
- **Scenario:** `acquire_token` falls back to a per-process in-memory bucket when Redis raises `RedisError` or `OSError`. Multiple workers or hosts will each keep their own bucket, so the hard per-OA 20 msg/min limit can be exceeded under concurrent multi-instance load.
- **Evidence:** `nowing_backend/app/gateway/ratelimit.py:88-117`, `nowing_backend/app/gateway/zalo/client.py:208-218`
- **Proposed guard:** Fail closed (reject or queue) when Redis is unavailable; do not silently degrade to uncoordinated local state for an external rate limit.

### 5. Rate-limit scope falls back to `"default"` when `oa_id` is missing
- **Scenario:** `ZaloClient.check_rate_limit` uses `self.oa_id or "default"`. If the client is constructed without an `oa_id`, all OAs share the `zalo:oa:default` bucket and the real per-OA rate limit is not enforced.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:208-218`
- **Proposed guard:** Require `oa_id` before sending; raise `ValueError` if it is missing, or derive it from `ZaloConnection`.

### 6. Phone normalization does not validate Vietnamese mobile format and can produce invalid numbers
- **Scenario:** `format_vietnam_phone` accepts any digit string and falls back to prefixing `84` and stripping leading zeros. For inputs like `+84 091 234 5678` it yields an 11-digit national number starting with `00`; for arbitrary 10/11-digit strings it can generate non-mobile or non-Vietnamese numbers. The frontend `cleanPhoneForZalo` has the same double-zero bug. These invalid numbers are then used for deep links and ZNS.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:27-66`, `nowing_web/components/leads/zalo-outreach-button.tsx:26-39`
- **Proposed guard:** Validate with a strict Vietnamese mobile regex and reject invalid numbers before building `zalo_url` or calling ZNS.

### 7. Webhook signature verification bypasses when global secret is missing and ignores per-connection `webhook_secret`
- **Scenario:** `zalo_inbound_webhook` uses `config.ZALO_APP_SECRET` for all webhooks, and `verify_zalo_signature` returns `True` when `secret_key` is empty. There is no way to use the per-OA `webhook_secret` stored on `ZaloConnection`. Because `app/config/__init__.py` has no ZALO environment settings, the global secret is empty by default, so the public endpoint accepts any payload.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:582-587`, `nowing_backend/app/gateway/zalo/webhook.py:52-85`, `nowing_backend/app/config/__init__.py:768-779`
- **Proposed guard:** Look up the active `ZaloConnection` by `app_id`/`oa_id` first and verify with `connection.webhook_secret`; require a non-empty secret and fail closed in production; add `ZALO_*` env settings to the config model.

### 8. Webhook signature verification does not prevent replay attacks
- **Scenario:** `verify_zalo_signature` validates the signature but never checks `timestamp`. A captured valid request can be replayed indefinitely, and a missing or far-future `timestamp` is accepted.
- **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:52-85`, `nowing_backend/app/routes/outbound_routes.py:582-587`
- **Proposed guard:** Reject events whose `timestamp` is missing or outside a short window (e.g., ±5 minutes); maintain a cache of processed `(timestamp, signature)` pairs to block exact replays.

### 9. Inbound webhooks for unknown or missing OA/app_id fall back to workspace 1
- **Scenario:** `handle_zalo_webhook_event` queries `ZaloConnection`; if none is found it hard-codes `workspace_id = 1`, creating `ZaloMessageLog` rows and possibly Telegram alerts in the wrong workspace. If both `oa_id` and `app_id` are missing and multiple active connections exist, `scalar_one_or_none()` raises `MultipleResultsFound`.
- **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:113-122`, `webhook.py:146-160`
- **Proposed guard:** Return 404 when no matching active connection exists; require `oa_id` or `app_id`; never default to workspace 1.

### 10. Webhook lead matching uses unescaped `LIKE` wildcards and weak company-name matching
- **Scenario:** `handle_zalo_webhook_event` searches `Lead.company_name.ilike(f"%{sender_id}%")`. If `sender_id` contains `%` or `_`, it becomes a SQL wildcard. It also matches any company name containing the sender's digits, not the actual phone or Zalo user ID, so replies can be attributed to the wrong lead.
- **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:134-143`
- **Proposed guard:** Escape LIKE wildcards; match on `recipient_phone` or a dedicated `zalo_user_id` field instead of `company_name`.

### 11. Inbound webhook processing has no idempotency, producing duplicate logs and alerts
- **Scenario:** If Zalo retries a webhook or the request is delivered twice, `handle_zalo_webhook_event` inserts a new `ZaloMessageLog` each time and triggers another Telegram alert, because there is no unique constraint on `external_message_id` and no cache of processed `msg_id`s.
- **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:146-176`, `nowing_backend/app/db.py:5164-5207`
- **Proposed guard:** Add a unique index on `(zalo_connection_id, external_message_id)` and `INSERT ... ON CONFLICT DO NOTHING`; cache processed `msg_id`s for the deduplication window.

### 12. ZNS send is not idempotent; duplicate tracking IDs or client retries send twice
- **Scenario:** `send_zns_message` accepts `tracking_id` and forwards it to Zalo, but it does not persist or check the ID before sending. A client retry or duplicate request with the same `tracking_id` will call Zalo twice and create two `ZaloMessageLog` rows.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:254-376`, `nowing_backend/app/gateway/zalo/client.py:330-335`
- **Proposed guard:** Create an idempotency table/cache keyed by `tracking_id` (or `tracking_id + lead_id`); write a `pending` record before the API call and return the stored result on duplicates.

### 13. ZNS consent guard treats any `legal_basis` as consent and ignores opt-out
- **Scenario:** `has_consent` is true if `lead.consent_status` is `consented`/`opted_in` **or** `lead.legal_basis` is non-empty. A lead marked `opted_out` with an old `legal_basis` still passes. There is also no audit of the `consent_confirmed` flag and no opt-out detection in inbound messages.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:271-280`, `nowing_backend/app/db.py:4473-4474`, `nowing_backend/app/gateway/zalo/webhook.py:18-49`
- **Proposed guard:** Explicitly reject `consent_status == "opted_out"`; require `consent_status in ("consented", "opted_in")` or explicit `consent_confirmed`; log the consent assertion in `ZaloMessageLog`; detect opt-out keywords in inbound messages and update consent.

### 14. Frontend ZNS schema defaults `consent_confirmed` to `true`
- **Scenario:** `znsSendRequestSchema` in the web frontend sets `consent_confirmed: z.boolean().default(true)`. A UI or caller using this schema will always send `true` without an explicit user action, bypassing the backend guard.
- **Evidence:** `nowing_web/contracts/types/leads.types.ts:152-158`
- **Proposed guard:** Remove the default or set it to `false`; require an explicit UI toggle before `sendZns` is called.

### 15. Token-refresh response not validated as a dict, causing AttributeError on unexpected JSON
- **Scenario:** `refresh_access_token` calls `resp.json()` and then, outside the `try` block, does `if "access_token" in res_data` and `res_data.get(...)`. If Zalo returns a list, string, or `null`, the `.get` or `in` operation raises `AttributeError`/`TypeError` that is not caught.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:250-267`
- **Proposed guard:** Validate `isinstance(res_data, dict)` immediately after parsing; otherwise raise a clear `RuntimeError`.

### 16. ZNS success check treats string `"0"` error codes as failure
- **Scenario:** `send_zns_message` computes `success = error_code == 0`. If Zalo returns `"error": "0"` (string), the comparison is `False` and the message is marked `failed` even though it succeeded.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:338-344`
- **Proposed guard:** Coerce `error_code` with `str(error_code) == "0"` or `int(error_code) == 0` after type checking.

### 17. `ZaloClient.from_connection` can crash on plaintext or corrupted encrypted tokens
- **Scenario:** `from_connection` calls `TokenEncryption.decrypt_token` without first checking `TokenEncryption.is_encrypted`. If the token is stored in plaintext (e.g., `SECRET_KEY` was empty when created) or is corrupted, the call raises `ValueError`/`InvalidToken`, which is only caught as a generic exception in `send_zns_message` and reported as a Zalo API error.
- **Evidence:** `nowing_backend/app/gateway/zalo/client.py:182-191`, `nowing_backend/app/utils/oauth_security.py:211-231`
- **Proposed guard:** Use `is_encrypted()` or wrap decryption in a recoverable exception; if decryption fails, mark the connection as invalid and request re-authorization.

### 18. Connection upsert is racy and can hit unique-constraint violations
- **Scenario:** `upsert_workspace_zalo_connection` SELECTs then INSERTs with no locking. Two concurrent calls for the same `(workspace_id, oa_id)` can both see no row and both INSERT, violating the unique constraint and raising an unhandled 500.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:452-483`
- **Proposed guard:** Use `INSERT ... ON CONFLICT (workspace_id, oa_id) DO UPDATE` (or a serializable transaction) and catch `IntegrityError`.

### 19. ZNS sender picks an arbitrary OA if a workspace has multiple active connections
- **Scenario:** `send_zns_message` selects `ZaloConnection` only by `workspace_id` and `is_active`. If a workspace has multiple active OA connections, `scalar_one_or_none()` may raise `MultipleResultsFound` or return a nondeterministic one.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:292-297`
- **Proposed guard:** Require the caller to specify `oa_id`, or select a single `is_primary` OA; handle multiple matches explicitly.

### 20. Inbound webhook JSON body shape not validated
- **Scenario:** `zalo_inbound_webhook` parses JSON and then immediately calls `data.get("app_id")`. If the body is a JSON array, string, or number, `data.get` raises `AttributeError` and leaks a 500 instead of a 400.
- **Evidence:** `nowing_backend/app/routes/outbound_routes.py:574-583`
- **Proposed guard:** Validate `isinstance(data, dict)` and that `oa_id`/`app_id` are strings before signature verification or dispatch.
