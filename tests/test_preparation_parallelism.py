"""Parallel preparation, shared recipes and independent console reclamation."""
import tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from righaven.preparation_slots import PreparationSlots,TerminalSlots
from righaven.resource_budget import ResourceBudget,BudgetBusy
from righaven import environment_runtime as factory,state

LIMITS={'cpus':4,'memory_mib':4096,'max_workers':2,'threads':4,'tmp_mib':512}


class ParallelPreparationTests(unittest.TestCase):
    def test_two_builds_and_two_consoles_fit_total_budget_without_a_third_heavy_job(self):
        budget=ResourceBudget()
        with patch('righaven.runtime_settings.effective',return_value=LIMITS):
            first=budget.acquire('first','build',timeout=0);second=budget.acquire('second','build',timeout=0)
            terminals=[budget.acquire(name,'terminal',timeout=0) for name in ('shell1','shell2')]
            control=budget.acquire('coordinator','control',timeout=0)
            self.assertLessEqual(sum(v['memory_mib'] for v in [first,second,*terminals,control]),4096)
            self.assertLessEqual(sum(v['cpus'] for v in [first,second,*terminals,control]),4)
            with self.assertRaises(BudgetBusy):budget.acquire('third','worker',timeout=0)
            budget.release('first');budget.acquire('worker','worker',timeout=0)
            self.assertIn('second',budget.leases);self.assertIn('shell2',budget.leases)

    def test_parallel_build_slots_and_exclusive_maintenance(self):
        pool=PreparationSlots();entered=threading.Barrier(3);release=threading.Event();errors=[]
        def work():
            try:
                self.assertTrue(pool.acquire(timeout=1));entered.wait(2);release.wait(2);pool.release()
            except BaseException as e:errors.append(e)
        with patch('righaven.runtime_settings.effective',return_value=LIMITS):
            threads=[threading.Thread(target=work) for _ in range(2)]
            for t in threads:t.start()
            try:
                entered.wait(2);self.assertFalse(pool.acquire(blocking=False));self.assertFalse(pool.acquire_maintenance())
            finally:release.set()
            for t in threads:t.join(2)
            self.assertFalse(errors,errors);self.assertFalse(pool.locked())
            self.assertTrue(pool.acquire_maintenance());self.assertFalse(pool.acquire(blocking=False));pool.release()

    def test_pressure_yields_all_preloads_but_no_slot_is_released_before_cleanup(self):
        pool=PreparationSlots();entered=threading.Barrier(3);release=threading.Event();events=[threading.Event(),threading.Event()]
        def work(event):
            self.assertTrue(pool.acquire_background(threading.Event(),event));entered.wait(2);release.wait(2);pool.release()
        with patch('righaven.runtime_settings.effective',return_value=LIMITS):
            threads=[threading.Thread(target=work,args=(e,)) for e in events]
            for t in threads:t.start()
            entered.wait(2)
            try:
                with pool.foreground_request():
                    self.assertTrue(all(e.is_set() for e in events));self.assertEqual(len(pool.owners),2)
            finally:release.set()
            for t in threads:t.join(2)
            self.assertFalse(pool.locked())

    def test_shared_recipe_waits_without_serializing_an_unrelated_image(self):
        first=threading.Event();second=threading.Event();independent=threading.Event();release=threading.Event()
        def owner():
            with factory.recipe_slot('same',None):first.set();release.wait(2)
        def same():
            with factory.recipe_slot('same',None):second.set()
        def other():
            with factory.recipe_slot('different',None):independent.set()
        a=threading.Thread(target=owner);a.start();self.assertTrue(first.wait(1))
        b=threading.Thread(target=same);c=threading.Thread(target=other);b.start();c.start()
        try:self.assertTrue(independent.wait(1));self.assertFalse(second.is_set())
        finally:release.set()
        for t in (a,b,c):t.join(2)
        self.assertTrue(second.is_set());self.assertFalse(factory._RECIPE_LOCKS)

    def test_multiple_terminal_slots_can_be_released_by_pty_monitor_threads(self):
        pool=TerminalSlots()
        with patch('righaven.runtime_settings.effective',return_value=LIMITS):
            self.assertTrue(pool.acquire_terminal(timeout=0));self.assertTrue(pool.acquire_terminal(timeout=0))
            self.assertFalse(pool.acquire_terminal(timeout=0))
            t=threading.Thread(target=pool.release);t.start();t.join(1)
            self.assertTrue(pool.locked());self.assertTrue(pool.acquire_terminal(timeout=0))
            pool.release();pool.release();self.assertFalse(pool.locked())
