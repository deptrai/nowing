---
baseline_commit: be2efe015
story_key: "27-2b"
epic: "epic-27"
story: "27.2b"
title: "Speaker Diarization Meeting Minutes from Chat"
status: "ready-for-dev"
---

# Story 27.2b: Speaker Diarization Meeting Minutes from Chat

**Status:** `ready-for-dev`  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Priority:** P1  
**Scope:** MVP chat-first slice for meeting minutes. Accept an audio file (or file URL) from chat, transcribe with speaker diarization, and surface a structured meeting-minutes deliverable with action items grouped by speaker.  
**Related Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-mode/tool-binding pattern.  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, FR-94; AD-112).  
**Replaces part of:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-2-manus-slides-presentation-studio-speaker-diarization.md" /> — this story takes the diarization slice.

## Story

As a **project manager or sales lead**,  
I want to upload a meeting recording in chat (or paste a URL) and ask for meeting minutes,  
So that the agent transcribes the audio, identifies each speaker, extracts action items per person, and shows a structured meeting-minutes deliverable.

## Goal

- **Chat-first, like 27.1a:** thread can be tagged with `platform_metadata.meeting_minutes_mode=true` via quick chip, `/meeting` slash prompt, or `?mode=meeting_minutes` URL.
- **Single-turn MVP:** user provides audio → agent calls `generate_meeting_minutes` → deliverable card appears in chat.
- **Graceful degradation:** if diarization is unavailable, the system still returns a transcript and a clear `degraded` state without crashing.
- **Privacy-first:** audio file is not retained permanently; transcription + minutes are stored as a `Document` or `MeetingMinutes` row.

## UX Review Notes

- **Audio input showstopper:** the current composer (`user-turn-api-parts.ts`) only supports image attachments. For MVP, use **URL-only input** (user pastes a public/private audio URL). The tool `generate_meeting_minutes` accepts `audio_url` and optionally `document_id` for already-uploaded files. Chat composer audio upload is deferred to a future iteration.
- **Quick chip flow:** clicking "Tóm tắt cuộc họp" / "Summarize a meeting" should either (a) paste a prompt placeholder *"Paste the meeting recording URL here"* into the composer, or (b) open a minimal file-upload dialog if the user has already uploaded a `Document`.
- **Artifact group naming:** add `meeting_minutes` to `ArtifactKind` with label **"Meeting Minutes"** and icon `Mic` or `Users`. Place it after "Slide Decks" in `GROUP_ORDER`.
- **Degraded state copy (bilingual):**
  - English: *"Transcript ready, but speaker labels are unavailable."*
  - Vietnamese: *"Đã bóc tách nội dung cuộc họp, nhưng chưa phân biệt được từng người nói. Bản ghi toàn văn ở bên dưới."*
- **Privacy note in UI:** when the user is asked for a URL, show a subtle caption *"The recording is not stored after processing; only the transcript and minutes are kept."* / *"Bản ghi âm không được lưu sau khi xử lý; chỉ bản ghi chép và kết luận được giữ lại."*
- **Prompt picker mode:** extend `PromptPickerAction` from `isWebBuilder` boolean to a `mode` string so `/meeting` can set `?mode=meeting_minutes`.
- **Deliverable card layout:** the card should be collapsible. Default view shows **Summary + Action Items**; user expands to see transcript segments grouped by speaker.
- **Error copy:**
  - Audio too large: *"This recording is over the size limit (X MB). Try a shorter file or split it."*
  - Unsupported format: *"This file format is not supported. Use MP3, WAV, M4A, or OGG."*
  - No speech: *"No speech detected in the recording."*

## Architecture Review Notes

- **STT + diarization must not run inside the chat stream:** `app/services/stt_service.py:37-68` calls `faster_whisper` synchronously and blocks the async event loop. `pyannote.audio` / `whisperx` + `torch` can take tens of seconds. Running this inside `stream_new_chat` will hang the SSE and likely timeout.
  - **Use a background task pattern** (Celery or `app/tasks/` async job):
    1. `generate_meeting_minutes` creates a `MeetingMinutes` row with `status="processing"`.
    2. The tool returns `GenerateMeetingMinutesOutput(status="processing", meeting_minutes_id=...)` immediately.
    3. A Celery worker (`tasks/process_meeting_minutes.py`) runs transcription + diarization + LLM extraction.
    4. Frontend polls `GET /api/v1/meeting-minutes/{meeting_minutes_id}` or uses Zero sync for `status` updates.
  - Set `MEETING_MINUTES_MAX_DURATION_SECONDS` low enough for MVP (e.g., 10 minutes) and validate before enqueue.
- **`MeetingMinutes` status model:** `status` must include `pending | processing | ready | failed | degraded`. The tool creates the row as `pending`, returns a card in `processing`, and the worker flips it to `ready`/`failed`/`degraded`. The chat deliverable card starts in `processing` and updates when the worker completes.
- **Optional heavy ML dependencies:** `pyannote.audio` + `torchaudio`/`torchcodec` are bundled as a `meeting-minutes` optional extra in `pyproject.toml`. `whisperx` is not used. At runtime, if `pyannote.audio` import fails or `MEETING_MINUTES_DIARIZATION_ENGINE=none`, return `status="degraded"` with transcript-only. Do not fail the install for self-hosted users.
- **Typed tool output with status/error:** like `build_web_app`, `generate_meeting_minutes` must return a Pydantic `GenerateMeetingMinutesOutput` with `status` and `error` fields, never raw strings. Empty/missing `audio_url` and `document_id` should return `status="validation_failed"`.
- **User ID parsing:** `deps["user_id"]` may be `UUID` or `str`. Use the same guard as <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py" lines="21-34" />.
- **Tool session handling:** do not call `session.commit()` in the tool after the service commits. Let `MeetingMinutesService` own the unit of work. The tool only opens the session and returns `result.model_dump_json()`.
- **Avoid chat-mode if-else chains:** add `meeting_minutes_mode` to the same `ChatMode` registry proposed in 27.2a (`app/tasks/chat/streaming/flows/new_chat/chat_modes.py`).
- **`enabled_tools` should not isolate the agent:** the meeting-minutes mode should inject a system prompt, not disable base tools. Users may want the agent to search related docs after generating minutes.
- **Feature gate on all routes:** every route in `app/routes/meeting_minutes_routes.py` must check `MEETING_MINUTES_ENABLED` and return 403 if disabled.
- **Audio file TTL and privacy:** the uploaded audio `Document` row and its blob are hard-deleted immediately after the transcript is saved. The `MeetingMinutes` row stores only `audio_source_url` (for audit), transcript, summary, and action items.
- **TokenUsage in async path:** `TokenUsage` rows for `meeting_minutes_transcription` and `meeting_minutes_extraction` must be written by the worker **after** the job completes, not when the tool returns the processing state. Use the same `record_token_usage()` flow as other deliverables.
- **Cross-cutting artifact system change:** adding `meeting_minutes` to `ArtifactKind` touches the same files as 27.2a (`model/artifact.ts`, `ARTIFACT_TOOL_KINDS`, `BODY_TOOLS`, `KIND_META`, `GROUP_ORDER`, `collect-artifacts.ts`). Treat as **Step 0**.

