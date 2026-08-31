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
**Given** an inbound email to `task@nowing.ai`, **when** the gateway processes it, **then** it resolves the sender via `From` address to a `User` (verified email match) and a target `Workspace` from `To` address parsing (`task+{workspace_short_id}@nowing.ai` or default workspace from user profile). If no match, the event is queued for manual review and a bounce/reply is sent.

### AC-3 — Attachment ingestion
**Given** an inbound email with attachments, **when** the attachments are parsed, **then** PDF/DOCX/TXT/MD attachments are stored as `Document` rows under the target workspace, and other MIME types trigger a reply saying "Unsupported attachment type".

### AC-4 — Natural-language mission creation
**Given** the email body contains a plain-text request (e.g. "Theo dõi giá cổ phiếu VCB trong 30 ngày"), **when** the gateway classifies the request, **then** it creates a `DSH mission` with `schedule_type=recurring_report`, `request_text` from the email body, `source=email`, and enqueues it via `LangGraphMissionExecutor`.

### AC-5 — Stateful scheduled DSH mission
**Given** a `DSH mission` with `schedule_type=recurring_report`, **when** the `ingestion` node writes checkpoint data, **then** it writes into `dsh_missions.checkpoint` JSONB under a `schedule_state` key. The next Celery Beat tick can load this checkpoint, compare with the previous run, and resume without losing intermediate state.

### AC-6 — Celery Beat recurring trigger
**Given** a mission with a valid `schedule` (cron expression or interval), **when** Celery Beat fires, **then** the new task `dsh_worker_scheduled_mission` loads the mission by `id`, checks `dsh_missions.status` is `pending`/`running`, calls `LangGraphMissionExecutor` with `resume_from_checkpoint=True`, and only runs the `ingestion` node if new data arrived.

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
| DSH service/routes | `nowing_backend/app/services/dsh_mission_service.py`, `nowing_backend/app/routes/dsh_routes.py` | Mission CRUD, public mission state. |
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
| `nowing_backend/app/tasks/celery_tasks/schedule_mission_tick.py` (or add to `celery_app.py`) | Beat tick that claims due scheduled DSH missions. |

### New DB Artifacts

| Table | Columns | Why |
|---|---|---|
| `inbound_email_event` | `id` (UUID PK), `workspace_id` (FK), `user_id` (FK), `provider` (SendGrid/Mailgun), `message_id` (unique per provider), `from_address`, `to_address`, `subject`, `body_text`, `body_html`, `attachments` (JSONB list of `{filename, mime_type, size, document_id}`), `status` (`received`, `parsed`, `mission_created`, `replied`, `failed`, `duplicate`), `dedupe_key` (hash of `message_id`), `created_at`, `processed_at`, `audit_events` FK optional. | Persistence, idempotency, replay, audit. |
| `dsh_missions` columns to use | `schedule_type`, `schedule` (cron/interval JSONB), `source` (`email`, `chat`, `api`), `request_text`, `checkpoint` (JSONB, key `schedule_state`). | Reuse existing table; no new snapshot table. |

### DB Migration

Create `alembic/versions/NNN_add_inbound_email_event.py` with:
- `inbound_email_event` table with composite unique index on `(provider, message_id)` and `workspace_id` RLS.
- Add `schedule_type` and `schedule` columns to `dsh_missions` if not present.
- Ensure `dsh_missions.checkpoint` JSONB can store `schedule_state`.

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
```

### Provider-Specific Notes

- **SendGrid Inbound Parse**: POSTs `email` MIME multipart to a webhook; use `email` stdlib to parse. Webhook verification is via `X-Twilio-Email-Event-Webhook-Signature` (public key in config).
- **Mailgun Routes**: POSTs parsed JSON fields (`sender`, `recipient`, `subject`, `body-plain`, `body-html`, `attachments`); signature is `hmac_sha256(timestamp+token, signing_key)`.

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
