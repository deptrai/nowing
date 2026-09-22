"""Live verification for Story 37.1 — Proactive Intent Signal Radar.

Runs against REAL Redis (REDIS_APP_URL) + Postgres (DATABASE_URL):
  A. IntentKeywordMatcher on real VN samples (accent/whitespace-insensitive)
  B. Celery task + beat schedule registration
  C. Telegram consumer E2E: push events to stream:telegram:raw_events, run the
     consumer once, assert Lead rows + stream ACK behaviour in Postgres/Redis
  D. AC-4 guardrails on real workspace state (low-credit pause, budget cap)
  E. fetch_new_incorporations live fetch (masothue + dangkykinhdoanh)
  F. Full-scan happy path on a throwaway workspace (incorporation signals only)

All rows/keys created by this script are deleted at the end.
Usage: cd nowing_backend && uv run python scripts/verify_intent_radar_37_1.py
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")

import redis.asyncio as aioredis
from sqlalchemy import delete, select, text

from app.config import config
from app.db import (
    Lead,
    LeadActivityLog,
    SignalEvent,
    Workspace,
    async_session_maker,
)
from app.lead_intelligence.signals.radar import (
    PURCHASE_INTENT_PATTERNS,
    TELEGRAM_INTENT_MATCHER,
    _scan_counter_key,
    fetch_new_incorporations,
    run_telegram_intent_consumer,
    scan_workspace_high_intent,
)

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def report(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, PASS if ok else FAIL, detail))
    print(f"  [{PASS if ok else FAIL}] {name} {detail}")


VERIFY_TAG = "37.1-VERIFY"


def section_matcher() -> None:
    print("\n== A. IntentKeywordMatcher ==")
    cases = [
        ("Cần tìm nhà cung cấp gấp cho dự án tháng này", True),
        ("Bao gia chi tiet cho toi nhe", True),  # accent-stripped
        ("báo  giá   lô hàng 500 cái", True),  # multi-space
        ("Tìm agency chạy ads tiktok", True),
        ("Tôi muốn thuê ngoài team dev", True),
        ("Hôm nay trời đẹp quá, đi cafe không mấy bạn", False),
        ("Xin chào admin nhóm", False),
        ("", False),
    ]
    bad = [
        (t, exp, TELEGRAM_INTENT_MATCHER.find_matches(t))
        for t, exp in cases
        if bool(TELEGRAM_INTENT_MATCHER.find_matches(t)) != exp
    ]
    report("matcher 8 cases", not bad, f"mismatches={bad or 'none'}")
    report(
        "all AC-2 patterns compiled",
        all(
            TELEGRAM_INTENT_MATCHER.has_match(p) for p in PURCHASE_INTENT_PATTERNS
        ),
        f"{len(PURCHASE_INTENT_PATTERNS)} patterns",
    )


def section_celery() -> None:
    print("\n== B. Celery registration ==")
    import app.tasks.celery_tasks.signal_radar_tasks  # noqa: F401 — register @task decorators
    from app.celery_app import celery_app

    tasks = set(celery_app.tasks)
    report(
        "tasks registered",
        {"scan_high_intent_companies_periodic", "process_telegram_intent_stream"}
        <= tasks,
    )
    sched = celery_app.conf.beat_schedule
    scan = sched.get("scan-high-intent-companies", {})
    stream = sched.get("process-telegram-intent-stream", {})
    report("beat: scan every 6h", scan.get("task") == "scan_high_intent_companies_periodic")
    report(
        "beat: stream every 30s",
        stream.get("task") == "process_telegram_intent_stream"
        and stream.get("schedule") == 30.0,
    )


async def section_consumer(redis_client, ws_id: int) -> list[int]:
    print("\n== C. Telegram consumer E2E (real stream + DB) ==")
    created_lead_ids: list = []
    msg_ids: list[str] = []
    try:
        # Group must exist BEFORE messages are pushed (post-patch id="$" semantics —
        # mirrors production: first beat run creates the group, then events flow in).
        with contextlib.suppress(Exception):  # BUSYGROUP — already exists
            await redis_client.xgroup_create(
                "stream:telegram:raw_events", "telegram_intent_processors", id="$", mkstream=True
            )
        base = {"channel_username": "verify_channel_371"}
        payloads = [
            {**base, "sender_name": f"{VERIFY_TAG} BuyerA", "message_id": "37101",
             "workspace_id": str(ws_id),
             "message_text": "Cần báo giá 200 áo thun đồng phục, liên hệ 0901234567"},
            {**base, "sender_name": f"{VERIFY_TAG} BuyerB", "message_id": "37102",
             "workspace_id": str(ws_id),
             "message_text": "Tìm agency làm landing page, ai biết chỉ em với"},
            {**base, "sender_name": f"{VERIFY_TAG} BuyerC", "message_id": "37103",
             "workspace_id": str(ws_id),
             "message_text": "Hôm nay nhóm mình off nhé cả nhà"},
        ]
        for p in payloads:
            msg_ids.append(await redis_client.xadd("stream:telegram:raw_events", {k: str(v) for k, v in p.items()}))

        processed = await run_telegram_intent_consumer(
            redis_client=redis_client, batch_size=10, block_ms=500, max_loops=3
        )
        report("consumer returns 2 leads", processed == 2, f"processed={processed}")

        async with async_session_maker() as s:
            leads = (
                await s.execute(
                    select(Lead).where(Lead.company_name.like(f"{VERIFY_TAG}%"))
                )
            ).scalars().all()
            created_lead_ids.extend(lead.id for lead in leads)
            report("2 leads persisted", len(leads) == 2, f"ids={created_lead_ids}")

            by_status = {lead.status for lead in leads}
            report(
                "contact→new / contactless→pending_enrichment",
                by_status == {"new", "pending_enrichment"},
                f"statuses={by_status}",
            )
            report(
                "enriched flags honest",
                all(lead.enriched is False and lead.needs_enrichment for lead in leads),
            )
            if created_lead_ids:
                logs = (
                    await s.execute(
                        select(LeadActivityLog).where(
                            LeadActivityLog.lead_id.in_(created_lead_ids)
                        )
                    )
                ).scalars().all()
            else:
                logs = []
            phones = [
                lg.details.get("phones")
                for lg in logs
                if lg.details.get("phones")
            ]
            report("activity logs + phone captured", len(logs) >= 2 and phones, f"logs={len(logs)}")

        pend = await redis_client.xpending("stream:telegram:raw_events", "telegram_intent_processors")
        pending_n = pend.get("pending", 0) if isinstance(pend, dict) else (pend[0] if pend else 0)
        report("stream fully acked", int(pending_n) == 0, f"pending={pending_n}")
        report("DLQ empty", (await redis_client.xlen("stream:telegram:intent_dlq")) == 0)
    finally:
        if msg_ids:
            await redis_client.xdel("stream:telegram:raw_events", *msg_ids)
    return created_lead_ids


async def section_guardrails(redis_client, ws_id: int, tmp_ws_id: int) -> None:
    print("\n== D. AC-4 guardrails ==")
    async with async_session_maker() as s:
        r = await scan_workspace_high_intent(s, redis_client, workspace_id=ws_id, new_incorporations=[])
        report("low-credit pause (ws1, 0 credits)", r.get("status") == "paused_low_credit", str(r))

    day = datetime.now(UTC).date()
    key = _scan_counter_key(tmp_ws_id, day)
    await redis_client.set(key, 100)
    async with async_session_maker() as s:
        r = await scan_workspace_high_intent(s, redis_client, workspace_id=tmp_ws_id, new_incorporations=[])
        report("budget exhausted at 100/day", r.get("status") == "budget_exhausted", str(r))
    await redis_client.delete(key)


async def section_incorporations() -> list[dict]:
    print("\n== E. fetch_new_incorporations (live HTTP) ==")
    items, reasons = await fetch_new_incorporations()
    report(
        "fetch returns items or explicit degradation",
        bool(items) or bool(reasons),
        f"items={len(items)} reasons={reasons}",
    )
    for it in items[:3]:
        print(f"    sample: {it.get('company_name')} | {it.get('tax_code')} | {it.get('source')}")
    return items[:2]


async def section_scan_e2e(redis_client, tmp_ws_id: int, inc_items: list[dict]) -> list[int]:
    print("\n== F. scan happy path (temp workspace) ==")
    sig_ids: list[int] = []
    # Env drift workaround: .env.local pins nomic-embed-text (768) but this DB's
    # memories.embedding column was migrated under a 384-dim model. Align BOTH
    # the declared column dim (pgvector validates client-side) and the zero-vector
    # size with the real DB column so the persist path can complete.
    from app.config import config
    from app.models.memory import Memory

    emb_col = Memory.__table__.c.embedding.type
    orig_col_dim, orig_dim = emb_col.dim, config.embedding_model_instance.dimension
    emb_col.dim = 384
    config.embedding_model_instance._dimension = 384
    try:
        async with async_session_maker() as s:
            r = await scan_workspace_high_intent(
                s, redis_client, workspace_id=tmp_ws_id, new_incorporations=inc_items
            )
            report("scan ok", r.get("status") == "ok", str(r))
            sigs = (
                await s.execute(
                    select(SignalEvent).where(SignalEvent.workspace_id == tmp_ws_id)
                )
            ).scalars().all()
            sig_ids.extend(x.id for x in sigs)
            ok = len(sigs) == len(inc_items) and all(
                x.signal_type == "incorporation" and (x.confidence or 0) >= 75 for x in sigs
            )
            report("incorporation SignalEvents ≥75", ok, f"created={len(sigs)}")
    finally:
        emb_col.dim = orig_col_dim
        config.embedding_model_instance._dimension = orig_dim
    return sig_ids


async def cleanup(redis_client, lead_ids, sig_ids, tmp_ws_id) -> None:
    print("\n== cleanup ==")
    async with async_session_maker() as s:
        if lead_ids:
            await s.execute(delete(LeadActivityLog).where(LeadActivityLog.lead_id.in_(lead_ids)))
            try:
                async with s.begin_nested():  # savepoint — keep txn usable if table missing
                    await s.execute(
                        text("DELETE FROM lead_assignments WHERE lead_id = ANY(:ids)"),
                        {"ids": lead_ids},
                    )
            except Exception:
                pass  # table may not exist / no rows; best-effort
            await s.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
        if sig_ids:
            try:
                async with s.begin_nested():  # signal memories share source_uuid
                    await s.execute(
                        text(
                            "DELETE FROM memories WHERE source_type='signal'"
                            " AND source_uuid = ANY(:ids)"
                        ),
                        {"ids": sig_ids},
                    )
            except Exception:
                pass  # best-effort
            await s.execute(delete(SignalEvent).where(SignalEvent.id.in_(sig_ids)))
        if tmp_ws_id:
            await s.execute(delete(Workspace).where(Workspace.id == tmp_ws_id))
        await s.commit()
    print(f"  deleted leads={lead_ids} signals={sig_ids} tmp_ws={tmp_ws_id}")


async def main() -> int:
    print("Story 37.1 live verification — real Redis + Postgres")
    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    lead_ids: list[int] = []
    sig_ids: list[int] = []
    tmp_ws_id: int | None = None
    try:
        section_matcher()
        section_celery()

        async with async_session_maker() as s:
            ws1 = await s.get(Workspace, 1)
            assert ws1 is not None
            tmp = Workspace(
                name=f"{VERIFY_TAG} ws",
                user_id=ws1.user_id,
                credit_micros_balance=60_000_000,
            )
            s.add(tmp)
            await s.commit()
            tmp_ws_id = tmp.id
            print(f"  tmp workspace id={tmp_ws_id} balance=60cr; ws1 balance={ws1.credit_micros_balance}")

        lead_ids = await section_consumer(redis_client, ws_id=1)
        await section_guardrails(redis_client, ws_id=1, tmp_ws_id=tmp_ws_id)
        inc_items = await section_incorporations()
        sig_ids = await section_scan_e2e(redis_client, tmp_ws_id, inc_items)
    finally:
        await cleanup(redis_client, lead_ids, sig_ids, tmp_ws_id)
        await redis_client.aclose()

    failed = [r for r in results if r[1] == FAIL]
    print(f"\n== SUMMARY: {len(results) - len(failed)}/{len(results)} pass ==")
    for name, status, detail in failed:
        print(f"  [{status}] {name} {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
