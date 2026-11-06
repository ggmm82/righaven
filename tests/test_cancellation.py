import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from righaven.cancellation import call, requested, watch


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_reaches_one_worker_and_waits_for_cleanup_without_losing_saved_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); saved = root / 'source.txt'; ready = threading.Event(); stopped = threading.Event()
            calls = []
            def worker():
                saved.write_text('keep')
                with watch(lambda: calls.append('only-this-job') or stopped.set(), lambda: calls.append('unconfirmed')):
                    ready.set()
                    self.assertTrue(stopped.wait(3), 'Worker was abandoned after cancelling the asyncio task')
                (root/'cleaned').write_text('container removed')
            task = asyncio.create_task(call(worker))
            for _ in range(100):
                if ready.is_set(): break
                await asyncio.sleep(.01)
            self.assertTrue(ready.is_set())
            other = asyncio.create_task(asyncio.sleep(.5, result='unrelated job alive'))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await asyncio.wait_for(task,3)
            self.assertEqual(saved.read_text(),'keep')
            self.assertTrue((root/'cleaned').exists())
            self.assertEqual(calls,['only-this-job'])
            self.assertEqual(await other,'unrelated job alive')

    async def test_normal_completion_and_disconnect_without_cancellation_do_not_stop_worker(self):
        stopped = []
        def worker():
            self.assertFalse(requested())
            with watch(lambda: stopped.append(True), lambda: stopped.append('failure')):
                return 'completed'
        self.assertEqual(await call(worker),'completed')
        self.assertEqual(stopped,[])
