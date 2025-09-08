/**
 * Unit tests for enhanced label validation functionality
 * Tests repository label existence validation and error handling
 */

const { GitHubClient } = require('../../src/utils/github-client');
const { LabelAutomation } = require('../../src/label-automation');
const { ConfigManager } = require('../../src/utils/config');

describe('Label Validation', () => {
  let mockGitHub;
  let mockContext;
  let mockConfig;

  beforeEach(() => {
    // Mock GitHub API
    mockGitHub = {
      rest: {
        issues: {
          listLabelsForRepo: jest.fn(),
          listLabelsOnIssue: jest.fn(),
          addLabels: jest.fn(),
          createComment: jest.fn(),
          listComments: jest.fn(),
          deleteComment: jest.fn()
        }
      }
    };

    // Mock context
    mockContext = {
      repo: { owner: 'test-owner', repo: 'test-repo' },
      issue: { number: 123 },
      eventName: 'pull_request',
      payload: {
        action: 'opened',
        pull_request: {
          number: 123,
          title: 'Test PR',
          body: '```yaml\nrelease: 2.1\nbackport: 1.5\n```',
          draft: false
        }
      }
    };

    // Mock config
    mockConfig = {
      isDryRun: () => false,
      owner: 'test-owner',
      repo: 'test-repo',
      repository: 'test-owner/test-repo',
      getRepository: () => ({ owner: 'test-owner', repo: 'test-repo' })
    };
  });

  describe('GitHubClient.getRepositoryLabels()', () => {
    test('should fetch all repository labels successfully', async () => {
      const client = new GitHubClient(mockGitHub, mockConfig);
      
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [
          { name: 'bug' },
          { name: 'enhancement' },
          { name: 'release-2.1' },
          { name: 'backport-1.5' }
        ]
      });

      const labels = await client.getRepositoryLabels();
      
      expect(labels).toEqual(['bug', 'enhancement', 'release-2.1', 'backport-1.5']);
      expect(mockGitHub.rest.issues.listLabelsForRepo).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        per_page: 100
      });
    });

    test('should handle API errors gracefully', async () => {
      const client = new GitHubClient(mockGitHub, mockConfig);
      
      mockGitHub.rest.issues.listLabelsForRepo.mockRejectedValue(new Error('API Error'));

      await expect(client.getRepositoryLabels()).rejects.toThrow('API Error');
    });
  });

  describe('GitHubClient.validateRepositoryLabels()', () => {
    let client;

    beforeEach(() => {
      client = new GitHubClient(mockGitHub, mockConfig);
      
      // Mock repository labels
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [
          { name: 'bug' },
          { name: 'enhancement' },
          { name: 'release-2.0' },
          { name: 'backport-1.4' }
        ]
      });
    });

    test('should return valid result when all labels exist', async () => {
      const result = await client.validateRepositoryLabels(['release-2.0', 'backport-1.4']);
      
      expect(result).toEqual({
        existing: ['release-2.0', 'backport-1.4'],
        missing: [],
        valid: true
      });
    });

    test('should identify missing labels', async () => {
      const result = await client.validateRepositoryLabels(['release-2.1', 'backport-1.5']);
      
      expect(result).toEqual({
        existing: [],
        missing: ['release-2.1', 'backport-1.5'],
        valid: false
      });
    });

    test('should handle mixed existing and missing labels', async () => {
      const result = await client.validateRepositoryLabels(['release-2.0', 'release-2.1', 'backport-1.4']);
      
      expect(result).toEqual({
        existing: ['release-2.0', 'backport-1.4'],
        missing: ['release-2.1'],
        valid: false
      });
    });

    test('should handle empty label array', async () => {
      const result = await client.validateRepositoryLabels([]);
      
      expect(result).toEqual({
        existing: [],
        missing: [],
        valid: true
      });
    });

    test('should handle null/undefined input', async () => {
      const result = await client.validateRepositoryLabels(null);
      
      expect(result).toEqual({
        existing: [],
        missing: [],
        valid: true
      });
    });
  });

  describe('LabelAutomation with Repository Validation', () => {
    let automation;
    let client;

    beforeEach(() => {
      // Create real config manager with test options
      const options = {
        acceptedReleases: ['1.0', '2.0', '2.1'],
        acceptedBackports: ['1.4', '1.5'],
        enableFeatureBranch: false
      };
      
      const config = new ConfigManager(mockContext, options);
      client = new GitHubClient(mockGitHub, config);
      automation = new LabelAutomation(mockContext, mockGitHub, options);
      
      // Replace the client in automation with our mocked one
      automation.client = client;
      automation.config = config;

      // Mock existing PR labels
      mockGitHub.rest.issues.listLabelsOnIssue.mockResolvedValue({
        data: []
      });

      // Mock comments list (for cleanup)
      mockGitHub.rest.issues.listComments.mockResolvedValue({
        data: []
      });
    });

    test('should succeed when repository labels exist', async () => {
      // Mock repository has the required labels
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [
          { name: 'bug' },
          { name: 'release-2.1' },
          { name: 'backport-1.5' }
        ]
      });

      // Mock successful label addition
      mockGitHub.rest.issues.addLabels.mockResolvedValue({});

      const features = { releaseLabeling: true, backportLabeling: true };
      const result = await automation.execute(features);

      expect(result.labelsAdded).toContain('release-2.1');
      expect(mockGitHub.rest.issues.addLabels).toHaveBeenCalled();
    });

    test('should fail with clear error when repository labels are missing', async () => {
      // Mock repository without the required labels
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [
          { name: 'bug' },
          { name: 'enhancement' }
        ]
      });

      // Mock comment posting
      mockGitHub.rest.issues.createComment.mockResolvedValue({});

      const features = { releaseLabeling: true, backportLabeling: true };
      
      await expect(automation.execute(features)).rejects.toThrow(
        'Label validation failed: ❌ Repository labels do not exist: "release-2.1", "backport-1.5"'
      );

      // Verify error comment was posted
      expect(mockGitHub.rest.issues.createComment).toHaveBeenCalledWith(
        expect.objectContaining({
          owner: 'test-owner',
          repo: 'test-repo',
          issue_number: 123,
          body: expect.stringContaining('🚨 YAML Validation Error')
        })
      );

      // Verify the comment includes repository admin instructions
      const commentCall = mockGitHub.rest.issues.createComment.mock.calls[0][0];
      expect(commentCall.body).toContain('For Repository Administrators');
      expect(commentCall.body).toContain('Missing repository labels detected');
      expect(commentCall.body).toContain('Go to repository **Settings** → **Labels**');
    });

    test('should handle partial label existence', async () => {
      // Mock repository with only release label, missing backport label
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [
          { name: 'bug' },
          { name: 'release-2.1' }
        ]
      });

      // Mock comment posting
      mockGitHub.rest.issues.createComment.mockResolvedValue({});

      const features = { releaseLabeling: true, backportLabeling: true };
      
      await expect(automation.execute(features)).rejects.toThrow(
        'Label validation failed: ❌ Repository labels do not exist: "backport-1.5"'
      );

      // Verify error comment mentions only the missing label
      const commentCall = mockGitHub.rest.issues.createComment.mock.calls[0][0];
      expect(commentCall.body).toContain('"backport-1.5"');
      expect(commentCall.body).not.toContain('"release-2.1"');
    });

    test('should handle YAML validation errors separately from repository label errors', async () => {
      // Update context with invalid YAML
      automation.context.payload.pull_request.body = '```yaml\nrelease: invalid-version\n```';

      // Mock repository has all labels
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [
          { name: 'release-2.1' },
          { name: 'backport-1.5' }
        ]
      });

      // Mock comment posting
      mockGitHub.rest.issues.createComment.mockResolvedValue({});

      const features = { releaseLabeling: true };
      
      await expect(automation.execute(features)).rejects.toThrow(
        'Label validation failed: ❌ Invalid release value: "invalid-version"'
      );

      // Verify error comment contains YAML validation guidance, not repository admin guidance
      const commentCall = mockGitHub.rest.issues.createComment.mock.calls[0][0];
      expect(commentCall.body).toContain('How to fix:');
      expect(commentCall.body).toContain('Valid YAML format:');
      expect(commentCall.body).not.toContain('For Repository Administrators');
    });

    test('should handle mixed YAML and repository validation errors', async () => {
      // Update context with valid YAML but missing repository labels
      automation.context.payload.pull_request.body = '```yaml\nrelease: 2.1\ninvalid_field: test\n```';

      // Mock repository without labels
      mockGitHub.rest.issues.listLabelsForRepo.mockResolvedValue({
        data: [{ name: 'bug' }]
      });

      // Mock comment posting
      mockGitHub.rest.issues.createComment.mockResolvedValue({});

      const features = { releaseLabeling: true };
      
      await expect(automation.execute(features)).rejects.toThrow('Label validation failed');

      // Verify error comment was posted
      expect(mockGitHub.rest.issues.createComment).toHaveBeenCalled();
    });
  });
});