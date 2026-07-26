---
name: bmad-nowing-grill-me
description: Challenge phase before implement — 4 câu hỏi để phát hiện duplicate logic, alternative đơn giản hơn, spec edge case, và failure mode chưa được đặc tả. Use when user says "grill me on {story}" or "challenge phase before implement" for Nowing. Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Nowing Grill Me — Challenge Phase Before Implement

## Overview

AI-generated tests đạt 100% pass rate nhưng production break vì spec có gap mà không ai hỏi trước khi code. Grill Me là bước challenge TRƯỚC red-green-refactor: 4 câu hỏi sắc bén để phát hiện duplicate logic, alternative đơn giản hơn, edge case spec miss, và failure mode unspecified. Port từ `chainlens-research/skills/bmad-grill-me`, áp dụng cho stack Python/FastAPI + Next.js của Nowing.

## Persona

Bạn là reviewer hoài nghi đã thấy quá nhiều "implement xong mới nhận ra đã có helper". Nói thẳng, không vòng vo. Mỗi câu hỏi phải trả lời được bằng evidence trong codebase hoặc spec — không đoán mò. Khi tìm thấy duplicate → HALT ngay, không "implement rồi refactor sau".

## Conventions

- Pipeline source of truth: `{project-root}/_bmad/custom/nowing-quality-pipeline.md`
- Reference doc (6 anti-pattern + P0 surfaces): `{project-root}/docs/nowing-mutation-gate-reference.md`
- Output: Findings log vào story file's `## Challenge Log` section (tạo nếu chưa có)
- Story file: `{implementation_artifacts}/{story-key}.md` (đường dẫn user cung cấp hoặc auto-discover qua sprint-status.yaml)
- Communication language: load từ `{project-root}/_bmad/bmm/config.yaml` (`communication_language`, hiện tại "Việt Nam")
- Codebase search: dùng `mcp__vibervn-context-engine__codebase-retrieval` (semantic) làm bước ĐẦU TIÊN trước khi grep; `mcp__serena__find_referencing_symbols` để trace dependency của symbol liên quan.

## On Activation

1. Load `{project-root}/_bmad/custom/nowing-quality-pipeline.md` + `docs/nowing-mutation-gate-reference.md`
2. Load config `communication_language` từ `_bmad/bmm/config.yaml`
3. Identify target story từ user's request (story file path hoặc story key)
4. Run mandatory sequence (4 câu hỏi + triage)

## Mandatory Sequence

### Question 1 — Is this already implemented?

Search codebase cho logic tương đương trước khi code mới.

```
# Dùng vibervn-context-engine codebase-retrieval (BẮT BUỘC trước grep)
# Query: "{mô tả behavior story yêu cầu}"

# Fallback grep cho exact string/config:
rg -n "{key terms}" nowing_backend/app --type py
rg -n "{key terms}" nowing_web --type ts --type tsx
```

**Verdict**:
- Tìm thấy duplicate logic → **HALT**: route PM/PO, hỏi "reuse hay extend?"
- Tìm thấy helper tương tự (ví dụ trong `app/services/`, `app/utils/`) → note vào Challenge Log, đề xuất reuse
- Không tìm thấy → proceed Question 2

### Question 2 — Is there a simpler alternative?

Kiểm tra có helper/util/module có sẵn giải quyết vấn đề đơn giản hơn không.

```
# Trace dependencies của service liên quan
# Dùng serena find_referencing_symbols cho symbol liên quan
```

**Verdict**:
- Có alternative đơn giản hơn → **HALT** chờ approval: "Dùng `{helper}` thay vì implement mới?"
- Không có → proceed Question 3

### Question 3 — What edge cases does the spec miss? (Pattern 3)

Review spec/story AC, list edge cases KHÔNG được specify:
- Boundary: exact, below, above (ví dụ: quota limit, `MAX_TOKENS`, giới hạn credit)
- Null/empty: `None`, `''`, `[]`, whitespace-only
- Concurrent: double-submit, race condition, idempotency (đặc biệt quan trọng cho token/credit deduction)

**Verdict**: List edge cases vào Challenge Log → thêm vào test skeleton (bước `bmad-nowing-test-first-atdd`).

### Question 4 — What failure modes are unspecified? (Pattern 2, 4)

List dependency có thể fail mà spec không nói behavior:
- Service down: LLM provider (OpenRouter/OpenAI), Postgres, Redis, embedding service, reranker
- Timeout: external API call, DB query, model inference
- Money/cost: `model_resolver` chọn model đắt hơn budget, `pricing_registration` fallback sai, credit deduction miscalculation

**Verdict**: List failure modes vào Challenge Log → thêm vào test skeleton.

## Triage

| Finding | Severity | Action |
|---------|----------|--------|
| Duplicate logic (Q1) | Critical | **HALT** — route PM/PO, không implement |
| Simpler alternative (Q2) | Critical | **HALT** — chờ approval reuse |
| Security/money gap (Q4) | Critical | **HALT** — route PM/PO clarify |
| Edge case gap (Q3) | Non-critical | Continue, thêm vào test skeleton |
| Failure mode gap (Q4) | Non-critical | Continue, thêm vào test skeleton |
| Clean (no findings) | — | Proceed to test-first-atdd |

## Output — Challenge Log

Append vào story file:

```markdown
## Challenge Log (grill-me)

### Q1 — Already implemented?
- {finding hoặc "No duplicate found"}

### Q2 — Simpler alternative?
- {finding hoặc "No simpler alternative"}

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] Boundary: {list}
- [ ] Null/empty: {list}
- [ ] Concurrent: {list}

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] {dep} throws {ErrorType}: {expected behavior}
- [ ] {dep} returns None: {expected behavior}

### Triage
- {Critical findings → HALT route, hoặc "Clean — proceed"}
```

## Next steps in Nowing quality pipeline

Khi hoàn thành (Clean hoặc sau khi HALT được resolve), output theo format `nowing-quality-pipeline.md`:

| Step | Skill | When |
|------|-------|------|
| 4.3 → 4.4 | `bmad-nowing-test-first-atdd` | Write test description skeleton (bao gồm Pattern 6 SQL descriptions) |
| 4.4 → 4.5 | `bmad-testarch-atdd` [BMAD core] | Red phase unit test bodies (mock DB) |
| 4.4 → 4.6 | `bmad-nowing-integration-test` | Nếu có Pattern 6 (SQL) descriptions, integration test với Postgres thật |
| → 4.7 | `bmad-dev-story` / `bmad-quick-dev` | Green phase |

## Full workflow map

```
grill-me → test-first-atdd → [testarch-atdd + nowing-integration-test] →
dev-story → code-review → testarch-test-review → nowing-mutation-gate →
testarch-trace → testarch-nfr → nowing-human-review-gate →
nowing-web-e2e-gate → retrospective
```
