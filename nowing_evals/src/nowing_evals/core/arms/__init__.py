"""Arm protocol + concrete arms shared across suites.

Concrete arms (``NativePdfArm``, ``NowingArm``, ``BareLlmArm``) are
imported lazily via ``__getattr__`` so consumers that only need the
protocol — e.g. the registry's ``Arm`` re-export — don't transitively
pull in ``httpx`` providers or the Nowing client unless they
actually use those arms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Arm, ArmRequest, ArmResult

if TYPE_CHECKING:  # pragma: no cover
    from .bare_llm import BareLlmArm
    from .native_pdf import NativePdfArm
    from .nowing import NowingArm

__all__ = [
    "Arm",
    "ArmRequest",
    "ArmResult",
    "BareLlmArm",
    "NativePdfArm",
    "NowingArm",
]


def __getattr__(name: str):  # PEP 562
    if name == "NativePdfArm":
        from .native_pdf import NativePdfArm

        return NativePdfArm
    if name == "NowingArm":
        from .nowing import NowingArm

        return NowingArm
    if name == "BareLlmArm":
        from .bare_llm import BareLlmArm

        return BareLlmArm
    raise AttributeError(f"module 'nowing_evals.core.arms' has no attribute {name!r}")
