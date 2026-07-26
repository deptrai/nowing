---
name: bmad-nowing-test-first-atdd
description: Test-first ATDD cho Nowing — human/AI viết description skeleton (WHAT) trước, body (HOW) implement từ spec KHÔNG phải từ implementation. Apply 6 Anti-Pattern Checklist per acceptance criterion. Use when user says "write tests test-first for {story}" or "ATDD skeleton" for Nowing. Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Nowing Test-First ATDD — Description Skeleton + 6 Anti-Pattern Checklist

## Overview

ATDD thông thường: AI viết cả description lẫn body → mirror implementation → test pass nhưng không phát hiện bug. Test-First ATDD đảo ngược: description skeleton (WHAT) viết trước, AI implement body (HOW) từ **spec** chứ không phải từ implementation.

Mandatory: Apply 6 Anti-Pattern Checklist (xem `docs/nowing-mutation-gate-reference.md`) cho mỗi AC — đảm bảo test cover mirror, mock, edge case, arithmetic, error message, SQL execution. Port từ `chainlens-research/skills/bmad-test-first-atdd`.

## Persona

Bạn là test architect tin rằng "test description quan trọng hơn test body". Description sai → body vô dụng. Viết description sắc bén, mỗi description nhắm một anti-pattern cụ thể. Không bao giờ đọc implementation khi viết description — chỉ đọc spec/AC.

## Conventions

- Pipeline source of truth: `{project-root}/_bmad/custom/nowing-quality-pipeline.md`
- Reference doc: `{project-root}/docs/nowing-mutation-gate-reference.md` — 6 anti-pattern + P0 surfaces
- Output: `{project-root}/_bmad-output/test-artifacts/atdd-checklist-{story_key}.md` (titles only, KHÔNG viết `assert`)
- Story file: `{implementation_artifacts}/{story-key}.md`
- Test conventions (Nowing backend, từ `nowing_backend/tests/README.md`): pytest markers `unit` (no DB) / `integration` (real Postgres) / `memory`; layout type-first module-mirrored dưới `tests/unit/` và `tests/integration/`
- Communication language: load từ `_bmad/bmm/config.yaml` (`communication_language`)

## On Activation

1. Load `{project-root}/_bmad/custom/nowing-quality-pipeline.md` + `docs/nowing-mutation-gate-reference.md`
2. Load config `communication_language`
3. Identify target story từ user's request
4. Read story AC + Challenge Log (từ `bmad-nowing-grill-me`, nếu có)
5. Run mandatory sequence (6 anti-pattern checklist per AC)

## Mandatory Sequence

### Step 1 — Parse AC + Challenge Log

Đọc story file, list tất cả Acceptance Criteria. Merge edge cases/failure modes từ Challenge Log (`bmad-nowing-grill-me` output, nếu tồn tại).

### Step 2 — Apply 6 Anti-Pattern Checklist per AC

Cho mỗi AC, sinh test description (title only, KHÔNG viết assertion body):

**Pattern 1 — Mirror Test**:
- "should return exactly fields `{field1, field2, field3}`"
- "should NOT return field `{sensitiveField}`"
- "should resolve model `{input}` to spec `{expectedSpecValue}` (not `{wrongValue}`)"

**Pattern 2 — Over-Mocking**:
- "should handle `{dep}` throwing `{ErrorType}`" (ví dụ: OpenRouter timeout, Postgres connection error, embedding service down)
- "should handle `{dep}` returning `None`"
- "should handle `{dep}` returning empty `[]`"

**Pattern 3 — Happy Path Only**:
- Boundary: "should handle `{param}` exactly at `{MAX}`", "below `{MIN}`", "above `{MAX}`" (ví dụ: quota limit, credit balance = 0)
- Null/empty: "should handle `None` `{param}`", "empty string", "whitespace only"
- Concurrent: "should handle double-submit (idempotent — second call no-op)" — quan trọng cho token/credit deduction

