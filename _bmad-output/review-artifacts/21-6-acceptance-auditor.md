# Story 21.6 Zalo Integration — Acceptance Audit

**Diff reviewed:** `_bmad-output/review-artifacts/21-6-diff.txt`  
**Spec:** `_bmad-output/implementation-artifacts/stories/21-6-zalo-integration.md`

## Auditor's note on the diff vs. the working tree

The audit was run against `21-6-diff.txt`. During the review I discovered that this diff is **not the same** as the current checked-out working tree. `git status` and `git diff` show uncommitted changes (notably in `nowing_backend/app/routes/outbound_routes.py` and `nowing_web/components/leads/zalo-outreach-button.tsx`) that already fix some of the issues below. If this diff is the patch under review, it should be regenerated from the current working tree before acceptance.

## Findings

### 1. [CRITICAL] `outbound_routes.py` uses non-existent `Permission` values and calls `check_permission` with the wrong argument order
- **AC violated:** AC1, AC2, AC4 (all Zalo outbound/connection routes are broken in the diff).
- **Evidence:**
  - `21-6-diff.txt` L1771 imports `Permission` from `app.db`.
  - `21-6-diff.txt` L1944, L2019, L2145, L2181, L2276 call `Permission.VIEW_DOCUMENTS`, `Permission.EDIT_DOCUMENTS`, and `Permission.ADMIN_USERS`.
  - The `Permission` StrEnum in `app/db.py` (baseline, confirmed in the checked-out tree at L302–426) has no such members. Valid equivalents include `LEADS_READ`, `LEADS_WRITE`, `SETTINGS_VIEW`, `SETTINGS_UPDATE`.
  - `21-6-diff.txt` L1944 etc. call `check_permission(auth, target_ws, Permission.XXX, session=session)`, but `app/utils/rbac.py` (checked-out L129–134) signature is `check_permission(session, auth, workspace_id, required_permission, ...)`.
- **Recommended fix:** Replace the non-existent permission constants with valid ones, put the arguments in the correct order (`session, auth, workspace_id, Permission.XXX`), and ensure the final diff matches the corrected working tree.

### 2. [HIGH] Webhook signature verification is insecure and conflates the OAuth app secret with the webhook secret
- **AC violated:** AC3, AC4 (security and Decree 356/compliance).
- **Evidence:**
  - `21-6-diff.txt` L678: `ZaloClient.from_connection` sets `secret_key=connection.webhook_secret or config.ZALO_APP_SECRET`, using the webhook secret for OAuth token refresh.
  - `21-6-diff.txt` L1108–1109: `verify_zalo_signature` returns `True` if `secret_key` is empty.
  - `21-6-diff.txt` L2337: `zalo_inbound_webhook` uses the global `config.ZALO_APP_SECRET` for verification instead of the per-connection `webhook_secret`.
- **Recommended fix:** Add a dedicated `app_secret` column/field for OAuth; verify webhook signatures using the matched `ZaloConnection.webhook_secret`; reject webhooks when no secret is configured (fail-closed).

### 3. [HIGH] Inbound Zalo replies are not matched to the correct lead
- **AC violated:** AC3 ("Zalo reply ... logged in the lead's activity timeline").
- **Evidence:**
  - `21-6-diff.txt` L1177–1187: the lead lookup does `Lead.company_name.ilike(f"%{sender_id}%")` where `sender_id` is the Zalo user ID, not a company name.
  - There is no phone or `recipient_zalo_id` lookup, and no stored mapping from Zalo user IDs to leads.
- **Recommended fix:** Match by normalized `VerifiedContact.phone` or maintain a `zalo_user_id` mapping; stop matching `company_name` against a Zalo user ID.

### 4. [HIGH] Zalo replies are persisted but not exposed on the lead activity timeline
- **AC violated:** AC3.
- **Evidence:**
  - `21-6-diff.txt` creates `zalo_message_logs` (L35–79, L327–438) and writes to it in the webhook, draft, and ZNS endpoints.
  - No GET endpoint returns these logs for a lead, and the `LeadRead` Pydantic schema is not extended with a `zalo_messages` field.
- **Recommended fix:** Add `GET /workspaces/{workspace_id}/leads/{lead_id}/zalo-messages`, include `zalo_message_logs` in the lead response, and render them in the frontend lead detail view.

### 5. [HIGH] No unsubscribe / opt-out handling for inbound Zalo messages
- **AC violated:** AC4, Task 3.2.
- **Evidence:**
  - `21-6-diff.txt` `webhook.py` L1062–1093 lists only positive buying-intent keywords.
  - `21-6-diff.txt` L1190–1205 logs inbound text but never updates `consent_status`/`legal_basis` on `Lead` or `VerifiedContact`.
  - `send_zns_message` checks consent at send time but does not react to an opt-out reply.
