"""AC-3 live latency benchmark for Story 3.14 (memory injection bounded retrieval).

Seeds 8 dedicated-identity cells onto ONE shared, real ``memories`` table/
HNSW/GIN background (200,400 rows total by default), times each cell's real
production code path (injection middleware / REST ``/memories/search`` /
REST ``/research-threads/{id}/context``), verifies canonical top-5 IDs and
sentinels that were fixed by the generator *before* any query ran (never
inferred from search output), evaluates the story's absolute/ratio/delta
latency gates, captures a JSON EXPLAIN per large cell, and emits a full
provenance artifact. Cleans up every seeded row in a ``finally`` block
regardless of outcome.

Run (from ``nowing_backend/``):

    uv run --active python scripts/benchmark_memory_story_3_14.py \\
      --small-corpus 100 --large-corpus 50000 \\
      --warmups 20 --samples 100 --freshness-samples 30 \\
      --output ../_bmad-output/implementation-artifacts/evidence/3-14-memory-performance.json

AC-5's live freshness harness (real Celery worker + real LLM extraction) runs
after AC-3 cleanup when ``--freshness-samples`` is greater than 0 and live LLM
credentials/worker are detected. If the environment has no live credentials or
worker, the harness records ``status: partial`` with
``reason: missing_llm_credentials``.

Timer placement note: the story specifies REST/context timers as "after
RBAC/before embedding through response compose" and injection timers as
"before shielded_async_session through exit" / "after guards/before
transcript through return". Modifying the production route/middleware
source to plant timers at those exact lines is out of this story's touch
set, so this script instead re-invokes the *identical* production
primitives (``check_permission``, ``embed_texts``, ``MemoryHybridSearch.
search``, response schema construction, ``shielded_async_session``) in the
same order the real route/middleware use, with timers placed at those same
logical boundaries. This is a faithful reproduction of the production code
path, not a source-level instrumentation of it.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import html
import json
import logging
import math
import platform
import statistics
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from langchain_core.messages import HumanMessage
from sqlalchemy import TextClause, delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_memory_story_3_14_freshness import (
    run_freshness_harness as _run_freshness_harness,
)

from app.agents.chat.multi_agent_chat.main_agent.middleware.memory import (
    middleware as middleware_module,
)
from app.agents.chat.multi_agent_chat.main_agent.middleware.memory.middleware import (
    MemoryInjectionMiddleware,
)
from app.auth.context import AuthContext
from app.config import config
from app.db import (
    ChatVisibility,
    Memory,
    MemorySourceType,
    MemoryType,
    Permission,
    ResearchThread,
    User,
    Workspace,
    async_session_maker,
)
from app.routes.workspaces_routes import (
    create_default_roles_and_membership,
)
from app.schemas.memory import (
    MemorySearchHit,
    MemorySearchResponse,
    ResearchThreadContext,
)
from app.services.memory import search as search_module
from app.services.memory.search import MemoryHybridSearch, ScoredMemory
from app.services.memory.thread_citations import collect_thread_citations
from app.services.memory.vector import (
    VectorValidationError,
    validate_embedding_vector,
    validate_single_embedding_result,
)
from app.utils.document_converters import embed_texts
from app.utils.rbac import check_permission

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("benchmark_memory_story_3_14")

GENERATOR_VERSION = "3.14.1"
RNG_SEED = 31414000
N_CONTENT_BUCKETS = 100
N_QUERY_BUCKETS = 10
TARGETS_PER_QUERY = 5
TARGET_RESERVED_ROWS = N_QUERY_BUCKETS * TARGETS_PER_QUERY  # 50
RECENCY_TAIL_ROWS = 5

# Fixed cell order per the story's AC-3 table — never reordered.
CELL_KINDS = ("injection-personal", "injection-team", "rest-ranked", "thread-recency")
CELL_SIZES = ("small", "large")

# AC-3: benchmark is strictly sequential; concurrency exists only as metadata.
CONCURRENCY = 1

# D6 constant reused verbatim for EXPLAIN reconstruction fidelity.
_MAX_CANDIDATES = search_module._MAX_CANDIDATES


def _stable_seed(*parts: str) -> int:
    """Deterministic, order-independent 32-bit seed for a labelled RNG stream."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:4], "big")


def _rng_for(*parts: str) -> np.random.Generator:
    return np.random.default_rng(
        np.random.SeedSequence([RNG_SEED, _stable_seed(*parts)])
    )


def _unit_vector(rng: np.random.Generator, dim: int) -> np.ndarray:
    v = rng.normal(size=dim).astype(np.float64)
    return v / np.linalg.norm(v)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _vector_literal(vec: np.ndarray) -> str:
    return "'[" + ",".join(f"{float(x):.8f}" for x in vec) + "]'::vector"


def nearest_rank(sorted_values: list[float], p: float) -> float:
    n = len(sorted_values)
    idx = max(0, min(math.ceil(p * n) - 1, n - 1))
    return sorted_values[idx]


