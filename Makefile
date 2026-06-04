.PHONY: help install test test-unit test-int lint format check migrate run clean precommit precommit-install

PYTHON ?= python3
VENV ?= .venv
ACT := $(VENV)/bin/activate

help:
	@echo "InterviewFindr common commands:"
	@echo "  make install          - create venv and install deps + dev tools"
	@echo "  make test             - run all tests"
	@echo "  make test-unit        - run unit tests only"
	@echo "  make test-int         - run integration tests only"
	@echo "  make lint             - run ruff check"
	@echo "  make format           - run ruff format"
	@echo "  make check            - run lint + format-check + tests"
	@echo "  make migrate          - apply alembic migrations"
	@echo "  make run              - start uvicorn dev server"
	@echo "  make clean            - remove caches and test DB"
	@echo "  make precommit-install - install pre-commit git hook"
	@echo "  make precommit        - run pre-commit on all files"

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"
	$(VENV)/bin/pip install pre-commit

install: $(VENV)/bin/activate

test:
	$(VENV)/bin/pytest

test-unit:
	$(VENV)/bin/pytest tests/unit/

test-int:
	$(VENV)/bin/pytest tests/integration/

lint:
	$(VENV)/bin/ruff check .

format:
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

check: lint
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/pytest

migrate:
	$(VENV)/bin/alembic upgrade head

run:
	$(VENV)/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	rm -rf data/*.db
	find . -type d -name __pycache__ -exec rm -rf {} +

precommit-install:
	$(VENV)/bin/pre-commit install

precommit:
	$(VENV)/bin/pre-commit run --all-files
