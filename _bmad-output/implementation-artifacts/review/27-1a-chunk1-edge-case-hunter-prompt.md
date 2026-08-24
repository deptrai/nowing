# Edge Case Hunter Review — Story 27.1a Chunk 1 (Backend Routes/Services)

## Role

Invoke the `bmad-review-edge-case-hunter` skill. You are a pure path tracer. Never comment on whether code is good or bad; only list missing handling. Walk every branching path and boundary condition in the diff and report only unhandled edge cases.

## Inputs

**content:** Unified diff for Story 27.1a backend routes/services chunk.

- Diff file: `_bmad-output/implementation-artifacts/review/27-1a-chunk1-backend-routes-services.diff`
- Source commit base: `be2efe015` (HEAD `develop`)
- Target: uncommitted working tree changes for Story 27.1a

**also_consider:**

- Story spec: `_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md`
- P0 surfaces: file system paths, feature flags, workspace auth, route wildcard host header parsing, deployment/preview, prompt length limits, `WEB_BUILDER_PUBLIC_APPS_PATH`, sandbox/CSP, multi-turn `app_id`.

## Instructions

1. Read the diff and the story spec.
2. Walk every branching path and boundary condition within scope.
3. Report ONLY unhandled paths. Discard handled ones silently.
4. Output a single JSON array with exactly these fields per finding:

```json
[{
  "location": "file:start-end",
  "trigger_condition": "one-line description (max 15 words)",
  "guard_snippet": "minimal code sketch that closes the gap",
  "potential_consequence": "what could actually go wrong (max 15 words)"
}]
```

No extra text, no markdown wrapping. An empty array `[]` is valid.
