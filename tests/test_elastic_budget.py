"""Live CPU borrowing, conservative failure handling and safe memory increases."""
import unittest
from unittest.mock import patch
from righaven.resource_budget import ResourceBudget,BudgetBusy


class ElasticBudgetTests(unittest.TestCase):
    def setUp(self):
        self.limits={'cpus':1.5,'memory_mib':3970,'tmp_mib':512,'threads':2,'max_workers':1}
        self.mock=patch('righaven.resource_budget.runtime_settings.effective',side_effect=lambda:dict(self.limits));self.mock.start();self.addCleanup(self.mock.stop)
        self.physical={};self.calls=[]
        def update(owner,cpu,memory):
            self.calls.append((owner,cpu,memory))
            if owner not in self.physical:return None
            value=self.physical[owner];value['cpus']=cpu
            if memory is not None:value['memory_mib']=memory
            return {**value,'confirmed':True}
        self.budget=ResourceBudget(elastic=True,updater=update)

    def start(self,name,kind='worker'):
        value=self.budget.acquire(name,kind,timeout=0);self.physical[name]=dict(value)
        return value

    def test_serial_worker_borrows_all_idle_cpu_and_control_and_console_reclaim_their_share(self):
        worker=self.start('worker')
        self.assertEqual(worker['cpus'],1.5)
        self.start('model','control');self.assertEqual(self.physical['worker']['cpus'],1.125)
        self.start('console','terminal');self.assertEqual(self.physical['worker']['cpus'],.875)
        self.assertLessEqual(self.budget.snapshot()['allocated_cpus'],1.5)
        self.budget.release('console');self.budget.release('model')
        self.assertEqual(self.physical['worker']['cpus'],1.5)
        self.assertEqual(self.physical['worker']['memory_mib'],worker['memory_mib'])

    def test_serial_preparation_has_the_whole_work_memory_budget_without_a_two_gib_cap(self):
        value=self.start('builder','build')
        self.assertEqual(value['memory_mib'],3202)
        self.assertEqual(value['cpus'],1.5)
        control=self.start('model','control');console=self.start('terminal','terminal')
        self.assertEqual(sum(v['memory_mib'] for v in self.budget.leases.values()),3970)

    def test_new_worker_splits_cpu_then_release_returns_cpu_without_restarting_peer(self):
        self.limits['max_workers']=2
        self.start('first');self.start('second')
        self.assertEqual(self.physical['first']['cpus'],.75)
        self.assertEqual(self.physical['second']['cpus'],.75)
        self.limits['max_workers']=1
        self.budget.rebalance()
        self.assertEqual(self.physical['first']['cpus'],.75)
        with self.assertRaises(BudgetBusy):self.budget.acquire('third','worker',timeout=0)
        self.budget.release('second')
        self.assertEqual(self.physical['first']['cpus'],1.5)
        result=self.budget.rebalance()
        self.assertEqual(result['pending'],0)
        self.assertEqual(self.physical['first']['memory_mib'],3202)
        # More parallel capacity must not lower a running process's memory.
        self.limits['max_workers']=2;self.budget.rebalance()
        self.assertEqual(self.physical['first']['memory_mib'],3202)

    def test_unlaunched_worker_keeps_reservation_and_cannot_be_overcommitted(self):
        self.limits['max_workers']=2
        first=self.budget.acquire('first','worker',timeout=0)
        with self.assertRaises(BudgetBusy):self.budget.acquire('second','worker',timeout=0)
        self.physical['first']=dict(first)
        self.start('second')
        self.assertLessEqual(self.budget.snapshot()['allocated_cpus'],1.5)

    def test_unconfirmed_update_reserves_the_upper_bound_and_reports_pending(self):
        self.start('worker');self.budget.leases['worker']['cpus']=.437
        self.budget.updater=lambda *args:(_ for _ in ()).throw(RuntimeError('Docker unavailable'))
        result=self.budget.rebalance()
        self.assertEqual(result['pending'],1)
        self.assertEqual(self.budget.leases['worker']['cpus'],1.5)
        self.assertTrue(self.budget.leases['worker']['quota_unconfirmed'])
        with self.assertRaises(BudgetBusy):self.budget.acquire('model','control',timeout=0)

    def test_live_progress_overrides_worker_initial_limits_with_confirmed_lease(self):
        import tempfile
        from pathlib import Path
        from righaven.progress import create_job,list_jobs,update
        with tempfile.TemporaryDirectory() as temp,patch('righaven.resource_budget.BUDGET',self.budget):
            root=Path(temp);path=create_job(root,'rh-job-123456abcdef','workspace','codex','fixture')
            self.start('worker');self.budget.observe_progress('worker',path)
            update(path,limits={'cpus':.437,'memory_mib':1601})
            self.assertEqual(list_jobs(root)[0]['limits']['cpus'],1.5)
