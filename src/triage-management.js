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
      staleDetection: !!(options.staleDays) || this.context.eventName === 'schedule'
    };
    
    // Log enabled features
    const enabledFeatures = Object.keys(features).filter(f => features[f]);
    console.log(`🎯 Enabled features: ${enabledFeatures.join(', ')}`);
    
    return features;
  }

  /**
   * Main execution function - orchestrates all enabled features
   */
  async execute() {
    try {
      this.config.validate();
      this.config.logConfig();

      console.log(`🔄 Starting repository automation for event: ${this.context.eventName}`);
      
      // Store enabled features in result
      this.result.featuresEnabled = Object.keys(this.features).filter(f => this.features[f]);

      // Run optional features first to check for validation errors
      if (this.features.releaseLabeling || this.features.backportLabeling || this.features.featureBranch) {
        await this.executeLabelAutomation();
      }
      
      // Run core triage automation after label automation
      await this.executeTriageAutomation();
      
      if (this.features.staleDetection) {
        await this.executeStaleDetection();
      }

      return this.result;

    } catch (error) {
      console.error('❌ Repository automation failed:', error.message);
      this.result.summary = `Failed: ${error.message}`;
      throw error;
    }
  }

  /**
   * Execute core triage automation (always runs)
   */
  async executeTriageAutomation() {
    console.log('🏷️ Executing core triage automation...');
    
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
      console.log(`ℹ️ Event type ${this.context.eventName} not handled by triage automation`);
    }
  }

  /**
   * Execute label automation features (release/backport/feature-branch)
   */
  async executeLabelAutomation() {
    console.log('🔖 Executing label automation...');
    
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
        console.log('ℹ️ Label automation module not yet implemented, skipping...');
      } else {
        throw error;
      }
    }
  }

  /**
   * Execute stale detection feature
   */
  async executeStaleDetection() {
    console.log('⏰ Executing stale detection...');
    
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
        console.log('ℹ️ Stale detection module not yet implemented, skipping...');
      } else {
        throw error;
      }
    }
  }

  /**
   * Handle issues.opened events
   */
  async handleIssueEvent() {
    if (this.context.payload.action !== 'opened') {
      console.log(`ℹ️ Issue action ${this.context.payload.action} not handled`);
      return;
    }

    const issueNumber = this.context.issue.number;
    console.log(`🎯 Processing new issue #${issueNumber}`);

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

    console.log(`🔄 Processing workflow_run from: ${workflowRun.name}`);
    
    // Try to load metadata from artifact first (new fork-compatible pattern)
    const metadata = await this.loadMetadataFromArtifact();
    
    if (metadata) {
      console.log(`📦 Using metadata from artifact: ${metadata.type} #${metadata.number}`);
      
      if (metadata.type === 'pull_request') {
        await this.handlePullRequestEvent(metadata);
      } else if (metadata.type === 'issue') {
        await this.handleIssueEventFromMetadata(metadata);
      }
      return;
    }
    
    // Fallback to old pattern: find PR by branch
    console.log('⚠️ No artifact metadata found, falling back to branch-based PR lookup');
    
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
      
      console.log('🔧 Applying targeted field escaping...');
      
      // Find and escape title field content using precise string parsing
      const titleStart = result.indexOf('"title": "');
      if (titleStart !== -1) {
        console.log('🎯 Found title field, attempting precise parsing');
        const valueStart = titleStart + 10; // Length of '"title": "'
        
        // Find the end by looking for an unescaped quote followed by comma/brace
        let pos = valueStart;
        let escaped = false;
        let titleEnd = -1;
        
        while (pos < result.length) {
          const char = result[pos];
          
          if (escaped) {
            escaped = false;
          } else if (char === '\\') {
            escaped = true;
          } else if (char === '"') {
            // Look ahead to see if this quote ends the field
            const nextPos = pos + 1;
            const afterQuote = result.substring(nextPos, nextPos + 10);
            if (afterQuote.match(/^\s*[,}]/)) {
              titleEnd = pos;
              console.log(`🎯 Found title end at position ${pos}`);
              break;
            }
          }
          pos++;
        }
        
        if (titleEnd !== -1) {
          const titleValue = result.substring(valueStart, titleEnd);
          console.log(`📝 Title content: "${titleValue}"`);
          
          if (titleValue.includes('\n') || titleValue.includes('\t') || titleValue.includes('"') || titleValue.includes('\\')) {
            console.log('🎯 Escaping title field content');
            const escapedTitleValue = titleValue
              .replace(/\\/g, '\\\\')
              .replace(/"/g, '\\"')
              .replace(/\n/g, '\\n')
              .replace(/\r/g, '\\r')
              .replace(/\t/g, '\\t');
            
            result = result.substring(0, valueStart) + escapedTitleValue + result.substring(titleEnd);
            console.log(`✅ Escaped title field content: "${escapedTitleValue}"`);
          }
        }
      }
      
      // Find body field and escape its content using improved parsing
      const bodyStart = result.indexOf('"body": "');
      if (bodyStart !== -1) {
        console.log('🎯 Found body field, attempting precise parsing');
        const valueStart = bodyStart + 9; // Length of '"body": "'
        
        // Find the end by looking for an unescaped quote followed by comma/brace
        let pos = valueStart;
        let escaped = false;
        let bodyEnd = -1;
        
        while (pos < result.length) {
          const char = result[pos];
          
          if (escaped) {
            escaped = false;
          } else if (char === '\\') {
            escaped = true;
          } else if (char === '"') {
            // Look ahead to see if this quote ends the field
            const nextPos = pos + 1;
            const afterQuote = result.substring(nextPos, nextPos + 10);
            if (afterQuote.match(/^\s*[,}]/)) {
              bodyEnd = pos;
              console.log(`🎯 Found body end at position ${pos}`);
              break;
            }
          }
          pos++;
        }
        
        if (bodyEnd !== -1) {
          const bodyValue = result.substring(valueStart, bodyEnd);
          console.log(`📝 Body content length: ${bodyValue.length} chars`);
          console.log(`📝 First 100 chars: ${bodyValue.substring(0, 100)}...`);
          
          if (bodyValue.includes('\n') || bodyValue.includes('\t') || bodyValue.includes('"') || bodyValue.includes('\\')) {
            const escapedBodyValue = bodyValue
              .replace(/\\/g, '\\\\')
              .replace(/"/g, '\\"')
              .replace(/\n/g, '\\n')
              .replace(/\r/g, '\\r')
              .replace(/\t/g, '\\t');
            
            result = result.substring(0, valueStart) + escapedBodyValue + result.substring(bodyEnd);
            console.log('✅ Escaped body field content');
            console.log(`📝 Escaped length: ${escapedBodyValue.length} chars`);
          } else {
            console.log('ℹ️ Body field needs no escaping');
          }
        } else {
          console.log('⚠️ Could not find body field end');
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