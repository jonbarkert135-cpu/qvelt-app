.PHONY: setup lint typecheck test test-postgres dev down check-skills link-skills

setup:
	npm install
	cd apps/api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

lint:
	cd apps/api && .venv/bin/ruff check .
	npm run lint

typecheck:
	npm run typecheck

test:
	npm test
	cd apps/api && .venv/bin/pytest -q

test-postgres:
	@: "$${QVELT_TEST_ADMIN_URL:?Set QVELT_TEST_ADMIN_URL for disposable PostgreSQL tests}"
	cd apps/api && .venv/bin/pytest -q -m integration

dev:
	docker compose up -d postgres redis

down:
	docker compose down

check-skills:
	python3 scripts/check_skills.py

# Expose the canonical .agents/skills to tools that look elsewhere (Linux/macOS; on Windows copy the folder instead).
link-skills:
	mkdir -p .claude .github
	ln -sfn ../.agents/skills .claude/skills
	ln -sfn ../.agents/skills .github/skills
