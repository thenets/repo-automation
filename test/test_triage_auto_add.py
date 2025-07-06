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
    
    def create_test_repo(self, repo_name: str, private: bool = True) -> Path:
        """Create a new GitHub repository for testing."""
        repo_path = self.cache_dir / repo_name
        
        # Clean up if exists
        if repo_path.exists():
            subprocess.run(["rm", "-rf", str(repo_path)], check=True)
        
        # Try to delete existing remote repository first
        try:
            subprocess.run([
                "gh", "repo", "delete", repo_name, "--yes"
            ], cwd=self.cache_dir, check=False, capture_output=True)
        except:
            pass  # Repository may not exist
        
        # Create new repository
        cmd = ["gh", "repo", "create", repo_name, "--clone"]
        if private:
            cmd.append("--private")
        
        subprocess.run(cmd, cwd=self.cache_dir, check=True)
        
        return repo_path
    
    def delete_test_repo(self, repo_name: str) -> bool:
        """Delete a GitHub repository."""
        try:
            subprocess.run([
                "gh", "repo", "delete", repo_name, "--yes"
            ], cwd=self.cache_dir, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def copy_workflow_files(self, source_repo: Path, target_repo: Path) -> None:
        """Copy workflow files from source to target repository."""
        workflow_src = source_repo / ".github/workflows/triage-auto-add.yml"
        workflow_dst = target_repo / ".github/workflows/triage-auto-add.yml"
        workflow_dst.parent.mkdir(parents=True, exist_ok=True)
        
        subprocess.run([
            "cp", str(workflow_src), str(workflow_dst)
        ], check=True)
    
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
        subprocess.run(["git", "push"], cwd=repo_path, check=True)
    
    def create_branch(self, repo_path: Path, branch_name: str) -> None:
        """Create and checkout a new branch."""
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
        """Create a test repository with the workflow for integration tests."""
        # Create unique repository name with timestamp
        repo_name = f"test-repo-automations-{int(time.time())}"
        
        # Create test repository
        repo_path = github_manager_class.create_test_repo(repo_name, private=True)
        
        # Copy workflow files to test repo
        current_repo = Path.cwd()
        github_manager_class.copy_workflow_files(current_repo, repo_path)
        
        # Create TESTING.md file
        testing_file = repo_path / "TESTING.md"
        testing_file.write_text("# Testing\n\nThis is a test file.\n")
        
        # Create triage label
        github_manager_class.create_label(
            repo_path, 
            "triage", 
            "yellow", 
            "Needs triage"
        )
        
        # Commit and push workflow
        github_manager_class.git_commit_and_push(repo_path, "Add triage auto-add workflow")
        
        yield repo_path
        
        # Cleanup
        github_manager_class.delete_test_repo(repo_name)
    
    @pytest.fixture(scope="class")
    def integration_manager(self, github_manager_class):
        """GitHub manager specifically for integration tests."""
        return github_manager_class


# Basic unit tests (non-integration)
class TestBasicFunctionality(GitHubFixtures):
    """Basic functionality tests that don't require GitHub integration."""
    
    def test_hello(self, cloned_repo):
        """Test that the cloned repo path is correct."""
        expected_path = Path("./cache/test/repo/test-hello-repo")
        assert cloned_repo == expected_path
        assert cloned_repo.exists()


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