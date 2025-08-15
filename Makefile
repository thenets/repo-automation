.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Create a virtual environment
	python3 -m venv venv
	./venv/bin/pip install -U pip setuptools
	./venv/bin/pip install -e ".[dev,test]"

.PHONY: lint
lint: lint-yaml lint-actions ## Run all linters
	@echo "All workflows are valid!"

.PHONY: lint-yaml
lint-yaml: venv ## Lint YAML files
	@echo "Linting YAML files..."
	@echo "Fixing trailing spaces and EOF newlines..."
	@for file in .github/workflows/*.yml; do \
		sed -i 's/[[:space:]]*$$//' "$$file"; \
		sed -i -e '$$a\' "$$file"; \
	done
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

.PHONY: test
test: venv ## Run tests (parallel, up to 10 threads) with coverage
	@echo "Running tests with coverage (parallel, up to 10 threads)..."
	./venv/bin/pytest -v -n 10 \
		--cov=. \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml
	@echo "Tests completed!"
	@echo "Coverage reports generated:"
	@echo "  - Terminal: coverage summary displayed above"
	@echo "  - HTML: htmlcov/index.html"
	@echo "  - XML: coverage.xml"

.PHONY: test-list
test-list: venv ## List all tests
	./venv/bin/pytest --collect-only

.PHONY: _gh_auth_check
_gh_auth_check: ## Check GitHub CLI authentication status
	@echo "Checking GitHub CLI authentication..."
	@if gh auth status >/dev/null 2>&1; then \
		echo "✅ GitHub CLI is authenticated"; \
	else \
		echo "❌ GitHub CLI is not authenticated"; \
		echo "Please authenticate with GitHub CLI:"; \
		echo "  gh auth login"; \
		echo ""; \
		echo "Then run 'make setup-token' again"; \
		exit 1; \
	fi

.PHONY: setup-token
setup-token: _gh_auth_check ## Generate GitHub token and create .env file for testing
	@echo "Setting up GitHub token for external repository testing..."
	@echo "This will guide you through creating a GitHub token for the specified repository."
	@echo ""
	@read -p "Enter GitHub organization/user: " GITHUB_ORG && \
	read -p "Enter repository name: " GITHUB_REPO && \
	echo "" && \
	echo "Validating repository access..." && \
	if gh repo view "$$GITHUB_ORG/$$GITHUB_REPO" >/dev/null 2>&1; then \
		echo "✅ Repository $$GITHUB_ORG/$$GITHUB_REPO is accessible"; \
	else \
		echo "❌ Repository $$GITHUB_ORG/$$GITHUB_REPO is not accessible or does not exist"; \
		echo "Please check the organization and repository names"; \
		exit 1; \
	fi && \
	echo "" && \
	echo "Please create a GitHub Personal Access Token with the following permissions:" && \
	echo "1. Go to: https://github.com/settings/personal-access-tokens/new" && \
	echo "2. Select 'Fine-grained personal access token'" && \
	echo "3. Choose 'Selected repositories' and select: $$GITHUB_ORG/$$GITHUB_REPO" && \
	echo "4. Grant the following repository permissions:" && \
	echo "   - Actions: Read and write (required for workflow files)" && \
	echo "   - Contents: Read and write (required for code and workflow files)" && \
	echo "   - Issues: Read and write (required for issue labeling)" && \
	echo "   - Pull requests: Read and write (required for PR labeling)" && \
	echo "   - Metadata: Read (required for repository access)" && \
	echo "   - Administration: Read (optional, for advanced repository management)" && \
	echo "5. Click 'Generate token' and copy the token" && \
	echo "" && \
	echo "⚠️  IMPORTANT: If you get 'workflow scope' errors later:" && \
	echo "   - Ensure 'Actions: Read and write' permission is granted" && \
	echo "   - Some repositories may require classic tokens instead of fine-grained" && \
	echo "   - For classic tokens, enable 'workflow' scope explicitly" && \
	echo "" && \
	read -p "Enter your GitHub token: " GITHUB_TOKEN && \
	echo "" && \
	echo "Testing token validity..." && \
	if echo "$$GITHUB_TOKEN" | gh auth login --with-token 2>/dev/null && gh repo view "$$GITHUB_ORG/$$GITHUB_REPO" >/dev/null 2>&1; then \
		echo "✅ Token is valid and has access to repository"; \
	else \
		echo "❌ Token validation failed"; \
		echo "Please ensure the token has correct permissions for $$GITHUB_ORG/$$GITHUB_REPO"; \
		exit 1; \
	fi && \
	echo "" && \
	echo "Creating .env file..." && \
	echo "TEST_GITHUB_ORG=\"$$GITHUB_ORG\"" > .env && \
	echo "TEST_GITHUB_REPO=\"$$GITHUB_REPO\"" >> .env && \
	echo "GITHUB_TOKEN=\"$$GITHUB_TOKEN\"" >> .env && \
	echo "" && \
	echo "✅ Setup complete! .env file created with:" && \
	echo "   Organization: $$GITHUB_ORG" && \
	echo "   Repository: $$GITHUB_REPO" && \
	echo "   Token: [hidden for security]" && \
	echo "" && \
	echo "Running validation tests..." && \
	$(MAKE) setup-token-test

.PHONY: setup-token-test
setup-token-test: venv ## Test and validate GitHub token setup
	@echo "" 
	@echo "=== Testing GitHub Token Setup ==="
	@echo "" 
	@echo "1. Validating configuration loading..."
	@python test/setup_org_testing.py --validate
	@echo "" 
	@echo "2. Running basic configuration tests..."
	@python -c "import sys; sys.path.append('test'); from test_config import get_test_config; config = get_test_config(); print(f'✅ Configuration loaded successfully: {config.primary_repo.full_name}')"
	@echo "" 
	@echo "3. Testing repository access..."
	@if [ -f .env ]; then \
		eval $$(grep -v '^#' .env | xargs) && \
		echo "Testing access to $$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO..." && \
		if gh repo view "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" >/dev/null 2>&1; then \
			echo "✅ Repository access confirmed"; \
		else \
			echo "❌ Repository access failed"; \
			exit 1; \
		fi; \
	else \
		echo "❌ .env file not found"; \
		exit 1; \
	fi
	@echo "" 
	@echo "✅ All setup validation tests passed!"
	@echo "" 
	@echo "You can now run the full test suite with:"
	@echo "  make test"
	@echo "" 
	@echo "Or run specific fork compatibility tests with:"
	@echo "  ./venv/bin/pytest -m fork_compatibility -v"

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf .ruff_cache/
	rm -rf venv/
	rm -rf cache/
	rm -f actionlint


# -------------
# debug
# -------------

.PHONY: debug-gh-list-pr
debug-gh-list-pr: ## List all PRs
	gh pr list --state all --limit 10

debug-clean-prs-and-branches: ## Close all PRs and delete branches
	gh pr list --state open --limit 1000 | awk '{print $$1}' | xargs -I {} gh pr close {}
	gh api repos/:owner/:repo/git/refs/heads | jq -r '.[] | select(.ref != "refs/heads/main") | .ref | sub("refs/heads/"; "")' | xargs -I {} gh api -X DELETE repos/:owner/:repo/git/refs/heads/{}
