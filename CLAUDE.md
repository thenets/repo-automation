# GitHub Repository Automations - Claude Instructions

## Project Overview

This repository contains GitHub Actions workflows for automating repository management tasks, specifically focused on triage label management for issues and pull requests.

## Current Features

1. **Auto-Add Triage Label**: Automatically adds "triage" label to new issues and PRs
2. **Triage Label Protection**: Prevents removal of "triage" label unless "release *" or "backport *" labels are present
3. **Stale PR Detection**: Automatically marks PRs as stale when inactive for more than 1 day

## Development Guidelines

### Workflow Structure
- All GitHub Actions workflows go in `.github/workflows/`
- Use descriptive filenames: `keeper-auto-add-triage-label.yml`, `keeper-triage-label-protection.yml`, `keeper-stale-pr-detector.yml`
- Follow YAML best practices for GitHub Actions

### Testing Commands
```bash
# Validate YAML syntax and formatting (run this before committing workflow changes)
make lint

# Run specific test class
./venv/bin/pytest test/test_triage_auto_add.py::TestStalePRDetector

# Run specific individual test
./venv/bin/pytest test/test_triage_auto_add.py::TestStalePRDetector::test_stale_pr_detection_manual_trigger -v

# Run tests with verbose output
./venv/bin/pytest -v

# Run tests and show print statements
./venv/bin/pytest -s

# If I pass a test name only to be executed, use the `-k` pytest arg to auto select this test
```

### Pre-Commit Guidelines
- Always run `make lint format" before commiting git changes

### Key Implementation Notes

1. **Label Management**:
   - Always check if "triage" label exists before adding
   - Handle API rate limits gracefully
   - Use `GITHUB_TOKEN` for authentication

2. **Event Triggers**:
   - Auto-add: `issues.opened`, `pull_request.opened`
   - Protection: `issues.labeled`, `issues.unlabeled`, `pull_request.labeled`, `pull_request.unlabeled`
   - Stale detection: `schedule` (daily cron), `workflow_dispatch` (manual trigger)

3. **Pattern Matching**:
   - Release labels: `release *` (e.g., "release 1.0", "release v2.3")
   - Backport labels: `backport *` (e.g., "backport 1.0", "backport main")

4. **Stale Detection Logic**:
   - Runs daily at 2 AM UTC
   - Checks all open PRs for activity in the last 24 hours
   - Activity includes: commits, comments, reviews, label changes, status changes
   - Only adds "stale" label if not already present
   - Skips PRs that already have stale label

### Required Permissions
GitHub Actions workflows need these permissions:
```yaml
permissions:
  issues: write
  pull-requests: write
```

### Error Handling
- Handle missing labels gracefully
- Log meaningful error messages
- Fail silently on permission issues to avoid noise

### File Organization
```
.github/workflows/
├── keeper-auto-add-triage-label.yml     # Auto-adds triage label to new issues/PRs
├── keeper-triage-label-protection.yml   # Protects triage label from removal
└── keeper-stale-pr-detector.yml         # Marks inactive PRs as stale
```

## Common Tasks

### Adding New Automation
1. Create new workflow file in `.github/workflows/`
2. Update README.md with feature documentation
3. Add testing scenarios
4. Update this CLAUDE.md if needed

### Modifying Existing Workflows
1. Always run `make lint` to validate YAML syntax and formatting before committing
2. Consider backward compatibility
3. Update documentation if behavior changes

### Debugging Workflows
- Check GitHub Actions logs in the repository
- Verify webhook events are triggering correctly
- Ensure labels exist in repository settings

## Repository Setup Requirements

1. **Labels**: Ensure required labels exist in repository settings:
   - "triage" (for new issues/PRs)
   - "stale" (for inactive PRs)
2. **Actions**: Enable GitHub Actions if not already enabled
3. **Permissions**: Verify Actions have appropriate permissions
4. **Branch Protection**: Consider if workflows need to run on protected branches
5. **Repository Restriction**: Update `if: github.repository == 'your-org/your-repo'` in all workflows

## Documentation Guidelines

- New feature plans must be documented into the README.md