import pytest
import uuid
from sqlalchemy import text
from unittest.mock import AsyncMock, MagicMock, patch
from app.db import User, SearchSpace, CryptoProject, CryptoDataSnapshot
from tests.utils.factories import make_user, make_search_space
from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
from datetime import datetime, UTC, timedelta

@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_cleanup_orphaned_integration(async_session):
    \"\"\"Integration test for _async_cleanup_orphaned using a real test DB (SQLite).\"\"\"
    
    # 1. Setup Data
    user_data = make_user()
    user = User(**user_data)
    async_session.add(user)
    await async_session.commit()
    
    # Create a project
    project = CryptoProject(
        project_id=f"test-project-{uuid.uuid4().hex[:6]}",
        symbol="TEST",
        name="Test Project",
        chain="ethereum"
    )
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    
    # Create SearchSpace 1 (Valid)
    ss1_data = make_search_space(user_id=user.id)
    ss1 = SearchSpace(**ss1_data)
    async_session.add(ss1)
    await async_session.commit()
    await async_session.refresh(ss1)
    
    # Create SearchSpace 2 (To be orphaned)
    ss2_data = make_search_space(user_id=user.id)
    ss2 = SearchSpace(**ss2_data)
    async_session.add(ss2)
    await async_session.commit()
    await async_session.refresh(ss2)
    
    # 2. Create Snapshots
    # S1: Valid (linked to ss1)
    s1 = CryptoDataSnapshot(
        search_space_id=ss1.id,
        project_id=project.id,
        data_category="price",
        tool_name="dexscreener",
        data={"price": 100},
        data_hash="hash1",
        fetched_at=datetime.now(UTC),
        ttl_seconds=3600,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        api_source="dexscreener"
    )
    
    # S2: To be orphaned (linked to ss2)
    s2 = CryptoDataSnapshot(
        search_space_id=ss2.id,
        project_id=project.id,
        data_category="price",
        tool_name="dexscreener",
        data={"price": 200},
        data_hash="hash2",
        fetched_at=datetime.now(UTC),
        ttl_seconds=3600,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        api_source="dexscreener"
    )
    
    async_session.add_all([s1, s2])
    await async_session.commit()
    await async_session.refresh(s1)
    await async_session.refresh(s2)
    
    # 3. Create an Orphan by deleting ss2 manually via raw SQL
    # We use raw SQL to avoid ORM cascades if they exist
    await async_session.execute(text(f"DELETE FROM searchspaces WHERE id = {ss2.id}"))
    await async_session.commit()
    
    # Verify we have 2 snapshots but one is an orphan
    res = await async_session.execute(text("SELECT count(*) FROM crypto_data_snapshots"))
    assert res.scalar() == 2
    
    # 4. Run the Cleanup Task
    # Patch session maker and lock to use our test session
    # Note: get_celery_session_maker is in app.tasks.celery_tasks
    with patch("app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker") as mock_maker, \
         patch("app.tasks.celery_tasks.crypto_refresh_tasks._try_acquire_orphan_lock", new=AsyncMock(return_value=(True, "token", AsyncMock()))), \
         patch("app.tasks.celery_tasks.crypto_refresh_tasks._release_orphan_lock", new=AsyncMock()):
        
        # mock_maker() should return an async_sessionmaker-like object that returns our session
        mock_session_maker = MagicMock()
        mock_session_maker.return_value = async_session
        mock_maker.return_value = mock_session_maker
        
        await _async_cleanup_orphaned()
        
    # 5. Verify Cleanup Result
    res = await async_session.execute(text("SELECT id FROM crypto_data_snapshots"))
    remaining_ids = res.scalars().all()
    
    assert len(remaining_ids) == 1
    assert remaining_ids[0] == s1.id
    
    # Final check: S2 is gone
    res = await async_session.execute(text(f"SELECT count(*) FROM crypto_data_snapshots WHERE id = {s2.id}"))
    assert res.scalar() == 0
