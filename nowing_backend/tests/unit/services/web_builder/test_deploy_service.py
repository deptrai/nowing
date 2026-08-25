import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace, WorkspaceApp
from app.services.web_builder.deploy_service import (
    WebAppDeployService,
    disambiguate_slug,
)


@pytest.fixture(autouse=True)
def mock_deploy_locks():
    with patch.object(
        WebAppDeployService, "_acquire_lock", new_callable=AsyncMock
    ) as mock_acq, patch.object(
        WebAppDeployService, "_release_lock", new_callable=AsyncMock
    ):
        mock_acq.return_value = asyncio.Lock()
        yield


@pytest.mark.unit
class TestWebAppDeployDisambiguation:
    """Unit tests for DNS label and slug disambiguation logic."""

    def test_disambiguate_slug_simple_unique(self):
        slug = disambiguate_slug("my-app", existing_slugs=set())
        assert slug == "my-app"

    def test_disambiguate_slug_sanitizes_special_characters(self):
        slug = disambiguate_slug("My Super App! @ Launch", existing_slugs=set())
        assert slug == "my-super-app-launch"

    def test_disambiguate_slug_resolves_collision(self):
        existing = {"my-app", "my-app-1"}
        slug = disambiguate_slug("my-app", existing_slugs=existing)
        assert slug == "my-app-2"

    def test_disambiguate_slug_enforces_max_length(self):
        long_name = "a" * 100
        slug = disambiguate_slug(long_name, existing_slugs=set(), max_length=63)
        assert len(slug) <= 63

    def test_disambiguate_slug_handles_empty_or_symbols_only(self):
        slug = disambiguate_slug("!@#$%^", existing_slugs=set())
        assert slug == "app"

    def test_disambiguate_slug_preserves_natural_number_when_unique(self):
        slug = disambiguate_slug("route-66", existing_slugs=set())
        assert slug == "route-66"

        colliding_slug = disambiguate_slug("route-66", existing_slugs={"route-66"})
        assert colliding_slug == "route-1"


