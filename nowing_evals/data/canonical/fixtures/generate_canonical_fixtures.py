"""Generate canonical dedup fixtures for BDS and Jobs at 15/30/70% overlap.

ponytail: fixtures are intentionally synthetic and deterministic.  Each
multi-source entity shares a phone/address key (BDS) or an exact canonical
key (Jobs) so the production dedup logic can merge them; every single-source
entity is isolated by a unique token so it is not merged.  The overlap rate
is the fraction of unique canonical entities that appear in >=2 distinct
sources, computed independently from the raw record total.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

random.seed(42)

N_ENTITIES = 100
OVERLAPS = (0.15, 0.30, 0.70)
BDS_SOURCES = ("batdongsan", "chotot_bds", "muaban_bds")
JOBS_SOURCES = ("vietnamworks", "topcv", "itviec")


def _unique_token(i: int) -> str:
    """Stable, two-letter, non-stop-word token for entity i."""
    return f"{chr(65 + i // 26)}{chr(97 + i % 26)}"


def _bds_record(entity_index: int, source: str, source_index: int, multi: bool) -> dict:
    """Build one raw BĐS record.

    ponytail: multi-source rows reuse the same phone and address components
    so the union-find deduper merges them; single-source rows use unique
    tokens for both so they remain in singleton groups.
    """
    token = _unique_token(entity_index)
    entity_id = f"bds-entity-{entity_index:04d}"
    source_id = f"{entity_id}-{source}"
    phone_core = f"090{100_000 + entity_index:06d}"

    return {
        "record_id": f"{entity_id}:{source}",
        "canonical_entity_id": entity_id,
        "source": source,
        "source_id": source_id,
        "listing_id": source_id,
        "title": f"Bán nhà Quận {token}",
        "price": "5 tỷ",
        "area": "75 m²",
        "location": f"Đường {token}",
        "district": f"Quận {token}",
        "ward": f"Phường {token}",
        "city": "Hồ Chí Minh",
        "project": f"Dự án {token}",
        "legal": "Sổ hồng",
        "phone": phone_core,
        "contact": phone_core,
        "thumbnail_url": f"https://example.com/img/{token}.jpg",
        "post_date": "2026-08-01",
        "detail_url": f"https://{source}.example.com/{source_id}",
    }


def _jobs_record(entity_index: int, source: str, source_index: int, multi: bool) -> dict:
    """Build one raw Jobs record.

    ponytail: the Jobs deduper keys on (company, title, location, posted_at).
    Multi-source rows share all four fields; single-source rows get a unique
    title/company pair so the canonical key is distinct.
    """
    token = _unique_token(entity_index)
    entity_id = f"jobs-entity-{entity_index:04d}"
    source_id = f"{entity_id}-{source}"

    if multi:
        title = f"Senior {token} Engineer"
        company = f"{token} Corp"
    else:
        title = f"Junior {token} Specialist"
        company = f"{token} Ltd"

    return {
        "record_id": f"{entity_id}:{source}",
        "canonical_entity_id": entity_id,
        "source": source,
        "source_id": source_id,
        "id": source_id,
        "title": title,
        "company": company,
        "location": "Hồ Chí Minh",
        "salary_min": 1_000,
        "salary_max": 2_000,
        "salary_raw": "1,000 - 2,000 USD",
        "salary_currency": "USD",
        "posted_at": "2026-08-01",
        "employment_type": "full_time",
        "experience_years": 3,
        "skills": ["python"],
        "job_description": f"Build {token} services.",
        "job_requirement": f"3+ years {token}.",
        "source_url": f"https://{source}.example.com/{source_id}",
    }


def _generate_fixture(domain: str, overlap: float, sources: tuple[str, ...]) -> list[dict]:
    """Return the raw-record list for a single domain/overlap tier."""
    multi_count = round(overlap * N_ENTITIES)
    record_builder = _bds_record if domain == "bds" else _jobs_record

    records: list[dict] = []
    for entity_index in range(N_ENTITIES):
        is_multi = entity_index < multi_count
        chosen_sources = (
            list(sources[:2])
            if is_multi
            else [sources[entity_index % len(sources)]]
        )
        random.shuffle(chosen_sources)
        for source_index, source in enumerate(chosen_sources):
            records.append(record_builder(entity_index, source, source_index, is_multi))

    random.shuffle(records)
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _fixture_stats(records: list[dict]) -> dict:
    """Return the counts and overlap rate that the fixture satisfies."""
    entity_sources: dict[str, set[str]] = defaultdict(set)
    for record in records:
        entity_sources[record["canonical_entity_id"]].add(record["source"])

    total_entities = len(entity_sources)
    multi_source_entities = sum(1 for sources in entity_sources.values() if len(sources) >= 2)
    return {
        "total_ground_truth_entities": total_entities,
        "multi_source_ground_truth_entities": multi_source_entities,
        "single_source_ground_truth_entities": total_entities - multi_source_entities,
        "total_raw_records": len(records),
        "overlap_rate": round(multi_source_entities / total_entities, 4) if total_entities else 0.0,
    }


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    manifest: dict[str, dict] = {}

    for overlap in OVERLAPS:
        for domain, sources in (("bds", BDS_SOURCES), ("jobs", JOBS_SOURCES)):
            records = _generate_fixture(domain, overlap, sources)
            filename = f"{domain}-overlap-{int(overlap * 100):02d}.jsonl"
            path = out_dir / filename
            _write_jsonl(path, records)
            stats = _fixture_stats(records)
            manifest[filename] = {
                "domain": domain,
                "target_overlap": overlap,
                **stats,
            }
            print(f"Wrote {path} : {stats}")

    manifest_path = out_dir / "canonical_fixtures_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    print(f"Wrote manifest {manifest_path}")


if __name__ == "__main__":
    main()
