.PHONY: help setup dev test lint clean docker smoke doctor mustang-validate

PYTHON ?= python3
VENV   := .venv

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup: ## Create venv with standard install
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip setuptools wheel --quiet
	$(VENV)/bin/pip install . --quiet
	@echo "\n  Installed trustrender into $(VENV)"
	@echo "  Activate: source $(VENV)/bin/activate"

dev: ## Create venv with editable install + dev deps
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip setuptools wheel --quiet
	$(VENV)/bin/pip install -e ".[dev]" --quiet
	@# Some Python builds skip __editable__*.pth files — add a fallback
	@pth=$$(ls $(VENV)/lib/python*/site-packages/__editable__*.pth 2>/dev/null | head -1); \
		if [ -n "$$pth" ]; then \
			dir=$$(dirname "$$pth"); \
			cp "$$pth" "$$dir/trustrender-editable.pth"; \
		fi
	@echo "\n  Installed trustrender (editable + dev) into $(VENV)"
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

build-playground: ## Build playground UI and copy to package
	cd website && npm run build
	rm -rf src/trustrender/playground
	cp -r website/dist src/trustrender/playground

docker: ## Build Docker image
	docker build -t trustrender .

smoke: ## Quick render + server health smoke test
	trustrender doctor --smoke

doctor: ## Run environment diagnostics
	trustrender doctor

MUSTANG_VERSION := 2.15.0
MUSTANG_JAR     := .cache/mustang-cli-$(MUSTANG_VERSION).jar

mustang-validate: ## Validate e-invoice against Mustang reference validator (requires Java)
	@which java > /dev/null 2>&1 || { echo "Error: Java not found — install JDK 11+"; exit 1; }
	@mkdir -p .cache
	@test -f $(MUSTANG_JAR) || { echo "Downloading Mustang CLI $(MUSTANG_VERSION)..."; \
		curl -fSL -o $(MUSTANG_JAR) \
		"https://repo1.maven.org/maven2/org/mustangproject/Mustang-CLI/$(MUSTANG_VERSION)/Mustang-CLI-$(MUSTANG_VERSION).jar"; }
	@echo "Rendering e-invoice..."
	@python -c "from trustrender import render; import json; \
		d = json.load(open('examples/einvoice_data.json')); \
		pdf = render('examples/einvoice.j2.typ', d, zugferd='en16931'); \
		open('.cache/einvoice_test.pdf','wb').write(pdf)"
	@echo "Validating with Mustang..."
	java -jar $(MUSTANG_JAR) --action validate --source .cache/einvoice_test.pdf
