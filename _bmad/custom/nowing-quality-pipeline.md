# Nowing Quality Pipeline — Source of Truth

**Mục đích:** Định nghĩa full quality pipeline cho Nowing (Python FastAPI backend + Next.js frontend). Đây là bản port của `chainlens-research/_bmad/custom/chainlens-quality-pipeline.md`, chỉnh cho stack Nowing (pytest/cosmic-ray thay vì bun:test/Stryker, Playwright cho `nowing_web`). Mọi BMad skill Phase 4 MUST load file này qua `persistent_facts` và MUST output "Next steps" section khi complete — đây chính là cơ chế tự động chain skill, không cần user tự gọi từng skill.

**Nguyên tắc:**
- **BẮT BUỘC (REQUIRED):** không skip được — story không done nếu thiếu
- **Recommended:** nên làm, skip nếu có lý do (doc-only story, hotfix, non-P0)
- **P0-gated:** chỉ BẮT BUỘC khi story touch P0 areas (token/credit, auth, provider/model routing, pricing, RAG/connector sync)

---

## Phase 1 — Analysis (optional, skip nếu PRD đã có)

| # | Bước | Skill | Mức |
|---|---|---|---|
| 1.1 | Brainstorm | `bmad-brainstorming` | Optional |
| 1.2 | Market/Domain/Technical Research | `bmad-market-research` / `bmad-domain-research` / `bmad-technical-research` | Optional |
| 1.3 | Product Brief HOẶC PRFAQ | `bmad-product-brief` / `bmad-prfaq` | Optional |

## Phase 2 — Planning (REQUIRED)

| # | Bước | Skill | Mức |
|---|---|---|---|
| 2.1 | PRD | `bmad-prd` (create) | **BẮT BUỘC** |
| 2.2 | UX Design | `bmad-ux` | Recommended (UI features) |

## Phase 3 — Solutioning (REQUIRED)

| # | Bước | Skill | Mức |
|---|---|---|---|
| 3.1 | Architecture | `bmad-architecture` | **BẮT BUỘC** |
| 3.2 | Epics & Stories | `bmad-create-epics-and-stories` | **BẮT BUỘC** |
| 3.3 | Implementation Readiness | `bmad-check-implementation-readiness` | **BẮT BUỘC** |
| 3.4 | Test Design | `bmad-testarch-test-design` | Recommended |
| 3.5 | Test Framework | `bmad-testarch-framework` | Recommended |
| 3.6 | CI Setup | `bmad-testarch-ci` | Recommended |

## Phase 4 — Implementation (REQUIRED) — Story Cycle

### Kickoff

| # | Bước | Skill | Mức |
|---|---|---|---|
| 4.0 | Sprint Planning | `bmad-sprint-planning` | **BẮT BUỘC** |

### Per-story cycle (lặp cho mỗi story)

| # | Bước | Skill | Mức | Khi nào apply |
|---|---|---|---|---|
| 4.1 | Create Story | `bmad-create-story` (create) | **BẮT BUỘC** | Mọi story |
| 4.2 | Validate Story | `bmad-create-story` (validate) | Recommended | Mọi story |
| 4.3 | Grill Me — challenge phase (4 câu hỏi) | `bmad-nowing-grill-me` | Recommended | Story không hiển nhiên (duplicate logic risk, spec gap risk) |
| 4.4 | Test-first ATDD skeleton | `bmad-nowing-test-first-atdd` | Recommended | Story có acceptance criteria |
| 4.5 | ATDD red-phase (unit test bodies, mock DB) | `bmad-testarch-atdd` [BMAD core] | Recommended | Story có acceptance criteria |
| 4.6 | Integration test (real Postgres) | `bmad-nowing-integration-test` | **P0-gated** | Story chạm SQL/DB logic (Pattern 6) |
| 4.7 | Dev Story (implement + unit tests) | `bmad-dev-story` | **BẮT BUỘC** | Mọi story |
| 4.8 | Code Review (3-layer adversarial) | `bmad-code-review` | **BẮT BUỘC** | Mọi story |
| 4.9 | Test quality review | `bmad-testarch-test-review` [BMAD core] | Recommended | Mọi story |
| 4.10 | Mutation gate (cosmic-ray) | `bmad-nowing-mutation-gate` | **P0-gated** | P0 source files touched |
| 4.11 | Traceability matrix | `bmad-testarch-trace` [BMAD core] | Recommended | Epic completion |
| 4.12 | NFR evidence audit | `bmad-testarch-nfr` [BMAD core] | Recommended | NFR-relevant stories |
| 4.13 | Human review gate (P0 areas) | `bmad-nowing-human-review-gate` | **P0-gated** | P0 source files touched |
| 4.14 | Web E2E gate (Playwright, `nowing_web`) | `bmad-nowing-web-e2e-gate` | Recommended | Web-facing feature, hoặc backend đổi response shape |
| 4.15 | Checkpoint preview | `bmad-checkpoint-preview` | Recommended | Human review |
| 4.16 | Loop lại 4.7 nếu review fail (max 2 vòng) | — | — | Review reject |

