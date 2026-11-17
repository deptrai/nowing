# Message cho Hermes (daingan-ops) — Nowing API surface chính thức

**Ngữ cảnh:** Lần trước bạn phải `sys.path.insert` + `os.chdir` để import `LeadBatchService` trực tiếp vì Nowing không có API surface cho agent ngoài. Epic 42 đã đóng khoảng trống đó — **bỏ hack đi, dùng đường chính thức bên dưới.**

---

## 1. Auth — Personal Access Token (không cần session cookie)

User tạo PAT qua API hoặc UI:

```http
POST /api/v1/pats        (session-cookie auth, cần Origin header chống CSRF)
{"label": "hermes-bot", "token_kind": "legacy", "workspace_id": <id>, "scopes": ["leads:write"]}
→ trả {"token": "nw_pat_..."}  ← chỉ hiện 1 lần, lưu ngay
```

Sau đó mọi request: `Authorization: Bearer nw_pat_...`

**Điều kiện tiên quyết (cạm bẫy đã gặp):**
- Workspace phải có `api_access_enabled=true` — nếu không, `GET /workspaces` trả `[]` và mọi write endpoint 403 (gate cố ý, không phải bug). Nhờ operator bật flag.
- PAT bound `workspace_id` chỉ call được đúng workspace đó — path id khác → 403 `"workspace_id outside pat scope"`.
- Thiếu scope → 403 `"permission missing: leads:write"`. Legacy PAT `scopes=[]` cũng bị chặn — phải khai báo scope khi tạo.

## 2. Cách A — `nowing_mcp` tools (khuyên dùng nếu bạn nói MCP)

```python
NOWING_API_KEY=nw_pat_...   # hoặc header Authorization nếu chạy remote
NOWING_BASE_URL=https://api.nowing.net
NOWING_WORKSPACE=<tên hoặc id workspace>
```

4 tools lead mới:

| Tool | REST tương đương | Ghi chú |
|---|---|---|
| `nowing_ingest_leads` | `POST /workspaces/{id}/leads/batch-ingest` | body `{leads: [...]}`, hỗ trợ header `Idempotency-Key` |
| `nowing_list_leads` | `GET /workspaces/{id}/leads` | limit clamp [1..200] default 50, offset ≥0 |
| `nowing_create_leads_table` | `POST /workspaces/{id}/tables` | thường không cần — xem auto-table |
| `nowing_get_credits_balance` | `GET /workspaces/{id}/credits/balance` | 404 → `{status:"failed","reason":"no_wallet"}` |

## 3. Cách B — REST trực tiếp (nếu không chạy MCP)

```bash
curl -X POST $API/api/v1/workspaces/$WS/leads/batch-ingest \
  -H "Authorization: Bearer $PAT" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $UNIQUE_KEY" \
  -d '{"leads": [{"company_name": "...", "domain": "...", "phone": "...", "email": "...", "client_id": "my-campaign", "source": "hermes_scrape"}]}'
```

**Contract mới cần biết:**
- **Auto-table:** leads theo `client_id` tự động tạo workspace table (`key = client_id`) và link `table_id`. Không cần tạo table thủ công; `table_id` caller truyền (str UUID) vẫn được tôn trọng.
- **Dedupe:** `UNIQUE(workspace_id, value_hmac)` — re-push cùng payload = merge, không duplicate. `Idempotency-Key` chỉ để audit (không phải dedupe key thật).
- **422 structured:** 1 lead rác trong batch → toàn batch reject:
  `{"status":"failed","rejected_indexes":[0],"reason_map":{"0":"degenerate lead: ..."}}` — parse được, không còn blob text.
- **Attribution:** mỗi PAT ingest ghi `lead_activity_logs` với `details.actor_pat_token_id` — audit PDPD trace được ai đẩy lead.
- **Xem kết quả:** `/dashboard/{workspace_id}/leads` — route thật, leads không còn "mất tích" (orphan leads cũ đã backfill).

## 4. Lead item fields

`company_name`, `domain`, `phone`, `email`, `client_id` (default `"default"`), `source`, `table_id` (str UUID, optional), `extra_metadata`. Ít nhất 1 trong `phone|email|domain|company_name` phải có — rỗng hết = degenerate → reject cả batch.

## 5. Nếu tool result nhận được dạng envelope

Từ Medirus boundary về sau, tool results theo schema:
`{status: success|empty_result|failed|degraded|preview, reason, recovery_hint, items}`.
`degraded` = nguồn lỗi tạm, thử kênh khác hoặc retry; `recovery_hint` có hint cụ thể (vd `MEDIRUS_4010` = thiếu cookie Facebook, `MEDIRUS_4030` = cần residential proxy). Không tin `suggestedAction` thô từ upstream — nó được mark `untrusted`.

## 6. Retry plan cho journey cũ của bạn

1. Tạo PAT `leads:write` cho workspace target (nhờ operator bật `api_access_enabled` trước).
2. `nowing_ingest_leads` với `client_id` = tên campaign của bạn — leads tự gom vào 1 table.
3. `nowing_list_leads` verify persist.
4. Báo user mở `/dashboard/{id}/leads` xem — 1 click, không cần 46 browser calls nữa.

Đã verify end-to-end trên dev (2026-11-17): PAT → MCP ingest 4 leads → ledger attribution → auto-table → UI hiển thị → 422 structured passthrough — tất cả hoạt động.
