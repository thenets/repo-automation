/**
 * Title-Label Sync Feature
 * Bi-directional synchronization between PR titles and labels
 * Supports POC, WIP, and HOLD status indicators
 *
 * Title is the source of truth - title changes always override labels
 */

const { logger } = require('./utils/logger');
const {
  getStatusLabels,
  extractStatusIndicators,
  syncTitleToStatuses
} = require('./utils/title-parser');

class TitleLabelSync {
  constructor(context, githubClient, config) {
    this.context = context;
    this.githubClient = githubClient;
    this.config = config;
    this.result = {
      titleUpdated: false,
      labelsAdded: [],
      labelsRemoved: [],
      syncPerformed: false,
      reason: null
    };
  }

  /**
   * Main execution method - determines sync direction and performs sync
   */
  async execute(prData) {
    const prNumber = prData.number;
    const currentTitle = prData.title;
    const action = this.context.payload.action;

    logger.log(`\n🔄 Title-Label Sync: Analyzing PR #${prNumber}`);
    logger.log(`   Action: ${action}`);
    logger.log(`   Title: "${currentTitle}"`);

    try {
      // Get current labels
      const currentLabels = await this.githubClient.getLabels(prNumber);
      const statusLabels = getStatusLabels();
      const currentStatusLabels = currentLabels.filter(label =>
        statusLabels.includes(label.toLowerCase())
      );

      logger.log(`   Current status labels: [${currentStatusLabels.join(', ')}]`);

      // Determine sync direction based on event action
      if (action === 'edited') {
        // Title was edited - sync labels to match title (title is source of truth)
        await this.syncTitleToLabels(prNumber, currentTitle, currentStatusLabels);
      } else if (action === 'labeled' || action === 'unlabeled') {
        // Labels were changed - sync title to match labels, then title wins
        await this.syncLabelsToTitle(prNumber, currentTitle, currentStatusLabels);
      }

      return this.result;

    } catch (error) {
      logger.error(`❌ Title-Label Sync failed for PR #${prNumber}: ${error.message}`);
      throw error;
    }
  }

  /**
   * Sync labels to match the title (title is source of truth)
   * Called when PR title is edited
   */
  async syncTitleToLabels(prNumber, title, currentStatusLabels) {
    logger.log(`\n📝 Syncing labels to match title (title is source of truth)`);

    // Extract status indicators from title
    const titleStatuses = extractStatusIndicators(title);
    logger.log(`   Status indicators in title: [${titleStatuses.join(', ')}]`);

    // Determine what needs to change
    const labelsToAdd = titleStatuses.filter(status =>
      !currentStatusLabels.includes(status)
    );
    const labelsToRemove = currentStatusLabels.filter(label =>
      !titleStatuses.includes(label.toLowerCase())
    );

    // Apply label changes
    if (labelsToAdd.length > 0) {
      logger.log(`   Adding labels: [${labelsToAdd.join(', ')}]`);
      await this.githubClient.addLabels(prNumber, labelsToAdd);
      this.result.labelsAdded = labelsToAdd;
      this.result.syncPerformed = true;
    }

    if (labelsToRemove.length > 0) {
      logger.log(`   Removing labels: [${labelsToRemove.join(', ')}]`);
      await this.githubClient.removeLabels(prNumber, labelsToRemove);
      this.result.labelsRemoved = labelsToRemove;
      this.result.syncPerformed = true;
    }

    if (labelsToAdd.length === 0 && labelsToRemove.length === 0) {
      logger.log(`   ✅ Labels already in sync with title`);
      this.result.reason = 'Labels already match title';
    } else {
      this.result.reason = 'Title updated, labels synced';
    }
  }

  /**
   * Sync title to match labels, then enforce title as source of truth
   * Called when labels are added/removed
   *
   * Note: This initially syncs title to labels, but if the user then edits
   * the title, the title will win (handled by the 'edited' event)
   */
  async syncLabelsToTitle(prNumber, currentTitle, currentStatusLabels) {
    logger.log(`\n🏷️  Syncing title to match labels`);
    logger.log(`   Current status labels: [${currentStatusLabels.join(', ')}]`);

    // Normalize labels to lowercase
    const normalizedLabels = currentStatusLabels.map(label => label.toLowerCase());

    // Sync title to match labels
    const newTitle = syncTitleToStatuses(currentTitle, normalizedLabels);

    // Check if title needs updating
    if (newTitle !== currentTitle) {
      logger.log(`   Updating title from: "${currentTitle}"`);
      logger.log(`                    to: "${newTitle}"`);

      await this.githubClient.updatePRTitle(prNumber, newTitle);
      this.result.titleUpdated = true;
      this.result.syncPerformed = true;
      this.result.reason = 'Labels changed, title synced';
    } else {
      logger.log(`   ✅ Title already in sync with labels`);
      this.result.reason = 'Title already matches labels';
    }
  }

  /**
   * Check if this feature should be enabled
   */
  static isEnabled(config) {
    // Check if feature is explicitly disabled
    const enabledInput = config.getInput('enable-title-label-sync');

    // Default to true (enabled by default)
    if (enabledInput === undefined || enabledInput === null || enabledInput === '') {
      return true;
    }

    // Parse boolean value
    const enabled = enabledInput === 'true' || enabledInput === true;
    logger.log(`🔄 Title-Label Sync feature ${enabled ? 'enabled' : 'disabled'}`);

    return enabled;
  }

  /**
   * Check if this event should trigger sync
   */
  static shouldSync(context) {
    const eventName = context.eventName;
    const action = context.payload.action;

    // Only sync on pull request events
    if (eventName !== 'pull_request') {
      return false;
    }

    // Only sync on specific actions
    const syncActions = ['edited', 'labeled', 'unlabeled'];
    if (!syncActions.includes(action)) {
      return false;
    }

    return true;
  }
}

module.exports = { TitleLabelSync };
