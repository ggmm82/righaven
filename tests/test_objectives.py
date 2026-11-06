"""A recipe initializes work; new objectives reuse results without old gates or acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import objectives,journeys,projects,state
from righaven.project_store import locked,load


class ObjectiveTests(unittest.TestCase):
    def test_new_objective_archives_recipe_and_keeps_real_files_without_revalidating_them(self):
        with tempfile.TemporaryDirectory() as directory, patch('righaven.connections._read',side_effect=ValueError('Missing fixture connection')):
            root=Path(directory);output=root/'outputs';output.mkdir();product=output/'dashboard.html';product.write_text('<h1>Prior delivery</h1>')
            journey=journeys.start(root,'data-pipeline',{'goal':'A simple dashboard'},mode='first_result')
            projects.create_plan(root,'A simple dashboard',[])
            projects.sync_acceptance(root,['A simple dashboard','Use sample data'])
            with locked(root) as folder:
                old=load(folder,root);old['product_path']='/mnt/user-data/outputs/dashboard.html';old['status']='ready'
                old['policy_validation']={'status':'passed'}
                old['connections']={'owner':'alice','ids':['warehouse'],'write':['warehouse']}
                state.atomic_json(folder/'project.json',old)
            current=objectives.view(root)
            changed=objectives.redirect(root,'Use this dashboard as the base for a customer portal',current['signature'],'human-new',
                                        ['A simple dashboard','Use sample data','Use this dashboard as the base for a customer portal'])
            self.assertTrue(changed['changed']);self.assertIsNone(journeys.view(root))
            new=projects.read_project(root);self.assertNotEqual(new['id'],old['id'])
            self.assertFalse(new.get('product_path'));self.assertNotEqual(new.get('quality_status'),'passed')
            self.assertEqual(new['scope']['parent']['product_path'],'/mnt/user-data/outputs/dashboard.html')
            self.assertTrue(product.exists());self.assertEqual(product.read_text(),'<h1>Prior delivery</h1>')
            with locked(root) as folder:
                raw=load(folder,root);self.assertEqual(raw['connections']['write'],[])
                self.assertNotIn('policy_validation',raw);self.assertNotIn('strategy',raw)
                self.assertFalse(raw['checkpoints']['enabled'])
                snapshot=json.loads((folder/'objective-history'/f"{old['id']}.json").read_text())
                self.assertEqual(snapshot['journey']['recipe_id'],'data-pipeline')
                # Simulate interruption before the obsolete journey file was removed.
                state.atomic_json(folder/'journey.json',snapshot['journey'])
            self.assertIsNone(journeys.view(root),'An obsolete journey cannot reactivate after restart')
            # Old native message history is not inherited as new requirements.
            projects.sync_acceptance(root,['A simple dashboard','Use sample data','Use this dashboard as the base for a customer portal','Keep the brand colors'])
            accepted=projects.read_project(root)['acceptance']['user_requests']
            self.assertEqual(accepted,['Use this dashboard as the base for a customer portal','Keep the brand colors'])
            # A lost response can be retried without another archive/new project.
            repeated=objectives.redirect(root,'Use this dashboard as the base for a customer portal',current['signature'],'human-new')
            self.assertFalse(repeated['changed']);self.assertEqual(repeated['project_id'],changed['project_id'])
            # A compacted graph can omit the transition message; the scope still anchors its goal.
            projects.sync_acceptance(root,['A simple dashboard','Add search'])
            accepted=projects.read_project(root)['acceptance']['user_requests']
            self.assertNotIn('A simple dashboard',accepted);self.assertIn('Add search',accepted)

    def test_active_stale_controls_and_missing_projects_do_not_change_objective(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(ValueError,'first project'):objectives.redirect(root,'New result','0'*64)
            projects.create_plan(root,'First result',[{'id':'build','agent':'workspace','goal':'Build a result','depends_on':[]}])
            current=objectives.view(root)
            with self.assertRaisesRegex(ValueError,'changed'):objectives.redirect(root,'New result','0'*64)
            with locked(root) as folder:
                p=load(folder,root);p['steps'][0].update(status='running',attempts=[{'status':'running','gateway_session':__import__('righaven.project_store',fromlist=['GATEWAY_SESSION']).GATEWAY_SESSION}]);state.atomic_json(folder/'project.json',p)
            current=objectives.view(root)
            with self.assertRaisesRegex(ValueError,'active work'):objectives.redirect(root,'New result',current['signature'])
            from righaven.project_controls import RESUME_INSTRUCTIONS
            for control in RESUME_INSTRUCTIONS:
                with self.assertRaisesRegex(ValueError,'continuation controls'):objectives.redirect(root,control,current['signature'])