@pytest.mark.unit
class TestWebAppDeployServiceCore:
    """Unit tests for WebAppDeployService publishing flow."""

    @pytest.fixture
    def deploy_service(self):
        return WebAppDeployService(base_domain="apps.nowing.net")

    @pytest.fixture
    def mock_db_session(self):
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        return session

    def _make_storage(self, tmpdir: str, workspace_id: int = 1, app_id: str = "app-123"):
        """Create a realistic scoped project directory under a temp storage root."""
        storage_root = Path(tmpdir)
        project_dir = storage_root / "web-app" / str(workspace_id) / app_id
        project_dir.mkdir(parents=True)
        return storage_root, project_dir

    @pytest.mark.asyncio
    async def test_deploy_app_workspace_not_found_or_disabled(
        self, deploy_service, mock_db_session
    ):
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        out = await deploy_service.deploy_app(
            app_id="app-123",
            workspace_id=999,
            session=mock_db_session,
        )
        assert out.status == "deploy_failed"
        assert "Web Builder is not enabled" in out.message

    @pytest.mark.asyncio
    async def test_deploy_app_missing_source_fails(
        self, deploy_service, mock_db_session
    ):
        ws = Workspace(id=1, name="Test WS", web_builder_enabled=True)
        app = WorkspaceApp(
            id="app-123",
            workspace_id=1,
            name="Missing App",
            slug="missing-app",
            status="generated",
            storage_path="/non/existent/path/for/app",
        )

        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_res_app = MagicMock()
        mock_res_app.scalars.return_value.first.return_value = app

        mock_db_session.execute.side_effect = [mock_res_ws, mock_res_app]

        out = await deploy_service.deploy_app(
            app_id="app-123",
            workspace_id=1,
            session=mock_db_session,
        )
        assert out.status == "deploy_failed"
        assert "source directory is missing" in out.message

    @pytest.mark.asyncio
    async def test_deploy_app_success(self, deploy_service, mock_db_session, tmp_path):
        storage_root, project_dir = self._make_storage(str(tmp_path))
        public_apps_dir = storage_root / "web-apps" / "pulse-ai-landing"
        public_apps_dir.mkdir(parents=True)

        (project_dir / "app").mkdir()
        (project_dir / "app" / "page.tsx").write_text(
            "export default function Home() { return <h1>PulseAI</h1>; }"
        )
        (project_dir / ".next").mkdir()
        (project_dir / ".next" / "standalone").mkdir()
        (project_dir / ".next" / "standalone" / "index.html").write_text(
            "<html><body>Hello</body></html>"
        )
        (project_dir / "package.json").write_text(
            '{"name": "test-app", "scripts": {"build": "next build"}}'
        )

        ws = Workspace(id=1, name="Test WS", web_builder_enabled=True)
        app = WorkspaceApp(
            id="app-123",
            workspace_id=1,
            user_id="user-001",
            name="PulseAI SaaS Landing",
            slug="pulse-ai-landing",
            status="preview_ready",
            storage_path=str(project_dir),
        )

        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_res_app = MagicMock()
        mock_res_app.scalars.return_value.first.return_value = app
        mock_res_slugs = MagicMock()
        mock_res_slugs.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_res_ws,
            mock_res_app,
            mock_res_slugs,
        ]

        with patch(
            "app.services.web_builder.deploy_service.record_token_usage",
            new_callable=AsyncMock,
        ) as mock_record_usage, patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(storage_root)
        ), patch(
            "app.config.config.WEB_BUILDER_PUBLIC_APPS_PATH",
            str(public_apps_dir.parent),
        ):
            out = await deploy_service.deploy_app(
                app_id="app-123",
                workspace_id=1,
                session=mock_db_session,
            )

            assert out.status == "published"
            assert "https://pulse-ai-landing.apps.nowing.net" in out.public_url
            assert out.slug == "pulse-ai-landing"
            assert app.status == "published"
            assert app.container_id is None
            mock_record_usage.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deploy_app_idempotent(self, deploy_service, mock_db_session, tmp_path):
        storage_root, project_dir = self._make_storage(str(tmp_path))
        public_apps_dir = storage_root / "web-apps" / "pulse-ai-landing"
        public_apps_dir.mkdir(parents=True)
        (public_apps_dir / "index.html").write_text("<html>Cached</html>")

        (project_dir / "app.js").write_text("console.log('hi')")

        ws = Workspace(id=1, name="Test WS", web_builder_enabled=True)
        app = WorkspaceApp(
            id="app-123",
            workspace_id=1,
            name="PulseAI SaaS Landing",
            slug="pulse-ai-landing",
            status="published",
            public_url="https://pulse-ai-landing.apps.nowing.net",
            storage_path=str(project_dir),
        )

        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_res_app = MagicMock()
        mock_res_app.scalars.return_value.first.return_value = app
        mock_res_slugs = MagicMock()
        mock_res_slugs.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_res_ws,
            mock_res_app,
            mock_res_slugs,
        ]

        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(storage_root)
        ), patch(
            "app.config.config.WEB_BUILDER_PUBLIC_APPS_PATH",
            str(public_apps_dir.parent),
        ):
            out = await deploy_service.deploy_app(
                app_id="app-123",
                workspace_id=1,
                session=mock_db_session,
                force=False,
            )

            assert out.status == "published"
            assert "already published" in out.message.lower()


