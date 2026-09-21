"""Entity match question set — Score over a rubric of 3 levels.

Ported from ``scripts/jev_eval/cases.py`` (ENTITY_MATCH). Eval baseline:
90% on 20 Vietnamese cases. Caller puts ``entity_a`` / ``entity_b``
dicts in ``state``. Score semantics: 0 = different, 1 = uncertain
(curator queue), 2 = same entity (auto-merge candidate).
"""

from __future__ import annotations

from app.services.decision.types import ScoreQuestion

VERSION = "1.0.0"

# State keys a caller must supply — passed to decide() so a missing key
# fails fast before any paid backend call.
REQUIRED_STATE_KEYS: tuple[str, ...] = ("entity_a", "entity_b")

QUESTIONS: dict[str, ScoreQuestion] = {
    "is_same": ScoreQuestion(
        instructions=(
            "Do entity_a and entity_b describe the same real-world entity? "
            "Consider: same name with different spellings, diacritics "
            "stripped, abbreviations, Vietnamese vs English naming, and same "
            "address/phone. Different entities can have similar names "
            "(Sunrise City vs Sunset City are DIFFERENT)."
        ),
        criteria=[
            "Different entity — safe to keep separate",
            "Uncertain — needs human curator review",
            "Same entity — safe to merge",
        ],
    ),
}
