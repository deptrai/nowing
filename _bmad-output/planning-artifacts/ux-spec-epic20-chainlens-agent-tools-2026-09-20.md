# UX Specification: ChainLens Agent Tool Suite & User Surfaces (Epic 20 Extension)

**Document ID:** `UX-SPEC-EPIC20-CHAINLENS-2026-09-20`
**Date:** 2026-09-20
**Author:** Sally (UX Designer)
**Scope:** Stories 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 26.9c
**Source of truth for tool contracts:** `chainlens-research/apps/mcp/src/tools/*.ts` (production MCP server)

---

## Part A — Agent Tool Catalog (the deliverable Dev implements)

Every ChainLens capability exposed to a Nowing sub-agent is a *capability tool* built via `build_capability_tools()` (`app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py`). The **tool name + description + parameter contract below is binding** — it is what the LLM sees and must reason over. Descriptions are written so the agent picks the RIGHT tool, not just any tool.

### A.1 Tool Routing Cheat-Sheet (put in system prompt of every ChainLens-enabled sub-agent)

```
CHAINLENS TOOL SELECTION:
- chainlens_search    → raw SERP results, no LLM answer. Use when caller wants
                        "find links about X", "top sources", "list of pages".
                        Fast (2–10s). Output: result list w/ titles+urls+snippets.
- chainlens_ask       → LLM-synthesized answer with citations. 3 depths:
                        fast(10–30s)/deep(30–90s)/research(60–180s). Use for
                        "answer/explain/summarize/compare" questions.
- chainlens_contents  → extract CLEAN TEXT from specific URLs you already have.
                        NOT a search tool — requires explicit urls[].
                        Use when caller pastes a link or names a page.
- chainlens_code_search → code snippets + API docs (GitHub/SO/packages).
                        Use ONLY for programming questions — never for prose.
- chainlens_wide_research → structured matrix comparing N entities (≤50).
                        Use for "compare all X", "market landscape", "competitor grid".
                        SLOW (up to 120s) — set expectation, stream progress.
- chainlens_monitor   → create/trigger recurring monitors (cron + webhook).
                        Use ONLY inside Automation builder context, not ad-hoc chat.
- chainlens_chats     → resume prior research session (chatId) or list history.
                        Use when continuing a multi-turn research thread.
- chainlens_pulse_feed → BROWSE curated news feed (pre-computed, per-topic).
                        Use for "what's new", "latest in AI/tech/finance",
                        "market/competitor news today" — NOT for entity queries
                        (→ entity_search) and NOT for reading a URL (→ contents).
                        Returns items + per-item research `angles` w/ cost hints.
- chainlens_pulse_research → 1-click deep research on ONE chosen pulse angle.
                        Use ONLY after pulse_feed surfaces an angle the user picks —
                        needs {itemId, angleId} from a feed item. Same SSE report
                        contract as chainlens_ask depth=research.
```

### A.2 Per-tool contract (name · when-to-use · params · gotchas)

#### `chainlens_search` — raw search results
- **Use when:** caller wants links/sources, not a written answer. "Find me articles about…", "what sites cover…"
- **Params:** `query` (required), `maxResults` (1–100), `category` (`general|company|people|publication|news|personal_site|financial_report|github`), `searchType` (`auto|keyword|hybrid|neural`), `includeDomains[]`, `excludeDomains[]`, `startPublishedDate`, `endPublishedDate`, `liveCrawl` (`always|fallback|never`), `maxContentLength`.
- **Gotchas:** Returns NO synthesized answer — just result rows. If user wants prose → `chainlens_ask`. `startPublishedDate` must be ≤ `endPublishedDate`; `includeDomains` and `excludeDomains` must not overlap (API rejects).

