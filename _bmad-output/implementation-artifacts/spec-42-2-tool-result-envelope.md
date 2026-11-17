---
title: 'Story 42.2 — ToolResultEnvelope: một result contract xuyên mọi boundary'
type: 'implementation'
created: '2026-11-17'
status: 'done'
baseline_revision: '7d0e80402c979f749e7b3f54fc556c08c260e605'
review_loop_iteration: 1
followup_review_recommended: true
warnings: []
deferred:
  - summary: >-
      write_back parse_mcp_result nhận diện lỗi qua prefix "Error:" — envelope
      {status:'failed'} lọt qua như success nếu Medirus meta-tools được wire
      vào write-back sau này.
    evidence: |-
      verification-gap review: shared.py:359-373 parse_mcp_result check
      "Error:" prefix hoặc key `error`; hiện không reachable vì
      MEDIRUS_MCP_CONNECTOR chỉ tạo read meta-tools (tool/http.py:301).
    location: >-
      nowing_backend/app/automations/actions/builtin/write_back/shared.py:359-373
    severity: low
context: []
---

# Story 42.2 — ToolResultEnvelope

## `<intent-contract>`

### Mục tiêu

Mọi tool result ở ranh giới Medirus→agent trả **một schema duy nhất**:
`{status, reason, recovery_hint, items}` — agent không còn nhầm `data:[]`
("kênh sống, không data") với lỗi kênh chết, và mỗi failure kèm recovery hint
cụ thể (credential/file/retest command) thay vì `Error executing ...`.

### Always

- `ToolResultEnvelope` sống ở module MỚI
  `nowing_backend/app/capabilities/core/tool_result.py` — không đặt trong
  `medirus_gateway.py` (module core dùng chung, không import LangChain).
- Shape chính xác (normative, AD-3): `status` ∈
  `'success' | 'empty_result' | 'failed' | 'degraded' | 'preview'` — required;
  `reason: str | None`; `recovery_hint: str | None`; `items: list` — required.
  KHÔNG thêm status value thứ 6, KHÔNG có kiểu `failed` thứ hai.
- `recovery_hint` sanitize + cap **≤500 chars**; khi forward Medirus
  `suggestedAction` verbatim phải đánh dấu `untrusted` trong hint text.
- Hint map `RECOVERY_HINT_MAP` seed đúng 4 code: `MEDIRUS_4001`,
  `MEDIRUS_4010`, `MEDIRUS_4030`, `MEDIRUS_5000`; default branch cho code lạ:
  `hint_map.get(code, {status:'failed', recovery_hint:'generic: check logs, retry'})`.
- Boundary sites emit envelope: `medirus_gateway._format_result` (agent-facing
  string → envelope JSON), `_execute_medirus_tool` error dicts → envelope,
  `medirus_proxy.make_medirus_executor` return dict → envelope keys + extras.
- `dryRun` stub → `status='preview'` — KHÔNG BAO GIỜ trông giống `success`.
- `degraded` (Medirus `meta.degraded` hoặc executor `degraded: true`) →
  `status='degraded'` + `reason` = degradation_reason.

### Never

- KHÔNG rewrite 3 schema executor/gateway/proxy — bọc adapter ở ranh giới
  tool→agent (A1 scope boundary-only). Không đụng `MedirusMcpClient`,
  không đụng local scrapers (`medirus_scrape_or_local` local path).
- KHÔNG forward `suggestedAction` raw không đánh dấu untrusted (PDPD/safety).
- KHÔNG để dryRun emit `status='success'` (AC literal — stub ≠ executed).
- KHÔNG viết hint dictionary cho error code chưa xảy ra (ngoài 4 seed + default).
- KHÔNG đổi behavior `_execute_medirus_tool` về dryRun default (`False`) hay
  `fullData` — chỉ thêm preview flag khi caller truyền `dryRun: true`.

### Decisions

- **D1 — Pydantic model:** `ToolResultEnvelope(BaseModel)` — free validation
  + `model_dump()` JSON-serializable (giống convention `app/schemas/*`);
  `items: list[Any] = []` default.
