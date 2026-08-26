# Triage — Story 27.2b Code Review

**Failed layers:** subagent quota exhausted; review chạy trực tiếp trong session.

| id | source | title | severity | route | location |
|---:|---|---|---|---|---|
| 1 | blind+edge+auditor | Migration `202` down_revision tạo branch | high | patch | `alembic/versions/202_add_meeting_minutes_table.py:20` |
| 2 | blind | Migration `id` không khai báo autoincrement | medium | patch | `alembic/versions/202_add_meeting_minutes_table.py:29` |
| 3 | blind+auditor | `language` parameter bị tool bỏ qua | medium | patch | `app/agents/chat/.../tools/meeting_minutes/generate_meeting_minutes.py:31-100` |
| 4 | blind | `/download` endpoint trả JSON thay vì file | medium | patch | `app/routes/meeting_minutes_routes.py:189-216` |
| 5 | blind | `_probe_duration` chạy full transcription hai lần | medium | patch | `app/services/meeting_minutes/service.py:433-450` |
| 6 | blind+auditor | Extraction lỗi vẫn đánh dấu `READY` thay vì `degraded` | medium | patch | `app/services/meeting_minutes/service.py:241-245, 530-588` |
| 7 | blind+edge | Parse speaker label trong diarization không an toàn | medium | patch | `app/services/meeting_minutes/diarization.py:65-66` |
| 8 | blind | `_download_audio` đọc toàn bộ URL vào RAM | medium | patch | `app/services/meeting_minutes/service.py:405-413` |
| 9 | blind | `update_status` không filter workspace | medium | patch | `app/services/meeting_minutes/service.py:334-352` |
| 10 | blind | `create` route không dùng Pydantic validation | low | patch | `app/routes/meeting_minutes_routes.py:89-129` |
| 11 | blind | Tool cho phép cả `audio_url` lẫn `document_id` | low | patch | `app/agents/chat/.../tools/meeting_minutes/generate_meeting_minutes.py:55-66` |
| 12 | blind | `title` không bao giờ được gán | low | patch | `app/services/meeting_minutes/service.py:253-261` |
| 13 | blind | Hàng `PROCESSING` treo nếu worker mất | medium | defer | `app/services/meeting_minutes/service.py:179` |
| 14 | blind | Integration service tests phụ thuộc env var | low | patch | `tests/integration/services/meeting_minutes/...` |
| 15 | auditor | Frontend chat mode / artifact panel chưa implement | high | defer | `nowing_web/...` |

**Dismissed:** 0