@pytest.mark.unit
class TestCustomDomainValidation:
    """Unit tests for Custom Domain CNAME validation & DNS proof-of-control."""

    @pytest.fixture
    def deploy_service(self):
        return WebAppDeployService(base_domain="apps.nowing.net")

    @pytest.fixture
    def mock_db_session(self):
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_custom_domain_syntax_validation(self, deploy_service):
        # Invalid: IP address
        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="app-1",
            workspace_id=1,
            custom_domain="192.168.1.1",
        )
        assert out.status == "failed"

        # Invalid: Localhost
        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="app-1",
            workspace_id=1,
            custom_domain="localhost",
        )
        assert out.status == "failed"

        # Invalid: Malformed symbols
        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="app-1",
            workspace_id=1,
            custom_domain="invalid_domain..com",
        )
        assert out.status == "failed"

        # Invalid: System reserved domain
        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="app-1",
            workspace_id=1,
            custom_domain="admin.apps.nowing.net",
        )
        assert out.status == "failed"
        assert "reserved infrastructure domains" in out.message

        # Invalid: too long (> 255)
        long_domain = "a" * 250 + ".com"
        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="app-1",
            workspace_id=1,
            custom_domain=long_domain,
        )
        assert out.status == "failed"

    @pytest.mark.asyncio
    async def test_custom_domain_workspace_feature_gate(
        self, deploy_service, mock_db_session
    ):
        ws = Workspace(id=1, name="Test WS", web_builder_enabled=False)
        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_db_session.execute.return_value = mock_res_ws

        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="app-1",
            workspace_id=1,
            custom_domain="landing.mybrand.com",
            session=mock_db_session,
        )
        assert out.status == "failed"
        assert "Web Builder is not enabled" in out.message

    @pytest.mark.asyncio
    async def test_custom_domain_cross_workspace_collision(
        self, deploy_service, mock_db_session
    ):
        ws = Workspace(id=1, name="Test WS", web_builder_enabled=True)
        existing_app = WorkspaceApp(
            id="other-app-999",
            workspace_id=2,
            custom_domain="landing.mybrand.com",
            custom_domain_status="active",
        )

        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_collision_res = MagicMock()
        mock_collision_res.scalars.return_value.first.return_value = existing_app

        mock_db_session.execute.side_effect = [mock_res_ws, mock_collision_res]

        out = await deploy_service.verify_and_bind_custom_domain(
            app_id="my-app-1",
            workspace_id=1,
            custom_domain="landing.mybrand.com",
            session=mock_db_session,
        )
        assert out.status == "failed"
        assert "already assigned to another application" in out.message

    @pytest.mark.asyncio
    async def test_dns_cname_verification_success_and_failure(
        self, deploy_service, mock_db_session
    ):
        ws = Workspace(id=1, name="Test WS", web_builder_enabled=True)
        app = WorkspaceApp(
            id="app-1",
            workspace_id=1,
            status="published",
            slug="my-app",
        )

        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_collision_res = MagicMock()
        mock_collision_res.scalars.return_value.first.return_value = None
        mock_app_res = MagicMock()
        mock_app_res.scalars.return_value.first.return_value = app

        mock_db_session.execute.side_effect = [
            mock_res_ws,
            mock_collision_res,
            mock_app_res,
        ]

        # 1. DNS Failure: unpointed CNAME
        with patch.object(
            deploy_service, "_resolve_cname_ingress", return_value=False
        ):
            out = await deploy_service.verify_and_bind_custom_domain(
                app_id="app-1",
                workspace_id=1,
                custom_domain="landing.mybrand.com",
                session=mock_db_session,
            )
            assert out.status == "failed"
            assert "CNAME does not point to" in out.message

        # 2. DNS Success: Points to cname-ingress.apps.nowing.net
        mock_db_session.reset_mock()
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.execute.side_effect = [
            mock_res_ws,
            mock_collision_res,
            mock_app_res,
        ]
        with patch.object(
            deploy_service, "_resolve_cname_ingress", return_value=True
        ):
            out = await deploy_service.verify_and_bind_custom_domain(
                app_id="app-1",
                workspace_id=1,
                custom_domain="landing.mybrand.com",
                session=mock_db_session,
            )
            assert out.status == "active"
            assert app.custom_domain == "landing.mybrand.com"
            assert app.custom_domain_status == "active"
            mock_db_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_custom_domain_not_published_is_pending(
        self, deploy_service, mock_db_session
    ):
        ws = Workspace(id=1, name="Test WS", web_builder_enabled=True)
        app = WorkspaceApp(id="app-1", workspace_id=1, status="generated")

        mock_res_ws = MagicMock()
        mock_res_ws.scalars.return_value.first.return_value = ws
        mock_collision_res = MagicMock()
        mock_collision_res.scalars.return_value.first.return_value = None
        mock_app_res = MagicMock()
        mock_app_res.scalars.return_value.first.return_value = app

        mock_db_session.execute.side_effect = [
            mock_res_ws,
            mock_collision_res,
            mock_app_res,
        ]

        with patch.object(
            deploy_service, "_resolve_cname_ingress", return_value=True
        ):
            out = await deploy_service.verify_and_bind_custom_domain(
                app_id="app-1",
                workspace_id=1,
                custom_domain="landing.mybrand.com",
                session=mock_db_session,
            )
            assert out.status == "pending_verification"
            assert app.custom_domain == "landing.mybrand.com"
            assert app.custom_domain_status == "pending_verification"


@pytest.mark.unit
class TestDynamicIngressGeneration:
    """Unit tests for Traefik and Caddy routing config generation."""

    def test_generate_traefik_labels(self):
        labels = WebAppDeployService.generate_traefik_labels(
            app_slug="pulse-ai",
            base_domain="apps.nowing.net",
            port=3000,
            custom_domain="landing.pulseai.io",
        )
        assert labels["traefik.enable"] == "true"
        assert (
            "Host(`pulse-ai.apps.nowing.net`)"
            in labels["traefik.http.routers.nowing-app-pulse-ai.rule"]
        )
        assert (
            "Host(`landing.pulseai.io`)"
            in labels["traefik.http.routers.nowing-app-pulse-ai.rule"]
        )
        assert (
            labels["traefik.http.services.nowing-app-pulse-ai.loadbalancer.server.port"]
            == "3000"
        )

    def test_generate_caddy_snippet(self):
        snippet = WebAppDeployService.generate_caddy_snippet(
            app_slug="pulse-ai",
            container_target="nowing-app-1-pulse-ai:3000",
            base_domain="apps.nowing.net",
            custom_domain="landing.pulseai.io",
        )
        assert "pulse-ai.apps.nowing.net, landing.pulseai.io" in snippet
        assert "reverse_proxy nowing-app-1-pulse-ai:3000" in snippet


