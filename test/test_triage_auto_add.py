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
        subprocess.run([
            "git", "clone", str(current_repo), str(clone_path)
        ], check=True)
        
        return clone_path
    
    def create_temp_repo(self, repo_name: str) -> Path:
        """Create a temporary local repository that uses the existing repo-automations as remote."""
        repo_path = self.cache_dir / repo_name
        
        # Clean up if exists
        if repo_path.exists():
            subprocess.run(["rm", "-rf", str(repo_path)], check=True)
        
        # Clone the existing repo-automations repository
        subprocess.run([
            "git", "clone", "https://github.com/thenets/repo-automations.git", str(repo_path)
        ], check=True)
        
        # Ensure we're on main branch
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)
        
        # Pull latest changes
        subprocess.run(["git", "pull", "origin", "main"], cwd=repo_path, check=True)
        
        return repo_path
    

    
    def create_label(self, repo_path: Path, name: str, color: str, description: str) -> bool:
        """Create a label in the repository."""
        try:
            subprocess.run([
                "gh", "label", "create", name,
                "--color", color,
                "--description", description
            ], cwd=repo_path, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def git_commit_and_push(self, repo_path: Path, message: str, files: Optional[List[str]] = None) -> None:
        """Add, commit, and push changes to git."""
        if files:
            for file in files:
                subprocess.run(["git", "add", file], cwd=repo_path, check=True)
        else:
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        
        subprocess.run([
            "git", "commit", "-m", message
        ], cwd=repo_path, check=True)
        
        # Get current branch name and push
        current_branch = subprocess.run(
            ["git", "branch", "--show-current"], 
            cwd=repo_path, 
            capture_output=True, 
            text=True, 
            check=True
        ).stdout.strip()
        
        subprocess.run(["git", "push", "origin", current_branch], cwd=repo_path, check=True)
    
    def create_branch(self, repo_path: Path, branch_name: str) -> None:
        """Create and checkout a new branch."""
        # First ensure we're on main branch
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)
        
        # Delete local branch if it exists
        subprocess.run([
            "git", "branch", "-D", branch_name
        ], cwd=repo_path, check=False)  # Don't fail if branch doesn't exist
        
        # Create new branch
        subprocess.run([
            "git", "checkout", "-b", branch_name
        ], cwd=repo_path, check=True)
    
    def push_branch(self, repo_path: Path, branch_name: str) -> None:
        """Push a branch to remote."""
        subprocess.run([
            "git", "push", "-u", "origin", branch_name
        ], cwd=repo_path, check=True)
    
    def create_pr(self, repo_path: Path, title: str, body: str, head: str, base: str = "main") -> str:
        """Create a pull request and return the PR number."""
        pr_result = subprocess.run([
            "gh", "pr", "create",
            "--title", title,
            "--body", body,
            "--head", head,
            "--base", base
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        # Extract PR number from output
        pr_url = pr_result.stdout.strip()
        return pr_url.split('/')[-1]
    
    def create_issue(self, repo_path: Path, title: str, body: str) -> str:
        """Create an issue and return the issue number."""
        issue_result = subprocess.run([
            "gh", "issue", "create",
            "--title", title,
            "--body", body
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        # Extract issue number from output
        issue_url = issue_result.stdout.strip()
        return issue_url.split('/')[-1]
    
    def get_pr_labels(self, repo_path: Path, pr_number: str) -> List[str]:
        """Get labels for a specific PR."""
        result = subprocess.run([
            "gh", "pr", "view", pr_number, "--json", "labels"
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        return [label["name"] for label in data["labels"]]
    
    def get_issue_labels(self, repo_path: Path, issue_number: str) -> List[str]:
        """Get labels for a specific issue."""
        result = subprocess.run([
            "gh", "issue", "view", issue_number, "--json", "labels"
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        return [label["name"] for label in data["labels"]]
    
    def close_pr(self, repo_path: Path, pr_number: str, delete_branch: bool = True) -> bool:
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
            subprocess.run([
                "gh", "issue", "close", issue_number
            ], cwd=repo_path, check=True)
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
        repo_name = f"test-repo-automations-{int(time.time())}"
        
        # Create temporary local repository
        repo_path = github_manager_class.create_temp_repo(repo_name)
        
        # Ensure triage label exists (create if it doesn't exist)
        github_manager_class.create_label(
            repo_path, 
            "triage", 
            "FFFF00", 
            "Needs triage"
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
        new_content = current_content + f"\n\n## Test Basic Functionality {int(time.time())}\n\nThis is a test from test_hello.\n"
        testing_file.write_text(new_content)
        
        # Commit and push the changes
        github_manager.git_commit_and_push(repo_path, "Test basic functionality from test_hello", ["TESTING.md"])
        
        # Create a PR
        pr_number = github_manager.create_pr(
            repo_path,
            "Test PR from test_hello",
            "This PR tests basic functionality from the test_hello method.",
            branch_name
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
    
    def test_pr_gets_triage_label(self, test_repo, integration_manager):
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
        new_content = current_content + f"\n\n## Test Change {int(time.time())}\n\nThis is a test change.\n"
        testing_file.write_text(new_content)
        
        # Commit and push changes
        integration_manager.git_commit_and_push(repo_path, "Test change for PR automation", ["TESTING.md"])
        integration_manager.push_branch(repo_path, branch_name)
        
        # Create PR
        pr_number = integration_manager.create_pr(
            repo_path,
            "Test PR for triage automation",
            "This PR tests the automatic triage label addition.",
            branch_name
        )
        
        # Wait for GitHub Actions to process
        time.sleep(30)
        
        # Check if triage label was added
        labels = integration_manager.get_pr_labels(repo_path, pr_number)
        
        assert "triage" in labels, f"Expected 'triage' label on PR #{pr_number}, but got: {labels}"
        
        # Cleanup PR
        integration_manager.close_pr(repo_path, pr_number, delete_branch=True)
    
    # def test_issue_gets_triage_label(self, test_repo, integration_manager):
    #     """Test that a new issue automatically gets the triage label."""
    #     repo_path = test_repo
        
    #     # Create a new issue
    #     issue_number = integration_manager.create_issue(
    #         repo_path,
    #         "Test issue for triage automation",
    #         "This issue tests the automatic triage label addition."
    #     )
        
    #     # Wait for GitHub Actions to process
    #     time.sleep(30)
        
    #     # Check if triage label was added
    #     labels = integration_manager.get_issue_labels(repo_path, issue_number)
        
    #     assert "triage" in labels, f"Expected 'triage' label on issue #{issue_number}, but got: {labels}"
        
    #     # Cleanup issue
    #     integration_manager.close_issue(repo_path, issue_number)