#### `chainlens_ask` — synthesized Q&A / deep research
- **Use when:** "answer", "explain", "compare X vs Y", "summarize", "deep dive". **Default tool** for open research questions.
- **Params:** `query` (required), `depth` (`fast`=single-pass Q&A · `deep`=multi-step reasoning · `research`=1500+ word report — maps to tiers ask/reason/research), `mode` (`speed|balanced|quality`), `sources[]` (`web|discussions|academic|crawl4ai`), `history` (`[role, content][]` pairs), `systemInstructions`, `chatId` (SEP-2567 session handle for continuation), `outputSchema` (optional JSON schema for structured output), `language` (`vi|en`), `bypassCache`.
- **Gotchas:** `depth=research` can take 60–180s — MUST stream progress to UI. Passing `chatId` from a prior response resumes the same session (SEP-2567). `history` is `[["human","…"],["assistant","…"]]` pairs, NOT objects.

#### `chainlens_contents` — clean page extraction
- **Use when:** user gives explicit URL(s) — "read this page", "what does this doc say", "summarize https://…". **NOT for discovering pages** (use `chainlens_search` to find, then `contents` to read).
- **Params:** `urls[]` (required, 1–50), `query` (optional focus — defaults to joined URLs), `sources[]`, `optimizationMode` (`instant|fast|balanced|auto`), `subpages` (0–10 same-origin subpages), `subpageTarget` (keyword/path filter), `livecrawl` (`always|fallback|never`), `maxAgeHours` (cache freshness 1–2160), `summary` (bool), `highlights` (bool or query-strings).
- **Gotchas:** Public web only — auth-walled/login pages return `unsupported_auth_wall`; route those to Browser Operator (Epic 32). Set `summary:true` + `highlights:["focus","terms"]` for token-efficient reads.

#### `chainlens_code_search` — technical/code context
- **Use when:** programming questions only — "how do I use X API", "error message Y", "example of Z in typescript".
- **Params:** `query` (required, ≤1000 chars), `language` (e.g. `typescript`, `python` — regex `^[a-z0-9+#-]+$`), `maxResults` (1–20, default 8), `mode` (`instant|fast|balanced|auto`, default `fast`).
- **Gotchas:** Returns `source:path` + fenced code blocks + line refs. If it times out → response has `nextAction` hint; retry narrower query. Do NOT use for conceptual/non-code questions (use `chainlens_ask`).

#### `chainlens_wide_research` — N-entity comparison matrix
- **Use when:** "compare all/50 companies", "competitive landscape of X", "matrix of Y across dimensions". Structured per-entity rows with citations.
- **Params:** `query` (required — the comparison question), `numEntities` (1–50, default 50), `sources[]`, `systemInstructions` (comparison focus), `bypassCache`.
- **Gotchas:** Up to 120s — MUST show live progress ("Đã phân tích N/M…") from streamed `entity_result` events. Persist each entity incrementally to checkpoint (AD-108). Entities may return `null` attributes → render "Không tìm thấy dữ liệu", not blank.

#### `chainlens_monitor` — recurring monitors (Automation-builder only)
- **Use when:** ONLY inside Automation trigger config, not chat. Create cron-scheduled monitors that POST results to a Nowing webhook.
- **Params:** `action` (`create|trigger`), `monitorId` (uuid, for trigger), `name`, `query`, `mode` (`fast|balanced|deep|deep-reasoning`), `cron` (e.g. `0 * * * *` or `@daily`), `webhookUrl`, `dedupKeyPolicy` (`content_hash|url_set|semantic_delta`), `outputSchema`.
- **Gotchas:** `webhookUrl` must be HTTPS. `action=trigger` requires `monitorId`. Never expose raw cron in UI — map presets.

#### `chainlens_chats` — research session history/resume
- **Use when:** continuing a prior deep-research thread; user asks "continue that research", "what did we find yesterday".
- **Params:** `chatId` (uuid — omit to LIST chats newest-first: `{id,title,createdAt,lastMessageAt}`; pass to READ full `[role,content]` history for `history` param), `limit`, `offset`.
- **Gotchas:** Owner-scoped — 404 if chatId belongs to another user. Output feeds `chainlens_ask`'s `history`/`chatId` params.