def stats_for(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    return {
        "n": len(ordered),
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
        "mean_ms": statistics.fmean(ordered),
        "p50_ms": nearest_rank(ordered, 0.50),
        "p95_ms": nearest_rank(ordered, 0.95),
        "p99_ms": nearest_rank(ordered, 0.99),
    }


def _build_sentinel_manifest(manifest: CellManifest) -> dict[int, str]:
    """Map every DB row id in the cell to its sentinel, if any."""
    mapping: dict[int, str] = {}
    for _q, pairs in manifest.canonical_by_query.items():
        for row_id, sentinel in pairs:
            mapping[row_id] = sentinel
    if manifest.canonical_recency:
        # Recency rows are inserted rank 5..1, so row_ids[-5:] is
        # [rank5_id, ..., rank1_id]. canonical_recency is rank 1..5,
        # so reverse the id tail to align rank1_id with the rank1 sentinel.
        for row_id, sentinel in zip(
            manifest.row_ids[-RECENCY_TAIL_ROWS:][::-1],
            manifest.canonical_recency,
            strict=True,
        ):
            mapping[row_id] = sentinel
    return mapping


async def _audit_stored_vectors(
    session: AsyncSession, row_ids: list[int], dim: int
) -> dict[str, Any]:
    """D6/B20: read every seeded embedding and classify failures by reason."""
    audit: dict[str, Any] = {"valid_count": 0, "invalid_count": 0, "by_reason": {}}
    for chunk in _chunked(row_ids, _DELETE_CHUNK_SIZE):
        result = await session.execute(
            select(Memory.id, Memory.embedding).where(Memory.id.in_(chunk))
        )
        for row_id, embedding in result:
            try:
                validate_embedding_vector(embedding, dimension=dim)
                audit["valid_count"] += 1
            except VectorValidationError as exc:
                audit["invalid_count"] += 1
                audit["by_reason"][exc.reason] = (
                    audit["by_reason"].get(exc.reason, 0) + 1
                )
                logger.warning(
                    "stored-row vector audit: id=%s reason=%s", row_id, exc.reason
                )
    return audit


# --------------------------------------------------------------------------
# Corpus generation
# --------------------------------------------------------------------------


@dataclass
class RowSpec:
    row_index: int
    bucket: int
    content: str
    embedding: np.ndarray
    is_target: bool
    query_bucket: int | None = None
    rank: int | None = None
    sentinel: str | None = None


@dataclass
class CellManifest:
    cell: str
    kind: str
    size: str
    corpus_size: int
    identity: dict[str, Any]
    row_ids: list[int] = field(default_factory=list)
    canonical_by_query: dict[int, list[tuple[int, str]]] = field(default_factory=dict)
    canonical_recency: list[str] = field(default_factory=list)
    query_text_raw: dict[int, str] = field(default_factory=dict)
    query_embedding_raw: dict[int, list[float]] = field(default_factory=dict)
    query_embedding_wrapped: dict[int, list[float]] = field(default_factory=dict)
    sentinel_manifest: dict[int, str] = field(default_factory=dict)
    vector_audit: dict[str, Any] = field(default_factory=dict)


#: Per-bucket subject phrases with mutually disjoint vocabulary. An earlier
#: version used one template varying only in the two-digit bucket number
#: ("s314probe topic number NN unrelated filler phrase alpha beta gamma");
#: the local embedding model mapped those near-identical sentences to
#: near-identical vectors (max pairwise centroid cos measured at 0.99882,
#: ABOVE the own-rank-5 target similarity 1/sqrt(1+0.05^2)=0.99875), so a
#: neighboring bucket's rank-1 target genuinely out-ranked the current
#: bucket's rank-5 target in exact vector order — the full-scale run's
#: verification failures. Distinct subjects push pairwise centroid cos far
#: below the danger zone; `assert_centroid_geometry()` enforces this
#: numerically before any row is seeded.
_QUERY_SUBJECTS = (
    "glacier penguin aurora midnight waltz",
    "cinnamon harpsichord nebula rising tide",
    "volcanic obsidian falcon desert mirage",
    "quantum ukulele sapphire monsoon drift",
    "bamboo lighthouse tundra velvet echo",
    "saffron pendulum orchid galactic reef",
    "juniper mammoth typhoon crystal prairie",
    "ivory labyrinth comet whistling fjord",
    "magnetic zeppelin cactus twilight sonata",
    "emerald accordion glacier moth citadel",
)


def query_text_for_bucket(q: int) -> str:
    # B16: query the query-bucket content keyword plus a distinct subject.
    # `s314bucket{q:02d}` matches the 1% of rows that share this content bucket;
    # target rows are seeded into that bucket and repeat the keyword, so the
    # keyword arm contributes meaningfully to RRF instead of collapsing.
    return f"s314bucket{q:02d} {_QUERY_SUBJECTS[q]}"


#: Pairwise centroid ceiling. A foreign bucket's target sits within ~0.05 of
#: its own centroid, so it can only invade bucket i's top-5 when
#: cos(c_i, c_j) approaches the own-rank-5 similarity 0.99875. Requiring
#: max pairwise cos < 0.90 leaves >0.04 of slack even after the worst-case
#: +0.05 perturbation shift.
_CENTROID_PAIRWISE_CEILING = 0.90


def assert_centroid_geometry(centroids: dict[int, np.ndarray], label: str) -> float:
    """Abort before seeding a single row if any two query centroids are close
    enough for cross-bucket target contamination (the exact failure mode of
    the first full-scale run)."""
    worst = -1.0
    worst_pair = (0, 0)
    for i in range(N_QUERY_BUCKETS):
        for j in range(i + 1, N_QUERY_BUCKETS):
            c = abs(_cosine(centroids[i], centroids[j]))
            if c > worst:
                worst, worst_pair = c, (i, j)
    if worst >= _CENTROID_PAIRWISE_CEILING:
        raise RuntimeError(
            f"{label}: query centroids {worst_pair[0]:02d}/{worst_pair[1]:02d} have "
            f"|cos|={worst:.6f} >= {_CENTROID_PAIRWISE_CEILING} — query texts are too "
            "similar for deterministic canonical top-5 geometry; make _QUERY_SUBJECTS "
            "more distinct"
        )
    return worst


def _build_content(
    run_tag: str,
    cell: str,
    row_index: int,
    bucket: int,
    sentinel: str | None,
    extra_keyword: str | None = None,
    keyword_repeats: int = 5,
) -> str:
    # B16: query bucket keyword is repeated in target rows so their keyword rank
    # dominates the 1% of rows that share the same content bucket.
    keyword_block = ""
    if extra_keyword:
        keyword_block = (extra_keyword + " ") * keyword_repeats
    base = (
        f"{keyword_block}{run_tag} s314bucket{bucket:02d} benchmark filler content "
        f"row {row_index} for cell {cell} lorem ipsum dolor sit amet consectetur "
        f"adipiscing elit."
    )
    if sentinel:
        base = f"{base} {sentinel}"
    return base


def generate_ranked_cell_rows(
    *,
    cell: str,
    run_tag: str,
    corpus_size: int,
    dim: int,
    query_embeddings: dict[int, np.ndarray],
) -> tuple[list[RowSpec], dict[int, list[tuple[int, str]]]]:
    """Deterministic corpus for a semantic-ranked cell (injection/rest-ranked).

    Reserves TARGET_RESERVED_ROWS row-slots (5 per query bucket) placed at
    strictly increasing cosine distance from that query's centroid so the
    semantic-rank order is fixed by construction; all remaining rows are
    filler, rejection-sampled to stay clearly farther from every centroid
    than the farthest reserved target. Canonical top-5 per query bucket is
    therefore known before any search ever runs.
    """
    if corpus_size < TARGET_RESERVED_ROWS:
        raise ValueError(
            f"{cell}: corpus_size {corpus_size} < reserved target rows {TARGET_RESERVED_ROWS}"
        )

    rng = _rng_for(cell, "rows")
    rows: list[RowSpec] = []
    canonical: dict[int, list[tuple[int, str]]] = {
        q: [] for q in range(N_QUERY_BUCKETS)
    }

    row_index = 0
    for q in range(N_QUERY_BUCKETS):
        centroid = query_embeddings[q]
        centroid_unit = centroid / np.linalg.norm(centroid)
        for rank in range(1, TARGETS_PER_QUERY + 1):
            direction = _unit_vector(rng, dim)
            # Orthogonalize against the centroid so the perturbation actually
            # moves the angle rather than just rescaling along it.
            direction = direction - np.dot(direction, centroid_unit) * centroid_unit
            direction_norm = np.linalg.norm(direction)
            if direction_norm < 1e-9:
                direction = _unit_vector(rng, dim)
                direction_norm = np.linalg.norm(direction)
            direction = direction / direction_norm
            epsilon = 0.01 * rank  # strictly increasing -> strictly increasing distance
            vec = centroid_unit + epsilon * direction
            # B16: target rows are placed in the query's own content bucket so the
            # keyword arm matches them, and the bucket keyword is repeated.
            bucket = q
            sentinel = f"s314:{cell}:{q:02d}:{rank}"
            extra_keyword = f"s314bucket{q:02d}"
            content = _build_content(
                run_tag, cell, row_index, bucket, sentinel, extra_keyword=extra_keyword
            )
            rows.append(
                RowSpec(
                    row_index=row_index,
                    bucket=bucket,
                    content=content,
                    embedding=vec,
                    is_target=True,
                    query_bucket=q,
                    rank=rank,
                    sentinel=sentinel,
                )
            )
            canonical[q].append((row_index, sentinel))
            row_index += 1

    centroid_units = [
        query_embeddings[q] / np.linalg.norm(query_embeddings[q])
        for q in range(N_QUERY_BUCKETS)
    ]

    # Direct canonical-property assertion over the full deterministic target
    # geometry: for every query bucket, its own 5 targets must be the strict
    # global top-5 by cosine among ALL 50 targets, in exact rank order. This
    # is exactly what _verify_hits() will later demand from live search — so
    # any violation must abort here, before a single row is seeded, rather
    # than surface as a mid-run verification failure at full scale.
    target_rows = [r for r in rows if r.is_target]
    for q in range(N_QUERY_BUCKETS):
        sims = sorted(
            ((_cosine(r.embedding, centroid_units[q]), r) for r in target_rows),
            key=lambda pair: pair[0],
            reverse=True,
        )
        top5 = [r for _, r in sims[:5]]
        expected = [(q, rank) for rank in range(1, TARGETS_PER_QUERY + 1)]
        actual = [(r.query_bucket, r.rank) for r in top5]
        if actual != expected:
            raise RuntimeError(
                f"{cell}: query {q:02d} canonical geometry violated — global "
                f"target top-5 is {actual}, expected {expected}; nearest "
                f"intruder cos={sims[0][0]:.6f}"
            )

    max_target_similarity = (
        1.0 - (0.01 * TARGETS_PER_QUERY) ** 2 / 2
    )  # loose upper bound, informational only
    filler_safety_ceiling = (
        0.5  # targets sit above ~0.9998 similarity; filler must stay well below this
    )

    while row_index < corpus_size:
        for _attempt in range(200):
            candidate = _unit_vector(rng, dim)
            if all(
                abs(_cosine(candidate, c)) < filler_safety_ceiling
                for c in centroid_units
            ):
                break
        else:
            raise RuntimeError(
                f"{cell}: could not place a safely-far filler vector after 200 attempts"
            )
        bucket = row_index % N_CONTENT_BUCKETS
        content = _build_content(run_tag, cell, row_index, bucket, sentinel=None)
        rows.append(
            RowSpec(
                row_index=row_index,
                bucket=bucket,
                content=content,
                embedding=candidate,
                is_target=False,
            )
        )
        row_index += 1

    del max_target_similarity  # documentation only, not asserted numerically here
    return rows, canonical


def generate_recency_cell_rows(
    *, cell: str, run_tag: str, corpus_size: int, dim: int
) -> tuple[list[RowSpec], list[str]]:
    """Deterministic corpus for a query-less thread-recency cell.

    Recency order is `created_at DESC, id DESC` — entirely a function of
    insertion order, not content/vector geometry. The last RECENCY_TAIL_ROWS
    rows inserted (highest ids) are tagged with sentinels in strict
    most-recent-first order; everything before them is undistinguished
    filler.
    """
    if corpus_size < RECENCY_TAIL_ROWS:
        raise ValueError(
            f"{cell}: corpus_size {corpus_size} < recency tail {RECENCY_TAIL_ROWS}"
        )

    rng = _rng_for(cell, "rows")
    rows: list[RowSpec] = []
    for row_index in range(corpus_size - RECENCY_TAIL_ROWS):
        vec = _unit_vector(rng, dim)
        bucket = row_index % N_CONTENT_BUCKETS
        content = _build_content(run_tag, cell, row_index, bucket, sentinel=None)
        rows.append(
            RowSpec(
                row_index=row_index,
                bucket=bucket,
                content=content,
                embedding=vec,
                is_target=False,
            )
        )

    sentinels: list[str] = []
    # Insert in rank 5..1 order so rank 1 (most recent) lands last (highest id).
    for rank in range(RECENCY_TAIL_ROWS, 0, -1):
        row_index = corpus_size - rank
        vec = _unit_vector(rng, dim)
        bucket = row_index % N_CONTENT_BUCKETS
        sentinel = f"s314:{cell}:recency:{rank}"
        content = _build_content(run_tag, cell, row_index, bucket, sentinel)
        rows.append(
            RowSpec(
                row_index=row_index,
                bucket=bucket,
                content=content,
                embedding=vec,
                is_target=True,
                rank=rank,
                sentinel=sentinel,
            )
        )
        sentinels.append(sentinel)
    sentinels.reverse()  # rank1..rank5 order
    return rows, sentinels


# --------------------------------------------------------------------------
# Identity + seeding
# --------------------------------------------------------------------------


async def _make_user(session: AsyncSession, tag: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{tag}@s314-bench.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        display_name=f"{tag} User",
    )
    session.add(user)
    await session.flush()
    return user


async def _make_workspace(session: AsyncSession, tag: str, owner: User) -> Workspace:
    ws = Workspace(name=f"s314-{tag}", user_id=owner.id)
    session.add(ws)
    await session.flush()
    return ws


async def setup_identities(
    session: AsyncSession, run_uuid_str: str
) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}

    for size in CELL_SIZES:
        cell = f"injection-personal-{size}"
        user = await _make_user(session, f"{run_uuid_str}-{cell}")
        identities[cell] = {"user": user}

    for size in CELL_SIZES:
        cell = f"injection-team-{size}"
        owner = await _make_user(session, f"{run_uuid_str}-{cell}-owner")
        ws = await _make_workspace(session, f"{run_uuid_str}-{cell}", owner)
        identities[cell] = {"workspace": ws, "owner": owner}

    for size in CELL_SIZES:
        cell = f"rest-ranked-{size}"
        owner = await _make_user(session, f"{run_uuid_str}-{cell}-owner")
        ws = await _make_workspace(session, f"{run_uuid_str}-{cell}", owner)
        await create_default_roles_and_membership(session, ws.id, owner.id)
        identities[cell] = {"workspace": ws, "owner": owner}

    for size in CELL_SIZES:
        cell = f"thread-recency-{size}"
        owner = await _make_user(session, f"{run_uuid_str}-{cell}-owner")
        ws = await _make_workspace(session, f"{run_uuid_str}-{cell}", owner)
        await create_default_roles_and_membership(session, ws.id, owner.id)
        thread = ResearchThread(
            workspace_id=ws.id, created_by_id=owner.id, title=f"s314-{cell}"
        )
        session.add(thread)
        await session.flush()
        identities[cell] = {"workspace": ws, "owner": owner, "thread": thread}

    await session.commit()
    return identities


