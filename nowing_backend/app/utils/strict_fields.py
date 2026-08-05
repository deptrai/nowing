"""Shared Pydantic field types that reject ``bool`` where an ``int`` is expected.

Pydantic v2's lax-mode ``int`` validation silently coerces ``True``/``False`` to
``1``/``0`` and does not reject a bool value even when ``ge``/``le`` constraints
are present on a plain ``int``-typed field. A :class:`~pydantic.BeforeValidator`
runs before that coercion, so it is the only place a bool can be turned away
(Story 3.14, D9 — "bool is invalid everywhere").
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, Field, StrictInt


def _coerce_top_k(value: object) -> object:
    """Coerce a rendered numeric string to ``int``; reject bool and non-numeric.

    Pydantic v2's lax-mode ``int`` would silently accept ``True``/``False`` as
    ``1``/``0`` and would also truncate floats. ``StrictInt`` blocks all of that,
    but it also rejects the numeric strings Jinja produces after rendering a
    templated ``top_k``. This before-validator converts those strings first, then
    the strict ``int`` check runs on the result.
    """
    if isinstance(value, bool):
        raise ValueError("must be an integer, not a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"must be a valid integer, got {value!r}") from exc
    raise ValueError(f"must be an integer, got {value!r}")


def strict_top_k(*, le: int, description: str) -> type:
    """An ``Annotated[int, ...]`` field type: ``ge=1``, ``le=le``, bool rejected.

    Accepts a plain ``int`` or a numeric string (e.g. a Jinja-rendered value),
    rejects ``bool``, ``float``, and non-numeric strings. Usable as a class
    attribute annotation (``top_k: strict_top_k(le=5, ...) = 5``) and, via
    ``FieldInfo.rebuild_annotation()`` + ``TypeAdapter``, for validating a single
    field's value outside of a full model (see ``app.automations.actions.validation``).
    """
    # B1/B13: StrictInt coerces neither strings/floats nor bools; the
    # BeforeValidator coerces numeric strings and explicitly rejects bool/non-numeric.
    return Annotated[
        StrictInt,
        BeforeValidator(_coerce_top_k),
        Field(ge=1, le=le, description=description),
    ]
