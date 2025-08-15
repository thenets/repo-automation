"""
Configuration system for multi-repository GitHub Actions testing.

This module provides configuration management for testing GitHub Actions workflows
across different organizations and repositories, supporting fork-based testing
scenarios as outlined in the implementation plan.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_env_file(env_file_path: Path = Path(".env")) -> Dict[str, str]:
    """Load environment variables from .env file.
    
    Args:
        env_file_path: Path to the .env file
        
    Returns:
        Dict[str, str]: Environment variables loaded from file
    """
    env_vars = {}
    
    if not env_file_path.exists():
        return env_vars
    
    try:
        with open(env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE format
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    env_vars[key] = value
                    
    except Exception as e:
        print(f"Warning: Error reading .env file: {e}")
    
    return env_vars


def get_current_repository() -> Optional[Tuple[str, str]]:
    """Get current repository from git remote origin for validation purposes only.
    
    Returns:
        Optional[Tuple[str, str]]: (owner, repo) or None if not found
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True
        )
        
        remote_url = result.stdout.strip()
        
        # Parse GitHub URL to extract owner and repo
        if "github.com" in remote_url:
            # Handle both SSH and HTTPS URLs
            if remote_url.startswith("git@github.com:"):
                repo_part = remote_url.replace("git@github.com:", "").replace(".git", "")
            else:
                repo_part = remote_url.replace("https://github.com/", "").replace(".git", "")
            
            if "/" in repo_part:
                owner, repo = repo_part.split("/", 1)
                return owner, repo
                
    except subprocess.CalledProcessError:
        pass
    
    return None


