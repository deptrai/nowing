"""Lead extraction regression benchmark (AC-1 / AD-107).

Evaluates F1 Phone, Hallucination Rate, MST Modulo-11 accuracy, and Company
Name F1 in live or replay modes.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

import yaml

from ....core.config import utc_iso_timestamp
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
    register,
)
from .extractor_client import ExtractorClient
from .metrics import (
    company_name_f1,
    f1_phone,
    hallucination_rate,
    mst_modulo11_accuracy,
)

logger = logging.getLogger(__name__)

_DESCRIPTION = (
    "Lead entity extraction regression: F1 Phone, Hallucination Rate, "
    "MST Modulo-11 validation accuracy, and Company Name F1."
)

_DEFAULT_DATASET: list[dict[str, Any]] = [
    {
        "case_id": "lead-001",
        "source_markdown": "Công ty TNHH Viễn Thông ABC. MST: 0100109106. Hotline: 0908123456 hoặc O912.345.678.",
        "expected_phones": ["0908123456", "0912345678"],
        "expected_tax_ids": ["0100109106"],
        "expected_tax_ids_valid": [True],
        "expected_company_name": "Công ty TNHH Viễn Thông ABC",
        "tags": ["telecom", "obfuscated-phone"],
    },
    {
        "case_id": "lead-002",
        "source_markdown": "TẬP ĐOÀN CÔNG NGHỆ FPT. Chi nhánh HCM: 0300588569-001. Alo ngay +84 987 654 321 gặp phòng kinh doanh.",
        "expected_phones": ["0987654321"],
        "expected_tax_ids": ["0300588569-001"],
        "expected_tax_ids_valid": [True],
        "expected_company_name": "TẬP ĐOÀN CÔNG NGHỆ FPT",
        "tags": ["tech", "branch-mst", "prefix-84"],
    },
    {
        "case_id": "lead-003",
        "source_markdown": "Chính chủ cho thuê nhà xưởng. Liên hệ anh Nam: 09 12 34 56 78. Không tiếp môi giới.",
        "expected_phones": ["0912345678"],
        "expected_tax_ids": [],
        "expected_tax_ids_valid": [],
        "expected_company_name": None,
        "tags": ["real-estate", "spaced-digits"],
    },
    {
        "case_id": "lead-004",
        "source_markdown": "DOANH NGHIỆP TƯ NHÂN MINH PHÁT. Mã số thuế: 0100109106. SĐT Zalo 84908889999.",
        "expected_phones": ["0908889999"],
        "expected_tax_ids": ["0100109106"],
        "expected_tax_ids_valid": [True],
        "expected_company_name": "DOANH NGHIỆP TƯ NHÂN MINH PHÁT",
        "tags": ["manufacturing", "zalo-84"],
    },
    {
        "case_id": "lead-005",
        "source_markdown": "Tuyển dụng nhân viên kinh doanh bất động sản. Hotline o79-888-9999 gặp Chị Hương.",
        "expected_phones": ["0798889999"],
        "expected_tax_ids": [],
        "expected_tax_ids_valid": [],
        "expected_company_name": None,
        "tags": ["recruitment", "letter-o"],
    },
    {
        "case_id": "lead-006",
        "source_markdown": "Công ty Cổ phần Xây dựng Delta. Mã số thuế 0300588569. Liên hệ số cũ 01681234567.",
        "expected_phones": ["0381234567"],
        "expected_tax_ids": ["0300588569"],
        "expected_tax_ids_valid": [True],
        "expected_company_name": "Công ty Cổ phần Xây dựng Delta",
        "tags": ["construction", "legacy-11-digit"],
    },
    {
        "case_id": "lead-007",
        "source_markdown": "Bán gấp lô đất mặt tiền quận 9. Gọi ngay o93.456.7890 hoặc nhắn tin Zalo.",
        "expected_phones": ["0934567890"],
        "expected_tax_ids": [],
        "expected_tax_ids_valid": [],
        "expected_company_name": None,
        "tags": ["real-estate", "obfuscated-dot"],
    },
    {
        "case_id": "lead-008",
        "source_markdown": "CÔNG TY TNHH GIẢI PHÁP SỐ. MST: 0100109106. Email: contact@digital.vn. SĐT: 0988776655.",
        "expected_phones": ["0988776655"],
        "expected_tax_ids": ["0100109106"],
        "expected_tax_ids_valid": [True],
        "expected_company_name": "CÔNG TY TNHH GIẢI PHÁP SỐ",
        "tags": ["tech", "full-profile"],
    },
    {
        "case_id": "lead-009",
        "source_markdown": "Mã số doanh nghiệp: 0300588569. Cảnh báo lừa đảo liên hệ 0911223344.",
        "expected_phones": ["0911223344"],
        "expected_tax_ids": ["0300588569"],
        "expected_tax_ids_valid": [True],
        "expected_company_name": None,
        "tags": ["fraud", "valid-mst"],
    },
    {
        "case_id": "lead-010",
        "source_markdown": "Tuyển lập trình viên Python / FastAPI lương $2000. CV gửi về hr@nowing.net hoặc gọi 0909000111.",
        "expected_phones": ["0909000111"],
        "expected_tax_ids": [],
        "expected_tax_ids_valid": [],
        "expected_company_name": None,
        "tags": ["tech-recruitment"],
    },
]


_CASE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_case_id(case_id: Any) -> str:
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("case_id must be a non-empty string")
    if not _CASE_ID_RE.match(case_id):
        raise ValueError(
            f"case_id {case_id!r} contains unsafe characters; only [a-zA-Z0-9_-] allowed"
        )
    return case_id


def _coerce_tags(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    return []


def _validate_case(case: Any, *, line_no: int | None = None) -> dict[str, Any]:
    """Validate a single case row and return a normalized copy."""
    if not isinstance(case, dict):
        prefix = f"cases.jsonl line {line_no}: " if line_no else ""
        raise ValueError(f"{prefix}each case must be a JSON object")

    case_id = _validate_case_id(case.get("case_id"))
    source_markdown = case.get("source_markdown")
    if not isinstance(source_markdown, str):
        prefix = f"cases.jsonl line {line_no}: " if line_no else ""
        raise ValueError(f"{prefix}case {case_id!r} missing required field 'source_markdown'")

    expected_phones = case.get("expected_phones", [])
    if expected_phones is not None and not isinstance(expected_phones, list):
        raise ValueError(f"case {case_id!r} 'expected_phones' must be a list")

    expected_tax_ids = case.get("expected_tax_ids", [])
    if expected_tax_ids is not None and not isinstance(expected_tax_ids, list):
        raise ValueError(f"case {case_id!r} 'expected_tax_ids' must be a list")

    expected_tax_ids_valid = case.get("expected_tax_ids_valid", [])
    if expected_tax_ids_valid is not None and not isinstance(expected_tax_ids_valid, list):
        raise ValueError(f"case {case_id!r} 'expected_tax_ids_valid' must be a list")

    expected_company_name = case.get("expected_company_name")
    if expected_company_name is not None and not isinstance(expected_company_name, str):
        raise ValueError(f"case {case_id!r} 'expected_company_name' must be a string or null")

    tags = _coerce_tags(case.get("tags"))
    allow_hallucinated_phones = bool(case.get("allow_hallucinated_phones", False))

    return {
        "case_id": case_id,
        "source_markdown": source_markdown,
        "expected_phones": expected_phones or [],
        "expected_tax_ids": expected_tax_ids or [],
        "expected_tax_ids_valid": expected_tax_ids_valid or [],
        "expected_company_name": expected_company_name,
        "tags": tags,
        "allow_hallucinated_phones": allow_hallucinated_phones,
    }


@dataclass
class _FileLock:
    """Advisory file lock using ``fcntl`` when available (no-op on Windows)."""

    path: Path

    def __enter__(self) -> _FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")
        if fcntl is not None:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                logger.debug("fcntl lock failed: %s", exc)
        return self

    def __exit__(self, *exc: Any) -> None:
        if fcntl is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        self._fh.close()


def _write_jsonl_atomic(path: Path, lines: list[dict[str, Any]]) -> None:
    """Write JSONL atomically using ``tmp + os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp, path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically using ``tmp + os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _load_lead_extraction_gate() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load (top-level, thresholds) from this benchmark's gate.yaml."""
    gate_path = Path(__file__).parent / "gate.yaml"
    if not gate_path.is_file():
        return {}, {}
    data = yaml.safe_load(gate_path.read_text(encoding="utf-8")) or {}
    return data, data.get("thresholds") or {}


