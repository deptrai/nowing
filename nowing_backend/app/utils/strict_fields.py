"""Shared Pydantic field types that reject ``bool`` where an ``int`` is expected.

Pydantic v2's lax-mode ``int`` validation silently coerces ``True``/``False`` to
``1``/``0`` and does not reject a bool value even when ``ge``/``le`` constraints
are present on a plain ``int``-typed field. A :class:`~pydantic.BeforeValidator`
runs before that coercion, so it is the only place a bool can be turned away
(Story 3.14, D9 — "bool is invalid everywhere").
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, Field


def _reject_bool(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("must be an integer, not a boolean")
    return value


def strict_top_k(*, le: int, description: str) -> type:
    """An ``Annotated[int, ...]`` field type: ``ge=1``, ``le=le``, bool rejected.

    Usable as a class attribute annotation (``top_k: strict_top_k(le=5, ...) = 5``)
    and, via ``FieldInfo.rebuild_annotation()`` + ``TypeAdapter``, for validating a
    single field's value outside of a full model (see
    ``app.automations.actions.validation``).
    """
    return Annotated[
        int,
        BeforeValidator(_reject_bool),
        Field(ge=1, le=le, description=description),
    ]
