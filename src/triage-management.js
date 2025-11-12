/**
 * Repository Automation Orchestrator
 * Main entry point for all repository automation features
 * 
 * Core Features (always enabled):
 * - Auto-add triage labels to new issues
 * - Smart PR labeling (triage vs ready-for-review based on release labels)
 * - Triage label protection (re-add if removed without release/backport labels)
 * - Fork compatibility through workflow_run events
 * 
 * Optional Features (enabled by inputs):
 * - Release/backport auto-labeling (when accepted-releases/accepted-backports provided)
 * - Feature branch automation (when enable-feature-branch is true)
 * - Stale PR detection (when stale-days provided or schedule event)
 */

const { ConfigManager } = require('./utils/config');
const { GitHubClient } = require('./utils/github-client');
const { logger } = require('./utils/logger');

class RepositoryAutomation {
  constructor(context, github, options = {}) {
    this.context = context;
    this.github = github;
    this.config = new ConfigManager(context, options);
    this.client = new GitHubClient(github, this.config);
    this.result = {
      labelsAdded: [],
      summary: '',
      actions: [],
      featuresEnabled: []
    };
    
    // Detect enabled features based on inputs
    this.features = this.detectEnabledFeatures();
  }

  /**
   * Detect which features are enabled based on provided inputs
   */
  detectEnabledFeatures() {
    const options = this.config.options;

    const features = {
      triage: true, // Always enabled (core functionality)
      releaseLabeling: !!(options.acceptedReleases && options.acceptedReleases.length > 0),
      backportLabeling: !!(options.acceptedBackports && options.acceptedBackports.length > 0),
      featureBranch: options.enableFeatureBranch === true,
      staleDetection: !!(options.staleDays) || this.context.eventName === 'schedule',
      titleLabelSync: options.enableTitleLabelSync !== false // Enabled by default (opt-out)
    };

    // Log enabled features
    const enabledFeatures = Object.keys(features).filter(f => features[f]);
    logger.log(`🎯 Enabled features: ${enabledFeatures.join(', ')}`);

    return features;
  }

  /**
   * Main execution function - orchestrates all enabled features
   */
  async execute() {
    try {
      this.config.validate();
      this.config.logConfig();

      logger.log(`🔄 Starting repository automation for event: ${this.context.eventName}`);
      
      // Store enabled features in result
      this.result.featuresEnabled = Object.keys(this.features).filter(f => this.features[f]);

      // Run optional features first to check for validation errors
      if (this.features.releaseLabeling || this.features.backportLabeling || this.features.featureBranch) {
        await this.executeLabelAutomation();
      }

      // Run title-label sync feature (runs before triage automation)
      if (this.features.titleLabelSync) {
        await this.executeTitleLabelSync();
      }

      // Run core triage automation after label automation
      await this.executeTriageAutomation();

      if (this.features.staleDetection) {
        await this.executeStaleDetection();
      }

      return this.result;

    } catch (error) {
      logger.error('❌ Repository automation failed:' + error.message);
      this.result.summary = `Failed: ${error.message}`;
      throw error;
    }
  }

  /**
   * Execute core triage automation (always runs)
   */
  async executeTriageAutomation() {
    await logger.group('🏷️ Executing core triage automation...', async () => {
      // Handle different event types for triage
      if (this.context.eventName === 'issues') {
        await this.handleIssueEvent();
      } else if (this.context.eventName === 'workflow_run') {
        await this.handleWorkflowRunEvent();
      } else if (this.context.eventName === 'pull_request') {
        // Direct PR events (when not using workflow_run pattern)
        const prData = this.context.payload.pull_request;
        await this.handlePullRequestEvent(prData);
      } else {
        logger.info(`ℹ️ Event type ${this.context.eventName} not handled by triage automation`);
      }
    });
  }

