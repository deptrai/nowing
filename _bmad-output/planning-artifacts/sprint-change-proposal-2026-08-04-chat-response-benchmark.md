# Sprint Change Proposal — Chat Response Quality Benchmark (2026-08-04)

**Workflow:** `bmad-correct-course` (batch mode)  
**Project:** Nowing  
**Date:** 2026-08-04  
**Author:** Devin (Agent) + PO Luisphan  
**Status:** 📝 **DRAFT — pending PO approval**

---

## 1. Issue Summary

### 1.1 Trigger
PO yêu cầu xây dựng một **benchmark chat response** để đo lường chất lượng câu trả lời của hệ thống Nowing **mỗi khi lên production**, sử dụng **dữ liệu thực tế**, và bao phủ đầy đủ các case chat của hệ thống.

### 1.2 Core Problem
Hiện tại Nowing chưa có một công cụ đánh giá chat response chính thức ở tầng `nowing_evals`:

- Kiểm thử chat trước deploy chủ yếu dựa vào **E2E smoke với fake LLM** (`nowing_backend/tests/e2e/fakes/chat_llm.py`, `nowing_web/tests/smoke/chat-ui-smoke.spec.ts`) — đảm bảo UI không crash nhưng không đo chất lượng câu trả lời thật.
- Dữ liệu production (query, context, token/cost, latency) chưa được thu thập, tổng hợp thành bộ benchmark để phát hiện regression.
- Không có gate để tự động chặn deploy nếu chat quality/latency/cost xuống cấp.

### 1.3 Evidence
- `nowing_evals/README.md` liệt kê các benchmark hiện có: `medical/*`, `multimodal_doc/mmlongbench`, `research/chainlens_latency` — **không có suite chat**.
- `nowing_evals/src/nowing_evals/core/clients/new_chat.py` đã có `NewChatClient` để gọi `/api/v1/new_chat`, nhưng chưa parse `data-token-usage` và `data-turn-info` từ SSE.
- Backend đã emit `token-usage` SSE frame với `prompt_tokens`, `completion_tokens`, `cost_micros`, `call_details` (`app/tasks/chat/streaming/flows/shared/finalize_emit.py`); và `TokenUsage` schema đã lưu `e2e_ms`, `ttfb_ms` (`app/db.py`).
- PRD §4.4 có FR-14/15/16/17 chat nhưng không có NFR/FR nào cho chat quality benchmark.

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Tác động |
|---|---|
| **Epic 4: Chat & Agents** | Nguồn gốc của feature. Cần thêm story/epic con để benchmark chat. Không làm thay đổi code chat runtime. |
| **Epic 3: Knowledge Base & Memory** | Chat benchmark phụ thuộc vào chất lượng memory recall (NFR-8) và hybrid search. Kết quả benchmark chat sẽ phản ánh trực tiếp trạng thái `3-14` (recall bounded). |
| **Epic 9: Deep Research** | Chat có thể gọi ChainLens (`FR-24`). Benchmark cần cover case deep-research trong chat, sử dụng cost thật đã được parse qua `9.2`. |
| **Epic 8: Billing/Credits** | Benchmark sẽ tiêu tốn credit. Cần cost cap, wallet pre-check, và theo dõi `TokenUsage` — tận dụng `8-7` đã xong. |
| **Epic 10–11** | Không ảnh hưởng trực tiếp. |

**Quyết định:** Cần một **epic mới** hoặc story nhóm vì tính cross-cutting. Đề xuất **Epic 4.8** hoặc **Epic 12** (nếu muốn tách thành epic độc lập). Epic 4 hiện `done` và chỉ còn `4.7` (tabs), nên đặt dưới Epic 4 làm `4.8` hoặc mở Epic 12 cho eval infrastructure.

### 2.2 Artifact Conflicts

#### PRD (`prd-Nowing-2026-07-22/prd.md`)
- Thêm **NFR-10: Chat Response Quality & Regression Gate** trong §5.
- Thêm **FR-42: Chat Response Benchmark** trong §4.4 (hoặc §4.8 nếu coi là ops/eval feature).
- Cập nhật §6.2 Out of Scope nếu có phần nào bị loại (ví dụ: LLM-as-judge cho Phase 2, không Phase 1).

#### Architecture (`ARCHITECTURE-SPINE.md`, `docs/architecture-evals.md`)
- `docs/architecture-evals.md` cần cập nhật danh sách benchmark hiện có.
- `ARCHITECTURE-SPINE` cần ghi nhận `nowing_evals` là bề mặt eval chính thức, và chat benchmark là consumer của `NewChatClient` + `TokenUsage`.

