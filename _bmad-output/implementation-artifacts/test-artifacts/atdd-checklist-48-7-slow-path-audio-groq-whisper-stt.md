# ATDD Checklist — 48-7 Slow-Path Audio Stream Extraction & OpenRouter Whisper STT Fallback

> **Story Key:** `48-7-slow-path-audio-groq-whisper-stt` (Story 48.7)  
> **Source Spec:** `_bmad-output/implementation-artifacts/stories/48-7-slow-path-audio-groq-whisper-stt.md`  
> **Reference:** `docs/mutation-gate-reference.md` (6 Anti-Pattern Checklist)  
> **Target Test Suites:**  
> - Unit: `apps/api/src/search/media/__tests__/audio-transcription.service.spec.ts`
> - Integration: `apps/api/src/search/media/__tests__/audio-transcription.integration.spec.ts`

---

## AC-1: Provider Key Resolution & User Credit Admission

**Given** a YouTube URL processed in `balanced` or `quality` mode where Story 48-6 detected no subtitle track,  
**When** `AudioTranscriptionService` is invoked,  
**Then** verify a Whisper API key (`WHISPER_API_KEY`, `OPENROUTER_API_KEY`, or `GROQ_API_KEY`) and user credit admission.

### Pattern 1 — Mirror
- [ ] should resolve provider `'openrouter'` when `WHISPER_PROVIDER=openrouter` and `OPENROUTER_API_KEY` is present
- [ ] should resolve provider `'groq'` when `WHISPER_PROVIDER=groq` and `GROQ_API_KEY` is present
- [ ] should resolve provider `'whisper'` when `WHISPER_PROVIDER=whisper` and `WHISPER_API_KEY` is present
- [ ] should NOT invoke `extractAudio` or `callWhisper` when credit admission check fails
- [ ] should NOT execute audio transcription when subtitle fast-path (48-6) successfully returned usable subtitle items

### Pattern 2 — Over-Mocking
- [ ] should handle `BillingService.checkAndIncrementQuota(userId)` throwing `QuotaServiceUnavailableException`
- [ ] should handle `BillingService.checkAndIncrementQuota(userId)` returning `false` (insufficient credits)
- [ ] should handle `ConfigService.get('WHISPER_API_KEY')`, `ConfigService.get('OPENROUTER_API_KEY')`, `ConfigService.get('GROQ_API_KEY')` all returning `undefined`
- [ ] should handle `BillingService` rejecting an anonymous or malformed `userId`

### Pattern 3 — Happy Path Only
- [ ] Boundary: should admit request when user credit balance is exactly equal to the minimum required quota
- [ ] Boundary: should reject request when user credit balance is `0`
- [ ] Null/empty: should handle empty string `userId=''` by defaulting to `'anonymous'` and enforcing public admission rules
- [ ] Null/empty: should handle `subtitleResult=null` and `subtitleResult={ items: [] }` by triggering slow-path
- [ ] Concurrent: should handle concurrent calls with same `userId` without race conditions on credit admission

### Pattern 4 — Arithmetic
- [ ] should deduct exactly `1` quota unit for video admission before starting stream extraction

### Pattern 5 — Error Message
- [ ] should throw `ConfigurationError` with message containing `'WHISPER_API_KEY'` or `'OPENROUTER_API_KEY'` or `'GROQ_API_KEY'` when no valid key is configured
- [ ] should throw `CreditAdmissionError` with message containing `'insufficient credit'` when billing quota is exhausted

### Pattern 6 — SQL / Integration
- [ ] should check real `subscriptions` and `usage` tables in PostgreSQL to enforce quota limits (integration, real DB)

---

## AC-2: Low-Bitrate Audio Stream Extraction & Proxy Routing

**Given** an active video without subtitles,  
**When** `yt-dlp` extracts the audio stream,  
**Then** download only the lowest-bitrate audio stream (`m4a` / `opus` $\le 128\text{kbps}$) routed through the Residential Proxy Pool (`Proxy-Seller` / `HTTP_PROXY`).

### Pattern 1 — Mirror
- [ ] should pass format selector `worstaudio[ext=m4a][abr<=128]/worstaudio[ext=opus][abr<=128]/worstaudio[abr<=128]` to `yt-dlp`
- [ ] should pass `--audio-quality 128K` argument to `yt-dlp`
- [ ] should return extracted audio as an in-memory `Buffer` (not a temporary file path on disk)
- [ ] should NOT request video streams (`bestvideo` or video container formats)
- [ ] should pass `--proxy` with the URL from `ProxyPoolProvider` or `process.env.HTTP_PROXY`

