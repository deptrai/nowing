---
status: draft
epic: 27
frs: [FR-93, FR-94]
stories: [27-1a, 27-2a, 27-2b]
updated: 2026-08-24
---

# UX Contract — Epic 27 Autonomous Workstation

**Phạm vi:** UX cho Web Builder chat mode, Presentation Studio (PPTX/Marp), và Speaker Diarization Meeting Minutes.
**Bám vào:** FR-93 · FR-94 · AD-113 · AD-114 · Story 27.1a · Story 27.2a · Story 27.2b · `DESIGN.md` · `EXPERIENCE.md`
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI bắt buộc cho Epic 27.

---

## User Outcome

After Epic 27, a sales, marketing, or project-management user can create and manage three kinds of generative deliverables directly from the Nowing chat interface:

- **Web Builder:** Describe a single-page sales/marketing page, preview it in a sandboxed iframe, mark/annotate an element, and publish it to `https://{slug}.apps.nowing.net` with one click. A custom CNAME can be added for owned domains.
- **Presentation Studio:** Describe a slide deck (or point the agent at a doc/URL), choose PPTX or Marp output, and download or preview the deck. The user can ask the agent to re-generate from feedback in the same thread.
- **Meeting Minutes:** Paste an audio URL (or select an already-uploaded audio `Document`) and receive a structured meeting-minutes deliverable with speaker-labeled transcript, summary, and action items.

All three flows are chat-first, gated by feature flags and workspace plan, and support right-to-delete. The deliverable card in chat is the primary surface; the Web Builder also exposes a standalone editor/preview/publish page.

---

## Key Flows

### Flow 1: Web Builder MVP — Mai (Marketing Lead)

1. **Intake.** Mai opens a new chat and sees the quick chip **"Build a landing page"**. She clicks it. The thread is created with `platform_metadata: { "web_builder_mode": true }` and the composer is pre-filled with a sales/marketing prompt template.
2. **Prompting.** Mai types "Landing page for a B2B sales course in Vietnamese." The agent uses the web-builder system prompt and the `build_web_app` tool.
3. **Generation.** A deliverable card appears in the chat showing `app_id`, `name`, `slug`, `preview_url`, and `public_url` (empty until published).
4. **Preview.** Mai clicks the card or the **Open** CTA. The standalone page `/dashboard/[workspace_id]/web-builder?app_id=xxx` loads a preview iframe, file tree, code viewer, and **Publish** button.
5. **Mark and iterate.** Mai hovers over a section in the iframe and the Mark Tool bounding-box selector appears. She clicks an element and types "Make the headline larger and more assertive." The agent re-generates the page; the card updates to the new version. In MVP the selector is a visual annotator; AST mutation itself is out of scope.
6. **Publish.** Mai clicks **Publish**. A publish drawer confirms the public URL `https://{slug}.apps.nowing.net`. She can optionally open the custom CNAME modal to add an owned domain.
7. **Outcome.** The page is live and world-readable. The deliverable card shows `status="published"` and the public URL.

If Mai asks for a multi-page site, complex backend, or database, the agent returns a scope message: v1 supports single-page sales/marketing sites only, then offers the closest template.

### Flow 2: Presentation Studio — Anh Minh (Sales Lead)

1. **Intake.** Anh Minh sees quick chips **"Create a pitch deck (PPTX)"** and **"Create Marp slides"**. He picks one. The thread is created with `platform_metadata: { "presentation_studio_mode": true }`.
2. **Prompting.** He types "5-slide sales pitch for our B2B CRM from this quarterly report" and optionally pastes a source URL.
3. **Generation.** The agent calls `generate_presentation` with `output_format` set by the chosen entry point. A deliverable card appears in chat showing title, format, slide count, and CTAs.
4. **Preview.** For PPTX, the primary CTA is **"Download .pptx"** with a secondary **"Open in Slides"** link. For Marp, the card can show a rendered HTML preview if `marp-cli` is installed; otherwise it shows **"Download .md"** and a helper line: *"Open this file in Marp for VS Code / Marp Web."*
5. **Re-generate.** Anh Minh types feedback in the same thread, e.g. "Add a pricing slide." The agent calls `generate_presentation` again and updates the deliverable card. In MVP slide preview does not expose the bounding-box Mark Tool; the design view/mark canvas is reused from the Web Builder iframe for `web_app` deliverables only.
6. **Outcome.** Anh Minh downloads the final deck or copies the preview/download link.

### Flow 3: Speaker Diarization Meeting Minutes — Chị Hương (Project Manager)

