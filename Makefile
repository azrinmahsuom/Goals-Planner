.PHONY: all fetch refresh verify upstream app test lint

all:          ## Rebuild everything from raw data, then test
	uv run python -m analysis.pipeline all
	uv run pytest

fetch:        ## Download any missing raw files
	uv run python -m analysis.pipeline fetch

refresh:      ## Re-download every source and accept updates into data/MANIFEST.yaml
	uv run python -m analysis.pipeline refresh

verify:       ## Check raw files against data/MANIFEST.yaml and write the drift report
	uv run python -m analysis.pipeline verify

upstream:     ## Re-vendor the earlier projects' derived figures at their pinned commits
	uv run python -m analysis.pipeline upstream

app:          ## Regenerate app/params.js from the committed outputs
	uv run python -m analysis.pipeline app

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
