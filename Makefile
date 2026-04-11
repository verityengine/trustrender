.PHONY: help setup dev test lint clean docker smoke doctor

PYTHON ?= python3
VENV   := .venv

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup: ## Create venv with standard install
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip setuptools wheel --quiet
	$(VENV)/bin/pip install . --quiet
	@echo "\n  Installed formforge into $(VENV)"
	@echo "  Activate: source $(VENV)/bin/activate"

dev: ## Create venv with editable install + dev deps
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip setuptools wheel --quiet
	$(VENV)/bin/pip install -e ".[dev]" --quiet
	@echo "\n  Installed formforge (editable + dev) into $(VENV)"
	@echo "  Activate: source $(VENV)/bin/activate"

test: ## Run pytest
	python -m pytest tests/ -v

lint: ## Run ruff check + format check
	python -m ruff check src/ tests/
	python -m ruff format --check src/ tests/

clean: ## Remove build artifacts (not .venv)
	rm -rf build/ dist/
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true

docker: ## Build Docker image
	docker build -t formforge .

smoke: ## Quick render + server health smoke test
	formforge doctor --smoke

doctor: ## Run environment diagnostics
	formforge doctor
