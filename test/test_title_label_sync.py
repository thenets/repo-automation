"""
Test suite for Title-Label Sync feature.

This test module validates bi-directional synchronization between PR titles
and status labels (POC, WIP, HOLD).
"""

import subprocess
import time
from pathlib import Path

import pytest

from .conftest import GitHubFixtures


class TestTitleLabelSync(GitHubFixtures):
    """Test title-label synchronization feature."""

    @pytest.mark.fork_compatibility
    def test_title_with_wip_adds_label(self, test_repo, github_manager):
        """Test that creating a PR with [WIP] in title automatically adds 'wip' label."""
        repo_path = test_repo
        branch_name = f"test-wip-title-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        # Modify a file
        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test WIP Title {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test WIP title feature", ["TESTING.md"]
        )

        # Create PR with [WIP] in title
        pr_number = github_manager.create_pr(
            repo_path,
            "[WIP] Test PR with WIP indicator",
            "This PR should automatically get the 'wip' label",
            branch_name,
        )

        print(f"Created PR #{pr_number} with [WIP] in title")

        # Wait for the wip label to be added
        print(f"Waiting for wip label to be added to PR #{pr_number}...")
        wip_added = github_manager.poll_until_condition(
            lambda: github_manager.pr_has_label(repo_path, pr_number, "wip"),
            timeout=120,
            poll_interval=5
        )

        # Verify the label was added
        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels: {labels}")

        assert wip_added, f"'wip' label was not added to PR #{pr_number}"
        assert "wip" in labels, f"'wip' label not found in PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_title_with_multiple_indicators(self, test_repo, github_manager):
        """Test PR with multiple status indicators [WIP][HOLD] adds both labels."""
        repo_path = test_repo
        branch_name = f"test-multiple-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Multiple Indicators {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test multiple indicators", ["TESTING.md"]
        )

        # Create PR with both [WIP] and [HOLD]
        pr_number = github_manager.create_pr(
            repo_path,
            "[WIP][HOLD] Test PR with multiple indicators",
            "This PR should get both 'wip' and 'hold' labels",
            branch_name,
        )

        print(f"Created PR #{pr_number} with [WIP][HOLD] in title")

        # Wait for both labels (longer timeout for multiple label operations)
        print(f"Waiting for wip and hold labels...")
        both_labels_added = github_manager.poll_until_condition(
            lambda: (
                github_manager.pr_has_label(repo_path, pr_number, "wip") and
                github_manager.pr_has_label(repo_path, pr_number, "hold")
            ),
            timeout=120,
            poll_interval=5
        )

        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels: {labels}")

        assert both_labels_added, f"Both labels were not added to PR #{pr_number}"
        assert "wip" in labels and "hold" in labels, f"Missing labels in PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_case_insensitive_matching(self, test_repo, github_manager):
        """Test that [wip], [WIP], and [Wip] all create the 'wip' label."""
        repo_path = test_repo
        branch_name = f"test-case-insensitive-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Case Insensitive {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test case insensitive", ["TESTING.md"]
        )

        # Create PR with lowercase [poc]
        pr_number = github_manager.create_pr(
            repo_path,
            "[poc] Test case insensitive matching",
            "This PR uses lowercase [poc] but should get 'poc' label",
            branch_name,
        )

        print(f"Created PR #{pr_number} with [poc] in title")

        # Wait for poc label
        poc_added = github_manager.poll_until_condition(
            lambda: github_manager.pr_has_label(repo_path, pr_number, "poc"),
            timeout=120,
            poll_interval=5
        )

        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels: {labels}")

        assert poc_added, f"'poc' label was not added to PR #{pr_number}"
        assert "poc" in labels, f"'poc' label not found in PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_indicators_anywhere_in_title(self, test_repo, github_manager):
        """Test that status indicators work anywhere in title, not just prefix."""
        repo_path = test_repo
        branch_name = f"test-anywhere-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Anywhere {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test indicators anywhere", ["TESTING.md"]
        )

        # Create PR with indicator in the middle
        pr_number = github_manager.create_pr(
            repo_path,
            "Feature implementation [WIP] for testing",
            "This PR has [WIP] in the middle of the title",
            branch_name,
        )

        print(f"Created PR #{pr_number} with [WIP] in middle of title")

        # Wait for wip label
        wip_added = github_manager.poll_until_condition(
            lambda: github_manager.pr_has_label(repo_path, pr_number, "wip"),
            timeout=120,
            poll_interval=5
        )

        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels: {labels}")

        assert wip_added, f"'wip' label was not added to PR #{pr_number}"
        assert "wip" in labels, f"'wip' label not found in PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_edit_title_to_remove_indicator(self, test_repo, github_manager):
        """Test that removing [WIP] from title removes 'wip' label."""
        repo_path = test_repo
        branch_name = f"test-remove-indicator-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Remove Indicator {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test remove indicator", ["TESTING.md"]
        )

        # Create PR with [WIP]
        pr_number = github_manager.create_pr(
            repo_path,
            "[WIP] Feature to be completed",
            "This PR will have [WIP] removed from title",
            branch_name,
        )

        print(f"Created PR #{pr_number} with [WIP]")

        # Wait for wip label
        wip_added = github_manager.poll_until_condition(
            lambda: github_manager.pr_has_label(repo_path, pr_number, "wip"),
            timeout=120,
            poll_interval=5
        )
        assert wip_added, "Initial 'wip' label not added"

        # Update PR title to remove [WIP]
        print(f"Removing [WIP] from PR #{pr_number} title")
        github_manager.update_pr_title(repo_path, pr_number, "Feature completed")

        # Wait for wip label to be removed
        wip_removed = github_manager.poll_until_condition(
            lambda: not github_manager.pr_has_label(repo_path, pr_number, "wip"),
            timeout=120,
            poll_interval=5
        )

        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels after title update: {labels}")

        assert wip_removed, f"'wip' label was not removed from PR #{pr_number}"
        assert "wip" not in labels, f"'wip' label still present in PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_edit_title_to_add_indicator(self, test_repo, github_manager):
        """Test that adding [HOLD] to title adds 'hold' label."""
        repo_path = test_repo
        branch_name = f"test-add-indicator-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Add Indicator {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test add indicator", ["TESTING.md"]
        )

        # Create PR without status indicator
        pr_number = github_manager.create_pr(
            repo_path,
            "Feature implementation",
            "This PR will have [HOLD] added to title",
            branch_name,
        )

        print(f"Created PR #{pr_number} without status indicator")

        # Update PR title to add [HOLD]
        print(f"Adding [HOLD] to PR #{pr_number} title")
        github_manager.update_pr_title(repo_path, pr_number, "[HOLD] Feature implementation")

        # Wait for hold label to be added
        hold_added = github_manager.poll_until_condition(
            lambda: github_manager.pr_has_label(repo_path, pr_number, "hold"),
            timeout=120,
            poll_interval=5
        )

        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels after title update: {labels}")

        assert hold_added, f"'hold' label was not added to PR #{pr_number}"
        assert "hold" in labels, f"'hold' label not found in PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_invalid_indicator_ignored(self, test_repo, github_manager):
        """Test that invalid status indicators like [INVALID] are ignored."""
        repo_path = test_repo
        branch_name = f"test-invalid-{int(time.time())}"
        github_manager.create_branch(repo_path, branch_name)

        testing_file = github_manager.ensure_testing_file_exists(repo_path)
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Invalid Indicator {int(time.time())}\n"
        testing_file.write_text(new_content)

        github_manager.git_commit_and_push(
            repo_path, "Test invalid indicator", ["TESTING.md"]
        )

        # Create PR with invalid indicator
        pr_number = github_manager.create_pr(
            repo_path,
            "[INVALID] Test PR with invalid indicator",
            "This PR should not get an 'invalid' label",
            branch_name,
        )

        print(f"Created PR #{pr_number} with [INVALID] in title")

        # Wait a bit for automation to run
        time.sleep(15)

        # Check labels - should not have 'invalid' label
        labels = github_manager.get_pr_labels(repo_path, pr_number)
        print(f"PR #{pr_number} labels: {labels}")

        assert "invalid" not in labels, f"Invalid label should not be created for PR #{pr_number}"

        # Clean up
        github_manager.close_pr(repo_path, pr_number, delete_branch=True)