async def bulk_insert_rows(
    session: AsyncSession,
    rows: list[RowSpec],
    *,
    workspace_id: int | None,
    created_by_id: uuid.UUID | None,
    research_thread_id: int | None,
    batch_size: int = 2000,
) -> list[int]:
    ids: list[int] = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        payload = [
            {
                "workspace_id": workspace_id,
                "created_by_id": created_by_id,
                "research_thread_id": research_thread_id,
                "type": MemoryType.SEMANTIC,
                "content": row.content,
                "embedding": row.embedding.astype(np.float32).tolist(),
                "source_type": MemorySourceType.MANUAL,
                "source_id": None,
                "tags": [],
                "confidence": 1.0,
            }
            for row in batch
        ]
        stmt = insert(Memory).returning(Memory.id)
        result = await session.execute(stmt, payload)
        batch_ids = [row[0] for row in result.fetchall()]
        if len(batch_ids) != len(batch):
            raise RuntimeError(
                "insertmanyvalues returned a different row count than inserted"
            )
        ids.extend(batch_ids)
    await session.commit()
    if sorted(ids) != ids:
        raise RuntimeError(
            "assigned memory ids were not strictly increasing in insertion order"
        )
    return ids


# --------------------------------------------------------------------------
# Timed cell execution
# --------------------------------------------------------------------------


@dataclass
class CellTiming:
    cell: str
    db_ms: list[float | None] = field(default_factory=list)
    total_ms: list[float] = field(default_factory=list)
    verification_failures: list[str] = field(default_factory=list)
    per_sample: list[dict[str, Any]] = field(default_factory=list)
    expected: dict[str, Any] = field(default_factory=dict)
    sentinel_manifest: dict[int, str] = field(default_factory=dict)
    vector_audit: dict[str, Any] = field(default_factory=dict)
    explain: dict[str, Any] | None = None


def _extract_expected(canonical: list[tuple[int, str]]) -> tuple[list[int], list[str]]:
    ordered = sorted(canonical, key=lambda pair: int(pair[1].rsplit(":", 1)[1]))
    return [row_id for row_id, _ in ordered], [sentinel for _, sentinel in ordered]


def _verify_hits(
    *,
    cell: str,
    label: str,
    expected_ids: list[int],
    expected_sentinels: list[str],
    actual_ids: list[int],
    actual_contents: list[str],
    failures: list[str],
) -> bool:
    if len(actual_ids) != 5:
        failures.append(f"{label}: expected exactly 5 hits, got {len(actual_ids)}")
        return False
    if len(set(actual_ids)) != 5:
        failures.append(f"{label}: duplicate IDs in result {actual_ids}")
        return False
    if actual_ids != expected_ids:
        failures.append(f"{label}: expected ID order {expected_ids}, got {actual_ids}")
        return False
    for sentinel, content in zip(expected_sentinels, actual_contents, strict=True):
        if sentinel not in content:
            failures.append(
                f"{label}: expected sentinel {sentinel!r} missing from row content"
            )
            return False
    return True


