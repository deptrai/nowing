# Sprint Change Proposal — Sales Copilot Playbook Expansion

**Date:** 2026-08-29  
**Project:** Nowing  
**Raised by:** User during Sales Copilot end-to-end verification  
**Skill:** `bmad-correct-course` (Batch review)  

---

## Section 1: Issue Summary

### 1.1 Trigger
Trong quá trình chạy thử end-to-end (E2E) tính năng **Sales Copilot / Quickstart Playbook Builder** và xác nhận lead hiển thị trong `NowingLeadMatrix`, user đưa ra 3 phản hồi chiến lược bổ sung:

1. **Nguồn dữ liệu mới — KOL / social comments & posts**:  
   "Mà sao các playbook bạn không tìm ở trong comment, post của YouTube, TikTok, Instagram của các KOLs nổi tiếng trong các lĩnh vực? Đó là nguồn khách hàng dồi dào."  
   Yêu cầu mở rộng adapter để khai thác dữ liệu công khai từ comment & post trên các nền tảng xã hội do KOL tạo ra.

2. **Tận dụng kịch tài nguyên trong system prompt**:  
   "Tôi thấy system prompt chưa tận dụng được hết các kịch tài nguyên đâu."  
   Yêu cầu agent dùng hơn các tài nguyên (kịch, playbook, resource snippets, ví dụ mẫu) có sẵn trong hệ thống khi tạo prompt.

3. **User-defined playbook + phân quyền rõ ràng**:  
   "Cho user tự tạo playbook luôn đi, nhưng để 1 mục riêng là user playbook (chỉ user nào tạo mới được xem), còn playbook admin tạo thì tất cả mọi người đều được dùng."

### 1.2 Current State (verified from code & docs)
- `playbooks` table đã tồn tại với `PlaybookScope.WORKSPACE` và `PlaybookScope.SYSTEM` (`nowing_backend/app/automations/persistence/models/playbook.py`).
- Epic 21 stories (21.15, 21.20) và Epic 24.5 đã xây **Vertical Playbook Marketplace** với các preset sẵn.
- Epic 6.6/6.7/6.9 đang **business-gated** (`gated sau pilot BĐS`) nhưng kỹ thuật đã có `AutomationDefinition.inputs.schema`, `PlanStep.params`, Jinja sandbox.
- Architecture Spine ghi rõ: **anti-bot / social scraping thuộc `app/proprietary/platforms/{reddit,tiktok,instagram}`**, và Nowing phải **delegate raw scraping tới XActions** (`AD-SOC-1`, `AD-SOC-9`), không build headless crawler mới trong repo.
- `LeadGenOrchestrator` đã hỗ trợ `target_sources` và `MultiSourceLeadGenRequest`, dễ mở rộng thêm adapter.

