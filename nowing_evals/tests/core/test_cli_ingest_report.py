"""CLI ingest/report for no-auth/no-setup suites (Story 4.8)."""

from __future__ import annotations

from nowing_evals.core.cli import main


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
