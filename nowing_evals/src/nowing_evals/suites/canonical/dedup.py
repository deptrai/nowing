"""Canonical dedup benchmark runner.

Loads synthetic BDS/Jobs fixtures, normalizes and deduplicates them with the
production domain logic, and reports pairwise precision/recall/F1 against the
ground-truth ``canonical_entity_id`` labels.  The benchmark fails closed when
any hard gate is not met.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import types
from collections import defaultdict
from pathlib import Path
from typing import Any

from nowing_evals.core.config import utc_iso_timestamp
from nowing_evals.core.registry import ReportSection, RunArtifact, RunContext

_GATES = {
    "precision": 0.95,
    "recall": 0.90,
    "f1": 0.92,
}

_BACKEND_MODULES: dict[str, Any] | None = None


def _backend_root() -> Path:
    """Return the sibling ``nowing_backend`` package root."""
    return Path(__file__).resolve().parents[5] / "nowing_backend"


def _ensure_backend_path() -> None:
    """Make ``app.*`` importable from the sibling ``nowing_backend`` package.

    ponytail: the eval harness and backend are separate packages; rather
    than coupling their pyprojects, we add the backend root to ``sys.path``
    at import time.  This works for source checkouts; installed wheels would
    need the backend package installed separately.
    """
    backend_root = _backend_root()
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


def _stub_jobs_aggregator_package() -> None:
    """Avoid importing ``jobs_aggregator/__init__.py``.

    ``jobs_aggregator/__init__.py`` eagerly imports the orchestrator, which
    pulls in ``app.config`` and its heavy third-party stack.  We only need
    ``dedupe.py`` and ``normalize.py`` for the benchmark, so we stub the
    package and let those submodules load on demand.
    """
    if "app.services.jobs_aggregator" in sys.modules:
        return
    pkg = types.ModuleType("app.services.jobs_aggregator")
    pkg.__path__ = [str(_backend_root() / "app" / "services" / "jobs_aggregator")]
    sys.modules["app.services.jobs_aggregator"] = pkg


def _import_backend_modules() -> dict[str, Any]:
    """Lazy import the production dedup modules, caching the result."""
    global _BACKEND_MODULES
    if _BACKEND_MODULES is not None:
        return _BACKEND_MODULES

    _ensure_backend_path()
    _stub_jobs_aggregator_package()

    # The first import of ``app.config`` is chatty; silence stdout/stderr.
    with (
        open(os.devnull, "w") as devnull,
        contextlib.redirect_stdout(devnull),
        contextlib.redirect_stderr(devnull),
    ):
        from app.canonical.eval.dedup_metrics import score_dedup
        from app.services.bds_aggregator.dedupe import (
            deduplicate as bds_deduplicate,
        )
        from app.services.bds_aggregator.dedupe import (
            fingerprint as bds_fingerprint,
        )
        from app.services.bds_aggregator.normalize import (
            normalize_listing as bds_normalize,
        )
        from app.services.jobs_aggregator.dedupe import (
            deduplicate as jobs_deduplicate,
        )
        from app.services.jobs_aggregator.dedupe import (
            fingerprint as jobs_fingerprint,
        )
        from app.services.jobs_aggregator.normalize import (
            normalize_listing as jobs_normalize,
        )

    _BACKEND_MODULES = {
        "bds_deduplicate": bds_deduplicate,
        "bds_fingerprint": bds_fingerprint,
        "bds_normalize": bds_normalize,
        "jobs_deduplicate": jobs_deduplicate,
        "jobs_fingerprint": jobs_fingerprint,
        "jobs_normalize": jobs_normalize,
        "score_dedup": score_dedup,
    }
    return _BACKEND_MODULES


def _default_fixture_dir() -> Path:
    """Return the committed fixture directory under ``data/canonical/fixtures``."""
    # parents[4] is the ``nowing_evals/`` package root (src/nowing_evals/suites/...).
    return Path(__file__).resolve().parents[4] / "data" / "canonical" / "fixtures"


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _record_index_key(record: dict) -> tuple[str, str]:
    return str(record["source"]), str(record.get("source_id", record.get("id", "")))


def _bds_predicted_groups(records: list[dict], merged: list[Any]) -> list[list[dict]]:
    record_index = {_record_index_key(r): r for r in records}
    groups: list[list[dict]] = []
    for item in merged:
        group: list[dict] = []
        for source, source_id in item.source_ids.items():
            if source_id is None:
                continue
            key = (source, str(source_id))
            if key in record_index:
                group.append(record_index.pop(key))
        if group:
            groups.append(group)
    # Any record not claimed by a merged source_ids map is a singleton.
    for record in record_index.values():
        groups.append([record])
    return groups


def _jobs_predicted_groups(records: list[dict], merged: list[Any]) -> list[list[dict]]:
    record_index = {_record_index_key(r): r for r in records}
    groups: list[list[dict]] = []
    for item in merged:
        group: list[dict] = []
        # _source_record_ids is a PrivateAttr; it is safe to read in this
        # benchmark context because we control the listing lifecycle.
        for source, source_id in item._source_record_ids.items():
            key = (source, str(source_id))
            if key in record_index:
                group.append(record_index.pop(key))
        if group:
            groups.append(group)
    for record in record_index.values():
        groups.append([record])
    return groups


def _fingerprint(domain: str, record: dict) -> str:
    mods = _import_backend_modules()
    return mods["bds_fingerprint"](record) if domain == "bds" else mods["jobs_fingerprint"](record)


def _run_fixture(domain: str, fixture_path: Path) -> dict:
    """Run one fixture end-to-end and return the result summary."""
    mods = _import_backend_modules()
    records = _load_jsonl(fixture_path)
    ground_truth = {r["record_id"]: r["canonical_entity_id"] for r in records}

    if domain == "bds":
        listings = [mods["bds_normalize"](r["source"], r) for r in records]
        merged = mods["bds_deduplicate"](listings)
        predicted_groups = _bds_predicted_groups(records, merged)
    else:
        listings = [mods["jobs_normalize"](r["source"], r) for r in records]
        merged = mods["jobs_deduplicate"](listings)
        predicted_groups = _jobs_predicted_groups(records, merged)

    for r in records:
        r["fingerprint"] = _fingerprint(domain, r)

    scores = mods["score_dedup"](records, predicted_groups, ground_truth)

    entity_sources: dict[str, set[str]] = defaultdict(set)
    for record in records:
        entity_sources[record["canonical_entity_id"]].add(record["source"])
    multi_source_entities = sum(1 for s in entity_sources.values() if len(s) >= 2)
    overlap_rate = (
        multi_source_entities / len(entity_sources) if entity_sources else 0.0
    )

    return {
        "domain": domain,
        "fixture": fixture_path.stem,
        "precision": round(scores.precision, 6),
        "recall": round(scores.recall, 6),
        "f1": round(scores.f1, 6),
        "true_positives": scores.true_positives,
        "false_positives": scores.false_positives,
        "false_negatives": scores.false_negatives,
        "n_records": scores.n_records,
        "n_entities": scores.n_entities,
        "multi_source_entities": multi_source_entities,
        "overlap_rate": round(overlap_rate, 4),
        "passed_gates": scores.passed,
    }


def _print_summary(result: dict) -> None:
    print(
        f"[{result['domain']:5}] {result['fixture']:20} "
        f"P={result['precision']:.4f} "
        f"R={result['recall']:.4f} "
        f"F1={result['f1']:.4f} "
        f"overlap={result['overlap_rate']:.2f} "
        f"{'PASS' if result['passed_gates'] else 'FAIL'}"
    )


class CanonicalDedupBenchmark:
    """Benchmark canonical deduplication quality for BDS and Jobs fixtures."""

    suite: str = "canonical"
    name: str = "dedup"
    headline: bool = False
    description: str = "Canonical deduplication P/R/F1 against ground-truth fixtures."
    requires_suite_setup: bool = False
    requires_auth_for_ingest: bool = False
    requires_auth_for_run: bool = False

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--domain",
            choices=("bds", "jobs"),
            required=True,
            help="Domain fixture type (bds or jobs).",
        )
        parser.add_argument(
            "--fixture",
            required=True,
            help="Fixture stem, e.g. 'bds-overlap-30'.",
        )
        parser.add_argument(
            "--fixture-dir",
            default=None,
            help="Override the default committed fixture directory.",
        )

    async def ingest(self, ctx: RunContext, **_opts: Any) -> None:
        """No live ingestion required; fixtures are committed."""
        return None

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        domain: str = opts["domain"]
        fixture: str = opts["fixture"]
        fixture_dir = opts.get("fixture_dir")
        if fixture_dir:
            fixture_path = Path(fixture_dir) / f"{fixture}.jsonl"
        else:
            fixture_path = _default_fixture_dir() / f"{fixture}.jsonl"

        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")

        result = _run_fixture(domain, fixture_path)
        _print_summary(result)

        if not result["passed_gates"]:
            raise RuntimeError(
                f"Gate failed for {domain}/{fixture}: "
                f"precision={result['precision']}, recall={result['recall']}, f1={result['f1']} "
                f"(require precision>=0.95, recall>=0.90, f1>=0.92)"
            )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        records = _load_jsonl(fixture_path)
        for r in records:
            r["fingerprint"] = _fingerprint(domain, r)
        _write_jsonl(raw_path, records)

        _write_json_atomic(
            run_dir / "run_artifact.json",
            {
                "suite": self.suite,
                "benchmark": self.name,
                "raw_path": "raw.jsonl",
                "metrics": result,
                "extra": {"fixture_path": str(fixture_path)},
            },
        )

        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=result,
            extra={"fixture_path": str(fixture_path)},
        )

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="Canonical dedup",
                headline=False,
                body_md="(no run artifacts found)",
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        result = latest.metrics
        body = "\n".join(
            [
                f"- domain: {result.get('domain')}",
                f"- fixture: {result.get('fixture')}",
                f"- precision: {result.get('precision'):.4f}",
                f"- recall: {result.get('recall'):.4f}",
                f"- f1: {result.get('f1'):.4f}",
                f"- overlap_rate: {result.get('overlap_rate'):.4f}",
                f"- gate: {'PASS' if result.get('passed_gates') else 'FAIL'}",
            ]
        )
        return ReportSection(
            title="Canonical dedup",
            headline=False,
            body_md=body,
            body_json=result,
        )


def _write_json_atomic(path: Path, payload: dict) -> None:
    """Write ``payload`` to ``path`` via a uniquely named temp file."""
    import os
    import uuid

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