- **Recommended fix:** Add Vietnamese opt-out keywords (e.g. "hủy", "từ chối", "stop", "không quan tâm"), set `consent_status="opted_out"` when matched, and block ZNS sends to opted-out leads.

### 6. [MEDIUM] Telegram lead alert fires on every `user_send_text` event, not just buying intent
- **AC violated:** Task 2.3 / Task 2.5.
- **Evidence:**
  - `21-6-diff.txt` L1211: `if has_intent or event_name == "user_send_text":` triggers an alert for all inbound text events.
- **Recommended fix:** Remove `or event_name == "user_send_text"` and dispatch Telegram alerts only when `has_intent` is `True`.

### 7. [MEDIUM] Frontend ZNS consent flag defaults to `true`, contradicting the backend
- **AC violated:** AC4.
- **Evidence:**
  - `21-6-diff.txt` L3466: `nowing_web/contracts/types/leads.types.ts` `znsSendRequestSchema` has `consent_confirmed: z.boolean().default(true)`.
  - `21-6-diff.txt` L1824: backend `ZnsSendRequest` has `consent_confirmed: bool = Field(default=False)`.
- **Recommended fix:** Change the frontend default to `false` and require an explicit user opt-in (e.g. a checkbox) before calling `sendZns`.

### 8. [MEDIUM] The "AI draft" is a hard-coded template, not AI-generated
- **AC violated:** AC2, Task 2.1.
- **Evidence:**
  - `21-6-diff.txt` L550–632: `generate_assisted_outbound_draft` concatenates fixed Vietnamese strings based on source/intent; no LLM is called.
- **Recommended fix:** Either rename the feature to "template-assisted draft" or integrate the existing LLM service to generate the message from a prompt.

### 9. [MEDIUM] ZNS send API exists but has no UI entry point
- **AC violated:** AC2.
- **Evidence:**
  - `21-6-diff.txt` `leads-api.service.ts` L3581–3593 adds `sendZns`.
  - `21-6-diff.txt` `zalo-outreach-button.tsx` L3222–3439 only calls `getZaloDraft` and opens a deep link; no component in the diff calls `sendZns`.
- **Recommended fix:** Add a ZNS send action to the lead card/table (template selector + explicit consent toggle) that calls `leadsApiService.sendZns`.

### 10. [MEDIUM] No Zalo OA OAuth redirect/callback flow
- **AC violated:** AC1, Task 1.2.
- **Evidence:**
  - `21-6-diff.txt` `outbound_routes.py` L1747–2346 contains only a manual token CRUD endpoint `/workspaces/{workspace_id}/zalo/connection`.
  - No `/zalo/auth` or `/gateway/zalo/oauth-callback` route performs the authorization-code exchange.
- **Recommended fix:** Add an OAuth authorize-URL route and a callback handler, or update the story task list to reflect a manual token-upload flow.

### 11. [LOW] `_resolve_lead_phone` checks a non-existent `phone_number` attribute on `VerifiedContact`
- **AC violated:** AC2.
- **Evidence:**
  - `21-6-diff.txt` L1905–1911: `for contact in lead.verified_contacts: if getattr(contact, "phone_number", None) ... if getattr(contact, "phone", None)`.
  - The `VerifiedContact` model in the same diff (L1670–1673 / `app/db.py` L4673) defines only a `phone` column.
- **Recommended fix:** Remove the `phone_number` branch and resolve from `contact.phone`.

### 12. [LOW] Webhook falls back to hard-coded workspace `1` when no connection is found
- **AC violated:** AC3.
- **Evidence:**
  - `21-6-diff.txt` L1166: `workspace_id = connection.workspace_id if connection else 1`.
- **Recommended fix:** Return `401 Unauthorized` or `404 Not Found` when the webhook cannot be associated with a `ZaloConnection`; do not default to workspace `1`.

### 13. [PROCESS] The diff contains substantial out-of-scope Story 21.3 / 21.10 code and does not match the working tree
- **AC / scope:** N/A — scope/artifact issue.
- **Evidence:**
  - `21-6-diff.txt` L1230–1368 adds `PhoneResolution*`, `ReverseIcp*`, `BuyerPersona`, `FilterPresets` to `lead_intelligence/schemas.py`.
  - `21-6-diff.txt` L1558–1746 adds `resolve-phone`, `report-invalid-phone`, and `reverse-icp` endpoints to `leads_routes.py`.
  - `21-6-diff.txt` L2347–2461 adds `phone_waterfall_worker.py`.
  - `git status` / `git diff` show 21 additional files changed in the working tree (including `outbound_routes.py` and `zalo-outreach-button.tsx`) that are not in the provided diff.
  - The 21.3/21.10 changes in the diff also contain likely bugs (e.g. `leads_routes.py` awaiting `has_permission` with 4 arguments, but `app.db.has_permission` is a sync 2-argument helper).
- **Recommended fix:** Regenerate the review diff from the intended branch or current working tree; keep Story 21.3 and 21.10 changes in their own story-specific diffs.
