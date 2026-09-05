"""App factory helpers."""
import contextlib
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address  # noqa: F401 — kept for reference
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from starlette.routing import Host
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.app.errors import (
    _http_exception_handler,
    _nowing_error_handler,
    _rate_limit_exceeded_handler,
    _unhandled_exception_handler,
    _validation_error_handler,
)
from app.app.lifespan import lifespan
from app.app.rate_limiter import (
    rate_limit_login,
    rate_limit_password_reset,
    rate_limit_register,
)
from app.app.shared import (
    _backend_build_id,
    registration_allowed,
)
from app.auth.context import AuthContext
from app.auth.csrf import CsrfOriginMiddleware
from app.auth.impersonation import ImpersonationGuardMiddleware
from app.config import (
    config,
)
from app.db import get_async_session
from app.exceptions import NowingError
from app.rate_limiter import limiter
from app.routes import router as crud_router
from app.routes.alert_rules_routes import (
    alerts_alias_router,
    router as alert_rules_router,
)
from app.routes.auth_routes import (
    resolve_google_user,
    router as auth_router,
    session_router,
)
from app.routes.chainlens_internal import router as chainlens_internal_router
from app.routes.dsh_routes import dsh_internal_router, dsh_public_router
from app.routes.hybrid_llm_routes import (
    hybrid_internal_router,
    hybrid_public_router,
)
from app.routes.lead_batch_routes import router as lead_batch_router
from app.routes.narrative_reports_routes import router as narrative_reports_router
from app.routes.self_host_research import router as self_host_research_router
from app.routes.users_routes import router as users_router
from app.routes.web_builder_routes import host_router as web_builder_host_router
from app.routes.zero_context_routes import router as zero_context_router
from app.schemas import UserCreate, UserRead
from app.users import SECRET, allow_any_principal, auth_backend, fastapi_users
from app.utils.perf import log_system_snapshot

_error_logger = logging.getLogger("nowing.errors")

rate_limit_logger = logging.getLogger("nowing.rate_limit")


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# limiter is imported from app.rate_limiter (shared module to avoid circular imports)


app = FastAPI(lifespan=lifespan)

