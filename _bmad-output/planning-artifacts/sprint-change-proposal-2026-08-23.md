# Sprint Change Proposal — Nowing Backlog Grooming (2026-08-23)

**Workflow:** `bmad-correct-course`
**Project:** Nowing
**Date:** 2026-08-23
**Author:** AI-assisted planning
**Affected artifacts:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/epics.md` (optional re-scope notes)

---

## 1. Issue Summary

Sprint review lại các story còn lại (`backlog` + `ready-for-dev`) phát hiện:

- **5 tech-debt followups** đang ở `ready-for-dev` nhưng chỉ nên làm khi parent feature đã active và pain point xuất hiện.
- **3 story scraping/enrichment** (Epic 14/17) bị block bởi dependency ngoài (`chainlens-research`, `XActions`) nhưng vẫn nằm trong pipeline sẵn sàng làm.
- **1 dashboard story** (`8-14`) chồng chéo với `8.3` và `8.7` đã xong.
- **1 automation story** (`6-10`) có phần scheduled tasks chồng khả năng với `26.8` (DSH Mission Executor).
- **3 business-gated splits** (`6-6a`, `6-7a`, `6-9a`) đã đúng là backlog nhưng cần giữ nguyên gating.

Mục tiêu: dọn backlog, tránh làm trùng/sớm, giải phóng `ready-for-dev` cho các story có giá trị thực.

---

## 2. Impact Analysis

### 2.1 Epic / Story Impact

| Epic | Story | Ảnh hưởng |
|---|---|---|
| Epic 4: Chat & Agents | 4-8c-followup, 4-8d-followup, 4-8h-followup | Tech debt followups; chuyển từ `ready-for-dev` về `backlog` với ghi chú trigger. |
| Epic 6: Automations | 6-10 | Phần Stateful Scheduled Tasks cần xem xét tách/gộp với `26.8`. Mail Gateway giữ lại. |
| Epic 8: Workspace Billing & Usage | 8-14 | Chồng với `8.3` + `8.7`; đề xuất merge hoặc re-scope thành dashboard enhancement. |
| Epic 9: Deep Research | 9-6-followup | Tech debt followup; chuyển về `backlog` với ghi chú trigger. |
| Epic 14: News | 14-2 | Entity enrichment giao cho `chainlens-research`; chuyển `ready-for-dev` về `backlog`/`blocked`. |
| Epic 17: E-commerce | 17-1, 17-5 | Raw scraping giao `XActions`; giữ `backlog` với ghi chú dependency. |

### 2.2 Artifact Impact

| Artifact | Thay đổi |
|---|---|
| `sprint-status.yaml` | Cập nhật trạng thái/ghi chú của 10+ story. Không đổi epic status. |
| `epics.md` | (Tùy chọn) cập nhật AC của `14-2`, `17-1`, `17-5` để phản ánh dependency ngoài; thêm ghi chú trigger cho followups. |

### 2.3 Technical Impact

- Không cần sửa code ngay. Đây là backlog grooming.
- Các story bị defer giảm cognitive load cho dev; tránh phát triển trước dependency.

---

## 3. Recommended Approach

1. **Duyệt backlog theo phân loại:** Keep / Defer / Merge / Blocked-by-external.
2. **Cập nhật `sprint-status.yaml`:** chuyển followups về `backlog`, gắn comment trigger; gắn comment `blocked-by-external` cho `14-2`, `17-1`, `17-5`; đánh dấu `8-14` cần merge/re-scope.
3. **Không xóa story file:** chỉ đổi status và comment để giữ lịch sử.
4. **PO xác nhận:** đặc biệt là quyết định merge `8-14` và tách `6-10`.

> **PO decision 2026-08-23:** Re-scope `8-14` thành **Story 8.3 v2 / follow-up dashboard** (per-turn cost breakdown + auto-extract budget toggle), giữ `8.3` `done`. Đã cập nhật `epics.md` cho 8.14.

---

## 4. Detailed Change Proposals

### Change 1 — Defer 5 tech-debt followups

**Artifact:** `sprint-status.yaml`

| Story | Lý do |
|---|---|
| `4-8c-followup` | P3, trigger: khi sampler thành automated job. Chưa active. |
| `4-8d-followup` | Tech debt `4-8d` chưa rõ AC; `4-8d` vẫn `ready-for-dev`, chưa production. |
| `4-8h-followup` | P2, trigger: khi ChainLens cost là pain point. Chưa đến. |
| `8-11-followup` | Tech debt `8-11` đã xong; cần rõ defer items trước khi làm. |
| `9-6-followup` | Tech debt `9-6` đã xong; cần rõ defer items trước khi làm. |

**OLD (current):**
```yaml
  4-8c-followup: ready-for-dev  # reopened
  4-8d-followup: ready-for-dev  # reopened
  4-8h-followup: ready-for-dev  # reopened
  8-11-followup: ready-for-dev  # reopened
  9-6-followup: ready-for-dev  # reopened
```

**NEW (proposed):**
```yaml
  4-8c-followup: backlog  # deferred: activate when production query sampler becomes automated job (P3)
  4-8d-followup: backlog  # deferred: depends on 4-8d active use and code-review items
  4-8h-followup: backlog  # deferred: activate when ChainLens cost becomes a pain point
  8-11-followup: backlog  # deferred: needs specific 8-11 code-review items before implementation
  9-6-followup: backlog  # deferred: needs specific 9-6 code-review items before implementation
