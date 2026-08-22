"""Two-Way AI Outreach Auto-Reply Agent & Intent Classifier (Story 24.6).

Adheres to:
- INV-24.7: Grounded responses (temperature=0.0, >=0.75 cosine similarity threshold, strict fallback).
- INV-24.8: Human takeover handover & 24h auto-reply pause sync.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from litellm import completion_cost
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Chunk, Document, Lead, Workspace, async_session_maker
from app.redis_client import get_redis_client as _get_shared_redis_client
from app.services.token_tracking_service import UsageType, record_token_usage

logger = logging.getLogger(__name__)


async def get_redis_client():
    return await _get_shared_redis_client()


async def is_auto_reply_paused(thread_id: str) -> bool:
    """Checks if AI Auto-Reply is paused for this thread (e.g. human takeover or hot lead)."""
    if not thread_id:
        return False
    try:
        redis = await get_redis_client()
        key = f"auto_reply_paused:{thread_id}"
        exists = await redis.exists(key)
        return bool(exists)
    except Exception as e:
        logger.error("Error checking auto_reply_paused status for %s: %s", thread_id, e)
        # ponytail: fail-closed: if Redis is down, do not auto-reply during a supposed human takeover.
        return True


async def pause_auto_reply(thread_id: str, duration_seconds: int = 86400) -> None:
    """Pauses AI Auto-Reply for 24h (or specified duration) for human sales takeover."""
    if not thread_id:
        logger.warning("pause_auto_reply called with empty thread_id")
        return
    try:
        redis = await get_redis_client()
        key = f"auto_reply_paused:{thread_id}"
        await redis.setex(key, duration_seconds, "1")
        logger.info("Paused auto-reply for thread %s for %ds", thread_id, duration_seconds)
    except Exception as e:
        logger.error("Error pausing auto_reply for %s: %s", thread_id, e)


@dataclass
class AutoReplyResult:
    reply_text: str
    is_answered: bool = True
    is_fallback: bool = False
    intent_score: float = 0.0
    is_hot_intent: bool = False
    intent_reason: str = ""
    matched_chunks: list[dict[str, Any]] = field(default_factory=list)


class InboundIntentClassifier:
    """Classifies buying signals and high-intent requests from prospects."""

    HOT_INTENT_PATTERNS = [
        (re.compile(r"(bảng giá|báo giá|giá bao nhiêu|bao nhiêu tiền|chi phí|báo phí)", re.IGNORECASE), 0.90, "Yêu cầu báo giá / bảng giá"),
        (re.compile(r"(hẹn xem|xem nhà|đi xem|lịch xem|coi nhà|xem thực tế)", re.IGNORECASE), 0.95, "Yêu cầu lịch hẹn xem nhà"),
        (re.compile(r"(số điện thoại|sđt|liên hệ|gọi cho tôi|gọi lại|alo|tư vấn trực tiếp)", re.IGNORECASE), 0.85, "Yêu cầu liên hệ / gọi tư vấn"),
        (re.compile(r"(đặt cọc|giữ chỗ|hợp đồng|mua ngay|thanh toán thế nào)", re.IGNORECASE), 0.95, "Ý định chốt cọc / hợp đồng"),
        (re.compile(r"(trả góp|vay ngân hàng|lãi suất|hỗ trợ vay)", re.IGNORECASE), 0.80, "Hỏi chính sách vay & tài chính"),
    ]

    def evaluate_intent(self, text: str) -> tuple[float, str, bool]:
        """Evaluates text and returns (score, reason, is_hot). Score >= 0.80 is considered hot."""
        clean_text = (text or "").strip()
        if not clean_text:
            return 0.0, "Không có nội dung", False

        highest_score = 0.0
        primary_reason = "Trao đổi thông thường"

        for pattern, score, reason in self.HOT_INTENT_PATTERNS:
            if pattern.search(clean_text) and score > highest_score:
                highest_score = score
                primary_reason = reason

        is_hot = highest_score >= 0.80
        return highest_score, primary_reason, is_hot


class AutoReplyAgent:
    """2-Way AI Auto-Reply Agent grounded in Workspace Knowledge Base."""

    SAFE_FALLBACK_TEXT = (
        "Dạ em xin phép ghi nhận thông tin và chuyển chuyên viên phụ trách liên hệ tư vấn chi tiết cho anh/chị ngay ạ!"
    )
    COSINE_SIMILARITY_THRESHOLD = 0.75

    def __init__(self, intent_classifier: InboundIntentClassifier | None = None):
        self.classifier = intent_classifier or InboundIntentClassifier()

    async def _retrieve_knowledge_chunks(
        self, workspace_id: int, query: str, collection_ids: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """Retrieves top semantic chunks from the workspace documents."""
        try:
            emb_model = config.embedding_model_instance
            if not emb_model:
                return []

            query_vector = await emb_model.aembed_query(query)
            async with async_session_maker() as session:
                workspace = await session.get(Workspace, workspace_id)
                if workspace is None:
                    logger.warning("Workspace %s not found for auto-reply RAG", workspace_id)
                    return []

                # Find matching documents in workspace, optionally filtered to selected collections.
                doc_query = select(Document.id).where(
                    Document.workspace_id == workspace_id,
                    Document.status == "indexed",
                )
                if collection_ids:
                    # ponytail: collection_ids are document ids in this first cut.
                    doc_query = doc_query.where(Document.id.in_(collection_ids))
                doc_res = await session.execute(doc_query)
                doc_ids = doc_res.scalars().all()
                if not doc_ids:
                    return []

                # Cosine distance search on chunks
                similarity_expr = 1 - Chunk.embedding.cosine_distance(query_vector)
                chunk_query = (
                    select(Chunk.content, similarity_expr.label("similarity"))
                    .where(
                        Chunk.document_id.in_(doc_ids),
                        Chunk.embedding.is_not(None),
                        Chunk.content.is_not(None),
                    )
                    .order_by(similarity_expr.desc())
                    .limit(5)
                )
                res = await session.execute(chunk_query)
                rows = res.all()
                return [
                    {"content": row[0], "similarity": float(row[1])}
                    for row in rows
                    if row[0] is not None
                ]
        except Exception as e:
            logger.warning("RAG retrieval failed in auto-reply agent: %s", e)
            return []

    async def _generate_llm_response(
        self,
        prompt: str,
        context: str,
        session: AsyncSession | None = None,
        workspace_id: int | None = None,
        user_id: UUID | None = None,
    ) -> str:
        """Generates grounded answer using LLM router with temperature=0.0."""
        try:
            from app.services.llm_router_service import LLMRouterService

            router = LLMRouterService.get_router()
            if not router:
                logger.warning("LLM router not initialized for auto-reply; using fallback")
                return self.SAFE_FALLBACK_TEXT

            system_prompt = (
                "Bạn là trợ lý tư vấn bán hàng chuyên nghiệp, tận tâm và ngắn gọn.\n"
                "QUY TẮC BẮT BUỘC:\n"
                "1. Chỉ trả lời dựa trên tài liệu sau đây. Không được tự bịa đặt giá cả, chiết khấu hay cam kết pháp lý.\n"
                "2. Xưng hô lịch sự, thân thiện (Dạ/em chào anh/chị).\n"
                "3. Trả lời tối đa trong 2-3 câu ngắn.\n\n"
                f"--- TÀI LIỆU THAM CHIẾU ---\n{context}\n----------------------------"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            model = getattr(config, "AUTO_REPLY_MODEL", "auto")
            response = await router.acompletion(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=250,
            )
            content = (response.choices[0].message.content or "").strip()

            # Record token usage for cost visibility if we have a billing session.
            if session is not None and workspace_id is not None and user_id is not None:
                usage = getattr(response, "usage", None) or {}
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                total_tokens = getattr(usage, "total_tokens", 0) or 0
                cost_usd = 0.0
                try:
                    cost_usd = float(completion_cost(completion_response=response) or 0.0)
                except Exception:
                    logger.debug("Could not compute auto-reply cost via litellm")
                cost_micros = round(cost_usd * 1_000_000)
                model_name = getattr(response, "model", None) or model or "unknown"
                await record_token_usage(
                    session,
                    usage_type=UsageType.ASSISTED_DRAFT,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_micros=cost_micros,
                    model_breakdown={
                        model_name: {
                            "provider": "llm_router",
                            "cost_micros": cost_micros,
                            "total_tokens": total_tokens,
                        }
                    },
                    call_details={"auto_reply": True},
                )

            return content or self.SAFE_FALLBACK_TEXT
        except Exception as e:
            logger.warning("LLM completion failed for auto-reply: %s", e)
            return self.SAFE_FALLBACK_TEXT

    async def _dispatch_hot_lead_alert(
        self,
        session: AsyncSession,
        workspace_id: int,
        channel: str,
        sender_id: str,
        thread_id: str,
        intent_reason: str,
        message_content: str,
        lead: Any | None = None,
        recipient_chat_id: str | None = None,
    ) -> None:
        """Dispatch a Telegram interactive alert for hot buying intent (AC-3)."""
        try:
            from app.gateway.telegram.client import TelegramClient
            from app.gateway.zalo.telegram_alerts import (
                _resolve_telegram_chat_and_token,
                build_lead_telegram_alert,
            )

            workspace = await session.get(Workspace, workspace_id)
            if workspace is None:
                logger.warning("Hot lead alert skipped: workspace %s not found", workspace_id)
                return

            # Resolve the Telegram chat id to notify from workspace settings.
            target_chat_id = recipient_chat_id or workspace.auto_reply_recipient_chat_id

            if not target_chat_id:
                logger.warning("Hot lead alert skipped: no recipient chat id for workspace %s", workspace_id)
                return

            # Validate the chat id belongs to a bound workspace Telegram channel
            # and resolve the bot token (bound account token or shared fallback).
            chat_id, token = await _resolve_telegram_chat_and_token(
                session, workspace_id, target_chat_id
            )
            if not chat_id or not token:
                logger.warning(
                    "Hot lead alert skipped: unauthorized or missing Telegram chat/token for workspace %s",
                    workspace_id,
                )
                return

            lead_name = "Khách hàng tiềm năng"
            phone = ""
            lead_id_str = None
            if lead is not None:
                lead_name = lead.company_name or lead_name
                phone = getattr(lead, "phone", "") or ""
                lead_id_str = str(lead.id) if lead.id else None

            text, keyboard = build_lead_telegram_alert(
                lead_name=lead_name,
                company_name=lead_name,
                phone=phone,
                source=channel,
                intent=intent_reason,
                message_content=message_content,
                workspace_id=workspace_id,
                lead_id=lead_id_str,
            )
            # Append the [Nhận Tư Vấn] inline button for human takeover.
            keyboard.setdefault("inline_keyboard", [[]])
            keyboard["inline_keyboard"].append(
                [
                    {
                        "text": "\u2705 Nhận Tư Vấn",
                        "callback_data": self._build_nhan_tu_van_callback_data(
                            thread_id, lead_id_str
                        ),
                    }
                ]
            )

            client = TelegramClient(token)
            await client.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
            logger.info(
                "Hot lead alert sent for workspace=%s channel=%s sender=%s thread=%s",
                workspace_id,
                channel,
                sender_id,
                thread_id,
            )
        except Exception as e:
            logger.error("Failed to dispatch hot lead alert: %s", e, exc_info=True)

    def _build_nhan_tu_van_callback_data(
        self, thread_id: str, lead_id: str | None
    ) -> str:
        """Build a short Telegram callback_data string that fits the 64-byte limit."""
        data = f"ntv:{thread_id}:{lead_id or ''}"
        if len(data.encode("utf-8")) > 64:
            # If somehow still too long, drop the lead_id and let the handler
            # reject the click with a clear message instead of breaking Telegram.
            return "ntv:overflow:"
        return data

    async def _get_or_create_lead(
        self,
        session: AsyncSession,
        workspace_id: int,
        sender_id: str,
        channel: str,
    ) -> Any | None:
        """Find an existing lead by external sender id or create a new one."""
        try:
            result = await session.execute(
                select(Lead).where(
                    Lead.workspace_id == workspace_id,
                    Lead.client_id == sender_id,
                )
            )
            lead = result.scalars().first()
            if lead is not None:
                return lead

            # Create a placeholder lead for a first-time hot prospect so the
            # human takeover callback has a valid lead_id to assign.
            value_hmac = hashlib.sha256(
                f"{workspace_id}:{channel}:{sender_id}".encode()
            ).hexdigest()
            lead = Lead(
                id=uuid4(),
                workspace_id=workspace_id,
                client_id=sender_id,
                source=channel,
                company_name="Khách hàng tiềm năng",
                value_hmac=value_hmac,
                status="new",
                enriched=False,
                intent_score=0.0,
            )
            session.add(lead)
            await session.flush()
            logger.info(
                "Created lead %s for auto-reply sender %s in workspace %s",
                lead.id,
                sender_id,
                workspace_id,
            )
            return lead
        except Exception:
            logger.exception("Failed to get or create lead for auto-reply")
            return None

    async def generate_reply(
        self,
        workspace_id: int,
        channel: str,
        sender_id: str,
        text: str,
        thread_id: str = "",
        session: AsyncSession | None = None,
        user_id: UUID | None = None,
        fallback_text: str | None = None,
    ) -> AutoReplyResult:
        """Processes incoming prospect message, runs intent detection, RAG retrieval, and generates reply."""
        # 1. Check if thread is paused
        if thread_id and await is_auto_reply_paused(thread_id):
            logger.info("Auto-reply is paused for thread %s. Skipping reply.", thread_id)
            return AutoReplyResult(
                reply_text="",
                is_answered=False,
                is_fallback=False,
            )

        # 2. Evaluate Buying Intent
        intent_score, intent_reason, is_hot = self.classifier.evaluate_intent(text)

        # 3. Load workspace settings and resolve fallback.
        collection_ids: list[int] | None = None
        if session is not None:
            workspace = await session.get(Workspace, workspace_id)
            if workspace is not None:
                fallback_text = fallback_text or workspace.auto_reply_fallback or self.SAFE_FALLBACK_TEXT
                collection_ids = workspace.auto_reply_collections or []

        fallback = fallback_text or self.SAFE_FALLBACK_TEXT

        # 4. Retrieve Workspace Knowledge Chunks (RAG)
        chunks = await self._retrieve_knowledge_chunks(workspace_id, text, collection_ids=collection_ids)
        valid_chunks = [c for c in chunks if c.get("similarity", 0.0) >= self.COSINE_SIMILARITY_THRESHOLD]

        # 5. Determine Answer vs Safe Fallback
        if not valid_chunks:
            # Fallback if no relevant documents match
            return AutoReplyResult(
                reply_text=fallback,
                is_answered=True,
                is_fallback=True,
                intent_score=intent_score,
                is_hot_intent=is_hot,
                intent_reason=intent_reason,
                matched_chunks=chunks,
            )

        # 6. Generate Grounded Reply
        context_str = "\n\n".join([c["content"] for c in valid_chunks])
        reply = await self._generate_llm_response(
            text,
            context_str,
            session=session,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        is_fallback = not reply or not reply.strip()
        if is_fallback:
            reply = fallback

        # 7. Hot lead alert (after we have a reply so the alert can include the prospect's message)
        if is_hot and thread_id and session is not None:
            lead = await self._get_or_create_lead(session, workspace_id, sender_id, channel)
            recipient_chat_id = None
            if session is not None:
                workspace = await session.get(Workspace, workspace_id)
                if workspace is not None:
                    recipient_chat_id = workspace.auto_reply_recipient_chat_id
            await self._dispatch_hot_lead_alert(
                session=session,
                workspace_id=workspace_id,
                channel=channel,
                sender_id=sender_id,
                thread_id=thread_id,
                intent_reason=intent_reason,
                message_content=text,
                lead=lead,
                recipient_chat_id=recipient_chat_id,
            )

        return AutoReplyResult(
            reply_text=reply,
            is_answered=True,
            is_fallback=is_fallback,
            intent_score=intent_score,
            is_hot_intent=is_hot,
            intent_reason=intent_reason,
            matched_chunks=valid_chunks,
        )
