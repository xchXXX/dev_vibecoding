"""Real repositories prove branch guards; tests never delete user branches."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / 'scripts/check_git_workflow.py'
SYNC = ROOT / 'scripts/sync_git_workflow.py'
POLICY = dict(schema_version=1, remote='origin', main_branch='main',
              task_prefixes=['codex/feat/', 'codex/fix/', 'codex/ops/'],
              reserved_branches={'codex/javirs': 'dots:javirs'},
              release_tag_pattern=r'release/\d{4}-\d{2}-\d{2}\.\d+',
              merge_method='merge', cleanup_mode='report-only')


class GitWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = ROOT / '.tmp/git-workflow/tests'
        temp.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=temp)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.write('config/ai/git-policy.json', json.dumps(POLICY))
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.remote = self.base / 'remote.git'
        self.git('init', '--bare', str(self.remote))
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-u', 'origin', 'main')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args],
                                       stderr=subprocess.PIPE, text=True).strip()

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def check(self, phase, *args, code=0):
        process = subprocess.run([sys.executable, str(CHECK), '--repo-root', str(self.repo),
                                  '--phase', phase, '--json', *args], capture_output=True, text=True)
        self.assertEqual(process.returncode, code, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def branch(self, name='codex/fix/example'):
        self.git('switch', '-c', name)
        self.write('change.txt', name)
        self.git('add', '.')
        self.git('commit', '-m', 'change')
        return name

    def test_task_branch_push_does_not_claim_unpushed_commit_is_remote(self):
        self.branch()
        result = self.check('push')
        self.assertFalse(result['upstream']['configured'])
        self.assertIsNone(result['upstream']['ahead'])

    def test_main_is_a_starting_point_but_not_direct_push_target(self):
        self.assertTrue(self.check('start')['needs_task_branch'])
        self.assertIn('MAIN_DIRECT_PUSH', self.check('push', code=1)['errors'])

    def test_invalid_branch_and_owner_reservation(self):
        self.git('switch', '-c', 'misc')
        self.assertIn('BRANCH_NAME', self.check('start', code=1)['errors'])
        self.git('switch', '-c', 'codex/javirs')
        self.assertEqual(self.check('start')['reserved_owner'], 'dots:javirs')

    def test_production_is_ci_only_and_never_a_cleanup_candidate(self):
        self.write('config/ai/git-policy.json', json.dumps({**POLICY, 'production_branch': 'production'}))
        self.git('add', '.')
        self.git('commit', '-m', 'production policy')
        self.git('switch', '-c', 'production')
        self.assertTrue(self.check('start')['needs_task_branch'])
        self.check('ci')
        self.assertIn('PRODUCTION_REQUIRES_APPROVED_RELEASE', self.check('push', code=1)['errors'])
        self.assertIn('PRODUCTION_REQUIRES_APPROVED_RELEASE', self.check('merge', code=1)['errors'])
        row = next(r for r in self.check('cleanup')['branches'] if r['branch'] == 'production')
        self.assertIn('PRODUCTION', row['reasons'])
        self.assertFalse(row['git_candidate'])

    def test_unrelated_dirty_files_reported_without_modification(self):
        self.branch()
        self.write('other-task.txt', 'keep')
        before = self.git('status', '--porcelain')
        self.assertTrue(self.check('start')['dirty'])
        self.assertIn('DIRTY_WORKTREE', self.check('merge', code=1)['errors'])
        self.assertEqual(before, self.git('status', '--porcelain'))

    def test_cleanup_protects_reserved_current_and_unmerged(self):
        self.git('branch', 'codex/javirs')
        task = self.branch()
        rows = {r['branch']: r for r in self.check('cleanup')['branches']}
        self.assertIn('RESERVED', rows['codex/javirs']['reasons'])
        self.assertIn('WORKTREE_IN_USE', rows[task]['reasons'])
        self.assertIn('NOT_MERGED', rows[task]['reasons'])
        self.assertFalse(any(r['delete_authorized'] for r in rows.values()))

    def test_merged_pushed_branch_is_only_candidate_not_deletion_permission(self):
        task = self.branch()
        self.git('push', '-u', 'origin', task)
        self.git('switch', 'main')
        self.git('merge', '--ff-only', task)
        self.git('push', 'origin', 'main')
        row = next(r for r in self.check('cleanup')['branches'] if r['branch'] == task)
        self.assertTrue(row['git_candidate'])
        self.assertFalse(row['delete_authorized'])
        self.assertIn(task, self.git('branch', '--list'))

    def test_second_worktree_branch_never_cleanup_candidate(self):
        task = self.branch()
        self.git('push', '-u', 'origin', task)
        self.git('switch', 'main')
        self.git('merge', '--ff-only', task)
        self.git('push', 'origin', 'main')
        self.git('worktree', 'add', str(self.base / 'second'), task)
        row = next(r for r in self.check('cleanup')['branches'] if r['branch'] == task)
        self.assertIn('WORKTREE_IN_USE', row['reasons'])
        self.assertFalse(row['git_candidate'])

    def test_remote_only_unmerged_commits_prevent_cleanup_candidate(self):
        task = self.branch()
        self.git('push', '-u', 'origin', task)
        self.git('switch', 'main')
        self.git('merge', '--ff-only', task)
        self.git('push', 'origin', 'main')
        self.git('switch', '-c', 'codex/fix/remote-writer')
        self.write('remote-only.txt', 'keep remote work')
        self.git('add', '.')
        self.git('commit', '-m', 'remote only')
        self.git('push', 'origin', 'HEAD:refs/heads/' + task)
        self.git('switch', 'main')
        self.git('fetch', 'origin')
        row = next(r for r in self.check('cleanup')['branches'] if r['branch'] == task)
        self.assertFalse(row['git_candidate'])
        self.assertIn('REMOTE_NOT_MERGED', row['reasons'])

    def test_unpushed_branch_not_cleanup_candidate_even_if_main_contains_it(self):
        task = self.branch()
        self.git('switch', 'main')
        self.git('merge', '--ff-only', task)
        self.git('push', 'origin', 'main')
        row = next(r for r in self.check('cleanup')['branches'] if r['branch'] == task)
        self.assertIn('REMOTE_BRANCH_UNKNOWN', row['reasons'])
        self.assertFalse(row['git_candidate'])

    def test_detached_pr_checkout_requires_explicit_ci_branch(self):
        self.git('checkout', '--detach')
        self.assertIn('DETACHED_HEAD', self.check('start', code=1)['errors'])
        self.check('ci', '--branch', 'codex/feat/example')
        self.assertIn('BRANCH_OVERRIDE_CI_ONLY', self.check('push', '--branch', 'codex/fix/spoof', code=1)['errors'])

    def test_release_requires_matching_tag_and_live_remote(self):
        tag = 'release/2026-10-13.1'
        self.git('tag', '-a', tag, '-m', 'release')
        self.assertIn('TAG_NOT_ON_REMOTE', self.check('release', '--release-tag', tag, code=1)['errors'])
        self.git('push', 'origin', tag)
        self.assertTrue(self.check('release', '--release-tag', tag)['remote_verified'])
        self.write('next', 'next')
        self.git('add', '.')
        self.git('commit', '-m', 'next')
        self.assertIn('TAG_HEAD_MISMATCH', self.check('release', '--release-tag', tag, code=1)['errors'])

    def test_configuration_cannot_enable_unsupported_auto_delete(self):
        self.write('config/ai/git-policy.json', json.dumps({**POLICY, 'cleanup_mode': 'automatic'}))
        self.assertIn('CONFIG_INVALID', self.check('start', code=2)['errors'])

    def test_project_copy_generation_is_repeatable_and_detects_drift(self):
        args = [sys.executable, str(SYNC), '--project-root', str(self.repo)]
        p = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        target = self.repo / 'modules/tooling/check_git_workflow.py'
        initial = target.read_bytes()
        self.assertEqual(subprocess.run([*args, '--check'], capture_output=True).returncode, 0)
        target.write_bytes(initial + b'\n# unexpected edit\n')
        self.assertNotEqual(subprocess.run([*args, '--check'], capture_output=True).returncode, 0)
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
        self.assertEqual(target.read_bytes(), initial + b'\n# unexpected edit\n')


if __name__ == '__main__':
    unittest.main()
