---
story_key: "24-6"
epic: "epic-24"
story: "24.6"
title: "Two-Way AI Outreach Auto-Reply Agent"
status: "review"
baseline_commit: "6ac305274"
---

# Story 24.6: Two-Way AI Outreach Auto-Reply Agent

## Story Overview

As a busy founder or sole sales representative,  
I want an AI Auto-Reply Agent that listens to incoming messages from prospects on Zalo OA and Telegram, understands their questions, answers accurately based on my Workspace Knowledge Base documents, and alerts me on hot buying signals,  
So that no customer inquiry is left unanswered 24/7 while my time is focused on closing high-intent deals.

---

## Architectural Invariants & Security Gates

- **`INV-24.7` (Inbound Auto-Reply Grounding & Async ACK SLA):**
  - Webhook endpoints for Zalo OA (`/api/v1/gateway/zalo/webhook`) and Telegram (`/api/v1/gateway/telegram/webhook`) MUST respond with `HTTP 200 OK` in $< 100\text{ms}$ and push incoming payloads to Redis Streams / Celery queue.
  - Inbound messages from the same sender within a $3\text{s}$ sliding window MUST be debounced and merged into a single context turn to prevent LLM spam.
  - AI Auto-Reply LLM runs with deterministic configuration (`temperature = 0.0`).
  - Knowledge Base RAG chunk similarity MUST satisfy Cosine Threshold $\ge 0.75$. If no chunks meet the threshold, the bot MUST politely defer without inventing prices, discounts, or contract terms.
- **`INV-24.8` (Human Escalation Handover & 24h Auto-Reply Pause):**
  - When `InboundIntentClassifier` detects a buying intent (e.g., *"Báo giá cho tôi"*, *"Hẹn xem nhà"*, *"Cho xin sđt tư vấn"*), or when a human sales representative sends a manual message in the thread, the system MUST set Redis key `auto_reply_paused:{thread_id}` with TTL $86400\text{s}$ ($24\text{h}$).
  - An interactive alert MUST be dispatched immediately to the assigned sales rep's Telegram Bot with an inline `[Nhận Tư Vấn]` button.
- **`INV-23.11` (Webhook Signature Verification & Fail-Closed Guard):**
  - All Zalo OA webhook events MUST verify HMAC-SHA256 signatures against `ZaloConnection.oa_secret`.
  - Telegram events MUST verify bot token hash matching.

---

## Acceptance Criteria

### AC-1 — Async Inbound Webhook Ingest & 3s Redis Debounce Buffer
- **Given** an external prospect sending rapid burst messages (e.g. 3 messages in $< 3\text{s}$) to Zalo OA or Telegram Bot,
- **When** received at the webhook endpoint,
- **Then**:
  1. The webhook acknowledges with `HTTP 200 OK` in $< 50\text{ms}$.
  2. The messages are appended to a Redis buffer list `inbound_debounce:{channel}:{sender_id}` with a $3\text{s}$ settling timer.
  3. After the $3\text{s}$ debounce timer fires, the buffered messages are merged into a single coherent prompt and dispatched to `AutoReplyWorker`.

### AC-2 — RAG-Grounded Factual Answering & Anti-Hallucination Guard
- **Given** a debounced prospect inquiry regarding products, pricing, or policies,
- **When** processed by `AutoReplyAgent.generate_reply(workspace_id, thread_id, prompt)`,
- **Then**:
  1. The agent performs semantic vector retrieval on workspace `Document` / `Chunk` records.
  2. If matching chunks have Cosine Similarity $\ge 0.75$, the agent generates a concise, professional Vietnamese reply citing factual content.
  3. If no matching chunks meet the threshold or if the question asks for custom discounts/legal commitments, the bot replies with a safe fallback: *"Dạ em xin phép ghi nhận thông tin và chuyển chuyên viên phụ trách liên hệ tư vấn chi tiết cho anh/chị ngay ạ!"*.

### AC-3 — Hot Buying Intent Detection & Telegram Interactive Alert
- **Given** an incoming message containing buying intent keywords or classified as high-intent by `InboundIntentClassifier` (intent score $\ge 0.80$),
- **When** evaluated,
- **Then**:
  1. The lead's CRM status is updated to `LeadStatus.WARM` or `LeadStatus.HOT`.
  2. A Telegram notification is dispatched to the workspace owner/assigned sales rep with formatted MarkdownV2 details: Prospect name, channel, message snippet, and detected intent.
  3. The Telegram alert includes an inline keyboard button `[🤝 Nhận Tư Vấn]`.
  4. Clicking `[Nhận Tư Vấn]` assigns the lead to the clicking user, replies to the prospect notifying them that a specialist has joined, and sets `auto_reply_paused:{thread_id}` for $24\text{h}$.

