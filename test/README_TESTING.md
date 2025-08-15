# GitHub Actions Multi-Repository Testing Guide

This guide explains how to test GitHub Actions workflows across different organizations and repositories using the simplified fork compatibility testing framework.

## Overview

The testing framework supports:
- **Organization/Repository Testing**: Test workflows against any GitHub organization and repository
- **Fork Compatibility**: Validate workflows work correctly with external contributors via pytest markers
- **Automatic Setup**: Fixtures handle repository cloning and GitHub Actions secrets management
- **Configuration-Driven**: Simple `.env` file configuration with git remote fallback

## Quick Start

### 1. Basic Setup

```bash
# Option 1: Use .env file configuration
echo 'TEST_GITHUB_ORG="my-org"' > .env
echo 'TEST_GITHUB_REPO="my-repo"' >> .env

# Option 2: Use automated setup script
python test/setup_org_testing.py --org my-org --repo my-repo --env-file
```

### 2. Run Fork Compatibility Tests

```bash
# Run all fork compatibility tests
./venv/bin/pytest -m fork_compatibility -v

# Run specific fork compatibility test
./venv/bin/pytest test/test_basic_functionality.py::TestBasicFunctionality::test_hello -v

# List all fork compatibility tests
./venv/bin/pytest --collect-only -m fork_compatibility
```

## Configuration

### Environment Variables (.env file)

Create a `.env` file in the project root:

```bash
# Required: Target repository for testing
TEST_GITHUB_ORG="my-organization"
TEST_GITHUB_REPO="my-repository"

# Optional: Custom GitHub token for repository secrets setup
CUSTOM_GITHUB_TOKEN="ghp_your_token_here"
```

### Git Remote Fallback

If no `.env` file is provided, the system automatically detects the repository from git remote origin:

```bash
# If your git remote origin is: https://github.com/my-org/my-repo.git
# The system will automatically use:
# TEST_GITHUB_ORG="my-org"
# TEST_GITHUB_REPO="my-repo"
```

## Fork Compatibility Testing

### Marked Tests

The following tests are marked with `@pytest.mark.fork_compatibility` for cross-repository validation:

1. **test_hello** - Basic repository operations and PR creation
2. **test_pr_triage_label_auto_add** - Triage label automation
3. **test_needs_feature_branch_true_labeling** - Feature branch labeling
4. **test_workflow_fails_with_invalid_release_label** - Workflow validation

### How It Works

1. **Repository Validation**: Fixtures validate that `TEST_GITHUB_ORG/TEST_GITHUB_REPO` exists and is accessible
2. **Automatic Cloning**: Test repositories are automatically cloned to `./cache/test/repo/`
3. **Secrets Management**: If `CUSTOM_GITHUB_TOKEN` is provided, it's automatically added to repository secrets
4. **Workflow Setup**: GitHub Actions workflows are configured for the target repository

### Running Tests

```bash
# Run all fork compatibility tests
./venv/bin/pytest -m fork_compatibility -v

# Run with specific output
./venv/bin/pytest -m fork_compatibility -v --tb=short

# Run in parallel (faster)
./venv/bin/pytest -m fork_compatibility -n auto
```

## Setup and Validation

### Prerequisites

Ensure you have:
- `gh` CLI installed and authenticated
- `git` command available
- `pytest` installed
- Access to the target repository

### Validation Commands

```bash
# Validate current configuration
python test/setup_org_testing.py --validate

# Show current configuration
python test/setup_org_testing.py --config

# Set up for specific repository
python test/setup_org_testing.py --org my-org --repo my-repo
```

### Repository Access

The system validates repository access using:

```bash
gh repo view my-org/my-repo
```

If this fails, check:
- Repository name is correct
- You have access to the repository  
- GitHub CLI is authenticated (`gh auth status`)

## GitHub Actions Secrets

### Automatic Setup

When `CUSTOM_GITHUB_TOKEN` is provided in `.env`, the fixtures automatically:

1. Validate repository exists and is accessible
2. Set `CUSTOM_GITHUB_TOKEN` as a repository secret using `gh secret set`
3. Configure workflows to use the custom token

### Manual Setup

If automatic setup fails, manually add the secret:

```bash
# Set repository secret manually
gh secret set GITHUB_TOKEN --repo my-org/my-repo --body "your_token_here"
```

## Test Configuration

### Cache Directory

Test repositories are cloned to: `./cache/test/repo/`

### Timeout Settings

Default test timeouts:
- **Test Timeout**: 180 seconds
- **Poll Interval**: 5 seconds

Override in `.env`:
```bash
TEST_TIMEOUT="300"
TEST_POLL_INTERVAL="10"
```

## Example Workflows

### Testing Your Organization

```bash
# 1. Set up configuration
echo 'TEST_GITHUB_ORG="acme-corp"' > .env
echo 'TEST_GITHUB_REPO="api-service"' >> .env
echo 'CUSTOM_GITHUB_TOKEN="ghp_..."' >> .env

# 2. Validate setup
python test/setup_org_testing.py --validate

# 3. Run fork compatibility tests
./venv/bin/pytest -m fork_compatibility -v
```

### Testing Open Source Projects

```bash
# Test against a public repository
echo 'TEST_GITHUB_ORG="kubernetes"' > .env
echo 'TEST_GITHUB_REPO="kubernetes"' >> .env

# Run tests (no custom token needed for public repos)
./venv/bin/pytest -m fork_compatibility -v
```

### Using Git Remote Detection

```bash
# In a repository with GitHub origin
cd my-existing-repo
git remote -v
# origin  https://github.com/my-org/my-repo.git (fetch)

# Run tests (automatic detection)
./venv/bin/pytest -m fork_compatibility -v
```

## Troubleshooting

### Common Issues

**Repository not accessible**:
```bash
# Check authentication
gh auth status

# Test repository access
gh repo view my-org/my-repo
```

**Secret setup fails**:
```bash
# Check repository permissions
gh api repos/my-org/my-repo --jq .permissions

# Manually set secret
gh secret set GITHUB_TOKEN --repo my-org/my-repo
```

**Tests timeout**:
```bash
# Increase timeout in .env
echo 'TEST_TIMEOUT="300"' >> .env

# Check GitHub Actions logs
gh run list --repo my-org/my-repo
```

### Debug Mode

```bash
# Run with verbose output
./venv/bin/pytest -m fork_compatibility -v -s

# Show fixture setup
./venv/bin/pytest -m fork_compatibility --setup-show
```

## Repository Structure

```
test/
├── conftest.py                    # Enhanced fixtures with repository management
├── test_config.py                 # Configuration management
├── setup_org_testing.py          # Simplified setup script
├── README_TESTING.md             # This guide
├── test_basic_functionality.py   # ✓ fork_compatibility
├── test_triage_auto_add.py        # ✓ fork_compatibility  
├── test_feature_branch_labeler.py # ✓ fork_compatibility
└── test_label_validation.py       # ✓ fork_compatibility
```

## Advanced Usage

### Configuration Object

Access configuration in tests:

```python
def test_my_workflow(test_config):
    assert test_config.primary_repo.owner == "my-org"
    assert test_config.primary_repo.repo == "my-repo"
```

### Repository Fixtures

Use repository fixtures:

```python
def test_my_workflow(test_repo, integration_manager):
    # test_repo is automatically cloned and configured
    # integration_manager handles GitHub operations
    pass
```

### Custom Test Marking

Add your own fork compatibility tests:

```python
@pytest.mark.fork_compatibility  
def test_my_custom_workflow(test_repo, integration_manager):
    """Test custom workflow with fork compatibility."""
    # Your test implementation
    pass
```

This simplified approach ensures reliable, maintainable fork compatibility testing across any GitHub organization and repository configuration. 