### Pattern 2 — Over-Mocking
- [ ] should handle `yt-dlp` process exiting with non-zero code (e.g. video unavailable, geo-blocked, bot-detection)
- [ ] should handle `yt-dlp` process hanging and timing out at `audioTimeoutMs`
- [ ] should handle `ProxyPoolProvider.getProxy()` returning `null` or throwing `ProxyUnavailableException`
- [ ] should handle residential proxy returning HTTP 407 (Proxy Authentication Required) or 502 (Bad Gateway)

### Pattern 3 — Happy Path Only
- [ ] Boundary: should accept audio stream with bitrate exactly `128kbps` (`128000` bps)
- [ ] Boundary: should accept audio stream with bitrate `64kbps` (`64000` bps)
- [ ] Boundary: should enforce hard stream cap at exactly `25MB` (`26,214,400` bytes)
- [ ] Null/empty: should handle `yt-dlp` returning zero-byte empty Buffer (`0` bytes) by throwing extraction error
- [ ] Concurrent: should allow up to 4 parallel extraction tasks without exhausting OS process limits

### Pattern 4 — Arithmetic
- [ ] should compute `128kbps` as exactly `128000` bps (not `128` bps)
- [ ] should compute 25MB buffer size threshold as exactly `26214400` bytes ($25 \times 1024 \times 1024$)

### Pattern 5 — Error Message
- [ ] should throw `StreamCapExceededError` with message containing `'25MB'` when downloaded audio chunk exceeds 26,214,400 bytes
- [ ] should throw `AudioExtractionError` with message containing `'yt-dlp'` and videoId when download process fails

### Pattern 6 — SQL / Integration
- [ ] should execute real `yt-dlp` CLI command against a public test YouTube video (`jNQXAC9IVRw`) and return valid audio Buffer $\le 128\text{kbps}$ (integration, real network + CLI)

---

## AC-3: Chunked Extraction & Download Sections for Long Videos

**Given** a long video where a single request would exceed the provider's practical limit,  
**When** `extractAudio` runs,  
**Then** it splits extraction into `YOUTUBE_AUDIO_CHUNK_SECONDS` chunks (default 600s) and calls `yt-dlp` per chunk with `--download-sections '*HH:MM:SS-HH:MM:SS'`.

### Pattern 1 — Mirror
- [ ] should split video into multiple chunks of size `YOUTUBE_AUDIO_CHUNK_SECONDS` (600s) when `durationSeconds > 600`
- [ ] should pass `--download-sections "*00:00:00-00:10:00"` for chunk 1 (0 to 600s)
- [ ] should pass `--download-sections "*00:10:00-00:20:00"` for chunk 2 (600 to 1200s)
- [ ] should NOT pass `--download-sections` when `durationSeconds <= chunkSeconds` and no cap is set
- [ ] should return `Array<{ buffer: Buffer; offsetSeconds: number }>` where `offsetSeconds` matches chunk start time

### Pattern 2 — Over-Mocking
- [ ] should handle `durationSeconds` being `undefined` or `null` by extracting a single chunk with default cap
- [ ] should handle failure of chunk 2 while chunk 1 succeeded by bubbling error to trigger graceful fallback
- [ ] should handle non-standard time format from video metadata

### Pattern 3 — Happy Path Only
- [ ] Boundary: should create exactly 1 chunk when `durationSeconds = 600`
- [ ] Boundary: should create exactly 2 chunks when `durationSeconds = 601`
- [ ] Boundary: should cap chunks to `YOUTUBE_AUDIO_MAX_SECONDS` when video is longer than the max configured seconds
- [ ] Null/empty: should handle `chunkSeconds <= 0` by falling back safely to default 600s
- [ ] Concurrent: should execute multiple chunk extractions in parallel bounded by max concurrency 4

### Pattern 4 — Arithmetic
- [ ] should compute chunk start and end seconds: Chunk 0 = `[0, 600]`, Chunk 1 = `[600, 1200]`, Chunk 2 = `[1200, 1800]`
- [ ] should format seconds to HH:MM:SS timestamps exactly: `0` -> `'00:00:00'`, `600` -> `'00:10:00'`, `3665` -> `'01:01:05'`
- [ ] should compute effective duration as `Math.min(durationSeconds, maxAudioSeconds)`