### Epic end

| # | Bước | Skill | Mức |
|---|---|---|---|
| 4.17 | Retrospective | `bmad-retrospective` | Recommended |

## Anytime (khi cần)

| Skill | Khi nào |
|---|---|
| `bmad-correct-course` | Change signal lớn mid-sprint |
| `bmad-sprint-status` | Check tiến độ |
| `bmad-quick-dev` | Quick fix không cần full pipeline |

---

## P0 Areas (Nowing)

Source files touch các area sau → MUST qua full pipeline (4.6 integration-test + 4.10 mutation-gate + 4.13 human-review-gate):

- **Token tracking / quota / credit:** `nowing_backend/app/services/token_tracking_service.py`, `token_quota_service.py`, `web_crawl_credit_service.py`, `platform_scrape_credit_service.py`
- **Auth:** `nowing_backend/app/auth/` (context.py, csrf.py, session_cookies.py), `nowing_backend/app/routes/auth_routes.py`
- **Provider / model routing:** `nowing_backend/app/services/provider_registry.py`, `model_resolver.py`, `openrouter_integration_service.py`
- **Pricing registration:** `nowing_backend/app/services/pricing_registration.py`
- **LLM service / router:** `nowing_backend/app/services/llm_service.py`, `llm_router_service.py`
- **Multi-agent chat:** multi-agent orchestrator + subagent composition services
- **RAG / connector sync:** embedding/indexing/KB sync services (`app/indexing_pipeline/`, `kb_sync_service.py`, `embedding_service.py`, `reranker_service.py`)

Chi tiết 6 anti-pattern + triage matrix: `docs/nowing-mutation-gate-reference.md`.

---

## Next Steps Output Format (BẮT BUỘC cho skill có on_complete override)

Khi skill complete, MUST output section này ở cuối response:

```
## Next steps in Nowing quality pipeline

**Vừa xong:** [skill-name] — [1-line summary]

**Bước tiếp theo (BẮT BUỘC):**
- [x.y] [skill-name] — [description]

**Bước tiếp theo (recommended):**
- [x.y] [skill-name] — [description] *(skip nếu [condition])*

**Còn lại trong pipeline:** [N] bước — [list ngắn hoặc "xem nowing-quality-pipeline.md"]
```

---

## Ghi chú

- Doc-only stories: skip 4.3-4.6, 4.10, 4.13-4.14
- Hotfix production: skip 4.1-4.6, làm 4.7 + 4.8 + 4.13 (human review)
- Non-P0 stories: skip 4.6, 4.10, 4.13 — vẫn làm 4.1, 4.7, 4.8
- `bmad-nowing-human-review-gate` là hard gate duy nhất — block `done` khi P0 areas touched
- Web E2E gate (4.14) chạy song song hoặc sau human review gate — không block `done`, nhưng recommended trước release cho story ảnh hưởng UI

## Full workflow map

```
4.1 create-story → 4.2 validate → 4.3 grill-me → 4.4 test-first-atdd →
4.5 testarch-atdd [core] → 4.6 nowing-integration-test (P0-gated) →
4.7 dev-story → 4.8 code-review → 4.9 testarch-test-review [core] →
4.10 nowing-mutation-gate (P0-gated) → 4.11 testarch-trace [core] →
4.12 testarch-nfr [core] → 4.13 nowing-human-review-gate (P0-gated) →
4.14 nowing-web-e2e-gate → 4.17 retrospective (epic end)
```

## Parallel Story Execution (Sub-Agent Fan-Out) — Best Practices

Áp dụng nguyên văn quy tắc đã kiểm chứng ở chainlens-research (xem `chainlens-quality-pipeline.md` gốc nếu cần đối chiếu), điều chỉnh cho stack Nowing:

**Khi nào fan-out:** nhiều story ĐỘC LẬP (không phụ thuộc lẫn nhau, không cùng sửa 1 file logic).

**RÀNG BUỘC BẮT BUỘC:**
1. **Git worktree riêng cho mỗi story** — `git worktree add ../wt-<story> -b feat/story-<story> develop`, chạy `uv sync` (backend) / `pnpm install` (web) trong mỗi worktree TRƯỚC khi dispatch.
2. **TỐI ĐA 2 sub-agent song song** — mỗi sub-agent có thể chạy `uvicorn`/`next dev` + pytest ăn RAM/CPU.
3. **Sub-agent KHÔNG start dev-server** (`uvicorn`/`next dev`) trừ khi bắt buộc E2E — port conflict là nguyên nhân abort chính. Chỉ pytest (`-m unit`/`-m integration` với `TEST_DATABASE_URL` riêng) không cần dev-server.
4. **Commit sớm, commit thường xuyên.**
5. **Verify tiến triển sau mỗi sub-agent:** `git status --short && git log --oneline -3`.
6. **Main thread dọn process rác sau abort** (`list_processes`).
