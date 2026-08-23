from __future__ import annotations

import json
import logging
import uuid

from app.capabilities.browser_operator.schemas import (
    BrowserOperatorInput,
    BrowserOperatorOutput,
)
from app.capabilities.core.types import CapabilityContext
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)


def build_browser_operator_executor():
    async def _execute(
        payload: BrowserOperatorInput, ctx: CapabilityContext | None = None
    ) -> BrowserOperatorOutput:
        user_id: str | None = None
        if ctx:
            if getattr(ctx, "user_id", None):
                user_id = str(ctx.user_id)
            elif getattr(ctx, "auth", None) and getattr(ctx.auth, "user", None):
                user_id = str(ctx.auth.user.id)
            elif getattr(ctx, "session", None) and getattr(ctx, "workspace_id", None):
                from sqlalchemy import select

                from app.db import Workspace

                res = await ctx.session.execute(
                    select(Workspace.owner_id).where(Workspace.id == ctx.workspace_id)
                )
                owner_id = res.scalar_one_or_none()
                if owner_id:
                    user_id = str(owner_id)

        if not user_id:
            return BrowserOperatorOutput(
                success=False,
                action=payload.action,
                message="User authentication context is required to execute browser operator commands.",
            )

        mission_id = str(uuid.uuid4())
        command_id = f"cmd-{uuid.uuid4().hex[:8]}"

        redis = await get_redis_client()
        channel = f"cdp_stream:{user_id}"
        result_key = f"cdp_result:{user_id}:{mission_id}"

        # Check if the user's extension is actively listening
        subs = await redis.pubsub_numsub(channel)
        if not subs or subs[0][1] == 0:
            return BrowserOperatorOutput(
                success=False,
                action=payload.action,
                message=(
                    "Nowing Extension is not connected on your browser. "
                    "Please ensure the extension is open and authenticated with your token."
                ),
            )

        cdp_cmd = {
            "action": payload.action,
            "mission_id": mission_id,
            "command_id": command_id,
            "url": payload.url,
            "selector": payload.selector,
            "text": payload.text,
            "direction": payload.direction,
            "px": payload.px,
            "format": payload.format,
        }

        await redis.delete(result_key)
        await redis.publish(channel, json.dumps(cdp_cmd))

        # Wait for extension result via BLPOP. Redis socket_timeout already exceeds 60s
        # so we can rely on blpop's own timeout instead of wrapping it in asyncio.wait_for.
        try:
            raw_result = await redis.blpop(result_key, timeout=60)
            if not raw_result:
                return BrowserOperatorOutput(
                    success=False,
                    action=payload.action,
                    message="Timed out waiting for browser extension response.",
                )

            _, data_str = raw_result
            data = json.loads(data_str)
            if data.get("requires_human") or data.get("challenge"):
                return BrowserOperatorOutput(
                    success=False,
                    action=payload.action,
                    message=(
                        "Encountered CAPTCHA/Challenge. "
                        "Human takeover is required in the browser extension popup."
                    ),
                    data=data,
                )

            if data.get("error"):
                return BrowserOperatorOutput(
                    success=False,
                    action=payload.action,
                    message=data["error"],
                    data=data.get("result"),
                )

            return BrowserOperatorOutput(
                success=True,
                action=payload.action,
                message=f"Successfully executed {payload.action} on your browser tab.",
                data=data.get("result"),
            )
        except TimeoutError:
            return BrowserOperatorOutput(
                success=False,
                action=payload.action,
                message="Timed out waiting for browser extension response (60s).",
            )
        except Exception as exc:
            logger.error("CDP command execution error: %s", exc)
            return BrowserOperatorOutput(
                success=False,
                action=payload.action,
                message=f"Error executing browser action: {exc}",
            )

    return _execute
