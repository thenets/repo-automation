# Implementation Guide: Remote Action Module Approach

This guide demonstrates how to implement the new remote action module approach for repository automation.

## Problem Solved

**Before**: Users had to copy all workflow files and source code (~1,500 lines)
**After**: Users only need to create 2 simple workflow files (~20 lines each) that reference remote workflows

## Implementation

### Step 1: Create Trigger Workflow

Create `.github/workflows/repository-automation-trigger.yml`:

```yaml
---
name: "Repository Automation: Trigger"
on:
  issues:
    types: [opened, labeled, unlabeled]
  pull_request:
    types: [opened, synchronize, edited, ready_for_review, labeled, unlabeled]

jobs:
  trigger:
    uses: thenets/repo-automation/.github/workflows/triage-automation-trigger.yml@main
```

### Step 2: Create Main Automation Workflow

Create `.github/workflows/repository-automation.yml`:

```yaml
---
name: Complete Repository Automation
on:
  workflow_run:
    workflows: ["Repository Automation: Trigger"]
    types: [completed]
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:
    inputs:
      dry-run:
        description: 'Dry run mode (true/false)'
        required: false
        default: 'false'

jobs:
  automation:
    if: github.repository == 'your-org/your-repo'  # UPDATE THIS
    uses: thenets/repo-automation/.github/workflows/triage-automation.yml@main
    with:
      dry-run: ${{ github.event.inputs.dry-run || 'false' }}
      accepted-releases: '["1.0", "2.0", "devel"]'
      accepted-backports: '["1.0", "2.0"]'
      enable-feature-branch: true
      stale-days: 1
    secrets:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      CUSTOM_GITHUB_TOKEN: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
```

### Step 3: Configuration

1. **Update Repository Reference**: Change `your-org/your-repo` to your actual repository
2. **Configure Features**: Adjust the `with:` parameters to enable your desired features
3. **Set up Secrets**: Ensure `CUSTOM_GITHUB_TOKEN` is set for external contributor support

## Benefits

- ✅ **99% Code Reduction**: ~1,500 lines → ~40 lines total
- ✅ **No File Copying**: Everything consumed remotely
- ✅ **Automatic Updates**: Changes propagate automatically
- ✅ **Fork Compatible**: Works with external contributors
- ✅ **Centralized Maintenance**: All logic in one place

## Migration from Template Approach

If you were using the old template approach:

1. **Delete** old src/ directory from your repository
2. **Replace** workflow files with the 2 simple ones above
3. **Remove** hardcoded repository references
4. **Test** with dry-run mode

## Testing

Use dry-run mode to test without making changes:

```bash
# Trigger manual run with dry-run enabled
gh workflow run repository-automation.yml -f dry-run=true
```

## Available Features

Features are automatically enabled based on inputs provided:

- **Core Triage**: Always enabled (auto-adds triage labels)
- **Release/Backport Labeling**: Enabled when `accepted-releases`/`accepted-backports` provided
- **Feature Branch Automation**: Enabled when `enable-feature-branch: true`
- **Stale Detection**: Enabled when `stale-days` provided or on schedule trigger

## Troubleshooting

### Permission Issues
- Ensure `CUSTOM_GITHUB_TOKEN` secret is set with proper permissions
- Verify workflows have required permissions in their jobs

### Repository Reference Issues
- Double-check `if: github.repository == 'your-org/your-repo'` matches exactly
- Repository name is case-sensitive

### Feature Not Working
- Check workflow run logs in Actions tab
- Verify feature inputs are properly configured
- Test with dry-run mode first

## Example Repositories

- `dednets/repo-automation-test`: Reference implementation
- Examples in `examples/reusable-workflow-examples/`