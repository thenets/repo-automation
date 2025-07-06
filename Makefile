.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Create a virtual environment
	python3 -m venv venv
	./venv/bin/pip install -U pip setuptools
	./venv/bin/pip install -r requirements.txt

.PHONY: lint
lint: lint-yaml lint-actions ## Run all linters
	@echo "All workflows are valid!"

.PHONY: lint-yaml
lint-yaml: venv ## Lint YAML files
	@echo "Linting YAML files..."
	./venv/bin/yamllint .github/workflows/*.yml
	@echo "YAML linting completed successfully!"
	
.PHONY: lint-actions
lint-actions: ## Lint GitHub Actions workflows
	@echo "Linting GitHub Actions workflows..."
	@if command -v podman > /dev/null 2>&1; then \
		echo "Using podman image..."; \
		podman run --rm -v $(PWD):/repo:z -w /repo docker.io/rhysd/actionlint:latest -color .github/workflows/*.yml; \
	else \
		echo "podman not found, raising error..."; \
		exit 1; \
	fi
	@echo "GitHub Actions workflow linting completed successfully!"

.PHONY: format
format: venv ## Format code with ruff
	./venv/bin/ruff format .

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf .ruff_cache/
	rm -rf venv/
	rm -f actionlint
