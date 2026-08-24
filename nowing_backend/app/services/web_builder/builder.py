"""Build runner service for Next.js web applications (Story 27.1b / AD-113 / AD-113a).

Executes npm dependency installation and standalone next build in an isolated,
resource-bounded subprocess with logging, timeout, and concurrency limits.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shlex
import shutil
import signal
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.config import config
from app.db import TokenUsage, Workspace, WorkspaceApp
from app.services.web_builder.schemas import BuildResult
from app.services.web_builder.validator import validate_project_security

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_global_semaphore: asyncio.Semaphore | None = None
_background_tasks: set[asyncio.Task[None]] = set()


def _get_global_build_semaphore(max_concurrent: int) -> asyncio.Semaphore:
    """Return a process-wide asyncio.Semaphore for concurrency bounding."""
    global _global_semaphore
    if _global_semaphore is None:
        _global_semaphore = asyncio.Semaphore(max_concurrent)
    return _global_semaphore


class BuilderService:
    """Service responsible for compiling Next.js projects to standalone preview targets."""

    _build_locks: dict[str, asyncio.Lock] = {}
    _build_lock_refs: dict[str, int] = {}
    _build_lock_creation_lock = asyncio.Lock()

    def __init__(
        self,
        storage_base_path: str | None = None,
        build_timeout_seconds: int | None = None,
        max_concurrent_builds: int | None = None,
    ):
        self.storage_base_path = Path(
            storage_base_path or config.FILE_STORAGE_LOCAL_PATH
        ).resolve()
        self.build_timeout_seconds = (
            build_timeout_seconds or config.WEB_BUILDER_BUILD_TIMEOUT_SECONDS
        )
        self.max_concurrent_builds = (
            max_concurrent_builds or config.WEB_BUILDER_MAX_CONCURRENT_BUILDS
        )
        if max_concurrent_builds is not None:
            self.semaphore = asyncio.Semaphore(max_concurrent_builds)
        else:
            self.semaphore = _get_global_build_semaphore(self.max_concurrent_builds)

    async def _acquire_build_lock(self, app_id: str):
        """Acquire a per-app build lock using Redis if available, otherwise in-memory."""
        try:
            from app.redis_client import get_redis_client

            redis_client = await get_redis_client()
            await redis_client.ping()
            return redis_client.lock(
                f"web_builder:build_lock:{app_id}",
                timeout=float(self.build_timeout_seconds) + 60.0,
                thread_local=False,
                blocking_timeout=float(self.build_timeout_seconds) + 60.0,
            )
        except Exception as e:
            logger.warning(
                "Redis build lock unavailable for app_id=%s; using in-memory fallback: %s",
                app_id,
                e,
            )

        async with BuilderService._build_lock_creation_lock:
            if app_id not in BuilderService._build_locks:
                BuilderService._build_locks[app_id] = asyncio.Lock()
                BuilderService._build_lock_refs[app_id] = 0
            BuilderService._build_lock_refs[app_id] += 1
        return BuilderService._build_locks[app_id]

    async def _release_build_lock(self, app_id: str) -> None:
        """Release the per-app build lock and clean up when no refs remain."""
        async with BuilderService._build_lock_creation_lock:
            refs = BuilderService._build_lock_refs.get(app_id, 1) - 1
            if refs <= 0:
                BuilderService._build_lock_refs.pop(app_id, None)
                BuilderService._build_locks.pop(app_id, None)
            else:
                BuilderService._build_lock_refs[app_id] = refs

    async def build_project(
        self,
        app_id: str,
        workspace_id: int,
        project_dir: Path | str,
        app_entity: WorkspaceApp | None = None,
        session: AsyncSession | None = None,
    ) -> BuildResult:
        """Run npm ci + next build inside project_dir and transition WorkspaceApp state.

        Args:
            app_id: Unique application UUID.
            workspace_id: Owning workspace ID.
            project_dir: Local filesystem path to the project source directory.
            app_entity: Optional ORM entity to update status and logs on.
            session: Optional AsyncSession for committing entity updates and TokenUsage.
        """
        resolved_base = self.storage_base_path.resolve()
        resolved_project_dir = Path(project_dir).resolve()

        # Security: Path traversal verification.
        # Must be strictly within FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/
        expected_scoped_dir = (
            resolved_base / "web-app" / str(workspace_id) / app_id
        ).resolve()
        if (
            not resolved_project_dir.is_relative_to(expected_scoped_dir)
            and resolved_project_dir != expected_scoped_dir
        ):
            logger.error(
                "Security violation: path traversal attempt in build_project. target=%s, expected_base=%s",
                resolved_project_dir,
                expected_scoped_dir,
            )
            raise ValueError(
                f"Path traversal detected: Invalid project directory '{project_dir}'"
            )

        if not (resolved_project_dir / "package.json").exists():
            error_msg = f"package.json not found in {resolved_project_dir}"
            if app_entity:
                app_entity.status = "build_failed"
                app_entity.error_message = error_msg
            return BuildResult(
                status="build_failed",
                success=False,
                error=error_msg,
                logs=error_msg,
            )

        # Store build logs in a dedicated directory outside .next so Next.js build clean does not wipe it
        log_dir = resolved_project_dir / ".build_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "build.log"

        legacy_log_dir = resolved_project_dir / ".next"
        legacy_log_dir.mkdir(parents=True, exist_ok=True)
        legacy_log_file = legacy_log_dir / "build.log"

        # Per-build npm cache isolated under the project directory (D2)
        npm_cache_dir = resolved_project_dir / ".npm-cache"
        npm_cache_dir.mkdir(parents=True, exist_ok=True)

        accumulated_logs: list[str] = []

        # Reset log file on fresh build
        with contextlib.suppress(Exception):
            log_file.write_text("", encoding="utf-8")
            legacy_log_file.write_text("", encoding="utf-8")

        def _append_log(message: str) -> None:
            accumulated_logs.append(message)
            with (
                contextlib.suppress(Exception),
                open(log_file, "a", encoding="utf-8") as f,
            ):
                f.write(message + "\n")
            with (
                contextlib.suppress(Exception),
                open(legacy_log_file, "a", encoding="utf-8") as f,
            ):
                f.write(message + "\n")

        # ponytail: per-app build lock is held for the whole build so two
        # requests cannot compile the same app_id concurrently; the global
        # semaphore still bounds total concurrent builds.
        build_lock = await self._acquire_build_lock(app_id)
        try:
            async with build_lock, self.semaphore:
                logger.info(
                    "Starting build for app_id=%s in %s", app_id, resolved_project_dir
                )
                _append_log(
                    f"--- Build started for app {app_id} (workspace {workspace_id}) ---"
                )

                if app_entity:
                    app_entity.status = "building"
                    if session:
                        with contextlib.suppress(Exception):
                            await session.flush()

                # Record TokenUsage on build attempt, not only success (AC-3)
                await self._record_token_usage(
                    workspace_id=workspace_id,
                    app_id=app_id,
                    cost_micros=config.WEB_BUILDER_BUILD_COST_MICROS,
                    user_id=app_entity.user_id if app_entity else None,
                    session=session,
                )

                # Step 1: Install dependencies with --ignore-scripts
                use_ci = (resolved_project_dir / "package-lock.json").exists()
                install_cmd = (
                    ["npm", "ci", "--ignore-scripts"]
                    if use_ci
                    else ["npm", "install", "--ignore-scripts"]
                )

                # Step 2: Run next build standalone
                build_cmd = ["npx", "--no-install", "next", "build"]

                try:
                    if config.WEB_BUILDER_DOCKER_SANDBOX_ENABLED:
                        # Install with network, then build offline in separate hardened containers (R-04).
                        install_shell = shlex.join(install_cmd)
                        _append_log(f"$ {install_shell}")
                        code, stdout, stderr = await self._run_subprocess(
                            ["sh", "-c", install_shell],
                            resolved_project_dir,
                            network="bridge",
                        )
                        if stdout:
                            _append_log(stdout)
                        if stderr:
                            _append_log(stderr)

                        if code != 0:
                            err = f"Dependency installation failed with code {code}\n{stderr or stdout}"
                            logger.warning(
                                "Build install failed for app_id=%s: %s", app_id, err
                            )
                            if app_entity:
                                app_entity.status = "build_failed"
                                app_entity.error_message = (
                                    stderr or stdout or "npm install failed"
                                )
                                if session:
                                    with contextlib.suppress(Exception):
                                        await session.flush()
                            return BuildResult(
                                status="build_failed",
                                success=False,
                                error=err,
                                logs="\n".join(accumulated_logs),
                            )

                        # Security: audit installed source and dependency scripts before build (R-05).
                        is_secure, security_issues = validate_project_security(
                            resolved_project_dir
                        )
                        if not is_secure:
                            sec_err = f"Security audit failed: {', '.join(security_issues)}"
                            logger.error(
                                "Build security audit failure for app_id=%s: %s", app_id, sec_err
                            )
                            if app_entity:
                                app_entity.status = "build_failed"
                                app_entity.error_message = sec_err
                                if session:
                                    with contextlib.suppress(Exception):
                                        await session.flush()
                            return BuildResult(
                                status="build_failed",
                                success=False,
                                error=sec_err,
                                logs="\n".join(accumulated_logs),
                            )

                        build_shell = shlex.join(build_cmd)
                        _append_log(f"$ {build_shell}")
                        code, stdout, stderr = await self._run_subprocess(
                            ["sh", "-c", build_shell],
                            resolved_project_dir,
                            network="none",
                        )
                        if stdout:
                            _append_log(stdout)
                        if stderr:
                            _append_log(stderr)

                        if code != 0:
                            err = f"Build failed with code {code}\n{stderr or stdout}"
                            logger.warning(
                                "Build failed for app_id=%s: %s", app_id, err
                            )
                            if app_entity:
                                app_entity.status = "build_failed"
                                app_entity.error_message = (
                                    stderr or stdout or "Build failed"
                                )
                                if session:
                                    with contextlib.suppress(Exception):
                                        await session.flush()
                            return BuildResult(
                                status="build_failed",
                                success=False,
                                error=err,
                                logs="\n".join(accumulated_logs),
                            )
                    else:
                        _append_log(f"$ {' '.join(install_cmd)}")
                        code, stdout, stderr = await self._run_subprocess(
                            install_cmd, resolved_project_dir
                        )
                        if stdout:
                            _append_log(stdout)
                        if stderr:
                            _append_log(stderr)

                        if code != 0:
                            err = f"Dependency installation failed with code {code}\n{stderr or stdout}"
                            logger.warning(
                                "Build install failed for app_id=%s: %s", app_id, err
                            )
                            if app_entity:
                                app_entity.status = "build_failed"
                                app_entity.error_message = (
                                    stderr or stdout or "npm install failed"
                                )
                                if session:
                                    with contextlib.suppress(Exception):
                                        await session.flush()
                            return BuildResult(
                                status="build_failed",
                                success=False,
                                error=err,
                                logs="\n".join(accumulated_logs),
                            )

                        # Security: audit installed source and dependency scripts before build (R-05).
                        is_secure, security_issues = validate_project_security(
                            resolved_project_dir
                        )
                        if not is_secure:
                            sec_err = f"Security audit failed: {', '.join(security_issues)}"
                            logger.error(
                                "Build security audit failure for app_id=%s: %s", app_id, sec_err
                            )
                            if app_entity:
                                app_entity.status = "build_failed"
                                app_entity.error_message = sec_err
                                if session:
                                    with contextlib.suppress(Exception):
                                        await session.flush()
                            return BuildResult(
                                status="build_failed",
                                success=False,
                                error=sec_err,
                                logs="\n".join(accumulated_logs),
                            )

                        _append_log(f"$ {' '.join(build_cmd)}")
                        code, stdout, stderr = await self._run_subprocess(
                            build_cmd, resolved_project_dir
                        )
                        if stdout:
                            _append_log(stdout)
                        if stderr:
                            _append_log(stderr)

                        if code != 0:
                            err = f"Next.js build failed with code {code}\n{stderr or stdout}"
                            logger.warning(
                                "Build compilation failed for app_id=%s: %s",
                                app_id,
                                err,
                            )
                            if app_entity:
                                app_entity.status = "build_failed"
                                app_entity.error_message = (
                                    stderr or stdout or "next build failed"
                                )
                                if session:
                                    with contextlib.suppress(Exception):
                                        await session.flush()
                            return BuildResult(
                                status="build_failed",
                                success=False,
                                error=err,
                                logs="\n".join(accumulated_logs),
                            )

                    # Step 3: Successful build
                    _append_log("--- Build completed successfully ---")
                    standalone_dir = resolved_project_dir / ".next" / "standalone"
                    if app_entity:
                        app_entity.status = "preview_ready"
                        app_entity.error_message = None
                        if not app_entity.preview_url:
                            app_entity.preview_url = f"/api/v1/web-builder/apps/{app_id}/preview?workspace_id={workspace_id}"
                        if session:
                            with contextlib.suppress(Exception):
                                await session.flush()

                    return BuildResult(
                        status="preview_ready",
                        success=True,
                        build_output_dir=str(
                            standalone_dir
                            if standalone_dir.exists()
                            else resolved_project_dir
                        ),
                        logs="\n".join(accumulated_logs),
                    )

                except TimeoutError:
                    timeout_err = (
                        f"Build timed out after {self.build_timeout_seconds} seconds"
                    )
                    logger.error("Build timeout for app_id=%s", app_id)
                    _append_log(f"ERROR: {timeout_err}")
                    if app_entity:
                        app_entity.status = "build_failed"
                        app_entity.error_message = timeout_err
                        if session:
                            with contextlib.suppress(Exception):
                                await session.flush()
                    return BuildResult(
                        status="build_failed",
                        success=False,
                        error=timeout_err,
                        logs="\n".join(accumulated_logs),
                    )
                except Exception as exc:
                    exc_err = f"Unexpected build error: {exc}"
                    logger.exception("Build unexpected exception for app_id=%s", app_id)
                    _append_log(f"ERROR: {exc_err}")
                    if app_entity:
                        app_entity.status = "build_failed"
                        app_entity.error_message = str(exc)
                        if session:
                            with contextlib.suppress(Exception):
                                await session.flush()
                    return BuildResult(
                        status="build_failed",
                        success=False,
                        error=exc_err,
                        logs="\n".join(accumulated_logs),
                    )
        finally:
            await self._release_build_lock(app_id)

    def _get_sanitized_build_env(self, project_dir: Path) -> dict[str, str]:
        """Construct a strictly scrubbed environment containing zero sensitive host secrets (DB, tokens, keys).

        No host HOME, USER, SHELL, or PATH is forwarded. A minimal, well-known
        PATH is supplied so npm/npx can resolve in both host and container
        runners, and npm cache is scoped to the project directory.
        """
        safe_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:/opt/homebrew/sbin",
            "NODE_ENV": "production",
            "NEXT_TELEMETRY_DISABLED": "1",
            "CI": "1",
            "npm_config_cache": str(project_dir / ".npm-cache"),
        }
        for key in ("TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "TERM"):
            if key in os.environ:
                safe_env[key] = os.environ[key]
        return safe_env

    async def _run_subprocess(
        self,
        cmd: list[str],
        cwd: Path,
        network: str | None = None,
    ) -> tuple[int, str, str]:
        """Execute a subprocess asynchronously with strict timeout bounding and process group cleanup."""
        actual_cmd = cmd
        env = self._get_sanitized_build_env(cwd)
        container_name: str | None = None

        # If Docker sandbox enabled, wrap inside a single ephemeral container.
        # Network is allowed so npm ci and next build can reach the registry.
        if config.WEB_BUILDER_DOCKER_SANDBOX_ENABLED:
            if len(cmd) >= 3 and cmd[0] == "sh" and cmd[1] == "-c":
                shell_cmd = cmd[2]
            else:
                shell_cmd = shlex.join(cmd)

            image = f"node:{config.WEB_BUILDER_BUILD_NODE_VERSION}-alpine"
            digest = config.WEB_BUILDER_BUILD_NODE_IMAGE_DIGEST
            if digest:
                image = f"{image}@{digest}"

            docker_bin = shutil.which("docker") or "docker"
            container_name = f"nowing-build-{uuid.uuid4().hex[:12]}"
            docker_args = [
                docker_bin,
                "run",
                "--rm",
                "--name",
                container_name,
                "--user",
                "1000:1000",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--memory",
                "1024m",
                "--cpus",
                "2.0",
                "-v",
                f"{cwd.resolve()}:/app",
                "-w",
                "/app",
                "-e",
                "NODE_ENV=production",
                "-e",
                "NEXT_TELEMETRY_DISABLED=1",
                "-e",
                "CI=1",
                "-e",
                "npm_config_cache=/app/.npm-cache",
            ]
            if network:
                docker_args.extend(["--network", network])
            docker_args.extend([image, "sh", "-c", shell_cmd])
            actual_cmd = docker_args

        kwargs: dict = {
            "cwd": str(cwd),
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "env": env,
        }
        if hasattr(os, "setsid"):
            kwargs["preexec_fn"] = os.setsid

        proc = await asyncio.create_subprocess_exec(*actual_cmd, **kwargs)
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(self.build_timeout_seconds),
            )
            return (
                proc.returncode or 0,
                stdout_b.decode("utf-8", errors="replace"),
                stderr_b.decode("utf-8", errors="replace"),
            )
        except TimeoutError:
            with contextlib.suppress(Exception):
                if (
                    hasattr(os, "killpg")
                    and hasattr(os, "getpgid")
                    and isinstance(getattr(proc, "pid", None), int)
                ):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                elif hasattr(proc, "kill"):
                    proc.kill()
            if container_name:
                # docker run --rm may not clean up if the CLI process is killed; force removal.
                with contextlib.suppress(Exception):
                    await asyncio.create_subprocess_exec(
                        shutil.which("docker") or "docker",
                        "rm",
                        "-f",
                        container_name,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
            if hasattr(proc, "wait") and callable(proc.wait):
                with contextlib.suppress(Exception):
                    res = proc.wait()
                    if asyncio.iscoroutine(res):
                        await asyncio.wait_for(res, timeout=1.0)
            raise

    async def _record_token_usage(
        self,
        workspace_id: int,
        app_id: str,
        cost_micros: int,
        user_id: UUID | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Persist a TokenUsage record for the build step."""
        if not session:
            return
        from app.capabilities.core.types import BillingUnit

        usage = TokenUsage(
            workspace_id=workspace_id,
            user_id=user_id,
            usage_type="web_builder_build",
            cost_micros=cost_micros,
            external_metadata={
                "app_id": app_id,
                "billing_unit": BillingUnit.WEB_BUILDER_BUILD.value,
            },
        )
        session.add(usage)
        with contextlib.suppress(Exception):
            await session.commit()

    @classmethod
    async def trigger_async_build(cls, app_id: str, workspace_id: int) -> None:
        """Trigger asynchronous background build execution.

        Enforces a single build per app, debits workspace credit, and transitions
        the app to the building state before compilation starts.
        """

        async def _run() -> None:
            from app.db import async_session_maker

            try:
                async with async_session_maker() as session:
                    # Lock the app row to prevent duplicate builds across workers (R-02).
                    stmt = (
                        select(WorkspaceApp)
                        .where(
                            WorkspaceApp.id == app_id,
                            WorkspaceApp.workspace_id == workspace_id,
                        )
                        .with_for_update()
                    )
                    res = await session.execute(stmt)
                    app_entity = res.scalars().first()
                    if not app_entity:
                        return

                    # Duplicate build guard: another worker already started/finished.
                    if app_entity.status in ("building", "preview_ready"):
                        return

                    # Debit build quota inside the worker so every trigger pays once.
                    cost = config.WEB_BUILDER_BUILD_COST_MICROS
                    if cost > 0:
                        ws_stmt = (
                            select(Workspace)
                            .where(Workspace.id == workspace_id)
                            .with_for_update()
                        )
                        ws_res = await session.execute(ws_stmt)
                        workspace = ws_res.scalars().first()
                        if not workspace or workspace.credit_micros_balance < cost:
                            app_entity.status = "build_failed"
                            app_entity.error_message = (
                                "Insufficient workspace credit balance for build. "
                                f"Required: {cost} micros."
                            )
                            if workspace and workspace.plan_tier == "free":
                                app_entity.error_message += (
                                    " Upgrade your workspace plan to continue building."
                                )
                            await session.commit()
                            return
                        workspace.credit_micros_balance -= cost

                    app_entity.status = "building"
                    await session.commit()

                    service = cls()
                    project_dir = Path(
                        app_entity.storage_path
                        or (
                            service.storage_base_path
                            / "web-app"
                            / str(workspace_id)
                            / app_id
                        )
                    )
                    await service.build_project(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        project_dir=project_dir,
                        app_entity=app_entity,
                        session=session,
                    )
                    await session.commit()
            except Exception as e:
                logger.exception(
                    "Fatal error in async build task for app_id=%s: %s", app_id, e
                )
                with contextlib.suppress(Exception):
                    async with async_session_maker() as err_session:
                        stmt = select(WorkspaceApp).where(
                            WorkspaceApp.id == app_id,
                            WorkspaceApp.workspace_id == workspace_id,
                        )
                        res = await err_session.execute(stmt)
                        err_app = res.scalars().first()
                        if err_app:
                            err_app.status = "build_failed"
                            err_app.error_message = f"Build runner worker error: {e}"
                            await err_session.commit()

        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    @classmethod
    def _read_tail(
        cls,
        log_file: Path,
        max_lines: int = 200,
        max_bytes: int = 256_000,
    ) -> tuple[str, int]:
        """Synchronous helper: capped read of the last N lines from a log file."""
        try:
            size = log_file.stat().st_size
            if size > max_bytes:
                with open(log_file, "rb") as f:
                    f.seek(-max_bytes, 2)
                    raw = f.read()
                # Drop a likely-partial first line so the tail starts clean
                if raw and raw[0] != ord("\n") and b"\n" in raw:
                    raw = raw.split(b"\n", 1)[1]
                content = raw.decode("utf-8", errors="replace")
            else:
                content = log_file.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            tail_lines = lines[-max_lines:] if len(lines) > max_lines else lines
            return "\n".join(tail_lines), len(tail_lines)
        except Exception as e:
            return f"Error reading logs: {e}", 1

    @classmethod
    async def get_build_logs(
        cls,
        app_id: str,
        workspace_id: int,
        storage_path: str | None = None,
        max_lines: int = 200,
    ) -> tuple[str, int]:
        """Read the last N lines from the application's build.log with path safety."""
        service = cls()
        expected_scoped_dir = (
            service.storage_base_path / "web-app" / str(workspace_id) / app_id
        ).resolve()

        if storage_path:
            project_dir = Path(storage_path).resolve()
        else:
            project_dir = expected_scoped_dir

        # Reject traversal, symlinks, and out-of-scope paths before any I/O
        if not project_dir.is_relative_to(expected_scoped_dir):
            logger.error(
                "Security violation: get_build_logs path traversal. target=%s, expected=%s",
                project_dir,
                expected_scoped_dir,
            )
            return "Invalid storage path.", 1

        try:
            # Use realpath to detect symlink loops and resolve links
            resolved_dir = project_dir.resolve()
            if resolved_dir != project_dir and not resolved_dir.is_relative_to(
                expected_scoped_dir
            ):
                return "Invalid storage path.", 1
        except (OSError, RuntimeError) as e:
            return f"Error resolving log path: {e}", 1

        # Check primary (.build_logs/build.log) and legacy (.next/build.log)
        log_file = resolved_dir / ".build_logs" / "build.log"
        if not log_file.exists():
            log_file = resolved_dir / ".next" / "build.log"

        if not log_file.exists():
            return "No build logs available yet.", 1

        # Reject symlinks and resolve-link escapes before reading (R-06).
        try:
            if log_file.is_symlink() or not log_file.resolve().is_relative_to(
                expected_scoped_dir
            ):
                logger.error(
                    "Security violation: get_build_logs symlink/escape. target=%s",
                    log_file,
                )
                return "Invalid log file.", 1
        except (OSError, RuntimeError) as e:
            return f"Error resolving log path: {e}", 1

        return await asyncio.to_thread(
            cls._read_tail, log_file, max_lines, max(1024, max_lines * 1024)
        )
