"""
Test suite for the release and backport auto-labeler GitHub Actions workflow.

This test validates that the workflow automatically adds release and backport labels
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
class TestReleaseBackportLabeler(GitHubFixtures):
    """Integration test cases for the release and backport auto-labeler workflow."""

    def test_yaml_code_block_labeling(self, test_repo, integration_manager):
        """Test that PR with YAML code block in description gets appropriate labels.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block in description
        5. Wait for labels to be added
        6. Verify correct labels are present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 1.5", "00FF00", "Release 1.5"
        )
        integration_manager.create_label(
            repo_path, "backport 1.4", "0000FF", "Backport to 1.4"
        )

        # Create a new branch
        branch_name = f"test-yaml-code-block-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_change.md"
        content = """# Test File

This file contains a simple change for testing PR labeling.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for PR labeling", ["test_change.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block in description
        pr_body = """This PR tests automatic labeling based on YAML code blocks in the PR description.

```yaml
release: 1.5
backport: 1.4
```

The changes are backward compatible."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with YAML code block",
            pr_body,
            branch_name,
        )

        # Wait for labels to be added
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.5"
            ),
            timeout=120,
            poll_interval=5,
        )

        backport_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "backport 1.4"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"
        assert backport_label_added, f"Backport label was not added to PR #{pr_number}"

        # Verify the labels are indeed present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 1.5" in labels, (
            f"Expected 'release 1.5' label on PR #{pr_number}, but got: {labels}"
        )
        assert "backport 1.4" in labels, (
            f"Expected 'backport 1.4' label on PR #{pr_number}, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_yaml_with_devel_release_labeling(self, test_repo, integration_manager):
        """Test that PR with YAML code block using 'devel' release gets appropriate labels.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block in description (using 'devel' release)
        5. Wait for labels to be added
        6. Verify correct labels are present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release devel", "FF0000", "Release devel"
        )
        integration_manager.create_label(
            repo_path, "backport 1.5", "00FFFF", "Backport to 1.5"
        )

        # Create a new branch
        branch_name = f"test-yaml-devel-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_devel.md"
        content = """# Test File for Devel Release

This file contains changes for development release.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for devel release", ["test_devel.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block in description
        pr_body = """This PR tests automatic labeling for development releases.

```yaml
release: devel
backport: 1.5
```

These changes are for the development branch."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with devel release YAML",
            pr_body,
            branch_name,
        )

        # Wait for labels to be added
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release devel"
            ),
            timeout=120,
            poll_interval=5,
        )

        backport_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "backport 1.5"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"
        assert backport_label_added, f"Backport label was not added to PR #{pr_number}"

        # Verify the labels are indeed present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release devel" in labels, (
            f"Expected 'release devel' label on PR #{pr_number}, but got: {labels}"
        )
        assert "backport 1.5" in labels, (
            f"Expected 'backport 1.5' label on PR #{pr_number}, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.parametrize(
        "yaml_format,test_description",
        [
            ("clean", "without comments"),
            ("with_comments", "with hash comments"),
        ],
    )
    def test_yaml_code_block_edit_description(
        self, test_repo, integration_manager, yaml_format, test_description
    ):
        """Test that editing the PR description with a YAML code block updates the labels.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with no YAML code block in description
        5. Edit the PR description with a YAML code block
           Parametrized to test:
            - YAML code block without '#' comment
            - YAML code block with '#' comment
        6. Verify correct labels are present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 1.0", "00FF00", "Release 1.0"
        )
        integration_manager.create_label(
            repo_path, "backport 1.1", "0000FF", "Backport to 1.1"
        )

        # Create a new branch
        branch_name = f"test-edit-description-{yaml_format}-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / f"test_edit_description_{yaml_format}.md"
        content = f"""# Test File - Edit Description {test_description}

This file contains changes to test PR description editing {test_description}.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            f"Add test file for description editing {test_description}",
            [f"test_edit_description_{yaml_format}.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with no YAML code block in description
        initial_pr_body = f"""This PR tests editing the description to add YAML code blocks {test_description}.

