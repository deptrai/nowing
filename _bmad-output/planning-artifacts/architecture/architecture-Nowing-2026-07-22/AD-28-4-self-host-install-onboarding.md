---
title: "AD-28.4 — Self-Host OSS Onboarding in Under 10 Minutes"
status: ADOPTED
date: 2026-08-21
owner: Architecture / DevOps
binds: FR-98, AR-14, INV-28.3
---

# AD-28.4 — Self-Host OSS Onboarding in Under 10 Minutes

## Context

Nowing là open-core (Apache-2.0 core + BSL 1.1 crawler engine). Self-host phải là aha moment cho dev mà không cần cloud account. Mục tiêu <10 phút từ zero đến `nowing_remember` + `nowing_recall` hoạt động.

## Decision

### Install script

- `install.sh` curl-bootstrap từ GitHub release.
- Detect OS (Linux/macOS/WSL2), Docker availability, port conflicts (Postgres 5432, Redis 6379, backend 8000, web 3000).
- Nếu port conflict → prompt + ghi `.env` override.
- Không cần cloud API key để chạy core.

### Local model default

- Nếu không có OpenAI/Anthropic key, script hỏi người dùng có muốn dùng **Ollama** không.
- Default models: `nomic-embed-text` (embedding), `llama3.1` (chat/LLM, 8B).
- `LOCAL_MODEL=true` trong `.env`; backend sử dụng local LiteLLM-compatible endpoints.

### Docker compose services

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
  redis:
    image: redis:7-alpine
  backend:
    build: ./nowing_backend
    env_file: .env
  web:
    build: ./nowing_web
    env_file: .env
  mcp:
    build: ./nowing_mcp
    env_file: .env
```

### Offline path

- Hỗ trợ pre-pull Ollama image qua `ollama pull ...` trước khi chạy `install.sh`.
- `install.sh --offline` bỏ qua curl check, yêu cầu image đã có locally.

### Cloud research (optional, v2)

- Khi user thêm `NOWING_CLOUD_API_URL` + `NOWING_SELF_HOST_API_KEY`, deep-research engine được route qua Nowing Cloud metered API.
- V1 không phụ thuộc Epic 9.5 (deferred); v2 mới bind.

### CI smoke

- Nightly Ubuntu VM chạy `install.sh` trên fresh runner, verify `http://localhost:3000` reachable và `nowing_recall` trả kết quả.

## Consequences

- **Positive:** OSS motion có concrete aha moment.
- **Positive:** Giảm reliance cloud API key cho first-run.
- **Negative:** Ollama 8B chậm hơn cloud; cần đặt kỳ vọng rõ ràng.
- **Risk:** Port conflict detection trên Windows/WSL2 phức tạp; cần test matrix.