- **D2 — `from_medirus(result) -> ToolResultEnvelope`:** normalize Medirus
  result dict → envelope; idempotent: input đã có `status`+`items` keys →
  pass-through. Mapping: `dry_run`/`preview` flag → `preview`; `success=False`
  → `failed` (reason=error/message, hint=RECOVERY_HINT_MAP[code] +
  suggestedAction-untrusted); `meta.degraded` → `degraded`; data empty →
  `empty_result`; else `success`. `items` = `data or preview or []`.
- **D3 — `from_exception(exc)`:** generic exception → `failed`,
  `reason=str(exc)`, hint generic; `MedirusMcpError`/`ExternalServiceError`
  có `.code` → tra hint map + `suggested_action` nếu có.
- **D4 — Hint map shape:** mỗi entry = `{credential_needed, config_file,
  retest_command}` (bảng A2); `recovery_hint` compose từ các field non-null +
  append `(untrusted suggestedAction: …)` khi có. Cap 500 sau compose.
- **D5 — Executor emit:** `make_medirus_executor.execute` return
  `{**envelope.model_dump(), cost_micros, total_items, stream,
  degradation_reason}` — giữ mọi key hiện có, thêm 4 contract keys; billing
  consumers đọc `items`/`cost_micros`/`total_items` không vỡ.
- **D6 — Handler early errors:** `medirus_*` handlers trả "Error: ..." strings
  (`scrape` missing target, `crawl_post` missing url) → đổi thành envelope
  `failed` JSON cùng `_format_result` helper — agent nhận 1 shape.

### I/O matrix

| Case | Input | Expected |
|---|---|---|
| SUCCESS | `{success:True, data:[{...}], meta:{}}` | `status='success'`, items=data |
| EMPTY | `{success:True, data:[]}` | `status='empty_result'`, items=[] |
| DEGRADED | `{success:True, data:[...], meta:{degraded:True, degradation_reason:'fb rate-limited'}}` | `status='degraded'`, reason set |
| DRY_RUN | result + `arguments.dryRun=true` | `status='preview'` |
| FAIL_4001 | `{success:False, error:'circuit open', code:'MEDIRUS_4001'}` | `failed` + hint retry/cooldown |
| FAIL_4010 | `{success:False, error:'auth', code:'MEDIRUS_4010', suggestedAction:'set c_user/xs'}` | `failed` + hint gồm cookie + `(untrusted ...)` |
| FAIL_4030 | `{success:False, code:'MEDIRUS_4030'}` | `failed` + hint proxy |
| FAIL_5000 | `{success:False, code:'MEDIRUS_5000'}` | `failed` + hint logs/retry |
| FAIL_UNKNOWN | `{success:False, code:'MEDIRUS_9999'}` | `failed` + `generic: check logs, retry` |
| EXC_GENERIC | `ValueError('boom')` | `failed`, reason='boom', hint generic |
| EXC_CODED | `MedirusMcpError(code='MEDIRUS_4010', suggested_action='...')` | `failed` + 4010 hint |
| IDEMPOTENT | dict đã envelope `{status:'failed', items:[], ...}` | pass-through nguyên |
| HANDLER_VAL | `medirus_scrape` thiếu target group_posts | envelope `failed` JSON string |
| EXECUTOR | proxy execute success/degraded/error | dict có `status`+`reason`+`recovery_hint`+`items` |

## Code Map