def _verify_injection_payload(
    *,
    cell: str,
    label: str,
    payload: str | None,
    expected_sentinels: list[str],
    failures: list[str],
    is_team: bool,
    display_name: str | None = None,
) -> bool:
    """B17: assert the real middleware payload is one bounded wrapper with all sentinels."""

    if payload is None:
        failures.append(f"{label}: middleware returned no injected payload")
        return False
    if len(payload) > 8_000:
        failures.append(f"{label}: injection payload {len(payload)} chars exceeds 8000")
        return False
    tag = "team_memory" if is_team else "user_memory"
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    if payload.count(open_tag) != 1 or payload.count(close_tag) != 1:
        failures.append(
            f"{label}: payload does not contain exactly one {open_tag} wrapper"
        )
        return False

    if not is_team:
        # Private cells must place the escaped first name inside <user_name>.
        if not display_name or not display_name.strip():
            failures.append(
                f"{label}: personal cell missing display_name for <user_name> verification"
            )
            return False
        name_open = payload.find("<user_name>")
        name_close = payload.find("</user_name>")
        if name_open == -1 or name_close == -1 or name_close <= name_open:
            failures.append(
                f"{label}: payload does not contain a valid <user_name> block"
            )
            return False
        first_name = html.escape(display_name.strip().split()[0], quote=True)
        name_content = payload[name_open + len("<user_name>") : name_close]
        if not name_content.startswith(first_name):
            failures.append(
                f"{label}: expected <user_name> to start with first name {first_name!r}"
            )
            return False

    for i, sentinel in enumerate(expected_sentinels):
        # Each sentinel must appear exactly once and in canonical order.
        if payload.count(sentinel) != 1:
            failures.append(
                f"{label}: expected sentinel {sentinel!r} once in payload, found {payload.count(sentinel)}"
            )
            return False
        prev = payload.find(expected_sentinels[i - 1]) if i > 0 else 0
        pos = payload.find(sentinel)
        if pos < prev:
            failures.append(
                f"{label}: sentinel {sentinel!r} is out of order in payload"
            )
            return False
    return True


async def run_injection_cell(
    manifest: CellManifest, *, warmups: int, samples: int, capture_explain: bool
) -> CellTiming:
    is_team = manifest.kind == "injection-team"
    identity = manifest.identity
    display_name = (
        identity["owner"].display_name if is_team else identity["user"].display_name
    )
    timing = CellTiming(cell=manifest.cell)
    timing.sentinel_manifest = manifest.sentinel_manifest
    timing.expected = {
        f"{q:02d}": {
            "ids": [row_id for row_id, _ in pairs],
            "sentinels": [sentinel for _, sentinel in pairs],
        }
        for q, pairs in manifest.canonical_by_query.items()
    }
    timing.vector_audit = manifest.vector_audit

    mw = MemoryInjectionMiddleware(
        user_id=None if is_team else identity["user"].id,
        workspace_id=identity["workspace"].id if is_team else 0,
        thread_visibility=ChatVisibility.SEARCH_SPACE
        if is_team
        else ChatVisibility.PRIVATE,
    )

    db_timer: dict[str, float | None] = {"start": None, "end": None}
    real_shielded = middleware_module.shielded_async_session

    @contextlib.asynccontextmanager
    async def timed_shielded_session():
        db_timer["start"] = time.perf_counter()
        try:
            async with real_shielded() as session:
                yield session
        finally:
            db_timer["end"] = time.perf_counter()

    async def run_once(
        query_bucket: int,
    ) -> tuple[float, float, list[ScoredMemory], str | None]:
        query_text = manifest.query_text_raw[query_bucket]
        state = {"messages": [HumanMessage(content=query_text)]}

        captured: list[list[ScoredMemory]] = []
        real_search = MemoryHybridSearch.search

        async def capturing_search(self, *args, **kwargs):
            hits = await real_search(self, *args, **kwargs)
            captured.append(hits)
            return hits

        middleware_module.shielded_async_session = timed_shielded_session
        MemoryHybridSearch.search = capturing_search
        try:
            total_start = time.perf_counter()
            abefore_result = await mw.abefore_agent(state, None)  # type: ignore[arg-type]
            total_end = time.perf_counter()
        finally:
            middleware_module.shielded_async_session = real_shielded
            MemoryHybridSearch.search = real_search

        hits = captured[0] if captured else []
        payload: str | None = None
        if isinstance(abefore_result, dict) and isinstance(
            abefore_result.get("messages"), list
        ):
            for msg in abefore_result["messages"]:
                if (
                    hasattr(msg, "content")
                    and isinstance(msg.content, str)
                    and "<" in msg.content
                ):
                    payload = msg.content
                    break
        db_start = db_timer["start"]
        db_end = db_timer["end"]
        db_ms = (
            (db_end - db_start) * 1000
            if db_start is not None and db_end is not None
            else None
        )
        total_ms = (total_end - total_start) * 1000
        return db_ms, total_ms, hits, payload

    for i in range(warmups):
        await run_once(i % N_QUERY_BUCKETS)

    for i in range(samples):
        q = i % N_QUERY_BUCKETS
        db_ms, total_ms, hits, payload = await run_once(q)
        timing.db_ms.append(db_ms)
        timing.total_ms.append(total_ms)
        expected_ids, expected_sentinels = _extract_expected(
            manifest.canonical_by_query[q]
        )
        actual_ids = [h.memory.id for h in hits]
        _verify_hits(
            cell=manifest.cell,
            label=f"sample {i} (query {q:02d})",
            expected_ids=expected_ids,
            expected_sentinels=expected_sentinels,
            actual_ids=actual_ids,
            actual_contents=[h.memory.content for h in hits],
            failures=timing.verification_failures,
        )
        _verify_injection_payload(
            cell=manifest.cell,
            label=f"sample {i} (query {q:02d})",
            payload=payload,
            expected_sentinels=expected_sentinels,
            failures=timing.verification_failures,
            is_team=is_team,
            display_name=display_name,
        )
        timing.per_sample.append(
            {
                "query_bucket": q,
                "expected_ids": expected_ids,
                "expected_sentinels": expected_sentinels,
                "actual_ids": actual_ids,
                "actual_sentinels": [
                    manifest.sentinel_manifest.get(i) for i in actual_ids
                ],
                "actual_scores": [h.score for h in hits],
                "actual_similarities": [h.similarity for h in hits],
                "payload_length": len(payload) if payload else None,
                "db_ms": db_ms,
                "total_ms": total_ms,
            }
        )

    if capture_explain:
        timing.explain = await explain_ranked_query(
            cell=manifest.cell,
            scope_sql=_scope_sql_for_injection(manifest),
            query_embedding=manifest.query_embedding_wrapped[0],
            query_text=manifest.query_text_raw[0],
        )
    return timing


def _scope_sql_for_injection(manifest: CellManifest) -> TextClause:
    if manifest.kind in ("injection-team", "rest-ranked"):
        ws_id = manifest.identity["workspace"].id
        return text("workspace_id = :workspace_id").bindparams(workspace_id=int(ws_id))
    user_id = manifest.identity["user"].id
    return text("workspace_id IS NULL AND created_by_id = :user_id").bindparams(
        user_id=user_id
    )


async def run_rest_ranked_cell(
    manifest: CellManifest, *, warmups: int, samples: int, capture_explain: bool
) -> CellTiming:
    timing = CellTiming(cell=manifest.cell)
    timing.sentinel_manifest = manifest.sentinel_manifest
    timing.expected = {
        f"{q:02d}": {
            "ids": [row_id for row_id, _ in pairs],
            "sentinels": [sentinel for _, sentinel in pairs],
        }
        for q, pairs in manifest.canonical_by_query.items()
    }
    timing.vector_audit = manifest.vector_audit
    identity = manifest.identity
    owner = identity["owner"]
    ws_id = identity["workspace"].id
    auth = AuthContext.session(owner)

    async def run_once(query_bucket: int) -> tuple[float, MemorySearchResponse]:
        query_text = manifest.query_text_raw[query_bucket]
        async with async_session_maker() as session:
            await check_permission(
                session,
                auth,
                ws_id,
                Permission.MEMORY_READ.value,
                error_message="benchmark: missing memory:read",
            )
            start = time.perf_counter()
            embeddings = await asyncio.to_thread(embed_texts, [query_text])
            query_embedding = validate_single_embedding_result(embeddings)
            search = MemoryHybridSearch(session)
            hits = await search.search(
                workspace_id=ws_id,
                query=query_text,
                query_embedding=query_embedding,
                top_k=5,
            )
            response = MemorySearchResponse(
                items=[
                    MemorySearchHit(
                        id=h.memory.id,
                        content=h.memory.content,
                        type=h.memory.type.value,
                        tags=h.memory.tags or [],
                        confidence=h.memory.confidence,
                        source_type=h.memory.source_type.value,
                        source_id=h.memory.source_id,
                        score=h.score,
                        similarity=h.similarity,
                    )
                    for h in hits
                ]
            )
            end = time.perf_counter()
        return (end - start) * 1000, response

    for i in range(warmups):
        await run_once(i % N_QUERY_BUCKETS)

    for i in range(samples):
        q = i % N_QUERY_BUCKETS
        total_ms, response = await run_once(q)
        timing.total_ms.append(total_ms)
        expected_ids, expected_sentinels = _extract_expected(
            manifest.canonical_by_query[q]
        )
        actual_ids = [item.id for item in response.items]
        _verify_hits(
            cell=manifest.cell,
            label=f"sample {i} (query {q:02d})",
            expected_ids=expected_ids,
            expected_sentinels=expected_sentinels,
            actual_ids=actual_ids,
            actual_contents=[item.content for item in response.items],
            failures=timing.verification_failures,
        )
        timing.per_sample.append(
            {
                "query_bucket": q,
                "expected_ids": expected_ids,
                "expected_sentinels": expected_sentinels,
                "actual_ids": actual_ids,
                "actual_sentinels": [
                    manifest.sentinel_manifest.get(i) for i in actual_ids
                ],
                "actual_scores": [item.score for item in response.items],
                "actual_similarities": [item.similarity for item in response.items],
                "db_ms": None,
                "total_ms": total_ms,
            }
        )

    if capture_explain:
        timing.explain = await explain_ranked_query(
            cell=manifest.cell,
            scope_sql=_scope_sql_for_injection(manifest),
            query_embedding=manifest.query_embedding_raw[0],
            query_text=manifest.query_text_raw[0],
        )
    return timing


