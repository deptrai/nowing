---
baseline_commit: 5c9367ff740eb0badb3215b25f03e0d330f2eef9
baseline_branch: develop
story_key: 9-1b-research-contract-regression-guard
status: done
---

# Story 9.1b: Research Contract Regression Guard

**Status:** done
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng
**Priority:** P0 — không chặn public repo (public-repo gate đã qua ở 9.1a)
**Requirements:** FR-24; AD-15; OQ-7(1)+(4)
**Baseline:** `5c9367ff740eb0badb3215b25f03e0d330f2eef9` on `develop`
**Dependencies:** Story `9-1a` done; parser/executor của `chainlens.research` đã có; ChainLens `42-2` fixture `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`; PRD §4.9, AD-15, SCP §3 cần sửa.

## Story

Với tư cách là người duy trì Nowing,
tôi muốn hợp đồng với deep-research engine được khoá bằng test trong CI,
để nếu engine đổi format thì tôi biết trước khi production vỡ, thay vì phát hiện qua báo lỗi của user.

## Current Reality

Tại baseline `5c9367ff740eb0badb3215b25f03e0d330f2eef9`:

- `nowing_backend/app/capabilities/chainlens/research/executor.py` đã parse `partial`, `insufficientEvidence`, `heartbeat`, `block`, `updateBlock`, `done`, `error` (sau 9.1a), nhưng vẫn giữ nhánh `event:` và nhánh `data: [DONE]` dự phòng ở `_SSEParser.feed_line` (`executor.py:143-156`, `151-152`). Theo OQ-7 (2026-07-25), NestJS `@Sse()` của ChainLens chỉ phát **data-only frame**, `type` nằm trong JSON, terminal thật là `{"type":"done"}` — nhánh `event:` không bao giờ chạy.
- `_call_chainlens` build body với `query`, `optimizationMode`, `tier`, `sources`, `history`, `stream`, `systemInstructions`, `chatId` (`executor.py:379-390`). `ResearchInput.query` đã có `min_length=1, max_length=500` (`schemas.py:15,63-65`) nên Pydantic là cổng chặn duy nhất; executor không cần clamp thêm.
- `_parse_sources` giữ thứ tự source như engine gửi (`executor.py:69-93`), nhưng test hiện tại chỉ kiểm tra 1 source (`test_executor.py:24-63`).
- `_SSEParser` xử lý `updateBlock` bằng cách apply patch RFC6902-style chỉ với `op` `replace`/`add` trên `/data` (`executor.py:192-202`), nhưng chưa có contract test khoá toàn bộ các trường hợp này.
- Tài liệu PRD §4.9, AD-15, SCP §3 vẫn mô tả SSE theo `event:`/`data:` và `data: [DONE]` — sai so với wire thật.
- ChainLens `42-2` đã có `nowing-sse-parser.ts` — bản mirror parser dùng `rfc6902 applyPatch`, nên Nowing nên tham chiếu fixture đó thay vì viết fixture thứ hai.

## Resolved Decisions

### D1 — Wire format thật là data-only frame

- NestJS `@Sse()` của ChainLens phát `data: <json>\n\n`; không có dòng `event:`.
- `type` là trường bên trong JSON payload (`{"type":"block"}`, `{"type":"updateBlock"}`, `{"type":"done"}`, `{"type":"error"}`, ...).
- Terminal marker thật là `{"type":"done", "chatId": ..., "webUrl": ...}`, không phải `data: [DONE]`.
- `_SSEParser` trong `nowing_backend/app/capabilities/chainlens/research/executor.py` đã gỡ bỏ hoàn toàn `pending_event_type`, nhánh xử lý `event:` và nhánh `data: [DONE]` khỏi `__slots__`, `__init__` và `feed_line`. Test cũ `test_parse_sse_raises_on_error_event` được đổi tên thành `test_parse_sse_raises_on_error_data_frame` và dùng `_sse_line({"type":"error","data":"upstream boom"}).

### D2 — Contract test phải fail khi engine đổi format

- Test regression khoá cả **request shape** (`POST /api/v1/search`, headers, body) và **SSE parse** (block create/replace, RFC6902 patch, terminal, error, metadata, source order).
- Test phải được chạy trong CI; nếu fixture/response của ChainLens đổi thì test đỏ trước khi lên prod.

### D3 — Pydantic schema là cổng chặn duy nhất cho `query`

- `ResearchInput.query` đã có `min_length=1, max_length=500`, `MAX_QUERY_LENGTH = 500`, và `field_validator("query", mode="before")` `_strip_query` trong `nowing_backend/app/capabilities/chainlens/research/schemas.py`.
- Validator strip đảm bảo query toàn khoảng trắng bị coi là rỗng và bị từ chối trước khi `_call_chainlens` chạy.
- Executor **không** thêm clamp thủ công; Pydantic là cổng chặn duy nhất.
- Unit test `test_research_input_rejects_blank_query` trong `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py` khóa hành vi này.

### D4 — `sources[]` giữ nguyên thứ tự trích dẫn

- `_parse_sources` và `ResearchOutput.sources` phải preserve order từ engine để map về citation UI.

### D5 — RFC6902 patch thủ công trên `/data` là đủ cho hiện tại

- `_SSEParser.updateBlock` giữ logic thủ công chỉ chấp nhận `op` trong `{"replace", "add"}` và `path == "/data"`.
- Phải có contract test dựa trên fixture ChainLens 42-2 để khoá các trường hợp này.
- Nếu ChainLens sau này phát thêm op/path khác (`test`, `remove`, `move`), chuyển sang thư viện `rfc6902` hoặc `jsonpatch` — không mở rộng logic thủ công.

### D6 — Đồng bộ fixture với ChainLens 42-2 bằng local copy + drift test

- Đã tạo `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` là bản sao của fixture ChainLens.
- Đã tạo `nowing_backend/tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` với golden fixture validation và drift test tùy chọn so sánh với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` tại build time.
- Drift test đỏ nếu local fixture lệch so với ChainLens 42-2.

