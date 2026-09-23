#!/usr/bin/env python3
"""Story 39.3 live verification: real scraper data -> real Jev decisions.

Proves the two-stage entity-resolution layer end to end against live
sources and the real TypeSafe System One backend (no mocks):

  bds   live-scrape 3 BĐS sources -> deduplicate -> find_match_candidates
        -> refine_entity_groups (entity_match_fanout@1.0.0 fan-out).
  corp  verify_company against live masothue -> fuzzy band -> Jev rescore
        (entity_match@1.0.0 pairwise, promote/review/out-of-band cases).
  merge fan-out merge edge: real harvested listing + cross-post clone
        (rephrased title, no shared keys) -> Jev confirm -> merge_group.

Usage:
    TYPESAFE_API_KEY=... DECISION_ENABLED=true DECISION_ENTITY_ENABLED=true \
    DECISION_BACKEND=jev uv run python scripts/verify_entity_resolution_39_3.py \
        --mode all --district "Quận 7" --max-items 15

Reads decision config from the environment; exits early if the key or the
master flag is missing (fail-open is the production default, so the check
is explicit here to avoid a silent no-op run).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("verify_39_3")

# Capability self-registration (app.routes does this inside the app).
import app.capabilities.batdongsan  # noqa: E402
import app.capabilities.chotot  # noqa: E402
import app.capabilities.muaban_bds  # noqa: E402,F401
from app.services.bds_aggregator.dedupe import (  # noqa: E402
    deduplicate,
    find_match_candidates,
    merge_group,
)
from app.services.bds_aggregator.normalize import normalize_listing  # noqa: E402
from app.services.bds_aggregator.orchestrator import (  # noqa: E402
    _entity_description,
    _entity_state,
    _execute_source,
)
from app.services.bds_aggregator.schemas import (  # noqa: E402
    VnBdsAggregatedListing,
    VnBdsAggregateInput,
)
from app.services.entity_resolution import refine_entity_groups  # noqa: E402


def _check_env() -> None:
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set — real Jev calls impossible")
    for var in ("DECISION_ENABLED", "DECISION_ENTITY_ENABLED"):
        if os.environ.get(var, "").lower() not in ("1", "true", "yes"):
            sys.exit(f"{var} is not enabled — run would silently fail-open")


async def run_bds(args: argparse.Namespace) -> None:
    payload = VnBdsAggregateInput(
        sources=["batdongsan", "chotot_bds", "muaban_bds"],
        city=args.city,
        district=args.district,
        listing_type="buy",
        max_items_per_source=args.max_items,
        max_pages=args.max_pages,
        resolve_phones=False,
    )

    normalized: list[VnBdsAggregatedListing] = []
    for source in payload.sources:
        items, cost, degraded, reason = await _execute_source(
            source, payload, None
        )
        print(
            f"[scrape] {source}: items={len(items)} cost={cost} "
            f"degraded={degraded} reason={reason}"
        )
        for raw in items:
            try:
                normalized.append(normalize_listing(source, raw))
            except Exception:
                log.exception("normalize failed for %s", source)
    print(f"[normalize] total listings={len(normalized)}")

    deduped = deduplicate(normalized)
    print(f"[dedup baseline] canonicals={len(deduped)}")

    pairs = find_match_candidates(deduped)
    print(
        f"[candidates] anchors={len(pairs)} "
        f"candidate_pairs={sum(len(v) for v in pairs.values())}"
    )
    for anchor_idx, cands in sorted(pairs.items()):
        anchor = deduped[anchor_idx]
        print(
            f"  anchor[{anchor_idx}] {anchor.canonical_id[:12]} "
            f"{(anchor.title or '')[:70]!r} -> {len(cands)} cand(s)"
        )
        for j in cands:
            c = deduped[j]
            print(
                f"      cand[{j}] {c.canonical_id[:12]} "
                f"{(c.title or '')[:70]!r} src={c.sources}"
            )

    refined, stats = await refine_entity_groups(
        deduped,
        pairs,
        id_of=lambda li: li.canonical_id,
        state_of=_entity_state,
        describe=_entity_description,
        merge_group=merge_group,
    )
    print(
        f"[refine] calls={stats.calls} confirmed={stats.confirmed} "
        f"no_match={stats.no_match} errors={stats.errors} "
        f"skipped_cap={stats.skipped_cap} aborted={stats.aborted}"
    )
    print(f"[result] baseline={len(deduped)} -> refined={len(refined)} canonicals")

    merged_away = {li.canonical_id for li in deduped} - {
        li.canonical_id for li in refined
    }
    if merged_away:
        print("[merges] canonicals merged away by Jev:")
        by_id = {li.canonical_id: li for li in deduped}
        for cid in sorted(merged_away):
            li = by_id[cid]
            print(
                f"  - {cid[:12]} {(li.title or '')[:70]!r} "
                f"loc={li.location or li.district or li.city} price={li.price}"
            )
        for li in refined:
            if len(li.source_ids) > 1 or len(li.sources) > 1:
                print(
                    f"  = merged {li.canonical_id[:12]} sources={li.sources} "
                    f"ids={list(li.source_ids)} {(li.title or '')[:60]!r}"
                )
    else:
        print("[merges] none — Jev confirmed no cross-cluster duplicates")


CORP_CASES = [
    # (input_name, city) — mix of band-hit and out-of-band real names
    ("Vinhomes", "Hồ Chí Minh"),
    ("Vinhomes Đan Phượng", "Hà Nội"),
    ("Công ty Vinhomes", "Hồ Chí Minh"),
    ("Bất động sản Vinhomes Đan Phượng", "Hà Nội"),
    ("Công ty Xây dựng Đại Phát", "Hồ Chí Minh"),
]


async def run_corp(_args: argparse.Namespace) -> None:
    from app.db.base import async_session_maker
    from app.services.corporate_verification_service import (
        AUTO_LINK_CONFIDENCE_THRESHOLD,
        CorporateVerificationService,
    )

    print(f"[config] AUTO_LINK_CONFIDENCE_THRESHOLD={AUTO_LINK_CONFIDENCE_THRESHOLD}")
    async with async_session_maker() as session:
        svc = CorporateVerificationService(session)
        for name, city in CORP_CASES:
            print(f"\n=== verify_company({name!r}, city={city!r}) ===")
            try:
                res = await svc.verify_company(
                    name, city=city, force_refresh=True, workspace_id=1
                )
            except Exception as exc:
                print(f"  EXC {type(exc).__name__}: {exc}")
                continue
            prof = res.profile
            print(
                f"  is_verified={res.is_verified} "
                f"confidence={res.confidence:.3f} "
                f"manual={res.requires_manual_confirmation} "
                f"degraded={res.degraded} cached={res.is_cached}"
            )
            if prof:
                print(
                    f"  matched: {prof.company_name!r} tax={prof.tax_id} "
                    f"city={prof.city} rep={prof.legal_representative}"
                )


def _listing(cid: str, title: str, **kw: Any) -> VnBdsAggregatedListing:
    return VnBdsAggregatedListing(
        canonical_id=cid,
        source_ids={kw.pop("src", "chotot_bds"): cid},
        title=title,
        confidence_score=0.8,
        **kw,
    )


async def run_merge(_args: argparse.Namespace) -> None:
    # Real listings harvested from the 2026-09-22 live Quận 3 scrape; the
    # clone mimics a broker cross-post (rephrased title, no shared keys) —
    # the exact false-negative shape the fan-out stage targets.
    real = [
        _listing(
            "real_anchor_q3_01",
            "Bán nhà xây mới Trung Tâm Q3",
            price="8,5 Tỷ",
            price_value=8_500_000_000,
            district="Quận 3",
            city="Hồ Chí Minh",
            ward="Phường 4",
            area="45m²",
            area_value=45.0,
            location="Trung tâm Quận 3",
        ),
        _listing(
            "real_clone_q3_01_xpost",
            "Bán nhà mới trung tâm Quận 3",
            price="8.5 tỷ",
            price_value=8_500_000_000,
            district="Quận 3",
            city="Hồ Chí Minh",
            ward="P.4",
            area="45 m2",
            area_value=45.0,
            location="TT Quận 3",
            src="muaban_bds",
        ),
        _listing(
            "real_ctrl_q3_hbt",
            "Chính chủ bán nhà hẻm xe hơi gần MT Hai Bà Trưng, "
            "3,5x23,5, nở hậu 5,5",
            price="12 Tỷ",
            price_value=12_000_000_000,
            district="Quận 3",
            city="Hồ Chí Minh",
            ward="Phường 6",
            area="82m²",
            area_value=82.0,
            src="muaban_bds",
        ),
    ]

    deduped = deduplicate(real)
    print(f"[dedup baseline] canonicals={len(deduped)} (no shared keys)")
    for i, li in enumerate(deduped):
        print(f"  [{i}] {li.canonical_id} {(li.title or '')[:60]!r}")

    pairs = find_match_candidates(deduped)
    print(f"[candidates] {dict(pairs)}")

    refined, stats = await refine_entity_groups(
        deduped,
        pairs,
        id_of=lambda li: li.canonical_id,
        state_of=_entity_state,
        describe=_entity_description,
        merge_group=merge_group,
    )
    print(
        f"[refine] calls={stats.calls} confirmed={stats.confirmed} "
        f"no_match={stats.no_match} errors={stats.errors} aborted={stats.aborted}"
    )
    print(f"[result] {len(deduped)} -> {len(refined)} canonicals")
    for li in refined:
        print(
            f"  = {li.canonical_id} sources={li.sources} "
            f"ids={li.source_ids} {(li.title or '')[:55]!r} price={li.price}"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["bds", "corp", "merge", "all"],
        default="all",
    )
    parser.add_argument("--city", default="Hồ Chí Minh")
    parser.add_argument("--district", default="Quận 7")
    parser.add_argument("--max-items", type=int, default=15)
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()

    _check_env()
    modes = ["bds", "corp", "merge"] if args.mode == "all" else [args.mode]
    for mode in modes:
        print(f"\n########## mode={mode} ##########")
        await {"bds": run_bds, "corp": run_corp, "merge": run_merge}[mode](args)


if __name__ == "__main__":
    asyncio.run(main())
