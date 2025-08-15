# GitHub Action Migration Plan

## Important Documentation References

### GitHub Actions Development
- **Creating Actions**: https://docs.github.com/en/actions/creating-actions
- **About Custom Actions**: https://docs.github.com/en/actions/creating-actions/about-custom-actions
- **Creating a Composite Action**: https://docs.github.com/en/actions/creating-actions/creating-a-composite-action
- **Metadata Syntax for GitHub Actions**: https://docs.github.com/en/actions/creating-actions/metadata-syntax-for-github-actions
- **Publishing Actions**: https://docs.github.com/en/actions/creating-actions/publishing-actions-in-github-marketplace

### GitHub API & Automation
- **GitHub REST API**: https://docs.github.com/en/rest
- **Working with GitHub Apps**: https://docs.github.com/en/apps
- **GitHub Scripts Action**: https://github.com/actions/github-script
- **Workflow Syntax**: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions

### Token & Permissions
- **Permissions for GITHUB_TOKEN**: https://docs.github.com/en/actions/security-guides/automatic-token-authentication
- **Fine-grained Personal Access Tokens**: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#fine-grained-personal-access-tokens
- **Assigning Permissions to Jobs**: https://docs.github.com/en/actions/using-jobs/assigning-permissions-to-jobs

### Testing & Validation
- **Testing Actions**: https://docs.github.com/en/actions/creating-actions/testing-actions
- **Local Action Testing**: https://github.com/nektos/act
- **Mock GitHub API**: https://github.com/octokit/fixtures

### Publishing & Distribution
- **GitHub Marketplace**: https://github.com/marketplace/actions
- **Semantic Versioning**: https://semver.org/
- **Action Versioning**: https://docs.github.com/en/actions/creating-actions/about-custom-actions#using-release-management-for-actions

### Composite Actions Specific
- **Composite Actions Examples**: https://github.com/actions/toolkit/tree/main/docs
- **Action Input/Output Best Practices**: https://docs.github.com/en/actions/creating-actions/metadata-syntax-for-github-actions#inputs
- **Environment Variables in Actions**: https://docs.github.com/en/actions/learn-github-actions/variables

### JavaScript/Node.js Development
- **Node.js GitHub Actions**: https://docs.github.com/en/actions/creating-actions/creating-a-javascript-action
- **Actions Toolkit**: https://github.com/actions/toolkit
- **Core Functions (@actions/core)**: https://github.com/actions/toolkit/tree/main/packages/core
- **GitHub API (@actions/github)**: https://github.com/actions/toolkit/tree/main/packages/github
- **Octokit REST API**: https://octokit.github.io/rest.js/

### GitHub Labels & Issues API
- **Issues API**: https://docs.github.com/en/rest/issues
- **Labels API**: https://docs.github.com/en/rest/issues/labels
- **Pull Requests API**: https://docs.github.com/en/rest/pulls
- **Repository API**: https://docs.github.com/en/rest/repos

### Security & Best Practices
- **Security Hardening**: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions
- **Using Secrets**: https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions
- **Script Injection Prevention**: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#understanding-the-risk-of-script-injections

### Example Actions for Reference
- **GitHub Labeler**: https://github.com/actions/labeler
- **Stale Action**: https://github.com/actions/stale
- **First Interaction**: https://github.com/actions/first-interaction
- **GitHub Script Examples**: https://github.com/actions/github-script#examples

### Current Project References
- **Repository Automations README**: [README.md](README.md)
- **Testing Documentation**: [README_TESTING.md](README_TESTING.md)
- **Current Workflows**: [.github/workflows/](.github/workflows/)
- **Current keeper-triage.yml**: [.github/workflows/keeper-triage.yml](.github/workflows/keeper-triage.yml)
- **Current keeper-trigger.yml**: [.github/workflows/keeper-trigger.yml](.github/workflows/keeper-trigger.yml)
- **Current keeper-stale-pr-detector.yml**: [.github/workflows/keeper-stale-pr-detector.yml](.github/workflows/keeper-stale-pr-detector.yml)

## Problem Statement

The current repository automation workflows (keeper-*) have several limitations that make them difficult to adopt and maintain:

### Current Limitations

1. **Repository-Specific Configuration**: Each workflow has hardcoded repository references (`if: github.repository == 'dednets/repo-automation-test'`) that must be manually updated for each new repository.

2. **Complex Setup Process**: New repositories need to:
   - Copy multiple workflow files
   - Update repository references in each file
   - Configure required labels and permissions
   - Set up custom tokens for fork compatibility

3. **Maintenance Overhead**: Bug fixes and feature improvements require updates across multiple repositories using these workflows.

4. **Limited Reusability**: The current workflows are tightly coupled to specific repository contexts, making them difficult to share across organizations or open-source projects.

5. **Inconsistent Adoption**: Different repositories may use different versions or configurations, leading to inconsistent behavior across projects.

## Goal

Transform the existing keeper-* workflows into a reusable, publishable GitHub Action that can be easily adopted by any repository with minimal configuration.

