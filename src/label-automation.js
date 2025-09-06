/**
 * Label Automation Module
 * Extracted and modularized logic from:
 * - keeper-auto-label-release-backport.yml
 * - keeper-feature-branch-auto-labeling.yml
 * 
 * Handles:
 * - Release/backport auto-labeling from YAML frontmatter
 * - Feature branch automation based on YAML configuration
 * - YAML validation with check runs and error reporting
 * - Comment cleanup and user feedback
 */

const { ConfigManager } = require('./utils/config');
const { GitHubClient } = require('./utils/github-client');

class LabelAutomation {
  constructor(context, github, options = {}) {
    this.context = context;
    this.github = github;
    this.config = new ConfigManager(context, options);
    this.client = new GitHubClient(github, this.config);
    this.result = {
      labelsAdded: [],
      actions: [],
      checkRuns: []
    };
  }

  /**
   * Main execution function for label automation
   */
  async execute(features) {
    try {
      console.log(`🔖 Starting label automation...`);

      // Extract PR data from event
      const targetPrData = await this.extractPRData();
      if (!targetPrData) {
        console.log('ℹ️ No PR data available for label automation');
        return this.result;
      }

      console.log(`🔍 Processing PR #${targetPrData.number}: ${targetPrData.title}`);

      // Skip if PR is draft
      if (targetPrData.draft) {
        console.log('⏭️ Skipping draft pull request');
        return this.result;
      }

      // Parse YAML from PR description
      const yamlContent = this.config.parseYamlFromText(targetPrData.body || '');
      
      if (!yamlContent) {
        console.log('ℹ️ No YAML frontmatter found in PR description');
        
        // Clean up any existing error comments when YAML is completely removed
        if (features.featureBranch) {
          console.log('🧹 Cleaning up feature branch error comments (no YAML found)');
          await this.client.cleanupWorkflowComments(targetPrData.number, '🚨 YAML Validation Error: feature branch');
        }
        
        if (features.releaseLabeling || features.backportLabeling) {
          console.log('🧹 Cleaning up release/backport error comments (no YAML found)');
          await this.client.cleanupWorkflowComments(targetPrData.number, '🚨 YAML Validation Error: release and backport');
        }
        
        return this.result;
      }

      console.log(`📝 Found YAML content in PR description`);

      // Process release/backport labeling if enabled
      if (features.releaseLabeling || features.backportLabeling) {
        await this.processReleaseBackportLabeling(targetPrData, yamlContent, features);
      }

      // Process feature branch labeling if enabled
      if (features.featureBranch) {
        await this.processFeatureBranchLabeling(targetPrData, yamlContent);
      }

      return this.result;

    } catch (error) {
      console.error('❌ Label automation failed:', error.message);
      throw error;
    }
  }

  /**
   * Extract PR data from context (handles both direct PR events and workflow_run)
   */
  async extractPRData() {
    if (this.context.eventName === 'pull_request') {
      // Direct PR event
      return this.context.payload.pull_request;
    } else if (this.context.eventName === 'workflow_run') {
      // workflow_run event - first try to load metadata from artifact (new fork-compatible pattern)
      const metadata = await this.loadMetadataFromArtifact();
      
      if (metadata && metadata.type === 'pull_request') {
        console.log(`📦 Using metadata from artifact: ${metadata.type} #${metadata.number}`);
        return metadata;
      }
      
      // Fallback to old pattern: find PR by branch
      console.log('⚠️ No artifact metadata found, falling back to branch-based PR lookup');
      const workflowRun = this.context.payload.workflow_run;
      const headBranch = workflowRun.head_branch;
      
      if (!headBranch || headBranch === 'main') {
        return null;
      }

      const pr = await this.client.findPRByBranch(headBranch);
      if (!pr || pr.state === 'closed') {
        return null;
      }

      return pr;
    }

    return null;
  }

