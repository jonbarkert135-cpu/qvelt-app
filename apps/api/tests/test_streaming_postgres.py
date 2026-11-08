"""PostgreSQL + Redis integration, including a real TCP disconnect/resume."""
import asyncio
import json
import os
import secrets
import socket
import sys
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
import test_auth_postgres as auth_tests
import uvicorn
from sqlalchemy import select
from test_auth_postgres import account, auth, runtime_engine

from qvelt_api.database import messages, run_events, runs, tenant_session
from qvelt_api.events import parse_event
from qvelt_api.providers import FakeProvider, ModelUsage
from qvelt_api.streaming import redis_client, stream_key
from qvelt_api.worker import Worker

pytestmark = pytest.mark.integration
api, postgres = auth_tests.api, auth_tests.postgres


@pytest_asyncio.fixture
async def env(api, postgres):
    url = os.getenv("QVELT_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set QVELT_TEST_REDIS_URL for Redis integration tests")
    redis = redis_client(url)
    assert await redis.ping()
    prefix = "test:" + uuid4().hex + ":"
    api.app.state.redis, api.app.state.redis_prefix = redis, prefix
    worker_engine = runtime_engine(postgres, pool_size=2)
    try:
        yield SimpleNamespace(api=api, redis=redis, prefix=prefix, worker_engine=worker_engine)
    finally:
        keys = [key async for key in redis.scan_iter(match=prefix + "*")]
        if keys:
            await redis.delete(*keys)
        await redis.aclose()
        if api.app.state.redis is not redis and api.app.state.redis is not None:
            await api.app.state.redis.aclose()
        await worker_engine.dispose()


@asynccontextmanager
async def running(env, provider=None, **limits):
    worker = Worker(env.worker_engine, env.redis, provider, prefix=env.prefix, **limits)
    task = asyncio.create_task(worker.serve())
    try:
        async with asyncio.timeout(15):
            yield worker
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def chat(env):
    user, token = await account(env.api)
    response = await env.api.client.post("/chats", headers=auth(token), json={"title": "Stream"})
    assert response.status_code == 201
    return user, token, response.json()["id"]


