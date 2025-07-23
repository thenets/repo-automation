# GitHub Organization + Fork Testing Implementation Plan

## Problem Statement

Based on the current README.md, there are significant limitations in testing GitHub Actions workflows with forks in organizational contexts:

### Current Limitations

1. **Permission Issues**: Traditional GitHub Actions workflows fail when triggered by pull requests from forks because:
   - Forked repositories don't have access to the original repository's secrets
   - GitHub's default `GITHUB_TOKEN` has limited permissions for external contributors
   - Workflows cannot add labels to pull requests from forks without elevated permissions

2. **Testing Gaps**: Current test suite uses real GitHub API calls but doesn't properly simulate:
   - External contributor workflows (fork → organization repo)
   - Fine-grained token permission scenarios
   - Cross-repository workflow triggers (`workflow_run` events)
   - Organization-level permission inheritance

3. **Repository Context**: Workflows have hardcoded repository checks (`if: github.repository == 'thenets/repo-automations'`) that need organizational context testing

## Implementation Plan

### Phase 1: Research & Design
**Goal**: Identify optimal testing architecture for GitHub Org + fork workflows

#### 1.1 Investigation Tasks
- [ ] **Research GitHub Organization Testing Patterns**
  - Study how major open-source projects test fork workflows
  - Investigate GitHub's official testing recommendations for organizations
  - Research testing frameworks for multi-repository scenarios

- [ ] **Analyze Current Architecture Limitations**
  - Map current two-workflow pattern (`keeper-trigger.yml` → action workflows)
  - Identify permission boundary issues in current tests
  - Document workflow trigger chain dependencies

- [ ] **Design Testing Architecture Options**
  - **Option A**: Use multiple test repositories (org repo + fork repo)
  - **Option B**: Simulate fork scenarios with branch-based testing
  - **Option C**: Use GitHub Apps for enhanced permissions
  - **Option D**: Hybrid approach with real forks + mock scenarios

#### 1.2 Technical Requirements Analysis
- [ ] **Permission Mapping**
  - Document required permissions for each workflow
  - Map fine-grained token vs default token scenarios
  - Identify minimum viable permissions for external contributors

- [ ] **Workflow Trigger Dependencies**
  - Test `workflow_run` trigger reliability across repositories
  - Validate artifact sharing between trigger and action workflows
  - Document timing and race condition considerations

### Phase 2: Test Environment Setup
**Goal**: Establish isolated testing environment for org + fork scenarios

#### 2.1 GitHub Organization Setup
- [ ] **Create Test Organization**
  - Set up dedicated GitHub organization for testing (e.g., `repo-automations-testing`)
  - Configure organization-level settings and permissions
  - Create main repository: `repo-automations-testing/test-main-repo`

- [ ] **Fork Repository Setup**
  - Create fork from personal account: `username/test-main-repo`
  - Configure fork-specific settings and permissions
  - Set up test data and baseline repository state

#### 2.2 Token and Permission Configuration
- [ ] **Fine-Grained Token Setup**
  - Create organization-level fine-grained personal access token
  - Configure minimum required permissions for testing
  - Document token scope limitations and requirements

- [ ] **Test User Accounts**
  - Set up external contributor simulation account
  - Configure different permission levels (collaborator vs external)
  - Document access patterns for each user type

#### 2.3 Test Data Infrastructure
- [ ] **Repository State Management**
  - Create scripts for repository reset/cleanup between tests
  - Set up baseline labels, branches, and configuration
  - Implement test isolation mechanisms

- [ ] **Workflow Configuration**
  - Deploy test versions of all keeper workflows to test organization
  - Update repository references to point to test organization
  - Configure test-specific trigger conditions and timeouts

### Phase 3: Test Suite Enhancement
**Goal**: Enhance existing test suite to properly handle org + fork scenarios

#### 3.1 Test Framework Updates
- [ ] **Multi-Repository Test Manager**
  - Extend `GitHubTestManager` in `test/conftest.py` to handle multiple repositories
  - Add fork creation and management capabilities
  - Implement cross-repository PR and workflow testing

- [ ] **Organization Context Testing**
  - Add organization-aware test fixtures
  - Implement permission level testing (external vs collaborator)
  - Add fine-grained token vs default token test scenarios

#### 3.2 Fork Workflow Testing
- [ ] **Cross-Repository PR Testing**
  ```python
  class TestForkWorkflows(GitHubFixtures):
      def test_external_contributor_pr_labeling(self, org_repo, fork_repo, external_user):
          """Test that external contributor PRs trigger workflows correctly."""
          # Create PR from fork to organization repo
          # Verify workflow triggers and completes
          # Validate labels are applied correctly
  ```

- [ ] **Workflow Trigger Chain Testing**
  - Test `keeper-trigger.yml` execution on forks
  - Verify artifact creation and upload from fork
  - Test `workflow_run` trigger reliability in organization repo
  - Validate action workflow execution with downloaded artifacts

#### 3.3 Permission Scenario Testing
- [ ] **Token Permission Testing**
  - Test workflows with default `GITHUB_TOKEN` (expected to fail gracefully)
  - Test workflows with fine-grained token (expected to succeed)
  - Validate error messages for permission failures

- [ ] **User Role Testing**
  - Test external contributor scenarios (no org permissions)
  - Test collaborator scenarios (limited org permissions)
  - Test maintainer scenarios (full org permissions)

