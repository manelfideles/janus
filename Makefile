setup:
	uv sync

test:
	uv run pytest -q --no-header

typecheck:
	uv run ty check packages/core

lint:
	uv run ruff check . && uv run ruff format --check .

lint_fix:
	uv run ruff check . --fix && uv run ruff format .
