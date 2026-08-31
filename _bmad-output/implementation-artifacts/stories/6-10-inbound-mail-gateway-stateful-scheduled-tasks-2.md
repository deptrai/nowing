---
title: Story 6.10 — Inbound Mail Gateway (`task@nowing.ai`) & Stateful Scheduled Tasks 2.0
epic: 6
story: 10
status: ready-for-dev
priority: P0
created: 2026-08-30
---

# Story 6.10 — Inbound Mail Gateway (`task@nowing.ai`) & Stateful Scheduled Tasks 2.0

**Epic:** 6 — Automations / Platform Primitives  
**As a:** workspace member or external collaborator  
**I want:** to trigger a Nowing research/report task by sending an email with attachments to `task@nowing.ai`, and have recurring scheduled tasks resume from the last checkpoint instead of losing state  
**So that:** Nowing supports asynchronous, email-driven workflows and reliable long-running scheduled missions without custom scheduler storage.

---

## Background & Context

This story builds on top of existing platform components:

- **Gateway webhook framework** (`nowing_backend/app/routes/gateway_webhook_routes.py`) — already handles Slack, Telegram, Discord, WhatsApp, Zalo webhooks and OAuth binding flows. We add an **email inbound adapter** as a new platform bundle.
- **Celery Beat scheduler** (`nowing_backend/app/tasks/celery_app.py` / `nowing_backend/app/automations/`) — already runs scheduled automations and alert rules.
- **`LangGraphMissionExecutor`** (`nowing_backend/app/tasks/dsh_worker_langgraph.py`) — runs DSH missions with checkpoint/resumption via `dsh_missions.checkpoint` JSONB.
- **`dsh_missions` table** (`nowing_backend/app/db.py`) — stores mission state, progress, and checkpoint.
- **Generic Alert Engine** (`Story 6-8`, `AD-33`) — already provides scheduler + diff + notification; this story does **not** replace it but adds a new mission-type consumer for recurring reports.

Historical note: The original spec mentioned a separate "Snapshot storage table" for scheduled tasks. That has been **replaced** by reusing `dsh_missions.checkpoint` (per `AD-115` guidance and the DSH executor pattern). Do not create a new snapshot table.

---

## Acceptance Criteria

### AC-1 — Inbound email webhook endpoint
**Given** SendGrid or Mailgun POSTs an inbound email event to Nowing, **when** the payload reaches `/api/v1/gateway/email/inbound`, **then** the endpoint validates the provider signature (SendGrid `X-Twilio-Email-Event-Webhook-Signature` or Mailgun `signature`/`token`/`timestamp`), parses `From`, `To`, `Subject`, `TextBody`, `HtmlBody`, and attachments, and persists an `inbound_email_event` row.

### AC-2 — Email address resolution
**Given** an inbound email to `task@nowing.ai`, **when** the gateway processes it, **then** it resolves the sender via `From` address to a `User` (verified email match) and a target `Workspace` from `To` address parsing. The primary format is `task+{workspace_id}@nowing.ai` (numeric workspace ID) because `Workspace` does not currently expose a public `short_id`; a slug/short-id mapping table (`email_workspace_alias`) may be added in this story if UX requires human-readable addresses. If no match, the event is queued for manual review and a bounce/reply is sent.

### AC-3 — Attachment ingestion
**Given** an inbound email with attachments, **when** the attachments are parsed, **then** PDF/DOCX/TXT/MD attachments are stored as `Document` rows under the target workspace, and other MIME types trigger a reply saying "Unsupported attachment type".

### AC-4 — Natural-language mission creation
**Given** the email body contains a plain-text request (e.g. "Theo dõi giá cổ phiếu VCB trong 30 ngày"), **when** the gateway classifies the request, **then** it creates a `DSH mission` with `mission_type="recurring_report"` (extend `DshMissionType` in `app/schemas/dsh.py`), `payload.query` = the email subject + body, `payload.source` = `"email"`, `payload.from_address`, `payload.attachment_document_ids`, and a `schedule` JSONB (cron + timezone). The mission is enqueued via `DshMissionService.create_mission()` and published to the Redis stream.

### AC-5 — Stateful scheduled DSH mission
**Given** a `DSH mission` with `mission_type="recurring_report"`, **when** the `ingestion` node writes checkpoint data, **then** it writes into `dsh_missions.checkpoint` JSONB under a `schedule_state` key. The mission also updates `dsh_missions.next_fire_at` from its `schedule` JSONB. The next Celery Beat tick can load this checkpoint, compare with the previous run, and resume without losing intermediate state.

### AC-6 — Celery Beat recurring trigger
**Given** a mission with a valid `schedule` (cron expression or interval), **when** Celery Beat fires `schedule_mission_tick`, **then** the task claims missions where `dsh_missions.next_fire_at <= now()` and `dsh_missions.status IN ('pending','running')`, calls `LangGraphMissionExecutor` with `resume_from_checkpoint=True`, and advances `next_fire_at` after a successful `ingestion` node. If no new data arrived, the `ingestion` node is a no-op and `next_fire_at` is still advanced.

