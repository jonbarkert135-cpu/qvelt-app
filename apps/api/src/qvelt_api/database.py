"""PostgreSQL tables; apply schema changes explicitly with Alembic."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from anyio import CancelScope
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

metadata = MetaData()
users = Table(
    "users", metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, nullable=False),
    Column("username", String(64), nullable=False, unique=True),
    Column("password_hash", String, nullable=False),
    Column("training_opt_in", Boolean, nullable=False, server_default="false"),
    CheckConstraint("owner_id = id", name="user_owns_account"),
)
sessions = Table(
    "sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
chats = Table(
    "chats", metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
           index=True),
    Column("title", String(200), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("id", "owner_id", name="uq_chats_id_owner"),
)

messages = Table(
    "messages", metadata,
    Column("id", Uuid, primary_key=True), Column("owner_id", Uuid, nullable=False),
    Column("chat_id", Uuid, nullable=False), Column("position", BigInteger, nullable=False),
    Column("role", String, nullable=False), Column("status", String, nullable=False),
    Column("parts", JSONB, nullable=False, server_default="[]"),
    Column("training_opt_in", Boolean, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["chat_id", "owner_id"], ["chats.id", "chats.owner_id"], ondelete="CASCADE"),
    UniqueConstraint("id", "owner_id", "chat_id", name="uq_messages_id_owner_chat"),
    UniqueConstraint("chat_id", "position", name="uq_messages_position"),
    CheckConstraint("position > 0"), CheckConstraint("role IN ('user', 'assistant')"),
    CheckConstraint("status IN ('queued','streaming','complete','cancelled','error')"),
)
runs = Table(
    "runs", metadata,
    Column("id", Uuid, primary_key=True), Column("owner_id", Uuid, nullable=False),
    Column("chat_id", Uuid, nullable=False), Column("user_message_id", Uuid, nullable=False),
    Column("assistant_message_id", Uuid, nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_hash", String(64), nullable=False), Column("model", String, nullable=False),
    Column("status", String, nullable=False, server_default="queued"),
    Column("cancel_requested", Boolean, nullable=False, server_default="false"),
    Column("last_seq", BigInteger, nullable=False, server_default="0"), Column("usage", JSONB),
    Column("started_at", DateTime(timezone=True)), Column("finished_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["user_message_id", "owner_id", "chat_id"],
                         ["messages.id", "messages.owner_id", "messages.chat_id"], ondelete="CASCADE"),
    ForeignKeyConstraint(["assistant_message_id", "owner_id", "chat_id"],
                         ["messages.id", "messages.owner_id", "messages.chat_id"], ondelete="CASCADE"),
    UniqueConstraint("id", "owner_id", name="uq_runs_id_owner"),
    UniqueConstraint("owner_id", "chat_id", "idempotency_key", name="uq_runs_idempotency"),
    CheckConstraint("last_seq BETWEEN 0 AND 9007199254740991"),
    CheckConstraint("status IN ('queued','running','complete','cancelled','error')"),
)
Index("uq_runs_active_chat", runs.c.owner_id, runs.c.chat_id, unique=True,
      postgresql_where=runs.c.status.in_(["queued", "running"]))
run_events = Table(
    "run_events", metadata,
    Column("run_id", Uuid, primary_key=True), Column("seq", BigInteger, primary_key=True),
    Column("owner_id", Uuid, nullable=False), Column("payload", JSONB, nullable=False),
    ForeignKeyConstraint(["run_id", "owner_id"], ["runs.id", "runs.owner_id"], ondelete="CASCADE"),
    CheckConstraint("seq BETWEEN 1 AND 9007199254740991"),
)
# Trusted service outbox, like the authentication tables: not exposed by any endpoint.
run_jobs = Table(
    "run_jobs", metadata,
    Column("run_id", Uuid, primary_key=True), Column("owner_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["run_id", "owner_id"], ["runs.id", "runs.owner_id"], ondelete="CASCADE"),
)


def validate_message_text(value: str) -> str:
    """Reject strings PostgreSQL JSONB cannot store, before attempting a write."""
    if "\x00" in value:
        raise ValueError("Message contains an unsupported character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Message must contain valid Unicode") from None
    return value


async def assert_runtime_role(connection: AsyncConnection) -> None:
    privileged = await connection.scalar(text(
        "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ))
    if privileged:
        raise RuntimeError("API database role must be NOSUPERUSER NOBYPASSRLS")


@asynccontextmanager
async def tenant_session(
    bind: AsyncEngine | AsyncConnection, owner: UUID,
) -> AsyncIterator[AsyncSession]:
    # These contexts contain DB operations only, never network streaming/provider
    # calls. A subscriber disconnect must not interrupt an asyncpg round trip or
    # rollback and return a closed connection to the pool.
    with CancelScope(shield=True):
        async with async_sessionmaker(bind, expire_on_commit=False)() as db, db.begin():
            await db.execute(text("SELECT set_config('qvelt.owner_id', :owner, true)"),
                             {"owner": str(owner)})
            yield db
