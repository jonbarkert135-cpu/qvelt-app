# QVELT App

Web product for QVELT: chat, files and ZIP projects, sandboxed code execution, artifacts and a coding agent.
The language model lives in a separate repository (QveltAI). This repo only talks to models through the
`ModelProvider` interface (see `docs/adr/0002-model-agnostic-provider.md`).

## Status
Implemented: event contract + reducer with tests (`packages/events`), FastAPI accounts,
revocable sessions and tenant-scoped chats with PostgreSQL RLS (`apps/api`), CI and local
services (`docker-compose.yml`). The web UI and streaming are still planned in
`docs/PHASE1_PLAN.md` and the blueprint in `docs/blueprint/`.

## Quick start
```
make setup      # npm install + Python venv for apps/api
make test       # runs TypeScript and Python tests
make dev        # starts Postgres(pgvector), Redis, MinIO via Docker
```
Requirements: Node 22+, Python 3.12+, Docker (for `make dev`).

For account API startup, migrations, database roles and PostgreSQL integration tests,
see [apps/api/README.md](apps/api/README.md). The Compose database owner is not an API
runtime role; the API rejects roles that bypass RLS. Authentication is a development
skeleton; see ADR-0003 before exposing it publicly.

## Layout
```
apps/api            FastAPI service (Python)
apps/web            Next.js app (created in PR 1.1)
packages/events     shared stream-event types + reducer (TypeScript)
docs/blueprint      architecture blueprint (put the exported file here)
docs/adr            architecture decision records
docs/prompts        prompts used to start and steer coding agents
docs/skills         third-party skills: candidates and vetting policy
.agents/skills      project skills agents must use (see AGENTS.md)
scripts             helper scripts (skills validator)
```

## Working with AI agents
Read `AGENTS.md` first. Agents work one PR-sized step at a time and stop for human review.
