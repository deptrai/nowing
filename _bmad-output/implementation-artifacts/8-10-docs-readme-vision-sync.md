---
baseline_commit: 37d6e881ff5c8e88e61a2d9a7a7b0fe31
baseline_branch: develop
story_key: 8-10-docs-readme-vision-sync
status: done
---

# Story 8.10: Docs / README / Vision Sync

**Status:** done  
**Epic:** 8 — Người dùng thấy và kiểm soát được chi phí  
**Priority:** MEDIUM — OQ-6 / AR-10 / RS-5 (docs-sync bắt buộc, chặn public repo trước khi README nói sai)  
**Requirements:** OQ-6, AR-10, RS-5  
**Architecture:** AD-15 (Nowing ↔ ChainLens boundary), AD-16 (dual license), AD-9 (workspace RBAC Owner/Editor/Viewer)  
**Dependencies:** Story 9.1a (degradation) done; Story 9.4 (docs sync Nowing ↔ ChainLens) done; Story 8.11 done.

> **Note (2026-08-05):** This is a historical dev artifact. The canonical Acceptance Criteria for Story 8.10 are in `_bmad-output/planning-artifacts/epics.md`; they were rewritten to remove implementation-specific file paths and migration numbers.  

## Story

As an OSS beachhead user (agent-builder),  
I want README/docs phản ánh đúng vision research-memory + trạng thái đã ship,  
So that mở repo không thấy định vị cũ / feature đã gỡ (tránh cảm giác vaporware).

## Current Reality

### Outdated / removed features still advertised

- **"Admin" role in RBAC** — migration 72 removed the system-wide `Admin` workspace role; RBAC hiện chỉ còn `Owner/Editor/Viewer`. Vẫn còn xuất hiện trong `README.md` (dòng 159, 237) và 4 bản dịch.
- **"AI file sorting"** — FR-5 removed; migration 172 xoá. Vẫn còn dòng 140 `README.md` và các bản dịch.
- **"NotebookLM alternative" positioning** — pre-pivot; brief §7/§12 yêu cầu gỡ khỏi mọi tài liệu công khai. Còn trong `README.md`, 4 bản dịch, web SEO (`nowing_web/app/layout.tsx`, `components/seo/json-ld.tsx`), landing copy (`components/homepage/hero-section.tsx`, `components/homepage/compare-table.tsx`, `app/(home)/free/page.tsx`), và install scripts (`docker/scripts/install.sh`, `docker/scripts/install.ps1`).

### Current vision / copy source of truth

Nguồn chân lý cho README/landing là `briefs/brief-Nowing-2026-07-25/brief.md` §1, §5.1, §7, §8, §12 (final 2026-07-25), được propagate sang PRD §1.1, §2.4, §4.9 và `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`.

- **One-sentence promise (English, dùng thật):**
  > "Nowing is open-source research memory for AI agents — it remembers what it went and found, not just what you told it."
- **Subtitle:**
  > "Self-hosted research workspace with long-term memory for AI agents and teams."
- **Differentiator trả lời "khác gì X":**
  > "Most memory layers remember what you told them. Nowing also remembers what it went and found."
- **License framing (ba tầng, không gọi tổng thể là "open source"):**
  - Core: Apache-2.0
  - Crawler engine (`nowing_backend/app/proprietary/**`): BSL 1.1 — *không phải OSS*, được dùng production, cấm bán lại dạng hosted/managed service.
  - Deep-research engine: closed-source, hosted.
- **Ranh giới self-host vs cloud:**
  - Self-host: miễn phí, dữ liệu không rời hạ tầng; có toàn bộ core + live connectors + memory + MCP.
  - Cloud: thêm deep multi-step open-web research trên hosted engine.
  - Deep research là năng lực **cloud-only Phase 1**, gọi là *"Nowing's hosted deep-research engine"* — **KHÔNG nêu tên ChainLens**.

### Files cần audit/update

| Nhóm | Files |
|---|---|
| README + docs gốc | `README.md`, `README.es.md`, `README.hi.md`, `README.pt-BR.md`, `README.zh-CN.md`, `docs/project-overview.md`, `docs/index.md` |
| Docs site (Fumadocs) | `nowing_web/content/docs/index.mdx`, `nowing_web/content/docs/how-to/mcp-server.mdx`, các meta title/description nếu cần |
| Web SEO/landing | `nowing_web/app/layout.tsx`, `nowing_web/components/seo/json-ld.tsx`, `nowing_web/components/homepage/hero-section.tsx`, `nowing_web/components/homepage/compare-table.tsx`, `nowing_web/app/(home)/free/page.tsx` |
| Install scripts | `docker/scripts/install.sh`, `docker/scripts/install.ps1` |