```

---

### Change 2 — Block 3 external-dependency stories

**Artifact:** `sprint-status.yaml` + `epics.md`

| Story | Dependency | Lý do |
|---|---|---|
| `14-2` | `chainlens-research` entity linking | `epics.md` giao entity linking/disambiguation cho engine; Nowing chỉ attach metadata. |
| `17-1` | `XActions` MCP `x_lazada_search` | Raw scraping delegated; adapter Nowing chưa có nền tảng. |
| `17-5` | `XActions` MCP `x_tiktok_shop_products` | Tương tự `17-1`; codebase hiện chỉ có TikTok video scraper. |

**Epics.md AC updates (applied 2026-08-23):**
- `14.2`: thêm note `Blocked-by-external`, AC yêu cầu `chainlens-research` expose entity search/ingest trước.
- `17.1`: thêm note `Blocked-by-external`, AC yêu cầu `XActions` `x_lazada_search`/`x_lazada_product` MCP tool available; không build in-house crawler.
- `17.5`: thêm note `Blocked-by-external`, AC yêu cầu `XActions` `x_tiktok_shop_products` MCP tool available.

**OLD (current):**
```yaml
  14-2: ready-for-dev  # story file created 2026-08-19
  17-1: backlog  # Lazada Product Data
  17-5: backlog  # TikTok Shop Product & Trending SKUs
```

**NEW (proposed):**
```yaml
  14-2: backlog  # blocked-by-external: chainlens-research entity linking not available
  17-1: backlog  # blocked-by-external: XActions x_lazada_search MCP tool not available
  17-5: backlog  # blocked-by-external: XActions x_tiktok_shop_products MCP tool not available
```

---

### Change 3 — Re-scope `8-14` as 8.3 v2 follow-up

**Artifact:** `sprint-status.yaml` + `epics.md`

**Lý do:** `8.3` (Usage & Credit Dashboard) và `8.7` (Auto-Extract Budget Cap) đã `done`. `8-14` chỉ thêm per-turn cost breakdown + budget toggle UI. PO quyết định re-scope `8-14` thành **Story 8.3 v2 / follow-up dashboard**, giữ `8.3` `done`.

**Sprint status OLD:**
```yaml
  8-14: backlog  # Cost & Auto-Extract Budget Dashboard
```

**Sprint status NEW:**
```yaml
  8-14: backlog  # PO 2026-08-23: re-scope as 8.3 follow-up / dashboard v2; per-turn cost + budget toggle; not duplicate
```

**Epics.md update:** Title + AC của `Story 8.14` đã cập nhật thành "Usage & Credit Dashboard v2 — Per-Turn Cost & Auto-Extract Budget Toggle", thêm note `Re-scope 2026-08-23` và các AC rõ là mở rộng trên 8.3.

---

### Change 4 — Split / re-scope `6-10`

**Artifact:** `sprint-status.yaml`

**Lý do:** `6-10` gồm Inbound Mail Gateway (mới) + Stateful Scheduled Tasks 2.0 (có thể chồng `26.8`).

**OLD (current):**
```yaml
  6-10: backlog  # Inbound Mail Gateway + Stateful Scheduled Tasks 2.0 as DSH mission template
```

**NEW (proposed):**
```yaml
  6-10: backlog  # split: keep Mail Gateway, evaluate Scheduled Tasks portion against 26.8 before implementation
```

---

### Change 5 — Keep business-gated splits unchanged

**Artifact:** `sprint-status.yaml`

`6-6a-playbook-reuse`, `6-7a-schema-form-ui`, `6-9a-workspace-vertical` đã đúng `backlog` với ghi chú business-gated. Không thay đổi.

---

## 5. Implementation Handoff

### Các artifact đã cập nhật
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-23.md` (this file)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (sẽ cập nhật khi approve)

### Việc cần làm tiếp theo

| Owner | Task | Acceptance |
|---|---|---|
| PO | Approve / chỉnh sửa 5 đề xuất; quyết định re-scope `8-14`; xác nhận split `6-10`. | Proposal được approve hoặc revise; `8-14` scope rõ ràng. |
| Dev/PM | Cập nhật `sprint-status.yaml` theo proposal. | Các story đúng status mới; `ruff`/`pytest` không bị ảnh hưởng (chỉ text). |
| PM | Cập nhật `epics.md` AC cho `8.14`, `14-2`, `17-1`, `17-5` để phản ánh external dependency / v2 scope. | AC rõ ràng dependency và scope.
| Dev lead | Sau grooming, chọn story `ready-for-dev` thực sự tiếp theo (ví dụ `7-8`, `25-4`, `25-5`, `25-6`, `27-1`, `27-2`). | Sprint status mới có 1+ in-progress. |

### Scope classification

- **Moderate:** Backlog reorganization cần PO/Dev coordination, không thay đổi code.

### Success criteria

- Không còn tech-debt followup nằm `ready-for-dev` khi parent chưa active.
- `14-2`, `17-1`, `17-5` có ghi chú rõ dependency ngoài.
- `8-14` đã được PO re-scope thành 8.3 v2 follow-up (giữ 8.3 done).
- Các story `ready-for-dev` còn lại đều có giá trị thực và không bị block.

---

## 6. Risk Notes

- Story `4-6` (Research Continuity) đã `done` nhưng không nằm trong `sprint-status.yaml` (orphan file). Không ảnh hưởng proposal này, nhưng nên cân nhắc thêm vào `sprint-status.yaml` để trace.
- `14-2` chỉ xuất hiện một lần trong `sprint-status.yaml` ở `ready-for-dev`, không duplicate như báo cáo sơ bộ ban đầu.
