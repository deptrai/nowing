import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.web_builder import get_web_builder_tier_limits
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

        with pytest.raises(RuntimeError, match=r"standalone/server\.js"):
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

                # The run command should include tier-scoped cgroup limits
                # (no plan_tier -> free defaults), hardening flags, and the
                # configured app network.
                run_cmd = asyncio.create_subprocess_exec.call_args_list[2][0]
                cmd = " ".join(run_cmd)
                assert "--memory=256m" in cmd
                assert "--memory-swap=256m" in cmd
                assert "--cpus=0.25" in cmd
                assert "--pids-limit=50" in cmd
                assert "--cap-drop=ALL" in cmd
                assert "--read-only" in cmd
                assert "--tmpfs /tmp:rw,noexec,nosuid,size=64m" in cmd
                assert "--security-opt=no-new-privileges" in cmd
                assert f"--network {app_config.WEB_BUILDER_DOKPLOY_NETWORK}" in cmd
                assert "traefik.enable=true" in cmd
                assert "docker.sock" not in cmd
                assert "--cap-add" not in cmd

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
            # .State snapshot inspect runs BEFORE the rm -f cleanup.
            inspect_proc = make_proc(0, b"unhealthy|false|1|false|boom")
            cleanup_proc = make_proc(0)

            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=[build_proc, rm_proc, run_proc, inspect_proc, cleanup_proc],
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


@pytest.mark.unit
class TestWebBuilderTierLimits:
    """Story 31.1 AC-1: get_web_builder_tier_limits resolves cgroup quotas."""

    def test_free_tier_exact_values(self):
        assert get_web_builder_tier_limits("free") == {
            "memory": "256m",
            "cpus": "0.25",
            "pids_limit": 50,
        }

    def test_paid_tier_exact_values(self):
        assert get_web_builder_tier_limits("team") == {
            "memory": "512m",
            "cpus": "0.5",
            "pids_limit": 100,
        }
        assert get_web_builder_tier_limits("growth") == {
            "memory": "1024m",
            "cpus": "1.0",
            "pids_limit": 200,
        }
        assert get_web_builder_tier_limits("enterprise") == {
            "memory": "2048m",
            "cpus": "2.0",
            "pids_limit": 400,
        }

    @pytest.mark.parametrize("tier", [None, "", "   ", "platinum"])
    def test_unknown_or_empty_tier_falls_back_to_free(self, tier):
        assert get_web_builder_tier_limits(tier) == {
            "memory": "256m",
            "cpus": "0.25",
            "pids_limit": 50,
        }

    def test_uppercase_tier_normalized(self):
        limits = get_web_builder_tier_limits("ENTERPRISE")
        assert limits["memory"] == "2048m"
        assert limits["cpus"] == "2.0"
        assert limits["pids_limit"] == 400

    def test_malformed_env_map_falls_back_with_warning(
        self, monkeypatch, caplog
    ):
        monkeypatch.setenv("WEB_BUILDER_TIER_MEMORY_MAP", "{bad")
        with caplog.at_level(logging.WARNING):
            limits = get_web_builder_tier_limits("growth")
        assert limits == {"memory": "1024m", "cpus": "1.0", "pids_limit": 200}
        assert any(
            "WEB_BUILDER_TIER_MEMORY_MAP" in record.getMessage()
            for record in caplog.records
        )

    def test_partial_env_override_only_changes_one_key(self, monkeypatch):
        monkeypatch.setenv("WEB_BUILDER_TIER_CPUS_MAP", '{"growth": "1.5"}')
        growth = get_web_builder_tier_limits("growth")
        assert growth["cpus"] == "1.5"
        assert growth["memory"] == "1024m"
        assert growth["pids_limit"] == 200
        # Untouched tiers keep code defaults.
        assert get_web_builder_tier_limits("free")["cpus"] == "0.25"
        assert get_web_builder_tier_limits("team")["cpus"] == "0.5"

    def test_unknown_tier_key_in_env_map_ignored(self, monkeypatch):
        monkeypatch.setenv("WEB_BUILDER_TIER_MEMORY_MAP", '{"platinum": "999m"}')
        assert get_web_builder_tier_limits("free")["memory"] == "256m"
        assert get_web_builder_tier_limits("growth")["memory"] == "1024m"

    def test_invalid_pids_override_falls_back(self, monkeypatch, caplog):
        monkeypatch.setenv("WEB_BUILDER_TIER_PIDS_MAP", '{"free": "not-a-number"}')
        with caplog.at_level(logging.WARNING):
            limits = get_web_builder_tier_limits("free")
        assert limits["pids_limit"] == 50
        assert any(
            "WEB_BUILDER_TIER_PIDS_MAP" in record.getMessage()
            for record in caplog.records
        )

    @pytest.mark.parametrize("bad_pids", ["0", "-1", "0", 0, -1, 99999999])
    def test_out_of_range_pids_override_falls_back(self, monkeypatch, bad_pids):
        monkeypatch.setenv(
            "WEB_BUILDER_TIER_PIDS_MAP", json.dumps({"free": bad_pids})
        )
        # 0/-1 would disable the pids cap entirely; huge values exceed the
        # kernel ceiling — all fall back to the tier default.
        assert get_web_builder_tier_limits("free")["pids_limit"] == 50

    @pytest.mark.parametrize("bad_memory", ["abc", "256", "-1g", "1.5g", ""])
    def test_memory_override_requires_unit_suffix(self, monkeypatch, bad_memory):
        monkeypatch.setenv(
            "WEB_BUILDER_TIER_MEMORY_MAP", json.dumps({"free": bad_memory})
        )
        # A bare number would be bytes on docker run — rejected; so is junk.
        assert get_web_builder_tier_limits("free")["memory"] == "256m"

    @pytest.mark.parametrize("bad_cpus", ["abc", "0", "-0.5", "", 0, -2])
    def test_non_positive_cpus_override_falls_back(self, monkeypatch, bad_cpus):
        monkeypatch.setenv(
            "WEB_BUILDER_TIER_CPUS_MAP", json.dumps({"free": bad_cpus})
        )
        assert get_web_builder_tier_limits("free")["cpus"] == "0.25"

    def test_env_map_keys_are_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("WEB_BUILDER_TIER_CPUS_MAP", '{"Growth": "1.5"}')
        assert get_web_builder_tier_limits("growth")["cpus"] == "1.5"

    def test_unknown_tier_fallback_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            limits = get_web_builder_tier_limits("platinum")
        assert limits["memory"] == "256m"
        assert any(
            "platinum" in record.getMessage()
            or "Unknown plan_tier" in record.getMessage()
            for record in caplog.records
        )


