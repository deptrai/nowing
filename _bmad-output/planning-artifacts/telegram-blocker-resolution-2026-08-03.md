---
title: Epic 11 Blocker Resolution
description: ''
createdAt: '2026-08-03'
---

# Epic 11 Blocker Resolution

## Cơ chế `/run` từ Telegram

**Vấn đề:** Không có trigger type nào cho manual fire; `MANUAL` chỉ là enum reserved.

**Giải pháp:** Dùng transient `AutomationTrigger`.

```python
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.dispatch.launch import launch_run

async def fire_automation_now(
    session: AsyncSession,
    automation: Automation,
    runtime_inputs: dict[str, Any] | None = None,
) -> AutomationRun:
    trigger = AutomationTrigger(
        automation_id=automation.id,
        type=TriggerType.MANUAL,
        params={},
        static_inputs={},
    )
    return await launch_run(
        session=session,
        trigger=trigger,
        runtime_inputs=runtime_inputs or {},
    )
```

- Không cần persist trigger; `AutomationRun.trigger_id` nullable (`SET NULL` on FK) nên `run.trigger_id = None` là hợp lệ.
- `launch_run` vẫn snapshots `AutomationDefinition`, tạo `AutomationRun` PENDING, và enqueue `automation_run_execute`.
- Telegram command handler gọi `fire_automation_now` sau khi `check_permission(..., Permission.AUTOMATIONS_EXECUTE)`.

## Mở rộng `TelegramClient` cho inline keyboard & callback

**Vấn đề:** `TelegramClient.send_message` chưa hỗ trợ `reply_markup`, chưa có callback helpers.

**Giải pháp:**

```python
from telegram import InlineKeyboardMarkup

class TelegramClient:
    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: str | None = None,
        reply_markup: dict | None = None,
    ) -> PlatformSendResult:
        kwargs = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = int(reply_to_message_id)
        if reply_markup:
            kwargs["reply_markup"] = InlineKeyboardMarkup.de_json(reply_markup, self.bot)
        ...

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        await self.bot.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )

    async def edit_message_reply_markup(
        self,
        *,
        chat_id: str,
        message_id: str,
        reply_markup: dict | None = None,
    ) -> None:
        await self.bot.edit_message_reply_markup(
            chat_id=int(chat_id),
            message_id=int(message_id),
            reply_markup=InlineKeyboardMarkup.de_json(reply_markup, self.bot) if reply_markup else None,
        )
```

- `TelegramAdapter.send_message` nhận thêm `reply_markup: dict | None` và forward xuống client.
- `TelegramAdapter.parse_inbound` xử lý `callback_query`: `external_peer_id` lấy từ `callback_query.message.chat.id`, `external_message_id` từ `callback_query.message.message_id`, `text` là `callback_query.data`.

## Migration cho `notification_preferences`

**Vấn đề:** Thêm field/column mới cho Story 11.1 nhưng chưa có migration.

**Giải pháp:**

- Chọn A: thêm `notification_preferences` JSONB trên `User`.
- Tạo Alembic migration, ví dụ:

```python
"""add user notification preferences"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "..."
down_revision = "..."

def upgrade():
    op.add_column("user", sa.Column("notification_preferences", JSONB, nullable=True))

def downgrade():
    op.drop_column("user", "notification_preferences")
```

- Hoặc tạo bảng riêng `user_notification_preferences` nếu cần audit/row-level. Theo `AD-2` thì migration là bắt buộc.
