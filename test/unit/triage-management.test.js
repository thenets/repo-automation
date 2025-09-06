/**
 * Unit tests for RepositoryAutomation class
 * Tests orchestration logic, feature detection, and triage management
 */

const { RepositoryAutomation } = require('../../src/triage-management');

// Mock the dependencies
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('RepositoryAutomation', () => {
  let mockContext;
  let mockGitHub;
  let mockConfig;
  let mockClient;
  let automation;

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockContext = createMockContext();
    mockGitHub = createMockGitHub();
    
    // Mock ConfigManager
    mockConfig = {
      options: {},
      validate: jest.fn(),
      logConfig: jest.fn(),
      parseYamlFromText: jest.fn(),
      parseYamlValue: jest.fn(),
      isDryRun: jest.fn().mockReturnValue(false)
    };
    ConfigManager.mockImplementation(() => mockConfig);
    
    // Mock GitHubClient
    mockClient = {
      addLabels: jest.fn(),
      getLabels: jest.fn(),
      hasLabels: jest.fn(),
      findPRByBranch: jest.fn()
    };
    GitHubClient.mockImplementation(() => mockClient);
    
    automation = new RepositoryAutomation(mockContext, mockGitHub);
  });

  describe('Constructor', () => {
    test('should initialize with context and github', () => {
      expect(automation.context).toBe(mockContext);
      expect(automation.github).toBe(mockGitHub);
      expect(ConfigManager).toHaveBeenCalledWith(mockContext, {});
      expect(GitHubClient).toHaveBeenCalledWith(mockGitHub, mockConfig);
    });

    test('should initialize with options', () => {
      const options = { dryRun: true };
      new RepositoryAutomation(mockContext, mockGitHub, options);
      
      expect(ConfigManager).toHaveBeenCalledWith(mockContext, options);
    });

    test('should initialize result object', () => {
      expect(automation.result).toEqual({
        labelsAdded: [],
        summary: '',
        actions: [],
        featuresEnabled: []
      });
    });
  });

  describe('detectEnabledFeatures', () => {
    test('should detect enabled features based on options', () => {
      mockConfig.options = {
        acceptedReleases: ['1.0'],
        acceptedBackports: ['main'],
        enableFeatureBranch: true,
        staleDays: 7
      };
      
      const automationWithFeatures = new RepositoryAutomation(mockContext, mockGitHub);
      
      expect(automationWithFeatures.features).toEqual({
        triage: true,
        releaseLabeling: true,
        backportLabeling: true,
        featureBranch: true,
        staleDetection: true
      });
    });

    test('should detect minimal features when no options provided', () => {
      mockConfig.options = {};
      
      const minimalAutomation = new RepositoryAutomation(mockContext, mockGitHub);
      
      expect(minimalAutomation.features).toEqual({
        triage: true,
        releaseLabeling: false,
        backportLabeling: false,
        featureBranch: false,
        staleDetection: false
      });
    });

    test('should detect stale detection on schedule event', () => {
      const scheduleContext = createMockContext({ eventName: 'schedule' });
      mockConfig.options = {};
      
      const scheduleAutomation = new RepositoryAutomation(scheduleContext, mockGitHub);
      
      expect(scheduleAutomation.features.staleDetection).toBe(true);
    });
  });

  describe('execute', () => {
    beforeEach(() => {
      // Mock the execution methods
      automation.executeLabelAutomation = jest.fn();
      automation.executeTriageAutomation = jest.fn();
      automation.executeStaleDetection = jest.fn();
    });

    test('should execute all enabled features', async () => {
      automation.features = {
        triage: true,
        releaseLabeling: true,
        featureBranch: true,
        staleDetection: true
      };
      
      const result = await automation.execute();
      
      expect(mockConfig.validate).toHaveBeenCalled();
      expect(mockConfig.logConfig).toHaveBeenCalled();
      expect(automation.executeLabelAutomation).toHaveBeenCalled();
      expect(automation.executeTriageAutomation).toHaveBeenCalled();
      expect(automation.executeStaleDetection).toHaveBeenCalled();
      expect(result.featuresEnabled).toContain('releaseLabeling');
      expect(result.featuresEnabled).toContain('featureBranch');
      expect(result.featuresEnabled).toContain('staleDetection');
    });

    test('should skip optional features when disabled', async () => {
      automation.features = {
        triage: true,
        releaseLabeling: false,
        featureBranch: false,
        staleDetection: false
      };
      
      await automation.execute();
      
      expect(automation.executeLabelAutomation).not.toHaveBeenCalled();
      expect(automation.executeStaleDetection).not.toHaveBeenCalled();
      expect(automation.executeTriageAutomation).toHaveBeenCalled();
    });

    test('should handle execution errors', async () => {
      const error = new Error('Execution failed');
      mockConfig.validate.mockImplementation(() => { throw error; });
      
      await expect(automation.execute()).rejects.toThrow('Execution failed');
      expect(automation.result.summary).toBe('Failed: Execution failed');
    });
  });

  describe('handleIssueEvent', () => {
    beforeEach(() => {
      mockContext.payload = { action: 'opened' };
      mockContext.issue = { number: 123 };
    });

    test('should add triage label to new issue', async () => {
      mockClient.addLabels.mockResolvedValue({ added: ['triage'] });
      
      await automation.handleIssueEvent();
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['triage']);
      expect(automation.result.labelsAdded).toContain('triage');
      expect(automation.result.actions).toContain('Added triage label to issue #123');
      expect(automation.result.summary).toBe('Successfully processed issue #123');
    });

    test('should skip non-opened issue actions', async () => {
      mockContext.payload.action = 'closed';
      
      await automation.handleIssueEvent();
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });

    test('should handle errors when adding labels to issue', async () => {
      const error = new Error('Label add failed');
      mockClient.addLabels.mockRejectedValue(error);
      
      await expect(automation.handleIssueEvent()).rejects.toThrow('Label add failed');
      expect(automation.result.summary).toBe('Failed to process issue #123: Label add failed');
    });
  });

  describe('handlePullRequestEvent', () => {
    let mockPR;

    beforeEach(() => {
      mockPR = {
        number: 123,
        title: 'Test PR',
        body: '',
        draft: false
      };
      
      mockClient.getLabels.mockResolvedValue([]);
      mockClient.hasLabels.mockResolvedValue({
        'release-*': false,
        'backport-*': false,
        'triage': false,
        'ready for review': false
      });
      
      // Mock sleep to avoid delays in tests
      automation.config.isDryRun = jest.fn().mockReturnValue(true);
    });

    test('should skip draft PRs', async () => {
      mockPR.draft = true;
      
      await automation.handlePullRequestEvent(mockPR);
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });

    test('should add triage label when no release labels', async () => {
      automation.handleTriageLabel = jest.fn();
      
      await automation.handlePullRequestEvent(mockPR);
      
      expect(automation.handleTriageLabel).toHaveBeenCalledWith(123, false, false);
    });

    test('should add ready for review when has release label and not draft', async () => {
      mockClient.hasLabels.mockResolvedValue({
        'release-*': true,
        'backport-*': false,
        'triage': false,
        'ready for review': false
      });
      
      automation.handleReadyForReviewLabel = jest.fn();
      
      await automation.handlePullRequestEvent(mockPR);
      
      expect(automation.handleReadyForReviewLabel).toHaveBeenCalledWith(123, false);
    });

    test('should add triage label when validation errors exist', async () => {
      automation.result.actions = ['Posted validation error comment to PR #123'];
      automation.handleTriageLabel = jest.fn();
      
      await automation.handlePullRequestEvent(mockPR);
      
      expect(automation.handleTriageLabel).toHaveBeenCalledWith(123, false, false);
    });

    test('should parse YAML content for release detection', async () => {
      mockPR.body = '```yaml\nrelease: "1.0"\n```';
      mockConfig.parseYamlFromText.mockReturnValue('release: "1.0"');
      mockConfig.parseYamlValue.mockReturnValue('1.0');
      
      automation.handleReadyForReviewLabel = jest.fn();
      
      await automation.handlePullRequestEvent(mockPR);
      
      expect(mockConfig.parseYamlFromText).toHaveBeenCalledWith(mockPR.body);
      expect(mockConfig.parseYamlValue).toHaveBeenCalledWith('release: "1.0"', 'release');
      expect(automation.handleReadyForReviewLabel).toHaveBeenCalled();
    });

    test('should skip labeling when has backport label/YAML', async () => {
      mockClient.hasLabels.mockResolvedValue({
        'release-*': false,
        'backport-*': true,
        'triage': false,
        'ready for review': false
      });
      
      automation.handleTriageLabel = jest.fn();
      automation.handleReadyForReviewLabel = jest.fn();
      
      await automation.handlePullRequestEvent(mockPR);
      
      expect(automation.handleTriageLabel).not.toHaveBeenCalled();
      expect(automation.handleReadyForReviewLabel).not.toHaveBeenCalled();
    });
  });

  describe('handleTriageLabel', () => {
    test('should add triage label when not present', async () => {
      mockClient.addLabels.mockResolvedValue({ added: ['triage'] });
      
      await automation.handleTriageLabel(123, false, false);
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['triage']);
      expect(automation.result.labelsAdded).toContain('triage');
      expect(automation.result.actions).toContain(
        'Added triage label to PR #123 (no release/backport label)'
      );
    });

    test('should not add triage label when already present', async () => {
      await automation.handleTriageLabel(123, true, false);
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });

    test('should use correct reason in action message', async () => {
      mockClient.addLabels.mockResolvedValue({ added: ['triage'] });
      
      await automation.handleTriageLabel(123, false, true);
      
      expect(automation.result.actions).toContain(
        'Added triage label to PR #123 (is draft)'
      );
    });
  });

  describe('handleReadyForReviewLabel', () => {
    test('should add ready for review label when not present', async () => {
      mockClient.addLabels.mockResolvedValue({ added: ['ready for review'] });
      
      await automation.handleReadyForReviewLabel(123, false);
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['ready for review']);
      expect(automation.result.labelsAdded).toContain('ready for review');
      expect(automation.result.actions).toContain(
        'Added "ready for review" label to PR #123 (has release label, not draft)'
      );
    });

    test('should not add ready for review label when already present', async () => {
      await automation.handleReadyForReviewLabel(123, true);
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });
  });

  describe('handleTriageProtection', () => {
    test('should re-add triage label when removed without release/backport labels', async () => {
      mockClient.hasLabels.mockResolvedValue({
        'release-*': false,
        'backport-*': false
      });
      mockClient.addLabels.mockResolvedValue({ added: ['triage'] });
      
      await automation.handleTriageProtection(123);
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['triage']);
      expect(automation.result.labelsAdded).toContain('triage');
      expect(automation.result.actions).toContain(
        'Re-added triage label to PR #123 (no release/backport labels found)'
      );
    });

    test('should allow triage removal when release label present', async () => {
      mockClient.hasLabels.mockResolvedValue({
        'release-*': true,
        'backport-*': false
      });
      
      await automation.handleTriageProtection(123);
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });

    test('should allow triage removal when backport label present', async () => {
      mockClient.hasLabels.mockResolvedValue({
        'release-*': false,
        'backport-*': true
      });
      
      await automation.handleTriageProtection(123);
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });

    test('should handle different event types in messages', async () => {
      mockClient.hasLabels.mockResolvedValue({
        'release-*': false,
        'backport-*': false
      });
      mockClient.addLabels.mockResolvedValue({ added: ['triage'] });
      
      await automation.handleTriageProtection(456, 'issue');
      
      expect(automation.result.actions).toContain(
        'Re-added triage label to issue #456 (no release/backport labels found)'
      );
    });
  });

  describe('handleWorkflowRunEvent', () => {
    beforeEach(() => {
      mockContext.payload = {
        workflow_run: {
          conclusion: 'success',
          name: 'Test Workflow',
          head_branch: 'feature-branch'
        }
      };
      
      automation.loadMetadataFromArtifact = jest.fn();
      automation.handlePullRequestEvent = jest.fn();
      automation.handleIssueEventFromMetadata = jest.fn();
    });

    test('should skip non-successful workflow runs', async () => {
      mockContext.payload.workflow_run.conclusion = 'failure';
      
      await automation.handleWorkflowRunEvent();
      
      expect(automation.loadMetadataFromArtifact).not.toHaveBeenCalled();
    });

    test('should use metadata when available', async () => {
      const mockMetadata = {
        type: 'pull_request',
        number: 123
      };
      automation.loadMetadataFromArtifact.mockResolvedValue(mockMetadata);
      
      await automation.handleWorkflowRunEvent();
      
      expect(automation.handlePullRequestEvent).toHaveBeenCalledWith(mockMetadata);
    });

    test('should handle issue metadata', async () => {
      const mockMetadata = {
        type: 'issue',
        number: 123
      };
      automation.loadMetadataFromArtifact.mockResolvedValue(mockMetadata);
      
      await automation.handleWorkflowRunEvent();
      
      expect(automation.handleIssueEventFromMetadata).toHaveBeenCalledWith(mockMetadata);
    });

    test('should fallback to branch lookup when no metadata', async () => {
      automation.loadMetadataFromArtifact.mockResolvedValue(null);
      const mockPR = { number: 123, state: 'open' };
      mockClient.findPRByBranch.mockResolvedValue(mockPR);
      
      await automation.handleWorkflowRunEvent();
      
      expect(mockClient.findPRByBranch).toHaveBeenCalledWith('feature-branch');
      expect(automation.handlePullRequestEvent).toHaveBeenCalledWith(mockPR);
    });

    test('should skip main branch', async () => {
      automation.loadMetadataFromArtifact.mockResolvedValue(null);
      mockContext.payload.workflow_run.head_branch = 'main';
      
      await automation.handleWorkflowRunEvent();
      
      expect(mockClient.findPRByBranch).not.toHaveBeenCalled();
    });

    test('should skip closed PRs', async () => {
      automation.loadMetadataFromArtifact.mockResolvedValue(null);
      const mockPR = { number: 123, state: 'closed' };
      mockClient.findPRByBranch.mockResolvedValue(mockPR);
      
      await automation.handleWorkflowRunEvent();
      
      expect(automation.handlePullRequestEvent).not.toHaveBeenCalled();
    });
  });

  describe('loadMetadataFromArtifact', () => {
    test('should return null when no metadata file exists', async () => {
      // This method is complex to test as it involves file system operations
      // For unit tests, we mock it at the test level rather than testing the implementation
      const result = await automation.loadMetadataFromArtifact();
      
      // Default behavior returns null when no file exists
      expect(result).toBeNull();
    });
  });

  describe('handleIssueEventFromMetadata', () => {
    test('should convert metadata to issue format and add triage label', async () => {
      const mockMetadata = {
        number: 123,
        title: 'Test Issue',
        body: 'Issue body',
        state: 'open',
        labels: [],
        author: { login: 'testuser' }
      };
      
      // Mock the addTriageLabel method that doesn't exist yet
      automation.addTriageLabel = jest.fn().mockResolvedValue();
      
      await automation.handleIssueEventFromMetadata(mockMetadata);
      
      expect(automation.addTriageLabel).toHaveBeenCalledWith(123, 'issue');
    });
  });
});