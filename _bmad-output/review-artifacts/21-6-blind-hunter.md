# Blind Hunter Review — Story 21.6 (Zalo Integration)

**Scope:** `nowing_backend/...` and `nowing_web/...` changes introduced in the supplied `21-6-diff.txt`. The current working tree has a handful of uncommitted follow-up fixes (e.g., `outbound_routes.py` RBAC call order was partially corrected), but the diff still contains the patterns below. Where an issue is still present in the working tree, line numbers point to the current source file; otherwise they point to the diff artifact.

---

## Critical

- **`leads_routes.py` calls `has_permission` with the wrong arity and awaits a non-coroutine**
  - **Severity:** Critical (runtime crash)
  - **Evidence:** `nowing_backend/app/routes/leads_routes.py:640-645,691`
    ```python
    has_enrich = await has_permission(
        session, auth, workspace_id, Permission.LEADS_ENRICH.value
    )
    ```
    `app.utils.rbac.has_permission` is the sync two-argument `has_permission(permissions: list[str], required: str)` re-exported from `app.db`. Passing `session, auth, workspace_id, ...` produces a `TypeError` at runtime.
  - **Fix:** Use `check_permission(session, auth, workspace_id, Permission.LEADS_ENRICH.value, ...)` for the deny-or-raise checks; use `get_user_permissions` + the sync `has_permission` only when you need a boolean.

- **Webhook signature verification bypasses on missing secret and accepts unsafe SHA-256 constructions**
  - **Severity:** Critical
  - **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:64-65,71-85` and `nowing_backend/app/routes/outbound_routes.py:586-587`
    ```python
    if not secret_key:
        return True  # Dev / test environment bypass if no secret configured
    ```
    The verifier also accepts raw `sha256(app_id|body|timestamp|secret)` and `sha256(secret|timestamp|body)` concatenations, which are not HMAC and are vulnerable to length-extension-style forgery. The public `zalo_inbound_webhook` uses a global `ZALO_APP_SECRET` instead of the per-OA `webhook_secret`.
  - **Fix:** Remove the `not secret_key` bypass; always use `hmac.new(secret, raw_body, sha256).hexdigest()`; enforce a fresh timestamp window (e.g., ±5 min); derive the secret from the `ZaloConnection` matching the event's `app_id`/`oa_id`.

- **Webhook handler falls back to arbitrary workspace / workspace 1 and spams Telegram on every text message**
  - **Severity:** Critical (data mis-routing + alert DoS)
  - **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:113-122,167-176`
    ```python
    workspace_id = connection.workspace_id if connection else 1
    ...
    if has_intent or event_name == "user_send_text":
        telegram_result = await send_telegram_lead_alert(...)
    ```
    If `oa_id`/`app_id` are missing it picks the first active `ZaloConnection`; if no connection is found it writes to workspace `1`. It then sends a Telegram alert for *every* `user_send_text` event, not just high-intent ones, with no idempotency check on `msg_id`.
  - **Fix:** Reject events that cannot be mapped to a connection; never default to workspace `1`; remove `or event_name == "user_send_text"`; deduplicate on `external_message_id` before logging/sending.

- **`ZaloClient` conflates the OA OAuth app secret with the webhook secret and may ship encrypted tokens as plaintext**
  - **Severity:** Critical
  - **Evidence:** `nowing_backend/app/gateway/zalo/client.py:180-201` and `nowing_backend/app/routes/outbound_routes.py:432-443`
    ```python
    secret_key=connection.webhook_secret
    or getattr(config, "ZALO_APP_SECRET", ""),
    ```
    `webhook_secret` is being reused as the OAuth `secret_key` for token refresh. The model has no `app_secret` column, so there is no clean place to store the actual OAuth app secret. Also, if `config.SECRET_KEY` is empty, tokens are stored plaintext (`enc = None`).
  - **Fix:** Add `app_secret_encrypted` (or similar) to `ZaloConnection`, separate from `webhook_secret`; require `SECRET_KEY` and fail closed if it is not configured; never pass the encrypted ciphertext as an `access_token`.

