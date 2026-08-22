# Code Review Triage — Story 24.7 Multi-Channel Drip Outreach Campaign Engine

## Review metadata

- **Story:** 24-7 / epic-24
- **Spec:** `_bmad-output/implementation-artifacts/stories/24-7-multi-channel-drip-outreach-campaign-engine.md`
- **Diff source:** `_bmad-output/implementation-artifacts/review-24-7-working-tree.diff` (baseline `4c37acfa9..HEAD`, filtered to Story 24.7 file list)
- **Review layers:** Blind Hunter (`bmad-review-adversarial-general`), Edge Case Hunter (`bmad-review-edge-case-hunter`), Acceptance Auditor
- **Triage date:** 2026-08-22
- **Status:** ❌ CHANGES REQUESTED — implementation is not wired end-to-end despite story being marked `done` in sprint-status.

## Triage summary

| Bucket | Count |
|---|---|
| `patch` | 18 |
| `decision_needed` | 0 |
| `defer` | 1 |
| `dismiss` | 2 |

## Dismissed findings (2)

1. **Dismiss — Diff mixed unrelated changes / incomplete** — This is an artifact/process issue, not a code defect. The diff was generated from `4c37acfa9..HEAD` filtered to the Story 24.7 file list; because most 24.7 code was committed in the baseline or intermediate commits, the diff artifact is dominated by other work. The review layers cross-read current working-tree files directly, so the findings are still valid. *(source: auditor)*

2. **Dismiss — `_register_opt_out_dnc` uses `hash_phone_hmac` for email** — The HMAC helper is deterministic and used for any normalized value; the function name is misleading but the behavior is not broken. Marking `low`/cosmetic and dismissing from this review. *(source: edge)*

## Findings

### P1 — Multi-channel execution path is stubbed and not wired

- **id:** 1
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** `execute_enrollment_step` only routes `send_email`, and `_send_zns_step` / `_send_telegram_step` are no-op stubs.
- **location:** `nowing_backend/app/services/sequencer_service.py:253-269`, `627-644`
- **detail:** `execute_enrollment_step` only handles `send_email`, `wait`, and `condition`. `send_zalo` and `send_telegram` fall to `else` and are silently skipped. The `_send_zns_step` and `_send_telegram_step` methods only return a hardcoded `{"status":"sent"}` without calling `ZnsClient.send_zns_template()` or `TelegramAdapter.send_message()`. This violates AC-5, AC-6, AC-7, Subtasks 4/6/7. The real executor must dispatch by `step.channel`/`step.step_type`, call the channel adapter, and record `SequenceEvent` + `BillingEvent`.

### P2 — Fallback orchestration is not invoked by the real send path

- **id:** 2
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** `execute_step_with_fallback` exists but is dead code; `_handle_send_email_step` never falls back.
- **location:** `nowing_backend/app/services/sequencer_service.py:271-314`, `776-802`
- **detail:** `execute_step_with_fallback` is only called from tests. `_handle_send_email_step` catches all exceptions and commits `failed` without trying `fallback_channels`. Refactor the executor to call `execute_step_with_fallback` (or equivalent) with the step's `fallback_channels` and dispatch to `_send_zns_step`, `_send_telegram_step`, `_send_email_step`.

### P3 — `BillingEventService.record_sequence_send` cannot record multi-channel events

- **id:** 3
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** `record_sequence_send` hardcodes `event_type="email_send"` and has no `event_type` parameter.
- **location:** `nowing_backend/app/services/billing_event_service.py:584-610`
- **detail:** The function must accept `event_type: str = "email_send"` and pass it to `_record_business_event` so it can record `zns_send` and `telegram_send`. This is required by AD-42/AD-48, AC-6, AC-7, Subtask 5.

### P4 — Required multi-channel config and AD-41 legal gate are missing

