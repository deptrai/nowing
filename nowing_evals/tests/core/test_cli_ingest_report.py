"""CLI ingest/report for no-auth/no-setup suites (Story 4.8)."""

from __future__ import annotations

import json
from pathlib import Path

from nowing_evals.core import registry
from nowing_evals.core.cli import main
from nowing_evals.core.registry import ReportSection


def test_ingest_chat_regression_requires_no_credentials(tmp_env, capsys):
    """`ChatRegressionBenchmark`` declares ``requires_auth_for_ingest=False``,
    so ``ingest chat regression`` must succeed without any Nowing credentials.
    """
    exit_code = main(["ingest", "chat", "regression"])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "ingest OK" in captured


def test_report_chat_allows_no_setup_suite(tmp_env, capsys):
    """``report --suite chat`` must not fail with "No setup for suite 'chat'".

    ChatRegressionBenchmark declares ``requires_suite_setup=False``; the CLI
    must fall back to a detached suite state and report absence of artifacts.
    """
    exit_code = main(["report", "--suite", "chat"])
    assert exit_code == 1
    captured = capsys.readouterr().out
    assert "No setup for suite" not in captured
    assert "Run a benchmark first" in captured


def test_report_filtered_benchmark_requires_setup(tmp_env, capsys):
    """Filtering to a setup-required benchmark must not bypass the setup check.

    A mixed suite with one no-setup benchmark used to make the CLI fall back
    to a detached state before the filter was applied (L5).
    """

    class _NeedsSetupBenchmark:
        suite = "chat"
        name = "needs_setup"
        headline = False
        description = "setup required"
        requires_suite_setup = True

        def report_section(self, _artifacts):
            return ReportSection(title="", headline=False, body_md="")

    registry.register(_NeedsSetupBenchmark())
    try:
        exit_code = main(["report", "--suite", "chat", "--benchmark", "needs_setup"])
    finally:
        registry.unregister("chat", "needs_setup")

    assert exit_code == 2
    captured = capsys.readouterr().out
    assert "No setup for suite" in captured


def test_ingest_accepts_sampler_jsonl_output(tmp_env, tmp_path: Path, capsys):
    """AC-5: JSONL produced by ``sample_chat_queries.py`` is accepted by ingest.

    The sampler writes one JSON object per line with keys ``case_id``,
    ``query``, ``tags``, ``mentioned_document_ids``, ``disabled_tools``, and
    ``workspace_id_hash``. The regression ingest must accept this format
    without error (extra keys like ``workspace_id_hash`` are ignored).
    """
    sampler_rows = [
        {
            "case_id": "prod-1",
            "query": "What is the Q3 budget?",
            "tags": ["memory", "budget"],
            "mentioned_document_ids": [10, 20],
            "disabled_tools": [],
            "workspace_id_hash": "abc123",
        },
        {
            "case_id": "prod-2",
            "query": "Summarize the memo",
            "tags": "document",
            "mentioned_document_ids": 5,
            "disabled_tools": ["web_search"],
            "workspace_id_hash": "def456",
        },
    ]
    dataset = tmp_path / "sampled.jsonl"
    with dataset.open("w", encoding="utf-8") as fh:
        for row in sampler_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    exit_code = main(["ingest", "chat", "regression", "--dataset", str(dataset)])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "ingest OK" in captured

    # Verify the cases were installed and parse cleanly via the runner loader.
    from nowing_evals.suites.chat.regression.runner import _load_cases

    data_dir = tmp_path / "data"
    cases_path = data_dir / "chat" / "regression" / "cases.jsonl"
    assert cases_path.is_file()
    cases = _load_cases(cases_path)
    assert {c.case_id for c in cases} == {"prod-1", "prod-2"}
    assert cases[0].mentioned_document_ids == [10, 20]
    assert cases[1].tags == ["document"]
    assert cases[1].mentioned_document_ids == [5]
    assert cases[1].disabled_tools == ["web_search"]