- **Model changes for `VerifiedContact` / `PhoneWaterfallLog` are not backed by a migration in the diff**
  - **Severity:** Critical (schema drift)
  - **Evidence:** `21-6-diff.txt:146-253` modifies `VerifiedContact` (nullable `email`, `enrichment_request_id`, new `is_valid`/`refunded_at`/`invalid_reason`) and adds `PhoneWaterfallLog`, but the only migration in the diff is `212_add_zalo_gateway_tables.py`.
  - **Fix:** Include the companion migration (`213_add_phone_waterfall_logs_and_refund.py`) so `alembic upgrade head` stays in sync with the ORM.

- **`outbound_routes.py` (new file) uses a broken `check_permission` call and non-existent permissions**
  - **Severity:** Critical (would crash on import/call)
  - **Evidence:** `21-6-diff.txt:1944,2019,2181,2276`
    ```python
    await check_permission(auth, target_ws, Permission.VIEW_DOCUMENTS, session=session)
    ```
    This reverses the `session`/`auth` argument order, uses `session=session` as a keyword for `error_message`, and references `Permission.VIEW_DOCUMENTS`, `EDIT_DOCUMENTS`, and `ADMIN_USERS`, which do not exist in the `Permission` enum.
  - **Fix:** Use `await check_permission(session, auth, target_ws, Permission.LEADS_READ)` (or `LEADS_WRITE` / `SETTINGS_UPDATE` as appropriate) and pass `.value` if `check_permission` expects plain strings.

## High

- **Async Celery workers run `asyncio.run` inside a sync task and swallow refund failures**
  - **Severity:** High
  - **Evidence:** `nowing_backend/app/tasks/phone_waterfall_worker.py:69,109-116`
    ```python
    return asyncio.run(_run())
    ...
    except Exception as exc:
        logger.exception(...)
        return {"refunded": False, "error": str(exc)}
    ```
    `asyncio.run` inside a Celery worker with an existing event loop can fail; `auto_refund_lead_task` catches and returns a dict on every exception, so `max_retries=1` is effectively ignored.
  - **Fix:** Use an async Celery task or a worker-scoped loop; re-raise the exception for Celery’s retry machinery.

- **Frontend `znsSendRequestSchema` defaults `consent_confirmed` to `true`, gutting the consent guardrail**
  - **Severity:** High (regulatory)
  - **Evidence:** `nowing_web/contracts/types/leads.types.ts:156`
    ```ts
    consent_confirmed: z.boolean().default(true),
    ```
    The backend explicitly checks this flag for Decree 356/ZNS compliance, but the frontend will always send `consent_confirmed: true` unless the caller explicitly overrides it.
  - **Fix:** Default to `false` and require a user action (checkbox) before sending.

- **`format_vietnam_phone` falls back to invalid 84-prefixed numbers**
  - **Severity:** High
  - **Evidence:** `nowing_backend/app/gateway/zalo/client.py:55-60`
    ```python
    clean_phone = digits
    international_phone = (
        digits if digits.startswith("84") else f"84{digits.lstrip('0')}"
    )
    ```
    Arbitrary digit strings are accepted and prefixed with `84`, producing invalid Zalo/ZNS recipient numbers.
  - **Fix:** Reject non-conforming inputs; accept only 10-digit national (`0x...`), 11-digit `84...`, or 9-digit legacy formats; raise for everything else.

- **Buying-intent detector is naïve, has no negation handling, and matches substrings**
  - **Severity:** High (false positives / alert spam)
  - **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:18-49,88-96`
    Keywords such as `giá`, `zalo`, `inbox`, `alo`, and `phone` match as substrings; phrases like “không quan tâm” or “không hẹn” still trigger because negation is not handled.
  - **Fix:** Replace substring scanning with a weighted intent model or at least a smaller phrase list and a negation regex; do not treat generic words as buying signals.

- **Webhook tries to match a lead by treating the Zalo `sender_id` as a company name**
  - **Severity:** High (wrong lead / privacy)
  - **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:134-143`
    ```python
    Lead.company_name.ilike(f"%{sender_id}%")
    ```
    `sender_id` is a Zalo user id, not a company name. This can return an unrelated lead or expose another workspace’s data if there is a numeric collision.
  - **Fix:** Look up by `lead.phone` / `verified_contacts.phone` or create a new lead; never match `company_name` against a Zalo user id.