### AC-7 — Reply via SMTP
**Given** the mission completes or fails, **when** the final `deliver` node runs, **then** it sends an email reply to the original `From` address via configured SMTP relay (SendGrid/Mailgun/Postmark) with a summary, a link to the deliverable, and `degradation_reasons` if degraded.

### AC-8 — Idempotency & deduplication
**Given** the same email `Message-Id` is POSTed twice, **when** the gateway receives it, **then** the second event is deduplicated and a `204 No Content` (or provider-specific success) is returned without creating duplicate missions.

### AC-9 — Telemetry & error handling
**Given** the email gateway or scheduled mission fails, **when** the failure occurs, **then** an `audit_events` row is written, an error count metric is emitted, and a non-retryable fatal error results in a reply to the user with a failure reason.

---

## Developer Context

### Existing Code to Reuse

| Component | File | What to reuse |
|---|---|---|
| Gateway webhook framework | `nowing_backend/app/routes/gateway_webhook_routes.py` | Provider signature verification, `inbound_event` persistence pattern, FastAPI router structure. |
| Gateway account/binding registry | `nowing_backend/app/gateway/` | `registry.py`, `inbox.py`, `inbox_processor.py`, `inbox_worker.py` for event routing and deduplication. |
| Celery Beat | `nowing_backend/app/tasks/celery_app.py` | Beat schedule, Celery task registration. |
| Schedule checker | `nowing_backend/app/tasks/celery_tasks/schedule_checker_task.py` | Pattern for claiming due scheduled items. |
| DSH executor | `nowing_backend/app/tasks/dsh_worker_langgraph.py` | `LangGraphMissionExecutor`, checkpoint semantics, `ingestion`/`reasoning`/`crawl`/`deliver` nodes. |
| DSH service/routes | `nowing_backend/app/services/dsh_mission_service.py`, `nowing_backend/app/routes/dsh_routes.py` | Mission CRUD, public mission state; update `DshMissionService.create_mission()` to accept `schedule`, `source`, `request_text`, `next_fire_at`. |
| Alert engine tick | `nowing_backend/app/alerts/engine/tick.py` | `_claim_due_rules` pattern for claiming due scheduled rules. |
| DSH DB model | `nowing_backend/app/db.py` (`DshMission` / `DshMissionCheckpoint`) | State machine, progress percent constraint, workspace_id status index. |
| Document ingestion | `nowing_backend/app/services/documents/document_service.py` | PDF/DOCX/TXT/MD → `Document` row. |

### New Code to Create

| File | Purpose |
|---|---|
| `nowing_backend/app/gateway/email/adapter.py` | Provider-agnostic inbound email parser; SendGrid & Mailgun payload normalization. |
| `nowing_backend/app/gateway/email/auth.py` | Provider signature verification. |
| `nowing_backend/app/gateway/email/sender.py` | SMTP/SendGrid/Mailgun outbound reply sender. |
| `nowing_backend/app/gateway/email/models.py` | Pydantic models for `InboundEmail`, `EmailAttachment`, `EmailReply`. |
| `nowing_backend/app/gateway/email/__init__.py` | Bundle exports. |
| `nowing_backend/app/routes/gateway_email_routes.py` | FastAPI routes: `POST /gateway/email/inbound`, `POST /gateway/email/sendgrid`, `POST /gateway/email/mailgun`, admin test endpoint. |
| `nowing_backend/app/tasks/dsh_worker_scheduled_mission.py` | Celery task: load recurring `dsh_missions`, resume from `checkpoint`, run `ingestion` if new data. |
| `nowing_backend/app/tasks/celery_tasks/schedule_mission_tick.py` | Beat tick that claims due scheduled DSH missions. |
| `nowing_backend/app/schemas/dsh.py` (update) | Add `"recurring_report"` to `DshMissionType`; add `RecurringReportPayload` and `RecurringReportSchedule` models. |

### New DB Artifacts

| Table | Columns | Why |
|---|---|---|
| `inbound_email_event` | `id` (UUID PK), `workspace_id` (FK), `user_id` (FK), `provider` (SendGrid/Mailgun), `message_id` (unique per provider), `from_address`, `to_address`, `subject`, `body_text`, `body_html`, `attachments` (JSONB list of `{filename, mime_type, size, document_id}`), `status` (`received`, `parsed`, `mission_created`, `replied`, `failed`, `duplicate`), `dedupe_key` (hash of `message_id`), `created_at`, `processed_at`, `audit_events` FK optional. | Persistence, idempotency, replay, audit. |
| `dsh_missions` columns to use | Add `schedule` (cron/interval JSONB), `source` (`email`, `chat`, `api`), `request_text`, `next_fire_at`, `last_fired_at`, and `checkpoint` (JSONB, key `schedule_state`). `mission_type` is extended to include `"recurring_report"`. | Reuse existing table; no new snapshot table. |

