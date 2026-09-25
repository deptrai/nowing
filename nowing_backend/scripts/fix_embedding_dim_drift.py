#!/usr/bin/env python3
"""Repair local/dev DBs whose vector columns were migrated under a different
embedding model than the one configured now.

Schema derives embedding dims from ``config.embedding_model_instance.dimension``
at migration time. If ``EMBEDDING_MODEL`` changed after the DB was migrated
(e.g. ``.env.local`` now pins ``ollama/nomic-embed-text`` = 768 while the column
was created at 384), every write to these columns fails with
``expected N dimensions, not M``.

This script:
  1. Alters config-derived embedding columns to the configured dimension.
     Old-dim vectors cannot be re-cast, so they are nulled first
     (``USING NULL``) — rows themselves are preserved.
  2. Re-embeds affected rows with the configured model via its real endpoint
     (``EMBEDDING_BASE_URL`` / ollama ``/api/embed``), so nothing is left
     unsearchable. Encrypted memories (``key_id IS NOT NULL``) are skipped —
     their content is ciphertext.
  3. Drops and recreates the HNSW index per altered column (preserving the
     partial ``WHERE embedding IS NOT NULL`` predicate on social_posts).

Run: ``uv run python scripts/fix_embedding_dim_drift.py`` from nowing_backend/.
Idempotent: columns already at the configured dim are skipped.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

sys.path.insert(0, ".")

from sqlalchemy import text

from app.config import config
from app.config.embedding_settings import resolve_embedding_base_url
from app.db import async_session_maker

# table -> dict(src_col, index, index_where, not_null, extra_null_filter)
TARGETS = {
    "memories": {
        "src_col": "content",
        "index": "ix_memories_embedding",
        "index_where": None,
        "not_null": True,
        "null_filter": "AND key_id IS NULL",  # skip encrypted rows
    },
    "documents": {
        "src_col": "content",
        "index": "document_vector_index",
        "index_where": None,
        "not_null": False,
        "null_filter": "",
    },
    "chunks": {
        "src_col": "content",
        "index": "chucks_vector_index",
        "index_where": None,
        "not_null": False,
        "null_filter": "",
    },
    "social_posts": {
        "src_col": "content",
        "index": "idx_social_posts_embedding_hnsw",
        "index_where": "WHERE (embedding IS NOT NULL)",
        "not_null": False,
        "null_filter": "",
    },
}

EMBED_BATCH = 32


async def _current_dim(session, table: str) -> int | None:
    return (
        await session.execute(
            text(
                "SELECT a.atttypmod FROM pg_attribute a"
                " JOIN pg_class c ON c.oid = a.attrelid"
                " JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' AND c.relname = :t"
                "   AND a.attname = 'embedding'"
            ),
            {"t": table},
        )
    ).scalar_one_or_none()


def _ollama_model_name(embedding_model: str) -> str:
    # litellm://ollama/nomic-embed-text -> nomic-embed-text
    return embedding_model.removeprefix("litellm://").split("/", 1)[-1]


async def _reembed(
    session, client: httpx.AsyncClient, base_url: str, model: str, table: str, spec: dict,
    ids: list,
) -> int:
    src = spec["src_col"]
    rows = (
        await session.execute(
            text(
                f"SELECT id, {src} FROM {table}"
                f" WHERE id = ANY(:ids) AND {src} IS NOT NULL {spec['null_filter']}"
            ),
            {"ids": ids},
        )
    ).all()
    for i in range(0, len(rows), EMBED_BATCH):
        batch = rows[i : i + EMBED_BATCH]
        r = await client.post(
            f"{base_url}/api/embed",
            json={"model": model, "input": [str(row[1])[:8000] for row in batch]},
            timeout=120,
        )
        r.raise_for_status()
        for (rid, _), vec in zip(batch, r.json()["embeddings"], strict=True):
            await session.execute(
                text(f"UPDATE {table} SET embedding = CAST(:v AS vector) WHERE id = :id"),
                {"v": "[" + ",".join(map(str, vec)) + "]", "id": rid},
            )
        print(f"    {table}: re-embedded {min(i + EMBED_BATCH, len(rows))}/{len(rows)}")
    return len(rows)


async def main() -> None:
    target_dim = config.embedding_model_instance.dimension
    embedding_model = config.EMBEDDING_MODEL or ""
    base_url = resolve_embedding_base_url()
    print(f"configured model={embedding_model} dim={target_dim} base_url={base_url}")

    async with async_session_maker() as session:
        altered: dict[str, list] = {}
        for table, spec in TARGETS.items():
            cur = await _current_dim(session, table)
            if cur is None or cur == target_dim:
                print(f"  {table}: {'no column' if cur is None else f'already {target_dim}'} — skip")
                continue
            # Snapshot rows that HAVE embeddings — only those get re-embedded.
            ids = [
                r[0]
                for r in (
                    await session.execute(
                        text(f"SELECT id FROM {table} WHERE embedding IS NOT NULL")
                    )
                ).all()
            ]
            print(f"  {table}: {cur} -> {target_dim} ({len(ids)} embedded rows)")
            await session.execute(text(f'DROP INDEX IF EXISTS "{spec["index"]}"'))
            if spec["not_null"]:
                await session.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN embedding DROP NOT NULL")
                )
            await session.execute(
                text(
                    f"ALTER TABLE {table} ALTER COLUMN embedding"
                    f" TYPE vector({target_dim}) USING NULL::vector"
                )
            )
            altered[table] = ids

        can_embed = bool(base_url) and "ollama/" in embedding_model
        if altered and can_embed:
            model = _ollama_model_name(embedding_model)
            async with httpx.AsyncClient() as client:
                for table, ids in altered.items():
                    spec = TARGETS[table]
                    if ids:
                        n = await _reembed(session, client, base_url, model, table, spec, ids)
                        print(f"    {table}: re-embedded {n}/{len(ids)} rows")
                    if spec["not_null"]:
                        remaining = (
                            await session.execute(
                                text(f"SELECT COUNT(*) FROM {table} WHERE embedding IS NULL")
                            )
                        ).scalar()
                        if remaining == 0:
                            await session.execute(
                                text(f"ALTER TABLE {table} ALTER COLUMN embedding SET NOT NULL")
                            )
                        else:
                            print(
                                f"    {table}: {remaining} rows still NULL"
                                " (encrypted/no-content) — NOT NULL not restored"
                            )
        elif altered:
            print("  no ollama endpoint — embeddings left NULL; re-index to regenerate")
            for table, spec in TARGETS.items():
                if spec["not_null"] and table in altered:
                    print(f"    {table}: NOT NULL left dropped — restore after re-embedding")

        for table in altered:
            spec = TARGETS[table]
            where = spec["index_where"] or ""
            await session.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS "{spec["index"]}" ON {table}'
                    f" USING hnsw (embedding public.vector_cosine_ops) {where}"
                )
            )
        await session.commit()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