### 1.3 Evidence
- User message kèm hình ảnh minh họa (Image #8) về giao diện playbook.
- Sprint status: Epic 21, Epic 24 đã `done`; Epic 6 còn in-progress với 3 business-gated stories (`6-6a`, `6-7a`, `6-9a`).
- `PlaybookScope` chỉ có 2 giá trị; chưa có `USER` (owner-only) scope.
- Hiện tại `quickstart-playbook-builder.tsx` hard-code `PLAYBOOK_PRESETS` array, không cho user tạo mới.

---

## Section 2: Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Required Change |
|---|---|---|
| **Epic 6 — Automations** | Cao | Bổ sung AC cho user-defined playbooks, `scope` mở rộng, UI tạo playbook, RBAC enforcement. Cần mở lại 6-6a/6-7a/6-9a từ `backlog` nếu user-gated decision được dỡ. |
| **Epic 21 — Lead Gen Intelligence** | Cao | Thêm adapter family `KOL Social Comment/Post` (YouTube/TikTok/Instagram) hoặc tích hợp XActions MCP; enrich `RawLeadRecord` với author, content, engagement. |
| **Epic 22 — Telegram** | Trung bình | Pattern MTProto / public web preview có thể tái dùng cho public social APIs; cần tránh duplicate. |
| **Epic 24 — Lead Conversion / Marketplace** | Cao | Playbook Marketplace UI cần tab/filter `User / Admin / All`; cần phân quyền install & run. |
| **Epic 18 — AgentConfig / Chat** | Trung bình | `AgentConfig` cần đọc `playbook.resources` / resource snippets để inject vào system prompt. |
| **Epic 28 — Legal/ToS** | Trung bình | Dữ liệu KOL public comments cần review ToS, PDPD Decree 13, opt-out/DNC. |

### 2.2 Story Impact

Cần thêm hoặc sửa các story:

- **Story 21.23 (NEW)**: KOL Social Comment & Post Lead Adapter.
- **Story 21.24 (NEW)**: System Prompt Resource Injection for Playbook Runs.
- **Story 6.10 (NEW/extend 6.6)**: User-Generated Playbooks with Visibility Scope.
- **Story 24.5.x (NEW/extend)**: Playbook Marketplace filters & tabs.
- **Story 6-6a/6-7a/6-9a**: Re-evaluate business gate.

### 2.3 Artifact Conflicts

| Artifact | Conflict / Gap | Action Needed |
|---|---|---|
| **PRD §4.10** | Không định nghĩa KOL/social source, không định nghĩa user playbook scope | Bổ sung FR-69.x và FR-6.x |
| **Epics.md 6.6 / 6.9** | Chỉ có `workspace` vs `system`; không có `user` (owner-only) | Cập nhật AC |
| **Architecture Spine** | Đã có rule XActions delegation cho raw scraper; cần thêm adapter contract cho KOL social | AD mới hoặc cập nhật AD-19.1 |
| **UX wireframes** | Không có UX cho user tạo playbook, không có filter user/admin | Bổ sung UX |
| **DB schema** | `playbooks.scope` enum 2 giá trị; cần mở rộng 3 giá trị hoặc thêm `is_private` | Alembic migration |

### 2.4 Technical Impact

- **Backend**: `PlaybookScope` enum mở rộng; API `POST /playbooks` cho phép user tạo; `GET /playbooks` filter by scope + workspace + user; `LeadGenOrchestrator` thêm `KolSocialAdapter`.
- **Frontend**: `quickstart-playbook-builder.tsx` thêm tab "Của tôi" / "Hệ thống" / "Workspace" + form tạo playbook; `PlaybooksContent` thêm filter chip.
- **Prompt engineering**: `AgentConfig` hoặc chat orchestrator đọc `playbook.resources` (markdown/JSONB) và append vào `system_instructions`.
- **XActions contract**: Đề xuất MCP tools `x_youtube_comments`, `x_tiktok_search`, `x_instagram_hashtag` (read-only, public data).
- **Legal/Compliance**: PDPD, ToS của YouTube/TikTok/Instagram, DNC whitelist, PII redaction.

---

## Section 3: Recommended Approach

### 3.1 Option Evaluation

| Option | Viability | Notes |
|---|---|---|
| **1. Direct Adjustment** | Viable (partial) | Phù hợp cho user-defined playbook + system prompt resources. KOL social scraping rộng, cần Spike/PoC trước. |
| **2. Rollback** | Not viable | Không có gì để revert. |
| **3. MVP Review** | Viable | Cần phân biệt MVP (user playbooks + admin visibility + prompt resources) vs post-MVP (KOL YouTube/TikTok/Instagram full ingestion). |

### 3.2 Recommended Path: Hybrid

- **P0 / MVP gấp**:
  1. **User-defined playbooks** với 3 visibility scope: `user` (owner-only), `workspace` (workspace members), `system` (admin/public).
  2. **Admin vs User playbook split** trong UI: tab/segmented control + backend filter.
  3. **System prompt resource injection**: `playbook.resources` JSONB/markdown appended to system prompt on run.

- **P1 / Spike**:
  4. **KOL Social Comment/Post adapter** — bắt đầu với **1 nền tảng pilot** (đề xuất YouTube public comments trước vì dữ liệu công khai, API/feed ổn định hơn TikTok/Instagram anti-bot).

- **P2 / Backlog**:
  5. Mở rộng sang TikTok/Instagram khi XActions MCP tool sẵn sàng hoặc sau khi pilot YouTube chứng minh retention.

### 3.3 Rationale
- User-defined playbooks + visibility là **low-hanging fruit**: backend đã có 80% (`Playbook` model, `AutomationDefinition.inputs.schema`, parameterized automation engine); chỉ cần mở rộng enum, UI, RBAC.
- System prompt resource injection **không phá vỡ architecture**: thêm trường `resources` vào `Playbook.definition`/`AgentConfig`.
- KOL social scraping **rủi ro cao** (ToS, anti-bot, PII) — cần XActions PoC và legal review, không nên ép vào cùng sprint.

### 3.4 Effort / Risk / Timeline

| Area | Effort | Risk | Timeline |
|---|---|---|---|
| User-defined playbooks + visibility | M | L | 3–5 ngày |
| System prompt resource injection | S | L | 1–2 ngày |
| KOL YouTube comment adapter (Spike) | M | H | 1–2 tuần (phụ thuộc XActions) |
| KOL TikTok/Instagram (post-spike) | L–XL | H | 2–4 tuần mỗi nền tảng |

---

## Section 4: Detailed Change Proposals

### 4.1 Story: 21.23 — KOL Social Comment & Post Lead Adapter

**OLD:**  
*(not in epics.md)*

**NEW:**

```
Story 21.23: KOL Social Comment & Post Lead Adapter

As a sales rep,
I want to harvest leads from comments and posts under KOL/influencer content on YouTube, TikTok, and Instagram in my vertical,
So that I can reach high-intent prospects who already engage with industry experts.

Acceptance Criteria:
- Given a KOL channel/post URL and vertical keywords, when KolSocialAdapter runs, then it returns RawLeadRecords containing: author handle, comment/post text, phone/email if publicly exposed, source URL, timestamp, engagement signal.
- Given YouTube/TikTok/Instagram anti-bot protections, when scraping, then it delegates to XActions MCP tools (x_youtube_comments, x_tiktok_search, x_instagram_hashtag) and ingests structured results.
- Given PII/consent constraints, when processing comments, then it redacts non-public PII, applies DNC/whitelist, and logs provenance.
- Given a comment without phone/email, when displayed, then the lead still surfaces the author handle, content snippet, and source URL so sales can engage manually.
```

**Rationale:** Mở nguồn khách hàng mà user chỉ ra; tái dùng XActions anti-bot stack; bắt đầu với public data & opt-in PII handling.

---

### 4.2 Story: 21.24 — System Prompt Resource Injection

**OLD:**  
*(not in epics.md)*

**NEW:**

```
Story 21.24: Playbook Resource Injection into Agent System Prompt

As a playbook runner,
I want the agent to automatically inject vertical resource scripts, example flows, and best-practice templates into the system prompt,
So that the agent uses existing playbook knowledge instead of generic instructions.

Acceptance Criteria:
- Given a playbook execution, when the system prompt is built, then it includes a resources block with: playbook intent, ICP criteria template, target sources, example output schema, fallback behavior.
- Given a user-defined playbook, when saved, then the user can attach markdown resource notes / prompt fragments that are appended to system prompt on run.
- Given no custom resources, when default playbooks run, then they still load canonical resource snippets from app/agents/chat/resources/{vertical}.md.
- Given a playbook update, when a new version is saved, then running instances pin to the old version and new runs use the new resources (versioning).
```

**Rationale:** Giải quyết feedback "chưa tận dụng kịch tài nguyên"; tận dụng sẵn có `AgentConfig.system_instructions` injection pattern.

---

### 4.3 Story: 6.10 — User-Generated Playbooks with Visibility Scope

**OLD (Story 6.6 AC trích từ epics.md):**

```
Given an AutomationDefinition đã chạy đúng, when user lưu nó thành playbook, then hệ thống lưu definition đó làm template and dùng chính inputs.schema sẵn có...
And playbook có ownership rõ ràng: workspace (user tạo) vs system (Nowing ship sẵn) — không rò rỉ giữa workspace.
```

**NEW:**

```
Story 6.10: User-Generated Playbooks with Visibility Scope

As a workspace user,
I want to create my own playbooks and keep them private, share with my workspace, or publish them for everyone,
So that I can reuse my best workflows and decide who can see or run them.

Acceptance Criteria:
- Given a playbook creation UI, when user saves, then they select scope: user (owner-only), workspace (workspace members), or system/public (admin-approved, visible to all).
- Given a user-scope playbook, when another user views the playbook library, then they cannot see it.
- Given a workspace-scope playbook, when a member of the same workspace views the library, then they see and can run it.
- Given a system/public-scope playbook created/approved by admin, when any user opens the library, then they see it (read-only install & run).
- Given a playbook run, when executed, then backend enforces scope at API level (playbook.scope, playbook.created_by, playbook.workspace_id).
- Given playbook versioning, when a user edits a playbook, then existing automation instances pin to the version they were created from.
```

**Rationale:** Đáp ứng chính xác yêu cầu user: "mục riêng user playbook, admin playbook mọi người dùng"; mở rộng AC 6.6 thay vì xây mới.

---

### 4.4 PRD Modification

**PRD §4.10 — Lead Gen Intelligence**

**OLD:**  
Chỉ liệt kê FR-63..FR-68; không có social/KOL source, không có user playbook.

**NEW:**

```
#### FR-69.1: KOL Social Comment & Post Lead Ingestion
As a sales rep, I want to discover leads from comments and posts under KOL/influencer content on YouTube, TikTok, and Instagram, so that I can reach prospects already engaged with industry voices.

Acceptance Criteria:
- Given a vertical and a KOL channel/post URL, when the KOL Social adapter runs, then it returns public author handles, content snippets, and any publicly exposed contact info.
- Given platform anti-bot or rate limits, when scraping, then it delegates to XActions MCP tools and gracefully degrades with partial results.
- Given PII/consent requirements, when processing, then it redacts non-public PII and applies DNC/whitelist.

#### FR-6.10: User-Created Playbook Library
As a workspace user, I want to create, save, and scope my own playbooks (private, workspace, or public), so that I can reuse workflows without exposing them inappropriately.

Acceptance Criteria:
- Given a playbook, when created, then the user selects a visibility scope enforced by backend RBAC.
- Given an admin-created playbook with public scope, when any user browses the library, then they can install and run it.
- Given a user-created private playbook, when another user queries the library, then it is not visible.
```

**Rationale:** Đưa yêu cầu mới vào nguồn sự thật PRD, liên kết với Epic 6 & Epic 21.

---

### 4.5 Architecture Changes

**Affected:** `app/automations/persistence/models/playbook.py`, `app/automations/schemas/api/playbook.py`, `app/lead_intelligence/services/lead_gen_orchestrator.py`, `app/lead_intelligence/adapters/`, chat orchestrator prompt builder.

**Proposed:**

1. **Playbook scope expansion**
   ```python
   class PlaybookScope(StrEnum):
       USER = "user"         # owner-only
       WORKSPACE = "workspace"
       SYSTEM = "system"     # admin/public
   ```

2. **Playbook resources field**
   ```python
   resources = Column(JSONB, nullable=False, default=dict, server_default="'{}'::jsonb")
   # resources = {"system_prompt_fragment": "...", "examples": [...], "fallback": "..."}
   ```

3. **New adapter `KolSocialAdapter`**
   ```
   app/lead_intelligence/adapters/kol_social_adapter.py
   - KolSocialAdapter(BaseLeadAdapter)
   - supports source keys: youtube_comments, tiktok_search, instagram_hashtag
   - calls XActions MCP: x_youtube_comments, x_tiktok_search, x_instagram_hashtag
   - maps to RawLeadRecord: author, content_snippet, source_url, timestamp, engagement
   ```

4. **System prompt composition**
   ```
   ChatOrchestrator / AgentConfig loader:
   - if playbook_id present, fetch playbook.resources
   - append resources.system_prompt_fragment to system_instructions
   - append playbook examples to few-shot context
   ```

**Rationale:** Kiến trúc tận dụng sẵn có; không vi phạm AD-SOC-1 (XActions delegation); RBAC rõ ràng.

---

### 4.6 UI/UX Specification Updates

**Affected:** `nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx`, `nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx`, `playbook-instantiate-dialog.tsx`.

**Proposed:**

1. **Playbook library tabs / segmented control:**
   - **Hệ thống** (system/admin playbooks — visible to all)
   - **Workspace** (workspace-scope playbooks)
   - **Của tôi** (user-scope playbooks)

2. **"Tạo Playbook" button**:
   - Form: name, vertical, intent, target sources, resource notes (markdown), scope toggle.
   - Save validates against `inputs.schema` (reuse existing `AutomationDefinition.inputs.schema`).

3. **Playbook card badges**:
   - `Admin` / `Workspace` / `Riêng tư` chip.
   - Run count, estimated credit cost preview, `max_leads_per_run` cap.

4. **Resource preview / editor**:
   - Collapsible markdown editor for system prompt fragment & examples.
   - Live preview of how prompt would look when injected.

**Rationale:** UX đơn giản, tái dùng pattern filter/tab đã có; không hard-code per playbook.

---

## Section 5: Implementation Handoff

### 5.1 Scope Classification

**Moderate to Major.**

- **Moderate** nếu chỉ làm P0 (user playbooks + visibility + prompt resources).
- **Major** nếu kéo theo KOL social scraping đầy đủ 3 nền tảng, vì tác động XActions, legal, ToS, anti-bot.

### 5.2 Recommended Handoff

| Role | Responsibility |
|---|---|
| **Product Owner / PM** | Quyết định dỡ business gate 6-6a/6-7a/6-9a; phê duyệt P0 vs P1 scope; chốt ToS/legal cho KOL public data. |
| **Solution Architect** | Review AD cho KOL social adapter, XActions contract, prompt injection design, RBAC scope. |
| **UX Designer (Sally)** | Wireframe tab User/Workspace/System, form tạo playbook, resource editor preview. |
| **Developer agent** | Implement backend scope migration, API filter, frontend tabs, prompt injection. |
| **XActions team / MCP owner** | Build `x_youtube_comments`, `x_tiktok_search`, `x_instagram_hashtag` tools (P1 spike). |
| **QA / Legal** | Review PII redaction, DNC, ToS compliance cho social comments. |

### 5.3 Success Criteria

- [ ] `playbooks.scope` hỗ trợ `user`/`workspace`/`system`, có migration, không duplicate.
- [ ] API `GET /playbooks` filter đúng scope theo user/workspace.
- [ ] UI hiển thị 3 tab Hệ thống / Workspace / Của tôi.
- [ ] User tạo playbook mới qua form và chạy được.
- [ ] System prompt của playbook run chứa `resources` content.
- [ ] (P1) XActions PoC trả về ≥1 lead từ YouTube public comments.
- [ ] (P2) Mở rộng TikTok/Instagram sau khi pilot thành công.

### 5.4 Sequencing

1. **Sprint A (P0)**: user playbook scope + visibility + resource injection.
2. **Sprint B (P1)**: YouTube comment adapter PoC via XActions.
3. **Sprint C (P2)**: TikTok/Instagram + marketplace community templates.

---

## Section 6: Checklist Summary

| Section | Status |
|---|---|
| 1. Understand Trigger and Context | [x] Done |
| 2. Epic Impact Assessment | [x] Done |
| 3. Artifact Conflict and Impact Analysis | [x] Done |
| 4. Path Forward Evaluation | [x] Done |
| 5. Sprint Change Proposal Components | [x] Done |
| 6. Final Review and Handoff | [x] Done |

---

*End of Sprint Change Proposal.*