## Technical Decisions (post-research)

### 1. Diarization library: `pyannote.audio`, not `whisperx`

- **Why `pyannote.audio`:** Context7 confirms `pyannote.audio` 4.0.7 declares `torch>=2.8.0`, `torchaudio>=2.8.0`, `torchcodec>=0.7.0`. The repo already pins `torch==2.11.0` / `torchvision==0.26.0` via `cpu`/`cu126`/`cu128` extras, so `pyannote.audio` can be added as an optional extra without forcing a PyTorch downgrade.
- **Why not `whisperx`:** `whisperx`'s `pyproject.toml` pins `torch~=2.8.0`, `torchaudio~=2.8.0`, `torchvision~=0.23.0` and adds `ctranslate2>=4.5.0` which may conflict with the existing `faster-whisper>=1.1.0` / `ctranslate2` version. Installing `whisperx` would likely break the existing image-generation and other `torch==2.11.0` consumers.
- **How we use `pyannote.audio`:** load `pyannote.audio.Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=os.getenv("HUGGINGFACE_TOKEN") or True)`, run it on the audio file, then map `faster-whisper` word/segment timestamps onto diarization turns by largest overlap. This gives the same output shape as `whisperx.assign_word_speakers` without the dependency conflict.

### 2. Transcription: extend existing `faster-whisper` instead of replacing it

- The existing `STTService` in `app/services/stt_service.py` currently returns combined text only. Add `transcribe_file_segments()` returning per-segment `start`, `end`, `text`, and `words`.
- This keeps the current `faster-whisper` dependency and avoids downloading a second Whisper model.

### 3. Async pattern: Celery worker mirroring `video_presentation_tasks.py` + idempotent `processing_task_id`

- The tool must **not** wait for diarization inside `stream_new_chat`; it creates a `MeetingMinutes` row, enqueues Celery, and returns `status="processing"`.
- The worker copies the `video_presentation_tasks.py` pattern (`run_async_celery_task`, `get_celery_session_maker`, `_resolve_agent_billing_for_workspace`, `billable_call`).
- For idempotency on Celery redelivery, the worker uses `processing_task_id` (Celery `self.request.id`) as a claim. If the row already has a different `processing_task_id`, the worker returns immediately. This is a lighter alternative to the `run_memory_extraction_task.py` CAS while still preventing duplicate LLM calls.

### 4. Cost tracking: two `TokenUsage` rows + `TokenQuotaService` for compute

- `MEETING_MINUTES_TRANSCRIPTION`: flat compute cost for STT + diarization. Reserve `duration_seconds * MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND` via `TokenQuotaService.credit_reserve`, then `credit_finalize` with the same amount and `record_token_usage`. For MVP the default rate is `0`; the code path is required so the rate can be turned on later.
- `MEETING_MINUTES_EXTRACTION`: LLM cost inside `billable_call` with `usage_type="meeting_minutes_extraction"`, mirroring `video_presentation_tasks.py`.

### 5. Audio source and retention

- `audio_url` is downloaded to a temp file in the worker (with timeout and retry) and deleted immediately after transcription.
- `document_id` streams the `DocumentFile` blob to a temp file; the temp file is deleted immediately, and the `Document` row/`DocumentFile` blob is hard-deleted after the `MeetingMinutes` is saved (AD-28.3 right-to-delete).
- The `MeetingMinutes` row stores only the transcript, summary, and action items, plus `audio_source_url` for audit.

### 6. Zero sync over polling

- Add `meeting_minutes` to `app/zero_publication.py` with only lightweight columns (`id`, `workspace_id`, `thread_id`, `status`, `title`, `error`, `created_at`, `updated_at`).
- The deliverable card Zero-syncs the row; poll `GET /api/v1/meeting-minutes/{id}` only as a fallback if Zero is unavailable.

## Architecture Alignment (Nowing Spine)

| AD | Invariant | Alignment | Required action |
|---|---|---|---|
| AD-1 | Monolith module hóa | `MeetingMinutesService` lives in `app/services/`, worker in `app/tasks/`, tool in `app/agents/`. No new microservice. | ✅ None |
| AD-2 | Async SQLA + Alembic + pgvector | New `MeetingMinutes` table, `AsyncSession`, Alembic migration. | ✅ None |
| AD-4 | Tool registry + permission middleware | Tool registered via `main_agent/tools/registry.py`; must log `AgentActionLog` and honor `PermissionMiddleware` on mutations. | ⚠️ Add `AgentActionLog` write and workspace auth to all `meeting_minutes_routes.py`. |
| AD-5 | Zero sync real-time | `meeting_minutes` table should be in `zero_publication`; frontend gets status updates via Zero instead of polling. | ⚠️ Add `meeting_minutes` to Zero publication or expose status via SSE. |
| AD-6 | Next.js server proxy | Frontend uses existing `/api/v1` proxy. | ✅ None |
| AD-8 | Unified credit wallet, real cost | `TokenUsage.cost_micros` recorded **after** async job completes. STT/diarization compute is a flat rate reserved/finalized via `TokenQuotaService`; LLM extraction is inside `billable_call`. | ⚠️ Move TokenUsage write into Celery worker; reserve `duration * micros_per_second` before diarization. |
| AD-9 | RBAC 3 roles | All REST routes must call `require_workspace_member` like `web_builder_routes.py`. | ⚠️ Add `require_workspace_member` to `meeting_minutes_routes.py`. |
| AD-10 | Token usage per msg/ws/user | `usage_type="meeting_minutes_transcription"` and `"meeting_minutes_extraction"` recorded. | ✅ None |
| AD-16 | License boundary | `pyannote.audio` MIT; code in `app/services/` (Apache/MIT), not `app/proprietary/`. `whisperx` is not used. | ✅ None |
| AD-17 | Async door | ⚠️ **Critical:** `stt_service.py` is synchronous. Diarization must not run inside `stream_new_chat`; use Celery background job (`app/tasks/`). | 🔴 Add `tasks/process_meeting_minutes.py` and `MeetingMinutes.status="processing"`. |
| AD-21 | Client tab state pointer-only | `?mode=meeting_minutes` is URL pointer; no local storage state. | ✅ None |
| AD-28.3 | Retention + right-to-delete | Audio `Document`/temp file must be deleted after processing; user can delete `MeetingMinutes` and transcript. | ⚠️ Add TTL + `DELETE /api/v1/meeting-minutes/{id}` + audit. |
| AD-30 | AgentConfig registry | Mode mapping goes through `ChatMode` registry, not hardcoded `if/elif` in `orchestrator.py`. | ⚠️ Register `meeting_minutes_mode` in `ChatMode` registry. |

