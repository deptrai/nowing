"""Entity match fan-out question set — Choice over surviving candidates.

Speculative fan-out ported from ``jev-ultrafast``'s ``choose()`` (Story
39.3): a stage-1 heuristic narrows N entities to K candidate pairs, then
ONE ``decide()`` call per anchor asks which candidate — if any — is the
same entity. Jev never re-scores pairs the heuristic already rejected.

The registered criteria is a template: callers ``dataclasses.replace``
it with ``{candidate_id: description, ..., "no_match": ...}`` — candidate
ids first, ``no_match`` LAST (``MockBackend`` answers the first option,
so tests can exercise a deterministic confirmed match).
"""

from __future__ import annotations

from app.services.decision.types import ChoiceQuestion

VERSION = "1.0.0"

# State keys a caller must supply — passed to decide() so a missing key
# fails fast before any paid backend call.
REQUIRED_STATE_KEYS: tuple[str, ...] = ("anchor", "candidates")

NO_MATCH_ID = "no_match"
NO_MATCH_DESCRIPTION = "None of the candidates is the same entity as the anchor"

QUESTIONS: dict[str, ChoiceQuestion] = {
    "match_decision": ChoiceQuestion(
        instructions=(
            "Which candidate (if any) describes the same real-world entity "
            "as the anchor? Consider: same name with different spellings, "
            "diacritics stripped, abbreviations, Vietnamese vs English "
            "naming, and same address/phone. Similar names can be DIFFERENT "
            "entities (Sunrise City vs Sunset City are different). Pick "
            "'no_match' when no candidate is the same entity."
        ),
        criteria={NO_MATCH_ID: NO_MATCH_DESCRIPTION},
    ),
}
