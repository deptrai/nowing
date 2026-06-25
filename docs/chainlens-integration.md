# Chainlens Deep Research Integration

## Mục đích

Chainlens Deep Research là engine nghiên cứu web chuyên sâu bên ngoài (B2B API) — Nowing tích hợp như một upgrade cho tính năng deep research, với cơ chế **graceful fallback** về `generate_report` built-in khi Chainlens không khả dụng.

Feature flag `CHAINLENS_RESEARCH_ENABLED` cho phép Admin/DevOps:
- Bật/tắt feature **không cần redeploy code** (FR26 No-Redeploy Toggle)
- Rollback nhanh khi vendor có vấn đề (outage, rate limit, key rotate)
- Phased rollout (bật trên staging trước, sau đó production)

Khi tắt hoặc khi Chainlens API không trả lời, service tự động dùng `generate_report` built-in — **người dùng không thấy error** (FR25 Silent Fallback).

## Cách lấy API Key

Liên hệ Chainlens team để được cấp B2B API key:

- Email hoặc portal: Liên hệ Chainlens admin của tổ chức bạn
- API key có dạng chuỗi dài (~64 chars), lưu giữ như credential bí mật

## Cách bật (3 bước)

```bash
# Bước 1: Edit .env (hoặc CI/CD secrets)
CHAINLENS_RESEARCH_API_URL=https://api.chainlens.example.com
CHAINLENS_RESEARCH_API_KEY=<paste-your-key-here>
CHAINLENS_RESEARCH_ENABLED=true
CHAINLENS_HEALTH_CACHE_TTL=30  # optional, default 30s

# Bước 2: Restart backend (không cần rebuild)
docker compose restart backend
# hoặc local dev:
# ctrl+c → uvicorn app.app:app --reload

# Bước 3: Verify startup log có dòng:
# [Chainlens] Integration ENABLED — URL=https://..., health cache TTL=30s
```

> **Lưu ý:** Env vars chỉ được đọc 1 lần khi service khởi động. Phải restart — hot reload không có hiệu lực.

## Cách tắt / Rollback (1 bước)

```bash
# Bước 1: Đổi env var
CHAINLENS_RESEARCH_ENABLED=false

# Bước 2: Restart
docker compose restart backend

# Verify startup log:
# [Chainlens] Integration DISABLED (CHAINLENS_RESEARCH_ENABLED=false) — using built-in research only
```

User **không bị gián đoạn** — deep research tự động dùng `generate_report` built-in, không có error UI.

## Verify Health Check (trước khi bật production)

Kiểm tra Chainlens API reachable từ server trước khi bật flag:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.chainlens.example.com/api/v1/b2b/health
# Expected: 200
```

Nếu 200 OK → safe to enable. Nếu khác → contact Chainlens team trước.

## Troubleshooting

| Triệu chứng | Nguyên nhân | Cách fix |
|---|---|---|
| Startup log "WARNING ... missing" | Thiếu `CHAINLENS_RESEARCH_API_URL` hoặc `CHAINLENS_RESEARCH_API_KEY` (hoặc whitespace-only) | Set đầy đủ env, restart |
| `ValueError` khi boot service | `CHAINLENS_HEALTH_CACHE_TTL` không phải số nguyên — raised ở **`Config` class load time** (`int(...)` trong `app/config/__init__.py`), KHÔNG phải từ `_validate_chainlens_config()` (validator wrap try/except, never raises) | Set giá trị int hợp lệ (vd: `30`), restart |
| User không thấy Chainlens result dù đã bật | Health check fail (Chainlens API down) | `curl .../api/v1/b2b/health`, kiểm tra API key |
| Startup log "DISABLED" dù đã set `ENABLED=true` | Giá trị không được parse như truthy. Story 7.1 dùng `.upper() == "TRUE"`, nên các value như `true`, `True`, `TRUE`, `tRuE` đều OK (case-insensitive). KHÔNG accept `1`, `yes`, `on`, `t`, `y` | Set `true` (case-insensitive), restart |

## Related

- Architecture overview: `_bmad-output/planning-artifacts/architecture.md` — section "Deep Research — Chainlens Integration Architecture"
- Service implementation: `nowing_backend/app/services/chainlens_research_service.py` (Story 7.1)
- LangGraph tool: `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` (Story 7.2)
- Stream event handler: `nowing_backend/app/tasks/chat/stream_new_chat.py` (Story 7.3)
- Startup config validation: `nowing_backend/app/app.py` — `_validate_chainlens_config()` (Story 7.4)
