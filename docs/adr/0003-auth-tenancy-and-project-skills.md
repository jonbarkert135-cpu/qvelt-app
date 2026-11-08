# ADR-0003: Minimal account and tenant boundary

Status: accepted

## Context

Phase 1.0 needs accounts before chat data. The current API has only a health
endpoint. The owner authorized autonomous implementation and creation of the
missing project skills, then supplied `ponytail` as the primary coding skill.

## Decision

- Use the existing FastAPI API and the planned PostgreSQL + SQLAlchemy/asyncpg
  stack. Alembic applies explicit versioned migrations; startup never mutates schema.
- Accounts use normalized ASCII usernames, Argon2id passwords and an owner ID equal
  to the account ID. Training consent defaults to false and cannot be set during
  registration. No training export or inference provider is introduced.
- Sessions are opaque random 32-byte secrets supplied in an Authorization Bearer
  header. Only SHA-256 digests are stored. Each session lasts 24 hours and can be
  revoked independently. This API skeleton does not create browser cookies or
  prescribe localStorage. The later web BFF must keep bearer tokens server-side
  and implement secure browser sessions and CSRF defenses.
- All domain reads include owner filters. Chats additionally have forced PostgreSQL
  RLS with both USING and WITH CHECK. The owner context is transaction-local to
  prevent connection-pool identity leaks. The API refuses superuser/BYPASSRLS roles.
- Users and sessions are trusted authentication tables: narrowly scoped username,
  credential-digest and verified-owner lookups bootstrap identity before a tenant
  context exists. They have owner columns and FK/check constraints, but **do not
  have RLS**. Database credentials therefore remain inside the trusted API boundary;
  never share them with the model, sandbox or browser. A separate authentication
  database role can be introduced if the service is split. This is not a claim
  that all database tables are protected against arbitrary SQL from the API role.
- Use original local baseline skills, with the owner's supplied MIT-labelled
  `ponytail` text as the main coding skill. Its frontmatter description is unfolded
  for the existing validator; instructions remain unchanged. The mistakenly
  supplied Playwright skill is excluded. No upstream skill was fetched or executed.

## Alternatives and consequences

JWT would add key rotation and revocation complexity without a current benefit.
In-memory accounts or SQLite tests would not establish PostgreSQL tenant isolation.
Security-definer login functions are deferred: no untrusted SQL is exposed, and
authentication currently lives in one small trusted API.

This is a development skeleton, not an Internet-ready identity service. Before
public access add distributed login/registration throttling, verified-email account
recovery, a browser BFF, TLS termination, secret management and retention/cleanup
of expired sessions. Argon2 work runs off the event loop but still needs concurrency
and request-size limits at the gateway. A small role-scoped chat list/get/create
surface exists only to demonstrate tenancy; streaming remains Phase 1.3.