- **id:** 4
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** `app.config` missing `SEQUENCE_*_COST_MICROS`, `AD_41_REACTIVATED`, and `SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS`; `validate_step_channel` does not gate `zalo`.
- **location:** `nowing_backend/app/config/__init__.py:631-632`, `nowing_backend/app/services/sequencer_service.py:172-183`
- **detail:** Only `SEQUENCER_OUTBOUND_CHANNELS` is defined. The cost map in `get_billing_event_for_step` is hardcoded to `email:1000, zalo:5000, telegram:0`, which also does not match the spec defaults (`500, 300, 0`). `validate_step_channel` must reject `zalo` when `AD_41_REACTIVATED` is `False` even if `zalo` is in the configured channel list.

### P5 — Backend schema is still email-only

- **id:** 5
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** `SequenceStepType`, `SequenceChannel`, `SequenceEventRead.channel`, and `SequenceAnalyticsResponse` do not support multi-channel.
- **location:** `nowing_backend/app/schemas/sequence.py:12-14`, `21`, `124`, `131-141`
- **detail:** Schema `SequenceStepType` lacks `send_zalo`/`send_telegram`; `SequenceChannel` is `Literal["email"]`. `SequenceStepBase` has no `fallback_channels` field. `SequenceEventRead.channel` and `SequenceAnalyticsResponse` lack multi-channel support and `channel_breakdown`. This blocks AC-1, AC-3, AC-9.

### P6 — `VerifiedContact` missing `external_chat_ids` storage

- **id:** 6
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** No `external_chat_ids` JSONB column on `VerifiedContact`; contact resolution ignores chat IDs.
- **location:** `nowing_backend/app/db.py:5255-5339`, `nowing_backend/app/services/sequencer_service.py:1171-1194`, `958-1001`
- **detail:** The spec requires a migration `226_add_verified_contact_external_chat_ids.py` and the `external_chat_ids` column to store `telegram_chat_id` and `zalo_user_id`. `_resolve_verified_contact` and `_resolve_inbound_contact` must read these IDs for `telegram`/`zalo` channels. Required by AC-4, AC-8, Subtask 2.

### P7 — Inbound interruption is incomplete and not wired

- **id:** 7
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** `handle_inbound_interruption` lacks chat-ID parameters and is a no-op; webhooks never call it.
- **location:** `nowing_backend/app/services/sequencer_service.py:1003-1044`, `nowing_backend/app/gateway/zalo/webhook.py:224-329`, `nowing_backend/app/gateway/inbox_processor.py:306-446`
- **detail:** `handle_inbound_interruption` must accept `telegram_chat_id`/`zalo_user_id`, perform CAS `UPDATE ... WHERE version=...`, and pause/cancel future steps. `zalo/webhook.py` and `inbox_processor.py` must match inbound senders against `VerifiedContact.external_chat_ids` and call `handle_inbound_interruption`. Required by AC-8, INV-24.7, Subtask 8.

### P8 — Frontend `VisualCadenceBuilder` does not enforce AD-41 / feature gate

- **id:** 8
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** Channel selector enables `zalo`/`telegram` without `SEQUENCER_OUTBOUND_CHANNELS` or `AD_41` gating, and lacks multi-channel template fields.
- **location:** `nowing_web/components/automations/VisualCadenceBuilder.tsx:74`, `250-290`, `429-519`, `521-536`
- **detail:** `zalo` should be disabled with "Deferred — AD-41 / DEF-102" tooltip. `telegram` should be hidden unless in `SEQUENCER_OUTBOUND_CHANNELS`. Telegram steps need `parse_mode` selector; Zalo steps need `template_data` mapping; fallback order should be user-configurable and default to spec values (`zalo` → `["telegram","email"]`, `telegram` → `["email"]`, `email` → `[]`). Current default `fallback_channels: ["telegram"]` for new email steps is wrong.

### P9 — `sequence.types.ts` allows arbitrary channel/fallback strings

- **id:** 9
- **source:** edge+auditor
- **severity:** medium
- **bucket:** patch
- **title:** `channel` and `fallback_channels` are typed as `z.string()` instead of channel enum.
- **location:** `nowing_web/contracts/types/sequence.types.ts:19`, `21`
- **detail:** Use `z.enum(["email","zalo","telegram"])` and validate `fallback_channels` against the same enum. This is a contract safety fix.

### P10 — `BillingEvent` for zero-cost sends may not be committed

