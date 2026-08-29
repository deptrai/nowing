"""Model-billing policy for automations.

Automations run unattended, so every run must be **explicitly billable**: the
user must choose a concrete model.  By default (``allow_global_model_selection=False``)
an automation may only use a premium global model (``billing_tier == "premium"``)
or a user-provided BYOK model (a positive model id).  Auto mode and free global
models are blocked because they can silently downgrade to an un-metered or
free deployment.

When ``allow_global_model_selection=True`` (e.g. playbook runs or HITL automation
approval), any global model may be selected explicitly, including free globals,
because the user has made a deliberate choice.  Auto mode (``id == 0``) is still
blocked for the same reason: it is not an explicit model.

Model id conventions (shared across chat / image / vision):
- ``id == 0``  → Auto mode (``AUTO_MODE_ID`` / ``IMAGE_GEN_AUTO_MODE_ID`` /
  ``VISION_AUTO_MODE_ID``). Always blocked.
- ``id < 0``   → global YAML/OpenRouter config. Allowed if premium, or if the
  caller explicitly passes ``allow_global_model_selection=True``.
- ``id > 0``   → user BYOK DB row. Always allowed.

This module is the single source of truth used by both creation-time enforcement
(``AutomationService.create`` and the ``create_automation`` chat tool) and the
runtime backstop (``agent_task`` dependencies).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.db import Workspace

ModelKind = Literal["chat", "image", "vision"]

_KIND_LABEL: dict[ModelKind, str] = {
    "chat": "chat model",
    "image": "image generation model",
    "vision": "vision model",
}

_KIND_CAPABILITY: dict[ModelKind, str] = {
    "chat": "supports_chat",
    "image": "supports_image_generation",
    "vision": "supports_image_input",
}


def _get_global_model(model_id: int) -> dict | None:
    """Return the global model record for a negative (global) model id."""
    from app.config import config as app_config

    return next((m for m in app_config.GLOBAL_MODELS if m.get("id") == model_id), None)


def _is_premium_global(model_id: int) -> bool:
    """Return True if a negative (global) model id is a premium tier model."""
    model = _get_global_model(model_id)
    if not model:
        return False
    return str(model.get("billing_tier", "free")).lower() == "premium"


def _classify(
    kind: ModelKind,
    model_id: int | None,
    *,
    allow_global_model_selection: bool = False,
) -> tuple[bool, str]:
    """Classify a resolved model id as allowed or blocked.

    Returns ``(allowed, reason)``; ``reason`` is empty when allowed.
    """
    label = _KIND_LABEL[kind]

    if model_id is None or model_id == 0:
        return (
            False,
            f"The {label} is set to Auto mode. Automations require an explicit "
            "model selection so every run is billable.",
        )

    if model_id > 0:
        # Positive id -> user/workspace BYOK model. Always allowed.
        return True, ""

    # Negative id -> global model. Always allowed if the caller explicitly chose
    # a known, enabled, capable global model; otherwise only premium globals are
    # allowed.
    if allow_global_model_selection:
        model = _get_global_model(model_id)
        if not model:
            return (
                False,
                f"The {label} references an unknown global model. "
                "Please select a valid global model.",
            )
        if not model.get("enabled", True):
            return (
                False,
                f"The {label} references a disabled global model. "
                "Please select an enabled global model.",
            )
        capability_key = _KIND_CAPABILITY[kind]
        if not model.get(capability_key, False):
            return (
                False,
                f"The {label} does not support {label} output. "
                "Please select a model with the right capability.",
            )
        return True, ""

    if _is_premium_global(model_id):
        return True, ""

    return (
        False,
        f"The {label} is a free model. Automations can only use premium models "
        "or your own (BYOK) models so every run is billable.",
    )


def get_model_eligibility(
    *,
    chat_model_id: int | None,
    image_gen_model_id: int | None,
    vision_model_id: int | None,
    allow_global_model_selection: bool = False,
) -> dict:
    """Return ``{"allowed": bool, "violations": [...]}`` for explicit model ids.

    The ID-based core shared by both the workspace path (creation/eligibility)
    and the captured-snapshot path (runtime backstop). Each violation is
    ``{"kind", "model_id", "reason"}``.

    When ``allow_global_model_selection`` is True, any negative (global) model id
    is accepted as long as it resolves to a known global model.  This is used for
    playbook runs and other HITL flows where the user has explicitly picked a
    global model rather than relying on Auto mode.
    """
    checks: list[tuple[ModelKind, int | None]] = [
        ("chat", chat_model_id),
        ("image", image_gen_model_id),
        ("vision", vision_model_id),
    ]

    violations: list[dict] = []
    for kind, model_id in checks:
        allowed, reason = _classify(
            kind, model_id, allow_global_model_selection=allow_global_model_selection
        )
        if not allowed:
            violations.append({"kind": kind, "model_id": model_id, "reason": reason})

    return {"allowed": not violations, "violations": violations}


def get_automation_model_eligibility(
    workspace: Workspace,
    *,
    allow_global_model_selection: bool = False,
) -> dict:
    """Return ``{"allowed": bool, "violations": [...]}`` for a workspace.

    Used by the eligibility endpoint and the chat tool's early check. Thin
    wrapper over :func:`get_model_eligibility`.
    """
    return get_model_eligibility(
        chat_model_id=workspace.chat_model_id,
        image_gen_model_id=workspace.image_gen_model_id,
        vision_model_id=workspace.vision_model_id,
        allow_global_model_selection=allow_global_model_selection,
    )


class AutomationModelPolicyError(Exception):
    """Raised when a workspace's models are not billable for automations."""

    def __init__(self, violations: list[dict]) -> None:
        self.violations = violations
        reasons = "; ".join(v["reason"] for v in violations)
        super().__init__(
            reasons or "Automations require premium or BYOK models for all model slots."
        )


def assert_models_billable(
    *,
    chat_model_id: int | None,
    image_gen_model_id: int | None,
    vision_model_id: int | None,
    allow_global_model_selection: bool = False,
) -> None:
    """Raise :class:`AutomationModelPolicyError` if any explicit id is not billable.

    The ID-based core used by the runtime backstop against an automation's
    captured model snapshot.
    """
    result = get_model_eligibility(
        chat_model_id=chat_model_id,
        image_gen_model_id=image_gen_model_id,
        vision_model_id=vision_model_id,
        allow_global_model_selection=allow_global_model_selection,
    )
    if not result["allowed"]:
        raise AutomationModelPolicyError(result["violations"])


def assert_automation_models_billable(
    workspace: Workspace,
    *,
    allow_global_model_selection: bool = False,
) -> None:
    """Raise :class:`AutomationModelPolicyError` if any model slot is not billable."""
    result = get_automation_model_eligibility(
        workspace, allow_global_model_selection=allow_global_model_selection
    )
    if not result["allowed"]:
        raise AutomationModelPolicyError(result["violations"])
