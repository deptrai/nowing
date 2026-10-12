"""Unit tests for AgentConfig schemas tool disjointness and duplicate validation."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_config import AgentConfigCreate, AgentConfigUpdate


def test_agent_config_create_disjoint_tools_validation():
    """Overlap between enabled_tools and disabled_tools raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentConfigCreate(
            client_id="client_1",
            name="Test Agent",
            display_name="Test Agent",
            enabled_tools=["update_memory", "create_automation"],
            disabled_tools=["update_memory"],
        )
    err = str(exc_info.value)
    assert "enabled_tools and disabled_tools must be disjoint" in err
    assert "update_memory" in err


def test_agent_config_create_duplicate_tools_rejected():
    """Duplicate tools in enabled_tools or disabled_tools raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentConfigCreate(
            client_id="client_1",
            name="Test Agent",
            display_name="Test Agent",
            enabled_tools=["update_memory", "update_memory"],
            disabled_tools=[],
        )
    err = str(exc_info.value)
    assert "duplicate tool names" in err
    assert "update_memory" in err

    with pytest.raises(ValidationError) as exc_info:
        AgentConfigCreate(
            client_id="client_1",
            name="Test Agent",
            display_name="Test Agent",
            enabled_tools=[],
            disabled_tools=["create_automation", "create_automation"],
        )
    err = str(exc_info.value)
    assert "duplicate tool names" in err
    assert "create_automation" in err


def test_agent_config_create_valid_passes():
    """Valid disjoint tools without duplicates passes validation."""
    config = AgentConfigCreate(
        client_id="client_1",
        name="Test Agent",
        display_name="Test Agent",
        enabled_tools=["update_memory"],
        disabled_tools=["create_automation"],
    )
    assert config.enabled_tools == ["update_memory"]
    assert config.disabled_tools == ["create_automation"]


def test_agent_config_update_disjoint_and_duplicate_validation():
    """AgentConfigUpdate validates disjoint sets and rejects duplicates."""
    # Duplicate in enabled_tools
    with pytest.raises(ValidationError) as exc_info:
        AgentConfigUpdate(
            enabled_tools=["update_memory", "update_memory"],
        )
    assert "duplicate tool names" in str(exc_info.value)

    # Overlap between enabled_tools and disabled_tools
    with pytest.raises(ValidationError) as exc_info:
        AgentConfigUpdate(
            enabled_tools=["update_memory"],
            disabled_tools=["update_memory"],
        )
    assert "enabled_tools and disabled_tools must be disjoint" in str(exc_info.value)

    # Valid update
    up = AgentConfigUpdate(
        enabled_tools=["update_memory"],
        disabled_tools=["create_automation"],
    )
    assert up.enabled_tools == ["update_memory"]
    assert up.disabled_tools == ["create_automation"]
