import tempfile,threading,time,unittest
from pathlib import Path

from righaven.resource_slot import ResourceSlot
from righaven.execution_queue import ExecutionQueue
from righaven.progress import create_job,read_status


class ResourceSlotTests(unittest.TestCase):
    def test_preload_yields_only_after_cleanup_then_fifo_chats_then_background_resumes(self):
        slot=ResourceSlot(idle_seconds=.02);queue=ExecutionQueue()
        cancelled=threading.Event();yielded=threading.Event();cleaning=threading.Event();allow_cleanup=threading.Event()
        order=[];errors=[]
        def background():
            try:
                self.assertTrue(slot.acquire_background(cancelled,yielded));order.append('preload')
                self.assertTrue(yielded.wait(3));cleaning.set();self.assertTrue(allow_cleanup.wait(3))
                order.append('removed');slot.release()
                self.assertTrue(slot.acquire_background(cancelled,threading.Event()))
                order.append('resumed');slot.release()
            except BaseException as exc:errors.append(exc)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);first=create_job(root/'one','rh-job-111111111111','wordcraft','codex','test')
            second=create_job(root/'two','rh-job-222222222222','wordcraft','codex','test')
            bg=threading.Thread(target=background);bg.start()
            until=time.monotonic()+2
            while not slot.locked() and time.monotonic()<until:time.sleep(.005)
            def chat(path):
                try:
                    self.assertTrue(queue.acquire(slot,path,root/'state',lambda:False))
                    order.append(path.parent.name);slot.release()
                except BaseException as exc:errors.append(exc)
            workers=[]
            try:
                for path in (first,second):
                    thread=threading.Thread(target=chat,args=(path,));thread.start();workers.append(thread)
                    until=time.monotonic()+2
                    while not read_status(path).get('queue_reason') and time.monotonic()<until:time.sleep(.005)
                self.assertTrue(cleaning.wait(2))
                self.assertEqual(read_status(first)['queue_reason'],'preload')
                self.assertIn('liberando',read_status(first)['queue_detail'])
                self.assertEqual(order,['preload'])
            finally:allow_cleanup.set()
            for worker in workers+[bg]:worker.join(5);self.assertFalse(worker.is_alive())
            self.assertEqual(errors,[])
            self.assertEqual(order,['preload','removed',first.parent.name,second.parent.name,'resumed'])
            self.assertFalse(slot.locked());self.assertEqual(slot.foreground_waiters,0)

    def test_blocking_foreground_requests_including_provider_login_preempt_background(self):
        slot=ResourceSlot(idle_seconds=0);cancel=threading.Event();yielded=threading.Event()
        self.assertTrue(slot.acquire_background(cancel,yielded))
        self.assertFalse(slot.acquire(timeout=.01));self.assertTrue(yielded.is_set())
        slot.release();self.assertTrue(slot.acquire(timeout=.1));slot.release()

    def test_cache_maintenance_does_not_preempt_a_running_compiler(self):
        slot=ResourceSlot(idle_seconds=0);yielded=threading.Event()
        self.assertTrue(slot.acquire_background(threading.Event(),yielded))
        self.assertFalse(slot.acquire_maintenance());self.assertFalse(yielded.is_set())
        slot.release();self.assertTrue(slot.acquire_maintenance());slot.release()

    def test_user_cancel_does_not_restart_background_and_cleanup_failure_blocks_new_admission(self):
        slot=ResourceSlot(idle_seconds=0);cancel=threading.Event();cancel.set()
        self.assertFalse(slot.acquire_background(cancel,threading.Event()))
        self.assertTrue(slot.acquire());slot.quarantine('Cleanup unconfirmed');slot.release()
        self.assertFalse(slot.acquire(timeout=.01));self.assertEqual(slot.waiting_info()['queue_reason'],'cleanup')
        self.assertTrue(slot.locked())

    def test_terminal_requests_preload_cleanup_before_acquiring_and_background_resumes(self):
        slot=ResourceSlot(idle_seconds=.01);yielded=threading.Event()
        self.assertTrue(slot.acquire_background(threading.Event(),yielded))
        results=[]
        terminal=threading.Thread(target=lambda:results.append(slot.acquire_terminal(timeout=2)))
        terminal.start();self.assertTrue(yielded.wait(1))
        self.assertEqual(slot.owner['kind'],'preload');self.assertEqual(results,[])
        slot.release()  # Preparation owns this release, after confirmed container removal.
        terminal.join(2);self.assertFalse(terminal.is_alive());self.assertEqual(results,[True])
        self.assertEqual(slot.waiting_info()['queue_reason'],'terminal')
        self.assertFalse(slot.acquire_maintenance())
        slot.release()
        self.assertTrue(slot.acquire_background(threading.Event(),threading.Event()));slot.release()
        self.assertEqual(slot.foreground_waiters,0)

    def test_terminal_never_interrupts_work_or_bypasses_failed_cleanup(self):
        slot=ResourceSlot(idle_seconds=0)
        self.assertTrue(slot.acquire());started=time.monotonic()
        self.assertFalse(slot.acquire_terminal(timeout=1));self.assertLess(time.monotonic()-started,.2)
        self.assertEqual(slot.owner['kind'],'work');slot.release()
        self.assertTrue(slot.acquire_maintenance());self.assertFalse(slot.acquire_terminal(timeout=1));slot.release()
        slot.quarantine('Unconfirmed removal')
        self.assertFalse(slot.acquire_terminal(timeout=1));self.assertEqual(slot.waiting_info()['queue_reason'],'cleanup')

    def test_terminal_timeout_retains_the_preparers_slot_until_actual_cleanup(self):
        slot=ResourceSlot(idle_seconds=0);yielded=threading.Event()
        self.assertTrue(slot.acquire_background(threading.Event(),yielded))
        self.assertFalse(slot.acquire_terminal(timeout=.01));self.assertTrue(yielded.is_set())
        self.assertEqual(slot.owner['kind'],'preload');self.assertEqual(slot.foreground_waiters,0)
        slot.release()

    def test_a_chat_waiting_during_terminal_preemption_has_priority(self):
        slot=ResourceSlot(idle_seconds=0);yielded=threading.Event();results=[]
        self.assertTrue(slot.acquire_background(threading.Event(),yielded))
        terminal=threading.Thread(target=lambda:results.append(slot.acquire_terminal(timeout=2)))
        terminal.start();self.assertTrue(yielded.wait(1))
        with slot.foreground_request():
            slot.release();terminal.join(2)
            self.assertFalse(terminal.is_alive());self.assertEqual(results,[False])
            self.assertTrue(slot.acquire(blocking=False));self.assertEqual(slot.owner['kind'],'work');slot.release()
        self.assertEqual(slot.foreground_waiters,0)
