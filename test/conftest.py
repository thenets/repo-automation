"""
Shared fixtures and utilities for the test suite.

This module contains the most commonly used fixtures and test utilities
that are shared across multiple test files. Enhanced to support multi-repository
testing with arbitrary organizations and fork scenarios.
"""

import json
import os
import random
import subprocess
import tempfile
import threading
import time
import fcntl
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

from .test_config import (
    RepositoryTestingConfig, 
    RepositoryConfig, 
    get_test_config,
    update_workflow_repository_references,
    validate_repository_exists
)


def pytest_sessionstart(session):
    """
    Called after the Session object has been created but before pytest starts collecting tests.
    
    This ensures initialization markers are cleaned up before any parallel workers start,
    preventing race conditions in parallel test execution.
    """
    cache_dir = Path("./cache/test/repo")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Force cleanup of initialization markers and lock files
    complete_file_path = cache_dir / ".initialization_complete"
    lock_file_path = cache_dir / ".initialization_lock"
    
    if complete_file_path.exists():
        print("🔄 [pytest_sessionstart] Removing initialization completion marker to force repository update...")
        complete_file_path.unlink()
    
    if lock_file_path.exists():
        print("🧹 [pytest_sessionstart] Cleaning up stale lock file from previous run...")
        lock_file_path.unlink()
    
    print("✅ [pytest_sessionstart] Repository reinitialization setup complete")


class RepositoryError(Exception):
    """Exception raised when repository operations fail."""
    pass


