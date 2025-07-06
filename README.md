# GitHub Repository Automations

This repository contains GitHub Actions workflows to automate common development tasks for team projects.

## Features

### 1. Auto-Add Triage Label
Automatically adds a "triage" label to new issues and pull requests when they are created.

**Trigger**: `issues.opened`, `pull_request.opened`

**Behavior**:
- Adds "triage" label to newly created issues
- Adds "triage" label to newly created pull requests
- Only adds if the label doesn't already exist

### 2. Triage Label Protection
Prevents removal of the "triage" label unless specific conditions are met.

**Trigger**: `issues.labeled`, `issues.unlabeled`, `pull_request.labeled`, `pull_request.unlabeled`

**Behavior**:
- Monitors when labels are added or removed
- If "triage" label is removed, checks for presence of:
  - Labels starting with "release " (e.g., "release 1.0", "release v2.3")
  - Labels starting with "backport " (e.g., "backport 1.0", "backport main")
- If neither condition is met, automatically re-adds the "triage" label

## Workflow Structure

```
.github/workflows/
├── triage-auto-add.yml      # Auto-adds triage label to new issues/PRs
└── triage-protection.yml    # Protects triage label from removal
```

## Implementation Plan

1. **Create Auto-Add Workflow**
   - Trigger on issue and PR creation
   - Use GitHub API to add "triage" label
   - Handle edge cases (label already exists, permissions)

2. **Create Protection Workflow**
   - Trigger on label changes
   - Check if "triage" was removed
   - Validate presence of "release *" or "backport *" labels
   - Re-add "triage" if conditions not met

3. **Error Handling**
   - Handle API rate limits
   - Graceful failure on permission issues
   - Logging for debugging

## Prerequisites

- Repository must have "triage" label created
- GitHub Actions must have write permissions for issues and pull requests
- Workflows require `GITHUB_TOKEN` with appropriate scopes

## Usage

1. Copy workflow files to `.github/workflows/` directory
2. Ensure "triage" label exists in repository settings
3. Verify GitHub Actions permissions include:
   - `issues: write`
   - `pull-requests: write`

## Testing

- Create test issues and PRs to verify auto-labeling
- Test label removal scenarios with and without release/backport labels
- Verify workflows don't interfere with each other