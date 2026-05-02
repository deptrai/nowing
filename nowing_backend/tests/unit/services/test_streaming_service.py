import pytest
from app.services.new_streaming_service import VercelStreamingService

def test_format_heartbeat():
    service = VercelStreamingService()
    # This should fail because format_heartbeat doesn't exist yet
    heartbeat = service.format_heartbeat()
    assert heartbeat == ": heartbeat\n\n"

def test_get_response_headers_updated():
    headers = VercelStreamingService.get_response_headers()
    assert headers["Cache-Control"] == "no-cache, no-transform"
    assert headers["X-Accel-Buffering"] == "no"