### Pattern 5 — Error Message
- [ ] should throw `ConfigurationError` with message containing `'chunkSeconds'` if invalid negative configuration passed
- [ ] should throw `AudioExtractionError` with message containing section range `'*00:10:00-00:20:00'` when a specific section fails

### Pattern 6 — SQL / Integration
- [ ] should verify section extraction with `yt-dlp --download-sections` against real video producing expected audio length (integration)

---

## AC-4: Speech-to-Text Transcription via Configured Whisper Model

**Given** a downloaded audio chunk,  
**When** calling the configured Whisper endpoint (`qwen/qwen3-asr-0.6b` for OpenRouter, `whisper-large-v3-turbo` for Groq, override bằng `WHISPER_MODEL`),  
**Then** complete within an adaptive SLA (1.5s for short audio, up to 60s for long chunks) with timestamped `segments`.

### Pattern 1 — Mirror
- [ ] should call OpenRouter `/v1/audio/transcriptions` with model `qwen/qwen3-asr-0.6b` by default when provider is `openrouter`
- [ ] should call Groq `/v1/audio/transcriptions` with model `whisper-large-v3-turbo` when provider is `groq`
- [ ] should call OpenAI `/v1/audio/transcriptions` with model `whisper-1` when provider is `whisper`
- [ ] should override model name when `WHISPER_MODEL` is explicitly provided
- [ ] should request `response_format: 'verbose_json'` with timestamp granularities `['segment']`

### Pattern 2 — Over-Mocking
- [ ] should handle STT provider returning HTTP 429 Rate Limit Exceeded
- [ ] should handle STT provider returning HTTP 500 Internal Server Error
- [ ] should handle STT provider returning invalid/malformed JSON or empty string
- [ ] should handle STT provider response without `segments` array (plain text fallback)
- [ ] should handle network socket reset / timeout during STT upload

### Pattern 3 — Happy Path Only
- [ ] Boundary: should timeout call if execution exceeds adaptive timeout (`getWhisperTimeoutMs`)
- [ ] Boundary: should handle single segment transcript
- [ ] Boundary: should handle multi-segment transcript with 100+ segments
- [ ] Null/empty: should handle empty segments array `segments: []`
- [ ] Concurrent: should execute multiple STT chunk requests concurrently without request body corruption

### Pattern 4 — Arithmetic
- [ ] should compute adaptive timeout SLA as `Math.min(60000, Math.max(1500, durationSeconds * 120))`
- [ ] should compute fallback timeout from buffer byte length when duration is not provided: `(buffer.length / (16 * 1024)) * 120`

### Pattern 5 — Error Message
- [ ] should throw `WhisperTimeoutError` with message containing `'SLA'` or timeout duration when STT request times out
- [ ] should throw `WhisperAPIError` with message containing status code and error details when upstream STT API fails

### Pattern 6 — SQL / Integration
- [ ] should call live OpenRouter/Groq transcription API with real test audio buffer and receive valid JSON response containing `text` and `segments` (integration, real API)

---

## AC-5: Multi-Chunk Transcript Merging & Chunk[] Output Shaping

**Given** multiple chunk transcripts,  
**When** `AudioTranscriptionService` receives them,  
**Then** it merges `segments` and `text` with correct `offsetSeconds`, producing a single continuous transcript and `Chunk[]`.

### Pattern 1 — Mirror
- [ ] should return output conforming to `Chunk[]` schema with `source: 'youtube_audio'`
- [ ] should include deep links with timestamp format `[MM:SS]` (e.g. `[05:30]`) in chunk titles and metadata
- [ ] should write combined transcript to Redis with key `transcript:audio:{videoId}:{durationSeconds}:{maxAudioSeconds}:{model}`
- [ ] should set Redis cache TTL to 7 days (`604800` seconds)
- [ ] should NOT lose intermediate segment timestamps during merging

### Pattern 2 — Over-Mocking
- [ ] should handle Redis `set` throwing `RedisConnectionException` without breaking the search response (non-blocking cache write)
- [ ] should handle empty text in one of the middle chunks
- [ ] should handle overlapping segment timestamps between adjacent chunks

