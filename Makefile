.PHONY: install install-dev test lint fix setup migrate serve worker clean

# ──────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────

setup: install-dev  ## Bootstrap the project (install deps + copy .env)
	@test -f .env || cp .env.example .env && echo "Created .env from .env.example"

install:  ## Install production dependencies
	pip install -e .

install-dev:  ## Install production + dev dependencies
	pip install -e ".[dev]"

# ──────────────────────────────────────────────────────────────
# Quality
# ──────────────────────────────────────────────────────────────

test:  ## Run test suite
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov=app --cov-report=term-missing

lint:  ## Run linter (ruff check + ruff format --check)
	ruff check app/ tests/
	ruff format --check app/ tests/

fix:  ## Auto-fix lint issues and format code
	ruff check --fix app/ tests/
	ruff format app/ tests/

# ──────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────

migrate:  ## Run Alembic migrations to head
	alembic upgrade head

migration:  ## Create a new auto-generated migration (usage: make migration m="description")
	alembic revision --autogenerate -m "$(m)"

# ──────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────

infra:  ## Start PostGIS + Redis via Docker Compose
	docker compose up -d postgres redis

serve:  ## Start API with hot-reload
	uvicorn app.main:app --reload

worker:  ## Start arq worker
	python -m arq app.worker.tasks.WorkerSettings

# ──────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/
