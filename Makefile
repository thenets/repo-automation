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
	./venv/bin/python -m pytest -v -n 10 \
		--cov=. \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml
	@echo "Tests completed!"
	@echo "Coverage reports generated:"
	@echo "  - Terminal: coverage summary displayed above"
	@echo "  - HTML: htmlcov/index.html"
	@echo "  - XML: coverage.xml"

.PHONY: unit-test-setup
unit-test-setup: ## Install JavaScript dependencies for unit tests
	@echo "Setting up JavaScript unit test dependencies..."
	@if command -v npm > /dev/null 2>&1; then \
		npm install; \
		echo "✅ JavaScript dependencies installed successfully!"; \
	else \
		echo "❌ npm not found. Please install Node.js and npm first."; \
		echo "💡 You can download Node.js from: https://nodejs.org/"; \
		exit 1; \
	fi

.PHONY: test-unit
test-unit: ## Run JavaScript unit tests for src/ directory
	@echo "Running JavaScript unit tests..."
	@if command -v npm > /dev/null 2>&1; then \
		if [ ! -d "node_modules" ]; then \
			echo "⚠️  Dependencies not installed. Run 'make unit-test-setup' first."; \
			exit 1; \
		fi; \
		npm test; \
	else \
		echo "❌ npm not found. Please install Node.js and npm to run unit tests."; \
		echo "💡 Run 'make unit-test-setup' to install dependencies."; \
		exit 1; \
	fi
	@echo "Unit tests completed!"

.PHONY: test-list
test-list: venv ## List all tests
	./venv/bin/python -m pytest --collect-only

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

.PHONY: _gh_auth_check_env
_gh_auth_check_env: ## Check GitHub CLI authentication using .env token
	@echo "Checking GitHub CLI authentication using .env configuration..."
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found"; \
		echo "Please run 'make setup-token' first to create .env file"; \
		exit 1; \
	fi
	@eval $$(grep -v '^#' .env | xargs) && \
	if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "❌ GITHUB_TOKEN not found in .env file"; \
		echo "Please run 'make setup-token' to configure authentication"; \
		exit 1; \
	fi && \
	if [ -z "$$TEST_GITHUB_ORG" ] || [ -z "$$TEST_GITHUB_REPO" ]; then \
		echo "❌ TEST_GITHUB_ORG or TEST_GITHUB_REPO not found in .env file"; \
		echo "Please run 'make setup-token' to configure repository settings"; \
		exit 1; \
	fi && \
	echo "Testing authentication and repository access..." && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	if gh repo view "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" >/dev/null 2>&1; then \
		echo "✅ GitHub CLI authenticated with .env token"; \
		echo "✅ Repository access confirmed: $$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO"; \
	else \
		echo "❌ Authentication or repository access failed"; \
		echo "Please check your token permissions for $$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO"; \
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
	echo "📋 IMPORTANT: Also enable these account permissions:" && \
	echo "   - Workflow: Write (REQUIRED for pushing .github/workflows/ files)" && \
	echo "5. Click 'Generate token' and copy the token" && \
	echo "" && \
	echo "⚠️  IMPORTANT: If you get 'workflow scope' errors later:" && \
	echo "   - Ensure 'Workflow: Write' account permission is enabled" && \
	echo "   - Ensure 'Actions: Read and write' repository permission is granted" && \
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
	find . -type f -name "*.pyc" -delete || true
	find . -type d -name "__pycache__" -delete || true
	find . -type d -name ".pytest_cache" -delete || true
	rm -rf .ruff_cache/
	rm -rf venv/
	rm -rf cache/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -f .coverage* coverage.xml
	rm -f actionlint


# -------------
# debug
# -------------

.PHONY: debug-gh-list-pr
debug-gh-list-pr: _gh_auth_check_env ## List all PRs using .env configuration
	@echo "Listing PRs for repository from .env configuration..."
	@eval $$(grep -v '^#' .env | xargs) && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	gh pr list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --state all --limit 10

.PHONY: debug-gh-list-pr-open
debug-gh-list-pr-open: _gh_auth_check_env ## List open PRs using .env configuration
	@echo "Listing open PRs for repository from .env configuration..."
	@eval $$(grep -v '^#' .env | xargs) && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	gh pr list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --state open --limit 20

.PHONY: debug-gh-list-branches
debug-gh-list-branches: _gh_auth_check_env ## List all branches using .env configuration
	@echo "Listing branches for repository from .env configuration..."
	@eval $$(grep -v '^#' .env | xargs) && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	gh api repos/"$$TEST_GITHUB_ORG"/"$$TEST_GITHUB_REPO"/branches | jq -r '.[].name' | head -20

.PHONY: debug-gh-repo-info
debug-gh-repo-info: _gh_auth_check_env ## Show repository information using .env configuration
	@echo "Repository information from .env configuration:"
	@eval $$(grep -v '^#' .env | xargs) && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	echo "Repository: $$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" && \
	echo "" && \
	gh repo view "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO"

