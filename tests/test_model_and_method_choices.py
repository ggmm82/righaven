import unittest

from righaven.codex_compat import modernize_codex_payload
from righaven.strategy import check_capability_choice


class ModelAndMethodChoicesTests(unittest.TestCase):
    def test_native_agent_no_thinking_uses_supported_minimum_without_mutation(self):
        for model in ('gpt-6.1-sol', 'gpt-6.1-sol-2026-10-01'):
            original = {'model': model, 'reasoning': {'effort': 'none', 'summary': 'detailed'}}
            result = modernize_codex_payload(original)
            self.assertEqual(result['reasoning'], {'effort': 'low', 'summary': 'detailed'})
            self.assertEqual(original['reasoning']['effort'], 'none')

    def test_other_models_and_explicit_supported_levels_are_preserved(self):
        for model, effort in [('gpt-5.4', 'none')] + [('gpt-6.1-sol', e) for e in ('low','medium','high','xhigh','max')]:
            payload = {'model': model, 'reasoning': {'effort': effort}}
            self.assertEqual(modernize_codex_payload(payload)['reasoning'], payload['reasoning'])
        self.assertNotIn('reasoning', modernize_codex_payload({'model': 'gpt-6.1-sol'}))

    def test_excluded_app_cannot_establish_a_blocker_without_available_method_assessment(self):
        policy = {'allowed': ['freecad', 'effectcraft'], 'blocked': ['blender']}
        strategy = {'state': 'needs_user', 'stop_reason': 'capability_limit', 'alternatives': []}
        with self.assertRaisesRegex(ValueError, 'scelta dell’utente'):
            check_capability_choice(strategy, policy)
        strategy['alternatives'] = [{'tools':['blender'], 'status':'unavailable'}]
        with self.assertRaises(ValueError):
            check_capability_choice(strategy, policy)
        strategy['alternatives'] = [{'tools':['freecad'], 'status':'candidate'}]
        with self.assertRaises(ValueError):
            check_capability_choice(strategy, policy)
        strategy['alternatives'][0]['status'] = 'unavailable'
        check_capability_choice(strategy, policy)

    def test_generic_exclusions_and_genuine_limits_remain_supported(self):
        for blocked, allowed in [('soundcraft','fluidsynth'),('blender','freecad')]:
            policy = {'blocked':[blocked], 'allowed':[allowed]}
            with self.assertRaisesRegex(ValueError, 'disabilitati'):
                check_capability_choice({'alternatives':[{'tools':[blocked], 'status':'candidate'}]}, policy)
            check_capability_choice({'state':'selected','alternatives':[{'tools':[allowed], 'status':'candidate'}]}, policy)
            check_capability_choice({'state':'needs_user','stop_reason':'missing_input'}, policy)
        check_capability_choice({'state':'needs_user','stop_reason':'capability_limit'}, {'allowed':[], 'blocked':[]})