### Alignment action items for 27.2b

1. **AD-17 (mandatory):** implement async processing. Tool creates `MeetingMinutes` row with `status="pending"`, returns `status="processing"` immediately, and enqueues Celery. Worker runs `stt_service.transcribe_file_segments` + `pyannote.audio` diarization + LLM extraction. Frontend Zero-syncs (poll fallback).
2. **AD-28.3 (mandatory):** hard-delete temp audio files immediately after transcription; hard-delete `Document` rows/blobs after `MeetingMinutes` is saved; provide `DELETE /api/v1/meeting-minutes/{id}`.
3. **AD-8 (mandatory):** reserve `duration * MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND` before diarization and finalize it after; wrap LLM extraction in `billable_call`; write `TokenUsage` rows inside the Celery worker.
4. **AD-5:** add `meeting_minutes` table to `zero_publication` so deliverable card updates in real time.
5. **AD-9:** add `require_workspace_member` to all `meeting_minutes_routes.py` endpoints.
6. **AD-4:** write `AgentActionLog` for `generate_meeting_minutes` tool calls.
7. **AD-30:** implement `ChatMode` registry (shared with 27.2a / 27.1a).

## [BUILT] vs [GAP]

### [BUILT] — patterns to reuse

- **Whisper STT service** (`app/services/stt_service.py` — `faster-whisper` transcription). Already loads model, transcribes audio to text with language detection.
- **Circleback meeting notes webhook** (`app/routes/circleback_webhook_route.py` → Markdown `Document`). Good pattern for turning external meeting data into a Markdown doc.
- **Document model + file upload** (`app/db.py:Document`, `app/routes/documents_routes.py`, `app/routes/uploads_routes.py`). Audio file can be stored as a `Document` with `content_type` and `source_url`.
- **Chat tool + artifact pattern from 27.1a:** `build_web_app` tool factory, `BODY_TOOLS`, `ARTIFACT_TOOL_KINDS`, `ArtifactKind`.
- **Tool registry** (`app/agents/chat/multi_agent_chat/main_agent/tools/index.py` and `registry.py`).
- **TokenUsage** pattern for cost tracking.
- **Chat mode gating** (`app/config/__init__.py`, `app/routes/new_chat_routes.py`, `app/tasks/chat/streaming/flows/new_chat/orchestrator.py`).

### [GAP] — new work

1. **Config + feature gate** (`app/config/__init__.py`):
   - `MEETING_MINUTES_ENABLED = os.getenv("MEETING_MINUTES_ENABLED", "FALSE").upper() == "TRUE"`
   - `MEETING_MINUTES_MAX_AUDIO_BYTES` (default 100 MB)
   - `MEETING_MINUTES_MAX_DURATION_SECONDS` (default 600 = 10 minutes)
   - `MEETING_MINUTES_DIARIZATION_ENGINE` (`pyannote` | `none`; default `pyannote`)
   - `MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND` (default 0 for MVP; may be raised once CPU cost is measured)
   - `HUGGINGFACE_TOKEN` (required when `DIARIZATION_ENGINE=pyannote`; used by `pyannote.audio` to download gated `pyannote/speaker-diarization-3.1`)

2. **Dependencies** (`pyproject.toml`):
   - **Chosen diarization library: `pyannote.audio>=4.0.0` as an optional extra `meeting-minutes`.**
     - `whisperx` is **rejected** for this story: its `pyproject.toml` pins `torch~=2.8.0`, `torchaudio~=2.8.0`, `torchvision~=0.23.0`, which conflicts with the repo's `torch==2.11.0` + `torchvision==0.26.0`. Resolving that would force a downgrade/replacement of the existing PyTorch stack used by image generation and other features.
     - `pyannote.audio` declares `torch>=2.8.0`, `torchaudio>=2.8.0`, `torchcodec>=0.7.0` and should be compatible with the existing `torch==2.11.0` extras (`cpu`/`cu126`/`cu128`). **Validate with `uv lock --extra meeting-minutes --extra cpu` before merging; adjust versions if the resolver conflicts.**
     - Add a `meeting-minutes` optional extra under `[project.optional-dependencies]`:
       ```toml
       meeting-minutes = [
           "pyannote.audio>=4.0.0",
           "torchaudio>=2.8.0",
           "torchcodec>=0.7.0",
       ]
       ```
       (add `huggingface-hub` only if not already pulled; the project already has `huggingface-hub>=0.28.1` via `pyannote.audio` and direct dependencies).
   - Fallback: if `pyannote.audio` is not installed or `MEETING_MINUTES_DIARIZATION_ENGINE=none`, return `status="degraded"` with transcript-only and a single `Speaker 1` label. Do not fail the install for self-hosted users.