def evaluate_lead_extraction_gate(
    metrics: dict[str, Any], thresholds: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Evaluate lead extraction metrics against gate thresholds.

    Missing primary metrics are treated as failures; no optimistic defaults.
    """
    reasons: list[str] = []

    for required in ("f1_phone", "hallucination_rate", "mst_modulo11_accuracy", "total_cases"):
        if required not in metrics:
            reasons.append(f"missing metric: {required}")

    if reasons:
        return False, reasons

    f1 = metrics["f1_phone"]
    min_f1 = thresholds.get("min_f1_phone", 0.98)
    if f1 < min_f1:
        reasons.append(f"f1_phone {f1:.4f} < min_f1_phone {min_f1:.4f}")

    hallucination = metrics["hallucination_rate"]
    max_hallucination = thresholds.get("max_hallucination_rate", 0.001)
    if hallucination > max_hallucination:
        reasons.append(
            f"hallucination_rate {hallucination:.4f} > max_hallucination_rate {max_hallucination:.4f}"
        )

    mst_acc = metrics["mst_modulo11_accuracy"]
    min_mst = thresholds.get("min_mst_modulo11_accuracy", 0.995)
    if mst_acc < min_mst:
        reasons.append(
            f"mst_modulo11_accuracy {mst_acc:.4f} < min_mst_modulo11_accuracy {min_mst:.4f}"
        )

    total_cases = metrics["total_cases"]
    min_cases = thresholds.get("min_cases", 10)
    if total_cases < min_cases:
        reasons.append(f"total_cases {total_cases} < min_cases {min_cases}")

    passed = len(reasons) == 0
    return passed, reasons


class LeadExtractionRegressionBenchmark:
    """Benchmark implementation for lead entity extraction regression."""

    suite = "lead_extraction"
    name = "regression"
    headline = True
    description = _DESCRIPTION
    requires_suite_setup = False
    requires_auth_for_ingest = False
    requires_auth_for_run = True
    supports_replay = True

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--tag",
            default=None,
            help="Filter cases by tag.",
        )
        parser.add_argument(
            "--max-cases",
            type=int,
            default=None,
            help="Limit number of cases to run (must be >= 0).",
        )
        parser.add_argument(
            "--run-id",
            default=None,
            help="Optional unique run-id suffix; auto-generated if omitted.",
        )
        parser.add_argument(
            "--fail-on-unratified",
            action="store_true",
            help="Fail the run if gate.yaml baseline_ratified is false.",
        )

    def _load_default_cases(self) -> list[dict[str, Any]]:
        """Load default cases from package JSONL if present, else fall back to embedded list."""
        package_cases = Path(__file__).parent / "default_cases.jsonl"
        if package_cases.is_file():
            cases: list[dict[str, Any]] = []
            with package_cases.open("r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    raw = json.loads(line)
                    cases.append(_validate_case(raw, line_no=line_no))
            return cases
        return _DEFAULT_DATASET

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        """Seed default cases.jsonl into benchmark data directory."""
        data_dir = ctx.benchmark_data_dir()
        cases_file = data_dir / "cases.jsonl"
        lock_file = data_dir / ".ingest.lock"
        default_cases = self._load_default_cases()

        with _FileLock(lock_file):
            _write_jsonl_atomic(cases_file, default_cases)

        logger.info("Wrote %d default cases to %s", len(default_cases), cases_file)

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        """Execute regression cases against live endpoint or recorded cassettes."""
        data_dir = ctx.benchmark_data_dir()
        cases_file = data_dir / "cases.jsonl"
        if not cases_file.exists():
            await self.ingest(ctx)

        cases: list[dict[str, Any]] = []
        with cases_file.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Malformed JSONL at {cases_file}:{line_no}: {exc}") from exc
                cases.append(_validate_case(raw, line_no=line_no))

        tag_filter = opts.get("tag")
        if tag_filter:
            cases = [c for c in cases if tag_filter in c["tags"]]

        max_cases = opts.get("max_cases")
        if max_cases is not None and max_cases < 0:
            raise ValueError(f"--max-cases must be >= 0, got {max_cases}")
        if max_cases is not None:
            cases = cases[:max_cases]

        client = ExtractorClient(ctx)
        run_id = opts.get("run_id") or uuid.uuid4().hex[:8]
        run_ts = f"{utc_iso_timestamp()}_{run_id}"
        runs_dir = ctx.runs_dir(run_timestamp=run_ts)
        raw_path = runs_dir / "raw.jsonl"

        results: list[dict[str, Any]] = []
        f1_scores: list[float] = []
        hallucinations: list[float] = []
        all_tax_valid: list[bool] = []
        company_f1_scores: list[float] = []

        per_tag: dict[str, dict[str, Any]] = {}

        for case in cases:
            case_id = case["case_id"]
            source_text = case["source_markdown"]
            expected_phones = case["expected_phones"]
            expected_tax_ids = case["expected_tax_ids"]
            expected_company_name = case["expected_company_name"]
            tags = case["tags"]

            extracted = await client.extract_entities(case_id, source_text)

            pred_phones = extracted.get("phones", [])
            pred_tax_ids = extracted.get("tax_ids", [])
            tax_ids_valid = extracted.get("tax_ids_valid", [])
            pred_company_name = extracted.get("company_name")

            case_f1 = f1_phone(pred_phones, expected_phones)
            case_hallucination = hallucination_rate(
                pred_phones,
                pred_tax_ids,
                source_text,
                expected_phones,
                expected_tax_ids,
            )
            case_mst = mst_modulo11_accuracy(tax_ids_valid)
            case_company_f1 = company_name_f1(pred_company_name, expected_company_name)

            f1_scores.append(case_f1)
            hallucinations.append(case_hallucination)
            all_tax_valid.extend(tax_ids_valid)
            company_f1_scores.append(case_company_f1)

            for tag in tags:
                bucket = per_tag.setdefault(
                    tag,
                    {
                        "f1_phone": [],
                        "hallucination_rate": [],
                        "company_name_f1": [],
                        "tax_ids_valid": [],
                        "total_cases": 0,
                    },
                )
                bucket["f1_phone"].append(case_f1)
                bucket["hallucination_rate"].append(case_hallucination)
                bucket["company_name_f1"].append(case_company_f1)
                bucket["tax_ids_valid"].extend(tax_ids_valid)
                bucket["total_cases"] += 1

            row = {
                "case_id": case_id,
                "tags": tags,
                "f1_phone": case_f1,
                "hallucination_rate": case_hallucination,
                "mst_modulo11_accuracy": case_mst,
                "company_name_f1": case_company_f1,
                "predicted_phones": pred_phones,
                "expected_phones": expected_phones,
                "predicted_tax_ids": pred_tax_ids,
                "expected_tax_ids": expected_tax_ids,
                "tax_ids_valid": tax_ids_valid,
                "predicted_company_name": pred_company_name,
                "expected_company_name": expected_company_name,
            }
            results.append(row)

        _write_jsonl_atomic(raw_path, results)

        avg_f1 = round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0.0
        avg_hallucination = (
            round(sum(hallucinations) / len(hallucinations), 4) if hallucinations else 0.0
        )
        avg_mst_acc = round(sum(all_tax_valid) / len(all_tax_valid), 4) if all_tax_valid else 1.0
        avg_company_f1 = (
            round(sum(company_f1_scores) / len(company_f1_scores), 4)
            if company_f1_scores
            else 1.0
        )

        per_tag_metrics: dict[str, Any] = {}
        for tag, bucket in sorted(per_tag.items()):
            tag_f1 = round(sum(bucket["f1_phone"]) / len(bucket["f1_phone"]), 4) if bucket["f1_phone"] else 0.0
            tag_hall = (
                round(sum(bucket["hallucination_rate"]) / len(bucket["hallucination_rate"]), 4)
                if bucket["hallucination_rate"]
                else 0.0
            )
            tag_mst = (
                round(
                    sum(bucket["tax_ids_valid"]) / len(bucket["tax_ids_valid"]), 4
                )
                if bucket["tax_ids_valid"]
                else 1.0
            )
            tag_company = (
                round(sum(bucket["company_name_f1"]) / len(bucket["company_name_f1"]), 4)
                if bucket["company_name_f1"]
                else 1.0
            )
            per_tag_metrics[tag] = {
                "total_cases": bucket["total_cases"],
                "f1_phone": tag_f1,
                "hallucination_rate": tag_hall,
                "mst_modulo11_accuracy": tag_mst,
                "company_name_f1": tag_company,
            }

        metrics: dict[str, Any] = {
            "total_cases": len(cases),
            "f1_phone": avg_f1,
            "hallucination_rate": avg_hallucination,
            "mst_modulo11_accuracy": avg_mst_acc,
            "company_name_f1": avg_company_f1,
            "mode": getattr(ctx, "mode", "live"),
            "per_tag": per_tag_metrics,
        }

        # Evaluate gate
        top, thresholds = _load_lead_extraction_gate()
        baseline_ratified = bool(top.get("baseline_ratified", False))
        baseline_source = str(top.get("baseline_source", ""))

        passed, reasons = evaluate_lead_extraction_gate(metrics, thresholds)
        extra = {
            "passed": passed,
            "gate_reasons": reasons,
            "thresholds": thresholds,
            "baseline_ratified": baseline_ratified,
            "baseline_source": baseline_source,
        }

        run_artifact_file = runs_dir / "run_artifact.json"
        _write_json_atomic(
            run_artifact_file,
            {
                "suite": self.suite,
                "benchmark": self.name,
                "run_timestamp": run_ts,
                "raw_path": "raw.jsonl",
                "metrics": metrics,
                "extra": extra,
            },
        )

        fail_on_unratified = bool(opts.get("fail_on_unratified"))

        if not passed:
            if baseline_ratified:
                raise RuntimeError(f"Lead extraction regression gate FAILED: {', '.join(reasons)}")
            logger.warning(
                "Lead extraction regression gate violations detected but baseline is not ratified "
                "(baseline_ratified=false): %s",
                "; ".join(reasons),
            )

        if fail_on_unratified and not baseline_ratified:
            raise RuntimeError(
                "Lead extraction regression gate is not ratified (baseline_ratified=false). "
                "Run with measured baseline and flip gate.yaml, or omit --fail-on-unratified."
            )

        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_ts,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
        )

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        """Render markdown section for benchmark summary report."""
        if not artifacts:
            return ReportSection(
                title="Lead Extraction Regression",
                headline=True,
                body_md="*No run artifacts available.*",
            )

        latest = max(artifacts, key=lambda a: a.run_timestamp)
        metrics = latest.metrics
        passed = latest.extra.get("passed", False)
        status_badge = "PASS" if passed else "FAIL"

        body_md = f"""### Lead Extraction Regression ({status_badge})


- **Mode:** `{metrics.get("mode", "live")}`
- **Cases Evaluated:** `{metrics.get("total_cases", 0)}`
- **F1 Phone Score:** `{metrics.get("f1_phone", 0.0):.4f}` (Target: `>= 0.9800`)
- **Hallucination Rate:** `{metrics.get("hallucination_rate", 0.0):.4f}` (Target: `<= 0.0010`)
- **MST Modulo-11 Accuracy:** `{metrics.get("mst_modulo11_accuracy", 1.0):.4f}` (Target: `>= 0.9950`)
- **Company Name F1:** `{metrics.get("company_name_f1", 1.0):.4f}`
"""
        per_tag = metrics.get("per_tag", {})
        if per_tag:
            body_md += "\n#### Per-tag Breakdown\n\n"
            body_md += "| Tag | Cases | F1 Phone | Hallucination | MST | Company F1 |\n"
            body_md += "|---|---|---|---|---|---|\n"
            for tag, vals in sorted(per_tag.items()):
                body_md += (
                    f"| {tag} | {vals.get('total_cases', 0)} | "
                    f"{vals.get('f1_phone', 0.0):.4f} | "
                    f"{vals.get('hallucination_rate', 0.0):.4f} | "
                    f"{vals.get('mst_modulo11_accuracy', 1.0):.4f} | "
                    f"{vals.get('company_name_f1', 1.0):.4f} |\n"
                )

        if not passed:
            reasons = latest.extra.get("gate_reasons", [])
            body_md += "\n**Gate failures:**\n\n"
            for reason in reasons:
                body_md += f"- {reason}\n"

        return ReportSection(
            title="Lead Extraction Regression",
            headline=True,
            body_md=body_md,
            body_json=metrics,
        )


# Auto-register benchmark
register(LeadExtractionRegressionBenchmark())