#### UX
- MVP **không cần UI**. Chỉ CLI + báo cáo markdown/json. UI admin xem benchmark report là follow-up.

#### Sprint Status (`sprint-status.yaml`)
- Thêm epic/story mới, cập nhật `action_items`.

### 2.3 Technical Impact

#### Tác động đến `nowing_evals`
- Tạo `src/nowing_evals/suites/chat/` với ít nhất một suite ban đầu (`regression`).
- Mở rộng `NewChatClient` để parse `data-token-usage`, `data-turn-info`, tính `ttfb_ms`.
- Có thể cần `core/metrics/chat_quality.py` cho LLM-as-judge (Phase 2).

#### Tác động đến backend
- **Không cần thay đổi runtime chat** nếu chỉ reuse SSE. Tuy nhiên, cần endpoint hoặc script admin để trích xuất production query đã **anonymize**.
- `TokenUsage` đã có `e2e_ms`, `ttfb_ms`, `cost_micros` — benchmark có thể đọc từ SSE hoặc query DB nếu có quyền admin.

#### Tác động đến data/privacy
- Dữ liệu production chat có thể chứa PII, sensitive workspace data. **Đây là rủi ro P0.**
- Cần policy: chỉ lấy query text, không lấy answer, không export PII; hoặc dùng synthetic data cho self-host.

### 2.4 Scope Classification
- **Moderate đến Major**: cross-epic, cần đầu tư dataset, privacy review, và integration CI.

---

## 3. Recommended Approach

### 3.1 Selected Path
**Option 1 — Direct Adjustment + Two-Phase Delivery**.

Lý do:
- Tận dụng sẵn `nowing_evals` harness, `NewChatClient`, `TokenUsage`, SSE `token-usage`.
- Không cần revert hoặc thay đổi PRD MVP core.
- Chia làm 2 phase để có gate sớm (Phase 1 regression) trước khi đầu tư LLM-as-judge (Phase 2 quality).

### 3.2 Two-Phase Delivery

#### Phase 1 — `chat/regression` (MVP, ship trước)
Mục tiêu: phát hiện **regression** sau mỗi deploy.

- Dataset: JSONL gồm các query thực tế (đã anonymize) hoặc synthetic, kèm `tags` phân loại case.
- Chạy mỗi query trên `/api/v1/new_chat` trong thread mới.
- Thu thập: `latency_ms`, `ttfb_ms`, `prompt/completion/total tokens`, `cost_micros`, `citation_count`, `finished_normally`, `error`, `answer_length`.
- Không cần reference answer — chỉ đo **drift so với baseline** (ví dụ: error rate p95, latency p95, citation count đột ngột giảm).
- Gate cơ bản: `error_rate < threshold`, `p95_latency < threshold`, `citation_count >= threshold`.

#### Phase 2 — `chat/quality` (LLM-as-judge)
Mục tiêu: đo **chất lượng câu trả lời** trên tập curated có reference/rubric.

- Dataset nhỏ hơn, có `reference_answer` và `rubric` cho từng case.
- Sử dụng strong judge model (OpenRouter) để chấm `correctness`, `citation_faithfulness`, `completeness`, `harmfulness`.
- Cover đầy đủ case: chat dựa memory, chat với document mention, chat với deep-research, anonymous chat, multi-tool, image, v.v.
- Chạy định kỳ (weekly hoặc pre-release), không chạy mỗi deploy vì tốn kém.

### 3.3 Rationale
- Phase 1 cung cấp **gate nhanh, rẻ, deterministic** để chặn deploy nghiêm trọng.
- Phase 2 cung cấp **số chất lượng** để ra quyết định cải tiến model/prompt/RAG.
- Tách phase giảm rủi ro cost và privacy ở Phase 1.

---

## 4. Detailed Change Proposals

### 4.1 PRD Changes

#### OLD — §5 Non-Functional Requirements (cuối section)
Không có NFR cho chat response quality.

#### NEW — Thêm NFR-10
```markdown
#### NFR-10: Chat Response Quality & Regression Gate
Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.

- `nowing_evals` chạy `chat/regression` trên tập query đại diện.
- Metrics bắt buộc: p95 e2e latency, p95 TTFB, error rate, finish rate, citation count, cost/turn.
- Ngưỡng cụ thể được chốt trong `gate.yaml` và chỉ có thể `baseline_ratified: true` sau 3 lần chạy liên tiếp ổn định.
- Dữ liệu benchmark không chứa PII; self-host có thể dùng synthetic dataset.
```

