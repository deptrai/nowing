"""Local folder DB folder mirroring and cleanup helpers."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Folder


async def _mirror_folder_structure(
    session: AsyncSession,
    folder_path: str,
    folder_name: str,
    workspace_id: int,
    user_id: str,
    root_folder_id: int | None = None,
    exclude_patterns: list[str] | None = None,
) -> tuple[dict[str, int], int]:
    """Mirror the local filesystem directory structure into DB Folder rows.

    Returns (mapping, root_folder_id) where mapping is
    relative_dir_path -> folder_id. The empty string key maps to the root folder.
    """
    root = Path(folder_path)
    if exclude_patterns is None:
        exclude_patterns = []

    subdirs: list[str] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_patterns]
        rel = Path(dirpath).relative_to(root)
        if any(part in exclude_patterns for part in rel.parts):
            continue
        rel_str = str(rel) if str(rel) != "." else ""
        if rel_str:
            subdirs.append(rel_str)

    subdirs.sort(key=lambda p: p.count(os.sep))

    mapping: dict[str, int] = {}

    if root_folder_id:
        existing = (
            await session.execute(select(Folder).where(Folder.id == root_folder_id))
        ).scalar_one_or_none()
        if existing:
            mapping[""] = existing.id
        else:
            root_folder_id = None

    if not root_folder_id:
        root_folder = Folder(
            name=folder_name,
            workspace_id=workspace_id,
            created_by_id=user_id,
            position="a0",
        )
        session.add(root_folder)
        await session.flush()
        mapping[""] = root_folder.id
        root_folder_id = root_folder.id

    for rel_dir in subdirs:
        dir_parts = Path(rel_dir).parts
        dir_name = dir_parts[-1]
        parent_rel = str(Path(*dir_parts[:-1])) if len(dir_parts) > 1 else ""

        parent_id = mapping.get(parent_rel, mapping[""])

        existing_folder = (
            await session.execute(
                select(Folder).where(
                    Folder.name == dir_name,
                    Folder.parent_id == parent_id,
                    Folder.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()

        if existing_folder:
            mapping[rel_dir] = existing_folder.id
        else:
            new_folder = Folder(
                name=dir_name,
                parent_id=parent_id,
                workspace_id=workspace_id,
                created_by_id=user_id,
                position="a0",
            )
            session.add(new_folder)
            await session.flush()
            mapping[rel_dir] = new_folder.id

    await session.flush()
    return mapping, root_folder_id


async def _resolve_folder_for_file(
    session: AsyncSession,
    rel_path: str,
    root_folder_id: int,
    workspace_id: int,
    user_id: str,
) -> int:
    """Given a file's relative path, ensure all parent Folder rows exist and
    return the folder_id for the file's immediate parent directory.

    For a file at "notes/daily/today.md", this ensures Folder rows exist for
    "notes" and "notes/daily", and returns the id of "notes/daily".
    For a file at "readme.md" (root level), returns root_folder_id.
    """
    parent_dir = str(Path(rel_path).parent)
    if parent_dir == ".":
        return root_folder_id

    parts = Path(parent_dir).parts
    current_parent_id = root_folder_id

    for part in parts:
        existing = (
            await session.execute(
                select(Folder).where(
                    Folder.name == part,
                    Folder.parent_id == current_parent_id,
                    Folder.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            current_parent_id = existing.id
        else:
            new_folder = Folder(
                name=part,
                parent_id=current_parent_id,
                workspace_id=workspace_id,
                created_by_id=user_id,
                position="a0",
            )
            session.add(new_folder)
            await session.flush()
            current_parent_id = new_folder.id

    return current_parent_id


async def _set_indexing_flag(session: AsyncSession, folder_id: int) -> None:
    folder = await session.get(Folder, folder_id)
    if folder:
        meta = dict(folder.folder_metadata or {})
        meta["indexing_in_progress"] = True
        folder.folder_metadata = meta
        await session.commit()


async def _clear_indexing_flag(session: AsyncSession, folder_id: int) -> None:
    try:
        folder = await session.get(Folder, folder_id)
        if folder:
            meta = dict(folder.folder_metadata or {})
            meta.pop("indexing_in_progress", None)
            folder.folder_metadata = meta
            await session.commit()
    except Exception:
        pass


async def _cleanup_empty_folder_chain(
    session: AsyncSession,
    folder_id: int,
    root_folder_id: int,
) -> None:
    """Walk up from folder_id toward root, deleting empty folders (no docs, no
    children). Stops at root_folder_id which is never deleted."""
    current_id = folder_id
    while current_id and current_id != root_folder_id:
        has_doc = (
            await session.execute(
                select(Document.id).where(Document.folder_id == current_id).limit(1)
            )
        ).scalar_one_or_none()
        if has_doc is not None:
            break

        has_child = (
            await session.execute(
                select(Folder.id).where(Folder.parent_id == current_id).limit(1)
            )
        ).scalar_one_or_none()
        if has_child is not None:
            break

        folder = (
            await session.execute(select(Folder).where(Folder.id == current_id))
        ).scalar_one_or_none()
        if not folder:
            break

        parent_id = folder.parent_id
        await session.delete(folder)
        await session.flush()
        current_id = parent_id


async def _cleanup_empty_folders(
    session: AsyncSession,
    root_folder_id: int,
    workspace_id: int,
    existing_dirs_on_disk: set[str],
    folder_mapping: dict[str, int],
    subtree_ids: list[int] | None = None,
) -> None:
    """Delete Folder rows that are empty (no docs, no children) and no longer on disk."""
    from sqlalchemy import delete as sa_delete

    id_to_rel: dict[int, str] = {fid: rel for rel, fid in folder_mapping.items() if rel}

    query = select(Folder).where(
        Folder.workspace_id == workspace_id,
        Folder.id != root_folder_id,
    )
    if subtree_ids is not None:
        query = query.where(Folder.id.in_(subtree_ids))

    all_folders = (await session.execute(query)).scalars().all()

    candidates: list[Folder] = []
    for folder in all_folders:
        rel = id_to_rel.get(folder.id)
        if rel and rel in existing_dirs_on_disk:
            continue
        candidates.append(folder)

    changed = True
    while changed:
        changed = False
        remaining: list[Folder] = []
        for folder in candidates:
            doc_exists = (
                await session.execute(
                    select(Document.id).where(Document.folder_id == folder.id).limit(1)
                )
            ).scalar_one_or_none()
            if doc_exists is not None:
                remaining.append(folder)
                continue

            child_exists = (
                await session.execute(
                    select(Folder.id).where(Folder.parent_id == folder.id).limit(1)
                )
            ).scalar_one_or_none()
            if child_exists is not None:
                remaining.append(folder)
                continue

            await session.execute(sa_delete(Folder).where(Folder.id == folder.id))
            changed = True
        candidates = remaining


async def _mirror_folder_structure_from_paths(
    session: AsyncSession,
    relative_paths: list[str],
    folder_name: str,
    workspace_id: int,
    user_id: str,
    root_folder_id: int | None = None,
) -> tuple[dict[str, int], int]:
    """Create DB Folder rows from a list of relative file paths.

    Unlike ``_mirror_folder_structure`` this does not walk the filesystem;
    it derives the directory tree from the paths provided by the client.

    Returns (mapping, root_folder_id) where mapping is
    relative_dir_path -> folder_id.  The empty-string key maps to root.
    """
    dir_set: set[str] = set()
    for rp in relative_paths:
        parent = str(Path(rp).parent)
        if parent == ".":
            continue
        parts = Path(parent).parts
        for i in range(len(parts)):
            dir_set.add(str(Path(*parts[: i + 1])))

    subdirs = sorted(dir_set, key=lambda p: p.count(os.sep))

    mapping: dict[str, int] = {}

    if root_folder_id:
        existing = (
            await session.execute(select(Folder).where(Folder.id == root_folder_id))
        ).scalar_one_or_none()
        if existing:
            mapping[""] = existing.id
        else:
            root_folder_id = None

    if not root_folder_id:
        root_folder = Folder(
            name=folder_name,
            workspace_id=workspace_id,
            created_by_id=user_id,
            position="a0",
        )
        session.add(root_folder)
        await session.flush()
        mapping[""] = root_folder.id
        root_folder_id = root_folder.id

    for rel_dir in subdirs:
        dir_parts = Path(rel_dir).parts
        dir_name = dir_parts[-1]
        parent_rel = str(Path(*dir_parts[:-1])) if len(dir_parts) > 1 else ""

        parent_id = mapping.get(parent_rel, mapping[""])

        existing_folder = (
            await session.execute(
                select(Folder).where(
                    Folder.name == dir_name,
                    Folder.parent_id == parent_id,
                    Folder.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()

        if existing_folder:
            mapping[rel_dir] = existing_folder.id
        else:
            new_folder = Folder(
                name=dir_name,
                parent_id=parent_id,
                workspace_id=workspace_id,
                created_by_id=user_id,
                position="a0",
            )
            session.add(new_folder)
            await session.flush()
            mapping[rel_dir] = new_folder.id

    await session.flush()
    return mapping, root_folder_id