## Migration Strategy: Composite GitHub Action

### Why Composite Action?

- **Complex Logic**: The existing workflows contain sophisticated JavaScript logic that is best preserved in a composite action
- **Multi-Step Processes**: Triage management, stale detection, and auto-labeling involve multiple coordinated steps
- **Flexibility**: Composite actions allow mixing of shell commands and action references
- **Maintainability**: Centralized logic with versioned releases

## Implementation Plan

### Phase 1: Action Structure Design 📝 **Planned**

**Goal**: Design the GitHub Action repository structure and metadata

#### 1.1 Repository Structure
```
action.yml                     # Main action metadata
src/
├── triage-management.js       # Extracted from keeper-triage.yml
├── stale-detection.js         # Extracted from keeper-stale-pr-detector.yml
├── label-automation.js        # Release/backport/feature labeling logic
└── utils/
    ├── github-client.js       # GitHub API utilities
    └── config.js              # Configuration management
README.md                      # Action documentation
examples/                      # Usage examples
├── basic-usage.yml
├── advanced-configuration.yml
└── fork-compatible-setup.yml
```

#### 1.2 Action Metadata Design (action.yml)
- **Name**: "Repository Automation Keeper"
- **Description**: "Automated triage, labeling, and maintenance for GitHub repositories"
- **Type**: Composite action
- **Inputs**:
  - `github-token` (required): GitHub token for API access
  - `custom-github-token` (optional): Custom token for external contributor support
  - `automation-type` (required): Type of automation (triage|stale-detection|auto-labeling|all)
  - `accepted-releases` (optional): JSON array of accepted release versions
  - `accepted-backports` (optional): JSON array of accepted backport versions
  - `stale-days` (optional): Days before marking PRs as stale (default: 1)
  - `dry-run` (optional): Preview mode without making changes
- **Outputs**:
  - `labels-added`: JSON array of labels that were added
  - `labels-removed`: JSON array of labels that were removed
  - `actions-taken`: Summary of all actions performed

### Phase 2: Extract and Modularize Logic 📝 **Planned**

**Goal**: Convert existing workflow JavaScript into modular, reusable components

#### 2.1 Logic Extraction Tasks
- [ ] **Triage Management Logic**
  - Extract JavaScript from `keeper-triage.yml`
  - Create modular functions for label adding, protection, and ready-for-review logic
  - Preserve fork compatibility mechanisms

- [ ] **Stale Detection Logic**
  - Extract from `keeper-stale-pr-detector.yml`
  - Create configurable stale detection with customizable timeframes
  - Maintain manual trigger capabilities

- [ ] **Auto-Labeling Logic**
  - Extract from `keeper-auto-label-release-backport.yml` and `keeper-feature-branch-auto-labeling.yml`
  - Create YAML frontmatter parsing utilities
  - Implement configurable release/backport pattern matching

#### 2.2 Utility Development
- [ ] **GitHub API Client**
  - Centralized GitHub API interaction layer
  - Error handling for permission issues
  - Rate limiting and retry logic

- [ ] **Configuration Management**
  - Dynamic repository detection (remove hardcoded references)
  - Input validation and default value handling
  - Environment-specific configuration support

### Phase 3: Create Composite Action 📝 **Planned**

**Goal**: Implement the composite action with all extracted logic

#### 3.1 Composite Action Implementation
- [ ] **action.yml Configuration**
  - Define all inputs with proper validation
  - Configure composite steps for each automation type
  - Set up conditional execution based on `automation-type` input

- [ ] **Fork Compatibility Preservation**
  - Maintain the trigger/action workflow pattern for external contributors
  - Preserve artifact-based communication mechanism
  - Ensure custom token support for permission elevation

#### 3.2 Integration Steps
- [ ] **Modular Execution**
  - Create entry points for each automation type
  - Implement conditional logic based on inputs
  - Ensure proper error handling and logging

- [ ] **Repository Agnostic Design**
  - Remove all hardcoded repository references
  - Implement dynamic repository detection using `github.repository`
  - Support organization and personal repository contexts

### Phase 4: Testing and Validation 📝 **Planned**

**Goal**: Ensure the action works correctly across different repository contexts

#### 4.1 Test Suite Development
- [ ] **Action Testing**
  - Unit tests for individual JavaScript modules
  - Integration tests for complete automation workflows
  - Mock GitHub API responses for consistent testing

- [ ] **Multi-Repository Testing**
  - Test action against different repository types (org, personal, fork)
  - Validate fork compatibility scenarios
  - Test permission boundary conditions

#### 4.2 Validation Scenarios
- [ ] **Input Validation**
  - Test all input combinations and edge cases
  - Validate error handling for invalid configurations
  - Ensure graceful degradation for missing permissions

- [ ] **Output Verification**
  - Verify action outputs match expected formats
  - Test output reliability across different scenarios
  - Validate action summaries and logging

### Phase 5: Documentation and Publishing 📝 **Planned**

**Goal**: Create comprehensive documentation and publish the action

