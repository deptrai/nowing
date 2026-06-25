.PHONY: test test-unit test-integration test-api test-cov test-watch

## Run all tests
test:
	uv run pytest

## Run only unit tests (fast, no DB)
test-unit:
	uv run pytest -m unit

## Run only integration tests (requires DB)
test-integration:
	uv run pytest -m integration

## Run only system tests
test-system:
	uv run pytest tests/system/

## Run only API tests
test-api:
	uv run pytest tests/api/

## Run with coverage report
test-cov:
	uv run pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov

## Run in watch mode (requires pytest-watch)
test-watch:
	uv run ptw -- -m unit

## Run fast (unit only, parallel, no coverage)
test-fast:
	uv run pytest -m unit -x --no-header -q

## Lint
lint:
	uv run ruff check .
	uv run ruff format --check .

## Format
fmt:
	uv run ruff check --fix .
	uv run ruff format .
