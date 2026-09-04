"""Health probe for Object Storage (S3, MinIO, Cloudflare R2)."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime

import httpx

from app.config import config
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class StorageHealthProbe(HealthProbe):
    """Probes object storage configuration and bucket accessibility."""

    def __init__(self, provider: str = "s3") -> None:
        self._provider = provider.lower()
        self._service_id = f"storage/{self._provider}"
        self._service_name = f"{self._provider.upper()} Object Storage"
        self._display_group = "Object Storage"

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "storage"

    @property
    def display_group(self) -> str:
        return self._display_group

    @property
    def interval_seconds(self) -> int:
        return 300  # 5 minutes

    def _read_credentials(self) -> dict[str, str | None]:
        """Read S3-compatible credentials from environment/config."""
        return {
            "endpoint": (
                getattr(config, "S3_ENDPOINT_URL", None)
                or os.getenv("S3_ENDPOINT_URL")
                or os.getenv("AWS_ENDPOINT_URL")
                or None
            ),
            "bucket": (
                getattr(config, "S3_BUCKET_NAME", None)
                or os.getenv("S3_BUCKET_NAME")
                or os.getenv("AWS_BUCKET_NAME")
                or None
            ),
            "access_key": (
                getattr(config, "S3_ACCESS_KEY_ID", None)
                or os.getenv("S3_ACCESS_KEY_ID")
                or os.getenv("AWS_ACCESS_KEY_ID")
                or None
            ),
            "secret_key": (
                getattr(config, "S3_SECRET_ACCESS_KEY", None)
                or os.getenv("S3_SECRET_ACCESS_KEY")
                or os.getenv("AWS_SECRET_ACCESS_KEY")
                or None
            ),
            "region": (
                getattr(config, "S3_REGION", None)
                or os.getenv("S3_REGION")
                or os.getenv("AWS_REGION")
                or "us-east-1"
            ),
        }

    async def _ping_s3(self, creds: dict[str, str | None]) -> tuple[HealthStatus, str | None]:
        endpoint = creds.get("endpoint")
        bucket = creds.get("bucket")
        access_key = creds.get("access_key")
        secret_key = creds.get("secret_key")
        region = creds.get("region") or "us-east-1"

        if not (bucket and access_key and secret_key):
            return ("not_configured", "S3 bucket, access key and secret key are required")

        # Standard AWS S3 virtual-hosted-style endpoint when none is provided.
        if not endpoint:
            endpoint = f"https://{bucket}.s3.{region}.amazonaws.com"
        elif "s3" not in endpoint.lower() and ".amazonaws.com" not in endpoint.lower():
            # If endpoint looks like a raw domain, treat it as a MinIO/R2-style base URL
            endpoint = f"{endpoint.rstrip('/')}/{bucket}"

        # Build a ListObjectsV2 request signed with AWS SigV4
        import hmac
        import hashlib
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        service = "s3"
        host = endpoint.replace("https://", "").replace("http://", "").split("/")[0]
        uri = f"/{bucket}"
        canonical_querystring = "list-type=2&max-keys=1"

        # Create canonical request
        canonical_headers = f"host:{host}\nx-amz-content-sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\nx-amz-date:{amz_date}\n"
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        payload_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        canonical_request = (
            f"GET\n{uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        k_date = hmac.new(f"AWS4{secret_key}".encode(), date_stamp.encode(), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode(), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, "aws4_request".encode(), hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        auth_header = (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        url = f"{endpoint.rstrip('/')}{uri}?{canonical_querystring}"
        headers = {
            "Authorization": auth_header,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Host": host,
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return ("healthy", None)
            if resp.status_code in (403, 401):
                return ("degraded", f"S3 credentials rejected (HTTP {resp.status_code})")
            if resp.status_code == 404:
                return ("degraded", "S3 bucket not found")
            if resp.status_code >= 500:
                return ("unavailable", f"S3 service returned HTTP {resp.status_code}")
            return ("degraded", f"S3 returned HTTP {resp.status_code}")
        except Exception as exc:
            return ("unavailable", f"S3 ping failed: {type(exc).__name__}: {exc}")

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None

        try:
            creds = self._read_credentials()
            if not (creds["endpoint"] and creds["access_key"] and creds["secret_key"] and creds["bucket"]):
                status = "not_configured"
                suggested_action = "Configure S3/Storage credentials (S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME)"
            else:
                status, last_error = await self._ping_s3(creds)
                if status != "healthy":
                    suggested_action = "Verify S3 endpoint, credentials, bucket name and network reachability"

            latency_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Storage probe error: {type(exc).__name__}"
            suggested_action = "Check object storage connectivity and credentials"

        success_rate = 100.0 if status == "healthy" else (50.0 if status == "degraded" else 0.0)
        error_rate = 0.0 if status == "healthy" else (50.0 if status == "degraded" else 100.0)

        # Never leak secret key in metadata
        safe_metadata = {
            "provider": self._provider,
            "endpoint": creds.get("endpoint"),
            "bucket": creds.get("bucket"),
            "region": creds.get("region"),
            "configured": bool(creds["endpoint"] and creds["access_key"] and creds["secret_key"] and creds["bucket"]),
        }

        return HealthResult(
            service_id=self._service_id,
            service_name=self._service_name,
            category=self.category,
            display_group=self.display_group,
            status=status,
            latency_ms=latency_ms,
            last_error=last_error,
            suggested_action=suggested_action,
            error_rate_15m=error_rate,
            success_rate_15m=success_rate,
            metadata=safe_metadata,
            probed_at=datetime.now(UTC),
        )