- **`send_zns_message` treats any non-empty `legal_basis` as consent**
  - **Severity:** High (compliance)
  - **Evidence:** `nowing_backend/app/routes/outbound_routes.py:271-275`
    ```python
    or bool(lead.legal_basis)
    ```
    Any non-empty `legal_basis` string (e.g., `"legitimate_interest"`) satisfies the consent guard. Decree 356 requires explicit consent for ZNS.
  - **Fix:** Only accept a closed set of consent statuses (`consented`, `opted_in`) plus an explicit `consent_confirmed` flag from the caller; audit the consent basis.

- **Duplicate FastAPI decorators on the same handler will collide in OpenAPI**
  - **Severity:** High
  - **Evidence:** `nowing_backend/app/routes/outbound_routes.py:168-177,244-253,505-513`
    Each of `generate_zalo_draft`, `send_zns_message`, and `dispatch_lead_telegram_alert` is decorated with two `@router.post` paths. FastAPI will generate duplicate operation ids for the same function and the unscoped `/leads/{lead_id}` route exposes workspace-scoped actions at a non-standard path.
  - **Fix:** Remove the unscoped duplicate routes or split into separate handler functions.

## Medium

- **`ZaloClient.send_cs_message` does not ensure a valid token**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/gateway/zalo/client.py:350-375`
    The method checks for an `access_token` but never refreshes it, so an expired token causes a runtime failure.
  - **Fix:** Call `await self.ensure_valid_token(...)` at the start of `send_cs_message`.

- **`recipient_phone` is set to the Zalo `sender_id`, not a phone number**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:146-151`
    ```python
    recipient_phone = sender_id if sender_id and sender_id.isdigit() else None
    ```
    Zalo `sender_id` is a user id, not a phone. This corrupts the log and the Telegram deep link.
  - **Fix:** Leave `recipient_phone` as `None` for inbound events; pull the phone from the matched `lead`/`verified_contact`.

- **`TelegramAlertRequest.chat_id` has no validation or workspace ownership check**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/routes/outbound_routes.py:111-114,538-548`
    A caller with `LEADS_READ` can supply an arbitrary `chat_id` and have the Telegram alert delivered there.
  - **Fix:** Restrict `chat_id` to the workspace’s verified `ExternalChatBinding` records unless the caller has a workspace-admin permission.

- **`ZaloMessageLog` stores raw `template_data` and inbound webhook payloads without redaction**
  - **Severity:** Medium (privacy)
  - **Evidence:** `nowing_backend/app/routes/outbound_routes.py:324-325` and `nowing_backend/app/gateway/zalo/webhook.py:157-158`
    ```python
    template_data=payload.template_data,
    template_data=event_data,
    ```
    These JSONB fields may contain PII. Access is not restricted in the read schemas returned by the API.
  - **Fix:** Redact known PII fields before logging; scope access to users with `CONTACTS_READ`.

- **`_resolve_lead_phone` checks a non-existent `contact.phone_number` field**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/routes/outbound_routes.py:156-159`
    ```python
    if getattr(contact, "phone_number", None):
        return str(contact.phone_number)
    ```
    `VerifiedContact` has `phone`, not `phone_number`. The branch is dead code and could hide a future model mismatch.
  - **Fix:** Remove the `phone_number` branch and use `contact.phone`.

