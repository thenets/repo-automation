"""
Test suite for the triage auto-add GitHub Actions workflow.

This test validates that the workflow automatically adds the "triage" label
to new issues and pull requests.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest


class GitHubTestManager:
    """Manages Git and GitHub operations for testing."""

    def __init__(self, cache_dir: Path = Path("./cache/test/repo")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def clone_current_repo(self, target_name: str = "test-hello-repo") -> Path:
        """Clone the current git repo to cache directory."""
        current_repo = Path.cwd()
        clone_path = self.cache_dir / target_name

        # Clean up if exists
        if clone_path.exists():
            subprocess.run(["rm", "-rf", str(clone_path)], check=True)

        # Clone the current repository
        subprocess.run(["git", "clone", str(current_repo), str(clone_path)], check=True)

        return clone_path

    def create_temp_repo(self, repo_name: str) -> Path:
        """Create a temporary local repository that uses the existing repo-automations as remote."""
        repo_path = self.cache_dir / repo_name

        # Clean up if exists
        if repo_path.exists():
            subprocess.run(["rm", "-rf", str(repo_path)], check=True)

        # Clone the existing repo-automations repository
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/thenets/repo-automations.git",
                str(repo_path),
            ],
            check=True,
        )

        # Ensure we're on main branch
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)

        # Pull latest changes
        subprocess.run(["git", "pull", "origin", "main"], cwd=repo_path, check=True)

        return repo_path

    def label_exists(self, repo_path: Path, name: str) -> bool:
        """Check if a label exists in the repository."""
        try:
            result = subprocess.run(
                ["gh", "label", "list", "--search", name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Check if the exact label name exists in the output
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line and line.split("\t")[0] == name:
                    return True
            return False
        except subprocess.CalledProcessError:
            return False

    def create_label(
        self, repo_path: Path, name: str, color: str, description: str
    ) -> bool:
        """Create a label in the repository if it doesn't already exist."""
        # Check if label already exists
        if self.label_exists(repo_path, name):
            return True  # Label already exists, no need to create

        # Create the label
        try:
            subprocess.run(
                [
                    "gh",
                    "label",
                    "create",
                    name,
                    "--color",
                    color,
                    "--description",
                    description,
                ],
                cwd=repo_path,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def git_commit_and_push(
        self, repo_path: Path, message: str, files: Optional[List[str]] = None
    ) -> None:
        """Add, commit, and push changes to git."""
        if files:
            for file in files:
                subprocess.run(["git", "add", file], cwd=repo_path, check=True)
        else:
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)

        subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True)

        # Get current branch name and push
        current_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        subprocess.run(
            ["git", "push", "origin", current_branch], cwd=repo_path, check=True
        )

    def create_branch(self, repo_path: Path, branch_name: str) -> None:
        """Create and checkout a new branch."""
        # First ensure we're on main branch
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)

        # Delete local branch if it exists
        subprocess.run(
            ["git", "branch", "-D", branch_name], cwd=repo_path, check=False
        )  # Don't fail if branch doesn't exist

        # Create new branch
        subprocess.run(
            ["git", "checkout", "-b", branch_name], cwd=repo_path, check=True
        )

    def push_branch(self, repo_path: Path, branch_name: str) -> None:
        """Push a branch to remote."""
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name], cwd=repo_path, check=True
        )

    def _get_repo_suffix(self, repo_path: Path) -> str:
        """Generate a suffix based on the local repository path."""
        # Get the relative path from cache_dir to help identify the repo
        try:
            relative_path = repo_path.relative_to(self.cache_dir)
            # Use the directory name as suffix
            return f"[{relative_path.name}]"
        except ValueError:
            # If repo_path is not under cache_dir, use the directory name
            return f"[{repo_path.name}]"

    def create_pr(
        self, repo_path: Path, title: str, body: str, head: str, base: str = "main"
    ) -> str:
        """Create a pull request and return the PR number."""
        # Add suffix to title based on local repository path
        suffix = self._get_repo_suffix(repo_path)
        title_with_suffix = f"{title} {suffix}"

        pr_result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                title_with_suffix,
                "--body",
                body,
                "--head",
                head,
                "--base",
                base,
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        # Extract PR number from output
        pr_url = pr_result.stdout.strip()
        return pr_url.split("/")[-1]

    def create_issue(self, repo_path: Path, title: str, body: str) -> str:
        """Create an issue and return the issue number."""
        # Add suffix to title based on local repository path
        suffix = self._get_repo_suffix(repo_path)
        title_with_suffix = f"{title} {suffix}"

        issue_result = subprocess.run(
            ["gh", "issue", "create", "--title", title_with_suffix, "--body", body],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        # Extract issue number from output
        issue_url = issue_result.stdout.strip()
        return issue_url.split("/")[-1]

    def get_pr_labels(self, repo_path: Path, pr_number: str) -> List[str]:
        """Get labels for a specific PR."""
        result = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "labels"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)
        return [label["name"] for label in data["labels"]]

    def get_issue_labels(self, repo_path: Path, issue_number: str) -> List[str]:
        """Get labels for a specific issue."""
        result = subprocess.run(
            ["gh", "issue", "view", issue_number, "--json", "labels"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)
        return [label["name"] for label in data["labels"]]

    def pr_has_label(self, repo_path: Path, pr_number: str, label_name: str) -> bool:
        """Check if a PR has a specific label."""
        try:
            labels = self.get_pr_labels(repo_path, pr_number)
            return label_name in labels
        except subprocess.CalledProcessError:
            return False

    def issue_has_label(
        self, repo_path: Path, issue_number: str, label_name: str
    ) -> bool:
        """Check if an issue has a specific label."""
        try:
            labels = self.get_issue_labels(repo_path, issue_number)
            return label_name in labels
        except subprocess.CalledProcessError:
            return False

    def poll_until_condition(
        self, condition_func, timeout: int = 120, poll_interval: int = 5
    ) -> bool:
        """Poll until a condition is met or timeout is reached.

        Args:
            condition_func: A callable that returns True when the condition is met
            timeout: Maximum time to wait in seconds (default: 120)
            poll_interval: Time between polls in seconds (default: 5)

        Returns:
            True if condition was met, False if timeout was reached
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(poll_interval)

        return False

    def close_pr(
        self, repo_path: Path, pr_number: str, delete_branch: bool = True
    ) -> bool:
        """Close a PR and optionally delete the branch."""
        try:
            cmd = ["gh", "pr", "close", pr_number]
            if delete_branch:
                cmd.append("--delete-branch")
            subprocess.run(cmd, cwd=repo_path, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def close_issue(self, repo_path: Path, issue_number: str) -> bool:
        """Close an issue."""
        try:
            subprocess.run(
                ["gh", "issue", "close", issue_number], cwd=repo_path, check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def add_labels_to_pr(
        self, repo_path: Path, pr_number: str, labels: List[str]
    ) -> bool:
        """Add labels to a PR."""
        try:
            cmd = ["gh", "pr", "edit", pr_number, "--add-label"]
            cmd.extend(labels)
            subprocess.run(cmd, cwd=repo_path, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def add_labels_to_issue(
        self, repo_path: Path, issue_number: str, labels: List[str]
    ) -> bool:
        """Add labels to an issue."""
        try:
            cmd = ["gh", "issue", "edit", issue_number, "--add-label"]
            cmd.extend(labels)
            subprocess.run(cmd, cwd=repo_path, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def remove_labels_from_pr(
        self, repo_path: Path, pr_number: str, labels: List[str]
    ) -> bool:
        """Remove labels from a PR."""
        try:
            cmd = ["gh", "pr", "edit", pr_number, "--remove-label"]
            cmd.extend(labels)
            subprocess.run(cmd, cwd=repo_path, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def remove_labels_from_issue(
        self, repo_path: Path, issue_number: str, labels: List[str]
    ) -> bool:
        """Remove labels from an issue."""
        try:
            cmd = ["gh", "issue", "edit", issue_number, "--remove-label"]
            cmd.extend(labels)
            subprocess.run(cmd, cwd=repo_path, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


class GitHubFixtures:
    """Aggregates all GitHub-related fixtures for testing."""

    @pytest.fixture(scope="function")
    def github_manager(self):
        """Create a GitHubTestManager instance for function-scoped tests."""
        return GitHubTestManager()

    @pytest.fixture(scope="class")
    def github_manager_class(self):
        """Create a GitHubTestManager instance for class-scoped tests."""
        return GitHubTestManager()

    @pytest.fixture(scope="function")
    def cloned_repo(self, github_manager):
        """Clone the current git repo to cache directory."""
        return github_manager.clone_current_repo()

    @pytest.fixture(scope="class")
    def test_repo(self, github_manager_class):
        """Create a temporary repository that uses the existing repo-automations as remote."""
        # Create unique repository name with timestamp
        repo_name = f"test-repo-{int(time.time())}"

        # Create temporary local repository
        repo_path = github_manager_class.create_temp_repo(repo_name)

        # Ensure triage label exists (create if it doesn't exist)
        github_manager_class.create_label(repo_path, "triage", "FFFF00", "Needs triage")

        # Create release and backport labels for testing
        github_manager_class.create_label(
            repo_path, "release 1.0", "00FF00", "Release 1.0"
        )

        github_manager_class.create_label(
            repo_path, "backport main", "0000FF", "Backport to main"
        )

        yield repo_path

        # Cleanup: remove temporary directory
        subprocess.run(["rm", "-rf", str(repo_path)], check=False)

    @pytest.fixture(scope="class")
    def integration_manager(self, github_manager_class):
        """GitHub manager specifically for integration tests."""
        return github_manager_class


# Basic unit tests (non-integration)
class TestBasicFunctionality(GitHubFixtures):
    """Basic functionality tests that don't require GitHub integration."""

    def test_hello(self, github_manager):
        """Test basic functionality of the GitHubTestManager class."""
        # Create a temporary repository using the existing repo-automations as remote
        repo_name = f"test-hello-{int(time.time())}"
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


# Integration tests
@pytest.mark.integration
class TestTriageAutoAdd(GitHubFixtures):
    """Integration test cases for the triage auto-add workflow."""

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
