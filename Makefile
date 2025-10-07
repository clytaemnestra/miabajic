.PHONY: help install build clean dev serve open lint format check all

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv sync

build: ## Generate the static site
	uv run python generate.py

clean: ## Clean the output directory
	rm -rf output/*

dev: build open ## Build and open the site for development

serve: ## Start a simple HTTP server for local preview
	@echo "Starting local server on http://localhost:8000"
	@cd output && python -m http.server 8000

open: ## Open the generated site in browser
	@if [ -f output/index.html ]; then \
		open output/index.html; \
	else \
		echo "Site not built yet. Run 'make build' first."; \
	fi

lint: ## Check YAML syntax
	@echo "Checking YAML files..."
	@for file in data/*.yaml; do \
		echo "Checking $$file..."; \
		python -c "import yaml; yaml.safe_load(open('$$file'))" || exit 1; \
	done
	@echo "✅ All YAML files are valid"

format: ## Format Python files (if you have black installed)
	@if command -v black >/dev/null 2>&1; then \
		black generate.py; \
	else \
		echo "black not installed, skipping formatting"; \
	fi

check: lint ## Run all checks
	@echo "✅ All checks passed"

watch: ## Watch for changes and rebuild automatically (requires entr)
	@if command -v entr >/dev/null 2>&1; then \
		echo "Watching for changes... Press Ctrl+C to stop"; \
		find data templates generate.py | entr -r make build; \
	else \
		echo "entr not installed. Install with: brew install entr"; \
	fi

all: clean install build open ## Full build pipeline

# Quick commands
quick: build open ## Quick build and open (alias for dev)

# Show current build info
info: ## Show build information
	@echo "Project: Podcast Static Site Generator"
	@echo "Build tool: Python + Jinja2"
	@echo "Dependencies: $(shell grep -c "=" pyproject.toml) packages"
	@if [ -f output/index.html ]; then \
		echo "Last build: $(shell stat -f "%Sm" output/index.html)"; \
	else \
		echo "Last build: Not built yet"; \
	fi