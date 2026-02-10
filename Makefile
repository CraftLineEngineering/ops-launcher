.PHONY: install dev test lint format check clean

# Install in editable mode
install:
	pip install -e .

# Install with dev dependencies
dev:
	pip install -e ".[dev]"

# Run tests
test:
	pytest -v --tb=short

# Run tests with coverage
cov:
	pytest --cov=ops_launcher --cov-report=term-missing -v

# Lint
lint:
	ruff check ops_launcher/ tests/
	mypy ops_launcher/

# Format
format:
	ruff format ops_launcher/ tests/
	ruff check --fix ops_launcher/ tests/

# Run all checks (lint + test)
check: lint test

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
