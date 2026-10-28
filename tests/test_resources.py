"""Real process lifecycle and shared runtime resource policy regressions."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from righaven import operations, resource_usage, runtime_settings, state


class ResourceTests(unittest.TestCase):
    def test_budget_is_shared_persistent_and_reserves_capacity(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(state, 'STATE', Path(directory)), patch.object(runtime_settings, 'capacity', return_value={'cpus': 4, 'memory_mib': 8192, 'detected': True}):
            self.assertEqual(runtime_settings.effective()['cpus'], 3.5)
            self.assertEqual(runtime_settings.effective()['memory_mib'], 6144)
            runtime_settings.save({'mode': 'manual', 'cpus': 2, 'memory_mib': 3072})
            self.assertEqual(runtime_settings.read()['effective']['memory_mib'], 3072)
            with self.assertRaises(ValueError):
                runtime_settings.save({'mode': 'manual', 'cpus': 2, 'memory_mib': 8192})
            self.assertEqual(runtime_settings.settings()['memory_mib'], 3072)
            self.assertEqual(runtime_settings.effective()['model_wait_seconds'], 0)
            runtime_settings.save({'mode':'auto','cpus':2,'memory_mib':3072,'model_wait_seconds':120})
            self.assertEqual(runtime_settings.read()['effective']['model_wait_seconds'],120)
            with self.assertRaises(ValueError):
                runtime_settings.save({'mode':'auto','cpus':2,'memory_mib':3072,'model_wait_seconds':1})
            self.assertEqual(runtime_settings.read()['effective']['model_wait_seconds'],120)

    def test_oom_requires_a_real_counter_not_exit_137(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(resource_usage.snapshot(root)['oom_kills'])
            (root / 'memory.events').write_text('oom 2\noom_kill 1\n')
            self.assertEqual(resource_usage.snapshot(root)['oom_kills'], 1)
            result, status = operations.supervise([sys.executable, '-c', 'raise SystemExit(137)'], root, 'forced')
            self.assertEqual(result.returncode, 137)
            self.assertNotEqual(status['state'], 'out_of_memory')

    def test_timeout_stops_children_and_releases_the_worker_for_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pidfile = root / 'pid.txt'
            script = "import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(90)']);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(90)"
            with self.assertRaises(subprocess.TimeoutExpired):
                operations.supervise([sys.executable, '-c', script, str(pidfile)], root, 'long', timeout=.6)
            child = int(pidfile.read_text())
            for _ in range(20):
                if operations.identity(child) is None:
                    break
                time.sleep(.05)
            self.assertIsNone(operations.identity(child))
            result, _ = operations.supervise([sys.executable, '-c', 'print("recovered")'], root, 'recovery')
            self.assertEqual(result.returncode, 0)

    def test_killed_supervisor_cannot_leave_an_undetected_duplicate_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = 'from righaven.operations import supervise;import sys;supervise([sys.executable,"-c","import time;time.sleep(30)"],sys.argv[1],"original")'
            manager = subprocess.Popen([sys.executable, '-c', code, str(root)], cwd=Path(__file__).resolve().parents[1])
            active = root / 'work/operations/active.json'
            record = None
            try:
                for _ in range(100):
                    if active.exists():
                        record = json.loads(active.read_text());break
                    time.sleep(.03)
                self.assertIsNotNone(record)
                manager.kill();manager.wait()
                with self.assertRaisesRegex(RuntimeError, 'ancora attivo'):
                    operations.supervise([sys.executable, '-c', 'print("duplicate")'], root, 'different-key')
            finally:
                if manager.poll() is None:
                    manager.kill();manager.wait()
                if record and operations.identity(record['pid']) == record['process_identity']:
                    os.killpg(record['pid'], signal.SIGKILL)

    def test_native_progress_is_persisted_without_publishing_log_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, status = operations.supervise([sys.executable, '-u', '-c', 'import time;print("Sample 4/48 secret-log");time.sleep(.7)'], root, 'progress')
            self.assertEqual(status['progress'], {'done': 4, 'total': 48, 'unit': 'campioni'})
            self.assertNotIn('secret-log', json.dumps(status))
            self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
