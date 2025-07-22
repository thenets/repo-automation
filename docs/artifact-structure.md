# PR Metadata Artifact Structure

This document describes the structure of the `pr-metadata.json` artifact created by the `keeper-trigger.yml` workflow.

## Purpose

The artifact contains ALL PR metadata collected from pull request events, enabling action workflows to process PRs from forks while maintaining security separation.

## Artifact Details

- **Name**: `pr-metadata`
- **File**: `pr-metadata.json`
- **Format**: JSON
- **Retention**: 7 days
- **Size**: Typically < 5KB

## Data Structure

```json
{
  "pr_number": 123,
  "repository": "owner/repo",
  "head_sha": "abc123def456...",
  "body": "This PR adds new feature...\n\n```yaml\nneeds_feature_branch: true\n```",
  "title": "Add new feature X",
  "draft": false,
  "action": "opened",
  "head_repo": "fork_owner/repo",
  "base_repo": "owner/repo", 
  "user": "contributor_username",
  "created_at": "2025-01-22T10:00:00Z",
  "updated_at": "2025-01-22T10:05:00Z",
  "mergeable": null,
  "state": "open",
  "workflow_run_id": "12345678",
  "collected_at": "2025-01-22T10:05:30.123Z"
}
```

## Field Descriptions

| Field | Type | Description | Usage |
|-------|------|-------------|-------|
| `pr_number` | number | PR number | Identifying the PR for labeling operations |
| `repository` | string | Target repository (`owner/repo`) | Repository validation in action workflows |
| `head_sha` | string | SHA of the PR head commit | Verification and status updates |
| `body` | string | PR description/body text | YAML parsing for feature flags |
| `title` | string | PR title | Logging and notifications |
| `draft` | boolean | Whether PR is in draft state | Triage label logic |
| `action` | string | Event action (`opened`, `synchronize`, etc.) | Determining what triggered the workflow |
| `head_repo` | string | Source repository (may be fork) | Fork detection |
| `base_repo` | string | Target repository | Repository validation |
| `user` | string | PR author username | User-based logic and logging |
| `created_at` | string | PR creation timestamp | Age-based processing |
| `updated_at` | string | Last update timestamp | Freshness checks |
| `mergeable` | boolean/null | Merge status | Conflict detection |
| `state` | string | PR state (`open`, `closed`) | State-based processing |
| `workflow_run_id` | string | Collection workflow run ID | Debugging and tracing |
| `collected_at` | string | Data collection timestamp | Freshness and debugging |

## Usage in Action Workflows

### Download Artifact

```yaml
- name: Download PR metadata
  uses: actions/download-artifact@v4
  with:
    name: pr-metadata
    github-token: ${{ secrets.GITHUB_TOKEN }}
    run-id: ${{ github.event.workflow_run.id }}
```

### Load and Use Data

```javascript
// Load PR metadata
const prData = JSON.parse(require('fs').readFileSync('pr-metadata.json', 'utf8'));

// Replace existing context usage
// OLD: context.payload.pull_request.body
// NEW: prData.body

// OLD: context.issue.number  
// NEW: prData.pr_number

// OLD: context.payload.pull_request.draft
// NEW: prData.draft
```

## Migration Examples

### Triage Labeling
```javascript
// Before
if (!github.event.pull_request.draft) {
  // Add triage label to context.issue.number
}

// After  
if (!prData.draft) {
  // Add triage label to prData.pr_number
}
```

### YAML Parsing
```javascript
// Before
const prBody = context.payload.pull_request.body || '';
const yamlMatch = prBody.match(/```yaml\s*\n([\s\S]*?)\n\s*```/g);

// After
const prBody = prData.body || '';
const yamlMatch = prBody.match(/```yaml\s*\n([\s\S]*?)\n\s*```/g);
```

### Repository Validation
```javascript
// Before
if (github.repository == 'thenets/repo-automations') {
  // Existing logic
}

// After - same validation still works
if (github.repository == 'thenets/repo-automations') {
  // Use prData instead of context.payload.pull_request
}
```

## Security Considerations

1. **No Processing**: Data is collected as-is without validation or processing
2. **Read-Only**: Collection workflow has minimal permissions
3. **Validation**: Action workflows perform all validation on downloaded data  
4. **Repository Restriction**: Action workflows maintain existing repository checks

## Error Handling

- **Missing Fields**: Some fields may be null (e.g., `mergeable` during processing)
- **Empty Body**: `body` field defaults to empty string if no description
- **Fork Detection**: Compare `head_repo` vs `base_repo` to detect forks

## Performance

- **Artifact Size**: ~2-5KB per PR
- **Collection Time**: ~10-15 seconds  
- **Download Time**: ~5-10 seconds
- **Total Overhead**: ~20-30 seconds per PR 