  /**
   * Execute label automation features (release/backport/feature-branch)
   */
  async executeLabelAutomation() {
    await logger.group('🔖 Executing label automation...', async () => {
      try {
        // Only process pull_request or workflow_run events for label automation
        if (this.context.eventName === 'pull_request' || this.context.eventName === 'workflow_run') {
          // We don't need to extract PR data here since LabelAutomation 
          // can now handle it on its own with the updated extractPRData method
          
          // Import label automation module when needed
          const { LabelAutomation } = require('./label-automation');
          const labelAutomation = new LabelAutomation(this.context, this.github, this.config.options);
          
          const labelResult = await labelAutomation.execute(this.features);
          
          // Merge results
          this.result.labelsAdded.push(...(labelResult.labelsAdded || []));
          this.result.actions.push(...(labelResult.actions || []));
        }
      } catch (error) {
        if (error.code === 'MODULE_NOT_FOUND') {
          logger.info('ℹ️ Label automation module not yet implemented, skipping...');
        } else {
          throw error;
        }
      }
    });
  }

  /**
   * Execute stale detection feature
   */
  async executeStaleDetection() {
    await logger.group('⏰ Executing stale detection...', async () => {
      try {
        // Only run stale detection on schedule events or when explicitly requested
        if (this.context.eventName === 'schedule' || this.features.staleDetection) {
          // Import stale detection module when needed
          const { StaleDetection } = require('./stale-detection');
          const staleDetection = new StaleDetection(this.context, this.github, this.config.options);

          const staleResult = await staleDetection.execute();

          // Merge results
          this.result.labelsAdded.push(...(staleResult.labelsAdded || []));
          this.result.actions.push(...(staleResult.actions || []));
        }
      } catch (error) {
        if (error.code === 'MODULE_NOT_FOUND') {
          logger.info('ℹ️ Stale detection module not yet implemented, skipping...');
        } else {
          throw error;
        }
      }
    });
  }

  /**
   * Execute title-label sync feature
   */
  async executeTitleLabelSync() {
    await logger.group('🔄 Executing title-label sync...', async () => {
      try {
        // Only process pull_request events for title-label sync
        if (this.context.eventName === 'pull_request') {
          const { TitleLabelSync } = require('./title-label-sync');

          // Check if this event should trigger sync
          if (!TitleLabelSync.shouldSync(this.context)) {
            logger.log(`ℹ️ Event action ${this.context.payload.action} does not require title-label sync`);
            return;
          }

          const prData = this.context.payload.pull_request;

          // Skip draft PRs
          if (prData.draft) {
            logger.log(`ℹ️ PR #${prData.number} is draft, skipping title-label sync`);
            return;
          }

          const titleLabelSync = new TitleLabelSync(this.context, this.client, this.config);
          const syncResult = await titleLabelSync.execute(prData);

          // Merge results
          if (syncResult.labelsAdded && syncResult.labelsAdded.length > 0) {
            this.result.labelsAdded.push(...syncResult.labelsAdded);
          }
          if (syncResult.labelsRemoved && syncResult.labelsRemoved.length > 0) {
            this.result.actions.push(`Removed labels: ${syncResult.labelsRemoved.join(', ')}`);
          }
          if (syncResult.titleUpdated) {
            this.result.actions.push(`Updated PR #${prData.number} title to match labels`);
          }
          if (syncResult.syncPerformed) {
            this.result.actions.push(`Title-label sync: ${syncResult.reason}`);
          }
        } else if (this.context.eventName === 'workflow_run') {
          // Handle workflow_run events for fork compatibility
          const metadata = await this.loadMetadataFromArtifact();

          if (metadata && metadata.type === 'pull_request') {
            const { TitleLabelSync } = require('./title-label-sync');

            // Check if the original event action supports sync
            const shouldSync = ['edited', 'labeled', 'unlabeled'].includes(metadata.event_action);
            if (!shouldSync) {
              logger.log(`ℹ️ Event action ${metadata.event_action} does not require title-label sync`);
              return;
            }

            // Skip draft PRs
            if (metadata.draft) {
              logger.log(`ℹ️ PR #${metadata.number} is draft, skipping title-label sync`);
              return;
            }

            const titleLabelSync = new TitleLabelSync(this.context, this.client, this.config);
            const syncResult = await titleLabelSync.execute(metadata);

            // Merge results
            if (syncResult.labelsAdded && syncResult.labelsAdded.length > 0) {
              this.result.labelsAdded.push(...syncResult.labelsAdded);
            }
            if (syncResult.labelsRemoved && syncResult.labelsRemoved.length > 0) {
              this.result.actions.push(`Removed labels: ${syncResult.labelsRemoved.join(', ')}`);
            }
            if (syncResult.titleUpdated) {
              this.result.actions.push(`Updated PR #${metadata.number} title to match labels`);
            }
            if (syncResult.syncPerformed) {
              this.result.actions.push(`Title-label sync: ${syncResult.reason}`);
            }
          }
        }
      } catch (error) {
        logger.error(`❌ Title-label sync failed: ${error.message}`);
        throw error;
      }
    });
  }