1. **Intake.** Chị Hương clicks the quick chip **"Summarize a meeting"** or types `/meeting`. The thread is created with `platform_metadata: { "meeting_minutes_mode": true }` and the composer shows the placeholder: *"Paste the meeting recording URL here."*
2. **Input.** She pastes a public audio URL or selects an already-uploaded audio `Document`. A subtle privacy caption appears: *"The recording is not stored after processing; only the transcript and minutes are kept."*
3. **Processing.** The agent calls `generate_meeting_minutes`, creates a `MeetingMinutes` row with `status="processing"`, and enqueues a Celery worker. The chat card shows a processing indicator immediately.
4. **Zero sync updates.** The deliverable card receives real-time status updates via Zero sync. If Zero is unavailable, the frontend polls `GET /api/v1/meeting-minutes/{id}` every 2 seconds.
5. **Ready.** When the worker completes, the card expands to show the meeting title, summary, action items grouped by speaker, and a transcript section.
6. **Transcript.** Chị Hương expands the transcript to see segments labeled `Speaker A`, `Speaker B`, etc. If diarization is unavailable, the transcript shows a single `Speaker 1` label and a `degraded` notice: *"Transcript ready, but speaker labels are unavailable."*
7. **Download and delete.** She downloads the minutes as Markdown or deletes the deliverable. The original audio temp file and `Document` blob are removed after processing; deleting the row is supported through `DELETE /api/v1/meeting-minutes/{id}`.

---

## Screens / Surfaces

| Screen | Purpose | Source / Owner |
|---|---|---|
| **Chat input mode picker** | Quick chips and slash templates for Web Builder, Presentation Studio, and Meeting Minutes; handles `?mode=` query params. | `components/new-chat/prompt-picker.tsx`, `components/assistant-ui/thread.tsx`, `app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx` |
| **Deliverable card (`web_app`)** | Shows generated app metadata, **Open**, **Publish**, and **Copy URL** CTAs; live status badge. | `components/tool-ui/web-builder.tsx`, `BODY_TOOLS` in `components/assistant-ui/assistant-message.tsx` |
| **Deliverable card (`presentation`)** | Shows title, format (PPTX/Marp), slide count, **Download** / **Preview** CTAs; loading, ready, failed, or degraded states. | `components/tool-ui/presentation.tsx`, `BODY_TOOLS` in `components/assistant-ui/assistant-message.tsx` |
| **Deliverable card (`meeting_minutes`)** | Shows title, status, summary, action items, expandable transcript, and **Download Markdown** CTA. | `components/tool-ui/meeting-minutes.tsx`, `BODY_TOOLS` in `components/assistant-ui/assistant-message.tsx` |
| **Preview iframe** | Sandboxed live preview of a generated web app or Marp HTML render. | `/dashboard/[workspace_id]/web-builder?app_id=...` |
| **Design view / mark canvas** | Bounding-box selector overlay on the preview iframe; user selects an element and types a change request. | `WebBuilderPage` + `MarkToolOverlay` |
| **Publish drawer** | Confirms public URL, deploys the static HTML snapshot, and reports success/failure. | `WebBuilderPage` |
| **Custom CNAME modal** | Input owned domain, validate DNS/SSL, and show the required CNAME record. | `CnameModal` |
| **Meeting minutes viewer** | Collapsible surface: summary + action items + speaker-labeled transcript + download/delete. | `components/tool-ui/meeting-minutes.tsx` and optional standalone viewer |
| **Artifacts panel** | Lists all workspace deliverables grouped by kind: **Web Apps**, **Slide Decks**, **Meeting Minutes**. | `features/chat-artifacts/ui/artifacts-panel.tsx`, `features/chat-artifacts/ui/artifact-row.tsx` |

---

## Component Patterns

### Existing components to extend

- **`components/assistant-ui/assistant-message.tsx`**: add `build_web_app`, `generate_presentation`, and `generate_meeting_minutes` to `BODY_TOOLS` and `ARTIFACT_TOOL_KINDS` so each deliverable renders as a first-class body card.
- **`features/chat-artifacts/model/artifact.ts`**: extend `ArtifactKind` and `ARTIFACT_TOOL_KINDS` with `web_app`, `presentation`, and `meeting_minutes`.
- **`features/chat-artifacts/ui/artifact-row.tsx`**: render rows for the three new kinds with the correct icon, status badge, and primary CTA.
- **`features/chat-artifacts/ui/artifacts-panel.tsx`**: update `GROUP_ORDER` and `KIND_META` so that **Web Apps**, **Slide Decks** (formerly grouped under `presentation`), and **Meeting Minutes** appear in a stable order. Rename the existing `video` group to **Video Presentations** to avoid collision with the new `presentation` group.
- **`features/chat-artifacts/lib/collect-artifacts.ts`**: add `describeArtifact` cases for `web_app`, `presentation`, and `meeting_minutes`.
- **`components/new-chat/prompt-picker.tsx`**: extend `PromptPickerAction`/`BuiltinPromptItem` from a boolean `isWebBuilder` to a `mode` string (`web_builder`, `presentation_studio`, `meeting_minutes`) and add slash templates: `/web`, `/slides pptx`, `/slides marp`, `/meeting`.
- **`app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx`**: handle `?mode=web_builder`, `?mode=presentation_studio`, and `?mode=meeting_minutes` query parameters and create the thread with the correct `platform_metadata`.