### Phase 4: Test Implementation
**Goal**: Implement comprehensive test coverage for all org + fork scenarios

#### 4.1 Enhanced Test Files
- [ ] **`test_fork_compatibility.py`**
  ```python
  @pytest.mark.integration
  @pytest.mark.org_testing
  class TestForkWorkflows:
      # External contributor workflow tests
      # Cross-repository trigger tests
      # Permission boundary tests
  ```

- [ ] **`test_organization_workflows.py`**
  ```python
  @pytest.mark.integration
  @pytest.mark.org_testing  
  class TestOrganizationWorkflows:
      # Organization-specific workflow tests
      # Fine-grained token tests
      # Multi-user scenario tests
  ```

#### 4.2 Updated Existing Tests
- [ ] **Update `test_triage_auto_add.py`**
  - Add fork-based triage label testing
  - Test external contributor PR triage workflows
  - Validate organization repository restrictions

- [ ] **Update `test_release_backport_labeler.py`**
  - Add cross-repository YAML parsing tests
  - Test fork-to-org PR label application
  - Validate error reporting across repositories

- [ ] **Update `test_feature_branch_labeler.py`**
  - Add fork-based feature branch labeling tests
  - Test external contributor feature branch workflows
  - Validate cross-repository error reporting

#### 4.3 Integration Test Infrastructure
- [ ] **Parallel Test Execution**
  - Ensure fork-based tests don't interfere with each other
  - Implement proper test isolation for multi-repository scenarios
  - Add cleanup mechanisms for cross-repository test artifacts

- [ ] **Performance Optimization**
  - Optimize test execution time for multi-repository scenarios
  - Implement caching for repository setup/teardown
  - Add parallel execution support for fork-based tests

### Phase 5: Documentation & Best Practices
**Goal**: Comprehensive documentation of org + fork testing approach

#### 5.1 README.md Updates
- [ ] **Update Testing Section**
  - Document new org + fork testing requirements
  - Add setup instructions for test organization
  - Document permission requirements and token setup

- [ ] **Update Development Section**
  - Add guidelines for testing fork-compatible workflows
  - Document best practices for cross-repository testing
  - Add troubleshooting guide for permission issues

#### 5.2 Test Documentation
- [ ] **Create `TESTING_FORKS.md`**
  ```markdown
  # Fork Testing Guide
  
  ## Overview
  This guide covers testing GitHub Actions workflows with organizational repositories and external contributor forks.
  
  ## Setup Requirements
  - Test organization: repo-automations-testing
  - Fork repository configuration
  - Fine-grained token setup
  
  ## Test Scenarios
  - External contributor PR workflows
  - Cross-repository trigger testing
  - Permission boundary validation
  ```

- [ ] **Test Architecture Documentation**
  - Document multi-repository test patterns
  - Create diagrams for fork workflow testing
  - Document permission testing scenarios

#### 5.3 Troubleshooting Guides
- [ ] **Permission Issue Troubleshooting**
  - Common permission errors and solutions
  - Token scope validation procedures
  - Organization settings requirements

- [ ] **Workflow Debugging Guide**
  - Cross-repository workflow debugging
  - Artifact sharing troubleshooting
  - Timing and race condition identification

## Success Criteria

### Phase 1 Success Metrics
- [ ] Clear understanding of GitHub org + fork testing architecture
- [ ] Documented comparison of testing approach options
- [ ] Technical requirements fully mapped

### Phase 2 Success Metrics
- [ ] Functional test organization with proper permissions
- [ ] Working fork repository with test workflows deployed
- [ ] Validated cross-repository workflow trigger chain

### Phase 3 Success Metrics
- [ ] Enhanced test framework supporting multi-repository scenarios
- [ ] Successful external contributor PR simulation
- [ ] Comprehensive permission scenario coverage

### Phase 4 Success Metrics
- [ ] Complete test suite passing for all org + fork scenarios
- [ ] Reliable cross-repository workflow testing
- [ ] Performance-optimized test execution

### Phase 5 Success Metrics
- [ ] Comprehensive documentation for org + fork testing
- [ ] Clear setup instructions for new contributors
- [ ] Troubleshooting guides for common issues

## Risk Mitigation

### Technical Risks
- **GitHub API Rate Limits**: Implement test batching and caching
- **Workflow Timing Issues**: Add robust polling and timeout mechanisms
- **Permission Complexity**: Create permission validation utilities

### Operational Risks
- **Test Environment Maintenance**: Automate test org cleanup and reset
- **Cost Management**: Monitor GitHub Actions usage in test organization
- **Security Considerations**: Use minimal viable permissions for testing

## Implementation Order

| Phase | Dependencies | Deliverables |
|-------|--------------|--------------|
| Phase 1 | - | Research findings, architecture design |
| Phase 2 | Phase 1 | Test organization, fork setup |
| Phase 3 | Phase 2 | Enhanced test framework |
| Phase 4 | Phase 3 | Complete test implementation |
| Phase 5 | Phase 4 | Documentation and guides |

## Next Steps

1. **Begin Phase 1**: Start with GitHub organization testing pattern research
2. **Create Test Organization**: Set up dedicated testing environment
3. **Validate Approach**: Test workflow trigger chain with real fork scenario
4. **Iterate on Design**: Refine testing architecture based on initial findings 