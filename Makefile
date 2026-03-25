.PHONY: install dev run test lint clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

run:
	python -m opsportal --reload

test:
	python -m pytest tests/ -v --tb=short

lint:
	python -m ruff check src/ tests/
	python -m ruff format --check src/ tests/

format:
	python -m ruff format src/ tests/
	python -m ruff check --fix src/ tests/

clean:
	rm -rf artifacts/ work/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install all tools in editable mode (for local development)
install-tools:
	pip install -e ../ReleasePilot
	pip install -e ../ReleaseBoard
	pip install -e ../LocaleSync
	pip install -e ../FlowBoard

# Full local dev setup
setup: dev install-tools
	@echo "OpsPortal + all tools installed. Run: make run"
