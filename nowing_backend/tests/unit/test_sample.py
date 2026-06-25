"""Sample pytest test — demonstrates fixture patterns for Nowing backend.

Run:
    uv run pytest tests/unit/test_sample.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.unit
class TestSampleUnit:
    """Pure logic tests — no DB, no external services."""

    def test_factories_generate_unique_data(self):
        from tests.utils.factories import make_user

        user_a = make_user()
        user_b = make_user()

        assert user_a["id"] != user_b["id"]
        assert user_a["email"] != user_b["email"]

    def test_factory_overrides_take_precedence(self):
        from tests.utils.factories import make_user

        user = make_user(email="custom@nowing.test", is_superuser=True)

        assert user["email"] == "custom@nowing.test"
        assert user["is_superuser"] is True

    @pytest.mark.asyncio
    async def test_async_mock_pattern(self):
        mock_fn = AsyncMock(return_value={"status": "ok"})
        result = await mock_fn()
        assert result["status"] == "ok"
        mock_fn.assert_awaited_once()

    def test_monkeypatch_pattern(self, monkeypatch):
        import os

        monkeypatch.setenv("MY_TEST_VAR", "hello")
        assert os.environ["MY_TEST_VAR"] == "hello"