class GitHubTestManager:
    """Manages Git and GitHub operations for testing with multi-repository support."""

    def __init__(
        self, 
        cache_dir: Path = Path("./cache/test/repo"),
        config: Optional[RepositoryTestingConfig] = None
    ):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or get_test_config()

    def setup_repository_secrets(self, repo_config: RepositoryConfig) -> bool:
        """Set up GitHub Actions secrets for the repository.
        
        Args:
            repo_config: Repository configuration
            
        Returns:
            bool: True if secrets were set up successfully
            
        Raises:
            RepositoryError: If repository doesn't exist or secrets setup fails
        """
        # Check if repository exists first
        if not validate_repository_exists(repo_config.owner, repo_config.repo):
            raise RepositoryError(
                f"Repository {repo_config.full_name} does not exist or is not accessible. "
                "Please check the repository name and your GitHub authentication."
            )
        
        # Get GITHUB_TOKEN from environment
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            print("⚠️ GITHUB_TOKEN not found in environment - skipping secrets setup")
            return False
        
        try:
            # Set GITHUB_TOKEN_AUTOMATION as a repository secret for workflow testing
            print(f"Setting up GITHUB_TOKEN_AUTOMATION secret for {repo_config.full_name}...")
            result = subprocess.run(
                [
                    "gh", "secret", "set", "GITHUB_TOKEN_AUTOMATION",
                    "--repo", repo_config.full_name,
                    "--body", github_token
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            print(f"✅ Successfully set GITHUB_TOKEN_AUTOMATION secret for {repo_config.full_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to set repository secret: {e}")
            print(f"   stdout: {e.stdout}")
            print(f"   stderr: {e.stderr}")
            return False

    def clone_target_repository(self, repo_config: RepositoryConfig, target_name: str) -> Path:
        """Clone the target repository specified in TEST_GITHUB_ORG/TEST_GITHUB_REPO.
        
        Args:
            repo_config: Repository configuration to clone
            target_name: Local directory name for the cloned repository
            
        Returns:
            Path: Path to the cloned repository
            
        Raises:
            RepositoryError: If repository doesn't exist or cloning fails
        """
        # Validate repository exists first
        if not validate_repository_exists(repo_config.owner, repo_config.repo):
            raise RepositoryError(
                f"Repository {repo_config.full_name} does not exist or is not accessible. "
                "Please check TEST_GITHUB_ORG and TEST_GITHUB_REPO in your .env file, "
                "or ensure you're in a git repository with a GitHub origin remote."
            )
        
        clone_path = self.cache_dir / target_name

        # Clean up if exists
        if clone_path.exists():
            subprocess.run(["rm", "-rf", str(clone_path)], check=True)

        try:
            # Get GITHUB_TOKEN for authenticated clone
            github_token = os.getenv("GITHUB_TOKEN")
            if github_token:
                # Use authenticated URL if token is available
                clone_url = f"https://{github_token}@github.com/{repo_config.full_name}.git"
            else:
                # Fallback to public URL
                clone_url = repo_config.github_url
            
            # Clone the repository
            print(f"Cloning {repo_config.full_name} to {clone_path}...")
            subprocess.run(
                ["git", "clone", clone_url, str(clone_path)], 
                check=True,
                capture_output=True
            )
            
            print(f"✅ Successfully cloned {repo_config.full_name}")
            
            # Set up repository secrets
            self.setup_repository_secrets(repo_config)
            
            return clone_path
            
        except subprocess.CalledProcessError as e:
            raise RepositoryError(
                f"Failed to clone repository {repo_config.full_name}. "
                f"Error: {e}. Please check your GitHub authentication and repository access."
            )

    def clone_repository(self, repo_config: RepositoryConfig, target_name: str) -> Path:
        """Clone a repository to cache directory.
        
        Args:
            repo_config: Repository configuration to clone
            target_name: Local directory name for the cloned repository
            
        Returns:
            Path: Path to the cloned repository
        """
        return self.clone_target_repository(repo_config, target_name)

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

    def generate_example_workflow(self, repo_config: RepositoryConfig) -> str:
        """Generate a clean example workflow from comprehensive-usage.yml for the test repository.
        
        Args:
            repo_config: Target repository configuration
            
        Returns:
            str: Generated workflow YAML content
        """
        # Use local action for testing (./), published action would be thenets/repo-automation@v1
        action_reference = "./"  # Local action reference for testing
        
        workflow_content = f"""---
# Complete Repository Automation - Generated from examples/comprehensive-usage.yml
# This workflow demonstrates the unified GitHub Action replacing 4 individual keeper workflows

name: Complete Repository Automation
on:
  issues:
    types: [opened, labeled, unlabeled]
  pull_request:
    types: [opened, synchronize, edited, ready_for_review, labeled, unlabeled]
  workflow_run:
    workflows: ["Keeper: trigger"]
    types: [completed]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC for stale detection
  workflow_dispatch:  # Manual trigger for testing

permissions:
  issues: write
  pull-requests: write
  checks: write

jobs:
  repository-automation:
    runs-on: ubuntu-latest
    if: github.repository == '{repo_config.full_name}'
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{{{ secrets.CUSTOM_GITHUB_TOKEN || secrets.GITHUB_TOKEN }}}}
        
      - name: Complete Repository Automation
        uses: {action_reference}
        with:
          github-token: ${{{{ secrets.GITHUB_TOKEN }}}}
          custom-github-token: ${{{{ secrets.CUSTOM_GITHUB_TOKEN }}}}
          
          # Stale detection configuration (enables stale detection)
          stale-days: 1
          
          # Release/backport labeling configuration (enables auto-labeling)
          accepted-releases: '["1.0", "1.1", "1.2", "2.0", "2.1", "devel"]'
          accepted-backports: '["1.0", "1.1", "1.2", "2.0", "2.1"]'
          
          # Feature branch automation (enables feature branch labeling)
          enable-feature-branch: true
          
          # Optional: dry-run mode for testing
          dry-run: false
"""
        return workflow_content

    def initialize_test_repository(self, repo_config: RepositoryConfig) -> bool:
        """Initialize test repository with current source code by force-pushing from current repo.
        
        This ensures the test repository contains all the latest workflows and source code
        from the current working directory.
        
        Args:
            repo_config: Target repository configuration to initialize
            
        Returns:
            bool: True if initialization was successful
            
        Raises:
            RepositoryError: If initialization fails
        """
        try:
            print(f"Initializing test repository {repo_config.full_name} with current source code...")
            
            # Create a unique temporary directory for the initialization to avoid parallel test conflicts
            import uuid
            temp_init_path = self.cache_dir / f"temp-init-{uuid.uuid4().hex[:8]}"
            if temp_init_path.exists():
                subprocess.run(["rm", "-rf", str(temp_init_path)], check=True)
            
            # Create fresh repository without git history to avoid workflow permissions issues
            current_repo = Path.cwd()
            temp_init_path.mkdir(parents=True)
            
            # Initialize new git repository with main branch
            subprocess.run(["git", "init", "-b", "main"], cwd=temp_init_path, check=True)
            subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=temp_init_path, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_init_path, check=True)
            
            # Copy only essential automation files
            import shutil
            
            # Copy TESTING.md for PR modification tests
            testing_file = current_repo / "TESTING.md"
            if testing_file.exists():
                shutil.copy2(testing_file, temp_init_path / "TESTING.md")
                print(f"Copied TESTING.md for PR testing")
            
            # Copy GitHub Action files (action.yml and src/ directory)
            action_file = current_repo / "action.yml"
            if action_file.exists():
                shutil.copy2(action_file, temp_init_path / "action.yml")
                print(f"Copied action.yml for GitHub Action testing")
            
            src_dir = current_repo / "src"
            if src_dir.exists():
                shutil.copytree(src_dir, temp_init_path / "src")
                print(f"Copied src/ directory for GitHub Action testing")
            
            # Copy examples directory
            examples_dir = current_repo / "examples"
            if examples_dir.exists():
                shutil.copytree(examples_dir, temp_init_path / "examples")
                print(f"Copied examples/ directory for GitHub Action testing")
            
            # Generate example workflow for test repository instead of copying internal workflows
            workflows_staging = temp_init_path / "_workflows_staging"
            workflows_staging.mkdir(parents=True)
            
            # Generate clean example workflow from comprehensive-usage.yml
            example_workflow_content = self.generate_example_workflow(repo_config)
            example_workflow_path = workflows_staging / "repository-automation.yml"
            example_workflow_path.write_text(example_workflow_content)
            
            print(f"Generated example workflow: repository-automation.yml for {repo_config.full_name}")
            
            # Get GITHUB_TOKEN for authenticated push
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                raise RepositoryError("GITHUB_TOKEN environment variable is required for repository initialization")
            
            # Add and commit essential files (workflows staged separately)
            subprocess.run(["git", "add", "TESTING.md", "action.yml", "src/", "examples/"], cwd=temp_init_path, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit - testing files and GitHub Action"], cwd=temp_init_path, check=True)
            
            # Add remote pointing to test repository with token authentication
            test_repo_url = f"https://{github_token}@github.com/{repo_config.full_name}.git"
            subprocess.run(
                ["git", "remote", "add", "origin", test_repo_url],
                cwd=temp_init_path,
                check=True
            )
            
            # Force push testing files to test repository
            print(f"Force-pushing testing files to {repo_config.full_name}...")
            result = subprocess.run(
                ["git", "push", "-f", "origin", "main"],
                cwd=temp_init_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Git push stderr: {result.stderr}")
                print(f"Git push stdout: {result.stdout}")
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
            
            # Now deploy generated example workflow to .github/workflows directory
            workflows_staging = temp_init_path / "_workflows_staging"
            if workflows_staging.exists():
                # Create .github/workflows directory
                github_dir = temp_init_path / ".github"
                workflows_dir = github_dir / "workflows" 
                workflows_dir.mkdir(parents=True)
                
                # Copy generated workflow to .github/workflows
                deployed_workflows = []
                for workflow_file in workflows_staging.glob("*.yml"):
                    shutil.copy2(workflow_file, workflows_dir / workflow_file.name)
                    deployed_workflows.append(workflow_file.name)
                
                # Stage and commit .github directory
                subprocess.run(["git", "add", ".github/"], cwd=temp_init_path, check=True)
                subprocess.run(["git", "commit", "-m", "Add example repository automation workflow"], cwd=temp_init_path, check=True)
                
                print(f"Pushing example workflow to {repo_config.full_name}: {', '.join(deployed_workflows)}")
                workflow_result = subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=temp_init_path,
                    capture_output=True,
                    text=True
                )
                
                if workflow_result.returncode != 0:
                    print(f"❌ Could not push workflow: {workflow_result.stderr}")
                    print("💡 This might be due to missing 'Workflow: Write' account permission.")
                    print("   Please check your GitHub token permissions and try again.")
                    raise RepositoryError(f"Failed to push workflow to {repo_config.full_name}")
                else:
                    print(f"✅ Successfully pushed example workflow: {', '.join(deployed_workflows)}")
            
            # Clean up temp directory
            subprocess.run(["rm", "-rf", str(temp_init_path)], check=False)
            
            print(f"✅ Successfully initialized {repo_config.full_name} with current source code")
            return True
            
        except subprocess.CalledProcessError as e:
            # Clean up temp directory on error
            if 'temp_init_path' in locals() and temp_init_path.exists():
                subprocess.run(["rm", "-rf", str(temp_init_path)], check=False)
                
            raise RepositoryError(
                f"Failed to initialize repository {repo_config.full_name}. "
                f"Error: {e}. Please check your GitHub authentication and repository permissions."
            )

    def create_temp_repo(self, repo_name: str) -> Path:
        """Create a temporary local repository using the configured primary repository.
        
        Note: Repository initialization is now handled by the session-scoped fixture,
        so this method only clones the already-initialized external repository.
        """
        repo_path = self.cache_dir / repo_name

        # Clean up if exists
        if repo_path.exists():
            subprocess.run(["rm", "-rf", str(repo_path)], check=True)

        # Clone the configured primary repository (which should already be initialized)
        return self.clone_target_repository(self.config.primary_repo, repo_name)

    def create_fork_repo(
        self, 
        fork_config: RepositoryConfig, 
        org_repo_path: Path,
        repo_name: str
    ) -> Path:
        """Create a fork repository for external contributor testing.
        
        Args:
            fork_config: Fork repository configuration
            org_repo_path: Path to the organization repository (to copy workflows from)
            repo_name: Local directory name for the fork
            
        Returns:
            Path: Path to the fork repository
        """
        fork_path = self.cache_dir / repo_name

        # Clean up if exists
        if fork_path.exists():
            subprocess.run(["rm", "-rf", str(fork_path)], check=True)

        # Clone the fork repository with validation
        fork_path = self.clone_target_repository(fork_config, repo_name)

        # Add organization repo as upstream remote
        if fork_config.fork_parent:
            parent_url = f"https://github.com/{fork_config.fork_parent}.git"
            subprocess.run(
                ["git", "remote", "add", "upstream", parent_url],
                cwd=fork_path,
                check=True
            )

        return fork_path

    def setup_repository_workflows(
        self, 
        repo_path: Path, 
        target_repo_config: RepositoryConfig
    ) -> bool:
        """Set up GitHub Actions workflows in a repository for testing.
        
        Args:
            repo_path: Path to the repository
            target_repo_config: Repository configuration for workflow targeting
            
        Returns:
            bool: True if setup was successful
        """
        workflows_dir = repo_path / ".github" / "workflows"
        if not workflows_dir.exists():
            workflows_dir.mkdir(parents=True)

        # Get workflow files from current repository
        current_workflows_dir = Path.cwd() / ".github" / "workflows"
        if not current_workflows_dir.exists():
            return False

        success = True
        # Copy all workflow files except test workflows
        for workflow_file in current_workflows_dir.glob("*.yml"):
            # Skip test workflows from being deployed to external test repositories
            if workflow_file.name.startswith("test-"):
                continue
                
            target_file = workflows_dir / workflow_file.name
            
            # Copy workflow file
            target_file.write_text(workflow_file.read_text())
            
            # Update repository references for workflows that have them
            if not update_workflow_repository_references(
                target_file, 
                target_repo_config, 
                backup=False
            ):
                success = False

        return success

    def create_organization_test_environment(self) -> Tuple[Path, Optional[Path]]:
        """Create a complete organization + fork test environment.
        
        Returns:
            Tuple[Path, Optional[Path]]: (org_repo_path, fork_repo_path)
        """
        # Generate unique names for parallel execution
        timestamp = int(time.time())
        thread_id = threading.get_ident()
        
        org_repo_name = f"test-org-{timestamp}-{thread_id}"
        org_repo_path = self.clone_repository(
            self.config.primary_repo, 
            org_repo_name
        )
        
        # Set up workflows for organization repository
        self.setup_repository_workflows(org_repo_path, self.config.primary_repo)
        
        fork_repo_path = None
        if self.config.fork_repo:
            fork_repo_name = f"test-fork-{timestamp}-{thread_id}"
            fork_repo_path = self.create_fork_repo(
                self.config.fork_repo,
                org_repo_path,
                fork_repo_name
            )
            
            # Set up workflows for fork repository (using fork's own config)
            self.setup_repository_workflows(fork_repo_path, self.config.fork_repo)
        
        return org_repo_path, fork_repo_path

    def simulate_external_contributor_pr(
        self,
        fork_repo_path: Path,
        org_repo_path: Path,
        pr_title: str,
        pr_body: str,
        branch_name: str
    ) -> str:
        """Simulate an external contributor creating a PR from fork to organization.
        
        Args:
            fork_repo_path: Path to the fork repository
            org_repo_path: Path to the organization repository  
            pr_title: Title for the pull request
            pr_body: Body content for the pull request
            branch_name: Branch name for the PR
            
        Returns:
            str: PR number
        """
        # Create branch and changes in fork
        self.create_branch(fork_repo_path, branch_name)
        
        # Make some changes to trigger workflows
        test_file = fork_repo_path / "test_changes.md"
        test_file.write_text(f"# Test changes for {pr_title}\n\nTimestamp: {time.time()}")
        
        self.git_commit_and_push(
            fork_repo_path, 
            f"Add test changes for {pr_title}",
            ["test_changes.md"]
        )
        
        # Create PR from fork to organization repo
        # Note: This requires the fork to have the org repo as upstream
        fork_owner = self.config.fork_repo.owner
        org_owner = self.config.primary_repo.owner
        org_repo = self.config.primary_repo.repo
        
        pr_result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--repo", f"{org_owner}/{org_repo}",
                "--title", pr_title,
                "--body", pr_body,
                "--head", f"{fork_owner}:{branch_name}",
                "--base", "main",
            ],
            cwd=fork_repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        # Extract PR number from output
        pr_url = pr_result.stdout.strip()
        return pr_url.split("/")[-1]

    def get_repository_context(self, repo_path: Path) -> Dict[str, str]:
        """Get repository context information for testing.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dict[str, str]: Repository context with owner, repo, full_name
        """
        # Get remote origin URL to determine repository context
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        
        # Parse GitHub URL to extract owner and repo
        remote_url = result.stdout.strip()
        if "github.com" in remote_url:
            # Handle both SSH and HTTPS URLs
            if remote_url.startswith("git@github.com:"):
                repo_part = remote_url.replace("git@github.com:", "").replace(".git", "")
            else:
                repo_part = remote_url.replace("https://github.com/", "").replace(".git", "")
            
            owner, repo = repo_part.split("/", 1)
            return {
                "owner": owner,
                "repo": repo,
                "full_name": f"{owner}/{repo}"
            }
        
        return {"owner": "unknown", "repo": "unknown", "full_name": "unknown/unknown"}

    def validate_token_permissions(self, repo_path: Path) -> Dict[str, bool]:
        """Validate GitHub token permissions for the repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dict[str, bool]: Permission validation results
        """
        permissions = {
            "issues_read": False,
            "issues_write": False,
            "pull_requests_read": False,
            "pull_requests_write": False,
            "metadata_read": False
        }
        
        try:
            # Test issues read permission
            subprocess.run(
                ["gh", "issue", "list", "--limit", "1"],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            permissions["issues_read"] = True
        except subprocess.CalledProcessError:
            pass
        
        try:
            # Test pull requests read permission
            subprocess.run(
                ["gh", "pr", "list", "--limit", "1"],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            permissions["pull_requests_read"] = True
        except subprocess.CalledProcessError:
            pass
        
        try:
            # Test metadata read permission (repository info)
            subprocess.run(
                ["gh", "repo", "view"],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            permissions["metadata_read"] = True
        except subprocess.CalledProcessError:
            pass
        
        # Write permissions will be tested by actual operations in tests
        
        return permissions

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
        self, condition_func, timeout: Optional[int] = None, poll_interval: Optional[int] = None
    ) -> bool:
        """Poll until a condition is met or timeout is reached.

        Args:
            condition_func: A callable that returns True when the condition is met
            timeout: Maximum time to wait in seconds (uses config default if None)
            poll_interval: Time between polls in seconds (uses config default if None)

        Returns:
            True if condition was met, False if timeout was reached
        """
        timeout = timeout or self.config.test_timeout
        poll_interval = poll_interval or self.config.poll_interval
        
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
    """Aggregates all GitHub-related fixtures for testing with multi-repository support."""

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

    def get_repo_path(self, test_repo_fixture) -> Path:
        """Safely get repository path from fixture with proper error handling.
        
        This method ensures that repository path assignment never fails with UnboundLocalError,
        even if the fixture setup encounters issues during parallel execution.
        
        Args:
            test_repo_fixture: The test_repo fixture value
            
        Returns:
            Path: Valid repository path
            
        Raises:
            RepositoryError: If repository path cannot be determined
        """
        try:
            if test_repo_fixture is None:
                raise RepositoryError("test_repo fixture returned None - repository setup failed")
            
            if not isinstance(test_repo_fixture, Path):
                raise RepositoryError(f"test_repo fixture returned invalid type: {type(test_repo_fixture)}")
            
            if not test_repo_fixture.exists():
                raise RepositoryError(f"Repository path does not exist: {test_repo_fixture}")
                
            return test_repo_fixture
            
        except Exception as e:
            raise RepositoryError(f"Failed to get repository path: {e}")

    def ensure_repository_initialized(self) -> None:
        """Ensure that the external repository has been properly initialized.
        
        This method should be called at the start of test methods to verify
        that the session-scoped initialization completed successfully.
        
        Raises:
            RepositoryError: If repository initialization is incomplete
        """
        cache_dir = Path("./cache/test/repo")
        complete_file_path = cache_dir / ".initialization_complete"
        
        if not complete_file_path.exists():
            raise RepositoryError(
                "External repository initialization not completed. "
                "This typically indicates a session-level setup failure."
            )

    @pytest.fixture(scope="function")
    def test_config(self):
        """Get the current test configuration."""
        return get_test_config()

    @pytest.fixture(scope="function")
    def github_manager(self, test_config):
        """Create a GitHubTestManager instance for function-scoped tests."""
        return GitHubTestManager(config=test_config)

    @pytest.fixture(scope="class")
    def github_manager_class(self):
        """Create a GitHubTestManager instance for class-scoped tests."""
        return GitHubTestManager(config=get_test_config())

    @pytest.fixture(scope="function")
    def cloned_repo(self, github_manager):
        """Clone the current git repo to cache directory."""
        return github_manager.clone_current_repo()

    @pytest.fixture(scope="class")
    def test_repo(self, github_manager_class, initialize_external_repository):
        """Create a temporary repository using the configured primary repository.
        
        This fixture depends on session-scoped initialization and creates a local
        clone of the already-initialized external repository for each test class.
        
        Raises:
            RepositoryError: If repository doesn't exist or cloning fails
        """
        # Verify that initialization completed successfully
        cache_dir = Path("./cache/test/repo")
        complete_file_path = cache_dir / ".initialization_complete"
        
        if not complete_file_path.exists():
            raise RepositoryError(
                "External repository initialization not completed. "
                "Session-scoped initialization may have failed."
            )
        
        # Create unique repository name per thread for parallel execution
        repo_name = self.generate_unique_name("test-repo")

        repo_path = None
        try:
            # Create temporary local repository (external repo is already initialized)
            repo_path = github_manager_class.create_temp_repo(repo_name)

            # Ensure required labels exist (create if they don't exist)
            for label_name in github_manager_class.config.required_labels:
                if label_name == "triage":
                    github_manager_class.create_label(repo_path, label_name, "FFFF00", "Needs triage")
                elif label_name == "stale":
                    github_manager_class.create_label(repo_path, label_name, "CCCCCC", "Stale issue/PR")
                elif label_name == "ready for review":
                    github_manager_class.create_label(repo_path, label_name, "00FF00", "Ready for review")
                elif label_name == "feature-branch":
                    github_manager_class.create_label(repo_path, label_name, "0000FF", "Feature branch")

            # Create release and backport labels for testing
            github_manager_class.create_label(
                repo_path, "release 1.0", "00FF00", "Release 1.0"
            )

            github_manager_class.create_label(
                repo_path, "backport main", "0000FF", "Backport to main"
            )

            yield repo_path

        except Exception as e:
            # Re-raise with more context
            if isinstance(e, RepositoryError):
                raise
            else:
                raise RepositoryError(f"Failed to set up test repository: {e}")

        finally:
            # Cleanup: remove temporary directory (only if it was created)
            if repo_path is not None:
                subprocess.run(["rm", "-rf", str(repo_path)], check=False)

    @pytest.fixture(scope="class")
    def org_test_environment(self, github_manager_class, initialize_external_repository):
        """Create a complete organization + fork test environment.
        
        This fixture depends on session-scoped initialization to ensure the
        external repository is properly set up before creating test environments.
        
        Returns:
            Tuple[Path, Optional[Path]]: (org_repo_path, fork_repo_path)
        """
        org_repo_path, fork_repo_path = github_manager_class.create_organization_test_environment()
        
        # Set up required labels in organization repo
        for label_name in github_manager_class.config.required_labels:
            if label_name == "triage":
                github_manager_class.create_label(org_repo_path, label_name, "FFFF00", "Needs triage")
            elif label_name == "stale":
                github_manager_class.create_label(org_repo_path, label_name, "CCCCCC", "Stale issue/PR")
            elif label_name == "ready for review":
                github_manager_class.create_label(org_repo_path, label_name, "00FF00", "Ready for review")
            elif label_name == "feature-branch":
                github_manager_class.create_label(org_repo_path, label_name, "0000FF", "Feature branch")

        # Create release and backport labels for testing
        github_manager_class.create_label(
            org_repo_path, "release 1.0", "00FF00", "Release 1.0"
        )
        github_manager_class.create_label(
            org_repo_path, "backport main", "0000FF", "Backport to main"
        )
        
        yield org_repo_path, fork_repo_path

        # Cleanup: remove temporary directories
        subprocess.run(["rm", "-rf", str(org_repo_path)], check=False)
        if fork_repo_path:
            subprocess.run(["rm", "-rf", str(fork_repo_path)], check=False)

    @pytest.fixture(scope="class")
    def integration_manager(self, github_manager_class):
        """GitHub manager specifically for integration tests."""
        return github_manager_class

    @pytest.fixture(scope="session", autouse=True)
    def initialize_external_repository(self):
        """Initialize the external test repository once per test session.
        
        This fixture uses file locking to coordinate between parallel workers,
        ensuring that repository initialization happens exactly once per test session.
        """
        config = get_test_config()
        cache_dir = Path("./cache/test/repo")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        lock_file_path = cache_dir / ".initialization_lock"
        complete_file_path = cache_dir / ".initialization_complete"
        
        # ALWAYS force re-initialization by removing completion marker
        # This ensures the test repository is updated with current source code
        if complete_file_path.exists():
            print("🔄 Removing existing initialization marker to force repository update...")
            complete_file_path.unlink()
        
        # Clean up any stale lock files from previous runs
        if lock_file_path.exists():
            print("🧹 Cleaning up stale lock file from previous run...")
            lock_file_path.unlink()
        
        # Try to acquire lock for initialization
        try:
            with open(lock_file_path, 'w') as lock_file:
                try:
                    # Non-blocking lock attempt
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    print("🔒 Acquired initialization lock - performing repository setup...")
                    
                    # This worker will perform the initialization
                    manager = GitHubTestManager(cache_dir=cache_dir, config=config)
                    
                    try:
                        # Perform the actual initialization
                        success = manager.initialize_test_repository(config.primary_repo)
                        if success:
                            # Signal completion to other workers
                            complete_file_path.write_text("initialized")
                            print("✅ External repository initialization completed successfully")
                        else:
                            raise RepositoryError("Repository initialization returned False")
                            
                    except Exception as e:
                        print(f"❌ Repository initialization failed: {e}")
                        # Clean up partial state on failure
                        if complete_file_path.exists():
                            complete_file_path.unlink()
                        raise
                        
                except IOError:
                    # Lock is held by another process - wait for completion
                    print("⏳ Another worker is initializing repository, waiting...")
                    
                    # Wait for completion signal with timeout
                    timeout = 300  # 5 minutes
                    start_time = time.time()
                    
                    while not complete_file_path.exists():
                        if time.time() - start_time > timeout:
                            raise RepositoryError(
                                "Timeout waiting for repository initialization by another worker"
                            )
                        time.sleep(2)
                    
                    print("✅ Repository initialization completed by another worker")
                    
        except Exception as e:
            # Clean up lock file on any error
            if lock_file_path.exists():
                try:
                    lock_file_path.unlink()
                except:
                    pass
            raise
        finally:
            # Always clean up lock file when done
            try:
                if lock_file_path.exists():
                    lock_file_path.unlink()
            except:
                pass 