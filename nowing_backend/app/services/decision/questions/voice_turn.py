"""Voice turn question set — 2 Nouls + 1 Score in one batched call.

Story 39.6: evaluated per completed STT turn inside
``VoiceSDRAgent.on_user_turn_completed``. Caller puts ``transcript``
(the final STT text for the turn) in ``state``. All three questions
evaluate in parallel server-side — keep them batched in one
``decide()`` call (splitting them would triple latency and cost).
"""

from __future__ import annotations

from app.services.decision.types import NoulQuestion, ScoreQuestion

VERSION = "1.0.0"

# State keys a caller must supply — passed to decide() so a missing key
# fails fast before any paid backend call.
REQUIRED_STATE_KEYS: tuple[str, ...] = ("transcript",)

QUESTIONS: dict[str, NoulQuestion | ScoreQuestion] = {
    "should_respond": NoulQuestion(
        instructions=(
            "The `transcript` is one completed turn of Vietnamese speech "
            "from a phone call between a caller and an AI sales agent. "
            "Should the agent respond to this turn? Backchannels and "
            "acknowledgements that expect no reply ('ừ', 'à', 'vâng ạ', "
            "'ừ hử'), STT noise, and filler are NO. Questions, requests, "
            "and statements that advance the conversation are YES."
        ),
        criteria={
            "true": {"what": "The turn needs an agent response"},
            "false": {"what": "Backchannel/noise — the agent stays silent"},
        },
    ),
    "caller_frustration": ScoreQuestion(
        instructions=(
            "Rate the caller's frustration level in `transcript` on a "
            "0-3 scale: 0 = calm or neutral; 1 = mild impatience; "
            "2 = clearly annoyed or complaining ('phiền quá', 'gọi hoài "
            "vậy'); 3 = angry, hostile, or demanding the call end."
        ),
        criteria=[
            "Calm or neutral tone",
            "Mild impatience or hesitation",
            "Clearly annoyed or complaining",
            "Angry, hostile, or demanding to hang up",
        ],
    ),
    "transfer_to_human": NoulQuestion(
        instructions=(
            "Does `transcript` contain an explicit request to speak with "
            "a human agent or real person (e.g. 'cho tôi nói chuyện với "
            "người thật', 'gặp nhân viên', 'chuyển tổng đài')? Vague "
            "dissatisfaction without an explicit transfer request is NO."
        ),
        criteria={
            "true": {"what": "Explicit request for a human agent"},
            "false": {"what": "No transfer request"},
        },
    ),
}