# Register rate limiter and custom 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register structured global exception handlers (order matters: most specific first)
app.add_exception_handler(NowingError, _nowing_error_handler)
app.add_exception_handler(RequestValidationError, _validation_error_handler)
app.add_exception_handler(HTTPException, _http_exception_handler)
app.add_exception_handler(Exception, _unhandled_exception_handler)


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and echo it in the response."""

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)
app.add_middleware(ImpersonationGuardMiddleware)


# ---------------------------------------------------------------------------
# Request-level performance middleware
# ---------------------------------------------------------------------------
# Logs wall-clock time, method, path, and status for every request so we can
# spot slow endpoints in production logs.

_PERF_SLOW_REQUEST_THRESHOLD = float(
    __import__("os").environ.get("PERF_SLOW_REQUEST_MS", "2000")
)


class RequestPerfMiddleware(BaseHTTPMiddleware):
    """Middleware that logs per-request wall-clock time.

    - ALL requests are logged at DEBUG level.
    - Requests exceeding PERF_SLOW_REQUEST_MS (default 2000ms) are logged at
      WARNING level with a system snapshot so we can correlate slow responses
      with CPU/memory usage at that moment.
    """

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        path = request.url.path

        if elapsed_ms > _PERF_SLOW_REQUEST_THRESHOLD:
            with contextlib.suppress(Exception):
                from opentelemetry import trace

                span = trace.get_current_span()
                span.set_attribute("slow_request", True)
                span.set_attribute("nowing.request.elapsed_ms", elapsed_ms)
                span.set_attribute("http.route", path)
            log_system_snapshot("slow_request")

        return response


app.add_middleware(RequestPerfMiddleware)

# Add SlowAPI middleware for automatic rate limiting
# Uses Starlette BaseHTTPMiddleware (not the raw ASGI variant) to avoid
# corrupting StreamingResponse — SlowAPIASGIMiddleware re-sends
# http.response.start on every body chunk, breaking SSE/streaming endpoints.
app.add_middleware(SlowAPIMiddleware)

# Add ProxyHeaders middleware FIRST to trust proxy headers (e.g., from Cloudflare)
# This ensures FastAPI uses HTTPS in redirects when behind a proxy
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Add CORS middleware
# When using credentials, we must specify exact origins (not "*")
# Build allowed origins list from NEXT_FRONTEND_URL
allowed_origins = []
if config.NEXT_FRONTEND_URL:
    allowed_origins.append(config.NEXT_FRONTEND_URL)
    # Also allow without trailing slash and with www/without www variants
    frontend_url = config.NEXT_FRONTEND_URL.rstrip("/")
    if frontend_url not in allowed_origins:
        allowed_origins.append(frontend_url)
    # Handle www variants
    if "://www." in frontend_url:
        non_www = frontend_url.replace("://www.", "://")
        if non_www not in allowed_origins:
            allowed_origins.append(non_www)
    elif "://" in frontend_url and "://www." not in frontend_url:
        # Add www variant
        www_url = frontend_url.replace("://", "://www.")
        if www_url not in allowed_origins:
            allowed_origins.append(www_url)

allowed_origins.extend(
    [  # For local development and desktop app
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)

app.add_middleware(CsrfOriginMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|chrome-extension://[a-z]+$)",
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
    # Cache CORS preflight (OPTIONS) responses for 24h. Browsers clamp:
    # Chrome/Edge cap at 7200s, Firefox honours up to 86400s. Setting the
    # higher value lets each browser cache for as long as it allows. This
    # eliminates an OPTIONS round-trip on every non-simple request from
    # FRONTEND_URL to BACKEND_URL.
    max_age=86400,
)

# Password / email-based auth routers are only mounted when not running in
# Google-OAuth-only mode. Mounting them in OAuth-only prod previously left
# POST /auth/register reachable, which is the bypass that allowed bots to
# create non-OAuth users in spite of AUTH_TYPE=GOOGLE.
if config.AUTH_TYPE != "GOOGLE":
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
        dependencies=[
            Depends(rate_limit_login),
            Depends(
                registration_allowed
            ),  # honour REGISTRATION_ENABLED kill switch on login too
        ],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
        dependencies=[
            Depends(rate_limit_register),
            Depends(registration_allowed),
        ],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
        dependencies=[Depends(rate_limit_password_reset)],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )

# /users/me uses the unified auth resolver so web cookie sessions, desktop bearer
# sessions, and PAT principals all resolve through the same authority.
app.include_router(users_router)

# Include custom auth routes (refresh token, logout)
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(zero_context_router)
app.include_router(alert_rules_router)
app.include_router(alerts_alias_router)
app.include_router(narrative_reports_router)

if config.AUTH_TYPE == "GOOGLE":
    from fastapi.responses import RedirectResponse

    from app.users import google_oauth_client

    # Determine if we're in a secure context (HTTPS) or local development (HTTP)
    # The CSRF cookie must have secure=False for HTTP (localhost development)
    is_secure_context = config.BACKEND_URL and config.BACKEND_URL.startswith("https://")

    # For cross-origin OAuth (frontend and backend on different domains):
    # - SameSite=None is required to allow cross-origin cookie setting
    # - Secure=True is required when SameSite=None
    # For same-origin or local development, use SameSite=Lax (default)
    csrf_cookie_samesite = "none" if is_secure_context else "lax"

    # Extract the domain from BACKEND_URL for cookie domain setting
    # This helps with cross-site cookie issues in Firefox/Safari
    csrf_cookie_domain = None
    if config.BACKEND_URL:
        from urllib.parse import urlparse

        parsed_url = urlparse(config.BACKEND_URL)
        csrf_cookie_domain = parsed_url.hostname

    from fastapi_users.jwt import decode_jwt
    from fastapi_users.router.oauth import (
        CSRF_TOKEN_COOKIE_NAME,
        CSRF_TOKEN_KEY,
        STATE_TOKEN_AUDIENCE,
        generate_state_token,
    )
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    from app.users import get_user_manager

    def _google_callback_url(request: Request) -> str:
        if config.BACKEND_URL:
            return f"{config.BACKEND_URL}/auth/google/callback"
        return str(request.url_for("google_oauth_callback"))

    def _set_google_oauth_csrf_cookie(response: Response, csrf_token: str) -> None:
        response.set_cookie(
            key=CSRF_TOKEN_COOKIE_NAME,
            value=csrf_token,
            max_age=3600,
            path="/",
            domain=csrf_cookie_domain,
            secure=is_secure_context,
            httponly=False,  # Required for cross-site OAuth in Firefox/Safari
            samesite=csrf_cookie_samesite,
        )

    async def _google_authorization_url(request: Request, response: Response) -> str:
        import secrets

        csrf_token = secrets.token_urlsafe(32)
        state = generate_state_token(
            {CSRF_TOKEN_KEY: csrf_token},
            SECRET,
            lifetime_seconds=3600,
        )
        authorization_url = await google_oauth_client.get_authorization_url(
            _google_callback_url(request),
            state,
            scope=["openid", "email", "profile"],
        )
        _set_google_oauth_csrf_cookie(response, csrf_token)
        return authorization_url

    @app.get(
        "/auth/google/authorize",
        tags=["auth"],
        dependencies=[Depends(registration_allowed)],
    )
    async def google_authorize(request: Request, response: Response):
        """Return Google's authorization URL, matching fastapi-users' shape."""
        return {"authorization_url": await _google_authorization_url(request, response)}

    @app.get(
        "/auth/google/callback",
        name="google_oauth_callback",
        tags=["auth"],
        dependencies=[Depends(registration_allowed)],
    )
    async def google_oauth_callback(
        request: Request,
        user_manager=Depends(get_user_manager),
    ):
        """Handle web Google OAuth with the same verified-email policy as desktop."""
        import secrets

        import httpx
        import jwt as pyjwt

        state = request.query_params.get("state")
        code = request.query_params.get("code")
        if not state or not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth callback missing code or state",
            )

        try:
            state_data = decode_jwt(state, SECRET, [STATE_TOKEN_AUDIENCE])
        except pyjwt.DecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ACCESS_TOKEN_DECODE_ERROR",
            ) from exc
        except pyjwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ACCESS_TOKEN_ALREADY_EXPIRED",
            ) from exc

        cookie_csrf_token = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
        state_csrf_token = state_data.get(CSRF_TOKEN_KEY)
        if (
            not cookie_csrf_token
            or not state_csrf_token
            or not secrets.compare_digest(cookie_csrf_token, state_csrf_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAUTH_INVALID_STATE",
            )

        token_payload = {
            "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _google_callback_url(request),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=token_payload,
            )
        if token_response.status_code >= 400:
            _error_logger.warning(
                "Web Google OAuth exchange failed: %s", token_response.text
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth exchange failed",
            )

        token_data = token_response.json()
        google_access_token = token_data.get("access_token")
        google_id_token_value = token_data.get("id_token")
        if not google_access_token or not google_id_token_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth exchange failed",
            )

        try:
            claims = google_id_token.verify_oauth2_token(
                google_id_token_value,
                google_requests.Request(),
                config.GOOGLE_OAUTH_CLIENT_ID,
            )
        except Exception as exc:
            _error_logger.warning("Web Google id_token verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google identity token",
            ) from exc

        expires_at = (
            int(datetime.now(UTC).timestamp()) + int(token_data["expires_in"])
            if token_data.get("expires_in")
            else None
        )
        user = await resolve_google_user(
            user_manager=user_manager,
            request=request,
            google_access_token=google_access_token,
            claims=claims,
            expires_at=expires_at,
            google_refresh_token=token_data.get("refresh_token"),
        )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LOGIN_BAD_CREDENTIALS",
            )

        response = await auth_backend.login(auth_backend.get_strategy(), user)
        await user_manager.on_after_login(user, request, response)
        response.delete_cookie(
            key=CSRF_TOKEN_COOKIE_NAME,
            path="/",
            domain=csrf_cookie_domain,
            secure=is_secure_context,
            samesite=csrf_cookie_samesite,
            httponly=False,
        )
        return response

    # Add a redirect-based authorize endpoint for Firefox/Safari compatibility
    # This endpoint performs a server-side redirect instead of returning JSON
    # which fixes cross-site cookie issues where browsers don't send cookies
    # set via cross-origin fetch requests on subsequent redirects.
    # The registration_allowed dependency mirrors the OAuth router above so
    # the kill switch fails fast here instead of bouncing users to Google
    # only to 403 on the callback.
    @app.get(
        "/auth/google/authorize-redirect",
        tags=["auth"],
        dependencies=[Depends(registration_allowed)],
    )
    async def google_authorize_redirect(
        request: Request,
    ):
        """
        Redirect-based OAuth authorization endpoint.

        Unlike the standard /auth/google/authorize endpoint that returns JSON,
        this endpoint directly redirects the browser to Google's OAuth page.
        This fixes CSRF cookie issues in Firefox and Safari where cookies set
        via cross-origin fetch requests are not sent on subsequent redirects.
        """
        response = RedirectResponse(url="", status_code=302)
        authorization_url = await _google_authorization_url(request, response)
        response.headers["location"] = authorization_url
        return response


# Anonymous (no-login) chat routes — mounted at /api/v1/public/anon-chat
from app.routes.anonymous_chat_routes import (  # noqa: E402
    router as anonymous_chat_router,
)

app.include_router(anonymous_chat_router)

# Internal chainlens-research callbacks are mounted at /v1 per the
# cross-project contract (Epic 47 / Story 20.4).
app.include_router(chainlens_internal_router, prefix="/v1")

# Self-hosted instances route deep-research calls through Nowing Cloud.
app.include_router(self_host_research_router, prefix="/v1")

app.include_router(lead_batch_router, prefix="/api/v1", tags=["lead-batch"])
app.include_router(dsh_public_router, prefix="/api/v1", tags=["dsh"])

# Internal DSH worker checkpoint callback is mounted at /v1.
app.include_router(dsh_internal_router, prefix="/v1")

# Hybrid LLM routing (Story 26.3)
app.include_router(hybrid_public_router, prefix="/api/v1", tags=["hybrid-llm"])
app.include_router(hybrid_internal_router, prefix="/v1", tags=["hybrid-llm-internal"])

app.include_router(crud_router, prefix="/api/v1", tags=["crud"])
app.include_router(crud_router, prefix="/api", tags=["crud"])
app.include_router(crud_router)


@app.get("/health", tags=["health"])
@limiter.exempt
async def health_check():
    """Lightweight liveness probe exempt from rate limiting."""
    return {"status": "ok", "build_id": _backend_build_id()}


@app.get("/ready", tags=["health"])
@limiter.exempt
async def readiness_check():
    """Readiness probe.

    Verifies that the schema state required by downstream services is
    present. Specifically checks that the ``zero_publication`` Postgres
    logical-replication publication exists; without it zero-cache crash-loops
    on `Unknown or invalid publications`.

    Returns 200 when ready, 503 otherwise. Used by the docker-compose
    backend healthcheck and by ``install.ps1`` / ``install.sh`` post-up
    verification.
    """
    from sqlalchemy import text

    from app.db import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT 1 FROM pg_publication WHERE pubname = 'zero_publication'")
        )
        if result.first() is None:
            raise HTTPException(
                status_code=503,
                detail="zero_publication missing; run alembic upgrade head",
            )
    return {"status": "ready"}


@app.get("/verify-token")
async def authenticated_route(
    auth: AuthContext = Depends(allow_any_principal),
    session: AsyncSession = Depends(get_async_session),
):
    return {"message": "Token is valid", "method": auth.method}


# Wildcard host routing for published web apps: only match *.HOSTING_BASE_DOMAIN.
host_web_app = FastAPI()
host_web_app.include_router(web_builder_host_router)
app.router.routes.insert(
    0,
    Host(
        f"{{subdomain}}.{config.HOSTING_BASE_DOMAIN}",
        app=host_web_app,
        name="web-builder-host",
    ),
)

# Catch-all host route so custom CNAMEs and arbitrary hostnames reach the
# web-builder host router after all path routes have been tried.
app.router.routes.append(
    Host(
        "{host}",
        app=host_web_app,
        name="web-builder-host-catchall",
    )
)
