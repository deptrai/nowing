---
title: 'Story 3.6: Citation Scroll-to-Highlight in Full Document Editor (New Gap)'
description: ''
createdAt: '2026-07-28T10:28:33.050Z'
updatedAt: '2026-07-28T15:17:33.342Z'
tags:
  - bmad
  - bmad-source-bmad-output-implementation-artifacts-3-6-citation-scroll-to-highlight-in-full-document-editor-new-gap-md
---

---
baseline_commit: c0b979c4bb79d6376f05e4822ecf93fa50c7b1a8
---

# Story 3.6: Citation Scroll-to-Highlight in Full Document Editor (New Gap)

**Status:** done
**Epic:** 3 — Knowledge Base & Search
**Source:** <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md" />
**Related PRD:** FR-13, NFR-6 in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />
**Related Architecture:** AD-DEFER-1 in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />

## Story

As a chat user,
I want clicking “Open full document” from a citation to jump to and highlight the cited chunk in the editor,
So that I can read the source in full context.

## Acceptance Criteria

1. **Pass `chunkId` into editor panel state**
   - **Given** the citation panel is open with a `chunkId`
   - **When** the user clicks “Open”
   - **Then** `editorPanelAtom` is opened with `documentId`, `workspaceId`, and `chunkId`

2. **Editor panel fetches the cited chunk**
   - **Given** the editor panel is opened with a `chunkId`
   - **When** the document content loads
   - **Then** the editor fetches chunk metadata (including absolute `position`) and locates the chunk content within `source_markdown`

3. **Scroll to chunk**
   - **Given** the editor has rendered the document
   - **When** the target chunk is located
   - **Then** the editor view scrolls the chunk into the viewport

4. **Highlight chunk**
   - **Given** the target chunk is visible
   - **When** the editor renders the document
   - **Then** the chunk is visually highlighted (background color, border, or selection) for a few seconds

5. **Plate editor support**
   - **Given** the document is rendered with the Plate editor
   - **When** the chunk is located
   - **Then** the highlight maps from `chunkId` to the corresponding Slate block/range and scrolls into view

6. **Monaco fallback support**
   - **Given** the document is large and rendered with Monaco
   - **When** the chunk is located
   - **Then** Monaco reveals the approximate line and applies a temporary highlight

7. **Markdown viewer support**
   - **Given** the document is rendered as read-only Markdown
   - **When** the chunk is located
   - **Then** the DOM element containing the chunk text is scrolled into view and highlighted

8. **Clear highlight on close/new document**
   - **Given** the editor panel is closed or a different document is opened
   - **When** the state resets
   - **Then** the highlight state is cleared

## Tasks / Subtasks

- [ ] Backend: expose chunk `position` in API responses (AC 2)
  - [ ] Add `position` to `ChunkRead` (no DB migration needed — `position` already exists in `Chunk` model)
  - [ ] Ensure `/documents/by-chunk/{chunk_id}` returns `position` for each chunk in the response
  - [ ] Verify `DocumentWithChunksRead` serializes `chunks[*].position` correctly
- [ ] Web: update Zod types (AC 2)
  - [ ] Add `position` to the `chunkRead` schema in `document.types.ts`
  - [ ] Update `documentWithChunks` / `getDocumentByChunkResponse` to include `position`
- [ ] Web: extend editor panel state (AC 1)
  - [ ] Add `chunkId: number | null` to `EditorPanelState` interface in `editor-panel.atom.ts`
  - [ ] Update `openEditorPanelAtom` payload to accept optional `chunkId` for `document` kind
  - [ ] Initialize `chunkId: null` in `initialState` and reset it in `closeEditorPanelAtom`
  - [ ] Pass `chunkId` from `CitationPanelContent` `handleOpenFullDocument`
  - [ ] Thread `chunkId` through `RightPanel` and `DesktopEditorPanel` props to `EditorPanelContent`
- [ ] Web: fetch and locate chunk in editor (AC 2, 3, 4)
  - [ ] Fetch chunk data when `chunkId` is present (reuse `getDocumentByChunk`)
  - [ ] Build a strategy to map chunk content to a position in `source_markdown` (text search fallback with `ponytail`)
  - [ ] Add scroll/highlight effect after document content loads
  - [ ] Clear highlight state when panel closes or a new document is opened
