/**
 * Jest setup file for unit tests
 * This file runs before each test file and sets up global test configuration
 */

// Mock console methods to reduce noise in tests unless explicitly needed
global.console = {
  ...console,
  // Uncomment below to silence console logs in tests
  // log: jest.fn(),
  // info: jest.fn(),
  // warn: jest.fn(),
  // error: jest.fn(),
};

// Global test utilities
global.createMockContext = (overrides = {}) => ({
  repo: {
    owner: 'test-owner',
    repo: 'test-repo'
  },
  eventName: 'pull_request',
  payload: {},
  issue: { number: 1 },
  ...overrides
});

global.createMockGitHub = () => ({
  rest: {
    issues: {
      addLabels: jest.fn(),
      listLabelsOnIssue: jest.fn(),
      createComment: jest.fn(),
      listComments: jest.fn(),
      deleteComment: jest.fn(),
      listEventsForTimeline: jest.fn()
    },
    pulls: {
      get: jest.fn(),
      list: jest.fn(),
      listCommits: jest.fn(),
      listReviewComments: jest.fn(),
      listReviews: jest.fn()
    },
    checks: {
      create: jest.fn(),
      update: jest.fn()
    }
  }
});