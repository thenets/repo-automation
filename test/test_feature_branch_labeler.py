"""
Test suite for the feature branch auto-labeler GitHub Actions workflow.

This test validates that the workflow automatically adds feature-branch labels
to PRs based on YAML code blocks in the PR description.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest
from .test_triage_auto_add import GitHubTestManager, GitHubFixtures


@pytest.mark.integration
class TestFeatureBranchLabeler(GitHubFixtures):
    """Integration test cases for the feature branch auto-labeler workflow."""

    def test_needs_feature_branch_true_labeling(self, test_repo, integration_manager):
        """Test that PR with needs_feature_branch: true gets feature-branch label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with needs_feature_branch: true in YAML block
        5. Wait for labels to be added
        6. Verify feature-branch label is present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-feature-branch-true-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_feature_branch_true.md"
        content = """# Test Feature Branch True

This file contains changes to test feature branch labeling when needs_feature_branch is true.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for feature branch labeling (true)",
            ["test_feature_branch_true.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block indicating needs_feature_branch: true
        pr_body = """This PR tests feature branch labeling when needs_feature_branch is true.

```yaml
needs_feature_branch: true
release: 1.5
backport: 1.4
```

This should add the feature-branch label."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Feature Branch Labeling (true)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait for feature-branch label to be added
        feature_branch_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "feature-branch"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert feature_branch_label_added, (
            f"Feature-branch label was not added to PR #{pr_number}"
        )

        # Verify the label is present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "feature-branch" in labels, (
            f"Expected 'feature-branch' label, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_needs_feature_branch_false_no_labeling(
        self, test_repo, integration_manager
    ):
        """Test that PR with needs_feature_branch: false does not get feature-branch label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with needs_feature_branch: false in YAML block
        5. Wait for other labels to be added
        6. Verify feature-branch label is NOT present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-feature-branch-false-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_feature_branch_false.md"
        content = """# Test Feature Branch False