  /**
   * Load metadata from artifact (for fork compatibility)
   */
  async loadMetadataFromArtifact() {
    try {
      const fs = require('fs');
      const path = require('path');
      
      // Check if artifact metadata file exists
      const metadataPath = path.join('./pr-metadata', 'metadata.json');
      
      if (!fs.existsSync(metadataPath)) {
        console.log('📋 No artifact metadata file found');
        return null;
      }
      
      // Read and parse metadata
      const metadataContent = fs.readFileSync(metadataPath, 'utf8');
      const metadata = JSON.parse(metadataContent);
      
      console.log(`📦 Loaded metadata: ${metadata.type} #${metadata.number} by ${metadata.author.login}`);
      
      return metadata;
      
    } catch (error) {
      console.log(`⚠️ Failed to load artifact metadata: ${error.message}`);
      return null;
    }
  }

  /**
   * Process release and backport labeling
   */
  async processReleaseBackportLabeling(prData, yamlContent, features) {
    const prNumber = prData.number;

    try {
      const validationErrors = [];
      const labelsToAdd = [];

      // Check existing labels to avoid overwriting manual labels
      const currentLabels = await this.client.getLabels(prNumber);
      const hasExistingReleaseLabel = currentLabels.some(label => label.startsWith('release-'));
      const hasExistingBackportLabel = currentLabels.some(label => label.startsWith('backport-'));

      // Process release labeling
      if (features.releaseLabeling) {
        const releaseResult = await this.processReleaseLabel(yamlContent, hasExistingReleaseLabel);
        if (releaseResult.error) {
          validationErrors.push(releaseResult.error);
        } else if (releaseResult.labels && releaseResult.labels.length > 0) {
          labelsToAdd.push(...releaseResult.labels);
        }
      }

      // Process backport labeling
      if (features.backportLabeling) {
        const backportResult = await this.processBackportLabel(yamlContent, hasExistingBackportLabel);
        if (backportResult.error) {
          validationErrors.push(backportResult.error);
        } else if (backportResult.labels && backportResult.labels.length > 0) {
          labelsToAdd.push(...backportResult.labels);
        }
      }

      // Handle validation errors by posting comments (no check runs required)
      if (validationErrors.length > 0) {
        await this.handleValidationErrors(prNumber, null, validationErrors);
        return;
      }

      // Clean up previous error comments
      await this.client.cleanupWorkflowComments(prNumber, '🚨 YAML Validation Error: release and backport');

      // Add labels if any
      if (labelsToAdd.length > 0) {
        const result = await this.client.addLabels(prNumber, labelsToAdd);
        this.result.labelsAdded.push(...result.added);
        this.result.actions.push(`Added release/backport labels: ${labelsToAdd.join(', ')}`);

        console.log(`✅ Successfully added release/backport labels: ${labelsToAdd.join(', ')}`);
      } else {
        console.log('ℹ️ No release/backport labels to add based on YAML configuration');
      }

    } catch (error) {
      console.error(`❌ Failed to process release/backport labeling: ${error.message}`);
      throw error;
    }
  }

  /**
   * Process release label from YAML (supports both single values and arrays)
   */
  async processReleaseLabel(yamlContent, hasExistingLabel) {
    const releaseValue = this.config.parseYamlValue(yamlContent, 'release');
    
    if (!releaseValue) {
      return { labels: [], error: null };
    }

    if (hasExistingLabel) {
      const displayValue = Array.isArray(releaseValue) ? JSON.stringify(releaseValue) : releaseValue;
      console.log(`Release label already exists, skipping automatic assignment of "release-${displayValue}"`);
      return { labels: [], error: null };
    }

    const validationResult = this.config.validateReleaseValue(releaseValue);
    
    if (Array.isArray(releaseValue)) {
      // Handle array values
      const invalidValues = this.config.getInvalidValues(validationResult);
      const validValues = this.config.getValidValues(validationResult);
      
      if (invalidValues.length > 0) {
        const acceptedReleases = this.config.getAcceptedReleases();
        return { 
          labels: [], 
          error: `❌ Invalid release values: ${invalidValues.map(v => `"${v}"`).join(', ')}. Accepted values: ${acceptedReleases.join(', ')}` 
        };
      }
      
      if (validValues.length > 0) {
        const labels = validValues.map(v => `release-${v}`);
        console.log(`Found valid release values: ${validValues.join(', ')}`);
        return { labels, error: null };
      }
    } else {
      // Handle single value (backward compatibility)
      if (validationResult) {
        console.log(`Found valid release: ${releaseValue}`);
        return { labels: [`release-${releaseValue}`], error: null };
      } else {
        const acceptedReleases = this.config.getAcceptedReleases();
        return { 
          labels: [], 
          error: `❌ Invalid release value: "${releaseValue}". Accepted values: ${acceptedReleases.join(', ')}` 
        };
      }
    }
    
    return { labels: [], error: null };
  }

