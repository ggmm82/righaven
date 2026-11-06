import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from righaven.execution_queue import ExecutionQueue, recover_waiters
from righaven.progress import create_job, read_status


class ExecutionQueueTests(unittest.TestCase):
    def test_fifo_across_conversations_survives_long_wait_and_cancel_does_not_release_active_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); slot = threading.Lock(); slot.acquire()
            queue = ExecutionQueue(); order = []; errors = []
            paths = [create_job(root / ('chat'+str(i)), 'rh-job-'+format(i,'012x'), 'workspace','codex','test') for i in range(1,4)]
            def worker(path):
                try:
                    if queue.acquire(slot,path,root/'state',lambda:False):
                        try:order.append(path.parent.name)
                        finally:slot.release()
                except BaseException as e:errors.append(e)
            threads=[]
            for index,path in enumerate(paths):
                thread=threading.Thread(target=worker,args=(path,));thread.start();threads.append(thread)
                for _ in range(100):
                    if read_status(path).get('queue_position') == index+1:break
                    time.sleep(.01)
                self.assertEqual(read_status(path).get('queue_position'),index+1)
            # The original two-minute cap no longer applies, even though the
            # shared slot remains owned by a different conversation.
            with patch('righaven.execution_queue.time.monotonic',return_value=time.monotonic()+300):
                time.sleep(.3)
                self.assertEqual(read_status(paths[0])['phase'],'queued')
            self.assertEqual(len(list((root/'state/execution-queue').glob('*.json'))),3)
            self.assertTrue(queue.cancel(paths[1]))
            threads[1].join(2);self.assertFalse(threads[1].is_alive())
            self.assertTrue(slot.locked());self.assertEqual(order,[])
            self.assertTrue(read_status(paths[1])['resources_reclaimed'])
            slot.release()
            for thread in threads:thread.join(3);self.assertFalse(thread.is_alive())
            self.assertEqual(errors,[])
            self.assertEqual(order,[paths[0].parent.name,paths[2].parent.name])
            self.assertFalse(list((root/'state/execution-queue').glob('*.json')))
            self.assertFalse(slot.locked())

    def test_restart_marks_lost_waiter_recoverable_without_launching_or_claiming_a_container(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);progress=create_job(root/'chat','rh-job-123456abcdef','workspace','codex','test')
            tickets=root/'state/execution-queue';tickets.mkdir(parents=True)
            (tickets/'rh-job-123456abcdef.json').write_text(json.dumps({'progress':str(progress)}))
            recover_waiters(root/'state')
            status=read_status(progress)
            self.assertEqual(status['error_code'],'queue_restart')
            self.assertTrue(status['resources_reclaimed'])
            self.assertIsNone(status['started_at'])
            self.assertFalse(list(tickets.glob('*.json')))

    def test_failed_starting_telemetry_releases_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);progress=create_job(root/'chat','rh-job-123456abcdef','workspace','codex','test')
            slot=threading.Lock()
            from righaven.progress import update
            def fail(path,phase=None,**fields):
                if phase=='starting':raise OSError('disk failure')
                return update(path,phase,**fields)
            with patch('righaven.execution_queue.update',side_effect=fail):
                with self.assertRaises(OSError):ExecutionQueue().acquire(slot,progress,root/'state',lambda:False)
            self.assertFalse(slot.locked())
