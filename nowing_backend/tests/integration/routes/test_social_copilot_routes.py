"""ATDD Red-Phase Integration Tests: Social Co-pilot REST Routes & Memory Persistence (Story 21.12 / AC 1, 2, 5)."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.skip(reason="ATDD Red Phase Scaffold: Social Co-pilot Routes implementation pending")
@pytest.mark.asyncio
async def test_create_and_fetch_voice_profile_endpoint(async_client: AsyncClient, test_user_headers):
    """AC 1: POST /api/workspaces/{id}/voice-profiles saves into memories with tag 'voice_profile'."""
    payload = {
        "profile_name": "Executive Founder",
        "sample_text": (
            "Hầu hết các nhà sáng lập đang lãng phí thời gian vào việc phát triển tính năng không ai cần. "
            "Trong 5 năm qua khi xây dựng 3 startup công nghệ, bài học lớn nhất của tôi là luôn kiểm chứng "
            "nhu cầu trước khi viết dòng mã đầu tiên. "
            "Quy trình thực chiến 3 bước: "
            "1. Phỏng vấn 20 khách hàng tiềm năng để tìm điểm nghẽn thực sự. "
            "2. Bán trước giải pháp bằng landing page đơn giản. "
            "3. Chỉ xây dựng khi có ít nhất 5 đơn vị sẵn sàng đặt cọc trả phí. "
            "Hãy tập trung vào giá trị cốt lõi thay vì sự hào nhoáng bên ngoài. "
            "Thành công trong kinh doanh là sự kiên trì và đo lường chính xác từng chỉ số tăng trưởng."
        ),
        "platform": "linkedin",
    }

    response = await async_client.post(
        "/api/workspaces/1/voice-profiles",
        json=payload,
        headers=test_user_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["profile_name"] == "Executive Founder"
    assert data["is_active"] is True
    assert "id" in data

    # Verify listing profiles
    list_res = await async_client.get(
        "/api/workspaces/1/voice-profiles",
        headers=test_user_headers,
    )
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(p["profile_name"] == "Executive Founder" for p in items)


@pytest.mark.integration
@pytest.mark.skip(reason="ATDD Red Phase Scaffold: Social Co-pilot Routes implementation pending")
@pytest.mark.asyncio
async def test_manual_post_ingestion_fallback_endpoint(async_client: AsyncClient, test_user_headers):
    """AC 5: Manual URL/Text ingestion endpoint works for degraded/unsupported platform posts."""
    payload = {
        "raw_text": "Top 5 xu hướng công nghệ năm 2026 sẽ thay đổi toàn bộ thị trường BĐS Việt Nam.",
        "source_url": "https://tiktok.com/@expert/video/123456789",
        "platform": "tiktok",
    }

    response = await async_client.post(
        "/api/workspaces/1/social-copilot/manual-ingest",
        json=payload,
        headers=test_user_headers,
    )
    assert response.status_code == 200
    res_data = response.json()
    assert "deconstructed_elements" in res_data
    assert res_data["platform"] == "tiktok"
