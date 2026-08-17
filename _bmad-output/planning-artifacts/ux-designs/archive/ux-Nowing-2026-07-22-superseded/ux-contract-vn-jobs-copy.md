# UX Copy Contract — Vietnam Job Market (`vn_jobs`)

**Ngày:** 2026-08-05  
**Phạm vi:** Epic 12 — HR/Recruitment Vertical (Vietnam). Chỉ copy, tool names, agent prompt, MCP descriptions, docs, và degradation map. **Không** UI mới, không behavior contract.  
**Bám vào:** FR-43..47 · NFR-11 · OQ-8 · AD-22..26 · SM-12  
**Loại tài liệu:** *copy spec* — định nghĩa strings, descriptions, labels user thấy. Không layout/màu.

---

## 1. Vì sao chỉ cần copy, không cần UI mới

Epic 12 là backend/data epic. Surfaces hiện có đủ:
- Chat/agent: tool call + fallback card.
- MCP server: `nowing_vn_jobs_aggregate`.
- REST API / Playground.
- Docs site (Fumadocs).

Tuy nhiên, **3 hạng mục copy bị thiếu**, làm giảm trust và discoverability:
1. Chat agent không discover `vn_jobs.aggregate` nếu không có subagent description.
2. Tool result JSON thô, không giải thích PII/salary/degraded.
3. PRFAQ links đến docs page chưa tồn tại.

---

## 2. Tool Display Names & Icons

### Chat / Playground / Docs

| Tool key | Display name (en) | Display name (vi) | Icon | Notes |
|---|---|---|---|---|
| `vietnamworks_scrape` | VietnamWorks Jobs | Việc làm VietnamWorks | `Briefcase` | Fallback icon if no dedicated icon. |
| `topcv_scrape` | TopCV Jobs | Việc làm TopCV | `Briefcase` | May show degraded badge if blocked. |
| `itviec_scrape` | ITviec Jobs | Việc làm ITviec | `Briefcase` | |
| `vn_jobs_aggregate` | Vietnam Job Market | Thị trường việc làm VN | `Layers` hoặc `BarChart3` | Aggregate cross-source view. |

### Icon mapping file

`nowing_web/contracts/enums/toolIcons.tsx`:
```tsx
vietnamworks_scrape: { icon: Briefcase, color: "blue" },
topcv_scrape: { icon: Briefcase, color: "orange" },
itviec_scrape: { icon: Briefcase, color: "green" },
vn_jobs_aggregate: { icon: BarChart3, color: "slate" },
```

---

## 3. Capability / MCP Descriptions

### REST / Capability registry

| Capability | Short description | Long description |
|---|---|---|
| `vietnamworks.scrape` | Search VietnamWorks job postings. | Search public VietnamWorks job postings by keyword, location, salary, and employment type. Returns typed job listings. Does not apply or submit CVs. |
| `topcv.scrape` | Search TopCV job postings. | Search TopCV job postings. May degrade if anti-bot protection blocks access. Salary data may be partial. |
| `itviec.scrape` | Search ITviec job postings. | Search ITviec job postings. Salary is often hidden for non-logged-in users; confidence may be lower. |
| `vn_jobs.aggregate` | Aggregate Vietnamese job market data. | Cross-source aggregate of VietnamWorks, TopCV, and ITviec. Normalizes, deduplicates, scores confidence, and flags salary/location conflicts. Research use only. |

### MCP tool descriptions

`nowing_mcp/mcp_server/features/scrapers/platforms/vn_jobs.py`:
- `nowing_vietnamworks_scrape`: "Search VietnamWorks job postings. Use for research; does not apply to jobs."
- `nowing_topcv_scrape`: "Search TopCV job postings. May return degraded results if blocked."
- `nowing_itviec_scrape`: "Search ITviec job postings. Salary may be hidden."
- `nowing_vn_jobs_aggregate`: "Aggregate and compare Vietnamese job postings from VietnamWorks, TopCV, and ITviec. Returns a normalized, deduplicated, confidence-scored view."

---

## 4. Subagent Description

### `app/agents/chat/multi_agent_chat/subagents/builtins/vn_jobs/description.md`

```markdown
# vn_jobs specialist

You are a Vietnamese job market research specialist.

Use `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape`, and `vn_jobs.aggregate` to answer questions about job postings, hiring trends, salary ranges, and skill demand in Vietnam.

Important framing:
- Nowing is a research/memory layer, NOT a job board or ATS.
- Do NOT help users apply to jobs, submit CVs, or contact recruiters on their behalf.
- Salary data may be incomplete or hidden (especially on ITviec). Report confidence scores and sources.
- If a source is degraded, explain which source failed and why.
- Always mention PII redaction: Nowing does not store phone numbers, emails, or personal names from job descriptions.
```

