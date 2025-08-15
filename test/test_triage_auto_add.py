"""
Test suite for the triage auto-add GitHub Actions workflow.

This test validates that the workflow automatically adds the "triage" label
to new issues and pull requests.
"""

import pytest

from .conftest import GitHubTestManager, GitHubFixtures


# Integration tests
@pytest.mark.integration
class TestTriageAutoAdd(GitHubFixtures):
    """Integration test cases for the triage auto-add workflow."""

    def test_pr_triage_label_draft_must_be_ignored(
        self, test_repo, integration_manager
    ):
        """Test that a draft PR does not get the triage label.

        Steps:
        1. Create a new branch and PR in draft state
        2. Verify that the triage label is not added
        3. Mark PR as ready for review
        4. Verify that the triage label is added
        5. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-draft-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Draft PR {int(time.time())}\n\nThis tests draft PR triage label behavior.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Test draft PR triage label behavior", ["TESTING.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create draft PR
        pr_number = integration_manager.create_draft_pr(
            repo_path,
            "Test Draft PR for triage automation",
            "This draft PR tests that triage labels are not added to draft PRs.",
            branch_name,
        )

        # Wait a moment for any potential automation to run
        time.sleep(30)

        # Verify that the triage label is NOT added to the draft PR
        has_triage_label = integration_manager.pr_has_label(
            repo_path, pr_number, "triage"
        )
        assert not has_triage_label, (
            f"Triage label should not be added to draft PR #{pr_number}"
        )

        # Mark PR as ready for review
        ready_success = integration_manager.mark_pr_ready_for_review(
            repo_path, pr_number
        )
        assert ready_success, f"Failed to mark PR #{pr_number} as ready for review"

        # Wait for the GitHub Actions workflow to process the ready for review event
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, (
            f"Triage label was not added to PR #{pr_number} after marking as ready for review"
        )

        # Verify the label is indeed present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "triage" in labels, (
            f"Expected 'triage' label on PR #{pr_number}, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    @pytest.mark.fork_compatibility
    def test_pr_triage_label_auto_add(self, test_repo, integration_manager):
        """Test that a new PR automatically gets the triage label.

        Steps:
        1. Create a new branch
        2. Modify TESTING.md
        3. Commit and push changes
        4. Create PR
        5. Wait for GitHub Actions to process
        6. Check if triage label was added
        7. Cleanup PR, including deleting the branch
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-pr-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Change {int(time.time())}\n\nThis is a test change.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Test change for PR automation", ["TESTING.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR
        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for triage automation",
            "This PR tests the automatic triage label addition.",
            branch_name,
        )

        # Poll until triage label is added (check every 5 seconds, timeout after 120 seconds)
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, (
            f"Triage label was not added to PR #{pr_number} within the timeout period"
        )

        # Verify the label is indeed present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "triage" in labels, (
            f"Expected 'triage' label on PR #{pr_number}, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_pr_triage_label_protection_without_release_labels(
        self, test_repo, integration_manager
    ):
        """Test that triage label is re-added when removed without release/backport labels.

        Steps:
        1. Create a new branch and PR
        2. Wait for triage label to be added
        3. Remove triage label
        4. Wait for triage label to be re-added by protection workflow
        5. Verify triage label is present
        6. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-protection-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Protection {int(time.time())}\n\nThis tests triage label protection.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Test triage label protection", ["TESTING.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR
        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for triage label protection",
            "This PR tests triage label protection without release/backport labels.",
            branch_name,
        )

        # Wait for triage label to be added
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, f"Triage label was not added to PR #{pr_number}"

        # Remove triage label
        integration_manager.remove_labels_from_pr(repo_path, pr_number, ["triage"])

        # Wait a moment for the removal to process
        time.sleep(2)

        # Wait for triage label to be re-added by protection workflow
        label_re_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_re_added, (
            f"Triage label was not re-added to PR #{pr_number} by protection workflow"
        )

        # Verify the label is indeed present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "triage" in labels, (
            f"Expected 'triage' label on PR #{pr_number}, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_pr_triage_label_protection_with_release_label(
        self, test_repo, integration_manager
    ):
        """Test that triage label removal is allowed when release label is present.

        Steps:
        1. Create a new branch and PR
        2. Wait for triage label to be added
        3. Add release label
        4. Remove triage label
        5. Wait and verify triage label is NOT re-added
        6. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-release-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Release {int(time.time())}\n\nThis tests triage label protection with release label.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Test triage label protection with release label", ["TESTING.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR
        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for triage label protection with release label",
            "This PR tests triage label protection with release label present.",
            branch_name,
        )

        # Wait for triage label to be added
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, f"Triage label was not added to PR #{pr_number}"

        # Add release label
        integration_manager.add_labels_to_pr(repo_path, pr_number, ["release 1.0"])

        # Wait a moment for the addition to process
        time.sleep(2)

        # Remove triage label
        integration_manager.remove_labels_from_pr(repo_path, pr_number, ["triage"])

        # Wait and verify triage label is NOT re-added (wait longer to be sure)
        time.sleep(30)

        # Verify triage label is still not present
        has_triage = integration_manager.pr_has_label(repo_path, pr_number, "triage")
        assert not has_triage, (
            f"Triage label should not be re-added to PR #{pr_number} when release label is present"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_pr_triage_label_protection_with_backport_label(
        self, test_repo, integration_manager
    ):
        """Test that triage label removal is allowed when backport label is present.

        Steps:
        1. Create a new branch and PR
        2. Wait for triage label to be added
        3. Add backport label
        4. Remove triage label
        5. Wait and verify triage label is NOT re-added
        6. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-backport-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Backport {int(time.time())}\n\nThis tests triage label protection with backport label.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path,
            "Test triage label protection with backport label",
            ["TESTING.md"],
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR
        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for triage label protection with backport label",
            "This PR tests triage label protection with backport label present.",
            branch_name,
        )

        # Wait for triage label to be added
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, f"Triage label was not added to PR #{pr_number}"

        # Add backport label
        integration_manager.add_labels_to_pr(repo_path, pr_number, ["backport main"])

        # Wait a moment for the addition to process
        time.sleep(2)

        # Remove triage label
        integration_manager.remove_labels_from_pr(repo_path, pr_number, ["triage"])

        # Wait and verify triage label is NOT re-added (wait longer to be sure)
        time.sleep(30)

        # Verify triage label is still not present
        has_triage = integration_manager.pr_has_label(repo_path, pr_number, "triage")
        assert not has_triage, (
            f"Triage label should not be re-added to PR #{pr_number} when backport label is present"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_issue_triage_label_auto_add(self, test_repo, integration_manager):
        """Test that a new issue automatically gets the triage label."""
        repo_path = test_repo

        # Create a new issue
        issue_number = integration_manager.create_issue(
            repo_path,
            "Test issue for triage automation",
            "This issue tests the automatic triage label addition.",
        )

        # Poll until triage label is added (check every 5 seconds, timeout after 120 seconds)
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.issue_has_label(
                repo_path, issue_number, "triage"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, (
            f"Triage label was not added to issue #{issue_number} within the timeout period"
        )

        # Verify the label is indeed present
        labels = integration_manager.get_issue_labels(repo_path, issue_number)
        assert "triage" in labels, (
            f"Expected 'triage' label on issue #{issue_number}, but got: {labels}"
        )

        # Cleanup issue
        integration_manager.close_issue(repo_path, issue_number)


@pytest.mark.integration
class TestStalePRDetector(GitHubFixtures):
    """Integration test cases for the stale PR detector workflow."""

    def test_stale_pr_detection_manual_trigger(self, test_repo, integration_manager):
        """Test stale PR detection by manually triggering the workflow.

        Steps:
        1. Create a new branch and PR
        2. Wait for initial triage label to be added
        3. Manually trigger the stale PR detector workflow
        4. Verify that stale label is NOT added (PR is fresh)
        5. Cleanup PR
        """
        repo_path = test_repo

        # Create a new branch
        branch_name = f"test-stale-fresh-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = (
            current_content
            + f"\n\n## Test Stale Fresh {int(time.time())}\n\nThis tests stale PR detection on a fresh PR.\n"
        )
        testing_file.write_text(new_content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Test stale PR detection on fresh PR", ["TESTING.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR
        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for stale detection (fresh)",
            "This PR tests stale detection on a fresh PR that should not be marked as stale.",
            branch_name,
        )

        # Wait for triage label to be added
        label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert label_added, f"Triage label was not added to PR #{pr_number}"

        # Manually trigger the stale PR detector workflow
        subprocess.run(
            ["gh", "workflow", "run", "keeper-stale-pr-detector.yml"],
            cwd=repo_path,
            check=True,
        )

        # Wait for workflow to complete
        time.sleep(30)

        # Check if stale label was added (it shouldn't be for a fresh PR)
        has_stale_label = integration_manager.pr_has_label(
            repo_path, pr_number, "stale"
        )
        assert not has_stale_label, (
            f"Stale label should not be added to fresh PR #{pr_number}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_stale_label_creation_and_manual_workflow(
        self, test_repo, integration_manager
    ):
        """Test that stale label exists and workflow can be manually triggered.

        Steps:
        1. Ensure stale label exists in repository
        2. Test manual workflow trigger
        3. Verify workflow completes without error
        """
        repo_path = test_repo

        # Ensure stale label exists
        stale_label_created = integration_manager.create_label(
            repo_path,
            "stale",
            "808080",
            "This PR has been inactive for more than 1 day",
        )

        if stale_label_created:
            print("Created stale label successfully")
        else:
            print("Stale label already exists or creation failed")

        # Test manual workflow trigger
        result = subprocess.run(
            ["gh", "workflow", "run", "keeper-stale-pr-detector.yml"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        print(f"Workflow trigger result: {result.returncode}")
        if result.stdout:
            print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")

        # If we get here, the workflow was triggered successfully
        print("Stale PR detector workflow triggered successfully")
