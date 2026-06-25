"""Integration tests for local folder indexer — Tier 3: Full Indexer (I1-I5)."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Document,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
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
# Tier 3: Full Indexer Integration (I1-I5)
# ====================================================================


class TestFullIndexer:
    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i1_new_file_indexed(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I1: Single new .md file is indexed with status READY."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

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

        docs = (
            (
                await db_session.execute(
                    select(Document).where(
                        Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                        Document.search_space_id == db_search_space.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(docs) == 1
        assert docs[0].document_type == DocumentType.LOCAL_FOLDER_FILE
        assert DocumentStatus.is_state(docs[0].status, DocumentStatus.READY)

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i2_unchanged_skipped(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I2: Second run on unchanged directory creates no new documents."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "note.md").write_text("# Hello\n\nSame content.")

        count1, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )
        assert count1 == 1

        count2, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )
        assert count2 == 0

        total = (
            await db_session.execute(
                select(func.count())
                .select_from(Document)
                .where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()
        assert total == 1

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i3_changed_reindexed(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I3: Modified file content triggers re-index and creates a version."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        f = tmp_path / "note.md"
        f.write_text("# Version 1\n\nOriginal.")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        f.write_text("# Version 2\n\nUpdated.")
        os.utime(f, (f.stat().st_atime + 10, f.stat().st_mtime + 10))

        count, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )
        assert count == 1

        versions = (
            (
                await db_session.execute(
                    select(DocumentVersion)
                    .join(Document)
                    .where(
                        Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                        Document.search_space_id == db_search_space.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(versions) >= 1

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i4_deleted_removed(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I4: Deleted file is removed from DB on re-sync."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        f = tmp_path / "to_delete.md"
        f.write_text("# Delete me")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        docs_before = (
            await db_session.execute(
                select(func.count())
                .select_from(Document)
                .where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()
        assert docs_before == 1

        f.unlink()

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )

        docs_after = (
            await db_session.execute(
                select(func.count())
                .select_from(Document)
                .where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()
        assert docs_after == 0

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i5_single_file_mode(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I5: Batch mode with a single file only processes that file."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "a.md").write_text("File A")
        (tmp_path / "b.md").write_text("File B")
        (tmp_path / "c.md").write_text("File C")

        count, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(tmp_path / "b.md")],
        )
        assert count == 1

        docs = (
            (
                await db_session.execute(
                    select(Document).where(
                        Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                        Document.search_space_id == db_search_space.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(docs) == 1
        assert docs[0].title == "b.md"
