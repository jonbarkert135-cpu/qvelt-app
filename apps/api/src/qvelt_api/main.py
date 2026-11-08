import os
import re
import secrets
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.concurrency import run_in_threadpool

from qvelt_api.database import (
    assert_runtime_role,
    chats,
    messages,
    runs,
    sessions,
    users,
    validate_message_text,
)
from qvelt_api.request_limits import MessageBodyLimit, PrivateResponses
from qvelt_api.security import (
    TOKEN_PATTERN,
    dummy_hash,
    password_hasher,
    token_digest,
    verify_password,
)
from qvelt_api.streaming import TERMINAL, owned_run, redis_client, submit, subscribe

SESSION_SECONDS = 86400
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class UserView(BaseModel):
    id: UUID
    username: str
    training_opt_in: bool


class SessionView(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = SESSION_SECONDS


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be blank")
        return value


class ChatView(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    created_at: datetime


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=100_000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return validate_message_text(value)


class MessageView(BaseModel):
    id: UUID
    chat_id: UUID
    position: int
    role: Literal["user", "assistant"]
    status: str
    parts: list[dict[str, Any]]
    training_opt_in: bool
    created_at: datetime


class RunView(BaseModel):
    id: UUID
    chat_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    model: str
    status: str
    cancel_requested: bool
    last_seq: int
    usage: dict[str, Any] | None


def unauthorized() -> HTTPException:
    return HTTPException(401, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"})


def create_app(
    engine: AsyncEngine | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = engine
        url = os.getenv("QVELT_DATABASE_URL")
        if database is None and url:
            database = create_async_engine(url, pool_pre_ping=True, hide_parameters=True)
        app.state.database = database
        redis_url = os.getenv("QVELT_REDIS_URL")
        app.state.redis = redis_client(redis_url) if redis_url else None
        app.state.redis_prefix = os.getenv("QVELT_REDIS_PREFIX", "qvelt:")
        if not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", app.state.redis_prefix):
            raise RuntimeError("Invalid Redis namespace prefix")
        try:
            if database is not None:
                async with database.connect() as connection:
                    await assert_runtime_role(connection)
            yield
        finally:
            if app.state.redis is not None:
                await app.state.redis.aclose()
            if database is not None and engine is None:
                await database.dispose()

    app = FastAPI(title="QVELT API", version="0.0.1", lifespan=lifespan)
    app.add_middleware(MessageBodyLimit)
    app.add_middleware(PrivateResponses)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Default validation errors can echo passwords and unknown secret fields.
        errors = [{k: e[k] for k in ("loc", "msg", "type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    async def database() -> AsyncIterator[AsyncSession]:
        db_engine = app.state.database
        if db_engine is None:
            raise HTTPException(503, "Database is not configured")
        async with async_sessionmaker(db_engine, expire_on_commit=False)() as db:
            yield db

    DB = Annotated[AsyncSession, Depends(database)]

    async def session_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        request: Request,
    ) -> str:
        if credentials is None or not TOKEN_PATTERN.fullmatch(credentials.credentials):
            raise unauthorized()
        digest = token_digest(credentials.credentials)
        request.state.token_hash = digest
        return digest

    async def authenticated(digest: Annotated[str, Depends(session_token)], db: DB) -> UUID:
        owner = await db.scalar(select(sessions.c.owner_id).where(
            sessions.c.token_hash == digest, sessions.c.expires_at > clock(),
        ))
        if owner is None:
            raise unauthorized()
        await db.execute(text("SELECT set_config('qvelt.owner_id', :owner, true)"),
                         {"owner": str(owner)})
        return owner

    Owner = Annotated[UUID, Depends(authenticated)]

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/register", response_model=UserView, status_code=201)
    async def register(body: Credentials, db: DB) -> dict:
        owner = uuid4()
        hashed = await run_in_threadpool(password_hasher.hash, body.password.get_secret_value())
        try:
            row = (await db.execute(insert(users).values(
                id=owner, owner_id=owner, username=body.username, password_hash=hashed,
            ).returning(users.c.id, users.c.username, users.c.training_opt_in))).mappings().one()
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "Username is unavailable") from None
        return dict(row)

    @app.post("/auth/login", response_model=SessionView)
    async def login(body: Credentials, db: DB) -> SessionView:
        user = (await db.execute(select(users).where(
            users.c.username == body.username,
        ))).mappings().one_or_none()
        valid = await run_in_threadpool(
            verify_password, user["password_hash"] if user else dummy_hash,
            body.password.get_secret_value(),
        )
        if not valid or user is None:
            raise unauthorized()
        token = secrets.token_urlsafe(32)
        await db.execute(insert(sessions).values(
            token_hash=token_digest(token), owner_id=user["id"],
            expires_at=clock() + timedelta(seconds=SESSION_SECONDS),
        ))
        await db.commit()
        return SessionView(access_token=token)

    @app.get("/auth/me", response_model=UserView)
    async def me(owner: Owner, db: DB) -> dict:
        row = await db.execute(select(users.c.id, users.c.username, users.c.training_opt_in)
                               .where(users.c.id == owner, users.c.owner_id == owner))
        return dict(row.mappings().one())

    @app.post("/auth/logout", status_code=204)
    async def logout(owner: Owner, request: Request, db: DB) -> Response:
        await db.execute(delete(sessions).where(
            sessions.c.owner_id == owner, sessions.c.token_hash == request.state.token_hash,
        ))
        await db.commit()
        return Response(status_code=204)

    @app.post("/chats", response_model=ChatView, status_code=201)
    async def create_chat(body: ChatInput, owner: Owner, db: DB) -> dict:
        row = (await db.execute(insert(chats).values(
            id=uuid4(), owner_id=owner, title=body.title,
        ).returning(chats))).mappings().one()
        await db.commit()
        return dict(row)

    @app.get("/chats", response_model=list[ChatView])
    async def list_chats(
        owner: Owner, db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[dict]:
        rows = await db.execute(select(chats).where(chats.c.owner_id == owner)
                               .order_by(chats.c.created_at.desc(), chats.c.id).limit(limit))
        return [dict(row) for row in rows.mappings()]

    @app.get("/chats/{chat_id}", response_model=ChatView)
    async def get_chat(chat_id: UUID, owner: Owner, db: DB) -> dict:
        row = (await db.execute(select(chats).where(
            chats.c.id == chat_id, chats.c.owner_id == owner,
        ))).mappings().one_or_none()
        if row is None:
            raise HTTPException(404, "Chat not found")
        return dict(row)

    Cursor = Annotated[int, Header(alias="Last-Event-ID", ge=0, le=9_007_199_254_740_991)]
    Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128,
                                pattern=r"^[A-Za-z0-9._:-]+$")]

    def require_streaming() -> None:
        if app.state.redis is None:
            raise HTTPException(503, "Streaming is not configured")

    async def stream_response(
        run: Mapping[str, Any], owner: UUID, db: AsyncSession, request: Request, after: int,
    ) -> Response:
        require_streaming()
        if after > run["last_seq"]:
            raise HTTPException(409, "Cursor is ahead of the run")
        headers = {"X-Run-ID": str(run["id"]),
                   "X-Message-ID": str(run["assistant_message_id"]), "X-Accel-Buffering": "no"}
        # Release authentication/query connections before the long-lived response.
        await db.rollback()
        if run["status"] in TERMINAL and after == run["last_seq"]:
            return Response(status_code=204, headers=headers)
        return StreamingResponse(subscribe(
            app.state.database, app.state.redis, app.state.redis_prefix, owner, run["id"],
            request.state.token_hash, clock, after, request,
        ), media_type="text/event-stream", headers=headers)

    @app.post("/chats/{chat_id}/messages", response_class=StreamingResponse,
              responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}})
    async def send_message(
        chat_id: UUID, body: MessageInput, owner: Owner, db: DB, request: Request,
        idempotency_key: Key, last_event_id: Cursor = 0,
    ) -> Response:
        require_streaming()
        run = await submit(db, owner, chat_id, idempotency_key, body.text, after=last_event_id)
        return await stream_response(run, owner, db, request, last_event_id)

    @app.get("/chats/{chat_id}/messages", response_model=list[MessageView])
    async def list_messages(
        chat_id: UUID, owner: Owner, db: DB,
        after: Annotated[int, Query(ge=0, le=9_007_199_254_740_991)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[dict[str, Any]]:
        chat = await db.scalar(select(chats.c.id).where(
            chats.c.id == chat_id, chats.c.owner_id == owner,
        ))
        if chat is None:
            raise HTTPException(404, "Chat not found")
        rows = await db.execute(select(messages).where(
            messages.c.chat_id == chat_id, messages.c.owner_id == owner, messages.c.position > after,
        ).order_by(messages.c.position).limit(limit))
        return [dict(row) for row in rows.mappings()]

    @app.get("/runs/{run_id}", response_model=RunView)
    async def get_run(run_id: UUID, owner: Owner, db: DB) -> dict[str, Any]:
        return dict(await owned_run(db, owner, run_id))

    @app.get("/runs/{run_id}/events", response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
                        204: {"description": "Terminal cursor already consumed"}})
    async def resume(
        run_id: UUID, owner: Owner, db: DB, request: Request, last_event_id: Cursor = 0,
    ) -> Response:
        run = await owned_run(db, owner, run_id)
        return await stream_response(run, owner, db, request, last_event_id)

    @app.post("/runs/{run_id}/cancel", status_code=202)
    async def cancel(run_id: UUID, owner: Owner, db: DB) -> dict[str, str]:
        run = await owned_run(db, owner, run_id)
        if run["status"] not in TERMINAL:
            await db.execute(update(runs).where(runs.c.id == run_id, runs.c.owner_id == owner)
                             .where(runs.c.status.in_(["queued", "running"]))
                             .values(cancel_requested=True))
            await db.commit()
        return {"run_id": str(run_id), "status": run["status"]}

    return app


app = create_app()