.PHONY: debug-clean-prs-and-branches
debug-clean-prs-and-branches: _gh_auth_check_env ## Close all PRs and delete branches using .env configuration
	@echo "⚠️  WARNING: This will close ALL open PRs and delete ALL non-main branches!"
	@echo "Repository: $$(eval $$(grep -v '^#' .env | xargs) && echo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO")"
	@echo ""
	@read -p "Are you sure you want to continue? [y/N]: " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		eval $$(grep -v '^#' .env | xargs) && \
		export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
		echo "Closing all open PRs..." && \
		gh pr list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --state open --limit 1000 --json number --jq '.[].number' | \
		xargs -I {} sh -c 'echo "Closing PR #{}..." && gh pr close {} --repo "'$$TEST_GITHUB_ORG'/'$$TEST_GITHUB_REPO'"' && \
		echo "Deleting all non-main branches..." && \
		gh api repos/"$$TEST_GITHUB_ORG"/"$$TEST_GITHUB_REPO"/git/refs/heads | \
		jq -r '.[] | select(.ref != "refs/heads/main") | .ref | sub("refs/heads/"; "")' | \
		xargs -I {} sh -c 'echo "Deleting branch {}..." && gh api -X DELETE repos/"'$$TEST_GITHUB_ORG'"/"'$$TEST_GITHUB_REPO'"/git/refs/heads/{}' && \
		echo "✅ Cleanup completed!"; \
	else \
		echo "Operation cancelled."; \
	fi

.PHONY: debug-gh-list-runs
debug-gh-list-runs: _gh_auth_check_env ## List recent workflow runs using .env configuration
	@echo "Listing recent workflow runs for repository from .env configuration..."
	@eval $$(grep -v '^#' .env | xargs) && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	gh run list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --limit 10

.PHONY: debug-gh-list-runs-failed
debug-gh-list-runs-failed: _gh_auth_check_env ## List recent failed workflow runs using .env configuration
	@echo "Listing recent failed workflow runs for repository from .env configuration..."
	@eval $$(grep -v '^#' .env | xargs) && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	gh run list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --status failure --limit 10

.PHONY: debug-test-env
debug-test-env: _gh_auth_check_env ## Test .env configuration and show current settings
	@echo "=== .env Configuration Test ==="
	@echo ""
	@eval $$(grep -v '^#' .env | xargs) && \
	echo "TEST_GITHUB_ORG: $$TEST_GITHUB_ORG" && \
	echo "TEST_GITHUB_REPO: $$TEST_GITHUB_REPO" && \
	echo "GITHUB_TOKEN: [hidden for security]" && \
	echo "" && \
	export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
	echo "Testing repository access..." && \
	gh repo view "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --json name,owner,visibility,isPrivate && \
	echo "" && \
	echo "✅ Configuration is working correctly!"

.PHONY: publish
publish: export TAG_NAME=v1
publish: ## Publish TAG_NAME tag to latest commit on main branch
	@echo "Publishing $(TAG_NAME) tag to latest commit on main branch..."
	@git checkout main
	@git pull origin main
	@LATEST_COMMIT=$$(git rev-parse HEAD) && \
	echo "Latest commit on main: $$LATEST_COMMIT" && \
	echo "Deleting remote $(TAG_NAME) tag..." && \
	git push --delete origin $(TAG_NAME) 2>/dev/null || echo "Remote $(TAG_NAME) tag doesn't exist" && \
	echo "Deleting local $(TAG_NAME) tag..." && \
	git tag -d $(TAG_NAME) 2>/dev/null || echo "Local $(TAG_NAME) tag doesn't exist" && \
	echo "Creating new $(TAG_NAME) tag at $$LATEST_COMMIT..." && \
	git tag $(TAG_NAME) $$LATEST_COMMIT && \
	echo "Pushing $(TAG_NAME) tag to remote..." && \
	git push origin $(TAG_NAME) && \
	echo "✅ $(TAG_NAME) tag published successfully!"

.PHONY: publish-beta
publish-beta: ## Publish beta tag to latest commit on main branch
	@echo "Publishing beta tag to latest commit on main branch..."
	@git checkout main
	@git pull origin main
	@LATEST_COMMIT=$$(git rev-parse HEAD) && \
	echo "Latest commit on main: $$LATEST_COMMIT" && \
	echo "Deleting remote beta tag..." && \
	git push --delete origin beta 2>/dev/null || echo "Remote beta tag doesn't exist" && \
	echo "Deleting local beta tag..." && \
	git tag -d beta 2>/dev/null || echo "Local beta tag doesn't exist" && \
	echo "Creating new beta tag at $$LATEST_COMMIT..." && \
	git tag beta $$LATEST_COMMIT && \
	echo "Pushing beta tag to remote..." && \
	git push origin beta && \
	echo "✅ beta tag published successfully!"

.PHONY: debug-clean-labels
debug-clean-labels: _gh_auth_check_env ## Delete all labels from repository using .env configuration
	@echo "⚠️  WARNING: This will delete ALL labels from the repository!"
	@eval $$(grep -v '^#' .env | xargs) && \
	echo "Repository: $$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" && \
	echo "" && \
	printf "Are you sure you want to continue? [y/N]: " && \
	read confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		export GITHUB_TOKEN="$$GITHUB_TOKEN" && \
		echo "Listing current labels..." && \
		gh label list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" && \
		echo "" && \
		echo "Deleting all labels..." && \
		gh label list --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" | cut -f1 | \
		xargs -I {} gh label delete "{}" --repo "$$TEST_GITHUB_ORG/$$TEST_GITHUB_REPO" --yes && \
		echo "✅ All labels deleted successfully!"; \
	else \
		echo "Operation cancelled."; \
	fi
