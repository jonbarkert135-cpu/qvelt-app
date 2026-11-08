"""Durable submission/journal with Redis Stream notifications and SSE replay."""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from qvelt_api.database import chats, messages, run_events, run_jobs, runs, sessions, tenant_session
from qvelt_api.events import parse_event

TERMINAL = {"complete", "cancelled", "error"}
logger = logging.getLogger(__name__)


def redis_client(url: str) -> Redis:
    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=1,
                          socket_timeout=2, retry=Retry(NoBackoff(), 0))


def stream_key(prefix: str, run_id: UUID) -> str:
    return f"{prefix}run:{run_id}:events"


async def owned_run(db: AsyncSession, owner: UUID, run_id: UUID) -> Mapping[str, Any]:
    row = (await db.execute(select(runs).where(
        runs.c.id == run_id, runs.c.owner_id == owner,
    ))).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Run not found")
    return row


async def submit(
    db: AsyncSession, owner: UUID, chat_id: UUID, key: str, message: str, after: int = 0,
) -> Mapping[str, Any]:
    # The chat lock serializes idempotency checks and message position allocation.
    chat = await db.scalar(select(chats.c.id).where(
        chats.c.id == chat_id, chats.c.owner_id == owner,
    ).with_for_update())
    if chat is None:
        raise HTTPException(404, "Chat not found")
    fingerprint = hashlib.sha256(message.encode()).hexdigest()
    existing = (await db.execute(select(runs).where(
        runs.c.owner_id == owner, runs.c.chat_id == chat_id, runs.c.idempotency_key == key,
    ))).mappings().one_or_none()
    if existing is not None:
        if not hmac.compare_digest(existing["request_hash"], fingerprint):
            raise HTTPException(409, "Idempotency key already used with different input")
        await db.rollback()
        return existing
    if after:
        raise HTTPException(409, "A new run requires cursor zero")
    active = await db.scalar(select(runs.c.id).where(
        runs.c.owner_id == owner, runs.c.chat_id == chat_id, runs.c.status.in_(["queued", "running"]),
    ))
    if active is not None:
        raise HTTPException(409, "Chat already has an active run")
    position = (await db.scalar(select(func.max(messages.c.position)).where(
        messages.c.chat_id == chat_id, messages.c.owner_id == owner,
    )) or 0) + 1
    user_id, assistant_id, run_id = uuid4(), uuid4(), uuid4()
    await db.execute(insert(messages), [
        {"id": user_id, "owner_id": owner, "chat_id": chat_id, "position": position,
         "role": "user", "status": "complete",
         "parts": [{"id": str(user_id), "type": "text", "text": message}]},
        {"id": assistant_id, "owner_id": owner, "chat_id": chat_id, "position": position + 1,
         "role": "assistant", "status": "queued", "parts": []},
    ])
    row = (await db.execute(insert(runs).values(
        id=run_id, owner_id=owner, chat_id=chat_id, user_message_id=user_id,
        assistant_message_id=assistant_id, idempotency_key=key, request_hash=fingerprint, model="fake",
    ).returning(runs))).mappings().one()
    await db.execute(insert(run_jobs).values(run_id=run_id, owner_id=owner))
    await db.commit()
    return row


async def emit(
    connection: AsyncConnection, redis: Redis, prefix: str, owner: UUID, run_id: UUID,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    async with tenant_session(connection, owner) as db:
        run = (await db.execute(select(runs).where(
            runs.c.id == run_id, runs.c.owner_id == owner,
        ).with_for_update())).mappings().one()
        if run["status"] in TERMINAL:
            return None
        event = parse_event(json.dumps({**payload, "seq": run["last_seq"] + 1}, allow_nan=False))
        changes: dict[str, Any] = {"last_seq": event["seq"]}
        message_changes: dict[str, Any] = {}
        if event["type"] == "message_start":
            if run["last_seq"] != 0:
                raise ValueError("Run already started")
            changes.update(status="running", started_at=func.now())
            message_changes["status"] = "streaming"
        elif event["type"] == "text_delta":
            if event["part_id"] != str(run["assistant_message_id"]):
                raise ValueError("Unexpected text part")
            parts = await db.scalar(select(messages.c.parts).where(
                messages.c.id == run["assistant_message_id"], messages.c.owner_id == owner,
            ))
            previous = parts[0]["text"] if parts else ""
            message_changes["parts"] = [{"id": event["part_id"], "type": "text",
                                         "text": previous + event["text"]}]
        elif event["type"] in ("message_complete", "error"):
            status = "error" if event["type"] == "error" else (
                "cancelled" if event["stop_reason"] == "cancelled" else "complete"
            )
            changes.update(status=status, finished_at=func.now())
            if event["type"] == "message_complete":
                changes["usage"] = event["usage"]
            message_changes["status"] = status
            await db.execute(delete(run_jobs).where(
                run_jobs.c.run_id == run_id, run_jobs.c.owner_id == owner,
            ))
        await db.execute(insert(run_events).values(
            run_id=run_id, owner_id=owner, seq=event["seq"], payload=event,
        ))
        await db.execute(update(runs).where(runs.c.id == run_id, runs.c.owner_id == owner)
                         .values(**changes))
        if message_changes:
            await db.execute(update(messages).where(
                messages.c.id == run["assistant_message_id"], messages.c.owner_id == owner,
            ).values(**message_changes))
    # Commit-before-notify: failed Redis delivery cannot lose or duplicate the journal.
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.xadd(stream_key(prefix, run_id), {"data": json.dumps(event)}, id=f"{event['seq']}-0")
            pipe.expire(stream_key(prefix, run_id), 86400)
            await pipe.execute()
    except RedisError:
        logger.warning("Redis notification unavailable; durable event journal retained")
    return event


def sse(event: dict[str, Any]) -> bytes:
    return (f"id: {event['seq']}\nevent: {event['type']}\n"
            f"data: {json.dumps(event, ensure_ascii=False)}\n\n").encode()


async def subscribe(
    engine: AsyncEngine, redis: Redis, prefix: str, owner: UUID, run_id: UUID,
    digest: str, clock: Callable[[], datetime], after: int, request: Request,
) -> AsyncIterator[bytes]:
    cursor, heartbeat = after, time.monotonic()
    while not await request.is_disconnected():
        # Transactions end before yielding bytes or waiting on Redis.
        async with tenant_session(engine, owner) as db:
            valid = await db.scalar(select(sessions.c.owner_id).where(
                sessions.c.owner_id == owner, sessions.c.token_hash == digest,
                sessions.c.expires_at > clock(),
            ))
            if valid is None:
                return
            run = (await db.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner_id == owner,
            ))).mappings().one_or_none()
            if run is None:
                return
            batch = (await db.execute(select(run_events.c.payload).where(
                run_events.c.run_id == run_id, run_events.c.owner_id == owner,
                run_events.c.seq > cursor,
            ).order_by(run_events.c.seq).limit(128))).scalars().all()
        for stored in batch:
            event = parse_event(json.dumps(stored))
            if event["seq"] != cursor + 1:
                raise RuntimeError("Stored event sequence gap")
            cursor = event["seq"]
            yield sse(event)
            if event["type"] in ("message_complete", "error"):
                return
        if batch:
            continue
        if run["status"] in TERMINAL:
            return
        try:
            await redis.xread({stream_key(prefix, run_id): f"{cursor}-0"}, count=128, block=1000)
        except RedisError:
            await asyncio.sleep(0.25)
        if time.monotonic() - heartbeat >= 15:
            yield b": heartbeat\n\n"
            heartbeat = time.monotonic()