def frames(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.split("\n\n"):
        lines = block.splitlines()
        data = [line[6:] for line in lines if line.startswith("data: ")]
        if not data:
            continue
        event = parse_event("\n".join(data))
        assert f"id: {event['seq']}" in lines
        assert f"event: {event['type']}" in lines
        events.append(event)
    return events


async def send(env, token, chat_id, key="key1", text="Hello 🌍\nПривіт"):
    return await env.api.client.post(f"/chats/{chat_id}/messages",
                                     headers={**auth(token), "Idempotency-Key": key},
                                     json={"text": text})


async def test_stream_replay_idempotency_and_persisted_parts(env):
    user, token, chat_id = await chat(env)
    async with running(env):
        first = await send(env, token, chat_id)
        events = frames(first)
        replay = await send(env, token, chat_id)
        assert frames(replay) == events
    run_id = first.headers["x-run-id"]
    assert run_id == replay.headers["x-run-id"]
    assert events[0]["type"] == "message_start"
    assert events[-1]["type"] == "message_complete"
    assert events[-1]["usage"]["reported"] is True
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
    text = "".join(event["text"] for event in events if event["type"] == "text_delta")
    assert text == "Echo (FakeProvider): Hello 🌍\nПривіт"
    assert events[-1]["usage"]["output_tokens"] == len(text.split())
    suffix = await env.api.client.get(f"/runs/{run_id}/events",
                                      headers={**auth(token), "Last-Event-ID": "1"})
    assert frames(suffix) == events[1:]
    caught_up = await env.api.client.get(f"/runs/{run_id}/events", headers={
        **auth(token), "Last-Event-ID": str(len(events)),
    })
    assert caught_up.status_code == 204
    changed = await send(env, token, chat_id, text="Different input")
    assert changed.status_code == 409
    rows = (await env.api.client.get(f"/chats/{chat_id}/messages", headers=auth(token))).json()
    assert len(rows) == 2
    assert [row["position"] for row in rows] == [1, 2]
    assert rows[1]["parts"][0]["text"] == text
    assert all(row["training_opt_in"] is False for row in rows)
    mirrored = await env.redis.xrange(stream_key(env.prefix, UUID(run_id)))
    assert [parse_event(fields["data"]) for _, fields in mirrored] == events
    assert await env.redis.ttl(stream_key(env.prefix, UUID(run_id))) > 0
    async with env.api.engine.connect() as connection:
        for table in (messages, runs, run_events):
            assert (await connection.execute(select(table))).all() == []
    async with tenant_session(env.api.engine, UUID(user["id"])) as db:
        assert len((await db.execute(select(runs))).all()) == 1


async def test_foreign_runs_messages_and_invalid_requests(env):
    _, token, chat_id = await chat(env)
    _, other_token = await account(env.api)
    async with running(env):
        response = await send(env, token, chat_id)
    run_id = response.headers["x-run-id"]
    for method, path in [
        ("GET", f"/runs/{run_id}"), ("GET", f"/runs/{run_id}/events"),
        ("POST", f"/runs/{run_id}/cancel"), ("GET", f"/chats/{chat_id}/messages"),
        ("POST", f"/chats/{chat_id}/messages"),
    ]:
        denied = await env.api.client.request(method, path, headers={
            **auth(other_token), "Idempotency-Key": "other",
        }, json={"text": "Do not expose"})
        assert denied.status_code == 404
    for cursor, status in [("-1", 422), ("1.5", 422), ("invalid", 422), ("999", 409)]:
        bad = await env.api.client.get(f"/runs/{run_id}/events", headers={
            **auth(token), "Last-Event-ID": cursor,
        })
        assert bad.status_code == status
    for body in [{"text": " "}, {"text": "x" * 100001}, {"text": "x", "owner_id": str(uuid4())}]:
        bad = await env.api.client.post(f"/chats/{chat_id}/messages", headers={
            **auth(token), "Idempotency-Key": "bad",
        }, json=body)
        assert bad.status_code == 422
    missing = await env.api.client.post(f"/chats/{chat_id}/messages",
                                        headers=auth(token), json={"text": "Missing key"})
    assert missing.status_code == 422
    huge = await env.api.client.post(f"/chats/{chat_id}/messages", headers={
        **auth(token), "Idempotency-Key": "huge", "Content-Type": "application/json",
    }, content=b'{' + b' ' * 1048576 + b'}')
    assert huge.status_code == 413


@pytest.mark.parametrize("text", ["invalid\x00text", "\ud800"], ids=["nul", "surrogate"])
async def test_invalid_storage_text_is_rejected_before_database_write(env, text):
    _, token, chat_id = await chat(env)
    response = await env.api.client.post(f"/chats/{chat_id}/messages", headers={
        **auth(token), "Idempotency-Key": "invalid-text", "Content-Type": "application/json",
    }, content=json.dumps({"text": text}, ensure_ascii=True).encode())
    assert response.status_code == 422
    assert (await env.api.client.get(f"/chats/{chat_id}/messages", headers=auth(token))).json() == []


async def test_cursor_on_a_new_request_does_not_enqueue_rejected_work(env):
    _, token, chat_id = await chat(env)
    response = await env.api.client.post(f"/chats/{chat_id}/messages", headers={
        **auth(token), "Idempotency-Key": "new", "Last-Event-ID": "1",
    }, json={"text": "Must not be queued"})
    assert response.status_code == 409
    assert (await env.api.client.get(f"/chats/{chat_id}/messages", headers=auth(token))).json() == []


class GatedProvider(FakeProvider):
    def __init__(self):
        self.blocked, self.release, self.closed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stream(self, history):
        try:
            yield "Partial 🌍"
            self.blocked.set()
            await self.release.wait()
            yield " finished"
            yield ModelUsage(1, 2)
        finally:
            self.closed.set()


async def test_concurrent_idempotency_and_cancellation_interrupts_a_stalled_provider(env):
    _, token, chat_id = await chat(env)
    provider = GatedProvider()
    async with running(env, provider):
        first = asyncio.create_task(send(env, token, chat_id))
        try:
            await provider.blocked.wait()
            duplicate = asyncio.create_task(send(env, token, chat_id))
            try:
                conflict = await send(env, token, chat_id, key="different")
                assert conflict.status_code == 409
                listed = (await env.api.client.get(f"/chats/{chat_id}/messages",
                                                   headers=auth(token))).json()
                async with tenant_session(env.api.engine, UUID((await env.api.client.get(
                    "/auth/me", headers=auth(token),
                )).json()["id"])) as db:
                    run_id = await db.scalar(select(runs.c.id).where(
                        runs.c.assistant_message_id == UUID(listed[1]["id"]),
                    ))
                cancelled = await env.api.client.post(f"/runs/{run_id}/cancel", headers=auth(token))
                assert cancelled.status_code == 202
                one, two = await asyncio.gather(first, duplicate)
                assert frames(one) == frames(two)
                assert frames(one)[-1]["stop_reason"] == "cancelled"
                assert frames(one)[-1]["usage"]["reported"] is False
                assert provider.closed.is_set()
                assert "finished" not in one.text
            finally:
                duplicate.cancel()
                with suppress(asyncio.CancelledError):
                    await duplicate
        finally:
            first.cancel()
            with suppress(asyncio.CancelledError):
                await first


async def test_worker_crash_preserves_prefix_and_does_not_repeat_generation(env):
    user, token, chat_id = await chat(env)
    provider = GatedProvider()
    first = asyncio.create_task(send(env, token, chat_id))
    task = asyncio.create_task(Worker(env.worker_engine, env.redis, provider,
                                      prefix=env.prefix).serve())
    try:
        async with asyncio.timeout(10):
            await provider.blocked.wait()
            # The competing worker must not claim the still-locked run.
            assert await Worker(env.worker_engine, env.redis, prefix=env.prefix).run_once() is False
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            assert await Worker(env.worker_engine, env.redis, prefix=env.prefix).run_once() is True
            response = await first
        events = frames(response)
        assert events[-1]["code"] == "worker_interrupted"
        assert sum(event["type"] == "message_start" for event in events) == 1
        assert "".join(event["text"] for event in events if event["type"] == "text_delta") == "Partial 🌍"
        async with tenant_session(env.api.engine, UUID(user["id"])) as db:
            assert len((await db.execute(select(runs))).all()) == 1
    finally:
        task.cancel()
        first.cancel()
        for pending in (task, first):
            with suppress(asyncio.CancelledError):
                await pending


class FailingProvider(FakeProvider):
    async def stream(self, history):
        yield "Preserved prefix"
        raise RuntimeError("sensitive-internal-provider-detail")


class InvalidTextProvider(FakeProvider):
    async def stream(self, history):
        yield "Preserved prefix"
        yield "invalid\x00output"


async def test_invalid_provider_text_is_a_sanitized_generation_error(env):
    _, token, chat_id = await chat(env)
    async with running(env, InvalidTextProvider()):
        response = await send(env, token, chat_id)
    assert frames(response)[-1]["code"] == "generation_failed"
    assert "invalid" not in response.text


async def test_revocation_closes_subscriber_without_cancelling_durable_work(env):
    user, token, chat_id = await chat(env)
    provider = GatedProvider()
    async with running(env, provider):
        request = asyncio.create_task(send(env, token, chat_id))
        try:
            await provider.blocked.wait()
            assert (await env.api.client.post("/auth/logout", headers=auth(token))).status_code == 204
            partial = await request
            received = frames(partial)
            assert all(event["type"] not in ("message_complete", "error") for event in received)
            assert [event["seq"] for event in received] == list(range(1, len(received) + 1))
            assert not provider.closed.is_set()
            run_id = partial.headers["x-run-id"]
            async with tenant_session(env.api.engine, UUID(user["id"])) as db:
                current = (await db.execute(select(runs).where(
                    runs.c.id == UUID(run_id), runs.c.owner_id == UUID(user["id"]),
                ))).mappings().one()
                assert current["status"] == "running"
                assert current["cancel_requested"] is False
            assert (await env.api.client.get(f"/runs/{run_id}", headers=auth(token))).status_code == 401
            provider.release.set()
            login = await env.api.client.post("/auth/login", json={
                "username": user["username"], "password": auth_tests.PASSWORD,
            })
            new_token = login.json()["access_token"]
            replay = await env.api.client.get(f"/runs/{run_id}/events", headers=auth(new_token))
            assert frames(replay)[-1]["type"] == "message_complete"
        finally:
            provider.release.set()
            request.cancel()
            with suppress(asyncio.CancelledError):
                await request


@pytest.mark.parametrize("mode,code", [
    ("failure", "generation_failed"), ("timeout", "deadline_exceeded"), ("output", "output_limit"),
])
async def test_provider_failures_and_limits_preserve_partial_output(env, mode, code):
    _, token, chat_id = await chat(env)
    provider = GatedProvider() if mode == "timeout" else FailingProvider()
    options = {"timeout": 0.1} if mode == "timeout" else {"max_output_chars": 1} if mode == "output" else {}
    async with running(env, provider, **options):
        response = await send(env, token, chat_id)
    events = frames(response)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == code
    assert "sensitive-internal-provider-detail" not in response.text
    stored = (await env.api.client.get(f"/chats/{chat_id}/messages", headers=auth(token))).json()
    assert stored[1]["status"] == "error"
    if mode == "failure":
        assert stored[1]["parts"][0]["text"] == "Preserved prefix"


async def test_redis_outage_does_not_lose_the_durable_result(env):
    _, token, chat_id = await chat(env)
    offline = redis_client("redis://127.0.0.1:1/0")
    env.api.app.state.redis = offline
    actual = env.redis
    env.redis = offline
    try:
        async with running(env):
            response = await send(env, token, chat_id)
        events = frames(response)
        assert events[-1]["type"] == "message_complete"
        replay = await env.api.client.get(f"/runs/{response.headers['x-run-id']}/events",
                                          headers=auth(token))
        assert frames(replay) == events
    finally:
        env.redis = actual
        await offline.aclose()


async def test_actual_tcp_disconnect_leaves_worker_alive_and_resumes_without_duplicates(env):
    _, token, chat_id = await chat(env)
    provider = GatedProvider()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(env.api.app, lifespan="off", access_log=False,
                                          log_level="error", loop="asyncio"))
    server_task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with running(env, provider):
            while not server.started:
                await asyncio.sleep(0.01)
            received = []
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                async with client.stream("POST", f"/chats/{chat_id}/messages", headers={
                    **auth(token), "Idempotency-Key": "tcp",
                }, json={"text": "Network test"}) as response:
                    assert response.status_code == 200
                    run_id = response.headers["x-run-id"]
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            received.append(parse_event(line[6:]))
                            if received[-1]["type"] == "text_delta":
                                break
                await provider.blocked.wait()
                assert not provider.closed.is_set()
                provider.release.set()
                replay = await client.get(f"/runs/{run_id}/events", headers={
                    **auth(token), "Last-Event-ID": str(received[-1]["seq"]),
                })
                combined = received + frames(replay)
                assert [event["seq"] for event in combined] == list(range(1, len(combined) + 1))
                assert combined[-1]["type"] == "message_complete"
                assert "".join(event["text"] for event in combined if event["type"] == "text_delta") == "Partial 🌍 finished"
    finally:
        provider.release.set()
        server.should_exit = True
        await server_task
        sock.close()


