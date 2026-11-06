import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from righaven import experience, lessons, projects
from righaven.lesson_curation import curate, lock
from righaven.production_observations import recent_context
import test_production_observations as fixtures


class GoalLearningTests(unittest.TestCase):
    def setUp(self):
        fixtures.ProductionObservationsTests.setUp(self)
    def test_old_role_failure_does_not_become_the_new_goal(self):
        value=json.loads(self.state.read_text())
        value['steps'][0]['role_id']='old-detail'
        value['roles']=[{'id':'new-edition'}]
        value['steps'].append({'id':'edition','agent':'workspace','role_id':'new-edition','goal':'Whole product','status':'pending','attempts':[]})
        self.assertEqual(recent_context(self.workspace,value),[])
        self.assertTrue(self.report.exists())
        value['roles']=[{'id':'old-detail'}]
        self.assertTrue(recent_context(self.workspace,value))
        value['steps'][0]['attempts'][0]['context']={'contract':'old-contract'}
        self.assertEqual(recent_context(self.workspace,value),[])

    def test_two_failed_previews_require_an_explicit_goal_decision(self):
        result={'ok':True,'output_dir':str(self.output),'handoff':{'output_files':[str(self.product)],
            'checks':[{'name':'Detail','status':'failed','evidence':'Unclear detail'}]}}
        invoke=Mock(return_value=json.dumps(result))
        for i in range(2):
            projects.execute_step(self.workspace,'workspace','Improve detail','checkpoint',invoke,purpose='preview')
        response=json.loads(projects.execute_step(self.workspace,'workspace','Try again','checkpoint',invoke,purpose='preview'))
        self.assertTrue(response['checkpoint_reassessment'])
        self.assertEqual(invoke.call_count,2)
        self.assertIn('obiettivo',response['error'])
        projects.revise_step(self.workspace,'checkpoint','Use a different representative sample to test the actual deliverable')
        projects.execute_step(self.workspace,'workspace','Reframed sample','checkpoint',invoke,purpose='preview')
        self.assertEqual(invoke.call_count,3)
        projects.execute_step(self.workspace,'workspace','Integrate useful components','checkpoint',invoke,purpose='integration')
        self.assertEqual(invoke.call_count,4)

    def test_empty_project_does_not_call_model_or_use_other_chats_sources(self):
        experience.collect(self.workspace,self.library,'other-chat')
        generate=Mock(side_effect=AssertionError('must not call model'))
        empty=self.root/'empty-project'
        projects.create_plan(empty,'A different new project',[])
        outcome=curate(empty,self.library,'this-chat',generate_fn=generate)
        self.assertEqual(outcome['status'],'no_sources')
        generate.assert_not_called()
        data=experience.summary(self.library,source_thread='this-chat')
        self.assertGreater(data['pending'],0)
        self.assertEqual(data['current_project']['meaningful'],0)

    def proposal(self,ids):
        return {'source_ids':ids,'lesson':{'category':'production_method','title':'Reconsider the whole deliverable after repeated local failures',
            'applies_when':'A local checkpoint repeatedly fails without improving the deliverable',
            'procedure':['Compare the detail with the actual requested outcome','Choose a representative sample or another method'],
            'verification':['Check the complete deliverable against user requirements'],
            'limits':'A failed attempt does not prove the alternative will work','tools':[]},
            'impact':{'level':'unknown','basis':'hypothesis','reason':'A repeated failure suggests a decision, not a verified improvement'}}

    def test_curation_saves_individual_proposal_without_approving_it_or_modifying_product(self):
        original=self.product.read_bytes()
        outcome=curate(self.workspace,self.library,'current-chat',generate_fn=lambda sources:
            {'proposals':[self.proposal([sources[0]['id']])],'dismissed':[]})
        self.assertEqual(outcome['saved'],1)
        self.assertFalse(lessons.accepted(self.library))
        self.assertEqual(self.product.read_bytes(),original)
        data=experience.summary(self.library,source_thread='current-chat')
        self.assertEqual(data['current_project']['lesson_ids'],outcome['lesson_ids'])
        self.assertEqual(data['lessons'][0]['approval'],'pending')

    def test_invalid_batch_cannot_save_a_plausible_proposal_before_foreign_source(self):
        def generate(sources):
            return {'proposals':[self.proposal([sources[0]['id']]),self.proposal(['a'*64])],'dismissed':[]}
        with self.assertRaisesRegex(ValueError,'fonti selezionate'):
            curate(self.workspace,self.library,'current-chat',generate_fn=generate)
        self.assertEqual(lessons.entries(self.library),[])

    def test_single_curation_at_a_time_and_dismissal_is_persistent(self):
        with lock(self.library):
            with self.assertRaisesRegex(ValueError,'già in corso'):
                curate(self.workspace,self.library,'current-chat',generate_fn=Mock())
        outcome=curate(self.workspace,self.library,'current-chat',generate_fn=lambda sources:
            {'proposals':[],'dismissed':[{'source_ids':[sources[0]['id']],'reason':'This observation has no transferable causal lesson'}]})
        self.assertEqual(outcome['dismissed'],1)
        self.assertEqual(curate(self.workspace,self.library,'current-chat',generate_fn=Mock())['status'],'no_sources')
