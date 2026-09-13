import asyncio
import contextlib
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    CNAME_INGRESS_HOST,
    HOSTING_BASE_DOMAIN,
    get_web_builder_tier_limits,
)
from app.services.web_builder.deploy.custom_domain import verify_and_bind_custom_domain
from app.services.web_builder.deploy.deploy_app import deploy_app
from app.services.web_builder.schemas import (
    CustomDomainOutput,
    WebAppDeployOutput,
)

logger = logging.getLogger(__name__)


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

    _NET_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]")

    @classmethod
    def _app_network_name(cls, workspace_id: int, app_id: str) -> str:
        """Per-app bridge network name for WEB_BUILDER_PER_APP_NETWORK mode.

        app_id is sanitized to ``[a-z0-9_.-]`` (lowercase) and the result
        bounded to 255 chars so the name is always a safe docker target.
        """
        safe_app = cls._NET_NAME_SAFE_RE.sub("-", str(app_id).lower())
        return f"nowing-app-{workspace_id}-{safe_app}-net"[:255]

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
        """Docker IDs/Names only contain safe characters (no shell metacharacters).

        The name bound is 255 chars, not 64: generated names like
        ``nowing-app-{workspace_id}-{slug}`` reach ~80 chars with a max-length
        (63-char) slug, and ``docker --name``/``inspect``/``rm`` impose no
        64-char limit. The charset regex is what guards against injection.
        """
        if not container_id_or_name:
            return False
        if len(container_id_or_name) <= 255 and self._CONTAINER_NAME_RE.match(container_id_or_name):
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

    async def _ensure_app_network(self, network: str, proxy_container: str) -> None:
        """Create the per-app bridge network and connect the ingress proxy.

        Both steps are idempotent across redeploys: ``docker network create``
        returning "already exists" and ``docker network connect`` returning
        "already exists"/"already connected" in stderr are tolerated.
        """
        docker_bin = shutil.which("docker")
        if not docker_bin:
            raise RuntimeError("Docker CLI is not available in current environment")
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            "network",
            "create",
            network,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        err = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0 and "already exists" not in err:
            raise RuntimeError(
                f"docker network create {network} failed: {err}"
            )
        if not self._is_safe_container_id(proxy_container):
            raise RuntimeError(
                f"WEB_BUILDER_INGRESS_PROXY_CONTAINER={proxy_container!r} is "
                "not a safe container name/id"
            )
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            "network",
            "connect",
            network,
            proxy_container,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        err = stderr.decode("utf-8", errors="replace")
        if (
            proc.returncode != 0
            and "already exists" not in err
            and "already connected" not in err
        ):
            raise RuntimeError(
                f"docker network connect {proxy_container} to {network} "
                f"failed: {err}"
            )

    async def _cleanup_app_network(
        self, workspace_id: int, app_id: str
    ) -> None:
        """Best-effort teardown of the per-app bridge network.

        Only acts when WEB_BUILDER_PER_APP_NETWORK is enabled. Disconnects
        the ingress proxy then removes the network; removal tolerates
        "active endpoints"/"not found" races — everything is suppress()ed.
        """
        from app.config import config as app_config

        if not getattr(app_config, "WEB_BUILDER_PER_APP_NETWORK", False):
            return
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return
        network = self._app_network_name(workspace_id, app_id)
        proxy_container = (
            getattr(app_config, "WEB_BUILDER_INGRESS_PROXY_CONTAINER", "") or ""
        ).strip()
        if proxy_container and self._is_safe_container_id(proxy_container):
            with contextlib.suppress(Exception):
                proc = await asyncio.create_subprocess_exec(
                    docker_bin,
                    "network",
                    "disconnect",
                    network,
                    proxy_container,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=10.0)
        with contextlib.suppress(Exception):
            proc = await asyncio.create_subprocess_exec(
                docker_bin,
                "network",
                "rm",
                network,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10.0)

    # Single inspect snapshot of everything the deploy path needs: health
    # status (image HEALTHCHECK), running flag, exit code, OOM kill flag, and
    # the daemon-recorded error string. Piped format keeps it to ONE call so
    # auto-restart cannot mutate state between separate inspects.
    _INSPECT_STATE_FORMAT = (
        "{{.State.Health.Status}}|{{.State.Running}}|{{.State.ExitCode}}"
        "|{{.State.OOMKilled}}|{{.State.Error}}"
    )

    async def _inspect_container_state(
        self, container_id_or_name: str
    ) -> dict[str, Any] | None:
        """Snapshot ``.State`` of a container in one ``docker inspect`` call.

        Returns ``None`` when the inspect itself fails (unsafe id, no docker
        binary, non-zero exit, timeout) — callers treat that as "unknown"
        rather than crashing the deploy/cleanup path.
        """
        if not self._is_safe_container_id(container_id_or_name):
            logger.warning(
                "Refusing to inspect container with unsafe id/name: %s",
                container_id_or_name,
            )
            return None
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                docker_bin,
                "inspect",
                "--format",
                self._INSPECT_STATE_FORMAT,
                container_id_or_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, PermissionError):
            # Spawn failure (missing binary race, sandbox denial) must not
            # bypass cleanup — treat the state as unknown.
            return None
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except TimeoutError:
            with contextlib.suppress(Exception):
                proc.kill()
            # Reap the child so a killed inspect cannot linger as a zombie.
            if hasattr(proc, "wait") and callable(proc.wait):
                with contextlib.suppress(Exception):
                    res = proc.wait()
                    if asyncio.iscoroutine(res):
                        await asyncio.wait_for(res, timeout=1.0)
            return None
        if proc.returncode != 0:
            return None

        parts = stdout.decode("utf-8", errors="replace").strip().split("|", 4)
        while len(parts) < 5:
            parts.append("")
        health_raw, running_raw, exit_raw, oom_raw, error = parts

        def _truthy(value: str) -> bool | None:
            value = value.strip().lower()
            if value in ("true", "false"):
                return value == "true"
            return None

        health: str | None = health_raw.strip()
        # "none"/"<no value>"/"" mean the image defines no HEALTHCHECK.
        if health in ("", "<no value>", "none"):
            health = None
        try:
            exit_code: int | None = int(exit_raw.strip())
        except ValueError:
            exit_code = None

        return {
            "health": health,
            "running": _truthy(running_raw),
            "exit_code": exit_code,
            "oom_killed": _truthy(oom_raw) is True,
            "error": error.strip(),
        }

    # Same probe the image HEALTHCHECK runs (docker/web-app.Dockerfile) —
    # used for the no-HEALTHCHECK fallback so "running" is never declared
    # healthy without proving the :3000 listener actually answers.
    _EXEC_HEALTH_CMD = (
        "require('http').get('http://127.0.0.1:3000',"
        "(r)=>process.exit(r.statusCode<400?0:1))"
        ".on('error',()=>process.exit(1))"
    )

    async def _exec_health_probe(self, container_id_or_name: str) -> bool | None:
        """``docker exec`` the HTTP probe inside the container.

        Returns ``True`` on exit code 0, ``False`` on a non-zero exit (the
        listener refused/errored), and ``None`` when the probe itself could
        not run (unsafe id, no docker binary, spawn failure, timeout).
        """
        if not self._is_safe_container_id(container_id_or_name):
            return None
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                docker_bin,
                "exec",
                container_id_or_name,
                "node",
                "-e",
                self._EXEC_HEALTH_CMD,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, PermissionError):
            return None
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except TimeoutError:
            with contextlib.suppress(Exception):
                proc.kill()
            if hasattr(proc, "wait") and callable(proc.wait):
                with contextlib.suppress(Exception):
                    res = proc.wait()
                    if asyncio.iscoroutine(res):
                        await asyncio.wait_for(res, timeout=1.0)
            return None
        return proc.returncode == 0

    async def _healthcheck_container(
        self,
        container_id_or_name: str,
        timeout_seconds: int = 60,
        retries: int = 10,
    ) -> bool:
        """Wait for the container to report healthy via ``docker inspect``.

        Polls ``.State.Health.Status`` until ``healthy`` or the deadline —
        the image already defines HEALTHCHECK (docker/web-app.Dockerfile).
        When the image has no HEALTHCHECK (``.State.Health`` nil) the
        fallback ``docker exec``s the same HTTP probe the image HEALTHCHECK
        uses so a running-but-not-serving container is not declared healthy.
        Never TCP-connects to the container name: the backend shares no
        network with user app containers, so container-name DNS does not
        resolve here (Story 31.1).

        A dead sample (Running=false with non-zero exit) is only fatal
        after 3 CONSECUTIVE observations — a single sample can land in the
        dead window between ``--restart unless-stopped`` restarts, while a
        real crash-loop still fails in seconds.
        """
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        delay = min(1.0, timeout_seconds / max(retries, 1))
        dead_streak = 0
        while asyncio.get_event_loop().time() < deadline:
            state = await self._inspect_container_state(container_id_or_name)
            if state is not None:
                dead = state.get("running") is False and state.get(
                    "exit_code"
                ) not in (None, 0)
                dead_streak = dead_streak + 1 if dead else 0
                if dead_streak >= 3:
                    # Container is persistently dead with a non-zero exit
                    # (e.g. OOM kill at startup): fail — the caller inspects
                    # .State once more before removal to surface the reason.
                    return False
                health = state.get("health")
                if health == "healthy":
                    return True
                # No HEALTHCHECK in image: prove the :3000 listener via the
                # same in-container probe the HEALTHCHECK uses.
                if (
                    health is None
                    and state.get("running")
                    and await self._exec_health_probe(container_id_or_name)
                ):
                    return True
                # "starting"/"unhealthy"/unknown/failed-probe: keep polling
                # until the deadline — --restart may still recover it.
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
            except Exception:  # DNS resolution failure → fail-closed: domain not verified
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
        except Exception:  # DNS A/AAAA resolution failure → fail-closed: domain not verified
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
            except Exception as e:  # file write can raise broadly; wrap as RuntimeError for caller
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
        except Exception as e:  # Redis lock down → in-memory fallback keeps deploy scheduling alive
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
        plan_tier: str | None = None,
    ) -> tuple[str, int]:
        """Builds Docker runtime image from .next/standalone and runs container.

        ``plan_tier`` selects the cgroup limits applied to the container via
        ``get_web_builder_tier_limits`` (Story 31.1); unknown/None -> free.
        """

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

        # Opt-in per-app network isolation (Story 31.1): each app runs on its
        # own bridge network nowing-app-{ws}-{app}-net so tenant containers
        # cannot reach each other by membership. The shared
        # WEB_BUILDER_DOKPLOY_NETWORK guard does not apply in this mode —
        # the per-app net IS the isolation — but the ingress proxy container
        # must be named so it can be connected into each app network.
        per_app_network = getattr(
            app_config, "WEB_BUILDER_PER_APP_NETWORK", False
        )
        proxy_container = (
            getattr(app_config, "WEB_BUILDER_INGRESS_PROXY_CONTAINER", "") or ""
        ).strip()
        if per_app_network:
            if not proxy_container:
                raise RuntimeError(
                    "WEB_BUILDER_INGRESS_PROXY_CONTAINER is empty while "
                    "WEB_BUILDER_PER_APP_NETWORK is enabled; refusing to "
                    "deploy because the ingress proxy could not be connected "
                    "to the per-app network (public URL would 502). Set it "
                    "to the proxy container name (e.g. dokploy-traefik on "
                    "Dokploy, the compose proxy container on self-host)."
                )
            network = self._app_network_name(workspace_id, app_id)
        else:
            # Fail fast when the app bridge network is unconfigured or points
            # at a Docker builtin/reserved name: either would land the
            # container on a non-isolated network (docker0 ICC on, no tenant
            # isolation, no ingress path). Refuse loudly instead
            # (Story 31.1) — deploy_container only runs when
            # WEB_BUILDER_CONTAINER_DEPLOY_ENABLED=TRUE.
            network = (app_config.WEB_BUILDER_DOKPLOY_NETWORK or "").strip()
            if not network:
                raise RuntimeError(
                    "WEB_BUILDER_DOKPLOY_NETWORK is empty; refusing to deploy the "
                    "app container onto the default docker0 bridge. Set it to the "
                    "dedicated app bridge network that the ingress proxy also "
                    "joins (e.g. nowing-web-apps-net)."
                )
            if network.lower() in ("default", "bridge", "host", "none"):
                raise RuntimeError(
                    f"WEB_BUILDER_DOKPLOY_NETWORK={network!r} is a reserved or "
                    "builtin Docker network name; refusing to deploy the app "
                    "container onto a non-isolated network. Set it to the "
                    "dedicated app bridge network that the ingress proxy also "
                    "joins (e.g. nowing-web-apps-net)."
                )
        tier_limits = get_web_builder_tier_limits(plan_tier)

        # 1. Build image from standalone directory with a bounded timeout.
        # The runtime Dockerfile (docker/web-app.Dockerfile) has zero RUN
        # steps — only COPY/ENV/USER — so `docker build` cannot execute user
        # code; the wait_for below already bounds build time.
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

        # 3. Per-app isolation: create the app's bridge network and attach
        # the ingress proxy BEFORE docker run. Idempotent on redeploy —
        # existing network/connection is tolerated. On failure, tear down
        # any partially-created network.
        if per_app_network:
            try:
                await self._ensure_app_network(network, proxy_container)
            except Exception:  # network ensure failure → cleanup partial network then re-raise
                await self._cleanup_app_network(workspace_id, app_id)
                raise

        # 4. Generate Traefik labels (port is the stable internal port 3000).
        labels = self.generate_traefik_labels(
            app_slug=slug,
            base_domain=self.base_domain,
            port=3000,
            custom_domain=custom_domain,
        )
        label_args = []
        for k, v in labels.items():
            label_args.extend(["--label", f"{k}={v}"])

        # 5. Run container on the dedicated (or per-app) bridge network with
        # tier-scoped cgroup limits and a hardened runtime profile
        # (Story 31.1): swap disabled via --memory-swap == --memory, all
        # capabilities dropped, root filesystem read-only with a small
        # noexec/nosuid /tmp tmpfs for runtime scratch, json-file logs
        # bounded to 3x10m so a noisy tenant cannot fill the host disk.
        # USER node comes from the image; /var/run/docker.sock is never
        # mounted.
        run_cmd = [
            docker_bin,
            "run",
            "-d",
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            f"--memory={tier_limits['memory']}",
            f"--memory-swap={tier_limits['memory']}",
            f"--cpus={tier_limits['cpus']}",
            f"--pids-limit={tier_limits['pids_limit']}",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--log-opt",
            "max-size=10m",
            "--log-opt",
            "max-file=3",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            # Next.js standalone writes ISR/image-optimizer cache under
            # /app/.next/cache (WORKDIR=/app) — needs a writable mount on
            # the read-only rootfs.
            "--tmpfs",
            "/app/.next/cache:rw,noexec,nosuid,size=128m",
            "--network",
            network,
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
            await self._cleanup_app_network(workspace_id, app_id)
            raise RuntimeError("Docker run timed out after 60s") from None
        if proc_run.returncode != 0:
            await self._cleanup_app_network(workspace_id, app_id)
            raise RuntimeError(
                f"Docker run failed: {stderr_run.decode('utf-8', errors='replace')}"
            )

        container_id = stdout_run.decode("utf-8").strip()[:12]

        # 6. Inspect-based healthcheck before declaring the container ready —
        # the backend shares no network with app containers, so TCP to the
        # container name is not an option (Story 31.1).
        port = 3000
        healthcheck_timeout = getattr(
            app_config, "WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT", 60
        )
        healthcheck_retries = getattr(
            app_config, "WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES", 10
        )
        healthy = await self._healthcheck_container(
            container_name,
            timeout_seconds=healthcheck_timeout,
            retries=healthcheck_retries,
        )
        if not healthy:
            # Capture .State (OOMKilled/ExitCode/Running/Error) in ONE inspect
            # BEFORE removing the container — auto-restart can mutate state
            # between calls and erase the evidence.
            state = await self._inspect_container_state(container_name)
            await self._stop_container(container_name)
            # Per-app mode: drop the orphaned bridge network too.
            await self._cleanup_app_network(workspace_id, app_id)
            reason = ""
            if state:
                details = []
                if state.get("oom_killed"):
                    details.append("OOMKilled=true")
                if state.get("exit_code") is not None:
                    details.append(f"ExitCode={state['exit_code']}")
                if state.get("running") is not None:
                    details.append(
                        f"Running={str(state['running']).lower()}"
                    )
                if state.get("error"):
                    details.append(f"Error={state['error']}")
                if details:
                    reason = " (" + "; ".join(details) + ")"
            raise RuntimeError(
                f"Container started but failed healthcheck; removed.{reason}"
            )

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
        return await deploy_app(self, app_id, workspace_id, slug_override=slug_override, force=force, session=session)

    async def verify_and_bind_custom_domain(
        self,
        app_id: str,
        workspace_id: int,
        custom_domain: str,
        session: AsyncSession | None = None,
    ) -> CustomDomainOutput:
        """Validate custom domain FQDN, verify DNS proof-of-control, and bind it."""
        return await verify_and_bind_custom_domain(self, app_id, workspace_id, custom_domain, session=session)