async def test_separate_worker_process_consumes_durable_job(env, postgres):
    user, token, chat_id = await chat(env)
    url, role = postgres
    secret = secrets.token_urlsafe(32)
    admin = await asyncpg.connect(host=url.host, port=url.port, user=url.username,
                                  password=url.password, database=url.database)
    try:
        quoted = await admin.fetchval("SELECT quote_literal($1::text)", secret)
        await admin.execute(f'ALTER ROLE "{role}" LOGIN PASSWORD {quoted}')
    finally:
        await admin.close()
    pending = asyncio.create_task(send(env, token, chat_id, key="process"))
    child = None
    try:
        async with asyncio.timeout(15):
            while True:
                async with tenant_session(env.api.engine, UUID(user["id"])) as db:
                    queued = await db.scalar(select(runs.c.id).where(
                        runs.c.owner_id == UUID(user["id"]), runs.c.chat_id == UUID(chat_id),
                    ))
                if queued is not None:
                    break
                await asyncio.sleep(0.01)
            worker_environment = dict(
                os.environ,
                QVELT_DATABASE_URL=url.set(username=role, password=secret).render_as_string(
                    hide_password=False,
                ),
                QVELT_REDIS_URL=os.environ["QVELT_TEST_REDIS_URL"], QVELT_REDIS_PREFIX=env.prefix,
            )
            child = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "qvelt_api.worker", "--once",
                cwd=Path(__file__).parents[1], env=worker_environment,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await child.communicate()
            assert child.returncode == 0, stderr.decode()
            response = await pending
        assert frames(response)[-1]["type"] == "message_complete"
        assert response.headers["x-run-id"] == str(queued)
    finally:
        if child is not None and child.returncode is None:
            child.terminate()
            await child.wait()
        pending.cancel()
        with suppress(asyncio.CancelledError):
            await pending
