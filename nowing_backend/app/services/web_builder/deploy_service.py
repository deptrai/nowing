import asyncio
import contextlib
import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import CNAME_INGRESS_HOST, HOSTING_BASE_DOMAIN
from app.services.token_tracking_service import record_token_usage
from app.services.web_builder.schemas import (
    CustomDomainOutput,
    WebAppDeployOutput,
)

logger = logging.getLogger(__name__)


def disambiguate_slug(
    base_slug: str,
    existing_slugs: set[str] | list[str],
    max_length: int = 63,
    max_attempts: int = 100_000,
) -> str:
    """Generate a collision-free, DNS-label-safe slug.

    The result is always <= ``max_length`` and has a bounded number of suffix
    attempts to avoid an infinite loop (P15).
    """
    existing = set(existing_slugs)
    # Sanitize and truncate base_slug to DNS label safe format
    cleaned = re.sub(r"[^a-z0-9-]", "-", base_slug.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-") or "app"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].strip("-") or "app"

    if cleaned not in existing:
        return cleaned

    # Base is in existing; strip any trailing numeric suffix before incrementing
    base_without_num = re.sub(r"-\d+$", "", cleaned).strip("-") or "app"
    for counter in range(1, max_attempts + 1):
        suffix = f"-{counter}"
        avail = max_length - len(suffix)
        candidate = f"{base_without_num[:avail].strip('-')}{suffix}"
        if candidate not in existing:
            return candidate

    # Collisions exhausted the numeric range; append a short random tail.
    tail = uuid.uuid4().hex[:6]
    base = base_without_num[: max_length - len(tail) - 1]
    return f"{base}-{tail}"


class WebAppDeployService:
    """Builds, publishes static HTML snapshots, and routes web applications dynamically."""

    _deploy_locks: dict[str, asyncio.Lock] = {}
    _deploy_lock_refs: dict[str, int] = {}
    _deploy_lock_creation_lock = asyncio.Lock()

    def __init__(self, base_domain: str | None = None):
        self.base_domain = base_domain or HOSTING_BASE_DOMAIN
        self._caddy_file_lock = asyncio.Lock()

    @classmethod
    def _container_name(cls, workspace_id: int, slug: str) -> str:
        return f"nowing-app-{workspace_id}-{slug}"

    @classmethod
    def _image_tag(cls, workspace_id: int, app_id: str, slug: str) -> str:
        return f"nowing-web-app-{workspace_id}-{app_id[:8]}:{slug}"

    @classmethod
    def generate_traefik_labels(
        cls,
        app_slug: str,
        base_domain: str = "apps.nowing.net",
        port: int = 3000,
        custom_domain: str | None = None,
    ) -> dict[str, str]:
        """Generate Traefik routing labels for Dokploy production ingress."""
        from app.config import config as app_config

        router_name = f"nowing-app-{app_slug}"
        host_rules = [f"Host(`{app_slug}.{base_domain}`)"]
        if custom_domain:
            clean_domain = custom_domain.strip().lower()
            if clean_domain and clean_domain not in host_rules:
                host_rules.append(f"Host(`{clean_domain}`)")

        rule = " || ".join(host_rules)
        entrypoints = getattr(
            app_config, "WEB_BUILDER_TRAEFIK_ENTRYPOINT", "websecure"
        )
        certresolver = getattr(
            app_config, "WEB_BUILDER_TRAEFIK_CERTRESOLVER", "default"
        )
        use_tls = getattr(app_config, "WEB_BUILDER_TRAEFIK_USE_TLS", True)

        labels: dict[str, str] = {
            "traefik.enable": "true",
            f"traefik.http.routers.{router_name}.rule": rule,
            f"traefik.http.routers.{router_name}.entrypoints": entrypoints,
            f"traefik.http.services.{router_name}.loadbalancer.server.port": str(port),
        }
        if use_tls:
            labels[f"traefik.http.routers.{router_name}.tls"] = "true"
            labels[f"traefik.http.routers.{router_name}.tls.certresolver"] = certresolver
        return labels

    @classmethod
    def generate_caddy_snippet(
        cls,
        app_slug: str,
        container_target: str,
        base_domain: str = "apps.nowing.net",
        custom_domain: str | None = None,
    ) -> str:
        """Generate Caddy reverse_proxy block for dynamic self-host ingress."""
        domains = [f"{app_slug}.{base_domain}"]
        if custom_domain:
            clean_domain = custom_domain.strip().lower()
            if clean_domain and clean_domain not in domains:
                domains.append(clean_domain)
        hosts = ", ".join(domains)
        return f"{hosts} {{\n\treverse_proxy {container_target}\n}}\n"

    def _validate_storage_path(
        self,
        storage_path: str | None,
        workspace_id: int,
        app_id: str,
        raise_on_error: bool = False,
    ) -> Path | None:
        """Resolve and validate that storage_path points to the scoped app directory.

        Returns the resolved Path on success, or None if invalid and raise_on_error
        is False. Raises ValueError when raise_on_error is True.
        """
        from app.config import config as app_config

        if not storage_path:
            if raise_on_error:
                raise ValueError("Application has no storage path")
            return None

        base_path = Path(app_config.FILE_STORAGE_LOCAL_PATH).resolve()
        expected_scoped_dir = (
            base_path / "web-app" / str(workspace_id) / app_id
        ).resolve()

        project_path = Path(storage_path)
        if ".." in project_path.parts:
            if raise_on_error:
                raise ValueError("Invalid application storage path: parent traversal")
            return None

        try:
            resolved_dir = project_path.resolve()
        except (OSError, RuntimeError):
            if raise_on_error:
                raise ValueError("Invalid application storage path") from None
            return None

        expected_suffix = Path("web-app") / str(workspace_id) / app_id
        suffix_ok = (
            resolved_dir.parts[-len(expected_suffix.parts) :]
            == expected_suffix.parts
        )
        if not resolved_dir.is_relative_to(expected_scoped_dir) and not suffix_ok:
            logger.error(
                "Security violation: deploy storage path traversal. target=%s, expected=%s",
                resolved_dir,
                expected_scoped_dir,
            )
            if raise_on_error:
                raise ValueError("Invalid application storage path: traversal detected")
            return None

        return resolved_dir

    _CONTAINER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$", re.ASCII)

    def _is_safe_container_id(self, container_id_or_name: str) -> bool:
        """Docker IDs/Names only contain safe characters (no shell metacharacters)."""
        if not container_id_or_name:
            return False
        if len(container_id_or_name) <= 64 and self._CONTAINER_NAME_RE.match(container_id_or_name):
            return True
        # Docker short ID is 12 hex characters
        return (
            len(container_id_or_name) == 12
            and re.fullmatch(r"[a-f0-9]{12}", container_id_or_name, re.ASCII) is not None
        )

    async def _is_container_running(self, container_id: str) -> bool:
        """Best-effort check whether a container is still running."""
        if not self._is_safe_container_id(container_id):
            logger.warning("Refusing to inspect container with unsafe id/name: %s", container_id)
            return False
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            "inspect",
            "--format",
            "{{.State.Running}}",
            container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except TimeoutError:
            with contextlib.suppress(Exception):
                proc.kill()
            return False
        return proc.returncode == 0 and stdout.decode("utf-8").strip().lower() == "true"

    async def _stop_container(self, container_id_or_name: str) -> None:
        """Remove a running container, ignoring errors."""
        if not self._is_safe_container_id(container_id_or_name):
            logger.warning("Refusing to stop container with unsafe id/name: %s", container_id_or_name)
            return
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            "rm",
            "-f",
            container_id_or_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(proc.communicate(), timeout=10.0)

    async def _healthcheck_container(
        self,
        host: str,
        port: int,
        timeout_seconds: int = 60,
        retries: int = 10,
    ) -> bool:
        """Wait for the container to accept HTTP connections on host:port."""
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        delay = min(1.0, timeout_seconds / max(retries, 1))
        while asyncio.get_event_loop().time() < deadline:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=5.0,
                )
                request = (
                    f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
                )
                writer.write(request.encode("utf-8"))
                await writer.drain()
                response = await asyncio.wait_for(reader.read(256), timeout=5.0)
                writer.close()
                await writer.wait_closed()
                if response and b"HTTP/1.1" in response:
                    return True
            except Exception:
                pass
            await asyncio.sleep(delay)
        return False

    def _is_system_domain(self, domain: str) -> bool:
        """Reject reserved infrastructure domains and configured base domains."""
        from app.config import config as app_config

        base_domain = (self.base_domain or "apps.nowing.net").lower().rstrip(".")
        cname_host = (CNAME_INGRESS_HOST or "cname-ingress.apps.nowing.net").lower().rstrip(".")
        raw_blacklist = getattr(
            app_config, "WEB_BUILDER_DOMAIN_BLACKLIST", ""
        )
        system_domains = {
            base_domain,
            cname_host,
            "nowing.net",
            "api.nowing.net",
            "localhost",
            "local",
        }
        for item in raw_blacklist.split(","):
            item = item.strip().lower().rstrip(".")
            if item:
                system_domains.add(item)

        clean = domain.lower().rstrip(".")
        if clean in system_domains:
            return True
        return any(clean.endswith(f".{sd}") for sd in system_domains if sd)

    async def _resolve_cname_ingress(
        self, domain: str, target: str, max_depth: int = 5
    ) -> bool:
        """Verify DNS proof-of-control for a custom domain.

        Follows CNAME chains and also accepts A/AAAA apex-style records that
        resolve to the same IP addresses as the CNAME ingress host.
        """
        import dns.resolver

        expected = target.lower().rstrip(".")
        current = domain.lower().rstrip(".")

        for _ in range(max_depth):
            try:
                resolver = dns.resolver.Resolver()
                resolver.lifetime = 5
                answers = await asyncio.to_thread(resolver.resolve, current, "CNAME")
                cname_values = {
                    str(rdata.target).rstrip(".").lower() for rdata in answers
                }
                if expected in cname_values:
                    return True
                if not cname_values:
                    return False
                # Follow the first CNAME in the chain
                current = next(iter(cname_values))
                continue
            except dns.resolver.NoAnswer:
                # No CNAME at this hop; stop the chain walk.
                break
            except dns.resolver.NXDOMAIN:
                return False
            except Exception:
                return False

        # No CNAME match; try A/AAAA for apex-style / ALIAS-like records.
        try:
            target_ips = set()
            resolver = dns.resolver.Resolver()
            resolver.lifetime = 5
            with contextlib.suppress(Exception):
                for rdata in await asyncio.to_thread(resolver.resolve, expected, "A"):
                    target_ips.add(str(rdata))
            with contextlib.suppress(Exception):
                for rdata in await asyncio.to_thread(
                    resolver.resolve, expected, "AAAA"
                ):
                    target_ips.add(str(rdata))

            domain_ips = set()
            with contextlib.suppress(Exception):
                for rdata in await asyncio.to_thread(resolver.resolve, current, "A"):
                    domain_ips.add(str(rdata))
            with contextlib.suppress(Exception):
                for rdata in await asyncio.to_thread(
                    resolver.resolve, current, "AAAA"
                ):
                    domain_ips.add(str(rdata))

            return bool(target_ips) and bool(domain_ips) and target_ips == domain_ips
        except Exception:
            return False

    def _caddy_snippets_path(self) -> Path:
        from app.config import config as app_config

        raw = getattr(
            app_config,
            "WEB_BUILDER_CADDY_SNIPPETS_PATH",
            "docker/proxy/web-apps.Caddyfile",
        )
        path = Path(raw)
        if not path.is_absolute():
            # Anchor relative paths from the repo root (one up from nowing_backend).
            repo_root = Path(__file__).resolve().parents[4]
            path = repo_root / path
        return path

    def _caddy_target_for_app(
        self, workspace_id: int, slug: str, container_id: str | None
    ) -> str:
        from app.config import config as app_config

        if container_id:
            container_host = self._container_name(workspace_id, slug)
            return f"{container_host}:3000"
        return getattr(
            app_config, "WEB_BUILDER_CADDY_BACKEND_TARGET", "backend:8000"
        )

    async def _write_caddy_snippet_for_app(
        self,
        app_entity,  # WorkspaceApp
        container_id: str | None = None,
    ) -> None:
        """(Re)write the per-app Caddy snippet and reload Caddy if available."""
        from app.config import config as app_config

        if not getattr(app_config, "WEB_BUILDER_CADDY_SNIPPETS_ENABLED", False):
            return

        slug = app_entity.slug
        custom_domain = app_entity.custom_domain
        workspace_id = app_entity.workspace_id
        target = self._caddy_target_for_app(
            workspace_id, slug, container_id or app_entity.container_id
        )

        snippet = self.generate_caddy_snippet(
            app_slug=slug,
            container_target=target,
            base_domain=self.base_domain,
            custom_domain=custom_domain,
        )

        caddy_file = self._caddy_snippets_path()
        marker = f"# BEGIN nowing-app-{workspace_id}-{slug}"
        end_marker = f"# END nowing-app-{workspace_id}-{slug}"

        async with self._caddy_file_lock:
            try:
                if caddy_file.exists():
                    text = caddy_file.read_text(encoding="utf-8")
                else:
                    text = "# Dynamic Web Builder App Routes (Generated by WebAppDeployService)\n"

                # Remove any existing block for this app
                while marker in text:
                    start = text.find(marker)
                    end = text.find(end_marker, start)
                    if end == -1:
                        break
                    text = text[:start] + text[end + len(end_marker) + 1 :]

                text = text.rstrip() + f"\n\n{marker}\n{snippet}{end_marker}\n"
                caddy_file.write_text(text, encoding="utf-8")
            except Exception as e:
                logger.error("Failed to write Caddy snippet for %s: %s", slug, e)
                raise RuntimeError(f"Failed to write Caddy snippet: {e}") from e

        await self._reload_caddy()

    async def _reload_caddy(self) -> None:
        """Best-effort Caddy reload; never fails if no Caddy CLI/container is available."""
        from app.config import config as app_config

        if not getattr(app_config, "WEB_BUILDER_CADDY_RELOAD_ENABLED", False):
            return

        docker_bin = shutil.which("docker")
        caddy_bin = shutil.which("caddy")

        if caddy_bin:
            proc = await asyncio.create_subprocess_exec(
                caddy_bin,
                "reload",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            with contextlib.suppress(asyncio.TimeoutError):
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=30.0
                )
            if proc.returncode == 0:
                return
            if proc.returncode is not None:
                logger.warning(
                    "Caddy reload returned %s: %s",
                    proc.returncode,
                    (stderr or stdout).decode("utf-8", errors="replace"),
                )

        container_name = getattr(app_config, "WEB_BUILDER_CADDY_CONTAINER_NAME", "")
        if docker_bin and container_name:
            proc = await asyncio.create_subprocess_exec(
                docker_bin,
                "exec",
                container_name,
                "caddy",
                "reload",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            with contextlib.suppress(asyncio.TimeoutError):
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=30.0
                )
            if proc.returncode == 0:
                return
            if proc.returncode is not None:
                logger.warning(
                    "Caddy reload in container %s returned %s: %s",
                    container_name,
                    proc.returncode,
                    (stderr or stdout).decode("utf-8", errors="replace"),
                )

        logger.info(
            "Caddy reload skipped: no caddy binary or container configured to reload"
        )

    async def _acquire_lock(
        self, lock_key: str, timeout_seconds: int
    ) -> Any:
        """Acquire a Redis or in-memory lock keyed by ``lock_key``."""
        try:
            from app.redis_client import get_redis_client

            redis_client = await get_redis_client()
            await redis_client.ping()
            return redis_client.lock(
                f"web_builder:{lock_key}",
                timeout=float(timeout_seconds) + 600.0,
                thread_local=False,
                blocking_timeout=float(timeout_seconds) + 60.0,
            )
        except Exception as e:
            logger.warning(
                "Redis lock unavailable for %s; using in-memory fallback: %s",
                lock_key,
                e,
            )

        async with self._deploy_lock_creation_lock:
            if lock_key not in self._deploy_locks:
                self._deploy_locks[lock_key] = asyncio.Lock()
                self._deploy_lock_refs[lock_key] = 0
            self._deploy_lock_refs[lock_key] += 1
        return self._deploy_locks[lock_key]

    async def _release_lock(self, lock_key: str) -> None:
        """Release an in-memory lock and clean up when no refs remain."""
        async with self._deploy_lock_creation_lock:
            refs = self._deploy_lock_refs.get(lock_key, 1) - 1
            if refs <= 0:
                self._deploy_lock_refs.pop(lock_key, None)
                self._deploy_locks.pop(lock_key, None)
            else:
                self._deploy_lock_refs[lock_key] = refs

    async def _acquire_deploy_lock(
        self, app_id: str, timeout_seconds: int
    ) -> Any:
        """Acquire the per-app deploy lock."""
        return await self._acquire_lock(f"deploy:{app_id}", timeout_seconds)

    async def _release_deploy_lock(self, app_id: str) -> None:
        await self._release_lock(f"deploy:{app_id}")

    async def _acquire_domain_lock(
        self, domain: str, timeout_seconds: int
    ) -> Any:
        """Acquire the per-domain custom-domain binding lock."""
        return await self._acquire_lock(f"domain:{domain}", timeout_seconds)

    async def _release_domain_lock(self, domain: str) -> None:
        await self._release_lock(f"domain:{domain}")

    async def deploy_container(
        self,
        app_id: str,
        workspace_id: int,
        project_path: Path,
        slug: str,
        custom_domain: str | None = None,
    ) -> tuple[str, int]:
        """Builds Docker runtime image from .next/standalone and runs container."""

        docker_bin = shutil.which("docker")
        if not docker_bin:
            raise RuntimeError("Docker CLI is not available in current environment")

        # Path-traversal guard: project_path must live under the scoped workspace dir.
        scoped_path = self._validate_storage_path(
            str(project_path), workspace_id, app_id, raise_on_error=True
        )
        if not scoped_path:
            raise RuntimeError("Invalid application storage path")

        standalone_dir = scoped_path / ".next" / "standalone"
        if not standalone_dir.exists() or not (standalone_dir / "server.js").exists():
            raise RuntimeError(
                "Compiled Next.js standalone build (.next/standalone/server.js) is missing. "
                "Please run project build before deploying runtime container."
            )

        # Ensure static assets are present in standalone directory
        static_src = scoped_path / ".next" / "static"
        static_dst = standalone_dir / ".next" / "static"
        if static_src.exists() and not static_dst.exists():
            shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
        public_src = scoped_path / "public"
        public_dst = standalone_dir / "public"
        if public_src.exists() and not public_dst.exists():
            shutil.copytree(public_src, public_dst, dirs_exist_ok=True)

        dockerfile_path = Path("docker/web-app.Dockerfile").resolve()
        if not dockerfile_path.exists():
            dockerfile_path = (
                Path(__file__).resolve().parents[4] / "docker" / "web-app.Dockerfile"
            )

        image_tag = self._image_tag(workspace_id, app_id, slug)
        container_name = self._container_name(workspace_id, slug)

        from app.config import config as app_config

        # 1. Build image from standalone directory with a bounded timeout.
        build_cmd = [
            docker_bin,
            "build",
            "-f",
            str(dockerfile_path),
            str(standalone_dir),
            "-t",
            image_tag,
        ]
        proc = await asyncio.create_subprocess_exec(
            *build_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(app_config.WEB_BUILDER_BUILD_TIMEOUT_SECONDS),
            )
        except TimeoutError:
            with contextlib.suppress(Exception):
                proc.kill()
            raise RuntimeError(
                f"Docker build timed out after {app_config.WEB_BUILDER_BUILD_TIMEOUT_SECONDS}s"
            ) from None
        if proc.returncode != 0:
            raise RuntimeError(
                f"Docker build failed: {stderr.decode('utf-8', errors='replace')}"
            )

        # 2. Stop/remove previous container if exists
        await self._stop_container(container_name)

        # 3. Generate Traefik labels (port is the stable internal port 3000).
        labels = self.generate_traefik_labels(
            app_slug=slug,
            base_domain=self.base_domain,
            port=3000,
            custom_domain=custom_domain,
        )
        label_args = []
        for k, v in labels.items():
            label_args.extend(["--label", f"{k}={v}"])

        # 4. Run container with resource limits and security opts on the dokploy network.
        network = app_config.WEB_BUILDER_DOKPLOY_NETWORK
        network_args = ["--network", network] if network else []
        run_cmd = [
            docker_bin,
            "run",
            "-d",
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            "--memory=512m",
            "--cpus=0.5",
            "--pids-limit=100",
            "--security-opt=no-new-privileges",
            *network_args,
            *label_args,
            image_tag,
        ]
        proc_run = await asyncio.create_subprocess_exec(
            *run_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_run, stderr_run = await asyncio.wait_for(
                proc_run.communicate(),
                timeout=60.0,
            )
        except TimeoutError:
            with contextlib.suppress(Exception):
                proc_run.kill()
            raise RuntimeError("Docker run timed out after 60s") from None
        if proc_run.returncode != 0:
            raise RuntimeError(
                f"Docker run failed: {stderr_run.decode('utf-8', errors='replace')}"
            )

        container_id = stdout_run.decode("utf-8").strip()[:12]

        # 5. Healthcheck the container before declaring it ready.
        port = 3000
        target_host = container_name
        healthcheck_timeout = getattr(
            app_config, "WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT", 60
        )
        healthcheck_retries = getattr(
            app_config, "WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES", 10
        )
        healthy = await self._healthcheck_container(
            target_host,
            port,
            timeout_seconds=healthcheck_timeout,
            retries=healthcheck_retries,
        )
        if not healthy:
            await self._stop_container(container_name)
            raise RuntimeError("Container started but failed healthcheck; removed.")

        return container_id, port

    async def deploy_app(
        self,
        app_id: str,
        workspace_id: int,
        slug_override: str | None = None,
        force: bool = False,
        session: AsyncSession | None = None,
    ) -> WebAppDeployOutput:
        """Publish a generated project to https://{slug}.apps.nowing.net."""
        from app.config import config as app_config
        from app.db import Workspace, WorkspaceApp
        from app.services.web_builder.preview_renderer import PreviewRenderer

        public_apps_base = Path(app_config.WEB_BUILDER_PUBLIC_APPS_PATH).resolve()
        public_apps_base.mkdir(parents=True, exist_ok=True)

        if not session:
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug="",
                message="Database session is required to publish an app",
            )

        # 0. Verify workspace and app gates (P3, P14).
        ws = (
            (
                await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id)
                )
            )
            .scalars()
            .first()
        )
        if ws is None or ws.web_builder_enabled is False:
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug="",
                message="Web Builder is not enabled on this workspace plan",
            )

        stmt = select(WorkspaceApp).where(
            WorkspaceApp.id == app_id,
            WorkspaceApp.workspace_id == workspace_id,
        )
        app_entity = (await session.execute(stmt)).scalars().first()

        if app_entity is None:
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug="",
                message="Application not found",
            )

        if not app_entity.storage_path:
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug="",
                message="Application has no generated files to publish",
            )

        # Path-traversal guard before touching the filesystem.
        project_path = self._validate_storage_path(
            app_entity.storage_path, workspace_id, app_id, raise_on_error=False
        )
        if not project_path or not project_path.exists() or not any(project_path.iterdir()):
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug="",
                message="Application source directory is missing or empty",
            )

        # Serialize deploys for this app so two publish clicks do not race on
        # slug selection, TokenUsage recording, or snapshot writes.
        deploy_lock = await self._acquire_deploy_lock(
            app_id, app_config.WEB_BUILDER_BUILD_TIMEOUT_SECONDS
        )
        try:
            async with deploy_lock:
                # 1. Disambiguate slug (global uniqueness across published apps).
                final_slug = slug_override or app_entity.slug or "web-app"
                all_slugs_stmt = select(WorkspaceApp.slug).where(
                    WorkspaceApp.id != app_id,
                    WorkspaceApp.status == "published",
                )
                res = await session.execute(all_slugs_stmt)
                existing_slugs = {s for s in res.scalars().all() if s}
                sanitized_slug = disambiguate_slug(final_slug, existing_slugs)
                public_url = f"https://{sanitized_slug}.{self.base_domain}"

                # 2. Idempotency check: if already published and (container running or
                # static snapshot exists) and not force.
                snapshot_dir = public_apps_base / sanitized_slug
                snapshot_file = snapshot_dir / "index.html"
                is_live = False
                if (
                    not force
                    and app_entity.status == "published"
                    and app_entity.slug == sanitized_slug
                ):
                    if app_config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED:
                        if app_entity.container_id and await self._is_container_running(
                            app_entity.container_id
                        ):
                            is_live = True
                    elif snapshot_file.exists():
                        is_live = True

                    if is_live:
                        return WebAppDeployOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            status="published",
                            public_url=app_entity.public_url or public_url,
                            slug=app_entity.slug or sanitized_slug,
                            message=f"Application already published at {app_entity.public_url or public_url}",
                        )

                # 3. Render static HTML snapshot (prefer compiled standalone build if exists, fallback to PreviewRenderer).
                try:
                    candidate_index_paths = [
                        project_path / ".next" / "server" / "app" / "index.html",
                        project_path / ".next" / "server" / "app" / "page.html",
                        project_path
                        / ".next"
                        / "standalone"
                        / ".next"
                        / "server"
                        / "app"
                        / "index.html",
                        project_path / ".next" / "standalone" / "index.html",
                        project_path / "out" / "index.html",
                    ]
                    static_html = None
                    for candidate in candidate_index_paths:
                        if candidate.exists():
                            static_html = candidate.read_text(encoding="utf-8")
                            break
                    if not static_html:
                        static_html = PreviewRenderer.render_app_html(
                            project_path,
                            app_name=app_entity.name,
                        )
                except Exception as e:
                    logger.error(
                        f"[WebAppDeployService] Rendering failed for app {app_id}: {e}"
                    )
                    app_entity.status = "deploy_failed"
                    app_entity.error_message = f"Rendering failed: {e}"
                    await session.commit()
                    return WebAppDeployOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        status="deploy_failed",
                        slug=sanitized_slug,
                        message=f"Rendering failed: {e}",
                    )

                # 4. Container deployment (if enabled). On failure, fail hard and
                # do NOT fall back to the static snapshot (Story 27.1c decision).
                container_id = None
                port = None
                if app_config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED:
                    try:
                        container_id, port = await self.deploy_container(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            project_path=project_path,
                            slug=sanitized_slug,
                            custom_domain=app_entity.custom_domain,
                        )
                    except Exception as e:
                        logger.error(
                            f"[WebAppDeployService] Container deploy failed for app {app_id}: {e}"
                        )
                        app_entity.status = "deploy_failed"
                        app_entity.error_message = f"Container deploy failed: {e}"
                        app_entity.public_url = public_url
                        app_entity.slug = sanitized_slug
                        with contextlib.suppress(Exception):
                            await session.commit()
                        return WebAppDeployOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            status="deploy_failed",
                            slug=sanitized_slug,
                            message=f"Container deploy failed: {e}",
                        )

                # Commit the published state to the database *before* writing the
                # snapshot file so a failed file write does not leave a published URL
                # with no matching static file (P16).
                try:
                    app_entity.slug = sanitized_slug
                    app_entity.public_url = public_url
                    if container_id:
                        app_entity.container_id = container_id
                        app_entity.port = port
                    app_entity.status = "published"
                    app_entity.error_message = None

                    # Record deployment billing metrics.
                    await record_token_usage(
                        session=session,
                        workspace_id=workspace_id,
                        user_id=app_entity.user_id,
                        usage_type="web_builder_deploy",
                        cost_micros=app_config.WEB_BUILDER_DEPLOY_COST_MICROS,
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(
                        f"[WebAppDeployService] Database publish failed for app {app_id}: {e}"
                    )
                    if container_id:
                        await self._stop_container(container_id)
                    return WebAppDeployOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        status="deploy_failed",
                        slug=sanitized_slug,
                        message=f"Database publish failed: {e}",
                    )

                # 5. Write per-app Caddy snippet (self-host ingress).
                try:
                    await self._write_caddy_snippet_for_app(
                        app_entity, container_id=container_id
                    )
                except Exception as e:
                    logger.error(
                        f"[WebAppDeployService] Caddy snippet write failed for app {app_id}: {e}"
                    )
                    await self._stop_container(container_id or "")
                    app_entity.status = "deploy_failed"
                    app_entity.error_message = f"Caddy snippet write failed: {e}"
                    with contextlib.suppress(Exception):
                        await session.commit()
                    return WebAppDeployOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        status="deploy_failed",
                        slug=sanitized_slug,
                        message=f"Caddy snippet write failed: {e}",
                    )

                # 6. Write the static snapshot after the DB is committed.
                try:
                    snapshot_dir.mkdir(parents=True, exist_ok=True)
                    snapshot_file.write_text(static_html, encoding="utf-8")
                except Exception as e:
                    logger.error(
                        f"[WebAppDeployService] Snapshot file write failed for app {app_id}: {e}"
                    )
                    # Roll back the published state and stop the container.
                    try:
                        if container_id:
                            await self._stop_container(container_id)
                        app_entity.status = "deploy_failed"
                        app_entity.error_message = f"Snapshot write failed: {e}"
                        await session.commit()
                    except Exception as db_err:
                        logger.error(
                            f"[WebAppDeployService] Failed to mark app {app_id} as deploy_failed: {db_err}"
                        )
                    return WebAppDeployOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        status="deploy_failed",
                        slug=sanitized_slug,
                        message=f"Snapshot write failed: {e}",
                    )

                return WebAppDeployOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    status="published",
                    public_url=public_url,
                    slug=sanitized_slug,
                    message=f"Application deployed successfully to {public_url}",
                )
        finally:
            await self._release_deploy_lock(app_id)

    async def verify_and_bind_custom_domain(
        self,
        app_id: str,
        workspace_id: int,
        custom_domain: str,
        session: AsyncSession | None = None,
    ) -> CustomDomainOutput:
        """Validate custom domain FQDN, verify DNS proof-of-control, and bind it."""
        from app.db import Workspace, WorkspaceApp

        clean_domain = custom_domain.strip().rstrip(".").lower()
        cname_target = CNAME_INGRESS_HOST

        if len(clean_domain) > 255:
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Custom domain exceeds the maximum length of 255 characters.",
            )

        # Basic FQDN validation (no IPs, no localhost, valid labels)
        if not re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", clean_domain):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Invalid custom domain. Provide a valid FQDN (e.g. app.mycompany.com).",
            )

        # Reserved / system infrastructure domain blacklist (config-driven)
        if self._is_system_domain(clean_domain):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Cannot use system domain or reserved infrastructure domains.",
            )

        for label in clean_domain.split("."):
            if (
                not label
                or label.startswith("-")
                or label.endswith("-")
                or len(label) > 63
            ):
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message="Invalid custom domain label. Each DNS label must be 1-63 characters and not start/end with a hyphen.",
                )

        if re.match(r"^\d+\.\d+\.\d+\.\d+$|^\[[0-9a-f:]+\]$", clean_domain):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="IP addresses are not valid custom domains.",
            )

        if clean_domain == "localhost" or clean_domain.endswith(".local"):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Local domains are not valid custom domains.",
            )

        if session:
            # Verify workspace feature gate.
            ws = (
                await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id)
                )
            ).scalars().first()
            if ws and ws.web_builder_enabled is False:
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message="Web Builder is not enabled on this workspace plan",
                )

            # Serialize binding for this domain so two workspaces cannot race
            # on the collision check and both commit the same custom domain.
            domain_lock = await self._acquire_domain_lock(clean_domain, 60)
            try:
                async with domain_lock:
                    # Check collision across workspaces for active/pending bindings.
                    collision_stmt = select(WorkspaceApp).where(
                        WorkspaceApp.custom_domain == clean_domain,
                        WorkspaceApp.id != app_id,
                        WorkspaceApp.custom_domain_status.in_(
                            ["active", "pending_verification"]
                        ),
                    )
                    col_res = await session.execute(collision_stmt)
                    if col_res.scalars().first():
                        return CustomDomainOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            custom_domain=clean_domain,
                            status="failed",
                            cname_target=cname_target,
                            message=f"Domain '{clean_domain}' is already assigned to another application",
                        )

                    # DNS proof-of-control: CNAME must point to the ingress host (R-11).
                    dns_ok = await self._resolve_cname_ingress(
                        clean_domain, cname_target
                    )
                    if not dns_ok:
                        return CustomDomainOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            custom_domain=clean_domain,
                            status="failed",
                            cname_target=cname_target,
                            message=f"Domain '{clean_domain}' CNAME does not point to {cname_target}.",
                        )

                    # Update DB entity
                    stmt = select(WorkspaceApp).where(
                        WorkspaceApp.id == app_id,
                        WorkspaceApp.workspace_id == workspace_id,
                    )
                    app_res = await session.execute(stmt)
                    app_entity = app_res.scalars().first()

                    if not app_entity:
                        return CustomDomainOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            custom_domain=clean_domain,
                            status="failed",
                            cname_target=cname_target,
                            message="Application not found",
                        )

                    if app_entity.status != "published":
                        app_entity.custom_domain = clean_domain
                        app_entity.custom_domain_status = "pending_verification"
                        await session.commit()
                        return CustomDomainOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            custom_domain=clean_domain,
                            status="pending_verification",
                            cname_target=cname_target,
                            message=f"Custom domain {clean_domain} verified. It will become active after the app is published.",
                        )

                    # For published apps, only mark active after a successful container
                    # redeploy (if container deploy is enabled) and Caddy rewrite.
                    from app.config import config as app_config

                    app_entity.custom_domain = clean_domain
                    app_entity.custom_domain_status = "pending_verification"
                    await session.commit()

                    if (
                        app_config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED
                        and app_entity.storage_path
                    ):
                        try:
                            project_path = self._validate_storage_path(
                                app_entity.storage_path,
                                workspace_id,
                                app_id,
                                raise_on_error=True,
                            )
                            container_id, port = await self.deploy_container(
                                app_id=app_id,
                                workspace_id=workspace_id,
                                project_path=project_path,
                                slug=app_entity.slug,
                                custom_domain=clean_domain,
                            )
                            app_entity.container_id = container_id
                            app_entity.port = port
                        except Exception as redeploy_err:
                            logger.error(
                                "[WebAppDeployService] Container redeploy for custom domain failed: %s",
                                redeploy_err,
                            )
                            app_entity.custom_domain_status = "failed"
                            app_entity.error_message = f"Container redeploy failed: {redeploy_err}"
                            await session.commit()
                            return CustomDomainOutput(
                                app_id=app_id,
                                workspace_id=workspace_id,
                                custom_domain=clean_domain,
                                status="failed",
                                cname_target=cname_target,
                                message=f"Custom domain verified, but container redeploy failed: {redeploy_err}",
                            )

                    # Rewrite the Caddy snippet with the new custom domain.
                    try:
                        await self._write_caddy_snippet_for_app(app_entity)
                    except Exception as caddy_err:
                        logger.error(
                            "[WebAppDeployService] Caddy snippet rewrite failed: %s", caddy_err
                        )
                        app_entity.custom_domain_status = "failed"
                        app_entity.error_message = f"Caddy snippet rewrite failed: {caddy_err}"
                        await session.commit()
                        return CustomDomainOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            custom_domain=clean_domain,
                            status="failed",
                            cname_target=cname_target,
                            message=f"Custom domain verified, but ingress update failed: {caddy_err}",
                        )

                    app_entity.custom_domain_status = "active"
                    await session.commit()

                    return CustomDomainOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        custom_domain=clean_domain,
                        status="active",
                        cname_target=cname_target,
                        message=f"Custom domain {clean_domain} verified and bound to {cname_target}.",
                    )
            finally:
                await self._release_domain_lock(clean_domain)

        return CustomDomainOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            custom_domain=clean_domain,
            status="pending_verification",
            cname_target=cname_target,
            message=f"Custom domain {clean_domain} configured. Point its CNAME to {cname_target}.",
        )
