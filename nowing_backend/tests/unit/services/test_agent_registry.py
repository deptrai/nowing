from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture

from app.services.agent_registry import (
    AgentConfigNotFoundError,
    get_agent_config,
    list_agents,
    upsert_agent_config,
)

pytestmark = pytest.mark.unit


def _make_config(**kwargs):
    defaults = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "client_id": "bdsai.vn",
        "name": "BDS AI Listing Assistant",
        "display_name": "BDS AI Listing Assistant",
        "slug": "bdsai-listing-assistant",
        "system_instructions": "You are helpful.",
        "enabled_tools": ["update_memory", "create_automation"],
        "disabled_tools": [],
        "model_name": None,
        "citations_enabled": True,
        "is_active": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _result(config=None, all_configs=None):
    if all_configs is None:
        all_configs = [config] if config else []
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(
            first=lambda: config,
            all=lambda: all_configs,
        ),
        scalar_one_or_none=lambda: config,
        unique=lambda: SimpleNamespace(scalar_one_or_none=lambda: config),
    )


@pytest.fixture
def session(mocker: MockerFixture):
    session = mocker.AsyncMock()
    # ``session.add`` is a synchronous call on the real AsyncSession.
    session.add = mocker.MagicMock()
    return session


@pytest.mark.anyio
async def test_get_agent_config_returns_active_config(session):
    config = _make_config()
    session.execute.return_value = _result(config)

    result = await get_agent_config(session, "bdsai.vn", "bdsai-listing-assistant")
    assert result.id == config.id
    assert result.name == config.name


@pytest.mark.anyio
async def test_get_agent_config_fails_closed_on_missing(session):
    session.execute.return_value = _result(None)
    with pytest.raises(AgentConfigNotFoundError):
        await get_agent_config(session, "bdsai.vn", "nonexistent")


@pytest.mark.anyio
async def test_get_agent_config_fails_closed_on_inactive(session):
    config = _make_config(is_active=False)
    session.execute.return_value = _result(config)
    with pytest.raises(AgentConfigNotFoundError):
        await get_agent_config(session, "bdsai.vn", "bdsai-listing-assistant")


@pytest.mark.anyio
async def test_get_agent_config_fails_closed_for_other_client(session):
    config = _make_config(client_id="other.vn")
    session.execute.return_value = _result(config)
    with pytest.raises(AgentConfigNotFoundError):
        await get_agent_config(session, "bdsai.vn", "bdsai-listing-assistant")


@pytest.mark.anyio
async def test_list_agents_is_global_not_workspace_scoped(session):
    a = _make_config(client_id="bdsai.vn")
    b = _make_config(client_id="other.vn", slug="other-agent", name="Other")
    session.execute.return_value = _result(None, [a, b])

    configs = await list_agents(session)
    client_ids = {c.client_id for c in configs}
    assert client_ids == {"bdsai.vn", "other.vn"}


@pytest.mark.anyio
async def test_list_agents_filters_by_client(session):
    a = _make_config()
    _ = _make_config(client_id="other.vn", slug="other-agent", name="Other")
    session.execute.return_value = _result(None, [a])

    configs = await list_agents(session, client_id="bdsai.vn")
    assert len(configs) == 1
    assert configs[0].slug == "bdsai-listing-assistant"


@pytest.mark.anyio
async def test_upsert_agent_config_is_idempotent_existing(session):
    config = _make_config()
    session.execute.return_value = _result(config)

    result = await upsert_agent_config(
        session,
        client_id="bdsai.vn",
        slug="bdsai-listing-assistant",
        name="BDS AI Listing Assistant",
        system_instructions="Updated.",
    )
    assert result.id == config.id
    assert result.system_instructions == "Updated."
    session.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_upsert_agent_config_is_idempotent_new(session):
    session.execute.return_value = _result(None)

    result = await upsert_agent_config(
        session,
        client_id="bdsai.vn",
        slug="new-agent",
        name="New Agent",
        is_active=True,
    )
    assert result.slug == "new-agent"
    assert result.client_id == "bdsai.vn"
    session.add.assert_called_once()
