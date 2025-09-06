/**
 * Unit tests for StaleDetection class
 * Tests stale PR detection logic, activity tracking, and labeling
 */

const { StaleDetection } = require('../../src/stale-detection');

// Mock the dependencies
jest.mock('../../src/utils/config');
jest.mock('../../src/utils/github-client');

const { ConfigManager } = require('../../src/utils/config');
const { GitHubClient } = require('../../src/utils/github-client');

describe('StaleDetection', () => {
  let mockContext;
  let mockGitHub;
  let mockConfig;
  let mockClient;
  let staleDetection;

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockContext = createMockContext();
    mockGitHub = createMockGitHub();
    
    // Mock ConfigManager
    mockConfig = {
      getStaleDays: jest.fn().mockReturnValue(1),
      isDryRun: jest.fn().mockReturnValue(false)
    };
    ConfigManager.mockImplementation(() => mockConfig);
    
    // Mock GitHubClient
    mockClient = {
      listOpenPRs: jest.fn(),
      getPR: jest.fn(),
      listPRCommits: jest.fn(),
      listComments: jest.fn(),
      listPRReviewComments: jest.fn(),
      listPRReviews: jest.fn(),
      listTimelineEvents: jest.fn(),
      addLabels: jest.fn()
    };
    GitHubClient.mockImplementation(() => mockClient);
    
    staleDetection = new StaleDetection(mockContext, mockGitHub);
  });

  describe('Constructor', () => {
    test('should initialize with context and github', () => {
      expect(staleDetection.context).toBe(mockContext);
      expect(staleDetection.github).toBe(mockGitHub);
      expect(ConfigManager).toHaveBeenCalledWith(mockContext, {});
      expect(GitHubClient).toHaveBeenCalledWith(mockGitHub, mockConfig);
    });

    test('should initialize with options', () => {
      const options = { staleDays: 7 };
      new StaleDetection(mockContext, mockGitHub, options);
      
      expect(ConfigManager).toHaveBeenCalledWith(mockContext, options);
    });

    test('should initialize result object', () => {
      expect(staleDetection.result).toEqual({
        labelsAdded: [],
        actions: [],
        processedPRs: 0,
        stalePRsFound: 0
      });
    });

    test('should set default stale days to 1', () => {
      mockConfig.getStaleDays.mockReturnValue(undefined);
      const detection = new StaleDetection(mockContext, mockGitHub);
      
      expect(detection.staleDays).toBe(1);
    });

    test('should use configured stale days', () => {
      mockConfig.getStaleDays.mockReturnValue(7);
      const detection = new StaleDetection(mockContext, mockGitHub);
      
      expect(detection.staleDays).toBe(7);
      expect(detection.staleThresholdMs).toBe(7 * 24 * 60 * 60 * 1000);
    });
  });

  describe('execute', () => {
    test('should process all open PRs', async () => {
      const mockPRs = [
        { number: 123, draft: false, labels: [] },
        { number: 124, draft: false, labels: [] }
      ];
      mockClient.listOpenPRs.mockResolvedValue(mockPRs);
      
      // Mock processPR to avoid complex setup
      staleDetection.processPR = jest.fn();
      
      const result = await staleDetection.execute();
      
      expect(mockClient.listOpenPRs).toHaveBeenCalled();
      expect(staleDetection.processPR).toHaveBeenCalledTimes(2);
      expect(result.processedPRs).toBe(2);
    });

    test('should handle individual PR processing errors gracefully', async () => {
      const mockPRs = [
        { number: 123, draft: false, labels: [] },
        { number: 124, draft: false, labels: [] }
      ];
      mockClient.listOpenPRs.mockResolvedValue(mockPRs);
      
      // Mock processPR to throw error for first PR
      staleDetection.processPR = jest.fn()
        .mockRejectedValueOnce(new Error('PR 123 error'))
        .mockResolvedValueOnce();
      
      const result = await staleDetection.execute();
      
      // Should continue processing despite error
      expect(staleDetection.processPR).toHaveBeenCalledTimes(2);
      expect(result.processedPRs).toBe(2);
    });

    test('should handle errors when listing PRs', async () => {
      mockClient.listOpenPRs.mockRejectedValue(new Error('API Error'));
      
      await expect(staleDetection.execute()).rejects.toThrow('API Error');
    });
  });

  describe('processPR', () => {
    let mockPR;
    let now;

    beforeEach(() => {
      now = new Date();
      mockPR = {
        number: 123,
        draft: false,
        labels: []
      };
      
      staleDetection.getLastActivityDate = jest.fn();
      staleDetection.markPRAsStale = jest.fn();
    });

    test('should skip draft PRs', async () => {
      mockPR.draft = true;
      
      await staleDetection.processPR(mockPR, now);
      
      expect(staleDetection.getLastActivityDate).not.toHaveBeenCalled();
      expect(staleDetection.markPRAsStale).not.toHaveBeenCalled();
    });

    test('should skip PRs that already have stale label', async () => {
      mockPR.labels = [{ name: 'stale' }];
      
      await staleDetection.processPR(mockPR, now);
      
      expect(staleDetection.getLastActivityDate).not.toHaveBeenCalled();
      expect(staleDetection.markPRAsStale).not.toHaveBeenCalled();
    });

    test('should mark PR as stale when threshold exceeded', async () => {
      const oneDayAgo = new Date(now.getTime() - (25 * 60 * 60 * 1000)); // 25 hours ago
      staleDetection.getLastActivityDate.mockResolvedValue(oneDayAgo);
      
      await staleDetection.processPR(mockPR, now);
      
      expect(staleDetection.getLastActivityDate).toHaveBeenCalledWith(123);
      expect(staleDetection.markPRAsStale).toHaveBeenCalledWith(123, 25);
    });

    test('should not mark PR as stale when threshold not exceeded', async () => {
      const recentActivity = new Date(now.getTime() - (12 * 60 * 60 * 1000)); // 12 hours ago
      staleDetection.getLastActivityDate.mockResolvedValue(recentActivity);
      
      await staleDetection.processPR(mockPR, now);
      
      expect(staleDetection.getLastActivityDate).toHaveBeenCalledWith(123);
      expect(staleDetection.markPRAsStale).not.toHaveBeenCalled();
    });

    test('should calculate hours correctly', async () => {
      const threeHoursAgo = new Date(now.getTime() - (3 * 60 * 60 * 1000));
      staleDetection.getLastActivityDate.mockResolvedValue(threeHoursAgo);
      
      await staleDetection.processPR(mockPR, now);
      
      // 3 hours is less than 24, so should not mark as stale
      expect(staleDetection.markPRAsStale).not.toHaveBeenCalled();
    });
  });

  describe('markPRAsStale', () => {
    test('should add stale label and update result', async () => {
      mockClient.addLabels.mockResolvedValue({ added: ['stale'] });
      
      await staleDetection.markPRAsStale(123, 48);
      
      expect(mockClient.addLabels).toHaveBeenCalledWith(123, ['stale']);
      expect(staleDetection.result.labelsAdded).toContain('stale');
      expect(staleDetection.result.actions).toContain(
        'Added stale label to PR #123 (inactive for 48 hours)'
      );
      expect(staleDetection.result.stalePRsFound).toBe(1);
    });

    test('should handle errors when adding stale label', async () => {
      const error = new Error('Label add failed');
      mockClient.addLabels.mockRejectedValue(error);
      
      await expect(staleDetection.markPRAsStale(123, 48)).rejects.toThrow('Label add failed');
    });
  });

  describe('getLastActivityDate', () => {
    beforeEach(() => {
      const baseDate = new Date('2023-01-01T00:00:00Z');
      
      // Mock all API calls with default empty responses
      mockClient.getPR.mockResolvedValue({ 
        updated_at: baseDate.toISOString() 
      });
      mockClient.listPRCommits.mockResolvedValue([]);
      mockClient.listComments.mockResolvedValue([]);
      mockClient.listPRReviewComments.mockResolvedValue([]);
      mockClient.listPRReviews.mockResolvedValue([]);
      mockClient.listTimelineEvents.mockResolvedValue([]);
    });

    test('should return PR updated_at when no other activity', async () => {
      const prDate = new Date('2023-01-01T12:00:00Z');
      mockClient.getPR.mockResolvedValue({ 
        updated_at: prDate.toISOString() 
      });
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(prDate);
    });

    test('should consider commit dates', async () => {
      const commitDate = new Date('2023-01-02T12:00:00Z');
      mockClient.listPRCommits.mockResolvedValue([
        {
          commit: {
            committer: {
              date: commitDate.toISOString()
            }
          }
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(commitDate);
    });

    test('should consider comment dates', async () => {
      const commentDate = new Date('2023-01-03T12:00:00Z');
      mockClient.listComments.mockResolvedValue([
        {
          created_at: commentDate.toISOString()
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(commentDate);
    });

    test('should consider review comment dates', async () => {
      const reviewCommentDate = new Date('2023-01-04T12:00:00Z');
      mockClient.listPRReviewComments.mockResolvedValue([
        {
          created_at: reviewCommentDate.toISOString()
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(reviewCommentDate);
    });

    test('should consider review dates', async () => {
      const reviewDate = new Date('2023-01-05T12:00:00Z');
      mockClient.listPRReviews.mockResolvedValue([
        {
          submitted_at: reviewDate.toISOString()
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(reviewDate);
    });

    test('should consider timeline events (label changes)', async () => {
      const labelDate = new Date('2023-01-06T12:00:00Z');
      mockClient.listTimelineEvents.mockResolvedValue([
        {
          event: 'labeled',
          created_at: labelDate.toISOString()
        },
        {
          event: 'assigned',
          created_at: '2023-01-05T12:00:00Z'
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(labelDate);
    });

    test('should return most recent activity from all sources', async () => {
      const prDate = new Date('2023-01-01T12:00:00Z');
      const commitDate = new Date('2023-01-02T12:00:00Z');
      const commentDate = new Date('2023-01-04T12:00:00Z'); // Most recent
      const reviewDate = new Date('2023-01-03T12:00:00Z');
      
      mockClient.getPR.mockResolvedValue({ 
        updated_at: prDate.toISOString() 
      });
      mockClient.listPRCommits.mockResolvedValue([
        {
          commit: {
            committer: {
              date: commitDate.toISOString()
            }
          }
        }
      ]);
      mockClient.listComments.mockResolvedValue([
        {
          created_at: commentDate.toISOString()
        }
      ]);
      mockClient.listPRReviews.mockResolvedValue([
        {
          submitted_at: reviewDate.toISOString()
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(commentDate);
    });

    test('should handle missing commit data gracefully', async () => {
      mockClient.listPRCommits.mockResolvedValue([
        {
          // Missing commit.committer.date
          commit: {}
        },
        {
          commit: {
            committer: {
              date: '2023-01-02T12:00:00Z'
            }
          }
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(new Date('2023-01-02T12:00:00Z'));
    });

    test('should handle missing review submitted_at gracefully', async () => {
      mockClient.listPRReviews.mockResolvedValue([
        {
          // Missing submitted_at
          id: 1
        },
        {
          submitted_at: '2023-01-02T12:00:00Z'
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(new Date('2023-01-02T12:00:00Z'));
    });

    test('should filter timeline events to only label changes', async () => {
      const labelDate = new Date('2023-01-02T12:00:00Z');
      const otherEventDate = new Date('2023-01-03T12:00:00Z');
      
      mockClient.listTimelineEvents.mockResolvedValue([
        {
          event: 'labeled',
          created_at: labelDate.toISOString()
        },
        {
          event: 'assigned', // This should be ignored
          created_at: otherEventDate.toISOString()
        },
        {
          event: 'unlabeled',
          created_at: labelDate.toISOString()
        }
      ]);
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(labelDate);
    });

    test('should handle errors when fetching PR details', async () => {
      mockClient.getPR.mockRejectedValue(new Error('PR not found'));
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      // Should return current time as fallback
      expect(lastActivity).toBeInstanceOf(Date);
    });

    test('should handle errors when fetching comments', async () => {
      mockClient.listComments.mockRejectedValue(new Error('Comments error'));
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      // Should still work with other data sources
      expect(lastActivity).toBeInstanceOf(Date);
    });

    test('should fallback to PR creation date when updated_at fails', async () => {
      const creationDate = new Date('2023-01-01T12:00:00Z');
      
      // First call for updated_at fails, second call for created_at succeeds
      mockClient.getPR
        .mockRejectedValueOnce(new Error('PR details error'))
        .mockResolvedValueOnce({ 
          created_at: creationDate.toISOString() 
        });
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(creationDate);
    });

    test('should fallback to current time when all PR fetches fail', async () => {
      mockClient.getPR.mockRejectedValue(new Error('All PR calls fail'));
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      // Should return a recent date (current time)
      const now = new Date();
      const timeDiff = Math.abs(now.getTime() - lastActivity.getTime());
      expect(timeDiff).toBeLessThan(1000); // Within 1 second
    });

    test('should return most recent when no activities found', async () => {
      // All API calls return empty arrays, only PR updated_at available
      const prDate = new Date('2023-01-01T12:00:00Z');
      mockClient.getPR.mockResolvedValue({ 
        updated_at: prDate.toISOString() 
      });
      
      const lastActivity = await staleDetection.getLastActivityDate(123);
      
      expect(lastActivity).toEqual(prDate);
    });
  });
});