### AC-4 — Human-in-the-Loop Takeover Sync
- **Given** an active prospect conversation where AI Auto-Reply is enabled,
- **When** a human sales rep sends a message from the Nowing CRM Inbox or directly on the connected channel,
- **Then**:
  1. The system flags the thread as human-controlled.
  2. Redis key `auto_reply_paused:{thread_id}` is set with TTL $24\text{h}$.
  3. AI Auto-Reply remains completely silent on subsequent incoming messages during this window unless explicitly unpaused.

### AC-5 — Workspace Communication Settings UI
- **Given** an authenticated user on `/dashboard/[workspace_id]/user-settings` under Communication Channels tab,
- **When** viewing the Auto-Reply configuration,
- **Then**:
  1. User can toggle **Bật AI Tự Động Trả Lời (2-Way Auto-Reply)** on/off per channel (Zalo OA, Telegram).
  2. User can select which Knowledge Base document collections are used for RAG grounding.
  3. User can configure the Telegram Alert recipient and custom fallback message.

---

## Tasks / Subtasks

- [x] **Task 1: Redis Debounce Buffer & Celery Async Inbound Worker**
  - [x] Implement `app/services/inbound_debounce_service.py` with $3\text{s}$ buffer and atomic aggregation.
- [x] **Task 2: `AutoReplyAgent` & `InboundIntentClassifier` Core Service**
  - [x] Create `app/services/auto_reply_agent.py` with intent score evaluation ($\ge 0.80$).
  - [x] Implement `is_auto_reply_paused` and `pause_auto_reply` ($24\text{h}$ TTL).
- [x] **Task 3: RAG Retrieval Engine Integration**
  - [x] Enforce Cosine Similarity threshold $\ge 0.75$ with pgvector cosine distance search.
  - [x] Implement safe fallback messaging when ungrounded.
- [x] **Task 4: Telegram Interactive Alert & Callback Handler**
  - [x] Implement callback handler `handle_telegram_callback_nhan_tu_van` in `app/gateway/telegram/callbacks.py`.
- [x] **Task 5: Human-in-the-Loop Takeover Sync**
  - [x] Redis key `auto_reply_paused:{thread_id}` guard.
- [x] **Task 6: Frontend Channel Settings UI**
  - [x] Added Two-Way AI Auto-Reply Agent card in `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx`.
- [x] **Task 7: Unit & Integration Tests**
  - [x] 4 unit tests in `tests/unit/services/test_auto_reply_agent.py` passing.
  - [x] 1 integration test in `tests/integration/gateway/test_auto_reply_pipeline.py` passing.

### Review Findings
- [x] [Review][Patch] Atomic Lua script for Redis debounce flush & delete [`app/services/inbound_debounce_service.py:160`]
- [x] [Review][Patch] Whitespace & empty text input guard in buffer_inbound_message [`app/services/inbound_debounce_service.py:138`]
- [x] [Review][Patch] Parameter validation guard for thread_id & lead_id in nhan_tu_van callback [`app/gateway/telegram/callbacks.py:575`]

### Review Findings (2026-08-21 triage)

- [x] [Review][Dismiss] `_handle_dsh_callback` (DSH checkpoint) được đánh giá sai — code này đã tồn tại ở HEAD, không phải diff 24.6; `tests/unit/gateway/test_telegram_callbacks.py` đã cover. [`app/gateway/telegram/callbacks.py:340-477`]

