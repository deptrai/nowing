# Review Prompts — spec-36-6a-canonical-action-matrix

**Status:** Review subagents failed to launch (API 503 — inference gateway unavailable).
Run each prompt below in a separate session (ideally a different LLM), then paste findings back.

**Review content** for all three reviewers lives at:
`/Users/luisphan/.claude/jobs/2671c713/tmp/review-diff.txt`

(If that temp file is gone, regenerate with:
```
cd /Users/luisphan/Documents/GitHub/nowing
git diff e442062f12a1036e0a06e96e2c8a75f8497529e5 -- \
  nowing_backend/app/config/entities.py \
  nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py \
  nowing_backend/app/routes/social_routes.py \
  nowing_backend/tests/unit/platforms/test_xactions_mapper.py \
  nowing_backend/tests/unit/routes/test_social_routes.py > /tmp/diff.txt
cat nowing_backend/app/proprietary/platforms/xactions/action_matrix.py >> /tmp/diff.txt
cat nowing_backend/tests/unit/platforms/test_canonical_action_matrix.py >> /tmp/diff.txt
```
)

---

## Layer 1 — Blind Hunter

```
Conduct a review of CONTENT.
Look for what's missing, not only what's wrong.
Find at least ten issues to fix or improve.
Output a Markdown list of findings only — no severity, priority, or ranking.
If the content is empty, stop and say so.
If you have zero findings, re-check and keep thinking; do not stop with an empty list.

CONTENT: <paste contents of review-diff.txt here>

Do not invoke any skill. Return only the review result.
```

---

## Layer 2 — Edge Case Hunter

```
Read `/Users/luisphan/Documents/GitHub/nowing/_bmad/render/bmad-build/nowing-a18a34d834f1/3cd047fdc04df5f4706e/review-prompts/edge-case-hunter.md` completely and follow it as your review instructions.

Review content: <paste contents of review-diff.txt here>

Do not invoke any skill. If the instruction file is unreadable, report that exact failure and stop. Return only the review result.
```

---

## Layer 3 — Verification Gap

```
Read `/Users/luisphan/Documents/GitHub/nowing/_bmad/render/bmad-build/nowing-a18a34d834f1/3cd047fdc04df5f4706e/review-prompts/verification-gap.md` completely and follow it as your review instructions.

Review content: <paste contents of review-diff.txt here>

Do not invoke any skill. If the instruction file is unreadable, report that exact failure and stop. Return only the review result.
```
