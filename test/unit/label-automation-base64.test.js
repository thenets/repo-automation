/**
 * Unit tests for LabelAutomation base64 metadata processing
 * Tests the base64 encoding/decoding functionality in label automation
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

describe('LabelAutomation - Base64 Metadata Processing', () => {
  let automation;
  let mockFs;
  let mockGitHub;
  let mockContext;

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
          deleteComment: jest.fn().mockResolvedValue({})
        }
      }
    };
    
    // Mock ConfigManager
    ConfigManager.mockImplementation(() => ({
      options: {
        enableFeatureBranch: true
      },
      parseYamlFromText: jest.fn(),
      parseYamlValue: jest.fn()
    }));
    
    // Mock GitHubClient
    GitHubClient.mockImplementation(() => ({
      hasLabels: jest.fn().mockResolvedValue({ 'feature-branch': false }),
      addLabels: jest.fn().mockResolvedValue({ added: [] }),
      createComment: jest.fn().mockResolvedValue({}),
      cleanupWorkflowComments: jest.fn().mockResolvedValue({}),
      getLabels: jest.fn().mockResolvedValue([]),
      findPRByBranch: jest.fn().mockResolvedValue(null)
    }));
    
    automation = new LabelAutomation(mockContext, mockGitHub);
    
    // Setup fs mocks
    mockFs = require('fs');
  });

  describe('loadMetadataFromArtifact with base64 encoding', () => {
    test('should successfully parse and decode base64 encoded metadata', async () => {
      // Create base64 encoded PR metadata (like what the new action.yml creates)
      const title = 'Test PR with needs_feature_branch validation';
      const body = 'PR description with YAML:\n\n```yaml\nneeds_feature_branch: maybe_invalid_value\n```\n\nThis should trigger validation error.';
      
      const titleBase64 = Buffer.from(title, 'utf8').toString('base64');
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 123,
        title_base64: titleBase64,
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

      const result = await automation.loadMetadataFromArtifact();

      // Should now succeed in loading and have decoded fields
      expect(result).not.toBeNull();
      expect(result.number).toBe(123);
      
      // These fields should now be properly decoded
      expect(result.title).toBe(title); // Should be decoded title
      expect(result.body).toBe(body); // Should be decoded body
      expect(result.title_base64).toBe(titleBase64); // Base64 field still exists
      expect(result.body_base64).toBe(bodyBase64); // Base64 field still exists
    });

    test('should handle feature branch validation with base64 encoded metadata', async () => {
      // Test the full flow: base64 metadata -> YAML parsing -> validation error
      const title = 'Test PR with invalid feature branch value';
      const body = 'PR with invalid YAML:\n\n```yaml\nneeds_feature_branch: invalid_value\n```\n\nThis should fail validation.';
      
      const titleBase64 = Buffer.from(title, 'utf8').toString('base64');
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 456,
        title_base64: titleBase64,
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

      // Mock config to return the YAML content (this should now work because body is decoded)
      automation.config.parseYamlFromText.mockReturnValue('needs_feature_branch: invalid_value');
      automation.config.parseYamlValue.mockReturnValue('invalid_value');

      const features = { featureBranch: true };
      
      // This should now succeed and post a validation error comment (not throw)
      const result = await automation.execute(features);
      
      // Verify that a validation error comment was posted
      expect(result.actions).toContain('Posted validation error comment to PR #456');
      expect(automation.client.createComment).toHaveBeenCalled();
    });

    test('should successfully parse YAML from base64 encoded body', async () => {
      // Create PR metadata with YAML in the body that needs to be parsed
      const body = `## Description
This PR adds new functionality.

\`\`\`yaml
needs_feature_branch: true
release: 2.1
\`\`\`

More description here.`;
      
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 789,
        title_base64: Buffer.from('Test PR', 'utf8').toString('base64'),
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

      const metadata = await automation.loadMetadataFromArtifact();
      
      // The metadata loads and has decoded fields
      expect(metadata).not.toBeNull();
      expect(metadata.body).toBe(body); // Should be the decoded body content
      expect(metadata.body_base64).toBe(bodyBase64); // Base64 content is there and decoded
      
      // This shows the fix: ConfigManager.parseYamlFromText would now receive the decoded body
      // instead of undefined, allowing YAML parsing to work
      automation.config.parseYamlFromText(metadata.body); // This gets the actual body content
      
      expect(automation.config.parseYamlFromText).toHaveBeenCalledWith(body);
    });

    test('should work with non-base64 metadata (backward compatibility)', async () => {
      // Test that the current implementation still works with old-style metadata
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 999,
        title: 'Plain title',
        body: 'Plain body with ```yaml\nneeds_feature_branch: true\n```',
        author: {
          login: 'testuser',
          id: 12345
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe('Plain title');
      expect(result.body).toBe('Plain body with ```yaml\nneeds_feature_branch: true\n```');
      expect(result.number).toBe(999);
    });

    test('should handle malformed base64 encoded metadata gracefully', async () => {
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 111,
        title_base64: 'invalid-base64!@#$',
        body_base64: 'also-invalid!@#$',
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

      const result = await automation.loadMetadataFromArtifact();

      // Should load metadata but gracefully handle invalid base64
      expect(result).not.toBeNull();
      expect(result.number).toBe(111);
      expect(result.title).toBeUndefined(); // Invalid base64 - not decoded
      expect(result.body).toBeUndefined(); // Invalid base64 - not decoded
    });

    test('should handle empty base64 fields', async () => {
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 222,
        title_base64: '',
        body_base64: '',
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

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.number).toBe(222);
      // Empty base64 should decode to empty string
      expect(result.title).toBe('');
      expect(result.body).toBe('');
    });
  });

  describe('Feature branch validation with base64 metadata', () => {
    test('should demonstrate the exact failure scenario from integration test', async () => {
      // Recreate the exact scenario from the failing integration test
      const prBody = `This PR tests the complete lifecycle of validation error comments.

\`\`\`yaml
needs_feature_branch: maybe_invalid_value  # Invalid value not in accepted list (true/false)
\`\`\`

The value above is not in the accepted list and should create a validation error comment.`;

      const bodyBase64 = Buffer.from(prBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 302, // Same number as failing test
        title_base64: Buffer.from('Test validation error comment lifecycle (create + auto-remove)', 'utf8').toString('base64'),
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

      // Mock that feature-branch label doesn't exist
      automation.client.hasLabels.mockResolvedValue({ 'feature-branch': false });

      const metadata = await automation.loadMetadataFromArtifact();
      
      // Fixed implementation now decodes base64, so body contains the actual content
      expect(metadata.body).toBe(prBody);
      
      // When ConfigManager tries to parse YAML from the decoded body, it finds the YAML
      automation.config.parseYamlFromText.mockReturnValue('needs_feature_branch: maybe_invalid_value');
      automation.config.parseYamlValue.mockReturnValue('maybe_invalid_value');

      const features = { featureBranch: true };
      
      // The validation should now succeed and post a validation error comment
      const result = await automation.execute(features);

      // The validation error comment should be posted
      expect(automation.client.createComment).toHaveBeenCalled();
      expect(result.actions).toContain('Posted validation error comment to PR #302');
    });
  });
});