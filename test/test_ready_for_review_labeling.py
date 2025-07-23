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
from .conftest import GitHubTestManager, GitHubFixtures


@pytest.mark.integration
class TestReadyForReviewLabeling(GitHubFixtures):
    """Test suite for keeper-ready-for-review-labeling.yml workflow"""

    def test_ready_for_review_label_added_when_conditions_met(self, test_repo, integration_manager):
        """Test that 'ready for review' label is added when PR has a release label and is not draft.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR WITHOUT YAML (no release labeling)
        5. Wait for triage label to be added initially
        6. Update PR to add YAML code block with a "release ?" label
        7. Remove the "triage" label
        8. Wait for ready for review label to be added
        9. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
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
No release information here - should get ready for review label.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for ready for review labeling", ["test_ready_for_review.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR WITHOUT YAML code block (no release label will be added)
        pr_body = """This PR adds new functionality.

No YAML block here initially, so no release label will be added.
Will be updated later to add release information."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test ready for review labeling",
            pr_body,
            branch_name,
        )

        # Wait for triage label to be added initially
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "triage"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Update PR to add YAML code block with a "release ?" label
        updated_pr_body = """This PR adds new functionality.

```yaml
release: 1.5
```

Now has release information, so should get ready for review label."""

        # Edit the PR description to add YAML
        subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body", updated_pr_body],
            cwd=repo_path,
            check=True,
        )

        # Ensure required release label exists
        integration_manager.create_label(
            repo_path, "release 1.5", "00FF00", "Release 1.5"
        )

        # Wait for release label to be added after PR description update
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.5"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number} after description update"

        # Remove the "triage" label
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

        # Verify final state: should have release label and ready for review label
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 1.5" in final_labels, f"Release label should be present: {final_labels}"
        assert "ready for review" in final_labels, f"Ready for review label should be present: {final_labels}"
        assert "triage" not in final_labels, f"Triage label should not be present: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_ready_for_review_when_created_with_release_label(self, test_repo, integration_manager):
        """Test that a PR with a release label gets the ready for review label.

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with release label
        5. Wait for ready for review label to be added
        6. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 2.0", "00FF00", "Release 2.0"
        )
        integration_manager.create_label(
            repo_path, "ready for review", "0E8A16", "PR is ready for team review"
        )

        # Create a new branch
        branch_name = f"test-release-ready-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_release_ready.md"
        content = """# Test Release Ready for Review

This file contains a simple change for testing ready for review with release label.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for release ready for review", ["test_release_ready.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with release label (YAML in description)
        pr_body = """This PR adds new functionality with release information.

```yaml
release: 2.0
```

Has release label from the start, should get ready for review label."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test ready for review with release label",
            pr_body,
            branch_name,
        )

        # Wait for release label to be added first
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 2.0"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"

        # Wait for ready for review label to be added
        ready_for_review_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "ready for review"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert ready_for_review_label_added, f"Ready for review label was not added to PR #{pr_number}"

        # Verify final state: should have both release and ready for review labels
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 2.0" in final_labels, f"Release label should be present: {final_labels}"
        assert "ready for review" in final_labels, f"Ready for review label should be present: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_draft_pr_gets_no_labels(self, test_repo, integration_manager):
        """Test that draft PRs get no labels (neither triage nor ready for review).

        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create DRAFT PR with release label
        5. Wait and verify NO labels are added
        6. Mark as ready for review
        7. Verify ready for review label is added
        8. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "ready for review", "0E8A16", "PR is ready for team review"
        )

        # Create a new branch
        branch_name = f"test-draft-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_draft.md"
        content = """# Test Draft PR

This file contains a simple change for testing draft PR behavior.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for draft PR", ["test_draft.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Ensure required release label exists
        integration_manager.create_label(
            repo_path, "release 1.0", "00FF00", "Release 1.0"
        )

        # Create DRAFT PR with YAML code block (has release label)
        pr_body = """This draft PR has release information.

```yaml
release: 1.0
```

Even though it has release info, it's a draft so should not get any labels initially."""

        pr_number = integration_manager.create_draft_pr(
            repo_path,
            "Test draft PR for labeling",
            pr_body,
            branch_name,
        )

        # Wait and verify NO labels are added to draft PR (even though it has release YAML)
        time.sleep(30)
        
        draft_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "triage" not in draft_labels, f"Draft PR should not have triage label: {draft_labels}"
        assert "ready for review" not in draft_labels, f"Draft PR should not have ready for review label: {draft_labels}"
        assert "release 1.0" not in draft_labels, f"Draft PR should not have release label: {draft_labels}"

        # Mark PR as ready for review
        ready_success = integration_manager.mark_pr_ready_for_review(repo_path, pr_number)
        assert ready_success, f"Failed to mark PR #{pr_number} as ready for review"

        # Wait for release label to be added first (now that it's not draft)
        release_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "release 1.0"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number} after marking as ready"

        # Wait for ready for review label to be added (since it has release label)
        ready_for_review_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "ready for review"
            ),
            timeout=120,
            poll_interval=10,
        )

        assert ready_for_review_label_added, f"Ready for review label was not added to PR #{pr_number} after marking as ready"

        # Verify final state: should have both release and ready for review labels
        final_labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "release 1.0" in final_labels, f"Release label should be present: {final_labels}"
        assert "ready for review" in final_labels, f"Ready for review label should be present: {final_labels}"

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 