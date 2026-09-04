"""Unit tests for HealthProbeScheduler."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.health.probe_base import HealthProbe, HealthResult
from app.services.health.scheduler import HealthProbeScheduler


class DummyTestProbe(HealthProbe):
    def __init__(self, s_id: str, cat: str = "infra") -> None:
        self._s_id = s_id
        self._cat = cat

    @property
    def service_id(self) -> str:
        return self._s_id

    @property
    def service_name(self) -> str:
        return "Dummy"

    @property
    def category(self) -> str:
        return self._cat

    @property
    def display_group(self) -> str:
        return "Test"

    async def probe(self) -> HealthResult:
        return HealthResult(
            service_id=self._s_id,
            service_name="Dummy",
            category=self._cat,
            display_group="Test",
            status="healthy",
        )


@pytest.mark.asyncio
async def test_scheduler_run_category() -> None:
    probes = [DummyTestProbe(f"infra/test_{i}", "infra") for i in range(5)]

    with patch("app.services.health.scheduler.HealthProbeRegistry.get_probes", return_value=probes), \
         patch("app.services.health.scheduler.HealthResultStore.save_result", new_callable=AsyncMock) as mock_save, \
         patch("app.services.health.scheduler.AdminHealthAlertEngine.evaluate_result", new_callable=AsyncMock) as mock_eval:
        mock_session = AsyncMock()

        results = await HealthProbeScheduler.run_category("infra", session=mock_session)
        assert len(results) == 5
        assert all(r.status == "healthy" for r in results)
        assert mock_save.call_count == 5
        assert mock_eval.call_count == 5
