"""Ship-gate: turn a scored RunArtifact into a pass/fail decision (Story 3.9, AC-6).

The gate exists because "we measured recall" is not the same as "recall is good
enough to ship". It reads the metrics a benchmark already persisted and compares
them against thresholds that must be **concrete numbers** committed to the repo.

Two rules drive the design, both from the story:

* **No placeholders** (epic AC3). ``None``, ``"≥80%"``, a bare ``"0.8"`` string,
  NaN, or anything outside ``[0, 1]`` is rejected at construction time rather
  than silently coerced. A gate whose threshold is unset is not a lenient gate,
  it is a broken one — and a broken gate that reports "pass" is worse than no
  gate at all.
* **A zero-query run cannot pass.** ``noise_rate`` defaults to 0.0 when nothing
  was judged, which would otherwise read as "perfectly clean". ``n_queries > 0``
  is therefore an explicit gate condition: no evidence is a failure, not a pass.

``evaluate_gate`` is pure — it takes a metrics mapping and thresholds and returns
a decision. Loading artifacts and choosing an exit code lives in the CLI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Where a suite's gate config lives, relative to the suite package:
#   suites/<suite>/<benchmark>/gate.yaml
_GATE_FILENAME = "gate.yaml"

_REQUIRED_KEYS = ("precision_at_5_min", "noise_rate_max")
_RECALL_SURFACE_KEYS = ("min_similarity", "top_k")

# RS-2: the recall gate never scores deeper than the top 5 hits.
MAX_TOP_K = 5


class GateConfigError(ValueError):
    """Raised when a gate config is missing, malformed, or uses a placeholder."""


def _require_unit_float(value: Any, *, field_name: str) -> float:
    """Coerce ``value`` to a float in ``[0, 1]`` or raise.

    Deliberately strict about types: ``bool`` is rejected (it is an ``int``
    subclass, so ``True`` would otherwise sail through as 1.0), and strings are
    rejected outright so a config carrying ``"≥80%"`` or even ``"0.8"`` fails
    loudly instead of being half-understood.
    """

    if value is None:
        raise GateConfigError(
            f"{field_name} is required and must be a concrete number — "
            "placeholder/None thresholds are not accepted (Story 3.9 AC-6)"
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GateConfigError(
            f"{field_name} must be a number in [0, 1], got {value!r} "
            f"({type(value).__name__}). Placeholders like '>=80%' are rejected."
        )
    as_float = float(value)
    if math.isnan(as_float) or math.isinf(as_float):
        raise GateConfigError(f"{field_name} must be finite, got {value!r}")
    if not 0.0 <= as_float <= 1.0:
        raise GateConfigError(f"{field_name} must be within [0, 1], got {as_float}")
    return as_float


def _require_top_k(value: Any) -> int:
    if value is None:
        raise GateConfigError(
            "top_k is required and must be a concrete int <= "
            f"{MAX_TOP_K} (RS-2) — placeholder/None is not accepted"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise GateConfigError(f"top_k must be an int, got {value!r} ({type(value).__name__})")
    if value < 1:
        raise GateConfigError(f"top_k must be >= 1, got {value}")
    if value > MAX_TOP_K:
        raise GateConfigError(f"top_k must be <= {MAX_TOP_K} (RS-2 clamp), got {value}")
    return value


@dataclass(frozen=True)
class GateThresholds:
    """Concrete SM-10 ship thresholds plus the recall-surface params (§6.3).

    ``precision_at_5_min`` / ``noise_rate_max`` are the ship conditions.
    ``top_k`` / ``min_similarity`` describe the oracle the run must have used —
    without them the thresholds would be scored against an unspecified surface,
    which makes the gate itself a placeholder.
    """

    precision_at_5_min: float
    noise_rate_max: float
    min_similarity: float = 0.30
    top_k: int = MAX_TOP_K

    def __post_init__(self) -> None:
        # Validate through object.__setattr__ because the dataclass is frozen.
        object.__setattr__(
            self,
            "precision_at_5_min",
            _require_unit_float(self.precision_at_5_min, field_name="precision_at_5_min"),
        )
        object.__setattr__(
            self,
            "noise_rate_max",
            _require_unit_float(self.noise_rate_max, field_name="noise_rate_max"),
        )
        object.__setattr__(
            self,
            "min_similarity",
            _require_unit_float(self.min_similarity, field_name="min_similarity"),
        )
        object.__setattr__(self, "top_k", _require_top_k(self.top_k))

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision_at_5_min": self.precision_at_5_min,
            "noise_rate_max": self.noise_rate_max,
            "min_similarity": self.min_similarity,
            "top_k": self.top_k,
        }


@dataclass(frozen=True)
class GateResult:
    """Decision plus human-readable reasons for every failed condition."""

    passed: bool
    reasons: list[str] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": list(self.reasons),
            "observed": dict(self.observed),
        }


def _precision_at_5(metrics: dict[str, Any]) -> float | None:
    """Pull precision@5 out of ``precision_at_k``, tolerating str/int keys.

    JSON round-trips dict keys to strings, so an artifact read back from disk has
    ``{"5": 0.8}`` while an in-memory ``RetrievalScores.to_dict()`` may have
    either. Both are accepted.
    """

    table = metrics.get("precision_at_k")
    if not isinstance(table, dict):
        return None
    for key in ("5", 5):
        if key in table:
            try:
                return float(table[key])
            except (TypeError, ValueError):
                return None
    return None


def evaluate_gate(metrics: dict[str, Any], thresholds: GateThresholds) -> GateResult:
    """Compare a run's ``metrics`` against ``thresholds``.

    Passes only when every condition holds: precision@5 at or above the floor,
    noise rate at or below the ceiling, and at least one judged query. Each
    failure contributes its own reason so a red gate says exactly what was wrong.
    """

    reasons: list[str] = []
    precision = _precision_at_5(metrics)
    noise = metrics.get("noise_rate")
    n_queries = metrics.get("n_queries")

    observed: dict[str, Any] = {
        "precision_at_5": precision,
        "noise_rate": noise,
        "n_queries": n_queries,
    }

    # A run with no judged queries reports noise_rate=0.0, which would otherwise
    # look like a flawless run. Treat missing evidence as a failure.
    if n_queries is not None:
        try:
            if int(n_queries) <= 0:
                reasons.append("n_queries is 0 — a run with no judged queries cannot pass the gate")
        except (TypeError, ValueError):
            reasons.append(f"n_queries is not an integer: {n_queries!r}")

    if precision is None:
        reasons.append("precision_at_k['5'] missing from run metrics")
    elif precision < thresholds.precision_at_5_min:
        reasons.append(
            f"precision@5 {precision:.3f} < required minimum {thresholds.precision_at_5_min:.3f}"
        )

    if noise is None:
        reasons.append("noise_rate missing from run metrics")
    else:
        try:
            noise_value = float(noise)
        except (TypeError, ValueError):
            reasons.append(f"noise_rate is not a number: {noise!r}")
        else:
            if noise_value > thresholds.noise_rate_max:
                reasons.append(
                    f"noise rate {noise_value:.3f} > allowed maximum "
                    f"{thresholds.noise_rate_max:.3f}"
                )

    return GateResult(passed=not reasons, reasons=reasons, observed=observed)


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #


def default_gate_config_path(suite: str = "memory", benchmark: str = "recall") -> Path:
    """Path to the committed gate config for ``<suite>/<benchmark>``."""

    from . import gate as _self  # noqa: PLC0415  (locate the installed package)

    core_dir = Path(_self.__file__).parent
    return core_dir.parent / "suites" / suite / benchmark / _GATE_FILENAME


def load_gate_thresholds(
    config_path: Path | str | None = None,
    *,
    suite: str = "memory",
    benchmark: str = "recall",
) -> GateThresholds:
    """Load thresholds from YAML, rejecting placeholders and unknown keys.

    Unknown keys are rejected rather than ignored: a typo'd ``precision_at5_min``
    would otherwise leave the real threshold at a default the operator never
    reviewed, which is the placeholder failure mode wearing a different hat.
    """

    import yaml  # noqa: PLC0415

    path = (
        Path(config_path) if config_path is not None else default_gate_config_path(suite, benchmark)
    )
    if not path.exists():
        raise GateConfigError(f"Gate config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GateConfigError(f"{path.name}: expected a YAML mapping, got {type(raw).__name__}")

    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if missing:
        raise GateConfigError(f"{path.name}: missing required threshold(s): {', '.join(missing)}")
    missing_surface = [key for key in _RECALL_SURFACE_KEYS if key not in raw]
    if missing_surface:
        raise GateConfigError(
            f"{path.name}: missing recall-surface param(s): {', '.join(missing_surface)} — "
            "without them the scored surface is unspecified (§6.3)"
        )

    known = set(_REQUIRED_KEYS) | set(_RECALL_SURFACE_KEYS)
    unknown = sorted(set(raw) - known)
    if unknown:
        raise GateConfigError(f"{path.name}: unknown key(s): {', '.join(unknown)}")

    return GateThresholds(
        precision_at_5_min=raw["precision_at_5_min"],
        noise_rate_max=raw["noise_rate_max"],
        min_similarity=raw["min_similarity"],
        top_k=raw["top_k"],
    )


__all__ = [
    "MAX_TOP_K",
    "GateConfigError",
    "GateResult",
    "GateThresholds",
    "default_gate_config_path",
    "evaluate_gate",
    "load_gate_thresholds",
]