### Drift check chưa có

Hiện không có CI nào chặn các cụm `NotebookLM`, `AI file sorting`, `Admin.*role`, hay `for people` quay lại README/docs/landing. Cần một script/quy trình kiểm tra tự động.

## Acceptance Criteria

### AC-1: Gỡ mô tả sai từ README/docs chính

**Given** `README.md`/`docs/project-overview.md`/`docs/index.md` còn pre-pivot  
**When** sync  
**Then** phản ánh "long-term research memory" + gỡ mô tả sai (Admin role removed mig 72, AI File Sorting removed mig 172, "NotebookLM alternative").  
*Source: `epics.md` Story 8.10; `brief.md` §7, §12.*

### AC-2: Cập nhật README translations

**Given** `README.es.md`, `README.hi.md`, `README.pt-BR.md`, `README.zh-CN.md` vẫn dùng định vị cũ  
**When** sync  
**Then** các bản dịch sử dụng câu hứa + framing tương đương, **KHÔNG** dịch nguyên văn "NotebookLM alternative" hay nhắc `Admin` / AI file sorting.

### AC-3: Cập nhật web SEO và landing copy

**Given** `nowing_web/app/layout.tsx`, `components/seo/json-ld.tsx`, `components/homepage/hero-section.tsx`, `components/homepage/compare-table.tsx`, `app/(home)/free/page.tsx` còn "NotebookLM"  
**When** sync  
**Then** thay bằng "long-term research memory" / "open-source core + hosted deep-research engine" theo brief §7, §12.

### AC-4: Cập nhật install scripts

**Given** `docker/scripts/install.sh` và `docker/scripts/install.ps1` in `NotebookLM for Open Web Research`  
**When** sync  
**Then** in thông điệp phù hợp vision hiện tại.

### AC-5: Publish one-sentence promise + MCP quickstart

**Given** README/docs thiếu câu hứa tập trung và MCP quickstart  
**When** sync  
**Then** README có câu hứa chính ở hero/header, và có/link đến MCP quickstart (`nowing_web/content/docs/how-to/mcp-server.mdx` hoặc đoạn quickstart trong README) để agent-builder chạy được trong vòng 5 phút.

### AC-6: CI docs-vs-code drift check

**Given** merge mới có thể đưa từ ngữ cũ quay lại  
**When** PR mở  
**Then** một check trong CI fail nếu phát hiện các forbidden phrases (`NotebookLM`, `AI file sorting`, `Admin.*role` trong README/docs, `for people` trong README) và report file/line.

## Resolved Decisions

### D1 — One-sentence promise là fixed copy

Dùng chính xác:
> "Nowing is open-source research memory for AI agents — it remembers what it went and found, not just what you told it."

Không sửa từ, không thêm biến thể mới ngoài subtitle ("Self-hosted research workspace with long-term memory for AI agents and teams.") và dòng trả lời "khác gì X". Source: `brief.md` §1, §12.1.

### D2 — Không gọi sản phẩm là "open source" trần trụi

README phải dùng **"Apache-2.0 core + BSL 1.1 crawler engine"** và giải thích BSL là điểm bán (self-host production OK, cấm bán lại hosted). Source: `brief.md` §5.1, §7.

### D3 — Bảng feature self-host vs cloud phải có

| | Self-host (miễn phí) | Cloud (trả theo dùng) |
|---|---|---|
| Memory layer + 4 MCP tool | ✅ | ✅ |
| Knowledge base + hybrid search + citations | ✅ | ✅ |
| 8 nền tảng / 14 scraping verb | ✅ (BSL) | ✅ |
| Chat đa agent + deliverables + automations | ✅ | ✅ |
| 5 client surface | ✅ | ✅ |
| Deep multi-step open-web research | Phase 1: ❌ · Phase 2: 💳 | ✅ |

Source: `brief.md` §5.1.

### D4 — Không nêu tên ChainLens, gọi là "Nowing's hosted deep-research engine"

Tuân thủ NG-3. Source: PRD §1.1, `brief.md` §5.1.

### D5 — RBAC chỉ Owner/Editor/Viewer