#### 5.1 Documentation
- [ ] **README.md**
  - Comprehensive usage guide with examples
  - Input/output reference documentation
  - Troubleshooting and FAQ section

- [ ] **Usage Examples**
  - Basic repository setup examples
  - Advanced configuration scenarios
  - Fork-compatible setup instructions

#### 5.2 Publishing
- [ ] **GitHub Marketplace**
  - Prepare action for marketplace publication
  - Create proper branding and metadata
  - Set up versioning and release process

- [ ] **Migration Guide**
  - Step-by-step migration from existing workflows
  - Backward compatibility considerations
  - Rollback procedures if needed

## Benefits of Migration

### For Repository Maintainers
- **Simplified Adoption**: Single action addition vs. multiple workflow files
- **Automatic Updates**: Action updates propagate automatically with version pinning
- **Consistent Behavior**: Same logic across all repositories using the action
- **Reduced Maintenance**: No need to manually sync workflow updates

### For the Automation Project
- **Centralized Maintenance**: Single codebase for all logic
- **Version Control**: Proper versioning and release management
- **Community Contributions**: Easier for community to contribute improvements
- **Broader Adoption**: Discoverable via GitHub Marketplace

### Technical Benefits
- **Repository Agnostic**: No hardcoded repository references
- **Configurable**: Extensive customization options via inputs
- **Fork Compatible**: Preserves existing fork compatibility mechanisms
- **Testable**: Proper test suite for reliability

## Usage Pattern (Post-Migration)

### Basic Usage
```yaml
# .github/workflows/repository-automation.yml
name: Repository Automation
on:
  issues:
    types: [opened, labeled, unlabeled]
  pull_request:
    types: [opened, synchronize, ready_for_review, labeled, unlabeled]

jobs:
  automation:
    runs-on: ubuntu-latest
    steps:
      - name: Repository Automation Keeper
        uses: thenets/repo-automation@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          custom-github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
          automation-type: 'all'
          accepted-releases: '["1.0", "2.0", "devel"]'
          accepted-backports: '["1.0", "2.0"]'
```

### Advanced Configuration
```yaml
      - name: Triage Management Only
        uses: thenets/repo-automation@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          automation-type: 'triage'
          dry-run: false

      - name: Stale Detection
        uses: thenets/repo-automation@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          automation-type: 'stale-detection'
          stale-days: 7
```

## Migration Path

### For Existing Users
1. **Replace Workflows**: Remove existing keeper-* workflow files
2. **Add Action**: Create single workflow file using the new action
3. **Configure**: Set up inputs to match previous workflow behavior
4. **Test**: Validate behavior in test repository before production deployment

### Backward Compatibility
- **Fork Support**: Maintains existing fork compatibility mechanisms
- **Permission Model**: Same token requirements and permission handling
- **Label Behavior**: Identical labeling logic and conditions
- **Configuration**: Equivalent configuration options via action inputs

## Success Criteria

### Phase 1 Success Metrics
- [ ] Complete action structure design documented
- [ ] Input/output specifications finalized
- [ ] Repository structure established

### Phase 2 Success Metrics
- [ ] All workflow logic successfully extracted to modular components
- [ ] JavaScript modules pass unit tests
- [ ] Utility functions handle edge cases properly

### Phase 3 Success Metrics
- [ ] Working composite action with all functionality
- [ ] Repository-agnostic operation confirmed
- [ ] Fork compatibility preserved

### Phase 4 Success Metrics
- [ ] Comprehensive test suite passing
- [ ] Multi-repository validation successful
- [ ] Performance equivalent to existing workflows

### Phase 5 Success Metrics
- [ ] Complete documentation published
- [ ] Action available on GitHub Marketplace
- [ ] Migration guide available for existing users

## Risk Mitigation

### Technical Risks
- **Logic Translation Errors**: Extensive testing and validation against existing workflows
- **Permission Changes**: Preserve existing permission model and token handling
- **Performance Impact**: Monitor action execution time vs. current workflows

### Adoption Risks
- **Migration Complexity**: Provide clear migration guide and examples
- **Breaking Changes**: Ensure backward compatibility in behavior
- **Support Burden**: Comprehensive documentation and troubleshooting guides

## Timeline

| Phase | Duration | Dependencies | Key Deliverables |
|-------|----------|--------------|------------------|
| Phase 1 | 1 week | - | Action design, repository structure |
| Phase 2 | 2 weeks | Phase 1 | Extracted logic modules, utilities |
| Phase 3 | 2 weeks | Phase 2 | Working composite action |
| Phase 4 | 1 week | Phase 3 | Test suite, validation |
| Phase 5 | 1 week | Phase 4 | Documentation, marketplace publication |

**Total Estimated Duration**: 7 weeks

## Next Steps

1. **Start Phase 1**: Design action structure and finalize input/output specifications
2. **Set Up Development Environment**: Create new repository for the action
3. **Begin Logic Extraction**: Start with triage management as the most complex component
4. **Establish Testing Framework**: Set up test infrastructure early for continuous validation