This file contains changes to test feature branch labeling when needs_feature_branch is false.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for feature branch labeling (false)",
            ["test_feature_branch_false.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block indicating needs_feature_branch: false
        pr_body = """This PR tests feature branch labeling when needs_feature_branch is false.

```yaml
needs_feature_branch: false
release: 1.5
backport: 1.4
```

This should NOT add the feature-branch label."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Feature Branch Labeling (false)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait a moment for any potential feature-branch label to be added
        time.sleep(30)

        # Verify the feature-branch label is NOT present
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert not has_feature_branch_label, (
            f"Feature-branch label should not be added when needs_feature_branch is false for PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_no_needs_feature_branch_field_no_labeling(
        self, test_repo, integration_manager
    ):
        """Test that PR without needs_feature_branch field does not get feature-branch label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML block but no needs_feature_branch field
        5. Wait for other labels to be added
        6. Verify feature-branch label is NOT present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-no-feature-branch-field-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_no_feature_branch_field.md"
        content = """# Test No Feature Branch Field

This file contains changes to test feature branch labeling when needs_feature_branch field is not present.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for feature branch labeling (no field)",
            ["test_no_feature_branch_field.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block but no needs_feature_branch field
        pr_body = """This PR tests feature branch labeling when needs_feature_branch field is not present.

```yaml
release: 1.5
backport: 1.4
```

This should NOT add the feature-branch label."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Feature Branch Labeling (no field)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait a moment for any potential feature-branch label to be added
        time.sleep(30)

        # Verify the feature-branch label is NOT present
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert not has_feature_branch_label, (
            f"Feature-branch label should not be added when needs_feature_branch field is not present for PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_invalid_needs_feature_branch_value_failure(
        self, test_repo, integration_manager
    ):
        """Test that PR with invalid needs_feature_branch value causes workflow to fail.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with invalid needs_feature_branch value
        5. Wait for triage label to be added
        6. Verify feature-branch label is NOT present (workflow should fail)
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-invalid-feature-branch-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_invalid_feature_branch.md"
        content = """# Test Invalid Feature Branch

This file contains changes to test feature branch labeling with invalid value.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for feature branch labeling (invalid)",
            ["test_invalid_feature_branch.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with invalid needs_feature_branch value
        pr_body = """This PR tests feature branch labeling with invalid needs_feature_branch value.

```yaml
needs_feature_branch: maybe
release: 1.5
backport: 1.4
```

This should cause the workflow to fail."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Feature Branch Labeling (invalid)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait a moment for any potential feature-branch label to be added
        time.sleep(30)

        # Verify the feature-branch label is NOT present (workflow should fail)
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert not has_feature_branch_label, (
            f"Feature-branch label should not be added when needs_feature_branch has invalid value for PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_empty_needs_feature_branch_value_no_labeling(
        self, test_repo, integration_manager
    ):
        """Test that PR with empty needs_feature_branch value does not get feature-branch label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with empty needs_feature_branch value
        5. Wait for other labels to be added
        6. Verify feature-branch label is NOT present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-empty-feature-branch-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_empty_feature_branch.md"
        content = """# Test Empty Feature Branch

This file contains changes to test feature branch labeling with empty value.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for feature branch labeling (empty)",
            ["test_empty_feature_branch.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with empty needs_feature_branch value
        pr_body = """This PR tests feature branch labeling with empty needs_feature_branch value.

```yaml
needs_feature_branch:
release: 1.5
backport: 1.4
```

This should NOT add the feature-branch label."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Feature Branch Labeling (empty)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait a moment for any potential feature-branch label to be added
        time.sleep(30)

        # Verify the feature-branch label is NOT present
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert not has_feature_branch_label, (
            f"Feature-branch label should not be added when needs_feature_branch is empty for PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_needs_feature_branch_with_comments_ignored(
        self, test_repo, integration_manager
    ):
        """Test that comments after # in needs_feature_branch value are ignored.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with needs_feature_branch: true#comment
        5. Wait for labels to be added
        6. Verify feature-branch label is present (comment ignored)
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-feature-branch-comments-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_feature_branch_comments.md"
        content = """# Test Feature Branch Comments

This file contains changes to test feature branch labeling with comments.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for feature branch labeling (comments)",
            ["test_feature_branch_comments.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with needs_feature_branch: true followed by comment
        pr_body = """This PR tests feature branch labeling with comments after the value.

```yaml
needs_feature_branch: true#this is a comment
release: 1.5
backport: 1.4
```

The comment should be ignored and feature-branch label should be added."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Feature Branch Labeling (with comments)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait for feature-branch label to be added
        feature_branch_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "feature-branch"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert feature_branch_label_added, (
            f"Feature-branch label was not added to PR #{pr_number} (comment should be ignored)"
        )

        # Verify the label is present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "feature-branch" in labels, (
            f"Expected 'feature-branch' label (comment ignored), but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_existing_feature_branch_label_preserved(
        self, test_repo, integration_manager
    ):
        """Test that existing feature-branch label is preserved and not overwritten.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with no YAML block
        5. Manually add feature-branch label
        6. Edit PR to include needs_feature_branch: false
        7. Verify feature-branch label is still present (preserved)
        8. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-preserve-feature-branch-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_preserve_feature_branch.md"
        content = """# Test Preserve Feature Branch

This file contains changes to test preserving existing feature-branch label.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for preserving feature branch label",
            ["test_preserve_feature_branch.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with no YAML block initially
        pr_body = """This PR tests preserving existing feature-branch label.

No YAML configuration initially."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Preserve Feature Branch Label",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Manually add feature-branch label
        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--add-label", "feature-branch"],
            cwd=repo_path,
            check=True,
        )

        # Verify feature-branch label was added
        feature_branch_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "feature-branch"
            ),
            timeout=60,
            poll_interval=3,
        )

        assert feature_branch_label_added, (
            f"Feature-branch label was not manually added to PR #{pr_number}"
        )

        # Edit PR to include needs_feature_branch: false
        updated_pr_body = """This PR tests preserving existing feature-branch label.

```yaml
needs_feature_branch: false
release: 1.5
backport: 1.4
```

The existing feature-branch label should be preserved."""

        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", updated_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Wait a moment for any potential label changes
        time.sleep(30)

        # Verify the feature-branch label is still present (preserved)
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert has_feature_branch_label, (
            f"Feature-branch label should be preserved even when needs_feature_branch is false for PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)