@pytest.mark.unit
class TestContainerDeployLifecycle:
    """Unit tests for the Docker container deploy path."""

    @pytest.fixture
    def deploy_service(self):
        return WebAppDeployService(base_domain="apps.nowing.net")

    @pytest.mark.asyncio
    async def test_deploy_container_missing_standalone_fails(self, deploy_service, tmp_path):
        project_dir = tmp_path / "web-app" / "1" / "app-123"
        project_dir.mkdir(parents=True)

        with pytest.raises(RuntimeError, match="standalone/server.js"):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )

    @pytest.mark.asyncio
    async def test_deploy_container_path_traversal_rejected(self, deploy_service, tmp_path):
        with pytest.raises((RuntimeError, ValueError), match="Invalid application storage path"):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=Path("/etc/shadow"),
                slug="my-app",
            )

    @pytest.mark.asyncio
    async def test_deploy_container_builds_and_runs_container(self, deploy_service, tmp_path):
        from app.config import config as app_config

        project_dir = tmp_path / "web-app" / "1" / "app-123"
        project_dir.mkdir(parents=True)
        standalone = project_dir / ".next" / "standalone"
        standalone.mkdir(parents=True)
        (standalone / "server.js").write_text("// mock")

        with patch("app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)):

            def make_proc(returncode=0, stdout=b"abc123def456"):
                proc = AsyncMock()
                proc.returncode = returncode
                proc.communicate = AsyncMock(return_value=(stdout, b""))
                proc.kill = MagicMock()
                return proc

            build_proc = make_proc(0)
            rm_proc = make_proc(0)
            run_proc = make_proc(0, b"container-id-123")

            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=[build_proc, rm_proc, run_proc],
            ), patch.object(
                deploy_service,
                "_healthcheck_container",
                new_callable=AsyncMock,
                return_value=True,
            ):
                container_id, port = await deploy_service.deploy_container(
                    app_id="app-123",
                    workspace_id=1,
                    project_path=project_dir,
                    slug="my-app",
                )
                assert container_id == "container-id"
                assert port == 3000

                # The build timeout is taken from config.
                build_call = build_proc.communicate.await_args
                assert build_call is not None

                # The run command should include security/resource limits and the dokploy network.
                run_args, _ = run_proc.communicate.call_args
                run_cmd = asyncio.create_subprocess_exec.call_args_list[2][0]
                cmd = " ".join(run_cmd)
                assert "--memory=512m" in cmd
                assert "--cpus=0.5" in cmd
                assert "--pids-limit=100" in cmd
                assert "--security-opt=no-new-privileges" in cmd
                assert f"--network {app_config.WEB_BUILDER_DOKPLOY_NETWORK}" in cmd
                assert "traefik.enable=true" in cmd

    @pytest.mark.asyncio
    async def test_deploy_container_healthcheck_failure_cleans_up(self, deploy_service, tmp_path):
        project_dir = tmp_path / "web-app" / "1" / "app-123"
        project_dir.mkdir(parents=True)
        standalone = project_dir / ".next" / "standalone"
        standalone.mkdir(parents=True)
        (standalone / "server.js").write_text("// mock")

        with patch("app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)):

            def make_proc(returncode=0, stdout=b"", rm_ok=True):
                proc = AsyncMock()
                proc.returncode = returncode
                proc.communicate = AsyncMock(return_value=(stdout, b""))
                proc.kill = MagicMock()
                return proc

            build_proc = make_proc(0)
            rm_proc = make_proc(0)
            run_proc = make_proc(0, b"container-id-123")
            cleanup_proc = make_proc(0)

            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=[build_proc, rm_proc, run_proc, cleanup_proc],
            ), patch.object(
                deploy_service,
                "_healthcheck_container",
                new_callable=AsyncMock,
                return_value=False,
            ):
                with pytest.raises(RuntimeError, match="failed healthcheck"):
                    await deploy_service.deploy_container(
                        app_id="app-123",
                        workspace_id=1,
                        project_path=project_dir,
                        slug="my-app",
                    )

                # A cleanup docker rm -f should have been issued after the failed healthcheck.
                calls = [
                    " ".join(c[0]) for c in asyncio.create_subprocess_exec.call_args_list
                ]
                assert any("docker" in c and "rm" in c and "-f" in c for c in calls[1:])
