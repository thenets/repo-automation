# GitHub Repository Automations

This repository contains GitHub Actions workflows to automate common development tasks for team projects.

## Table of Contents

- [Features](#features)
  - [1. Keeper: auto-add triage label](#1-keeper-auto-add-triage-label) ✅ **Implemented**
  - [2. Keeper: triage label protection](#2-triage-label-protection) ✅ **Implemented**
  - [3. Keeper: stale PR detector](#3-keeper-stale-pr-detector) ✅ **Implemented**
  - [4. Keeper: auto-label release and backport](#4-keeper-auto-label-release-and-backport) ✅ **Implemented**
  - [5. Keeper: closed PR label cleanup](#5-keeper-closed-pr-label-cleanup) 📝 **Planned**
  - [6. Keeper: feature branch auto-labeling](#6-keeper-feature-branch-auto-labeling) ✅ **Implemented**
  - [7. Keeper: enhanced triage label management](#7-keeper-enhanced-triage-label-management) 📝 **Planned**
- [Workflow Structure](#workflow-structure)
- [Implementation Plan](#implementation-plan)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Testing](#testing)
- [License](#license)

## Workflow Structure

```
.github/workflows/
├── keeper-auto-add-triage-label.yml       # Auto-adds triage label to new issues/PRs
├── keeper-triage-label-protection.yml     # Protects triage label from removal
├── keeper-stale-pr-detector.yml           # Marks inactive PRs as stale
├── keeper-auto-label-release-backport.yml # Auto-labels PRs based on YAML frontmatter
├── keeper-closed-pr-label-cleanup.yml     # Removes "ready for review" label from closed PRs
├── keeper-feature-branch-auto-labeling.yml # Auto-labels PRs as "feature-branch" based on YAML frontmatter
└── keeper-enhanced-triage-management.yml  # Enhanced triage label management with release/ready conditions
```

## How to use them

1. Copy the workflows under the `.github/workflows/` dir to your repository
2. Make sure to update the `if: github.repository == 'thenets/repo-automations'` to match your repository

## Features

### 1. Keeper: auto-add triage label
Automatically adds a "triage" label to new issues and pull requests when they are created.

**File**: `.github/workflows/keeper-auto-add-triage-label.yml`

**Trigger**: `issues.opened`, `pull_request.opened`

**Behavior**:
- Adds "triage" label to newly created issues
- Adds "triage" label to newly created pull requests
- Only adds if the label doesn't already exist

```mermaid
flowchart LR
    A[New Issue/PR Created] --> B[Add 'triage' Label]
    B --> C[✅ Complete]
```



### 2. Keeper: triage label protection
Prevents removal of the "triage" label unless specific conditions are met.

**File**: `.github/workflows/keeper-triage-label-protection.yml`

**Trigger**: `issues.labeled`, `issues.unlabeled`, `pull_request.labeled`, `pull_request.unlabeled`

**Behavior**:
- Monitors when labels are added or removed
- If "triage" label is removed, checks for presence of:
  - Labels starting with "release " (e.g., "release 1.0", "release v2.3")
  - Labels starting with "backport " (e.g., "backport 1.0", "backport main")
- If neither condition is met, automatically re-adds the "triage" label

```mermaid
flowchart LR
    A[Triage Label Removed] --> B{Has release/backport label?}
    B -->|Yes| C[✅ Allow Removal]
    B -->|No| D[Re-add Triage Label]
    D --> E[✅ Complete]
```

### 3. Keeper: stale PR detector
Automatically marks pull requests as stale when they have no activity for more than 1 day.

**File**: `.github/workflows/keeper-stale-pr-detector.yml`

**Trigger**: `schedule` (daily cron job)

**Behavior**:
- Runs daily to check all open pull requests
- Identifies PRs with no activity (comments, commits, or label changes) for more than 1 day
- Adds "stale" label to inactive PRs
- Skips PRs that already have the "stale" label
- Considers these activities as "activity":
  - New commits pushed to the PR branch
  - Comments added to the PR
  - Labels added or removed
  - PR reviews submitted
  - PR status changes (ready for review, draft, etc.)

```mermaid
flowchart LR
    A[Daily Cron Job] --> B[Check Open PRs]
    B --> C{PR inactive >1 day?}
    C -->|Yes| D[Add 'stale' Label]
    C -->|No| E[Skip PR]
    D --> F[✅ Complete]
    E --> F
```

### 4. Keeper: auto-label release and backport
Automatically adds release and backport labels to pull requests based on YAML code blocks in the PR description.

**File**: `.github/workflows/keeper-auto-label-release-backport.yml`

**Trigger**: `pull_request.opened`, `pull_request.synchronize`

**Behavior**:
- Scans the PR description for YAML code blocks
- Parses `release` and `backport` values from YAML
- Validates values against accepted lists (see below)
- Adds corresponding labels (e.g., `release 1.5`, `backport 1.4`)
- Ignores comments after `#` in YAML values
- Only processes the first YAML block found

**Validation Rules**:
- **Empty values** (e.g., `release:` with no value) → Workflow exits gracefully
- **Existing labels** → Skips assignment to preserve manually set labels
- **Valid values** (from accepted lists) → Labels are added successfully  
- **Invalid values** (not in accepted lists) → **Workflow fails with error**

**Accepted Values**:
- **Release tags**: `1.0`, `1.1`, `1.2`, `1.3`, `1.4`, `1.5`, `1.6`, `2.0`, `2.1`, `2.2`, `devel`, `main`
- **Backport tags**: `1.0`, `1.1`, `1.2`, `1.3`, `1.4`, `1.5`, `1.6`, `2.0`, `2.1`, `2.2`, `main`

*Note: Using values not in these lists will cause the workflow to fail, alerting you to fix the invalid value.*

**Supported YAML format**:

Include a YAML code block in your PR description:
```yaml
release: 1.5    # Creates "release 1.5" label
backport: 1.4   # Creates "backport 1.4" label  
```

**Example PR description**:

> This PR adds new feature X.
> 
> ```yaml
> release: 1.5
> backport: 1.4
> ```
> 
> The changes are backward compatible.

```mermaid
flowchart LR
    A[PR Created/Updated] --> B[Scan Changed Files]
    B --> C{YAML Found?}
    C -->|Yes| D[Parse release/backport]
    C -->|No| E[✅ Skip]
    D --> F[Add Labels]
    F --> G[✅ Complete]
```

### 5. Keeper: closed PR label cleanup
Automatically removes the "ready for review" label from closed pull requests during nightly runs.

**File**: `.github/workflows/keeper-closed-pr-label-cleanup.yml`

**Trigger**: `schedule` (nightly cron job)

**Behavior**:
- Runs nightly to check all closed pull requests
- Identifies closed PRs that still have the "ready for review" label
- Removes the "ready for review" label from these PRs
- Helps maintain clean label states by removing review-related labels that are no longer relevant
- Only processes PRs that are in closed state (merged or closed without merge)

```mermaid
flowchart LR
    A[Nightly Cron Job] --> B[Check Closed PRs]
    B --> C{Has 'ready for review' label?}
    C -->|Yes| D[Remove Label]
    C -->|No| E[Skip PR]
    D --> F[✅ Complete]
    E --> F
```

### 6. Keeper: feature branch auto-labeling
Automatically adds "feature-branch" label to pull requests based on YAML code blocks in the PR description.

**File**: `.github/workflows/keeper-feature-branch-auto-labeling.yml`

**Trigger**: `pull_request.opened`, `pull_request.synchronize`

**Behavior**:
- Scans the PR description for YAML code blocks
- Parses `needs_feature_branch` value from YAML (Boolean: `true` or `false`)
- If `needs_feature_branch: true`, adds "feature-branch" label to the PR
- If `needs_feature_branch: false`, no action is taken
- Ignores comments after `#` in YAML values
- Only processes the first YAML block found

**Validation Rules**:
- **Empty values** (e.g., `needs_feature_branch:` with no value) → Workflow exits gracefully
- **Existing labels** → Skips assignment to preserve manually set labels
- **Valid values** (`true`, `false`) → Labels are added successfully if `true`
- **Invalid values** (not boolean) → **Workflow fails with error**

**Supported YAML format**:

Include a YAML code block in your PR description:
```yaml
needs_feature_branch: true    # Creates "feature-branch" label
release: 1.5                  # Creates "release 1.5" label (existing feature)
backport: 1.4                 # Creates "backport 1.4" label (existing feature)
```

**Example PR description**:

> This PR adds new feature X that requires a feature branch.
> 
> ```yaml
> needs_feature_branch: true
> release: 1.5
> backport: 1.4
> ```
> 
> The changes require coordination with multiple teams.

```mermaid
flowchart LR
    A[PR Created/Updated] --> B[Scan PR Description]
    B --> C{YAML Found?}
    C -->|Yes| D[Parse needs_feature_branch]
    C -->|No| E[✅ Skip]
    D --> F{Value is true?}
    F -->|Yes| G[Add feature-branch Label]
    F -->|No| H[✅ Skip]
    G --> I[✅ Complete]
    H --> I
```

### 7. Keeper: enhanced triage label management
Enhances the existing triage label protection by automatically removing the "triage" label when specific conditions are met.

**File**: `.github/workflows/keeper-enhanced-triage-management.yml`

**Trigger**: `pull_request.labeled`, `pull_request.unlabeled`

**Behavior**:
- Monitors when labels are added or removed from PRs
- Automatically removes "triage" label when ALL conditions are met:
  - PR has any label starting with "release " (e.g., "release 1.5", "release main")
  - PR has "ready for review" label
- This indicates the PR is properly categorized and ready for review, so triage is no longer needed
- Works in conjunction with existing triage protection workflow

**Logic Flow**:
1. **Label Change Detected** → Check if PR has both "release *" and "ready for review" labels
2. **Conditions Met** → Remove "triage" label (if present)
3. **Conditions Not Met** → No action taken (existing protection workflow handles re-adding if needed)

**Integration with Existing Workflows**:
- **Complements** `keeper-triage-label-protection.yml` (doesn't replace it)
- **Works with** `keeper-auto-label-release-backport.yml` for complete label management
- **Respects** manual label changes by only acting on specific conditions

```mermaid
flowchart LR
    A[PR Label Change] --> B{Has release label?}
    B -->|Yes| C{Has ready for review?}
    B -->|No| D[✅ No Action]
    C -->|Yes| E[Remove triage Label]
    C -->|No| F[✅ No Action]
    E --> G[✅ Complete]
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

3. **Create Stale PR Detection Workflow**
   - Schedule daily execution using cron
   - Query all open PRs in the repository
   - Check last activity timestamp for each PR
   - Add "stale" label to PRs inactive for >1 day
   - Skip PRs already marked as stale

4. **Error Handling**
   - Handle API rate limits
   - Graceful failure on permission issues
   - Logging for debugging

## Prerequisites

- Repository must have "triage" and "stale" labels created
- GitHub Actions must have write permissions for issues and pull requests
- Workflows require `GITHUB_TOKEN` with appropriate scopes

## Usage

1. Copy workflow files to `.github/workflows/` directory
2. Ensure required labels exist in repository settings:
   - "triage" (for new issues/PRs)
   - "stale" (for inactive PRs)
3. Verify GitHub Actions permissions include:
   - `issues: write`
   - `pull-requests: write`

## Testing

### Prerequisites for Testing

1. **Fork this repository** to your GitHub account
2. **Update repository references** in all workflow files:
   - Change `if: github.repository == 'thenets/repo-automations'` to `if: github.repository == 'your-username/repo-automations'`
   - This line appears in all `keeper-*.yml` workflow files under `.github/workflows/`

### Automated Testing

Run the test suite:

```bash
# Run all tests
make test

# Run specific test method
make venv
./venv/bin/pytest -k test_stale_pr_detection_manual_trigger -v
```

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.