### D7 — `tier` và `stream` là một phần của request contract

- `_call_chainlens` đã gửi `tier: "research"` (`executor.py:382`) và `stream: True` (`executor.py:385`) từ 9.1a.
- Hai trường này là một phần hợp lệ của body; giữ nguyên trong code.
- Cập nhật PRD §4.9, AD-15 để liệt kê đầy đủ request shape.
- Contract test phải assert headers + body chính xác, bao gồm `tier` và `stream`.

### D8 — Sửa tài liệu Nowing cho đúng contract

- PRD §4.9 FR-24, AD-15 phải xoá/giải thích sai lệch `event:`/`data: [DONE]`.
- Ghi rõ: data-only frames, `type` trong JSON, terminal `{"type":"done"}`.

### D9 — Docstring `_parse_sse` phải phản ánh data-only frame

- Đã cập nhật docstring `nowing_backend/app/capabilities/chainlens/research/executor.py:_parse_sse` (và `_SSEParser`) thành: chỉ nhận data-only frames, không có dòng `event:`, terminal thật là `{"type":"done"}`.
- Không còn nhắc tới `event: error` hay `data: [DONE]`.

## Acceptance Criteria

1. **Contract regression test khoá request shape** (FR-24, D2, D7)
   - **Given** `POST {CHAINLENS_API_URL}/api/v1/search` với header `Authorization: Bearer <CHAINLENS_API_KEY>`, `Content-Type: application/json`, `Accept: text/event-stream`,
   - **When** CI chạy,
   - **Then** có test assert body chính xác `{query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId?}` (`executor.py:379-390`) — bao gồm `tier` và `stream`,
   - **And** test fail nếu request shape thay đổi.

2. **Contract regression test khoá SSE parse** (FR-24, D1, D2, D5)
   - **Given** SSE data-only frames từ ChainLens: `{"type":"block", "block":{...}}`, `{"type":"updateBlock", "blockId":"...", "patch":[RFC6902 ops]}`, `{"type":"done", "chatId":..., "webUrl":...}`, `{"type":"error", ...}`,
   - **When** `_parse_sse` chạy,
   - **Then** có contract test xác nhận: block create/replace, RFC6902 patch trên `/data` (chỉ `replace`/`add`), terminal `{"type":"done"}` kèm `chatId`/`webUrl`, `error` data-only được parse đúng,
   - **And** test fail nếu engine đổi format.

3. **Pydantic schema là cổng duy nhất cho query** (FR-24, D3)
   - **Given** `ResearchInput.query` có `min_length=1, max_length=500` và `field_validator("query", mode="before")` `_strip_query` trong `schemas.py`,
   - **When** API/MCP nhận input `query > 500`, `query` rỗng, hoặc `query` toàn khoảng trắng,
   - **Then** Pydantic từ chối trước khi `_call_chainlens` chạy,
   - **And** executor không thêm clamp thủ công; query rỗng/toàn khoảng trắng không bao giờ vào engine,
   - **And** test `test_research_input_rejects_blank_query` trong `test_executor.py` khóa hành vi này.

4. **Source order được bảo toàn** (FR-24, D4)
   - **Given** một câu trả lời có nhiều source,
   - **When** parse SSE,
   - **Then** `ResearchOutput.sources[]` giữ nguyên thứ tự trích dẫn từ engine để map đúng về citation UI.

5. **Sửa tài liệu Nowing, docstring `_parse_sse`, và gỡ nhánh `event:` không chạy** (OQ-7, D1, D8, D9)
   - **Given** PRD §4.9 FR-24, `AD-15` đang ghi sai contract (`event:`/`data: [DONE]`) và docstring `_parse_sse` vẫn mô tả `event:`/`data: [DONE]`,
   - **When** code thay đổi,
   - **Then** `_SSEParser` gỡ bỏ `pending_event_type`, nhánh xử lý `event:` và nhánh `data: [DONE]` khỏi `__slots__`, `__init__` và `feed_line` trong `executor.py`,
   - **And** cập nhật docstring `_parse_sse` phản ánh data-only frame, terminal `{"type":"done"}`,
   - **And** test cũ `test_parse_sse_raises_on_error_event` được đổi tên thành `test_parse_sse_raises_on_error_data_frame` và dùng `_sse_line({"type":"error","data":"upstream boom"})`,
   - **And** PRD §4.9 và AD-15 cập nhật request/response contract đúng wire thật.