@pytest.mark.unit
class TestContainerCgroupAndIsolation:
    """Story 31.1 AC-2/3/4: run_cmd flags, network isolation, inspect health."""

    @pytest.fixture
    def deploy_service(self):
        return WebAppDeployService(base_domain="apps.nowing.net")

    @staticmethod
    def _make_standalone(tmp_path: Path, workspace_id: int = 1, app_id: str = "app-123") -> Path:
        project_dir = tmp_path / "web-app" / str(workspace_id) / app_id
        standalone = project_dir / ".next" / "standalone"
        standalone.mkdir(parents=True)
        (standalone / "server.js").write_text("// mock")
        return project_dir

    @staticmethod
    def _proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        proc = AsyncMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(stdout, stderr))
        proc.kill = MagicMock()
        return proc

    def _docker_router(
        self,
        inspect_stdout: bytes = b"healthy|true|0|false|",
        run_returncode: int = 0,
        run_stderr: bytes = b"",
    ):
        """Route docker CLI argv to canned procs; returns (calls, side_effect)."""
        calls: list[list[str]] = []

        def _router(*args, **kwargs):
            argv = [str(a) for a in args]
            calls.append(argv)
            sub = argv[1] if len(argv) > 1 else ""
            if sub == "run":
                return self._proc(run_returncode, b"container-id-123", run_stderr)
            if sub == "inspect":
                return self._proc(0, inspect_stdout)
            return self._proc(0)

        return calls, _router

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "tier,memory,cpus,pids",
        [
            ("free", "256m", "0.25", "50"),
            ("team", "512m", "0.5", "100"),
            ("growth", "1024m", "1.0", "200"),
            ("enterprise", "2048m", "2.0", "400"),
        ],
    )
    async def test_run_cmd_uses_tier_limits(
        self, deploy_service, tmp_path, tier, memory, cpus, pids
    ):
        project_dir = self._make_standalone(tmp_path)
        calls, router = self._docker_router()
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
                plan_tier=tier,
            )
        run_cmd = next(c for c in calls if len(c) > 1 and c[1] == "run")
        cmd = " ".join(run_cmd)
        assert f"--memory={memory}" in cmd
        # --memory-swap is EXACTLY --memory (swap disabled) for every tier.
        assert f"--memory-swap={memory}" in cmd
        assert f"--cpus={cpus}" in cmd
        assert f"--pids-limit={pids}" in cmd

    @pytest.mark.asyncio
    async def test_run_cmd_hardening_flags(self, deploy_service, tmp_path):
        project_dir = self._make_standalone(tmp_path)
        calls, router = self._docker_router()
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
                plan_tier="free",
            )
        run_cmd = next(c for c in calls if len(c) > 1 and c[1] == "run")
        cmd = " ".join(run_cmd)
        assert "-d" in run_cmd
        assert "--restart unless-stopped" in cmd
        assert "--cap-drop=ALL" in cmd
        assert "--security-opt=no-new-privileges" in cmd
        assert "--read-only" in cmd
        assert "--tmpfs /tmp:rw,noexec,nosuid,size=64m" in cmd
        # Writable Next.js ISR/image cache on the read-only rootfs.
        assert "--tmpfs /app/.next/cache:rw,noexec,nosuid,size=128m" in cmd
        # json-file logs bounded so a noisy tenant cannot fill the host disk.
        assert "--log-opt max-size=10m" in cmd
        assert "--log-opt max-file=3" in cmd
        # Never mount the docker socket or any host path; no extra caps.
        assert "docker.sock" not in cmd
        assert "-v" not in run_cmd and "--volume" not in run_cmd
        assert "--cap-add" not in cmd

    @pytest.mark.asyncio
    @pytest.mark.parametrize("empty_value", ["", "   "])
    async def test_empty_network_refuses_deploy(
        self, deploy_service, tmp_path, empty_value
    ):
        project_dir = self._make_standalone(tmp_path)
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_DOKPLOY_NETWORK", empty_value
        ), patch(
            "app.config.config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED", True
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec, pytest.raises(RuntimeError, match="WEB_BUILDER_DOKPLOY_NETWORK"):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        # Refused BEFORE any docker CLI invocation — never lands on docker0.
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("reserved", ["default", "bridge", "host", "none"])
    async def test_reserved_network_refuses_deploy(
        self, deploy_service, tmp_path, reserved
    ):
        project_dir = self._make_standalone(tmp_path)
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_DOKPLOY_NETWORK", reserved
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec, pytest.raises(RuntimeError, match="WEB_BUILDER_DOKPLOY_NETWORK"):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_configured_network_attached(self, deploy_service, tmp_path):
        project_dir = self._make_standalone(tmp_path)
        calls, router = self._docker_router()
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_DOKPLOY_NETWORK", "nowing-web-apps-net"
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        run_cmd = next(c for c in calls if len(c) > 1 and c[1] == "run")
        network_value = run_cmd[run_cmd.index("--network") + 1]
        assert network_value == "nowing-web-apps-net"
        # Never the compose `default` network or shared dokploy-network.
        assert network_value != "default"
        assert "dokploy-network" not in run_cmd

    @pytest.mark.asyncio
    async def test_missing_network_error_surfaces_name(
        self, deploy_service, tmp_path
    ):
        project_dir = self._make_standalone(tmp_path)
        _, router = self._docker_router(
            run_returncode=1,
            run_stderr=b"Error response from daemon: network nowing-web-apps-net not found",
        )
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_DOKPLOY_NETWORK", "nowing-web-apps-net"
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ), pytest.raises(RuntimeError) as exc_info:
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        assert "nowing-web-apps-net" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_healthcheck_polls_inspect_health_status(self, deploy_service):
        calls, router = self._docker_router(b"healthy|true|0|false|")
        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=5, retries=5
            )
        assert ok is True
        inspect_calls = [c for c in calls if len(c) > 1 and c[1] == "inspect"]
        assert inspect_calls, "expected docker inspect polling"
        inspect_cmd = " ".join(inspect_calls[0])
        assert "--format" in inspect_cmd
        assert ".State.Health.Status" in inspect_cmd
        # The container name is only an inspect target — no TCP connect.
        assert "nowing-app-1-my-app" in inspect_calls[0]

    @pytest.mark.asyncio
    async def test_healthcheck_falls_back_to_running_when_no_healthcheck(
        self, deploy_service
    ):
        # Image without HEALTHCHECK: .State.Health renders as <no value>.
        _, router = self._docker_router(b"<no value>|true|0|false|")
        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=5, retries=5
            )
        assert ok is True

    @pytest.mark.asyncio
    async def test_healthcheck_inspect_failure_is_graceful(self, deploy_service):
        def _failing(*args, **kwargs):
            return self._proc(1, b"", b"No such container")

        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=_failing):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=0.3, retries=3
            )
        assert ok is False

    @pytest.mark.asyncio
    async def test_healthcheck_timeout_when_starting(self, deploy_service):
        calls, router = self._docker_router(b"starting|true|0|false|")
        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=0.3, retries=3
            )
        assert ok is False
        assert any(c[1] == "inspect" for c in calls if len(c) > 1)

    @pytest.mark.asyncio
    async def test_oomkilled_startup_surfaces_state_before_cleanup(
        self, deploy_service, tmp_path
    ):
        project_dir = self._make_standalone(tmp_path)
        calls, router = self._docker_router(
            b"unhealthy|false|137|true|Out of memory"
        )
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ), pytest.raises(RuntimeError) as exc_info:
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
                plan_tier="free",
            )
        message = str(exc_info.value)
        assert "OOMKilled" in message
        assert "137" in message
        subs = [c[1] for c in calls if len(c) > 1]
        # The .State inspect snapshot happens BEFORE the final rm -f cleanup.
        last_inspect = max(i for i, s in enumerate(subs) if s == "inspect")
        last_rm = max(i for i, s in enumerate(subs) if s == "rm")
        assert last_inspect < last_rm
        assert subs[-1] == "rm"

    @pytest.mark.asyncio
    async def test_exited_clean_container_counts_as_failure(
        self, deploy_service, tmp_path
    ):
        project_dir = self._make_standalone(tmp_path)
        # Running=false with ExitCode=0 must not be treated as healthy.
        calls, router = self._docker_router(b"<no value>|false|0|false|")
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT", 0.3
        ), patch(
            "app.config.config.WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES", 3
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ), pytest.raises(RuntimeError, match="failed healthcheck"):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        subs = [c[1] for c in calls if len(c) > 1]
        assert subs[-1] == "rm"

    @pytest.mark.asyncio
    async def test_max_length_container_name_passes_safety_guard(
        self, deploy_service, tmp_path
    ):
        """Regression: _container_name can exceed 64 chars (slug max = 63);
        inspect/rm must not refuse it or the container is orphaned."""
        slug = "a" * 63
        project_dir = self._make_standalone(tmp_path)
        container_name = deploy_service._container_name(1, slug)
        assert len(container_name) > 64
        assert deploy_service._is_safe_container_id(container_name)

        calls, router = self._docker_router()
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ):
            container_id, _ = await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug=slug,
            )
        assert container_id == "container-id"
        inspect_calls = [c for c in calls if len(c) > 1 and c[1] == "inspect"]
        assert inspect_calls and inspect_calls[0][-1] == container_name
        rm_calls = [c for c in calls if len(c) > 1 and c[1] == "rm"]
        assert rm_calls and rm_calls[0][-1] == container_name

    def test_oversized_or_metachar_name_still_refused(self, deploy_service):
        assert not deploy_service._is_safe_container_id("x" * 256)
        assert not deploy_service._is_safe_container_id("name; rm -rf /")
        assert not deploy_service._is_safe_container_id("$(whoami)")

    @pytest.mark.asyncio
    async def test_no_healthcheck_fallback_execs_http_probe(self, deploy_service):
        """No-HEALTHCHECK images must prove the :3000 listener via docker
        exec — 'running' alone is not enough."""
        calls, router = self._docker_router(b"<no value>|true|0|false|")
        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=5, retries=5
            )
        assert ok is True
        exec_calls = [c for c in calls if len(c) > 1 and c[1] == "exec"]
        assert exec_calls, "expected a docker exec http probe"
        assert "node" in exec_calls[0] and "127.0.0.1:3000" in " ".join(
            exec_calls[0]
        )

    @pytest.mark.asyncio
    async def test_no_healthcheck_failed_probe_keeps_polling(
        self, deploy_service
    ):
        """A running container whose exec probe exits non-zero is NOT
        healthy — keep polling until the deadline."""
        calls: list[list[str]] = []
        probe_results = iter([1, 1, 0])  # probe fails twice, then passes

        def _router(*args, **kwargs):
            argv = [str(a) for a in args]
            calls.append(argv)
            sub = argv[1] if len(argv) > 1 else ""
            if sub == "inspect":
                return self._proc(0, b"<no value>|true|0|false|")
            if sub == "exec":
                return self._proc(next(probe_results, 0))
            return self._proc(0)

        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=_router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=5, retries=50
            )
        assert ok is True
        assert len([c for c in calls if c[1] == "exec"]) == 3

    @pytest.mark.asyncio
    async def test_dead_window_samples_need_three_consecutive(
        self, deploy_service
    ):
        """A single running=false/nonzero-exit sample can land between
        --restart unless-stopped restarts — it must not fail the deploy."""
        calls: list[list[str]] = []
        states = iter(
            [
                b"<no value>|false|1|false|",  # dead sample 1 (restart gap)
                b"<no value>|false|1|false|",  # dead sample 2
                b"healthy|true|0|false|",      # recovered on next poll
            ]
        )

        def _router(*args, **kwargs):
            argv = [str(a) for a in args]
            calls.append(argv)
            if argv[1] == "inspect":
                return self._proc(0, next(states, b"healthy|true|0|false|"))
            return self._proc(0)

        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=_router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=5, retries=50
            )
        assert ok is True

    @pytest.mark.asyncio
    async def test_persistent_crashloop_fails_after_three_dead_samples(
        self, deploy_service
    ):
        calls: list[list[str]] = []

        def _router(*args, **kwargs):
            argv = [str(a) for a in args]
            calls.append(argv)
            return self._proc(0, b"unhealthy|false|137|true|oom")

        with patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch("asyncio.create_subprocess_exec", side_effect=_router):
            ok = await deploy_service._healthcheck_container(
                "nowing-app-1-my-app", timeout_seconds=30, retries=50
            )
        assert ok is False
        # Failed fast on the 3rd consecutive dead sample, not the deadline.
        assert len([c for c in calls if c[1] == "inspect"]) == 3


