# GitHub Repository Automations - Claude Instructions

## Project Overview

This repository contains GitHub Actions workflows for automating repository management tasks, specifically focused on triage label management for issues and pull requests.

## Current Features

1. **Auto-Add Triage Label**: Automatically adds "triage" label to new issues and PRs
2. **Triage Label Protection**: Prevents removal of "triage" label unless "release *" or "backport *" labels are present

## Development Guidelines

### Workflow Structure
- All GitHub Actions workflows go in `.github/workflows/`
- Use descriptive filenames: `triage-auto-add.yml`, `triage-protection.yml`
- Follow YAML best practices for GitHub Actions

### Testing Commands
```bash
# Validate YAML syntax
yamllint .github/workflows/*.yml

# Test workflow syntax (if available)
actionlint .github/workflows/*.yml
```

### Key Implementation Notes

1. **Label Management**:
   - Always check if "triage" label exists before adding
   - Handle API rate limits gracefully
   - Use `GITHUB_TOKEN` for authentication

2. **Event Triggers**:
   - Auto-add: `issues.opened`, `pull_request.opened`
   - Protection: `issues.labeled`, `issues.unlabeled`, `pull_request.labeled`, `pull_request.unlabeled`

3. **Pattern Matching**:
   - Release labels: `release *` (e.g., "release 1.0", "release v2.3")
   - Backport labels: `backport *` (e.g., "backport 1.0", "backport main")

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
├── triage-auto-add.yml      # Auto-adds triage label to new issues/PRs
└── triage-protection.yml    # Protects triage label from removal
```

## Common Tasks

### Adding New Automation
1. Create new workflow file in `.github/workflows/`
2. Update README.md with feature documentation
3. Add testing scenarios
4. Update this CLAUDE.md if needed

### Modifying Existing Workflows
1. Always test YAML syntax before committing
2. Consider backward compatibility
3. Update documentation if behavior changes

### Debugging Workflows
- Check GitHub Actions logs in the repository
- Verify webhook events are triggering correctly
- Ensure labels exist in repository settings

## Repository Setup Requirements

1. **Labels**: Ensure "triage" label exists in repository settings
2. **Actions**: Enable GitHub Actions if not already enabled
3. **Permissions**: Verify Actions have appropriate permissions
4. **Branch Protection**: Consider if workflows need to run on protected branches