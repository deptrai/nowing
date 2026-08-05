"""``ContinueResearchActionParams`` contract (Story 6.5 AC-3, FR-35; Story 3.14 D9).

Surface:
    app.automations.actions.builtin.continue_research.params.ContinueResearchActionParams
      - research_thread_id: int   # required
      - top_k: int = 5, ge=1, le=5, bool rejected  # new-write producer (schema_version 1.1)
      - model_config = ConfigDict(extra="forbid")

    app.automations.actions.builtin.continue_research.params._LegacyContinueResearchActionParams
      - same shape, top_k ge=1, le=100, bool rejected  # schema_version 1.0 reads only
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_research_thread_id_is_required() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams()


def test_top_k_defaults_to_5() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    params = ContinueResearchActionParams(research_thread_id=1)

    assert params.research_thread_id == 1
    assert params.top_k == 5


def test_accepts_research_thread_id_and_top_k() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    params = ContinueResearchActionParams(research_thread_id=7, top_k=3)

    assert params.research_thread_id == 7
    assert params.top_k == 3


def test_extra_keys_are_forbidden() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, typo=True)


def test_top_k_rejects_zero() -> None:
    """``top_k`` has a floor of 1 (``ge=1``): 0 recalls nothing and is invalid."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, top_k=0)


def test_top_k_rejects_above_ceiling() -> None:
    """Story 3.14 (D9): new-write ``top_k`` ceiling is 5, not the old 100."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, top_k=6)


def test_top_k_accepts_inclusive_bounds() -> None:
    """The bounds themselves are valid (inclusive ge/le)."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    assert ContinueResearchActionParams(research_thread_id=1, top_k=1).top_k == 1
    assert ContinueResearchActionParams(research_thread_id=1, top_k=5).top_k == 5


def test_top_k_rejects_bool() -> None:
    """Story 3.14 (D9): bool is invalid everywhere, even though it's an int subclass."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, top_k=True)


def test_top_k_accepts_rendered_numeric_string() -> None:
    """B1: a Jinja-rendered numeric string is coerced to ``int`` and accepted."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    params = ContinueResearchActionParams(research_thread_id=1, top_k="3")
    assert params.top_k == 3
    assert isinstance(params.top_k, int)


def test_top_k_rejects_non_numeric_string() -> None:
    """B1: non-numeric strings (e.g. bad Jinja output) are rejected."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, top_k="abc")


def test_top_k_rejects_float() -> None:
    """B1: floats are not valid ``top_k`` values (must be integer)."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, top_k=3.0)


# --- _LegacyContinueResearchActionParams (schema_version 1.0 reads only) ---------


def test_legacy_top_k_defaults_to_5() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        _LegacyContinueResearchActionParams,
    )

    params = _LegacyContinueResearchActionParams(research_thread_id=1)

    assert params.top_k == 5


def test_legacy_accepts_wider_range() -> None:
    """The legacy model still accepts the old 1..100 range (clamping happens in invoke.py)."""
    from app.automations.actions.builtin.continue_research.params import (
        _LegacyContinueResearchActionParams,
    )

    params = _LegacyContinueResearchActionParams(research_thread_id=7, top_k=100)

    assert params.top_k == 100


def test_legacy_top_k_rejects_zero() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        _LegacyContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        _LegacyContinueResearchActionParams(research_thread_id=1, top_k=0)


def test_legacy_top_k_rejects_above_ceiling() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        _LegacyContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        _LegacyContinueResearchActionParams(research_thread_id=1, top_k=101)


def test_legacy_top_k_rejects_bool() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        _LegacyContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        _LegacyContinueResearchActionParams(research_thread_id=1, top_k=True)


def test_legacy_extra_keys_are_forbidden() -> None:
    from app.automations.actions.builtin.continue_research.params import (
        _LegacyContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        _LegacyContinueResearchActionParams(research_thread_id=1, typo=True)
