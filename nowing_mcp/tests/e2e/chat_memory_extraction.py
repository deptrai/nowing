"""E2E smoke: send a chat turn and verify a memory is auto-extracted."""

import asyncio
import json

import httpx

BASE = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmOWFlYjM5Ny1jOGUyLTRiNmUtOTI4My0wOGNlNWNiMTdmZjkiLCJhdWQiOlsiZmFzdGFwaS11c2VyczphdXRoIl0sImlhdCI6MTc4NDg1OTcwNiwiZXhwIjoxNzg0ODYzMzA2fQ.2hSgVIibFYavQGxhY8CttGhznIV-pvmJxyb7WJ1uaJA"

QUERY = "My competitor X raised prices by 10% in Q2 2026."


async def main() -> None:
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        # Send a chat turn. The endpoint streams server-sent events.
        payload = {
            "chat_id": 1,
            "user_query": QUERY,
            "workspace_id": 1,
        }
        async with client.stream(
            "POST", "/api/v1/new_chat", headers=headers, json=payload
        ) as resp:
            print("new_chat status:", resp.status_code)
            async for _ in resp.aiter_text():
                pass

        # Wait for Celery extraction task.
        for attempt in range(12):
            await asyncio.sleep(5)
            search = await client.post(
                "/api/v1/workspaces/1/memories/search",
                headers=headers,
                json={"query": "Competitor X raised prices", "top_k": 5},
            )
            results = search.json().get("items", [])
            print(f"attempt {attempt + 1}: {len(results)} results")
            for item in results:
                if "Competitor X raised prices by 10% in Q2 2026" in item["content"]:
                    print("Extracted memory:", json.dumps(item, indent=2, default=str))
                    return
        raise RuntimeError("Memory was not auto-extracted from chat turn")


if __name__ == "__main__":
    asyncio.run(main())
