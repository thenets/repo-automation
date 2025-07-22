#!/usr/bin/env python3

import pytest
import time
import subprocess
from test_utils import poll_until_condition


class TestReadyForReviewLabeling:
    """Test suite for keeper-ready-for-review-labeling.yml workflow"""

    def test_ready_for_review_label_added_when_conditions_met(self):
        """Test that 'ready for review' label is added when PR has release label but no triage label"""
        
        # Create a test PR with YAML that will trigger release labeling
        pr_description = """
This PR adds new functionality.

```yaml
release: 1.5
```

Ready for team review.
"""
        
        # Create the PR
        result = subprocess.run([
            'gh', 'pr', 'create',
            '--title', 'Test ready for review labeling',
            '--body', pr_description,
            '--head', f'test-ready-for-review-{int(time.time())}',
            '--base', 'main'
        ], capture_output=True, text=True, cwd='.')
        
        assert result.returncode == 0, f"Failed to create PR: {result.stderr}"
        
        # Extract PR number from output
        pr_url = result.stdout.strip()
        pr_number = pr_url.split('/')[-1]
        
        try:
            # Wait for release label to be added (from release-backport workflow)
            def check_release_label():
                result = subprocess.run([
                    'gh', 'pr', 'view', pr_number, '--json', 'labels'
                ], capture_output=True, text=True, cwd='.')
                if result.returncode != 0:
                    return False
                
                import json
                labels = json.loads(result.stdout)['labels']
                label_names = [label['name'] for label in labels]
                return any(label.startswith('release ') for label in label_names)
            
            assert poll_until_condition(check_release_label, timeout=120, poll_interval=10), \
                "Release label was not added within expected time"
            
            # Manually remove triage label to simulate condition for ready for review
            subprocess.run([
                'gh', 'pr', 'edit', pr_number, '--remove-label', 'triage'
            ], capture_output=True, text=True, cwd='.')
            
            # Wait for ready for review label to be added
            def check_ready_for_review_label():
                result = subprocess.run([
                    'gh', 'pr', 'view', pr_number, '--json', 'labels'
                ], capture_output=True, text=True, cwd='.')
                if result.returncode != 0:
                    return False
                
                import json
                labels = json.loads(result.stdout)['labels']
                label_names = [label['name'] for label in labels]
                
                has_release = any(label.startswith('release ') for label in label_names)
                has_triage = 'triage' in label_names
                has_ready_for_review = 'ready for review' in label_names
                
                print(f"Labels: {label_names}")
                print(f"Has release: {has_release}, Has triage: {has_triage}, Has ready for review: {has_ready_for_review}")
                
                # Should have release label, no triage label, and ready for review label
                return has_release and not has_triage and has_ready_for_review
            
            assert poll_until_condition(check_ready_for_review_label, timeout=120, poll_interval=10), \
                "Ready for review label was not added when conditions were met"
                
        finally:
            # Cleanup: close the PR
            subprocess.run([
                'gh', 'pr', 'close', pr_number, '--delete-branch'
            ], capture_output=True, text=True, cwd='.')

    def test_ready_for_review_not_added_when_triage_present(self):
        """Test that 'ready for review' label is NOT added when PR still has triage label"""
        
        # Create a test PR with YAML that will trigger release labeling
        pr_description = """
This PR adds new functionality but still needs triage.

```yaml
release: 2.1
```

Still in triage process.
"""
        
        # Create the PR
        result = subprocess.run([
            'gh', 'pr', 'create',
            '--title', 'Test ready for review NOT added with triage',
            '--body', pr_description,
            '--head', f'test-no-ready-for-review-{int(time.time())}',
            '--base', 'main'
        ], capture_output=True, text=True, cwd='.')
        
        assert result.returncode == 0, f"Failed to create PR: {result.stderr}"
        
        # Extract PR number from output
        pr_url = result.stdout.strip()
        pr_number = pr_url.split('/')[-1]
        
        try:
            # Wait for release and triage labels to be present
            def check_both_labels():
                result = subprocess.run([
                    'gh', 'pr', 'view', pr_number, '--json', 'labels'
                ], capture_output=True, text=True, cwd='.')
                if result.returncode != 0:
                    return False
                
                import json
                labels = json.loads(result.stdout)['labels']
                label_names = [label['name'] for label in labels]
                
                has_release = any(label.startswith('release ') for label in label_names)
                has_triage = 'triage' in label_names
                
                return has_release and has_triage
            
            assert poll_until_condition(check_both_labels, timeout=120, poll_interval=10), \
                "Both release and triage labels should be present"
            
            # Wait a bit more to ensure ready for review workflow has had time to run
            time.sleep(30)
            
            # Verify ready for review label was NOT added
            def check_no_ready_for_review():
                result = subprocess.run([
                    'gh', 'pr', 'view', pr_number, '--json', 'labels'
                ], capture_output=True, text=True, cwd='.')
                if result.returncode != 0:
                    return False
                
                import json
                labels = json.loads(result.stdout)['labels']
                label_names = [label['name'] for label in labels]
                
                has_ready_for_review = 'ready for review' in label_names
                print(f"Labels: {label_names}")
                print(f"Has ready for review: {has_ready_for_review}")
                
                # Should NOT have ready for review label
                return not has_ready_for_review
            
            assert check_no_ready_for_review(), \
                "Ready for review label should NOT be added when triage label is present"
                
        finally:
            # Cleanup: close the PR
            subprocess.run([
                'gh', 'pr', 'close', pr_number, '--delete-branch'
            ], capture_output=True, text=True, cwd='.')

    def test_ready_for_review_not_added_without_release_label(self):
        """Test that 'ready for review' label is NOT added when PR has no release label"""
        
        # Create a test PR without release YAML
        pr_description = """
This PR adds new functionality but has no release labeling.

No YAML block here, so no release label will be added.
"""
        
        # Create the PR
        result = subprocess.run([
            'gh', 'pr', 'create',
            '--title', 'Test no ready for review without release',
            '--body', pr_description,
            '--head', f'test-no-release-{int(time.time())}',
            '--base', 'main'
        ], capture_output=True, text=True, cwd='.')
        
        assert result.returncode == 0, f"Failed to create PR: {result.stderr}"
        
        # Extract PR number from output
        pr_url = result.stdout.strip()
        pr_number = pr_url.split('/')[-1]
        
        try:
            # Remove triage label to simulate one condition
            time.sleep(20)  # Wait for triage label to be added first
            subprocess.run([
                'gh', 'pr', 'edit', pr_number, '--remove-label', 'triage'
            ], capture_output=True, text=True, cwd='.')
            
            # Wait and verify ready for review label was NOT added
            time.sleep(30)
            
            def check_no_ready_for_review():
                result = subprocess.run([
                    'gh', 'pr', 'view', pr_number, '--json', 'labels'
                ], capture_output=True, text=True, cwd='.')
                if result.returncode != 0:
                    return False
                
                import json
                labels = json.loads(result.stdout)['labels']
                label_names = [label['name'] for label in labels]
                
                has_release = any(label.startswith('release ') for label in label_names)
                has_ready_for_review = 'ready for review' in label_names
                
                print(f"Labels: {label_names}")
                print(f"Has release: {has_release}, Has ready for review: {has_ready_for_review}")
                
                # Should NOT have ready for review label since no release label
                return not has_release and not has_ready_for_review
            
            assert check_no_ready_for_review(), \
                "Ready for review label should NOT be added when no release label is present"
                
        finally:
            # Cleanup: close the PR
            subprocess.run([
                'gh', 'pr', 'close', pr_number, '--delete-branch'
            ], capture_output=True, text=True, cwd='.')


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 