.PHONY: setup dev dev-stop dev-api dev-web check check-browser format format-check format-check-python format-check-web lint lint-python lint-web typecheck test test-python test-web test-web-smoke build build-web hooks pre-commit

setup:
	uv sync
	npm install --prefix web
	uv run pre-commit install

dev:
	@set -u; \
	uv run read-along serve --reload & \
	api_pid=$$!; \
	npm run dev --prefix web & \
	web_pid=$$!; \
	cleanup() { \
		trap - INT TERM EXIT; \
		kill $$api_pid $$web_pid 2>/dev/null || true; \
		wait $$api_pid 2>/dev/null || true; \
		wait $$web_pid 2>/dev/null || true; \
	}; \
	trap 'cleanup; exit 130' INT; \
	trap 'cleanup; exit 143' TERM; \
	trap cleanup EXIT; \
	while :; do \
		if ! kill -0 $$api_pid 2>/dev/null; then exited_pid=$$api_pid; break; fi; \
		if ! kill -0 $$web_pid 2>/dev/null; then exited_pid=$$web_pid; break; fi; \
		sleep 1; \
	done; \
	status=0; \
	wait $$exited_pid || status=$$?; \
	cleanup; \
	exit $$status

dev-stop:
	@project_dir=$$(pwd -P); stopped=0; \
	candidates=$$(pgrep -u "$$(id -u)" -f '(^|/)make dev$$'); status=$$?; \
	if [ "$$status" -gt 1 ]; then echo "无法读取进程列表。" >&2; exit "$$status"; fi; \
	for pid in $$candidates; do \
		process_command=$$(ps -ww -p "$$pid" -o command= 2>/dev/null); \
		process_name=$${process_command%% *}; \
		process_name=$${process_name##*/}; \
		process_args=$${process_command#* }; \
		process_dir=$$(lsof -a -p "$$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'); \
		if [ "$$process_name" = make ] && [ "$$process_args" = dev ] && [ "$$process_dir" = "$$project_dir" ]; then \
			kill -TERM "$$pid" || exit 1; \
			stopped=1; \
		fi; \
	done; \
	if [ "$$stopped" -eq 1 ]; then \
		echo "已向 Read Along 开发服务发送停止信号。"; \
	else \
		echo "没有运行中的 Read Along 开发服务。"; \
	fi

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
	api_log=$$tmp_home/api.log; \
	web_log=$$tmp_home/web.log; \
	READ_ALONG_HOME="$$tmp_home" uv run uvicorn read_along.api:app --host 127.0.0.1 --port 8765 >"$$api_log" 2>&1 & \
	api_pid=$$!; \
	npm run dev --prefix web -- --host 127.0.0.1 >"$$web_log" 2>&1 & \
	web_pid=$$!; \
	cleanup() { \
		trap - INT TERM EXIT; \
		kill $$api_pid $$web_pid 2>/dev/null || true; \
		wait $$api_pid 2>/dev/null || true; \
		wait $$web_pid 2>/dev/null || true; \
		rm -rf "$$tmp_home"; \
	}; \
	trap 'cleanup; exit 130' INT; \
	trap 'cleanup; exit 143' TERM; \
	trap cleanup EXIT; \
	for i in $$(seq 1 60); do \
		if ! kill -0 $$api_pid 2>/dev/null; then \
			echo "Read Along smoke API stopped before becoming ready"; \
			cat "$$api_log" 2>/dev/null || true; \
			exit 1; \
		fi; \
		if ! kill -0 $$web_pid 2>/dev/null; then \
			echo "Read Along smoke web server stopped before becoming ready"; \
			cat "$$web_log" 2>/dev/null || true; \
			exit 1; \
		fi; \
		if curl -fsS http://127.0.0.1:8765/api/health >/dev/null 2>&1 && curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then \
			break; \
		fi; \
		if [ $$i -eq 60 ]; then \
			echo "Read Along smoke servers did not become ready"; \
			cat "$$api_log" "$$web_log" 2>/dev/null || true; \
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
