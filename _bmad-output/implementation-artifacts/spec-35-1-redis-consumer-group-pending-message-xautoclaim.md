# Story 35.1 Spec: Redis Consumer Group Pending Message Auto-Claim (XAUTOCLAIM) & DLQ Replay

## Intent

As a Data Infrastructure Engineer, I want consumer groups on `stream:social:raw_posts` to automatically reclaim pending messages from dead worker processes, so that worker crashes during high-volume ingress do not leave messages stuck in PEL.

## Acceptance Criteria

- **Given** messages stuck in PEL longer than `min_idle_time` (default 60s), **When** the stream worker runs, **Then** `XAUTOCLAIM` reassigns them to active workers before reading new messages.
- **And** messages exceeding max delivery attempts are routed to DLQ.

## Technical Design

### 1. Auto-claim Step in Worker Loop

Before calling `xreadgroup(..., streams={stream: ">"})`:
```python
# Reclaim pending messages stuck in PEL > min_idle_time_ms
try:
    claim_result = await redis_client.xautoclaim(
        name=STREAM_SOCIAL_RAW_POSTS,
        groupname=CONSUMER_GROUP_NAME,
        consumername=consumer_name,
        min_idle_time=min_idle_time_ms,
        start_id="0-0",
        count=count,
    )
    # claim_result: (next_start_id, messages, deleted_ids)
    if claim_result and len(claim_result) >= 2:
        claimed_messages = claim_result[1]
        if claimed_messages:
            # Process claimed messages before reading new ones
            await _process_message_batch(claimed_messages, ...)
except Exception as exc:
    logger.warning("XAUTOCLAIM failed; continuing with new messages: %s", exc)
```

### 2. Configuration Parameters

- `SOCIAL_STREAM_AUTOCLAIM_MIN_IDLE_MS = 60_000` (60 seconds)
- `SOCIAL_STREAM_MAX_DELIVERY_ATTEMPTS = 5`
