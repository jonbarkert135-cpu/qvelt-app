"""Durable runs, event journal and a transactional service outbox."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_chats_id_owner", "chats", ["id", "owner_id"])
    op.execute("""CREATE TABLE messages (
        id uuid PRIMARY KEY, owner_id uuid NOT NULL, chat_id uuid NOT NULL,
        position bigint NOT NULL CHECK (position > 0),
        role text NOT NULL CHECK (role IN ('user','assistant')),
        status text NOT NULL CHECK (status IN ('queued','streaming','complete','cancelled','error')),
        parts jsonb NOT NULL DEFAULT '[]', training_opt_in boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY (chat_id,owner_id) REFERENCES chats(id,owner_id) ON DELETE CASCADE,
        CONSTRAINT uq_messages_id_owner_chat UNIQUE(id,owner_id,chat_id),
        CONSTRAINT uq_messages_position UNIQUE(chat_id,position))""")
    op.execute("""CREATE TABLE runs (
        id uuid PRIMARY KEY, owner_id uuid NOT NULL, chat_id uuid NOT NULL,
        user_message_id uuid NOT NULL, assistant_message_id uuid NOT NULL,
        idempotency_key varchar(128) NOT NULL, request_hash varchar(64) NOT NULL,
        model text NOT NULL, status text NOT NULL DEFAULT 'queued'
            CHECK (status IN ('queued','running','complete','cancelled','error')),
        cancel_requested boolean NOT NULL DEFAULT false,
        last_seq bigint NOT NULL DEFAULT 0 CHECK (last_seq BETWEEN 0 AND 9007199254740991),
        usage jsonb, started_at timestamptz, finished_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY (user_message_id,owner_id,chat_id)
            REFERENCES messages(id,owner_id,chat_id) ON DELETE CASCADE,
        FOREIGN KEY (assistant_message_id,owner_id,chat_id)
            REFERENCES messages(id,owner_id,chat_id) ON DELETE CASCADE,
        CONSTRAINT uq_runs_id_owner UNIQUE(id,owner_id),
        CONSTRAINT uq_runs_idempotency UNIQUE(owner_id,chat_id,idempotency_key))""")
    op.execute("""CREATE UNIQUE INDEX uq_runs_active_chat ON runs(owner_id,chat_id)
        WHERE status IN ('queued','running')""")
    op.execute("""CREATE TABLE run_events (
        run_id uuid NOT NULL, seq bigint NOT NULL CHECK (seq BETWEEN 1 AND 9007199254740991),
        owner_id uuid NOT NULL, payload jsonb NOT NULL, PRIMARY KEY(run_id,seq),
        FOREIGN KEY(run_id,owner_id) REFERENCES runs(id,owner_id) ON DELETE CASCADE)""")
    op.execute("""CREATE TABLE run_jobs (
        run_id uuid PRIMARY KEY, owner_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY(run_id,owner_id) REFERENCES runs(id,owner_id) ON DELETE CASCADE)""")
    for table in ("messages", "runs", "run_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table}
            USING (owner_id = nullif(current_setting('qvelt.owner_id',true),'')::uuid)
            WITH CHECK (owner_id = nullif(current_setting('qvelt.owner_id',true),'')::uuid)""")


def downgrade() -> None:
    for table in ("run_jobs", "run_events", "runs", "messages"):
        op.drop_table(table)
    op.drop_constraint("uq_chats_id_owner", "chats", type_="unique")