async def run_thread_recency_cell(
    manifest: CellManifest, *, warmups: int, samples: int, capture_explain: bool
) -> CellTiming:
    timing = CellTiming(cell=manifest.cell)
    timing.sentinel_manifest = manifest.sentinel_manifest
    timing.vector_audit = manifest.vector_audit
    identity = manifest.identity
    owner = identity["owner"]
    ws_id = identity["workspace"].id
    thread = identity["thread"]
    auth = AuthContext.session(owner)

    # Canonical recency IDs are simply the last RECENCY_TAIL_ROWS assigned ids,
    # in reverse insertion order (rank1 = most recent = last inserted).
    expected_ids = list(reversed(manifest.row_ids[-RECENCY_TAIL_ROWS:]))
    expected_sentinels = manifest.canonical_recency
    timing.expected = {
        "recency": {"ids": expected_ids, "sentinels": expected_sentinels}
    }

    async def run_once() -> tuple[float, ResearchThreadContext]:
        async with async_session_maker() as session:
            await check_permission(
                session,
                auth,
                ws_id,
                Permission.MEMORY_READ.value,
                error_message="benchmark: missing memory:read",
            )
            start = time.perf_counter()
            search = MemoryHybridSearch(session)
            hits = await search.search(
                workspace_id=ws_id,
                query="",
                query_embedding=None,
                top_k=5,
                research_thread_id=thread.id,
            )
            citations = await collect_thread_citations(session, thread)
            response = ResearchThreadContext(
                thread_id=thread.id,
                title=thread.title,
                memories=[
                    MemorySearchHit(
                        id=h.memory.id,
                        content=h.memory.content,
                        type=h.memory.type.value,
                        tags=h.memory.tags or [],
                        confidence=h.memory.confidence,
                        source_type=h.memory.source_type.value,
                        source_id=h.memory.source_id,
                        score=h.score,
                        similarity=h.similarity,
                    )
                    for h in hits
                ],
                citations=citations,
            )
            end = time.perf_counter()
        return (end - start) * 1000, response

    for _ in range(warmups):
        await run_once()

    for i in range(samples):
        total_ms, response = await run_once()
        timing.total_ms.append(total_ms)
        actual_ids = [item.id for item in response.memories]
        _verify_hits(
            cell=manifest.cell,
            label=f"sample {i}",
            expected_ids=expected_ids,
            expected_sentinels=expected_sentinels,
            actual_ids=actual_ids,
            actual_contents=[item.content for item in response.memories],
            failures=timing.verification_failures,
        )
        timing.per_sample.append(
            {
                "query_bucket": None,
                "expected_ids": expected_ids,
                "expected_sentinels": expected_sentinels,
                "actual_ids": actual_ids,
                "actual_sentinels": [
                    manifest.sentinel_manifest.get(i) for i in actual_ids
                ],
                "actual_scores": [item.score for item in response.memories],
                "actual_similarities": [item.similarity for item in response.memories],
                "db_ms": None,
                "total_ms": total_ms,
            }
        )

    if capture_explain:
        timing.explain = await explain_recency_query(
            cell=manifest.cell, ws_id=ws_id, thread_id=thread.id
        )
    return timing


# --------------------------------------------------------------------------
# EXPLAIN capture
# --------------------------------------------------------------------------


def _semantic_cte_sql(
    *, scope_sql: TextClause, query_embedding: list[float]
) -> TextClause:
    vec_literal = _vector_literal(np.asarray(query_embedding, dtype=np.float64))
    limit = _MAX_CANDIDATES
    params = {**scope_sql.compile().params, "limit": limit}
    return text(
        f"SELECT id, row_number() OVER (ORDER BY embedding <=> {vec_literal} ASC, id ASC) AS rank "
        f"FROM memories WHERE {scope_sql.text} "
        f"ORDER BY embedding <=> {vec_literal} ASC, id ASC LIMIT :limit"
    ).bindparams(**params)


def _keyword_cte_sql(*, scope_sql: TextClause, query_text: str) -> TextClause:
    limit = _MAX_CANDIDATES
    params = {**scope_sql.compile().params, "qtext": query_text, "limit": limit}
    return text(
        "SELECT id, row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', content), "
        "plainto_tsquery('english', :qtext)) DESC, id ASC) AS rank "
        f"FROM memories WHERE {scope_sql.text} AND to_tsvector('english', content) @@ plainto_tsquery('english', :qtext) "
        "ORDER BY ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', :qtext)) "
        "DESC, id ASC LIMIT :limit"
    ).bindparams(**params)


def _ranked_query_sql(
    *, scope_sql: TextClause, query_embedding: list[float], query_text: str
) -> TextClause:
    vec_literal = _vector_literal(np.asarray(query_embedding, dtype=np.float64))
    limit = _MAX_CANDIDATES
    params = {**scope_sql.compile().params, "qtext": query_text, "limit": limit}
    return text(
        f"""
WITH semantic_memory AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> {vec_literal} ASC, id ASC) AS rank
    FROM memories
    WHERE {scope_sql.text}
    ORDER BY embedding <=> {vec_literal} ASC, id ASC
    LIMIT :limit
),
keyword_memory AS (
    SELECT id, row_number() OVER (
        ORDER BY ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', :qtext)) DESC, id ASC
    ) AS rank
    FROM memories
    WHERE {scope_sql.text} AND to_tsvector('english', content) @@ plainto_tsquery('english', :qtext)
    ORDER BY ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', :qtext)) DESC, id ASC
    LIMIT :limit
)
SELECT m.id,
    COALESCE(1.0 / (60 + semantic_memory.rank), 0.0) + COALESCE(1.0 / (60 + keyword_memory.rank), 0.0) AS score,
    1.0 - (m.embedding <=> {vec_literal}) AS similarity
FROM semantic_memory
FULL OUTER JOIN keyword_memory ON semantic_memory.id = keyword_memory.id
JOIN memories m ON m.id = COALESCE(semantic_memory.id, keyword_memory.id)
ORDER BY score DESC, similarity DESC, m.created_at DESC, m.id ASC
LIMIT :limit
""".strip()
    ).bindparams(**params)


def _recency_query_sql(*, ws_id: int, thread_id: int) -> TextClause:
    return text(
        "SELECT id FROM memories WHERE workspace_id = :ws_id AND research_thread_id = :thread_id "
        "ORDER BY created_at DESC, id DESC LIMIT :limit"
    ).bindparams(ws_id=ws_id, thread_id=thread_id, limit=5)


def _plan_has_memories_seqscan(node: Any) -> bool:
    if isinstance(node, dict):
        if (
            node.get("Node Type") == "Seq Scan"
            and node.get("Relation Name") == "memories"
        ):
            return True
        return any(_plan_has_memories_seqscan(v) for v in node.values())
    if isinstance(node, list):
        return any(_plan_has_memories_seqscan(v) for v in node)
    return False