@pytest.mark.unit
class TestPerAppNetworkIsolation:
    """Story 31.1: opt-in per-app bridge networks (tenant-vs-tenant)."""

    @pytest.fixture
    def deploy_service(self):
        return WebAppDeployService(base_domain="apps.nowing.net")

    @staticmethod
    def _make_standalone(tmp_path: Path) -> Path:
        project_dir = tmp_path / "web-app" / "1" / "app-123"
        standalone = project_dir / ".next" / "standalone"
        standalone.mkdir(parents=True)
        (standalone / "server.js").write_text("// mock")
        return project_dir

    @staticmethod
    def _proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        proc = AsyncMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(stdout, stderr))
        proc.kill = MagicMock()
        return proc

    def test_app_network_name_sanitizes_and_bounds(self, deploy_service):
        assert (
            deploy_service._app_network_name(1, "app-123")
            == "nowing-app-1-app-123-net"
        )
        # Uppercase / unsafe app_id chars are normalized to [a-z0-9_.-]
        # (underscore is valid; ';' and ' ' each become '-').
        assert (
            deploy_service._app_network_name(1, "APP_X; rm -rf")
            == "nowing-app-1-app_x--rm--rf-net"
        )
        # Bound: total name length never exceeds 255.
        long_name = deploy_service._app_network_name(1, "a" * 300)
        assert len(long_name) <= 255

    def _router(self, network_fail: str | None = None):
        calls: list[list[str]] = []

        def _route(*args, **kwargs):
            argv = [str(a) for a in args]
            calls.append(argv)
            sub = argv[1] if len(argv) > 1 else ""
            if sub == "run":
                return self._proc(0, b"container-id-123")
            if sub == "inspect":
                return self._proc(0, b"healthy|true|0|false|")
            if sub == "network" and network_fail == "already":
                # Idempotent redeploy: net exists, proxy already connected.
                if argv[2] == "create":
                    return self._proc(1, stderr=b"network already exists")
                if argv[2] == "connect":
                    return self._proc(
                        1,
                        stderr=b"container is already connected to network",
                    )
            return self._proc(0)

        return calls, _route

    @pytest.mark.asyncio
    async def test_per_app_network_sequence(self, deploy_service, tmp_path):
        project_dir = self._make_standalone(tmp_path)
        calls, router = self._router()
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_PER_APP_NETWORK", True
        ), patch(
            "app.config.config.WEB_BUILDER_INGRESS_PROXY_CONTAINER",
            "dokploy-traefik",
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ):
            container_id, _ = await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        assert container_id == "container-id"
        app_net = "nowing-app-1-app-123-net"
        net_create = next(
            c for c in calls if c[1:3] == ["network", "create"]
        )
        net_connect = next(
            c for c in calls if c[1:3] == ["network", "connect"]
        )
        assert net_create[-1] == app_net
        assert net_connect[3:] == [app_net, "dokploy-traefik"]
        run_cmd = next(c for c in calls if c[1] == "run")
        assert run_cmd[run_cmd.index("--network") + 1] == app_net
        # Order: network create + connect BEFORE docker run.
        subs = [c[1] for c in calls]
        assert subs.index("network") < subs.index("run")

    @pytest.mark.asyncio
    async def test_per_app_network_idempotent_redeploy(
        self, deploy_service, tmp_path
    ):
        project_dir = self._make_standalone(tmp_path)
        _, router = self._router(network_fail="already")
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_PER_APP_NETWORK", True
        ), patch(
            "app.config.config.WEB_BUILDER_INGRESS_PROXY_CONTAINER",
            "dokploy-traefik",
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=router
        ):
            container_id, _ = await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        assert container_id == "container-id"

    @pytest.mark.asyncio
    async def test_per_app_missing_proxy_container_refuses(
        self, deploy_service, tmp_path
    ):
        project_dir = self._make_standalone(tmp_path)
        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_PER_APP_NETWORK", True
        ), patch(
            "app.config.config.WEB_BUILDER_INGRESS_PROXY_CONTAINER", ""
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec, pytest.raises(
            RuntimeError, match="WEB_BUILDER_INGRESS_PROXY_CONTAINER"
        ):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        # Refused BEFORE any docker CLI call — fail loud, no half-created net.
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_per_app_failure_disconnects_and_removes_network(
        self, deploy_service, tmp_path
    ):
        project_dir = self._make_standalone(tmp_path)
        calls: list[list[str]] = []

        # Force a persistently-dead container so healthcheck fails fast.
        def _dead(*args, **kwargs):
            argv = [str(a) for a in args]
            calls.append(argv)
            sub = argv[1] if len(argv) > 1 else ""
            if sub == "inspect":
                return self._proc(0, b"unhealthy|false|1|false|boom")
            if sub == "run":
                return self._proc(0, b"container-id-123")
            return self._proc(0)

        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ), patch(
            "app.config.config.WEB_BUILDER_PER_APP_NETWORK", True
        ), patch(
            "app.config.config.WEB_BUILDER_INGRESS_PROXY_CONTAINER",
            "dokploy-traefik",
        ), patch(
            "app.config.config.WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT", 2
        ), patch(
            "app.config.config.WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES", 10
        ), patch(
            "shutil.which", return_value="/usr/bin/docker"
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=_dead
        ), pytest.raises(RuntimeError, match="failed healthcheck"):
            await deploy_service.deploy_container(
                app_id="app-123",
                workspace_id=1,
                project_path=project_dir,
                slug="my-app",
            )
        app_net = "nowing-app-1-app-123-net"
        disconnect = [
            c for c in calls if c[1:3] == ["network", "disconnect"]
        ]
        net_rm = [c for c in calls if c[1:3] == ["network", "rm"]]
        assert disconnect and disconnect[0][3:] == [app_net, "dokploy-traefik"]
        assert net_rm and net_rm[0][-1] == app_net
        # Teardown ordering: container rm -f happens before network removal.
        rm_idx = max(i for i, c in enumerate(calls) if c[1] == "rm")
        net_rm_idx = calls.index(net_rm[0])
        assert rm_idx < net_rm_idx


