"""``PlaybookService`` — lifecycle of reusable automation templates."""

from __future__ import annotations

from typing import Any

import jsonschema
from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.automations.actions import get_action
from app.automations.actions.validation import StepValidationError, validate_plan_steps
from app.automations.dispatch.inputs import validate_inputs
from app.automations.persistence.enums.playbook_scope import PlaybookScope
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.playbook import Playbook
from app.automations.schemas.api import (
    AutomationCreate,
    PlaybookCreate,
    PlaybookInstantiate,
    PlaybookUpdate,
    TriggerCreate,
)
from app.automations.schemas.definition import AutomationDefinition, Inputs, Metadata
from app.automations.schemas.definition.envelope import AutomationModels
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.services.automation import AutomationService
from app.automations.services.model_policy import (
    AutomationModelPolicyError,
    assert_automation_models_billable,
)
from app.db import Permission, Workspace, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission


def _extract_inputs_schema(definition: AutomationDefinition) -> dict[str, Any]:
    """Return the JSON Schema from the definition's ``inputs.schema_``."""
    if definition.inputs is None:
        return {}
    return definition.inputs.schema_ or {}


def _extract_tool_scope(definition: AutomationDefinition) -> list[str]:
    """Collect the unique action types used by the plan and on-failure steps."""
    actions: set[str] = set()
    for step in definition.plan:
        actions.add(step.action)
    for step in definition.execution.on_failure or []:
        actions.add(step.action)
    return sorted(actions)


def _validate_definition_plan(definition: AutomationDefinition) -> None:
    """Re-use the same save-time plan validation as ``AutomationService``."""
    try:
        validate_plan_steps(definition.plan)
        validate_plan_steps(definition.execution.on_failure or [])
    except StepValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validate_json_schema(schema: dict[str, Any]) -> None:
    """Reject malformed JSON Schemas before they are persisted."""
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise HTTPException(status_code=422, detail=f"invalid inputs schema: {exc.message}") from exc