**Pattern 4 — Arithmetic Not Asserted**:
- "should compute `{result}` as exactly `{value}` when inputs are `{specific values}`"
- "should compute `cost_micros` as exactly `{X}` when `{tokens=Y, rate=Z}`"

**Pattern 5 — Error Message Not Asserted**:
- "should raise `{ExceptionType}` with message containing `{key phrase}`" (ánh xạ tới `NowingError.code`/`message` trong `app/exceptions.py`)
- "should return error envelope with `code={ERROR_CODE}` and `status={N}`"

**Pattern 6 — SQL Mock Not Executed**:
- "should execute query and return rows with columns `{id, title, created_at}` (integration, real DB)"
- "should respect FK constraint — insert with non-existent `{fk}` → raises IntegrityError"
- "should respect UNIQUE constraint — duplicate `{(user_id, workspace_id)}` → raises IntegrityError"

### Step 3 — Output checklist

Write `_bmad-output/test-artifacts/atdd-checklist-{story_key}.md`:

```markdown
# ATDD Checklist — {story_key}

## AC-1: {AC description}

### Pattern 1 (Mirror)
- [ ] should return exactly fields `{...}`
- [ ] should NOT return field `{...}`

### Pattern 2 (Over-Mocking)
- [ ] should handle `{dep}` throwing `{ErrorType}`
- [ ] should handle `{dep}` returning `None`

### Pattern 3 (Edge cases)
- [ ] Boundary: {list}
- [ ] Null/empty: {list}
- [ ] Concurrent: {list}

### Pattern 4 (Arithmetic)
- [ ] should compute `{result}` as exactly `{value}` when {inputs}

### Pattern 5 (Error message)
- [ ] should raise `{ExceptionType}` with message containing `{phrase}`

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should execute query and return rows {columns} (integration, real DB)

## AC-2: ...
```

### Step 4 — Downstream handoff

Sau khi bodies implemented (bởi `bmad-testarch-atdd` red phase + `bmad-nowing-integration-test`), invoke `bmad-nowing-mutation-gate` để verify effectiveness.

## The destination

- **Output**: `_bmad-output/test-artifacts/atdd-checklist-{story_key}.md`
- **Consumer**: `bmad-testarch-atdd` [BMAD core] (unit test bodies, mock DB) + `bmad-nowing-integration-test` (Pattern 6, real Postgres)
- **Bar**: Mỗi AC có ít nhất 1 description per applicable pattern. Pattern 6 descriptions flagged riêng cho integration-test.

## Cross-links — where this skill sits in the workflow

| Direction | Skill | Relationship |
|-----------|-------|--------------|
| Input from | `bmad-nowing-grill-me` | Challenge Log edge cases + failure modes merged vào checklist |
| Output to | `bmad-testarch-atdd` [BMAD core] | Red phase unit test bodies (mock DB) |
| Output to | `bmad-nowing-integration-test` | Pattern 6 descriptions → integration test với Postgres thật |
| Output to | `bmad-nowing-mutation-gate` | Sau khi bodies implemented → verify effectiveness |

## Next steps in Nowing quality pipeline

| Step | Skill | When |
|------|-------|------|
| 4.4 → 4.5 | `bmad-testarch-atdd` [BMAD core] | Red phase unit test bodies (mock DB) |
| 4.4 → 4.6 | `bmad-nowing-integration-test` | Nếu Pattern 6 (SQL) descriptions tồn tại, integration test với Postgres thật |
| 4.5+4.6 → 4.7 | `bmad-dev-story` / `bmad-quick-dev` | Green phase |

## Full workflow map

```
grill-me → test-first-atdd → [testarch-atdd + nowing-integration-test] →
dev-story → code-review → testarch-test-review → nowing-mutation-gate →
testarch-trace → testarch-nfr → nowing-human-review-gate →
nowing-web-e2e-gate → retrospective
```
