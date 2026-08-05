"""``AutomationService.create()``/``update()`` save-time validation + schema_version
normalization (Story 3.14, D9 points 1/3/4).

Isolates the new wiring: an invalid plan step must 422 before any commit, and a
persisted definition always carries the current schema_version ("1.1") on
create/update, even when the client omits it or sends the legacy "1.0".
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

import app.automations.services.automation as automation_mod
from app.auth.context import AuthContext
from app.automations.actions.builtin import continue_research  # noqa: F401
from app.automations.schemas.api import AutomationCreate, AutomationUpdate
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.services.automation import AutomationService

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self, workspace: Any = None) -> None:
        self._workspace = workspace
        self.added: list[Any] = []
        self.commits = 0

    async def get(self, _model: Any, _pk: int) -> Any:
        return self._workspace

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _service(session: _FakeSession) -> AutomationService:
    return AutomationService(
        session=session, auth=AuthContext.session(SimpleNamespace(id="u-1"))
    )


def _valid_definition(
    *, plan: list[PlanStep] | None = None, **kwargs: Any
) -> AutomationDefinition:
    return AutomationDefinition(
        name="A",
        plan=plan
        or [
            PlanStep(
                step_id="s1",
                action="continue_research",
                params={"research_thread_id": 1},
            )
        ],
        **kwargs,
    )


def _bind_billable_and_authorize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        automation_mod, "assert_automation_models_billable", lambda _ss: None
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)

    async def _return_added(self, _aid):
        return self.session.added[-1]

    monkeypatch.setattr(AutomationService, "_get_with_triggers_or_raise", _return_added)


async def test_create_rejects_invalid_plan_with_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An out-of-range static ``top_k`` on a step 422s before any commit."""
    _bind_billable_and_authorize(monkeypatch)

    service = _service(
        _FakeSession(
            SimpleNamespace(chat_model_id=0, image_gen_model_id=0, vision_model_id=0)
        )
    )
    payload = AutomationCreate(
        workspace_id=1,
        name="A",
        definition=_valid_definition(
            plan=[
                PlanStep(
                    step_id="s1",
                    action="continue_research",
                    params={"research_thread_id": 1, "top_k": 6},
                )
            ]
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create(payload)

    assert exc_info.value.status_code == 422
    assert service.session.commits == 0


async def test_create_rejects_unknown_action_with_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_billable_and_authorize(monkeypatch)

    service = _service(
        _FakeSession(
            SimpleNamespace(chat_model_id=0, image_gen_model_id=0, vision_model_id=0)
        )
    )
    payload = AutomationCreate(
        workspace_id=1,
        name="A",
        definition=_valid_definition(
            plan=[PlanStep(step_id="s1", action="does_not_exist")]
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create(payload)

    assert exc_info.value.status_code == 422


async def test_create_normalizes_schema_version_to_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client-omitted (parser default "1.1") schema_version is persisted as "1.1"."""
    _bind_billable_and_authorize(monkeypatch)

    service = _service(
        _FakeSession(
            SimpleNamespace(chat_model_id=0, image_gen_model_id=0, vision_model_id=0)
        )
    )
    payload = AutomationCreate(workspace_id=1, name="A", definition=_valid_definition())

    assert payload.definition.schema_version == "1.1"  # parser default, pre-create

    automation = await service.create(payload)

    assert automation.definition["schema_version"] == "1.1"


async def test_create_normalizes_explicit_legacy_schema_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even an explicit client-sent "1.0" is normalized to "1.1" on a new write."""
    _bind_billable_and_authorize(monkeypatch)

    service = _service(
        _FakeSession(
            SimpleNamespace(chat_model_id=0, image_gen_model_id=0, vision_model_id=0)
        )
    )
    payload = AutomationCreate(
        workspace_id=1, name="A", definition=_valid_definition(schema_version="1.0")
    )

    automation = await service.create(payload)

    assert automation.definition["schema_version"] == "1.1"


async def test_update_rejects_invalid_plan_with_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = SimpleNamespace(
        workspace_id=1,
        definition={"name": "A", "plan": [], "schema_version": "1.1"},
        version=3,
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    async def _return_existing(self, _aid):
        return existing

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)
    monkeypatch.setattr(
        AutomationService, "_get_with_triggers_or_raise", _return_existing
    )

    service = _service(_FakeSession())
    patch = AutomationUpdate(
        definition=_valid_definition(
            plan=[
                PlanStep(
                    step_id="s1",
                    action="continue_research",
                    params={"research_thread_id": 1, "top_k": 6},
                )
            ]
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update(7, patch)

    assert exc_info.value.status_code == 422
    assert existing.version == 3  # untouched — no partial update on rejection


async def test_update_normalizes_schema_version_to_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An edited definition always persists as the current schema_version, even
    when the patch is built from a legacy "1.0" snapshot."""
    existing = SimpleNamespace(
        workspace_id=1,
        definition={"name": "A", "plan": [], "schema_version": "1.0"},
        version=3,
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    async def _return_existing(self, _aid):
        return existing

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)
    monkeypatch.setattr(
        AutomationService, "_get_with_triggers_or_raise", _return_existing
    )

    service = _service(_FakeSession())
    patch = AutomationUpdate(definition=_valid_definition(schema_version="1.0"))

    result = await service.update(7, patch)

    assert result.definition["schema_version"] == "1.1"
    assert result.version == 4


async def test_update_without_definition_leaves_schema_version_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A patch that never touches ``definition`` doesn't run save-time validation
    or normalization at all — the old snapshot is untouched."""
    existing = SimpleNamespace(
        workspace_id=1,
        definition={"name": "A", "plan": [], "schema_version": "1.0"},
        version=3,
        name="A",
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    async def _return_existing(self, _aid):
        return existing

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)
    monkeypatch.setattr(
        AutomationService, "_get_with_triggers_or_raise", _return_existing
    )

    service = _service(_FakeSession())
    patch = AutomationUpdate(name="Renamed")

    result = await service.update(7, patch)

    assert result.definition["schema_version"] == "1.0"  # untouched
    assert result.version == 3  # no bump — no definition change