No YAML configuration initially."""

        pr_number = integration_manager.create_pr(
            repo_path,
            f"Test PR for description editing {test_description}",
            initial_pr_body,
            branch_name,
        )

        # Wait for triage label to be added (from existing triage workflow)
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Verify no release/backport labels initially
        initial_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        release_labels = [
            label for label in initial_labels if label.startswith("release")
        ]
        backport_labels = [
            label for label in initial_labels if label.startswith("backport")
        ]

        assert len(release_labels) == 0, (
            f"Expected no release labels initially, got: {release_labels}"
        )
        assert len(backport_labels) == 0, (
            f"Expected no backport labels initially, got: {backport_labels}"
        )

        # Prepare the YAML content based on the parameter
        if yaml_format == "clean":
            yaml_content = """```yaml
release: 1.0
backport: 1.1
```"""
            description_suffix = "This should add the release and backport labels."
        elif yaml_format == "with_comments":
            yaml_content = """```yaml
release: 1.0#this is a comment
backport: 1.1#another comment
```"""
            description_suffix = "The '#' character and everything after it should be removed by the current implementation."

        # Update the PR description with the parameterized YAML content
        updated_pr_body = f"""This PR tests editing the description to add YAML code blocks {test_description}.

{yaml_content}

{description_suffix}"""

        # Update the PR description
        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", updated_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Wait for labels to be added
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.0"
            ),
            timeout=120,
            poll_interval=5,
        )

        backport_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "backport 1.1"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert release_label_added, (
            f"Release label was not added after description update to PR #{pr_number} ({test_description})"
        )
        assert backport_label_added, (
            f"Backport label was not added after description update to PR #{pr_number} ({test_description})"
        )

        # Verify the labels are present
        updated_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 1.0" in updated_labels, (
            f"Expected 'release 1.0' label after update ({test_description}), got: {updated_labels}"
        )
        assert "backport 1.1" in updated_labels, (
            f"Expected 'backport 1.1' label after update ({test_description}), got: {updated_labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_release_only_labeling(self, test_repo, integration_manager):
        """Test that PR with only release info gets only release label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block containing only release info
        5. Wait for release label to be added
        6. Verify only release label is present (no backport)
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required label exists
        integration_manager.create_label(
            repo_path, "release 1.4", "FFFF00", "Release 1.4"
        )

        # Create a new branch
        branch_name = f"test-release-only-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_release_only.md"
        content = """# Test File - Release Only

This file contains changes for release only.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file with release info only", ["test_release_only.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block containing only release info
        pr_body = """This PR tests automatic labeling with only release information.

```yaml
release: 1.4
```

