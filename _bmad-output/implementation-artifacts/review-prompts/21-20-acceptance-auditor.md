# Acceptance Auditor Prompt — Story 21.20 Code Review

## Your Role
You are an Acceptance Auditor. Review the provided diff against the spec and any loaded context docs. Check for: violations of acceptance criteria, deviations from spec intent, missing implementation of specified behavior, contradictions between spec constraints and actual code.

## Scope
Review the uncommitted diff for Story 21.20 "Extend Multi-Source Lead Gen Adapters" in the Nowing repository.

- Diff file: `_bmad-output/review-artifacts/21-20-diff.txt`
- Spec file: `_bmad-output/implementation-artifacts/stories/21-20-extend-lead-source-adapters.md`
- Project root: `/Users/luisphan/Documents/GitHub/nowing`

## Acceptance Criteria (from the spec)
1. BĐS query triggers `MuabanBdsLeadAdapter` alongside `batdongsan` and `chotot`, calls `scrape_muaban_bds`, and returns `RawLeadRecord`s with `degraded` handling consistent with 21.19.
2. Recruitment query triggers `VnJobsLeadAdapter` calling `aggregate_jobs(..., ctx=None)` across TopCV/ITviec/VietnamWorks without self-persisting; `VietnamWorksLeadAdapter` only when query explicitly mentions "vietnamworks".
3. Public-procurement query triggers `MuaSamCongLeadAdapter` calling `MuasamcongScraper.search_tenders()` and returns company/tender leads.
4. New adapters registered; `resolve_adapters_for_intent(query)` returns the right adapters and avoids duplicate calls across `vn_jobs`/`vietnamworks`/`job_market`.
5. `ruff check` and `pytest` pass with no lint/type errors and relevant tests pass.

## Instructions
1. Read the spec (Story, Acceptance Criteria, Tasks/Subtasks, Dev Notes) and the diff.
2. For each AC, verify it is implemented correctly in the code.
3. Check for deviations, missing pieces, contradictions.
4. Output findings as a Markdown bullet list. Each bullet: one-line title, which AC/constraint it violates, and evidence from the diff (file/line).
5. Do not assign severity.
