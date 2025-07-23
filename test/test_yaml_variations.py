"""
Test suite for YAML variations support in GitHub Actions workflows.

This test validates that the workflows correctly handle:
1. Quoted values for release and backport
2. Case-insensitive boolean values for needs_feature_branch
"""

import time
import pytest
from .conftest import GitHubTestManager, GitHubFixtures


@pytest.mark.integration
class TestYAMLVariations(GitHubFixtures):
    """Integration test cases for YAML variations support."""

    def test_quoted_release_backport_values(self, test_repo, integration_manager):
        """Test that PR with quoted release/backport values works correctly.

        This test validates the fix for issue #65 - quoted values support.
        
        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with quoted YAML values in description
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
            repo_path, "backport 2.2", "00FF00", "Backport to 2.2"
        )

        # Create a new branch
        branch_name = f"test-quoted-values-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_quoted_values.md"
        content = """# Test File for Quoted Values

This file tests quoted YAML values parsing.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for quoted values", ["test_quoted_values.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with quoted YAML values in description (simulates issue #65 example)
        pr_body = """This PR tests quoted release/backport values parsing.

```yaml
release: "devel"
backport: "2.2"
```

This should work with the updated workflow."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with quoted YAML values",
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
                repo_path, pr_number, "backport 2.2"
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
        assert "backport 2.2" in labels, (
            f"Expected 'backport 2.2' label on PR #{pr_number}, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_case_insensitive_boolean_values(self, test_repo, integration_manager):
        """Test that PR with case-insensitive boolean values works correctly.

        This test validates the fix for issue #65 - boolean case sensitivity.
        
        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with uppercase boolean YAML value in description
        5. Wait for feature-branch label to be added
        6. Verify feature-branch label is present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required label exists
        integration_manager.create_label(
            repo_path, "feature-branch", "FFFF00", "Feature branch required"
        )

        # Create a new branch
        branch_name = f"test-boolean-case-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_boolean_case.md"
        content = """# Test File for Boolean Case

This file tests case-insensitive boolean parsing.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for boolean case", ["test_boolean_case.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with uppercase boolean value in description (simulates issue #65 example)
        pr_body = """This PR tests case-insensitive boolean parsing.

```yaml
needs_feature_branch: False
```

This should work with the updated workflow (False should be treated as false)."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with uppercase boolean",
            pr_body,
            branch_name,
        )

        # Wait briefly to ensure the workflow processes the PR
        # Since needs_feature_branch is False, no feature-branch label should be added
        # We'll wait for the triage label to confirm the workflow ran
        triage_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(repo_path, pr_number, "triage"),
            timeout=120,
            poll_interval=5,
        )

        assert triage_label_added, f"Triage label was not added to PR #{pr_number}"

        # Verify NO feature-branch label was added (since value is False)
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        assert "feature-branch" not in labels, (
            f"Feature-branch label should NOT be added when needs_feature_branch is False, but got: {labels}"
        )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)

    def test_mixed_variations_support(self, test_repo, integration_manager):
        """Test that PR with mixed quote/case variations works correctly.

        This comprehensive test validates multiple variations in a single PR.
        
        Steps:
        1. Create a new branch
        2. Create a simple file change
        3. Commit and push changes
        4. Create PR with mixed variations YAML in description
        5. Wait for all appropriate labels to be added
        6. Verify correct labels are present
        7. Cleanup PR
        """
        repo_path = test_repo

        # Ensure required labels exist
        integration_manager.create_label(
            repo_path, "release 1.0", "FF0000", "Release 1.0"
        )
        integration_manager.create_label(
            repo_path, "backport 1.1", "00FF00", "Backport to 1.1"
        )
        integration_manager.create_label(
            repo_path, "feature-branch", "FFFF00", "Feature branch required"
        )

        # Create a new branch
        branch_name = f"test-mixed-variations-{int(time.time())}"
        integration_manager.create_branch(repo_path, branch_name)

        # Create a simple file change
        test_file = repo_path / "test_mixed_variations.md"
        content = """# Test File for Mixed Variations

This file tests multiple YAML variations in one PR.
"""
        test_file.write_text(content)

        # Commit and push changes
        integration_manager.git_commit_and_push(
            repo_path, "Add test file for mixed variations", ["test_mixed_variations.md"]
        )
        integration_manager.push_branch(repo_path, branch_name)

        # Create PR with mixed variations in description
        pr_body = """This PR tests multiple YAML variations support.

```yaml
release: '1.0'             # Single quotes
backport: "1.1"            # Double quotes  
needs_feature_branch: TRUE # Uppercase boolean
```

All these variations should be handled correctly."""

        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR with mixed YAML variations",
            pr_body,
            branch_name,
        )

        # Wait for all labels to be added
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

        feature_label_added = integration_manager.poll_until_condition(
            lambda: integration_manager.pr_has_label(
                repo_path, pr_number, "feature-branch"
            ),
            timeout=120,
            poll_interval=5,
        )

        assert release_label_added, f"Release label was not added to PR #{pr_number}"
        assert backport_label_added, f"Backport label was not added to PR #{pr_number}"
        assert feature_label_added, f"Feature-branch label was not added to PR #{pr_number}"

        # Verify all labels are indeed present
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        expected_labels = ["release 1.0", "backport 1.1", "feature-branch"]
        
        for expected_label in expected_labels:
            assert expected_label in labels, (
                f"Expected '{expected_label}' label on PR #{pr_number}, but got: {labels}"
            )

        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True) 