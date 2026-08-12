#!/usr/bin/env python3
"""Smoke test ``vn_jobs.aggregate`` against live source APIs.

Usage:
    cd nowing_backend
    uv run python scripts/smoke_vn_jobs_aggregate.py

This calls the multi-source aggregator with a small request (max 2 items,
max 1 page per source).  Persistence is disabled (no DB session).  Output
is printed as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from types import SimpleNamespace

import orjson

from app.services.jobs_aggregator import aggregate_jobs
from app.services.jobs_aggregator.schemas import VnJobAggregateInput


async def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test vn_jobs.aggregate")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["vietnamworks", "topcv", "itviec"],
        help="sources to aggregate",
    )
    parser.add_argument("--keyword", default="data engineer")
    parser.add_argument("--location", default="Hà Nội")
    parser.add_argument("--max-items", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=1)
    args = parser.parse_args()

    input = VnJobAggregateInput(
        keyword=args.keyword,
        location=args.location,
        sources=args.sources,
        max_items_per_source=args.max_items,
        max_pages=args.max_pages,
    )
    # ctx without session -> persistence returns "not_attempted"
    ctx = SimpleNamespace(run_id=None, workspace_id=None, session=None)

    output = await aggregate_jobs(input, ctx)

    print(json.dumps({
        "total_items": len(output.items),
        "cost_micros": output.cost_micros,
        "degraded": output.degraded,
        "degraded_source_ids": output.degraded_source_ids,
        "degradation_reasons": output.degradation_reasons,
        "source_breakdown": output.source_breakdown,
        "items": [orjson.loads(item.model_dump_json()) for item in output.items],
    }, ensure_ascii=False, default=str, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
