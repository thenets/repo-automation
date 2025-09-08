/**
 * Unit tests for base64 metadata encoding/decoding functionality
 * Tests the new base64 approach to prevent JSON parsing issues
 */

const { RepositoryAutomation } = require('../../src/triage-management');
const fs = require('fs');
const path = require('path');

// Mock dependencies to isolate metadata testing
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');
jest.mock('fs');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('RepositoryAutomation - Base64 Metadata Processing', () => {
  let automation;
  let mockFs;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock context and github objects
    const mockContext = {
      repo: { owner: 'test', repo: 'test' },
      eventName: 'workflow_run',
      payload: {}
    };
    const mockGitHub = {};
    
    // Mock ConfigManager
    ConfigManager.mockImplementation(() => ({
      options: {},
      validate: jest.fn(),
      logConfig: jest.fn(),
      isDryRun: jest.fn().mockReturnValue(false)
    }));
    
    // Mock GitHubClient
    GitHubClient.mockImplementation(() => ({}));
    
    automation = new RepositoryAutomation(mockContext, mockGitHub);
    
    // Setup fs mocks
    mockFs = require('fs');
  });

  describe('loadMetadataFromArtifact with base64 encoding', () => {
    test('should successfully decode base64 encoded title and body', async () => {
      const title = 'Test PR with "quotes" and newlines\nMultiple lines';
      const body = 'PR body with ```yaml\nrelease: 2.1\nbackport: "1.5"\n```\nAnd more content';
      
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

      expect(result).not.toBeNull();
      expect(result.title).toBe(title);
      expect(result.body).toBe(body);
      expect(result.number).toBe(123);
      expect(result.author.login).toBe('testuser');
    });

    test('should handle metadata without base64 encoding (backward compatibility)', async () => {
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 456,
        title: 'Simple title',
        body: 'Simple body',
        author: {
          login: 'testuser2',
          id: 67890
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe('Simple title');
      expect(result.body).toBe('Simple body');
      expect(result.number).toBe(456);
    });

    test('should handle partial base64 encoding (only title encoded)', async () => {
      const title = 'Encoded title with "quotes"';
      const titleBase64 = Buffer.from(title, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 789,
        title_base64: titleBase64,
        body: 'Plain body text',
        encoding: {
          title: 'base64'
        },
        author: {
          login: 'testuser3',
          id: 11111
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe(title);
      expect(result.body).toBe('Plain body text');
    });

    test('should handle partial base64 encoding (only body encoded)', async () => {
      const body = 'Encoded body with ```yaml\nrelease: 2.1\n```';
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 999,
        title: 'Plain title',
        body_base64: bodyBase64,
        encoding: {
          body: 'base64'
        },
        author: {
          login: 'testuser4',
          id: 22222
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe('Plain title');
      expect(result.body).toBe(body);
    });

    test('should handle complex content that would cause JSON parsing errors without base64', async () => {
      // This content would cause "Bad control character in string literal" error if not base64 encoded
      const title = 'PR with control chars: \n\t\r"';
      const body = `## Description

Complex YAML content:

\`\`\`yaml
release: "2.1"
backport: # (optional) "2.5", "2.6", "2.7"
needs_feature_branch: true
labels:
  - "enhancement"
  - "bug-fix"
\`\`\`

Multiple lines with quotes " and newlines
	Tabs and other control characters`;

      const titleBase64 = Buffer.from(title, 'utf8').toString('base64');
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'edited',
        number: 6,
        title_base64: titleBase64,
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        state: 'open',
        draft: false,
        author: {
          login: 'thenets',
          id: 2138276
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe(title);
      expect(result.body).toBe(body);
      expect(result.body).toContain('```yaml');
      expect(result.body).toContain('release: "2.1"');
      expect(result.body).toContain('needs_feature_branch: true');
      expect(result.body).toContain('"enhancement"');
      expect(result.number).toBe(6);
      expect(result.author.login).toBe('thenets');
    });

    test('should handle issue metadata with base64 encoding', async () => {
      const title = 'Issue with "quotes" and\nnewlines';
      const body = 'Issue body with special chars:\n\t- Item 1\n\t- Item 2';
      
      const titleBase64 = Buffer.from(title, 'utf8').toString('base64');
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'issue',
        event_action: 'opened',
        number: 42,
        title_base64: titleBase64,
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        state: 'open',
        author: {
          login: 'issueuser',
          id: 33333
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.type).toBe('issue');
      expect(result.title).toBe(title);
      expect(result.body).toBe(body);
      expect(result.number).toBe(42);
    });

    test('should gracefully handle base64 decoding errors', async () => {
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 999,
        title_base64: 'invalid-base64!@#$',
        body_base64: 'also-invalid-base64!@#$',
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

      // Should still return metadata but without decoded fields
      expect(result).not.toBeNull();
      expect(result.number).toBe(999);
      expect(result.author.login).toBe('testuser');
      // Title and body should remain undefined since decoding failed
      expect(result.title).toBeUndefined();
      expect(result.body).toBeUndefined();
    });

    test('should handle empty base64 fields', async () => {
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 111,
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
      expect(result.title).toBe('');
      expect(result.body).toBe('');
      expect(result.number).toBe(111);
    });

    test('should handle missing base64 fields when encoding is specified', async () => {
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 222,
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
      // Should not have title/body since the base64 fields are missing
      expect(result.title).toBeUndefined();
      expect(result.body).toBeUndefined();
    });
  });

  describe('Base64 encoding/decoding edge cases', () => {
    test('should handle Unicode characters in base64 content', async () => {
      const title = 'PR with émojis 🚀 and üñíçødé chars';
      const body = 'Content with various Unicode: café, naïve, 中文, العربية, 🎉';
      
      const titleBase64 = Buffer.from(title, 'utf8').toString('base64');
      const bodyBase64 = Buffer.from(body, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 555,
        title_base64: titleBase64,
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'unicode-user',
          id: 44444
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe(title);
      expect(result.body).toBe(body);
      expect(result.title).toContain('🚀');
      expect(result.body).toContain('🎉');
      expect(result.body).toContain('中文');
    });

    test('should handle very long content in base64', async () => {
      // Create a very long PR body to test large base64 content
      const longBody = 'This is a very long PR description.\n'.repeat(1000);
      const bodyBase64 = Buffer.from(longBody, 'utf8').toString('base64');
      
      const metadataContent = JSON.stringify({
        type: 'pull_request',
        event_action: 'opened',
        number: 777,
        title_base64: Buffer.from('Long content test', 'utf8').toString('base64'),
        body_base64: bodyBase64,
        encoding: {
          title: 'base64',
          body: 'base64'
        },
        author: {
          login: 'long-content-user',
          id: 55555
        }
      });

      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(metadataContent);

      const result = await automation.loadMetadataFromArtifact();

      expect(result).not.toBeNull();
      expect(result.title).toBe('Long content test');
      expect(result.body).toBe(longBody);
      expect(result.body.length).toBe(longBody.length);
    });
  });
});