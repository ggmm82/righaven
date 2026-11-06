from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from righaven import state
from righaven import organization_limits as limits


class OrganizationLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=patch.object(state,'STATE',Path(self.temp.name));p.start();self.addCleanup(p.stop)

    def test_parallel_admission_is_atomic_and_other_users_are_isolated(self):
        limits.configure('alice',1,2)
        started=threading.Event();release=threading.Event()
        def worker():
            with limits.admission('alice'):
                started.set();release.wait(5)
        with ThreadPoolExecutor() as pool:
            task=pool.submit(worker)
            try:
                self.assertTrue(started.wait(3))
                with self.assertRaisesRegex(ValueError,'concurrency'):
                    with limits.admission('alice'):pass
                with limits.admission('bob'):pass
                self.assertEqual(limits.snapshot('alice')['active_jobs'],1)
                self.assertEqual(limits.snapshot('bob')['active_jobs'],0)
            finally:release.set();task.result()
        with limits.admission('alice'):pass
        with self.assertRaisesRegex(ValueError,'monthly'):
            with limits.admission('alice'):pass

    def test_failed_jobs_release_slots_and_restart_recovery_preserves_usage(self):
        with self.assertRaises(RuntimeError):
            with limits.admission('alice'):raise RuntimeError('worker failed')
        before=limits.snapshot('alice')
        self.assertEqual(before['active_jobs'],0)
        self.assertEqual(before['used_jobs'],1)
        limits.recover_after_cleanup()
        self.assertEqual(limits.snapshot('alice')['used_jobs'],1)
        self.assertGreaterEqual(before['measured_job_seconds'],0)