#### OLD — §4.4 Chat & Agents
Chỉ có FR-14..FR-17.

#### NEW — Thêm FR-42
```markdown
#### FR-42: Chat Response Benchmark
Hệ thống cung cấp benchmark `nowing_evals` để đo chat response quality với dữ liệu thực tế hoặc curated.

- Bao gồm ít nhất `chat/regression` (drift gate) và `chat/quality` (LLM-as-judge).
- Tích hợp vào CI/CD deploy pipeline.
- Tôn trọng phân quyền workspace và PII.
```

### 4.2 Epic/Story Proposal

#### Option A: Gộp vào Epic 4

```yaml
epic-4:
  4.8-chat-response-benchmark: ready-for-dev
```

**Story 4.8a — Extend `NewChatClient` for benchmark telemetry**
- Parse `data-token-usage`, `data-turn-info` từ SSE.
- Trả về `input_tokens`, `output_tokens`, `cost_micros`, `ttfb_ms`, `turn_id` trong `StreamedAnswer`.

**Story 4.8b — `chat/regression` benchmark suite (Phase 1)**
- Tạo `nowing_evals/suites/chat/regression/`.
- `ingest.py`: load dataset JSONL; hỗ trợ tải lên workspace/docs nếu cần.
- `runner.py`: chạy query, gọi `NewChatClient.ask`, ghi raw JSONL, aggregate metrics, gate.
- `gate.yaml`: ngưỡng cho error rate, p95 latency, cost, citation count.
- `report_section()`: markdown report theo tag.

**Story 4.8c — Production query sampler/anonymizer**
- Script admin hoặc endpoint nội bộ trích xuất N query gần đây, loại bỏ PII, gắn tag case.
- Output JSONL sẵn sàng cho `ingest`.
- Chạy trên production DB read-replica hoặc backup.

**Story 4.8d — `chat/quality` benchmark suite (Phase 2)**
- Dataset có reference/rubric.
- LLM-as-judge scorer.
- Metrics: correctness, citation faithfulness, completeness, cost.

**Story 4.8e — CI integration**
- GitHub Action/Dokploy step chạy `chat/regression` trước khi đánh dấu deploy thành công.
- Báo cáo gửi Slack/Telegram nếu gate fail.

#### Option B: Epic 12 mới
Nếu muốn tách eval thành epic riêng (phù hợp với xu hướng `nowing_evals` ngày càng lớn):

```yaml
epic-12-chat-quality-benchmark:
  12-1: 4.8a  # client telemetry
  12-2: 4.8b  # regression suite
  12-3: 4.8c  # query sampler
  12-4: 4.8d  # quality suite
  12-5: 4.8e  # CI integration
```

**Khuyến nghị:** Dùng **Story 4.8a–e gộp trong Epic 4** để tránh phình epic, trừ khi PO muốn eval infrastructure là epic độc lập.

### 4.3 Architecture Changes

#### `nowing_evals/src/nowing_evals/core/clients/new_chat.py`
OLD:
```python
@dataclass
class StreamedAnswer:
    text: str
    raw_events: list[dict[str, Any]]
    latency_ms: int
    user_message_id: str | None
    assistant_message_id: str | None
    finished_normally: bool
```

NEW:
```python
@dataclass
class StreamedAnswer:
    text: str
    raw_events: list[dict[str, Any]]
    latency_ms: int
    ttfb_ms: int | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    turn_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_micros: int | None = None
    finished_normally: bool = False
```

Và `_consume_sse` thêm nhánh `data-token-usage`, `data-turn-info`, `data-turn-status`.

#### `nowing_evals/src/nowing_evals/suites/chat/regression/__init__.py`
Tự đăng ký benchmark qua `register()` theo pattern `chainlens_latency`.

#### `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
Tương tự `ChainlensLatencyBenchmark`:
- `add_run_args`: `--cases`, `--n`, `--concurrency`, `--tags`, `--workspace-id`, `--backend-build-id`.
- `ingest`: load JSONL dataset; seed workspace nếu cần.
- `run`: gọi `NowingArm` hoặc trực tiếp `NewChatClient.ask`, ghi raw, aggregate.
- `report_section`: bảng metrics theo tag.

