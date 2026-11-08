.PHONY: setup lint typecheck test dev down check-skills link-skills

setup:
	npm install
	cd apps/api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

lint:
	cd apps/api && .venv/bin/ruff check .

typecheck:
	npm run typecheck

test:
	npm test
	cd apps/api && .venv/bin/pytest -q

dev:
	docker compose up -d

down:
	docker compose down

check-skills:
	python3 scripts/check_skills.py

# Expose the canonical .agents/skills to tools that look elsewhere (Linux/macOS; on Windows copy the folder instead).
link-skills:
	mkdir -p .claude .github
	ln -sfn ../.agents/skills .claude/skills
	ln -sfn ../.agents/skills .github/skills
