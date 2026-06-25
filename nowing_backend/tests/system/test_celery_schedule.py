from celery.schedules import crontab
from app.celery_app import celery_app

def test_orphaned_purge_schedule_registration():
    """[P1] System: Verify task is registered in beat schedule with correct timing."""
    schedule = celery_app.conf.beat_schedule
    key = "crypto-cleanup-orphaned-snapshots"
    
    assert key in schedule
    entry = schedule[key]
    assert entry["task"] == "crypto.cleanup_orphaned_snapshots"
    # Sunday 4:00 AM UTC
    assert entry["schedule"] == crontab(hour=4, minute=0, day_of_week=0)
    assert entry["options"]["expires"] == 43200