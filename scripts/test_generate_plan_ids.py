"""Unit tests for `scripts/generate_plan_ids.py`.

Run from repo root:  uv run pytest scripts/test_generate_plan_ids.py
or:                  python3 -m pytest scripts/test_generate_plan_ids.py

Round 2 review of Story 11.6: covers the AST-parsing edge cases that the
hardened script must handle (Field-form, dunder skip, helper-method skip,
declaration order preservation).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parent / "generate_plan_ids.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_plan_ids", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen():
    return _load_module()


@pytest.fixture
def schema_file(tmp_path):
    def _write(content: str) -> Path:
        path = tmp_path / "schema.py"
        path.write_text(content, encoding="utf-8")
        return path
    return _write


def test_plain_string_literal(gen, schema_file):
    path = schema_file(
        """
from enum import Enum
class PlanId(str, Enum):
    pro_monthly = "pro_monthly"
    pro_yearly = "pro_yearly"
"""
    )
    assert gen.extract_plan_ids(path) == ["pro_monthly", "pro_yearly"]


def test_annotated_form(gen, schema_file):
    path = schema_file(
        """
from enum import Enum
class PlanId(str, Enum):
    pro_monthly: str = "pro_monthly"
"""
    )
    assert gen.extract_plan_ids(path) == ["pro_monthly"]


def test_field_call_form_round2(gen, schema_file):
    """Round 2: BE may add Pydantic Field metadata. Codegen must accept this
    rather than break CI for every BE PR that touches PlanId."""
    path = schema_file(
        """
from enum import Enum
from pydantic import Field
class PlanId(str, Enum):
    pro_monthly: str = Field("pro_monthly", description="Pro monthly tier")
    pro_yearly: str = Field("pro_yearly")
"""
    )
    assert gen.extract_plan_ids(path) == ["pro_monthly", "pro_yearly"]


def test_skip_dunder_and_helpers(gen, schema_file):
    """Round 2: Enum housekeeping (`__order__`, `_ignore_`, classmethods,
    docstrings) must be skipped — must NOT leak as fake plan IDs."""
    path = schema_file(
        '''
from enum import Enum
class PlanId(str, Enum):
    """Subscription tiers."""
    pro_monthly = "pro_monthly"
    __order__ = "pro_monthly pro_yearly"
    _ignore_ = "internal"
    pro_yearly = "pro_yearly"

    @classmethod
    def list_all(cls):
        return list(cls)

    def display(self):
        return self.value
'''
    )
    assert gen.extract_plan_ids(path) == ["pro_monthly", "pro_yearly"]


def test_preserves_declaration_order(gen, schema_file):
    """Round 1: order must reflect BE source, not alphabetical."""
    path = schema_file(
        """
from enum import Enum
class PlanId(str, Enum):
    pro_yearly = "pro_yearly"
    pro_monthly = "pro_monthly"
    max_yearly = "max_yearly"
    max_monthly = "max_monthly"
"""
    )
    assert gen.extract_plan_ids(path) == [
        "pro_yearly", "pro_monthly", "max_yearly", "max_monthly",
    ]


def test_raises_on_computed_value(gen, schema_file):
    """Round 2: unrecognized shapes raise loudly — better to break codegen
    than silently drop a real plan."""
    path = schema_file(
        """
from enum import Enum
def make_id(): return "computed"
class PlanId(str, Enum):
    pro_monthly = make_id()
"""
    )
    with pytest.raises(RuntimeError, match="unexpected member shape"):
        gen.extract_plan_ids(path)


def test_raises_when_planid_class_missing(gen, schema_file):
    path = schema_file(
        """
from enum import Enum
class OtherEnum(str, Enum):
    a = "a"
"""
    )
    with pytest.raises(RuntimeError, match="PlanId class not found"):
        gen.extract_plan_ids(path)


def test_raises_when_no_string_members(gen, schema_file):
    path = schema_file(
        """
from enum import Enum
class PlanId(str, Enum):
    pass
"""
    )
    with pytest.raises(RuntimeError, match="no string members"):
        gen.extract_plan_ids(path)