3. **Database model** (`app/db.py` + alembic migration):
   - New `MeetingMinutesStatus` StrEnum: `pending`, `processing`, `ready`, `failed`, `degraded`.
   - New `MeetingMinutes` table (inherits `BaseModel`, so `id` is an auto-increment `Integer` like `VideoPresentation`):
     - `id` (Integer PK, inherited)
     - `workspace_id` (FK `workspaces.id`, not null, index)
     - `user_id` (UUID, not null)
     - `thread_id` (FK `new_chat_threads.id`, nullable)
     - `document_id` (FK `documents.id`, nullable — only if the audio was uploaded as a `Document`)
     - `audio_source_url` (Text, nullable — original URL if `audio_url` was used; never the raw blob)
     - `processing_task_id` (String, nullable — Celery `self.request.id` used as an idempotency claim, see Technical Decisions)
     - `title` (String, nullable)
     - `status`
     - `transcript` (JSONB: list of `{speaker, text, start, end}`)
     - `action_items` (JSONB: list of `{speaker, task, due}`)
     - `summary` (Text)
     - `raw_transcript` (Text)
     - `error` (Text, nullable)
     - `metadata` (JSONB)
     - `created_at`, `updated_at`
   - `Workspace.meeting_minutes` relationship.

4. **Diarization service** (`app/services/meeting_minutes/`):
   - `STTService` extension: add `transcribe_file_segments(audio_path, language=None)` that returns `faster-whisper` segments with `start`, `end`, `text`, and `words` (when available). Keep the existing `transcribe_file` API unchanged.
   - `DiarizationService`:
     - If `MEETING_MINUTES_DIARIZATION_ENGINE=none` or `pyannote.audio` import fails, return a single `Speaker 1` segment covering the whole audio.
     - Otherwise load `pyannote.audio.Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=os.getenv("HUGGINGFACE_TOKEN") or True)` once and cache it per worker process.
     - Run the pipeline on the audio file to get `(start, end, speaker)` turns.
     - Map each `faster-whisper` word/segment to the diarization turn with the largest time overlap; collapse consecutive words with the same speaker into transcript segments.
   - `MeetingMinutesService`:
     - Resolve audio source: download `audio_url` to a temp file (with timeout/retry) or stream `document_id` from `DocumentFile` storage to a temp file.
     - Validate size and duration before transcription; reject early if limits exceeded.
     - Call `STTService.transcribe_file_segments`.
     - Call `DiarizationService.diarize`.
     - Merge into `transcript`.
     - Resolve billing via `_resolve_agent_billing_for_workspace(session, workspace_id, thread_id=meeting_minutes.thread_id)` (same helper as `video_presentation_tasks.py`).
     - Wrap LLM extraction in `billable_call` with `usage_type=UsageType.MEETING_MINUTES_EXTRACTION` (or `"meeting_minutes_extraction"` string) and an override reserve based on transcript token count; call `get_agent_llm(session, workspace_id)` inside.
     - Return typed `MeetingMinutesOutput`.
   - Storage: do **not** save generated minutes to filesystem; keep `transcript`/`action_items`/`summary` in the `MeetingMinutes` row. The download endpoint renders Markdown on the fly.

5. **Pydantic schemas** (`app/services/meeting_minutes/schemas.py`):
   - `GenerateMeetingMinutesInput`: `audio_url` or `document_id` (int), `language` (optional, default `"auto"`), `title` (optional).
   - `GenerateMeetingMinutesOutput`: `meeting_minutes_id` (int, same `BaseModel` `id` type), `title`, `status`, `transcript` (list of segments), `action_items`, `summary`, `download_url`, `error`.
   - `MeetingMinutesStatus` values also reflected in the DB enum.

6. **LangChain tool** (`app/agents/chat/multi_agent_chat/main_agent/tools/meeting_minutes/generate_meeting_minutes.py`):
   - Factory `create_generate_meeting_minutes_tool(deps)`.
   - Tool `generate_meeting_minutes(audio_url: str | None = None, document_id: int | None = None, language: str = "auto")`.
   - Validates that exactly one of `audio_url` or `document_id` is provided.
   - Creates a `MeetingMinutes` row with `status="pending"`.
   - Enqueues `process_meeting_minutes` Celery task.
   - Returns `GenerateMeetingMinutesOutput(status="processing", meeting_minutes_id=..., download_url=...)` immediately. **Do not call the heavy service inline.**

7. **Celery worker** (`app/tasks/celery_tasks/process_meeting_minutes.py`):
   - Mirror `video_presentation_tasks.py` shape: `run_async_celery_task`, `get_celery_session_maker`.
   - **Idempotency:** on entry, SELECT the row; if `status` is already `ready`/`failed`/`degraded`, return. If `status` is `pending` and `processing_task_id` is `NULL`, set `status="processing"` and `processing_task_id = self.request.id`, then commit. If `processing_task_id` is already set to a different task id, log and return (another worker is running).
   - On crash/OOM: a stale `processing` row is possible; add a periodic stale-cleanup task or a `processing_started_at` column for future reclaim (MVP can leave it; the deliverable card will simply hang and user can retry after a documented timeout).
   - Wrap LLM extraction in `billable_call` (reuse `app/services/billable_calls.py`) with `usage_type=UsageType.MEETING_MINUTES_EXTRACTION` and a `quota_reserve_micros_override` based on transcript length.
   - For transcription/diarization compute cost, reserve a flat `duration_seconds * MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND` via `TokenQuotaService.credit_reserve`, then `credit_finalize` with the same amount (flat compute charge), and record a `TokenUsage` row with `usage_type=UsageType.MEETING_MINUTES_TRANSCRIPTION`.
   - On any exception, mark `MeetingMinutes.status="failed"`, record `error`, release any reservation, and re-raise only for Celery retry on transient errors (`TimeoutError`, LLM API errors).

8. **Tool registration** (`app/agents/chat/multi_agent_chat/main_agent/tools/index.py` and `registry.py`):
   - Add `generate_meeting_minutes` to `MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED`.
   - Register in `MAIN_AGENT_NOWING_TOOL_FACTORIES` with deps `("workspace_id", "user_id")`.

9. **Chat mode wiring** (`app/routes/new_chat_routes.py`, `app/tasks/chat/streaming/flows/new_chat/orchestrator.py`):
   - Allow `platform_metadata.meeting_minutes_mode=true`.
   - 403 if `MEETING_MINUTES_ENABLED=false`.
   - In `stream_new_chat`, when mode is true, enable `generate_meeting_minutes` and prepend a system prompt instructing the user to paste an audio URL.
   - Per-turn override + thread fallback (same `ChatMode` registry as 27.2a/27.1a).