  /**
   * Handle issues.opened events
   */
  async handleIssueEvent() {
    if (this.context.payload.action !== 'opened') {
      logger.info(`ℹ️ Issue action ${this.context.payload.action} not handled`);
      return;
    }

    const issueNumber = this.context.issue.number;
    logger.log(`🎯 Processing new issue #${issueNumber}`);

    try {
      const result = await this.client.addLabels(issueNumber, ['triage']);
      
      if (result.added.length > 0) {
        this.result.labelsAdded.push(...result.added);
        this.result.actions.push(`Added triage label to issue #${issueNumber}`);
      }
      
      this.result.summary = `Successfully processed issue #${issueNumber}`;
      
    } catch (error) {
      this.result.summary = `Failed to process issue #${issueNumber}: ${error.message}`;
      throw error;
    }
  }

  /**
   * Handle workflow_run events (for fork compatibility)
   */
  async handleWorkflowRunEvent() {
    const workflowRun = this.context.payload.workflow_run;
    
    if (workflowRun.conclusion !== 'success') {
      console.log(`ℹ️ Workflow run conclusion was ${workflowRun.conclusion}, skipping`);
      return;
    }

    logger.log(`🔄 Processing workflow_run from: ${workflowRun.name}`);
    
    // Try to load metadata from artifact first (new fork-compatible pattern)
    const metadata = await this.loadMetadataFromArtifact();
    
    if (metadata) {
      logger.log(`📦 Using metadata from artifact: ${metadata.type} #${metadata.number}`);
      
      if (metadata.type === 'pull_request') {
        await this.handlePullRequestEvent(metadata);
      } else if (metadata.type === 'issue') {
        await this.handleIssueEventFromMetadata(metadata);
      }
      return;
    }
    
    // Fallback to old pattern: find PR by branch
    logger.log('⚠️ No artifact metadata found, falling back to branch-based PR lookup');
    
    const headBranch = workflowRun.head_branch;
    console.log(`📋 Head branch: ${headBranch}`);

    if (!headBranch || headBranch === 'main') {
      console.log('ℹ️ Workflow was not triggered by a PR branch, skipping');
      return;
    }

    // Find the PR associated with this branch
    const pr = await this.client.findPRByBranch(headBranch);
    
    if (!pr) {
      console.log(`ℹ️ No PR found for branch ${headBranch}`);
      return;
    }

    console.log(`🎯 Found PR #${pr.number}: ${pr.title} (state: ${pr.state})`);

    // Skip if PR is closed
    if (pr.state === 'closed') {
      console.log(`ℹ️ PR #${pr.number} is closed, skipping labeling`);
      return;
    }

    await this.handlePullRequestEvent(pr);
  }

