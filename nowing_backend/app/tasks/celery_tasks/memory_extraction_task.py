"""Celery task that extracts durable memory from finalized assistant turns."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.services.memory.extraction import MemoryExtractionService
from app.tasks.celery_tasks import run_async_celery_task

logger = logging.getLogger(__name__)


async def _extract_memory_after_chat_turn(message_id: int) -> None:
    """Load the assistant message and trigger memory extraction."""
    from sqlalchemy.orm import selectinload

    from app.db import NewChatMessage
    from app.tasks.celery_tasks import get_celery_session_maker

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(NewChatMessage)
            .options(selectinload(NewChatMessage.thread))
            .where(NewChatMessage.id == message_id)
        )
        message = result.scalar_one_or_none()
        if message is None:
            logger.warning("Assistant message %s not found for extraction", message_id)
            return

        service = MemoryExtractionService(session=session)
        await service.extract_from_turn(
            thread_id=message.thread_id,
            turn_id=message.turn_id,
            assistant_message_id=message_id,
        )


@celery_app.task(name="extract_memory_after_chat_turn", bind=True)
def extract_memory_after_chat_turn(self, message_id: int) -> None:
    """Best-effort memory extraction after an assistant turn is finalized."""
    return run_async_celery_task(lambda: _extract_memory_after_chat_turn(message_id))