No backport is needed for this change."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with release only",
            pr_body,
            branch_name,
        )

        # Wait for release label to be added
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.4"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"

        # Verify the labels
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 1.4" in labels, (
            f"Expected 'release 1.4' label on PR #{pr_number}, but got: {labels}"
        )

        # Verify no backport labels are present
        backport_labels = [label for label in labels if label.startswith("backport")]
        assert len(backport_labels) == 0, (
            f"No backport labels should be present, but found: {backport_labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_no_yaml_no_labeling(self, test_repo, integration_manager):
        """Test that PR without YAML code block doesn't get release/backport labels.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR without YAML code block in description
        5. Wait for triage label (should still be added)
        6. Verify no release/backport labels are present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-no-yaml-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_no_yaml.md"
        content = """# Test File - No YAML

This file contains a simple change without any YAML configuration.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file without YAML", ["test_no_yaml.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR without YAML code block in description
        pr_body = """This PR tests that PRs without YAML code blocks don't get release/backport labels.

The changes are simple and don't require any specific labeling."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR without YAML",
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

        # Wait a bit more to ensure release/backport workflow has time to run
        time.sleep(10)

        # Verify no release/backport labels are present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        release_labels = [label for label in labels if label.startswith("release")]
        backport_labels = [label for label in labels if label.startswith("backport")]

        assert len(release_labels) == 0, (
            f"No release labels should be present, but found: {release_labels}"
        )
        assert len(backport_labels) == 0, (
            f"No backport labels should be present, but found: {backport_labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_invalid_yaml_no_labeling(self, test_repo, integration_manager):
        """Test that PR with invalid YAML code block doesn't get labels.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with malformed YAML code block in description
        5. Wait for triage label (should still be added)
        6. Verify no release/backport labels are present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-invalid-yaml-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_invalid_yaml.md"
        content = """# Test File - Invalid YAML

This file contains changes to test invalid YAML handling.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file with invalid YAML", ["test_invalid_yaml.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with malformed YAML code block in description
        pr_body = """This PR tests that malformed YAML code blocks don't get release/backport labels.

```yaml
release: 
backport
```

The YAML above is malformed and should be ignored."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with invalid YAML",
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

        # Wait a bit more to ensure release/backport workflow has time to run
        time.sleep(10)

        # Verify no release/backport labels are present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        release_labels = [label for label in labels if label.startswith("release")]
        backport_labels = [label for label in labels if label.startswith("backport")]

        assert len(release_labels) == 0, (
            f"No release labels should be present, but found: {release_labels}"
        )
        assert len(backport_labels) == 0, (
            f"No backport labels should be present, but found: {backport_labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_validation_error_comment_lifecycle(self, test_repo, integration_manager):
        """Test the complete lifecycle of validation error comments: creation and auto-removal.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block containing invalid tag values
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

        # Create PR with YAML code block containing invalid tag values
        pr_body = """This PR tests the complete lifecycle of validation error comments.

```yaml
release: 99.99  # Invalid release version not in accepted list
backport: invalid-branch  # Invalid backport target not in accepted list
```

The tags above are not in the accepted lists and should create a validation error comment."""

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
                repo_path, pr_number, "🚨 YAML Validation Error"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert validation_comment_posted, f"Validation error comment was not posted to PR #{pr_number}"

        # Verify no release/backport labels are present (validation failed)
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        release_labels = [label for label in labels if label.startswith("release")]
        backport_labels = [label for label in labels if label.startswith("backport")]

        assert len(release_labels) == 0, (
            f"No release labels should be present due to validation failure, but found: {release_labels}"
        )
        assert len(backport_labels) == 0, (
            f"No backport labels should be present due to validation failure, but found: {backport_labels}"
        )

        # Verify the specific invalid values mentioned in the comment
        comments = integration_manager.get_pr_comments(repo_path, pr_number)
        error_comment = None
        for comment in comments:
            if "🚨 YAML Validation Error" in comment.get("body", ""):
                error_comment = comment.get("body", "")
                break

        assert error_comment is not None, "Could not find the validation error comment"
        assert "Invalid release value: \"99.99\"" in error_comment, "Error comment should mention invalid release value"
        assert "Invalid backport value: \"invalid-branch\"" in error_comment, "Error comment should mention invalid backport value"
        assert "How to fix:" in error_comment, "Error comment should provide fix instructions"
        assert "Valid YAML format:" in error_comment, "Error comment should provide example YAML"

        # Step 7: Update PR description with valid YAML
        valid_pr_body = """This PR tests that validation error comments are auto-deleted when YAML is fixed.

```yaml
release: 1.5  # Valid release version
backport: 1.4  # Valid backport target
```

The tags above are now valid and should cause the error comment to be automatically deleted."""

        # Update the PR description
        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", valid_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Step 8: Wait for validation error comment to be removed
        comment_removed = integration_manager.poll_until_condition(
            lambda: not integration_manager.pr_has_comment_containing(
                repo_path, pr_number, "🚨 YAML Validation Error"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert comment_removed, f"Validation error comment was not automatically removed from PR #{pr_number}"

        # Verify that valid labels were added
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        final_release_labels = [label for label in final_labels if label.startswith("release")]
        final_backport_labels = [label for label in final_labels if label.startswith("backport")]

        assert "release 1.5" in final_labels, f"Expected 'release 1.5' label to be added, but found: {final_labels}"
        assert "backport 1.4" in final_labels, f"Expected 'backport 1.4' label to be added, but found: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_empty_tag_values_graceful_exit(self, test_repo, integration_manager):
        """Test that PR with empty release/backport values exits gracefully.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block containing empty tag values
        5. Wait for triage label (should still be added)
        6. Verify no release/backport labels are present (but workflow should succeed)
        7. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-empty-tags-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_empty_tags.md"
        content = """# Test File - Empty Tags

This file contains changes to test empty tag value handling.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file with empty tag values", ["test_empty_tags.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block containing empty tag values
        pr_body = """This PR tests that empty release/backport tag values exit gracefully.

```yaml
release:   # Empty release value
backport:  # Empty backport value
```

The empty values above should be handled gracefully without workflow failure."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with empty tag values",
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

        # Wait for release/backport workflow to process
        time.sleep(10)

        # Verify no release/backport labels are present (empty values should be ignored)
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        release_labels = [label for label in labels if label.startswith("release")]
        backport_labels = [label for label in labels if label.startswith("backport")]

        assert len(release_labels) == 0, (
            f"No release labels should be present with empty values, but found: {release_labels}"
        )
        assert len(backport_labels) == 0, (
            f"No backport labels should be present with empty values, but found: {backport_labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_existing_labels_preserved_on_description_update(
        self, test_repo, integration_manager
    ):
        """Test that existing release/backport labels are preserved when PR description is updated.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML code block
        5. Wait for initial labels to be added
        6. Update PR description with different YAML values
        7. Verify original labels are preserved
        8. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 1.2", "00FF00", "Release 1.2"
        )
        integration_manager.create_label(
            repo_path, "backport 1.1", "0000FF", "Backport to 1.1"
        )

        # Create a new branch
        branch_name = f"test-preserve-labels-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_preserve_labels.md"
        content = """# Test File - Preserve Labels

This file contains changes to test label preservation behavior.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Add test file for label preservation",
            ["test_preserve_labels.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with initial YAML code block
        initial_pr_body = """This PR tests that existing labels are preserved when description is updated.

```yaml
release: 1.2
backport: 1.1
```

Initial release and backport configuration."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for label preservation",
            initial_pr_body,
            branch_name,
        )

        # Wait for initial labels to be added
        initial_release_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.2"
            ),
            timeout=120,
            poll_interval=5,
        )

        initial_backport_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "backport 1.1"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert initial_release_added, (
            f"Initial release label was not added to PR #{pr_number}"
        )
        assert initial_backport_added, (
            f"Initial backport label was not added to PR #{pr_number}"
        )

        # Update PR description with different YAML values
        updated_pr_body = """This PR tests that existing labels are preserved when description is updated.

```yaml
release: 1.5  # This should be ignored since release 1.2 already exists
backport: 1.4  # This should be ignored since backport 1.1 already exists
```

Updated release and backport configuration (should be ignored)."""

        # Update the PR description (this simulates synchronize event)
        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", updated_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Wait for workflow to process the description update
        time.sleep(10)

        # Verify that the original labels are preserved (not overwritten)
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)

        # Original labels should still be present
        assert "release 1.2" in final_labels, (
            f"Original release label should be preserved, but got: {final_labels}"
        )
        assert "backport 1.1" in final_labels, (
            f"Original backport label should be preserved, but got: {final_labels}"
        )

        # New labels from updated description should NOT be added
        assert "release 1.5" not in final_labels, (
            f"New release label should not be added when existing label present"
        )
        assert "backport 1.4" not in final_labels, (
            f"New backport label should not be added when existing label present"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)
