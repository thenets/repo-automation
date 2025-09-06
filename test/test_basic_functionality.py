"""
Test suite for basic functionality tests.

This test module contains basic functionality tests that don't require GitHub integration.
"""

import subprocess
import time
from pathlib import Path

import pytest

from .conftest import GitHubFixtures


class TestBasicFunctionality(GitHubFixtures):
    """Basic functionality tests that don't require GitHub integration."""

    @pytest.mark.fork_compatibility
    def test_hello(self, test_repo, github_manager):
        """Test basic functionality of the GitHubTestManager class."""
        # Use the session-initialized test repository
        repo_path = test_repo

        # Verify the repository was created and exists
        assert repo_path.exists()
        assert (repo_path / ".git").exists()

        # Create a test branch
        branch_name = f"test-branch-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        # Modify a file (TESTING.md)
        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Basic Functionality {int(time.time())}\n\nThis is a test from test_hello.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push the changes
        github_manager.git_commit_and_push(
            repo_path, "Test basic functionality from test_hello", ["TESTING.md"]
        )

        # Create a PR
        pr_number = github_manager.create_pr(
            repo_path,
            "Test PR from test_hello",
            "This PR tests basic functionality from the test_hello method.",
            branch_name,
        )

        print(f"Created PR #{pr_number}")

        # Wait for the triage label to be added (this tests the automation)
        print(f"Waiting for triage label to be added to PR #{pr_number}...")
        triage_added = github_manager.poll_until_condition(
            lambda: github_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=30,  # Wait up to 30 seconds
            poll_interval=5  # Check every 5 seconds
        )
        
        if triage_added:
            print(f"✅ Triage label successfully added to PR #{pr_number}")
        else:
            print(f"⚠️ Triage label was not added to PR #{pr_number} within timeout")

        # Verify the PR labels after automation runs
        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} final labels: {labels}")
        
        # Assert that the triage label was added (test will fail if not present)
        assert triage_added, f"Triage label was not added to PR #{pr_number} within timeout"
        assert "triage" in labels, f"Triage label not found in PR #{pr_number} labels: {labels}"

        # Clean up: close the PR and delete the branch
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

        # Clean up: remove temporary directory
        subprocess.run(["rm", "-rf", str(repo_path)], check=False)
