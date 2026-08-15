"""In-process capability registry, populated at import by each verb's ``definition.py``."""

from __future__ import annotations

from typing import Any

from app.capabilities.core.types import Capability

_REGISTRY: dict[str, Capability] = {}


class CapabilityRegistry:
    """Canonical in-process registry of executable verbs."""

    @classmethod
    def register(cls, capability: Capability) -> None:
        """Add a verb by name."""
        if capability.name in _REGISTRY:
            raise ValueError(f"Action already registered: {capability.name}")
        if capability.metadata is not None:
            if "emits_signals" in capability.metadata and not isinstance(
                capability.metadata["emits_signals"], bool
            ):
                raise ValueError("emits_signals must be boolean")
            if "signal_types" in capability.metadata:
                signal_types = capability.metadata["signal_types"]
                if not isinstance(signal_types, list) or not signal_types:
                    raise ValueError("signal_types must not be empty")
        _REGISTRY[capability.name] = capability

    @classmethod
    def get(cls, name: str) -> Capability:
        return _REGISTRY[name]

    @classmethod
    def all(cls) -> list[Capability]:
        return list(_REGISTRY.values())

    @classmethod
    def query_metadata(cls, key: str) -> dict[str, Any]:
        """Return ``{capability_name: metadata_value}`` for every capability that has ``key``."""
        return {
            capability.name: capability.metadata[key]
            for capability in _REGISTRY.values()
            if capability.metadata and key in capability.metadata
        }

    @classmethod
    def query_metadata_for(cls, name: str, key: str) -> Any | None:
        """Return a single metadata value for a specific capability, or ``None``."""
        capability = _REGISTRY.get(name)
        if capability is None or not capability.metadata:
            return None
        return capability.metadata.get(key)


def register_capability(capability: Capability) -> None:
    """Add (or replace) a verb by name."""
    CapabilityRegistry.register(capability)


def get_capability(name: str) -> Capability:
    return CapabilityRegistry.get(name)


def all_capabilities() -> list[Capability]:
    return CapabilityRegistry.all()
