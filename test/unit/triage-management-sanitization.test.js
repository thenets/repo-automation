/**
 * Unit tests for JSON sanitization in RepositoryAutomation
 * Tests the sanitizeJsonContent method with various edge cases
 */

const { RepositoryAutomation } = require('../../src/triage-management');

// Mock dependencies to isolate sanitization testing
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('RepositoryAutomation - JSON Sanitization', () => {
  let automation;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock context and github objects
    const mockContext = {
      repo: { owner: 'test', repo: 'test' },
      eventName: 'pull_request',
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
  });

  describe('sanitizeJsonContent', () => {
    test('should handle simple single-line fields', () => {
      const input = `{
  "type": "pull_request",
  "title": "Simple title",
  "body": "Simple body"
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toBe('Simple title');
      expect(parsed.body).toBe('Simple body');
    });

    test('should escape quotes in fields', () => {
      const input = `{
  "type": "pull_request",
  "title": "Title with "quotes" inside",
  "body": "Body with "quotes" too"
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toBe('Title with "quotes" inside');
      expect(parsed.body).toBe('Body with "quotes" too');
    });

    test('should handle multi-line fields with newlines', () => {
      const input = `{
  "type": "pull_request",
  "title": "Simple title",
  "body": "First line
Second line
Third line"
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.body).toBe('First line\nSecond line\nThird line');
    });

    test('should handle complex PR body with markdown and YAML', () => {
      const input = `{
  "type": "pull_request",
  "title": "no op change",
  "body": "## Description

<!-- Mandatory: Provide a clear, concise description of the changes and their purpose -->
- What is being changed?
- Why is this change needed?

\`\`\`yaml
release: "2.5"
backport: # (optional) "2.5", "2.6", "2.7"
needs_feature_branch: false
\`\`\`

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)"
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toBe('no op change');
      expect(parsed.body).toContain('## Description');
      expect(parsed.body).toContain('```yaml');
      expect(parsed.body).toContain('release: "2.5"');
    });

    test('should handle special characters and tabs', () => {
      const input = `{
  "type": "pull_request",
  "title": "Special chars: tabs	and newlines",
  "body": "Body with multiple lines	and tabs"
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toContain('tabs\t');
      expect(parsed.body).toContain('tabs');
    });

    test('should handle real-world aap-gateway-debug example', () => {
      // This is a simplified version of the actual failing content
      const input = `{
  "type": "pull_request",
  "number": 6,
  "title": "no op change",
  "body": "## Description

<!-- Comment with quotes " and newlines -->
- What is being changed?

\`\`\`yaml
release: "2.6"
\`\`\`

## Type of Change
- [ ] Bug fix",
  "author": {
    "login": "thenets",
    "id": 2138276
  }
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toBe('no op change');
      expect(parsed.body).toContain('## Description');
      expect(parsed.body).toContain('```yaml');
      expect(parsed.author.login).toBe('thenets');
      expect(parsed.number).toBe(6);
    });

    test('should handle empty fields', () => {
      const input = `{
  "type": "pull_request",
  "title": "",
  "body": ""
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toBe('');
      expect(parsed.body).toBe('');
    });

    test('should handle fields with only whitespace', () => {
      const input = `{
  "type": "pull_request",
  "title": "   ",
  "body": "
  
  "
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toBe('   ');
      expect(parsed.body).toBe('\n  \n  ');
    });

    test('should not modify JSON if no title or body fields present', () => {
      const input = `{
  "type": "issue",
  "number": 123,
  "state": "open"
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(result).toBe(input);
      expect(() => JSON.parse(result)).not.toThrow();
    });

    test('should handle nested quotes and backslashes', () => {
      const input = `{
  "type": "pull_request",
  "title": "Path: C:\\\\Users\\\\test",
  "body": "Code: \\"const x = 'hello';\\"
And more \\"nested \\\\\\"quotes\\\\\\" here\""
}`;
      
      const result = automation.sanitizeJsonContent(input);
      expect(() => JSON.parse(result)).not.toThrow();
      
      const parsed = JSON.parse(result);
      expect(parsed.title).toContain('C:\\\\Users\\\\test');
      expect(parsed.body).toContain('const x = \'hello\';');
    });
  });
});