- **`ZaloClient` rate-limiter fallback is per-process, not per-deployment**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/gateway/zalo/client.py:208-218` and `nowing_backend/app/gateway/ratelimit.py:88-120`
    If Redis is unavailable, the in-memory bucket is per worker process, so a multi-pod deployment can exceed Zalo’s rate limit.
  - **Fix:** Either fail closed when Redis is down or use a shared coordination mechanism; do not silently degrade to per-process limits.

- **`app/db.py` reintroduces a circular top-level import of `SpatialPlanningZone`**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/db.py:4762`
    ```python
    from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone
    ```
    `spatial_planning/models.py` imports `BaseModel, TimestampMixin` from `app.db`. The import currently works because `BaseModel` is already defined, but it is fragile and was explicitly avoided before by importing inside `create_db_and_tables`.
  - **Fix:** Register the model lazily or keep the import inside `create_db_and_tables` to avoid coupling at import time.

- **Inconsistent delete semantics: SQLAlchemy `cascade="delete-orphan"` vs DB `ON DELETE SET NULL`**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/db.py:5157-5161,5222-5224` and `alembic/versions/212_add_zalo_gateway_tables.py` (migr `ON DELETE SET NULL` on `lead_id`/`zalo_connection_id`)
    `ZaloConnection.message_logs` and `Lead.zalo_message_logs` declare `cascade="all, delete-orphan"`, but the migration uses `ON DELETE SET NULL` for the corresponding foreign keys. Behavior differs between SQLAlchemy-managed and raw SQL deletes.
  - **Fix:** Choose one behavior (keep logs with null FKs on parent delete) and align the ORM and migration.

- **`upsert_workspace_zalo_connection` always sets `is_active=True`, so it cannot be deactivated or revoked**
  - **Severity:** Medium
  - **Evidence:** `nowing_backend/app/routes/outbound_routes.py:470-471`
    Every upsert re-activates the connection. There is no disable/soft-delete endpoint.
  - **Fix:** Add an `is_active` field to `ZaloConnectionCreate` or a separate `DELETE /workspaces/{id}/zalo/connection` endpoint.

## Low

- **`generate_assisted_outbound_draft` hard-codes the product name and lacks input validation**
  - **Severity:** Low
  - **Evidence:** `nowing_backend/app/gateway/zalo/client.py:69-104`
    The function always says “liên hệ từ Nowing” and interpolates arbitrary lead fields with no length or character validation.
  - **Fix:** Make the brand configurable and cap/sanitize the injected values.

- **`ZaloClient` HTTP client uses a fixed 15 s timeout and no retry/backoff**
  - **Severity:** Low
  - **Evidence:** `nowing_backend/app/gateway/zalo/client.py:204-206`
    A single hard-coded timeout and no retries make Zalo flakiness surface directly as 502s.
  - **Fix:** Make the timeout configurable and add a small idempotent retry with exponential backoff.

- **`LeadCard.tsx` event listener returns a cleanup that is never registered**
  - **Severity:** Low
  - **Evidence:** `nowing_web/components/leads/LeadCard.tsx:62-74` (supplied diff)
    The listener returns `() => clearTimeout(timer)`, but that return value is discarded by `addEventListener`; if multiple events fire before unmount, the previous timers are not cleared.
  - **Fix:** Track the timer in a ref and clear it in the `useEffect` cleanup function, not in the event handler.

- **`handle_zalo_webhook_event` commits the inbound log before the Telegram alert attempt and has no idempotency**
  - **Severity:** Low
  - **Evidence:** `nowing_backend/app/gateway/zalo/webhook.py:160-176`
    A failure in `send_telegram_lead_alert` after `session.commit()` leaves a log row with no record that the downstream alert failed, and repeated delivery of the same `msg_id` creates duplicate rows.
  - **Fix:** Add a unique constraint or upsert on `external_message_id` (per workspace/connection) and wrap the log + alert in a single transaction or clearly record alert outcome.

- **`PhoneResolutionResponse` hard-codes 1.5 credit cost even on `pending` async results**
  - **Severity:** Low
  - **Evidence:** `nowing_backend/app/routes/leads_routes.py:595-602`
    The async endpoint returns `cost_credits=1.5, cost_micros=1500000` before any work is done, which is misleading if the waterfall later fails or is free.
  - **Fix:** Return `0` or `null` for `cost_*` in the `pending` async response and update when the task completes.