- `nowing_backend/app/capabilities/core/tool_result.py` — **NEW**:
  `ToolResultEnvelope`, `RECOVERY_HINT_MAP`, `from_medirus()`,
  `from_exception()`, `_sanitize_hint()`.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:180-235`
  — `_execute_medirus_tool`: sau `call_tool`, `arguments.get("dryRun")` →
  `result["dry_run"]=True`; 2 error dict returns →
  `ToolResultEnvelope.from_exception(exc).model_dump()`.
- `medirus_gateway.py:238-256` — `_format_result`: đổi thành
  `json.dumps(from_medirus(result, tool_name=tool_name).model_dump(), ensure_ascii=False)`.
- `medirus_gateway.py:330,339,410` — 3 early-error strings →
  `json.dumps(from_exception(ValueError(reason)).model_dump())` (hoặc helper
  `_fail(reason)` trong file).
- `nowing_backend/app/capabilities/core/medirus_proxy.py:89-109` — success
  path: bọc data/meta qua `from_medirus`-compatible dict rồi
  `{**envelope.model_dump(), "cost_micros":…, "total_items":…, "stream":…,
  "degradation_reason":…}`; `degraded` flag cũ → `status='degraded'`.
- `app/proprietary/platforms/medirus/mcp_client.py:66-80` —
  `MedirusMcpError(message, code, retry_after, suggested_action)` — đọc
  `.suggested_action` cho D3 (KHÔNG sửa file này).

### Tests

- NEW `tests/unit/capabilities/test_tool_result.py` — tất cả matrix rows:
  4 seed codes + default + generic exception + coded exception + dry_run +
  degraded + empty + idempotent + hint ≤500 + untrusted marker.
- EXTEND `tests/unit/agents/multi_agent_chat/shared/tools/mcp/test_medirus_gateway.py`
  — `_format_result` emits envelope JSON; dryRun arg → preview; handler
  early-error → failed envelope.
- EXTEND `tests/unit/capabilities/test_medirus_proxy.py` — execute return
  dict chứa contract keys; degraded → status='degraded'.

## Tasks & Acceptance

### Execution

- [ ] Viết `tool_result.py`: model + hint map (4 seeds + default) +
  `from_medirus` + `from_exception` + `_sanitize_hint` (≤500, strip control
  chars/newlines, untrusted marker).
- [ ] `medirus_gateway`: `_format_result` → envelope JSON; `_execute_medirus_tool`
  error dicts + dry_run flag; 3 early-error strings → failed envelope.
- [ ] `medirus_proxy`: success return dict bọc envelope.
- [ ] Tests (3 files) cover đủ matrix.

### Acceptance criteria

- [x] `ToolResultEnvelope` + `from_medirus` + `from_exception` + hint map
  seed 4 codes + default branch đúng AC literal.
- [x] `_format_result`/`_execute_medirus_tool`/executor returns đều emit
  envelope `{status, reason, recovery_hint, items}`.
- [x] dryRun → `status='preview'`, không trông giống success.
- [x] `recovery_hint` ≤500 chars + untrusted marker khi có `suggestedAction`.
- [x] Unit tests: seed×4 + default + generic exception + matrix rows — pass.

## Spec Change Log

- 2026-11-17 — draft → ready-for-dev (verify anchors xong).

## Review Triage Log

_(trống — điền khi review xong)_

## Design Notes

- A1 scope boundary-only: chỉ adapter ở `tool→agent` seam; 3 schema nội bộ
  (gateway dict / executor dict / proxy return) giữ nguyên keys hiện có,
  thêm contract keys — backward compatible với `total_items`, `cost_micros`.
- `RECOVERY_HINT_MAP` seeds (A2): 4001=circuit cooldown/retest;
  4010=Facebook `authCookie (c_user/xs)` trong `Medirus/.env` +
  `MEDIRUS_FACEBOOK_ACCOUNT_ID` retest dryRun; 4030=residential proxy
  `Medirus/.env PROXY_*`; 5000=check `medirus-mcp.log` + retry.
- `from_medirus` idempotent để `_execute_medirus_tool` (trả envelope dict)
  và `_format_result` (nhận dict bất kỳ) chain an toàn.

## Verification

```bash
.venv/bin/python -m pytest tests/unit/capabilities/test_tool_result.py \
  tests/unit/capabilities/test_medirus_proxy.py \
  tests/unit/agents/multi_agent_chat/shared/tools/mcp/test_medirus_gateway.py -x -q
