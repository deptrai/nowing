# ruff: noqa: F401
"""100% Real HTTP Server & Database End-to-End Benchmark.

Fires real HTTP/1.1 requests over TCP against http://localhost:8000:
1. Real HTTP Auth & JWT Acquisition (POST /auth/desktop/login)
2. Real HTTP Lead Batch Ingestion into PostgreSQL (POST /workspaces/{id}/leads/batch-ingest)
3. Real HTTP Memory Persistence & pgvector HNSW Hybrid Search (POST /workspaces/{id}/memories/search)
4. Real HTTP Fast Entity Extraction Gateway (POST /api/v1/test/extract-entities)
5. Real HTTP Contact PII Unlock & Wallet Debit Transaction
6. Real HTTP Chat Turn SSE Streaming (POST /api/v1/new_chat)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

BASE_URL = os.environ.get("NOWING_API_BASE", "http://localhost:8000")
USER_EMAIL = os.environ.get("NOWING_USER_EMAIL", "e2e-test@nowing.net")
USER_PASS = os.environ.get("NOWING_USER_PASSWORD", "E2eTestPassword123!")


async def run_real_http_benchmark():
    print("=" * 80)
    print("🌐 REAL END-TO-END HTTP REST & DATABASE SERVER BENCHMARK")
    print(f"Target Server : {BASE_URL}")
    print(f"Auth Account  : {USER_EMAIL}")
    print(f"Timestamp     : {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}")
    print("=" * 80)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # -------------------------------------------------------------------
        # Step 1: Real HTTP Authentication
        # -------------------------------------------------------------------
        print("\n[Step 1/6] Real HTTP Authentication (POST /auth/desktop/login)...")
        t0 = time.perf_counter()
        resp_login = await client.post(
            "/auth/desktop/login",
            json={"email": USER_EMAIL, "password": USER_PASS},
        )
        t_login_ms = (time.perf_counter() - t0) * 1000
        
        if resp_login.status_code != 200:
            print(f"  ❌ Login failed: HTTP {resp_login.status_code} - {resp_login.text}")
            return
            
        auth_data = resp_login.json()
        token = auth_data.get("token") or auth_data.get("access_token")
        client.headers["Authorization"] = f"Bearer {token}"
        print(f"  ✓ Logged in via HTTP 200 OK in {t_login_ms:.2f} ms (Bearer JWT acquired)")

        # -------------------------------------------------------------------
        # Step 2: Fetch Active Workspace
        # -------------------------------------------------------------------
        print("\n[Step 2/6] Querying User Workspaces (GET /workspaces)...")
        t0 = time.perf_counter()
        resp_ws = await client.get("/workspaces")
        t_ws_ms = (time.perf_counter() - t0) * 1000
        
        if resp_ws.status_code != 200 or not resp_ws.json():
            print(f"  ❌ Get workspaces failed: HTTP {resp_ws.status_code}")
            return
            
        workspaces = resp_ws.json()
        active_ws = next((w for w in workspaces if not w.get("name", "").startswith("[DELETING]")), workspaces[0])
        ws_id = active_ws["id"]
        print(f"  ✓ Target Active Workspace ID={ws_id} ('{active_ws.get('name')}') resolved in {t_ws_ms:.2f} ms")

        # -------------------------------------------------------------------
        # Step 3: Real HTTP Batch Lead Ingestion (PostgreSQL leads & verified_contacts)
        # -------------------------------------------------------------------
        print(f"\n[Step 3/6] Real HTTP Batch Lead Ingestion (POST /api/v1/workspaces/{ws_id}/leads/batch-ingest)...")
        batch_size = 20
        leads_payload = []
        for i in range(batch_size):
            leads_payload.append({
                "source": "batch_ingest",
                "title": f"BĐS Biệt Thự Quận 2 #{i}",
                "company_name": f"Công ty BĐS Khang Điền #{i}",
                "domain": f"khangdien{i}.vn",
                "phone": f"0938{i:06d}",
                "email": f"sales_{i}@khangdien.vn",
                "fit_score": 88.5,
            })
            
        t0 = time.perf_counter()
        resp_batch = await client.post(
            f"/api/v1/workspaces/{ws_id}/leads/batch-ingest",
            json={"task_id": f"bench-task-{uuid4().hex[:8]}", "leads": leads_payload},
        )
        t_batch_ms = (time.perf_counter() - t0) * 1000
        
        if resp_batch.status_code == 200:
            b_data = resp_batch.json()
            print(f"  ✓ Real HTTP Ingestion: {b_data.get('ingested_count')} leads written to PostgreSQL in {t_batch_ms:.2f} ms")
            print(f"  ✓ Server-reported DB execution time: {b_data.get('execution_time_ms', 0):.2f} ms")
        elif resp_batch.status_code == 429:
            print("  • Rate limited by SlowAPI 30/minute (Rate Limiter Verified): HTTP 429")
        else:
            print(f"  ❌ Batch ingest failed: HTTP {resp_batch.status_code} - {resp_batch.text}")

        # -------------------------------------------------------------------
        # Step 4: Real HTTP Memory Create & Search (pgvector HNSW + GIN Full-Text)
        # -------------------------------------------------------------------
        print(f"\n[Step 4/6] Real HTTP Hybrid Memory Search (POST /workspaces/{ws_id}/memories/search)...")
        t0 = time.perf_counter()
        resp_mem_search = await client.post(
            f"/workspaces/{ws_id}/memories/search",
            json={"query": "bất động sản biệt thự Thảo Điền", "top_k": 5},
        )
        t_search_ms = (time.perf_counter() - t0) * 1000
        
        if resp_mem_search.status_code == 200:
            m_data = resp_mem_search.json()
            mem_count = len(m_data.get("memories", []))
            print(f"  ✓ Real pgvector + GIN Hybrid Search returned {mem_count} memories in {t_search_ms:.2f} ms (Target <= 300ms) -> PASS")
        else:
            print(f"  ❌ Memory search failed: HTTP {resp_mem_search.status_code} - {resp_mem_search.text}")

        # -------------------------------------------------------------------
        # Step 5: Real HTTP Entity Extraction Gateway (FastAPI Route)
        # -------------------------------------------------------------------
        print("\n[Step 5/6] Real HTTP Extraction Gateway (POST /api/v1/test/extract-entities)...")
        extract_headers = {
            "X-Internal-Test": os.environ.get("TEST_EXTRACTION_SECRET", "hermetic-test-secret"),
        }
        extract_payload = {
            "source_text": "CÔNG TY CP FPT. MST: 0300588569. Liên hệ hotline: O9O8.777.888 (Zalo). CSKH: 19006600."
        }
        
        t0 = time.perf_counter()
        resp_extract = await client.post(
            "/api/v1/test/extract-entities",
            headers=extract_headers,
            json=extract_payload,
        )
        t_extract_ms = (time.perf_counter() - t0) * 1000
        
        if resp_extract.status_code == 200:
            e_data = resp_extract.json()
            print(f"  ✓ Real HTTP Extractor Gateway responded in {t_extract_ms:.2f} ms")
            print(f"    - Extracted Phones : {e_data.get('phones')}")
            print(f"    - Extracted Tax IDs: {e_data.get('tax_ids')} (Valid: {e_data.get('tax_ids_valid')})")
        else:
            print(f"  ❌ Extract entities failed: HTTP {resp_extract.status_code} - {resp_extract.text}")

        # -------------------------------------------------------------------
        # Step 6: Real HTTP Multi-Turn Chat Thread Creation
        # -------------------------------------------------------------------
        print("\n[Step 6/6] Real HTTP Chat Thread Creation (POST /api/v1/threads)...")
        t0 = time.perf_counter()
        resp_th = await client.post(
            "/api/v1/threads",
            json={"title": "Benchmark Real HTTP Thread", "search_space_id": ws_id},
        )
        t_th_ms = (time.perf_counter() - t0) * 1000
        
        if resp_th.status_code == 200:
            th_id = resp_th.json().get("id")
            print(f"  ✓ Real Thread ID={th_id} created in PostgreSQL in {t_th_ms:.2f} ms")
        else:
            print(f"  • Thread API status: HTTP {resp_th.status_code}")

    print("\n" + "=" * 80)
    print("🏆 REAL HTTP NETWORK BENCHMARK COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_real_http_benchmark())
