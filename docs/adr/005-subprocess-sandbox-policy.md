# ADR-005: Sandbox policy cho `subprocess`/`Popen`/`eval`

## Status

Accepted — dự kiến thực hiện (Giai đoạn F)

## Context

Một số điểm chạy external command hoặc eval:
- `app/services/web_builder/builder.py`
- `app/services/web_builder/deploy_service.py`
- `app/routes/admin_scraper_platform_accounts_routes.py`
- `app/agents/video_presentation/nodes.py`
- `app/services/presentation/marp_driver.py`
- `app/templates/export_helpers.py`
- `app/tasks/chat/streaming/handlers/tools/filesystem/ls/thinking.py` (`ast.literal_eval`)
- `app/agents/chat/multi_agent_chat/shared/middleware/filesystem/sandbox.py`

User input hoặc output LLM có thể lọt vào command/args gây command injection hoặc sandbox escape.

## Decision

### Subprocess/Popen
- **Không dùng `shell=True`**.
- **Không pass user input trực tiếp** vào command/args.
- Dùng allow-list cho command và working directory.
- Chạy web builder/scraper trong Daytona sandbox hoặc container riêng.
- Timeout cứng, kill orphan process.
- `Popen` ở admin route đưa thành Celery task với timeout.

### eval / literal_eval
- Không dùng `eval()`/`exec()` với input từ user/LLM.
- `ast.literal_eval` chỉ dùng khi input đã qua sandbox/validation; không dùng với user raw.

### Logging & audit
- Ghi log command, args, cwd, user_id, workspace_id trước khi chạy.
- Trả lỗi client-safe, không expose command/path.

## Consequences

- Giảm rủi ro command injection và sandbox escape.
- Có thể tăng latency do sandbox/container; cần benchmark trước khi bật buộc.
- Cần audit toàn bộ điểm còn lại.

## Related

- [[ADR-003-split-routes-and-services]]
