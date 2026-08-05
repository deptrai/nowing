"""CLI ingest/report for no-auth/no-setup suites (Story 4.8)."""

from __future__ import annotations

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