10. **Frontend deliverable card** (`nowing_web/components/tool-ui/meeting-minutes.tsx` new file):
    - `MeetingMinutesToolUI` shows title, transcript segments grouped by speaker, action items checklist, summary, download button.
    - States: `pending`, `processing`, `ready`, `failed`, `degraded`.
    - Zero-syncs `meeting_minutes` table or polls `GET /api/v1/meeting-minutes/{id}` every 2 seconds while `processing`.

11. **Artifact mapping** (`nowing_web/components/assistant-ui/assistant-message.tsx`, `nowing_web/features/chat-artifacts/model/artifact.ts`, `nowing_web/features/chat-artifacts/ui/artifact-row.tsx`, `nowing_web/features/chat-artifacts/ui/artifacts-panel.tsx`, `nowing_web/features/chat-artifacts/lib/collect-artifacts.ts`):
    - Add `"meeting_minutes"` to `ArtifactKind`.
    - Map `generate_meeting_minutes: "meeting_minutes"` in `ARTIFACT_TOOL_KINDS` and `BODY_TOOLS`.
    - Add icon and group order after "Slide Decks".
    - Add `describeArtifact` case.

12. **Chat entry points** (`nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx`, `nowing_web/components/assistant-ui/thread.tsx`, `nowing_web/components/new-chat/prompt-picker.tsx`):
    - Quick chip "Summarize a meeting".
    - Slash prompt `/meeting`.
    - URL query `?mode=meeting_minutes`.

13. **REST routes** (`app/routes/meeting_minutes_routes.py`):
    - `GET /api/v1/meeting-minutes` (list, workspace-scoped, paginated).
    - `GET /api/v1/meeting-minutes/{meeting_minutes_id}` (read).
    - `GET /api/v1/meeting-minutes/{meeting_minutes_id}/download` (Markdown export).
    - `DELETE /api/v1/meeting-minutes/{meeting_minutes_id}` (right-to-delete, AD-28.3).
    - Feature-gated 403 if disabled.
    - All routes use `require_workspace_member`.

14. **Zero sync + cleanup**:
    - Add `meeting_minutes` to `app/zero_publication.py` with a lightweight column list: `id`, `workspace_id`, `thread_id`, `status`, `title`, `error`, `created_at`, `updated_at`. Exclude `transcript`, `action_items`, `summary` (fetched over REST).
    - TTL: immediately delete the downloaded temp file after transcription/diarization. If `document_id` was provided, **hard-delete the `DocumentFile` blob** and the `Document` row (or set `archived_at`) after successful processing. The `MeetingMinutes` row keeps only the transcript/minutes.
    - Add a nightly Celery cleanup task that finds `MeetingMinutes` rows older than retention and hard-deletes them along with any leftover audio blobs (reuse document retention cron pattern).

15. **Token usage / cost tracking**:
    - Add `UsageType.MEETING_MINUTES_TRANSCRIPTION` and `UsageType.MEETING_MINUTES_EXTRACTION` to `app/services/token_tracking_service.py`.
    - Worker records `MEETING_MINUTES_TRANSCRIPTION` after diarization (flat compute charge) and `MEETING_MINUTES_EXTRACTION` inside `billable_call` (LLM tokens).
    - Add both usage types to `app/services/billable_calls.py::BACKGROUND_ARTIFACT_USAGE_TYPES` so the worker session handles them correctly.

## Acceptance Criteria

### AC-1: Chat Session in Meeting Minutes Mode

- **Given** the user is on the new-chat welcome screen,  
  **When** they click "Summarize a meeting" (or use `/meeting` or `?mode=meeting_minutes`),  
  **Then** a thread is created with `platform_metadata: { "meeting_minutes_mode": true }`, and the chat runtime enables the `generate_meeting_minutes` tool.

- **Given** a meeting-minutes chat session,  
  **When** the user provides an audio file or URL and submits,  
  **Then** the agent calls `generate_meeting_minutes` and the response stream includes a deliverable card with `meeting_minutes_id`, `title`, `status`, `transcript` preview, `action_items`, and `download_url`.

### AC-2: Transcription with Speaker Diarization

- **Given** a meeting audio file with multiple speakers,  
  **When** `MeetingMinutesService` processes it,  
  **Then** the output contains a transcript broken into segments, each labeled `Speaker A`, `Speaker B`, etc., and a summary of the meeting.

- **Given** the diarization engine is installed and enabled,  
  **When** the transcript is generated,  
  **Then** action items are grouped by speaker and included in the deliverable.

### AC-3: Graceful Degradation

- **Given** the diarization dependency is not installed, `MEETING_MINUTES_DIARIZATION_ENGINE=none`, or `HUGGINGFACE_TOKEN` is missing/invalid,  
  **When** the user requests meeting minutes,  
  **Then** the system returns a full transcript with a single `Speaker 1` label and `status="degraded"`, and a clear note that speaker labels are unavailable.

- **Given** no speech is detected or the audio is silent,  
  **When** the service processes it,  
  **Then** it returns `status="degraded"` with an empty `transcript` and `summary="No speech detected."`.

- **Given** the audio file is too large, unsupported, or corrupted,  
  **When** the service processes it,  
  **Then** it returns `status="failed"` with a human-readable `error` and does not crash.

- **Given** LLM extraction returns malformed JSON,  
  **When** the service retries once and still fails,  
  **Then** it returns `status="degraded"` with the transcript and an empty `action_items` list.

### AC-4: Workspace-Scoped Registry + Cost Tracking

- **Given** a generated meeting minutes,  
  **When** it is saved,  
  **Then** a `MeetingMinutes` row is written with `workspace_id`, `user_id`, `document_id`, `status`, and `created_at`.

- **Given** the worker completes transcription + diarization,  
  **When** the service finalizes compute cost,  
  **Then** a `TokenUsage` row with `usage_type="meeting_minutes_transcription"` is recorded with a flat compute `cost_micros`.

- **Given** the worker completes LLM extraction,  
  **When** `billable_call` closes,  
  **Then** a `TokenUsage` row with `usage_type="meeting_minutes_extraction"` is recorded with actual LLM `cost_micros`.