### Pattern 3 — Happy Path Only
- [ ] Boundary: should handle merging exactly 1 chunk (offset = 0)
- [ ] Boundary: should handle merging 10+ chunks for a long video
- [ ] Null/empty: should handle chunk with empty segments by preserving chunk text
- [ ] Concurrent: should ensure atomic write to Redis when multiple concurrent queries request the same video

### Pattern 4 — Arithmetic
- [ ] should adjust chunk 2 segment timestamps by adding `offsetSeconds`: `segment.start = rawStart + 600`, `segment.end = rawEnd + 600`
- [ ] should compute combined transcript total duration as sum of all chunk durations
- [ ] should split final merged text into `Chunk[]` with chunk size $\le 1000$ tokens

### Pattern 5 — Error Message
- [ ] should log warning with message containing `'Redis cache write failed'` if caching throws, while returning valid `Chunk[]`

### Pattern 6 — SQL / Integration
- [ ] should write transcript to real Redis instance and verify retrieval with identical key and fields (integration, real Redis)

---

## AC-6: Model-Specific Cost Calculation & Enrichment Accounting

**Given** STT completion,  
**When** calculating request costs,  
**Then** calculate audio duration cost at the model-specific per-hour rate (`qwen/qwen3-asr-0.6b` ≈ $0.012/hr, Groq `whisper-large-v3-turbo` ≈ $0.04/hr) and record into `costDollars` breakdown under `costs.enrichment`.

### Pattern 1 — Mirror
- [ ] should record cost under `costBreakdown.enrichment` (not `costs.search`, `costs.contents`, or `costs.model`)
- [ ] should record model-specific rate: `$0.012/hr` for `qwen/qwen3-asr-0.6b` and `$0.04/hr` for `whisper-large-v3-turbo`
- [ ] should return `costDollars` as a float rounded to 6 decimal places
- [ ] should pass recorded cost to `usageSink` and `usageTracker.recordCost`

### Pattern 2 — Over-Mocking
- [ ] should handle `usageTracker.recordCost` throwing without failing the user response
- [ ] should handle unknown model key by falling back to standard rate `$0.04/hr`
- [ ] should handle `durationSeconds = 0` by returning cost `0.000000`

### Pattern 3 — Happy Path Only
- [ ] Boundary: should compute cost for `durationSeconds = 3600` (1 hour)
- [ ] Boundary: should compute cost for `durationSeconds = 600` (10 minutes)
- [ ] Boundary: should compute cost for `durationSeconds = 1` (1 second)
- [ ] Null/empty: should reject negative `durationSeconds < 0`
- [ ] Concurrent: should accumulate costs from parallel audio extractions into the single parent request's usage

### Pattern 4 — Arithmetic
- [ ] should compute cost for `qwen/qwen3-asr-0.6b` ($0.012/hr):
  - `3600s` $\rightarrow$ exactly `0.012000`
  - `600s` $\rightarrow$ exactly `0.002000`
  - `300s` $\rightarrow$ exactly `0.001000`
  - `60s` $\rightarrow$ exactly `0.000200`
- [ ] should compute cost for `whisper-large-v3-turbo` / `whisper-1` ($0.04/hr):
  - `3600s` $\rightarrow$ exactly `0.040000`
  - `600s` $\rightarrow$ exactly `0.006667`
  - `300s` $\rightarrow$ exactly `0.003333`
- [ ] should round result to exactly 6 decimal places: `Math.round(rawCost * 1e6) / 1e6`

### Pattern 5 — Error Message
- [ ] should throw `CostCalculationError` with message containing `'durationSeconds'` when duration is negative or `NaN`

### Pattern 6 — SQL / Integration
- [ ] should persist enrichment cost in PostgreSQL `usage_ledger` table with correct `cost_dollars` value (integration, real DB)

---

## AC-7: Multi-Video AudioBudget & Concurrency Cap

**Given** a search/extract request that includes multiple YouTube URLs without subtitles,  
**When** `deepExtract` processes them in `balanced` or `quality` mode,  
**Then** the total audio seconds transcribed across all videos does not exceed `YOUTUBE_AUDIO_TOTAL_MAX_SECONDS` (default 300s for `balanced`/`quality`, 60s for `speed`), preserving unused seconds for remaining videos.

### Pattern 1 — Mirror
- [ ] should initialize `AudioBudget` with `YOUTUBE_AUDIO_TOTAL_MAX_SECONDS` (default 300s in balanced/quality, 60s in speed)
- [ ] should pass `AudioBudget` across all video extract tasks within a single search request
- [ ] should acquire budget before calling `transcribe()` and refund unused seconds in `finally` block
- [ ] should NOT exceed total allocated audio seconds across all processed videos in the request