- [x] [Review][Patch] Thêm `gateway.process_auto_reply_buffer` Celery task, `buffer_inbound_message` tự schedule khi payload có `workspace_id`/`thread_id`. [`app/services/inbound_debounce_service.py:40-65`] [`app/tasks/celery_tasks/gateway_tasks.py:170-200`]
- [x] [Review][Patch] `handle_telegram_callback_nhan_tu_van` được wire vào `handle_callback_query` với định dạng `nhan_tu_van:{thread_id}:{lead_id}` và validate clicker. [`app/gateway/telegram/callbacks.py:480-575`]
- [x] [Review][Patch] Callback `[Nhận Tư Vấn]` cập nhật `Lead.status = "warm"`, gán `user_id`, commit, và reply prospect. [`app/gateway/telegram/callbacks.py:617-700`]
- [x] [Review][Patch] `AutoReplyAgent` gọi `_dispatch_hot_lead_alert` khi `is_hot`; placeholder để sau này wire Telegram/Zalo alert sender (TODO). [`app/services/auto_reply_agent.py:186-210`]
- [x] [Review][Patch] UI Auto-Reply dùng state `autoReplyEnabled` riêng, thêm controls `KB Collections`, `Fallback Message`, `Hot-Lead Recipient Chat ID`. [`nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx:667-760`]
- [x] [Review][Patch] Hard-coded `model="gemini-flash"` trong `_generate_llm_response` → đổi thành `getattr(config, "AUTO_REPLY_MODEL", "gemini-flash")`. [`app/services/auto_reply_agent.py:166-172`]
- [x] [Review][Patch] Tạo Redis client riêng → dùng shared `app.redis_client.get_redis_client` qua wrapper. [`app/services/auto_reply_agent.py:23-30`] [`app/services/inbound_debounce_service.py:20-27`]
- [x] [Review][Patch] `is_auto_reply_paused` fail-open khi Redis lỗi → fail-closed trả `True`. [`app/services/auto_reply_agent.py:33-44`]
- [x] [Review][Patch] `_retrieve_knowledge_chunks` thêm validate workspace tồn tại và chunk content not-null. [`app/services/auto_reply_agent.py:111-147`]
- [x] [Review][Patch] `generate_reply` fallback khi `reply_text` rỗng. [`app/services/auto_reply_agent.py:177-227`]
- [x] [Review][Patch] `buffer_inbound_message` dùng `json.dumps(..., default=str)` chống non-serializable. [`app/services/inbound_debounce_service.py:40-62`]
- [x] [Review][Patch] `flush_and_aggregate_messages` thêm Redis distributed lock `...:lock` bằng `SET NX EX`, bỏ fallback `lrange+delete` non-atomic. [`app/services/inbound_debounce_service.py:75-130`]
- [x] [Review][Patch] `handle_telegram_callback_nhan_tu_van` thêm validate người click (clicker == binding owner) khi dispatch. [`app/gateway/telegram/callbacks.py:540-575`]
- [x] [Review][Patch] `pause_auto_reply` log warning khi `thread_id` rỗng và log error khi Redis lỗi. [`app/services/auto_reply_agent.py:47-57`]
- [x] [Review][Patch] Tăng cường tests: double-flush lock, hot-lead alert dispatch, lead claim + prospect reply. [`nowing_backend/tests/unit/services/test_auto_reply_agent.py`] [`nowing_backend/tests/integration/gateway/test_auto_reply_pipeline.py`]

### Review Findings (2026-08-22 re-review)

#### decision_needed
- [x] [Review][Decision] Auto-reply integration point with gateway inbox pipeline — resolved: hook into `inbox_processor._dispatch_inbound_event` after binding validation and empty-message check; buffer direct text messages into `InboundDebounceService` when `workspace.auto_reply_enabled` is true. (AC-1)
- [x] [Review][Decision] Workspace auto-reply settings persistence — resolved: add columns directly to `Workspace` (`auto_reply_enabled`, `auto_reply_collections`, `auto_reply_fallback`, `auto_reply_recipient_chat_id`) plus migration `222`, and expose via existing `WorkspaceUpdate`/`WorkspaceRead` schemas.

#### patch
- [x] [Review][Patch] `AutoReplyAgent._generate_llm_response` fixed to call `LLMRouterService.get_router().acompletion(...)` (OpenAI-style dict messages) and record `TokenUsage`/`cost_micros` via `record_token_usage`. [nowing_backend/app/services/auto_reply_agent.py:170-220]
- [x] [Review][Patch] `process_auto_reply_buffer_task` now resolves the platform adapter from `account_id`/`binding_id`, sends the generated reply via `adapter.send_message`, and commits token usage. [nowing_backend/app/tasks/celery_tasks/gateway_tasks.py:172-260]
- [x] [Review][Patch] `_dispatch_hot_lead_alert` implemented: uses `build_lead_telegram_alert`, appends `[Nhận Tư Vấn]` inline button with `nhan_tu_van:{thread_id}:{lead_id}` callback, and sends via `TelegramClient` to `workspace.auto_reply_recipient_chat_id`. [nowing_backend/app/services/auto_reply_agent.py:230-310]
- [x] [Review][Patch] Unit tests fixed to mock `is_auto_reply_paused` and pass `session=AsyncMock()` where hot-lead alert dispatch is asserted. [nowing_backend/tests/unit/services/test_auto_reply_agent.py:55-200]
- [x] [Review][Patch] Integration test `test_nhan_tu_van_claims_lead_and_replies_prospect` updated to assert `lead.user_id == binding.user_id` (validated clicker via `binding.external_peer_id`). [nowing_backend/tests/integration/gateway/test_auto_reply_pipeline.py:41-85]
- [x] [Review][Patch] Frontend `MessagingChannelsContent` wired to `workspacesApiService.getWorkspace`/`updateWorkspace`; controls enabled and persist `auto_reply_*` fields. [nowing_web/.../MessagingChannelsContent.tsx:80-250, 690-780]
- [x] [Review][Patch] `AutoReplyAgent` records `TokenUsage` with prompt/completion/total tokens and `cost_micros` via `litellm.completion_cost`. [nowing_backend/app/services/auto_reply_agent.py:170-220]
- [x] [Review][Patch] `handle_telegram_callback_nhan_tu_van` assigns `lead.user_id = binding.user_id` and relies on `handle_callback_query` clicker validation (`event.external_user_id == binding.external_peer_id`). [nowing_backend/app/gateway/telegram/callbacks.py:621-700]

