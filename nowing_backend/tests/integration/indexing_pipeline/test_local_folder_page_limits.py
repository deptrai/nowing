"""Integration tests for local folder indexer — Tier 8 (PL1-PL6), Tier 9 (IP1-IP3)."""

from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Document,
    DocumentType,
    Folder,
    SearchSpace,
    User,
)

pytestmark = pytest.mark.integration

UNIFIED_FIXTURES = (
    "patched_summarize",
    "patched_embed_texts",
    "patched_chunk_text",
)


class _FakeSessionMaker:
    """Wraps an existing AsyncSession so ``async with factory()`` yields it
    without closing it. Used to route batch-mode DB operations through the
    test's savepoint-wrapped session."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def __call__(self):
        @asynccontextmanager
        async def _ctx():
            yield self._session

        return _ctx()


@pytest.fixture
def patched_batch_sessions(monkeypatch, db_session):
    """Make ``_index_batch_files`` use the test session and run sequentially."""
    monkeypatch.setattr(
        "app.tasks.connector_indexers.local_folder_indexer.get_celery_session_maker",
        lambda: _FakeSessionMaker(db_session),
    )
    monkeypatch.setattr(
        "app.tasks.connector_indexers.local_folder_indexer.BATCH_CONCURRENCY",
        1,
    )


# ====================================================================
# Tier 8: Page Limits (PL1-PL6)
# ====================================================================


class TestPageLimits:
    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_pl1_full_scan_increments_pages_used(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """PL1: Successful full-scan sync increments user.pages_used."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        db_user.pages_used = 0
        db_user.pages_limit = 500
        await db_session.flush()

        (tmp_path / "note.md").write_text("# Hello World\n\nContent here.")

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert err is None
        assert count == 1

        await db_session.refresh(db_user)
        assert db_user.pages_used > 0, "pages_used should increase after indexing"

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_pl2_full_scan_blocked_when_limit_exhausted(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """PL2: Full-scan skips file when page limit is exhausted."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        db_user.pages_used = 100
        db_user.pages_limit = 100
        await db_session.flush()

        (tmp_path / "note.md").write_text("# Hello World\n\nContent here.")

        count, _skipped, _root_folder_id, _err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert count == 0

        await db_session.refresh(db_user)
        assert db_user.pages_used == 100, "pages_used should not change on rejection"

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_pl3_single_file_increments_pages_used(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """PL3: Single-file mode increments user.pages_used on success."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        db_user.pages_used = 0
        db_user.pages_limit = 500
        await db_session.flush()

        (tmp_path / "note.md").write_text("# Hello World\n\nContent here.")

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(tmp_path / "note.md")],
        )

        assert err is None
        assert count == 1

        await db_session.refresh(db_user)
        assert db_user.pages_used > 0, "pages_used should increase after indexing"

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_pl4_single_file_blocked_when_limit_exhausted(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """PL4: Single-file mode skips file when page limit is exhausted."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        db_user.pages_used = 100
        db_user.pages_limit = 100
        await db_session.flush()

        (tmp_path / "note.md").write_text("# Hello World\n\nContent here.")

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(tmp_path / "note.md")],
        )

        assert count == 0
        assert err is not None
        assert "page limit" in err.lower()

        await db_session.refresh(db_user)
        assert db_user.pages_used == 100, "pages_used should not change on rejection"

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_pl5_unchanged_resync_no_extra_pages(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """PL5: Re-syncing an unchanged file does not consume additional pages."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        db_user.pages_used = 0
        db_user.pages_limit = 500
        await db_session.flush()

        (tmp_path / "note.md").write_text("# Hello\n\nSame content.")

        count1, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )
        assert count1 == 1

        await db_session.refresh(db_user)
        pages_after_first = db_user.pages_used
        assert pages_after_first > 0

        count2, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )
        assert count2 == 0

        await db_session.refresh(db_user)
        assert db_user.pages_used == pages_after_first, (
            "pages_used should not increase for unchanged files"
        )

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_pl6_batch_partial_page_limit_exhaustion(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
        patched_batch_sessions,
    ):
        """PL6: Batch mode with a very low page limit: some files succeed, rest fail."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        db_user.pages_used = 0
        db_user.pages_limit = 1
        await db_session.flush()

        (tmp_path / "a.md").write_text("File A content")
        (tmp_path / "b.md").write_text("File B content")
        (tmp_path / "c.md").write_text("File C content")

        count, failed, _root_folder_id, _err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[
                str(tmp_path / "a.md"),
                str(tmp_path / "b.md"),
                str(tmp_path / "c.md"),
            ],
        )

        assert count >= 1, "at least one file should succeed"
        assert failed >= 1, "at least one file should fail due to page limit"
        assert count + failed == 3

        await db_session.refresh(db_user)
        assert db_user.pages_used > 0
        assert db_user.pages_used <= db_user.pages_limit + 1


# ====================================================================
# Tier 9: Indexing Progress Flag (IP1-IP3)
# ====================================================================


class TestIndexingProgressFlag:
    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_ip1_full_scan_clears_flag(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """IP1: Full-scan mode clears indexing_in_progress after completion."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "note.md").write_text("# Hello\n\nContent.")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert root_folder_id is not None
        root_folder = (
            await db_session.execute(select(Folder).where(Folder.id == root_folder_id))
        ).scalar_one()
        meta = root_folder.folder_metadata or {}
        assert "indexing_in_progress" not in meta

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_ip2_single_file_clears_flag(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """IP2: Single-file (Chokidar) mode clears indexing_in_progress after completion."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "root.md").write_text("root")
        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        (tmp_path / "new.md").write_text("new file content")

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(tmp_path / "new.md")],
            root_folder_id=root_folder_id,
        )

        root_folder = (
            await db_session.execute(select(Folder).where(Folder.id == root_folder_id))
        ).scalar_one()
        meta = root_folder.folder_metadata or {}
        assert "indexing_in_progress" not in meta

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_ip3_flag_set_during_indexing(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """IP3: indexing_in_progress is True on the root folder while indexing is running."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "note.md").write_text("# Check flag\n\nDuring indexing.")

        from app.indexing_pipeline.indexing_pipeline_service import (
            IndexingPipelineService,
        )

        original_index = IndexingPipelineService.index
        flag_observed = []

        async def patched_index(self_pipe, document, connector_doc, llm):
            folder = (
                await db_session.execute(
                    select(Folder).where(
                        Folder.search_space_id == db_search_space.id,
                        Folder.parent_id.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if folder:
                meta = folder.folder_metadata or {}
                flag_observed.append(meta.get("indexing_in_progress", False))
            return await original_index(self_pipe, document, connector_doc, llm)

        IndexingPipelineService.index = patched_index
        try:
            _, _, root_folder_id, _ = await index_local_folder(
                session=db_session,
                search_space_id=db_search_space.id,
                user_id=str(db_user.id),
                folder_path=str(tmp_path),
                folder_name="test-folder",
            )
        finally:
            IndexingPipelineService.index = original_index

        assert len(flag_observed) > 0, "index() should have been called at least once"
        assert all(flag_observed), "indexing_in_progress should be True during indexing"

        root_folder = (
            await db_session.execute(select(Folder).where(Folder.id == root_folder_id))
        ).scalar_one()
        meta = root_folder.folder_metadata or {}
        assert "indexing_in_progress" not in meta
