# QVELT API

## Install and test

From the repository root, `make setup` installs the dependencies. `make test
typecheck lint check-skills` runs the normal checks. Integration tests are
explicitly skipped unless `QVELT_TEST_ADMIN_URL` is set.

For real PostgreSQL and streaming validation start the required services:

```sh
docker compose up -d postgres redis
export QVELT_TEST_ADMIN_URL='postgresql+asyncpg://qvelt:qvelt@127.0.0.1:5432/postgres'
export QVELT_TEST_REDIS_URL='redis://127.0.0.1:6379/0'
make test-postgres
```

The URL above uses the repository's **local development** credentials, not a
production account. The test admin must be able to create/drop databases and
roles. Tests create a uniquely named disposable database and a NOLOGIN runtime
role without RLS bypass, run migrations, exercise the API and RLS, and remove
only that test database/role on teardown. The worker-process test temporarily gives
that role a generated test-only LOGIN password without logging or saving its value.
Redis tests delete only their random test-prefix keys, never FLUSHDB. Streaming
tests additionally skip if `QVELT_TEST_REDIS_URL` is absent. Never use production.

## Migrate and run

Use separate migrator and runtime roles. Supply connection URLs through the
environment; never commit real connection credentials.

```sh
cd apps/api
# QVELT_DATABASE_URL: migrator URL, with schema DDL permission
.venv/bin/alembic upgrade head
```

In the target database, an administrator provisions the application role:

```sql
CREATE ROLE qvelt_api LOGIN NOSUPERUSER NOBYPASSRLS;
-- Set a strong password securely via psql's \password qvelt_api or a secret manager.
GRANT CONNECT ON DATABASE qvelt TO qvelt_api;
GRANT USAGE ON SCHEMA public TO qvelt_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, chats TO qvelt_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages, runs, run_events, run_jobs TO qvelt_api;
```

Then set `QVELT_DATABASE_URL` to the runtime role's URL and start:

```sh
.venv/bin/uvicorn qvelt_api.main:app --host 127.0.0.1 --port 8000
```

The Compose `qvelt` database owner is a superuser: the API intentionally refuses
to start with that role. Schema migrations are not run on application startup.
Without a URL, `/healthz` still serves liveness; database-backed routes return 503.
`/healthz` is not a database readiness probe.

## API boundary

| Method and path | Behavior |
| --- | --- |
| POST /auth/register | `{username, password}` → public account, 201 |
| POST /auth/login | Same body → `{access_token, token_type, expires_in}` |
| GET /auth/me | Current account from verified bearer credentials |
| POST /auth/logout | Revoke only the presented session, 204 |
| POST /chats | `{title}` → a chat owned by the authenticated account |
| GET /chats?limit=50 | Only the caller's chats; limit 1–100 |
| GET /chats/{id} | Owned chat, or 404 for missing/foreign chat |

Usernames normalize case/outer whitespace and accept 3–64 ASCII letters, digits,
underscores, dots and hyphens (starting with a letter or digit). Passwords accept
12–128 characters, are not trimmed, and use salted Argon2id hashes. Unknown JSON
fields are rejected. Validation errors omit raw input. Private responses use
`Cache-Control: no-store`; there is no permissive CORS configuration.

Send `Authorization: Bearer <access_token>` on protected routes. Session tokens
are secrets: never put them in URLs, logs, committed files or browser localStorage.
Sessions expire at the exact stored UTC expiry boundary and are independently
revocable. The API issues no cookies. Browser BFF integration belongs to the web
milestone, not to this API-only account skeleton.

See ADR-0003 for RLS coverage and the remaining production security prerequisites.

## Streaming and worker (Phase 1.3)

Apply migration `0002` and the new table grants above. Supply the same runtime
`QVELT_DATABASE_URL`, `QVELT_REDIS_URL` and optional `QVELT_REDIS_PREFIX` to the API
and worker. For local Redis use `redis://127.0.0.1:6379/0`. Secrets in production
URLs belong in secure environment configuration, not command-line arguments.

In a **second process**, from `apps/api`:

```sh
.venv/bin/python -m qvelt_api.worker
# Operational single-job mode (also exercised by integration tests):
.venv/bin/python -m qvelt_api.worker --once
```

The worker is not started by the API. Without a worker, accepted jobs remain queued
and SSE subscribers receive heartbeats. Stopping an API connection/process does not
cancel a job. Optional worker settings are `QVELT_RUN_TIMEOUT_SECONDS` (60 seconds),
`QVELT_MAX_OUTPUT_CHARS` (200000 Unicode characters) and `QVELT_HISTORY_MESSAGES`
(100 recent messages). They are service guards; provider capabilities/token budgets
belong to the next milestone. `QVELT_REDIS_PREFIX` defaults to `qvelt:` and must
match in both processes. MinIO is not needed for this text-only milestone.

| Method and path | Behavior |
| --- | --- |
| POST /chats/{id}/messages | `{text}` plus required `Idempotency-Key` → SSE, 200 |
| GET /chats/{id}/messages?after=0&limit=50 | Ordered persisted parts; positional pagination |
| GET /runs/{id} | Owned status, IDs, applied cursor and usage metadata |
| GET /runs/{id}/events | SSE replay strictly after `Last-Event-ID`, default 0 |
| POST /runs/{id}/cancel | Persist cancellation request, 202; poll run/stream for completion |

All routes require bearer authentication. Foreign resources return 404. Reusing
an owner/chat/key with the same text replays the same run; changing text returns
409. Keys accept 1–128 ASCII letters/digits and `._:-`. A different key cannot start
another active run in the same chat (409). Use cursor 0 when creating new work;
a nonzero initial cursor is rejected without creating messages or a job.

Responses contain `X-Run-ID`, `X-Message-ID`, `X-Accel-Buffering: no` and
`Cache-Control: no-store`. The SSE content type is `text/event-stream`; each frame
has matching integer `id`, event type and contract-validated JSON `data`. Heartbeat
comments every 15 seconds do not advance the cursor. A future cursor is 409;
resuming an already consumed terminal cursor returns 204 to stop reconnects.

Raw message bodies are limited to 1 MiB before JSON decoding; text accepts up to
100000 characters, rejects blank text, NUL and invalid Unicode, and preserves
whitespace. Unknown fields are rejected. User and assistant records default to
`training_opt_in=false`. Text/parts/last sequence and each journal event commit
together. Redis holds mirrored events with a 24-hour TTL and wakes subscribers;
the durable PostgreSQL journal provides recovery when Redis is absent or expired.
No DB connection is retained while waiting for provider output or between SSE
batches. Subscribers recheck session expiry/revocation between batches.

FakeProvider returns `Echo (FakeProvider): <text>`. Its whitespace-token counts are
fake test data, not real model usage or billing. `usage.reported=false` means counters
were not received; zero placeholders must not be displayed as measured zero. Real
models, authenticated browser sessions and chat rendering are not connected yet.

On provider/limit failure the stream ends with a sanitized error and saved prefix.
After worker interruption a new worker marks the run `worker_interrupted`, preserving
its prefix; it never silently generates that text again. Repeat the same key to
inspect/replay that failure, or choose a new key for an explicit new attempt.
Cancellation interrupts a waiting provider, subject to storage/finalization latency;
logout revokes the subscriber, not the independently queued job. See ADR-0007.