  /**
   * Sanitize JSON content by escaping special characters only within string field values
   */
  sanitizeJsonContent(content) {
    try {
      console.log('🔧 Starting field-aware JSON sanitization...');
      
      // First, try to parse as-is
      try {
        JSON.parse(content);
        console.log('✅ JSON is already valid, no sanitization needed');
        return content;
      } catch (parseError) {
        console.log(`📋 JSON parse failed (${parseError.message}), attempting sanitization`);
      }
      
      let result = content;
      
      // REMOVED: Global escaping that breaks JSON structure
      // We only escape content within specific string fields
      
      console.log('🔧 Using simple field-specific replacement...');
      
      // Simple approach: Use indexOf to find the exact positions and replace content within
      
      // Process title field
      const titleStartPattern = '"title": "';
      const titleStart = result.indexOf(titleStartPattern);
      if (titleStart !== -1) {
        const titleValueStart = titleStart + titleStartPattern.length;
        
        // Find the closing quote by looking for quote followed by comma/brace
        let titleEnd = -1;
        for (let i = titleValueStart; i < result.length; i++) {
          if (result[i] === '"' && result[i-1] !== '\\') {
            // Check if followed by comma or brace
            const afterQuote = result.substring(i + 1, i + 5);
            if (afterQuote.match(/^\s*[,}]/)) {
              titleEnd = i;
              break;
            }
          }
        }
        
        if (titleEnd !== -1) {
          const titleValue = result.substring(titleValueStart, titleEnd);
          console.log(`🎯 Processing title: "${titleValue}"`);
          
          const escapedTitle = titleValue
            .replace(/\\/g, '\\\\')
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r')
            .replace(/\t/g, '\\t');
          
          result = result.substring(0, titleValueStart) + escapedTitle + result.substring(titleEnd);
          console.log(`✅ Escaped title field`);
        }
      }
      
      // Process body field (after title may have changed positions)
      const bodyStartPattern = '"body": "';
      const bodyStart = result.indexOf(bodyStartPattern);
      if (bodyStart !== -1) {
        const bodyValueStart = bodyStart + bodyStartPattern.length;
        
        // Find the REAL end by looking for the pattern of quote followed by comma/brace
        // Work backwards from potential end points
        let bodyEnd = -1;
        
        // Look for closing patterns in the JSON - comma followed by next field or closing brace
        const possibleEndings = [];
        
        // Find all possible ending positions (quotes followed by comma or brace)
        for (let i = bodyValueStart + 1; i < result.length; i++) {
          if (result[i] === '"' && result[i-1] !== '\\') {
            let j = i + 1;
            // Skip whitespace
            while (j < result.length && /\s/.test(result[j])) j++;
            
            if (j < result.length) {
              if (result[j] === ',') {
                // Check if next non-whitespace after comma looks like a JSON field
                let k = j + 1;
                while (k < result.length && /\s/.test(result[k])) k++;
                if (k < result.length && result[k] === '"') {
                  // Make sure this is actually a field name, not a string value
                  const nextColon = result.indexOf(':', k);
                  if (nextColon > k && nextColon < k + 50) {
                    possibleEndings.push(i);
                  }
                }
              } else if (result[j] === '}') {
                possibleEndings.push(i);
              }
            }
          }
        }
        
        // Choose the right ending - prefer the one that doesn't include nested objects
        if (possibleEndings.length > 0) {
          bodyEnd = possibleEndings[possibleEndings.length - 1]; // Start with last
          
          // Check if body content includes nested JSON structure (braces/brackets)
          
          // If the content has unbalanced braces or looks like it includes other JSON fields,
          // try earlier endings
          if (possibleEndings.length > 1) {
            for (let i = possibleEndings.length - 1; i >= 0; i--) {
              const candidateEnd = possibleEndings[i];
              const candidateBody = result.substring(bodyValueStart, candidateEnd);
              
              // Check if this candidate body looks like it contains JSON structure
              const afterCandidate = result.substring(candidateEnd);
              
              // If what comes after looks like a clean JSON field (starts with comma + field name),
              // this is likely the right ending
              if (afterCandidate.match(/^\s*,\s*"[a-zA-Z_][a-zA-Z0-9_]*"\s*:/)) {
                bodyEnd = candidateEnd;
                console.log(`🎯 Selected ending ${i+1}/${possibleEndings.length} based on clean JSON structure`);
                break;
              }
              
              // Also check if the candidate body doesn't contain nested objects
              const openBraces = (candidateBody.match(/\{/g) || []).length;
              const closeBraces = (candidateBody.match(/\}/g) || []).length;
              if (openBraces === 0 && closeBraces === 0) {
                // This body doesn't contain nested objects, probably safer
                bodyEnd = candidateEnd;
                console.log(`🎯 Selected ending ${i+1}/${possibleEndings.length} based on no nested objects`);
                break;
              }
            }
          }
          
          const bodyValue = result.substring(bodyValueStart, bodyEnd);
          console.log(`🎯 Processing body (${bodyValue.length} chars) - found ${possibleEndings.length} possible endings`);
          console.log(`📝 Body preview: ${bodyValue.substring(0, 100)}...`);
          console.log(`📝 Body ending: ...${bodyValue.substring(Math.max(0, bodyValue.length - 50))}`);
          
          const escapedBody = bodyValue
            .replace(/\\/g, '\\\\')
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r')
            .replace(/\t/g, '\\t');
          
          result = result.substring(0, bodyValueStart) + escapedBody + result.substring(bodyEnd);
          console.log(`✅ Escaped body field (${bodyValue.length} → ${escapedBody.length} chars)`);
        } else {
          console.log('⚠️ Could not find body field end - no valid ending patterns found');
        }
      }
      
      // Final attempt to parse
      try {
        JSON.parse(result);
        console.log('✅ Field-aware sanitization successful - JSON is now valid');
        return result;
      } catch (finalError) {
        console.log(`⚠️ Sanitization failed: ${finalError.message}`);
        console.log('📄 Sanitized content (first 500 chars):');
        console.log(result.substring(0, 500) + (result.length > 500 ? '...' : ''));
        console.log('📄 Falling back to original content');
        return content;
      }
      
    } catch (error) {
      console.log(`⚠️ Failed to sanitize JSON content: ${error.message}`);
      console.log(`📄 Error stack: ${error.stack}`);
      return content;
    }
  }

  /**
   * Validate metadata structure
   */
  validateMetadata(metadata) {
    if (!metadata || typeof metadata !== 'object') {
      return false;
    }

    // Check required fields exist
    const requiredFields = ['type', 'event_action'];
    for (const field of requiredFields) {
      if (!metadata.hasOwnProperty(field)) {
        console.log(`⚠️ Metadata missing required field: ${field}`);
        return false;
      }
    }

    // Validate type is one of expected values
    if (!['pull_request', 'issue', 'workflow_run'].includes(metadata.type)) {
      console.log(`⚠️ Invalid metadata type: ${metadata.type}`);
      return false;
    }

    // For PR and issue types, ensure we have author info
    if ((metadata.type === 'pull_request' || metadata.type === 'issue') && 
        (!metadata.author || !metadata.author.login)) {
      console.log(`⚠️ Metadata missing author information for ${metadata.type}`);
      return false;
    }

    return true;
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
      
      // Read metadata content
      const metadataContent = fs.readFileSync(metadataPath, 'utf8');
      console.log('🔍 Raw metadata content (first 200 chars):');
      console.log(metadataContent.substring(0, 200) + (metadataContent.length > 200 ? '...' : ''));
      
      let metadata;
      
      // First attempt: try standard JSON parsing
      try {
        metadata = JSON.parse(metadataContent);
        console.log('✅ Successfully parsed metadata on first attempt');
      } catch (firstError) {
        console.log(`⚠️ First JSON parse failed: ${firstError.message}`);
        console.log('🔧 Attempting to sanitize and retry...');
        
        // Second attempt: sanitize and try again
        const sanitizedContent = this.sanitizeJsonContent(metadataContent);
        
        if (sanitizedContent !== metadataContent) {
          console.log('🔍 Sanitized metadata content (first 200 chars):');
          console.log(sanitizedContent.substring(0, 200) + (sanitizedContent.length > 200 ? '...' : ''));
          
          try {
            metadata = JSON.parse(sanitizedContent);
            console.log('✅ Successfully parsed metadata after sanitization');
          } catch (secondError) {
            console.log(`❌ Second JSON parse failed: ${secondError.message}`);
            console.log('📄 Full raw content for debugging:');
            console.log('--- START METADATA ---');
            console.log(metadataContent);
            console.log('--- END METADATA ---');
            return null;
          }
        } else {
          console.log('❌ Sanitization did not change content, parsing failed');
          console.log('📄 Full raw content for debugging:');
          console.log('--- START METADATA ---');
          console.log(metadataContent);
          console.log('--- END METADATA ---');
          return null;
        }
      }
      
      // Decode base64 encoded fields if present
      if (metadata.encoding) {
        if (metadata.encoding.title === 'base64' && metadata.title_base64 !== undefined) {
          try {
            // Handle empty strings
            if (metadata.title_base64 === '') {
              metadata.title = '';
              console.log('✅ Decoded empty base64 title field');
            } else {
              // Validate base64 format before decoding
              if (!/^[A-Za-z0-9+/]*={0,2}$/.test(metadata.title_base64)) {
                console.log(`⚠️ Invalid base64 format in title field`);
              } else {
                metadata.title = Buffer.from(metadata.title_base64, 'base64').toString('utf8');
                console.log('✅ Decoded base64 title field');
              }
            }
          } catch (error) {
            console.log(`⚠️ Failed to decode base64 title: ${error.message}`);
          }
        }
        
        if (metadata.encoding.body === 'base64' && metadata.body_base64 !== undefined) {
          try {
            // Handle empty strings
            if (metadata.body_base64 === '') {
              metadata.body = '';
              console.log('✅ Decoded empty base64 body field');
            } else {
              // Validate base64 format before decoding
              if (!/^[A-Za-z0-9+/]*={0,2}$/.test(metadata.body_base64)) {
                console.log(`⚠️ Invalid base64 format in body field`);
              } else {
                metadata.body = Buffer.from(metadata.body_base64, 'base64').toString('utf8');
                console.log('✅ Decoded base64 body field');
              }
            }
          } catch (error) {
            console.log(`⚠️ Failed to decode base64 body: ${error.message}`);
          }
        }
      }
      
      // Validate metadata structure
      if (!this.validateMetadata(metadata)) {
        console.log('❌ Metadata validation failed');
        return null;
      }
      
      console.log(`📦 Loaded metadata: ${metadata.type} #${metadata.number} by ${metadata.author ? metadata.author.login : 'unknown'}`);
      
      return metadata;
      
    } catch (error) {
      console.log(`⚠️ Failed to load artifact metadata: ${error.message}`);
      return null;
    }
  }

  /**
   * Handle issue event from metadata
   */
  async handleIssueEventFromMetadata(metadata) {
    // Convert metadata to issue-like object for compatibility
    const issueData = {
      number: metadata.number,
      title: metadata.title,
      body: metadata.body,
      state: metadata.state,
      labels: metadata.labels,
      user: metadata.author
    };
    
    await this.addTriageLabel(issueData.number, 'issue');
  }

  /**
   * Handle pull request events with smart labeling logic
   */
  async handlePullRequestEvent(prData) {
    const prNumber = prData.number;
    
    // Skip draft PRs
    if (prData.draft) {
      console.log(`ℹ️ PR #${prNumber} is draft, skipping labeling`);
      return;
    }

    // Add 10-second delay as requested in original workflow
    console.log('⏳ Sleeping for 10 seconds...');
    if (!this.config.isDryRun()) {
      await new Promise(resolve => setTimeout(resolve, 10000));
    }

    try {
      // Get current labels on the PR
      const currentLabels = await this.client.getLabels(prNumber);
      console.log(`📋 Current labels on PR #${prNumber}: ${currentLabels.join(', ')}`);

      // Check label conditions
      const labelChecks = await this.client.hasLabels(prNumber, [
        'release-*',
        'backport-*', 
        'triage',
        'ready for review'
      ]);

      const hasReleaseLabel = labelChecks['release-*'];
      const hasBackportLabel = labelChecks['backport-*'];
      const hasTriageLabel = labelChecks['triage'];
      const hasReadyForReviewLabel = labelChecks['ready for review'];

      // Also check for release content in YAML (for cases where the release label hasn't been added yet)
      const yamlContent = this.config.parseYamlFromText(prData.body || '');
      const hasReleaseYaml = yamlContent && this.config.parseYamlValue(yamlContent, 'release');
      const hasBackportYaml = yamlContent && this.config.parseYamlValue(yamlContent, 'backport');

      // Check if label automation posted validation error comments (indicating invalid YAML)
      const hasValidationErrors = this.result.actions.some(action => 
        action.includes('Posted validation error comment') || 
        action.includes('validation error comment')
      );

      console.log(`🔍 Label analysis:`);
      console.log(`  - Has release label: ${hasReleaseLabel}`);
      console.log(`  - Has backport label: ${hasBackportLabel}`);
      console.log(`  - Has triage label: ${hasTriageLabel}`);
      console.log(`  - Has ready for review label: ${hasReadyForReviewLabel}`);
      console.log(`  - Has release YAML: ${!!hasReleaseYaml}`);
      console.log(`  - Has backport YAML: ${!!hasBackportYaml}`);
      console.log(`  - Has validation errors: ${hasValidationErrors}`);
      console.log(`  - Is draft: ${prData.draft}`);

      // Main logic: 
      // 1. If YAML has validation errors, always add triage label (needs manual review)
      // 2. If PR has valid release label/YAML and not draft, add ready for review
      // 3. Otherwise add triage
      if (hasValidationErrors) {
        await this.handleTriageLabel(prNumber, hasTriageLabel, false);
        console.log(`🏷️ Added triage label due to YAML validation errors`);
      } else if ((hasReleaseLabel || hasReleaseYaml) && !prData.draft) {
        await this.handleReadyForReviewLabel(prNumber, hasReadyForReviewLabel);
      } else if (!hasBackportLabel && !hasBackportYaml) {
        await this.handleTriageLabel(prNumber, hasTriageLabel, hasReleaseLabel || !!hasReleaseYaml);
      } else {
        console.log(`ℹ️ PR #${prNumber} has backport label/YAML, skipping automatic labeling`);
      }

    } catch (error) {
      this.result.summary = `Failed to process PR #${prNumber}: ${error.message}`;
      throw error;
    }
  }

  /**
   * Handle adding ready-for-review label
   */
  async handleReadyForReviewLabel(prNumber, hasLabel) {
    if (!hasLabel) {
      const result = await this.client.addLabels(prNumber, ['ready for review']);
      
      if (result.added.length > 0) {
        this.result.labelsAdded.push(...result.added);
        this.result.actions.push(`Added "ready for review" label to PR #${prNumber} (has release label, not draft)`);
      }
    } else {
      console.log(`ℹ️ PR #${prNumber} already has "ready for review" label`);
    }
  }

  /**
   * Handle adding triage label
   */
  async handleTriageLabel(prNumber, hasLabel, hasReleaseLabel) {
    if (!hasLabel) {
      const result = await this.client.addLabels(prNumber, ['triage']);
      
      if (result.added.length > 0) {
        this.result.labelsAdded.push(...result.added);
        
        const reason = !hasReleaseLabel ? 
          'no release/backport label' : 
          'is draft';
        this.result.actions.push(`Added triage label to PR #${prNumber} (${reason})`);
      }
    } else {
      console.log(`ℹ️ PR #${prNumber} already has triage label`);
    }
  }

  /**
   * Handle triage protection (re-add if removed without release/backport labels)
   * This would be called for labeled/unlabeled events
   */
  async handleTriageProtection(issueNumber, eventType = 'PR') {
    console.log(`🛡️ Triage label removed from ${eventType} #${issueNumber}, checking for protection conditions`);

    try {
      const labelChecks = await this.client.hasLabels(issueNumber, ['release-*', 'backport-*']);
      const hasReleaseLabel = labelChecks['release-*'];
      const hasBackportLabel = labelChecks['backport-*'];

      // If no release or backport labels, re-add triage label
      if (!hasReleaseLabel && !hasBackportLabel) {
        const result = await this.client.addLabels(issueNumber, ['triage']);
        
        if (result.added.length > 0) {
          this.result.labelsAdded.push(...result.added);
          this.result.actions.push(`Re-added triage label to ${eventType} #${issueNumber} (no release/backport labels found)`);
        }
        
        console.log(`✅ Re-added triage label to ${eventType} #${issueNumber} (no release/backport labels found)`);
      } else {
        console.log(`ℹ️ Triage label removal allowed for ${eventType} #${issueNumber} (release/backport labels present)`);
      }
    } catch (error) {
      this.result.summary = `Failed to handle triage protection for ${eventType} #${issueNumber}: ${error.message}`;
      throw error;
    }
  }
}

/**
 * Main execute function for the action
 */
async function execute(context, github, options = {}) {
  const automation = new RepositoryAutomation(context, github, options);
  const result = await automation.execute();
  
  // Generate summary
  if (result.actions.length > 0) {
    result.summary = `Completed ${result.actions.length} action(s): ${result.actions.join('; ')}`;
  } else {
    result.summary = result.summary || 'No actions needed';
  }
  
  console.log(`✅ Repository automation completed successfully`);
  console.log(`📋 Features enabled: ${result.featuresEnabled.join(', ')}`);
  console.log(`📋 Summary: ${result.summary}`);
  
  return result;
}

module.exports = { RepositoryAutomation, execute };