### New components required

- **`components/tool-ui/web-builder.tsx`** — `GenerateWebAppToolUI`: renders the `web_app` deliverable card with Open, Publish, Copy URL, and error/degraded states.
- **`components/tool-ui/presentation.tsx`** — `GeneratePresentationToolUI`: renders the `presentation` deliverable card with format icon, slide count, download/preview CTAs, and PPTX/Marp-specific hints.
- **`components/tool-ui/meeting-minutes.tsx`** — `MeetingMinutesToolUI`: renders the `meeting_minutes` card with summary, action items, expandable transcript, and download/delete CTAs.
- **`app/dashboard/[workspace_id]/web-builder/page.tsx`** — standalone Web Builder surface with preview iframe, file tree, code viewer, **Publish** button, and **Custom CNAME** trigger.
- **`MarkToolOverlay`** — a transparent overlay on the preview iframe that draws a bounding box around hovered/clicked elements and captures the user's annotation as a new chat prompt.
- **`PublishDrawer`** — slide-out drawer for confirming and triggering `WebAppDeployService.deploy_app`.
- **`CnameModal`** — modal for entering and validating a custom CNAME.

### Design token usage

- Deliverable cards use `colors.surface-card` (`#FFFFFF`) with `1px solid {colors.border}` (`#E2E8F0`) and `rounded.xl` (`16px`) when shown as a floating card; `rounded.md` (`8px`) inside the chat stream.
- Status badges use `colors.status-active` (`#10B981`) for ready/published, `colors.status-warning` (`#F59E0B`) for processing/degraded, and `colors.fit-score-low` (`#EF4444`) for failed.
- Headings inside cards use `typography.heading-2`; body text and captions use `typography.body` and `typography.caption`; code/slugs use `typography.mono`.
- Primary CTAs use `colors.primary` (`#10B981`) background with `colors.primary-foreground` (`#FFFFFF`); hover uses `colors.primary-hover` (`#059669`).

---

## State Patterns

| Deliverable | State model | UI treatment |
|---|---|---|
| **Web app** | `generating` → `generated` → `publishing` → `published` / `failed` | Shimmer skeleton in card while `generating`; iframe loads `preview_url` when `generated`; publish drawer shows `publishing` spinner, then `published` URL. |
| **Presentation** | `generating` → `ready` / `failed` / `degraded` | Progress text *"Designing your slides..."* while generating; ready card shows download/preview CTAs; degraded card shows a helper line and a fallback download. |
| **Meeting minutes** | `pending` → `processing` → `ready` / `failed` / `degraded` | Card created immediately with `processing` status; Zero-sync or 2-second polling updates it; ready card expands to summary + action items; degraded card shows transcript under a single speaker and a clear notice. |

### Right-to-delete

- A `DELETE` action is available on every deliverable card and in the standalone list for `MeetingMinutes`, `SlidePresentation`, and `WorkspaceApp`.
- Deleting a `MeetingMinutes` row also removes the rendered Markdown cache; the original audio `Document` and temp file are already removed after processing per AD-28.3.
- Deleting a `WorkspaceApp` unpublishes the static HTML and frees the `*.apps.nowing.net` slug.

### Zero sync vs polling fallback

- `WorkspaceApp`, `SlidePresentation`, and `MeetingMinutes` should be added to `app/zero_publication.py` with a lightweight column list (id, workspace_id, thread_id, status, title, error, updated_at) so the deliverable card updates in real time.
- If Zero sync is unavailable (self-host without `zero-cache`, 401, or timeout), the frontend falls back to polling the relevant `GET /api/v1/.../{id}` endpoint every 2 seconds while the status is not terminal.

---

## Interaction Primitives

