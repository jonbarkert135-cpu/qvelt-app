# QVELT App

Web product for QVELT: chat, files and ZIP projects, sandboxed code execution, artifacts and a coding agent.
The language model lives in a separate repository (QveltAI). This repo only talks to models through the
`ModelProvider` interface (see `docs/adr/0002-model-agnostic-provider.md`).

## Status
Starter scaffold. Implemented: event contract + reducer with tests (`packages/events`), FastAPI health
endpoint (`apps/api`), CI, local services (`docker-compose.yml`). Everything else is planned in
`docs/PHASE1_PLAN.md` and the blueprint in `docs/blueprint/`.

## Quick start
```
make setup      # npm install + Python venv for apps/api
make test       # runs TypeScript and Python tests
make dev        # starts Postgres(pgvector), Redis, MinIO via Docker
```
Requirements: Node 22+, Python 3.12+, Docker (for `make dev`).

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