```

## Review Triage Log

### 2026-11-17 — Review pass 1

4 layers: blind-hunter (8), edge-case-hunter (8), verification-gap (1 + 1
informational), intent-alignment (COMPLIANT, 4 edge notes). Dedup → 15
findings: 0 high, 4 medium, 5 low, 6 false/unreachable.

**patch (medium)**
- `[medium][patch] BH1/EC1: from_medirus check dry_run trước success-is-False
  → dryRun + in-band {success:false} trả 'preview', nuốt error+hint — failure
  thật bị giả trang stub. Reorder: failed branch trước preview branch.`
- `[medium][patch] BH7/EC3+EC4+EC5+EC6: type assumptions có thể raise xuyên
  boundary — meta/arguments non-dict truthy → .get AttributeError;
  degradation_reason/reason/exc.message non-str → ValidationError;
  error.code unhashable → TypeError trong RECOVERY_HINT_MAP.get. Normalizer
  raise = vi phạm mục tiêu "boundary không bao giờ throw". Sweep: isinstance
  guards + str() coerce.`
- `[low→med][patch] BH3/IA: preview=True (bool flag) leak vào items=[True]
  qua `data or preview or []`. Filter bool ra khỏi items.`
- `[low→med][patch] BH4: _fail() (deterministic arg-validation) emit hint
  "generic: check logs, retry" — khuyến khích retry call chắc chắn fail.
  Emit recovery_hint=None cho _fail path.`

**patch (low)**
- `[low][patch] BH5: XACT_* legacy codes không normalize trước hint lookup —
  XACT_4001 → generic thay vì seeded hint; codebase có precedent normalize
  (medirus_proxy.py:161-163). Map XACT_→MEDIRUS_ trong _hint_for_code.`
- `[low][patch] BH8/EC8: spec matrix shape {suggestedAction camelCase
  top-level} không được _error_suggested_action đọc (chỉ snake top-level +
  camel nested). Thêm result.get("suggestedAction").`
- `[low][patch] VG1-remnant: claim "append raw sau sanitize" FALSE — đã chứng
  minh _hint_for_code sanitize SAU compose (reproduce: dirty 600-char action
  → hint đúng 500 chars, sạch \n/\x00). Remnant hợp lệ: thiếu test assert
  len≤500 + no control chars trên composed hint. Test-only.`
- `[low][patch] BH2a-remnant: passthrough model_validate không guard —
  {"status":"ok-ish","items":[]} → ValidationError raise. try/except fall
  through normalize (cùng nhóm "boundary không raise").`

**reject (false/unreachable)**
- `[reject] BH6/EC2 success falsy-không-phải-False: call_tool (mcp_client.
  py:369-380) build success flag chính nó → luôn bool; "is False" khớp spec
  matrix literal.`
- `[reject] BH2b/EC7b extra='ignore' drop cost_micros trên passthrough:
  unreachable — không chain nào feed executor-output vào from_medirus.`
- `[reject] IA dead param tool_name / EOF newline: cosmetic.`
- `[reject] IA dry_run stamp ngoài try: call_tool luôn trả dict cố định.`

**defer**
- `[defer][low] VG2: app/automations/actions/builtin/write_back/shared.py
  parse_mcp_result nhận diện lỗi qua prefix "Error:" — envelope failed lọt
  qua như success NẾU meta-tools được wire vào write-back sau này (hiện
  không reachable: connector chỉ tạo read meta-tools).`

## Auto Run Result

- **Status:** done (review loop 1, `followup_review_recommended: true` — 2 patched medium)
- **Verified:** spec Verification command 57/57 pass; regression
  `tests/unit/capabilities` + `tests/unit/agents/multi_agent_chat` 1316 pass
  (1 fail `test_parallel_tasks` pre-existing ở baseline, stash-confirmed).
- **Review:** 4 layers — blind-hunter 8, edge-case 8, verification-gap 1+1
  informational, intent-alignment COMPLIANT. Triage: 15 findings → 7 patch
  (reorder dryRun/failed; type-safety sweep meta/arguments/code/reason/
  message/passthrough; preview-bool leak; `_fail` hint=None; XACT→MEDIRUS
  normalize; top-level `suggestedAction`; dirty-hint pin tests), 6 reject,
  1 defer (`parse_mcp_result` envelope-blind — frontmatter `deferred`).
- **Post-patch verify:** 57/57 pass, implementer tự fix thêm `_coerce_items`
  edge `data=[]`+`preview=[...]` được test gốc pin lại.
- **Jev gate:** `needs_deep_review` (0.99) — thỏa bởi review pass ở trên.
