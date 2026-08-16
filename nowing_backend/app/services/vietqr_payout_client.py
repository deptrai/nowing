"""VietQR / Napas 24/7 Gateway HTTP Client (Story 23.3 / Task 2)."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import httpx

VIETQR_GATEWAY_URL = os.environ.get("VIETQR_GATEWAY_URL", "https://api.vietqr.io/v2")
VIETQR_CLIENT_ID = os.environ.get("VIETQR_CLIENT_ID", "test_client_id")
VIETQR_API_KEY = os.environ.get("VIETQR_API_KEY", "test_api_key")
VIETQR_WEBHOOK_SECRET = os.environ.get("VIETQR_WEBHOOK_SECRET", "test_webhook_secret_key_123")


class VietQRPayoutClient:
    """Client for initiating Napas 24/7 VietQR payouts and checking transaction status."""

    def __init__(
        self,
        base_url: str = VIETQR_GATEWAY_URL,
        client_id: str = VIETQR_CLIENT_ID,
        api_key: str = VIETQR_API_KEY,
        webhook_secret: str = VIETQR_WEBHOOK_SECRET,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.api_key = api_key
        self.webhook_secret = webhook_secret

    @classmethod
    def verify_webhook_signature(
        cls, payload: bytes, signature: str, secret: str = VIETQR_WEBHOOK_SECRET
    ) -> bool:
        """Verify HMAC-SHA256 signature against webhook secret."""
        if not signature or not secret:
            return False
        expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    async def initiate_payout(
        self,
        tx_reference: str,
        amount_vnd: int,
        bank_bin: str,
        account_number: str,
        account_name: str,
        memo: str,
    ) -> dict[str, Any]:
        """Dispatch payout request to VietQR/Napas gateway (POST /v1/transfers)."""
        payload = {
            "tx_reference": tx_reference,
            "amount": amount_vnd,
            "bank_bin": bank_bin,
            "account_number": account_number,
            "account_name": account_name,
            "memo": memo,
        }
        headers = {
            "x-client-id": self.client_id,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/transfers",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def query_transfer_status(self, tx_reference: str) -> dict[str, Any]:
        """Query transfer status by transaction reference (GET /v1/transfers/{tx_reference})."""
        headers = {
            "x-client-id": self.client_id,
            "x-api-key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.base_url}/transfers/{tx_reference}",
                headers=headers,
            )
            if resp.status_code == 404:
                return {"status": "NOT_FOUND", "tx_reference": tx_reference}
            resp.raise_for_status()
            return resp.json()
