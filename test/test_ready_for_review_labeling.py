"""
Test suite for the ready for review auto-labeling GitHub Actions workflow.

This test validates that the workflow automatically adds "ready for review" labels
to PRs that have release labels but no triage label.
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
class TestReadyForReviewLabeling(GitHubFixtures):
    """Test suite for keeper-ready-for-review-labeling.yml workflow"""

    def test_ready_for_review_label_added_when_conditions_met(self, test_repo, integration_manager):
        """Test that 'ready for review' label is added when PR has release label but no triage label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML that will trigger release labeling
        5. Wait for release label to be added
        6. Remove triage label manually
        7. Wait for ready for review label to be added
        8. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 1.5", "00FF00", "Release 1.5"
        )
        integration_manager.create_label(
            repo_path, "ready for review", "0E8A16", "PR is ready for team review"
        )

        # Create a new branch
        branch_name = f"test-ready-for-review-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_ready_for_review.md"
        content = """# Test Ready for Review

This file contains a simple change for testing ready for review labeling.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for ready for review labeling", ["test_ready_for_review.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block in description
        pr_body = """This PR adds new functionality.

```yaml
release: 1.5
```

Ready for team review."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test ready for review labeling",
            pr_body,
            branch_name,
        )

        # Wait for release label to be added (from release-backport workflow)
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.5"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"

        # Manually remove triage label to simulate condition for ready for review
        integration_manager.remove_labels_from_pr(repo_path, pr_number, ["triage"])

        # Wait for ready for review label to be added
        ready_for_review_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "ready for review"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert ready_for_review_label_added, f"Ready for review label was not added to PR #{pr_number}"

        # Verify final state: should have release label, no triage label, and ready for review label
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 1.5" in final_labels, f"Release label should be present: {final_labels}"
        assert "triage" not in final_labels, f"Triage label should not be present: {final_labels}"
        assert "ready for review" in final_labels, f"Ready for review label should be present: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_ready_for_review_not_added_when_triage_present(self, test_repo, integration_manager):
        """Test that 'ready for review' label is NOT added when PR still has triage label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with YAML that will trigger release labeling
        5. Wait for both release and triage labels to be added
        6. Wait to ensure ready for review workflow has time to run
        7. Verify ready for review label was NOT added
        8. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 2.1", "00FF00", "Release 2.1"
        )
        integration_manager.create_label(
            repo_path, "ready for review", "0E8A16", "PR is ready for team review"
        )

        # Create a new branch
        branch_name = f"test-no-ready-for-review-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_no_ready_for_review.md"
        content = """# Test No Ready for Review

This file contains a simple change for testing that ready for review is NOT added when triage is present.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for no ready for review with triage", ["test_no_ready_for_review.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with YAML code block in description
        pr_body = """This PR adds new functionality but still needs triage.

```yaml
release: 2.1
```

Still in triage process."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test ready for review NOT added with triage",
            pr_body,
            branch_name,
        )

        # Wait for release label to be added
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 2.1"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"

        # Wait for triage label to be added
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "triage"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Wait a bit more to ensure ready for review workflow has had time to run
        time.sleep(30)

        # Verify ready for review label was NOT added
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 2.1" in final_labels, f"Release label should be present: {final_labels}"
        assert "triage" in final_labels, f"Triage label should be present: {final_labels}"
        assert "ready for review" not in final_labels, f"Ready for review label should NOT be present: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_ready_for_review_not_added_without_release_label(self, test_repo, integration_manager):
        """Test that 'ready for review' label is NOT added when PR has no release label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR without YAML (no release label)
        5. Wait for triage label to be added
        6. Remove triage label manually
        7. Wait and verify ready for review label was NOT added
        8. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "ready for review", "0E8A16", "PR is ready for team review"
        )

        # Create a new branch
        branch_name = f"test-no-release-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_no_release.md"
        content = """# Test No Release

This file contains a simple change for testing that ready for review is NOT added without release label.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for no ready for review without release", ["test_no_release.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR without YAML code block (no release label)
        pr_body = """This PR adds new functionality but has no release labeling.

No YAML block here, so no release label will be added."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test no ready for review without release",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "triage"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Remove triage label to simulate one condition being met
        integration_manager.remove_labels_from_pr(repo_path, pr_number, ["triage"])

        # Wait and verify ready for review label was NOT added
        time.sleep(30)

        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        has_release = any(label.startswith('release ') for label in final_labels)
        has_ready_for_review = 'ready for review' in final_labels

        assert not has_release, f"No release label should be present: {final_labels}"
        assert not has_ready_for_review, f"Ready for review label should NOT be present without release label: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 