### DB Migration

Create `nowing_backend/alembic/versions/236_add_inbound_email_and_scheduled_dsh_missions.py` with:
- `inbound_email_event` table with composite unique index on `(provider, message_id)`, `workspace_id` RLS, and `status` enum index.
- Add `email_workspace_alias` table (`workspace_id`, `alias`, `created_at`, unique `alias`) if short-id addressing is implemented; otherwise document the decision to use numeric `workspace_id`.
- Add to `dsh_missions`: `schedule` (JSONB, nullable, default `{}`), `source` (String, nullable), `request_text` (Text, nullable), `next_fire_at` (TIMESTAMP TZ, nullable, index), `last_fired_at` (TIMESTAMP TZ, nullable).
- Update `chk_dsh_missions_status` only if needed (do not alter existing values).
- Ensure `dsh_missions.checkpoint` JSONB already supports `schedule_state` (no change).

### Configuration

Add to `nowing_backend/app/config.py` (or `.env`):

```
GATEWAY_EMAIL_ENABLED=true
GATEWAY_EMAIL_PROVIDER=sendgrid  # or mailgun
GATEWAY_EMAIL_DOMAIN=nowing.ai
SENDGRID_WEBHOOK_PUBLIC_KEY=<PEM>
SENDGRID_API_KEY=<key for outbound>
MAILGUN_WEBHOOK_SIGNING_KEY=<key>
MAILGUN_API_KEY=<key for outbound>
SMTP_REPLY_FROM=Nowing <task@nowing.ai>

# Optional: Celery Beat schedule interval in seconds for schedule_mission_tick
SCHEDULED_DSH_MISSION_TICK_SECONDS=60
```

Also add a beat entry in `nowing_backend/app/celery_app.py` (or equivalent) to run `app.tasks.celery_tasks.schedule_mission_tick.schedule_mission_tick` every `SCHEDULED_DSH_MISSION_TICK_SECONDS`.

### Provider-Specific Notes

- **SendGrid Inbound Parse**: POSTs `email` MIME multipart to a webhook; use `email` stdlib to parse. Webhook verification is via `X-Twilio-Email-Event-Webhook-Signature` (public key in config).
- **Mailgun Routes**: POSTs parsed JSON fields (`sender`, `recipient`, `subject`, `body-plain`, `body-html`, `attachments`); signature is `hmac_sha256(timestamp+token, signing_key)`.

### `schedule` JSONB Schema

The `dsh_missions.schedule` column follows the same pattern as `alert_rules.cron`/`next_fire_at`:

```json
{
  "type": "cron",
  "expression": "0 9 * * 1",
  "timezone": "Asia/Ho_Chi_Minh",
  "next_fire_at": "2026-09-07T02:00:00+00:00"
}
```

or interval:

```json
{
  "type": "interval",
  "minutes": 360,
  "next_fire_at": "2026-09-07T02:00:00+00:00"
}
```

Use the existing `app/alerts/engine/cron.py` helpers (`compute_next_fire_at`) to compute `next_fire_at`.

### Testing Requirements

- Unit tests:
  - `tests/unit/gateway/email/test_adapter.py` — parse SendGrid/Mailgun payloads.
  - `tests/unit/gateway/email/test_auth.py` — signature verification (success/failure/replay).
  - `tests/unit/tasks/test_dsh_worker_scheduled_mission.py` — resume from checkpoint, no-op when no new data.
- Integration tests:
  - `tests/integration/gateway/test_email_inbound.py` — end-to-end: POST webhook → `inbound_email_event` → mission created → reply queued.
  - `tests/integration/tasks/test_scheduled_mission_tick.py` — Celery tick claims and resumes mission.

### Non-Goals

- Do **not** build a new scheduler from scratch; reuse Celery Beat and `dsh_missions.checkpoint`.
- Do **not** create a separate `snapshot` table; use `DshMission.checkpoint`.
- Do **not** support real-time bidirectional email chat in this story; only inbound trigger + outbound reply.
- Email outbound marketing/drip is out of scope (Epic 24 covers multi-channel drip).

### References

- `Story 6-8` — Generic Alert Engine (scheduler + tick pattern).
- `AD-33` — Generic Alert Engine architecture.
- `AD-115` — DSH mission as scheduled task primitive.
- `epics.md` §4046 — "Story 6.10 — Inbound Mail Gateway & Stateful Scheduled Tasks 2.0".
- `sprint-priority.md` — Tier 0, item 5.

---

## Story Completion Status

**ready-for-dev**

Ultimate context engine analysis completed — comprehensive developer guide created.
