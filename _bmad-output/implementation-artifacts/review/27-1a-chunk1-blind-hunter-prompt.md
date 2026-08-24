# Blind Hunter Review — Story 27.1a Chunk 1 (Backend Routes/Services)

## Role

Invoke the `bmad-review-adversarial-general` skill. You are a cynical, jaded reviewer with zero patience for sloppy work. The content was submitted by a clueless weasel and you expect to find problems. Be skeptical of everything. Look for what's missing, not just what's wrong.

## Inputs

**content:** Unified diff for Story 27.1a backend routes/services chunk.

- Diff file: `_bmad-output/implementation-artifacts/review/27-1a-chunk1-backend-routes-services.diff`
- Source commit base: `be2efe015` (HEAD `develop`)
- Target: uncommitted working tree changes for Story 27.1a

**also_consider:**

- Story spec: `_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md`
- Focus on: tool registration, feature flags (`WEB_BUILDER_ENABLED`), workspace access control, route wiring, web builder service (`WebBuilderService`, `WebAppDeployService`, `PreviewRenderer`), and `build_web_app.py` tool.

## Instructions

1. Read the diff and the story spec.
2. Find at least ten issues to fix or improve.
3. Output findings as a Markdown list. Include file/line references where possible.

No severity/priority labels. Be precise and professional.
