/**
 * Unit tests for automatic label creation functionality in LabelAutomation
 * Tests the feature where missing repository labels are automatically created
 * when they correspond to valid release/backport values
 */

const { LabelAutomation } = require('../../src/label-automation');
const fs = require('fs');
const path = require('path');

// Mock dependencies
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');
jest.mock('fs');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('LabelAutomation - Automatic Label Creation', () => {
  let automation;
  let mockFs;
  let mockGitHub;
  let mockContext;
  let mockConfig;
  let mockClient;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock context for workflow_run event
    mockContext = {
      repo: { owner: 'test', repo: 'test' },
      eventName: 'workflow_run',
      payload: {
        workflow_run: {
          head_branch: 'feature-branch',
          conclusion: 'success'
        }
      }
    };
    
    mockGitHub = {
      rest: {
        issues: {
          listLabelsOnIssue: jest.fn().mockResolvedValue({ data: [] }),
          addLabels: jest.fn().mockResolvedValue({}),
          createComment: jest.fn().mockResolvedValue({}),
          listComments: jest.fn().mockResolvedValue({ data: [] }),
          deleteComment: jest.fn().mockResolvedValue({}),
          createLabel: jest.fn().mockResolvedValue({})
        }
      }
    };
    
    // Mock ConfigManager
    mockConfig = {
      options: {
        enableFeatureBranch: true,
        acceptedReleases: ['1.0', '1.1', '1.2', '2.0', '2.1', '2.2'],
        acceptedBackports: ['1.0', '1.1', '1.2', '1.5', '2.0']
      },
      parseYamlFromText: jest.fn(),
      parseYamlValue: jest.fn(),
      getAcceptedReleases: jest.fn().mockReturnValue(['1.0', '1.1', '1.2', '2.0', '2.1', '2.2']),
      getAcceptedBackports: jest.fn().mockReturnValue(['1.0', '1.1', '1.2', '1.5', '2.0']),
      validateReleaseValue: jest.fn(),
      validateBackportValue: jest.fn()
    };
    
    ConfigManager.mockImplementation(() => mockConfig);
    
    // Mock GitHubClient
    mockClient = {
      hasLabels: jest.fn().mockResolvedValue({ 'feature-branch': false }),
      addLabels: jest.fn().mockResolvedValue({ added: [] }),
      createComment: jest.fn().mockResolvedValue({}),
      cleanupWorkflowComments: jest.fn().mockResolvedValue({}),
      getLabels: jest.fn().mockResolvedValue([]),
      findPRByBranch: jest.fn().mockResolvedValue(null),
      validateRepositoryLabels: jest.fn(),
      createRepositoryLabel: jest.fn().mockResolvedValue({})
    };
    
    GitHubClient.mockImplementation(() => mockClient);
    
    automation = new LabelAutomation(mockContext, mockGitHub);
    
    // Setup fs mocks
    mockFs = require('fs');
  });

  describe('Automatic creation of missing release labels', () => {
    test('should create missing release label when valid release value is found', async () => {
      // Create PR metadata with valid release value
      const prBody = `## Description
This PR implements a new feature.

\`\`\`yaml
release: 2.1
\`\`\`

More description here.`;
      
      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 123,
        title_base64: Buffer.from('Test PR with missing release label', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      // Mock config to return valid release value
      mockConfig.parseYamlFromText.mockReturnValue('release: 2.1');
      mockConfig.parseYamlValue.mockReturnValue('2.1');
      mockConfig.validateReleaseValue.mockReturnValue(true);

      // Mock that release-2.1 label doesn't exist
      mockClient.validateRepositoryLabels.mockResolvedValue({
        existing: [],
        missing: ['release-2.1'],
        valid: false
      });

      // Mock that no existing labels conflict
      mockClient.getLabels.mockResolvedValue([]);

      const features = { releaseLabeling: true };
      
      // Execute the automation
      const result = await automation.execute(features);
      
      // Verify that createRepositoryLabel was called with correct parameters
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('release-2.1', '00FF00', 'Release 2.1');
      
      // Verify that the label was then added to the PR
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['release-2.1']);
      
      // Verify successful completion
      expect(result.actions).toContain('Added release/backport labels: release-2.1');
    });

    test('should create missing backport label when valid backport value is found', async () => {
      // Create PR metadata with valid backport value
      const prBody = `## Description
This is a backport PR.

\`\`\`yaml
backport: 1.5
\`\`\`

Backporting to version 1.5.`;
      
      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 456,
        title_base64: Buffer.from('Test backport with missing label', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      // Mock config to return valid backport value
      mockConfig.parseYamlFromText.mockReturnValue('backport: 1.5');
      mockConfig.parseYamlValue.mockReturnValue('1.5');
      mockConfig.validateBackportValue.mockReturnValue(true);

      // Mock that backport-1.5 label doesn't exist
      mockClient.validateRepositoryLabels.mockResolvedValue({
        existing: [],
        missing: ['backport-1.5'],
        valid: false
      });

      // Mock that no existing labels conflict
      mockClient.getLabels.mockResolvedValue([]);

      const features = { backportLabeling: true };
      
      // Execute the automation
      const result = await automation.execute(features);
      
      // Verify that createRepositoryLabel was called with correct parameters
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('backport-1.5', '0000FF', 'Backport to 1.5');
      
      // Verify that the label was then added to the PR
      expect(mockClient.addLabels).toHaveBeenCalledWith(456, ['backport-1.5']);
      
      // Verify successful completion
      expect(result.actions).toContain('Added release/backport labels: backport-1.5');
    });

    test('should create multiple missing labels for array values', async () => {
      // Create PR metadata with multiple release values
      const prBody = `## Description
This PR affects multiple releases.

\`\`\`yaml
release: [2.1, 2.2]
backport: [1.0, 1.5]
\`\`\`

Multiple release and backport targets.`;
      
      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 789,
        title_base64: Buffer.from('Test multiple missing labels', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      // Mock config to return array values
      mockConfig.parseYamlFromText.mockReturnValue('release: [2.1, 2.2]\nbackport: [1.0, 1.5]');
      mockConfig.parseYamlValue
        .mockReturnValueOnce(['2.1', '2.2'])  // First call for release
        .mockReturnValueOnce(['1.0', '1.5']); // Second call for backport
      
      // Mock validation for array values
      mockConfig.validateReleaseValue.mockReturnValue([true, true]);
      mockConfig.validateBackportValue.mockReturnValue([true, true]);
      mockConfig.getValidValues = jest.fn()
        .mockReturnValueOnce(['2.1', '2.2'])  // First call for release
        .mockReturnValueOnce(['1.0', '1.5']); // Second call for backport
      mockConfig.getInvalidValues = jest.fn().mockReturnValue([]);

      // Mock that all labels are missing
      mockClient.validateRepositoryLabels.mockResolvedValue({
        existing: [],
        missing: ['release-2.1', 'release-2.2', 'backport-1.0', 'backport-1.5'],
        valid: false
      });

      // Mock that no existing labels conflict
      mockClient.getLabels.mockResolvedValue([]);

      const features = { releaseLabeling: true, backportLabeling: true };
      
      // Execute the automation
      const result = await automation.execute(features);
      
      // Verify that all missing labels were created
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('release-2.1', '00FF00', 'Release 2.1');
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('release-2.2', '00FF00', 'Release 2.2');
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('backport-1.0', '0000FF', 'Backport to 1.0');
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('backport-1.5', '0000FF', 'Backport to 1.5');
      
      // Verify that all labels were added to the PR
      expect(mockClient.addLabels).toHaveBeenCalledWith(789, ['release-2.1', 'release-2.2', 'backport-1.0', 'backport-1.5']);
    });

    test('should not create labels for invalid release/backport values', async () => {
      // Create PR metadata with invalid values
      const prBody = `## Description
This PR has invalid values.

\`\`\`yaml
release: invalid_release
backport: invalid_backport
\`\`\`

These values are not in the accepted lists.`;
      
      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 999,
        title_base64: Buffer.from('Test invalid values', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      // Mock config to return invalid values
      mockConfig.parseYamlFromText.mockReturnValue('release: invalid_release\nbackport: invalid_backport');
      mockConfig.parseYamlValue
        .mockReturnValueOnce('invalid_release')
        .mockReturnValueOnce('invalid_backport');
      
      // Mock validation to return false for invalid values
      mockConfig.validateReleaseValue.mockReturnValue(false);
      mockConfig.validateBackportValue.mockReturnValue(false);

      // Mock that no existing labels conflict
      mockClient.getLabels.mockResolvedValue([]);

      const features = { releaseLabeling: true, backportLabeling: true };
      
      // Execute the automation - should throw error for invalid values
      await expect(automation.execute(features)).rejects.toThrow('Label validation failed');
      
      // Verify that no labels were created
      expect(mockClient.createRepositoryLabel).not.toHaveBeenCalled();
      
      // Verify that validation error comment was posted
      expect(mockClient.createComment).toHaveBeenCalled();
    });

    test('should skip creation if labels already exist', async () => {
      // Create PR metadata with release value
      const prBody = `## Description
This PR targets an existing release.

\`\`\`yaml
release: 2.0
\`\`\`

The release-2.0 label already exists.`;
      
      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 111,
        title_base64: Buffer.from('Test existing label', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      // Mock config to return valid release value
      mockConfig.parseYamlFromText.mockReturnValue('release: 2.0');
      mockConfig.parseYamlValue.mockReturnValue('2.0');
      mockConfig.validateReleaseValue.mockReturnValue(true);

      // Mock that release-2.0 label already exists
      mockClient.validateRepositoryLabels.mockResolvedValue({
        existing: ['release-2.0'],
        missing: [],
        valid: true
      });

      // Mock that no existing labels conflict
      mockClient.getLabels.mockResolvedValue([]);

      const features = { releaseLabeling: true };
      
      // Execute the automation
      const result = await automation.execute(features);
      
      // Verify that no label creation was attempted
      expect(mockClient.createRepositoryLabel).not.toHaveBeenCalled();
      
      // Verify that the existing label was added to the PR
      expect(mockClient.addLabels).toHaveBeenCalledWith(111, ['release-2.0']);
      
      // Verify successful completion
      expect(result.actions).toContain('Added release/backport labels: release-2.0');
    });
  });

  describe('Error handling for label creation', () => {
    test('should handle label creation API errors gracefully', async () => {
      // Create PR metadata with valid release value
      const prBody = `## Description
This PR should trigger a label creation error.

\`\`\`yaml
release: 2.1
\`\`\``;
      
      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 222,
        title_base64: Buffer.from('Test label creation error', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      // Mock config to return valid release value
      mockConfig.parseYamlFromText.mockReturnValue('release: 2.1');
      mockConfig.parseYamlValue.mockReturnValue('2.1');
      mockConfig.validateReleaseValue.mockReturnValue(true);

      // Mock that release-2.1 label doesn't exist
      mockClient.validateRepositoryLabels.mockResolvedValue({
        existing: [],
        missing: ['release-2.1'],
        valid: false
      });

      // Mock label creation to fail
      mockClient.createRepositoryLabel.mockRejectedValue(new Error('Permission denied'));

      // Mock that no existing labels conflict
      mockClient.getLabels.mockResolvedValue([]);

      const features = { releaseLabeling: true };
      
      // Execute the automation - should handle the error and continue
      await expect(automation.execute(features)).rejects.toThrow();
      
      // Verify that label creation was attempted
      expect(mockClient.createRepositoryLabel).toHaveBeenCalledWith('release-2.1', '00FF00', 'Release 2.1');
    });
  });
});