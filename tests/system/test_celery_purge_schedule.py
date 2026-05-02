import pytest
from app.celery_app import celery_app
from celery.schedules import crontab

def test_crypto_cleanup_orphaned_snapshots_schedule():
    \"\"\"System test to verify the weekly orphaned snapshot cleanup task is registered with correct crontab.\"\"\"
    schedule = celery_app.conf.beat_schedule
    task_name = "crypto-cleanup-orphaned-snapshots"
    
    assert task_name in schedule, f"Task {task_name} not found in beat_schedule"
    entry = schedule[task_name]
    
    assert entry["task"] == "crypto.cleanup_orphaned_snapshots"
    # Expected: Weekly Sunday 4 AM UTC
    # Note: crontab(hour=4, minute=0, day_of_week=0)
    expected_schedule = crontab(hour=4, minute=0, day_of_week=0)
    
    assert entry["schedule"] == expected_schedule, f"Expected {expected_schedule}, got {entry['schedule']}"
    
    # Check expires option
    assert entry["options"]["expires"] == 43200, f"Expected expires=43200, got {entry['options']['expires']}"

def test_celery_app_timezone_configuration():
    \"\"\"Verify Celery app is pinned to UTC to ensure crontab timings are deterministic.\"\"\"
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True
