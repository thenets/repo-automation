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
from .conftest import GitHubTestManager, GitHubFixtures


@pytest.mark.integration
class TestFeatureBranchLabeler(GitHubFixtures):
    """Integration test cases for the feature branch auto-labeler workflow."""

    @pytest.mark.fork_compatibility
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
some_other_field: value
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


@pytest.mark.integration
class TestFeatureBranchErrorReporting(GitHubFixtures):
    """Integration test cases for the feature branch auto-labeler error reporting functionality."""

    def test_validation_error_comment_lifecycle(self, test_repo, integration_manager):
        """Test the complete lifecycle of validation error comments: creation and auto-removal.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block containing invalid needs_feature_branch value
        5. Wait for triage label (should still be added by separate workflow)
        6. Verify the validation error comment is posted to the PR
        7. Change the PR description to add valid YAML code block
        8. Validate the comment will be removed
        9. Cleanup PR

        Note: This test verifies that invalid values cause the workflow to post
        a validation error comment explaining what went wrong and how to fix it,
        and that the comment is automatically removed when the YAML is corrected.
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-validation-comment-lifecycle-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_validation_lifecycle.md"
        content = """# Test File - Validation Comment Lifecycle

This file contains changes to test the complete lifecycle of validation error comments.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for validation comment lifecycle", ["test_validation_lifecycle.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block containing invalid needs_feature_branch value
        pr_body = """This PR tests the complete lifecycle of validation error comments.

```yaml
needs_feature_branch: maybe_invalid_value  # Invalid value not in accepted list (true/false)
```

The value above is not in the accepted list and should create a validation error comment."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test validation error comment lifecycle (create + auto-remove)",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from the existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait for validation error comment to be posted
        validation_comment_posted = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error: feature branch"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert validation_comment_posted, f"Validation error comment was not posted to PR #{pr_number}"

        # Verify no feature-branch label is present (validation failed)
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert not has_feature_branch_label, (
            f"Feature-branch label should not be present due to validation failure for PR #{pr_number}"
        )

        # Verify the specific invalid values mentioned in the comment
        comments = integration_manager.get_pr_comments(repo_path, pr_number)
        error_comment = None
        for comment in comments:
            if "🚨 YAML Validation Error: feature branch" in comment.get("body", ""):
                error_comment = comment.get("body", "")
                break

        assert error_comment is not None, "Could not find the validation error comment"
        assert "Invalid needs_feature_branch value: \"maybe_invalid_value\"" in error_comment, "Error comment should mention invalid value"
        assert "How to fix:" in error_comment, "Error comment should provide fix instructions"
        assert "Valid YAML format:" in error_comment, "Error comment should provide example YAML"
        assert "keeper-feature-branch-auto-labeling workflow" in error_comment, "Error comment should mention the workflow"

        # Update PR description with valid YAML
        valid_pr_body = """This PR tests that validation error comments are auto-deleted when YAML is fixed.

```yaml
needs_feature_branch: true  # Valid value
```

The value above is now valid and should cause the error comment to be automatically deleted."""

        # Update the PR description
        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", valid_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Wait for validation error comment to be removed
        comment_removed = integration_manager.poll_until_condition(
            lambda: not integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error: feature branch"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert comment_removed, f"Validation error comment was not automatically removed from PR #{pr_number}"

        # Verify that valid label was added
        feature_branch_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "feature-branch"),
            timeout=60,
            poll_interval=5,
        )

        assert feature_branch_label_added, f"Feature-branch label was not added after fixing YAML for PR #{pr_number}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_no_yaml_comment_cleanup(self, test_repo, integration_manager):
        """Test that error comments are cleaned up when YAML is removed entirely.

        Steps:
        1. Create PR with invalid YAML -> error comment posted
        2. Edit PR to remove YAML entirely -> error comment removed
        3. Verify workflow succeeds
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-no-yaml-cleanup-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_no_yaml_cleanup.md"
        content = """# Test No YAML Cleanup

This file tests cleanup when YAML is removed entirely.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for no YAML cleanup",
            ["test_no_yaml_cleanup.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with invalid YAML
        invalid_pr_body = """This PR tests cleanup when YAML is removed.

```yaml
needs_feature_branch: invalid_value
```

This should trigger an error comment."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test No YAML Comment Cleanup",
            invalid_pr_body,
            branch_name,
        )

        # Wait for error comment to be posted
        error_comment_posted = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error: feature branch"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert error_comment_posted, f"Validation error comment was not posted to PR #{pr_number}"

        # Edit PR description to remove YAML entirely
        no_yaml_pr_body = """This PR now has no YAML.

The YAML block has been removed, so the error comment should be cleaned up."""

        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", no_yaml_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Wait for error comment to be removed
        error_comment_removed = integration_manager.poll_until_condition(
            lambda: not integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error: feature branch"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert error_comment_removed, f"Validation error comment was not removed from PR #{pr_number}"

        # Verify no feature-branch label was added (no YAML = no labeling)
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert not has_feature_branch_label, (
            f"Feature-branch label should not be added when no YAML is present for PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_existing_label_comment_cleanup(self, test_repo, integration_manager):
        """Test that error comments are cleaned up when feature-branch label already exists.

        Steps:
        1. Create PR with invalid YAML
        2. Manually add feature-branch label
        3. Edit PR description to trigger workflow again
        4. Verify error comment is cleaned up due to existing label
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "feature-branch", "FF6600", "Feature Branch"
        )

        # Create a new branch
        branch_name = f"test-existing-label-cleanup-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_existing_label_cleanup.md"
        content = """# Test Existing Label Cleanup

This file tests cleanup when feature-branch label already exists.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for existing label cleanup",
            ["test_existing_label_cleanup.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with invalid YAML
        invalid_pr_body = """This PR tests cleanup when feature-branch label exists.

```yaml
needs_feature_branch: invalid_value
```

This should trigger an error comment initially."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test Existing Label Comment Cleanup",
            invalid_pr_body,
            branch_name,
        )

        # Wait for error comment to be posted
        error_comment_posted = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error: feature branch"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert error_comment_posted, f"Validation error comment was not posted to PR #{pr_number}"

        # Manually add feature-branch label
        integration_manager.add_labels_to_pr(repo_path, pr_number, ["feature-branch"])

        # Edit PR description to trigger workflow again (keep invalid YAML)
        still_invalid_pr_body = """This PR tests cleanup when feature-branch label exists.

```yaml
needs_feature_branch: still_invalid_value
```

The error comment should be cleaned up because the label already exists."""

        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", still_invalid_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Wait for error comment to be removed (despite invalid YAML, label exists)
        error_comment_removed = integration_manager.poll_until_condition(
            lambda: not integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error: feature branch"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert error_comment_removed, f"Validation error comment was not removed when feature-branch label exists on PR #{pr_number}"

        # Verify feature-branch label is still present
        has_feature_branch_label = integration_manager.pr_has_label(
            repo_path, pr_number, "feature-branch"
        )
        assert has_feature_branch_label, (
            f"Feature-branch label should still be present on PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)
