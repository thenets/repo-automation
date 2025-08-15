/**
 * Triage Management Module
 * Extracted and modularized logic from keeper-triage.yml
 * 
 * Handles:
 * - Auto-add triage labels to new issues
 * - Smart PR labeling (triage vs ready-for-review based on release labels)
 * - Triage label protection (re-add if removed without release/backport labels)
 * - Fork compatibility through workflow_run events
 */

const { ConfigManager } = require('./utils/config');
const { GitHubClient } = require('./utils/github-client');

class TriageManager {
  constructor(context, github, options = {}) {
    this.context = context;
    this.github = github;
    this.config = new ConfigManager(context, options);
    this.client = new GitHubClient(github, this.config);
    this.result = {
      labelsAdded: [],
      summary: '',
      actions: []
    };
  }

  /**
   * Main execution function
   */
  async execute() {
    try {
      this.config.validate();
      this.config.logConfig();

      console.log(`🔄 Starting triage automation for event: ${this.context.eventName}`);

      // Handle different event types
      if (this.context.eventName === 'issues') {
        await this.handleIssueEvent();
      } else if (this.context.eventName === 'workflow_run') {
        await this.handleWorkflowRunEvent();
      } else {
        console.log(`ℹ️ Event type ${this.context.eventName} not handled by triage automation`);
        this.result.summary = `Event type ${this.context.eventName} not handled`;
      }

      return this.result;

    } catch (error) {
      console.error('❌ Triage automation failed:', error.message);
      this.result.summary = `Failed: ${error.message}`;
      throw error;
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
        'release *',
        'backport *', 
        'triage',
        'ready for review'
      ]);

      const hasReleaseLabel = labelChecks['release *'];
      const hasBackportLabel = labelChecks['backport *'];
      const hasTriageLabel = labelChecks['triage'];
      const hasReadyForReviewLabel = labelChecks['ready for review'];

      console.log(`🔍 Label analysis:`);
      console.log(`  - Has release label: ${hasReleaseLabel}`);
      console.log(`  - Has backport label: ${hasBackportLabel}`);
      console.log(`  - Has triage label: ${hasTriageLabel}`);
      console.log(`  - Has ready for review label: ${hasReadyForReviewLabel}`);
      console.log(`  - Is draft: ${prData.draft}`);

      // Main logic: If PR has release label and not draft, add ready for review; otherwise add triage
      if (hasReleaseLabel && !prData.draft) {
        await this.handleReadyForReviewLabel(prNumber, hasReadyForReviewLabel);
      } else if (!hasBackportLabel) {
        await this.handleTriageLabel(prNumber, hasTriageLabel, hasReleaseLabel);
      } else {
        console.log(`ℹ️ PR #${prNumber} has backport label, skipping automatic labeling`);
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
      const labelChecks = await this.client.hasLabels(issueNumber, ['release *', 'backport *']);
      const hasReleaseLabel = labelChecks['release *'];
      const hasBackportLabel = labelChecks['backport *'];

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
  const manager = new TriageManager(context, github, options);
  const result = await manager.execute();
  
  // Generate summary
  if (result.actions.length > 0) {
    result.summary = `Completed ${result.actions.length} action(s): ${result.actions.join('; ')}`;
  } else {
    result.summary = result.summary || 'No actions needed';
  }
  
  return result;
}

module.exports = { TriageManager, execute };