# Repository Triage Automation

[![CI](https://github.com/thenets/repo-automation/actions/workflows/test.yml/badge.svg)](https://github.com/thenets/repo-automation/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Automated triage labeling for GitHub repositories with intelligent label management, release/backport labeling, and stale PR detection.

## Usage

> **⚠️ Important**: This action uses a **two-workflow pattern** for fork compatibility. You need to create **both** workflow files for proper functionality with external contributors.

### Basic Setup

Create these two workflows in your repository:

**`.github/workflows/repository-automation-trigger.yml`:**
```yaml
---
name: "Repository Automation: Trigger"

on:
  issues:
    types: [opened, labeled, unlabeled]
  pull_request:
    types: [opened, synchronize, edited, ready_for_review, labeled, unlabeled]

permissions:
  contents: read

jobs:
  trigger:
    runs-on: ubuntu-latest
    
    steps:
      - name: Create Minimal Metadata
        run: |
          echo "🚀 Creating minimal metadata for workflow_run event"
          mkdir -p ./pr-metadata
          if [ "${{ github.event_name }}" == "pull_request" ]; then
            TITLE_B64=$(echo -n '${{ github.event.pull_request.title }}' | base64 -w 0)
            BODY_B64=$(echo -n '${{ github.event.pull_request.body }}' | base64 -w 0)
            
            cat > ./pr-metadata/metadata.json << EOF
          {
            "type": "pull_request",
            "event_action": "${{ github.event.action }}",
            "number": ${{ github.event.pull_request.number }},
            "title_base64": "$TITLE_B64",
            "body_base64": "$BODY_B64",
            "state": "${{ github.event.pull_request.state }}",
            "encoding": {"title": "base64", "body": "base64"},
            "head": {"ref": "${{ github.event.pull_request.head.ref }}"},
            "author": {"login": "${{ github.event.pull_request.user.login }}"}
          }
          EOF
          elif [ "${{ github.event_name }}" == "issues" ]; then
            TITLE_B64=$(echo -n '${{ github.event.issue.title }}' | base64 -w 0)
            BODY_B64=$(echo -n '${{ github.event.issue.body }}' | base64 -w 0)
            
            cat > ./pr-metadata/metadata.json << EOF
          {
            "type": "issue",
            "event_action": "${{ github.event.action }}",
            "number": ${{ github.event.issue.number }},
            "title_base64": "$TITLE_B64",
            "body_base64": "$BODY_B64",
            "state": "${{ github.event.issue.state }}",
            "encoding": {"title": "base64", "body": "base64"},
            "author": {"login": "${{ github.event.issue.user.login }}"}
          }
          EOF
          fi

      - name: Store Metadata as Artifact
        uses: actions/upload-artifact@v4
        with:
          name: pr-metadata
          path: pr-metadata/metadata.json
          retention-days: 1
```

**`.github/workflows/repository-automation.yml`:**
```yaml
---
name: Complete Repository Automation

on:
  workflow_run:
    workflows: ["Repository Automation: Trigger"]
    types: [completed]

permissions:
  issues: write
  pull-requests: write
  checks: write

jobs:
  automation:
    runs-on: ubuntu-latest
    if: github.repository == 'your-org/your-repo'  # Update this!
    
    steps:
      - name: Repository Automation
        uses: thenets/repo-automation@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
```

### Complete Configuration

For full functionality with all features enabled, update your workflows:

**`.github/workflows/repository-automation-trigger.yml`** (same as basic setup above)

**`.github/workflows/repository-automation.yml`:**
```yaml
---
name: Complete Repository Automation

on:
  # Fork compatibility via workflow_run
  workflow_run:
    workflows: ["Repository Automation: Trigger"]
    types: [completed]
  
  # Scheduled events for stale detection
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  
  # Manual trigger for testing
  workflow_dispatch:
    inputs:
      pr-number:
        description: 'PR number to process (optional)'
        required: false
        type: string
      dry-run:
        description: 'Dry run mode (true/false)'
        required: false
        default: 'false'

permissions:
  issues: write
  pull-requests: write
  checks: write

jobs:
  automation:
    runs-on: ubuntu-latest
    if: github.repository == 'your-org/your-repo'  # Update this!
    
    steps:
      - name: Repository Automation
        uses: thenets/repo-automation@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
          dry-run: ${{ github.event.inputs.dry-run || 'false' }}

          # Enable all features
          accepted-releases: '["2.6", "2.7", "devel"]'
          accepted-backports: '["2.5", "2.6", "devel"]'
          enable-feature-branch: true
          enable-title-label-sync: true  # Enabled by default
          stale-days: 5
```

## Scenarios

### Feature-Specific Configuration

All scenarios use the two-workflow pattern shown above. Customize the main workflow by adjusting the action inputs:

#### Automatic Triage Labeling Only
Update your `repository-automation.yml` to use minimal configuration:

```yaml
- name: Repository Automation
  uses: thenets/repo-automation@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
    # No additional features enabled - just triage labeling
```

**Features enabled:**
- Adds "triage" label to new issues and PRs
- Protects "triage" label from removal until proper categorization
- Automatically removes "triage" when release labels are applied

#### Release and Backport Labeling
Add release/backport configuration to enable YAML parsing:

```yaml
- name: Repository Automation
  uses: thenets/repo-automation@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
    accepted-releases: '["1.5", "2.0", "devel"]'
    accepted-backports: '["1.4", "1.5"]'
```

**PR description format:**
```yaml
release: "2.0"           # Creates "release-2.0" label
backport: "1.5"          # Creates "backport-1.5" label

# Multiple versions supported
release: ["2.0", "2.1"]  # Creates both labels
```

#### Feature Branch Detection
Enable feature branch automation:

```yaml
- name: Repository Automation
  uses: thenets/repo-automation@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
    enable-feature-branch: true
```

**PR description format:**
```yaml
needs_feature_branch: true  # Creates "feature-branch" label
```

#### Stale PR Detection
Add stale detection with scheduled triggers:

```yaml
- name: Repository Automation
  uses: thenets/repo-automation@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
    stale-days: 7  # Mark PRs stale after 7 days of inactivity
```

**Note:** Requires `schedule` trigger in your main workflow.

### Direct Action Usage (Single Workflow)

> **⚠️ Limited Fork Support**: This pattern won't work for external contributors from forks.

For simple repositories that don't need fork compatibility:

```yaml
name: Simple Repository Automation
on:
  issues:
    types: [opened]
  pull_request:
    types: [opened, ready_for_review]

permissions:
  issues: write
  pull-requests: write

jobs:
  automation:
    runs-on: ubuntu-latest
    steps:
      - uses: thenets/repo-automation@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          # Add feature configurations as needed
```

## Inputs

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| `github-token` | GitHub token for API access | ✅ | |
| `custom-github-token` | Custom token for external contributor support | | `github-token` |
| `dry-run` | Preview mode without making changes | | `false` |
| `accepted-releases` | JSON array of accepted release versions | | |
| `accepted-backports` | JSON array of accepted backport versions | | |
| `enable-feature-branch` | Enable feature branch automation | | `false` |
| `stale-days` | Days before marking PRs as stale | | |

## Outputs

| Name | Description |
|------|-------------|
| `labels-added` | JSON array of labels that were added |
| `actions-taken` | Summary of all actions performed |
| `features-enabled` | JSON array of features enabled based on inputs |

## Features

### 🎯 Unified Triage Management
- Automatically adds "triage" label to new issues and PRs
- Protects triage labels from premature removal
- Smart conditional labeling based on PR state (draft vs ready)
- Removes triage labels when proper categorization is complete

### 🏷️ Release and Backport Labeling
- Parses YAML code blocks in PR descriptions
- Supports single version: `release: "1.5"`
- Supports multiple versions: `release: ["1.5", "2.0"]`
- Validates against configured accepted versions
- Provides clear error messages for invalid values

### 🌿 Feature Branch Detection
- Detects `needs_feature_branch: true` in PR YAML
- Automatically applies "feature-branch" label
- Case-insensitive boolean parsing

### ⏰ Stale PR Detection
- Configurable inactivity period
- Considers commits, comments, reviews, and label changes as activity
- Runs on schedule or manual trigger
- Skips already stale PRs

### 🔄 Title-Label Sync (Bi-directional)
- Automatically syncs PR titles and labels for POC, WIP, and HOLD status
- **Title is source of truth**: Title changes always override labels
- Supports multiple status indicators: `[WIP][HOLD] Feature implementation`
- Case-insensitive matching: `[wip]`, `[WIP]`, `[Wip]` all work
- Status brackets can appear anywhere in title: `Fix [WIP] the bug`
- Labels are always lowercase: `poc`, `wip`, `hold`
- Enabled by default (opt-out with `enable-title-label-sync: false`)

**Examples:**
- Create PR with `[WIP] Feature` → automatically adds `wip` label
- Add `hold` label → title updates to include `[HOLD]`
- Edit title to remove `[WIP]` → automatically removes `wip` label
- Edit title to add `[POC]` → automatically adds `poc` label

### 🔒 Fork Compatibility
- Two-workflow pattern for external contributor support
- Secure artifact sharing between workflows
- Maintains full functionality for fork PRs
- Requires `CUSTOM_GITHUB_TOKEN` with proper permissions

### 🧹 Label Cleanup
- Removes "ready for review" labels from closed PRs
- Maintains clean label states
- Nightly cleanup automation

## Prerequisites

### Required Labels
Create these labels in your repository:
- `triage` - For new issues/PRs requiring categorization
- `stale` - For inactive PRs
- `ready for review` - For PRs ready for team review
- `feature-branch` - For PRs requiring feature branch coordination
- `poc`, `wip`, `hold` - For title-label sync feature (POC, WIP, HOLD status)

### Fork Compatibility Setup

> **🔄 Why Two Workflows?** External contributors from forks can't access your repository secrets. The two-workflow pattern solves this by having forks run a simple metadata collection workflow, then the main repository processes that data with full permissions.

For external contributor support, create a fine-grained personal access token with these permissions:

**Required Permissions:**
- **Metadata**: Read
- **Actions**: Read and Write (critical for artifact downloads)
- **Code**: Read and Write
- **Issues**: Read and Write
- **Pull requests**: Read and Write
- **Workflows**: Read and Write

**Setup Instructions:**
1. Go to [GitHub Settings > Personal Access Tokens (Beta)](https://github.com/settings/tokens?type=beta)
2. Select your repository or choose "All repositories"
3. Grant all required permissions above
4. Add token as repository secret named `CUSTOM_GITHUB_TOKEN`

**⚠️ Important Setup Notes:**
- **Repository Reference**: Update `if: github.repository == 'your-org/your-repo'` in your main workflow to match your actual repository
- **Token Requirement**: Without `CUSTOM_GITHUB_TOKEN`, workflows will fail for external contributors with "Resource not accessible" errors
- **Workflow Names**: The trigger workflow name must exactly match the `workflow_run.workflows` reference in your main workflow

## Migration from Individual Workflows

This action replaces multiple individual keeper workflows with a single, powerful automation:

**Before**: 4+ individual workflows (~1,500+ lines)
**After**: 1-2 workflows using this action (~20-80 lines)

See [DESIGN.md](./DESIGN.md) for detailed migration guidance and technical documentation.

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.