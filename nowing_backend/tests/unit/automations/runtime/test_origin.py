"""Automation-origin contextvar (Story 6.5, AC-5, mechanism 1).

Pure-unit coverage of ``app.automations.runtime.origin`` — the contextvar the
run executor stamps so an in-process memory write inside a run is recognised as
automation-origin (and its ``memory.changed`` emission skipped) WITHOUT a
hand-passed kwarg.

The repository's loop-guard and the integration tests exercise this indirectly;
here we lock the primitive's own contract directly: default, set/reset, nesting,
exception-safety, and no cross-run leak on a reused event loop.
"""

from __future__ import annotations

import pytest

from app.automations.runtime.origin import (
    automation_run_origin,
    get_current_automation_run_id,
)

pytestmark = pytest.mark.unit


def test_default_origin_is_none() -> None:
    """Outside any run, there is no automation origin."""
    assert get_current_automation_run_id() is None


def test_origin_is_set_inside_the_block_and_reset_after() -> None:
    """The executor stamps a run id for the block; it is cleared on exit."""
    assert get_current_automation_run_id() is None
    with automation_run_origin(77):
        assert get_current_automation_run_id() == 77
    assert get_current_automation_run_id() is None


def test_nested_origins_restore_the_outer_value() -> None:
    """A nested block (e.g. a sub-run) restores the enclosing origin on exit,
    never collapsing to ``None`` while the outer block is still active."""
    with automation_run_origin(100):
        assert get_current_automation_run_id() == 100
        with automation_run_origin(200):
            assert get_current_automation_run_id() == 200
        # Inner exit restores the outer run, not None.
        assert get_current_automation_run_id() == 100
    assert get_current_automation_run_id() is None


def test_origin_is_reset_even_when_the_block_raises() -> None:
    """A crash inside a run must not leak its origin into the next task."""
    with pytest.raises(RuntimeError), automation_run_origin(555):
        assert get_current_automation_run_id() == 555
        raise RuntimeError("run blew up")
    assert get_current_automation_run_id() is None


def test_explicit_none_origin_is_transparent() -> None:
    """Stamping ``None`` (no origin) leaves reads as ``None`` and restores
    cleanly — a run launched without an id must not mask an outer origin."""
    with automation_run_origin(9):
        assert get_current_automation_run_id() == 9
        with automation_run_origin(None):
            assert get_current_automation_run_id() is None
        assert get_current_automation_run_id() == 9


def test_sequential_blocks_do_not_leak_between_runs() -> None:
    """A reused event loop running one run after another sees each origin in
    isolation — the previous run's id never bleeds into the next."""
    with automation_run_origin(1):
        assert get_current_automation_run_id() == 1
    assert get_current_automation_run_id() is None
    with automation_run_origin(2):
        assert get_current_automation_run_id() == 2
    assert get_current_automation_run_id() is None