### System prompt key lines

`app/agents/chat/multi_agent_chat/subagents/builtins/vn_jobs/system_prompt.md`:
- "When the user asks about jobs, hiring trends, or salaries in Vietnam, prefer `vn_jobs.aggregate` to cross-source data."
- "If `degraded=true`, say which source failed and summarize what is still available."
- "For salary questions, mention `salary_confidence` and `salary_consistency_score`."
- "Never frame the result as an application or recommendation to apply."

---

## 5. Human-Readable Degradation Map

`degradation_reasons` từ aggregator là `list[str]` dạng `"{source}: {reason}"`. Map sang plain language cho UI và agent:

| Raw reason | English message | Vietnamese message |
|---|---|---|
| `vietnamworks: api_error` | VietnamWorks API temporarily unavailable. | VietnamWorks API tạm thời không khả dụng. |
| `topcv: cloudflare_challenge` | TopCV blocked by anti-bot protection. | TopCV bị chặn bởi bảo vệ chống bot. |
| `itviec: invalid_input` | ITviec request could not be built. | Yêu cầu ITviec không hợp lệ. |
| `itviec: salary_hidden` | ITviec hides salary for non-logged-in users. | ITviec ẩn lương với người dùng chưa đăng nhập. |
| `topcv: disabled` | TopCV disabled by ToS/legal decision. | TopCV bị tắt theo quyết định ToS/pháp lý. |
| `vn_jobs: unknown_source` | Unknown source requested. | Nguồn không xác định được yêu cầu. |

UI hiển thị badge `degraded` + tooltip chứa message. Agent nhắc đến trong câu trả lời.

---

## 6. PII / Salary / Trust Strings

### Agent final answer template

```
I found {total} listings from {sources}.

- {vietnamworks_count} from VietnamWorks
- {topcv_count} from TopCV
- {itviec_count} from ITviec

Notes:
- Salary may be hidden or marked "negotiable" on some sources (confidence: {salary_confidence}).
- Personal contact info (phone, email, names) has been redacted before storage.
- {degraded_message}
```

### Tool result card strings

- **PII redacted label:** "Personal contact info removed" / "Đã loại bỏ thông tin liên hệ cá nhân"
- **Salary hidden label:** "Salary not shown" / "Lương không hiển thị"
- **Negotiable label:** "Negotiable" / "Thương lượng"
- **Degraded badge:** "Partial result" / "Kết quả một phần"
- **Conflict badge:** "Salary/location conflict across sources" / "Lương/địa điểm không nhất quán giữa các nguồn"

---

## 7. Docs Page

### `content/docs/connectors/native/vn_jobs.mdx`

**Title:** Vietnam Job Market (`vn_jobs`)

**Sections:**
1. What is it — research aggregate, not a job board.
2. Sources — VietnamWorks, TopCV, ITviec.
3. PII handling — phone/email/names redacted.
4. Salary caveats — hidden, negotiable, confidence score.
5. How to use — REST, MCP, chat agent.
6. Pricing — per-query + per-item; degraded sources not billed.
7. Pilot status — 8-week pilot, 20–50 workspaces, feedback.

---

## 8. Playground Catalog (nếu trong pilot scope)

`nowing_web/lib/playground/catalog.ts`:
```ts
{ id: "vietnamworks", name: "VietnamWorks", category: "jobs", capability: "vietnamworks.scrape" },
{ id: "topcv", name: "TopCV", category: "jobs", capability: "topcv.scrape" },
{ id: "itviec", name: "ITviec", category: "jobs", capability: "itviec.scrape" },
{ id: "vn_jobs", name: "Vietnam Job Market", category: "jobs", capability: "vn_jobs.aggregate" },
```

`platform-icons.tsx`:
```ts
const JOB_ICON = Briefcase;
```

---

## 9. Implementation Notes for Dev

- Các strings trên được hard-code trong capability description và subagent prompt. Không cần i18n đầy đủ ở pilot.
- `degradation_reasons` map nên là static map trong `nowing_web/lib/i18n/vn-jobs-degraded.ts` và backend `app/services/jobs_aggregator/messages.py`.
- Tool icon mapping thêm vào `toolIcons.tsx`.
- Subagent package cần được tạo theo pattern `batdongsan`.
