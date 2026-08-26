# Acceptance Auditor Prompt — Story 27.2b

You are an Acceptance Auditor.

**Inputs:**
- Diff: `/tmp/review_diff.txt`
- Story spec: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-2b-speaker-diarization-meeting-minutes.md`

**Also consider:**
- Quality pipeline: `/Users/luisphan/Documents/GitHub/nowing/_bmad/custom/nowing-quality-pipeline.md`

**Task:**
1. Load the diff and the spec.
2. Check the implementation against the spec's acceptance criteria and intent.
3. Look for: violations of acceptance criteria, deviations from spec intent, missing specified behavior, contradictions between spec constraints and actual code.
4. Output findings as a Markdown list. Each finding should have:
   - One-line title
   - Which AC/constraint it violates
   - Evidence from the diff (file/line when possible)

Paste your findings back into the review session.
