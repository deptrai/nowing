"""``_coerce_research_thread_id`` contract (Story 6.5, AC-4).

Pure-unit coverage of the JSON -> int coercion ``launch.resolve_research_thread_id``
runs before it touches the DB. A ``research_thread_id`` arrives from JSONB run
inputs / a ``memory.changed`` payload, so it can be an int, a digit string, or
junk. Coercion normalises it to an ``int`` (existence/workspace validation is a
separate DB step) or ``None`` when it can never be a valid FK.

The critical edge is ``bool``: ``True``/``False`` are ``int`` subclasses in
Python, so a naive ``isinstance(x, int)`` would coerce ``True`` -> ``1`` and
silently link a run to research thread #1. Coercion must reject bools outright.
The DB-backed drop of non-existent / cross-workspace ids is covered separately
in the launch integration tests.
"""

from __future__ import annotations

import pytest

from app.automations.dispatch.launch import _coerce_research_thread_id

pytestmark = pytest.mark.unit


def test_int_passes_through() -> None:
    assert _coerce_research_thread_id(42) == 42


def test_digit_string_is_parsed_to_int() -> None:
    """A JSON payload may carry the id as a string; a pure-digit string coerces."""
    assert _coerce_research_thread_id("123") == 123


@pytest.mark.parametrize("value", [True, False])
def test_bool_is_rejected(value: bool) -> None:
    """``bool`` is an ``int`` subclass but never a valid FK — must not become 1/0."""
    assert _coerce_research_thread_id(value) is None


@pytest.mark.parametrize("value", [1.5, 3.0, 0.0])
def test_float_is_rejected(value: float) -> None:
    """A float is never a valid integer FK, even when it looks whole (3.0)."""
    assert _coerce_research_thread_id(value) is None


@pytest.mark.parametrize("value", ["", "abc", "12.5", "-5", "12a", "  7  "])
def test_non_digit_strings_are_rejected(value: str) -> None:
    """Only a bare run of digits parses; signs, dots, spaces, and letters do not."""
    assert _coerce_research_thread_id(value) is None


def test_none_stays_none() -> None:
    assert _coerce_research_thread_id(None) is None


@pytest.mark.parametrize("value", [[], {}, object()])
def test_other_types_are_rejected(value: object) -> None:
    assert _coerce_research_thread_id(value) is None
