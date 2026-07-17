.PHONY: help dev seed test eval ingest backend frontend install

help:
	@echo "Nexus BI — targets:"
	@echo "  make install   install backend + frontend deps"
	@echo "  make seed      seed the SQLite demo from the real Olist CSVs"
	@echo "  make backend   run FastAPI (http://localhost:8000)"
	@echo "  make frontend  run Next.js  (http://localhost:3000)"
	@echo "  make dev       seed + run backend (frontend in a second shell)"
	@echo "  make test      run the backend test suite"
	@echo "  make eval      run all eval suites -> backend/evals/*.json"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

seed:
	cd backend && python -m app.db.seed_demo

ingest: seed  # semantic catalog is built on demand from the seeded schema

backend:
	cd backend && uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

dev: seed backend

test:
	cd backend && python -m pytest

eval:
	cd backend && python -m evals.run_evals