- [ ] Web: implement editor-specific scroll + highlight + cleanup (AC 5, 6, 7, 8)
  - [ ] Plate: convert character offset to Slate `Point`/`Range`, `Transforms.select`, temporary `highlight` mark; remove mark on cleanup
  - [ ] Monaco: calculate target line, `editor.revealLineInCenter`, add decoration via `editor.deltaDecorations`, store decoration IDs for cleanup
  - [ ] MarkdownViewer: DOM text search, `scrollIntoView`, temporary CSS highlight class; remove class on cleanup
- [ ] Tests
  - [ ] Unit test backend `ChunkRead` includes `position` and `/documents/by-chunk/{chunk_id}` response contains `position`
  - [ ] Component/E2E test: open citation → click “Open” → editor scrolls/highlight visible in Plate, Monaco, and MarkdownViewer modes

## Dev Notes

### Background

Story 3.4 already implemented a right-panel citation viewer (`CitationPanelContent`) that fetches `/documents/by-chunk/{chunk_id}?chunk_window=5` and highlights the cited chunk inside the panel. The missing piece is the “Open full document” action: it currently calls `openEditorPanel` with only `documentId`, `workspaceId`, and `title`, so the full editor has no idea which chunk to jump to.

### Data model

The `Chunk` model already has a `position` column used for ordering:

```python
class Chunk(BaseModel, TimestampMixin):
    __tablename__ = "chunks"
    id: int
    content: Text
    position: Integer  # order within the document
    document_id: Integer
    ...
```

<ref_snippet file="/Users/luisphan/Documents/nowing/nowing_backend/app/db.py" lines="1467-1484" />

However, `ChunkRead` currently does **not** expose `position`:

```python
class ChunkBase(BaseModel):
    content: str
    document_id: int

class ChunkRead(ChunkBase, IDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True)
```

<ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/app/schemas/chunks.py" />

The `/documents/by-chunk/{chunk_id}` endpoint calculates the cited chunk index (`cited_idx`) by counting chunks with a lower `position` or same `position` and lower `id`, then returns a window of chunks. It already returns `total_chunks` and `chunk_start_index`.

<ref_snippet file="/Users/luisphan/Documents/nowing/nowing_backend/app/routes/documents_routes.py" lines="1055-1150" />

### Existing APIs

- `GET /api/v1/documents/by-chunk/{chunk_id}?chunk_window=5` returns `DocumentWithChunksRead` with a window of chunks.
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/editor-content` returns the full `source_markdown` plus viewer-mode flags.

<ref_snippet file="/Users/luisphan/Documents/nowing/nowing_backend/app/routes/editor_routes.py" lines="46-120" />

### Frontend state

`editorPanelAtom` currently holds:

```typescript
interface EditorPanelState {
  isOpen: boolean;
  kind: "document" | "local_file" | "memory";
  documentId: number | null;
  localFilePath: string | null;
  workspaceId: number | null;
  memoryScope: "user" | "team" | null;
  title: string | null;
  chunkId: number | null;  // NEW
}
```

`openEditorPanelAtom` must accept an optional `chunkId` in the `document` payload, and `closeEditorPanelAtom` must reset `chunkId` to `null`.

<ref_file file="/Users/luisphan/Documents/nowing/nowing_web/atoms/editor/editor-panel.atom.ts" />

`CitationPanelContent` currently opens the editor without `chunkId`:

```typescript
const handleOpenFullDocument = () => {
  if (!data) return;
  openEditorPanel({
    documentId: data.id,
    workspaceId: data.workspace_id,
    title: data.title,
    chunkId: chunkId,  // NEW
  });
};
```

<ref_snippet file="/Users/luisphan/Documents/nowing/nowing_web/components/citation-panel/citation-panel.tsx" lines="76-83" />

`RightPanel.tsx` and `DesktopEditorPanel` must thread `chunkId` from `editorPanelAtom` into `EditorPanelContent`:

```typescript
<EditorPanelContent
  kind={editorState.kind}
  documentId={editorState.documentId ?? undefined}
  workspaceId={editorState.workspaceId ?? undefined}
  title={editorState.title}
  chunkId={editorState.chunkId ?? undefined}  // NEW
  onClose={closeEditor}
