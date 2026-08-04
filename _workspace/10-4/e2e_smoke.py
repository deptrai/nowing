"""E2E smoke test for Story 10.4 vn_bds.aggregate REST endpoint."""

from __future__ import annotations

import sys

import httpx

BASE = "http://localhost:8000"
API = "http://localhost:8000/api/v1"
EMAIL = "e2e-10-4@nowing.net"
PASSWORD = "E2eTestPassword123!"


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30) as client, httpx.Client(
        base_url=API, timeout=30
    ) as api_client:
        # Use an existing / freshly registered e2e user; the mint endpoint
        # creates the token if the user exists.
        resp = client.post(
            "/__e2e__/auth/token",
            json={"email": EMAIL},
            headers={"X-E2E-Mint-Secret": "local-e2e-mint-secret-not-for-production"},
        )
        if resp.status_code != 200:
            print(f"mint failed: {resp.status_code} {resp.text}")
            return 1
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a workspace.
        resp = api_client.post("/workspaces", json={"name": "10-4 e2e"}, headers=headers)
        if resp.status_code not in (200, 201):
            print(f"workspace create failed: {resp.status_code} {resp.text}")
            return 1
        workspace_id = resp.json()["id"]

        # Aggregate with an unknown city should degrade gracefully.
        resp = api_client.post(
            f"/workspaces/{workspace_id}/scrapers/vn_bds/aggregate",
            json={
                "sources": ["batdongsan"],
                "city": "Atlantis",
                "max_items_per_source": 1,
                "max_pages": 1,
            },
            headers=headers,
        )
        if resp.status_code not in (200, 202):
            print(f"aggregate failed: {resp.status_code} {resp.text}")
            return 1

        data = resp.json()
        print("aggregate response:", data)
        if not data.get("degraded"):
            print("expected degraded=true for unknown city")
            return 1
        if not any("unknown_city" in r for r in data.get("degradation_reasons", [])):
            print("expected unknown_city degradation reason")
            return 1

        # Aggregate with a known city should return successfully
        # (sources may be degraded due to e2e network, but the call itself succeeds).
        resp = api_client.post(
            f"/workspaces/{workspace_id}/scrapers/vn_bds/aggregate",
            json={
                "sources": ["batdongsan"],
                "city": "Hà Nội",
                "max_items_per_source": 1,
                "max_pages": 1,
            },
            headers=headers,
        )
        if resp.status_code not in (200, 202):
            print(f"aggregate (known city) failed: {resp.status_code} {resp.text}")
            return 1

        data = resp.json()
        print("aggregate (known city) response keys:", sorted(data.keys()))
        if "items" not in data or "degraded" not in data:
            print("expected items and degraded in response")
            return 1

    print("e2e smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
