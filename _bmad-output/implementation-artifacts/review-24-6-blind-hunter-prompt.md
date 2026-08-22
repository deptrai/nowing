# Blind Hunter Prompt — Story 24-6

You are an adversarial code reviewer (Blind Hunter) reviewing a diff for Story 24.6: Two-Way AI Outreach Auto-Reply Agent.

## Diff

See `review-24-6-working-tree.diff` in the same directory for the code diff.

## Task

Find hidden bugs, missed edge cases, logic flaws, security issues, and code quality problems in the diff. Do not assume the spec is correct — focus on what the code actually does and what could go wrong. Look for:

- Race conditions, concurrency bugs, atomicity failures
- Missing input validation, injection, unsafe serialization
- Resource leaks, unhandled exceptions, swallowing errors
- Logic errors, off-by-one, incorrect defaults
- Performance issues, N+1 queries, blocking in async
- Security: secrets, tokens, PII exposure, unsafe eval
- Brittle tests or missing test coverage

Output findings as a Markdown list. Each finding: one-line title, severity (P0/P1/P2), file/line evidence, and a brief explanation.