/**
 * Unit tests for ConfigManager class
 * Tests configuration management, YAML parsing, and validation logic
 */

const { ConfigManager } = require('../../../src/utils/config');

describe('ConfigManager', () => {
  let mockContext;
  let config;

  beforeEach(() => {
    mockContext = createMockContext();
    config = new ConfigManager(mockContext);
  });

  describe('Constructor and Basic Properties', () => {
    test('should initialize with context', () => {
      expect(config.context).toBe(mockContext);
      expect(config.owner).toBe('test-owner');
      expect(config.repo).toBe('test-repo');
      expect(config.repository).toBe('test-owner/test-repo');
    });

    test('should initialize with options', () => {
      const options = { dryRun: true, githubToken: 'token123' };
      const configWithOptions = new ConfigManager(mockContext, options);
      
      expect(configWithOptions.options).toBe(options);
      expect(configWithOptions.isDryRun()).toBe(true);
      expect(configWithOptions.getGithubToken()).toBe('token123');
    });
  });

  describe('Repository Information', () => {
    test('should return repository information', () => {
      const repoInfo = config.getRepository();
      
      expect(repoInfo).toEqual({
        owner: 'test-owner',
        repo: 'test-repo',
        fullName: 'test-owner/test-repo'
      });
    });
  });

  describe('Configuration Getters', () => {
    test('should return dry run status', () => {
      expect(config.isDryRun()).toBe(false);
      
      const dryRunConfig = new ConfigManager(mockContext, { dryRun: true });
      expect(dryRunConfig.isDryRun()).toBe(true);
    });

    test('should return GitHub token', () => {
      expect(config.getGithubToken()).toBeUndefined();
      
      const tokenConfig = new ConfigManager(mockContext, { githubToken: 'test-token' });
      expect(tokenConfig.getGithubToken()).toBe('test-token');
    });

    test('should return accepted releases', () => {
      expect(config.getAcceptedReleases()).toEqual([]);
      
      const releasesConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0', '1.1'] 
      });
      expect(releasesConfig.getAcceptedReleases()).toEqual(['1.0', '1.1']);
    });

    test('should return accepted backports', () => {
      expect(config.getAcceptedBackports()).toEqual([]);
      
      const backportsConfig = new ConfigManager(mockContext, { 
        acceptedBackports: ['main', '1.0'] 
      });
      expect(backportsConfig.getAcceptedBackports()).toEqual(['main', '1.0']);
    });

    test('should return stale days', () => {
      expect(config.getStaleDays()).toBeUndefined();
      
      const staleConfig = new ConfigManager(mockContext, { staleDays: 7 });
      expect(staleConfig.getStaleDays()).toBe(7);
    });
  });

  describe('Feature Detection', () => {
    test('should detect feature branch enabled', () => {
      expect(config.isFeatureBranchEnabled()).toBe(false);
      
      const featureConfig = new ConfigManager(mockContext, { enableFeatureBranch: true });
      expect(featureConfig.isFeatureBranchEnabled()).toBe(true);
    });

    test('should detect release labeling enabled', () => {
      expect(config.isReleaseLabelingEnabled()).toBe(false);
      
      const releaseConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0'] 
      });
      expect(releaseConfig.isReleaseLabelingEnabled()).toBe(true);
    });

    test('should detect backport labeling enabled', () => {
      expect(config.isBackportLabelingEnabled()).toBe(false);
      
      const backportConfig = new ConfigManager(mockContext, { 
        acceptedBackports: ['main'] 
      });
      expect(backportConfig.isBackportLabelingEnabled()).toBe(true);
    });

    test('should detect stale detection enabled', () => {
      expect(config.isStaleDetectionEnabled()).toBe(false);
      
      const staleConfig = new ConfigManager(mockContext, { staleDays: 7 });
      expect(staleConfig.isStaleDetectionEnabled()).toBe(true);
      
      const scheduleContext = createMockContext({ eventName: 'schedule' });
      const scheduleConfig = new ConfigManager(scheduleContext);
      expect(scheduleConfig.isStaleDetectionEnabled()).toBe(true);
    });
  });

  describe('YAML Parsing', () => {
    test('should parse YAML from text', () => {
      const text = `
Some text before
\`\`\`yaml
release: "1.0"
backport: "main"
\`\`\`
Some text after
      `;
      
      const yamlContent = config.parseYamlFromText(text);
      expect(yamlContent).toBe('release: "1.0"\nbackport: "main"');
    });

    test('should return null for text without YAML', () => {
      const text = 'Just some regular text';
      const yamlContent = config.parseYamlFromText(text);
      expect(yamlContent).toBeNull();
    });

    test('should return null for empty text', () => {
      expect(config.parseYamlFromText('')).toBeNull();
      expect(config.parseYamlFromText(null)).toBeNull();
    });

    test('should parse first YAML block when multiple exist', () => {
      const text = `
\`\`\`yaml
release: "1.0"
\`\`\`
Some text
\`\`\`yaml
release: "2.0"
\`\`\`
      `;
      
      const yamlContent = config.parseYamlFromText(text);
      expect(yamlContent).toBe('release: "1.0"');
    });
  });

  describe('YAML Value Parsing', () => {
    test('should parse simple values', () => {
      const yamlContent = 'release: "1.0"\nbackport: main';
      
      expect(config.parseYamlValue(yamlContent, 'release')).toBe('1.0');
      expect(config.parseYamlValue(yamlContent, 'backport')).toBe('main');
    });

    test('should handle values with comments', () => {
      const yamlContent = 'release: "1.0" # This is a comment';
      
      expect(config.parseYamlValue(yamlContent, 'release')).toBe('1.0');
    });

    test('should handle quoted values', () => {
      const yamlContent = `
release: '1.0'
backport: "main"
feature: unquoted
      `;
      
      expect(config.parseYamlValue(yamlContent, 'release')).toBe('1.0');
      expect(config.parseYamlValue(yamlContent, 'backport')).toBe('main');
      expect(config.parseYamlValue(yamlContent, 'feature')).toBe('unquoted');
    });

    test('should parse array values', () => {
      const yamlContent = 'release: ["1.0", "1.1"]';
      
      const result = config.parseYamlValue(yamlContent, 'release');
      expect(result).toEqual(['1.0', '1.1']);
    });

    test('should handle mixed quote arrays', () => {
      const yamlContent = "release: ['1.0', \"1.1\"]";
      
      const result = config.parseYamlValue(yamlContent, 'release');
      expect(result).toEqual(['1.0', '1.1']);
    });

    test('should return null for missing fields', () => {
      const yamlContent = 'release: "1.0"';
      
      expect(config.parseYamlValue(yamlContent, 'missing')).toBeNull();
    });

    test('should return null for empty yamlContent', () => {
      expect(config.parseYamlValue('', 'release')).toBeNull();
      expect(config.parseYamlValue(null, 'release')).toBeNull();
    });
  });

  describe('YAML Array Parsing', () => {
    test('should parse valid JSON arrays', () => {
      expect(config.parseYamlArrayValue('["1.0", "1.1"]')).toEqual(['1.0', '1.1']);
      expect(config.parseYamlArrayValue("['1.0', '1.1']")).toEqual(['1.0', '1.1']);
    });

    test('should handle mixed quotes', () => {
      expect(config.parseYamlArrayValue("['1.0', \"1.1\"]")).toEqual(['1.0', '1.1']);
    });

    test('should filter empty strings', () => {
      expect(config.parseYamlArrayValue('["1.0", "", "1.1"]')).toEqual(['1.0', '1.1']);
    });

    test('should convert non-string values to strings', () => {
      expect(config.parseYamlArrayValue('[1.0, 1.1]')).toEqual(['1', '1.1']);
    });

    test('should return null for invalid arrays', () => {
      expect(config.parseYamlArrayValue('invalid')).toBeNull();
      expect(config.parseYamlArrayValue('["unclosed')).toBeNull();
      expect(config.parseYamlArrayValue('not-an-array')).toBeNull();
    });

    test('should return null for non-array JSON', () => {
      expect(config.parseYamlArrayValue('"string"')).toBeNull();
      expect(config.parseYamlArrayValue('123')).toBeNull();
    });
  });

  describe('Validation', () => {
    test('should validate release values - single value', () => {
      const releaseConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0', '1.1'] 
      });
      
      expect(releaseConfig.validateReleaseValue('1.0')).toBe(true);
      expect(releaseConfig.validateReleaseValue('2.0')).toBe(false);
    });

    test('should validate release values - array', () => {
      const releaseConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0', '1.1'] 
      });
      
      const result = releaseConfig.validateReleaseValue(['1.0', '1.1', '2.0']);
      expect(result).toEqual([
        { value: '1.0', valid: true },
        { value: '1.1', valid: true },
        { value: '2.0', valid: false }
      ]);
    });

    test('should validate backport values - single value', () => {
      const backportConfig = new ConfigManager(mockContext, { 
        acceptedBackports: ['main', '1.0'] 
      });
      
      expect(backportConfig.validateBackportValue('main')).toBe(true);
      expect(backportConfig.validateBackportValue('feature')).toBe(false);
    });

    test('should validate backport values - array', () => {
      const backportConfig = new ConfigManager(mockContext, { 
        acceptedBackports: ['main', '1.0'] 
      });
      
      const result = backportConfig.validateBackportValue(['main', '1.0', 'feature']);
      expect(result).toEqual([
        { value: 'main', valid: true },
        { value: '1.0', valid: true },
        { value: 'feature', valid: false }
      ]);
    });

    test('should get invalid values from validation result', () => {
      const releaseConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0', '1.1'] 
      });
      
      const validationResult = releaseConfig.validateReleaseValue(['1.0', '2.0', '3.0']);
      const invalidValues = releaseConfig.getInvalidValues(validationResult);
      
      expect(invalidValues).toEqual(['2.0', '3.0']);
    });

    test('should get valid values from validation result', () => {
      const releaseConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0', '1.1'] 
      });
      
      const validationResult = releaseConfig.validateReleaseValue(['1.0', '2.0', '1.1']);
      const validValues = releaseConfig.getValidValues(validationResult);
      
      expect(validValues).toEqual(['1.0', '1.1']);
    });

    test('should handle single value in getValidValues', () => {
      const releaseConfig = new ConfigManager(mockContext, { 
        acceptedReleases: ['1.0'] 
      });
      
      expect(releaseConfig.getValidValues(true)).toEqual([true]);
      expect(releaseConfig.getValidValues(false)).toEqual([]);
    });
  });

  describe('Configuration Validation', () => {
    test('should validate required configuration', () => {
      const validConfig = new ConfigManager(mockContext, { githubToken: 'token' });
      expect(() => validConfig.validate()).not.toThrow();
    });

    test('should throw error for missing repository info', () => {
      const invalidContext = { repo: {} };
      const invalidConfig = new ConfigManager(invalidContext, { githubToken: 'token' });
      
      expect(() => invalidConfig.validate()).toThrow('Repository owner and name are required');
    });

    test('should throw error for missing GitHub token', () => {
      expect(() => config.validate()).toThrow('GitHub token is required');
    });

    test('should validate stale detection days', () => {
      // For validation to trigger, we need staleDays set to a negative value
      // since 0 is falsy and won't trigger the getStaleDays() check
      const invalidStaleConfig = new ConfigManager(mockContext, { 
        githubToken: 'token',
        staleDays: -1  // Negative value will be truthy and < 1
      });
      
      expect(() => invalidStaleConfig.validate()).toThrow('Stale detection days must be 1 or greater');
    });

    test('should allow valid stale detection days', () => {
      const validStaleConfig = new ConfigManager(mockContext, { 
        githubToken: 'token',
        staleDays: 7 
      });
      
      expect(() => validStaleConfig.validate()).not.toThrow();
    });
  });
});