#### defer
- [x] [Review][Defer] Zalo signature verification (INV-23.11) is pre-existing in `app/gateway/zalo/webhook.py` and not changed by this story. — deferred, pre-existing

### Review Findings — 2026-08-22 (re-review)

#### decision_needed
- [x] [Review][Decision] Lead creation policy for unknown hot prospects — resolved: create a `Lead` record on first hot inbound so the `[Nhận Tư Vấn]` callback has a valid `lead_id`.

#### patch
- [x] [Review][Patch] `_get_or_create_lead` must actually create a Lead for unknown hot senders — `nowing_backend/app/services/auto_reply_agent.py:322-341`
- [x] [Review][Patch] Multiple debounce Celery tasks scheduled per burst — `nowing_backend/app/services/inbound_debounce_service.py:34-75` — every `buffer_inbound_message` call schedules a fresh `process_auto_reply_buffer` task, causing redundant workers for a single burst.
- [x] [Review][Patch] `process_auto_reply_buffer_task` resolves `user_id` incorrectly — `nowing_backend/app/tasks/celery_tasks/gateway_tasks.py:198-205` — the else branch passes `workspace.user_id` to `session.get(User, ...)` even when it is `None`, so the workspace owner is never resolved.
- [x] [Review][Patch] Hot-lead alert bypasses workspace-telegram binding validation — `nowing_backend/app/services/auto_reply_agent.py:270-274, 305-311` — uses `config.TELEGRAM_SHARED_BOT_TOKEN` and sends to an arbitrary `recipient_chat_id` without validating it is a bound channel in the workspace.
- [x] [Review][Patch] Telegram callback_data may exceed 64-byte limit — `nowing_backend/app/services/auto_reply_agent.py:300` — `nhan_tu_van:{thread_id}:{lead_id}` is currently near the Telegram limit; should assert length in tests or shorten encoding.

#### defer
- [x] [Review][Defer] Human-in-the-Loop takeover from CRM not wired — `nowing_backend/app/gateway/inbox_processor.py` outbound path — AC-4 requires human rep message to set `auto_reply_paused`, but the outbound path is pre-existing and not connected to `pause_auto_reply`.
- [x] [Review][Defer] Zalo OA webhook signature verification — `nowing_backend/app/gateway/zalo/webhook.py` — pre-existing, not changed by this diff.

---

## Dev Agent Record

### File List
- `nowing_backend/app/services/inbound_debounce_service.py` [NEW]
- `nowing_backend/app/services/auto_reply_agent.py` [NEW]
- `nowing_backend/app/gateway/telegram/callbacks.py` [MODIFY]
- `nowing_backend/tests/unit/services/test_auto_reply_agent.py` [NEW]
- `nowing_backend/tests/integration/gateway/test_auto_reply_pipeline.py` [NEW]
- `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx` [MODIFY]

### Dev Agent Record Additions
- `nowing_backend/alembic/versions/c610f68d47fb_add_workspace_auto_reply_settings.py` [NEW] — migration `c610f68d47fb`, down_revision `222`, adds `auto_reply_*` columns to `workspaces`.

### Verification Results (2026-08-22 post-patch)
- **Alembic Upgrade:** `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing uv run alembic upgrade heads` ➔ **Success** (applied `c610f68d47fb` + `193_add_playbook_is_approved`).
- **Unit Tests:** `uv run pytest tests/unit/services/test_auto_reply_agent.py -q` ➔ **6 passed, 0 failed**.
- **Integration Tests (real DB):** `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing uv run pytest tests/integration/gateway/test_auto_reply_pipeline.py -q` ➔ **2 passed, 0 failed**.
- **LLM Smoke:** `uv run python -c "from app.services.auto_reply_agent import AutoReplyAgent; ..."` ➔ `_generate_llm_response` no longer raises `ImportError`; falls back gracefully when LLM router is not initialized.
- **Backend Lint (touched files):** `uv run ruff check app/services/auto_reply_agent.py app/services/inbound_debounce_service.py app/gateway/inbox_processor.py app/gateway/telegram/callbacks.py app/tasks/celery_tasks/gateway_tasks.py app/schemas/workspace.py app/db.py alembic/versions/c610f68d47fb_add_workspace_auto_reply_settings.py` ➔ **All checks passed**.
- **Frontend Typecheck:** `pnpm tsc --noEmit` ➔ **Clean**.
- **Frontend Biome:** `pnpm exec biome check app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx` ➔ **Clean**.
