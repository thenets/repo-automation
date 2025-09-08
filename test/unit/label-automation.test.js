/**
 * Unit tests for LabelAutomation class
 * Tests release/backport labeling, feature branch automation, and YAML validation
 */

const { LabelAutomation } = require('../../src/label-automation');

// Mock the dependencies
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('LabelAutomation', () => {
  let mockContext;
  let mockGitHub;
  let mockConfig;
  let mockClient;
  let labelAutomation;

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockContext = createMockContext();
    mockGitHub = createMockGitHub();
    
    // Mock ConfigManager
    mockConfig = {
      parseYamlFromText: jest.fn(),
      parseYamlValue: jest.fn(),
      validateReleaseValue: jest.fn(),
      validateBackportValue: jest.fn(),
      getInvalidValues: jest.fn(),
      getValidValues: jest.fn(),
      getAcceptedReleases: jest.fn(),
      getAcceptedBackports: jest.fn(),
      isDryRun: jest.fn().mockReturnValue(false)
    };
    ConfigManager.mockImplementation(() => mockConfig);
    
    // Mock GitHubClient
    mockClient = {
      findPRByBranch: jest.fn(),
      getLabels: jest.fn(),
      addLabels: jest.fn(),
      createComment: jest.fn(),
      cleanupWorkflowComments: jest.fn(),
      createCheckRun: jest.fn(),
      updateCheckRun: jest.fn(),
      validateRepositoryLabels: jest.fn().mockResolvedValue({ existing: [], missing: [], valid: true })
    };
    GitHubClient.mockImplementation(() => mockClient);
    
    labelAutomation = new LabelAutomation(mockContext, mockGitHub);
  });

  describe('Constructor', () => {
    test('should initialize with context and github', () => {
      expect(labelAutomation.context).toBe(mockContext);
      expect(labelAutomation.github).toBe(mockGitHub);
      expect(ConfigManager).toHaveBeenCalledWith(mockContext, {});
      expect(GitHubClient).toHaveBeenCalledWith(mockGitHub, mockConfig);
    });

    test('should initialize with options', () => {
      const options = { dryRun: true };
      new LabelAutomation(mockContext, mockGitHub, options);
      
      expect(ConfigManager).toHaveBeenCalledWith(mockContext, options);
    });

    test('should initialize result object', () => {
      expect(labelAutomation.result).toEqual({
        labelsAdded: [],
        actions: [],
        checkRuns: []
      });
    });
  });

  describe('extractPRData', () => {
    test('should extract PR data from pull_request event', async () => {
      const mockPR = { number: 123, title: 'Test PR' };
      mockContext.eventName = 'pull_request';
      mockContext.payload = { pull_request: mockPR };
      
      const prData = await labelAutomation.extractPRData();
      
      expect(prData).toBe(mockPR);
    });

    test('should extract PR data from workflow_run event with artifact', async () => {
      mockContext.eventName = 'workflow_run';
      
      // Mock the loadMetadataFromArtifact method directly
      const mockMetadata = {
        type: 'pull_request',
        number: 123,
        title: 'Test PR'
      };
      
      labelAutomation.loadMetadataFromArtifact = jest.fn().mockResolvedValue(mockMetadata);
      
      const prData = await labelAutomation.extractPRData();
      
      expect(prData).toBe(mockMetadata);
    });

    test('should extract PR data from workflow_run event by branch fallback', async () => {
      mockContext.eventName = 'workflow_run';
      mockContext.payload = {
        workflow_run: {
          head_branch: 'feature-branch'
        }
      };
      
      const mockPR = { number: 123, state: 'open' };
      mockClient.findPRByBranch.mockResolvedValue(mockPR);
      
      const prData = await labelAutomation.extractPRData();
      
      expect(mockClient.findPRByBranch).toHaveBeenCalledWith('feature-branch');
      expect(prData).toBe(mockPR);
    });

    test('should return null for main branch', async () => {
      mockContext.eventName = 'workflow_run';
      mockContext.payload = {
        workflow_run: {
          head_branch: 'main'
        }
      };
      
      const prData = await labelAutomation.extractPRData();
      
      expect(prData).toBeNull();
    });

    test('should return null for closed PR', async () => {
      mockContext.eventName = 'workflow_run';
      mockContext.payload = {
        workflow_run: {
          head_branch: 'feature-branch'
        }
      };
      
      const mockPR = { number: 123, state: 'closed' };
      mockClient.findPRByBranch.mockResolvedValue(mockPR);
      
      const prData = await labelAutomation.extractPRData();
      
      expect(prData).toBeNull();
    });
  });

  describe('execute', () => {
    test('should skip draft PRs', async () => {
      const mockPR = { number: 123, draft: true };
      mockContext.payload = { pull_request: mockPR };
      
      const result = await labelAutomation.execute({});
      
      expect(result.labelsAdded).toEqual([]);
      expect(result.actions).toEqual([]);
    });

    test('should process non-draft PRs with YAML', async () => {
      const mockPR = { 
        number: 123, 
        title: 'Test PR',
        body: '```yaml\nrelease: "1.0"\n```',
        draft: false 
      };
      mockContext.payload = { pull_request: mockPR };
      mockConfig.parseYamlFromText.mockReturnValue('release: "1.0"');
      mockClient.getLabels.mockResolvedValue([]); // Mock the getLabels call
      
      const features = { releaseLabeling: true };
      const result = await labelAutomation.execute(features);
      
      expect(mockConfig.parseYamlFromText).toHaveBeenCalledWith(mockPR.body);
      expect(result).toBeDefined();
    });

    test('should clean up comments when no YAML found', async () => {
      const mockPR = { 
        number: 123, 
        title: 'Test PR',
        body: 'No YAML here',
        draft: false 
      };
      mockContext.payload = { pull_request: mockPR };
      mockConfig.parseYamlFromText.mockReturnValue(null);
      
      const features = { featureBranch: true, releaseLabeling: true };
      await labelAutomation.execute(features);
      
      expect(mockClient.cleanupWorkflowComments).toHaveBeenCalledWith(
        123, '🚨 YAML Validation Error: feature branch'
      );
      expect(mockClient.cleanupWorkflowComments).toHaveBeenCalledWith(
        123, '🚨 YAML Validation Error: release and backport'
      );
    });
  });

  describe('processReleaseLabel', () => {
    beforeEach(() => {
      mockConfig.getAcceptedReleases.mockReturnValue(['1.0', '1.1']);
    });

    test('should return empty result when no release value', async () => {
      mockConfig.parseYamlValue.mockReturnValue(null);
      
      const result = await labelAutomation.processReleaseLabel('yaml-content', false);
      
      expect(result).toEqual({ labels: [], error: null });
    });

    test('should skip when release label already exists', async () => {
      mockConfig.parseYamlValue.mockReturnValue('1.0');
      
      const result = await labelAutomation.processReleaseLabel('yaml-content', true);
      
      expect(result).toEqual({ labels: [], error: null });
    });

    test('should process valid single release value', async () => {
      mockConfig.parseYamlValue.mockReturnValue('1.0');
      mockConfig.validateReleaseValue.mockReturnValue(true);
      
      const result = await labelAutomation.processReleaseLabel('yaml-content', false);
      
      expect(result).toEqual({ 
        labels: ['release-1.0'], 
        error: null 
      });
    });

    test('should handle invalid single release value', async () => {
      mockConfig.parseYamlValue.mockReturnValue('2.0');
      mockConfig.validateReleaseValue.mockReturnValue(false);
      
      const result = await labelAutomation.processReleaseLabel('yaml-content', false);
      
      expect(result.error).toContain('Invalid release value: "2.0"');
      expect(result.labels).toEqual([]);
    });

    test('should process valid array release values', async () => {
      mockConfig.parseYamlValue.mockReturnValue(['1.0', '1.1']);
      mockConfig.validateReleaseValue.mockReturnValue([
        { value: '1.0', valid: true },
        { value: '1.1', valid: true }
      ]);
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['1.0', '1.1']);
      
      const result = await labelAutomation.processReleaseLabel('yaml-content', false);
      
      expect(result).toEqual({ 
        labels: ['release-1.0', 'release-1.1'], 
        error: null 
      });
    });

    test('should handle mixed valid/invalid array release values', async () => {
      mockConfig.parseYamlValue.mockReturnValue(['1.0', '2.0']);
      mockConfig.validateReleaseValue.mockReturnValue([
        { value: '1.0', valid: true },
        { value: '2.0', valid: false }
      ]);
      mockConfig.getInvalidValues.mockReturnValue(['2.0']);
      
      const result = await labelAutomation.processReleaseLabel('yaml-content', false);
      
      expect(result.error).toContain('Invalid release values: "2.0"');
      expect(result.labels).toEqual([]);
    });
  });

  describe('processBackportLabel', () => {
    beforeEach(() => {
      mockConfig.getAcceptedBackports.mockReturnValue(['main', '1.0']);
    });

    test('should return empty result when no backport value', async () => {
      mockConfig.parseYamlValue.mockReturnValue(null);
      
      const result = await labelAutomation.processBackportLabel('yaml-content', false);
      
      expect(result).toEqual({ labels: [], error: null });
    });

    test('should process valid single backport value', async () => {
      mockConfig.parseYamlValue.mockReturnValue('main');
      mockConfig.validateBackportValue.mockReturnValue(true);
      
      const result = await labelAutomation.processBackportLabel('yaml-content', false);
      
      expect(result).toEqual({ 
        labels: ['backport-main'], 
        error: null 
      });
    });

    test('should handle invalid single backport value', async () => {
      mockConfig.parseYamlValue.mockReturnValue('feature');
      mockConfig.validateBackportValue.mockReturnValue(false);
      
      const result = await labelAutomation.processBackportLabel('yaml-content', false);
      
      expect(result.error).toContain('Invalid backport value: "feature"');
      expect(result.labels).toEqual([]);
    });
  });

  describe('processFeatureBranchLabeling', () => {
    test('should skip when feature-branch label already exists', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue(['feature-branch', 'triage']);
      
      await labelAutomation.processFeatureBranchLabeling(mockPR, 'yaml-content');
      
      expect(mockClient.cleanupWorkflowComments).toHaveBeenCalled();
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });

    test('should add feature-branch label when needs_feature_branch is true', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue(['triage']);
      mockConfig.parseYamlValue.mockReturnValue('true');
      mockClient.addLabels.mockResolvedValue({ added: ['feature-branch'] });
      
      await labelAutomation.processFeatureBranchLabeling(mockPR, 'yaml-content');
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['feature-branch']);
      expect(labelAutomation.result.labelsAdded).toContain('feature-branch');
    });

    test('should not add label when needs_feature_branch is false', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue(['triage']);
      mockConfig.parseYamlValue.mockReturnValue('false');
      
      await labelAutomation.processFeatureBranchLabeling(mockPR, 'yaml-content');
      
      expect(mockClient.addLabels).not.toHaveBeenCalled();
      expect(mockClient.cleanupWorkflowComments).toHaveBeenCalled();
    });

    test('should handle invalid needs_feature_branch value', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue(['triage']);
      mockConfig.parseYamlValue.mockReturnValue('invalid');
      
      // Mock the handleFeatureBranchValidationError method
      labelAutomation.handleFeatureBranchValidationError = jest.fn();
      
      await labelAutomation.processFeatureBranchLabeling(mockPR, 'yaml-content');
      
      expect(labelAutomation.handleFeatureBranchValidationError).toHaveBeenCalledWith(
        123, 
        null, 
        expect.stringContaining('Invalid needs_feature_branch value')
      );
    });

    test('should clean up comments when no needs_feature_branch field', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue(['triage']);
      mockConfig.parseYamlValue.mockReturnValue(null);
      
      await labelAutomation.processFeatureBranchLabeling(mockPR, 'yaml-content');
      
      expect(mockClient.cleanupWorkflowComments).toHaveBeenCalled();
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });
  });

  describe('processReleaseBackportLabeling', () => {
    test('should skip labeling when labels already exist', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue(['release-1.0', 'backport-main']);
      
      const features = { releaseLabeling: true, backportLabeling: true };
      
      // Mock the process methods to return empty results
      labelAutomation.processReleaseLabel = jest.fn().mockResolvedValue({ labels: [], error: null });
      labelAutomation.processBackportLabel = jest.fn().mockResolvedValue({ labels: [], error: null });
      
      await labelAutomation.processReleaseBackportLabeling(mockPR, 'yaml-content', features);
      
      expect(labelAutomation.processReleaseLabel).toHaveBeenCalledWith('yaml-content', true);
      expect(labelAutomation.processBackportLabel).toHaveBeenCalledWith('yaml-content', true);
    });

    test('should add labels when validation passes', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue([]);
      mockClient.addLabels.mockResolvedValue({ added: ['release-1.0'] });
      
      const features = { releaseLabeling: true };
      
      // Mock the process methods
      labelAutomation.processReleaseLabel = jest.fn().mockResolvedValue({ 
        labels: ['release-1.0'], 
        error: null 
      });
      
      await labelAutomation.processReleaseBackportLabeling(mockPR, 'yaml-content', features);
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['release-1.0']);
      expect(labelAutomation.result.labelsAdded).toContain('release-1.0');
    });

    test('should handle validation errors', async () => {
      const mockPR = { number: 123 };
      mockClient.getLabels.mockResolvedValue([]);
      
      const features = { releaseLabeling: true };
      
      // Mock the process methods to return errors
      labelAutomation.processReleaseLabel = jest.fn().mockResolvedValue({ 
        labels: [], 
        error: 'Invalid release value' 
      });
      
      // Mock the error handler
      labelAutomation.handleValidationErrors = jest.fn();
      
      // Expect the function to throw an error
      await expect(labelAutomation.processReleaseBackportLabeling(mockPR, 'yaml-content', features))
        .rejects.toThrow('Label validation failed: Invalid release value');
      
      expect(labelAutomation.handleValidationErrors).toHaveBeenCalledWith(
        123, 
        null, 
        ['Invalid release value']
      );
    });
  });

  describe('handleValidationErrors', () => {
    beforeEach(() => {
      mockConfig.getAcceptedReleases.mockReturnValue(['1.0', '1.1']);
      mockConfig.getAcceptedBackports.mockReturnValue(['main', '1.0']);
    });

    test('should create error comment', async () => {
      const errors = ['Invalid release value: "2.0"'];
      
      await labelAutomation.handleValidationErrors(123, null, errors);
      
      expect(mockClient.createComment).toHaveBeenCalledWith(
        123, 
        expect.stringContaining('🚨 YAML Validation Error: release and backport')
      );
      expect(labelAutomation.result.actions).toContain(
        'Posted validation error comment to PR #123'
      );
    });

    test('should update check run when provided', async () => {
      const errors = ['Invalid release value: "2.0"'];
      
      await labelAutomation.handleValidationErrors(123, 'check-123', errors);
      
      expect(mockClient.updateCheckRun).toHaveBeenCalledWith(
        'check-123',
        'completed',
        'failure',
        expect.objectContaining({
          title: 'YAML Validation Failed',
          summary: expect.stringContaining('1 validation error')
        })
      );
    });
  });

  describe('handleFeatureBranchValidationError', () => {
    test('should create feature branch error comment', async () => {
      const errorMsg = 'Invalid needs_feature_branch value';
      
      await labelAutomation.handleFeatureBranchValidationError(123, null, errorMsg);
      
      expect(mockClient.createComment).toHaveBeenCalledWith(
        123, 
        expect.stringContaining('🚨 YAML Validation Error: feature branch')
      );
      expect(labelAutomation.result.actions).toContain(
        'Posted validation error comment to PR #123'
      );
    });
  });
});