@pytest.mark.unit
class TestDeployCallersThreadPlanTier:
    """Story 31.1 AC-5: both deploy_container callers pass the workspace tier."""

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

    @staticmethod
    def _res(value):
        res = MagicMock()
        res.scalars.return_value.first.return_value = value
        return res

    @pytest.mark.asyncio
    async def test_deploy_app_threads_workspace_plan_tier(
        self, deploy_service, mock_db_session, tmp_path
    ):
        storage_root = tmp_path
        project_dir = storage_root / "web-app" / "1" / "app-123"
        standalone = project_dir / ".next" / "standalone"
        standalone.mkdir(parents=True)
        (standalone / "index.html").write_text("<html>ok</html>")
        public_apps_dir = storage_root / "web-apps"

        ws = Workspace(
            id=1, name="Test WS", web_builder_enabled=True, plan_tier="growth"
        )
        app = WorkspaceApp(
            id="app-123",
            workspace_id=1,
            user_id="user-001",
            name="Tier App",
            slug="tier-app",
            status="preview_ready",
            storage_path=str(project_dir),
        )

        # slug list path uses scalars().all()
        slugs_res = MagicMock()
        slugs_res.scalars.return_value.all.return_value = []
        mock_db_session.execute.side_effect = [
            self._res(ws),
            self._res(app),
            slugs_res,
        ]

        with patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(storage_root)
        ), patch(
            "app.config.config.WEB_BUILDER_PUBLIC_APPS_PATH",
            str(public_apps_dir),
        ), patch(
            "app.config.config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED", True
        ), patch(
            "app.services.web_builder.deploy_service.record_token_usage",
            new_callable=AsyncMock,
        ), patch.object(
            deploy_service,
            "deploy_container",
            new_callable=AsyncMock,
            return_value=("cid-123", 3000),
        ) as mock_deploy:
            out = await deploy_service.deploy_app(
                app_id="app-123",
                workspace_id=1,
                session=mock_db_session,
            )

        assert out.status == "published"
        mock_deploy.assert_awaited_once()
        assert mock_deploy.await_args.kwargs["plan_tier"] == "growth"

    @pytest.mark.asyncio
    async def test_custom_domain_redeploy_threads_plan_tier(
        self, deploy_service, mock_db_session, tmp_path
    ):
        project_dir = tmp_path / "web-app" / "1" / "app-1"
        project_dir.mkdir(parents=True)

        ws = Workspace(
            id=1, name="Test WS", web_builder_enabled=True, plan_tier="growth"
        )
        app = WorkspaceApp(
            id="app-1",
            workspace_id=1,
            status="published",
            slug="my-app",
            storage_path=str(project_dir),
        )
        mock_db_session.execute.side_effect = [
            self._res(ws),
            self._res(None),  # no collision
            self._res(app),
        ]

        with patch.object(
            deploy_service, "_resolve_cname_ingress", return_value=True
        ), patch.object(
            deploy_service,
            "deploy_container",
            new_callable=AsyncMock,
            return_value=("cid-123", 3000),
        ) as mock_deploy, patch(
            "app.config.config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED", True
        ), patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ):
            out = await deploy_service.verify_and_bind_custom_domain(
                app_id="app-1",
                workspace_id=1,
                custom_domain="landing.mybrand.com",
                session=mock_db_session,
            )

        assert out.status == "active"
        mock_deploy.assert_awaited_once()
        assert mock_deploy.await_args.kwargs["plan_tier"] == "growth"

    @pytest.mark.asyncio
    async def test_custom_domain_missing_workspace_falls_back_to_none_tier(
        self, deploy_service, mock_db_session, tmp_path
    ):
        project_dir = tmp_path / "web-app" / "1" / "app-1"
        project_dir.mkdir(parents=True)

        app = WorkspaceApp(
            id="app-1",
            workspace_id=1,
            status="published",
            slug="my-app",
            storage_path=str(project_dir),
        )
        mock_db_session.execute.side_effect = [
            self._res(None),  # workspace row missing
            self._res(None),  # no collision
            self._res(app),
        ]

        with patch.object(
            deploy_service, "_resolve_cname_ingress", return_value=True
        ), patch.object(
            deploy_service,
            "deploy_container",
            new_callable=AsyncMock,
            return_value=("cid-123", 3000),
        ) as mock_deploy, patch(
            "app.config.config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED", True
        ), patch(
            "app.config.config.FILE_STORAGE_LOCAL_PATH", str(tmp_path)
        ):
            out = await deploy_service.verify_and_bind_custom_domain(
                app_id="app-1",
                workspace_id=1,
                custom_domain="landing.mybrand.com",
                session=mock_db_session,
            )

        assert out.status == "active"
        mock_deploy.assert_awaited_once()
        # None tier -> deploy_container resolves free limits internally.
        assert mock_deploy.await_args.kwargs["plan_tier"] is None
