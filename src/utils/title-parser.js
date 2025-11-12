/**
 * Title Parser Utilities
 * Parse and manage status indicators in PR titles
 * Supports POC, WIP, and HOLD status indicators in brackets
 */

const { logger } = require('./logger');

/**
 * Get the list of supported status labels
 * @returns {string[]} Array of lowercase status labels
 */
function getStatusLabels() {
  return ['poc', 'wip', 'hold'];
}

/**
 * Extract all status indicators from a PR title (case-insensitive)
 * Matches [POC], [WIP], [HOLD] anywhere in the title
 * @param {string} title - The PR title to parse
 * @returns {string[]} Array of lowercase status indicators found
 */
function extractStatusIndicators(title) {
  if (!title || typeof title !== 'string') {
    return [];
  }

  const statusLabels = getStatusLabels();
  const found = [];

  // Create regex pattern that matches any status label in brackets (case-insensitive)
  // Matches [POC], [WIP], [HOLD] anywhere in the title
  const pattern = /\[([^\]]+)\]/gi;
  const matches = title.matchAll(pattern);

  for (const match of matches) {
    const content = match[1].toLowerCase().trim();
    if (statusLabels.includes(content)) {
      // Avoid duplicates
      if (!found.includes(content)) {
        found.push(content);
      }
    }
  }

  logger.log(`📝 Found status indicators in title: [${found.join(', ')}]`);
  return found;
}

/**
 * Check if a title contains a specific status indicator (case-insensitive)
 * @param {string} title - The PR title to check
 * @param {string} status - The status to look for (poc, wip, or hold)
 * @returns {boolean} True if the status is present in the title
 */
function hasStatusIndicator(title, status) {
  if (!title || typeof title !== 'string') {
    return false;
  }

  const normalizedStatus = status.toLowerCase().trim();
  if (!getStatusLabels().includes(normalizedStatus)) {
    return false;
  }

  // Case-insensitive search for [STATUS] in title
  const pattern = new RegExp(`\\[${normalizedStatus}\\]`, 'gi');
  return pattern.test(title);
}

/**
 * Add status indicators to a title if not already present
 * Adds brackets at the beginning of the title
 * @param {string} title - The original title
 * @param {string[]} statuses - Array of status indicators to add
 * @returns {string} Updated title with status indicators
 */
function addStatusIndicators(title, statuses) {
  if (!title || typeof title !== 'string') {
    return title;
  }

  if (!statuses || statuses.length === 0) {
    return title;
  }

  let updatedTitle = title;
  const statusLabels = getStatusLabels();

  // Filter valid statuses and avoid duplicates
  const validStatuses = statuses
    .map(s => s.toLowerCase().trim())
    .filter(s => statusLabels.includes(s))
    .filter(s => !hasStatusIndicator(updatedTitle, s));

  if (validStatuses.length === 0) {
    logger.log(`ℹ️ No new status indicators to add to title`);
    return title;
  }

  // Add status indicators at the beginning
  const prefix = validStatuses.map(s => `[${s.toUpperCase()}]`).join(' ');
  updatedTitle = `${prefix} ${updatedTitle}`;

  logger.log(`✅ Added status indicators to title: ${prefix}`);
  return updatedTitle;
}

/**
 * Remove status indicators from a title
 * @param {string} title - The original title
 * @param {string[]} statuses - Array of status indicators to remove
 * @returns {string} Updated title without specified status indicators
 */
function removeStatusIndicators(title, statuses) {
  if (!title || typeof title !== 'string') {
    return title;
  }

  if (!statuses || statuses.length === 0) {
    return title;
  }

  let updatedTitle = title;
  const statusLabels = getStatusLabels();

  // Filter valid statuses
  const validStatuses = statuses
    .map(s => s.toLowerCase().trim())
    .filter(s => statusLabels.includes(s));

  if (validStatuses.length === 0) {
    return title;
  }

  // Remove each status indicator (case-insensitive)
  for (const status of validStatuses) {
    const pattern = new RegExp(`\\[${status}\\]`, 'gi');
    updatedTitle = updatedTitle.replace(pattern, '');
  }

  // Clean up extra spaces
  updatedTitle = updatedTitle.replace(/\s+/g, ' ').trim();

  logger.log(`✅ Removed status indicators from title: [${validStatuses.join(', ')}]`);
  return updatedTitle;
}

/**
 * Sync title to match a specific set of status labels
 * Removes indicators not in the target set and adds missing ones
 * @param {string} title - The original title
 * @param {string[]} targetStatuses - Array of status indicators that should be present
 * @returns {string} Updated title with only the target status indicators
 */
function syncTitleToStatuses(title, targetStatuses) {
  if (!title || typeof title !== 'string') {
    return title;
  }

  const statusLabels = getStatusLabels();
  const currentStatuses = extractStatusIndicators(title);

  // Normalize target statuses
  const normalizedTargets = (targetStatuses || [])
    .map(s => s.toLowerCase().trim())
    .filter(s => statusLabels.includes(s));

  // Find statuses to remove and add
  const toRemove = currentStatuses.filter(s => !normalizedTargets.includes(s));
  const toAdd = normalizedTargets.filter(s => !currentStatuses.includes(s));

  let updatedTitle = title;

  // Remove unwanted statuses
  if (toRemove.length > 0) {
    updatedTitle = removeStatusIndicators(updatedTitle, toRemove);
  }

  // Add missing statuses
  if (toAdd.length > 0) {
    updatedTitle = addStatusIndicators(updatedTitle, toAdd);
  }

  return updatedTitle;
}

module.exports = {
  getStatusLabels,
  extractStatusIndicators,
  hasStatusIndicator,
  addStatusIndicators,
  removeStatusIndicators,
  syncTitleToStatuses
};