def validate_repository_exists(owner: str, repo: str) -> bool:
    """Validate that a GitHub repository exists using gh CLI.
    
    Args:
        owner: Repository owner
        repo: Repository name
        
    Returns:
        bool: True if repository exists and is accessible
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "view", f"{owner}/{repo}"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def validate_workflow_repository_references(
    workflow_dir: Path,
    expected_owner: str,
    expected_repo: str
) -> List[str]:
    """Validate that workflow files reference the correct repository.
    
    Args:
        workflow_dir: Directory containing workflow files
        expected_owner: Expected repository owner
        expected_repo: Expected repository name
        
    Returns:
        List[str]: List of validation issues found
    """
    issues = []
    expected_full_name = f"{expected_owner}/{expected_repo}"
    
    if not workflow_dir.exists():
        issues.append(f"Workflow directory {workflow_dir} does not exist")
        return issues
    
    workflow_files = list(workflow_dir.glob("keeper-*.yml"))
    if not workflow_files:
        issues.append(f"No keeper-*.yml workflow files found in {workflow_dir}")
        return issues
    
    for workflow_file in workflow_files:
        try:
            content = workflow_file.read_text()
            
            # Check for github.repository conditions
            repo_conditions = re.findall(r"github\.repository == ['\"]([^'\"]+)['\"]", content)
            
            for found_repo in repo_conditions:
                if found_repo != expected_full_name:
                    issues.append(
                        f"{workflow_file.name}: Repository condition '{found_repo}' should be '{expected_full_name}'"
                    )
            
            # Check for hardcoded repository URLs in comments
            url_pattern = r"# Source: https://github\.com/([^/]+)/([^\s]+)"
            url_matches = re.findall(url_pattern, content)
            
            for url_owner, url_repo in url_matches:
                url_repo = url_repo.rstrip('/')  # Remove trailing slash if present
                if f"{url_owner}/{url_repo}" != expected_full_name:
                    issues.append(
                        f"{workflow_file.name}: Source URL references '{url_owner}/{url_repo}' should be '{expected_full_name}'"
                    )
                    
        except Exception as e:
            issues.append(f"{workflow_file.name}: Error reading file - {e}")
    
    return issues


@dataclass
class RepositoryConfig:
    """Configuration for a single repository in testing scenarios."""
    
    owner: str
    repo: str
    is_organization: bool = False
    is_fork: bool = False
    fork_parent: Optional[str] = None  # Format: "org/repo"
    
    @property
    def full_name(self) -> str:
        """Get the full repository name in owner/repo format."""
        return f"{self.owner}/{self.repo}"
    
    @property
    def github_url(self) -> str:
        """Get the GitHub HTTPS URL for the repository."""
        return f"https://github.com/{self.full_name}.git"


@dataclass
class TestingConfig:
    """Configuration for multi-repository testing scenarios."""
    
    # Primary repository (organization repo)
    primary_repo: RepositoryConfig
    
    # Fork repository (external contributor simulation)
    fork_repo: Optional[RepositoryConfig] = None
    
    # GitHub token configuration
    github_token_env_var: str = "GITHUB_TOKEN" 
    
    # Test environment settings
    cache_dir: str = "./cache/test/repo"
    test_timeout: int = 300  # 5 minutes default timeout
    poll_interval: int = 10  # 10 seconds default polling
    
    # Workflow configuration
    workflow_base_path: str = ".github/workflows"
    required_labels: List[str] = None
    
    def __post_init__(self):
        """Initialize default values after object creation."""
        if self.required_labels is None:
            self.required_labels = [
                "triage", 
                "stale", 
                "ready for review",
                "feature-branch"
            ]


class TestConfigManager:
    """Manages test configuration from .env file and git remote origin."""
    
    @staticmethod
    def load_from_env_file(env_file_path: Path = Path(".env")) -> TestingConfig:
        """Load testing configuration from .env file with fallback to git remote.
        
        Args:
            env_file_path: Path to the .env file
            
        Environment Variables:
        - TEST_GITHUB_ORG: Organization/user name (required)
        - TEST_GITHUB_REPO: Repository name (required)
        - TEST_FORK_OWNER: Fork owner for external contributor simulation (optional)
        - TEST_FORK_REPO: Fork repository name (optional, defaults to same as main repo)
        - GITHUB_TOKEN: GitHub token for repository access
        - TEST_CACHE_DIR: Cache directory for test repositories
        - TEST_TIMEOUT: Timeout for workflow operations (seconds)
        - TEST_POLL_INTERVAL: Polling interval for workflow checks (seconds)
        
        Returns:
            TestingConfig: Configured testing environment
        """
        # Load all environment variables from .env file
        env_vars = load_env_file(env_file_path)
        
        # Apply loaded environment variables to current environment
        for key, value in env_vars.items():
            os.environ[key] = value
        
        print(f"Loaded {len(env_vars)} environment variables from {env_file_path}")
        
        # Get primary repository configuration - strict enforcement
        primary_owner = env_vars.get("TEST_GITHUB_ORG") or os.getenv("TEST_GITHUB_ORG")
        primary_repo = env_vars.get("TEST_GITHUB_REPO") or os.getenv("TEST_GITHUB_REPO")
        
        # Require explicit configuration - no fallback
        if not primary_owner or not primary_repo:
            raise ValueError(
                "TEST_GITHUB_ORG and TEST_GITHUB_REPO are required. "
                "Please set them in .env file or environment variables. "
                "Example .env file:\n"
                'TEST_GITHUB_ORG="my-org"\n'
                'TEST_GITHUB_REPO="my-repo"\n'
                'GITHUB_TOKEN="ghp_your_token_here"'
            )
        
        # Validate repository exists and is external
        current_repo = get_current_repository()
        if current_repo and current_repo == (primary_owner, primary_repo):
            raise ValueError(
                f"Cannot run tests on the same repository ({primary_owner}/{primary_repo}). "
                "Tests must run against an external repository to validate cross-repository workflows. "
                "Please set TEST_GITHUB_ORG and TEST_GITHUB_REPO to a different repository."
            )
        
        print(f"Validating external repository {primary_owner}/{primary_repo}...")
        if not validate_repository_exists(primary_owner, primary_repo):
            raise ValueError(
                f"Repository {primary_owner}/{primary_repo} does not exist or is not accessible. "
                "Please check the repository name and your GitHub authentication."
            )
        
        print(f"✅ Repository {primary_owner}/{primary_repo} validated successfully")
        
        # Check workflow files for correct repository references
        workflow_dir = Path(".github/workflows")
        workflow_issues = validate_workflow_repository_references(
            workflow_dir, 
            primary_owner, 
            primary_repo
        )
        
        if workflow_issues:
            print("⚠️ Workflow file validation issues found:")
            for issue in workflow_issues:
                print(f"   - {issue}")
            print("💡 Consider updating workflow files to match your repository configuration")
        else:
            print("✅ Workflow files validated successfully")
        
        # Create primary repository config
        primary_config = RepositoryConfig(
            owner=primary_owner,
            repo=primary_repo,
            is_organization=True,  # Assume organization for testing
            is_fork=False
        )
        
        # Load fork repository configuration if specified
        fork_config = None
        fork_owner = env_vars.get("TEST_FORK_OWNER") or os.getenv("TEST_FORK_OWNER")
        if fork_owner:
            fork_repo_name = env_vars.get("TEST_FORK_REPO") or os.getenv("TEST_FORK_REPO") or primary_repo
            
            # Validate fork repository exists
            print(f"Validating fork repository {fork_owner}/{fork_repo_name}...")
            if validate_repository_exists(fork_owner, fork_repo_name):
                fork_config = RepositoryConfig(
                    owner=fork_owner,
                    repo=fork_repo_name,
                    is_organization=False,
                    is_fork=True,
                    fork_parent=primary_config.full_name
                )
                print(f"✅ Fork repository {fork_owner}/{fork_repo_name} validated successfully")
            else:
                print(f"⚠️ Fork repository {fork_owner}/{fork_repo_name} not found or not accessible")
                print("💡 Fork-based tests will be skipped")
        
        # Load other configuration
        cache_dir = env_vars.get("TEST_CACHE_DIR") or os.getenv("TEST_CACHE_DIR", "./cache/test/repo")
        test_timeout = int(env_vars.get("TEST_TIMEOUT") or os.getenv("TEST_TIMEOUT", "300"))
        poll_interval = int(env_vars.get("TEST_POLL_INTERVAL") or os.getenv("TEST_POLL_INTERVAL", "10"))
        
        return TestingConfig(
            primary_repo=primary_config,
            fork_repo=fork_config,
            cache_dir=cache_dir,
            test_timeout=test_timeout,
            poll_interval=poll_interval
        )
    
    @staticmethod
    def create_default_config() -> TestingConfig:
        """Deprecated: Configuration must be explicitly provided.
        
        Raises:
            ValueError: Always raises as default configuration is not allowed
        """
        raise ValueError(
            "Default configuration is not allowed. "
            "Please create a .env file with TEST_GITHUB_ORG and TEST_GITHUB_REPO "
            "or set them as environment variables."
        )
    
    @staticmethod
    def create_org_fork_config(
        org_owner: str,
        org_repo: str,
        fork_owner: str,
        fork_repo: Optional[str] = None
    ) -> TestingConfig:
        """Create configuration for organization + fork testing scenario.
        
        Args:
            org_owner: Organization owner name
            org_repo: Organization repository name
            fork_owner: Fork owner name (external contributor)
            fork_repo: Fork repository name (defaults to org_repo)
            
        Returns:
            TestingConfig: Configuration for org + fork testing
        """
        if fork_repo is None:
            fork_repo = org_repo
            
        primary_config = RepositoryConfig(
            owner=org_owner,
            repo=org_repo,
            is_organization=True,
            is_fork=False
        )
        
        fork_config = RepositoryConfig(
            owner=fork_owner,
            repo=fork_repo,
            is_organization=False,
            is_fork=True,
            fork_parent=primary_config.full_name
        )
        
        return TestingConfig(
            primary_repo=primary_config,
            fork_repo=fork_config
        )


def get_test_config() -> TestingConfig:
    """Get the appropriate test configuration.
    
    Attempts to load from .env file first, falls back to git remote origin or defaults.
    
    Returns:
        TestingConfig: Active testing configuration
    """
    # Always try to load from .env file first
    env_file = Path(".env")
    if env_file.exists():
        try:
            return TestConfigManager.load_from_env_file(env_file)
        except Exception as e:
            raise ValueError(
                f"Error loading configuration from .env file: {e}. "
                "Please ensure your .env file is properly formatted with TEST_GITHUB_ORG and TEST_GITHUB_REPO."
            )
    
    # No fallback - require explicit configuration
    raise ValueError(
        "No .env file found. Please create .env file with TEST_GITHUB_ORG and TEST_GITHUB_REPO."
    )


def get_workflow_repository_check(repo_config: RepositoryConfig) -> str:
    """Generate the repository check condition for GitHub Actions workflows.
    
    Args:
        repo_config: Repository configuration
        
    Returns:
        str: The condition string for workflow if statements
    """
    return f"github.repository == '{repo_config.full_name}'"


def update_workflow_repository_references(
    workflow_path: Path,
    target_repo: RepositoryConfig,
    backup: bool = True
) -> bool:
    """Update repository references in a workflow file.
    
    Args:
        workflow_path: Path to the workflow file
        target_repo: Target repository configuration
        backup: Whether to create a backup of the original file
        
    Returns:
        bool: True if update was successful
    """
    try:
        if not workflow_path.exists():
            return False
            
        # Read original content
        content = workflow_path.read_text()
        
        # Create backup if requested
        if backup:
            backup_path = workflow_path.with_suffix(workflow_path.suffix + '.backup')
            backup_path.write_text(content)
        
        # Replace repository references
        # Update repository condition checks
        import re
        
        # Pattern to match: github.repository == 'owner/repo'
        repo_pattern = r"github\.repository == '[^']+'"
        new_condition = f"github.repository == '{target_repo.full_name}'"
        content = re.sub(repo_pattern, new_condition, content)
        
        # Update source comments
        source_pattern = r"# Source: https://github\.com/[^/]+/[^\s]+"
        new_source = f"# Source: https://github.com/{target_repo.full_name}"
        content = re.sub(source_pattern, new_source, content)
        
        # Write updated content
        workflow_path.write_text(content)
        
        return True
        
    except Exception:
        return False 