### Pattern 2 — Over-Mocking
- [ ] should handle `AudioBudget.acquire()` returning `0` (budget exhausted) by skipping STT for subsequent videos
- [ ] should handle exception in `transcribe()` and ensure full unused duration is refunded to `AudioBudget`
- [ ] should handle supplemental research passes sharing the original `AudioBudget` instance

### Pattern 3 — Happy Path Only
- [ ] Boundary: should allow video 1 to consume 180s and video 2 to consume remaining 120s of a 300s budget
- [ ] Boundary: should truncate video 2 duration to 100s if only 100s remaining in budget
- [ ] Boundary: should skip video 3 entirely when budget remaining is `0s`
- [ ] Null/empty: should reject `NaN` or `Infinity` in `AudioBudget` methods
- [ ] Concurrent: should support thread-safe atomic `acquire()` and `refund()` under concurrent Promise execution

### Pattern 4 — Arithmetic
- [ ] should compute remaining budget accurately: `remaining = totalCap - acquired + refunded`
- [ ] should refund exact delta: `refundSeconds = allowedDuration - actualTranscribedDuration`

### Pattern 5 — Error Message
- [ ] should throw `Error` with message containing `'Invalid budget'` if initialized with negative or NaN budget

### Pattern 6 — SQL / Integration
- [ ] should run multi-video extract in `SearchService` and verify total transcribed duration does not exceed budget (integration)

---

## AC-8: Fast Fallback to SearXNG Snippet in Speed Mode or When Disabled

**Given** `speed` mode or `YOUTUBE_AUDIO_STT_ENABLED=false`,  
**When** subtitle extraction fails,  
**Then** skip audio STT entirely and fall back to the SearXNG snippet to strictly uphold the <10s SLA.

### Pattern 1 — Mirror
- [ ] should return `canTranscribe() === false` when `mode === 'speed'`
- [ ] should return `canTranscribe() === false` when `YOUTUBE_AUDIO_STT_ENABLED=false` or `'false'`
- [ ] should call `fallbackToSearxng(youtubeUrl)` with query `site:youtube.com <videoId>`
- [ ] should return `Chunk[]` with `source: 'searxng'` for fallback results
- [ ] should complete within $<10\text{s}$ total request SLA

### Pattern 2 — Over-Mocking
- [ ] should handle SearXNG search returning empty results `[]` by returning hardcoded local video metadata snippet
- [ ] should handle SearXNG search throwing `SearchError` / HTTP 503 by logging warning and returning hardcoded fallback
- [ ] should handle SearXNG timeout ($>2\text{s}$) by aborting search and returning fallback snippet

### Pattern 3 — Happy Path Only
- [ ] Boundary: should handle mode `speed` (skip STT immediately)
- [ ] Boundary: should handle mode `balanced` with `YOUTUBE_AUDIO_STT_ENABLED=false` (skip STT)
- [ ] Boundary: should handle mode `quality` with `YOUTUBE_AUDIO_STT_ENABLED=true` (execute STT)
- [ ] Null/empty: should handle empty string `YOUTUBE_AUDIO_STT_ENABLED=''` as enabled default
- [ ] Concurrent: should handle multiple concurrent fallback requests without blocking search pipeline

### Pattern 4 — Arithmetic
- [ ] should enforce SearXNG fallback timeout budget $\le 2000\text{ms}$ to ensure total search time remains $<10\text{s}$

### Pattern 5 — Error Message
- [ ] should NOT throw error to end-user when STT is skipped or fails; should log info/warning and return valid fallback `Chunk[]`

### Pattern 6 — SQL / Integration
- [ ] should call live SearXNG service with `site:youtube.com <videoId>` and receive snippet content (integration, real search)

---

## Downstream Handoff

1. **Unit Test Bodies (Mock DB):** Feed to `bmad-testarch-atdd` for red-phase unit tests.
2. **Integration Test Bodies (Real DB/CLI/Network):** Feed Pattern 6 items to `bmad-integration-test`.
3. **Mutation Testing Gate:** Run `bmad-mutation-gate` (Stryker) on `apps/api/src/search/media/audio-transcription.service.ts` and verify mutation score $\ge 80\%$.
