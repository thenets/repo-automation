"""
Test suite for label validation scenarios in GitHub Actions workflows.

This test validates that workflows properly fail when YAML in PR descriptions
references labels that don't exist in the repository.

These tests use real GitHub API calls to validate actual workflow failure behavior.
"""

import subprocess
import time

import pytest

from .conftest import GitHubFixtures


@pytest.mark.integration
class TestLabelValidation(GitHubFixtures):
    """Test label validation logic using real GitHub API calls."""

    @pytest.fixture(scope="class")
    def test_repo_with_labels(self, github_manager_class):
        """Create a test repository with some labels present and others missing."""
        # Create unique repository name per thread for parallel execution
        repo_name = self.generate_unique_name("test-label-validation")

        # Create temporary local repository
        repo_path = github_manager_class.create_temp_repo(repo_name)

        # Create some valid labels that workflows can use
        github_manager_class.create_label(
            repo_path, "triage", "FFFF00", "Needs triage"
        )
        github_manager_class.create_label(
            repo_path, "stale", "808080", "Stale issue/PR"
        )
        github_manager_class.create_label(
            repo_path, "feature-branch", "00FF00", "Feature branch needed"
        )
        # Add some valid release labels
        github_manager_class.create_label(
            repo_path, "release 1.0", "00FF00", "Release 1.0"
        )
        github_manager_class.create_label(
            repo_path, "backport 1.0", "0000FF", "Backport 1.0"
        )

        # Note: We intentionally DON'T create:
        # - "release invalid-version"
        # - "backport invalid-version"
        # These will be used to test workflow failure scenarios

        yield repo_path

        # Cleanup: remove temporary directory
        subprocess.run(["rm", "-rf", str(repo_path)], check=False)

    @pytest.mark.fork_compatibility
    def test_workflow_fails_with_invalid_release_label(
        self, test_repo_with_labels, github_manager_class
    ):
        """Test release/backport workflow fails when YAML references invalid release."""
        repo_path = test_repo_with_labels

        # Create a test PR with invalid release value in YAML
        branch_name = f"test-invalid-release-{int(time.time())}"
        github_manager_class.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content +
            f"\n\n## Test Invalid Release {int(time.time())}\n\n"
            f"Testing workflow failure with invalid release label.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        github_manager_class.git_commit_and_push(
            repo_path, "Test invalid release label", ["TESTING.md"]
        )
        github_manager_class.push_branch(repo_path, branch_name)

        # Create PR with YAML containing invalid release value
        pr_description = """
This PR tests workflow failure with invalid release value.

```yaml
release: invalid-version  # This should cause workflow to fail
backport: 1.0            # This is valid
```

The workflow should fail because 'invalid-version' is not in the accepted releases list.
"""

        pr_number = github_manager_class.create_pr(
            repo_path,
            "Test PR with invalid release label",
            pr_description,
            branch_name,
        )

        # Wait for triage label to be added (this should work)
        label_added = github_manager_class.poll_until_condition(
            lambda: github_manager_class.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )
        assert label_added, f"Triage label should be added to PR #{pr_number}"

        # Wait a bit more for the release/backport workflow to process
        time.sleep(60)

        # Verify that no invalid release label was added
        labels = github_manager_class.get_pr_labels(repo_path, pr_number)
        assert "release invalid-version" not in labels, (
            f"Invalid release label should not be added to PR #{pr_number}"
        )

        # The valid backport label should also not be added because the workflow failed
        assert "backport 1.0" not in labels, (
            "Backport label should not be added when workflow fails "
            "due to invalid release"
        )

        # Only triage label should be present
        assert "triage" in labels, f"Triage label should be present on PR #{pr_number}"

        # Cleanup
        github_manager_class.close_pr(repo_path, pr_number, delete_branch=True)

    def test_workflow_fails_with_invalid_backport_label(
        self, test_repo_with_labels, github_manager_class
    ):
        """Test release/backport workflow fails when YAML has invalid backport."""
        repo_path = test_repo_with_labels

        # Create a test PR with invalid backport value in YAML
        branch_name = f"test-invalid-backport-{int(time.time())}"
        github_manager_class.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content +
            f"\n\n## Test Invalid Backport {int(time.time())}\n\n"
            f"Testing workflow failure with invalid backport label.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        github_manager_class.git_commit_and_push(
            repo_path, "Test invalid backport label", ["TESTING.md"]
        )
        github_manager_class.push_branch(repo_path, branch_name)

        # Create PR with YAML containing invalid backport value
        pr_description = """
This PR tests workflow failure with invalid backport value.

```yaml
release: 1.0                    # This is valid
backport: invalid-backport      # This should cause workflow to fail
```

The workflow should fail because 'invalid-backport' is not in the accepted
backports list.
"""

        pr_number = github_manager_class.create_pr(
            repo_path,
            "Test PR with invalid backport label",
            pr_description,
            branch_name,
        )

        # Wait for triage label to be added (this should work)
        label_added = github_manager_class.poll_until_condition(
            lambda: github_manager_class.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )
        assert label_added, f"Triage label should be added to PR #{pr_number}"

        # Wait a bit more for the release/backport workflow to process
        time.sleep(60)

        # Verify that no invalid backport label was added
        labels = github_manager_class.get_pr_labels(repo_path, pr_number)
        assert "backport invalid-backport" not in labels, (
            f"Invalid backport label should not be added to PR #{pr_number}"
        )

        # The valid release label should also not be added because the workflow failed
        assert "release 1.0" not in labels, (
            "Release label should not be added when workflow fails "
            "due to invalid backport"
        )

        # Only triage label should be present
        assert "triage" in labels, f"Triage label should be present on PR #{pr_number}"

        # Cleanup
        github_manager_class.close_pr(repo_path, pr_number, delete_branch=True)

    def test_workflow_fails_with_invalid_feature_branch_value(
        self, test_repo_with_labels, github_manager_class
    ):
        """Test feature branch workflow fails when YAML has invalid boolean value."""
        repo_path = test_repo_with_labels

        # Create a test PR with invalid feature branch value in YAML
        branch_name = f"test-invalid-feature-{int(time.time())}"
        github_manager_class.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content +
            f"\n\n## Test Invalid Feature Branch {int(time.time())}\n\n"
            f"Testing workflow failure with invalid feature branch value.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        github_manager_class.git_commit_and_push(
            repo_path, "Test invalid feature branch value", ["TESTING.md"]
        )
        github_manager_class.push_branch(repo_path, branch_name)

        # Create PR with YAML containing invalid feature branch value
        pr_description = """
This PR tests workflow failure with invalid feature branch value.

```yaml
needs_feature_branch: invalid-boolean  # This should cause workflow to fail
```

The workflow should fail because 'invalid-boolean' is not a valid boolean (true/false).
"""

        pr_number = github_manager_class.create_pr(
            repo_path,
            "Test PR with invalid feature branch value",
            pr_description,
            branch_name,
        )

        # Wait for triage label to be added (this should work)
        label_added = github_manager_class.poll_until_condition(
            lambda: github_manager_class.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )
        assert label_added, f"Triage label should be added to PR #{pr_number}"

        # Wait a bit more for the feature branch workflow to process
        time.sleep(60)

        # Verify that feature-branch label was NOT added (workflow should fail)
        labels = github_manager_class.get_pr_labels(repo_path, pr_number)
        assert "feature-branch" not in labels, (
            "Feature-branch label should not be added when workflow fails "
            "due to invalid boolean value"
        )

        # Only triage label should be present
        assert "triage" in labels, f"Triage label should be present on PR #{pr_number}"

        # Cleanup
        github_manager_class.close_pr(repo_path, pr_number, delete_branch=True)
