"""``app.utils.strict_fields`` contract (Story 3.14, D9)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.utils.strict_fields import strict_top_k

pytestmark = pytest.mark.unit


class _Model(BaseModel):
    """Minimal model exercising ``strict_top_k`` as a field annotation."""

    top_k: strict_top_k(le=5, description="Number of items to recall.") = 5


def test_accepts_int_within_range() -> None:
    assert _Model(top_k=3).top_k == 3
    assert _Model(top_k=1).top_k == 1
    assert _Model(top_k=5).top_k == 5


def test_defaults_to_five() -> None:
    assert _Model().top_k == 5


def test_accepts_rendered_numeric_string() -> None:
    """B1: Jinja produces numeric strings; the field must coerce them."""
    assert _Model(top_k="3").top_k == 3
    assert _Model(top_k=" 3 ").top_k == 3


def test_rejects_bool() -> None:
    """D9: ``bool`` is an ``int`` subclass but is never a valid ``top_k``."""
    with pytest.raises(ValidationError):
        _Model(top_k=True)

    with pytest.raises(ValidationError):
        _Model(top_k=False)


def test_rejects_non_numeric_string() -> None:
    """B1: non-numeric strings must fail cleanly."""
    with pytest.raises(ValidationError):
        _Model(top_k="abc")


def test_rejects_float() -> None:
    """B1: floats are not integer top_k values."""
    with pytest.raises(ValidationError):
        _Model(top_k=3.0)


def test_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        _Model(top_k=0)

    with pytest.raises(ValidationError):
        _Model(top_k=6)


def test_type_adapter_validates_a_single_value() -> None:
    """B1: ``FieldInfo.rebuild_annotation()`` + ``TypeAdapter`` must also
    coerce numeric strings, because ``validate_plan_steps`` validates static
    fields individually through this path."""
    annotation = _Model.model_fields["top_k"].rebuild_annotation()
    adapter = TypeAdapter(annotation)

    assert adapter.validate_python(3) == 3
    assert adapter.validate_python("3") == 3

    with pytest.raises(ValidationError):
        adapter.validate_python(True)

    with pytest.raises(ValidationError):
        adapter.validate_python("abc")

    with pytest.raises(ValidationError):
        adapter.validate_python(6)
