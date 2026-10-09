"""BANT scoring question set — 4 Score questions for lead qualification (AI-38.5).

Evaluates Budget, Authority, Need, and Timeline from a phone call transcript.
Each dimension evaluates on a 0-3 graduated scale, mapped to 0-25 points (total 0-100).
"""

from __future__ import annotations

from app.services.decision.types import ScoreQuestion

VERSION = "1.0.0"

# State keys a caller must supply — passed to decide() so a missing key
# fails fast before any paid backend call.
REQUIRED_STATE_KEYS: tuple[str, ...] = ("transcript",)

QUESTIONS: dict[str, ScoreQuestion] = {
    "budget": ScoreQuestion(
        instructions=(
            "Rate the prospect's budget and financial qualification in `transcript` "
            "on a 0-3 scale: "
            "0 = no mention or no budget/financial capability; "
            "1 = vague interest or budget concerns without clear capacity; "
            "2 = feasible budget or pricing discussed with clear willingness; "
            "3 = confirmed strong budget, explicit financial readiness or pre-approval."
        ),
        criteria=[
            "No budget mentioned or negative financial capacity",
            "Vague interest or financial concerns",
            "Feasible budget discussed with clear capacity",
            "Confirmed strong budget or explicit financial readiness",
        ],
    ),
    "authority": ScoreQuestion(
        instructions=(
            "Rate the prospect's decision-making authority in `transcript` "
            "on a 0-3 scale: "
            "0 = no decision authority mentioned or not a decision maker; "
            "1 = influencer or needs to consult family/partners; "
            "2 = primary co-decision maker with significant input; "
            "3 = sole decision maker with full authority."
        ),
        criteria=[
            "No decision authority or not a decision maker",
            "Influencer or needs to consult others",
            "Primary co-decision maker with significant input",
            "Sole decision maker with full authority",
        ],
    ),
    "need": ScoreQuestion(
        instructions=(
            "Rate the prospect's need and pain points in `transcript` "
            "on a 0-3 scale: "
            "0 = no explicit need or not interested; "
            "1 = casual curiosity or mild exploration; "
            "2 = clear need or defined requirements; "
            "3 = urgent, well-defined, critical need."
        ),
        criteria=[
            "No explicit need or not interested",
            "Casual curiosity or mild exploration",
            "Clear need or defined requirements",
            "Urgent, critical, well-defined need",
        ],
    ),
    "timeline": ScoreQuestion(
        instructions=(
            "Rate the prospect's purchase or action timeline in `transcript` "
            "on a 0-3 scale: "
            "0 = no timeline mentioned or distant future (>12 months); "
            "1 = medium term (6-12 months) or uncertain timing; "
            "2 = near term (1-3 months) with concrete milestone; "
            "3 = immediate action (within days or weeks)."
        ),
        criteria=[
            "No timeline mentioned or distant future",
            "Medium term (6-12 months) or uncertain",
            "Near term (1-3 months) with concrete timing",
            "Immediate action (within days or weeks)",
        ],
    ),
}
