"""PostgreSQL tables; apply schema changes explicitly with Alembic."""
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    Uuid,
    func,
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
)
