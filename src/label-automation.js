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
const { logger } = require('./utils/logger');

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
      logger.log(`🔖 Starting label automation...`);

      // Extract PR data from event
      const targetPrData = await this.extractPRData();
      if (!targetPrData) {
        logger.info('ℹ️ No PR data available for label automation');
        return this.result;
      }

      logger.log(`🔍 Processing PR #${targetPrData.number}: ${targetPrData.title}`);

      // Skip if PR is draft
      if (targetPrData.draft) {
        logger.info('⏭️ Skipping draft pull request');
        return this.result;
      }

      // Parse YAML from PR description
      const yamlContent = this.config.parseYamlFromText(targetPrData.body || '');
      
      if (!yamlContent) {
        logger.info('ℹ️ No YAML frontmatter found in PR description');
        
        // Clean up any existing error comments when YAML is completely removed
        if (features.featureBranch) {
          logger.info('🧹 Cleaning up feature branch error comments (no YAML found)');
          await this.client.cleanupWorkflowComments(targetPrData.number, '🚨 YAML Validation Error: feature branch');
        }
        
        if (features.releaseLabeling || features.backportLabeling) {
          logger.info('🧹 Cleaning up release/backport error comments (no YAML found)');
          await this.client.cleanupWorkflowComments(targetPrData.number, '🚨 YAML Validation Error: release and backport');
        }
        
        return this.result;
      }

      logger.log(`📝 Found YAML content in PR description`);

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
      logger.error('❌ Label automation failed:' + error.message);
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
        logger.log(`📦 Using metadata from artifact: ${metadata.type} #${metadata.number}`);
        return metadata;
      }
      
      // Fallback to old pattern: find PR by branch
      logger.info('⚠️ No artifact metadata found, falling back to branch-based PR lookup');
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
        logger.info('📋 No artifact metadata file found');
        return null;
      }
      
      // Read and parse metadata
      const metadataContent = fs.readFileSync(metadataPath, 'utf8');
      const metadata = JSON.parse(metadataContent);
      
      // Decode base64 encoded fields if present
      if (metadata.encoding) {
        if (metadata.encoding.title === 'base64' && metadata.title_base64 !== undefined) {
          try {
            // Handle empty strings
            if (metadata.title_base64 === '') {
              metadata.title = '';
              logger.log('✅ Decoded empty base64 title field');
            } else {
              // Validate base64 format before decoding
              if (!/^[A-Za-z0-9+/]*={0,2}$/.test(metadata.title_base64)) {
                logger.log(`⚠️ Invalid base64 format in title field`);
              } else {
                metadata.title = Buffer.from(metadata.title_base64, 'base64').toString('utf8');
                logger.log('✅ Decoded base64 title field');
              }
            }
          } catch (error) {
            logger.log(`⚠️ Failed to decode base64 title: ${error.message}`);
          }
        }
        
        if (metadata.encoding.body === 'base64' && metadata.body_base64 !== undefined) {
          try {
            // Handle empty strings
            if (metadata.body_base64 === '') {
              metadata.body = '';
              logger.log('✅ Decoded empty base64 body field');
            } else {
              // Validate base64 format before decoding
              if (!/^[A-Za-z0-9+/]*={0,2}$/.test(metadata.body_base64)) {
                logger.log(`⚠️ Invalid base64 format in body field`);
              } else {
                metadata.body = Buffer.from(metadata.body_base64, 'base64').toString('utf8');
                logger.log('✅ Decoded base64 body field');
              }
            }
          } catch (error) {
            logger.log(`⚠️ Failed to decode base64 body: ${error.message}`);
          }
        }
      }
      
      logger.log(`📦 Loaded metadata: ${metadata.type} #${metadata.number} by ${metadata.author ? metadata.author.login : 'unknown'}`);
      
      return metadata;
      
    } catch (error) {
      logger.log(`⚠️ Failed to load artifact metadata: ${error.message}`);
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

      // Validate repository label existence and create missing labels for valid values
      if (labelsToAdd.length > 0) {
        const labelValidation = await this.client.validateRepositoryLabels(labelsToAdd);
        if (!labelValidation.valid) {
          const missingLabels = labelValidation.missing;
          const createdLabels = [];
          const failedLabels = [];

          // Attempt to create missing labels for valid release/backport values
          for (const missingLabel of missingLabels) {
            try {
              if (this.isValidLabelForCreation(missingLabel)) {
                const { color, description } = this.getLabelMetadata(missingLabel);
                await this.client.createRepositoryLabel(missingLabel, color, description);
                createdLabels.push(missingLabel);
                logger.log(`✅ Created missing repository label: ${missingLabel}`);
              } else {
                failedLabels.push(missingLabel);
              }
            } catch (error) {
              logger.error(`❌ Failed to create repository label "${missingLabel}": ${error.message}`);
              failedLabels.push(missingLabel);
            }
          }

          // Only report errors for labels that couldn't be created
          if (failedLabels.length > 0) {
            const repositoryLabelError = `❌ Repository labels do not exist and could not be created: ${failedLabels.map(l => `"${l}"`).join(', ')}. ` +
              `Repository administrators must create these labels in the repository settings before they can be used.`;
            validationErrors.push(repositoryLabelError);
          }

          // Log successful creations
          if (createdLabels.length > 0) {
            logger.log(`✅ Successfully created ${createdLabels.length} missing repository label(s): ${createdLabels.join(', ')}`);
          }
        }
      }

      // Handle validation errors by posting comments (no check runs required)
      if (validationErrors.length > 0) {
        await this.handleValidationErrors(prNumber, null, validationErrors);
        // Throw error to fail the job explicitly
        throw new Error(`Label validation failed: ${validationErrors.join('; ')}`);
      }

      // Clean up previous error comments
      await this.client.cleanupWorkflowComments(prNumber, '🚨 YAML Validation Error: release and backport');

      // Add labels if any
      if (labelsToAdd.length > 0) {
        const result = await this.client.addLabels(prNumber, labelsToAdd);
        this.result.labelsAdded.push(...result.added);
        this.result.actions.push(`Added release/backport labels: ${labelsToAdd.join(', ')}`);

        logger.log(`✅ Successfully added release/backport labels: ${labelsToAdd.join(', ')}`);
      } else {
        logger.info('ℹ️ No release/backport labels to add based on YAML configuration');
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

    // Check if any errors are related to missing repository labels
    const hasRepositoryLabelErrors = errors.some(error => error.includes('Repository labels do not exist'));

    let errorComment = '## 🚨 YAML Validation Error: release and backport\n\n' +
      errors.map(error => `- ${error}`).join('\n') + '\n\n';

    if (hasRepositoryLabelErrors) {
      errorComment += '### For Repository Administrators:\n' +
        '⚠️ **Missing repository labels detected!** The following labels need to be created:\n\n' +
        '1. Go to repository **Settings** → **Labels**\n' +
        '2. Create the missing labels shown in the error above\n' +
        '3. Use these naming patterns:\n' +
        '   - `release-X.Y` (e.g., `release-2.1`, `release-2.2`)\n' +
        '   - `backport-X.Y` (e.g., `backport-1.5`, `backport-2.0`)\n' +
        '4. Re-run the workflow after creating the labels\n\n' +
        '### For Contributors:\n' +
        'Please wait for repository administrators to create the required labels.\n\n';
    } else {
      errorComment += '### How to fix:\n' +
        '1. Update your PR description YAML block with valid values\n' +
        '2. The workflow will automatically re-run when you edit the description\n\n' +
        '### Valid YAML format:\n' +
        '```yaml\n' +
        `release: 1.5    # Valid releases: ${acceptedReleases.join(', ')}\n` +
        `backport: 1.4   # Valid backports: ${acceptedBackports.join(', ')}\n` +
        '```\n\n';
    }

    errorComment += `_This comment was posted by the repository automation workflow._`;

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
    this.result.actions.push(`Posted validation error comment to PR #${prNumber}`);
    console.log('💬 Posted validation error comment to PR');
  }

  /**
   * Check if a label is valid for automatic creation
   * Only release-* and backport-* labels for valid values should be created
   */
  isValidLabelForCreation(labelName) {
    if (labelName.startsWith('release-')) {
      const version = labelName.substring('release-'.length);
      const acceptedReleases = this.config.getAcceptedReleases();
      return acceptedReleases.includes(version);
    }
    
    if (labelName.startsWith('backport-')) {
      const version = labelName.substring('backport-'.length);
      const acceptedBackports = this.config.getAcceptedBackports();
      return acceptedBackports.includes(version);
    }
    
    return false;
  }

  /**
   * Get label metadata (color and description) for automatic creation
   */
  getLabelMetadata(labelName) {
    if (labelName.startsWith('release-')) {
      const version = labelName.substring('release-'.length);
      return {
        color: '00FF00', // Green for releases
        description: `Release ${version}`
      };
    }
    
    if (labelName.startsWith('backport-')) {
      const version = labelName.substring('backport-'.length);
      return {
        color: '0000FF', // Blue for backports  
        description: `Backport to ${version}`
      };
    }
    
    // Default fallback (shouldn't be reached if isValidLabelForCreation is used properly)
    return {
      color: 'CCCCCC',
      description: 'Automatically created label'
    };
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
    this.result.actions.push(`Posted validation error comment to PR #${prNumber}`);
    console.log('💬 Posted validation error comment to PR');
  }
}

module.exports = { LabelAutomation };