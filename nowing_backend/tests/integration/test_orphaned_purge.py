import pytest
from sqlalchemy import text
from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned

@pytest.mark.asyncio
async def test_orphaned_purge_integration_db(db_session, search_space_factory, snapshot_factory):
    """[P1] Integration: Verify orphaned snapshots are deleted while active ones remain."""
    # 1. Setup data
    space = await search_space_factory.create()
    # Active snapshot
    active_snap = await snapshot_factory.create(search_space_id=space.id)
    # Orphaned snapshot (search_space_id exists but space will be deleted)
    orphan_space = await search_space_factory.create()
    orphan_snap = await snapshot_factory.create(search_space_id=orphan_space.id)
    
    # 2. Delete space to create orphan
    await db_session.delete(orphan_space)
    await db_session.commit()

    # 3. Run purge
    await _async_cleanup_orphaned()

    # 4. Verify
    result = await db_session.execute(text("SELECT id FROM crypto_data_snapshots"))
    remaining_ids = [r[0] for r in result.fetchall()]
    
    assert active_snap.id in remaining_ids
    assert orphan_snap.id not in remaining_ids