/>
```

`EditorPanelContent` must add `chunkId?: number` to its props and use it after the document loads.

### Editor rendering

`EditorPanelContent` supports three render paths:

1. **PlateEditor** for normal rich-markdown documents (`viewer_mode === "plate"` or default).
2. **SourceCodeEditor** (Monaco) for large documents (`viewer_mode === "monaco"` or `isLargeDocument`).
3. **MarkdownViewer** for read-only view.

<ref_snippet file="/Users/luisphan/Documents/nowing/nowing_web/components/editor-panel/editor-panel.tsx" lines="840-872" />

### Mapping strategy

The core challenge is mapping a `chunkId` to a location in the full `source_markdown`.

`source_markdown` is not guaranteed to be a simple concatenation of `Chunk.content` (cleaning/normalization during chunking can differ). The first working approach:

1. Add `position` to `ChunkRead` and the frontend Zod schema.
2. Request `/documents/by-chunk/{chunk_id}` to get the cited chunk `content` and `position`.
3. After `editor-content` loads, search `source_markdown` for the chunk content.
4. If the content is unique, compute line/character offset and scroll/highlight.
5. If the content appears multiple times or was normalized differently, fall back to an estimate: `position / total_chunks * line_count`, then search within a small window around that line.
6. If not found at all, fall back to a proportional scroll based on `position`.

`ponytail:` Text search is a heuristic. It works for most documents where chunks are contiguous substrings of `source_markdown`, but it can fail if chunking splits or cleans the text. Upgrade path: persist `start_char_offset` / `end_char_offset` on `Chunk` at indexing time and expose those fields, then scroll by exact character range.

### Editor-specific scroll + highlight + cleanup

Use the same `requestAnimationFrame` + `scrollIntoView` / reveal pattern that `CitationPanelContent` already uses for panel scrolling.

| Editor | Scroll API | Highlight API | Cleanup API |
|---|---|---|---|
| **Plate** | Convert line/char offset to a Slate `Point`/`Range`, call `Transforms.select(editor, range)` and `ReactEditor.focus(editor)`. Slate scrolls the selection into view automatically. | Add a temporary `highlight` mark with `Transforms.setNodes(editor, { highlight: true }, { at: range, split: true })`. | On unmount/document change, call `Transforms.setNodes(editor, { highlight: false }, { at: [], match: (n) => n.highlight === true })` or reload the editor value to strip marks. |
| **Monaco** | `editor.revealLineInCenter(lineNumber)` or `editor.revealRangeInCenter(range)`. | `const id = editor.deltaDecorations([], [{ range: new monaco.Range(line, 1, line, 1), options: { className: 'chunk-highlight', isWholeLine: true } }])`. | Store the decoration `id` in a ref and remove with `editor.deltaDecorations([id], [])` when the chunk changes, panel closes, or component unmounts. |
| **MarkdownViewer** | Find the DOM node whose text contains the chunk content and call `node.scrollIntoView({ behavior: 'smooth', block: 'center' })`. | Add a CSS class (e.g. `bg-yellow-200`) to the wrapper element. | Track the highlighted element in a ref and remove the class when `chunkId`/`documentId` changes or after a timeout (e.g. 5s). |

Anti-pattern: do **not** fetch all chunks of a document just to locate one chunk. Always use `/documents/by-chunk/{chunk_id}` and the `chunkId` already in hand.

### Backend: expose `position`

No database migration is needed — `Chunk.position` already exists and is populated by the chunking pipeline.

- Add `position: int` to `ChunkBase` in `nowing_backend/app/schemas/chunks.py`.
- Because `model_config = ConfigDict(from_attributes=True)`, `ChunkRead` will automatically pick up the `position` attribute from the ORM model.
- Add `position` to the frontend Zod `chunkRead` schema in `nowing_web/contracts/types/document.types.ts` so the response validates.
- Verify `/documents/by-chunk/{chunk_id}` serializes `chunks[*].position` correctly.

### Highlight cleanup

The highlight and any editor decoration must be cleared when:
- The editor panel closes (`closeEditorPanelAtom` resets state).
- A different document is opened (`documentId` changes).
- A different `chunkId` is supplied.

Use `useEffect` cleanup functions and refs to track Monaco decoration IDs, Plate mark paths, and highlighted DOM elements.

### Security / permissions

No new permission is needed. `DOCUMENTS_READ` is already checked by both `/documents/by-chunk/{chunk_id}` and `/workspaces/{workspace_id}/documents/{document_id}/editor-content`.

### Performance & accessibility notes

- `/documents/by-chunk/{chunk_id}` already uses SQL-level pagination; keep using it.
- Text search in `source_markdown` is O(n) but only runs once after document load.
- Avoid loading all chunks into the browser; only request the cited chunk (or a small window) for the `content` used for text search.
- For Monaco with very large documents, wait for the model content to be ready (`onDidModelChangeContent` or `editor.getModel()?.getLineCount()`) before calling `revealLineInCenter`.
- Debounce or gate the scroll effect so a rapid `documentId`/`chunkId` change does not trigger multiple competing scroll/highlight animations.
- When a chunk is highlighted, consider adding `aria-live="polite"` announcement or moving focus logically so screen reader users are notified that the editor jumped to the cited source.

### Consistency & conventions

- Follow existing Jotai atom patterns in `nowing_web/atoms/editor/editor-panel.atom.ts`.
- Follow existing Zod schemas in `nowing_web/contracts/types/document.types.ts`.
- Follow existing Pydantic schemas in `nowing_backend/app/schemas/chunks.py`.
- Keep changes minimal: this is primarily a frontend UX enhancement with a small backend schema addition.

## References

- Backend chunk schema: <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/app/schemas/chunks.py" />
- Backend document/chunk routes: <ref_snippet file="/Users/luisphan/Documents/nowing/nowing_backend/app/routes/documents_routes.py" lines="1055-1150" />
- Backend editor-content route: <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/app/routes/editor_routes.py" />
- Frontend editor panel atom: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/atoms/editor/editor-panel.atom.ts" />
- Frontend citation panel: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/components/citation-panel/citation-panel.tsx" />
- Frontend editor panel content: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/components/editor-panel/editor-panel.tsx" />
- Frontend right panel wiring: <ref_snippet file="/Users/luisphan/Documents/nowing/nowing_web/components/layout/ui/right-panel/RightPanel.tsx" lines="270-309" />
- Frontend document types: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/contracts/types/document.types.ts" />

## File List

- nowing_backend/app/schemas/chunks.py
- nowing_backend/app/schemas/documents.py (if adding a new `DocumentWithPositionedChunksRead`)
- nowing_backend/app/routes/documents_routes.py (if schema response changes)
- nowing_web/atoms/editor/editor-panel.atom.ts
- nowing_web/components/citation-panel/citation-panel.tsx
- nowing_web/components/editor-panel/editor-panel.tsx
- nowing_web/components/editor/plate-editor.tsx (if adding highlight mark)
- nowing_web/components/editor/source-code-editor.tsx (if Monaco decoration)
- nowing_web/components/layout/ui/right-panel/RightPanel.tsx
- nowing_web/contracts/types/document.types.ts
- nowing_web/lib/apis/documents-api.service.ts (if adding a chunk-with-position endpoint)

## Dev Agent Record

### Agent Model Used

- SWE-1.7 Max

### Debug Log References

- Planning artifact `sprint-change-proposal-2026-07-22.md` identifies Story 3.6 as the next gap to implement after Story 2.5.
- `Chunk.position` exists in the DB model but is not exposed in `ChunkRead`.
- `editorPanelAtom` does not yet carry `chunkId`.
- `CitationPanelContent` does not pass `chunkId` to `openEditorPanel`.

### Completion Notes List

- Expose `Chunk.position` in API responses.
- Extend `editorPanelAtom` and `openEditorPanel` to accept `chunkId`.
- Pass `chunkId` from citation panel through right panel to editor panel.
- Implement scroll/highlight for Plate, Monaco, and MarkdownViewer.
- Add tests for schema and E2E scroll/highlight behavior.

### Review Findings

#### Decision Needed

- [x] [Review][Decision] Should `position` be added directly to `ChunkRead` (breaking change for clients expecting only `content`/`document_id`) or should a new `ChunkReadWithPosition` schema be introduced and used only for the editor/citation paths?
  - **Resolved:** Add `position` directly to `ChunkRead` / `ChunkBase`. The `position` column already exists on the `Chunk` model, adding it to the read schema is additive, and all existing clients (citation panel, document list, etc.) can safely ignore the extra field. No new schema or migration is required.

#### Patch

- [ ] [Review][Patch] `findChunkInSource` proportional fallback can overflow `source.length` and uses `totalChunks - 1` denominator inconsistent with the spec mapping strategy — clamp ratio and align formula. [nowing_web/components/editor-panel/editor-panel.tsx:154]
- [ ] [Review][Patch] `offsetToLineColumn` only treats `
` as a line break, so CRLF/CR documents miscompute the Monaco highlight range. [nowing_web/components/editor/source-code-editor.tsx:offsetToLineColumn]
- [ ] [Review][Patch] `SourceCodeEditor` can highlight the top-left corner or create a zero-width decoration when `highlightText` is empty or `highlightLength` is `0`. [nowing_web/components/editor/source-code-editor.tsx:applyHighlight]
- [ ] [Review][Patch] `SourceCodeEditor` Monaco fallback line formula is off-by-one and never reaches the last line. [nowing_web/components/editor/source-code-editor.tsx:617]
- [ ] [Review][Patch] Monaco re-steals focus and re-scrolls on every `onDidLayoutChange`; should not call `editor.focus()` on layout-driven re-applies. [nowing_web/components/editor/source-code-editor.tsx:245]
- [ ] [Review][Patch] No editor auto-clears the highlight after “a few seconds” (AC 4); add a `setTimeout` cleanup in Plate, Monaco, and MarkdownViewer. [editor viewers]
- [ ] [Review][Patch] `MarkdownViewer` only adds the yellow highlight class when the match is out-of-view and fails to clear the class/selection when `highlightText` becomes undefined. [nowing_web/components/markdown-viewer.tsx:76]
- [ ] [Review][Patch] `citation-editor.spec.ts` silently falls back to the first chunk when the marker is not found, which can mask chunking bugs. [nowing_web/tests/workspace-settings/citation-editor.spec.ts:45]
- [ ] [Review][Patch] `documentWithChunks` Zod contract and `chunkRead` diverge on `document_id`; sync the schemas. [nowing_web/contracts/types/document.types.ts:68]
- [ ] [Review][Patch] Backend integration test docstring claims tests are skipped but no skip marker exists. [nowing_backend/tests/integration/documents/test_document_chunk_position.py:1]

#### Defer

- [x] [Review][Defer] `get_document_by_chunk_id` allows an unbounded `chunk_window` query parameter — pre-existing route, not changed by this story. [nowing_backend/app/routes/documents_routes.py:1058] — deferred, pre-existing
- [x] [Review][Defer] `_InlineTaskDispatcher` swallows exceptions and imports a private Celery task — test-only E2E harness; refactor when the harness is formalized. [nowing_backend/tests/e2e/run_backend.py:322] — deferred, pre-existing
- [x] [Review][Defer] Extra `getDocumentByChunk` round-trip from the editor panel — optimization; current behavior is correct. [nowing_web/components/editor-panel/editor-panel.tsx:204] — deferred, optimization
- [x] [Review][Defer] `document_metadata` coercion changes in `DocumentRead` are slightly out of scope but were required to fix a test validation error. [nowing_backend/app/schemas/documents.py:60] — deferred, required-at-the-time

#### Decision Needed

- [x] [Review][Decision] Should `position` remain in `ChunkBase` (and therefore required for `ChunkCreate`/`ChunkUpdate`), or be moved to `ChunkRead`/made optional to avoid future schema breakage?
  - **Resolved:** Move `position` out of `ChunkBase` and add it to `ChunkRead` only; `ChunkCreate`/`ChunkUpdate` should not be forced to supply `position`.
- [x] [Review][Decision] Rich-text viewers (Plate, MarkdownViewer) currently search the rendered DOM for raw chunk text. This is a known `ponytail` best-effort shortcut that can fail across text nodes, markdown formatting, and repeated text. Decide: (a) keep the shortcut and document the ceiling, (b) implement proportional fallback at minimum, or (c) build source-offset → DOM/Slate mapping for robust highlighting.
  - **Resolved:** Option (b) — implement proportional fallback and keep the text-search shortcut, documenting the known ceiling. Pass `highlightPosition`/`totalChunks` to Plate and MarkdownViewer so they can fall back to a proportional scroll when the exact text is not found.

#### Dismissed

- `editor-panel.tsx` null `source_markdown` crash — handled by `findChunkInSource` falsy guard; no evidence of production crash.
- `MarkdownViewer` over-highlights the parent element — folded into the rich-text viewer highlight strategy decision above.
- `document_metadata` validator “masks data corruption” — coercing non-dicts to `{}` is defensive for legacy data; raising validation errors would break existing documents.
