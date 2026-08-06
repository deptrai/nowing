"""Celery task for polling RSS news feeds."""

from app.celery_app import celery_app
from app.tasks.celery_tasks import (
    get_celery_session_maker,
    run_async_celery_task as _run_async_celery_task,
)
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds


@celery_app.task(name="index_rss_feeds", bind=True)
def index_rss_feeds_task(
    self,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Celery task to fetch and index RSS news articles for a connector.

    ``start_date`` and ``end_date`` are ignored; RSS is a rolling feed.
    They are kept in the signature so the meta-scheduler can dispatch this
    task with the same positional arguments as other connector tasks.
    """

    async def _run():
        async with get_celery_session_maker()() as session:
            await index_rss_feeds(session, connector_id, workspace_id, user_id)

    return _run_async_celery_task(_run)
