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
from typing import Dict, List

import pytest


@pytest.mark.integration
class TestTriageAutoAdd:
    """Test cases for the triage auto-add workflow."""
    
    CACHE_DIR = Path("./cache/test/repo")
    TEST_REPO_NAME = "test-repo-automations"
    
    @pytest.fixture(scope="class")
    def test_repo(self):
        """Create a test repository with the workflow."""
        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create a temporary test repository
        repo_path = self.CACHE_DIR / self.TEST_REPO_NAME
        
        # Clean up if exists
        if repo_path.exists():
            subprocess.run(["rm", "-rf", str(repo_path)], check=True)
        
        # Create new repository
        subprocess.run([
            "gh", "repo", "create", self.TEST_REPO_NAME,
            "--private", "--clone", "--confirm"
        ], cwd=self.CACHE_DIR, check=True)
        
        # Copy workflow files to test repo
        workflow_src = Path(".github/workflows/triage-auto-add.yml")
        workflow_dst = repo_path / ".github/workflows/triage-auto-add.yml"
        workflow_dst.parent.mkdir(parents=True, exist_ok=True)
        
        subprocess.run([
            "cp", str(workflow_src), str(workflow_dst)
        ], check=True)
        
        # Create TESTING.md file
        testing_file = repo_path / "TESTING.md"
        testing_file.write_text("# Testing\n\nThis is a test file.\n")
        
        # Create triage label
        subprocess.run([
            "gh", "label", "create", "triage",
            "--color", "yellow",
            "--description", "Needs triage"
        ], cwd=repo_path, check=True)
        
        # Commit and push workflow
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run([
            "git", "commit", "-m", "Add triage auto-add workflow"
        ], cwd=repo_path, check=True)
        subprocess.run(["git", "push"], cwd=repo_path, check=True)
        
        yield repo_path
        
        # Cleanup
        subprocess.run([
            "gh", "repo", "delete", self.TEST_REPO_NAME, "--yes"
        ], cwd=self.CACHE_DIR, check=False)
    
    def test_pr_gets_triage_label(self, test_repo):
        """Test that a new PR automatically gets the triage label."""
        repo_path = test_repo
        
        # Create a new branch
        branch_name = f"test-pr-{int(time.time())}"
        subprocess.run([
            "git", "checkout", "-b", branch_name
        ], cwd=repo_path, check=True)
        
        # Modify TESTING.md
        testing_file = repo_path / "TESTING.md"
        current_content = testing_file.read_text()
        new_content = current_content + f"\n\n## Test Change {int(time.time())}\n\nThis is a test change.\n"
        testing_file.write_text(new_content)
        
        # Commit and push changes
        subprocess.run(["git", "add", "TESTING.md"], cwd=repo_path, check=True)
        subprocess.run([
            "git", "commit", "-m", "Test change for PR automation"
        ], cwd=repo_path, check=True)
        subprocess.run([
            "git", "push", "-u", "origin", branch_name
        ], cwd=repo_path, check=True)
        
        # Create PR
        pr_result = subprocess.run([
            "gh", "pr", "create",
            "--title", "Test PR for triage automation",
            "--body", "This PR tests the automatic triage label addition.",
            "--head", branch_name,
            "--base", "main"
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        # Extract PR number from output
        pr_url = pr_result.stdout.strip()
        pr_number = pr_url.split('/')[-1]
        
        # Wait for GitHub Actions to process
        time.sleep(30)
        
        # Check if triage label was added
        labels = self._get_pr_labels(repo_path, pr_number)
        
        assert "triage" in labels, f"Expected 'triage' label on PR #{pr_number}, but got: {labels}"
        
        # Cleanup PR
        subprocess.run([
            "gh", "pr", "close", pr_number, "--delete-branch"
        ], cwd=repo_path, check=False)
    
    def test_issue_gets_triage_label(self, test_repo):
        """Test that a new issue automatically gets the triage label."""
        repo_path = test_repo
        
        # Create a new issue
        issue_result = subprocess.run([
            "gh", "issue", "create",
            "--title", "Test issue for triage automation",
            "--body", "This issue tests the automatic triage label addition."
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        # Extract issue number from output
        issue_url = issue_result.stdout.strip()
        issue_number = issue_url.split('/')[-1]
        
        # Wait for GitHub Actions to process
        time.sleep(30)
        
        # Check if triage label was added
        labels = self._get_issue_labels(repo_path, issue_number)
        
        assert "triage" in labels, f"Expected 'triage' label on issue #{issue_number}, but got: {labels}"
        
        # Cleanup issue
        subprocess.run([
            "gh", "issue", "close", issue_number
        ], cwd=repo_path, check=False)
    
    def _get_pr_labels(self, repo_path: Path, pr_number: str) -> List[str]:
        """Get labels for a specific PR."""
        result = subprocess.run([
            "gh", "pr", "view", pr_number, "--json", "labels"
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        return [label["name"] for label in data["labels"]]
    
    def _get_issue_labels(self, repo_path: Path, issue_number: str) -> List[str]:
        """Get labels for a specific issue."""
        result = subprocess.run([
            "gh", "issue", "view", issue_number, "--json", "labels"
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        return [label["name"] for label in data["labels"]]