#### `chainlens_pulse_feed` — curated intelligence feed + angles
- **Use when:** browsing news — "what's new in AI", "latest finance news", "show me today's feed", "competitor/industry headlines". Pre-computed feed, NOT a search.
- **Params:** `topic` (`tech|ai|finance|science|security|startup`, default `tech`), `cursor` (ISO date — keyset "older-than" pagination, NOT offset; pass `pagination.nextCursor` for next page), `itemId` (uuid — when set, returns that item's `angles` instead of the feed).
- **Returns:** feed → `{items:[{id,title,summary,url,thumbnailUrl,publishedAt,source,topic,anglesCount}], pagination}`; angles → `[{angleId,label,description,prompt,estimatedCredits,costDollars,model}]`.
- **Gotchas:** GET-only (public throttled), no SSE. `anglesCount` on each item tells you whether angle research is available — surface the angle picker only when >0. Cost hint = `estimatedCredits`; show it BEFORE launching research.

#### `chainlens_pulse_research` — angle deep-research (SSE)
- **Use when:** user picked ONE angle from a pulse feed item and wants the deep dive — "research this angle", "dig into the second take", "expand that angle".
- **Params:** `itemId` (uuid, required), `angleId` (string, required — from the angle picker), `mode` (`research|balanced|deep|speed|auto|fast|instant|quality`, default `research`), `chatId` (optional — resume/attach session).
- **Returns:** SSE stream identical to `chainlens_ask depth=research` — `init` → `text_delta` → `done{usage,chatId}` → final cited report. Reuse the SAME renderer/parser as research.
- **Gotchas:** Requires BOTH ids — if you only have a headline, call `pulse_feed(itemId)` first to fetch its angles then let user pick. 402 → insufficient credits; 404 → item/angle gone. Persist returned `chatId` for SEP-2567 resume.

### A.3 Guardrails the agent MUST apply (system-prompt level)

1. **PII redaction:** any `query`/`urls` leaving Nowing passes `redact_pii()` first (AD-25/49).
2. **Feed vs search disambiguation:** "what's new / latest / headlines / feed" → `pulse_feed`; "news about <entity>" → `entity_search`; "compare N entities" → `wide_research`; "read this link" → `contents`. Never run `pulse_research` without a user-picked `angleId`.
3. **Source picking:** default `sources=["web"]`; only add `academic`/`discussions` when the question is research/community-flavored — wrong source mix wastes cost.
4. **Depth discipline:** prefer `fast`; escalate to `deep`/`research` only when user explicitly wants thoroughness or the task is multi-step.
5. **Cost pre-check:** before `wide_research`, `pulse_research`, or `research` depth, surface estimated cost — for pulse angles use the feed-provided `estimatedCredits` directly.
6. **Degrade gracefully:** ChainLens 5xx/timeout → `degradation-ux` pattern (banner + retry), never raw error in chat.

---

## Part B — User-Facing Surfaces (per story)

### B.1 Story 20.7 — Model picker: ChainLens (Web-Grounded) group

**Where:** `admin/global-model-connections/page.tsx` preset + workspace model picker.

```
┌─────────────────────────────────────────┐
│  Choose a model                         │
│  ─────────────────────────────────────  │
│  ▼ Anthropic                            │
│     claude-sonnet-4-6        (default)  │
│  ▼ ChainLens (Web-Grounded) 🌐          │
│     claude-sonnet-4-6  🔍   ~3–6s       │
│     haiku-4.5          🔍   ~2–4s       │
└─────────────────────────────────────────┘
```

- Globe icon + `Web-Grounded` tag visually separates grounded models.
- Tooltip (vi): *"Mô hình có tìm kiếm web trực tiếp — phản hồi chậm hơn (~3–6s) nhưng luôn cập nhật. Phù hợp khi cần tin tức, giá cả, sự kiện mới nhất."*
- Tooltip (en): *"Web-grounded model — slower first token (~3–6s) but always up to date. Best for news, prices, live events."*

### B.2 Story 20.5 — Contents read in chat

**Surface:** tool-call chip in the chat transcript.

- **Chip label (vi):** `Đang đọc trang web…` → completed: `Đã đọc N trang · X nguồn`
- **Expanded view:** clean markdown rendered, `sourceUrls` as citation chips, `highlights` shown as pull-quote blocks.
- **Edge case:** auth-walled URL → inline notice *"Trang này cần đăng nhập — chuyển sang Trình duyệt (Browser Operator) để mở."* (routes to Epic 32 path, not an error).

### B.3 Story 20.6 — Code search results

**Surface:** code-block rendering (PlateJS) inside chat.

- Each snippet: language badge, `source:path:line` link-out, **copy button**.
- >5 results → show top-3 + *"Xem thêm N kết quả"* expander (keeps chat readable).
- Timeout → show `nextAction` hint verbatim + retry affordance.

### B.4 Story 26.9c — DSH mission live progress

**Surface:** mission-control progress panel.

```
┌──────────────────────────────────────┐
│ Wide Research — Competitor Matrix    │
│ Đã phân tích 12/50 thực thể…  ▓▓▓░░░ │
│ Đang xử lý: "Acme Corp"              │
│ ⏸ Tiếp tục sau · ⟳ Làm mới          │
└──────────────────────────────────────┘
```

- Progress driven by incremental `entity_result` events; resume shows already-done entities immediately (from checkpoint) — never restart from 0.
- Entity with `null` attributes → cell reads `Không tìm thấy dữ liệu` (italic, muted) — not blank.

### B.5 Story 20.8 — Automation trigger `chainlens_monitor`

**Surface:** Automation builder — trigger type dropdown + config form.

- **Trigger name (vi):** *"Theo dõi tin tức web định kỳ"* · **(en):** *"Scheduled web monitor"*
- **Config form:**
  - `query` — free text, placeholder *"ví dụ: tin tức đối thủ FPT AI tuần này"*
  - `schedule` — preset picker: `Hàng ngày (@daily)` / `Hàng tuần (@weekly)` / `Mỗi giờ (@hourly)` / `Tùy chỉnh (cron…)` — NEVER raw cron by default.
  - `dedupKeyPolicy` — radio: `Chỉ tin mới (semantic_delta)` recommended default; `Theo URL mới (url_set)`; `Theo nội dung (content_hash)` — plain-language labels.
- **Run timeline:** each monitor fire → digest card (collapsible citations); zero-delta run → *"Chưa có tin mới kể từ lần kiểm tra trước"* empty state, never an error.

### B.6 Story 20.9 — Async research in chat

- Long research shows phase labels: `Đang tìm nguồn…` → `Đang đọc N trang…` → `Đang tổng hợp…`
- On disconnect/reconnect, resume silently — user sees final report without knowing the worker restarted.
- If the job is still running on return, re-attach to the SSE stream and continue phase labels (no duplicate run).

### B.7 Stories 20.10/20.11 — Pulse intelligence feed + angle picker

**Where:** a "Pulse" tab on the research/news surface (and a feed tool-call chip in chat). Two-step flow: browse → pick an angle → research.

**Feed list (step 1):**

```
┌────────────────────────────────────────────┐
│ Pulse  [tech|ai|finance|science|security|  │
│        startup]  ▾        ⟳ Làm mới        │
├────────────────────────────────────────────┤
│ ● NVIDIA ra chip mới — giá tăng 8%         │
│   reuters.com · 2h trước · 3 góc nhìn ▾    │
│ ┌────────────────────────────────────────┐ │
│ │ ● Apple mở rộng AI sang chuỗi cung ứng │ │
│ │   bloomberg.com · 5h trước · 2 góc nhìn│ │
│ └────────────────────────────────────────┘ │
│            … tải thêm (cursor)             │
└────────────────────────────────────────────┘
```

- Topic filter chips (vi labels: `Công nghệ|AI|Tài chính|Khoa học|Bảo mật|Khởi nghiệp`). Item shows `source`, relative `publishedAt`, and **`N góc nhìn`** badge (= `anglesCount`; hidden when 0).
- Infinite scroll keyed by `pagination.nextCursor` — never offset page numbers.

**Angle picker (step 2, expands under the item):**

```
│  Chọn một góc nhìn để phân tích sâu:       │
│  ▸ Tác động lên chuỗi cung ứng VN   ~0.05$ │
│  ▸ So sánh với đối thủ AMD          ~0.04$ │
│  ▸ Rủi ro địa chính trị             ~0.06$ │
```

- Each angle row shows `label` + `estimatedCredits`/`costDollars` as a **cost badge** (transparency — no surprise charge). Disabled state when angle `prompt` is empty.
- Tap an angle → runs `pulse_research` → streams the report into the panel/chat (same SSE renderer as deep research): `Đang phân tích…` → cited report with source chips.
- **Edge cases:** zero-angle item → no expander; 402 → *"Không đủ credit"* + top-up affordance; feed empty → *"Chưa có tin mới trong chủ đề này."*

**Agent chip in chat** (when the tool runs inside a conversation): `Đang đọc bảng tin…` → `Đã tải {n} tin · {topic}`; on angle research: `Đang phân tích góc nhìn…` → report.

---

## Part C — Copy inventory (i18n keys to add)

All strings below ship in both `vi.json` and `en.json` under namespace `chainlens.*`:

| Key | vi | en |
| :--- | :--- | :--- |
| `chainlens.model_group` | `ChainLens (Web-Grounded)` | `ChainLens (Web-Grounded)` |
| `chainlens.model_tooltip` | `Mô hình có tìm kiếm web trực tiếp — phản hồi chậm hơn nhưng luôn cập nhật.` | `Web-grounded model — slower but always up to date.` |
| `chainlens.reading` | `Đang đọc trang web…` | `Reading page…` |
| `chainlens.pages_read` | `Đã đọc {n} trang` | `Read {n} pages` |
| `chainlens.auth_wall` | `Trang này cần đăng nhập — dùng Trình duyệt để mở.` | `This page needs sign-in — use Browser to open.` |
| `chainlens.show_more` | `Xem thêm {n} kết quả` | `Show {n} more results` |
| `chainlens.monitor_trigger` | `Theo dõi tin tức web định kỳ` | `Scheduled web monitor` |
| `chainlens.monitor_empty` | `Chưa có tin mới kể từ lần kiểm tra trước` | `No new updates since last check` |
| `chainlens.entity_progress` | `Đã phân tích {done}/{total} thực thể…` | `Analyzed {done}/{total} entities…` |
| `chainlens.entity_no_data` | `Không tìm thấy dữ liệu` | `No data found` |
| `chainlens.degraded` | `ChainLens đang tạm gián đoạn — thử lại.` | `ChainLens is temporarily unavailable — retry.` |
| `chainlens.pulse_feed` | `Bảng tin` | `Pulse feed` |
| `chainlens.pulse_reading` | `Đang đọc bảng tin…` | `Reading feed…` |
| `chainlens.pulse_loaded` | `Đã tải {n} tin` | `Loaded {n} items` |
| `chainlens.pulse_angles` | `{n} góc nhìn` | `{n} angles` |
| `chainlens.pulse_pick_angle` | `Chọn một góc nhìn để phân tích sâu:` | `Pick an angle to research:` |
| `chainlens.pulse_researching` | `Đang phân tích góc nhìn…` | `Researching angle…` |
| `chainlens.pulse_empty` | `Chưa có tin mới trong chủ đề này.` | `No new items in this topic.` |
| `chainlens.pulse_no_credits` | `Không đủ credit — nạp thêm để tiếp tục.` | `Not enough credits — top up to continue.` |

---

*Authored by BMad UX Designer (`bmad-agent-ux-designer`).*
