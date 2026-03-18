.PHONY: metadata
metadata:
	uv run bin/update_manifests.py

.PHONY: lint
lint: metadata
	uv run ruff format
	uv run ruff check --fix --show-fixes
	uv run mypy custom_components/ tests/

.PHONY: test
test:
	uv run pytest
