.PHONY: setup dev dev-api dev-web check format format-check lint typecheck test test-web build hooks pre-commit

setup:
	uv sync
	npm install --prefix web
	uv run pre-commit install

dev:
	@set -eu; \
	uv run read-along serve & \
	api_pid=$$!; \
	trap 'kill $$api_pid 2>/dev/null || true' INT TERM EXIT; \
	npm run dev --prefix web

dev-api:
	uv run read-along serve

dev-web:
	npm run dev --prefix web

check: lint format-check typecheck test test-web build

format:
	uv run ruff check --fix .
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run pyrefly check

test:
	uv run pytest

test-web:
	npm run test --prefix web

build:
	npm run build --prefix web

hooks:
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files
