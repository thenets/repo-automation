/**
 * Unit tests for GitHubClient class
 * Tests GitHub API interactions, error handling, and dry-run mode
 */

const { GitHubClient } = require('../../../src/utils/github-client');

describe('GitHubClient', () => {
  let mockGitHub;
  let mockConfig;
  let client;

  beforeEach(() => {
    mockGitHub = createMockGitHub();
    mockConfig = {
      getRepository: () => ({ owner: 'test-owner', repo: 'test-repo' }),
      isDryRun: () => false,
      getGithubToken: () => 'test-token'
    };
    client = new GitHubClient(mockGitHub, mockConfig);
  });

  describe('Constructor', () => {
    test('should initialize with github and config', () => {
      expect(client.github).toBe(mockGitHub);
      expect(client.config).toBe(mockConfig);
      expect(client.owner).toBe('test-owner');
      expect(client.repo).toBe('test-repo');
    });
  });

  describe('addLabels', () => {
    test('should add labels successfully', async () => {
      mockGitHub.rest.issues.addLabels.mockResolvedValue({});
      
      const result = await client.addLabels(123, ['triage', 'bug']);
      
      expect(mockGitHub.rest.issues.addLabels).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        issue_number: 123,
        labels: ['triage', 'bug']
      });
      expect(result).toEqual({ added: ['triage', 'bug'], skipped: false });
    });

    test('should handle dry run mode', async () => {
      mockConfig.isDryRun = () => true;
      
      const result = await client.addLabels(123, ['triage']);
      
      expect(mockGitHub.rest.issues.addLabels).not.toHaveBeenCalled();
      expect(result).toEqual({ added: ['triage'], skipped: false });
    });

    test('should handle 403 permission errors', async () => {
      const error = new Error('Forbidden');
      error.status = 403;
      mockGitHub.rest.issues.addLabels.mockRejectedValue(error);
      
      await expect(client.addLabels(123, ['triage'])).rejects.toThrow(
        /Permission denied.*CUSTOM_GITHUB_TOKEN/
      );
    });

    test('should handle 422 label already exists', async () => {
      const error = new Error('Unprocessable Entity');
      error.status = 422;
      mockGitHub.rest.issues.addLabels.mockRejectedValue(error);
      
      // Mock getLabels to return current labels
      mockGitHub.rest.issues.listLabelsOnIssue.mockResolvedValue({
        data: [{ name: 'triage' }]
      });
      
      const result = await client.addLabels(123, ['triage']);
      
      expect(result).toEqual({ added: [], skipped: ['triage'] });
    });

    test('should handle 422 label does not exist in repo', async () => {
      const error = new Error('Unprocessable Entity');
      error.status = 422;
      mockGitHub.rest.issues.addLabels.mockRejectedValue(error);
      
      // Mock getLabels to return different labels
      mockGitHub.rest.issues.listLabelsOnIssue.mockResolvedValue({
        data: [{ name: 'bug' }]
      });
      
      await expect(client.addLabels(123, ['triage'])).rejects.toThrow(
        /don't exist in the repository/
      );
    });

    test('should handle other HTTP errors', async () => {
      const error = new Error('Server Error');
      error.status = 500;
      mockGitHub.rest.issues.addLabels.mockRejectedValue(error);
      
      await expect(client.addLabels(123, ['triage'])).rejects.toThrow(
        /Unexpected error.*Server Error/
      );
    });
  });

  describe('getLabels', () => {
    test('should get labels successfully', async () => {
      mockGitHub.rest.issues.listLabelsOnIssue.mockResolvedValue({
        data: [
          { name: 'triage' },
          { name: 'bug' },
          { name: 'enhancement' }
        ]
      });
      
      const labels = await client.getLabels(123);
      
      expect(mockGitHub.rest.issues.listLabelsOnIssue).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        issue_number: 123
      });
      expect(labels).toEqual(['triage', 'bug', 'enhancement']);
    });

    test('should handle errors when getting labels', async () => {
      const error = new Error('Not found');
      mockGitHub.rest.issues.listLabelsOnIssue.mockRejectedValue(error);
      
      await expect(client.getLabels(123)).rejects.toThrow('Not found');
    });
  });

  describe('hasLabels', () => {
    beforeEach(() => {
      mockGitHub.rest.issues.listLabelsOnIssue.mockResolvedValue({
        data: [
          { name: 'triage' },
          { name: 'release-1.0' },
          { name: 'backport-main' }
        ]
      });
    });

    test('should check exact label matches', async () => {
      const result = await client.hasLabels(123, ['triage', 'bug']);
      
      expect(result).toEqual({
        'triage': true,
        'bug': false
      });
    });

    test('should check wildcard label matches', async () => {
      const result = await client.hasLabels(123, ['release-*', 'feature-*']);
      
      expect(result).toEqual({
        'release-*': true,
        'feature-*': false
      });
    });

    test('should handle mixed exact and wildcard matches', async () => {
      const result = await client.hasLabels(123, ['triage', 'release-*', 'bug']);
      
      expect(result).toEqual({
        'triage': true,
        'release-*': true,
        'bug': false
      });
    });
  });

  describe('getPR', () => {
    test('should get PR successfully', async () => {
      const mockPR = { number: 123, title: 'Test PR' };
      mockGitHub.rest.pulls.get.mockResolvedValue({ data: mockPR });
      
      const pr = await client.getPR(123);
      
      expect(mockGitHub.rest.pulls.get).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        pull_number: 123
      });
      expect(pr).toBe(mockPR);
    });

    test('should handle errors when getting PR', async () => {
      const error = new Error('Not found');
      mockGitHub.rest.pulls.get.mockRejectedValue(error);
      
      await expect(client.getPR(123)).rejects.toThrow('Not found');
    });
  });

  describe('findPRByBranch', () => {
    test('should find PR by branch successfully', async () => {
      const mockPRs = [
        { number: 123, title: 'Test PR' },
        { number: 124, title: 'Another PR' }
      ];
      mockGitHub.rest.pulls.list.mockResolvedValue({ data: mockPRs });
      
      const pr = await client.findPRByBranch('feature-branch');
      
      expect(mockGitHub.rest.pulls.list).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        head: 'test-owner:feature-branch',
        state: 'all',
        sort: 'updated',
        direction: 'desc'
      });
      expect(pr).toBe(mockPRs[0]);
    });

    test('should return null when no PR found', async () => {
      mockGitHub.rest.pulls.list.mockResolvedValue({ data: [] });
      
      const pr = await client.findPRByBranch('nonexistent-branch');
      
      expect(pr).toBeNull();
    });

    test('should handle errors when finding PR', async () => {
      const error = new Error('API Error');
      mockGitHub.rest.pulls.list.mockRejectedValue(error);
      
      await expect(client.findPRByBranch('branch')).rejects.toThrow('API Error');
    });
  });

  describe('createCheckRun', () => {
    test('should create check run successfully', async () => {
      const mockCheckRun = { data: { id: 'check-123' } };
      mockGitHub.rest.checks.create.mockResolvedValue(mockCheckRun);
      
      const result = await client.createCheckRun('Test Check', 'abc123', 'https://example.com');
      
      expect(mockGitHub.rest.checks.create).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        name: 'Test Check',
        head_sha: 'abc123',
        status: 'in_progress',
        started_at: expect.any(String),
        details_url: 'https://example.com'
      });
      expect(result).toBe(mockCheckRun);
    });

    test('should handle dry run mode for check run', async () => {
      mockConfig.isDryRun = () => true;
      
      const result = await client.createCheckRun('Test Check', 'abc123');
      
      expect(mockGitHub.rest.checks.create).not.toHaveBeenCalled();
      expect(result).toEqual({ data: { id: 'dry-run-check-id' } });
    });
  });

  describe('updateCheckRun', () => {
    test('should update check run successfully', async () => {
      mockGitHub.rest.checks.update.mockResolvedValue({});
      
      const output = { title: 'Test', summary: 'Test summary' };
      await client.updateCheckRun('check-123', 'completed', 'success', output);
      
      expect(mockGitHub.rest.checks.update).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        check_run_id: 'check-123',
        status: 'completed',
        conclusion: 'success',
        completed_at: expect.any(String),
        output
      });
    });

    test('should handle dry run mode for check run update', async () => {
      mockConfig.isDryRun = () => true;
      
      await client.updateCheckRun('check-123', 'completed', 'success');
      
      expect(mockGitHub.rest.checks.update).not.toHaveBeenCalled();
    });
  });

  describe('createComment', () => {
    test('should create comment successfully', async () => {
      mockGitHub.rest.issues.createComment.mockResolvedValue({});
      
      await client.createComment(123, 'Test comment');
      
      expect(mockGitHub.rest.issues.createComment).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        issue_number: 123,
        body: 'Test comment'
      });
    });

    test('should handle dry run mode for comments', async () => {
      mockConfig.isDryRun = () => true;
      
      await client.createComment(123, 'Test comment');
      
      expect(mockGitHub.rest.issues.createComment).not.toHaveBeenCalled();
    });
  });

  describe('listComments', () => {
    test('should list comments successfully', async () => {
      const mockComments = [
        { id: 1, body: 'First comment' },
        { id: 2, body: 'Second comment' }
      ];
      mockGitHub.rest.issues.listComments.mockResolvedValue({ data: mockComments });
      
      const comments = await client.listComments(123);
      
      expect(mockGitHub.rest.issues.listComments).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        issue_number: 123
      });
      expect(comments).toBe(mockComments);
    });
  });

  describe('deleteComment', () => {
    test('should delete comment successfully', async () => {
      mockGitHub.rest.issues.deleteComment.mockResolvedValue({});
      
      await client.deleteComment(456);
      
      expect(mockGitHub.rest.issues.deleteComment).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        comment_id: 456
      });
    });

    test('should handle dry run mode for comment deletion', async () => {
      mockConfig.isDryRun = () => true;
      
      await client.deleteComment(456);
      
      expect(mockGitHub.rest.issues.deleteComment).not.toHaveBeenCalled();
    });
  });

  describe('cleanupWorkflowComments', () => {
    test('should cleanup workflow comments successfully', async () => {
      const mockComments = [
        { id: 1, body: 'Normal comment' },
        { id: 2, body: 'Workflow comment with identifier' },
        { id: 3, body: 'Another identifier comment' }
      ];
      mockGitHub.rest.issues.listComments.mockResolvedValue({ data: mockComments });
      mockGitHub.rest.issues.deleteComment.mockResolvedValue({});
      
      await client.cleanupWorkflowComments(123, 'identifier');
      
      expect(mockGitHub.rest.issues.deleteComment).toHaveBeenCalledTimes(2);
      expect(mockGitHub.rest.issues.deleteComment).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        comment_id: 2
      });
      expect(mockGitHub.rest.issues.deleteComment).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        comment_id: 3
      });
    });

    test('should handle errors gracefully during cleanup', async () => {
      mockGitHub.rest.issues.listComments.mockRejectedValue(new Error('API Error'));
      
      // Should not throw, just log
      await expect(client.cleanupWorkflowComments(123, 'identifier')).resolves.toBeUndefined();
    });
  });

  describe('listOpenPRs', () => {
    test('should list open PRs successfully', async () => {
      const mockPRs = [
        { number: 123, title: 'PR 1' },
        { number: 124, title: 'PR 2' }
      ];
      mockGitHub.rest.pulls.list.mockResolvedValue({ data: mockPRs });
      
      const prs = await client.listOpenPRs();
      
      expect(mockGitHub.rest.pulls.list).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        state: 'open',
        per_page: 100
      });
      expect(prs).toBe(mockPRs);
    });

    test('should support custom per_page parameter', async () => {
      mockGitHub.rest.pulls.list.mockResolvedValue({ data: [] });
      
      await client.listOpenPRs(50);
      
      expect(mockGitHub.rest.pulls.list).toHaveBeenCalledWith({
        owner: 'test-owner',
        repo: 'test-repo',
        state: 'open',
        per_page: 50
      });
    });
  });

  describe('PR Activity Methods', () => {
    test('should list PR commits with error handling', async () => {
      const mockCommits = [{ sha: 'abc123' }];
      mockGitHub.rest.pulls.listCommits.mockResolvedValue({ data: mockCommits });
      
      const commits = await client.listPRCommits(123);
      
      expect(commits).toBe(mockCommits);
    });

    test('should return empty array on commits error', async () => {
      mockGitHub.rest.pulls.listCommits.mockRejectedValue(new Error('Error'));
      
      const commits = await client.listPRCommits(123);
      
      expect(commits).toEqual([]);
    });

    test('should list PR review comments with error handling', async () => {
      const mockComments = [{ id: 1 }];
      mockGitHub.rest.pulls.listReviewComments.mockResolvedValue({ data: mockComments });
      
      const comments = await client.listPRReviewComments(123);
      
      expect(comments).toBe(mockComments);
    });

    test('should list PR reviews with error handling', async () => {
      const mockReviews = [{ id: 1 }];
      mockGitHub.rest.pulls.listReviews.mockResolvedValue({ data: mockReviews });
      
      const reviews = await client.listPRReviews(123);
      
      expect(reviews).toBe(mockReviews);
    });

    test('should list timeline events with error handling', async () => {
      const mockTimeline = [{ event: 'labeled' }];
      mockGitHub.rest.issues.listEventsForTimeline.mockResolvedValue({ data: mockTimeline });
      
      const timeline = await client.listTimelineEvents(123);
      
      expect(timeline).toBe(mockTimeline);
    });
  });
});