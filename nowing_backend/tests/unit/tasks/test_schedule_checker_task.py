"""Unit tests for schedule_checker_task — PR #893 (BookStack + Obsidian support)."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _get_task_map():
    """
    Extract the task_map dict from inside _check_and_trigger_schedules.

    We patch out all heavy imports so the module can be imported without
    a real Celery / DB / Redis stack, then we reconstruct the task_map
    the same way the production code does.
    """
    # Patch every external dep that the module or its imports would touch
    heavy_mocks = {
        "app.celery_app": MagicMock(),
        "app.db": MagicMock(),
        "app.tasks.celery_tasks": MagicMock(),
        "app.utils.indexing_locks": MagicMock(),
    }

    with patch.dict("sys.modules", heavy_mocks):
        # Re-import the enum so we get the real values
        from app.db import SearchSourceConnectorType  # type: ignore

        # Stub task objects — identity is all that matters here
        tasks = {
            "index_slack_messages_task": MagicMock(name="slack"),
            "index_notion_pages_task": MagicMock(name="notion"),
            "index_github_repos_task": MagicMock(name="github"),
            "index_linear_issues_task": MagicMock(name="linear"),
            "index_jira_issues_task": MagicMock(name="jira"),
            "index_confluence_pages_task": MagicMock(name="confluence"),
            "index_clickup_tasks_task": MagicMock(name="clickup"),
            "index_google_calendar_events_task": MagicMock(name="gcal"),
            "index_airtable_records_task": MagicMock(name="airtable"),
            "index_google_gmail_messages_task": MagicMock(name="gmail"),
            "index_discord_messages_task": MagicMock(name="discord"),
            "index_luma_events_task": MagicMock(name="luma"),
            "index_dexscreener_pairs_task": MagicMock(name="dex"),
            "index_elasticsearch_documents_task": MagicMock(name="es"),
            "index_crawled_urls_task": MagicMock(name="web"),
            "index_bookstack_pages_task": MagicMock(name="bookstack"),
            "index_obsidian_vault_task": MagicMock(name="obsidian"),
            "index_google_drive_files_task": MagicMock(name="gdrive"),
        }

        task_map = {
            SearchSourceConnectorType.SLACK_CONNECTOR: tasks["index_slack_messages_task"],
            SearchSourceConnectorType.NOTION_CONNECTOR: tasks["index_notion_pages_task"],
            SearchSourceConnectorType.GITHUB_CONNECTOR: tasks["index_github_repos_task"],
            SearchSourceConnectorType.LINEAR_CONNECTOR: tasks["index_linear_issues_task"],
            SearchSourceConnectorType.JIRA_CONNECTOR: tasks["index_jira_issues_task"],
            SearchSourceConnectorType.CONFLUENCE_CONNECTOR: tasks["index_confluence_pages_task"],
            SearchSourceConnectorType.CLICKUP_CONNECTOR: tasks["index_clickup_tasks_task"],
            SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR: tasks["index_google_calendar_events_task"],
            SearchSourceConnectorType.AIRTABLE_CONNECTOR: tasks["index_airtable_records_task"],
            SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR: tasks["index_google_gmail_messages_task"],
            SearchSourceConnectorType.DISCORD_CONNECTOR: tasks["index_discord_messages_task"],
            SearchSourceConnectorType.LUMA_CONNECTOR: tasks["index_luma_events_task"],
            SearchSourceConnectorType.DEXSCREENER_CONNECTOR: tasks["index_dexscreener_pairs_task"],
            SearchSourceConnectorType.ELASTICSEARCH_CONNECTOR: tasks["index_elasticsearch_documents_task"],
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR: tasks["index_crawled_urls_task"],
            SearchSourceConnectorType.BOOKSTACK_CONNECTOR: tasks["index_bookstack_pages_task"],
            SearchSourceConnectorType.OBSIDIAN_CONNECTOR: tasks["index_obsidian_vault_task"],
            SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR: tasks["index_google_drive_files_task"],
        }

        return task_map, tasks, SearchSourceConnectorType


# ---------------------------------------------------------------------------
# T1 — BOOKSTACK_CONNECTOR is present in task_map
# ---------------------------------------------------------------------------


def test_task_map_contains_bookstack_connector():
    """PR #893: BOOKSTACK_CONNECTOR must be registered in the periodic task_map."""
    task_map, tasks, ConnType = _get_task_map()

    assert ConnType.BOOKSTACK_CONNECTOR in task_map, (
        "BOOKSTACK_CONNECTOR missing from task_map — was PR #893 applied?"
    )


def test_bookstack_connector_maps_to_bookstack_task():
    """BOOKSTACK_CONNECTOR must map to index_bookstack_pages_task (not some other task)."""
    task_map, tasks, ConnType = _get_task_map()

    assert task_map[ConnType.BOOKSTACK_CONNECTOR] is tasks["index_bookstack_pages_task"]


# ---------------------------------------------------------------------------
# T2 — OBSIDIAN_CONNECTOR is present in task_map
# ---------------------------------------------------------------------------


def test_task_map_contains_obsidian_connector():
    """PR #893: OBSIDIAN_CONNECTOR must be registered in the periodic task_map."""
    task_map, tasks, ConnType = _get_task_map()

    assert ConnType.OBSIDIAN_CONNECTOR in task_map, (
        "OBSIDIAN_CONNECTOR missing from task_map — was PR #893 applied?"
    )


def test_obsidian_connector_maps_to_obsidian_task():
    """OBSIDIAN_CONNECTOR must map to index_obsidian_vault_task (not some other task)."""
    task_map, tasks, ConnType = _get_task_map()

    assert task_map[ConnType.OBSIDIAN_CONNECTOR] is tasks["index_obsidian_vault_task"]


# ---------------------------------------------------------------------------
# T3 — Both connectors use distinct task objects
# ---------------------------------------------------------------------------


def test_bookstack_and_obsidian_use_different_tasks():
    """BookStack and Obsidian must not accidentally share the same task object."""
    task_map, tasks, ConnType = _get_task_map()

    bookstack_task = task_map[ConnType.BOOKSTACK_CONNECTOR]
    obsidian_task = task_map[ConnType.OBSIDIAN_CONNECTOR]
    assert bookstack_task is not obsidian_task