#### `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`
```yaml
baseline_ratified: false
thresholds:
  error_rate: 0.05
  p95_e2e_ms: 30000
  p95_ttfb_ms: 5000
  min_citation_count: 1
  max_cost_micros_per_turn: 200000
```

### 4.4 Dataset Format

```jsonl
{"case_id": "prod-001", "query": "What did we decide about the Q3 budget?", "tags": ["memory", "factual"], "expected_contains": ["Q3", "budget"], "workspace_name": "acme-finance"}
{"case_id": "doc-042", "query": "Summarize the key clauses of the NDA.", "tags": ["document"], "mentioned_document_ids": [123], "reference_answer": "..."}
{"case_id": "research-015", "query": "Latest trends in RAG evaluation 2025.", "tags": ["deep-research"], "disabled_tools": []}
```

- `expected_contains` dùng cho Phase 1 (cheap deterministic check).
- `reference_answer` dùng cho Phase 2 (LLM judge).

### 4.5 Implementation Plan

| Story | Nội dung | Est. | Tiền đề |
|---|---|---|---|
| 4.8a | Extend `NewChatClient` parse token-usage/turn-info | 1 ngày | — |
| 4.8b | `chat/regression` suite (ingest, runner, gate, report) | 2–3 ngày | 4.8a |
| 4.8c | Production query sampler + anonymizer | 1–2 ngày | DB access + privacy review |
| 4.8d | `chat/quality` suite (LLM judge, labeled dataset) | 3–4 ngày | 4.8b |
| 4.8e | CI/CD gate + docs | 1 ngày | 4.8b |

**Tổng estimate Phase 1 (4.8a–c + 4.8e):** 5–7 ngày.  
**Tổng estimate Phase 2 (4.8d):** +3–4 ngày.

---

## 5. Implementation Handoff

### 5.1 Scope Classification
**Moderate to Major** — cross-epic, cần privacy review, dataset curation, CI integration.

### 5.2 Roles & Responsibilities

| Vai trò | Trách nhiệm |
|---|---|
| **PO (Luisphan)** | Phê duyệt privacy approach, baseline ratification, ngưỡng gate, phân bổ epic ID (4.8 vs 12). |
| **Architect** | Review thiết kế `NewChatClient` extension, dataset schema, integration với `TokenUsage`, `AD-15` nếu benchmark gọi ChainLens. |
| **Developer** | Implement stories 4.8a–e. |
| **QA/Eval** | Xây dựng dataset, chạy baseline, xác nhận gate. |
| **DevOps** | Cấu hình CI/Dokploy step, bảo mật production query sampler. |

### 5.3 Success Criteria
- `python -m nowing_evals run chat regression` chạy thành công trên local + production staging.
- Báo cáo markdown/json được tạo ra với metrics latency, cost, citation, error rate.
- Gate fail khi inject một regression giả (ví dụ: vô hiệu hóa memory injection).
- Dataset không chứa PII sau khi anonymize.
- Không làm tăng độ trễ hoặc cost của production chat runtime (chỉ chạy benchmark song song, không inline).

### 5.4 Open Questions
1. PO muốn gộp vào Epic 4 hay mở Epic 12?
2. Có đồng ý dùng **synthetic/curated dataset** cho Phase 1 thay vì production query không?
3. Ngưỡng gate dự kiến (p95 latency, cost/turn) là bao nhiêu?
4. Judge model cho Phase 2 chọn model nào (Claude Sonnet, GPT-5, Gemini)?

---

## 6. Recommendation

**Approve Phase 1 (4.8a–c + 4.8e) trước** để có deploy gate nhanh. Phase 2 (LLM-as-judge) là follow-up sau khi baseline ổn định.

Nếu PO đồng ý, tôi sẽ:
1. Tạo story file cho `4.8a` (hoặc `12-1`).
2. Bắt đầu implement `NewChatClient` telemetry extension.
3. Thiết kế dataset schema và `chat/regression` runner theo pattern `chainlens_latency`.

---

**Artifacts được đề xuất cập nhật:**
- `prd-Nowing-2026-07-22/prd.md` (NFR-10, FR-42)
- `epics.md` (story 4.8 / Epic 12)
- `sprint-status.yaml` (trạng thái mới)
- `docs/architecture-evals.md` (danh sách benchmark mới)
- `nowing_evals/src/nowing_evals/core/clients/new_chat.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/*` (mới)