  /**
   * Process backport label from YAML (supports both single values and arrays)
   */
  async processBackportLabel(yamlContent, hasExistingLabel) {
    const backportValue = this.config.parseYamlValue(yamlContent, 'backport');
    
    if (!backportValue) {
      return { labels: [], error: null };
    }

    if (hasExistingLabel) {
      const displayValue = Array.isArray(backportValue) ? JSON.stringify(backportValue) : backportValue;
      console.log(`Backport label already exists, skipping automatic assignment of "backport-${displayValue}"`);
      return { labels: [], error: null };
    }

    const validationResult = this.config.validateBackportValue(backportValue);
    
    if (Array.isArray(backportValue)) {
      // Handle array values
      const invalidValues = this.config.getInvalidValues(validationResult);
      const validValues = this.config.getValidValues(validationResult);
      
      if (invalidValues.length > 0) {
        const acceptedBackports = this.config.getAcceptedBackports();
        return { 
          labels: [], 
          error: `❌ Invalid backport values: ${invalidValues.map(v => `"${v}"`).join(', ')}. Accepted values: ${acceptedBackports.join(', ')}` 
        };
      }
      
      if (validValues.length > 0) {
        const labels = validValues.map(v => `backport-${v}`);
        console.log(`Found valid backport values: ${validValues.join(', ')}`);
        return { labels, error: null };
      }
    } else {
      // Handle single value (backward compatibility)
      if (validationResult) {
        console.log(`Found valid backport: ${backportValue}`);
        return { labels: [`backport-${backportValue}`], error: null };
      } else {
        const acceptedBackports = this.config.getAcceptedBackports();
        return { 
          labels: [], 
          error: `❌ Invalid backport value: "${backportValue}". Accepted values: ${acceptedBackports.join(', ')}` 
        };
      }
    }
    
    return { labels: [], error: null };
  }

  /**
   * Process feature branch labeling
   */
  async processFeatureBranchLabeling(prData, yamlContent) {
    const prNumber = prData.number;

    try {
      // Check if feature-branch label already exists
      const currentLabels = await this.client.getLabels(prNumber);
      const hasFeatureBranchLabel = currentLabels.includes('feature-branch');

      if (hasFeatureBranchLabel) {
        console.log('ℹ️ Feature-branch label already exists, skipping automatic assignment');
        await this.client.cleanupWorkflowComments(prNumber, '🚨 YAML Validation Error: feature branch');
        return;
      }

      // Parse needs_feature_branch value
      const featureBranchValue = this.config.parseYamlValue(yamlContent, 'needs_feature_branch');
      
      if (!featureBranchValue) {
        console.log('ℹ️ No needs_feature_branch field found in YAML');
        await this.client.cleanupWorkflowComments(prNumber, '🚨 YAML Validation Error: feature branch');
        return;
      }

      // Validate boolean value
      const lowerValue = featureBranchValue.toLowerCase();
      if (lowerValue === 'true') {
        // Add feature-branch label
        const result = await this.client.addLabels(prNumber, ['feature-branch']);
        this.result.labelsAdded.push(...result.added);
        this.result.actions.push(`Added feature-branch label to PR #${prNumber}`);

        await this.client.cleanupWorkflowComments(prNumber, '🚨 YAML Validation Error: feature branch');
        console.log('✅ Successfully added feature-branch label');

      } else if (lowerValue === 'false' || lowerValue === '') {
        // Valid false/empty value - no action needed
        console.log('✅ No feature-branch label needed based on YAML configuration');
        await this.client.cleanupWorkflowComments(prNumber, '🚨 YAML Validation Error: feature branch');

      } else {
        // Invalid value - post error comment
        const errorMsg = `❌ Invalid needs_feature_branch value: "${featureBranchValue}". Accepted values: true, false (case-insensitive, with optional quotes)`;
        await this.handleFeatureBranchValidationError(prNumber, null, errorMsg);
      }

    } catch (error) {
      console.error(`❌ Failed to process feature branch labeling: ${error.message}`);
      throw error;
    }
  }

