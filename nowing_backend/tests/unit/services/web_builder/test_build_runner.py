"""Unit tests for BuilderService (Story 27.1b: Web App Build & Preview Runner).

Acceptance Criteria:
- AC-2: Build & Preview Runner (npm ci --ignore-scripts + next build standalone, logs, status transitions).
- AC-3: Workspace-Scoped App Registry & Cost Observability (TokenUsage web_builder_build).
- NFR-2: Security (path traversal prevention, --ignore-scripts, timeout, concurrency semaphore).

TDD Phase: RED (Scaffolds for BuilderService).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]


class TestBuilderServiceCore:
    """AC-2: Core build runner execution and lifecycle."""

    @pytest.mark.asyncio
    async def test_build_project_success(self, tmp_path: Path):
        """AC-2: Given a valid generated Next.js project, BuilderService runs npm ci + next build and transitions to preview_ready."""
        from app.db import WorkspaceApp
        from app.services.web_builder.builder import BuilderService, BuildResult

        storage_root = tmp_path / "storage"
        app_id = "test-app-success"
        workspace_id = 1
        project_dir = storage_root / "web-app" / str(workspace_id) / app_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "package.json").write_text(
            '{"name": "test-app"}', encoding="utf-8"
        )
        (project_dir / "next.config.js").write_text(
            "module.exports = { output: 'standalone' };", encoding="utf-8"
        )

        mock_session = AsyncMock()
        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=workspace_id,
            name="Test App",
            slug="test-app",
            status="generated",
            storage_path=str(project_dir),
        )

        service = BuilderService(storage_base_path=str(storage_root))

        mock_proc_install = AsyncMock()
        mock_proc_install.communicate.return_value = (b"added 50 packages", b"")
        mock_proc_install.returncode = 0

        mock_proc_build = AsyncMock()
        mock_proc_build.communicate.return_value = (
            b"Compiled successfully\nOutput: standalone",
            b"",
        )
        mock_proc_build.returncode = 0

        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=[mock_proc_install, mock_proc_build],
            ),
            patch.object(
                service, "_record_token_usage", new_callable=AsyncMock
            ) as mock_usage,
        ):
            result = await service.build_project(
                app_id=app_id,
                workspace_id=workspace_id,
                project_dir=project_dir,
                app_entity=mock_app,
                session=mock_session,
            )

        assert isinstance(result, BuildResult)
        assert result.status == "preview_ready"
        assert result.success is True
        assert mock_app.status == "preview_ready"
        assert (project_dir / ".next" / "build.log").exists()
        log_content = (project_dir / ".next" / "build.log").read_text(encoding="utf-8")
        assert "Compiled successfully" in log_content
        mock_usage.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_build_project_failure_compilation_error(self, tmp_path: Path):
        """AC-2: Given build errors in project, BuilderService marks status as build_failed and persists logs."""
        from app.db import WorkspaceApp
        from app.services.web_builder.builder import BuilderService, BuildResult

        storage_root = tmp_path / "storage"
        app_id = "test-app-fail"
        workspace_id = 1
        project_dir = storage_root / "web-app" / str(workspace_id) / app_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "package.json").write_text(
            '{"name": "test-app"}', encoding="utf-8"
        )

        mock_session = AsyncMock()
        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=workspace_id,
            name="Test App Fail",
            slug="test-app-fail",
            status="generated",
            storage_path=str(project_dir),
        )

        service = BuilderService(storage_base_path=str(storage_root))

        mock_proc_install = AsyncMock()
        mock_proc_install.communicate.return_value = (b"npm ci ok", b"")
        mock_proc_install.returncode = 0

        mock_proc_build = AsyncMock()
        mock_proc_build.communicate.return_value = (
            b"",
            b"Error: Type error in app/page.tsx: Property 'x' does not exist",
        )
        mock_proc_build.returncode = 1

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=[mock_proc_install, mock_proc_build],
        ):
            result = await service.build_project(
                app_id=app_id,
                workspace_id=workspace_id,
                project_dir=project_dir,
                app_entity=mock_app,
                session=mock_session,
            )

        assert isinstance(result, BuildResult)
        assert result.status == "build_failed"
        assert result.success is False
        assert mock_app.status == "build_failed"
        assert "Type error in app/page.tsx" in (mock_app.error_message or "")
        assert (project_dir / ".next" / "build.log").exists()

    @pytest.mark.asyncio
    async def test_build_project_timeout_handling(self, tmp_path: Path):
        """AC-2 & NFR-1: Given build exceeding timeout, BuilderService cancels subprocess and flags build_failed."""
        from app.db import WorkspaceApp
        from app.services.web_builder.builder import BuilderService

        storage_root = tmp_path / "storage"
        app_id = "test-app-timeout"
        workspace_id = 1
        project_dir = storage_root / "web-app" / str(workspace_id) / app_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "package.json").write_text(
            '{"name": "test-app"}', encoding="utf-8"
        )

        mock_session = AsyncMock()
        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=workspace_id,
            name="Test App Timeout",
            slug="test-app-timeout",
            status="generated",
            storage_path=str(project_dir),
        )

        service = BuilderService(
            storage_base_path=str(storage_root), build_timeout_seconds=1
        )

        async def fake_slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        mock_proc = AsyncMock()
        mock_proc.communicate = fake_slow_communicate
        mock_proc.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.build_project(
                app_id=app_id,
                workspace_id=workspace_id,
                project_dir=project_dir,
                app_entity=mock_app,
                session=mock_session,
            )

        assert result.status == "build_failed"
        assert (
            "timed out" in (mock_app.error_message or "").lower()
            or "timeout" in (result.error or "").lower()
        )
        assert mock_app.status == "build_failed"


class TestBuilderSecurityAndConcurrency:
    """NFR-2: Path traversal security, script execution sandbox, and concurrency bounds."""

    @pytest.mark.asyncio
    async def test_build_project_path_traversal_rejection(self, tmp_path: Path):
        """Security: Path outside scoped workspace storage is rejected immediately with ValueError."""
        from app.db import WorkspaceApp
        from app.services.web_builder.builder import BuilderService

        storage_root = tmp_path / "storage"
        storage_root.mkdir(parents=True, exist_ok=True)

        service = BuilderService(storage_base_path=str(storage_root))
        malicious_path = Path("/etc/shadow")
        mock_session = AsyncMock()
        mock_app = WorkspaceApp(id="app-evil", workspace_id=1, status="generated")

        with pytest.raises(
            ValueError, match=r"Path traversal|Invalid project directory"
        ):
            await service.build_project(
                app_id="app-evil",
                workspace_id=1,
                project_dir=malicious_path,
                app_entity=mock_app,
                session=mock_session,
            )

    @pytest.mark.asyncio
    async def test_build_enforces_ignore_scripts_flag(self, tmp_path: Path):
        """Security: npm install/ci must always be executed with --ignore-scripts."""
        from app.db import WorkspaceApp
        from app.services.web_builder.builder import BuilderService

        storage_root = tmp_path / "storage"
        app_id = "test-app-scripts"
        workspace_id = 1
        project_dir = storage_root / "web-app" / str(workspace_id) / app_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "package.json").write_text(
            '{"name": "test-app"}', encoding="utf-8"
        )

        mock_session = AsyncMock()
        mock_app = WorkspaceApp(
            id=app_id, workspace_id=workspace_id, status="generated"
        )
        service = BuilderService(storage_base_path=str(storage_root))

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"ok", b"")
        mock_proc.returncode = 0

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_exec,
            patch.object(service, "_record_token_usage", new_callable=AsyncMock),
        ):
            await service.build_project(
                app_id=app_id,
                workspace_id=workspace_id,
                project_dir=project_dir,
                app_entity=mock_app,
                session=mock_session,
            )

        for call in mock_exec.call_args_list:
            args = call[0]
            if "npm" in args[0] or "pnpm" in args[0]:
                assert "--ignore-scripts" in args

    @pytest.mark.asyncio
    async def test_build_concurrency_semaphore(self, tmp_path: Path):
        """NFR-1 & NFR-2: BuilderService bounds concurrent builds with Semaphore."""
        from app.services.web_builder.builder import BuilderService

        storage_root = tmp_path / "storage"
        service = BuilderService(
            storage_base_path=str(storage_root), max_concurrent_builds=2
        )
        assert service.semaphore._value == 2


class TestBuilderCostObservability:
    """AC-3: TokenUsage & cost observability."""

    @pytest.mark.asyncio
    async def test_record_token_usage_web_builder_build(self, tmp_path: Path):
        """AC-3: BuilderService records TokenUsage with usage_type='web_builder_build'."""
        from app.db import TokenUsage
        from app.services.web_builder.builder import BuilderService

        service = BuilderService(storage_base_path=str(tmp_path))
        mock_session = AsyncMock()

        await service._record_token_usage(
            workspace_id=1,
            app_id="test-app-cost",
            cost_micros=50000,
            session=mock_session,
        )

        mock_session.add.assert_called_once()
        added_record = mock_session.add.call_args[0][0]
        assert isinstance(added_record, TokenUsage)
        assert added_record.workspace_id == 1
        assert added_record.usage_type == "web_builder_build"
        assert added_record.cost_micros == 50000


class TestBuilderSecurityHardening:
    """NFR-2 & Security Sandbox: Config audit & Environment Scrubbing."""

    @pytest.mark.asyncio
    async def test_build_project_security_audit_rejection(self, tmp_path: Path):
        """Security: BuilderService rejects projects containing malicious child_process/eval in config files."""
        from app.db import WorkspaceApp
        from app.services.web_builder.builder import BuilderService, BuildResult

        storage_root = tmp_path / "storage"
        app_id = "test-app-malicious"
        workspace_id = 1
        project_dir = storage_root / "web-app" / str(workspace_id) / app_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "package.json").write_text(
            '{"name": "malicious-app"}', encoding="utf-8"
        )
        (project_dir / "next.config.js").write_text(
            "const { execSync } = require('child_process'); execSync('curl leak'); module.exports = {};",
            encoding="utf-8",
        )

        mock_session = AsyncMock()
        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=workspace_id,
            name="Malicious App",
            slug="malicious-app",
            status="generated",
            storage_path=str(project_dir),
        )

        service = BuilderService(storage_base_path=str(storage_root))
        result = await service.build_project(
            app_id=app_id,
            workspace_id=workspace_id,
            project_dir=project_dir,
            app_entity=mock_app,
            session=mock_session,
        )

        assert isinstance(result, BuildResult)
        assert result.status == "build_failed"
        assert result.success is False
        assert "Security audit failed" in (result.error or "")
        assert mock_app.status == "build_failed"

    def test_build_environment_sanitization(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Security: Sanitized environment scrubs all database, auth, and secret keys from subprocess."""
        from app.services.web_builder.builder import BuilderService

        monkeypatch.setenv(
            "DATABASE_URL", "postgresql+asyncpg://postgres:secret@localhost:5434/nowing"
        )
        monkeypatch.setenv("SECRET_KEY", "super-secret-production-key")
        monkeypatch.setenv("CHAINLENS_API_KEY", "cl_live_key_123")
        monkeypatch.setenv("REDIS_URL", "redis://:pass@localhost:6380/0")

        service = BuilderService(storage_base_path=str(tmp_path))
        safe_env = service._get_sanitized_build_env(tmp_path)

        assert "DATABASE_URL" not in safe_env
        assert "SECRET_KEY" not in safe_env
        assert "CHAINLENS_API_KEY" not in safe_env
        assert "REDIS_URL" not in safe_env
        assert safe_env.get("NODE_ENV") == "production"
        assert safe_env.get("NEXT_TELEMETRY_DISABLED") == "1"
