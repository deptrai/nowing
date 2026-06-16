"""Email service powered by Resend.

Graceful no-op when RESEND_API_KEY is unset — logs a warning, never crashes.
This allows the app to boot and function without email (e.g., local dev).

Usage:
    from app.services.email_service import send_welcome_email, send_verify_email, send_reset_password_email
"""

import logging
import os

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Nowing <onboarding@resend.dev>")
FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL", "https://nowing.net")


def _is_configured() -> bool:
    """Check if Resend is configured (has API key)."""
    return bool(RESEND_API_KEY.strip())


def _get_client():
    """Lazy-init Resend client."""
    import resend

    resend.api_key = RESEND_API_KEY
    return resend


# ---------------------------------------------------------------------------
# Welcome email (after registration, non-blocking)
# ---------------------------------------------------------------------------


def send_welcome_email(email: str, display_name: str | None = None) -> None:
    """Send a welcome email after successful registration."""
    if not _is_configured():
        logger.warning("[Email] RESEND_API_KEY not set — skipping welcome email to %s", email)
        return

    name = display_name or email.split("@")[0]
    try:
        client = _get_client()
        client.Emails.send(
            {
                "from": RESEND_FROM_EMAIL,
                "to": [email],
                "subject": f"Welcome to Nowing, {name}! 🎉",
                "html": f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
    <h1 style="font-size: 24px; color: #111;">Welcome to Nowing!</h1>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        Hi {name},
    </p>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        Your account has been created. Please verify your email to get started with AI-powered knowledge search for your team.
    </p>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        Check your inbox for a verification link, or log in at:
    </p>
    <a href="{FRONTEND_URL}/login" style="display: inline-block; background: #111; color: #fff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">
        Sign In to Nowing
    </a>
    <p style="font-size: 14px; color: #888; margin-top: 32px;">
        — The Nowing Team
    </p>
</div>
""",
            }
        )
        logger.info("[Email] Welcome email sent to %s", email)
    except Exception as exc:
        logger.warning("[Email] Failed to send welcome email to %s: %s", email, exc)


# ---------------------------------------------------------------------------
# Verify email (with token link)
# ---------------------------------------------------------------------------


def send_verify_email(email: str, token: str, display_name: str | None = None) -> None:
    """Send email verification link."""
    if not _is_configured():
        logger.warning("[Email] RESEND_API_KEY not set — skipping verify email to %s", email)
        return

    name = display_name or email.split("@")[0]
    verify_url = f"{FRONTEND_URL}/verify-token?token={token}"

    try:
        client = _get_client()
        client.Emails.send(
            {
                "from": RESEND_FROM_EMAIL,
                "to": [email],
                "subject": "Verify your Nowing email",
                "html": f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
    <h1 style="font-size: 24px; color: #111;">Verify your email</h1>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        Hi {name},
    </p>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        Click the button below to verify your email address and activate your Nowing account.
    </p>
    <a href="{verify_url}" style="display: inline-block; background: #111; color: #fff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">
        Verify Email
    </a>
    <p style="font-size: 14px; color: #888; margin-top: 32px;">
        If you didn't create an account, you can safely ignore this email.
    </p>
    <p style="font-size: 14px; color: #888;">
        — The Nowing Team
    </p>
</div>
""",
            }
        )
        logger.info("[Email] Verify email sent to %s", email)
    except Exception as exc:
        logger.warning("[Email] Failed to send verify email to %s: %s", email, exc)


# ---------------------------------------------------------------------------
# Forgot password (reset link)
# ---------------------------------------------------------------------------


def send_reset_password_email(email: str, token: str, display_name: str | None = None) -> None:
    """Send password reset link."""
    if not _is_configured():
        logger.warning("[Email] RESEND_API_KEY not set — skipping reset email to %s", email)
        return

    name = display_name or email.split("@")[0]
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"

    try:
        client = _get_client()
        client.Emails.send(
            {
                "from": RESEND_FROM_EMAIL,
                "to": [email],
                "subject": "Reset your Nowing password",
                "html": f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
    <h1 style="font-size: 24px; color: #111;">Reset your password</h1>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        Hi {name},
    </p>
    <p style="font-size: 16px; color: #444; line-height: 1.6;">
        We received a request to reset your password. Click the button below to choose a new one.
    </p>
    <a href="{reset_url}" style="display: inline-block; background: #111; color: #fff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">
        Reset Password
    </a>
    <p style="font-size: 14px; color: #888; margin-top: 32px;">
        This link expires in 1 hour. If you didn't request a reset, you can safely ignore this email.
    </p>
    <p style="font-size: 14px; color: #888;">
        — The Nowing Team
    </p>
</div>
""",
            }
        )
        logger.info("[Email] Reset password email sent to %s", email)
    except Exception as exc:
        logger.warning("[Email] Failed to send reset email to %s: %s", email, exc)
