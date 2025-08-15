/**
 * Configuration Management Utilities
 * Handles dynamic repository detection and configuration parsing
 */

class ConfigManager {
  constructor(context, options = {}) {
    this.context = context;
    this.options = options;
    this.owner = context.repo.owner;
    this.repo = context.repo.repo;
    this.repository = `${this.owner}/${this.repo}`;
  }

  /**
   * Get repository information
   */
  getRepository() {
    return {
      owner: this.owner,
      repo: this.repo,
      fullName: this.repository
    };
  }

  /**
   * Check if running in dry-run mode
   */
  isDryRun() {
    return this.options.dryRun === true;
  }

  /**
   * Get the GitHub token to use
   */
  getGithubToken() {
    return this.options.githubToken;
  }

  /**
   * Log configuration information
   */
  logConfig() {
    console.log(`📋 Configuration:`);
    console.log(`  - Repository: ${this.repository}`);
    console.log(`  - Dry Run: ${this.isDryRun()}`);
    console.log(`  - Token: ${this.getGithubToken() ? '[CONFIGURED]' : '[NOT SET]'}`);
  }

  /**
   * Validate that required configuration is present
   */
  validate() {
    if (!this.owner || !this.repo) {
      throw new Error('Repository owner and name are required');
    }
    
    if (!this.getGithubToken()) {
      throw new Error('GitHub token is required');
    }

    return true;
  }
}

module.exports = { ConfigManager };