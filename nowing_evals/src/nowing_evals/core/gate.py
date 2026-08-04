"""Deterministic ship-gate evaluation for persisted benchmark artifacts.

Design constraints this module exists to satisfy (Story 3.9, NFR-8 / SM-10 /
RS-7), and the review decisions that shaped it:

* **Concrete thresholds, no placeholders** (epics AC3). Every threshold is a
  ``StrictFloat``/``StrictInt`` in range; ``None``, ints-for-floats and
  ``">=X%"`` strings are rejected at load time.
* **But a concrete number is not a validated number.** ``epics.md`` requires
  the SM-10 figures to be chosen *after* a measured baseline ("Given baseline
  đã đo, When chốt số SM-10"), and the PRD warns that setting thresholds
  before measuring repeats the NFR6 mistake. So the config also carries
  ``baseline_ratified`` + ``baseline_source``: until the numbers are backed by
  a real measurement and signed off, the gate **fails closed** rather than
  going green on invented figures.
* **The gate must judge the run it was handed, not the config it was given.**
  It verifies the artifact's own scoring configuration (``top_k``,
  ``oracle_mode``), sample size and failure count, so a run scored with a
  narrower window or a different oracle cannot pass while the console prints
  the pinned values.
* **Gated noise is the distractor-hit rate**, never ``1 - precision``. The
  latter is algebraically determined by precision, so gating on both applies
  one constraint while looking like two.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt, field_validator

# RS-2 caps the recall window at 5.
_MAX_TOP_K = 5
_SUPPORTED_ORACLE_MODES = ("rank_only", "score_threshold")


class GateThresholds(BaseModel):
    """Concrete, ship-blocking thresholds plus the pinned recall-surface contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Quality floors / ceilings.
    recall_at_5_min: StrictFloat
    mrr_min: StrictFloat
    distractor_noise_rate_max: StrictFloat
    off_corpus_rate_max: StrictFloat

    # Evidence requirements — a passing verdict on 1 query is not evidence.
    min_queries: StrictInt

    # The scoring contract the artifact must have been produced under.
    top_k: StrictInt = 5
    required_oracle_mode: str = "rank_only"

    # SM-10 ratification. Concrete numbers are mandatory; *trusted* numbers
    # require a measured baseline and an owner sign-off.
    baseline_ratified: StrictBool = False
    baseline_source: str = ""

    @field_validator(
        "recall_at_5_min",
        "mrr_min",
        "distractor_noise_rate_max",
        "off_corpus_rate_max",
    )
    @classmethod
    def _validate_probability(cls, value: float) -> float:
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("must be a finite float between 0 and 1")
        return value

    @field_validator("top_k")
    @classmethod
    def _validate_top_k(cls, value: int) -> int:
        if not 1 <= value <= _MAX_TOP_K:
            raise ValueError(f"must be an integer between 1 and {_MAX_TOP_K} (RS-2)")
        return value

    @field_validator("min_queries")
    @classmethod
    def _validate_min_queries(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1 — a zero-query run is not evidence")
        return value

    @field_validator("required_oracle_mode")
    @classmethod
    def _validate_oracle_mode(cls, value: str) -> str:
        if value not in _SUPPORTED_ORACLE_MODES:
            raise ValueError(f"must be one of {', '.join(_SUPPORTED_ORACLE_MODES)}")
        return value

    def model_post_init(self, _context: Any) -> None:
        binding = (
            self.recall_at_5_min > 0.0
            or self.mrr_min > 0.0
            or self.distractor_noise_rate_max < 1.0
            or self.off_corpus_rate_max < 1.0
        )
        if not binding:
            raise ValueError(
                "gate thresholds are vacuous — every condition would accept any run; "
                "at least one of recall_at_5_min / mrr_min must exceed 0 or one of "
                "distractor_noise_rate_max / off_corpus_rate_max must be below 1"
            )
        if self.baseline_ratified and not self.baseline_source.strip():
            raise ValueError(
                "baseline_ratified requires a non-empty baseline_source "
                "(run id / evidence pointer for the measured baseline)"
            )


@dataclass(frozen=True)
class GateResult:
    """A gate decision with all threshold-miss explanations preserved."""

    passed: bool
    reasons: list[str]
    observed: dict[str, float | int | str | None]


def _metric_number(value: Any) -> float | None:
    """Coerce a metric to a probability, or ``None`` when it is unusable.

    Fail-closed: bools, strings, NaN/inf and out-of-range values all become
    ``None``, which the caller turns into an explicit failure reason rather
    than a silent pass.
    """

    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        return None
    return numeric


def _metric_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _metric_at(metrics: Mapping[str, Any], field: str, k: int) -> float | None:
    bucket = metrics.get(field)
    if not isinstance(bucket, Mapping):
        return None
    return _metric_number(bucket.get(str(k), bucket.get(k)))


def evaluate_gate(metrics: Mapping[str, Any], thresholds: GateThresholds) -> GateResult:
    """Evaluate a persisted artifact's metrics against concrete ship thresholds."""

    reasons: list[str] = []

    # A7: if the runner recorded a backend build id, the gate must confirm it
    # was verified against the running backend.
    if "backend_build_id" in metrics:
        if not metrics.get("backend_build_id_verified"):
            reasons.append("backend_build_id was not verified against the running backend")
        elif metrics.get("backend_build_id") != metrics.get("verified_backend_build_id"):
            reasons.append(
                f"backend_build_id mismatch: artifact claims {metrics.get('backend_build_id')!r}, "
                f"running backend is {metrics.get('verified_backend_build_id')!r}"
            )

    if not thresholds.baseline_ratified:
        reasons.append(
            "SM-10 thresholds are not ratified against a measured baseline "
            "(baseline_ratified=false) — epics AC3 requires the numbers to be chosen "
            "after a real measurement, so the gate fails closed until an owner signs off"
        )

    # --- Evidence checks: is this run even admissible? ---------------------
    n_queries = _metric_int(metrics.get("n_queries"))
    if n_queries is None:
        reasons.append("n_queries is missing or not an integer")
    elif n_queries < thresholds.min_queries:
        reasons.append(
            f"n_queries {n_queries} is below the minimum sample size {thresholds.min_queries}"
        )

    n_failed = _metric_int(metrics.get("n_failed_queries", 0))
    if n_failed is None:
        reasons.append("n_failed_queries is missing or not an integer")
    elif n_failed > 0:
        reasons.append(
            f"{n_failed} query/queries failed during the run — a partial run cannot clear a ship gate"
        )

    artifact_top_k = _metric_int(metrics.get("top_k"))
    if artifact_top_k is None:
        reasons.append("top_k is missing from the artifact — cannot verify the scoring window")
    elif artifact_top_k != thresholds.top_k:
        reasons.append(
            f"artifact was scored with top_k={artifact_top_k} but the gate pins "
            f"top_k={thresholds.top_k}; the numbers are not comparable"
        )

    oracle_mode = metrics.get("oracle_mode")
    if not isinstance(oracle_mode, str) or not oracle_mode:
        reasons.append("oracle_mode is missing from the artifact")
    elif oracle_mode != thresholds.required_oracle_mode:
        reasons.append(
            f"artifact was scored with oracle_mode={oracle_mode!r} but the gate requires "
            f"{thresholds.required_oracle_mode!r}"
        )

    off_corpus_measured = metrics.get("off_corpus_measured")
    if off_corpus_measured is not True:
        reasons.append(
            "off_corpus_rate was not measured — results that resolve to no labeled memory "
            "would be invisible, so the noise figures cannot be trusted"
        )

    # --- Quality checks ----------------------------------------------------
    recall_at_5 = _metric_at(metrics, "recall_at_k", thresholds.top_k)
    if recall_at_5 is None:
        reasons.append(f"recall@{thresholds.top_k} is missing or not a finite number in [0, 1]")
    elif recall_at_5 < thresholds.recall_at_5_min:
        reasons.append(
            f"recall@{thresholds.top_k} {recall_at_5:.3f} is below required "
            f"{thresholds.recall_at_5_min:.3f}"
        )

    mrr_value = _metric_number(metrics.get("mrr"))
    if mrr_value is None:
        reasons.append("mrr is missing or not a finite number in [0, 1]")
    elif mrr_value < thresholds.mrr_min:
        reasons.append(f"MRR {mrr_value:.3f} is below required {thresholds.mrr_min:.3f}")

    distractor_noise = _metric_number(metrics.get("distractor_noise_rate"))
    if distractor_noise is None:
        reasons.append("distractor_noise_rate is missing or not a finite number in [0, 1]")
    elif distractor_noise > thresholds.distractor_noise_rate_max:
        reasons.append(
            f"distractor noise rate {distractor_noise:.3f} is above allowed "
            f"{thresholds.distractor_noise_rate_max:.3f}"
        )

    off_corpus = _metric_number(metrics.get("off_corpus_rate"))
    if off_corpus is None:
        reasons.append("off_corpus_rate is missing or not a finite number in [0, 1]")
    elif off_corpus > thresholds.off_corpus_rate_max:
        reasons.append(
            f"off-corpus rate {off_corpus:.3f} is above allowed "
            f"{thresholds.off_corpus_rate_max:.3f} — the workspace contains memories the "
            "labels cannot judge"
        )

    return GateResult(
        passed=not reasons,
        reasons=reasons,
        observed={
            "recall_at_5": recall_at_5,
            "mrr": mrr_value,
            "distractor_noise_rate": distractor_noise,
            "off_corpus_rate": off_corpus,
            "n_queries": n_queries,
            "n_failed_queries": n_failed,
            "top_k": artifact_top_k,
            "oracle_mode": oracle_mode if isinstance(oracle_mode, str) else None,
        },
    )


class GateConfigError(ValueError):
    """Raised when a gate configuration cannot be loaded or is malformed.

    Distinct from a quality failure so a CI job can tell "the gate is
    misconfigured" from "the run is below threshold".
    """


def load_gate_thresholds(path: str | Path) -> GateThresholds:
    """Load strict thresholds from a YAML gate configuration.

    ``core`` deliberately does not know where any suite keeps its config; the
    benchmark supplies the path (see ``MemoryRecallBenchmark.gate_config_path``).
    """

    config_path = Path(path)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GateConfigError(f"Unable to read gate configuration {config_path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise GateConfigError(
            f"Gate configuration {config_path} is not valid UTF-8: {exc}"
        ) from exc
    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise GateConfigError(f"Gate configuration {config_path} is not valid YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise GateConfigError(f"Gate configuration {config_path} must contain a mapping")
    try:
        return GateThresholds.model_validate(payload)
    except ValueError as exc:
        raise GateConfigError(f"Invalid gate configuration {config_path}: {exc}") from exc


__all__ = [
    "GateConfigError",
    "GateResult",
    "GateThresholds",
    "evaluate_gate",
    "load_gate_thresholds",
]