### AC-5: Feature Gating

- **Given** `MEETING_MINUTES_ENABLED=false`,  
  **When** a user tries to create a meeting-minutes thread or call the generation route,  
  **Then** the API returns 403 with a clear message.

### AC-6: Edge Cases & Degradation

#### Audio duration and file-size limits

- **Given** an audio file is at or below `MEETING_MINUTES_MAX_AUDIO_BYTES` and `MEETING_MINUTES_MAX_DURATION_SECONDS`,  
  **When** the worker validates the file,  
  **Then** it proceeds to transcription/diarization; boundary values are accepted (inclusive).

- **Given** an audio file exceeds `MEETING_MINUTES_MAX_AUDIO_BYTES` or `MEETING_MINUTES_MAX_DURATION_SECONDS`,  
  **When** the worker validates the file,  
  **Then** it rejects before transcription with `status="failed"` and `error="audio_too_large"`.

- **Given** an audio file has zero or sub-second duration,  
  **When** the worker validates the file,  
  **Then** it returns `status="degraded"` with `summary="No speech detected."`.

#### Concurrent double-click and idempotent enqueue

- **Given** a user double-clicks the quick chip,  
  **When** `generate_meeting_minutes` is invoked twice,  
  **Then** each click creates its own `MeetingMinutes` row and Celery task; the UI documents that no URL-based idempotency is enforced in MVP.

- **Given** a worker picks up a `MeetingMinutes` row,  
  **When** the `processing_task_id` is already set to a different task id,  
  **Then** the worker returns immediately to prevent duplicate processing.

#### Language auto-detection fallback

- **Given** `language="auto"` and `faster-whisper` returns a language with low confidence (< 0.5),  
  **When** the worker processes the audio,  
  **Then** it falls back to a configurable default language (e.g., `en`) and records the low-confidence language in `metadata`.

- **Given** a requested language is not supported by the loaded `faster-whisper` model,  
  **When** the worker runs transcription,  
  **Then** it returns `status="degraded"` with transcript-only and `error="unsupported_language"`.

#### Token/credit exhaustion and cost reservation

- **Given** the workspace has insufficient credits for transcription compute,  
  **When** the worker attempts to reserve cost,  
  **Then** it returns `status="failed"` with `error="insufficient_credits"` and does not run diarization.

- **Given** the workspace has insufficient credits for LLM extraction,  
  **When** `billable_call` is invoked,  
  **Then** it raises `QuotaInsufficientError`, the worker sets `status="failed"`, `error="insufficient_credits"`, and releases any reservation.

- **Given** the actual cost exceeds the wallet balance mid-worker,  
  **When** the worker detects a negative balance,  
  **Then** it records `TokenUsage` for the consumed amount and does not allow further spend in the same turn.

#### Audio download failure / network / source errors

- **Given** an `audio_url` returns `404`, `403`, a redirect loop, or an SSL error,  
  **When** the worker downloads the audio,  
  **Then** it retries with timeout/backoff and then sets `status="failed"` with `error="audio_url_unreachable"`.

- **Given** the audio `Document` row or blob is deleted before the worker starts,  
  **When** the worker loads the document,  
  **Then** it sets `status="failed"` with `error="audio_document_missing"`.

- **Given** file storage is missing or full,  
  **When** the worker writes the audio temp file,  
  **Then** it handles `OSError`, logs the failure, and sets `status="failed"` with `error="storage_error"`.

#### GPU OOM / `pyannote.audio` import failure degraded path

- **Given** `pyannote.audio` fails to import or the `pyannote/speaker-diarization-3.1` model download fails,  
  **When** the worker runs diarization,  
  **Then** it falls back to a single `Speaker 1` segment covering the whole audio and returns `status="degraded"`.

- **Given** the diarization pipeline raises OOM or a memory error,  
  **When** the worker catches the error,  
  **Then** it retries once on a smaller chunk or returns `status="degraded"` with transcript-only and a clear note.

#### `record_token_usage` failure must not abort the turn

- **Given** the worker completes transcription or extraction,  
  **When** `record_token_usage` fails,  
  **Then** the worker logs and alerts but still returns the deliverable with the correct `status`; the failure is best-effort audit only.

## Consequences

- New `app/services/meeting_minutes/` module.
- New `MeetingMinutes` DB table + alembic migration.
- New `app/tasks/celery_tasks/process_meeting_minutes.py` worker.
- New `pyannote.audio` optional extra (`meeting-minutes`); `whisperx` explicitly not chosen.
- New `UsageType.MEETING_MINUTES_TRANSCRIPTION` and `UsageType.MEETING_MINUTES_EXTRACTION` in `app/services/token_tracking_service.py`.
- New frontend tool card and artifact kind.
- New `DELETE` route and audio-blob cleanup for AD-28.3 retention / right-to-delete.

## Edge Cases & Risks

