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
    def test_hello(self, github_manager):
        """Test basic functionality of the GitHubTestManager class."""
        # Create a temporary repository using the existing repo-automations as remote
        # Generate thread-safe unique repo name for parallel execution
        repo_name = self.generate_unique_name("test-hello")
        repo_path = github_manager.create_temp_repo(repo_name)

        # Verify the repository was created and exists
        assert repo_path.exists()
        assert (repo_path / ".git").exists()

        # Create a test branch
        branch_name = f"test-branch-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        # Modify a file (TESTING.md)
        testing_file = repo_path / "TESTING.md"
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

        # Verify the PR was created by checking its labels
        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels: {labels}")

        # Clean up: close the PR and delete the branch
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

        # Clean up: remove temporary directory
        subprocess.run(["rm", "-rf", str(repo_path)], check=False)