- **Chat trigger.** Three entry points are functionally equivalent: quick chip, slash prompt, and URL query (`?mode=web_builder&q=...`, `?mode=presentation_studio&q=...`, `?mode=meeting_minutes&q=...`).
- **Deliverable card expand.** Clicking the card header or **Expand** CTA toggles the full body; `Esc` collapses. Keyboard: `Enter` or `Space` on the focused card header expands it.
- **Preview iframe sandbox.** The iframe uses a `sandbox` attribute appropriate for generated content (e.g. `allow-scripts allow-same-origin` for the Web Builder preview) and a CSP that allows CDN assets (`default-src 'self' https:`). CDN failure must show a graceful fallback instead of a blank screen.
- **Mark tool bounding box selector.** Hover highlights an element with a 2px `colors.primary` (`#10B981`) outline; click selects it and opens a small inline prompt input. The selected element is referenced in the next user prompt, e.g. *"Change the selected hero headline."* Multi-select is out of scope for MVP.
- **CNAME input.** Validates the domain string, shows the required DNS record (`CNAME {slug}.apps.nowing.net` or custom target), and reports SSL provisioning status. Errors are shown inline; success returns to the publish drawer.
- **Download / publish primary actions.** Primary CTA uses `colors.primary`; disabled states use `colors.foreground-subtle` (`#94A3B8`) on `colors.surface-subtle` (`#F8FAFC`).

---

## Accessibility Floor

- **Keyboard navigation.** Quick chips, slash prompts, and deliverable cards are reachable with `Tab`. `Enter` activates; `Esc` collapses cards and closes drawers/modals.
- **Screen reader labels.** Each deliverable card announces its kind, title, and status, e.g. "Web app [name], status published, public URL [url]." Speaker labels are announced as "Speaker A" or "Speaker 1" via `aria-label`. Status changes use `aria-live="polite"`.
- **Focus management in iframe.** When the standalone Web Builder loads, focus is placed on the preview frame wrapper or the first focusable control. `Esc` from a modal/drawer returns focus to the trigger. The Mark Tool overlay must trap focus while active.
- **Contrast and color.** All text on `surface-card` (`#FFFFFF`) uses `foreground` (`#0F172A`) or `foreground-muted` (`#475569`) and meets WCAG 2.1 AA. Status badges use the semantic `status-*` color pairs from `DESIGN.md`.
- **Reduced motion.** Shimmer/progress animations respect `prefers-reduced-motion`; static labels are shown as fallback.

---

## Open Questions

The following UX decisions are not yet made and should be resolved before the contract is marked final:

1. **SEO fields for web builder.** Should the publish drawer expose title, meta description, OG image, and favicon inputs, or should they be inferred from the generated page?
2. **Analytics toggle.** Should each published web app include a PostHog snippet, and who controls the toggle (workspace owner, app creator, global admin)?
3. **Slide export formats beyond PPTX/Marp.** Do we need PDF export, Google Slides import, or PowerPoint online?
4. **Mark tool scope in MVP.** Is the visual selector allowed only to produce a re-generation prompt, or should it drive an AST mutator as described in AD-114? Story 27.1a currently keeps AST mutation out of scope.
5. **Custom CNAME validation flow.** Does the user add a TXT record for ownership, a CNAME record, or both? How is SSL renewal surfaced in the UI?
6. **Audio upload in the chat composer.** The composer currently supports only image attachments. When should direct audio upload be enabled?
7. **Meeting minutes retention.** Transcripts are kept in the `MeetingMinutes` row; how long should they live, and should workspace deletion cascade?
8. **Plan gating display.** Which workspace roles can create/publish/delete these deliverables? Should `Editor` have a `WEB_BUILDER_CREATE` permission?
9. **Speaker label naming.** Can the user rename `Speaker A`/`Speaker 1` to real names, and should that rename persist across re-generations?
10. **CDN fallback for published web apps.** If React/Babel/Tailwind CDN scripts fail, should the page show plain HTML, a retry CTA, or an offline-friendly bundle?

---

## References

- **PRD:** `planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §4.10 (FR-93, FR-94)
- **PRD Amendment:** `planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`
- **Architecture spine:** `planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` §8 (AD-111–AD-115)
- **Design tokens:** `planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md`
- **Experience spine:** `planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md`
- **Feature audit:** `planning-artifacts/manus-nowing-feature-audit-2026-08-20.md`
- **Story 27.1a:** `implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md`
- **Story 27.2a:** `implementation-artifacts/stories/27-2a-manus-slides-presentation-studio-chat.md`
- **Story 27.2b:** `implementation-artifacts/stories/27-2b-speaker-diarization-meeting-minutes.md`