| Edge | Handling |
|---|---|
| No `audio_url` and no `document_id` | Tool returns `validation_failed` with error "Provide an audio file or URL." |
| Both `audio_url` and `document_id` provided | Tool returns `validation_failed` with error "Provide only an audio URL **or** an already-uploaded document, not both." |
| `audio_url` is empty/whitespace or `document_id` <= 0 | Tool returns `validation_failed` before creating a `MeetingMinutes` row. |
| Audio URL returns 404 / 403 / redirect loop / SSL error | Worker catches `httpx.HTTPError`/`aiohttp.ClientError`, sets `status="failed"`, `error="audio_url_unreachable"`, and does not retry (terminal). |
| Audio format unsupported (not in `supported-extensions.ts`) | Worker sets `status="failed"`, `error="unsupported_format"`. |
| Audio exceeds `MEETING_MINUTES_MAX_AUDIO_BYTES` or `MEETING_MINUTES_MAX_DURATION_SECONDS` | Worker rejects **before** transcription/diarization with `error="audio_too_large"`. |
| Diarization dependency not installed or `MEETING_MINUTES_DIARIZATION_ENGINE=none` | Service returns `status="degraded"` with full transcript under a single `Speaker 1` label and a privacy-safe note. |
| `pyannote.audio` import fails or `HUGGINGFACE_TOKEN` missing/invalid | Same `degraded` fallback. Log the missing token clearly so self-hosters know what to set. |
| `faster-whisper` model fails to load (missing file / no disk / OOM) | Worker sets `status="failed"`, `error="transcription_model_error"`. |
| No speech detected | Service returns `status="degraded"`, `transcript=[]`, `summary="No speech detected."` |
| Diarization returns 0, 1, or >10 speakers | Use `Speaker 1`...`Speaker N`; cap display labels at a configurable `MEETING_MINUTES_MAX_SPEAKER_LABELS` (default 20). Do not hallucinate names. |
| LLM extraction returns malformed JSON | Retry once with a stricter JSON prompt; on second failure, return `status="degraded"` with transcript and `action_items=[]`. |
| `MEETING_MINUTES_ENABLED=false` | 403 on thread creation and all routes. |
| Token/credit insufficient for LLM extraction | `billable_call` raises `QuotaInsufficientError`; worker sets `status="failed"`, `error="insufficient_credits"`, releases reservation. |
| Token/credit insufficient for transcription compute | Worker checks wallet before reserving; if denied, sets `status="failed"`, `error="insufficient_credits"`. |
| User double-clicks quick chip | Two `MeetingMinutes` rows are allowed (no URL-based idempotency in MVP), but each gets its own Celery task. Document in UX as known. |
| `Document` row deleted before worker starts | Worker sets `status="failed"`, `error="audio_document_missing"`. |
| User deletes `MeetingMinutes` while worker is running | Worker finishes but `MeetingMinutes` row is gone; the resulting `UPDATE` affects 0 rows. Logs warn. No orphan `MeetingMinutes`. |
| Celery worker killed mid-processing | Row stays `processing` and card hangs. Add a **documented timeout** in the UI (e.g., "Taking longer than expected. Refresh or try again in a few minutes."). A future story can add stale-reaper. |
| Postgres/Redis down after tool returns `processing` | Card stays `processing` until service recovers. The worker will resume from retry (transient) or mark `failed` (terminal). |
| `record_token_usage` fails inside worker | Log and alert, but do not fail the deliverable. This is best-effort audit. |

## Verification Commands

Backend:
```bash
cd nowing_backend
ruff check app/services/meeting_minutes app/routes/meeting_minutes_routes.py app/agents/chat/multi_agent_chat/main_agent/tools/meeting_minutes app/tasks/celery_tasks/process_meeting_minutes.py app/db.py app/config/__init__.py app/services/token_tracking_service.py
ruff format app/services/meeting_minutes app/routes/meeting_minutes_routes.py app/agents/chat/multi_agent_chat/main_agent/tools/meeting_minutes app/tasks/celery_tasks/process_meeting_minutes.py app/db.py app/config/__init__.py app/services/token_tracking_service.py
uv run uv lock --extra meeting-minutes --extra cpu
uv run alembic upgrade head
uv run pytest tests/unit/services/meeting_minutes -q
uv run pytest tests/unit/tasks/celery_tasks/test_process_meeting_minutes.py -q
uv run pytest tests/integration/services/test_meeting_minutes.py -q
```

Frontend:
```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/tool-ui/meeting-minutes.tsx components/assistant-ui/assistant-message.tsx features/chat-artifacts features/new-chat --diagnostic-level=error
```

## Challenge Log (grill-me)

### Q1 — Is this already implemented?

- **No duplicate of diarization/speaker-label logic found.** Searched `vibervn-context-engine` for "speaker diarization", "meeting minutes", "pyannote", "whisperx", "speaker labels" — no existing implementation in `nowing_backend`.
- **Existing audio transcription:** `app/services/stt_service.py` uses `faster-whisper` and returns combined text (no per-word timestamps, no speaker labels). It will need to be extended or bypassed to support diarization.
- **Existing audio upload support:** `nowing_web/lib/supported-extensions.ts` already lists `audio/mpeg`, `audio/mp4`, `audio/wav`, `audio/webm` as accepted document upload types. `DocumentUploadTab.tsx` and `documents_routes.py` can store audio as a `Document`.
- **Existing async task pattern:** `app/tasks/celery_tasks/run_memory_extraction_task.py` (`extract_memory_after_run`) is the canonical Celery pattern to copy: `run_async_celery_task`, `get_celery_session_maker`, `autoretry_for` transient LLM errors, idempotent completion state. **Not a duplicate, but a pattern to reuse.**
- **Risk of confusion:** There is a test artifact `atdd-checklist-48-7-slow-path-audio-groq-whisper-stt.md` in the repo, but it belongs to `chainlens-research` (external Whisper provider) and is not implemented in Nowing. Do not conflate it with 27.2b's local `faster-whisper` + `pyannote/whisperx`.

**Verdict:** No duplicate logic. Proceed, but reuse the existing `run_async_celery_task` + `record_token_usage` patterns.

### Q2 — Is there a simpler alternative?

- **Celery task wrapper:** Reuse `app/tasks/celery_tasks/__init__.py::run_async_celery_task` and `get_celery_session_maker` instead of a new event-loop setup. This is the canonical helper and avoids the previous copy-paste bug.
- **Token usage recording:** Reuse `app/services/token_tracking_service.py::record_token_usage` with `UsageType` enum, already called from other Celery tasks.
- **STT path:** Extend `stt_service.py` to add `transcribe_file_segments()` returning `start`/`end`/`text`/`words`. This is chosen over replacing with `whisperx` because `whisperx` has PyTorch version conflicts (see Technical Decisions §1).
- **Diarization path:** Use `pyannote.audio` directly (`pyannote/speaker-diarization-3.1`), not `whisperx`, and assign speakers by time overlap. Chosen because it is compatible with the repo's `torch==2.11.0`.
- **No "skip diarization" simplification for MVP:** that would violate the story scope. `MEETING_MINUTES_DIARIZATION_ENGINE=none` and import failures are the degraded fallback.

**Verdict:** Reuse canonical Celery and token-usage helpers. Chosen stack: `faster-whisper` (transcription) + `pyannote.audio` (diarization) + existing LLM extractor.

### Q3 — What edge cases does the spec miss?