Không nhắc `Admin` role trong bất kỳ tài liệu công khai. Platform admin (superuser) là khái niệm khác, không nằm trong workspace RBAC. Source: AD-9, Story 8.11 D1.

### D6 — CI drift check chạy trong `code-quality.yml`

Không tạo workflow riêng nếu có thể gắn vào `code-quality.yml` (job `file-quality` hoặc job mới `docs-drift`) để tránh phân mảnh. Script Python kiểm tra forbidden phrases và report line numbers.

## Tasks / Subtasks

- [x] T1 — Audit toàn bộ README + docs hiện tại, xác nhận danh sách chỗ cần sửa (AC-1, AC-2)
  - [x] 1.1 Đọc `README.md` và 4 bản dịch
  - [x] 1.2 Đọc `docs/project-overview.md`, `docs/index.md`, các `nowing_web/content/docs/*`
  - [x] 1.3 Đọc `nowing_web/app/layout.tsx`, `components/seo/json-ld.tsx`, `components/homepage/hero-section.tsx`, `components/homepage/compare-table.tsx`, `app/(home)/free/page.tsx`
  - [x] 1.4 Đọc `docker/scripts/install.sh`, `docker/scripts/install.ps1`
  - [x] 1.5 Ghi lại tất cả vị trí chứa forbidden phrases
- [x] T2 — Cập nhật README.md chính (AC-1, AC-5)
  - [x] 2.1 Thay title/hero bằng one-sentence promise
  - [x] 2.2 Gỡ "AI file sorting" (dòng 140)
  - [x] 2.3 Sửa RBAC thành Owner/Editor/Viewer (dòng 159, 237)
  - [x] 2.4 Thay "NotebookLM alternative" → long-term research memory / hosted deep-research engine
  - [x] 2.5 Xoá hoặc thay section "Nowing vs Google NotebookLM" / comparison table
  - [x] 2.6 Thêm MCP quickstart section/link
  - [x] 2.7 Thêm bảng self-host vs cloud
  - [x] 2.8 Cập nhật license wording (Apache-2.0 + BSL 1.1)
- [x] T3 — Cập nhật 4 README translations (AC-2)
  - [x] 3.1 `README.es.md`
  - [x] 3.2 `README.hi.md`
  - [x] 3.3 `README.pt-BR.md`
  - [x] 3.4 `README.zh-CN.md`
- [x] T4 — Cập nhật docs site (Fumadocs) (AC-1, AC-5)
  - [x] 4.1 `nowing_web/content/docs/index.mdx` — thêm one-sentence promise và link MCP quickstart
  - [x] 4.2 Kiểm tra `nowing_web/content/docs/how-to/mcp-server.mdx` còn đúng vision không
  - [x] 4.3 Kiểm tra/cập nhật `docs/project-overview.md`, `docs/index.md` trong root
- [x] T5 — Cập nhật web SEO và landing copy (AC-3)
  - [x] 5.1 `nowing_web/app/layout.tsx` metadata
  - [x] 5.2 `nowing_web/components/seo/json-ld.tsx`
  - [x] 5.3 `nowing_web/components/homepage/hero-section.tsx`
  - [x] 5.4 `nowing_web/components/homepage/compare-table.tsx`
  - [x] 5.5 `nowing_web/app/(home)/free/page.tsx`
- [x] T6 — Cập nhật install scripts (AC-4)
  - [x] 6.1 `docker/scripts/install.sh`
  - [x] 6.2 `docker/scripts/install.ps1`
- [x] T7 — Implement CI docs-vs-code drift check (AC-6)
  - [x] 7.1 Viết `scripts/check-docs-drift.py` hoặc tương đương
  - [x] 7.2 Cấu hình forbidden phrases + allowed exceptions
  - [x] 7.3 Gắn vào `.github/workflows/code-quality.yml` hoặc workflow mới
  - [x] 7.4 Chạy thử trên working tree hiện tại để xác nhận fail trước khi sửa và pass sau khi sửa
- [x] T8 — Self-review + validation
  - [x] 8.1 Chạy drift check
  - [x] 8.2 `pnpm tsc --noEmit` nếu đụng TSX
  - [x] 8.3 Review diff tổng thể
  - [x] 8.4 Cập nhật `AGENTS.md` với lệnh verify cho story 8.10

## Dev Notes

### Forbidden phrases list (fuzzy vùng docs + web)

