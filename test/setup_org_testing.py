#!/usr/bin/env python3
"""
Setup script for simplified organization testing environment.

This script helps configure the test environment for testing GitHub Actions
workflows across different organizations and repositories. The fixtures
handle repository cloning and GitHub Actions secrets setup automatically.

Usage:
    python test/setup_org_testing.py --help
    python test/setup_org_testing.py --org my-org --repo my-repo
    python test/setup_org_testing.py --validate
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from test_config import TestConfigManager, RepositoryConfig, TestingConfig, get_test_config


def check_prerequisites() -> Dict[str, bool]:
    """Check if required tools and configurations are available.
    
    Returns:
        Dict[str, bool]: Status of each prerequisite
    """
    prerequisites = {}
    
    # Check GitHub CLI
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
        prerequisites["gh_cli"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        prerequisites["gh_cli"] = False
    
    # Check Git
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        prerequisites["git"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        prerequisites["git"] = False
    
    # Check GitHub authentication
    try:
        subprocess.run(["gh", "auth", "status"], capture_output=True, check=True)
        prerequisites["gh_auth"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        prerequisites["gh_auth"] = False
    
    # Check pytest
    try:
        subprocess.run([sys.executable, "-m", "pytest", "--version"], capture_output=True, check=True)
        prerequisites["pytest"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        prerequisites["pytest"] = False
    
    return prerequisites


def validate_repository_access(org: str, repo: str) -> bool:
    """Validate that the repository exists and is accessible.
    
    Args:
        org: GitHub organization/user name
        repo: Repository name
        
    Returns:
        bool: True if repository is accessible
    """
    try:
        subprocess.run(
            ["gh", "repo", "view", f"{org}/{repo}"],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def create_env_file(org: str, repo: str, env_file_path: Path = Path(".env")) -> bool:
    """Create .env file with basic configuration.
    
    Args:
        org: GitHub organization name
        repo: Repository name
        env_file_path: Path to .env file
        
    Returns:
        bool: True if file was created successfully
    """
    try:
        with open(env_file_path, "w") as f:
            f.write(f'# GitHub repository configuration for testing\n')
            f.write(f'TEST_GITHUB_ORG="{org}"\n')
            f.write(f'TEST_GITHUB_REPO="{repo}"\n')
            f.write(f'\n# Required: GitHub token for authentication\n')
            f.write(f'GITHUB_TOKEN=your_token_here\n')
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False


def validate_workflow_files() -> Dict[str, bool]:
    """Validate GitHub Actions workflow files exist.
    
    Returns:
        Dict[str, bool]: Status of each workflow file
    """
    workflows_dir = Path(".github/workflows")
    if not workflows_dir.exists():
        return {}
    
    workflow_files = {}
    for workflow_file in workflows_dir.glob("keeper-*.yml"):
        workflow_files[workflow_file.name] = True
    
    return workflow_files


def print_setup_summary(config: TestingConfig, prerequisites: Dict[str, bool]):
    """Print a summary of the setup configuration.
    
    Args:
        config: Current testing configuration
        prerequisites: Prerequisites check results
    """
    print("\n" + "="*60)
    print("📋 TESTING CONFIGURATION SUMMARY")
    print("="*60)
    
    print(f"\n🎯 Primary Repository:")
    print(f"   Organization: {config.primary_repo.owner}")
    print(f"   Repository:   {config.primary_repo.repo}")
    print(f"   Full Name:    {config.primary_repo.full_name}")
    print(f"   GitHub URL:   {config.primary_repo.github_url}")
    
    print(f"\n🔧 Prerequisites:")
    for name, status in prerequisites.items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {name.replace('_', ' ').title()}")
    
    print(f"\n⚙️ Configuration:")
    print(f"   Test Timeout:  {config.test_timeout}s")
    print(f"   Poll Interval: {config.poll_interval}s")
    
    workflow_files = validate_workflow_files()
    print(f"\n📋 Workflow Files:")
    if workflow_files:
        for filename, exists in workflow_files.items():
            icon = "✅" if exists else "❌"
            print(f"   {icon} {filename}")
    else:
        print(f"   ⚠️ No keeper-*.yml workflow files found")
    
    print(f"\n🚀 Usage:")
    print(f"   # Run all fork compatibility tests:")
    print(f"   ./venv/bin/pytest -m fork_compatibility -v")
    print(f"   ")
    print(f"   # Run specific test:")
    print(f"   ./venv/bin/pytest test/test_basic_functionality.py::TestBasicFunctionality::test_hello -v")
    print(f"   ")
    print(f"   # List all fork compatibility tests:")
    print(f"   ./venv/bin/pytest --collect-only -m fork_compatibility")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(
        description="Setup simplified organization testing environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup for specific org/repo
  python test/setup_org_testing.py --org my-org --repo my-repo
  
  # Validate current configuration
  python test/setup_org_testing.py --validate
  
  # Show current configuration
  python test/setup_org_testing.py --config
        """
    )
    
    parser.add_argument(
        "--org",
        help="GitHub organization name"
    )
    
    parser.add_argument(
        "--repo", 
        help="Repository name"
    )
    
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate current configuration and prerequisites"
    )
    
    parser.add_argument(
        "--config",
        action="store_true", 
        help="Show current configuration"
    )
    
    parser.add_argument(
        "--env-file",
        action="store_true",
        help="Create .env file with specified org/repo"
    )
    
    args = parser.parse_args()
    
    # Check prerequisites
    prerequisites = check_prerequisites()
    
    if args.validate or args.config:
        # Show current configuration
        try:
            config = get_test_config()
            print_setup_summary(config, prerequisites)
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            return 1
        
        if args.validate:
            # Validate repository access
            config = get_test_config()
            print(f"\n🔍 Validating repository access...")
            
            repo_accessible = validate_repository_access(
                config.primary_repo.owner,
                config.primary_repo.repo
            )
            
            if repo_accessible:
                print(f"   ✅ Repository {config.primary_repo.full_name} is accessible")
            else:
                print(f"   ❌ Repository {config.primary_repo.full_name} is not accessible")
                print(f"      Check your GitHub authentication and repository permissions")
                return 1
        
        return 0
    
    if args.org and args.repo:
        # Validate repository exists
        print(f"🔍 Validating repository {args.org}/{args.repo}...")
        
        if not validate_repository_access(args.org, args.repo):
            print(f"❌ Repository {args.org}/{args.repo} is not accessible")
            print(f"   Please check:")
            print(f"   - Repository name is correct")
            print(f"   - You have access to the repository")
            print(f"   - GitHub CLI is authenticated (run 'gh auth status')")
            return 1
        
        print(f"✅ Repository {args.org}/{args.repo} is accessible")
        
        if args.env_file:
            # Create .env file
            print(f"📝 Creating .env file...")
            
            if create_env_file(args.org, args.repo):
                print(f"✅ Created .env file with:")
                print(f"   TEST_GITHUB_ORG=\"{args.org}\"")
                print(f"   TEST_GITHUB_REPO=\"{args.repo}\"")
            else:
                return 1
        
        # Show configuration summary
        try:
            config = get_test_config()
            print_setup_summary(config, prerequisites)
        except Exception as e:
            print(f"❌ Failed to load updated configuration: {e}")
            return 1
        
        return 0
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 