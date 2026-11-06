"""An assignment issued together with a plan update starts after the plan is recorded."""
import threading
import time
import unittest
from types import SimpleNamespace

try:
    from righaven import tools
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    tools = None


def runtime(call_id, calls):
    message = SimpleNamespace(type='ai', tool_calls=calls)
    return SimpleNamespace(tool_call_id=call_id, state={'messages': [SimpleNamespace(type='human', tool_calls=None), message]})


@unittest.skipIf(tools is None, 'Requires the pinned Gateway tool runtime')
class ParallelPlanTests(unittest.TestCase):
    def test_delegation_waits_for_the_plan_of_the_same_response(self):
        calls = [{'id': 'plan-1', 'name': 'harness_plan'}, {'id': 'work-1', 'name': 'harness_delegate'}]
        order = []

        @tools.signals_plan
        def plan(runtime):
            time.sleep(0.3)
            order.append('plan recorded')

        delegate = threading.Thread(target=lambda: (tools.wait_for_sibling_plans(runtime('work-1', calls)), order.append('assignment started')))
        delegate.start()
        time.sleep(0.05)  # the assignment is already waiting when the plan begins
        plan(runtime=runtime('plan-1', calls))
        delegate.join(5)
        self.assertEqual(order, ['plan recorded', 'assignment started'])

    def test_a_failed_plan_releases_the_assignment_and_unrelated_calls_do_not_wait(self):
        calls = [{'id': 'plan-2', 'name': 'harness_plan'}, {'id': 'work-2', 'name': 'harness_delegate'}]

        @tools.signals_plan
        def plan(runtime):
            raise ValueError('piano rifiutato')
        with self.assertRaises(ValueError):
            plan(runtime=runtime('plan-2', calls))
        started = time.monotonic()
        tools.wait_for_sibling_plans(runtime('work-2', calls))
        self.assertLess(time.monotonic() - started, 1)
        alone = [{'id': 'work-3', 'name': 'harness_delegate'}]
        self.assertEqual(tools.sibling_plan_calls(runtime('work-3', alone)), [])
        self.assertEqual(tools.sibling_plan_calls(SimpleNamespace(tool_call_id=None, state={})), [])

    def test_phase_start_is_ordered_before_its_sibling_assignment(self):
        calls=[{'id':'guided-plan','name':'harness_plan'},{'id':'guided-start','name':'harness_journey'},{'id':'guided-work','name':'harness_delegate'}]
        self.assertEqual(tools.sibling_plan_calls(runtime('guided-work',calls)),['guided-plan','guided-start'])
        self.assertEqual(tools.sibling_plan_calls(runtime('guided-start',calls),names=('harness_plan',)),['guided-plan'])
        @tools.signals_plan
        def finish(runtime):return None
        finish(runtime=runtime('guided-plan',calls))
        order=[]
        worker=threading.Thread(target=lambda:(tools.wait_for_sibling_plans(runtime('guided-work',calls)),order.append('started')))
        worker.start();time.sleep(.05);self.assertEqual(order,[])
        finish(runtime=runtime('guided-start',calls));worker.join(5)
        self.assertEqual(order,['started'])

    def test_the_registered_tool_still_exposes_the_plan_arguments(self):
        self.assertIn('roles_json', tools.harness_plan.args)
        self.assertIn('policies_json', tools.harness_plan.args)


if __name__ == '__main__':
    unittest.main()
