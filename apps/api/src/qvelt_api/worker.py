"""Separate durable worker: python -m qvelt_api.worker."""
import argparse
import asyncio
import logging
import math
import os
import re
from collections.abc import Mapping
from contextlib import aclosing, suppress
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from qvelt_api.database import (
    assert_runtime_role,
    messages,
    run_jobs,
    runs,
    tenant_session,
    validate_message_text,
)
from qvelt_api.providers import FakeProvider, ModelMessage, ModelProvider, ModelUsage
from qvelt_api.streaming import TERMINAL, emit, redis_client

logger = logging.getLogger(__name__)


class OutputLimitExceeded(Exception):
    pass


class Worker:
    def __init__(
        self, engine: AsyncEngine, redis: Redis, provider: ModelProvider | None = None,
        prefix: str = "qvelt:", timeout: float = 60, max_output_chars: int = 200_000,
        history_limit: int = 100,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0 or max_output_chars < 1 or history_limit < 1:
            raise ValueError("Invalid worker limits")
        if not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", prefix):
            raise ValueError("Invalid Redis namespace prefix")
        self.engine, self.redis = engine, redis
        self.provider = provider or FakeProvider()
        self.prefix, self.timeout = prefix, timeout
        self.max_output_chars, self.history_limit = max_output_chars, history_limit

    async def run_once(self) -> bool:
        # ponytail: one run per worker; start more worker processes for concurrency.
        async with self.engine.connect() as connection:
            await assert_runtime_role(connection)
            jobs = (await connection.execute(select(run_jobs).order_by(
                run_jobs.c.created_at, run_jobs.c.run_id,
            ).limit(128))).mappings().all()
            await connection.commit()
            for job in jobs:
                run_id, owner = job["run_id"], job["owner_id"]
                key = int.from_bytes(run_id.bytes[:8], "big", signed=True)
                locked = await connection.scalar(text("SELECT pg_try_advisory_lock(:key)"),
                                                 {"key": key})
                await connection.commit()
                if not locked:
                    continue
                try:
                    await self._process(connection, owner, run_id)
                    return True
                finally:
                    await connection.rollback()
                    await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                    await connection.commit()
        return False

    async def serve(self) -> None:
        while True:
            try:
                if not await self.run_once():
                    await asyncio.sleep(0.25)
            except SQLAlchemyError:
                logger.warning("Worker database unavailable; durable jobs retained")
                await asyncio.sleep(1)

    async def _emit(
        self, connection: AsyncConnection, owner: UUID, run_id: UUID, payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await emit(connection, self.redis, self.prefix, owner, run_id, payload)

    async def _error(
        self, connection: AsyncConnection, owner: UUID, run_id: UUID, code: str, message: str,
    ) -> None:
        await self._emit(connection, owner, run_id, {
            "type": "error", "code": code, "message": message, "retryable": True,
        })

    async def _process(self, connection: AsyncConnection, owner: UUID, run_id: UUID) -> None:
        async with tenant_session(connection, owner) as db:
            run = (await db.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner_id == owner,
            ))).mappings().one_or_none()
            if run is None or run["status"] in TERMINAL:
                await db.execute(delete(run_jobs).where(
                    run_jobs.c.run_id == run_id, run_jobs.c.owner_id == owner,
                ))
                return
        if run["last_seq"]:
            # A previous worker died. Never replay inference over already emitted text.
            await self._error(connection, owner, run_id, "worker_interrupted",
                              "Generation was interrupted. Partial output was preserved.")
            return
        await self._emit(connection, owner, run_id, {
            "type": "message_start", "message_id": str(run["assistant_message_id"]),
            "chat_id": str(run["chat_id"]), "model": run["model"],
        })
        try:
            if run["model"] != self.provider.name:
                raise ValueError("Unsupported provider")
            async with asyncio.timeout(self.timeout):
                await self._generate(connection, owner, run)
        except TimeoutError:
            await self._error(connection, owner, run_id, "deadline_exceeded",
                              "Generation exceeded its time limit. Partial output was preserved.")
        except OutputLimitExceeded:
            await self._error(connection, owner, run_id, "output_limit",
                              "Generation exceeded its output limit. Partial output was preserved.")
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            logger.warning("Generation failed (%s)", type(exc).__name__)
            await self._error(connection, owner, run_id, "generation_failed",
                              "Generation failed. Partial output was preserved.")

    async def _cancelled(self, connection: AsyncConnection, owner: UUID, run_id: UUID) -> bool:
        async with tenant_session(connection, owner) as db:
            return bool(await db.scalar(select(runs.c.cancel_requested).where(
                runs.c.id == run_id, runs.c.owner_id == owner,
            )))

    async def _generate(
        self, connection: AsyncConnection, owner: UUID, run: Mapping[str, Any],
    ) -> None:
        run_id, message_id = run["id"], str(run["assistant_message_id"])
        async with tenant_session(connection, owner) as db:
            position = await db.scalar(select(messages.c.position).where(
                messages.c.id == run["assistant_message_id"], messages.c.owner_id == owner,
            ))
            history = (await db.execute(select(messages).where(
                messages.c.owner_id == owner, messages.c.chat_id == run["chat_id"],
                messages.c.position < position,
            ).order_by(messages.c.position.desc()).limit(self.history_limit))).mappings().all()
        model_messages = [ModelMessage(row["role"], "".join(
            part["text"] for part in row["parts"] if part["type"] == "text"
        )) for row in reversed(history)]
        usage: dict[str, Any] = {"input_tokens": 0, "output_tokens": 0, "reported": False}

        async def complete(reason: str) -> None:
            await self._emit(connection, owner, run_id, {
                "type": "message_complete", "message_id": message_id,
                "stop_reason": reason, "usage": usage,
            })

        if await self._cancelled(connection, owner, run_id):
            await complete("cancelled")
            return
        output_chars = 0
        async with aclosing(self.provider.stream(model_messages)) as stream:
            pending: asyncio.Future[str | ModelUsage] | None = None
            try:
                while True:
                    pending = asyncio.ensure_future(anext(stream))
                    while True:
                        await asyncio.wait({pending}, timeout=0.25)
                        if await self._cancelled(connection, owner, run_id):
                            await complete("cancelled")
                            return
                        if pending.done():
                            break
                    try:
                        item = pending.result()
                    except StopAsyncIteration:
                        break
                    pending = None
                    if isinstance(item, ModelUsage):
                        if usage["reported"]:
                            raise ValueError("Duplicate provider usage")
                        usage = {"input_tokens": item.input_tokens,
                                 "output_tokens": item.output_tokens, "reported": True}
                    elif isinstance(item, str) and not usage["reported"]:
                        if not item:
                            continue
                        validate_message_text(item)
                        output_chars += len(item)
                        if output_chars > self.max_output_chars:
                            raise OutputLimitExceeded
                        await self._emit(connection, owner, run_id, {
                            "type": "text_delta", "part_id": message_id, "text": item,
                        })
                    else:
                        raise ValueError("Invalid provider stream")
            finally:
                if pending is not None:
                    if not pending.done():
                        pending.cancel()
                    with suppress(asyncio.CancelledError, StopAsyncIteration):
                        await pending
        await complete("end_turn")


async def main(once: bool = False) -> None:
    engine = create_async_engine(os.environ["QVELT_DATABASE_URL"], pool_pre_ping=True,
                                 hide_parameters=True)
    redis = redis_client(os.environ["QVELT_REDIS_URL"])
    try:
        worker = Worker(
            engine, redis, prefix=os.getenv("QVELT_REDIS_PREFIX", "qvelt:"),
            timeout=float(os.getenv("QVELT_RUN_TIMEOUT_SECONDS", "60")),
            max_output_chars=int(os.getenv("QVELT_MAX_OUTPUT_CHARS", "200000")),
            history_limit=int(os.getenv("QVELT_HISTORY_MESSAGES", "100")),
        )
        if once:
            await worker.run_once()
        else:
            await worker.serve()
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process durable QVELT generation jobs")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(main(once=parser.parse_args().once))
