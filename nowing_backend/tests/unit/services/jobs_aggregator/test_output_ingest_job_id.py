"""Unit tests for jobs_aggregator output ingest_job_id (Story 12-4e)."""

from __future__ import annotations

import pytest

from app.services.jobs_aggregator.schemas import VnJobAggregateOutput

pytestmark = pytest.mark.unit



def test_vn_job_aggregate_output_has_ingest_job_id_field():
    """VnJobAggregateOutput has ingest_job_id field."""
    output = VnJobAggregateOutput()

    assert hasattr(output, "ingest_job_id")
    assert output.ingest_job_id is None



def test_vn_job_aggregate_output_ingest_job_id_is_optional():
    """ingest_job_id is optional and defaults to None."""
    output = VnJobAggregateOutput()

    assert output.ingest_job_id is None



def test_vn_job_aggregate_output_ingest_job_id_can_be_set():
    """ingest_job_id can be set to a string value."""
    output = VnJobAggregateOutput(ingest_job_id="job-123")

    assert output.ingest_job_id == "job-123"
