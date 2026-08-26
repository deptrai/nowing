# Blind Hunter Findings — Story 27.2b

> Reviewer: adversarial, cynical. Tìm vấn đề bị bỏ sót hoặc làm không đúng.

1. **Migration `202` down_revision sai gốc — tạo branch head.** `alembic/versions/202_add_meeting_minutes_table.py:20` đặt `down_revision = "697ee5945395"`, nhưng migration `2014b3fa9eda_add_workspace_presentation_studio_.py` đã dựa trên `697ee5945395`. Kết quả: `202` và `2014b3fa9eda` song song, tạo hai head. Cần điểm `down_revision` tới `2014b3fa9eda`.

2. **`id` trong migration không autoincrement.** `202_add_meeting_minutes_table.py:29` khai báo `sa.Integer(), nullable=False, primary_key=True` nhưng thiếu `autoincrement=True`. Dù SQLAlchemy có thể tự động, rõ ràng hơn nên khai báo `sa.Integer, autoincrement=True, primary_key=True`.

3. **`generate_meeting_minutes` tool bỏ qua tham số `language`.** `app/agents/chat/multi_agent_chat/main_agent/tools/meeting_minutes/generate_meeting_minutes.py:31-45` nhận `language` nhưng chỉ ghi vào `NewChatThread.platform_metadata`; không truyền vào `service.create`. `service._transcribe` đọc `row.meeting_metadata.get("language")`, nên hint ngôn ngữ bị bỏ qua hoàn toàn.

4. **Tool cho phép cung cấp cả `audio_url` lẫn `document_id`.** Tool chỉ kiểm tra `if not audio_url and not document_id`; không kiểm tra XOR. Người dùng có thể gửi cả hai, `service.create` sẽ từ chối, nhưng UX tốt hơn nên từ chối sớm.

5. **`/download` route trả JSON thay vì file download.** `app/routes/meeting_minutes_routes.py:189-216` route tên `download` nhưng trả dict JSON. User kỳ vọng `FileResponse` hoặc attachment. Đặt tên `download_url` trong output mà không có file để tải về.

6. **`_probe_duration` chạy full transcription hai lần.** `app/services/meeting_minutes/service.py:433-440` gọi `stt_service.transcribe_file`, sau đó `service.py:442-450` lại gọi `stt_service.transcribe_file_segments`. Chi phí tính toán gấp đôi. Nên lấy duration từ `transcribe_file_segments` hoặc dùng `ffprobe` / `mutagen`.

7. **`_extract_summary_and_actions` bị lỗi vẫn đánh dấu `READY`.** `app/services/meeting_minutes/service.py:530-588` catch `Exception` trả `("", [])` rồi `process` set `row.status = READY` ở dòng 245. Spec yêu cầu trạng thái `degraded` rõ ràng khi extraction/diarization thất bại.

8. **`DiarizationService` parse nhãn speaker không an toàn.** `app/services/meeting_minutes/diarization.py:65-66` dùng `int(speaker.split('_')[-1]) + 1`. Nếu pyannote trả nhãn không theo mẫu `SPEAKER_XX` (ví dụ `SPEAKER_A`, `UNKNOWN`), sẽ crash.

9. **Hàng bị `PROCESSING` treo mãi nếu worker mất.** `app/services/meeting_minutes/service.py:179` set `status = PROCESSING` rồi `await session.commit()` trước khi làm việc. Nếu Celery worker mất hoặc container restart, hàng ở trạng thái `PROCESSING` vĩnh viễn. Thiếu timeout / stale-job reaper.

10. **`_download_audio` đọc toàn bộ URL vào RAM mới check size.** `app/services/meeting_minutes/service.py:405-413` gọi `client.get()` rồi `len(response.content) > MAX`. File lớn đã nạp hết vào memory trước khi từ chối. Nên stream hoặc head request.

11. **`create` route không validate bằng Pydantic schema.** `app/routes/meeting_minutes_routes.py:89-129` dùng `await request.json()` trực tiếp. Không có schema, không strip, không kiểm tra `audio_url` scheme. Có thể nhận payload bất hợp lệ.

12. **`update_status` không filter workspace.** `app/services/meeting_minutes/service.py:334-352` query `MeetingMinutes.id == meeting_minutes_id` không giới hạn `workspace_id`. Worker có thể update row của workspace khác nếu biết id.

13. **`MeetingMinutes.title` không bao giờ được gán.** Model có `title` nhưng `process` không set. API luôn trả `title: null`. Nên tạo title từ summary hoặc đầu vào.

14. **Integration service tests phụ thuộc env var `MEETING_MINUTES_ENABLED`.** `tests/integration/services/meeting_minutes/test_meeting_minutes_service.py` cần `MEETING_MINUTES_ENABLED=true` để chạy; route tests thì patch config. Test isolation kém — nên patch trong fixture.
