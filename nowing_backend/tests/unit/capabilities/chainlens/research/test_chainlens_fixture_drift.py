from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from app.capabilities.chainlens.research.schemas import ResearchOutput

from .test_executor import _parse_sse, _sse_line

pytestmark = [pytest.mark.unit, pytest.mark.contract]


_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "chainlens-sse-golden.json"
_CHAINLENS_FIXTURE = "apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts"


def _extract_json_from_ts(ts_path: Path) -> list[dict]:
    """Crudely extract the first JSON array/object literal from a .ts file."""
    text = ts_path.read_text(encoding="utf-8")
    match = re.search(r"(?:const\s+\w+\s*=\s*|export\s+default\s*)(\[|{", text)
    if not match:
        pytest.fail(f"Could not find a fixture literal in {ts_path}")
    start = match.start(1)
    brace = text[start]
    end_brace = "]" if brace == "[" else "}"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not in_string:
            in_string = True
        elif ch == '"' and in_string:
            in_string = False
        elif not in_string and ch in (brace, end_brace):
            if ch == brace:
                depth += 1
            elif ch == end_brace:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError as exc:
                        pytest.fail(f"Invalid JSON in {ts_path}: {exc}")
    pytest.fail(f"Unterminated fixture literal in {ts_path}")


@pytest.mark.test_id("9-1b-040")
def test_chainlens_sse_golden_fixture_is_valid_json():
    """Local golden fixture loads and contains a non-empty list of frames."""
    raw = _GOLDEN_PATH.read_text(encoding="utf-8")
    fixture = json.loads(raw)
    assert isinstance(fixture, list)
    assert len(fixture) >= 1
    assert all(isinstance(frame, dict) for frame in fixture)


@pytest.mark.test_id("9-1b-041")
def test_chainlens_sse_golden_fixture_parses_through_parse_sse():
    """Golden fixture is semantically parseable and produces usable output."""
    fixture = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    raw = "".join(_sse_line(frame) for frame in fixture)
    output = _parse_sse(raw)

    assert isinstance(output, ResearchOutput)
    assert output.status not in ("insufficient_evidence", "timeout")
    assert output.answer or output.sources


@pytest.mark.test_id("9-1b-042")
@pytest.mark.skipif(
    not os.environ.get("CHAINLENS_REPO_PATH"),
    reason="Set CHAINLENS_REPO_PATH to run drift test against ChainLens fixture",
)
def test_chainlens_sse_golden_matches_upstream_fixture():
    """Drift guard: fail CI if the local golden diverges from ChainLens source."""
    repo_path = Path(os.environ["CHAINLENS_REPO_PATH"])
    upstream = repo_path / _CHAINLENS_FIXTURE
    if not upstream.exists():
        pytest.fail(
            f"CHAINLENS_REPO_PATH does not contain expected fixture: {upstream}"
        )

    local = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    upstream_data = _extract_json_from_ts(upstream)
    assert local == upstream_data, (
        "Local chainlens-sse-golden.json has drifted from upstream "
        f"{_CHAINLENS_FIXTURE}. Copy the updated fixture and re-run tests."
    )
