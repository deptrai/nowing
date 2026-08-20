---
story_key: "27-2"
epic: "epic-27"
story: "27.2"
title: "Manus Slides Presentation Studio & Speaker Diarization Meeting Minutes"
status: "ready-for-dev"
---

# Story 27.2: Manus Slides Presentation Studio & Speaker Diarization Meeting Minutes

## Story Overview

As a Nowing user,
I want to generate presentation slides from a prompt and extract action items from meeting recordings with speaker diarization,
So that I can deliver polished decks and structured meeting minutes automatically.

## Reuse From Existing Code

- Remotion video presentations (`video_presentations_routes.py`).
- Export PDF/DOCX/LaTeX/EPUB (`reports_routes.py` — Pandoc + Typst).
- Whisper STT local (`services/stt_service.py` — `faster-whisper` transcription).
- Circleback meeting notes webhook (`circleback_webhook_route.py` → Markdown document).

## New Code

1. `python-pptx` dependency + PPTX export route (16:9 slides, charts, speaker notes).
2. Marp Markdown slide renderer.
3. Speaker diarization (`pyannote.audio` or `whisperx`) added to `stt_service.py`.

## Acceptance Criteria

1. **PPTX Slide Generation**
   - **Given** a presentation prompt,
   - **When** the user requests PPTX export,
   - **Then** a `.pptx` 16:9 file is generated with speaker notes and charts.

2. **Marp Markdown Slides**
   - **Given** a presentation prompt,
   - **When** the user requests Marp output,
   - **Then** a Marp-compatible Markdown slide deck is rendered.

3. **Speaker Diarization for Meeting Minutes**
   - **Given** a meeting recording,
   - **When** the user requests diarization,
   - **Then** the output contains action items grouped by speaker and a meeting minutes document.

4. **Graceful Degradation**
   - **Given** the STT service cannot identify speakers,
   - **When** diarization is requested,
   - **Then** the system returns an empty result without crashing the pipeline.

## Consequences

- New route for PPTX/Marp export.
- `stt_service.py` extended with diarization.
- Optional `pyannote.audio` / `whisperx` dependency.
