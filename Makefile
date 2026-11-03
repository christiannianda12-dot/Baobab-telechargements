.PHONY: audit docker-up test-pg install backend-install frontend-install migrate api web test lint backup

install: backend-install frontend-install

backend-install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

frontend-install:
	cd frontend && npm install

migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head

api:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && . .venv/bin/activate && python -m pytest
	cd frontend && npm run lint && npm run typecheck

lint:
	cd backend && . .venv/bin/activate && ruff check .

backup:
	cd backend && . .venv/bin/activate && python ../scripts/backup_db.py

# Tests sur PostgreSQL : TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/predix_test make test-pg
test-pg:
	cd backend && . .venv/bin/activate && pip install -q -r requirements-postgres.txt && python -m pytest

audit:
	cd backend && . .venv/bin/activate && pip install -q pip-audit && pip-audit -r requirements.txt
	cd frontend && npm audit --omit=dev --audit-level=high

docker-up:
	docker compose up --build