async def _capture_explain(sql: TextClause) -> dict[str, Any]:
    compiled = sql.compile()
    async with async_session_maker() as session:
        result = await session.execute(
            text(f"EXPLAIN (FORMAT JSON) {compiled.string}").bindparams(
                **compiled.params
            )
        )
        plan = result.scalar_one()
    return {
        "plan": plan,
        "no_seq_scan_on_memories": not _plan_has_memories_seqscan(plan),
        "sql": compiled.string,
    }


async def explain_ranked_query(
    *, cell: str, scope_sql: TextClause, query_embedding: list[float], query_text: str
) -> dict[str, Any]:
    """Capture EXPLAIN for the semantic CTE, keyword CTE, and final fused query
    separately, per AC-3's "large-cell JSON EXPLAIN ... semantic+keyword+final"
    requirement — a single combined-query plan alone is insufficient evidence
    that neither underlying index path degrades to a sequential scan.
    """
    semantic_sql = _semantic_cte_sql(
        scope_sql=scope_sql, query_embedding=query_embedding
    )
    keyword_sql = _keyword_cte_sql(scope_sql=scope_sql, query_text=query_text)
    final_sql = _ranked_query_sql(
        scope_sql=scope_sql, query_embedding=query_embedding, query_text=query_text
    )
    semantic = await _capture_explain(semantic_sql)
    keyword = await _capture_explain(keyword_sql)
    final = await _capture_explain(final_sql)
    return {
        "cell": cell,
        "kind": "ranked",
        "semantic": semantic,
        "keyword": keyword,
        "final": final,
        "no_seq_scan_on_memories": (
            semantic["no_seq_scan_on_memories"]
            and keyword["no_seq_scan_on_memories"]
            and final["no_seq_scan_on_memories"]
        ),
    }


async def explain_recency_query(
    *, cell: str, ws_id: int, thread_id: int
) -> dict[str, Any]:
    sql = _recency_query_sql(ws_id=ws_id, thread_id=thread_id)
    result = await _capture_explain(sql)
    result["cell"] = cell
    result["kind"] = "recency"
    return result


# --------------------------------------------------------------------------
# Counting / cleanup
# --------------------------------------------------------------------------


async def global_memory_count(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(Memory))
    ).scalar_one()


async def run_tag_count(session: AsyncSession, run_tag: str) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Memory)
            .where(Memory.content.like(f"%{run_tag}%"))
        )
    ).scalar_one()


async def scoped_count(session: AsyncSession, manifest: CellManifest) -> int:
    identity = manifest.identity
    stmt = select(func.count()).select_from(Memory)
    if manifest.kind == "injection-personal":
        stmt = stmt.where(
            Memory.workspace_id.is_(None), Memory.created_by_id == identity["user"].id
        )
    elif manifest.kind == "thread-recency":
        stmt = stmt.where(
            Memory.workspace_id == identity["workspace"].id,
            Memory.research_thread_id == identity["thread"].id,
        )
    else:
        stmt = stmt.where(Memory.workspace_id == identity["workspace"].id)
    return (await session.execute(stmt)).scalar_one()


#: asyncpg rejects a single query with more than 32767 bind parameters — a
#: 50k-row large cell's id list must be deleted in chunks well under that
#: ceiling, not as one giant IN(...) clause.
_DELETE_CHUNK_SIZE = 5000


def _chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def cleanup_all(
    session: AsyncSession,
    manifests: list[CellManifest],
    identities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    audit: dict[str, Any] = {"per_cell_zero": {}, "errors": []}
    for manifest in manifests:
        for chunk in _chunked(manifest.row_ids, _DELETE_CHUNK_SIZE):
            await session.execute(delete(Memory).where(Memory.id.in_(chunk)))
    await session.commit()

    for manifest in manifests:
        count = await scoped_count(session, manifest)
        audit["per_cell_zero"][manifest.cell] = count
        if count != 0:
            audit["errors"].append(
                f"{manifest.cell}: scoped count after delete = {count}, expected 0"
            )

    for identity in identities.values():
        thread = identity.get("thread")
        if thread is not None:
            await session.execute(
                delete(ResearchThread).where(ResearchThread.id == thread.id)
            )
    await session.commit()

    workspace_ids = [
        identity["workspace"].id
        for identity in identities.values()
        if "workspace" in identity
    ]
    if workspace_ids:
        await session.execute(delete(Workspace).where(Workspace.id.in_(workspace_ids)))
    await session.commit()

    user_ids: set[uuid.UUID] = set()
    for identity in identities.values():
        if "user" in identity:
            user_ids.add(identity["user"].id)
        if "owner" in identity:
            user_ids.add(identity["owner"].id)
    if user_ids:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
    await session.commit()

    return audit


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


async def prepare_cell(
    *,
    kind: str,
    size: str,
    corpus_size: int,
    run_tag: str,
    identities: dict[str, dict[str, Any]],
    query_embeddings_raw: dict[int, np.ndarray],
    query_embeddings_wrapped: dict[int, np.ndarray],
    dim: int,
    session: AsyncSession,
) -> CellManifest:
    cell = f"{kind}-{size}"
    identity = identities[cell]
    manifest = CellManifest(
        cell=cell, kind=kind, size=size, corpus_size=corpus_size, identity=identity
    )
    for q in range(N_QUERY_BUCKETS):
        manifest.query_text_raw[q] = query_text_for_bucket(q)
        manifest.query_embedding_raw[q] = query_embeddings_raw[q].tolist()
        manifest.query_embedding_wrapped[q] = query_embeddings_wrapped[q].tolist()

    if kind == "thread-recency":
        rows, sentinels = generate_recency_cell_rows(
            cell=cell, run_tag=run_tag, corpus_size=corpus_size, dim=dim
        )
        manifest.canonical_recency = sentinels
    else:
        centroids = (
            query_embeddings_wrapped if kind != "rest-ranked" else query_embeddings_raw
        )
        rows, canonical = generate_ranked_cell_rows(
            cell=cell,
            run_tag=run_tag,
            corpus_size=corpus_size,
            dim=dim,
            query_embeddings=centroids,
        )
        manifest.canonical_by_query = canonical

    if kind == "injection-personal":
        ids = await bulk_insert_rows(
            session,
            rows,
            workspace_id=None,
            created_by_id=identity["user"].id,
            research_thread_id=None,
        )
    elif kind == "injection-team" or kind == "rest-ranked":
        ids = await bulk_insert_rows(
            session,
            rows,
            workspace_id=identity["workspace"].id,
            created_by_id=identity["owner"].id,
            research_thread_id=None,
        )
    else:  # thread-recency
        ids = await bulk_insert_rows(
            session,
            rows,
            workspace_id=identity["workspace"].id,
            created_by_id=identity["owner"].id,
            research_thread_id=identity["thread"].id,
        )
    manifest.row_ids = ids

    if kind == "thread-recency":
        # remap sentinel->id now that real ids are known (recency canonical
        # already stores sentinels only; verification joins them against the
        # tail of manifest.row_ids directly).
        pass
    else:
        # remap row_index -> real DB id in the canonical map.
        remapped: dict[int, list[tuple[int, str]]] = {}
        for q, pairs in manifest.canonical_by_query.items():
            remapped[q] = [(ids[row_index], sentinel) for row_index, sentinel in pairs]
        manifest.canonical_by_query = remapped

    manifest.sentinel_manifest = _build_sentinel_manifest(manifest)
    manifest.vector_audit = await _audit_stored_vectors(session, manifest.row_ids, dim)

    return manifest


def evaluate_gates(cell_timings: dict[str, CellTiming]) -> dict[str, Any]:
    gates: dict[str, Any] = {"absolute": {}, "ratio": {}, "delta": {}, "failures": []}

    def db_p95(cell: str) -> float:
        samples = [x for x in cell_timings[cell].db_ms if x is not None]
        if not samples:
            return 0.0
        return stats_for(samples)["p95_ms"]

    def total_p95(cell: str) -> float:
        return stats_for(cell_timings[cell].total_ms)["p95_ms"]

    for cell in (
        "injection-personal-small",
        "injection-personal-large",
        "injection-team-small",
        "injection-team-large",
    ):
        p95 = db_p95(cell)
        gates["absolute"][f"{cell}:db_p95_ms"] = p95
        if p95 > 150:
            gates["failures"].append(f"{cell}: injection DB p95 {p95:.2f}ms > 150ms")

    for cell in (
        "rest-ranked-small",
        "rest-ranked-large",
        "thread-recency-small",
        "thread-recency-large",
    ):
        p95 = total_p95(cell)
        gates["absolute"][f"{cell}:total_p95_ms"] = p95
        if p95 > 300:
            gates["failures"].append(f"{cell}: total p95 {p95:.2f}ms > 300ms")

    pairs = [
        ("injection-personal", "db", db_p95),
        ("injection-team", "db", db_p95),
        ("rest-ranked", "total", total_p95),
        ("thread-recency", "total", total_p95),
    ]
    for kind, source, metric in pairs:
        small = metric(f"{kind}-small")
        large = metric(f"{kind}-large")
        ratio = large / max(small, 1.0)
        delta = large - small
        gates["ratio"][kind] = {
            "small_ms": small,
            "large_ms": large,
            "ratio": ratio,
            "source": source,
        }
        gates["delta"][kind] = {"delta_ms": delta, "source": source}
        if ratio > 3.0:
            gates["failures"].append(
                f"{kind}: {source} p95 growth ratio {ratio:.3f} > 3.0"
            )
        delta_limit = 100.0 if source == "db" else 150.0
        if delta > delta_limit:
            gates["failures"].append(
                f"{kind}: {source} p95 delta {delta:.2f}ms > {delta_limit}ms"
            )

    for timing in cell_timings.values():
        if timing.verification_failures:
            gates["failures"].append(
                f"{timing.cell}: {len(timing.verification_failures)} verification failure(s), "
                f"first: {timing.verification_failures[0]}"
            )

    for timing in cell_timings.values():
        if timing.explain is not None and not timing.explain["no_seq_scan_on_memories"]:
            gates["failures"].append(
                f"{timing.cell}: EXPLAIN plan contains a Seq Scan on memories"
            )

    for timing in cell_timings.values():
        invalid = timing.vector_audit.get("invalid_count", 0)
        if invalid:
            gates["failures"].append(
                f"{timing.cell}: stored-row vector audit found {invalid} invalid row(s) "
                f"by reason {timing.vector_audit.get('by_reason', {})}"
            )

    return gates


def _alembic_head_from_filesystem(script_path: Path) -> str | None:
    """Return the highest numeric revision prefix in the alembic versions dir."""
    versions_dir = script_path.parent.parent / "alembic" / "versions"
    numeric = []
    for path in versions_dir.glob("*.py"):
        stem = path.stem
        if stem[0].isdigit():
            try:
                numeric.append((int(stem.split("_", 1)[0]), stem))
            except ValueError:
                continue
    if not numeric:
        return None
    return max(numeric, key=lambda pair: pair[0])[1]


async def _collect_environment_metadata(
    session: AsyncSession,
    manifests: list[CellManifest],
    *,
    script_path: Path,
    warmups: int,
    freshness_samples: int,
) -> dict[str, Any]:
    """B19: capture the DB, runtime and generator metadata required by AC-3."""

    pg_version = (await session.execute(text("SELECT version()"))).scalar_one()
    pgvector_version = (
        await session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        )
    ).scalar_one_or_none()
    current_revisions = (
        (await session.execute(text("SELECT version_num FROM alembic_version")))
        .scalars()
        .all()
    )

    index_rows = await session.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename='memories' AND schemaname='public'"
        )
    )
    index_inventory = [{"name": name, "defn": defn} for name, defn in index_rows]

    uv_lock_path = script_path.parent.parent / "uv.lock"
    uv_lock_hash = (
        hashlib.sha256(uv_lock_path.read_bytes()).hexdigest()
        if uv_lock_path.is_file()
        else None
    )
    script_hash = hashlib.sha256(script_path.read_bytes()).hexdigest()

    cell_identities: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        ids: dict[str, Any] = {}
        if "user" in manifest.identity:
            ids["user_id"] = str(manifest.identity["user"].id)
        if "owner" in manifest.identity:
            ids["owner_id"] = str(manifest.identity["owner"].id)
        if "workspace" in manifest.identity:
            ids["workspace_id"] = manifest.identity["workspace"].id
        if "thread" in manifest.identity:
            ids["thread_id"] = manifest.identity["thread"].id
        cell_identities[manifest.cell] = ids

    return {
        "postgresql_version": pg_version,
        "pgvector_version": pgvector_version,
        "migration_current_revisions": list(current_revisions),
        "migration_head_revision": _alembic_head_from_filesystem(script_path),
        "memories_index_inventory": index_inventory,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "generator_script_path": str(script_path),
        "generator_script_hash": script_hash,
        "uv_lock_hash": uv_lock_hash,
        "argv": sys.argv,
        "cache_warmups": warmups,
        "concurrency": CONCURRENCY,
        "requested_freshness_samples": freshness_samples,
        "cell_identities": cell_identities,
    }


