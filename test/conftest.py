"""
Shared fixtures and utilities for the test suite.

This module contains the most commonly used fixtures and test utilities
that are shared across multiple test files.
"""

import json
import os
import random
import subprocess
import tempfile
import threading
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

    def create_draft_pr(
        self, repo_path: Path, title: str, body: str, head: str, base: str = "main"
    ) -> str:
        """Create a draft pull request and return the PR number."""
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
                "--draft",
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

    def get_pr_comments(self, repo_path: Path, pr_number: str) -> List[Dict]:
        """Get all comments for a PR."""
        try:
            result = subprocess.run(
                ["gh", "pr", "view", pr_number, "--json", "comments"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            
            data = json.loads(result.stdout)
            return data.get("comments", [])
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return []

    def pr_has_comment_containing(self, repo_path: Path, pr_number: str, text: str) -> bool:
        """Check if a PR has any comment containing the specified text."""
        comments = self.get_pr_comments(repo_path, pr_number)
        return any(text in comment.get("body", "") for comment in comments)

    def mark_pr_ready_for_review(self, repo_path: Path, pr_number: str) -> bool:
        """Mark a draft PR as ready for review."""
        try:
            subprocess.run(
                ["gh", "pr", "ready", pr_number],
                cwd=repo_path,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False


class GitHubFixtures:
    """Aggregates all GitHub-related fixtures for testing."""

    @staticmethod
    def generate_unique_name(prefix: str) -> str:
        """Generate a thread-safe unique name for parallel test execution.

        Args:
            prefix: The prefix to use for the name (e.g., 'test-repo', 'test-branch')

        Returns:
            A unique name with the format: {prefix}-{timestamp}-{thread_id}-{process_id}-{random}
        """
        timestamp = time.time()
        thread_id = threading.get_ident()
        process_id = os.getpid()
        random_suffix = random.randint(1000, 9999)
        return f"{prefix}-{int(timestamp)}-{thread_id}-{process_id}-{random_suffix}"

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
        # Create unique repository name per thread for parallel execution
        repo_name = self.generate_unique_name("test-repo")

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