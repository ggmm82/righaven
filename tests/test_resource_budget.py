import threading
import unittest
from unittest.mock import patch
from righaven.resource_budget import ResourceBudget
from righaven.resource_slot import ResourceSlot


class ResourceBudgetTests(unittest.TestCase):
    def test_live_limit_changes_preserve_active_leases_and_admit_waiters_safely(self):
        limits={'cpus':4,'memory_mib':4096,'tmp_mib':1024,'threads':4,'max_workers':2}
        with patch('righaven.resource_budget.runtime_settings.effective',side_effect=lambda:dict(limits)):
            first=self.budget.acquire('private-account-first','build')
            second=self.budget.acquire('private-account-second','build')
            limits['max_workers']=1
            self.assertEqual(self.budget.snapshot()['configured_limit'],1)
            self.assertEqual(self.budget.snapshot()['active']['build'],2)
            self.assertNotIn('private-account',str(self.budget.snapshot()))
            with self.assertRaises(RuntimeError):self.budget.acquire('third','build',timeout=0)
            self.assertEqual(self.budget.snapshot()['waiting']['build'],0)
            self.assertEqual(self.budget.leases['private-account-first']['memory_mib'],first['memory_mib'])
            self.budget.release('private-account-second')
            with self.assertRaises(RuntimeError):self.budget.acquire('third','build',timeout=0)
            limits['max_workers']=2
            results=[]
            thread=threading.Thread(target=lambda:results.append(self.budget.acquire('third','build',timeout=2)))
            thread.start();thread.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(len(results),1)
            monitor=self.budget.snapshot()
            self.assertLessEqual(monitor['allocated_memory_mib'],limits['memory_mib'])
            self.assertLessEqual(monitor['allocated_cpus'],limits['cpus'])
            self.budget.release('private-account-first');self.budget.release('third')

    def test_monitor_reports_budget_wait_and_removes_cancelled_waiter(self):
        import time
        self.budget.acquire('first','worker')
        cancelled=threading.Event();errors=[]
        def wait():
            try:self.budget.acquire('second','build',cancel=cancelled)
            except RuntimeError as error:errors.append(str(error))
        thread=threading.Thread(target=wait);thread.start()
        try:
            deadline=time.monotonic()+2
            while not self.budget.snapshot()['waiting']['build'] and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(self.budget.snapshot()['waiting']['build'],1)
            cancelled.set();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertIn('annullata',errors[0])
            self.assertEqual(self.budget.snapshot()['waiting']['build'],0)
        finally:cancelled.set();self.budget.release('first');thread.join(2)

    def setUp(self):
        value={'cpus':4,'memory_mib':6144,'tmp_mib':1024,'threads':4,'max_workers':1}
        mock=patch('righaven.resource_budget.runtime_settings.effective',return_value=value);mock.start();self.addCleanup(mock.stop)
        self.budget=ResourceBudget()

    def test_three_lanes_stay_within_total_and_console_is_always_available(self):
        builder=self.budget.acquire('compiler','build')
        with self.assertRaisesRegex(RuntimeError,'occupato'):self.budget.acquire('job','worker',timeout=0)
        self.budget.release('compiler')
        worker=self.budget.acquire('job','worker')
        terminal=self.budget.acquire('console','terminal')
        self.assertLessEqual(sum(x['memory_mib'] for x in (worker,terminal)),6144)
        self.assertLessEqual(sum(x['cpus'] for x in (worker,terminal)),4)
        self.assertEqual(terminal['memory_mib'],256)
        self.budget.release('console')
        self.assertIn('job',self.budget.leases);self.assertNotIn('compiler',self.budget.leases)

    def test_insufficient_memory_wait_is_cancellable_and_cleanup_failure_blocks_all_lanes(self):
        self.budget.acquire('worker','worker')
        cancel=threading.Event();cancel.set()
        with self.assertRaisesRegex(RuntimeError,'annullata'):self.budget.acquire('build','build',cancel=cancel)
        with self.assertRaisesRegex(RuntimeError,'occupato'):self.budget.acquire('build','build',timeout=0)
        self.budget.quarantine('cleanup failed');self.budget.release('worker')
        with self.assertRaisesRegex(RuntimeError,'cleanup failed'):self.budget.acquire('console','terminal')

    def test_one_worker_only_but_terminal_and_build_do_not_own_worker_queue(self):
        worker,build,terminal=(ResourceSlot() for _ in range(3))
        self.assertTrue(worker.acquire());self.assertFalse(worker.acquire(blocking=False))
        self.assertTrue(build.acquire());self.assertTrue(terminal.acquire_terminal())
        terminal.release();self.assertTrue(worker.locked());self.assertTrue(build.locked())
        build.release();worker.release()

    def test_waiting_for_preparation_lane_can_be_cancelled_without_releasing_active_builder(self):
        from righaven.environment_runtime import preparation_slot
        slot=ResourceSlot();self.assertTrue(slot.acquire())
        cancelled=threading.Event();cancelled.set()
        with self.assertRaisesRegex(RuntimeError,'annullata'):
            with preparation_slot(slot,True,cancelled,None):self.fail('Cancelled builder admitted')
        self.assertTrue(slot.locked());slot.release()

    def test_ready_environment_bypasses_preparation_queue_and_is_pinned_until_worker_cleanup(self):
        import tempfile
        from pathlib import Path
        from righaven import environment_runtime as factory, state, docker_runtime
        record={'id':'a'*64,'status':'ready','tools':['d2'],'image':'prepared','image_id':'sha256:ready'}
        slot=ResourceSlot();self.assertTrue(slot.acquire())
        with tempfile.TemporaryDirectory() as temporary, patch.object(state,'STATE',Path(temporary)), \
             patch.object(factory,'recipe',return_value=(record['id'],{'tools':['d2']})), \
             patch.object(factory,'read',return_value=record),patch.object(factory,'image_exists',return_value=True), \
             patch.object(factory,'save',side_effect=lambda key,**kwargs:{**record,**kwargs}), \
             patch.object(docker_runtime,'BUILD_LOCK',slot):
            ready=factory.ensure(['d2'],claim='job-before-docker-start')
            try:
                self.assertEqual(ready['image_id'],'sha256:ready')
                self.assertEqual(factory._CLAIMS['job-before-docker-start'],record['id'])
                with patch.object(factory,'pinned',return_value=set(factory._CLAIMS.values())):
                    with self.assertRaisesRegex(ValueError,'assegnato'):factory.evict(record['id'])
            finally:factory.release_claim('job-before-docker-start')
        self.assertTrue(slot.locked());slot.release()

    def test_cli_coordinator_can_request_preload_yield_when_budget_is_full(self):
        from righaven import docker_runtime
        slot=ResourceSlot(idle_seconds=0);yielded=threading.Event()
        self.assertTrue(slot.acquire_background(threading.Event(),yielded))
        self.budget.acquire('occupant','worker');results=[]
        with patch.object(docker_runtime,'BUILD_LOCK',slot),patch('righaven.resource_budget.BUDGET',self.budget):
            thread=threading.Thread(target=lambda:results.append(docker_runtime.worker_resources('coordinator')))
            thread.start()
            try:
                self.assertTrue(yielded.wait(1))
                self.assertEqual(results,[])
                self.budget.release('occupant');slot.release()
                thread.join(2);self.assertFalse(thread.is_alive())
                self.assertTrue(results)
            finally:
                self.budget.release('occupant');self.budget.release('coordinator')