async def main_async(args: argparse.Namespace) -> int:
    dim = config.embedding_model_instance.dimension
    run_id = str(uuid.uuid4())
    run_tag = f"s314run:{run_id}"
    script_path = Path(__file__).resolve()

    small = args.small_corpus
    large = args.large_corpus

    async with async_session_maker() as session:
        g0 = await global_memory_count(session)

    identities: dict[str, dict[str, Any]] = {}
    manifests: list[CellManifest] = []
    provenance: dict[str, Any] = {
        "generator_version": GENERATOR_VERSION,
        "rng_seed": RNG_SEED,
        "run_id": run_id,
        "run_tag": run_tag,
        "embedding_dimension": dim,
        "small_corpus": small,
        "large_corpus": large,
        "warmups": args.warmups,
        "samples": args.samples,
        "cell_order": [f"{k}-{s}" for k in CELL_KINDS for s in CELL_SIZES],
        "g0": g0,
    }

    try:
        async with async_session_maker() as session:
            identities = await setup_identities(session, run_id)

        query_texts = [query_text_for_bucket(q) for q in range(N_QUERY_BUCKETS)]
        wrapped_texts = [f"human: {t}" for t in query_texts]
        raw_embeddings_list = await asyncio.to_thread(embed_texts, query_texts)
        wrapped_embeddings_list = await asyncio.to_thread(embed_texts, wrapped_texts)
        query_embeddings_raw = {
            q: np.asarray(v, dtype=np.float64)
            for q, v in enumerate(raw_embeddings_list)
        }
        query_embeddings_wrapped = {
            q: np.asarray(v, dtype=np.float64)
            for q, v in enumerate(wrapped_embeddings_list)
        }

        worst_raw = assert_centroid_geometry(query_embeddings_raw, "raw centroids")
        worst_wrapped = assert_centroid_geometry(
            query_embeddings_wrapped, "wrapped centroids"
        )

        provenance["queries"] = {
            f"{q:02d}": {"text": query_texts[q]} for q in range(N_QUERY_BUCKETS)
        }
        provenance["centroid_geometry"] = {
            "pairwise_cos_ceiling": _CENTROID_PAIRWISE_CEILING,
            "max_pairwise_cos_raw": worst_raw,
            "max_pairwise_cos_wrapped": worst_wrapped,
        }

        async with async_session_maker() as session:
            for kind in CELL_KINDS:
                for size in CELL_SIZES:
                    corpus_size = small if size == "small" else large
                    manifest = await prepare_cell(
                        kind=kind,
                        size=size,
                        corpus_size=corpus_size,
                        run_tag=run_tag,
                        identities=identities,
                        query_embeddings_raw=query_embeddings_raw,
                        query_embeddings_wrapped=query_embeddings_wrapped,
                        dim=dim,
                        session=session,
                    )
                    manifests.append(manifest)

        expected_total = 4 * small + 4 * large
        actual_total = sum(len(m.row_ids) for m in manifests)
        if actual_total != expected_total:
            raise RuntimeError(
                f"seeded row total {actual_total} != expected {expected_total}"
            )

        async with async_session_maker() as session:
            tag_count = await run_tag_count(session, run_tag)
            if tag_count != expected_total:
                raise RuntimeError(
                    f"run-tag row count {tag_count} != expected {expected_total}"
                )
            g_after_seed = await global_memory_count(session)
            if g_after_seed != g0 + expected_total:
                raise RuntimeError(
                    f"global count drift: {g0} + {expected_total} != {g_after_seed}"
                )
            for manifest in manifests:
                count = await scoped_count(session, manifest)
                if count != manifest.corpus_size:
                    raise RuntimeError(
                        f"{manifest.cell}: scoped count {count} != expected {manifest.corpus_size}"
                    )
            # B18: ANALYZE is transactional; the session must commit before close
            # or the statistics are rolled back with the transaction.
            await session.execute(text("ANALYZE memories"))
            await session.commit()

        provenance["g_after_seed"] = g_after_seed
        provenance["run_tag_count"] = tag_count
        provenance["scoped_counts"] = {m.cell: m.corpus_size for m in manifests}

        cell_timings: dict[str, CellTiming] = {}
        for manifest in manifests:
            is_large = manifest.size == "large"
            if manifest.kind in ("injection-personal", "injection-team"):
                timing = await run_injection_cell(
                    manifest,
                    warmups=args.warmups,
                    samples=args.samples,
                    capture_explain=is_large,
                )
            elif manifest.kind == "rest-ranked":
                timing = await run_rest_ranked_cell(
                    manifest,
                    warmups=args.warmups,
                    samples=args.samples,
                    capture_explain=is_large,
                )
            else:
                timing = await run_thread_recency_cell(
                    manifest,
                    warmups=args.warmups,
                    samples=args.samples,
                    capture_explain=is_large,
                )
            cell_timings[manifest.cell] = timing
            async with async_session_maker() as session:
                count = await scoped_count(session, manifest)
                if count != manifest.corpus_size:
                    raise RuntimeError(
                        f"{manifest.cell}: scoped count drifted mid-run to {count}, expected {manifest.corpus_size}"
                    )

        async with async_session_maker() as session:
            g_after_run = await global_memory_count(session)
            if g_after_run != g_after_seed:
                raise RuntimeError(
                    f"global count drift after timed run: {g_after_seed} != {g_after_run}"
                )

        async with async_session_maker() as session:
            environment = await _collect_environment_metadata(
                session,
                manifests,
                script_path=script_path,
                warmups=args.warmups,
                freshness_samples=args.freshness_samples,
            )
        provenance["environment"] = environment

        gates = evaluate_gates(cell_timings)

        # B20: per-sample expected/actual evidence plus sentinel/vector audit.
        provenance["samples_stats"] = {
            cell: {
                "db_ms": [x for x in t.db_ms if x is not None] or None,
                "total_ms": t.total_ms,
                "db_stats": (
                    stats_for([x for x in t.db_ms if x is not None])
                    if any(x is not None for x in t.db_ms)
                    else None
                ),
                "total_stats": stats_for(t.total_ms),
                "verification_failures": t.verification_failures,
                "expected": t.expected,
                "sentinel_manifest": t.sentinel_manifest,
                "per_sample": t.per_sample,
                "vector_audit": t.vector_audit,
            }
            for cell, t in cell_timings.items()
        }
        provenance["vector_audit_summary"] = {
            cell: t.vector_audit for cell, t in cell_timings.items()
        }
        provenance["explain"] = {
            cell: t.explain for cell, t in cell_timings.items() if t.explain is not None
        }
        provenance["gates"] = gates

        # AC-5 freshness results are finalized in the finally block after latency cleanup.

    except Exception as exc:
        provenance["error"] = str(exc)
        provenance["traceback"] = traceback.format_exc()
        logger.exception("AC-3 benchmark failed: %s", exc)

    finally:
        cleanup_audit: dict[str, Any] = {}
        g_final = g0
        tag_final = 0
        try:
            async with async_session_maker() as session:
                cleanup_audit = await cleanup_all(session, manifests, identities)
                g_final = await global_memory_count(session)
                tag_final = await run_tag_count(session, run_tag)
        except Exception as exc:
            cleanup_audit["success"] = False
            cleanup_audit["errors"] = [str(exc), traceback.format_exc()]
            logger.exception("AC-3 cleanup failed: %s", exc)
        cleanup_audit["global_restored_to_g0"] = g_final == g0
        cleanup_audit["g0"] = g0
        cleanup_audit["g_final"] = g_final
        cleanup_audit["run_tag_count_final"] = tag_final
        provenance["cleanup"] = cleanup_audit
        if g_final != g0 or tag_final != 0:
            logger.error(
                "CLEANUP DID NOT REACH ZERO: g0=%s g_final=%s run_tag_final=%s",
                g0,
                g_final,
                tag_final,
            )

        # AC-5: live freshness harness runs only after AC-3 latency cleanup succeeds
        # and no earlier benchmark error was recorded.
        cleanup_ok = g_final == g0 and tag_final == 0 and "error" not in provenance
        freshness_partial = False
        if args.freshness_samples > 0:
            if cleanup_ok:
                try:
                    freshness, freshness_partial = await _run_freshness_harness(
                        n=args.freshness_samples,
                        run_tag=run_tag,
                    )
                except Exception as exc:
                    freshness = {
                        "status": "partial",
                        "pass": False,
                        "reason": "harness_error",
                        "detail": f"Freshness harness raised: {exc}",
                        "requested_freshness_samples": args.freshness_samples,
                    }
                    freshness_partial = True
            else:
                freshness = {
                    "status": "partial",
                    "pass": False,
                    "reason": "ac3_not_clean",
                    "detail": (
                        "AC-5 skipped because AC-3 cleanup did not reach zero "
                        "or an earlier benchmark error was recorded."
                    ),
                    "requested_freshness_samples": args.freshness_samples,
                }
                freshness_partial = True
        else:
            freshness = {
                "status": "skipped",
                "pass": True,
                "reason": "disabled_by_user",
                "detail": "--freshness-samples is 0; AC-5 phase explicitly disabled.",
                "requested_freshness_samples": 0,
            }
            freshness_partial = False
        provenance["freshness"] = freshness
        gates = provenance.get("gates", {})
        provenance["pass"] = (
            "error" not in provenance
            and len(gates.get("failures", [])) == 0
            and not freshness_partial
        )
        provenance["status"] = (
            "error"
            if "error" in provenance
            else ("partial" if freshness_partial else "complete")
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Post-freshness DB count assertion: the whole benchmark must leave the
    # database exactly where it started.
    g_after_freshness = g_final
    tag_after_freshness = tag_final
    try:
        async with async_session_maker() as session:
            g_after_freshness = await global_memory_count(session)
            tag_after_freshness = await run_tag_count(session, run_tag)
    except Exception as exc:
        logger.exception("Post-freshness count failed: %s", exc)
        provenance.setdefault("post_freshness_error", str(exc))
    if "cleanup" in provenance:
        provenance["cleanup"]["g_after_freshness"] = g_after_freshness
        provenance["cleanup"]["tag_after_freshness"] = tag_after_freshness
        provenance["cleanup"]["global_restored_to_g0_after_freshness"] = (
            g_after_freshness == g0
        )

    output_path.write_text(json.dumps(provenance, indent=2, default=str))

    ok = (
        provenance.get("pass", False)
        and cleanup_audit.get("global_restored_to_g0", False)
        and cleanup_audit.get("run_tag_count_final") == 0
        and g_after_freshness == g0
    )
    print(f"Artifact written to {output_path}")
    print(f"PASS={ok}")
    if not ok:
        for failure in provenance.get("gates", {}).get("failures", []):
            print(f"  GATE FAIL: {failure}")
        for error in cleanup_audit.get("errors", []):
            print(f"  CLEANUP FAIL: {error}")
    return 0 if ok else 1


def _positive_int(value: str) -> int:
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from exc
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"{value!r} is not a positive integer")
    return ivalue


def _non_negative_int(value: str) -> int:
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from exc
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a non-negative integer")
    return ivalue


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Story 3.14 AC-3 live memory latency benchmark"
    )
    parser.add_argument("--small-corpus", type=_positive_int, default=100)
    parser.add_argument("--large-corpus", type=_positive_int, default=50_000)
    parser.add_argument("--warmups", type=_positive_int, default=20)
    parser.add_argument("--samples", type=_positive_int, default=100)
    parser.add_argument(
        "--freshness-samples",
        type=_non_negative_int,
        default=30,
        help="AC-5 live freshness samples. 0 disables the phase; >0 requires LLM credentials + a real Celery worker.",
    )
    parser.add_argument("--output", type=str, required=True)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
