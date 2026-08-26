# Acceptance Auditor Findings — Story 27.2b

> Diff được so sánh với `_bmad-output/implementation-artifacts/stories/27-2b-speaker-diarization-meeting-minutes.md`.

1. **Thiếu trạng thái `degraded` rõ ràng (Spec intent + AC-3).**
   - Spec: *"Graceful degradation: if diarization is unavailable, the system still returns a transcript and a clear `degraded` state without crashing."*
   - Evidence: `app/services/meeting_minutes/service.py:241-245` set `row.status = MeetingMinutesStatus.READY` sau khi `_diarize` / `_degraded_segments` trả về single-speaker transcript. Không có `degraded` status hoặc flag nào trong output.

2. **Ngôn ngữ (`language`) không thực sự được dùng (Spec — gợi ý `en`, `vi`).**
   - Tool `generate_meeting_minutes` nhận `language` ở `app/agents/chat/multi_agent_chat/main_agent/tools/meeting_minutes/generate_meeting_minutes.py:31` nhưng chỉ lưu vào `NewChatThread.platform_metadata` (dòng 95-100). `service._transcribe` ở `service.py:445` đọc `row.meeting_metadata`, không phải thread metadata. Transcription sẽ tự động detect language, không tôn trọng hint.

3. **Download endpoint không cung cấp file tải về (Spec intent + download_url).**
   - Spec / UX đề cập download. `app/routes/meeting_minutes_routes.py:189-216` route `/download` trả JSON response, không phải `FileResponse`/`StreamingResponse`. `GenerateMeetingMinutesOutput.download_url` (`service.py:133`) hứa hẹn `/download` nhưng endpoint trả JSON inline.

4. **Frontend chat mode / quick chip / slash prompt chưa có trong diff (AC-1 / Goal).**
   - Diff chỉ có backend. `nowing_web/tests/meeting-minutes/meeting-minutes-chat.spec.ts` là scaffold chưa hoàn thiện. Không có thay đổi `ArtifactKind`, `GROUP_ORDER`, hoặc composer UI. Đây là phạm vi còn thiếu.

5. **Quyền truy cập `FULL_ACCESS` thay vì member (AC-5 / AC-6).**
   - `app/routes/meeting_minutes_routes.py:37-43` dùng `Permission.FULL_ACCESS.value` trong `require_workspace_member`. Nếu spec cho phép mọi member workspace dùng tính năng, chỉ cần `MEMBER` hoặc tương đương. Cần xác nhận RBAC intent.

6. **`generate_meeting_minutes` tool không reject khi cung cấp cả `audio_url` lẫn `document_id` (Spec — single audio source).**
   - Tool dòng 55 chỉ check cả hai đều None; `service.create` có XOR check, nhưng tool nên reject sớm với message rõ ràng.

7. **Thiếu index `(workspace_id, created_at)` trên `token_usage` (Spec note AC-7 / Dev Notes).**
   - Dev Notes gợi ý nếu query chậm mới thêm, không bắt buộc. Tuy nhiên `service.record_token_usage` gọi chung, chưa kiểm tra performance. Không phải lỗi nhưng cần theo dõi.

8. **Migration `202` down_revision tạo branch (không liên quan trực tiếp AC nhưng cản trở deploy).**
   - `alembic/versions/202_add_meeting_minutes_table.py:20` down_revision `697ee5945395` không phải head hiện tại. Deploy sẽ gặp nhiều head.
