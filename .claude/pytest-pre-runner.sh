#!/bin/bash

# Check if we're in the right directory (should have this repository structure)
if [[ ! -f "action.yml" ]] || [[ ! -d ".github/workflows" ]]; then
    exit 0  # Not in the right repository
fi

# Check if there are any changes to commit
if git diff-index --quiet HEAD --; then
    exit 0  # No changes to commit
fi

# Return JSON to instruct Claude Code to use the pytest-pre-runner agent
cat << 'EOF'
{
  "action": "block",
  "message": "🚨 Uncommitted changes detected before pytest execution. Using pytest-pre-runner agent to commit and push changes first so test repositories can access the latest workflow code.",
  "context": "A pytest command is about to run, but there are uncommitted changes. This repository's tests deploy workflows to external test repositories that need access to the latest code from the main branch."
}
EOF