6. **Đồng bộ fixture với ChainLens 42-2 bằng local copy + drift test** (OQ-7, D6)
   - **Given** ChainLens `42-2` có `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`,
   - **When** viết contract test phía Nowing,
   - **Then** copy fixture đó vào `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` (không tự viết fixture thứ hai),
   - **And** thêm drift test so sánh local fixture với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` tại build time; test đỏ nếu lệch,
   - **And** CI chạy contract test với command `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`.

## Tasks / Subtasks

- [x] **T1 — Viết contract regression test cho request shape** (AC-1)
  - [x] Xác định baseline body gửi từ `_call_chainlens` (`executor.py:379-390`)
  - [x] Test assert body chính xác `{query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId?}` — giữ nguyên `tier`/`stream` đã có từ 9.1a.
  - [x] Test headers gồm `Authorization: Bearer ...`, `Content-Type: application/json`, `Accept: text/event-stream`.
  - [x] Test fail khi body shape thay đổi.

- [x] **T2 — Viết contract regression test cho SSE parse** (AC-2)
  - [x] Dùng data-only fixtures: `block`, `updateBlock` (RFC6902 patch `replace`/`add` trên `/data`), `done`, `error`.
  - [x] Kiểm tra `chatId`/`webUrl` từ `done` được parse.
  - [x] Kiểm tra `updateBlock` thay đổi `block.data` đúng.
  - [x] Kiểm tra `error` data-only raise `ChainLensError`.
  - [x] Kiểm tra unknown `type` được bỏ qua mà không raise.
  - [x] Test fail khi engine đổi format.

- [x] **T3 — Pydantic gate cho query, không clamp trong executor** (AC-3)
  - [x] Thêm `field_validator("query", mode="before")` `_strip_query` trong `schemas.py` để strip khoảng trắng trước khi `min_length=1` kiểm tra.
  - [x] Xác nhận `ResearchInput.query` có `min_length=1, max_length=500`.
  - [x] Executor **không** thêm clamp thủ công; Pydantic từ chối `query > 500`, `query` rỗng và `query` toàn khoảng trắng.
  - [x] Thêm `test_research_input_rejects_blank_query` trong `test_executor.py`.

- [x] **T4 — Kiểm tra source order preservation** (AC-4)
  - [x] Thêm test nhiều source (≥ 3) vào `_parse_sse`/`_parse_sources`.
  - [x] Assert `ResearchOutput.sources[i]` khớp thứ tự engine gửi.

- [x] **T5 — Sửa tài liệu, docstring, và gỡ nhánh `event:`/`[DONE]`** (AC-5)
  - [x] Cập nhật PRD §4.9 FR-24 và AD-15: request shape có `tier`/`stream`, response data-only frame, terminal `{"type":"done"}`.
  - [x] Cập nhật docstring `_parse_sse` thành data-only frame, terminal `{"type":"done"}`.
  - [x] Trong `executor.py`, gỡ bỏ `pending_event_type`, nhánh `event:` và `data: [DONE]` khỏi `_SSEParser.__slots__`, `__init__` và `feed_line`.
  - [x] Đổi tên test `test_parse_sse_raises_on_error_event` thành `test_parse_sse_raises_on_error_data_frame` và dùng `_sse_line({"type":"error","data":"upstream boom"}).

