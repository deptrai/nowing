"""Unit tests for GitHubConnector ingestion and validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.github_connector import GitHubConnector

pytestmark = pytest.mark.unit


class TestGitHubConnectorValidation:
    """Validation of repo/branch names to prevent command injection."""

    def test_rejects_repo_with_path_traversal(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("owner/../etc/passwd") is None

    def test_rejects_repo_with_shell_metacharacters(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("owner; rm -rf /") is None

    def test_rejects_repo_with_url_fragment(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("owner/repo#branch") is None

    def test_rejects_repo_without_slash(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("owner") is None

    def test_rejects_repo_with_leading_dot(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("-/.config") is None

    def test_rejects_invalid_branch_name(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("owner/repo", branch="main;whoami") is None

    def test_rejects_branch_with_newline(self):
        connector = GitHubConnector()
        assert connector.ingest_repository("owner/repo", branch="main\n--output") is None

    def test_accepts_valid_repo_and_branch(self):
        connector = GitHubConnector()
        with (
            patch("subprocess.run") as mock_run,
            patch.object(Path, "is_file", return_value=True),
            patch(
                "app.connectors.github_connector.open",
                MagicMock(return_value=MagicMock(read=MagicMock(return_value="content"))),
            ),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            mock_run.return_value.stderr = ""
            result = connector.ingest_repository("owner/repo", branch="v1.0.0")

        assert result is not None
        assert result.repo_full_name == "owner/repo"
        assert result.branch == "v1.0.0"

        call = mock_run.call_args
        args = call[0][0]
        assert args[0] == "gitingest"
        assert args[1] == "https://github.com/owner/repo"
        assert "--branch" in args
        assert "v1.0.0" in args


class TestGitHubConnectorSubprocess:
    """Subprocess safety: list args, no shell=True, timeout, and token env."""

    @patch("tempfile.NamedTemporaryFile")
    @patch("app.connectors.github_connector.open")
    @patch("os.unlink")
    @patch("os.environ")
    def test_uses_safe_subprocess_list_and_timeout(
        self, _mock_env, _mock_unlink, mock_open, mock_temp
    ):
        mock_temp.return_value.__enter__.return_value.name = "/tmp/fake.txt"
        mock_open.return_value.__enter__.return_value.read.return_value = "# content"

        with (
            patch("subprocess.run") as mock_run,
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "exists", return_value=True),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            mock_run.return_value.stderr = ""
            connector = GitHubConnector(token="ghp_secret")
            connector.ingest_repository("owner/repo", branch="main")

        call = mock_run.call_args
        assert call[1].get("shell") is not True
        assert call[1].get("timeout") == 900
        assert isinstance(call[0][0], list)