  /**
   * Handle validation errors for release/backport
   */
  async handleValidationErrors(prNumber, checkRunId, errors) {
    const acceptedReleases = this.config.getAcceptedReleases();
    const acceptedBackports = this.config.getAcceptedBackports();

    const errorComment = '## 🚨 YAML Validation Error: release and backport\n\n' +
      errors.map(error => `- ${error}`).join('\n') + '\n\n' +
      '### How to fix:\n' +
      '1. Update your PR description YAML block with valid values\n' +
      '2. The workflow will automatically re-run when you edit the description\n\n' +
      '### Valid YAML format:\n' +
      '```yaml\n' +
      `release: 1.5    # Valid releases: ${acceptedReleases.join(', ')}\n` +
      `backport: 1.4   # Valid backports: ${acceptedBackports.join(', ')}\n` +
      '```\n\n' +
      `_This comment was posted by the repository automation workflow._`;

    // Only update check run if checkRunId is provided (for backwards compatibility)
    if (checkRunId) {
      await this.client.updateCheckRun(checkRunId, 'completed', 'failure', {
        title: 'YAML Validation Failed',
        summary: `Found ${errors.length} validation error(s) in PR description YAML block.`,
        text: errors.map(error => `- ${error}`).join('\n') + '\n\n' +
              '**How to fix:**\n' +
              '1. Update your PR description YAML block with valid values\n' +
              '2. The workflow will automatically re-run when you edit the description\n\n' +
              '**Valid YAML format:**\n' +
              '```yaml\n' +
              `release: 1.5    # Valid releases: ${acceptedReleases.join(', ')}\n` +
              `backport: 1.4   # Valid backports: ${acceptedBackports.join(', ')}\n` +
              '```'
      });
    }

    await this.client.createComment(prNumber, errorComment);
    console.log('💬 Posted validation error comment to PR');
  }

  /**
   * Handle validation errors for feature branch
   */
  async handleFeatureBranchValidationError(prNumber, checkRunId, errorMsg) {
    const errorComment = '## 🚨 YAML Validation Error: feature branch\n\n' +
      `- ${errorMsg}\n\n` +
      '### How to fix:\n' +
      '1. Update your PR description YAML block with valid values\n' +
      '2. The workflow will automatically re-run when you edit the description\n\n' +
      '### Valid YAML format:\n' +
      '```yaml\n' +
      'needs_feature_branch: true    # Valid values: true, false (case-insensitive)\n' +
      'needs_feature_branch: false   # Quotes are optional: "true", \'false\', etc.\n' +
      '```\n\n' +
      `_This comment was posted by the repository automation workflow._`;

    // Only update check run if checkRunId is provided (for backwards compatibility)
    if (checkRunId) {
      await this.client.updateCheckRun(checkRunId, 'completed', 'failure', {
        title: 'YAML Validation Failed',
        summary: 'Found validation error in PR description YAML block.',
        text: `- ${errorMsg}\n\n` +
              '**How to fix:**\n' +
              '1. Update your PR description YAML block with valid values\n' +
              '2. The workflow will automatically re-run when you edit the description\n\n' +
              '**Valid YAML format:**\n' +
              '```yaml\n' +
              'needs_feature_branch: true    # Valid values: true, false (case-insensitive)\n' +
              'needs_feature_branch: false   # Quotes are optional: "true", \'false\', etc.\n' +
              '```'
      });
    }

    await this.client.createComment(prNumber, errorComment);
    console.log('💬 Posted validation error comment to PR');
  }
}

module.exports = { LabelAutomation };