- [x] **T6 — Đồng bộ fixture ChainLens 42-2** (AC-6)
  - [x] Tạo `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` từ nội dung `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.
  - [x] Tạo `tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` với golden fixture validation và drift test tùy chọn so sánh với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.
  - [x] Dùng local fixture cho contract test SSE; không viết fixture thứ hai.

## Dev Notes (Ngữ cảnh phát triển)

### Architecture Compliance

- **AD-15 — ChainLens là external deep-research dependency, không phải scraper.** `app/capabilities/chainlens/` giữ nguyên vị trí, governance là external service. Contract `POST /api/v1/search` phải được regression-guard.
- **FR-24 — Deep Open-Web Research via ChainLens Engine.** Section PRD §4.9 (lines 565-659) cần cập nhật cho đúng wire format.
- **OQ-7 — Nowing trả lời ChainLens (2026-07-25).** Q1 xác nhận `/api/v1/search` là đủ; Q4 rút lại vì parser Nowing bỏ event; fixture `nowing-sse-parser.ts` được ghi nhận ở `oq7-answers-to-chainlens-2026-07-25.md:124-127`.

### Technical Requirements

- **Request contract (`_call_chainlens`, `executor.py:379-390`):**
  - Body: `{ "query": str, "optimizationMode": str, "tier": "research", "sources": list[str], "history": list[list[str]], "stream": True, "systemInstructions": str?, "chatId": str? }`.
  - Header: `Authorization: Bearer {config.CHAINLENS_API_KEY}`, `Content-Type: application/json`, `Accept: text/event-stream`.
  - `tier`/`stream` là một phần của contract; giữ nguyên trong code.
  - `query` được kiểm soát bởi Pydantic `ResearchInput.query` (`min_length=1, max_length=500`); executor không clamp thêm.

- **SSE parse contract (`_SSEParser`, `executor.py:96-317`):**
  - `feed_line` đọc `data: <json>`; bỏ qua dòng trống; **không** xử lý `event:` (D1).
  - `block` (`event_type == "block"`, `executor.py:185-190`): tạo/replace block theo `id`, lưu `type` + `data`.
  - `updateBlock` (`executor.py:192-202`): apply patch RFC6902 thủ công, chỉ `op` trong `{"replace", "add"}` và `path == "/data"` (D5).
  - `done` (`executor.py:179-183`): set `saw_done`, lưu `chatId`/`chat_id`, `webUrl`; terminal thật là `{"type":"done"}`.
  - `error` (`executor.py:170-177`): set `error_msg` từ `data` hoặc JSON dump; `finalize` raise `ChainLensError`.
  - `partial`/`insufficientEvidence`/`heartbeat` đã xử lý ở 9.1a; story này không đổi logic nhưng cần có trong contract test.

- **Source order (`_parse_sources`, `executor.py:69-93`):**
  - Duyệt `raw_sources` theo thứ tự list.
  - Bỏ source không có `url` hợp lệ.
  - Trả về `list[Source]` theo đúng thứ tự.

- **Schema (`schemas.py`):**
  - `MAX_QUERY_LENGTH = 500` line 15.
  - `ResearchInput.query` line 63-65: `min_length=1`, `max_length=MAX_QUERY_LENGTH`.
  - `ResearchOutput.sources` line 107-110: "Grounding sources, in the order they were cited."

### Library & Framework Requirements

- `httpx` — giữ nguyên cho async HTTP.
- `rfc6902`/`jsonpatch` — hiện không thêm dependency mới. `_SSEParser.updateBlock` giữ thủ công `replace`/`add` trên `/data`; nếu fixture ChainLens xuất hiện thêm op/path khác, chuyển sang `rfc6902` hoặc `jsonpatch`.
- `pytest` / `pytest-asyncio` — mock `httpx.AsyncClient`, fixture SSE.
- Không thêm dependency mới nếu không cần thiết.

### File Structure / Project Structure Notes

- `nowing_backend/app/capabilities/chainlens/research/executor.py` — **UPDATE/TEST**: `_SSEParser.feed_line` gỡ/mark `event:`/`[DONE]`; cập nhật docstring `_parse_sse`; **KHÔNG** thêm clamp query trong `_call_chainlens`.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py` — **READ-ONLY trừ khi cần**: `MAX_QUERY_LENGTH`, `ResearchInput`, `ResearchOutput`.
- `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py` — **ADD**: contract regression tests, query Pydantic validation, source order, fixture drift.
- `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` — **NEW**: bản sao fixture ChainLens `nowing-sse-parser.ts`.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — **UPDATE** §4.9 FR-24.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — **UPDATE** AD-15 nếu còn mô tả sai.
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` — **UPDATE** §3 nếu còn mô tả sai.
- `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` (ChainLens repo, story 42-2) — **REFERENCE/SYNC**.

### References

- `_bmad-output/planning-artifacts/epics.md:462-493` — Story 9.1b scope, AC gốc.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:565-659` — FR-24 contract hiện tại (sai về `event:`/`data:[DONE]`).
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:185-203` — AD-15.
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md:85-108` — SCP §3 (impact PRD/AD-15/UX).
- `nowing_backend/scripts/nowing-sse-contract-snippet.py` (ChainLens standalone contract regression snippet, 2026-08-02) — parse SSE wire format mẫu, extract answer/sources/costDollars.
- `_bmad-output/planning-artifacts/oq7-answers-to-chainlens-2026-07-25.md` — Q1, Q4, fixture `nowing-sse-parser.ts`.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:96-317` — `_SSEParser`.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:369-425` — `_call_chainlens`.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py:15-95` — `MAX_QUERY_LENGTH`, `ResearchInput`, `ResearchOutput`.
- `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py:1-388` — baseline tests.

## Testing Requirements

### Test Matrix

| Case | File | Expected invariant |
|---|---|---|
| Request body shape | `test_executor.py` | Assert body chính xác `{query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId?}`; headers đúng. |
| SSE data-only `block` create/replace | `test_executor.py` | `_parse_sse` trả `answer` + `sources` đúng từ block `text` + `source`. |
| SSE `updateBlock` RFC6902 patch | `test_executor.py` | Patch `replace`/`add` trên `/data` cập nhật block data; patch khác bị bỏ qua. |
| SSE terminal `done` | `test_executor.py` | `chat_id` + `web_url` được parse; `status == "complete"` nếu có nội dung. |
| SSE `error` data-only | `test_executor.py` | Raise `ChainLensError` với message từ payload. |
| Query > 500 hoặc rỗng | `test_executor.py` | Pydantic `ResearchInput` từ chối `query > 500` và `query < 1`; executor không clamp thêm. |
| Source order multi-source | `test_executor.py` | `output.sources` giữ đúng thứ tự engine gửi. |
| No `event:` branch regression | `test_executor.py` | Test cũ `event: error\ndata: ...` bị cập nhật hoặc xoá; parser không còn dựa vào `event:`. |
| Fixture sync with ChainLens 42-2 | `test_executor.py` + `fixtures/chainlens-sse-golden.json` | Copy `nowing-sse-parser.ts` vào local fixture; drift test đỏ nếu lệch. |
| Doc correctness | PRD/AD-15 review | Không còn mô tả `event:`/`data: [DONE]`; request shape có `tier`/`stream`. |

### Suggested Commands

```bash
cd nowing_backend
uv run --active python -m pytest tests/unit/capabilities/chainlens/research -q
```

Chạy lại contract test khi bump ChainLens hoặc sửa `_parse_sse`:

```bash
uv run --active python -m pytest tests/unit/capabilities/chainlens/research/test_executor.py -q
```

## Failure Modes / Edge Cases

| Failure | Behavior |
|---|---|
| Test vẫn viết theo `event:`/`data:[DONE]` cũ | Test sẽ pass trên format không tồn tại, giấu regression. Phải viết test theo data-only frame thật. |
| Query > 500 hoặc rỗng vượt qua Pydantic | `ResearchInput` phải giữ `min_length=1, max_length=500`. Nếu bỏ/relax validation, query rỗng/dài vào engine → 400. |
| Executor tự clamp query | Dư thừa vì Pydantic đã chặn; dễ gây mâu thuẫn logic. Executor không clamp. |
| Source order bị đảo | Citation UI map sai. Test multi-source bắt lỗi. |
| Fixture Nowing tự viết tách biệt ChainLens 42-2 | Drift theo thời gian; regression test bắt sai. Phải đồng bộ fixture. |
| `_SSEParser` vẫn xoá nhánh `event:` nhưng lại xoá cả xử lý `error` | `error` data-only vẫn phải giữ; chỉ xoá nhánh `event:`/`[DONE]` không chạy. |
| Contract test không chạy trong CI | Engine đổi format sẽ vỡ prod. Thêm vào CI target. |

## Open Questions

- **OQ-7 (contract doc sai):** Đã verify 2026-07-25 — NestJS `@Sse()` phát data-only frame, terminal `{"type":"done"}`. Story này sửa tài liệu và parser để bám sát wire thật.
- **ChainLens 42-2 fixture sync:** Nowing sẽ copy `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` vào `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` và viết drift test tại build time. Không chờ ChainLens export golden JSON.

## Dev Agent Record

### Agent Model Used

Devin subagent / Claude Son (background, low-effort mode).

### Debug Log References

- `tests/unit/capabilities/chainlens/research/test_executor.py` — contract regression suite run.
- `tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` — fixture validation + optional drift test.

### Completion Notes List

- T1: Added `_request_capturing_client` helper and two request-shape contract tests (`test_call_chainlens_request_contract_full_payload`, `test_call_chainlens_request_contract_omits_optional_fields`) that assert exact headers and JSON body sent by `_call_chainlens`, including `tier`/`stream` and optional `systemInstructions`/`chatId` omission. Tests fail if the request shape changes.
- T2: Added data-only SSE contract tests for `block` create/replace, `updateBlock` `replace`/`add` on `/data`, unsupported patch operations ignored, `done` chatId/webUrl metadata, and unknown types (`noop`/`progress`) ignored without breaking known frames. Existing `test_parse_sse_raises_on_error_data_frame` and `test_parse_sse_raises_on_error_event_with_json_payload` cover `error` data-only frames.
- T4: Added `test_parse_sse_preserves_source_order` with three sources and assert `ResearchOutput.sources[i]` matches the engine order.
- T3/T5/T6: Verified existing Pydantic query validation, `_SSEParser` data-only frame handling, docstring, and ChainLens 42-2 golden fixture + drift test remain complete and pass.
- Test results: `pytest -m contract` 35 passed / 1 skipped; `pytest tests/unit/capabilities/chainlens/research/ -v` 58 passed / 1 skipped.

### File List

- `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py` — added contract tests (no changes to `executor.py` or `schemas.py`).

## Change Log

| Date | Version | Description | Author |
|---|---|---:|---|
| 2026-07-29 | 0.1 | Created implementation-ready Story 9.1b from epics.md, 9-1a, executor/schemas/test files, PRD/AD-15/SCP/OQ-7. | bmad-create-story |
| 2026-07-29 | 0.2 | Course correction sau Winston review: D3 Pydantic gate, D5 RFC6902, D6 fixture copy + drift, D7 tier/stream, D8/D9 docs/docstring. Cập nhật AC, task, test matrix. | bmad-correct-course |
| 2026-07-29 | 0.3 | 4 open items resolved by code changes: `_strip_query` field validator, removed `pending_event_type`/`event:` branch, `chainlens-sse-golden.json` + drift test, CI `contract` marker. Focused tests 25 passed, 1 skipped with -m contract; 39 passed, 1 skipped full focused. | devin-update |
| 2026-07-30 | 0.4 | Implemented T1/T2/T4 contract regression tests: request shape assertions (headers + exact JSON body), SSE data-only `block`/`updateBlock`/`done`/`error`/`unknown` behavior, and multi-source order preservation. All contract tests pass (35/1) and full research unit tests pass (58/1). Story moved to `review`. | devin-update |
| 2026-07-30 | 0.5 | Mutation gate passed (88.11%, 600/682 killed, 0 P0 survivors). Added `test_mutation_killers.py`, `test_mutation_killers_extra.py`, and `conftest.py` litellm mocks to fix `cosmic-ray` import failures. Ruff clean. | devin-update |

### Architect Review (Winston)

**Review date:** 2026-07-29  
**IR verdict:** `READY` — 4 open items resolved by code changes, focused tests **25 passed, 1 skipped with -m contract; 39 passed, 1 skipped full focused**.  
**CA verdict:** `CONCERNS` → `RESOLVED` (R1–R5 đã chốt bằng D3–D9 và contract test)  
**Review artifact:** `_bmad-output/test-artifacts/9-1b-winston-review.md`

Story 9.1b đã chốt các vấn đề từ Winston review và sẵn sàng cho dev sau khi SCP batch được phê duyệt:

1. **Query clamp vs. Pydantic schema — RESOLVED (D3).** Giữ Pydantic `ResearchInput.query` (`min_length=1, max_length=500`) làm cổng chặn duy nhất. Executor không clamp thêm; query rỗng/dài không vào engine.

2. **Fixture sync with ChainLens 42-2 — RESOLVED (D6).** ChainLens không xuất golden JSON trực tiếp. Nowing copy fixture `nowing-sse-parser.ts` vào `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` và thêm drift test tại build time.

3. **Request body `tier`/`stream` — RESOLVED (D7).** Hai trường đã có trong `executor.py:382,385` từ 9.1a và là một phần hợp lệ của contract. Cập nhật PRD §4.9, AD-15, thêm contract test assert body chính xác.

4. **RFC6902 patch — RESOLVED (D5).** Giữ thủ công `replace`/`add` trên `/data`; khoá bằng contract test từ ChainLens fixture. Chuyển sang `rfc6902`/`jsonpatch` nếu fixture sau này có thêm op/path.

5. **Docstring `_parse_sse` outdated — RESOLVED (D9).** Cập nhật docstring trong dev: không có `event:`, terminal là `{"type":"done"}`.

**Status sau correction:** `review` — T1/T2/T4 contract tests implemented and verified, focused tests **35 passed, 1 skipped with -m contract; 58 passed, 1 skipped full research unit suite**.

### Implementation Readiness

**Status:** `READY FOR REVIEW` (2026-07-30)

T1/T2/T4 completed in this pass; T3/T5/T6 already complete and verified:
1. **AC-1 request shape contract:** added `test_call_chainlens_request_contract_full_payload` and `test_call_chainlens_request_contract_omits_optional_fields` in `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py`, asserting exact headers (`Authorization`, `Content-Type`, `Accept`) and body (`query`, `optimizationMode`, `tier`, `sources`, `history`, `stream`, `systemInstructions?`, `chatId?`).
2. **AC-2 SSE parse contract:** added data-only tests for `block` create/replace, `updateBlock` `replace`/`add` on `/data` plus ignored unsupported patch ops, `done` chatId/webUrl, and unknown types ignored without raising.
3. **AC-4 source order preservation:** added `test_parse_sse_preserves_source_order` with 3 sources and assert order matches engine output.
4. **AC-3 Pydantic query gate:** `test_research_input_rejects_blank_query` passes; executor does not clamp.
5. **AC-5 SSE data-only wire & docstring:** `_SSEParser` has no `event:`/`[DONE]` branch; docstring reflects data-only frames; `test_parse_sse_raises_on_error_data_frame` uses data-only error frame.
6. **AC-6 ChainLens fixture sync:** `chainlens-sse-golden.json` + `test_chainlens_fixture_drift.py` remain in place; optional drift test skipped when `CHAINLENS_REPO_PATH` is unset.
7. **CI target:** marker `contract` in `pyproject.toml`; command `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`.

Focused contract tests: **35 passed, 1 skipped**. Full research unit tests: **58 passed, 1 skipped**. Story chuyển sang `review`.

## Code Review (2026-07-30)

**Reviewer:** Devin subagent / Claude Son (background, low-effort mode).  
**Verdict:** ✅ **APPROVED**

### Review Scope

- Diff: `_bmad-output/test-artifacts/9-1b-review-2026-07-30.diff`
- Source files reviewed: `nowing_backend/app/capabilities/chainlens/research/executor.py`, `nowing_backend/app/capabilities/chainlens/research/schemas.py`, `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py`, `nowing_backend/tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py`, `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json`, `nowing_backend/pyproject.toml`.
- Acceptance criteria: All 6 ACs covered.

### Review Findings

| Triage | Item | Resolution |
|---|---|---|
| `SHOULD_FIX` | `schemas.py:13` ruff `I001` import formatting | Fixed — expanded to multi-line sorted import. |
| `SHOULD_FIX` | `executor.py:56` dead `_SourceDict` alias | Fixed — removed. |
| `SHOULD_FIX` | Missing boundary test for `query > 500` | Fixed — added `test_research_input_rejects_oversized_query` (`test_executor.py:126`). |
| `NOTE` | `insufficientEvidence` may overwrite a prior `partial` answer if `partial.answer` is empty | Non-blocking; inherited pre-existing behavior, no AC test coverage. |
| `NOTE` | Golden fixture is not fed through `_parse_sse` in CI; drift test requires `CHAINLENS_REPO_PATH` | Non-blocking; consider a follow-up contract test. |
| `NOTE` | `test_call_chainlens_maps_unknown_4xx_to_upstream_error` assertion allows `auth_failed` | Non-blocking; tighten to `upstream_error` in follow-up. |

### Verification

- `pytest ... -m contract -v`: **36 passed, 1 skipped**.
- `pytest tests/unit/capabilities/chainlens/research -q`: **59 passed, 1 skipped**.
- `ruff check ...`: **All checks passed**.

### Review Artifact

- `_bmad-output/test-artifacts/9-1b-code-review-2026-07-30.md`

Story ready for merge.

## Test Review (2026-07-30)

**Reviewer:** Devin subagent / Claude Son (background, low-effort mode).  
**Verdict:** ✅ **APPROVED**  
**Score / Grade:** **96/100 — A**  
**Review artifact:** `_bmad-output/test-artifacts/test-review-validation-report-9-1b.md`

### Scope

- `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py`
- `nowing_backend/tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py`
- `nowing_backend/tests/unit/capabilities/chainlens/research/test_schemas.py`

### Verification

- `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`: **41 passed, 1 skipped**.
- `pytest tests/unit/capabilities/chainlens/research/ -q`: **64 passed, 1 skipped**.
- `pytest tests/unit/capabilities/chainlens/research/test_schemas.py -q`: **14 passed**.
- `ruff check tests/unit/capabilities/chainlens/research/ --fix`: **All checks passed**.

### Key Findings

1. **Test / contract coverage is strong**: request shape, headers, body, SSE `block`/`updateBlock`/`done`/`error`/`partial`/`insufficientEvidence`/`heartbeat`, unknown types, Pydantic query validation, source order, and fixture drift are all guarded.
2. **All review findings resolved**:
   - **Test IDs added**: every test in `test_executor.py` and `test_chainlens_fixture_drift.py` now carries `@pytest.mark.test_id("9-1b-NNN")`; marker `test_id` registered in `pyproject.toml`.
   - **Loose assertions tightened**: `test_executor.py` now asserts exact `engine_unavailable`, `partial`, `upstream_error`, and `unreachable` values instead of `in`/`getattr(..., None)`.
   - **Golden fixture is parsed through `_parse_sse`**: `test_parse_sse_golden_fixture_parses` (in `test_executor.py`) and `test_chainlens_sse_golden_fixture_parses_through_parse_sse` (in `test_chainlens_fixture_drift.py`) feed the fixture into `_parse_sse` and assert usable output.
   - **Missing contract tests added**: `event:` / `data: [DONE]` ignored, async iterator path, and `insufficientEvidence` with empty answer/sources are now covered.
3. **Quality gaps (intentional / non-blocking)**:
   - `test_executor.py` is now **793 lines** and exceeds the 300-line guideline. The team intentionally colocates the parser/executor contract suite in one file for traceability; splitting is deferred to a future refactor.
   - `partial` with `state="insufficient_evidence"` and no content is inherited pre-existing behavior and is not additionally covered beyond the `insufficientEvidence` empty case.

### Next Steps

1. Merge after final code review sign-off.
2. Future refactor: split `test_executor.py` into `test_research_contract.py` if the contract suite continues to grow.

## Mutation Gate (2026-07-30)

**Gate:** `bmad-nowing-mutation-gate` (P0 mandatory)  
**Verdict:** ✅ **PASS** — mutation score **88.11%** (threshold ≥ 80%).  
**Report:** `_bmad-output/test-artifacts/mutation-nowing-chainlens-research-gate-report-9-1b.md`

### Headline numbers

| Metric | Count |
|---|---:|
| Total mutants | 682 |
| Killed | 600 |
| Survived | 74 |
| Timeout | 0 |
| No tests / incompetent | 1 |
| **Mutation score** | **88.11%** |

### Triage

- **P0 survivors:** 0
- **P1:** 70 (mostly equivalent `ReplaceBinaryOperator_BitOr_*` mutations on `from __future__ import annotations` type-annotation unions; 4 real `NumberReplacer` / comparison survivors)
- **P2:** 4

### What changed to pass the gate

1. **Litellm mocking in `conftest.py`:** `cosmic-ray` import failures for `litellm`, `litellm.utils.ImageResponse`, and `litellm.types.utils.Delta` were resolved by extending `tests/conftest.py` to treat the fake `litellm` as a package and to mock `aimage_generation`, `image_generation`, `Router`, `utils`, and `types`.
2. **Mutation-killer tests:** `test_mutation_killers.py` (120 tests) and `test_mutation_killers_extra.py` (39 tests) cover boundary conditions, comparison-operator mutations, and branch logic in `executor.py` and `schemas.py`.
3. **Ruff clean-up:** `RUF005` and `SIM117` fixes were applied to `test_mutation_killers_extra.py`; `N818` was addressed in `tests/conftest.py`.

### Verification

- `pytest tests/unit/capabilities/chainlens/research/test_mutation_killers.py -q`: **120 passed**
- `pytest tests/unit/capabilities/chainlens/research/test_mutation_killers_extra.py -q`: **39 passed**
- `pytest <full discovered test command under COSMIC_RAY=1> -q`: **286 passed, 1 skipped** (drift test skipped because `CHAINLENS_REPO_PATH` is unset)
- `ruff check tests/unit/capabilities/chainlens/research/ tests/conftest.py`: **All checks passed**

### Human Review Gate (2026-07-30)

**Gate:** `bmad-nowing-human-review-gate`  
**P0 Areas Touched:**
- **External integrations with side effects** — `app/capabilities/chainlens/research/executor.py` calls ChainLens `POST /api/v1/search` and streams SSE; real API key, real upstream, real cost.
- **RAG / connector sync with side effects** — KB fallback (`_kb_fallback`) calls `search_chunks` in `app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py`; touches workspace knowledge base.
- **Authentication / authorization** — `app/capabilities/core/access/agent.py` re-validates `auth_context`/`workspace_id` before executing tools; `app/capabilities/core/access/rest.py` runs `check_workspace_access` on every sync call.
- **Token / credit / billing** — `agent.py:163` and `rest.py:424` call `charge_capability` to record `cost_micros`; `agent.py:133` and `rest.py:339` call `gate_capability` for credit pre-check.
- **Multi-agent chat orchestration** — `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` passes `auth_context` into ChainLens subagent tool loader.

**What to review manually:**
1. `executor.py:384-417` — ChainLens call contract, auth header, error mapping, and `response.aclose()` cleanup.
2. `executor.py:491-561` — KB fallback logic: top-k clamping, source construction, status transitions.
3. `core/access/agent.py:128-165` — workspace access check vs auth bypass when `auth_context is None`, charge failure swallowing, `cost_micros=None` recording.
4. `core/access/rest.py:336-426` — sync run auth, credit gate, charge failure, `cost_micros` handling.
5. `metrics.py` — degradation reason redaction does not leak PII or sensitive URLs.
6. `core/__init__.py:20-86` — executor signature inspection and `ctx` passing; backward compatibility for capability executors.

**Status:** ✅ **APPROVED** — human reviewer signed off, story moved to `done`.

### Next Steps

1. ✅ Human reviewer approved.
2. Merge branch `develop` (commit `fd64d84f4`) when ready.

---

### Review Findings (bmad-code-review second pass — 2026-07-30)

| Triage | Item | Detail | Location |
|---|---|---|---|
| `resolved` | Type hint uses `//` instead of `\|` | Fixed: `_block_type_for` now uses `str | None`. | `executor.py:56` |
| `resolved` | Test name still uses `event` terminology | Fixed: renamed to `test_parse_sse_raises_on_error_data_frame_with_json_payload`. | `test_executor.py:149` |
| `resolved` | CI contract test execution | Added dedicated `backend-contract` job in `.github/workflows/test.yml` running `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`. | `.github/workflows/test.yml:271` |
| `dismiss` | `top_k` default changed from 5 to 6 | Call site passes `top_k=5` and value is clamped to `max(1, min(top_k, 5))`. No runtime impact. | `executor.py:449` |
| `dismiss` | `_parse_sources` uses `Any` | Removed `_SourceDict` alias and changed signature to `Any` to support `partial_blob.get("sources")`; runtime `isinstance` checks still guard. | `executor.py:35` |
| `dismiss` | Metrics call dropped `url` parameter | `metrics.record_blocked_url_coverage` new signature only takes `block_type`; call matches. | `executor.py:229,261` |
| `defer` | `core/__init__.py` signature-inspection can raise on builtins/C extensions | `inspect.signature` may raise `ValueError` for some callables. No fallback. Should be handled or tested as part of capability-core hardening. | `core/__init__.py:21,31` |
| `defer` | Agent tool workspace-access check skipped when `auth_context is None` | Intentional for unauthenticated internal invocations per docstring, but creates a trust-boundary gap vs REST door. Needs security decision/audit. | `core/access/agent.py:176` |
| `defer` | `check_workspace_access` has no timeout | Agent tool could hang indefinitely if workspace access check stalls. | `core/access/agent.py:146` |
| `defer` | `scripts/mutation-gate.py` service path validation | No validation for empty/None/invalid `service` argument in `discover_tests`. Could produce misleading errors. | `scripts/mutation-gate.py:164` |
| `defer` | `test_system_prompt.py` uses `parents[8]` | Fragile relative path; could break if test directory depth changes. Consider project-root helper. | `test_system_prompt.py:149` |

**Tally:** 2 `patch`, 1 `decision`, 3 `dismiss`, 6 `defer`.

**Recommendation:** Apply the two `patch` items immediately; they are unambiguous and the type-annotation one is a latent type-checker failure. Resolve the `decision` before final merge.
