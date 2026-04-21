"""Integration tests for local folder indexer — Tier 5 (P1), Tier 6 (B1-B2), Tier 7 (DC1-DC4)."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Document,
    DocumentStatus,
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
# Tier 6: Batch Mode (B1-B2)
# ====================================================================


class TestBatchMode:
    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_b1_batch_indexes_multiple_files(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
        patched_batch_sessions,
    ):
        """B1: Batch with 3 files indexes all of them."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "a.md").write_text("File A content")
        (tmp_path / "b.md").write_text("File B content")
        (tmp_path / "c.md").write_text("File C content")

        count, failed, _root_folder_id, err = await index_local_folder(
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

        assert count == 3
        assert failed == 0
        assert err is None

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
        assert len(docs) == 3
        assert {d.title for d in docs} == {"a.md", "b.md", "c.md"}
        assert all(
            DocumentStatus.is_state(d.status, DocumentStatus.READY) for d in docs
        )

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_b2_partial_failure(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
        patched_batch_sessions,
    ):
        """B2: One unreadable file fails gracefully; the other two still get indexed."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "good1.md").write_text("Good file one")
        (tmp_path / "good2.md").write_text("Good file two")
        (tmp_path / "bad.md").write_bytes(b"\x00binary garbage")

        count, failed, _, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[
                str(tmp_path / "good1.md"),
                str(tmp_path / "bad.md"),
                str(tmp_path / "good2.md"),
            ],
        )

        assert count == 2
        assert failed == 1
        assert err is not None

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
        assert len(docs) == 2
        assert {d.title for d in docs} == {"good1.md", "good2.md"}


# ====================================================================
# Tier 5: Pipeline Integration (P1)
# ====================================================================


class TestPipelineIntegration:
    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_p1_local_folder_file_through_pipeline(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        mocker,
    ):
        """P1: LOCAL_FOLDER_FILE ConnectorDocument through prepare+index to READY."""
        from app.indexing_pipeline.connector_document import ConnectorDocument
        from app.indexing_pipeline.indexing_pipeline_service import (
            IndexingPipelineService,
        )

        doc = ConnectorDocument(
            title="Test Local File",
            source_markdown="## Local file\n\nContent from disk.",
            unique_id="test-folder:test.md",
            document_type=DocumentType.LOCAL_FOLDER_FILE,
            search_space_id=db_search_space.id,
            connector_id=None,
            created_by_id=str(db_user.id),
        )

        service = IndexingPipelineService(session=db_session)
        prepared = await service.prepare_for_indexing([doc])
        assert len(prepared) == 1

        db_doc = prepared[0]
        result = await service.index(db_doc, doc, llm=mocker.Mock())
        assert result is not None

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
        assert DocumentStatus.is_state(docs[0].status, DocumentStatus.READY)


# ====================================================================
# Tier 7: Direct Converters (DC1-DC4)
# ====================================================================


class TestDirectConvert:
    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_dc1_csv_produces_markdown_table(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """DC1: CSV file is indexed as a markdown table, not raw comma-separated text."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "data.csv").write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert err is None
        assert count == 1

        doc = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()

        assert "| name" in doc.source_markdown
        assert "| Alice" in doc.source_markdown
        assert "name,age,city" not in doc.source_markdown

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_dc2_tsv_produces_markdown_table(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """DC2: TSV file is indexed as a markdown table."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "data.tsv").write_text(
            "name\tage\tcity\nAlice\t30\tNYC\nBob\t25\tLA\n"
        )

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert err is None
        assert count == 1

        doc = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()

        assert "| name" in doc.source_markdown
        assert "| Alice" in doc.source_markdown

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_dc3_html_produces_clean_markdown(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """DC3: HTML file is indexed as clean markdown, not raw HTML."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "page.html").write_text("<h1>Title</h1><p>Hello world</p>")

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert err is None
        assert count == 1

        doc = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()

        assert "Title" in doc.source_markdown
        assert "<h1>" not in doc.source_markdown

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_dc4_csv_single_file_mode(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """DC4: CSV via single-file batch mode also produces a markdown table."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "data.csv").write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")

        count, _skipped, _root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(tmp_path / "data.csv")],
        )

        assert err is None
        assert count == 1

        doc = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()

        assert "| name" in doc.source_markdown
        assert "name,age,city" not in doc.source_markdown
