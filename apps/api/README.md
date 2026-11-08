# QVELT API

## Install and test

From the repository root, `make setup` installs the dependencies. `make test
typecheck lint check-skills` runs the normal checks. Integration tests are
explicitly skipped unless `QVELT_TEST_ADMIN_URL` is set.

For real PostgreSQL validation start only the required service:

```sh
docker compose up -d postgres
export QVELT_TEST_ADMIN_URL='postgresql+asyncpg://qvelt:qvelt@127.0.0.1:5432/postgres'
make test-postgres
```

The URL above uses the repository's **local development** credentials, not a
production account. The test admin must be able to create/drop databases and
roles. Tests create a uniquely named disposable database and a NOLOGIN runtime
role without RLS bypass, run migrations, exercise the API and RLS, and remove
only that test database/role on teardown. Never point this at production.

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