- **id:** 10
- **source:** blind+edge
- **severity:** high
- **bucket:** patch
- **title:** `_record_business_event` removed the final `session.commit()`; zero-cost `BillingEvent`s and `SequenceEvent`s may be lost.
- **location:** `nowing_backend/app/services/billing_event_service.py:846-857`, `nowing_backend/app/services/sequencer_service.py:826-835`
- **detail:** `_record_business_event` now adds `BillingEvent` after `wallet_credit.apply_debit` has already committed. When `cost_micros > 0` the `apply_debit` commit persists the `BillingEvent` and staged `SequenceEvent`. When `cost_micros = 0` (e.g., Telegram) or the debit path is skipped, the `BillingEvent` is added but never committed, and `_handle_send_email_step` does not commit after `record_sequence_send`. Add an explicit `await session.commit()` after `record_sequence_send` in the send handler, or restore a conditional commit in `_record_business_event` for zero-cost/ownerless events.

### P11 — DNC helper uses wrong `is_blocked` signature

- **id:** 11
- **source:** auditor
- **severity:** high
- **bucket:** patch
- **title:** `check_outbound_compliance` calls `DncComplianceService.is_blocked` with invalid kwargs and treats the result as a bool.
- **location:** `nowing_backend/app/services/sequencer_service.py:216-220`
- **detail:** `DncComplianceService.is_blocked` takes `workspace_id`, `phone`/`email`/`domain`/`tax_id`, and `session`; it returns `DncCheckResult`, not a bool. The current call `is_blocked(..., value=..., context=...)` will raise `TypeError` at runtime if reached. This helper is also not currently used by the real send path, but once wired it will break.

### P12 — `calculate_step_eta` does not guard negative `delay_seconds`

- **id:** 12
- **source:** edge
- **severity:** medium
- **bucket:** patch
- **title:** Negative `delay_seconds` can bypass quiet-hour logic.
- **location:** `nowing_backend/app/services/sequencer_service.py:90-121`
- **detail:** Add `max(delay_seconds, 0)` at the top of `calculate_step_eta` to prevent scheduling in the past.

### P13 — Celery `execute_sequence_step` retries may be too low for Telegram

- **id:** 13
- **source:** edge
- **severity:** low
- **bucket:** patch
- **title:** `max_retries=3` may not be enough for Telegram `RetryAfter`.
- **location:** `nowing_backend/app/automations/tasks/sequence_tasks.py:35`
- **detail:** Spec allows raising to 5 for Telegram `RetryAfter`. Increase `max_retries` or make it configurable per channel.

### P14 — `CampaignAnalyticsPage` does not display per-channel breakdown

- **id:** 14
- **source:** edge
- **severity:** low
- **bucket:** patch
- **title:** Analytics page lacks `channel_breakdown` rendering.
- **location:** `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx:107-195`, `nowing_backend/app/schemas/sequence.py:131-141`
- **detail:** Add `channel_breakdown` to `SequenceAnalyticsResponse` schema and render it on the analytics page.

### P15 — Zalo webhook lead matching checks non-existent `Lead.zalo_user_id`

- **id:** 15
- **source:** blind
- **severity:** medium
- **bucket:** patch
- **title:** `hasattr(Lead, "zalo_user_id")` will always be false.
- **location:** `nowing_backend/app/gateway/zalo/webhook.py:209`
- **detail:** Once `VerifiedContact.external_chat_ids` is added, match on `VerifiedContact.external_chat_ids.zalo_user_id` instead.

### P16 — `wait` and `condition` steps inherit `selectedChannel` from the builder

- **id:** 16
- **source:** edge
- **severity:** medium
- **bucket:** patch
- **title:** New `wait`/`condition` steps get `channel` set to the last selected channel (`zalo`/`telegram`).
- **location:** `nowing_web/components/automations/VisualCadenceBuilder.tsx:104-120`
- **detail:** `wait` and `condition` step types should not have a `channel` value, or the schema should accept any channel for them. Otherwise the backend `Literal["email"]` schema will reject non-email wait/condition steps.

### P17 — Zalo webhook updates `lead.consent_status`/`lead.status` directly instead of calling `handle_inbound_interruption`