- [x] (covered by AC-6) **Boundary — duration/file size:** audio exactly at `MEETING_MINUTES_MAX_DURATION_SECONDS` or `MEETING_MINUTES_MAX_AUDIO_BYTES` (inclusive vs exclusive).
- [x] (covered by AC-6) **Boundary — max duration seconds:** zero-duration or sub-second audio.
- [x] (covered by AC-6) **Null/empty:** `audio_url` is `''` or whitespace-only; `document_id` is 0 or negative.
- [x] (covered by AC-6) **Null/empty:** both `audio_url` and `document_id` missing (story handles, but AC does not explicitly mention).
- [x] (covered by AC-6) **Concurrent:** user double-clicks quick chip; two `MeetingMinutes` rows created for the same audio.
- [x] (covered by AC-6) **Concurrent:** two users in the same workspace paste the same public `audio_url` at the same time; idempotency by URL is not specified.
- [x] (covered by AC-6) **Language:** `language="auto"` with `faster-whisper` — it returns `info.language`; what if probability is low (< 0.5)?
- [x] (covered by AC-6) **Language:** requested language not supported by `faster-whisper` model size.
- [x] (covered by AC-6) **Speaker count:** diarization returns 1, 10, 50, or 0 speakers; max number of speakers not capped in UI.
- [x] (covered by AC-6) **Speaker labels:** `Speaker 1`, `Speaker 2`, ... are stable within one run but not comparable across runs/re-generations.
- [x] (covered by AC-6) **Action items:** no action items in the meeting; `action_items` should be `[]`, not a fabricated generic list.
- [x] (covered by AC-6) **Malformed JSON:** LLM extraction of `action_items` returns non-JSON or wrong schema.
- [x] (covered by AC-6) **Download URL:** `download_url` generated for `ready` row but file has been TTL-deleted.
- [x] (covered by AC-6) **Celery redelivery:** worker killed after creating `MeetingMinutes` but before setting `status="ready"`; retry must be idempotent.

### Q4 — What failure modes are unspecified?

- [x] (covered by AC-6) **`faster-whisper` model fails to load** (missing model file / no disk space / OOM): currently raises in `stt_service._get_model`; worker should catch and return `status="failed"`.
- [x] (covered by AC-6) **`pyannote.audio` import fails** or model download fails (gated `pyannote/speaker-diarization-3.1`, bad `HUGGINGFACE_TOKEN`): worker falls back to `status="degraded"` with transcript-only.
- [x] (covered by AC-6) **GPU OOM during diarization:** currently CPU is forced in `stt_service`; diarization may still OOM with large audio.
- [x] (covered by AC-6) **Celery worker not running / Redis down:** `generate_meeting_minutes` returns `processing`, but the deliverable card stays in `processing` forever. Need timeout/detection.
- [x] (covered by AC-6) **Postgres down after tool returns `processing`:** frontend cannot poll; status stays `processing` until worker recovers.
- [x] **LLM extraction fails after transcription succeeds:** retry once; on second failure set `status="degraded"` with transcript and empty `action_items`.
- [x] (covered by AC-6) **Cost exceeds wallet mid-worker:** credit check happens at chat turn, but LLM/diarization cost is real; negative balance possible if cost estimate is wrong.
- [x] (covered by AC-6) **Audio `Document` row deleted before worker starts:** worker must handle missing `document_id` and fail gracefully.
- [x] (covered by AC-6) **Audio URL returns 404 / 403 / redirect loop / SSL error:** download must have timeout and retry.
- [x] (covered by AC-6) **File storage path missing or full:** `MeetingMinutesService` must create directories but also handle `OSError`.
- [x] (covered by AC-6) **`record_token_usage` fails inside worker:** should not fail the whole deliverable, but must log and alert.
- [x] (covered by AC-6) **User deletes `MeetingMinutes` while worker is running:** worker should detect and stop or skip write.

### Triage

- **Q1:** No duplicate → **proceed**. `pyannote.audio` diarization is new to the repo; all other patterns are reusable.
- **Q2:** Reuse canonical `run_async_celery_task` + `record_token_usage`. Chosen stack: `faster-whisper` + `pyannote.audio` + existing LLM extractor. `whisperx` rejected due to PyTorch version conflict.
- **Q3:** Edge cases in concurrent/idempotency/language/speaker-count/JSON extraction are now specified in **Edge Cases & Risks**, **Technical Decisions**, and **AC-6**. Add to ATDD test skeleton.
- **Q4:** Failure modes (Celery down, LLM fail after transcription, OOM, audio download, missing document, wallet exhausted, `record_token_usage` failures) are now specified in **Edge Cases & Risks**, **AC-3/AC-4**, and **AC-6**. Add unit/integration tests for each terminal/degraded path.

**Overall:** **Spec is ready for test-first ATDD.** Continue with `bmad-test-first-atdd` or `kn-spec` verification. Update test skeleton to cover all Q3/Q4 rows.

### Grill-Me Re-validation (2026-08-26)

Q1 — Already implemented? **No duplicate logic.** `generate_meeting_minutes`, `MeetingMinutes` model, `pyannote.audio`/diarization code, and `MeetingMinutesService` do not exist in `nowing_backend`. `chat_modes.py:84-93` and `app/config/__init__.py:1897-1905` already contain partial `meeting_minutes` mode wiring; dev should reuse/extend, not recreate.

Q2 — Simpler alternative? **No simpler alternative found.** The canonical Celery + `STTService` + `billable_call` + `TokenUsage` patterns are the right reuse targets. External diarization API is not configured; `pyannote.audio` optional extra is the chosen path.

Q3 — Edge cases the spec may still miss (added):
- Workspace gating: `ChatMode.meeting_minutes` currently has no `workspace_feature_field` (only global `MEETING_MINUTES_ENABLED`). If workspace plan gating is required later, add `Workspace.meeting_minutes_enabled` and update `chat_modes.py`.
- `faster-whisper` `word_timestamps=True` is required for per-word `words` output used in diarization overlap mapping; the spec says "when available" but does not say how to enable it.

Q4 — Failure modes to add to test skeleton:
- `pyannote.audio`/PyTorch dependency resolver conflict during `uv lock --extra meeting-minutes --extra cpu`.
- `HUGGINGFACE_TOKEN` missing/invalid when `DIARIZATION_ENGINE=pyannote` (gated model download).
- `Workspace` or `Document` row missing when worker loads (race with delete).
- Celery worker not running / Redis down after tool returns `processing`.

**Triage:** Clean with notes — proceed to `bmad-nowing-test-first-atdd`.
