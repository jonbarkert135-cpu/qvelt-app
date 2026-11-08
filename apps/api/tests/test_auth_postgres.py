"""Real PostgreSQL security checks, using a disposable DB and a non-bypass role."""
import asyncio
import os
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, event, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from qvelt_api.database import chats, sessions, users
from qvelt_api.main import SESSION_SECONDS, create_app
from qvelt_api.security import token_digest, verify_password

pytestmark = pytest.mark.integration
PASSWORD = "test-only-long-password"


@pytest.fixture(scope="module")
def postgres():
    configured = os.getenv("QVELT_TEST_ADMIN_URL")
    if not configured:
        pytest.skip("Set QVELT_TEST_ADMIN_URL to run disposable PostgreSQL integration tests")
    admin_url = make_url(configured)
    database_name = "qvelt_test_" + uuid4().hex
    role = database_name + "_api"
    runtime_url = admin_url.set(drivername="postgresql+asyncpg", database=database_name)

    async def admin_connection():
        return await asyncpg.connect(
            host=admin_url.host, port=admin_url.port or 5432,
            user=admin_url.username, password=admin_url.password, database=admin_url.database,
        )

    async def provision():
        connection = await admin_connection()
        try:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
            await connection.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        finally:
            await connection.close()

    async def grant():
        engine = create_async_engine(runtime_url, hide_parameters=True)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
                await connection.execute(text(
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, chats, '
                    f'messages, runs, run_events, run_jobs TO "{role}"'
                ))
        finally:
            await engine.dispose()

    async def cleanup():
        connection = await admin_connection()
        try:
            await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            await connection.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await connection.close()

    def migrate(action, target):
        environment = dict(os.environ, QVELT_DATABASE_URL=runtime_url.render_as_string(
            hide_password=False,
        ))
        result = subprocess.run(
            [str(Path(__file__).parents[1] / ".venv/bin/alembic"), action, target],
            cwd=Path(__file__).parents[1], env=environment, capture_output=True, text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    try:
        asyncio.run(provision())
        migrate("upgrade", "head")
        # Running the same migration twice must preserve data/schema.
        migrate("upgrade", "head")
        migrate("downgrade", "base")
        migrate("upgrade", "head")
        asyncio.run(grant())
        yield runtime_url, role
    finally:
        asyncio.run(cleanup())


def runtime_engine(postgres, pool_size=1):
    url, role = postgres
    engine = create_async_engine(url, pool_size=pool_size, max_overflow=0, hide_parameters=True)

    @event.listens_for(engine.sync_engine, "connect")
    def use_runtime_role(connection, record):
        cursor = connection.cursor()
        cursor.execute(f'SET ROLE "{role}"')
        cursor.close()
        connection.commit()

    return engine


@pytest_asyncio.fixture
async def api(postgres):
    engine = runtime_engine(postgres)

    now = [datetime(2026, 11, 8, tzinfo=UTC)]
    app = create_app(engine, clock=lambda: now[0])
    try:
        async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            yield SimpleNamespace(client=client, engine=engine, now=now, app=app)
    finally:
        await engine.dispose()


async def account(api):
    username = "user_" + uuid4().hex
    registered = await api.client.post("/auth/register", json={
        "username": username, "password": PASSWORD,
    })
    assert registered.status_code == 201, registered.text
    signed_in = await api.client.post("/auth/login", json={
        "username": username, "password": PASSWORD,
    })
    assert signed_in.status_code == 200, signed_in.text
    return registered.json(), signed_in.json()["access_token"]


def auth(token):
    return {"Authorization": "Bearer " + token}


async def test_two_users_cannot_read_or_impersonate_each_other(api):
    alice, alice_token = await account(api)
    bob, bob_token = await account(api)
    response = await api.client.post("/chats", headers=auth(alice_token), json={"title": "Private"})
    assert response.status_code == 201
    chat = response.json()
    assert chat["owner_id"] == alice["id"]
    assert (await api.client.get("/chats/" + chat["id"], headers=auth(bob_token))).status_code == 404
    assert (await api.client.get("/chats/" + str(uuid4()), headers=auth(bob_token))).status_code == 404
    assert (await api.client.get("/chats", headers=auth(bob_token))).json() == []
    assert (await api.client.get("/chats", headers=auth(alice_token))).json() == [chat]
    assert (await api.client.get("/auth/me", headers=auth(bob_token))).json() == bob
    injected = await api.client.post("/chats", headers=auth(bob_token), json={
        "title": "Stolen owner", "owner_id": alice["id"],
    })
    assert injected.status_code == 422
    assert (await api.client.get("/chats")).status_code == 401


async def test_sessions_expire_at_boundary_and_logout_revokes_only_current(api):
    user, token = await account(api)
    second = await api.client.post("/auth/login", json={
        "username": user["username"], "password": PASSWORD,
    })
    other = second.json()["access_token"]
    assert other != token
    assert second.headers["cache-control"] == "no-store"
    assert "set-cookie" not in second.headers
    assert second.json()["expires_in"] == SESSION_SECONDS
    assert (await api.client.post("/auth/logout", headers=auth(token))).status_code == 204
    assert (await api.client.get("/auth/me", headers=auth(token))).status_code == 401
    api.now[0] += timedelta(seconds=SESSION_SECONDS - 1)
    assert (await api.client.get("/auth/me", headers=auth(other))).status_code == 200
    api.now[0] += timedelta(seconds=1)
    assert (await api.client.get("/auth/me", headers=auth(other))).status_code == 401
    api.now[0] += timedelta(seconds=1)
    assert (await api.client.get("/auth/me", headers=auth(other))).status_code == 401
    forged = secrets.token_urlsafe(32)
    assert (await api.client.get("/auth/me", headers=auth(forged))).status_code == 401


async def test_password_storage_and_identity_validation(api):
    user, token = await account(api)
    other, _ = await account(api)
    assert user["training_opt_in"] is False
    assert set(user) == {"id", "username", "training_opt_in"}
    async with api.engine.connect() as connection:
        stored = (await connection.execute(select(users).where(
            users.c.id.in_([UUID(user["id"]), UUID(other["id"])]),
        ))).mappings().all()
        assert len(stored) == 2
        assert stored[0]["password_hash"] != stored[1]["password_hash"]
        assert all(verify_password(row["password_hash"], PASSWORD) for row in stored)
        session = (await connection.execute(select(sessions).where(
            sessions.c.token_hash == token_digest(token),
        ))).mappings().one()
        assert session["token_hash"] != token
    duplicate = await api.client.post("/auth/register", json={
        "username": " " + user["username"].upper() + " ", "password": PASSWORD,
    })
    assert duplicate.status_code == 409
    bad = await api.client.post("/auth/login", json={
        "username": user["username"], "password": "incorrect-long-password",
    })
    absent = await api.client.post("/auth/login", json={
        "username": "missing_" + uuid4().hex, "password": "incorrect-long-password",
    })
    assert bad.status_code == absent.status_code == 401
    assert bad.json() == absent.json()
    for body in [
        {"username": "bad'; DROP TABLE users;--", "password": PASSWORD},
        {"username": "valid-name", "password": "xY!7"},
        {"username": "valid-name", "password": "x" * 129},
        {"username": "valid-name", "password": PASSWORD, "training_opt_in": True},
    ]:
        response = await api.client.post("/auth/register", json=body)
        assert response.status_code == 422
        assert body["password"] not in response.text
    assert (await api.client.get("/chats?limit=101", headers=auth(token))).status_code == 422
    assert (await api.client.post("/chats", headers=auth(token), json={"title": " "})).status_code == 422


async def test_rls_blocks_unscoped_reads_and_cross_owner_writes_on_reused_connection(api):
    alice, token = await account(api)
    bob, _ = await account(api)
    chat = await api.client.post("/chats", headers=auth(token), json={"title": "RLS private"})
    chat_id = UUID(chat.json()["id"])
    async with api.engine.begin() as connection:
        assert await connection.scalar(text(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )) is False
        assert (await connection.execute(select(chats))).all() == []
        await connection.execute(text("SELECT set_config('qvelt.owner_id', :owner, true)"),
                                 {"owner": alice["id"]})
        assert (await connection.execute(select(chats))).mappings().one()["id"] == chat_id
    # Same physical connection, new transaction: previous identity must be gone.
    async with api.engine.begin() as connection:
        assert (await connection.execute(select(chats))).all() == []
        await connection.execute(text("SELECT set_config('qvelt.owner_id', :owner, true)"),
                                 {"owner": bob["id"]})
        assert (await connection.execute(select(chats).where(chats.c.id == chat_id))).all() == []
        changed = await connection.execute(update(chats).where(chats.c.id == chat_id)
                                           .values(title="Stolen"))
        assert changed.rowcount == 0
        removed = await connection.execute(delete(chats).where(chats.c.id == chat_id))
        assert removed.rowcount == 0
    with pytest.raises(DBAPIError, match="row-level security"):
        async with api.engine.begin() as connection:
            await connection.execute(text("SELECT set_config('qvelt.owner_id', :owner, true)"),
                                     {"owner": bob["id"]})
            await connection.execute(insert(chats).values(
                id=uuid4(), owner_id=UUID(alice["id"]), title="Forged",
            ))
    with pytest.raises(DBAPIError, match="row-level security"):
        async with api.engine.begin() as connection:
            await connection.execute(text("SELECT set_config('qvelt.owner_id', :owner, true)"),
                                     {"owner": alice["id"]})
            await connection.execute(update(chats).where(chats.c.id == chat_id)
                                     .values(owner_id=UUID(bob["id"])))


async def test_startup_refuses_role_that_can_bypass_rls(postgres):
    url, _ = postgres
    engine = create_async_engine(url, hide_parameters=True)
    try:
        app = create_app(engine)
        with pytest.raises(RuntimeError, match="NOSUPERUSER NOBYPASSRLS"):
            async with app.router.lifespan_context(app):
                pass
    finally:
        await engine.dispose()
