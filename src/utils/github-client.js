/**
 * GitHub API Client Utilities
 * Centralized GitHub API interaction layer with error handling
 */

class GitHubClient {
  constructor(github, config) {
    this.github = github;
    this.config = config;
    this.owner = config.getRepository().owner;
    this.repo = config.getRepository().repo;
  }

  /**
   * Add labels to an issue or PR
   */
  async addLabels(issueNumber, labels) {
    if (this.config.isDryRun()) {
      console.log(`🧪 DRY RUN: Would add labels [${labels.join(', ')}] to #${issueNumber}`);
      return { added: labels, skipped: false };
    }

    try {
      await this.github.rest.issues.addLabels({
        owner: this.owner,
        repo: this.repo,
        issue_number: issueNumber,
        labels: labels
      });
      
      console.log(`✅ Successfully added labels [${labels.join(', ')}] to #${issueNumber}`);
      return { added: labels, skipped: false };
      
    } catch (error) {
      return this._handleLabelError(error, issueNumber, labels, 'add');
    }
  }

  /**
   * Get labels on an issue or PR
   */
  async getLabels(issueNumber) {
    try {
      const { data: labels } = await this.github.rest.issues.listLabelsOnIssue({
        owner: this.owner,
        repo: this.repo,
        issue_number: issueNumber
      });
      
      return labels.map(label => label.name);
      
    } catch (error) {
      console.error(`❌ Error getting labels for #${issueNumber}:`, error.message);
      throw error;
    }
  }

  /**
   * Check if specific labels exist on an issue or PR
   */
  async hasLabels(issueNumber, labelNames) {
    const currentLabels = await this.getLabels(issueNumber);
    const result = {};
    
    labelNames.forEach(labelName => {
      if (labelName.endsWith('*')) {
        // Wildcard matching (e.g., "release *")
        const prefix = labelName.slice(0, -1);
        result[labelName] = currentLabels.some(label => label.startsWith(prefix));
      } else {
        // Exact matching
        result[labelName] = currentLabels.includes(labelName);
      }
    });
    
    return result;
  }

  /**
   * Get PR details
   */
  async getPR(prNumber) {
    try {
      const { data: pr } = await this.github.rest.pulls.get({
        owner: this.owner,
        repo: this.repo,
        pull_number: prNumber
      });
      
      return pr;
      
    } catch (error) {
      console.error(`❌ Error getting PR #${prNumber}:`, error.message);
      throw error;
    }
  }

  /**
   * Find PR by branch name
   */
  async findPRByBranch(branchName) {
    try {
      const { data: prs } = await this.github.rest.pulls.list({
        owner: this.owner,
        repo: this.repo,
        head: `${this.owner}:${branchName}`,
        state: 'all',
        sort: 'updated',
        direction: 'desc'
      });

      return prs.length > 0 ? prs[0] : null;
      
    } catch (error) {
      console.error(`❌ Error finding PR for branch ${branchName}:`, error.message);
      throw error;
    }
  }

  /**
   * Handle label-related errors with specific error messages
   */
  _handleLabelError(error, issueNumber, labels, action) {
    if (error.status === 403) {
      const errorMsg = `❌ Permission denied: Unable to ${action} labels [${labels.join(', ')}] to #${issueNumber}. Repository administrators should add a CUSTOM_GITHUB_TOKEN secret with appropriate permissions.`;
      console.error(errorMsg);
      throw new Error(errorMsg);
      
    } else if (error.status === 422) {
      // Check if labels already exist or if they don't exist in the repository
      return this._handle422Error(error, issueNumber, labels, action);
      
    } else {
      const errorMsg = `❌ Unexpected error ${action}ing labels [${labels.join(', ')}] to #${issueNumber}: ${error.message}`;
      console.error(errorMsg);
      throw new Error(errorMsg);
    }
  }

  /**
   * Handle 422 errors (label already exists or label doesn't exist in repo)
   */
  async _handle422Error(error, issueNumber, labels, action) {
    try {
      const currentLabels = await this.getLabels(issueNumber);
      const alreadyHasLabels = labels.filter(label => currentLabels.includes(label));
      
      if (alreadyHasLabels.length > 0) {
        console.log(`ℹ️ Labels [${alreadyHasLabels.join(', ')}] already exist on #${issueNumber} - this is expected behavior`);
        return { added: [], skipped: alreadyHasLabels };
      } else {
        const errorMsg = `❌ Failed to ${action} labels [${labels.join(', ')}] to #${issueNumber}: One or more labels don't exist in the repository.`;
        console.error(errorMsg);
        throw new Error(errorMsg);
      }
      
    } catch (listError) {
      const errorMsg = `❌ Error checking existing labels on #${issueNumber}: ${listError.message}`;
      console.error(errorMsg);
      throw new Error(errorMsg);
    }
  }
}

module.exports = { GitHubClient };