| Phrase | Status | Replacement gợi ý |
|---|---|---|
| `NotebookLM alternative` | FORBIDDEN | `open-source research memory for AI agents` / `long-term research memory` |
| `AI file sorting` | FORBIDDEN | (xoá) |
| `Admin` khi đi kèm RBAC roles | FORBIDDEN | chỉ `Owner / Editor / Viewer` |
| `for people` trong positioning | FORBIDDEN | `for AI agents and research teams` |
| `open source` trần trụi cho cả sản phẩm | AVOID | `Apache-2.0 core + BSL 1.1 crawler engine` |
| `ChainLens` | FORBIDDEN in public docs | `Nowing's hosted deep-research engine` |

### Scope web components

- `social-proof.tsx` chứa **YouTube video titles do người dùng tạo** — không sửa vì đó là nội dung bên thứ ba; chỉ sửa copy do Nowing viết.
- Các metadata OpenGraph/Twitter trong `layout.tsx` cần consistent với `json-ld.tsx`.

### CI drift check design

- Input: danh sách forbidden regex + file glob.
- Output: exit 1 + danh sách file/line nếu match.
- Exceptions: các file `.knowns/docs/` (runtime), `README.*.md` translations cũng phải check (không exception).
- Gợi ý implementation:
  - Python script đọc `forbidden_phrases.json`.
  - Chạy trên `README.md`, `README.*.md`, `docs/**/*.md`, `nowing_web/content/docs/**/*.mdx`, `nowing_web/app/layout.tsx`, `nowing_web/components/seo/**/*.tsx`, `nowing_web/components/homepage/**/*.tsx`, `nowing_web/app/(home)/free/page.tsx`, `docker/scripts/install.sh`, `docker/scripts/install.ps1`.
  - Bỏ qua URLs, image alt nếu cần — nhưng với vision sync thì nên strict.

## Project Structure Notes

- `README.md` và `README.*.md` nằm ở root.
- `docs/` ở root chứa markdown tài liệu dự án (không phải Fumadocs site).
- `nowing_web/content/docs/` là nguồn Fumadocs; `nowing_web/app/docs/[[...slug]]/page.tsx` render động.
- `docker/scripts/install.sh` và `install.ps1` in banner khi chạy Docker setup.
- `.github/workflows/code-quality.yml` là nơi hợp lý để thêm drift check.

## References

- `epics.md` Story 8.10: `_bmad-output/planning-artifacts/epics.md` §366-374
- Product Brief (nguồn chân lý copy): `_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md` §1, §5.1, §7, §8, §12
- PRD vision & non-goals: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §1, §1.1, §2.4
- Sprint change proposal (Nowing ↔ ChainLens boundary): `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`
- Story 8.11 (platform admin, RBAC context): `_bmad-output/implementation-artifacts/8-11-admin-ui-global-llm-model-config.md`
- Current README: `README.md`
- Current docs index: `docs/index.md`
- Docs site index: `nowing_web/content/docs/index.mdx`
- CI workflow: `.github/workflows/code-quality.yml`

## Dev Agent Record

### Agent Model Used

Devin (SWE-1.7 Max) — story creation via `bmad-create-story` workflow.

### Debug Log References

- Sprint status generated: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Outdated content audit: background subagent `1ce0d2c0` — `Story 8.10 Docs/README/Vision Sync Audit Report`

### Completion Notes List

- Story 8.10 được chọn là story backlog đầu tiên sau khi `bmad-sprint-planning` refresh.
- Đã phân tích `brief.md`, `prd.md`, `epics.md`, README hiện tại, docs site, web components, và install scripts.
- Forbidden phrases và replacement copy đã xác định theo brief §7.

### File List

- `_bmad-output/implementation-artifacts/8-10-docs-readme-vision-sync.md` (story file này)
- Files sẽ touch khi dev:
  - `README.md`
  - `README.es.md`, `README.hi.md`, `README.pt-BR.md`, `README.zh-CN.md`
  - `docs/project-overview.md`, `docs/index.md`
  - `nowing_web/content/docs/index.mdx`
  - `nowing_web/app/layout.tsx`
  - `nowing_web/components/seo/json-ld.tsx`
  - `nowing_web/components/homepage/hero-section.tsx`
  - `nowing_web/components/homepage/compare-table.tsx`
  - `nowing_web/app/(home)/free/page.tsx`
  - `docker/scripts/install.sh`, `docker/scripts/install.ps1`
  - `.github/workflows/code-quality.yml` (hoặc file workflow mới)
  - `AGENTS.md`
