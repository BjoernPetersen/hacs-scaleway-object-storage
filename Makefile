.PHONY: metadata
metadata:
	uv run bin/update_manifests.py

.PHONY: lint
lint: metadata
	uv run ruff format
	uv run ruff check --fix --show-fixes
	uv run mypy .

.PHONY: test
test:
	uv run pytest