class PlaybookService:
    """Lifecycle of the ``Playbook`` resource and its automation instances."""

    def __init__(self, *, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth
        self.user = auth.user

    async def create_from_automation(self, payload: PlaybookCreate) -> Playbook:
        """Save an existing automation's definition as a playbook template."""
        automation = await self._get_automation_or_raise(payload.source_automation_id)
        await self._authorize(automation.workspace_id, Permission.AUTOMATIONS_READ.value)

        try:
            definition = AutomationDefinition.model_validate(automation.definition)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=f"source automation definition is invalid: {exc}"
            ) from exc

        _validate_definition_plan(definition)

        # Always store with the current schema version.
        definition.schema_version = "1.1"

        # Record lineage in the free-form metadata (no parallel params model).
        derived_meta: dict[str, Any] = {
            "tags": list(definition.metadata.tags or []),
            "derived_from_automation_id": payload.source_automation_id,
        }
        if payload.tool_scope:
            derived_meta["tool_scope"] = sorted(set(payload.tool_scope))
        definition.metadata = Metadata.model_validate(derived_meta)

        inputs_schema = _extract_inputs_schema(definition)
        _validate_json_schema(inputs_schema)

        tool_scope = payload.tool_scope or _extract_tool_scope(definition)
        self._validate_tool_scope(tool_scope, definition)

        verticals = await self._resolve_verticals(payload.verticals, automation.workspace_id)

        playbook = Playbook(
            workspace_id=automation.workspace_id,
            created_by_user_id=self.user.id,
            name=payload.name,
            description=payload.description,
            definition=definition.model_dump(mode="json", by_alias=True),
            inputs_schema=inputs_schema,
            tool_scope=tool_scope,
            verticals=verticals,
            scope=PlaybookScope.WORKSPACE,
            version=1,
        )

        self.session.add(playbook)
        await self.session.commit()
        return await self._get_playbook_or_raise(playbook.id)

    async def list_playbooks(
        self,
        *,
        workspace_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Playbook], int]:
        """Return workspace playbooks and system playbooks a user can instantiate.

        Playbooks are visible when they declare the workspace's vertical or ``general``.
        """
        await self._authorize(workspace_id, Permission.AUTOMATIONS_READ.value)

        workspace = await self._get_workspace_or_raise(workspace_id)

        base = select(Playbook).where(
            or_(
                Playbook.workspace_id == workspace_id,
                Playbook.scope == PlaybookScope.SYSTEM,
            ),
            or_(
                Playbook.verticals.contains([workspace.vertical]),
                Playbook.verticals.contains(["general"]),
            ),
        )
        total = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )

        rows = (
            (
                await self.session.execute(
                    base.order_by(Playbook.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total or 0)

    async def get(self, playbook_id: int) -> Playbook:
        """Get a single playbook if the caller is allowed to see it."""
        playbook = await self._get_playbook_or_raise(playbook_id)
        await self._authorize_playbook_access(playbook, Permission.AUTOMATIONS_READ.value)
        return playbook

    async def update(self, playbook_id: int, patch: PlaybookUpdate) -> Playbook:
        """Patch a playbook. Definition or tool_scope changes bump the version."""
        playbook = await self._get_playbook_or_raise(playbook_id)
        await self._authorize_playbook_access(playbook, Permission.AUTOMATIONS_UPDATE.value)

        data = patch.model_dump(exclude_unset=True)
        version_bumped = False

        if "name" in data:
            playbook.name = data["name"]
        if "description" in data:
            playbook.description = data["description"]

        if "definition" in data and patch.definition is not None:
            _validate_definition_plan(patch.definition)
            patch.definition.schema_version = "1.1"
            new_inputs_schema = _extract_inputs_schema(patch.definition)
            _validate_json_schema(new_inputs_schema)
            playbook.inputs_schema = new_inputs_schema

            if "tool_scope" in data and patch.tool_scope is not None:
                tool_scope = patch.tool_scope
                self._validate_tool_scope(tool_scope, patch.definition)
                playbook.tool_scope = tool_scope
            else:
                playbook.tool_scope = _extract_tool_scope(patch.definition)

            playbook.definition = patch.definition.model_dump(mode="json", by_alias=True)
            version_bumped = True

        if "tool_scope" in data and patch.tool_scope is not None and "definition" not in data:
            definition = AutomationDefinition.model_validate(playbook.definition)
            self._validate_tool_scope(patch.tool_scope, definition)
            playbook.tool_scope = patch.tool_scope
            version_bumped = True

        if "verticals" in data and patch.verticals is not None:
            playbook.verticals = sorted(set(patch.verticals))

        if version_bumped:
            playbook.version += 1

        await self.session.commit()
        return await self._get_playbook_or_raise(playbook_id)

    async def instantiate(
        self,
        playbook_id: int,
        payload: PlaybookInstantiate,
    ) -> Automation:
        """Create a new automation from a playbook, validating inputs against the schema."""
        playbook = await self._get_playbook_or_raise(playbook_id)
        await self._authorize(payload.workspace_id, Permission.AUTOMATIONS_CREATE.value)

        # Pin the instance to the playbook version it was created from.
        self._validate_inputs(playbook, payload.inputs)

        workspace = await self._assert_models_billable(payload.workspace_id)

        try:
            definition = AutomationDefinition.model_validate(playbook.definition)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=f"playbook definition is invalid: {exc}") from exc

        # Ensure the captured schema version and tool scope lineage follow the playbook.
        definition.schema_version = "1.1"
        if playbook.tool_scope:
            meta_extra: dict[str, Any] = {
                "tags": list(definition.metadata.tags or []),
                "playbook_tool_scope": playbook.tool_scope,
            }
            # Preserve the source automation id if it was recorded on the playbook.
            if (
                definition.metadata
                and definition.metadata.model_extra
                and "derived_from_automation_id" in definition.metadata.model_extra
            ):
                meta_extra["derived_from_automation_id"] = definition.metadata.model_extra["derived_from_automation_id"]
            definition.metadata = Metadata.model_validate(meta_extra)

        # Capture a billable model snapshot from the target workspace.
        # Playbooks are workspace-agnostic templates; instances always inherit the
        # target workspace's current billable model profile.
        definition.models = AutomationModels(
            chat_model_id=workspace.chat_model_id or 0,
            image_gen_model_id=workspace.image_gen_model_id or 0,
            vision_model_id=workspace.vision_model_id or 0,
        )

        triggers = self._build_triggers_from_definition(definition)

        create_payload = AutomationCreate(
            workspace_id=payload.workspace_id,
            name=payload.name or playbook.name,
            description=payload.description if payload.description is not None else playbook.description,
            definition=definition,
            triggers=triggers,
        )

        # Reuse the existing automation creation path so plan + trigger validation is identical.
        automation_service = AutomationService(session=self.session, auth=self.auth)
        automation = await automation_service.create(create_payload)

        # Apply lineage pinning after creation so the instance never silently drifts.
        automation.derived_from_playbook_id = playbook.id
        automation.playbook_version = playbook.version
        await self.session.commit()

        return await automation_service._get_with_triggers_or_raise(automation.id)

    def _validate_inputs(self, playbook: Playbook, inputs: dict[str, Any]) -> None:
        """Validate the supplied inputs against the playbook's ``inputs_schema``."""
        if not playbook.inputs_schema:
            return
        # Build a minimal AutomationDefinition so we can reuse the runtime
        # input validator; only ``inputs.schema_`` matters here.
        definition = AutomationDefinition(
            name=playbook.name or "playbook",
            plan=[PlanStep(step_id="noop", action="agent_task")],
            inputs=Inputs(schema=playbook.inputs_schema),
        )
        try:
            validate_inputs(definition, inputs)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"inputs invalid: {exc}") from exc

    def _validate_tool_scope(
        self,
        tool_scope: list[str],
        definition: AutomationDefinition,
    ) -> None:
        """Ensure the declared tool scope only references registered/used actions."""
        allowed = set(_extract_tool_scope(definition))
        for action in tool_scope:
            if get_action(action) is None:
                raise HTTPException(status_code=422, detail=f"unknown action in tool_scope: {action}")
            if action not in allowed:
                raise HTTPException(
                    status_code=422,
                    detail=f"tool_scope action {action!r} is not used by the playbook plan",
                )

    def _build_triggers_from_definition(
        self,
        definition: AutomationDefinition,
    ) -> list[TriggerCreate]:
        """Convert the playbook's trigger specs into creatable triggers.

        ``manual`` is not registered in the trigger registry, so it is skipped here
        and can be created transiently through the manual run path.
        """
        trigger_creates: list[TriggerCreate] = []
        for spec in definition.triggers:
            if spec.type == TriggerType.MANUAL.value:
                continue
            try:
                trigger_type = TriggerType(spec.type)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"unknown trigger type {spec.type!r}") from exc
            trigger_creates.append(
                TriggerCreate(
                    type=trigger_type,
                    params=spec.params or {},
                    static_inputs={},
                    enabled=True,
                )
            )
        return trigger_creates

    async def _resolve_verticals(
        self,
        requested_verticals: list[str] | None,
        workspace_id: int,
    ) -> list[str]:
        """Use the requested verticals or default to the workspace vertical + ``general``."""
        if requested_verticals:
            return sorted(set(requested_verticals))
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            return ["general"]
        if workspace.vertical and workspace.vertical != "general":
            return sorted({workspace.vertical, "general"})
        return ["general"]

    async def _get_workspace_or_raise(self, workspace_id: int) -> Workspace:
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail=f"workspace {workspace_id} not found")
        return workspace

    async def _assert_models_billable(self, workspace_id: int) -> Workspace:
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail=f"workspace {workspace_id} not found")
        try:
            assert_automation_models_billable(workspace)
        except AutomationModelPolicyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return workspace

    async def _get_playbook_or_raise(self, playbook_id: int) -> Playbook:
        stmt = (
            select(Playbook)
            .where(Playbook.id == playbook_id)
            .options(selectinload(Playbook.automations))
        )
        playbook = (await self.session.execute(stmt)).scalar_one_or_none()
        if playbook is None:
            raise HTTPException(status_code=404, detail=f"playbook {playbook_id} not found")
        return playbook

    async def _get_automation_or_raise(self, automation_id: int) -> Automation:
        automation = await self.session.get(Automation, automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail=f"automation {automation_id} not found")
        return automation

    async def _authorize_playbook_access(
        self,
        playbook: Playbook,
        permission: str,
    ) -> None:
        if playbook.scope == PlaybookScope.SYSTEM:
            # System playbooks are readable by any authenticated user;
            # writes are not exposed to workspace users.
            if permission == Permission.AUTOMATIONS_READ.value:
                return
            raise HTTPException(status_code=403, detail="system playbooks are read-only")

        if playbook.workspace_id is None:
            raise HTTPException(status_code=403, detail="playbook has no owning workspace")
        await self._authorize(playbook.workspace_id, permission)

    async def _authorize(self, workspace_id: int, permission: str) -> None:
        await check_permission(
            self.session,
            self.auth,
            workspace_id,
            permission,
            f"You don't have permission to {permission.split(':')[1]} playbooks in this workspace",
        )


def get_playbook_service(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> PlaybookService:
    return PlaybookService(session=session, auth=auth)
