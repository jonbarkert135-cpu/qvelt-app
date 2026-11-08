# ADR-0007: Durable generation jobs and resumable SSE

Status: accepted

## Problem and behavior

Phase 1.3 must survive a closed HTTP connection without losing generation or
creating a second run when a message POST is retried. Sending is now a transaction
that creates the user/assistant messages, a run and a durable service job. A separate
worker consumes that job, validates emitted events against the shared contract and
persists message parts and a contiguous event journal before Redis notification.
SSE clients resume strictly after Last-Event-ID. Generation never runs inside the
request handler or a FastAPI background task.

## Decisions

- PostgreSQL owns message ordering, idempotency and the authoritative journal.
  A chat lock allocates consecutive message positions; a partial unique index
  allows one active run per chat. Idempotency is scoped to owner/chat/key and binds
  the exact input hash. A changed body returns 409. An invalid initial resume cursor
  is rejected before enqueueing work. Repeated identical requests reuse both IDs
  and the same event history, including failed runs.
- Use a transactional `run_jobs` outbox instead of attempting an atomic PostgreSQL
  commit plus Redis enqueue. Workers scan pending jobs and use a session advisory
  lock to prevent duplicate consumers; every claimed UUID/owner is rechecked in
  PostgreSQL. A worker processes one run at a time; more processes add concurrency.
  This deliberately avoids a generic queue framework and ambiguous cross-system ack.
- Every committed event is mirrored into a Redis Stream with its explicit seq-0 ID
  and a 24-hour TTL. SSE readers use XREAD for wakeups, and always read authorized
  event batches from PostgreSQL. Redis loss/expiry therefore falls back to journal
  polling, rather than dropping an acknowledged event. Redis is not the sole durable
  store. This is an intentional refinement of the reference design's transient
  Redis source: transactional recovery is more useful here than a second outbox.
- Messages, runs and events have owner columns and forced RLS. Composite foreign
  keys prevent cross-owner/chat associations. The small service outbox, like the
  existing auth tables, has owner metadata but no RLS: it is an explicitly trusted
  cross-tenant dispatch index. Only the trusted API/worker database role may access
  it; there is no public job endpoint. Model text never supplies dispatch authority.
  Both API and worker refuse superuser/BYPASSRLS roles.
- The provider boundary is `ModelProvider`. FakeProvider is explicitly an echo,
  not a QVELT model or a real inference benchmark. Its usage is deterministic
  whitespace-token test data and must never be billed. Add optional `usage.reported`
  to the shared schema: false denotes unavailable counters (zero placeholders),
  not measured zero usage. The worker always supplies this flag; absent legacy
  values must not be treated as billing evidence.
- Cancellation is a durable flag and is polled while waiting for provider output,
  so a stalled iterator can be closed. Session revocation closes its subscriber
  at a subsequent authorization check without cancelling the independently
  authorized job. A terminal stream already fully consumed returns 204; a cursor
  ahead of durable history returns 409. No synthetic gap repair or text replay.
- A crashed worker does not restart inference over an emitted prefix. Recovery
  preserves the journal/parts and emits `worker_interrupted`. Provider failure,
  wall-clock timeout and output budget produce terminal sanitized errors with any
  earlier output retained. Retrying generation requires a new idempotency key.
- Bound raw message JSON at 1 MiB before decoding, text at 100,000 Unicode characters,
  output with a configurable character budget and recent history with a message
  limit. These are service guards, not model token/context capabilities. Reject
  NUL/unpaired surrogates before PostgreSQL JSONB writes. Never expose provider
  exception messages, credentials or raw validation inputs in public error frames.
- Use pure ASGI response-header middleware and shield short tenant DB transactions
  from ASGI cancellation. No transaction is held across yield, XREAD or provider
  work. The real disconnect test exposed a closed-connection pool race in the old
  middleware/cleanup path; shielding cleanup alone did not fix interrupted queries.

## Limits and evidence

This stage is the backend protocol. The browser shell still has no authenticated
BFF or streaming message UI; those integrations must follow ADR-0003 and the UI
milestones. No vendor SDK, real-model fallback, tool execution or training export
is introduced. Distributed admission/rate controls and retention remain later work.

Tests use real PostgreSQL without RLS bypass and namespaced Redis keys. They cover
duplicate/concurrent POSTs, foreign resource denial, replay, cancellation during a
stalled provider, worker crash/exclusive claims, Redis outage, resource limits,
invalid Unicode, revoked subscribers, a real TCP disconnect/reconnect, and the
separate worker CLI using a temporary private LOGIN role. No Redis FLUSH or shared
database teardown is used: only disposable test databases/roles and test-prefix
keys are removed. CI runs Redis alongside PostgreSQL.
