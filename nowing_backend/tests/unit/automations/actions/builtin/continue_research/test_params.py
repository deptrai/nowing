"""``ContinueResearchActionParams`` contract (Story 6.5, AC-3, FR-35).

Red-phase ATDD scaffolds. The ``continue_research`` action params model does not
exist yet, so app imports happen inside each test; every test is skipped until
``dev-story`` builds it.

Expected surface (mirrors ``builtin/write_back_notion/params.py``):
    app.automations.actions.builtin.continue_research.params.ContinueResearchActionParams
      - research_thread_id: int   # required
      - top_k: int = 5
      - model_config = ConfigDict(extra="forbid")
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

    params = ContinueResearchActionParams(research_thread_id=7, top_k=10)

    assert params.research_thread_id == 7
    assert params.top_k == 10


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
    """``top_k`` has a ceiling of 100 (``le=100``) to bound the recall payload."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    with pytest.raises(ValueError):
        ContinueResearchActionParams(research_thread_id=1, top_k=101)


def test_top_k_accepts_inclusive_bounds() -> None:
    """The bounds themselves are valid (inclusive ge/le)."""
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )

    assert ContinueResearchActionParams(research_thread_id=1, top_k=1).top_k == 1
    assert ContinueResearchActionParams(research_thread_id=1, top_k=100).top_k == 100
