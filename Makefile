.PHONY: setup dev dev-api dev-web check check-browser format format-check format-check-python format-check-web lint lint-python lint-web typecheck test test-python test-web test-web-smoke build build-web hooks pre-commit

setup:
	uv sync
	npm install --prefix web
	uv run pre-commit install

dev:
	@set -eu; \
	uv run read-along serve --reload & \
	api_pid=$$!; \
	trap 'kill $$api_pid 2>/dev/null || true' INT TERM EXIT; \
	npm run dev --prefix web

dev-api:
	uv run read-along serve --reload

dev-web:
	npm run dev --prefix web

check: lint format-check typecheck test test-web build

check-browser: test-web-smoke

format:
	uv run ruff check --fix .
	uv run ruff format .
	npm run format --prefix web

format-check: format-check-python format-check-web

format-check-python:
	uv run ruff format --check .

format-check-web:
	npm run format:check --prefix web

lint: lint-python lint-web

lint-python:
	uv run ruff check .

lint-web:
	npm run lint --prefix web

typecheck:
	uv run pyrefly check

test: test-python

test-python:
	uv run pytest

test-web:
	npm run test --prefix web

test-web-smoke:
	@set -eu; \
	tmp_home=$$(mktemp -d); \
	READ_ALONG_HOME=$$tmp_home uv run read-along serve --host 127.0.0.1 --port 8765 & \
	api_pid=$$!; \
	npm run dev --prefix web -- --host 127.0.0.1 > /tmp/read-along-vite-smoke.log 2>&1 & \
	web_pid=$$!; \
	cleanup() { kill $$api_pid $$web_pid 2>/dev/null || true; rm -rf "$$tmp_home"; }; \
	trap cleanup INT TERM EXIT; \
	for i in $$(seq 1 60); do \
		if curl -fsS http://127.0.0.1:8765/api/health >/dev/null 2>&1 && curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then \
			break; \
		fi; \
		if [ $$i -eq 60 ]; then \
			echo "Read Along smoke servers did not become ready"; \
			cat /tmp/read-along-vite-smoke.log 2>/dev/null || true; \
			exit 1; \
		fi; \
		sleep 1; \
	done; \
	READ_ALONG_WEB_URL=http://127.0.0.1:5173 npm run test:smoke --prefix web

build: build-web

build-web:
	npm run build --prefix web

hooks:
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files