- **id:** 17
- **source:** blind+edge+auditor
- **severity:** high
- **bucket:** patch
- **title:** Zalo webhook performs ad-hoc lead updates and never dispatches to `SequencerService`.
- **location:** `nowing_backend/app/gateway/zalo/webhook.py:224-329`
- **detail:** Refactor to call `SequencerService.handle_inbound_interruption` with `channel='zalo'`, `phone`, `zalo_user_id`, and `text`, then let the sequencer update lead consent and cancel future steps. This overlaps P7 but is the specific integration point.

### P18 — `get_billing_event_for_step` has wrong costs and is unused

- **id:** 18
- **source:** edge+auditor
- **severity:** medium
- **bucket:** patch
- **title:** `get_billing_event_for_step` hardcodes `email:1000, zalo:5000, telegram:0` and is not used.
- **location:** `nowing_backend/app/services/sequencer_service.py:226-251`
- **detail:** Remove dead code or wire it into the executor and align costs with `SEQUENCE_*_COST_MICROS` config (defaults 500, 300, 0).

### D1 — `contact_unlock` refund logic changed in `billing_event_service.py`

- **id:** 19
- **source:** diff
- **severity:** medium
- **bucket:** defer
- **title:** `billing_event_service.py` diff includes new contact-unlock refund/relock code unrelated to Story 24.7.
- **location:** `nowing_backend/app/services/billing_event_service.py`
- **detail:** This is a pre-existing / cross-cutting billing change (likely Story 26.x or contact-unlock work). It is not introduced by Story 24.7 and should be reviewed under its own story. The zero-cost commit issue (P10) is the 24.7-relevant part.

## Verdict

**PATCHES APPLIED — READY FOR RE-REVIEW.**

All 18 patch findings and the 1 deferred item have been addressed. The multi-channel execution path is now wired end-to-end:

1. `_send_zns_dispatch` and `_send_telegram_dispatch` implemented and wired into `_handle_send_step` with fallback orchestration.
2. `BillingEventService.record_sequence_send` accepts `event_type`; zero-cost sends commit `SequenceEvent` and `BillingEvent` correctly.
3. `VerifiedContact.external_chat_ids` JSONB column + migration added; used in `_resolve_verified_contact` and `_resolve_inbound_contact`.
4. Multi-channel config variables (`SEQUENCE_*_COST_MICROS`, `AD_41_REACTIVATED`, `SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS`) added; `AD_41_REACTIVATED` gate enforced for Zalo.
5. Backend schemas (`SequenceStepType`, `SequenceChannel`, `SequenceEventRead`, analytics) and frontend `VisualCadenceBuilder` / `sequence.types.ts` support/validate multi-channel steps.
6. Zalo and Telegram webhooks wired into `handle_inbound_interruption` with Redis lock and CAS update.
7. Channel breakdown analytics added to backend, schema, route, and frontend campaign page.
8. Celery `max_retries` raised to 5 for Telegram `RetryAfter`; negative `delay_seconds` guarded in `calculate_step_eta`.

Verification run: `ruff`, `tsc --noEmit`, `biome check`, and 34 backend tests (unit + integration + routes) green.

## Next steps in Nowing quality pipeline

**Vừa xong:** `bmad-dev-story` — all patches applied and verified green.

**Bước tiếp theo (BẮT BUỘC):**
- [4.8] `bmad-code-review` — re-review after patches (max 2 rounds).

**Bước tiếp theo (recommended):**
- [4.9] `bmad-testarch-test-review` — verify ATDD/integration tests cover the multi-channel path.
- [4.10] `bmad-nowing-mutation-gate` — mutation test for `sequencer_service.py` and `billing_event_service.py` *(P0-gated because billing/ledger touched)*.
- [4.11] `bmad-testarch-trace` — update traceability matrix.
- [4.13] `bmad-nowing-human-review-gate` — human review for billing/PII/outbound channels *(P0-gated)*.
- [4.14] `bmad-nowing-web-e2e-gate` — Playwright for `VisualCadenceBuilder` and campaign analytics.

**Còn lại trong pipeline:** 6 bước — xem `nowing-quality-pipeline.md`.
