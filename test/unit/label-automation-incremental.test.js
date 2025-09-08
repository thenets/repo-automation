/**
 * Unit tests for incremental label addition in LabelAutomation
 * Tests scenarios where users edit PR descriptions to add new versions
 * while preserving existing labels
 */

const { LabelAutomation } = require('../../src/label-automation');

// Mock the dependencies
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('LabelAutomation - Incremental Label Addition', () => {
  let mockContext;
  let mockGitHub;
  let mockConfig;
  let mockClient;
  let labelAutomation;

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockContext = createMockContext({
      eventName: 'pull_request',
      payload: {
        pull_request: {
          number: 123,
          title: 'Test PR',
          draft: false,
          body: '## Description\nTest PR with YAML\n```yaml\nbackport: ["2.5", "2.6"]\n```'
        }
      }
    });
    mockGitHub = createMockGitHub();
    
    // Mock ConfigManager
    mockConfig = {
      parseYamlFromText: jest.fn(),
      parseYamlValue: jest.fn(),
      validateReleaseValue: jest.fn(),
      validateBackportValue: jest.fn(),
      getInvalidValues: jest.fn(),
      getValidValues: jest.fn(),
      getAcceptedReleases: jest.fn().mockReturnValue(['1.0', '2.0', '2.5', '2.6', 'devel']),
      getAcceptedBackports: jest.fn().mockReturnValue(['1.0', '2.0', '2.5', '2.6', 'devel']),
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
      validateRepositoryLabels: jest.fn(),
      createRepositoryLabel: jest.fn()
    };
    GitHubClient.mockImplementation(() => mockClient);
    
    labelAutomation = new LabelAutomation(mockContext, mockGitHub);
  });

  describe('processBackportLabel - Incremental Addition', () => {
    test('should add new backport label when existing label is present', async () => {
      // Setup: PR has backport-2.5 label, YAML has ["2.5", "2.6"]
      mockClient.getLabels.mockResolvedValue(['backport-2.5', 'triage']);
      mockConfig.parseYamlFromText.mockReturnValue('backport: ["2.5", "2.6"]');
      mockConfig.parseYamlValue.mockReturnValue(['2.5', '2.6']);
      mockConfig.validateBackportValue.mockReturnValue({ '2.5': true, '2.6': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['2.5', '2.6']);
      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels.mockResolvedValue({ added: ['backport-2.6'], skipped: ['backport-2.5'] });

      const features = { backportLabeling: true };
      await labelAutomation.execute(features);

      // Should add only the new label (backport-2.6)
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['backport-2.5', 'backport-2.6']);
      expect(labelAutomation.result.labelsAdded).toContain('backport-2.6');
    });

    test('should add multiple new backport labels when one exists', async () => {
      // Setup: PR has backport-2.5, YAML has ["2.5", "2.6", "devel"]
      mockClient.getLabels.mockResolvedValue(['backport-2.5', 'ready for review']);
      mockConfig.parseYamlFromText.mockReturnValue('backport: ["2.5", "2.6", "devel"]');
      mockConfig.parseYamlValue.mockReturnValue(['2.5', '2.6', 'devel']);
      mockConfig.validateBackportValue.mockReturnValue({ '2.5': true, '2.6': true, 'devel': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['2.5', '2.6', 'devel']);
      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels.mockResolvedValue({ added: ['backport-2.6', 'backport-devel'], skipped: ['backport-2.5'] });

      const features = { backportLabeling: true };
      await labelAutomation.execute(features);

      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['backport-2.5', 'backport-2.6', 'backport-devel']);
      expect(labelAutomation.result.labelsAdded).toEqual(expect.arrayContaining(['backport-2.6', 'backport-devel']));
    });

    test('should not remove existing labels not in YAML', async () => {
      // Setup: PR has backport-2.5 and backport-1.0, YAML only has ["2.6"]
      mockClient.getLabels.mockResolvedValue(['backport-2.5', 'backport-1.0', 'triage']);
      mockConfig.parseYamlFromText.mockReturnValue('backport: ["2.6"]');
      mockConfig.parseYamlValue.mockReturnValue(['2.6']);
      mockConfig.validateBackportValue.mockReturnValue({ '2.6': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['2.6']);
      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels.mockResolvedValue({ added: ['backport-2.6'], skipped: ['backport-2.5', 'backport-1.0'] });

      const features = { backportLabeling: true };
      await labelAutomation.execute(features);

      // Should preserve existing labels and add new one
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['backport-2.5', 'backport-1.0', 'backport-2.6']);
      expect(labelAutomation.result.labelsAdded).toContain('backport-2.6');
      // Should not remove existing backport-2.5 or backport-1.0
    });

    test('should handle mixed valid and invalid values with existing labels', async () => {
      // Setup: PR has backport-2.5, YAML has ["2.5", "2.6", "invalid"]
      mockClient.getLabels.mockResolvedValue(['backport-2.5']);
      mockConfig.parseYamlFromText.mockReturnValue('backport: ["2.5", "2.6", "invalid"]');
      mockConfig.parseYamlValue.mockReturnValue(['2.5', '2.6', 'invalid']);
      mockConfig.validateBackportValue.mockReturnValue({ '2.5': true, '2.6': true, 'invalid': false });
      mockConfig.getInvalidValues.mockReturnValue(['invalid']);
      mockConfig.getValidValues.mockReturnValue(['2.5', '2.6']);

      const features = { backportLabeling: true };

      // Should throw error due to invalid values
      await expect(labelAutomation.execute(features)).rejects.toThrow('Label validation failed');
      
      // Should not add any labels due to validation error
      expect(mockClient.addLabels).not.toHaveBeenCalled();
    });
  });

  describe('processReleaseLabel - Incremental Addition', () => {
    test('should add new release label when existing label is present', async () => {
      // Setup: PR has release-2.5 label, YAML has ["2.5", "2.6"]
      mockClient.getLabels.mockResolvedValue(['release-2.5', 'ready for review']);
      mockConfig.parseYamlFromText.mockReturnValue('release: ["2.5", "2.6"]');
      mockConfig.parseYamlValue
        .mockReturnValueOnce(['2.5', '2.6'])  // for release
        .mockReturnValueOnce(null);            // for backport
      mockConfig.validateReleaseValue.mockReturnValue({ '2.5': true, '2.6': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['2.5', '2.6']);
      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels.mockResolvedValue({ added: ['release-2.6'], skipped: ['release-2.5'] });

      const features = { releaseLabeling: true };
      await labelAutomation.execute(features);

      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['release-2.5', 'release-2.6']);
      expect(labelAutomation.result.labelsAdded).toContain('release-2.6');
    });

    test('should add multiple new release labels', async () => {
      // Setup: PR has release-1.0, YAML has ["1.0", "2.5", "2.6"]
      mockClient.getLabels.mockResolvedValue(['release-1.0']);
      mockConfig.parseYamlFromText.mockReturnValue('release: ["1.0", "2.5", "2.6"]');
      mockConfig.parseYamlValue
        .mockReturnValueOnce(['1.0', '2.5', '2.6'])  // for release
        .mockReturnValueOnce(null);                   // for backport
      mockConfig.validateReleaseValue.mockReturnValue({ '1.0': true, '2.5': true, '2.6': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['1.0', '2.5', '2.6']);
      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels.mockResolvedValue({ added: ['release-2.5', 'release-2.6'], skipped: ['release-1.0'] });

      const features = { releaseLabeling: true };
      await labelAutomation.execute(features);

      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['release-1.0', 'release-2.5', 'release-2.6']);
      expect(labelAutomation.result.labelsAdded).toEqual(expect.arrayContaining(['release-2.5', 'release-2.6']));
    });
  });

  describe('Mixed Release and Backport - Incremental Addition', () => {
    test('should handle both release and backport incremental additions', async () => {
      // Setup: PR has release-2.5 and backport-2.5, YAML adds new versions
      mockClient.getLabels.mockResolvedValue(['release-2.5', 'backport-2.5', 'triage']);
      mockConfig.parseYamlFromText.mockReturnValue('release: ["2.5", "2.6"]\nbackport: ["2.5", "1.0"]');
      mockConfig.parseYamlValue
        .mockReturnValueOnce(['2.5', '2.6'])      // for release call
        .mockReturnValueOnce(['2.5', '1.0']);     // for backport call

      mockConfig.validateReleaseValue.mockReturnValue({ '2.5': true, '2.6': true });
      mockConfig.validateBackportValue.mockReturnValue({ '2.5': true, '1.0': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues
        .mockReturnValueOnce(['2.5', '2.6'])      // for release
        .mockReturnValueOnce(['2.5', '1.0']);     // for backport

      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels
        .mockResolvedValueOnce({ added: ['release-2.6'], skipped: ['release-2.5'] })   // First call for release+backport labels
        .mockResolvedValueOnce({ added: [], skipped: [] });                            // Second call if any

      const features = { releaseLabeling: true, backportLabeling: true };
      await labelAutomation.execute(features);

      // Should add both new release and backport labels
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['release-2.5', 'release-2.6', 'backport-2.5', 'backport-1.0']);
      expect(labelAutomation.result.labelsAdded).toContain('release-2.6');
    });
  });

  describe('Edge Cases', () => {
    test('should handle empty array in YAML with existing labels', async () => {
      // Setup: PR has backport-2.5, YAML has empty array []
      mockClient.getLabels.mockResolvedValue(['backport-2.5', 'triage']);
      mockConfig.parseYamlFromText.mockReturnValue('backport: []');
      mockConfig.parseYamlValue.mockReturnValue([]);
      mockConfig.validateBackportValue.mockReturnValue({});
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue([]);

      const features = { backportLabeling: true };
      await labelAutomation.execute(features);

      // Should not add or remove any labels
      expect(mockClient.addLabels).not.toHaveBeenCalled();
      expect(labelAutomation.result.labelsAdded).toEqual([]);
    });

    test('should handle single value to array transition', async () => {
      // Setup: PR has backport-2.5, YAML changes from "2.5" to ["2.5", "2.6"]
      mockClient.getLabels.mockResolvedValue(['backport-2.5']);
      mockConfig.parseYamlFromText.mockReturnValue('backport: ["2.5", "2.6"]');
      mockConfig.parseYamlValue.mockReturnValue(['2.5', '2.6']);
      mockConfig.validateBackportValue.mockReturnValue({ '2.5': true, '2.6': true });
      mockConfig.getInvalidValues.mockReturnValue([]);
      mockConfig.getValidValues.mockReturnValue(['2.5', '2.6']);
      mockClient.validateRepositoryLabels.mockResolvedValue({ valid: true, existing: [], missing: [] });
      mockClient.addLabels.mockResolvedValue({ added: ['backport-2.6'], skipped: ['backport-2.5'] });

      const features = { backportLabeling: true };
      await labelAutomation.execute(features);

      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['backport-2.5', 'backport-2.6']);
      expect(labelAutomation.result.labelsAdded).toContain('backport-2.6');
    });
  });
});