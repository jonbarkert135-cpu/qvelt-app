"""Accounts, revocable sessions and owner-scoped chats."""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("owner_id", sa.Uuid, nullable=False),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("training_opt_in", sa.Boolean, nullable=False, server_default="false"),
        sa.CheckConstraint("owner_id = id", name="user_owns_account"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "chats",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("owner_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_chats_owner_id", "chats", ["owner_id"])
    op.execute("ALTER TABLE chats ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chats FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY chats_owner ON chats
        USING (owner_id = nullif(current_setting('qvelt.owner_id', true), '')::uuid)
        WITH CHECK (owner_id = nullif(current_setting('qvelt.owner_id', true), '')::uuid)""")


def downgrade() -> None:
    op.drop_table("chats")
    op.drop_table("sessions")
    op.drop_table("users")
