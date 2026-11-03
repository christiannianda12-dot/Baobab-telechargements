.PHONY: install backend-install frontend-install migrate api web test lint backup

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
